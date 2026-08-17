from uuid import uuid4
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import (
    Credential,
    CredentialKind,
    Inventory,
    InventoryFormat,
    JobMode,
    JobRun,
    JobStatus,
    JobTemplate,
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


@pytest.mark.asyncio(loop_scope="session")
async def test_get_job_detail_context_resolution(client, db):
    suffix = uuid4().hex
    requester = await _user(db, f"req-{suffix}")
    approver = await _user(db, f"app-{suffix}")
    project = Project(name=f"proj-{suffix}", git_path=f"/tmp/proj-{suffix}")
    db.add(project)
    await db.flush()

    playbook = Playbook(project_id=project.id, rel_path="playbooks/deploy.yml", name="Deploy Playbook")
    inventory = Inventory(project_id=project.id, name=f"inv-{suffix}", rel_path=f"inventories/{suffix}.yml", format=InventoryFormat.yaml)
    cred = Credential(project_id=project.id, name=f"cred-{suffix}", kind=CredentialKind.ssh_password, username="ansible_user", payload_enc=b"encrypted", created_by=requester.id)
    db.add_all([playbook, inventory, cred])
    await db.flush()

    template = JobTemplate(project_id=project.id, name=f"tmpl-{suffix}", playbook_id=playbook.id, inventory_id=inventory.id)
    db.add(template)
    await db.flush()

    job = JobRun(
        template_id=template.id,
        playbook_id=playbook.id,
        inventory_id=inventory.id,
        mode=JobMode.live,
        status=JobStatus.pending_approval,
        requested_by=requester.id,
        approved_by=approver.id,
        params_snapshot={"credential_ids": [cred.id], "extra_vars": {"env": "prod"}},
    )
    db.add(job)
    await db.commit()

    await _login(client)
    res = await client.get(f"/api/jobs/{job.id}")
    assert res.status_code == 200
    data = res.json()
    assert "context" in data
    ctx = data["context"]
    assert ctx["project_name"] == project.name
    assert ctx["playbook_name"] == "Deploy Playbook"
    assert ctx["playbook_rel_path"] == "playbooks/deploy.yml"
    assert ctx["inventory_name"] == inventory.name
    assert ctx["inventory_rel_path"] == inventory.rel_path
    assert ctx["template_name"] == template.name
    assert ctx["requested_by_username"] == requester.username
    assert ctx["approved_by_username"] == approver.username
    assert len(ctx["credentials"]) == 1
    assert ctx["credentials"][0]["id"] == cred.id
    assert ctx["credentials"][0]["name"] == cred.name
    assert ctx["credentials"][0]["kind"] == "ssh_password"
    assert ctx["credentials"][0]["username"] == "ansible_user"


@pytest.mark.asyncio(loop_scope="session")
async def test_approve_note_required(client, db):
    suffix = uuid4().hex
    requester = await _user(db, f"req-{suffix}")
    project = Project(name=f"proj-{suffix}", git_path=f"/tmp/proj-{suffix}")
    db.add(project)
    await db.flush()

    playbook = Playbook(project_id=project.id, rel_path="playbooks/deploy.yml", name="Deploy Playbook")
    db.add(playbook)
    await db.flush()

    job = JobRun(
        playbook_id=playbook.id,
        inventory_id=None,
        mode=JobMode.live,
        status=JobStatus.pending_approval,
        requested_by=requester.id,
        params_snapshot={},
    )
    db.add(job)
    await db.commit()

    await _login(client)
    # Empty body
    res1 = await client.post(f"/api/jobs/{job.id}/approve", json={}, headers=MUTATE)
    assert res1.status_code == 422
    assert res1.json()["detail"]["code"] == "approval_note_required"

    await db.refresh(job)
    assert job.status == JobStatus.pending_approval

    # Whitespace only
    res2 = await client.post(f"/api/jobs/{job.id}/approve", json={"approval_note": "   "}, headers=MUTATE)
    assert res2.status_code == 422
    assert res2.json()["detail"]["code"] == "approval_note_required"

    await db.refresh(job)
    assert job.status == JobStatus.pending_approval


@pytest.mark.asyncio(loop_scope="session")
async def test_approve_with_note_success(client, db, monkeypatch):
    suffix = uuid4().hex
    requester = await _user(db, f"req-{suffix}")
    project = Project(name=f"proj-{suffix}", git_path=f"/tmp/proj-{suffix}")
    db.add(project)
    await db.flush()

    playbook = Playbook(project_id=project.id, rel_path="playbooks/deploy.yml", name="Deploy Playbook")
    db.add(playbook)
    await db.flush()

    job = JobRun(
        playbook_id=playbook.id,
        inventory_id=None,
        mode=JobMode.live,
        status=JobStatus.pending_approval,
        requested_by=requester.id,
        params_snapshot={},
    )
    db.add(job)
    await db.commit()

    class Task:
        id = "test-task-123"

    monkeypatch.setattr("app.api.jobs.lifecycle.run_job.delay", lambda _job_id: Task())

    await _login(client)  # logs in as admin (different from requester)
    res = await client.post(f"/api/jobs/{job.id}/approve", json={"approval_note": "reviewed and approved"}, headers=MUTATE)
    assert res.status_code == 200
    await db.refresh(job)
    assert job.status == JobStatus.queued
    assert job.approval_note == "reviewed and approved"
