import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.db.models import Project, Playbook, JobRun, JobStatus, User
from app.api.auth import require
from app.services.audit import audit
from app.services.content import init_project_repo, get_project_repo_path
from app.core.config import settings

router = APIRouter(prefix="/api/projects", tags=["projects"])

class ProjectCreate(BaseModel):
    name: str

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    default_branch: Optional[str] = None

def _project_response(p: Project):
    return {"id": p.id, "name": p.name, "git_path": p.git_path, "default_branch": p.default_branch, "is_inventory_repo": p.name == settings.INVENTORY_REPO_NAME}

def _validate_project_name(name: str) -> None:
    if name in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", name):
        raise HTTPException(status_code=400, detail={"code": "bad_name", "message": "Project name must be 1-64 chars of letters, digits, dot, dash or underscore"})

@router.get("")
async def list_projects(
    user: User = Depends(require("read")),
    db: AsyncSession = Depends(get_db)
):
    projects = (await db.execute(select(Project))).scalars().all()
    return [_project_response(p) for p in projects]

@router.post("")
async def create_project(
    req: ProjectCreate,
    user: User = Depends(require("content.write")),
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
    await db.refresh(p)

    await init_project_repo(db, p, user.username, user.email)
    return _project_response(p)

@router.patch("/{project_id}")
async def update_project(
    project_id: int,
    req: ProjectUpdate,
    user: User = Depends(require("content.write")),
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

    await db.commit()
    await db.refresh(p)
    if old_name != p.name:
        await audit(db, "project_renamed", actor_user_id=user.id, object_type="project", object_id=p.id, detail={"from": old_name, "to": p.name})
    return _project_response(p)

@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    user: User = Depends(require("content.write")),
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
    return {"status": "ok"}
