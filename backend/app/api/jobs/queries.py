from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require
from app.db.models import JobEvent, JobRun, JobStatus, User
from app.db.session import get_db
from app.services.job_events import RELEVANT_EVENTS, build_host_summary, build_task_tree


router = APIRouter()


@router.get("")
async def list_jobs(
    status: Optional[JobStatus] = None,
    template_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(require("read")),
    db: AsyncSession = Depends(get_db)
):
    filters = []
    if status is not None:
        filters.append(JobRun.status == status)
    if template_id is not None:
        filters.append(JobRun.template_id == template_id)
    total = (await db.execute(select(func.count(JobRun.id)).where(*filters))).scalar_one()
    query = select(JobRun).where(*filters).order_by(JobRun.created_at.desc()).offset(offset).limit(min(limit, 200))
    jobs = (await db.execute(query)).scalars().all()
    items = [{"id": j.id, "template_id": j.template_id, "playbook_id": j.playbook_id, "inventory_id": j.inventory_id, "mode": j.mode, "status": j.status, "requested_by": j.requested_by, "approved_by": j.approved_by, "created_at": j.created_at.isoformat() if j.created_at else None, "finished_at": j.finished_at.isoformat() if j.finished_at else None} for j in jobs]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/summary")
async def job_summary(user: User = Depends(require("read")), db: AsyncSession = Depends(get_db)):
    pending = (await db.execute(select(JobRun).where(JobRun.status == JobStatus.pending_approval).order_by(JobRun.created_at.asc()).limit(20))).scalars().all()
    running = (await db.execute(select(func.count(JobRun.id)).where(JobRun.status.in_([JobStatus.running, JobStatus.queued])))).scalar_one()
    since = datetime.utcnow() - timedelta(days=7)
    grouped = (await db.execute(select(JobRun.status, func.count(JobRun.id)).where(JobRun.created_at >= since).group_by(JobRun.status))).all()
    recent = (await db.execute(select(JobRun).order_by(JobRun.created_at.desc()).limit(10))).scalars().all()
    return {
        "pending_approval": [{"id": j.id, "template_id": j.template_id, "playbook_id": j.playbook_id, "mode": j.mode, "requested_by": j.requested_by, "created_at": j.created_at.isoformat() if j.created_at else None} for j in pending],
        "running": running,
        "last_7_days": {"successful": 0, "failed": 0, "canceled": 0, **{status.value: count for status, count in grouped if status in {JobStatus.successful, JobStatus.failed, JobStatus.canceled}}},
        "recent": [{"id": j.id, "status": j.status, "mode": j.mode, "finished_at": j.finished_at.isoformat() if j.finished_at else None} for j in recent],
    }


async def _event_rows(job_id: int, db: AsyncSession):
    exists = (await db.execute(select(JobRun.id).where(JobRun.id == job_id))).scalar_one_or_none()
    if not exists:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job run not found"})
    return (await db.execute(select(JobEvent.counter, JobEvent.event, JobEvent.host, JobEvent.payload).where(JobEvent.job_run_id == job_id, JobEvent.event.in_(RELEVANT_EVENTS)).order_by(JobEvent.counter.asc()))).all()


@router.get("/{job_id}/tasks")
async def get_job_tasks(job_id: int, user: User = Depends(require("read")), db: AsyncSession = Depends(get_db)):
    return build_task_tree(await _event_rows(job_id, db))


@router.get("/{job_id}/hosts")
async def get_job_hosts(job_id: int, user: User = Depends(require("read")), db: AsyncSession = Depends(get_db)):
    return build_host_summary(await _event_rows(job_id, db))


@router.get("/{job_id}")
async def get_job_detail(job_id: int, user: User = Depends(require("read")), db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(JobRun).where(JobRun.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job run not found"})
    return {"id": job.id, "template_id": job.template_id, "playbook_id": job.playbook_id, "inventory_id": job.inventory_id, "mode": job.mode, "status": job.status, "requested_by": job.requested_by, "approved_by": job.approved_by, "approval_note": job.approval_note, "rc": job.rc, "stats": job.stats, "params_snapshot": job.params_snapshot, "created_at": job.created_at.isoformat() if job.created_at else None, "started_at": job.started_at.isoformat() if job.started_at else None, "finished_at": job.finished_at.isoformat() if job.finished_at else None, "relaunch_of_id": job.relaunch_of_id}
