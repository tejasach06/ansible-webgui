
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.models import Credential, Inventory, JobTemplate, Schedule, User
from app.db.session import get_db
from app.services.audit import audit
from app.services.rbac_scope import assert_project_perm, inventory_visible_to_project, visible_project_ids
from app.services.surveys import validate_survey_spec
from app.services.credential_slots import SLOT_LABEL, find_slot_conflict


def survey_error(code: str) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": code, "message": code})

router = APIRouter(prefix="/api/job_templates", tags=["job_templates"])

async def _validate_credential_set(db: AsyncSession, credential_ids: list[int]) -> None:
    if credential_ids:
        rows = (await db.execute(select(Credential.name, Credential.username, Credential.kind).where(Credential.id.in_(credential_ids)))).all()
        user_rows = [(name, username) for name, username, _ in rows if username is not None]
        if len({username for _, username in user_rows}) > 1:
            raise HTTPException(status_code=422, detail={"code": "credential_user_conflict", "message": "Multiple selected credentials set different usernames", "credentials": [name for name, _ in user_rows]})
        conflict = find_slot_conflict([(name, kind) for name, _, kind in rows])
        if conflict:
            slot, names = conflict
            raise HTTPException(status_code=422, detail={"code": "credential_slot_conflict", "message": f"Select at most one {SLOT_LABEL[slot]} credential", "slot": slot, "credentials": names})

class JobTemplateCreate(BaseModel):
    project_id: int
    name: str
    description: str | None = None
    playbook_id: int
    inventory_id: int | None = None
    limit_pattern: str | None = None
    tags: str | None = None
    skip_tags: str | None = None
    extra_vars: dict = {}
    verbosity: int = 0
    forks: int = 5
    credential_ids: list[int] = []
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
    name: str | None = None
    description: str | None = None
    playbook_id: int | None = None
    inventory_id: int | None = None
    limit_pattern: str | None = None
    tags: str | None = None
    skip_tags: str | None = None
    extra_vars: dict | None = None
    verbosity: int | None = None
    forks: int | None = None
    credential_ids: list[int] | None = None
    requires_approval: bool | None = None
    diff_mode: bool | None = None
    survey_spec: list | None = None
    ask_limit: bool | None = None
    ask_tags: bool | None = None
    ask_skip_tags: bool | None = None
    ask_extra_vars: bool | None = None
    ask_verbosity: bool | None = None
    ask_diff: bool | None = None
    ask_credentials: bool | None = None
    ask_inventory: bool | None = None
    ask_mode: bool | None = None
@router.get("")
async def list_templates(
    project_id: int | None = None,
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
    await _validate_credential_set(db, req.credential_ids)
    if req.inventory_id is not None:
        inv = (await db.execute(select(Inventory).where(Inventory.id == req.inventory_id))).scalar_one_or_none()
        if not inv:
            raise HTTPException(status_code=404, detail={"code": "inventory_not_found", "message": "Inventory not found"})
        if not inventory_visible_to_project(inv, req.project_id):
            raise HTTPException(status_code=422, detail={"code": "inventory_not_in_project", "message": "That inventory belongs to another project"})
    try:
        validate_survey_spec(req.survey_spec)
    except ValueError as e:
        raise survey_error(str(e)) from None
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
        await _validate_credential_set(db, data["credential_ids"])
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
            raise survey_error(str(e)) from None
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
