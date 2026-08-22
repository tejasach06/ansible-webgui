import redis
from sqlalchemy import select

from app.core.config import settings
from app.core.time import utcnow
from app.db import session as db_session
from app.db.models import (
    Inventory,
    JobRun,
    JobStatus,
    JobTemplate,
    PipelineRun,
    PipelineStatus,
    PipelineStep,
    Playbook,
    Project,
)
from app.services.approvals import freeze_params_snapshot
from app.services.content import get_project_repo_path
from app.services.rbac_scope import inventory_visible_to_project
from app.tasks.run_job import run_job
from app.tasks.worker import celery_app


@celery_app.task(name="run_pipeline")
def run_pipeline(pipeline_run_id: int, resume_from: int = 0):
    db = db_session.SyncSessionLocal()
    r = redis.from_url(settings.REDIS_URL)

    try:
        prun = db.execute(select(PipelineRun).where(PipelineRun.id == pipeline_run_id)).scalar_one_or_none()
        if not prun:
            return

        if prun.status == PipelineStatus.canceled:
            return
        prun.status = PipelineStatus.running
        if not prun.started_at:
            prun.started_at = utcnow()
        db.commit()

        steps = db.execute(
            select(PipelineStep)
            .where(PipelineStep.pipeline_id == prun.pipeline_id, PipelineStep.position >= resume_from)
            .order_by(PipelineStep.position.asc())
        ).scalars().all()

        template_ids = [s.template_id for s in steps]
        templates = {t.id: t for t in db.execute(select(JobTemplate).where(JobTemplate.id.in_(template_ids))).scalars().all()} if template_ids else {}
        playbook_ids = [t.playbook_id for t in templates.values()]
        project_ids = [t.project_id for t in templates.values()]
        playbooks = {p.id: p for p in db.execute(select(Playbook).where(Playbook.id.in_(playbook_ids))).scalars().all()} if playbook_ids else {}
        projects = {p.id: p for p in db.execute(select(Project).where(Project.id.in_(project_ids))).scalars().all()} if project_ids else {}
        inv_ids = {t.inventory_id for t in templates.values() if t.inventory_id} | {p.default_inventory_id for p in projects.values() if p.default_inventory_id}
        inventories = {i.id: i for i in db.execute(select(Inventory).where(Inventory.id.in_(inv_ids))).scalars().all()} if inv_ids else {}


        for step in steps:
            # Check cancel flag
            if r.get(f"pipeline:{pipeline_run_id}:cancel") == b"1":
                prun.status = PipelineStatus.canceled
                prun.finished_at = utcnow()
                db.commit()
                return

            prun.current_position = step.position
            db.commit()

            # Step 5.4 resumption / idempotency: check existing child JobRun
            child = db.execute(
                select(JobRun).where(
                    JobRun.pipeline_run_id == pipeline_run_id,
                    JobRun.pipeline_step_id == step.id
                )
            ).scalar_one_or_none()

            tmpl = templates.get(step.template_id)
            if not tmpl:
                prun.status = PipelineStatus.failed
                prun.finished_at = utcnow()
                db.commit()
                return

            playbook = playbooks.get(tmpl.playbook_id)
            project = projects.get(tmpl.project_id)
            effective_inventory_id = tmpl.inventory_id or (project.default_inventory_id if project else None)
            inventory = inventories.get(effective_inventory_id)
            if not inventory or not inventory_visible_to_project(inventory, tmpl.project_id):
                prun.status = PipelineStatus.failed
                prun.finished_at = utcnow()
                db.commit()
                return

            snapshot_data = prun.params_snapshot or {}
            git_sha = snapshot_data.get("git_sha")
            inventory_git_sha = snapshot_data.get("inventory_git_sha")

            repo_path = str(get_project_repo_path(project.name)) if project else ""
            playbook_rel = playbook.rel_path if playbook else ""
            inventory_rel = inventory.rel_path if inventory else ""

            if child is None:
                snapshot = freeze_params_snapshot(
                    project_git_path=repo_path,
                    playbook_rel_path=playbook_rel,
                    inventory_rel_path=inventory_rel,
                    mode="live",
                    limit=tmpl.limit_pattern,
                    tags=tmpl.tags,
                    skip_tags=tmpl.skip_tags,
                    extra_vars=tmpl.extra_vars or {},
                    verbosity=tmpl.verbosity,
                    forks=tmpl.forks,
                    become=False,
                    diff=tmpl.diff_mode,
                    credential_ids=tmpl.credential_ids or [],
                    git_sha=git_sha,
                    inventory_git_sha=inventory_git_sha,
                    overrides={},
                )

                child_status = JobStatus.pending_approval if step.requires_approval else JobStatus.queued

                child = JobRun(
                    template_id=tmpl.id,
                    playbook_id=tmpl.playbook_id,
                    inventory_id=effective_inventory_id,
                    mode="live",
                    status=child_status,
                    requested_by=prun.requested_by,
                    params_snapshot=snapshot,
                    pipeline_run_id=prun.id,
                    pipeline_step_id=step.id,
                )
                db.add(child)
                db.commit()
                db.refresh(child)

            if child.status == JobStatus.pending_approval:
                db.commit()
                return

            if child.status == JobStatus.queued:
                run_job(child.id)
                db.refresh(child)

            term_status = child.status.value if hasattr(child.status, "value") else str(child.status)

            if term_status == "successful":
                continue
            if term_status in ("canceled", "rejected"):
                prun.status = PipelineStatus.canceled if term_status == "canceled" else PipelineStatus.failed
                prun.finished_at = utcnow()
                db.commit()
                return
            if step.continue_on_failure:
                continue
            prun.status = PipelineStatus.failed
            prun.finished_at = utcnow()
            db.commit()
            return

        prun.status = PipelineStatus.successful
        prun.finished_at = utcnow()
        db.commit()

    except Exception:
        if 'prun' in locals() and prun:
            prun.status = PipelineStatus.failed
            prun.finished_at = utcnow()
            db.commit()
        raise
    finally:
        db.close()
