from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.db.models import User, Role, JobRun
from app.core.security import hash_password
from app.api.auth import require
from sqlalchemy.orm import selectinload
from app.services.audit import audit

router = APIRouter(prefix="/api/users", tags=["users"])

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    roles: List[str]

class UserUpdate(BaseModel):
    email: Optional[str] = None
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None

class PasswordUpdate(BaseModel):
    password: str

@router.get("")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(require("user.manage")),
    db: AsyncSession = Depends(get_db)
):
    total = (await db.execute(select(func.count(User.id)))).scalar_one()
    query = select(User).options(selectinload(User.roles)).order_by(User.id).offset(offset).limit(min(limit, 200))
    users = (await db.execute(query)).unique().scalars().all()

    items = []
    for u in users:
        items.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
            "roles": [r.name for r in u.roles]
        })
    return {"items": items, "total": total, "limit": limit, "offset": offset}

@router.post("")
async def create_user(
    req: UserCreate,
    request: Request,
    user: User = Depends(require("user.manage")),
    db: AsyncSession = Depends(get_db)
):
    existing = (await db.execute(select(User).where(User.username == req.username))).unique().scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail={"code": "username_exists", "message": "Username already taken"})

    roles = (await db.execute(select(Role).where(Role.name.in_(req.roles)))).scalars().all()
    new_user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
        is_active=True,
        roles=list(roles)
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    await audit(db, "user_created", actor_user_id=user.id, object_type="user", object_id=new_user.id, detail={"username": new_user.username})
    return {
        "id": new_user.id,
        "username": new_user.username,
        "email": new_user.email,
        "is_active": new_user.is_active,
        "roles": [r.name for r in new_user.roles]
    }

@router.patch("/{user_id}")
async def update_user(
    user_id: int,
    req: UserUpdate,
    request: Request,
    user: User = Depends(require("user.manage")),
    db: AsyncSession = Depends(get_db)
):
    target = (await db.execute(select(User).where(User.id == user_id))).unique().scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail={"code": "user_not_found", "message": "User not found"})

    if req.is_active is False and target.id == user.id:
        raise HTTPException(status_code=409, detail={"code": "self_deactivation_forbidden", "message": "Admin cannot deactivate own account"})

    if req.email is not None:
        target.email = req.email
    if req.is_active is not None:
        target.is_active = req.is_active
        if not req.is_active:
            await audit(db, "user_deactivated", actor_user_id=user.id, object_type="user", object_id=target.id)
    if req.roles is not None:
        roles = (await db.execute(select(Role).where(Role.name.in_(req.roles)))).scalars().all()
        target.roles = list(roles)
        await audit(db, "user_role_changed", actor_user_id=user.id, object_type="user", object_id=target.id, detail={"roles": req.roles})

    await db.commit()
    await db.refresh(target)
    return {
        "id": target.id,
        "username": target.username,
        "email": target.email,
        "is_active": target.is_active,
        "roles": [r.name for r in target.roles]
    }

@router.post("/{user_id}/password")
async def update_password(
    user_id: int,
    req: PasswordUpdate,
    user: User = Depends(require("user.manage")),
    db: AsyncSession = Depends(get_db)
):
    target = (await db.execute(select(User).where(User.id == user_id))).unique().scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail={"code": "user_not_found", "message": "User not found"})

    target.password_hash = hash_password(req.password)
    await db.commit()
    return {"status": "ok"}

@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    user: User = Depends(require("user.manage")),
    db: AsyncSession = Depends(get_db)
):
    target = (await db.execute(select(User).where(User.id == user_id))).unique().scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail={"code": "user_not_found", "message": "User not found"})

    if target.id == user.id:
        raise HTTPException(status_code=409, detail={"code": "self_deactivation_forbidden", "message": "Cannot delete self"})

    runs_count = (await db.execute(select(func.count(JobRun.id)).where(JobRun.requested_by == user_id))).scalar_one()
    if runs_count > 0:
        raise HTTPException(status_code=409, detail={"code": "user_referenced", "message": "User has job runs, soft delete by setting is_active=false"})

    target.is_active = False
    await db.commit()
    return {"status": "ok"}
