import anyio
import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.models import Inventory, InventoryFormat, JobTemplate, User
from app.db.session import get_db
from app.services.audit import audit
from app.services.content import (
    commit_file,
    ensure_inventory_repo,
    get_inventory_repo_path,
    validate_safe_path,
    verify_inventory_file,
)
from app.services.rbac_scope import assert_project_perm, has_inventory_write

router = APIRouter(prefix="/api/inventories", tags=["inventories"])
INVENTORY_DIR = "inventories"


class InventoryRegister(BaseModel):
    filename: str
    name: str
    format: InventoryFormat
    project_id: int | None = None
    content: str | None = None
    message: str | None = None


class InventoryFileSave(BaseModel):
    content: str
    message: str
    base_sha: str | None = None


class InventoryUpdate(BaseModel):
    name: str | None = None
    format: InventoryFormat | None = None


async def _load_inventory(db: AsyncSession, inventory_id: int) -> Inventory:
    inv = (await db.execute(select(Inventory).where(Inventory.id == inventory_id))).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail={"code": "inventory_not_found", "message": "Inventory row not found"})
    return inv


def _inventory_response(inv: Inventory):
    return {"id": inv.id, "rel_path": inv.rel_path, "name": inv.name, "format": inv.format, "project_id": inv.project_id}


def _inventory_rel_path(filename: str, project_name: str | None = None) -> str:
    fn = filename.strip()
    if not fn or "/" in fn or "\\" in fn or fn.startswith(".") or fn in {".", ".."}:
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Filename must be a plain file name inside inventories/, with no path separators"})
    if fn.endswith((".py", ".sh")):
        raise HTTPException(status_code=400, detail={"code": "executable_inventory_forbidden", "message": "Executable inventories forbidden"})
    if project_name:
        return f"{INVENTORY_DIR}/{project_name}/{fn}"
    return f"{INVENTORY_DIR}/{fn}"


async def _ensure_inventory_write(db: AsyncSession, user: User) -> None:
    if not await has_inventory_write(db, user):
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Insufficient project permission"})


@router.get("")
async def list_inventories(
    request: Request,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Inventory)
    if "project_id" in request.query_params:
        pid_str = request.query_params["project_id"]
        try:
            pid = int(pid_str)
        except ValueError:
            raise HTTPException(status_code=422, detail={"code": "bad_query", "message": "project_id must be an integer"}) from None
        stmt = stmt.where(or_(Inventory.project_id.is_(None), Inventory.project_id == pid))

    invs = (await db.execute(stmt)).scalars().all()
    return [_inventory_response(inv) for inv in invs]


