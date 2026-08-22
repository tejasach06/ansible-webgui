import pytest
from git import Actor, Repo
from sqlalchemy import select
from test_content_api import login

from app.core.config import settings
from app.db.models import AuditLog, Commit
from app.services.content import ensure_inventory_repo, get_inventory_repo_path, get_project_repo_path

PLAYBOOK = """---
- name: Test play
  hosts: all
  gather_facts: false
  tasks:
    - name: Ping
      ansible.builtin.ping:
"""

INVENTORY_YAML = "all:\n  hosts:\n    web1:\n"


async def _inventory_repo(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    project = await ensure_inventory_repo(db)
    await login(client)
    return project, get_inventory_repo_path()


async def _project(client, monkeypatch, tmp_path, name):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await login(client)
    res = await client.post(
        "/api/projects",
        json={"name": name},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res.status_code == 200
    return res.json(), get_project_repo_path(name)


@pytest.mark.asyncio(loop_scope="session")
async def test_register_existing_playbook_without_content_still_works(client, db, monkeypatch, tmp_path):
    project, repo_path = await _project(client, monkeypatch, tmp_path, "existing-playbook")
    playbook = repo_path / "playbooks" / "existing.yml"
    playbook.write_text(PLAYBOOK)
    repo = Repo(repo_path)
    actor = Actor("admin", "admin@example.com")
    repo.index.add(["playbooks/existing.yml"])
    repo.index.commit("Add existing playbook", author=actor, committer=actor)

    res = await client.post(
        "/api/playbooks",
        json={"project_id": project["id"], "name": "existing", "rel_path": "playbooks/existing.yml"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["rel_path"] == "playbooks/existing.yml"
    audit = (
        await db.execute(
            select(AuditLog).where(AuditLog.action == "playbook_registered", AuditLog.object_id == str(body["id"]))
        )
    ).scalar_one()
    assert audit.detail == {"created": False}


@pytest.mark.asyncio(loop_scope="session")
async def test_create_playbook_with_content_and_reject_duplicate_path_and_name(client, db, monkeypatch, tmp_path):
    project, repo_path = await _project(client, monkeypatch, tmp_path, "create-playbook")

    res = await client.post(
        "/api/playbooks",
        json={
            "project_id": project["id"],
            "name": "fresh",
            "rel_path": "playbooks/fresh.yml",
            "content": PLAYBOOK,
            "message": "Create fresh",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "fresh"
    assert (repo_path / "playbooks" / "fresh.yml").read_text() == PLAYBOOK
    audit = (
        await db.execute(
            select(AuditLog).where(AuditLog.action == "playbook_registered", AuditLog.object_id == str(body["id"]))
        )
    ).scalar_one()
    assert audit.detail == {"created": True}

    same_path = await client.post(
        "/api/playbooks",
        json={"project_id": project["id"], "name": "fresh-copy", "rel_path": "playbooks/fresh.yml", "content": PLAYBOOK},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    same_name = await client.post(
        "/api/playbooks",
        json={"project_id": project["id"], "name": "fresh", "rel_path": "playbooks/fresh-copy.yml", "content": PLAYBOOK},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert same_path.status_code == 400
    assert same_path.json()["detail"]["code"] == "name_exists"
    assert same_name.status_code == 400
    assert same_name.json()["detail"]["code"] == "name_exists"
    assert not (repo_path / "playbooks" / "fresh-copy.yml").exists()


@pytest.mark.asyncio(loop_scope="session")
async def test_create_playbook_rejects_bad_extension_before_write(client, monkeypatch, tmp_path):
    project, repo_path = await _project(client, monkeypatch, tmp_path, "bad-extension-playbook")

    res = await client.post(
        "/api/playbooks",
        json={"project_id": project["id"], "name": "bad-ext", "rel_path": "playbooks/bad.txt", "content": PLAYBOOK},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert res.status_code == 400
    assert res.json()["detail"] == {"code": "bad_path", "message": "Playbook file must end in .yml or .yaml"}
    assert not (repo_path / "playbooks" / "bad.txt").exists()


@pytest.mark.asyncio(loop_scope="session")
async def test_create_playbook_invalid_lint_rolls_back_file(client, monkeypatch, tmp_path):
    project, repo_path = await _project(client, monkeypatch, tmp_path, "invalid-playbook")

    res = await client.post(
        "/api/playbooks",
        json={"project_id": project["id"], "name": "bad", "rel_path": "playbooks/bad.yml", "content": "---\n- name: Bad\n  hosts: all\n  tasks: nope\n"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "lint_error"
    assert not (repo_path / "playbooks" / "bad.yml").exists()


@pytest.mark.asyncio(loop_scope="session")
async def test_register_missing_playbook_without_content_still_404(client, monkeypatch, tmp_path):
    project, _ = await _project(client, monkeypatch, tmp_path, "missing-playbook")

    res = await client.post(
        "/api/playbooks",
        json={"project_id": project["id"], "name": "missing", "rel_path": "playbooks/missing.yml"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert res.status_code == 404
    assert res.json()["detail"] == {"code": "file_not_found", "message": "Playbook file not found in git repo"}



@pytest.mark.asyncio(loop_scope="session")
async def test_create_inventory_with_content_commits_file_and_returns_row(client, db, monkeypatch, tmp_path):
    project, repo_path = await _inventory_repo(client, db, monkeypatch, tmp_path)

    res = await client.post(
        "/api/inventories",
        json={
            "name": "fresh-inventory",
            "filename": "fresh.yml",
            "format": "yaml",
            "content": INVENTORY_YAML,
            "message": "Create fresh inventory",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body == {"id": body["id"], "rel_path": "inventories/fresh.yml", "name": "fresh-inventory", "format": "yaml", "project_id": None}
    assert (repo_path / "inventories" / "fresh.yml").read_text() == INVENTORY_YAML
    commit = (await db.execute(select(Commit).where(Commit.message == "Create fresh inventory"))).scalar_one()
    assert commit.project_id == project.id
    assert commit.files_changed == ["inventories/fresh.yml"]
    assert len(commit.sha) == 40


@pytest.mark.asyncio(loop_scope="session")
async def test_create_inventory_rejects_malformed_yaml_without_file(client, db, monkeypatch, tmp_path):
    _, repo_path = await _inventory_repo(client, db, monkeypatch, tmp_path)

    res = await client.post(
        "/api/inventories",
        json={"name": "bad-inventory", "filename": "bad.yml", "format": "yaml", "content": "all: [\n"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "invalid_yaml"
    assert not (repo_path / "inventories" / "bad.yml").exists()


@pytest.mark.asyncio(loop_scope="session")
async def test_register_missing_inventory_without_content_still_404(client, db, monkeypatch, tmp_path):
    await _inventory_repo(client, db, monkeypatch, tmp_path)

    res = await client.post(
        "/api/inventories",
        json={"name": "missing-inventory", "filename": "missing.yml", "format": "yaml"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert res.status_code == 404
    assert res.json()["detail"] == {"code": "file_not_found", "message": "Inventory file not found in git repo"}


@pytest.mark.asyncio(loop_scope="session")
async def test_create_inventory_rejects_executable_suffix_after_stripping(client, db, monkeypatch, tmp_path):
    _, repo_path = await _inventory_repo(client, db, monkeypatch, tmp_path)

    res = await client.post(
        "/api/inventories",
        json={"name": "evil", "filename": "evil.py ", "format": "ini", "content": "[all]\nlocalhost\n"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "executable_inventory_forbidden"
    assert not (repo_path / "inventories" / "evil.py").exists()

@pytest.mark.asyncio(loop_scope="session")
async def test_create_inventory_checks_duplicate_before_writing_content(client, db, monkeypatch, tmp_path):
    _, repo_path = await _inventory_repo(client, db, monkeypatch, tmp_path)
    existing = repo_path / "inventories" / "existing.yml"
    existing.write_text(INVENTORY_YAML)
    repo = Repo(repo_path)
    actor = Actor("admin", "admin@example.com")
    repo.index.add(["inventories/existing.yml"])
    repo.index.commit("Add existing inventory", author=actor, committer=actor)

    registered = await client.post(
        "/api/inventories",
        json={"name": "existing-inventory", "filename": "existing.yml", "format": "yaml"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    duplicate = await client.post(
        "/api/inventories",
        json={"name": "existing-inventory", "filename": "should-not-write.yml", "format": "yaml", "content": INVENTORY_YAML},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert registered.status_code == 200
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"]["code"] == "name_exists"
    assert not (repo_path / "inventories" / "should-not-write.yml").exists()