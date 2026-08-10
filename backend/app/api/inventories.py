from typing import Optional
import yaml
from git import Actor, Repo
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select, func
from app.db.session import get_db
from app.db.models import Commit, Inventory, InventoryFormat, JobTemplate, User
from app.api.auth import require
from app.services.content import ensure_inventory_repo, get_inventory_repo_path, validate_safe_path

router = APIRouter(prefix="/api/inventories", tags=["inventories"])
INVENTORY_DIR = "inventories"


class InventoryRegister(BaseModel):
    filename: str
    name: str
    format: InventoryFormat
    content: Optional[str] = None
    message: Optional[str] = None

class InventoryFileSave(BaseModel):
    content: str
    message: str
    base_sha: Optional[str] = None

class InventoryUpdate(BaseModel):
    name: Optional[str] = None
    format: Optional[InventoryFormat] = None

async def _load_inventory(db: AsyncSession, inventory_id: int) -> Inventory:
    inv = (await db.execute(select(Inventory).where(Inventory.id == inventory_id))).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail={"code": "inventory_not_found", "message": "Inventory row not found"})
    return inv

def _inventory_response(inv: Inventory):
    return {"id": inv.id, "rel_path": inv.rel_path, "name": inv.name, "format": inv.format}

def _inventory_rel_path(filename: str) -> str:
    fn = filename.strip()
    if not fn or "/" in fn or "\\" in fn or fn.startswith(".") or fn in {".", ".."}:
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Filename must be a plain file name inside inventories/, with no path separators"})
    return f"{INVENTORY_DIR}/{fn}"


@router.get("")
async def list_inventories(
    request: Request,
    user: User = Depends(require("read")),
    db: AsyncSession = Depends(get_db)
):
    if "project_id" in request.query_params:
        raise HTTPException(status_code=422, detail={"code": "bad_query", "message": "project_id is not supported"})
    invs = (await db.execute(select(Inventory))).scalars().all()
    return [{"id": inv.id, "rel_path": inv.rel_path, "name": inv.name, "format": inv.format} for inv in invs]

@router.post("")
async def register_inventory(
    req: InventoryRegister,
    user: User = Depends(require("content.write")),
    db: AsyncSession = Depends(get_db)
):

    rel_path = _inventory_rel_path(req.filename)
    if rel_path.endswith((".py", ".sh")):
        raise HTTPException(status_code=400, detail={"code": "executable_inventory_forbidden", "message": "Executable inventories forbidden"})
    repo_path = get_inventory_repo_path()
    if not (repo_path / ".git").exists():
        raise HTTPException(status_code=404, detail={"code": "inventory_repo_missing", "message": "Shared inventory repo is not initialized. Restart the API."})
    try:
        file_path = validate_safe_path(repo_path, rel_path)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Invalid path"})

    duplicate = (await db.execute(select(Inventory).where(or_(Inventory.name == req.name, Inventory.rel_path == rel_path)))).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=400, detail={"code": "name_exists", "message": "Inventory name or path already registered"})

    if not file_path.is_file():
        if req.content is None:
            raise HTTPException(status_code=404, detail={"code": "file_not_found", "message": "Inventory file not found in git repo"})
        if req.format == InventoryFormat.yaml:
            try:
                yaml.safe_load(req.content)
            except yaml.YAMLError as exc:
                raise HTTPException(status_code=422, detail={"code": "invalid_yaml", "message": "Inventory YAML is invalid", "stderr": str(exc)})
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(req.content)
        repo = Repo(repo_path)
        repo.index.add([rel_path])
        actor = Actor(user.username, user.email)
        message = req.message or f"Create inventory {req.name}"
        commit = repo.index.commit(message, author=actor, committer=actor)
        db.add(Commit(project_id=(await ensure_inventory_repo(db)).id, sha=commit.hexsha, author_user_id=user.id, message=message, files_changed=[rel_path]))

    inv = Inventory(rel_path=rel_path, name=req.name, format=req.format)
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return _inventory_response(inv)

@router.get("/{inventory_id}/file")
async def get_inventory_file(
    inventory_id: int,
    user: User = Depends(require("read")),
    db: AsyncSession = Depends(get_db)
):
    inv = await _load_inventory(db, inventory_id)
    repo_path = get_inventory_repo_path()
    try:
        file_path = validate_safe_path(repo_path, inv.rel_path)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Invalid path"})
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail={"code": "file_not_found", "message": "Inventory file not found in git repo"})
    return {"id": inv.id, "rel_path": inv.rel_path, "format": inv.format, "content": file_path.read_text(), "sha": Repo(repo_path).head.commit.hexsha}

@router.post("/{inventory_id}/file")
async def save_inventory_file(
    inventory_id: int,
    req: InventoryFileSave,
    user: User = Depends(require("content.write")),
    db: AsyncSession = Depends(get_db)
):
    inv = await _load_inventory(db, inventory_id)
    repo_path = get_inventory_repo_path()
    try:
        file_path = validate_safe_path(repo_path, inv.rel_path)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Invalid path"})
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail={"code": "file_not_found", "message": "Inventory file not found in git repo"})
    repo = Repo(repo_path)
    if req.base_sha and repo.head.commit.hexsha != req.base_sha:
        raise HTTPException(status_code=409, detail={"code": "stale_write", "message": "File modified since last read", "current_content": file_path.read_text() if file_path.exists() else "", "current_sha": repo.head.commit.hexsha})
    if inv.format == InventoryFormat.yaml:
        try:
            yaml.safe_load(req.content)
        except yaml.YAMLError as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_yaml", "message": "Inventory YAML is invalid", "stderr": str(exc)})
    message = req.message or f"Update inventory {inv.name}"
    file_path.write_text(req.content)
    repo.index.add([inv.rel_path])
    actor = Actor(user.username, user.email)
    commit = repo.index.commit(message, author=actor, committer=actor)
    db.add(Commit(project_id=(await ensure_inventory_repo(db)).id, sha=commit.hexsha, author_user_id=user.id, message=message, files_changed=[inv.rel_path]))
    await db.commit()
    return {"status": "ok", "sha": commit.hexsha}

@router.patch("/{inventory_id}")
async def update_inventory(
    inventory_id: int,
    req: InventoryUpdate,
    user: User = Depends(require("content.write")),
    db: AsyncSession = Depends(get_db)
):
    inv = await _load_inventory(db, inventory_id)
    if req.name is not None and req.name != inv.name:
        duplicate = (await db.execute(select(Inventory).where(Inventory.name == req.name, Inventory.id != inventory_id))).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=400, detail={"code": "name_exists", "message": "Inventory name or path already registered"})
        inv.name = req.name
    if req.format is not None:
        inv.format = req.format
    await db.commit()
    await db.refresh(inv)
    return _inventory_response(inv)

@router.delete("/{inventory_id}")
async def delete_inventory_row(
    inventory_id: int,
    user: User = Depends(require("content.write")),
    db: AsyncSession = Depends(get_db)
):
    inv = await _load_inventory(db, inventory_id)
    refs = (await db.execute(select(func.count(JobTemplate.id)).where(JobTemplate.inventory_id == inventory_id))).scalar_one()
    if refs:
        raise HTTPException(status_code=409, detail={"code": "inventory_in_use", "message": "Inventory is used by job templates"})
    await db.delete(inv)
    await db.commit()
    return {"status": "ok"}
