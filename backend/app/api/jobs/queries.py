from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require
from app.core.time import utcnow
from app.db.models import (
    Credential,
    Inventory,
    JobRun,
    JobStatus,
    JobTemplate,
    Playbook,
    Project,
    User,
)
from app.db.session import get_db
from app.services.job_access import load_job_for_perm
from app.services.run_report import build_report

router = APIRouter()
@router.get("")
async def list_jobs(
    status: JobStatus | None = None,
    template_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: User = Depends(require("read")),
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
    pb_ids = list({j.playbook_id for j in jobs if j.playbook_id})
    inv_ids = list({j.inventory_id for j in jobs if j.inventory_id})
    pbs = {p.id: p for p in (await db.execute(select(Playbook).where(Playbook.id.in_(pb_ids)))).scalars().all()} if pb_ids else {}
    invs = {i.id: i for i in (await db.execute(select(Inventory).where(Inventory.id.in_(inv_ids)))).scalars().all()} if inv_ids else {}
    items = []
    for j in jobs:
        pb = pbs.get(j.playbook_id)
        inv = invs.get(j.inventory_id)
        items.append({
            "id": j.id,
            "template_id": j.template_id,
            "playbook_id": j.playbook_id,
            "playbook_name": pb.name if pb else None,
            "playbook_rel_path": pb.rel_path if pb else None,
            "inventory_id": j.inventory_id,
            "inventory_name": inv.name if inv else None,
            "inventory_rel_path": inv.rel_path if inv else None,
            "mode": j.mode,
            "status": j.status,
            "requested_by": j.requested_by,
            "approved_by": j.approved_by,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        })
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/summary")
async def job_summary(_user: User = Depends(require("read")), db: AsyncSession = Depends(get_db)):
    pending = (await db.execute(select(JobRun).where(JobRun.status == JobStatus.pending_approval).order_by(JobRun.created_at.asc()).limit(20))).scalars().all()
    running = (await db.execute(select(func.count(JobRun.id)).where(JobRun.status.in_([JobStatus.running, JobStatus.queued])))).scalar_one()
    since = utcnow() - timedelta(days=7)
    grouped = (await db.execute(select(JobRun.status, func.count(JobRun.id)).where(JobRun.created_at >= since).group_by(JobRun.status))).all()
    recent = (await db.execute(select(JobRun).order_by(JobRun.created_at.desc()).limit(10))).scalars().all()
    return {
        "pending_approval": [{"id": j.id, "template_id": j.template_id, "playbook_id": j.playbook_id, "mode": j.mode, "requested_by": j.requested_by, "created_at": j.created_at.isoformat() if j.created_at else None} for j in pending],
        "running": running,
        "last_7_days": {"successful": 0, "failed": 0, "canceled": 0, **{status.value: count for status, count in grouped if status in {JobStatus.successful, JobStatus.failed, JobStatus.canceled}}},
        "recent": [{"id": j.id, "status": j.status, "mode": j.mode, "finished_at": j.finished_at.isoformat() if j.finished_at else None} for j in recent],
    }



@router.get("/{job_id}/report")
async def get_job_report(job_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await load_job_for_perm(db, user, job_id, "read")
    return await build_report(db, job_id)

@router.get("/{job_id}")
async def get_job_detail(job_id: int, _user: User = Depends(require("read")), db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(JobRun).where(JobRun.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job run not found"})
    playbook = (await db.execute(select(Playbook).where(Playbook.id == job.playbook_id))).scalar_one_or_none()
    project = (await db.execute(select(Project).where(Project.id == playbook.project_id))).scalar_one_or_none() if playbook else None
    inventory = (await db.execute(select(Inventory).where(Inventory.id == job.inventory_id))).scalar_one_or_none() if job.inventory_id else None
    template = (await db.execute(select(JobTemplate).where(JobTemplate.id == job.template_id))).scalar_one_or_none() if job.template_id else None
    snap = job.params_snapshot or {}
    cred_ids = snap.get("credential_ids") or []
    creds = (await db.execute(select(Credential.id, Credential.name, Credential.kind, Credential.username).where(Credential.id.in_(cred_ids)))).all() if cred_ids else []
    user_ids = [i for i in (job.requested_by, job.approved_by) if i]
    names = dict((await db.execute(select(User.id, User.username).where(User.id.in_(user_ids)))).all()) if user_ids else {}

    context = {
        "project_name": project.name if project else None,
        "playbook_name": playbook.name if playbook else None,
        "playbook_rel_path": playbook.rel_path if playbook else None,
        "inventory_name": inventory.name if inventory else None,
        "inventory_rel_path": inventory.rel_path if inventory else None,
        "template_name": template.name if template else None,
        "requested_by_username": names.get(job.requested_by),
        "approved_by_username": names.get(job.approved_by),
        "credentials": [{"id": cid, "name": cname, "kind": ckind.value if hasattr(ckind, "value") else ckind, "username": cuser} for cid, cname, ckind, cuser in creds],
    }
    return {"id": job.id, "template_id": job.template_id, "playbook_id": job.playbook_id, "inventory_id": job.inventory_id, "mode": job.mode, "status": job.status, "requested_by": job.requested_by, "approved_by": job.approved_by, "approval_note": job.approval_note, "rc": job.rc, "stats": job.stats, "params_snapshot": job.params_snapshot, "overrides": (job.params_snapshot or {}).get("overrides", {}), "context": context, "created_at": job.created_at.isoformat() if job.created_at else None, "started_at": job.started_at.isoformat() if job.started_at else None, "finished_at": job.finished_at.isoformat() if job.finished_at else None, "relaunch_of_id": job.relaunch_of_id}
