import pytest
from app.core.config import settings
from app.db.models import Project, Playbook, Inventory, InventoryFormat
from app.services.content import ensure_inventory_repo, init_project_repo
from test_content_api import login


@pytest.mark.asyncio(loop_scope="session")
async def test_set_project_default_inventory(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await ensure_inventory_repo(db)
    await login(client)

    p_res = await client.post("/api/projects", json={"name": "proj-def"}, headers={"X-Requested-With": "XMLHttpRequest"})
    p_id = p_res.json()["id"]

    inv_res = await client.post(
        "/api/inventories",
        json={"name": "inv-for-def", "filename": "hosts.yml", "format": "yaml", "project_id": p_id, "content": "all: {hosts: {node1: {}}}\n"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    inv_id = inv_res.json()["id"]

    patch_res = await client.patch(
        f"/api/projects/{p_id}",
        json={"default_inventory_id": inv_id},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["default_inventory_id"] == inv_id


@pytest.mark.asyncio(loop_scope="session")
async def test_default_inventory_rejects_foreign_project_inventory(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await ensure_inventory_repo(db)
    await login(client)

    p1 = (await client.post("/api/projects", json={"name": "p1-def"}, headers={"X-Requested-With": "XMLHttpRequest"})).json()
    p2 = (await client.post("/api/projects", json={"name": "p2-def"}, headers={"X-Requested-With": "XMLHttpRequest"})).json()

    inv2 = (await client.post(
        "/api/inventories",
        json={"name": "p2-inv", "filename": "hosts.yml", "format": "yaml", "project_id": p2["id"], "content": "all: {hosts: {node2: {}}}\n"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )).json()

    # Attempt to assign p2's inventory as p1's default
    patch_res = await client.patch(
        f"/api/projects/{p1['id']}",
        json={"default_inventory_id": inv2["id"]},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert patch_res.status_code == 422
    assert patch_res.json()["detail"]["code"] == "inventory_not_in_project"


@pytest.mark.asyncio(loop_scope="session")
async def test_launch_without_inventory_uses_project_default(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await ensure_inventory_repo(db)
    await login(client)

    p_res = await client.post("/api/projects", json={"name": "launch-proj"}, headers={"X-Requested-With": "XMLHttpRequest"})
    p_id = p_res.json()["id"]

    inv_res = await client.post(
        "/api/inventories",
        json={"name": "def-inv", "filename": "def.yml", "format": "yaml", "project_id": p_id, "content": "all: {hosts: {srv: {}}}\n"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    inv_id = inv_res.json()["id"]

    # Set project default
    await client.patch(
        f"/api/projects/{p_id}",
        json={"default_inventory_id": inv_id},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    # Create playbook
    pb_res = await client.post(
        "/api/playbooks",
        json={
            "project_id": p_id,
            "name": "ping",
            "rel_path": "ping.yml",
            "content": "- hosts: all\n  tasks: [{ansible.builtin.ping: {}}]\n",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    pb_id = pb_res.json()["id"]

    # Request job without inventory_id
    job_res = await client.post(
        "/api/jobs",
        json={"playbook_id": pb_id, "mode": "check", "inventory_id": None},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert job_res.status_code == 200
    job_id = job_res.json()["id"]

    job_detail = (await client.get(f"/api/jobs/{job_id}")).json()
    assert job_detail["inventory_id"] == inv_id
    assert job_detail["params_snapshot"]["inventory_rel_path"] == f"inventories/launch-proj/def.yml"


@pytest.mark.asyncio(loop_scope="session")
async def test_launch_without_inventory_and_no_default_returns_inventory_required(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await ensure_inventory_repo(db)
    await login(client)

    p_res = await client.post("/api/projects", json={"name": "no-def-proj"}, headers={"X-Requested-With": "XMLHttpRequest"})
    p_id = p_res.json()["id"]

    pb_res = await client.post(
        "/api/playbooks",
        json={
            "project_id": p_id,
            "name": "ping",
            "rel_path": "ping.yml",
            "content": "- hosts: all\n  tasks: [{ansible.builtin.ping: {}}]\n",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    pb_id = pb_res.json()["id"]

    job_res = await client.post(
        "/api/jobs",
        json={"playbook_id": pb_id, "mode": "check", "inventory_id": None},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert job_res.status_code == 422
    assert job_res.json()["detail"]["code"] == "inventory_required"


@pytest.mark.asyncio(loop_scope="session")
async def test_clearing_default_with_zero_sentinel(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await ensure_inventory_repo(db)
    await login(client)

    p_res = await client.post("/api/projects", json={"name": "clear-proj"}, headers={"X-Requested-With": "XMLHttpRequest"})
    p_id = p_res.json()["id"]

    inv_res = await client.post(
        "/api/inventories",
        json={"name": "to-clear-inv", "filename": "clear.yml", "format": "yaml", "project_id": p_id, "content": "all: {hosts: {node: {}}}\n"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    inv_id = inv_res.json()["id"]

    # Set default
    await client.patch(
        f"/api/projects/{p_id}",
        json={"default_inventory_id": inv_id},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    # Clear with 0 sentinel
    clear_res = await client.patch(
        f"/api/projects/{p_id}",
        json={"default_inventory_id": 0},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert clear_res.status_code == 200
    assert clear_res.json()["default_inventory_id"] is None
