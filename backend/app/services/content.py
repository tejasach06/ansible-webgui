import json
import os
import pathlib
import subprocess

import anyio
from fastapi import HTTPException
from git import Actor, Repo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Commit, Project


def get_project_repo_path(project_name: str) -> pathlib.Path:
    path = pathlib.Path(settings.CONTENT_ROOT) / project_name
    return path.resolve()

def get_inventory_repo_path() -> pathlib.Path:
    return get_project_repo_path(settings.INVENTORY_REPO_NAME)

def validate_safe_path(base_dir: pathlib.Path, rel_path: str) -> pathlib.Path:
    target = (base_dir / rel_path).resolve()
    if not target.is_relative_to(base_dir):
        raise ValueError("bad_path")
    if target.is_symlink():
        raise ValueError("bad_path")
    return target

async def init_project_repo(db: AsyncSession, project: Project, author_username: str, author_email: str):
    repo_path = get_project_repo_path(project.name)
    repo_path.mkdir(parents=True, exist_ok=True)
    repo = Repo.init(repo_path)
    
    gitignore = repo_path / ".gitignore"
    gitignore.write_text("*.retry\ngalaxy_roles/\ncollections/\n")
    
    cfg = repo_path / "ansible.cfg"
    cfg.write_text(
        "[defaults]\n"
        "host_key_checking = True\n"
        "inventory = inventories/\n"
        "roles_path = roles:galaxy_roles\n"
        "collections_path = collections:/usr/share/ansible/collections\n"
        "retry_files_enabled = False\n"
        "callbacks_enabled = profile_tasks\n"
        "[ssh_connection]\n"
        "pipelining = True\n"
    )
    
    (repo_path / "inventories").mkdir(exist_ok=True)
    (repo_path / "roles").mkdir(exist_ok=True)
    (repo_path / "playbooks").mkdir(exist_ok=True)
    
    repo.index.add([".gitignore", "ansible.cfg"])
    actor = Actor(author_username, author_email)
    commit = repo.index.commit("Initial project structure", author=actor, committer=actor)
    existing = (await db.execute(select(Commit).where(Commit.sha == commit.hexsha))).scalar_one_or_none()
    if existing is None:
        c = Commit(
            project_id=project.id,
            sha=commit.hexsha,
            author_user_id=None,
            message="Initial project structure",
            files_changed=[".gitignore", "ansible.cfg"]
        )
        db.add(c)
    await db.commit()
    return repo

async def commit_file(
    db: AsyncSession,
    project: Project,
    rel_path: str,
    content: str,
    message: str,
    base_sha: str | None,
    user,
    lint: bool = True,
    verify_inventory: bool = False,
) -> str:
    """Write, lint-gate, commit and record rel_path in project's repo. Returns commit sha."""
    repo_path = get_project_repo_path(project.name)
    try:
        file_path = validate_safe_path(repo_path, rel_path)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "bad_path", "message": "Invalid path"}) from None

    repo = Repo(repo_path)
    head_sha = await anyio.to_thread.run_sync(lambda: repo.head.commit.hexsha)
    if base_sha and head_sha != base_sha:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stale_write",
                "message": "File modified since last read",
                "current_content": file_path.read_text() if file_path.exists() else "",
                "current_sha": head_sha,
            },
        )

    file_path.parent.mkdir(parents=True, exist_ok=True)
    orig_content = file_path.read_text() if file_path.exists() else None
    file_path.write_text(content)

    if lint:
        res = await anyio.to_thread.run_sync(lambda: subprocess.run(["ansible-lint", str(file_path)], capture_output=True, text=True, cwd=repo_path))
        if res.returncode != 0 and "syntax-check" in res.stderr:
            if orig_content is not None:
                file_path.write_text(orig_content)
            else:
                file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail={"code": "lint_error", "message": "Ansible lint failed", "stderr": res.stderr})
    if verify_inventory:
        try:
            verify_inventory_file(file_path)
        except HTTPException:
            if orig_content is not None:
                file_path.write_text(orig_content)
            else:
                file_path.unlink(missing_ok=True)
            raise
    await anyio.to_thread.run_sync(repo.index.add, [rel_path])
    actor = Actor(user.username, user.email)
    commit = await anyio.to_thread.run_sync(lambda: repo.index.commit(message, author=actor, committer=actor))
    db.add(Commit(project_id=project.id, sha=commit.hexsha, author_user_id=user.id, message=message, files_changed=[rel_path]))
    await db.commit()
    return commit.hexsha

async def ensure_inventory_repo(db: AsyncSession) -> Project:
    name = settings.INVENTORY_REPO_NAME
    project = (await db.execute(select(Project).where(Project.name == name))).scalar_one_or_none()
    if project is None:
        project = Project(name=name, git_path=str(get_inventory_repo_path()), default_branch="main")
        db.add(project)
        await db.commit()
        await db.refresh(project)

    if not (get_inventory_repo_path() / ".git").exists():
        await init_project_repo(db, project, "system", "system@local")

    return project

INVENTORY_PLUGIN_ALLOWLIST = "yaml,ini,host_list"

def verify_inventory_file(file_path: pathlib.Path) -> dict:
    """Run ansible-inventory --list against file_path. Returns parsed JSON, or raises 422 inventory_invalid."""
    try:
        res = subprocess.run(
            ["ansible-inventory", "-i", str(file_path), "--list"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=file_path.parent,
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "ANSIBLE_INVENTORY_ENABLED": INVENTORY_PLUGIN_ALLOWLIST,
                "ANSIBLE_INVENTORY_ANY_UNPARSED_IS_FAILED": "True",
            },
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=422,
            detail={"code": "inventory_invalid", "message": "Inventory could not be parsed", "stderr": "ansible-inventory timed out after 15s"},
        ) from None

    if res.returncode != 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "inventory_invalid", "message": "Inventory could not be parsed", "stderr": res.stderr[:4000]},
        )

    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=422,
            detail={"code": "inventory_invalid", "message": "Inventory could not be parsed", "stderr": res.stderr[:4000] or "Failed to decode ansible-inventory output as JSON"},
        ) from None
