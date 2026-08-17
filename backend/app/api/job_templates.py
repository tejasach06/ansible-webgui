from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.db.models import Credential, JobTemplate, Schedule, User, Inventory
from app.api.auth import get_current_user
from app.services.rbac_scope import assert_project_perm, visible_project_ids, inventory_visible_to_project
from app.services.surveys import validate_survey_spec
from app.services.audit import audit

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
    description: Optional[str] = None
    playbook_id: int
    inventory_id: Optional[int] = None
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
    ask_limit: bool = False
    ask_tags: bool = False
    ask_skip_tags: bool = False
    ask_extra_vars: bool = False
    ask_verbosity: bool = False
    ask_diff: bool = False
    ask_credentials: bool = False
    ask_inventory: bool = False
    ask_mode: bool = False

class JobTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
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
    ask_limit: Optional[bool] = None
    ask_tags: Optional[bool] = None
    ask_skip_tags: Optional[bool] = None
    ask_extra_vars: Optional[bool] = None
    ask_verbosity: Optional[bool] = None
    ask_diff: Optional[bool] = None
    ask_credentials: Optional[bool] = None
    ask_inventory: Optional[bool] = None
    ask_mode: Optional[bool] = None
@router.get("")
async def list_templates(
    project_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(JobTemplate)
    visible_ids = await visible_project_ids(db, user)
    if visible_ids is not None:
        query = query.where(JobTemplate.project_id.in_(visible_ids))
    if project_id is not None:
        query = query.where(JobTemplate.project_id == project_id)
    templates = (await db.execute(query)).scalars().all()
    return [{
        "id": t.id,
        "project_id": t.project_id,
        "name": t.name,
        "description": t.description,
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
        "ask_limit": t.ask_limit,
        "ask_tags": t.ask_tags,
        "ask_skip_tags": t.ask_skip_tags,
        "ask_extra_vars": t.ask_extra_vars,
        "ask_verbosity": t.ask_verbosity,
        "ask_diff": t.ask_diff,
        "ask_credentials": t.ask_credentials,
        "ask_inventory": t.ask_inventory,
        "ask_mode": t.ask_mode,
    } for t in templates]

@router.post("")
async def create_template(
    req: JobTemplateCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await assert_project_perm(db, user, req.project_id, "content.write")
    await _reject_credential_user_conflict(db, req.credential_ids)
    if req.inventory_id is not None:
        inv = (await db.execute(select(Inventory).where(Inventory.id == req.inventory_id))).scalar_one_or_none()
        if not inv:
            raise HTTPException(status_code=404, detail={"code": "inventory_not_found", "message": "Inventory not found"})
        if not inventory_visible_to_project(inv, req.project_id):
            raise HTTPException(status_code=422, detail={"code": "inventory_not_in_project", "message": "That inventory belongs to another project"})
    try:
        validate_survey_spec(req.survey_spec)
    except ValueError as e:
        raise survey_error(str(e))
    t = JobTemplate(**req.model_dump())
    db.add(t)
    await db.commit()
    await db.refresh(t)
    await audit(db, "template_created", actor_user_id=user.id, object_type="job_template", object_id=t.id, detail={"project_id": t.project_id})
    return {"id": t.id, "name": t.name}

@router.patch("/{template_id}")
async def update_template(
    template_id: int,
    req: JobTemplateUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    t = (await db.execute(select(JobTemplate).where(JobTemplate.id == template_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail={"code": "template_not_found", "message": "Template not found"})
    await assert_project_perm(db, user, t.project_id, "content.write")
    data = req.model_dump(exclude_unset=True)
    if "credential_ids" in data:
        await _reject_credential_user_conflict(db, data["credential_ids"])
    if "inventory_id" in data:
        if data["inventory_id"] == 0:
            data["inventory_id"] = None
        elif data["inventory_id"] is not None:
            inv = (await db.execute(select(Inventory).where(Inventory.id == data["inventory_id"]))).scalar_one_or_none()
            if not inv:
                raise HTTPException(status_code=404, detail={"code": "inventory_not_found", "message": "Inventory not found"})
            if not inventory_visible_to_project(inv, t.project_id):
                raise HTTPException(status_code=422, detail={"code": "inventory_not_in_project", "message": "That inventory belongs to another project"})
    if "survey_spec" in data:
        try:
            validate_survey_spec(data["survey_spec"])
        except ValueError as e:
            raise survey_error(str(e))
    for k, v in data.items():
        setattr(t, k, v)
    await db.commit()
    await db.refresh(t)
    await audit(db, "template_updated", actor_user_id=user.id, object_type="job_template", object_id=t.id)
    return {"id": t.id, "name": t.name}

@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    t = (await db.execute(select(JobTemplate).where(JobTemplate.id == template_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail={"code": "template_not_found", "message": "Template not found"})
    await assert_project_perm(db, user, t.project_id, "content.write")
    count = (await db.execute(select(func.count(Schedule.id)).where(Schedule.template_id == template_id))).scalar_one()
    if count:
        raise HTTPException(status_code=409, detail={"code": "template_in_use", "message": "Template is used by schedules"})
    await db.delete(t)
    await db.commit()
    await audit(db, "template_deleted", actor_user_id=user.id, object_type="job_template", object_id=template_id)
    return {"status": "ok"}
