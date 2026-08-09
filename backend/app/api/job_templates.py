from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.db.models import Credential, JobTemplate, Schedule, User
from app.api.auth import require
from app.core.rbac import get_user_permissions

router = APIRouter(prefix="/api/job_templates", tags=["job_templates"])

async def _reject_credential_user_conflict(db: AsyncSession, credential_ids: List[int]) -> None:
    if credential_ids:
        named = (await db.execute(select(Credential.name).where(Credential.id.in_(credential_ids), Credential.username.isnot(None)))).scalars().all()
        if len(named) > 1:
            raise HTTPException(status_code=422, detail={"code": "credential_user_conflict", "message": "Multiple selected credentials set a username", "credentials": named})


class JobTemplateCreate(BaseModel):
    project_id: int
    name: str
    playbook_id: int
    inventory_id: int
    limit_pattern: Optional[str] = None
    tags: Optional[str] = None
    skip_tags: Optional[str] = None
    extra_vars: dict = {}
    verbosity: int = 0
    forks: int = 5
    credential_ids: List[int] = []
    requires_approval: bool = True

class JobTemplateUpdate(BaseModel):
    name: Optional[str] = None
    playbook_id: Optional[int] = None
    inventory_id: Optional[int] = None
    limit_pattern: Optional[str] = None
    tags: Optional[str] = None
    skip_tags: Optional[str] = None
    extra_vars: Optional[dict] = None
    verbosity: Optional[int] = None
    forks: Optional[int] = None
    credential_ids: Optional[List[int]] = None
    requires_approval: Optional[bool] = None

@router.get("")
async def list_templates(
    project_id: Optional[int] = None,
    user: User = Depends(require("read")),
    db: AsyncSession = Depends(get_db)
):
    query = select(JobTemplate)
    if project_id:
        query = query.where(JobTemplate.project_id == project_id)
    templates = (await db.execute(query)).scalars().all()
    return [{
        "id": t.id,
        "project_id": t.project_id,
        "name": t.name,
        "playbook_id": t.playbook_id,
        "inventory_id": t.inventory_id,
        "limit_pattern": t.limit_pattern,
        "tags": t.tags,
        "skip_tags": t.skip_tags,
        "extra_vars": t.extra_vars,
        "verbosity": t.verbosity,
        "forks": t.forks,
        "credential_ids": t.credential_ids,
        "requires_approval": t.requires_approval
    } for t in templates]

@router.post("")
async def create_template(
    req: JobTemplateCreate,
    user: User = Depends(require("schedule.write")),
    db: AsyncSession = Depends(get_db)
):
    perms = get_user_permissions(user.roles)
    if req.requires_approval is False and "user.manage" not in perms: # Admin check
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Only admin can set requires_approval=false"})

    await _reject_credential_user_conflict(db, req.credential_ids)

    t = JobTemplate(**req.model_dump())
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return {"id": t.id, "name": t.name}

@router.patch("/{template_id}")
async def update_template(
    template_id: int,
    req: JobTemplateUpdate,
    user: User = Depends(require("schedule.write")),
    db: AsyncSession = Depends(get_db)
):
    t = (await db.execute(select(JobTemplate).where(JobTemplate.id == template_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail={"code": "template_not_found", "message": "Template not found"})

    perms = get_user_permissions(user.roles)
    if req.requires_approval is False and "user.manage" not in perms:
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Only admin can set requires_approval=false"})

    if req.credential_ids is not None:
        await _reject_credential_user_conflict(db, req.credential_ids)

    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(t, k, v)

    await db.commit()
    await db.refresh(t)
    return {"id": t.id, "name": t.name}

@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    user: User = Depends(require("schedule.write")),
    db: AsyncSession = Depends(get_db)
):
    t = (await db.execute(select(JobTemplate).where(JobTemplate.id == template_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail={"code": "template_not_found", "message": "Template not found"})

    schedules_count = (await db.execute(select(func.count(Schedule.id)).where(Schedule.template_id == template_id))).scalar_one()
    if schedules_count > 0:
        raise HTTPException(status_code=409, detail={"code": "template_in_use", "message": "Template referenced by active schedule"})

    await db.delete(t)
    await db.commit()
    return {"status": "ok"}
