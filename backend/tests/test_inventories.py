import pytest
from git import Actor, Repo

from app.core.config import settings
from app.services.content import ensure_inventory_repo, get_inventory_repo_path

from test_content_api import login


@pytest.mark.asyncio(loop_scope="session")
async def test_register_global_inventory_from_shared_repo(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    project = await ensure_inventory_repo(db)
    repo_path = get_inventory_repo_path()
    inventory = repo_path / "inventories" / "prod.yml"
    inventory.write_text("all: {hosts: {localhost: {ansible_connection: local}}}\n")
    repo = Repo(repo_path)
    repo.index.add(["inventories/prod.yml"])
    actor = Actor("admin", "admin@example.com")
    repo.index.commit("Add prod inventory", author=actor, committer=actor)

    await login(client)
    res = await client.post(
        "/api/inventories",
        json={"name": "prod", "filename": "prod.yml", "format": "yaml"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "prod"
    assert body["rel_path"] == "inventories/prod.yml"
    assert "project_id" not in body
    assert project.name == settings.INVENTORY_REPO_NAME


@pytest.mark.asyncio(loop_scope="session")
async def test_inventories_rejects_removed_project_filter(client):
    await login(client)

    res = await client.get("/api/inventories?project_id=1")

    assert res.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_reserved_inventory_project_name_rejected(client):
    await login(client)

    res = await client.post(
        "/api/projects",
        json={"name": settings.INVENTORY_REPO_NAME},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "reserved_project_name"


@pytest.mark.asyncio(loop_scope="session")
async def test_duplicate_inventory_path_rejected(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await ensure_inventory_repo(db)
    repo_path = get_inventory_repo_path()
    inventory = repo_path / "inventories" / "prod2.yml"
    inventory.write_text("all: {hosts: {localhost: {ansible_connection: local}}}\n")
    repo = Repo(repo_path)
    repo.index.add(["inventories/prod2.yml"])
    actor = Actor("admin", "admin@example.com")
    repo.index.commit("Add prod inventory", author=actor, committer=actor)

    await login(client)
    payload = {"name": "prod2-a", "filename": "prod2.yml", "format": "yaml"}
    first = await client.post("/api/inventories", json=payload, headers={"X-Requested-With": "XMLHttpRequest"})
    second = await client.post(
        "/api/inventories",
        json={**payload, "name": "prod2-b"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["detail"]["code"] == "name_exists"

async def _register_inventory(client, db, monkeypatch, tmp_path, rel_path=None, name=None, fmt="yaml", content="all: {hosts: {localhost: {ansible_connection: local}}}\n"):
    name = name or tmp_path.name.replace("/", "-")
    rel_path = rel_path or f"inventories/{name}.yml"
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await ensure_inventory_repo(db)
    repo_path = get_inventory_repo_path()
    inventory = repo_path / rel_path
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text(content)
    repo = Repo(repo_path)
    repo.index.add([rel_path])
    actor = Actor("admin", "admin@example.com")
    repo.index.commit(f"Add {name} inventory", author=actor, committer=actor)
    await login(client)
    res = await client.post(
        "/api/inventories",
        json={"name": name, "filename": rel_path.removeprefix("inventories/"), "format": fmt},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res.status_code == 200
    return res.json(), repo_path

@pytest.mark.asyncio(loop_scope="session")
async def test_register_inventory_rejects_subdirectory_filenames(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await ensure_inventory_repo(db)
    await login(client)

    for filename in ("sub/prod.yml", "../escape.yml"):
        res = await client.post(
            "/api/inventories",
            json={"name": f"bad-{filename}", "filename": filename, "format": "yaml"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        assert res.status_code == 400
        assert res.json()["detail"]["code"] == "bad_path"


@pytest.mark.asyncio(loop_scope="session")
async def test_read_inventory_file_returns_content_and_sha(client, db, monkeypatch, tmp_path):
    inv, _ = await _register_inventory(client, db, monkeypatch, tmp_path)

    res = await client.get(f"/api/inventories/{inv['id']}/file")

    assert res.status_code == 200
    body = res.json()
    assert body["content"] == "all: {hosts: {localhost: {ansible_connection: local}}}\n"
    assert len(body["sha"]) == 40


@pytest.mark.asyncio(loop_scope="session")
async def test_save_inventory_file_commits_and_returns_updated_content(client, db, monkeypatch, tmp_path):
    inv, _ = await _register_inventory(client, db, monkeypatch, tmp_path)
    current = (await client.get(f"/api/inventories/{inv['id']}/file")).json()

    res = await client.post(
        f"/api/inventories/{inv['id']}/file",
        json={"content": "all: {hosts: {web1: {}}}\n", "message": "Update prod", "base_sha": current["sha"]},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert res.status_code == 200
    assert res.json()["sha"] != current["sha"]
    reread = (await client.get(f"/api/inventories/{inv['id']}/file")).json()
    assert reread["content"] == "all: {hosts: {web1: {}}}\n"


@pytest.mark.asyncio(loop_scope="session")
async def test_save_inventory_file_rejects_stale_base_sha(client, db, monkeypatch, tmp_path):
    inv, _ = await _register_inventory(client, db, monkeypatch, tmp_path)

    res = await client.post(
        f"/api/inventories/{inv['id']}/file",
        json={"content": "all: {hosts: {web1: {}}}\n", "message": "Update prod", "base_sha": "deadbeef"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "stale_write"


@pytest.mark.asyncio(loop_scope="session")
async def test_save_inventory_file_validates_yaml_but_not_ini(client, db, monkeypatch, tmp_path):
    yaml_inv, _ = await _register_inventory(client, db, monkeypatch, tmp_path / "yaml", name="prod-yaml")
    yaml_file = (await client.get(f"/api/inventories/{yaml_inv['id']}/file")).json()

    yaml_res = await client.post(
        f"/api/inventories/{yaml_inv['id']}/file",
        json={"content": "a: [1,\n", "message": "Bad yaml", "base_sha": yaml_file["sha"]},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert yaml_res.status_code == 422
    assert yaml_res.json()["detail"]["code"] == "invalid_yaml"

    ini_inv, _ = await _register_inventory(client, db, monkeypatch, tmp_path / "ini", rel_path="inventories/prod.ini", name="prod-ini", fmt="ini", content="[all]\nlocalhost\n")
    ini_file = (await client.get(f"/api/inventories/{ini_inv['id']}/file")).json()

    ini_res = await client.post(
        f"/api/inventories/{ini_inv['id']}/file",
        json={"content": "a: [1,\n", "message": "INI allows this", "base_sha": ini_file["sha"]},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert ini_res.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_update_inventory_metadata_and_rejects_duplicate_name(client, db, monkeypatch, tmp_path):
    inv, _ = await _register_inventory(client, db, monkeypatch, tmp_path, name="prod-meta")
    await _register_inventory(client, db, monkeypatch, tmp_path / "other", rel_path="inventories/other-meta.yml", name="other-meta")

    renamed = await client.patch(
        f"/api/inventories/{inv['id']}",
        json={"name": "prod2-meta"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert renamed.status_code == 200
    assert renamed.json()["name"] == "prod2-meta"

    duplicate = await client.patch(
        f"/api/inventories/{inv['id']}",
        json={"name": "other-meta"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert duplicate.status_code == 400
    assert duplicate.json()["detail"]["code"] == "name_exists"