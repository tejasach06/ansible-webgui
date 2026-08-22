import zoneinfo

from celery.schedules import crontab
from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from redbeat import RedBeatSchedulerEntry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.models import JobTemplate, Schedule, User
from app.db.session import get_db
from app.services.audit import audit
from app.services.rbac_scope import assert_project_perm, visible_project_ids
from app.tasks.worker import celery_app

router = APIRouter(prefix="/api/schedules", tags=["schedules"])

class ScheduleCreate(BaseModel):
    template_id: int
    name: str
    cron_expr: str
    timezone: str = "UTC"

class ScheduleUpdate(BaseModel):
    name: str | None = None
    cron_expr: str | None = None
    timezone: str | None = None
    enabled: bool | None = None

@router.get("")
async def list_schedules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Schedule)
    visible_ids = await visible_project_ids(db, user)
    if visible_ids is not None:
        query = query.where(Schedule.template_id.in_(select(JobTemplate.id).where(JobTemplate.project_id.in_(visible_ids))))
    schedules = (await db.execute(query)).scalars().all()
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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not croniter.is_valid(req.cron_expr):
        raise HTTPException(status_code=422, detail={"code": "bad_cron", "message": "Invalid cron expression"})

    try:
        zoneinfo.ZoneInfo(req.timezone)
    except Exception:
        raise HTTPException(status_code=422, detail={"code": "bad_timezone", "message": "Invalid timezone"}) from None

    template = (await db.execute(select(JobTemplate).where(JobTemplate.id == req.template_id))).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail={"code": "template_not_found", "message": "Template not found"})
    await assert_project_perm(db, user, template.project_id, "schedule.write")

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

    parts = req.cron_expr.split()
    if len(parts) != 5:
        raise HTTPException(status_code=422, detail={"code": "bad_cron", "message": "Invalid cron expression"})
    m, h, dom, mon, dow = parts
    entry = RedBeatSchedulerEntry(
        name=redbeat_key,
        task="run_scheduled",
        schedule=crontab(minute=m, hour=h, day_of_month=dom, month_of_year=mon, day_of_week=dow),
        args=[sched.id],
        app=celery_app,
    )
    entry.save()

    await audit(db, "schedule_created", actor_user_id=user.id, object_type="schedule", object_id=sched.id)
    return {"id": sched.id, "name": sched.name}

@router.patch("/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    req: ScheduleUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(Schedule, JobTemplate.project_id)
        .join(JobTemplate, Schedule.template_id == JobTemplate.id)
        .where(Schedule.id == schedule_id)
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "schedule_not_found", "message": "Schedule not found"})
    sched, project_id = row
    await assert_project_perm(db, user, project_id, "schedule.write")

    if req.cron_expr and not croniter.is_valid(req.cron_expr):
        raise HTTPException(status_code=422, detail={"code": "bad_cron", "message": "Invalid cron expression"})

    if req.timezone:
        try:
            zoneinfo.ZoneInfo(req.timezone)
        except Exception:
            raise HTTPException(status_code=422, detail={"code": "bad_timezone", "message": "Invalid timezone"}) from None

    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(sched, k, v)

    await db.commit()
    await db.refresh(sched)
    await audit(db, "schedule_updated", actor_user_id=user.id, object_type="schedule", object_id=sched.id)
    return {"id": sched.id, "name": sched.name}

@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(Schedule, JobTemplate.project_id)
        .join(JobTemplate, Schedule.template_id == JobTemplate.id)
        .where(Schedule.id == schedule_id)
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "schedule_not_found", "message": "Schedule not found"})
    sched, project_id = row
    await assert_project_perm(db, user, project_id, "schedule.write")

    try:
        entry = RedBeatSchedulerEntry.from_key(sched.redbeat_key, app=celery_app)
        entry.delete()
    except Exception:
        pass

    await db.delete(sched)
    await db.commit()
    await audit(db, "schedule_deleted", actor_user_id=user.id, object_type="schedule", object_id=schedule_id)
    return {"status": "ok"}
