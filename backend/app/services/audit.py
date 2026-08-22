
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


async def audit(
    db: AsyncSession,
    action: str,
    actor_user_id: int | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    detail: dict | None = None,
    ip: str | None = None
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
