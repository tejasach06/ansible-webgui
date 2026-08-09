from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from git import Actor, Repo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require
from app.api.content.schemas import RevertRequest
from app.db.models import Commit, Project, User
from app.db.session import get_db
from app.services.content import get_project_repo_path, validate_safe_path


router = APIRouter()


async def get_history(
    project_id: int,
    path: Optional[str] = None,
    user: User = Depends(require("read")),
    db: AsyncSession = Depends(get_db)
):
    query = select(Commit).where(Commit.project_id == project_id).order_by(Commit.created_at.desc())
    commits = (await db.execute(query)).scalars().all()
    
    res = []
    for c in commits:
        if path and path not in c.files_changed:
            continue
        res.append({
            "sha": c.sha,
            "message": c.message,
            "author_user_id": c.author_user_id,
            "files_changed": c.files_changed,
            "created_at": c.created_at.isoformat()
        })
    return res


async def get_diff(
    project_id: int,
    sha: str,
    path: Optional[str] = None,
    user: User = Depends(require("read")),
    db: AsyncSession = Depends(get_db)
):
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Project not found"})
    repo_path = get_project_repo_path(project.name)
    repo = Repo(repo_path)
    
    cmd = ["--", path] if path else []
    diff_text = repo.git.show(sha, *cmd)
    return {"diff": diff_text}


async def revert_commit(
    project_id: int,
    req: RevertRequest,
    user: User = Depends(require("content.write")),
    db: AsyncSession = Depends(get_db)
):
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Project not found"})
    repo_path = get_project_repo_path(project.name)
    repo = Repo(repo_path)
    
    old_content = repo.git.show(f"{req.sha}:{req.rel_path}")
    file_path = validate_safe_path(repo_path, req.rel_path)
    file_path.write_text(old_content)

    msg = f"Revert {req.rel_path} to {req.sha[:7]}"
    repo.index.add([req.rel_path])
    actor = Actor(user.username, user.email)
    commit = repo.index.commit(msg, author=actor, committer=actor)

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
