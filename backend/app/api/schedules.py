import zoneinfo
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from croniter import croniter
from redbeat import RedBeatSchedulerEntry
from app.db.session import get_db
from app.db.models import Schedule, JobTemplate, User
from app.api.auth import require
from app.tasks.worker import celery_app
from app.services.audit import audit

router = APIRouter(prefix="/api/schedules", tags=["schedules"])

class ScheduleCreate(BaseModel):
    template_id: int
    name: str
    cron_expr: str
    timezone: str = "UTC"

class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    cron_expr: Optional[str] = None
    timezone: Optional[str] = None
    enabled: Optional[bool] = None

@router.get("")
async def list_schedules(
    user: User = Depends(require("read")),
    db: AsyncSession = Depends(get_db)
):
    schedules = (await db.execute(select(Schedule))).scalars().all()
    return [{
        "id": s.id,
        "template_id": s.template_id,
        "name": s.name,
        "cron_expr": s.cron_expr,
        "timezone": s.timezone,
        "enabled": s.enabled,
        "created_by": s.created_by
    } for s in schedules]

@router.post("")
async def create_schedule(
    req: ScheduleCreate,
    user: User = Depends(require("schedule.write")),
    db: AsyncSession = Depends(get_db)
):
    if not croniter.is_valid(req.cron_expr):
        raise HTTPException(status_code=422, detail={"code": "bad_cron", "message": "Invalid cron expression"})

    try:
        zoneinfo.ZoneInfo(req.timezone)
    except Exception:
        raise HTTPException(status_code=422, detail={"code": "bad_timezone", "message": "Invalid timezone"})

    template = (await db.execute(select(JobTemplate).where(JobTemplate.id == req.template_id))).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail={"code": "template_not_found", "message": "Template not found"})

    redbeat_key = f"redbeat:job:{req.name}"

    sched = Schedule(
        template_id=req.template_id,
        name=req.name,
        cron_expr=req.cron_expr,
        timezone=req.timezone,
        enabled=True,
        redbeat_key=redbeat_key,
        created_by=user.id
    )
    db.add(sched)
    await db.commit()
    await db.refresh(sched)

    entry = RedBeatSchedulerEntry(
        name=redbeat_key,
        task="run_scheduled",
        schedule=croniter(req.cron_expr),
        args=[sched.id],
        app=celery_app
    )
    entry.save()

    await audit(db, "schedule_created", actor_user_id=user.id, object_type="schedule", object_id=sched.id)
    return {"id": sched.id, "name": sched.name}

@router.patch("/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    req: ScheduleUpdate,
    user: User = Depends(require("schedule.write")),
    db: AsyncSession = Depends(get_db)
):
    sched = (await db.execute(select(Schedule).where(Schedule.id == schedule_id))).scalar_one_or_none()
    if not sched:
        raise HTTPException(status_code=404, detail={"code": "schedule_not_found", "message": "Schedule not found"})

    if req.cron_expr and not croniter.is_valid(req.cron_expr):
        raise HTTPException(status_code=422, detail={"code": "bad_cron", "message": "Invalid cron expression"})

    if req.timezone:
        try:
            zoneinfo.ZoneInfo(req.timezone)
        except Exception:
            raise HTTPException(status_code=422, detail={"code": "bad_timezone", "message": "Invalid timezone"})

    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(sched, k, v)

    await db.commit()
    await db.refresh(sched)
    return {"id": sched.id, "name": sched.name}

@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    user: User = Depends(require("schedule.write")),
    db: AsyncSession = Depends(get_db)
):
    sched = (await db.execute(select(Schedule).where(Schedule.id == schedule_id))).scalar_one_or_none()
    if not sched:
        raise HTTPException(status_code=404, detail={"code": "schedule_not_found", "message": "Schedule not found"})

    try:
        entry = RedBeatSchedulerEntry.from_key(sched.redbeat_key, app=celery_app)
        entry.delete()
    except Exception:
        pass

    await db.delete(sched)
    await db.commit()
    await audit(db, "schedule_deleted", actor_user_id=user.id, object_type="schedule", object_id=schedule_id)
    return {"status": "ok"}
