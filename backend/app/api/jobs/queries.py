from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require
from app.db.models import JobRun, JobStatus, User
from app.db.session import get_db


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

    items = []
    for j in jobs:
        items.append({
            "id": j.id,
            "template_id": j.template_id,
            "playbook_id": j.playbook_id,
            "inventory_id": j.inventory_id,
            "mode": j.mode,
            "status": j.status,
            "requested_by": j.requested_by,
            "approved_by": j.approved_by,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None
        })
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{job_id}")
async def get_job_detail(
    job_id: int,
    user: User = Depends(require("read")),
    db: AsyncSession = Depends(get_db)
):
    job = (await db.execute(select(JobRun).where(JobRun.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job run not found"})

    return {
        "id": job.id,
        "template_id": job.template_id,
        "playbook_id": job.playbook_id,
        "inventory_id": job.inventory_id,
        "mode": job.mode,
        "status": job.status,
        "requested_by": job.requested_by,
        "approved_by": job.approved_by,
        "approval_note": job.approval_note,
        "rc": job.rc,
        "stats": job.stats,
        "params_snapshot": job.params_snapshot,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None
    }
