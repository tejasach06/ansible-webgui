import os

from fastapi import APIRouter, Depends, HTTPException
from git import Repo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require, require_project
from app.api.content.schemas import SaveFileRequest
from app.db.models import Project, User
from app.db.session import get_db
from app.services.content import commit_file, get_project_repo_path, validate_safe_path
from app.services.audit import audit


router = APIRouter()


@router.get("/{project_id}/file")
async def get_file(
    project_id: int,
    path: str,
    user: User = Depends(require_project("read")),
    db: AsyncSession = Depends(get_db)
):
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Project not found"})

    repo_path = get_project_repo_path(project.name)
    try:
        file_path = validate_safe_path(repo_path, path)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Invalid path"})

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail={"code": "file_not_found", "message": "File not found"})

    content = file_path.read_text()
    is_vault = content.startswith("$ANSIBLE_VAULT;")
    
    repo = Repo(repo_path)
    current_sha = repo.head.commit.hexsha

    return {
        "rel_path": path,
        "content": content,
        "is_vault": is_vault,
        "sha": current_sha
    }


@router.get("/{project_id}/tree")
async def get_tree(
    project_id: int,
    user: User = Depends(require_project("read")),
    db: AsyncSession = Depends(get_db)
):
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Project not found"})

    repo_path = get_project_repo_path(project.name)
    if not repo_path.is_dir():
        return {"entries": [], "truncated": False}
    entries = []
    truncated = False
    pruned = {".git", "galaxy_roles", "collections", "__pycache__"}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in pruned and not os.path.islink(os.path.join(root, d))]
        for name in sorted(dirs):
            path = os.path.join(root, name)
            rel_path = os.path.relpath(path, repo_path).replace(os.sep, "/")
            entries.append({"rel_path": rel_path, "name": name, "type": "dir", "size": 0})
            if len(entries) >= 5000:
                truncated = True
                break
        if truncated:
            break
        for name in sorted(files):
            if name.startswith(".git"):
                continue
            path = os.path.join(root, name)
            if os.path.islink(path):
                continue
            rel_path = os.path.relpath(path, repo_path).replace(os.sep, "/")
            entries.append({"rel_path": rel_path, "name": name, "type": "file", "size": os.path.getsize(path)})
            if len(entries) >= 5000:
                truncated = True
                break
        if truncated:
            break

    return {"entries": sorted(entries, key=lambda item: item["rel_path"]), "truncated": truncated}


@router.post("/{project_id}/save")
async def save_file(
    project_id: int,
    req: SaveFileRequest,
    user: User = Depends(require_project("content.write")),
    db: AsyncSession = Depends(get_db)
):
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Project not found"})

    sha = await commit_file(db, project, req.rel_path, req.content, req.message, req.base_sha, user, lint=True)
    await audit(db, "content_saved", actor_user_id=user.id, object_type="project", object_id=project_id, detail={"path": req.rel_path, "sha": sha})
    return {"status": "ok", "sha": sha}
