
import anyio
from fastapi import APIRouter, Depends, HTTPException
from git import Actor, Repo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require, require_project
from app.api.content.schemas import RevertRequest
from app.db.models import Commit, Project, User
from app.db.session import get_db
from app.services.content import get_project_repo_path, validate_safe_path

router = APIRouter()


@router.get("/{project_id}/history")
async def get_history(
    project_id: int,
    path: str | None = None,
    _user: User = Depends(require("read")),
    db: AsyncSession = Depends(get_db)
):
    query = select(Commit).where(Commit.project_id == project_id)
    if path:
        query = query.where(Commit.files_changed.any(path))
    query = query.order_by(Commit.created_at.desc()).limit(200)
    commits = (await db.execute(query)).scalars().all()

    return [
        {
            "sha": c.sha,
            "message": c.message,
            "author_user_id": c.author_user_id,
            "files_changed": c.files_changed,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in commits
    ]


@router.get("/{project_id}/diff")
async def get_diff(
    project_id: int,
    sha: str,
    path: str | None = None,
    _user: User = Depends(require("read")),
    db: AsyncSession = Depends(get_db)
):
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Project not found"})
    repo_path = get_project_repo_path(project.name)
    repo = Repo(repo_path)
    
    cmd = ["--", path] if path else []
    diff_text = await anyio.to_thread.run_sync(repo.git.show, sha, *cmd)
    return {"diff": diff_text}


@router.post("/{project_id}/revert")
async def revert_commit(
    project_id: int,
    req: RevertRequest,
    user: User = Depends(require_project("content.write")),
    db: AsyncSession = Depends(get_db)
):
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Project not found"})
    repo_path = get_project_repo_path(project.name)
    repo = Repo(repo_path)
    
    try:
        file_path = validate_safe_path(repo_path, req.rel_path)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Invalid path"}) from None
    try:
        old_content = await anyio.to_thread.run_sync(repo.git.show, f"{req.sha}:{req.rel_path}")
    except Exception:
        raise HTTPException(status_code=404, detail={"code": "file_not_found", "message": "File or commit not found in git repo"}) from None
    file_path.write_text(old_content)

    msg = f"Revert {req.rel_path} to {req.sha[:7]}"
    await anyio.to_thread.run_sync(repo.index.add, [req.rel_path])
    actor = Actor(user.username, user.email)
    commit = await anyio.to_thread.run_sync(lambda: repo.index.commit(msg, author=actor, committer=actor))
    c = Commit(
        project_id=project.id,
        sha=commit.hexsha,
        author_user_id=user.id,
        message=msg,
        files_changed=[req.rel_path]
    )
    db.add(c)
    await db.commit()
    return {"status": "ok", "sha": commit.hexsha}
