from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require
from app.db.models import AuditLog, User
from app.db.session import get_db

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
async def list_audit(
    action: str | None = None,
    actor_user_id: int | None = None,
    actor: str | None = None,
    object_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: User = Depends(require("audit.read")),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if action is not None and action.strip():
        filters.append(AuditLog.action.ilike(f"%{action.strip()}%"))
    if actor_user_id is not None:
        filters.append(AuditLog.actor_user_id == actor_user_id)
    elif actor is not None and actor.strip():
        term = actor.strip()
        if term.isdigit():
            filters.append(
                or_(
                    AuditLog.actor_user_id == int(term),
                    User.username.ilike(f"%{term}%"),
                )
            )
        else:
            filters.append(
                or_(
                    User.username.ilike(f"%{term}%"),
                    User.email.ilike(f"%{term}%"),
                )
            )
    if object_type is not None and object_type.strip():
        filters.append(AuditLog.object_type.ilike(f"%{object_type.strip()}%"))

    count_stmt = select(func.count(AuditLog.id)).outerjoin(User, AuditLog.actor_user_id == User.id).where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    rows = (
        await db.execute(
            select(AuditLog, User.username, User.email)
            .outerjoin(User, AuditLog.actor_user_id == User.id)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(min(limit, 200))
        )
    ).all()

    return {
        "items": [
            {
                "id": log.id,
                "actor_user_id": log.actor_user_id,
                "actor_username": username,
                "actor_email": email,
                "action": log.action,
                "object_type": log.object_type,
                "object_id": log.object_id,
                "detail": log.detail,
                "ip": log.ip,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log, username, email in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
