from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.db.models import Project, User
from app.core.security import verify_password
from app.core.auth import create_access_token, create_refresh_token, decode_token
from app.core.rbac import get_user_permissions, get_project_permissions
from app.db.models import ProjectMembership
from app.core.config import settings
from app.services.audit import audit

router = APIRouter(prefix="/api", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    roles: List[str]
    perms: List[str]

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "Not authenticated"})
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "Invalid token type"})
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "Invalid token"})

    user = (await db.execute(select(User).options(selectinload(User.roles)).where(User.id == int(user_id)))).unique().scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "User inactive or not found"})
    return user

def require_csrf(request: Request):
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
            raise HTTPException(status_code=403, detail={"code": "csrf_missing", "message": "X-Requested-With header missing"})

def require(perm: str):
    async def dependency(request: Request, user: User = Depends(get_current_user)):
        require_csrf(request)
        perms = get_user_permissions(user.roles)
        if perm not in perms:
            raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Permission denied"})
        return user
    return dependency

def require_project(perm: str, param: str = "project_id"):
    async def dependency(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        require_csrf(request)
        raw_pid = request.path_params.get(param)
        if raw_pid is None:
            raw_pid = request.query_params.get(param)
        if raw_pid is None:
            raise HTTPException(status_code=400, detail={"code": "project_id_required", "message": "project_id is required"})
        try:
            project_id = int(raw_pid)
        except ValueError:
            raise HTTPException(status_code=400, detail={"code": "invalid_project_id", "message": "project_id must be integer"})

        project = (await db.execute(select(Project.id).where(Project.id == project_id))).scalar_one_or_none()
        if project is None:
            raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Project not found"})

        global_perms = get_user_permissions(user.roles)
        if "system.admin" in global_perms:
            return user

        res = await db.execute(
            select(ProjectMembership).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.user_id == user.id,
            )
        )
        membership = res.scalar_one_or_none()
        if not membership:
            raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Insufficient project permission"})
        role_str = membership.role.value if hasattr(membership.role, "value") else str(membership.role)
        proj_perms = get_project_permissions(role_str)
        if perm not in proj_perms:
            raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Insufficient project permission"})
        return user
    return dependency

@router.post("/auth/login")
async def login(req: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    require_csrf(request)
    user = (await db.execute(select(User).where(User.username == req.username))).unique().scalar_one_or_none()
    if not user or not verify_password(user.password_hash, req.password) or not user.is_active:
        await audit(db, "login_failed", detail={"username": req.username}, ip=request.client.host)
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "Invalid credentials"})

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        samesite="strict",
        secure=settings.COOKIE_SECURE,
        path="/"
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        samesite="strict",
        secure=settings.COOKIE_SECURE,
        path="/api/auth/refresh"
    )

    await audit(db, "login_success", actor_user_id=user.id, ip=request.client.host)
    roles = [r.name for r in user.roles]
    perms = list(get_user_permissions(user.roles))
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "roles": roles,
        "perms": perms
    }

@router.post("/auth/refresh")
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "No refresh token"})
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "Invalid token type"})
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "Invalid refresh token"})

    user = (await db.execute(select(User).where(User.id == int(user_id)))).unique().scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "User inactive"})

    access_token = create_access_token({"sub": str(user.id)})
    await audit(db, "token_refreshed", actor_user_id=user.id)
    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        samesite="strict",
        secure=settings.COOKIE_SECURE,
        path="/"
    )
    return {"status": "ok"}

@router.post("/auth/logout")
async def logout(response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    require_csrf(request)
    token = request.cookies.get("access_token")
    actor_user_id = None
    if token:
        try:
            payload = decode_token(token)
            if payload.get("type") == "access":
                actor_user_id = int(payload.get("sub"))
        except Exception:
            actor_user_id = None
    await audit(db, "logout", actor_user_id=actor_user_id)
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/auth/refresh")
    return {"status": "ok"}

@router.get("/me")
async def get_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    roles = [r.name for r in user.roles]
    perms = list(get_user_permissions(user.roles))
    res = await db.execute(select(ProjectMembership).where(ProjectMembership.user_id == user.id))
    memberships = res.scalars().all()
    project_perms = {}
    for m in memberships:
        role_str = m.role.value if hasattr(m.role, "value") else str(m.role)
        project_perms[str(m.project_id)] = sorted(list(get_project_permissions(role_str)))
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "roles": roles,
        "perms": perms,
        "project_perms": project_perms,
    }
