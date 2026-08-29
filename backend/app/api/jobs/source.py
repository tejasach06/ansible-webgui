import pathlib

import anyio
from fastapi import APIRouter, Depends, HTTPException
from git import BadName, Repo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require
from app.db.models import Inventory, JobRun, Playbook, Project, User
from app.db.session import get_db
from app.services.content import get_inventory_repo_path, get_project_repo_path

router = APIRouter()

MAX_SOURCE_BYTES = 512 * 1024


def _read_blob(repo_path: pathlib.Path, rel_path: str, sha: str | None) -> dict:
    if not (repo_path / ".git").exists():
        return {"rel_path": rel_path, "content": None, "sha": sha, "is_vault": False, "error": "repo_not_found"}

    try:
        repo = Repo(repo_path)
        commit = repo.commit(sha) if sha else repo.head.commit
    except (BadName, ValueError, KeyError):
        return {"rel_path": rel_path, "content": None, "sha": sha, "is_vault": False, "error": "revision_not_found"}

    try:
        blob = commit.tree / rel_path
    except KeyError:
        return {"rel_path": rel_path, "content": None, "sha": commit.hexsha, "is_vault": False, "error": "file_not_found_at_revision"}

    if blob.size > MAX_SOURCE_BYTES:
        return {"rel_path": rel_path, "content": None, "sha": commit.hexsha, "is_vault": False, "error": "file_too_large"}

    content = blob.data_stream.read().decode("utf-8", "replace")
    is_vault = content.startswith("$ANSIBLE_VAULT;")
    return {
        "rel_path": rel_path,
        "content": content,
        "sha": commit.hexsha,
        "is_vault": is_vault,
        "error": None,
    }


@router.get("/{job_id}/source")
async def get_job_source(
    job_id: int,
    _user: User = Depends(require("read")),
    db: AsyncSession = Depends(get_db),
):
    job = (await db.execute(select(JobRun).where(JobRun.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Job run not found"})

    playbook = (await db.execute(select(Playbook).where(Playbook.id == job.playbook_id))).scalar_one_or_none() if job.playbook_id else None
    inventory = (await db.execute(select(Inventory).where(Inventory.id == job.inventory_id))).scalar_one_or_none() if job.inventory_id else None

    snap = job.params_snapshot or {}

    playbook_res = None
    if playbook:
        project = (await db.execute(select(Project).where(Project.id == playbook.project_id))).scalar_one_or_none()
        if project:
            playbook_res = await anyio.to_thread.run_sync(
                _read_blob, get_project_repo_path(project.name), playbook.rel_path, snap.get("git_sha")
            )
        else:
            playbook_res = {
                "rel_path": playbook.rel_path,
                "content": None,
                "sha": snap.get("git_sha"),
                "is_vault": False,
                "error": "repo_not_found",
            }

    inventory_res = None
    if inventory:
        inventory_res = await anyio.to_thread.run_sync(
            _read_blob, get_inventory_repo_path(), inventory.rel_path, snap.get("inventory_git_sha")
        )

    return {"playbook": playbook_res, "inventory": inventory_res}
