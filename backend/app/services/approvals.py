from typing import Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import JobRun, JobStatus, JobTemplate, Playbook, Inventory, Project

def freeze_params_snapshot(
    project_git_path: str,
    playbook_rel_path: str,
    inventory_rel_path: str,
    mode: str,
    limit: str = None,
    tags: str = None,
    skip_tags: str = None,
    extra_vars: dict = None,
    verbosity: int = 0,
    forks: int = 5,
    become: bool = False,
    become_user: str = None,
    become_method: str = None,
    diff: bool = False,
    credential_ids: list = None,
    job_timeout: int = 3600,
    git_sha: str = None,
    inventory_git_sha: str = None
) -> dict:
    return {
        "git_sha": git_sha,
        "inventory_git_sha": inventory_git_sha,
        "playbook_rel_path": playbook_rel_path,
        "inventory_rel_path": inventory_rel_path,
        "mode": mode,
        "limit": limit,
        "tags": tags,
        "skip_tags": skip_tags,
        "extra_vars": extra_vars or {},
        "verbosity": verbosity,
        "forks": forks,
        "become": become,
        "become_user": become_user,
        "become_method": become_method,
        "diff": diff,
        "credential_ids": credential_ids or [],
        "job_timeout": job_timeout
    }

async def approve_job_run(
    db: AsyncSession,
    job_run: JobRun,
    approver_id: int,
    approval_note: str = None
) -> JobRun:
    if job_run.requested_by == approver_id:
        raise ValueError("self_approval_forbidden")
    if job_run.status != JobStatus.pending_approval:
        raise ValueError("bad_state")
    
    job_run.approved_by = approver_id
    job_run.approval_note = approval_note
    job_run.status = JobStatus.queued
    await db.commit()
    await db.refresh(job_run)
    return job_run
