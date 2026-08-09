from fastapi import APIRouter, Depends, HTTPException
from git import Actor, Repo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require
from app.api.content.schemas import CreateRoleRequest
from app.db.models import Commit, Project, User
from app.db.session import get_db
from app.services.content import get_project_repo_path


router = APIRouter()


async def create_role(
    project_id: int,
    req: CreateRoleRequest,
    user: User = Depends(require("content.write")),
    db: AsyncSession = Depends(get_db)
):
    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": "Project not found"})
    repo_path = get_project_repo_path(project.name)
    
    role_dir = repo_path / "roles" / req.role_name
    if role_dir.exists():
        raise HTTPException(status_code=400, detail={"code": "role_exists", "message": "Role directory exists"})

    subdirs = ["tasks", "handlers", "defaults", "vars", "templates", "files", "meta"]
    for d in subdirs:
        (role_dir / d).mkdir(parents=True, exist_ok=True)

    (role_dir / "tasks" / "main.yml").write_text("---\n# tasks file for " + req.role_name + "\n")
    (role_dir / "handlers" / "main.yml").write_text("---\n# handlers file for " + req.role_name + "\n")
    (role_dir / "defaults" / "main.yml").write_text("---\n# defaults file for " + req.role_name + "\n")
    (role_dir / "vars" / "main.yml").write_text("---\n# vars file for " + req.role_name + "\n")
    (role_dir / "meta" / "main.yml").write_text("galaxy_info:\n  author: ansible-webgui\n  description: Role " + req.role_name + "\n")

    repo = Repo(repo_path)
    rel_paths = [str(p.relative_to(repo_path)) for p in role_dir.rglob("*") if p.is_file()]
    repo.index.add(rel_paths)
    
    actor = Actor(user.username, user.email)
    msg = f"Scaffold role {req.role_name}"
    commit = repo.index.commit(msg, author=actor, committer=actor)

    c = Commit(
        project_id=project.id,
        sha=commit.hexsha,
        author_user_id=user.id,
        message=msg,
        files_changed=rel_paths
    )
    db.add(c)
    await db.commit()
    return {"status": "ok", "sha": commit.hexsha}
