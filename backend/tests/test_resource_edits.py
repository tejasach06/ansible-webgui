import pytest
from pathlib import Path
from sqlalchemy import select

from app.core.config import settings
from app.db.models import Credential, CredentialKind, Inventory, InventoryFormat, JobTemplate, Playbook, Project
from app.services.content import get_project_repo_path, init_project_repo
from app.services.credentials import decrypt_payload
from test_content_api import login

MUTATE = {"X-Requested-With": "XMLHttpRequest"}


async def _project_with_playbooks(db, name: str):
    project = Project(name=name, git_path=f"/data/content/{name}")
    db.add(project)
    await db.commit()
    await db.refresh(project)
    await init_project_repo(db, project, "admin", "admin@example.com")
    repo_path = get_project_repo_path(project.name)
    site = repo_path / "playbooks" / "site.yml"
    site.write_text("- hosts: localhost\n  tasks: []\n")
    other = repo_path / "playbooks" / "other.yml"
    other.write_text("- hosts: all\n  tasks: []\n")
    return project, repo_path


async def _inventory(db, name: str = "resource-inv"):
    inv = Inventory(name=name, rel_path=f"{name}.yml", format=InventoryFormat.yaml)
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv


@pytest.mark.asyncio(loop_scope="session")
async def test_patch_credential_username_and_list_hides_payload(client, db):
    await login(client)
    project, _ = await _project_with_playbooks(db, "cred-proj-1")
    created = await client.post("/api/credentials", json={"project_id": project.id, "name": "machine", "kind": "ssh_password", "payload": "secret"}, headers=MUTATE)
    assert created.status_code == 200

    res = await client.patch(f"/api/credentials/{created.json()['id']}", json={"username": "deploy"}, headers=MUTATE)

    assert res.status_code == 200
    assert res.json()["username"] == "deploy"
    listed = await client.get(f"/api/credentials?project_id={project.id}")
    assert listed.status_code == 200
    assert all("payload" not in item for item in listed.json())


@pytest.mark.asyncio(loop_scope="session")
async def test_patch_credential_rotates_secret_and_name_keeps_secret(client, db):
    await login(client)
    project, _ = await _project_with_playbooks(db, "cred-proj-2")
    created = await client.post("/api/credentials", json={"project_id": project.id, "name": "rotate", "kind": "ssh_key", "payload": "old"}, headers=MUTATE)
    cred_id = created.json()["id"]

    rotated = await client.patch(f"/api/credentials/{cred_id}", json={"payload": "newsecret"}, headers=MUTATE)
    renamed = await client.patch(f"/api/credentials/{cred_id}", json={"name": "renamed-rotate"}, headers=MUTATE)

    assert rotated.status_code == 200
    assert renamed.status_code == 200
    row = (await db.execute(select(Credential).where(Credential.id == cred_id))).scalar_one()
    assert decrypt_payload(row.payload_enc) == "newsecret"


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_credential_referenced_by_template_returns_conflict(client, db):
    await login(client)
    project, _ = await _project_with_playbooks(db, "cred-template-project")
    playbook = Playbook(project_id=project.id, rel_path="playbooks/site.yml", name="site")
    inv = await _inventory(db, "cred-template-inv")
    cred = Credential(project_id=project.id, name="templated-cred", kind=CredentialKind.ssh_password, username="deploy", payload_enc=b"x", created_by=1)
    db.add_all([playbook, cred])
    await db.commit()
    await db.refresh(playbook)
    await db.refresh(cred)
    template = JobTemplate(project_id=project.id, name="uses-cred", playbook_id=playbook.id, inventory_id=inv.id, credential_ids=[cred.id])
    db.add(template)
    await db.commit()

    res = await client.delete(f"/api/credentials/{cred.id}", headers=MUTATE)

    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "credential_in_use"


@pytest.mark.asyncio(loop_scope="session")
async def test_request_job_rejects_multiple_credential_usernames(client, db):
    await login(client)
    project, _ = await _project_with_playbooks(db, "job-user-conflict-project")
    playbook = Playbook(project_id=project.id, rel_path="playbooks/site.yml", name="site")
    inv = await _inventory(db, "job-user-conflict-inv")
    c1 = Credential(project_id=project.id, name="user-one", kind=CredentialKind.ssh_password, username="one", payload_enc=b"x", created_by=1)
    c2 = Credential(project_id=project.id, name="user-two", kind=CredentialKind.ssh_key, username="two", payload_enc=b"y", created_by=1)
    db.add_all([playbook, c1, c2])
    await db.commit()
    await db.refresh(playbook)
    await db.refresh(c1)
    await db.refresh(c2)

    res = await client.post("/api/jobs", json={"playbook_id": playbook.id, "inventory_id": inv.id, "mode": "check", "credential_ids": [c1.id, c2.id]}, headers=MUTATE)

    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "credential_user_conflict"


