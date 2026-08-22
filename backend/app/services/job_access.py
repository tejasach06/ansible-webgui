from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobRun, Playbook, User
from app.services.rbac_scope import assert_project_perm


async def load_job_for_perm(db: AsyncSession, user: User, job_id: int, perm: str) -> tuple[JobRun, Playbook | None]:
    job = (await db.execute(select(JobRun).where(JobRun.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job run not found"})

    playbook = (await db.execute(select(Playbook).where(Playbook.id == job.playbook_id))).scalar_one_or_none()
    if playbook:
        await assert_project_perm(db, user, playbook.project_id, perm)

    return job, playbook
