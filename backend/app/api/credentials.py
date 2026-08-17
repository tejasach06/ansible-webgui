from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.models import Credential, CredentialKind, JobTemplate, User
from app.api.auth import get_current_user, require_csrf, require_project
from app.services.credentials import encrypt_payload
from app.services.audit import audit
from app.services.rbac_scope import assert_project_perm

router = APIRouter(prefix="/api/credentials", tags=["credentials"])

class CredentialCreate(BaseModel):
    project_id: int
    name: str
    kind: CredentialKind
    payload: str
    username: Optional[str] = None

class CredentialUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    payload: Optional[str] = None

def _credential_response(c: Credential):
    return {"id": c.id, "project_id": c.project_id, "name": c.name, "kind": c.kind, "username": c.username, "created_by": c.created_by}

async def _load_credential(db: AsyncSession, cred_id: int) -> Credential:
    c = (await db.execute(select(Credential).where(Credential.id == cred_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail={"code": "credential_not_found", "message": "Credential not found"})
    return c

@router.get("")
async def list_credentials(
    project_id: int,
    user: User = Depends(require_project("read")),
    db: AsyncSession = Depends(get_db)
):
    creds = (await db.execute(select(Credential).where(Credential.project_id == project_id))).scalars().all()
    return [_credential_response(c) for c in creds]

@router.post("")
async def create_credential(
    req: CredentialCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    require_csrf(request)
    await assert_project_perm(db, user, req.project_id, "credential.write")
    existing = (await db.execute(select(Credential).where(Credential.project_id == req.project_id, Credential.name == req.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail={"code": "name_exists", "message": "Credential name exists"})

    c = Credential(
        project_id=req.project_id,
        name=req.name,
        kind=req.kind,
        username=req.username or None,
        payload_enc=encrypt_payload(req.payload),
        created_by=user.id
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)

    await audit(db, "credential_created", actor_user_id=user.id, object_type="credential", object_id=c.id)
    return _credential_response(c)

@router.patch("/{cred_id}")
async def update_credential(
    cred_id: int,
    req: CredentialUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    require_csrf(request)
    c = await _load_credential(db, cred_id)
    await assert_project_perm(db, user, c.project_id, "credential.write")

    if req.name is not None and req.name != c.name:
        existing = (await db.execute(select(Credential).where(Credential.project_id == c.project_id, Credential.name == req.name, Credential.id != cred_id))).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail={"code": "name_exists", "message": "Credential name exists"})
        c.name = req.name
    if req.username is not None:
        c.username = req.username or None
    if req.payload:
        c.payload_enc = encrypt_payload(req.payload)

    await db.commit()
    await db.refresh(c)
    await audit(db, "credential_updated", actor_user_id=user.id, object_type="credential", object_id=c.id, detail={"rotated": req.payload is not None})
    return _credential_response(c)

@router.delete("/{cred_id}")
async def delete_credential(
    cred_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    require_csrf(request)
    c = await _load_credential(db, cred_id)
    await assert_project_perm(db, user, c.project_id, "credential.write")

    refs = (await db.execute(select(JobTemplate.name).where(JobTemplate.project_id == c.project_id, JobTemplate.credential_ids.any(cred_id)))).scalars().all()
    if refs:
        raise HTTPException(status_code=409, detail={"code": "credential_in_use", "message": "Credential is used by job templates", "templates": refs})

    await db.delete(c)
    await db.commit()
    await audit(db, "credential_deleted", actor_user_id=user.id, object_type="credential", object_id=cred_id)
    return {"status": "ok"}
