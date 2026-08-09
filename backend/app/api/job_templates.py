from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.db.models import Credential, JobTemplate, Schedule, User
from app.api.auth import require
from app.core.rbac import get_user_permissions
from app.services.surveys import validate_survey_spec

def survey_error(code: str) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": code, "message": code})

router = APIRouter(prefix="/api/job_templates", tags=["job_templates"])

async def _reject_credential_user_conflict(db: AsyncSession, credential_ids: List[int]) -> None:
    if credential_ids:
        rows = (await db.execute(select(Credential.name, Credential.username).where(Credential.id.in_(credential_ids), Credential.username.isnot(None)))).all()
        if len({username for _, username in rows}) > 1:
            raise HTTPException(status_code=422, detail={"code": "credential_user_conflict", "message": "Multiple selected credentials set different usernames", "credentials": [name for name, _ in rows]})


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
    diff_mode: bool = False
    survey_spec: list = []

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
    diff_mode: Optional[bool] = None
    survey_spec: Optional[list] = None

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
        "requires_approval": t.requires_approval,
        "diff_mode": t.diff_mode,
        "survey_spec": t.survey_spec,
    } for t in templates]

@router.post("")
async def create_template(
    req: JobTemplateCreate,
    user: User = Depends(require("schedule.write")),
    db: AsyncSession = Depends(get_db)
):
    perms = get_user_permissions(user.roles)
    requires_approval = req.requires_approval if "user.manage" in perms else True
    await _reject_credential_user_conflict(db, req.credential_ids)
    try:
        validate_survey_spec(req.survey_spec)
    except ValueError as e:
        raise survey_error(str(e))
    t = JobTemplate(**req.model_dump(exclude={"requires_approval"}), requires_approval=requires_approval)
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
    data = req.model_dump(exclude_unset=True)
    if "credential_ids" in data:
        await _reject_credential_user_conflict(db, data["credential_ids"])
    if "survey_spec" in data:
        try:
            validate_survey_spec(data["survey_spec"])
        except ValueError as e:
            raise survey_error(str(e))
    if "requires_approval" in data and "user.manage" not in get_user_permissions(user.roles):
        data.pop("requires_approval")
    for k, v in data.items():
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
    count = (await db.execute(select(func.count(Schedule.id)).where(Schedule.template_id == template_id))).scalar_one()
    if count:
        raise HTTPException(status_code=409, detail={"code": "template_in_use", "message": "Template is used by schedules"})
    await db.delete(t)
    await db.commit()
    return {"status": "ok"}
