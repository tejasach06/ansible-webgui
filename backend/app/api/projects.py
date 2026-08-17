import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.db.models import Project, Playbook, JobRun, JobStatus, User, ProjectMembership, ProjectRole, Inventory
from app.api.auth import require, require_project
from app.services.rbac_scope import visible_project_ids, inventory_visible_to_project
from app.services.audit import audit
from app.services.content import init_project_repo, get_project_repo_path
from app.core.config import settings

router = APIRouter(prefix="/api/projects", tags=["projects"])

class ProjectCreate(BaseModel):
    name: str

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    default_branch: Optional[str] = None
    default_inventory_id: Optional[int] = None

class MemberRoleUpdate(BaseModel):
    role: ProjectRole

def _project_response(p: Project):
    return {
        "id": p.id,
        "name": p.name,
        "git_path": p.git_path,
        "default_branch": p.default_branch,
        "default_inventory_id": p.default_inventory_id,
        "is_inventory_repo": p.name == settings.INVENTORY_REPO_NAME,
    }

def _validate_project_name(name: str) -> None:
    if name in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", name):
        raise HTTPException(status_code=400, detail={"code": "bad_name", "message": "Project name must be 1-64 chars of letters, digits, dot, dash or underscore"})

@router.get("")
async def list_projects(
    user: User = Depends(require("read")),
    db: AsyncSession = Depends(get_db)
):
    vids = await visible_project_ids(db, user)
    stmt = select(Project)
    if vids is not None:
        stmt = stmt.where(Project.id.in_(vids))
    projects = (await db.execute(stmt)).scalars().all()
    return [_project_response(p) for p in projects]

@router.get("/{project_id}")
async def get_project(
    project_id: int,
    user: User = Depends(require_project("read")),
    db: AsyncSession = Depends(get_db)
):
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Project not found"})
    return _project_response(p)

@router.post("")
async def create_project(
    req: ProjectCreate,
    user: User = Depends(require("project.create")),
    db: AsyncSession = Depends(get_db)
):
    if req.name == settings.INVENTORY_REPO_NAME:
        raise HTTPException(status_code=400, detail={"code": "reserved_project_name", "message": "That project name is reserved for the shared inventory repo."})
    _validate_project_name(req.name)
    existing = (await db.execute(select(Project).where(Project.name == req.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail={"code": "name_exists", "message": "Project name exists"})

    p = Project(name=req.name, git_path=f"/data/content/{req.name}", default_branch="main")
    db.add(p)
    await db.commit()
    db.add(ProjectMembership(project_id=p.id, user_id=user.id, role=ProjectRole.owner))
    await db.commit()
    await db.refresh(p)

    await init_project_repo(db, p, user.username, user.email)
    await audit(db, "project_created", actor_user_id=user.id, object_type="project", object_id=p.id)
    return _project_response(p)

@router.patch("/{project_id}")
async def update_project(
    project_id: int,
    req: ProjectUpdate,
    user: User = Depends(require_project("project.admin")),
    db: AsyncSession = Depends(get_db)
):
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Project not found"})
    if p.name == settings.INVENTORY_REPO_NAME and req.name is not None and req.name != p.name:
        raise HTTPException(status_code=409, detail={"code": "inventory_repo_immutable", "message": "The shared inventory repo cannot be renamed."})

    old_name = p.name
    if req.name is not None and req.name != p.name:
        if req.name == settings.INVENTORY_REPO_NAME:
            raise HTTPException(status_code=400, detail={"code": "reserved_project_name", "message": "That project name is reserved for the shared inventory repo."})
        _validate_project_name(req.name)
        existing = (await db.execute(select(Project).where(Project.name == req.name, Project.id != project_id))).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail={"code": "name_exists", "message": "Project name exists"})
        pbs = (await db.execute(select(Playbook.id).where(Playbook.project_id == project_id))).scalars().all()
        if pbs:
            active = (await db.execute(select(func.count(JobRun.id)).where(JobRun.playbook_id.in_(pbs), JobRun.status.in_([JobStatus.pending_approval, JobStatus.approved, JobStatus.queued, JobStatus.running])))).scalar_one()
            if active:
                raise HTTPException(status_code=409, detail={"code": "project_busy", "message": "Project has pending or running jobs; rename after they finish"})
        old = get_project_repo_path(p.name)
        new = get_project_repo_path(req.name)
        if new.exists():
            raise HTTPException(status_code=409, detail={"code": "path_exists", "message": "Target repo directory already exists"})
        try:
            if old.exists():
                old.rename(new)
        except OSError as exc:
            raise HTTPException(status_code=500, detail={"code": "rename_failed", "message": str(exc)})
        p.name = req.name
        p.git_path = str(new)
    if req.default_branch is not None:
        p.default_branch = req.default_branch
    if req.default_inventory_id is not None:
        if req.default_inventory_id == 0:
            p.default_inventory_id = None
        else:
            inv = (await db.execute(select(Inventory).where(Inventory.id == req.default_inventory_id))).scalar_one_or_none()
            if not inv:
                raise HTTPException(status_code=404, detail={"code": "inventory_not_found", "message": "Inventory not found"})
            if not inventory_visible_to_project(inv, project_id):
                raise HTTPException(status_code=422, detail={"code": "inventory_not_in_project", "message": "That inventory belongs to another project"})
            p.default_inventory_id = req.default_inventory_id
        await audit(db, "project_default_inventory_set", actor_user_id=user.id, object_type="project", object_id=project_id, detail={"inventory_id": p.default_inventory_id})

    await db.commit()
    await db.refresh(p)
    if old_name != p.name:
        await audit(db, "project_renamed", actor_user_id=user.id, object_type="project", object_id=p.id, detail={"from": old_name, "to": p.name})
    return _project_response(p)

@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    user: User = Depends(require_project("project.admin")),
    db: AsyncSession = Depends(get_db)
):
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Project not found"})
    if p.name == settings.INVENTORY_REPO_NAME:
        raise HTTPException(status_code=409, detail={"code": "inventory_repo_undeletable", "message": "The shared inventory repo cannot be deleted."})

    pbs = (await db.execute(select(Playbook.id).where(Playbook.project_id == project_id))).scalars().all()
    if pbs:
        runs_count = (await db.execute(select(func.count(JobRun.id)).where(JobRun.playbook_id.in_(pbs)))).scalar_one()
        if runs_count > 0:
            raise HTTPException(status_code=409, detail={"code": "project_has_runs", "message": "Project has job runs and cannot be deleted"})

    await db.delete(p)
    await db.commit()
    await audit(db, "project_deleted", actor_user_id=user.id, object_type="project", object_id=project_id)
    return {"status": "ok"}