@pytest.mark.asyncio(loop_scope="session")
async def test_request_job_allows_password_and_become_credentials_for_same_username(client, db):
    await login(client)
    project, _ = await _project_with_playbooks(db, "job-user-shared-project")
    playbook = Playbook(project_id=project.id, rel_path="playbooks/site.yml", name="site")
    inv = await _inventory(db, "job-user-shared-inv")
    c1 = Credential(project_id=project.id, name="shared-ssh", kind=CredentialKind.ssh_password, username="tejas", payload_enc=b"x", created_by=1)
    c2 = Credential(project_id=project.id, name="shared-become", kind=CredentialKind.become_password, username="tejas", payload_enc=b"y", created_by=1)
    db.add_all([playbook, c1, c2])
    await db.commit()
    await db.refresh(playbook)
    await db.refresh(c1)
    await db.refresh(c2)

    res = await client.post("/api/jobs", json={"playbook_id": playbook.id, "inventory_id": inv.id, "mode": "check", "credential_ids": [c1.id, c2.id]}, headers=MUTATE)

    assert res.status_code != 422


@pytest.mark.asyncio(loop_scope="session")
async def test_patch_playbook_repaths_existing_file_and_rejects_missing(client, db):
    await login(client)
    project, _ = await _project_with_playbooks(db, "playbook-repath-project")
    created = await client.post("/api/playbooks", json={"project_id": project.id, "rel_path": "playbooks/site.yml", "name": "site"}, headers=MUTATE)
    playbook_id = created.json()["id"]

    missing = await client.patch(f"/api/playbooks/{playbook_id}", json={"rel_path": "playbooks/missing.yml"}, headers=MUTATE)
    valid = await client.patch(f"/api/playbooks/{playbook_id}", json={"rel_path": "playbooks/other.yml", "name": "other"}, headers=MUTATE)
    listed = await client.get(f"/api/playbooks?project_id={project.id}")

    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "file_not_found"
    assert valid.status_code == 200
    assert valid.json()["rel_path"] == "playbooks/other.yml"
    assert listed.json()[0]["rel_path"] == "playbooks/other.yml"


@pytest.mark.asyncio(loop_scope="session")
async def test_playbook_file_stale_write_and_valid_save(client, db, monkeypatch):
    await login(client)
    project, repo_path = await _project_with_playbooks(db, "playbook-file-project")
    created = await client.post("/api/playbooks", json={"project_id": project.id, "rel_path": "playbooks/site.yml", "name": "site"}, headers=MUTATE)
    playbook_id = created.json()["id"]
    first = await client.get(f"/api/playbooks/{playbook_id}/file")
    (repo_path / "playbooks" / "site.yml").write_text("- hosts: localhost\n  tasks:\n    - debug: {msg: changed}\n")
    from git import Repo
    repo = Repo(repo_path)
    repo.index.add(["playbooks/site.yml"])
    repo.index.commit("external change")

    stale = await client.post(f"/api/playbooks/{playbook_id}/file", json={"content": first.json()["content"], "message": "stale", "base_sha": first.json()["sha"]}, headers=MUTATE)
    monkeypatch.setattr("app.services.content.subprocess.run", lambda *a, **k: type("R", (), {"returncode": 0, "stderr": ""})())
    saved = await client.post(f"/api/playbooks/{playbook_id}/file", json={"content": "- hosts: all\n  tasks: []\n", "message": "valid"}, headers=MUTATE)
    reread = await client.get(f"/api/playbooks/{playbook_id}/file")

    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_write"
    assert saved.status_code == 200
    assert reread.json()["content"] == "- hosts: all\n  tasks: []\n"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_project_rejects_path_escape(client):
    await login(client)
    res = await client.post("/api/projects", json={"name": "../escape"}, headers=MUTATE)

    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "bad_name"


@pytest.mark.asyncio(loop_scope="session")
async def test_patch_project_renames_directory_and_git_path(client, db):
    await login(client)
    project, _ = await _project_with_playbooks(db, "old-project-name")

    res = await client.patch(f"/api/projects/{project.id}", json={"name": "new-project-name", "default_branch": "stable"}, headers=MUTATE)

    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "new-project-name"
    assert body["default_branch"] == "stable"
    content_root = Path(settings.CONTENT_ROOT)
    assert (content_root / "new-project-name").exists()
    assert not (content_root / "old-project-name").exists()
    await db.refresh(project)
    assert project.git_path == str(content_root / "new-project-name")
