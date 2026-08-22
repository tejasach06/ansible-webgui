from datetime import datetime

from croniter import croniter
from git import Repo
from sqlalchemy import select

from app.core.time import utcnow
from app.db import session as db_session
from app.db.models import Inventory, JobRun, JobStatus, JobTemplate, Playbook, Project, Schedule
from app.services.approvals import freeze_params_snapshot
from app.services.content import get_inventory_repo_path, get_project_repo_path
from app.services.rbac_scope import inventory_visible_to_project
from app.tasks.run_job import run_job
from app.tasks.worker import celery_app


@celery_app.task(name="run_scheduled")
def run_scheduled(schedule_id: int):
    db = db_session.SyncSessionLocal()
    try:
        sched = db.execute(select(Schedule).where(Schedule.id == schedule_id)).scalar_one_or_none()
        if not sched or not sched.enabled:
            return

        tmpl = db.execute(select(JobTemplate).where(JobTemplate.id == sched.template_id)).scalar_one_or_none()
        if not tmpl:
            return

        playbook = db.execute(select(Playbook).where(Playbook.id == tmpl.playbook_id)).scalar_one_or_none()
        project = db.execute(select(Project).where(Project.id == tmpl.project_id)).scalar_one_or_none()
        if not playbook or not project:
            return

        effective_inventory_id = tmpl.inventory_id or project.default_inventory_id
        if not effective_inventory_id:
            return

        inventory = db.execute(select(Inventory).where(Inventory.id == effective_inventory_id)).scalar_one_or_none()
        if not inventory or not inventory_visible_to_project(inventory, tmpl.project_id):
            return

        repo_path = str(get_project_repo_path(project.name))
        git_sha = Repo(repo_path).head.commit.hexsha
        inv_repo_path = str(get_inventory_repo_path())
        inventory_git_sha = Repo(inv_repo_path).head.commit.hexsha

        snapshot = freeze_params_snapshot(
            project_git_path=repo_path,
            playbook_rel_path=playbook.rel_path,
            inventory_rel_path=inventory.rel_path,
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

        job = JobRun(
            template_id=tmpl.id,
            playbook_id=playbook.id,
            inventory_id=effective_inventory_id,
            mode="live",
            status=JobStatus.queued,
            requested_by=sched.created_by,
            params_snapshot=snapshot,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        sched.last_job_run_id = job.id
        sched.next_run_at = croniter(sched.cron_expr, utcnow()).get_next(datetime)
        db.commit()

        run_job.delay(job.id)
    finally:
        db.close()
