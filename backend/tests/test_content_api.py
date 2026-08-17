import pytest
from sqlalchemy import select

from app.db.models import Project, User, Role, ProjectMembership, ProjectRole, AuditLog
from app.core.security import hash_password
from app.core.config import settings
from app.services.content import init_project_repo, get_project_repo_path


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
    db.add(ProjectMembership(project_id=project.id, user_id=1, role=ProjectRole.owner))
    await db.commit()
    await init_project_repo(db, project, "admin", "admin@example.com")
    playbook = get_project_repo_path(project.name) / "playbooks" / "site.yml"
    playbook.write_text("- hosts: localhost\n  tasks: []\n")

    await login(client)
    res = await client.get(f"/api/content/{project.id}/tree")

    assert res.status_code == 200, f"Expected 200 got {res.status_code}: {res.json()}"
    body = res.json()
    assert {"rel_path": "playbooks/site.yml", "name": "site.yml", "type": "file", "size": playbook.stat().st_size} in body["entries"]
    assert body["truncated"] is False
    assert not any(entry["rel_path"].startswith(".git") for entry in body["entries"])


@pytest.mark.asyncio(loop_scope="session")
async def test_tree_unknown_project_404(client):
    await login(client)
    res = await client.get("/api/content/999999/tree")

    assert res.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_requires_user_manage(client, db):
    user_role = (await db.execute(select(Role).where(Role.name == "user"))).scalar_one()
    non_admin = User(username="user-audit", email="user-audit@example.com", password_hash=hash_password("changeme"), roles=[user_role])
    db.add(non_admin)
    await db.commit()

    await login(client, "user-audit", "changeme")
    res = await client.get("/api/audit")

    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "forbidden"


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
