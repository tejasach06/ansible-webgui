import pytest
from pathlib import Path
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import Credential, CredentialKind, Inventory, InventoryFormat, JobTemplate, Playbook, Project, ProjectMembership, ProjectRole, Role, User
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
async def test_list_credentials_no_project_id_filters_by_visible_projects(client, db):
    project_a, _ = await _project_with_playbooks(db, "cred-vis-a")
    project_b, _ = await _project_with_playbooks(db, "cred-vis-b")

    c_a = Credential(project_id=project_a.id, name="cred-a", kind=CredentialKind.ssh_password, payload_enc=b"x", created_by=1)
    c_b = Credential(project_id=project_b.id, name="cred-b", kind=CredentialKind.ssh_password, payload_enc=b"y", created_by=1)
    db.add_all([c_a, c_b])

    role_user = (await db.execute(select(Role).where(Role.name == "user"))).scalar_one_or_none()
    if not role_user:
        role_user = Role(name="user")
        db.add(role_user)
        await db.flush()

    member_user = User(username="cred-member", email="cred-member@example.com", password_hash=hash_password("password123"), roles=[role_user])
    db.add(member_user)
    await db.flush()

    membership = ProjectMembership(project_id=project_a.id, user_id=member_user.id, role=ProjectRole.viewer)
    db.add(membership)
    await db.commit()

    # Login as member_user
    login_res = await client.post("/api/auth/login", json={"username": "cred-member", "password": "password123"}, headers=MUTATE)
    assert login_res.status_code == 200

    res = await client.get("/api/credentials")
    assert res.status_code == 200
    names = [item["name"] for item in res.json()]
    assert "cred-a" in names
    assert "cred-b" not in names


@pytest.mark.asyncio(loop_scope="session")
async def test_create_credential_become_same_as_ssh_flag_validation(client, db):
    await login(client)
    project, _ = await _project_with_playbooks(db, "cred-become-flag-proj")

    bad_res = await client.post(
        "/api/credentials",
        json={"project_id": project.id, "name": "bad-key", "kind": "ssh_key", "payload": "keydata", "become_same_as_ssh": True},
        headers=MUTATE,
    )
    assert bad_res.status_code == 400
    assert bad_res.json()["detail"]["code"] == "become_same_requires_ssh_password"

    ok_res = await client.post(
        "/api/credentials",
        json={"project_id": project.id, "name": "ok-ssh-pass", "kind": "ssh_password", "payload": "passdata", "become_same_as_ssh": True},
        headers=MUTATE,
    )
    assert ok_res.status_code == 200
    assert ok_res.json()["become_same_as_ssh"] is True


@pytest.mark.asyncio(loop_scope="session")
async def test_request_job_rejects_credential_not_in_project(client, db):
    await login(client)
    project_a, _ = await _project_with_playbooks(db, "job-proj-a")
    project_b, _ = await _project_with_playbooks(db, "job-proj-b")
    playbook_a = Playbook(project_id=project_a.id, rel_path="playbooks/site.yml", name="site-a")
    inv_a = await _inventory(db, "job-inv-a")
    c_b = Credential(project_id=project_b.id, name="cred-other-proj", kind=CredentialKind.ssh_password, payload_enc=b"x", created_by=1)
    db.add_all([playbook_a, c_b])
    await db.commit()
    await db.refresh(playbook_a)
    await db.refresh(c_b)

    res = await client.post(
        "/api/jobs",
        json={"playbook_id": playbook_a.id, "inventory_id": inv_a.id, "mode": "check", "credential_ids": [c_b.id]},
        headers=MUTATE,
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "credential_not_in_project"


@pytest.mark.asyncio(loop_scope="session")
async def test_request_job_rejects_become_password_conflict(client, db):
    await login(client)
    project, _ = await _project_with_playbooks(db, "job-become-conflict-proj")
    playbook = Playbook(project_id=project.id, rel_path="playbooks/site.yml", name="site")
    inv = await _inventory(db, "job-become-conflict-inv")
    c1 = Credential(project_id=project.id, name="ssh-reused", kind=CredentialKind.ssh_password, become_same_as_ssh=True, payload_enc=b"x", created_by=1)
    c2 = Credential(project_id=project.id, name="separate-become", kind=CredentialKind.become_password, payload_enc=b"y", created_by=1)
    db.add_all([playbook, c1, c2])
    await db.commit()
    await db.refresh(playbook)
    await db.refresh(c1)
    await db.refresh(c2)

    res = await client.post(
        "/api/jobs",
        json={"playbook_id": playbook.id, "inventory_id": inv.id, "mode": "check", "credential_ids": [c1.id, c2.id]},
        headers=MUTATE,
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "become_password_conflict"

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