@router.post("")
async def register_inventory(
    req: InventoryRegister,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    project_name: str | None = None
    if req.project_id is not None:
        await assert_project_perm(db, user, req.project_id, "content.write")
        from app.db.models import Project
        project = (await db.execute(select(Project).where(Project.id == req.project_id))).scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Project not found"})
        project_name = project.name
    else:
        await _ensure_inventory_write(db, user)

    rel_path = _inventory_rel_path(req.filename, project_name)
    repo_path = get_inventory_repo_path()
    if not (repo_path / ".git").exists():
        raise HTTPException(status_code=404, detail={"code": "inventory_repo_missing", "message": "Shared inventory repo is not initialized. Restart the API."})
    try:
        file_path = validate_safe_path(repo_path, rel_path)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Invalid path"}) from None

    # Scope-aware duplicate check
    duplicate_path = (await db.execute(select(Inventory).where(Inventory.rel_path == rel_path))).scalar_one_or_none()
    if duplicate_path:
        raise HTTPException(status_code=400, detail={"code": "name_exists", "message": "Inventory name or path already registered"})

    scope_cond = Inventory.project_id.is_(None) if req.project_id is None else Inventory.project_id == req.project_id
    duplicate_name = (await db.execute(select(Inventory).where(and_(Inventory.name == req.name, scope_cond)))).scalar_one_or_none()
    if duplicate_name:
        raise HTTPException(status_code=400, detail={"code": "name_exists", "message": "Inventory name or path already registered"})

    if not file_path.is_file():
        if req.content is None:
            raise HTTPException(status_code=404, detail={"code": "file_not_found", "message": "Inventory file not found in git repo"})
        if req.format == InventoryFormat.yaml:
            try:
                yaml.safe_load(req.content)
            except yaml.YAMLError as exc:
                raise HTTPException(status_code=422, detail={"code": "invalid_yaml", "message": "Inventory YAML is invalid", "stderr": str(exc)}) from None
        inv_proj = await ensure_inventory_repo(db)
        await commit_file(
            db=db,
            project=inv_proj,
            rel_path=rel_path,
            content=req.content,
            message=req.message or f"Create inventory {req.name}",
            base_sha=None,
            user=user,
            lint=False,
            verify_inventory=True,
        )
    else:
        # File exists; verify it before registering row
        verify_inventory_file(file_path)

    inv = Inventory(rel_path=rel_path, name=req.name, format=req.format, project_id=req.project_id)
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    await audit(db, "inventory_registered", actor_user_id=user.id, object_type="inventory", object_id=inv.id, detail={"path": inv.rel_path, "project_id": inv.project_id})
    return _inventory_response(inv)


@router.get("/{inventory_id}/file")
async def get_inventory_file(
    inventory_id: int,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from git import Repo
    inv = await _load_inventory(db, inventory_id)
    repo_path = get_inventory_repo_path()
    try:
        file_path = validate_safe_path(repo_path, inv.rel_path)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Invalid path"}) from None
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail={"code": "file_not_found", "message": "Inventory file not found in git repo"})
    sha = await anyio.to_thread.run_sync(lambda: Repo(repo_path).head.commit.hexsha)
    return {"id": inv.id, "rel_path": inv.rel_path, "format": inv.format, "content": file_path.read_text(), "sha": sha}


@router.post("/{inventory_id}/file")
async def save_inventory_file(
    inventory_id: int,
    req: InventoryFileSave,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    inv = await _load_inventory(db, inventory_id)
    if inv.project_id is not None:
        await assert_project_perm(db, user, inv.project_id, "content.write")
    else:
        await _ensure_inventory_write(db, user)
    if inv.format == InventoryFormat.yaml:
        try:
            yaml.safe_load(req.content)
        except yaml.YAMLError as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_yaml", "message": "Inventory YAML is invalid", "stderr": str(exc)}) from None
    inv_proj = await ensure_inventory_repo(db)
    sha = await commit_file(
        db=db,
        project=inv_proj,
        rel_path=inv.rel_path,
        content=req.content,
        message=req.message or f"Update inventory {inv.name}",
        base_sha=req.base_sha,
        user=user,
        lint=False,
        verify_inventory=True,
    )
    await audit(db, "inventory_file_saved", actor_user_id=user.id, object_type="inventory", object_id=inv.id, detail={"sha": sha})
    return {"status": "ok", "sha": sha}


@router.post("/{inventory_id}/verify")
async def verify_inventory(
    inventory_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    inv = await _load_inventory(db, inventory_id)
    if inv.project_id is not None:
        await assert_project_perm(db, user, inv.project_id, "content.write")
    else:
        await _ensure_inventory_write(db, user)
    repo_path = get_inventory_repo_path()
    try:
        file_path = validate_safe_path(repo_path, inv.rel_path)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Invalid path"}) from None
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail={"code": "file_not_found", "message": "Inventory file not found in git repo"})

    parsed = verify_inventory_file(file_path)
    hosts_set = set(parsed.get("_meta", {}).get("hostvars", {}).keys())
    for k, v in parsed.items():
        if k != "_meta" and isinstance(v, dict):
            for h in v.get("hosts", []):
                hosts_set.add(h)
    hosts = sorted(hosts_set)
    groups = {g: v.get("hosts", []) for g, v in parsed.items() if g != "_meta" and isinstance(v, dict)}
    return {"hosts": hosts, "groups": groups, "raw": parsed}


@router.patch("/{inventory_id}")
async def update_inventory(
    inventory_id: int,
    req: InventoryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    inv = await _load_inventory(db, inventory_id)
    if inv.project_id is not None:
        await assert_project_perm(db, user, inv.project_id, "content.write")
    else:
        await _ensure_inventory_write(db, user)
    if req.name is not None and req.name != inv.name:
        scope_cond = Inventory.project_id.is_(None) if inv.project_id is None else Inventory.project_id == inv.project_id
        duplicate = (await db.execute(select(Inventory).where(and_(Inventory.name == req.name, scope_cond, Inventory.id != inventory_id)))).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=400, detail={"code": "name_exists", "message": "Inventory name or path already registered"})
        inv.name = req.name
    if req.format is not None:
        inv.format = req.format
    await db.commit()
    await db.refresh(inv)
    await audit(db, "inventory_updated", actor_user_id=user.id, object_type="inventory", object_id=inv.id)
    return _inventory_response(inv)


@router.delete("/{inventory_id}")
async def delete_inventory_row(
    inventory_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    inv = await _load_inventory(db, inventory_id)
    if inv.project_id is not None:
        await assert_project_perm(db, user, inv.project_id, "content.write")
    else:
        await _ensure_inventory_write(db, user)
    refs = (await db.execute(select(func.count(JobTemplate.id)).where(JobTemplate.inventory_id == inventory_id))).scalar_one()
    if refs:
        raise HTTPException(status_code=409, detail={"code": "inventory_in_use", "message": "Inventory is used by job templates"})
    await db.delete(inv)
    await db.commit()
    await audit(db, "inventory_deleted", actor_user_id=user.id, object_type="inventory", object_id=inventory_id)
    return {"status": "ok"}
