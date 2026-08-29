from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models import Inventory, InventoryFormat, JobMode, JobRun, JobStatus, Playbook, Project, User
from app.services.content import commit_file, ensure_inventory_repo, init_project_repo

MUTATE = {"X-Requested-With": "XMLHttpRequest"}


async def _login(client, username=settings.BOOTSTRAP_ADMIN_USER, password=None):
    return await client.post(
        "/api/auth/login",
        json={"username": username, "password": password or settings.BOOTSTRAP_ADMIN_PASSWORD},
        headers=MUTATE,
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_get_job_source_pinned_revisions(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))

    suffix = uuid4().hex
    admin = (await db.execute(select(User).where(User.username == settings.BOOTSTRAP_ADMIN_USER))).unique().scalar_one()

    project = Project(name=f"proj-{suffix}", git_path=f"{tmp_path}/proj-{suffix}")
    db.add(project)
    await db.commit()
    await db.refresh(project)

    await init_project_repo(db, project, admin.username, admin.email)

    pb_rel = "playbooks/deploy.yml"
    sha_v1 = await commit_file(
        db, project, pb_rel, "- hosts: all\n  tasks: [v1]\n", "add v1", None, admin, lint=False
    )
    sha_v2 = await commit_file(
        db, project, pb_rel, "- hosts: all\n  tasks: [v2]\n", "add v2", sha_v1, admin, lint=False
    )
    assert sha_v1 != sha_v2

    inv_project = await ensure_inventory_repo(db)
    inv_rel = f"inventories/{suffix}.yml"
    inv_sha = await commit_file(
        db, inv_project, inv_rel, "all:\n  hosts:\n    web1:\n", "add inv", None, admin, lint=False
    )

    playbook = Playbook(project_id=project.id, rel_path=pb_rel, name="Deploy Playbook")
    inventory = Inventory(project_id=project.id, name=f"inv-{suffix}", rel_path=inv_rel, format=InventoryFormat.yaml)
    db.add_all([playbook, inventory])
    await db.commit()

    job = JobRun(
        playbook_id=playbook.id,
        inventory_id=inventory.id,
        mode=JobMode.live,
        status=JobStatus.pending_approval,
        requested_by=admin.id,
        params_snapshot={"git_sha": sha_v1, "inventory_git_sha": inv_sha},
    )
    db.add(job)
    await db.commit()

    await _login(client)
    res = await client.get(f"/api/jobs/{job.id}/source")
    assert res.status_code == 200
    data = res.json()

    assert data["playbook"]["rel_path"] == pb_rel
    assert data["playbook"]["sha"] == sha_v1
    assert "tasks: [v1]" in data["playbook"]["content"]
    assert data["playbook"]["error"] is None

    assert data["inventory"]["rel_path"] == inv_rel
    assert data["inventory"]["sha"] == inv_sha
    assert "web1:" in data["inventory"]["content"]
    assert data["inventory"]["error"] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_get_job_source_revision_not_found(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    suffix = uuid4().hex
    admin = (await db.execute(select(User).where(User.username == settings.BOOTSTRAP_ADMIN_USER))).unique().scalar_one()

    project = Project(name=f"proj-{suffix}", git_path=f"{tmp_path}/proj-{suffix}")
    db.add(project)
    await db.commit()
    await db.refresh(project)

    await init_project_repo(db, project, admin.username, admin.email)

    playbook = Playbook(project_id=project.id, rel_path="playbooks/deploy.yml", name="Deploy")
    db.add(playbook)
    await db.commit()

    bogus_sha = "a" * 40
    job = JobRun(
        playbook_id=playbook.id,
        inventory_id=None,
        mode=JobMode.live,
        status=JobStatus.pending_approval,
        requested_by=admin.id,
        params_snapshot={"git_sha": bogus_sha},
    )
    db.add(job)
    await db.commit()

    await _login(client)
    res = await client.get(f"/api/jobs/{job.id}/source")
    assert res.status_code == 200
    data = res.json()

    assert data["playbook"]["rel_path"] == "playbooks/deploy.yml"
    assert data["playbook"]["content"] is None
    assert data["playbook"]["error"] == "revision_not_found"
    assert data["inventory"] is None
