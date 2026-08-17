from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import get_user_permissions, get_project_permissions
from app.db.models import ProjectMembership, ProjectRole, User

def _role_name(role) -> str:
    return role.value if hasattr(role, "value") else str(role)

async def _user_global_perms(db: AsyncSession, user: User) -> set:
    res = await db.execute(select(User).options(selectinload(User.roles)).where(User.id == user.id))
    u = res.unique().scalar_one_or_none()
    return get_user_permissions(u.roles) if u else set()

async def assert_project_perm(db: AsyncSession, user: User, project_id: int, perm: str) -> None:
    global_perms = await _user_global_perms(db, user)
    if "system.admin" in global_perms:
        return
    res = await db.execute(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user.id,
        )
    )
    membership = res.scalar_one_or_none()
    if not membership or perm not in get_project_permissions(_role_name(membership.role)):
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Insufficient project permission"})


async def visible_project_ids(db: AsyncSession, user: User) -> Optional[List[int]]:
    global_perms = await _user_global_perms(db, user)
    if "system.admin" in global_perms:
        return None

    res = await db.execute(
        select(ProjectMembership.project_id).where(ProjectMembership.user_id == user.id)
    )
    return list(res.scalars().all())


async def has_inventory_write(db: AsyncSession, user: User) -> bool:
    global_perms = await _user_global_perms(db, user)
    if "system.admin" in global_perms:
        return True

    res = await db.execute(
        select(ProjectMembership.id).where(
            ProjectMembership.user_id == user.id,
            ProjectMembership.role.in_([ProjectRole.owner, ProjectRole.maintainer, ProjectRole.developer]),
        ).limit(1)
    )
    return res.scalar_one_or_none() is not None
