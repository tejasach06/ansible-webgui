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
    assert body["project_id"] is None
    assert project.name == settings.INVENTORY_REPO_NAME


@pytest.mark.asyncio(loop_scope="session")
async def test_inventories_project_filter_returns_shared_and_owned(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await ensure_inventory_repo(db)
    await login(client)

    p1_res = await client.post("/api/projects", json={"name": "p1"}, headers={"X-Requested-With": "XMLHttpRequest"})
    p1_id = p1_res.json()["id"]
    p2_res = await client.post("/api/projects", json={"name": "p2"}, headers={"X-Requested-With": "XMLHttpRequest"})
    p2_id = p2_res.json()["id"]

    # 1. Shared inventory
    await client.post(
        "/api/inventories",
        json={"name": "shared-inv", "filename": "shared.yml", "format": "yaml", "content": "all: {hosts: {localhost: {}}}\n"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    # 2. P1 inventory
    await client.post(
        "/api/inventories",
        json={"name": "p1-inv", "filename": "p1.yml", "format": "yaml", "project_id": p1_id, "content": "all: {hosts: {p1host: {}}}\n"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    # Query for p1 -> returns shared + p1
    res1 = await client.get(f"/api/inventories?project_id={p1_id}")
    assert res1.status_code == 200
    names1 = [i["name"] for i in res1.json()]
    assert "shared-inv" in names1 and "p1-inv" in names1

    # Query for p2 -> returns only shared
    res2 = await client.get(f"/api/inventories?project_id={p2_id}")
    assert res2.status_code == 200
    names2 = [i["name"] for i in res2.json()]
    assert "shared-inv" in names2 and "p1-inv" not in names2


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
        json={"content": "[all]\nweb1\nweb2\n", "message": "INI allows valid format", "base_sha": ini_file["sha"]},
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


@pytest.mark.asyncio(loop_scope="session")
async def test_project_scoped_inventory_written_under_project_subdirectory(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await ensure_inventory_repo(db)
    await login(client)

    p_res = await client.post("/api/projects", json={"name": "subproj"}, headers={"X-Requested-With": "XMLHttpRequest"})
    p_id = p_res.json()["id"]

    res = await client.post(
        "/api/inventories",
        json={"name": "scoped-inv", "filename": "hosts.yml", "format": "yaml", "project_id": p_id, "content": "all: {hosts: {srv1: {}}}\n"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["rel_path"] == "inventories/subproj/hosts.yml"
    assert body["project_id"] == p_id


@pytest.mark.asyncio(loop_scope="session")
async def test_same_inventory_name_allowed_in_two_projects(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await ensure_inventory_repo(db)
    await login(client)

    p1 = (await client.post("/api/projects", json={"name": "alpha"}, headers={"X-Requested-With": "XMLHttpRequest"})).json()
    p2 = (await client.post("/api/projects", json={"name": "beta"}, headers={"X-Requested-With": "XMLHttpRequest"})).json()

    r1 = await client.post(
        "/api/inventories",
        json={"name": "prod", "filename": "hosts.yml", "format": "yaml", "project_id": p1["id"], "content": "all: {hosts: {alpha1: {}}}\n"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert r1.status_code == 200

    r2 = await client.post(
        "/api/inventories",
        json={"name": "prod", "filename": "hosts.yml", "format": "yaml", "project_id": p2["id"], "content": "all: {hosts: {beta1: {}}}\n"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert r2.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_verify_inventory_returns_groups_and_hosts(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    inv, _ = await _register_inventory(
        client, db, monkeypatch, tmp_path, name="verify-yaml",
        content="web:\n  hosts:\n    node1.example.com:\n    node2.example.com:\n"
    )
    verify_res = await client.post(
        f"/api/inventories/{inv['id']}/verify",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert verify_res.status_code == 200
    data = verify_res.json()
    assert "node1.example.com" in data["hosts"]
    assert "node2.example.com" in data["hosts"]
    assert "web" in data["groups"]
    assert "node1.example.com" in data["groups"]["web"]


@pytest.mark.asyncio(loop_scope="session")
async def test_verify_rejects_malformed_inventory(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    inv, repo_path = await _register_inventory(client, db, monkeypatch, tmp_path, name="broken-check")
    file_path = repo_path / inv["rel_path"]
    file_path.write_text("[unclosed_ini_section\n")

    verify_res = await client.post(
        f"/api/inventories/{inv['id']}/verify",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert verify_res.status_code == 422
    assert verify_res.json()["detail"]["code"] == "inventory_invalid"


@pytest.mark.asyncio(loop_scope="session")
async def test_register_rejects_unparseable_inventory_and_leaves_repo_clean(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await ensure_inventory_repo(db)
    repo_path = get_inventory_repo_path()
    await login(client)

    res = await client.post(
        "/api/inventories",
        json={"name": "broken-reg", "filename": "broken.ini", "format": "ini", "content": "[unclosed\n"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "inventory_invalid"
    assert not (repo_path / "inventories" / "broken.ini").exists()