import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from git import Repo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require
from app.api.jobs.schemas import ApproveRequest, JobRequest
from app.core.config import settings
from app.db.models import Credential, Inventory, JobMode, JobRun, JobStatus, JobTemplate, Playbook, Project, User
from app.db.session import get_db
from app.services.approvals import approve_job_run, freeze_params_snapshot
from app.services.audit import audit
from app.services.content import get_inventory_repo_path, get_project_repo_path
from app.tasks.run_job import run_job


router = APIRouter()


async def request_job(
    req: JobRequest,
    user: User = Depends(require("job.request")),
    db: AsyncSession = Depends(get_db)
):
    playbook = (await db.execute(select(Playbook).where(Playbook.id == req.playbook_id))).scalar_one_or_none()
    if not playbook:
        raise HTTPException(status_code=404, detail={"code": "playbook_not_found", "message": "Playbook not found"})

    inventory = (await db.execute(select(Inventory).where(Inventory.id == req.inventory_id))).scalar_one_or_none()
    if not inventory:
        raise HTTPException(status_code=404, detail={"code": "inventory_not_found", "message": "Inventory not found"})

    if req.credential_ids:
        named = (await db.execute(select(Credential.name).where(Credential.id.in_(req.credential_ids), Credential.username.isnot(None)))).scalars().all()
        if len(named) > 1:
            raise HTTPException(status_code=422, detail={"code": "credential_user_conflict", "message": "Multiple selected credentials set a username", "credentials": named})

    project = (await db.execute(select(Project).where(Project.id == playbook.project_id))).scalar_one_or_none()
    repo_path = get_project_repo_path(project.name)
    repo = Repo(repo_path)
    git_sha = repo.head.commit.hexsha
    inventory_repo_path = get_inventory_repo_path()
    if not (inventory_repo_path / ".git").exists():
        raise HTTPException(status_code=404, detail={"code": "inventory_repo_missing", "message": "Shared inventory repo is not initialized. Restart the API."})
    inventory_git_sha = Repo(inventory_repo_path).head.commit.hexsha

    # Check for active live runs of the same template
    if req.template_id and req.mode == JobMode.live:
        active = (await db.execute(
            select(JobRun).where(
                JobRun.template_id == req.template_id,
                JobRun.mode == JobMode.live,
                JobRun.status.in_([JobStatus.queued, JobStatus.running])
            )
        )).scalars().all()
        if active:
            raise HTTPException(status_code=409, detail={"code": "template_busy", "message": "Template has a queued/running live run"})

    requires_appr = True
    if req.template_id:
        tmpl = (await db.execute(select(JobTemplate).where(JobTemplate.id == req.template_id))).scalar_one_or_none()
        if tmpl:
            requires_appr = tmpl.requires_approval

    mode_status = JobStatus.pending_approval
    if req.mode == JobMode.check or not requires_appr:
        mode_status = JobStatus.queued

    snapshot = freeze_params_snapshot(
        project_git_path=str(repo_path),
        playbook_rel_path=playbook.rel_path,
        inventory_rel_path=inventory.rel_path,
        mode=req.mode.value,
        limit=req.limit,
        tags=req.tags,
        skip_tags=req.skip_tags,
        extra_vars=req.extra_vars,
        verbosity=req.verbosity,
        forks=req.forks,
        become=req.become,
        become_user=req.become_user,
        become_method=req.become_method,
        credential_ids=req.credential_ids,
        git_sha=git_sha,
        inventory_git_sha=inventory_git_sha,
    )

    job = JobRun(
        template_id=req.template_id,
        playbook_id=req.playbook_id,
        inventory_id=req.inventory_id,
        mode=req.mode,
        status=mode_status,
        requested_by=user.id,
        params_snapshot=snapshot
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await audit(db, "job_requested", actor_user_id=user.id, object_type="job_run", object_id=job.id, detail={"mode": req.mode})

    if mode_status == JobStatus.queued:
        task = run_job.delay(job.id)
        job.celery_task_id = task.id
        await db.commit()

    return {"id": job.id, "status": job.status, "mode": job.mode}


async def approve_job(
    job_id: int,
    req: ApproveRequest,
    user: User = Depends(require("job.approve")),
    db: AsyncSession = Depends(get_db)
):
    job = (await db.execute(select(JobRun).where(JobRun.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job run not found"})

    try:
        job = await approve_job_run(db, job, user.id, req.approval_note)
    except ValueError as e:
        err_code = str(e)
        if err_code == "self_approval_forbidden":
            raise HTTPException(status_code=409, detail={"code": "self_approval_forbidden", "message": "Cannot approve own job run"})
        elif err_code == "bad_state":
            raise HTTPException(status_code=409, detail={"code": "bad_state", "message": "Job is not in pending_approval state"})
        raise HTTPException(status_code=400, detail={"code": "error", "message": str(e)})

    task = run_job.delay(job.id)
    job.celery_task_id = task.id
    await db.commit()

    await audit(db, "job_approved", actor_user_id=user.id, object_type="job_run", object_id=job.id)
    return {"id": job.id, "status": job.status}


async def reject_job(
    job_id: int,
    user: User = Depends(require("job.approve")),
    db: AsyncSession = Depends(get_db)
):
    job = (await db.execute(select(JobRun).where(JobRun.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job run not found"})

    if job.status != JobStatus.pending_approval:
        raise HTTPException(status_code=409, detail={"code": "bad_state", "message": "Job is not in pending_approval state"})

    job.status = JobStatus.rejected
    await db.commit()
    await audit(db, "job_rejected", actor_user_id=user.id, object_type="job_run", object_id=job.id)
    return {"id": job.id, "status": job.status}


async def cancel_job(
    job_id: int,
    user: User = Depends(require("job.cancel")),
    db: AsyncSession = Depends(get_db)
):
    job = (await db.execute(select(JobRun).where(JobRun.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job run not found"})

    r = aioredis.from_url(settings.REDIS_URL)
    await r.set(f"job:{job.id}:cancel", "1")

    if job.status == JobStatus.queued and job.celery_task_id:
        from app.tasks.worker import celery_app
        celery_app.control.revoke(job.celery_task_id)
        job.status = JobStatus.canceled
        await db.commit()

    await audit(db, "job_canceled", actor_user_id=user.id, object_type="job_run", object_id=job.id)
    return {"id": job.id, "status": job.status}
