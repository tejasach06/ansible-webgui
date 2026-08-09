from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require
from app.db.models import AuditLog, User
from app.db.session import get_db

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
async def list_audit(
    action: Optional[str] = None,
    actor_user_id: Optional[int] = None,
    object_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(require("user.manage")),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if action is not None:
        filters.append(AuditLog.action == action)
    if actor_user_id is not None:
        filters.append(AuditLog.actor_user_id == actor_user_id)
    if object_type is not None:
        filters.append(AuditLog.object_type == object_type)

    total = (await db.execute(select(func.count(AuditLog.id)).where(*filters))).scalar_one()
    rows = (await db.execute(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(min(limit, 200))
    )).scalars().all()

    return {
        "items": [
            {
                "id": row.id,
                "actor_user_id": row.actor_user_id,
                "action": row.action,
                "object_type": row.object_type,
                "object_id": row.object_id,
                "detail": row.detail,
                "ip": row.ip,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
