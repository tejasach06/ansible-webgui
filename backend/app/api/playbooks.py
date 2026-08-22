import anyio
from fastapi import APIRouter, Depends, HTTPException, Request
from git import Repo
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_csrf
from app.db.models import Playbook, Project, User
from app.db.session import get_db
from app.services.audit import audit
from app.services.content import commit_file, get_project_repo_path, validate_safe_path
from app.services.rbac_scope import assert_project_perm, visible_project_ids

router = APIRouter(prefix="/api/playbooks", tags=["playbooks"])

class PlaybookRegister(BaseModel):
    project_id: int
    rel_path: str
    name: str
    content: str | None = None
    message: str | None = None

class PlaybookUpdate(BaseModel):
    name: str | None = None
    rel_path: str | None = None

class PlaybookFileSave(BaseModel):
    content: str
    message: str
    base_sha: str | None = None

async def _load_playbook(db: AsyncSession, playbook_id: int) -> Playbook:
    pb = (await db.execute(select(Playbook).where(Playbook.id == playbook_id))).scalar_one_or_none()
    if not pb:
        raise HTTPException(status_code=404, detail={"code": "playbook_not_found", "message": "Playbook row not found"})
    return pb

def _playbook_response(pb: Playbook):
    return {"id": pb.id, "project_id": pb.project_id, "rel_path": pb.rel_path, "name": pb.name}

@router.get("")
async def list_playbooks(
    project_id: int | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Playbook)
    if project_id:
        await assert_project_perm(db, user, project_id, "read")
        query = query.where(Playbook.project_id == project_id)
    else:
        vids = await visible_project_ids(db, user)
        if vids is not None:
            query = query.where(Playbook.project_id.in_(vids))
    playbooks = (await db.execute(query)).scalars().all()
    return [_playbook_response(pb) for pb in playbooks]

@router.post("")
async def register_playbook(
    req: PlaybookRegister,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    require_csrf(request)
    project = (await db.execute(select(Project).where(Project.id == req.project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Project not found"})
    await assert_project_perm(db, user, req.project_id, "content.write")

    repo_path = get_project_repo_path(project.name)
    try:
        file_path = validate_safe_path(repo_path, req.rel_path)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Invalid path"}) from None

    if req.content is not None and not req.rel_path.endswith((".yml", ".yaml")):
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Playbook file must end in .yml or .yaml"})

    duplicate = (await db.execute(select(Playbook).where(Playbook.project_id == req.project_id, or_(Playbook.name == req.name, Playbook.rel_path == req.rel_path)))).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=400, detail={"code": "name_exists", "message": "Playbook name or path already registered"})

    created_file = False
    if not file_path.is_file():
        if req.content is None:
            raise HTTPException(status_code=404, detail={"code": "file_not_found", "message": "Playbook file not found in git repo"})
        await commit_file(db, project, req.rel_path, req.content, req.message or f"Create playbook {req.name}", None, user, lint=True)
        created_file = True
    pb = Playbook(project_id=req.project_id, rel_path=req.rel_path, name=req.name)
    db.add(pb)
    await db.commit()
    await db.refresh(pb)
    await audit(db, "playbook_registered", actor_user_id=user.id, object_type="playbook", object_id=pb.id, detail={"created": created_file})
    return _playbook_response(pb)

@router.get("/{playbook_id}/file")
async def get_playbook_file(
    playbook_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    pb = await _load_playbook(db, playbook_id)
    await assert_project_perm(db, user, pb.project_id, "read")
    project = (await db.execute(select(Project).where(Project.id == pb.project_id))).scalar_one()
    repo_path = get_project_repo_path(project.name)
    try:
        file_path = validate_safe_path(repo_path, pb.rel_path)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Invalid path"}) from None
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail={"code": "file_not_found", "message": "Playbook file not found in git repo"})
    sha = await anyio.to_thread.run_sync(lambda: Repo(repo_path).head.commit.hexsha)
    return {"id": pb.id, "rel_path": pb.rel_path, "content": file_path.read_text(), "sha": sha}

@router.post("/{playbook_id}/file")
async def save_playbook_file(
    playbook_id: int,
    req: PlaybookFileSave,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    require_csrf(request)
    pb = await _load_playbook(db, playbook_id)
    await assert_project_perm(db, user, pb.project_id, "content.write")
    project = (await db.execute(select(Project).where(Project.id == pb.project_id))).scalar_one()
    repo_path = get_project_repo_path(project.name)
    try:
        file_path = validate_safe_path(repo_path, pb.rel_path)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Invalid path"}) from None
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail={"code": "file_not_found", "message": "Playbook file not found in git repo"})
    sha = await commit_file(db, project, pb.rel_path, req.content, req.message or f"Update playbook {pb.name}", req.base_sha, user, lint=True)
    await audit(db, "playbook_file_saved", actor_user_id=user.id, object_type="playbook", object_id=pb.id, detail={"sha": sha})
    return {"status": "ok", "sha": sha}

@router.patch("/{playbook_id}")
async def update_playbook(
    playbook_id: int,
    req: PlaybookUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    require_csrf(request)
    pb = await _load_playbook(db, playbook_id)
    await assert_project_perm(db, user, pb.project_id, "content.write")
    if req.rel_path is not None and req.rel_path != pb.rel_path:
        project = (await db.execute(select(Project).where(Project.id == pb.project_id))).scalar_one()
        repo_path = get_project_repo_path(project.name)
        try:
            file_path = validate_safe_path(repo_path, req.rel_path)
        except ValueError:
            raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Invalid path"}) from None
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail={"code": "file_not_found", "message": "Playbook file not found in git repo"})
        duplicate = (await db.execute(select(Playbook).where(Playbook.project_id == pb.project_id, Playbook.rel_path == req.rel_path, Playbook.id != playbook_id))).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=400, detail={"code": "path_exists", "message": "Playbook path already registered in this project"})
        pb.rel_path = req.rel_path
    if req.name is not None:
        pb.name = req.name
    await db.commit()
    await db.refresh(pb)
    await audit(db, "playbook_updated", actor_user_id=user.id, object_type="playbook", object_id=pb.id)
    return _playbook_response(pb)

@router.delete("/{playbook_id}")
async def delete_playbook_row(
    playbook_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    require_csrf(request)
    pb = await _load_playbook(db, playbook_id)
    await assert_project_perm(db, user, pb.project_id, "content.write")
    await db.delete(pb)
    await db.commit()
    await audit(db, "playbook_deleted", actor_user_id=user.id, object_type="playbook", object_id=playbook_id)
    return {"status": "ok"}
