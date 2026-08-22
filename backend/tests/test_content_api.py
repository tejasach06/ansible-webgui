import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import AuditLog, Project, Role, User
from app.services.content import get_project_repo_path, init_project_repo


async def login(client, username="admin", password=None):
    return await client.post(
        "/api/auth/login",
        json={"username": username, "password": password or settings.BOOTSTRAP_ADMIN_PASSWORD},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_tree_lists_repo_files(client, db):
    project = Project(name="tree-test", git_path="/data/content/tree-test")
    db.add(project)
    await db.commit()
    await db.refresh(project)
    await init_project_repo(db, project, "admin", "admin@example.com")
    playbook = get_project_repo_path(project.name) / "playbooks" / "site.yml"
    playbook.write_text("- hosts: localhost\n  tasks: []\n")

    await login(client)
    res = await client.get(f"/api/content/{project.id}/tree")

    assert res.status_code == 200
    body = res.json()
    assert {"rel_path": "playbooks/site.yml", "name": "site.yml", "type": "file", "size": playbook.stat().st_size} in body["entries"]
    assert body["truncated"] is False
    assert not any(entry["rel_path"].startswith(".git") for entry in body["entries"])


@pytest.mark.asyncio(loop_scope="session")
async def test_tree_unknown_project_404(client):
    await login(client)
    res = await client.get("/api/content/999999/tree")

    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "project_not_found"


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_requires_audit_read(client, db):
    user_role = (await db.execute(select(Role).where(Role.name == "user"))).scalar_one()
    user = User(username="user-audit", email="user-audit@example.com", password_hash=hash_password("changeme"), roles=[user_role])
    auditor_role = (await db.execute(select(Role).where(Role.name == "auditor"))).scalar_one()
    auditor = User(username="auditor-audit", email="auditor-audit@example.com", password_hash=hash_password("changeme"), roles=[auditor_role])
    db.add_all([user, auditor])
    await db.commit()

    await login(client, "user-audit", "changeme")
    res = await client.get("/api/audit")
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "forbidden"

    await login(client, "auditor-audit", "changeme")
    res_auditor = await client.get("/api/audit")
    assert res_auditor.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_filters_by_action(client, db):
    db.add_all([
        AuditLog(action="tree_a", object_type="project", object_id="1"),
        AuditLog(action="tree_b", object_type="project", object_id="2"),
    ])
    await db.commit()

    await login(client)
    res = await client.get("/api/audit?action=tree_a")

    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "tree_a"