@router.get("/{project_id}/members")
async def list_members(
    project_id: int,
    user: User = Depends(require_project("read")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(ProjectMembership, User.username)
        .join(User, ProjectMembership.user_id == User.id)
        .where(ProjectMembership.project_id == project_id)
    )
    rows = res.all()
    return [
        {
            "user_id": m.user_id,
            "username": uname,
            "role": m.role.value if hasattr(m.role, "value") else str(m.role),
        }
        for m, uname in rows
    ]

@router.put("/{project_id}/members/{target_user_id}")
async def upsert_member(
    project_id: int,
    target_user_id: int,
    req: MemberRoleUpdate,
    user: User = Depends(require_project("project.admin")),
    db: AsyncSession = Depends(get_db)
):
    target_user = (await db.execute(select(User).where(User.id == target_user_id))).scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail={"code": "user_not_found", "message": "User not found"})

    res = await db.execute(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == target_user_id,
        )
    )
    membership = res.scalar_one_or_none()
    if membership:
        membership.role = req.role
    else:
        membership = ProjectMembership(project_id=project_id, user_id=target_user_id, role=req.role)
        db.add(membership)

    await db.commit()
    await audit(db, "member_granted", actor_user_id=user.id, object_type="project_membership", object_id=project_id, detail={"user_id": target_user_id, "role": req.role.value if hasattr(req.role, "value") else str(req.role)})
    return {
        "user_id": target_user_id,
        "username": target_user.username,
        "role": req.role.value if hasattr(req.role, "value") else str(req.role),
    }

@router.delete("/{project_id}/members/{target_user_id}", status_code=204)
async def delete_member(
    project_id: int,
    target_user_id: int,
    user: User = Depends(require_project("project.admin")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == target_user_id,
        )
    )
    membership = res.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail={"code": "member_not_found", "message": "Membership not found"})

    role_str = membership.role.value if hasattr(membership.role, "value") else str(membership.role)
    if role_str == "owner":
        owner_count = (
            await db.execute(
                select(func.count(ProjectMembership.id)).where(
                    ProjectMembership.project_id == project_id,
                    ProjectMembership.role == ProjectRole.owner,
                )
            )
        ).scalar_one()
        if owner_count <= 1:
            raise HTTPException(status_code=409, detail={"code": "last_owner", "message": "Project must retain an owner"})

    await db.delete(membership)
    await db.commit()
    await audit(db, "member_revoked", actor_user_id=user.id, object_type="project_membership", object_id=project_id, detail={"user_id": target_user_id})
    return None
