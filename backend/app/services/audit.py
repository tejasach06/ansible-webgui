from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AuditLog

async def audit(
    db: AsyncSession,
    action: str,
    actor_user_id: Optional[int] = None,
    object_type: Optional[str] = None,
    object_id: Optional[str] = None,
    detail: Optional[dict] = None,
    ip: Optional[str] = None
):
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        object_type=object_type,
        object_id=str(object_id) if object_id is not None else None,
        detail=detail,
        ip=ip
    )
    db.add(entry)
    await db.commit()
