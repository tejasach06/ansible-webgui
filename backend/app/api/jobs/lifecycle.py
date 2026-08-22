import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from git import Repo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.jobs.schemas import ApproveRequest, JobRequest, RelaunchRequest
from app.core.config import settings
from app.core.rbac import get_user_permissions
from app.core.time import utcnow
from app.db.models import (
    Credential,
    CredentialKind,
    HostResultStatus,
    Inventory,
    JobHostResult,
    JobMode,
    JobRun,
    JobStatus,
    JobTemplate,
    PipelineRun,
    PipelineStatus,
    PipelineStep,
    Playbook,
    Project,
    ProjectMembership,
    User,
)
from app.db.session import get_db
from app.services.approvals import approve_job_run, freeze_params_snapshot
from app.services.audit import audit
from app.services.content import get_inventory_repo_path, get_project_repo_path
from app.services.credentials import encrypt_payload
from app.services.job_access import load_job_for_perm
from app.services.launch import resolve_launch
from app.services.rbac_scope import assert_project_perm, inventory_visible_to_project, role_name
from app.services.surveys import apply_survey
from app.tasks.run_job import run_job

router = APIRouter()


@router.post("")
async def request_job(
    req: JobRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    template = None
    if req.template_id:
        template = (await db.execute(select(JobTemplate).where(JobTemplate.id == req.template_id))).scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=404, detail={"code": "template_not_found", "message": "Template not found"})

    playbook_id = req.playbook_id or (template.playbook_id if template else None)
    if not playbook_id:
        raise HTTPException(status_code=422, detail={"code": "playbook_required", "message": "playbook_id or template_id is required"})

    playbook = (await db.execute(select(Playbook).where(Playbook.id == playbook_id))).scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail={"code": "playbook_not_found", "message": "Playbook not found"})
    if template is None:
        global_perms = get_user_permissions(user.roles)
        if "system.admin" not in global_perms:
            res = await db.execute(select(ProjectMembership).where(ProjectMembership.project_id == playbook.project_id, ProjectMembership.user_id == user.id))
            membership = res.scalar_one_or_none()
            role_str = role_name(membership.role) if membership else ""
            if role_str != "owner":
                raise HTTPException(status_code=403, detail={"code": "adhoc_forbidden", "message": "Ad-hoc runs require project admin"})
    else:
        req_mode = req.mode or JobMode.live
        perm = "job.run_check" if req_mode == JobMode.check else "job.request"
        await assert_project_perm(db, user, playbook.project_id, perm)

    survey_vars = set()
    secret_vars = {}
    if template and template.survey_spec:
        try:
            plain_vars, secret_vars = apply_survey(template.survey_spec, req.survey_answers)
            survey_vars = set(plain_vars.keys()) | set(secret_vars.keys())
        except ValueError as e:
            raise HTTPException(status_code=422, detail={"code": str(e), "message": str(e)}) from None

    try:
        effective, overrides = resolve_launch(template, req, survey_vars)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("override_not_allowed:"):
            fields = [f.strip() for f in msg.split(":", 1)[1].split(",") if f.strip()]
            raise HTTPException(status_code=422, detail={"code": "override_not_allowed", "message": "Field not permitted at launch", "fields": fields}) from None
        raise

    inventory_id = effective["inventory_id"]
    if not inventory_id:
        project_row = (await db.execute(select(Project).where(Project.id == playbook.project_id))).scalar_one_or_none()
        inventory_id = project_row.default_inventory_id if project_row else None
    if not inventory_id:
        raise HTTPException(status_code=422, detail={"code": "inventory_required", "message": "No inventory given and this project has no default inventory"})
    inventory = (await db.execute(select(Inventory).where(Inventory.id == inventory_id))).scalar_one_or_none()
    if not inventory:
        raise HTTPException(status_code=404, detail={"code": "inventory_not_found", "message": "Inventory not found"})
    if not inventory_visible_to_project(inventory, playbook.project_id):
        raise HTTPException(status_code=422, detail={"code": "inventory_not_in_project", "message": "That inventory belongs to another project"})
    cred_ids = effective["credential_ids"]
    if cred_ids:
        rows = (await db.execute(
            select(Credential.name, Credential.username, Credential.project_id, Credential.kind, Credential.become_same_as_ssh)
            .where(Credential.id.in_(cred_ids))
        )).all()
        user_rows = [(name, username) for name, username, _, _, _ in rows if username is not None]
        usernames = {username for _, username in user_rows}
        if len(usernames) > 1:
            raise HTTPException(status_code=422, detail={"code": "credential_user_conflict", "message": "Multiple selected credentials set different usernames", "credentials": [name for name, _ in user_rows]})

        offending = [name for name, _, pid, _, _ in rows if pid != playbook.project_id]
        if offending:
            raise HTTPException(status_code=422, detail={"code": "credential_not_in_project", "message": "That credential belongs to another project", "credentials": offending})

        has_become_same = any(become_same for _, _, _, _, become_same in rows)
        has_become_pass = any(kind == CredentialKind.become_password for _, _, _, kind, _ in rows)
        if has_become_same and has_become_pass:
            raise HTTPException(status_code=422, detail={"code": "become_password_conflict", "message": "Selected credential already reuses the SSH password for become; remove the separate become password credential"})
    project = (await db.execute(select(Project).where(Project.id == playbook.project_id))).scalar_one_or_none()
    repo_path = get_project_repo_path(project.name)
    repo = Repo(repo_path)
    git_sha = repo.head.commit.hexsha
    inventory_repo_path = get_inventory_repo_path()
    if not (inventory_repo_path / ".git").exists():
        raise HTTPException(status_code=404, detail={"code": "inventory_repo_missing", "message": "Shared inventory repo is not initialized. Restart the API."})
    inventory_git_sha = Repo(inventory_repo_path).head.commit.hexsha

    mode_val = effective["mode"]
    if req.template_id and mode_val == JobMode.live:
        active = (await db.execute(
            select(JobRun).where(
                JobRun.template_id == req.template_id,
                JobRun.mode == JobMode.live,
                JobRun.status.in_([JobStatus.queued, JobStatus.running])
            )
        )).scalars().all()
        if active:
            raise HTTPException(status_code=409, detail={"code": "template_busy", "message": "Template has a queued/running live run"})

    requires_appr = template.requires_approval if template else True
    mode_status = JobStatus.pending_approval
    if mode_val == JobMode.check or not requires_appr:
        mode_status = JobStatus.queued

    extra_vars = effective["extra_vars"]
    if template and template.survey_spec and secret_vars:
        extra_vars = {**extra_vars, **{k: "$encrypted$" for k in secret_vars}}

    snapshot = freeze_params_snapshot(
        project_git_path=str(repo_path),
        playbook_rel_path=playbook.rel_path,
        inventory_rel_path=inventory.rel_path,
        mode=mode_val.value if hasattr(mode_val, "value") else str(mode_val),
        limit=effective["limit"],
        tags=effective["tags"],
        skip_tags=effective["skip_tags"],
        extra_vars=extra_vars,
        verbosity=effective["verbosity"],
        forks=effective["forks"],
        become=effective["become"],
        become_user=effective["become_user"],
        become_method=effective["become_method"],
        diff=effective["diff"],
        credential_ids=effective["credential_ids"],
        git_sha=git_sha,
        inventory_git_sha=inventory_git_sha,
        overrides=overrides,
    )

    job = JobRun(
        template_id=req.template_id,
        playbook_id=playbook.id,
        inventory_id=inventory.id,
        mode=mode_val,
        status=mode_status,
        requested_by=user.id,
        params_snapshot=snapshot,
        survey_secrets_enc=encrypt_payload(json.dumps(secret_vars)) if secret_vars else None
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await audit(db, "job_requested", actor_user_id=user.id, object_type="job_run", object_id=job.id, detail={"mode": req.mode})
    if mode_status == JobStatus.pending_approval:
        from app.tasks.notify import send_notification
        send_notification.delay("approval_needed", {"event": "approval_needed", "job_id": job.id, "mode": job.mode.value, "template_id": job.template_id, "requested_by": user.id})

    if mode_status == JobStatus.queued:
        task = run_job.delay(job.id)
        job.celery_task_id = task.id
        await db.commit()

    return {"id": job.id, "status": job.status, "mode": job.mode}

@router.post("/{job_id}/relaunch")
async def relaunch_job(
    job_id: int,
    req: RelaunchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    source, _ = await load_job_for_perm(db, user, job_id, "job.request")
    if source.status not in {JobStatus.successful, JobStatus.failed, JobStatus.canceled, JobStatus.timed_out}:
        raise HTTPException(status_code=409, detail={"code": "bad_state", "message": "Source run has not finished"})
    snapshot = dict(source.params_snapshot or {})
    mode = req.mode or source.mode
    if req.hosts == "failed":
        res = await db.execute(
            select(JobHostResult.host)
            .where(
                JobHostResult.job_run_id == source.id,
                JobHostResult.status.in_([HostResultStatus.failed, HostResultStatus.unreachable]),
                JobHostResult.ignore_errors.is_(False),
            )
            .distinct()
        )
        failed_hosts = list(res.scalars().all())
        if not failed_hosts:
            raise HTTPException(status_code=409, detail={"code": "no_failed_hosts", "message": "No failed hosts"})
        snapshot["limit"] = ",".join(failed_hosts)
    snapshot["mode"] = mode.value
    if source.template_id and mode == JobMode.live:
        active = (await db.execute(select(JobRun).where(JobRun.template_id == source.template_id, JobRun.mode == JobMode.live, JobRun.status.in_([JobStatus.queued, JobStatus.running])))).scalars().all()
        if active:
            raise HTTPException(status_code=409, detail={"code": "template_busy", "message": "Template has a queued/running live run"})
    tmpl = (await db.execute(select(JobTemplate).where(JobTemplate.id == source.template_id))).scalar_one_or_none() if source.template_id else None
    requires_appr = tmpl.requires_approval if tmpl else True
    mode_status = JobStatus.queued if mode == JobMode.check or not requires_appr else JobStatus.pending_approval
    job = JobRun(template_id=source.template_id, playbook_id=source.playbook_id, inventory_id=source.inventory_id, mode=mode, status=mode_status, requested_by=user.id, params_snapshot=snapshot, survey_secrets_enc=source.survey_secrets_enc, relaunch_of_id=source.id)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    await audit(db, "job_relaunched", actor_user_id=user.id, object_type="job_run", object_id=job.id, detail={"source_job_id": source.id, "hosts": req.hosts})
    if mode_status == JobStatus.pending_approval:
        from app.tasks.notify import send_notification
        send_notification.delay("approval_needed", {"event": "approval_needed", "job_id": job.id, "mode": job.mode.value, "template_id": job.template_id, "requested_by": user.id})
    if mode_status == JobStatus.queued:
        task = run_job.delay(job.id)
        job.celery_task_id = task.id
        await db.commit()
    return {"id": job.id, "status": job.status, "mode": job.mode}


@router.post("/{job_id}/approve")
async def approve_job(
    job_id: int,
    req: ApproveRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    job, _ = await load_job_for_perm(db, user, job_id, "job.approve")

    note = (req.approval_note or "").strip() if req else ""
    if not note:
        raise HTTPException(status_code=422, detail={"code": "approval_note_required", "message": "An approval note is required"})
    try:
        job = await approve_job_run(db, job, user.id, note)
    except ValueError as e:
        err_code = str(e)
        if err_code == "self_approval_forbidden":
            raise HTTPException(status_code=409, detail={"code": "self_approval_forbidden", "message": "Cannot approve own job run"}) from None
        if err_code == "bad_state":
            raise HTTPException(status_code=409, detail={"code": "bad_state", "message": "Job is not in pending_approval state"}) from None
        raise HTTPException(status_code=400, detail={"code": "error", "message": str(e)}) from None

    if job.pipeline_run_id:
        step = (await db.execute(select(PipelineStep).where(PipelineStep.id == job.pipeline_step_id))).scalar_one_or_none()
        resume_pos = step.position if step else 0
        from app.tasks.run_pipeline import run_pipeline
        task = run_pipeline.delay(job.pipeline_run_id, resume_from=resume_pos)
        job.celery_task_id = task.id
        await db.commit()
    else:
        task = run_job.delay(job.id)
        job.celery_task_id = task.id
        await db.commit()

    await audit(db, "job_approved", actor_user_id=user.id, object_type="job_run", object_id=job.id, detail={"approval_note": note})
    return {"id": job.id, "status": job.status}


@router.post("/{job_id}/reject")
async def reject_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    job, _ = await load_job_for_perm(db, user, job_id, "job.approve")

    if job.status != JobStatus.pending_approval:
        raise HTTPException(status_code=409, detail={"code": "bad_state", "message": "Job is not in pending_approval state"})

    job.status = JobStatus.rejected
    if job.pipeline_run_id:
        prun = (await db.execute(select(PipelineRun).where(PipelineRun.id == job.pipeline_run_id))).scalar_one_or_none()
        if prun:
            prun.status = PipelineStatus.failed
            prun.finished_at = utcnow()
    await db.commit()
    await audit(db, "job_rejected", actor_user_id=user.id, object_type="job_run", object_id=job.id)
    return {"id": job.id, "status": job.status}


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    job, _ = await load_job_for_perm(db, user, job_id, "job.cancel")
    if job.status in (
        JobStatus.successful,
        JobStatus.failed,
        JobStatus.canceled,
        JobStatus.timed_out,
        JobStatus.rejected,
    ):
        raise HTTPException(status_code=409, detail={"code": "bad_state", "message": "Job is already finished"})


    r = aioredis.from_url(settings.REDIS_URL)
    await r.set(f"job:{job.id}:cancel", "1")

    if job.status in (JobStatus.pending_approval, JobStatus.approved, JobStatus.queued):
        if job.celery_task_id:
            from app.tasks.worker import celery_app
            celery_app.control.revoke(job.celery_task_id)
        job.status = JobStatus.canceled
        await db.commit()

    await audit(db, "job_canceled", actor_user_id=user.id, object_type="job_run", object_id=job.id)
    return {"id": job.id, "status": job.status}
