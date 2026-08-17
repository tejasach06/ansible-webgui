from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import (
    Inventory,
    InventoryFormat,
    JobMode,
    JobRun,
    JobStatus,
    Playbook,
    Project,
    ProjectMembership,
    ProjectRole,
    Role,
    User,
)

MUTATE = {"X-Requested-With": "XMLHttpRequest"}


async def _login(client, username=settings.BOOTSTRAP_ADMIN_USER, password=None):
    return await client.post(
        "/api/auth/login",
        json={"username": username, "password": password or settings.BOOTSTRAP_ADMIN_PASSWORD},
        headers=MUTATE,
    )


async def _role(db, name: str):
    role = (await db.execute(select(Role).where(Role.name == name))).scalar_one_or_none()
    if role is None:
        role = Role(name=name)
        db.add(role)
        await db.flush()
    return role


async def _user(db, username: str, role_name: str = "user"):
    role = await _role(db, role_name)
    user = User(username=username, email=f"{username}@example.com", password_hash=hash_password("changeme"), roles=[role])
    db.add(user)
    await db.flush()
    return user


async def _pending_job(db, project: Project, requested_by: int = 1):
    playbook = Playbook(project_id=project.id, rel_path=f"playbooks/{uuid4().hex}.yml", name=f"pb-{uuid4().hex}")
    inventory = Inventory(name=f"inv-{uuid4().hex}", rel_path=f"inventories/{uuid4().hex}.yml", format=InventoryFormat.yaml)
    db.add_all([playbook, inventory])
    await db.flush()
    job = JobRun(
        playbook_id=playbook.id,
        inventory_id=inventory.id,
        mode=JobMode.live,
        status=JobStatus.pending_approval,
        requested_by=requested_by,
        params_snapshot={},
    )
    db.add(job)
    await db.flush()
    return job


@pytest.mark.asyncio(loop_scope="session")
async def test_developer_member_cannot_approve(client, db):
    suffix = uuid4().hex
    requester = await _user(db, f"requester-{suffix}")
    developer = await _user(db, f"developer-{suffix}")
    project = Project(name=f"rbac-dev-{suffix}", git_path=f"/tmp/rbac-dev-{suffix}")
    db.add(project)
    await db.flush()
    db.add(ProjectMembership(project_id=project.id, user_id=developer.id, role=ProjectRole.developer))
    job = await _pending_job(db, project, requester.id)
    await db.commit()

    await _login(client, developer.username, "changeme")
    res = await client.post(f"/api/jobs/{job.id}/approve", json={}, headers=MUTATE)

    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "forbidden"


@pytest.mark.asyncio(loop_scope="session")
async def test_non_member_cannot_approve(client, db):
    suffix = uuid4().hex
    requester = await _user(db, f"requester-{suffix}")
    outsider = await _user(db, f"outsider-{suffix}")
    project = Project(name=f"rbac-outsider-{suffix}", git_path=f"/tmp/rbac-outsider-{suffix}")
    db.add(project)
    await db.flush()
    job = await _pending_job(db, project, requester.id)
    await db.commit()

    await _login(client, outsider.username, "changeme")
    res = await client.post(f"/api/jobs/{job.id}/approve", json={}, headers=MUTATE)

    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "forbidden"


@pytest.mark.asyncio(loop_scope="session")
async def test_system_admin_bypasses_project_membership(client, db, monkeypatch):
    suffix = uuid4().hex
    requester = await _user(db, f"requester-{suffix}")
    project = Project(name=f"rbac-admin-{suffix}", git_path=f"/tmp/rbac-admin-{suffix}")
    db.add(project)
    await db.flush()
    job = await _pending_job(db, project, requester.id)
    await db.commit()

    class Task:
        id = "test-task"

    monkeypatch.setattr("app.api.jobs.lifecycle.run_job.delay", lambda _job_id: Task())
    await _login(client)
    res = await client.post(f"/api/jobs/{job.id}/approve", json={}, headers=MUTATE)

    assert res.status_code == 200
    await db.refresh(job)
    assert job.status == JobStatus.queued


@pytest.mark.asyncio(loop_scope="session")
async def test_deleting_last_owner_returns_last_owner(client, db):
    suffix = uuid4().hex
    owner = await _user(db, f"owner-{suffix}")
    project = Project(name=f"rbac-owner-{suffix}", git_path=f"/tmp/rbac-owner-{suffix}")
    db.add(project)
    await db.flush()
    db.add(ProjectMembership(project_id=project.id, user_id=owner.id, role=ProjectRole.owner))
    await db.commit()

    await _login(client, owner.username, "changeme")
    res = await client.delete(f"/api/projects/{project.id}/members/{owner.id}", headers=MUTATE)

    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "last_owner"
