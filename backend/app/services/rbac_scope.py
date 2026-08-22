
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import get_project_permissions, get_user_permissions
from app.db.models import Inventory, ProjectMembership, ProjectRole, User


def role_name(role) -> str:
    return role.value if hasattr(role, "value") else str(role)


async def assert_project_perm(db: AsyncSession, user: User, project_id: int, perm: str) -> None:
    global_perms = get_user_permissions(user.roles)
    if "system.admin" in global_perms:
        return
    res = await db.execute(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user.id,
        )
    )
    membership = res.scalar_one_or_none()
    if not membership or perm not in get_project_permissions(role_name(membership.role)):
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Insufficient project permission"})


async def visible_project_ids(db: AsyncSession, user: User) -> list[int] | None:
    global_perms = get_user_permissions(user.roles)
    if "system.admin" in global_perms:
        return None

    res = await db.execute(
        select(ProjectMembership.project_id).where(ProjectMembership.user_id == user.id)
    )
    return list(res.scalars().all())


async def has_inventory_write(db: AsyncSession, user: User) -> bool:
    global_perms = get_user_permissions(user.roles)
    if "system.admin" in global_perms:
        return True

    res = await db.execute(
        select(ProjectMembership.id).where(
            ProjectMembership.user_id == user.id,
            ProjectMembership.role.in_([ProjectRole.owner, ProjectRole.maintainer, ProjectRole.developer]),
        ).limit(1)
    )
    return res.scalar_one_or_none() is not None

def inventory_visible_to_project(inv: Inventory, project_id: int) -> bool:
    return inv.project_id is None or inv.project_id == project_id
