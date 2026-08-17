from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models import JobRun, JobStatus, JobEvent, JobPlay, JobTask, JobHostResult, Playbook, User, HostResultStatus
from app.api.auth import get_current_user, require
from app.services.rbac_scope import visible_project_ids, assert_project_perm

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


@router.get("/{job_id}/report")
async def get_job_report(job_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(JobRun).where(JobRun.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job run not found"})

    playbook = (await db.execute(select(Playbook).where(Playbook.id == job.playbook_id))).scalar_one_or_none()
    if playbook:
        await assert_project_perm(db, user, playbook.project_id, "read")

    plays = (await db.execute(select(JobPlay).where(JobPlay.job_run_id == job_id).order_by(JobPlay.counter.asc()))).scalars().all()
    tasks = (await db.execute(select(JobTask).where(JobTask.job_run_id == job_id).order_by(JobTask.counter.asc()))).scalars().all()
    host_results = (await db.execute(select(JobHostResult).where(JobHostResult.job_run_id == job_id).order_by(JobHostResult.counter.asc()))).scalars().all()

    hr_by_task = {}
    hr_by_host = {}
    totals = {"ok": 0, "changed": 0, "failed": 0, "unreachable": 0, "skipped": 0}

    for hr in host_results:
        st = hr.status.value if hasattr(hr.status, "value") else str(hr.status)
        totals[st] = totals.get(st, 0) + 1

        if hr.task_id not in hr_by_task:
            hr_by_task[hr.task_id] = []
        hr_by_task[hr.task_id].append(hr)

        if hr.host not in hr_by_host:
            hr_by_host[hr.host] = {"ok": 0, "changed": 0, "failed": 0, "unreachable": 0, "skipped": 0, "first_failure_counter": None}
        hr_by_host[hr.host][st] = hr_by_host[hr.host].get(st, 0) + 1

        if st in ("failed", "unreachable"):
            ffc = hr_by_host[hr.host]["first_failure_counter"]
            if ffc is None or hr.counter < ffc:
                hr_by_host[hr.host]["first_failure_counter"] = hr.counter

    tasks_by_play = {}
    for task in tasks:
        t_hrs = hr_by_task.get(task.id, [])
        res = {"ok": 0, "changed": 0, "failed": 0, "unreachable": 0, "skipped": 0}
        failed_hosts = []
        first_fail_counter = None
        durations = []

        for hr in t_hrs:
            st = hr.status.value if hasattr(hr.status, "value") else str(hr.status)
            res[st] = res.get(st, 0) + 1
            if hr.duration_ms is not None:
                durations.append(hr.duration_ms)

            is_failed = (st == "unreachable") or (st == "failed" and not hr.ignore_errors)
            if is_failed:
                if hr.host not in failed_hosts:
                    failed_hosts.append(hr.host)
                if first_fail_counter is None or hr.counter < first_fail_counter:
                    first_fail_counter = hr.counter

        task_dict = {
            "uuid": task.uuid,
            "name": task.name,
            "action": task.action,
            "duration_ms": max(durations) if durations else 0,
            "results": res,
            "failed_hosts": failed_hosts,
            "first_failure_counter": first_fail_counter,
        }

        if task.play_id not in tasks_by_play:
            tasks_by_play[task.play_id] = []
        tasks_by_play[task.play_id].append(task_dict)

    plays_list = []
    for play in plays:
        p_tasks = tasks_by_play.get(play.id, [])
        p_durations = [t["duration_ms"] for t in p_tasks]
        plays_list.append({
            "uuid": play.uuid,
            "name": play.name,
            "duration_ms": sum(p_durations),
            "tasks": p_tasks,
        })

    hosts_list = []
    for host_name, stats in hr_by_host.items():
        if stats["unreachable"] > 0:
            st = "unreachable"
        elif stats["failed"] > 0:
            st = "failed"
        elif stats["changed"] > 0:
            st = "changed"
        elif stats["ok"] > 0:
            st = "ok"
        else:
            st = "skipped"

        hosts_list.append({
            "host": host_name,
            "ok": stats["ok"],
            "changed": stats["changed"],
            "failed": stats["failed"],
            "unreachable": stats["unreachable"],
            "skipped": stats["skipped"],
            "status": st,
            "first_failure_counter": stats["first_failure_counter"],
        })

    hosts_list.sort(key=lambda h: (0 if h["status"] in ("failed", "unreachable") else 1, h["host"]))

    return {
        "plays": plays_list,
        "hosts": hosts_list,
        "totals": totals,
    }

@router.get("/{job_id}")
async def get_job_detail(job_id: int, user: User = Depends(require("read")), db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(JobRun).where(JobRun.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job run not found"})
    return {"id": job.id, "template_id": job.template_id, "playbook_id": job.playbook_id, "inventory_id": job.inventory_id, "mode": job.mode, "status": job.status, "requested_by": job.requested_by, "approved_by": job.approved_by, "approval_note": job.approval_note, "rc": job.rc, "stats": job.stats, "params_snapshot": job.params_snapshot, "overrides": (job.params_snapshot or {}).get("overrides", {}), "created_at": job.created_at.isoformat() if job.created_at else None, "started_at": job.started_at.isoformat() if job.started_at else None, "finished_at": job.finished_at.isoformat() if job.finished_at else None, "relaunch_of_id": job.relaunch_of_id}
