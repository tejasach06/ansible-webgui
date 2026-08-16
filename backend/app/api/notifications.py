from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require
from app.db.models import Notification, User
from app.db.session import get_db
from app.services.audit import audit
from app.tasks.notify import send_notification

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def item(n: Notification):
    return {"id": n.id, "name": n.name, "kind": n.kind, "url": n.url, "enabled": n.enabled, "on_success": n.on_success, "on_failure": n.on_failure, "on_approval_needed": n.on_approval_needed, "created_by": n.created_by}


@router.get("")
async def list_notifications(user: User = Depends(require("read")), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Notification).order_by(Notification.name))).scalars().all()
    return [item(n) for n in rows]


@router.post("")
async def create_notification(req: dict, user: User = Depends(require("notification.write")), db: AsyncSession = Depends(get_db)):
    n = Notification(**req, created_by=user.id)
    db.add(n)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail={"code": "notification_name_taken", "message": "Notification name already exists"})
    await db.refresh(n)
    await audit(db, "notification_created", actor_user_id=user.id, object_type="notification", object_id=n.id)
    return item(n)


@router.patch("/{notification_id}")
async def update_notification(notification_id: int, req: dict, user: User = Depends(require("notification.write")), db: AsyncSession = Depends(get_db)):
    n = (await db.execute(select(Notification).where(Notification.id == notification_id))).scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=404, detail={"code": "notification_not_found", "message": "Notification not found"})
    for k, v in req.items():
        if k != "id" and hasattr(n, k):
            setattr(n, k, v)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail={"code": "notification_name_taken", "message": "Notification name already exists"})
    await db.refresh(n)
    await audit(db, "notification_updated", actor_user_id=user.id, object_type="notification", object_id=n.id)
    return item(n)


@router.delete("/{notification_id}")
async def delete_notification(notification_id: int, user: User = Depends(require("notification.write")), db: AsyncSession = Depends(get_db)):
    n = (await db.execute(select(Notification).where(Notification.id == notification_id))).scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=404, detail={"code": "notification_not_found", "message": "Notification not found"})
    await db.delete(n)
    await db.commit()
    await audit(db, "notification_deleted", actor_user_id=user.id, object_type="notification", object_id=notification_id)
    return {"status": "ok"}


@router.post("/{notification_id}/test")
async def test_notification(notification_id: int, user: User = Depends(require("notification.write")), db: AsyncSession = Depends(get_db)):
    n = (await db.execute(select(Notification).where(Notification.id == notification_id))).scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=404, detail={"code": "notification_not_found", "message": "Notification not found"})
    send_notification.delay("job_finished", {"event": "job_finished", "job_id": 0, "status": "successful", "mode": "check", "template_id": None, "playbook_id": None, "rc": 0, "stats": {}, "url": None})
    await audit(db, "notification_tested", actor_user_id=user.id, object_type="notification", object_id=n.id)
    return {"status": "ok"}
