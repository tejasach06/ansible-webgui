from uuid import uuid4

import pytest
from git import Actor, Repo
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import (
    Inventory,
    InventoryFormat,
    JobTemplate,
    Playbook,
    Project,
    ProjectMembership,
    ProjectRole,
    Role,
    User,
)
from app.services.content import (
    ensure_inventory_repo,
    get_inventory_repo_path,
    get_project_repo_path,
    init_project_repo,
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


async def _stack(db, monkeypatch, tmp_path, name: str, ask_limit: bool = False, limit_pattern: str | None = None):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    project = Project(name=name, git_path=str(tmp_path / name))
    db.add(project)
    await db.flush()
    await init_project_repo(db, project, "admin", "admin@example.com")
    playbook_path = get_project_repo_path(project.name) / "playbooks" / "site.yml"
    playbook_path.write_text("- hosts: all\n  gather_facts: false\n  tasks: []\n")
    repo = Repo(get_project_repo_path(project.name))
    actor = Actor("admin", "admin@example.com")
    repo.index.add(["playbooks/site.yml"])
    repo.index.commit("Add playbook", author=actor, committer=actor)

    await ensure_inventory_repo(db)
    inventory_path = get_inventory_repo_path() / "inventories" / f"{name}.yml"
    inventory_path.write_text("all: {hosts: {web: {ansible_connection: local}}}\n")
    inventory_repo = Repo(get_inventory_repo_path())
    inventory_repo.index.add([f"inventories/{name}.yml"])
    inventory_repo.index.commit("Add inventory", author=actor, committer=actor)

    playbook = Playbook(project_id=project.id, rel_path="playbooks/site.yml", name=f"site-{name}")
    inventory = Inventory(name=f"inv-{name}", rel_path=f"inventories/{name}.yml", format=InventoryFormat.yaml)
    db.add_all([playbook, inventory])
    await db.flush()
    template = JobTemplate(
        project_id=project.id,
        name=f"tmpl-{name}",
        playbook_id=playbook.id,
        inventory_id=inventory.id,
        requires_approval=True,
        ask_limit=ask_limit,
        limit_pattern=limit_pattern,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return project, playbook, inventory, template


@pytest.mark.asyncio(loop_scope="session")
async def test_limit_override_rejected_when_template_does_not_ask(client, db, monkeypatch, tmp_path):
    _, _, _, template = await _stack(db, monkeypatch, tmp_path, f"launch-locked-{uuid4().hex}", ask_limit=False)
    await _login(client)

    res = await client.post("/api/jobs", json={"template_id": template.id, "limit": "web"}, headers=MUTATE)

    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "override_not_allowed"
    assert res.json()["detail"]["fields"] == ["limit"]


@pytest.mark.asyncio(loop_scope="session")
async def test_limit_override_allowed_records_override_diff(client, db, monkeypatch, tmp_path):
    _, _, _, template = await _stack(db, monkeypatch, tmp_path, f"launch-open-{uuid4().hex}", ask_limit=True)
    await _login(client)

    created = await client.post("/api/jobs", json={"template_id": template.id, "limit": "web"}, headers=MUTATE)
    assert created.status_code == 200

    detail = await client.get(f"/api/jobs/{created.json()['id']}")
    assert detail.status_code == 200
    assert detail.json()["overrides"] == {"limit": {"template": None, "request": "web"}}


@pytest.mark.asyncio(loop_scope="session")
async def test_adhoc_launch_forbidden_for_non_admin(client, db, monkeypatch, tmp_path):
    project, playbook, inventory, _ = await _stack(db, monkeypatch, tmp_path, f"launch-adhoc-{uuid4().hex}")
    user = await _user(db, f"adhoc-user-{uuid4().hex}")
    db.add(ProjectMembership(project_id=project.id, user_id=user.id, role=ProjectRole.developer))
    await db.commit()
    await _login(client, user.username, "changeme")

    res = await client.post(
        "/api/jobs",
        json={"template_id": None, "playbook_id": playbook.id, "inventory_id": inventory.id, "mode": "live"},
        headers=MUTATE,
    )

    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "adhoc_forbidden"


@pytest.mark.asyncio(loop_scope="session")
async def test_template_default_limit_pattern_applied(client, db, monkeypatch, tmp_path):
    _, _, _, template = await _stack(db, monkeypatch, tmp_path, f"launch-limit-{uuid4().hex}", ask_limit=False, limit_pattern="web")
    await _login(client)

    created = await client.post("/api/jobs", json={"template_id": template.id}, headers=MUTATE)
    assert created.status_code == 200
    job_id = created.json()["id"]

    detail = await client.get(f"/api/jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["params_snapshot"]["limit"] == "web"
