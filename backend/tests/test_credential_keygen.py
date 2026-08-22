import pytest
from sqlalchemy import select
from app.core.config import settings
from app.db.models import Credential, CredentialKind, Playbook, Project, User
from app.services.content import get_project_repo_path
from app.services.credentials import decrypt_payload


async def login(client, username="admin", password=None):
    res = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password or settings.BOOTSTRAP_ADMIN_PASSWORD},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res.status_code == 200


async def _create_project(client, name="test-keygen-proj"):
    res = await client.post(
        "/api/projects",
        json={"name": name},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.asyncio(loop_scope="session")
async def test_credential_generate_ed25519(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await login(client)
    project = await _create_project(client, "proj-ed25519")

    res = await client.post(
        "/api/credentials/generate",
        json={
            "project_id": project["id"],
            "name": "ed-key",
            "username": "ansible",
            "key_type": "ed25519",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["name"] == "ed-key"
    assert data["kind"] == "ssh_key"
    assert data["username"] == "ansible"
    assert data["public_key"].startswith("ssh-ed25519 ")
    assert f"ansible-webgui:{project['id']}/ed-key" in data["public_key"]

    row = (await db.execute(select(Credential).where(Credential.id == data["id"]))).scalar_one()
    assert row.public_key == data["public_key"]
    decrypted_priv = decrypt_payload(row.payload_enc)
    assert "BEGIN OPENSSH PRIVATE KEY" in decrypted_priv


@pytest.mark.asyncio(loop_scope="session")
async def test_credential_generate_rsa4096(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await login(client)
    project = await _create_project(client, "proj-rsa")

    res = await client.post(
        "/api/credentials/generate",
        json={
            "project_id": project["id"],
            "name": "rsa-key",
            "key_type": "rsa4096",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["public_key"].startswith("ssh-rsa ")

    row = (await db.execute(select(Credential).where(Credential.id == data["id"]))).scalar_one()
    decrypted_priv = decrypt_payload(row.payload_enc)
    assert "BEGIN OPENSSH PRIVATE KEY" in decrypted_priv


@pytest.mark.asyncio(loop_scope="session")
async def test_credential_generate_validation_and_csrf(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await login(client)
    project = await _create_project(client, "proj-val")

    # Missing CSRF header
    res_no_csrf = await client.post(
        "/api/credentials/generate",
        json={"project_id": project["id"], "name": "k1", "key_type": "ed25519"},
    )
    assert res_no_csrf.status_code == 403

    # Successful creation
    res1 = await client.post(
        "/api/credentials/generate",
        json={"project_id": project["id"], "name": "dup-key", "key_type": "ed25519"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res1.status_code == 200

    # Duplicate name check
    res_dup = await client.post(
        "/api/credentials/generate",
        json={"project_id": project["id"], "name": "dup-key", "key_type": "ed25519"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res_dup.status_code == 400
    assert res_dup.json()["detail"]["code"] == "name_exists"


@pytest.mark.asyncio(loop_scope="session")
async def test_credential_rotation_clears_public_key(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await login(client)
    project = await _create_project(client, "proj-rot")

    res = await client.post(
        "/api/credentials/generate",
        json={"project_id": project["id"], "name": "rotate-me", "key_type": "ed25519"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res.status_code == 200
    cred_id = res.json()["id"]
    assert res.json()["public_key"] is not None

    # Patch with new payload -> public_key must become None
    patch_res = await client.patch(
        f"/api/credentials/{cred_id}",
        json={"payload": "fake-new-private-key"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["public_key"] is None

    row = (await db.execute(select(Credential).where(Credential.id == cred_id))).scalar_one()
    assert row.public_key is None


@pytest.mark.asyncio(loop_scope="session")
async def test_bootstrap_playbook_endpoint(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await login(client)
    project = await _create_project(client, "proj-bootstrap")

    # 1. Non-generated credential (or ssh_password) -> 422 not_generated_key
    res_pw = await client.post(
        "/api/credentials",
        json={
            "project_id": project["id"],
            "name": "mypass",
            "kind": "ssh_password",
            "payload": "secret",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res_pw.status_code == 200
    pw_id = res_pw.json()["id"]

    res_fail = await client.post(
        f"/api/credentials/{pw_id}/bootstrap-playbook",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res_fail.status_code == 422
    assert res_fail.json()["detail"]["code"] == "not_generated_key"

    # 2. Generated key -> 200, creates playbook in repo and Playbook record
    res_gen = await client.post(
        "/api/credentials/generate",
        json={"project_id": project["id"], "name": "gen-key", "key_type": "ed25519"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    gen_id = res_gen.json()["id"]
    pub_key = res_gen.json()["public_key"]

    res_boot = await client.post(
        f"/api/credentials/{gen_id}/bootstrap-playbook",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res_boot.status_code == 200
    boot_data = res_boot.json()
    assert boot_data["rel_path"] == "playbooks/_webgui_bootstrap_authorized_key.yml"
    assert boot_data["public_key"] == pub_key
    playbook_id = boot_data["playbook_id"]

    repo_path = get_project_repo_path(project["name"])
    file_on_disk = repo_path / "playbooks" / "_webgui_bootstrap_authorized_key.yml"
    assert file_on_disk.exists()
    assert "Install WebGUI generated public key" in file_on_disk.read_text()

    # Playbook DB row exists
    pb_row = (await db.execute(select(Playbook).where(Playbook.id == playbook_id))).scalar_one()
    assert pb_row.rel_path == "playbooks/_webgui_bootstrap_authorized_key.yml"

    # 3. Idempotent second call returns same playbook_id
    res_boot2 = await client.post(
        f"/api/credentials/{gen_id}/bootstrap-playbook",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert res_boot2.status_code == 200
    assert res_boot2.json()["playbook_id"] == playbook_id
