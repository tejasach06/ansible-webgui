from typing import Optional, Literal
import anyio
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.models import Credential, CredentialKind, JobTemplate, User, Project, Playbook
from app.api.auth import get_current_user, require_csrf
from app.services.credentials import encrypt_payload
from app.services.ssh_keys import generate_keypair
from app.services.content import commit_file, get_project_repo_path, validate_safe_path
from app.services.audit import audit
from app.services.rbac_scope import assert_project_perm, visible_project_ids
router = APIRouter(prefix="/api/credentials", tags=["credentials"])

class CredentialCreate(BaseModel):
    project_id: int
    name: str
    kind: CredentialKind
    payload: str
    username: Optional[str] = None
    become_same_as_ssh: bool = False

class CredentialUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    payload: Optional[str] = None
    become_same_as_ssh: Optional[bool] = None

class CredentialGenerate(BaseModel):
    project_id: int
    name: str
    username: Optional[str] = None
    key_type: Literal["ed25519", "rsa4096"] = "ed25519"
def _credential_response(c: Credential):
    return {
        "id": c.id,
        "project_id": c.project_id,
        "name": c.name,
        "kind": c.kind,
        "username": c.username,
        "become_same_as_ssh": c.become_same_as_ssh,
        "public_key": c.public_key,
        "created_by": c.created_by,
    }

def _check_become_flag(kind: CredentialKind, flag: bool) -> None:
    if flag and kind != CredentialKind.ssh_password:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "become_same_requires_ssh_password",
                "message": "Only an ssh_password credential can be reused for the become password",
            },
        )

async def _load_credential(db: AsyncSession, cred_id: int) -> Credential:
    c = (await db.execute(select(Credential).where(Credential.id == cred_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail={"code": "credential_not_found", "message": "Credential not found"})
    return c

@router.get("")
async def list_credentials(
    project_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Credential)
    if project_id is not None:
        await assert_project_perm(db, user, project_id, "read")
        stmt = stmt.where(Credential.project_id == project_id)
    else:
        pids = await visible_project_ids(db, user)
        if pids is not None:
            stmt = stmt.where(Credential.project_id.in_(pids))
    creds = (await db.execute(stmt)).scalars().all()
    return [_credential_response(c) for c in creds]

@router.post("/generate")
async def generate_credential(
    req: CredentialGenerate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_csrf(request)
    await assert_project_perm(db, user, req.project_id, "credential.write")
    existing = (
        await db.execute(
            select(Credential).where(
                Credential.project_id == req.project_id,
                Credential.name == req.name,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail={"code": "name_exists", "message": "Credential name exists"})

    comment = f"ansible-webgui:{req.project_id}/{req.name}"
    try:
        private_pem, public_line = await anyio.to_thread.run_sync(
            generate_keypair, req.key_type, comment
        )
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"code": "bad_key_type", "message": "Unsupported key type"},
        )

    c = Credential(
        project_id=req.project_id,
        name=req.name,
        kind=CredentialKind.ssh_key,
        username=req.username or None,
        become_same_as_ssh=False,
        public_key=public_line,
        payload_enc=encrypt_payload(private_pem),
        created_by=user.id,
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    await audit(
        db,
        "credential_generated",
        actor_user_id=user.id,
        object_type="credential",
        object_id=c.id,
        detail={"key_type": req.key_type},
    )
    return _credential_response(c)

@router.post("")
async def create_credential(
    req: CredentialCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    require_csrf(request)
    await assert_project_perm(db, user, req.project_id, "credential.write")
    _check_become_flag(req.kind, req.become_same_as_ssh)
    existing = (await db.execute(select(Credential).where(Credential.project_id == req.project_id, Credential.name == req.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail={"code": "name_exists", "message": "Credential name exists"})

    c = Credential(
        project_id=req.project_id,
        name=req.name,
        kind=req.kind,
        username=req.username or None,
        become_same_as_ssh=req.become_same_as_ssh,
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
    if req.become_same_as_ssh is not None:
        _check_become_flag(c.kind, req.become_same_as_ssh)
        c.become_same_as_ssh = req.become_same_as_ssh

    if req.name is not None and req.name != c.name:
        existing = (await db.execute(select(Credential).where(Credential.project_id == c.project_id, Credential.name == req.name, Credential.id != cred_id))).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail={"code": "name_exists", "message": "Credential name exists"})
        c.name = req.name
    if req.username is not None:
        c.username = req.username or None
    if req.payload:
        c.payload_enc = encrypt_payload(req.payload)
        c.public_key = None
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

BOOTSTRAP_PLAYBOOK_CONTENT = """---
- name: Install WebGUI generated public key
  hosts: all
  gather_facts: false
  become: true
  vars:
    webgui_public_key: ""
    webgui_target_user: "{{ ansible_user | default(ansible_user_id) }}"
  tasks:
    - name: Fail when no public key was supplied
      ansible.builtin.assert:
        that:
          - webgui_public_key | length > 0
        fail_msg: Pass webgui_public_key in extra vars

    - name: Ensure .ssh directory exists
      ansible.builtin.file:
        path: "~{{ webgui_target_user }}/.ssh"
        state: directory
        owner: "{{ webgui_target_user }}"
        mode: "0700"

    - name: Ensure public key is authorized
      ansible.builtin.lineinfile:
        path: "~{{ webgui_target_user }}/.ssh/authorized_keys"
        line: "{{ webgui_public_key }}"
        create: true
        owner: "{{ webgui_target_user }}"
        mode: "0600"
        state: present
"""


@router.post("/{cred_id}/bootstrap-playbook")
async def create_bootstrap_playbook(
    cred_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_csrf(request)
    c = await _load_credential(db, cred_id)
    await assert_project_perm(db, user, c.project_id, "content.write")

    if c.kind != CredentialKind.ssh_key or not c.public_key:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "not_generated_key",
                "message": "Only a generated ssh_key credential has a public key to deploy",
            },
        )

    project = (
        await db.execute(select(Project).where(Project.id == c.project_id))
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=404,
            detail={"code": "project_not_found", "message": "Project not found"},
        )

    rel_path = "playbooks/_webgui_bootstrap_authorized_key.yml"
    repo_path = get_project_repo_path(project.name)
    try:
        file_path = validate_safe_path(repo_path, rel_path)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"code": "bad_path", "message": "Invalid path"},
        )

    disk_content = file_path.read_text() if file_path.exists() else None
    if disk_content != BOOTSTRAP_PLAYBOOK_CONTENT:
        await commit_file(
            db=db,
            project=project,
            rel_path=rel_path,
            content=BOOTSTRAP_PLAYBOOK_CONTENT,
            message="Add WebGUI authorized_key bootstrap playbook",
            base_sha=None,
            user=user,
            lint=True,
        )

    pb = (
        await db.execute(
            select(Playbook).where(
                Playbook.project_id == project.id,
                Playbook.rel_path == rel_path,
            )
        )
    ).scalar_one_or_none()
    if not pb:
        pb = Playbook(
            project_id=project.id,
            rel_path=rel_path,
            name="Bootstrap authorized_key",
        )
        db.add(pb)
        await db.commit()
        await db.refresh(pb)

    await audit(
        db,
        "credential_bootstrap_playbook_ready",
        actor_user_id=user.id,
        object_type="credential",
        object_id=c.id,
        detail={"playbook_id": pb.id, "rel_path": rel_path},
    )

    return {
        "playbook_id": pb.id,
        "rel_path": rel_path,
        "public_key": c.public_key,
    }
