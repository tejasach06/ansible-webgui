import json
import os
import tarfile

from git import Repo

from app.core.config import settings
from app.db.models import Credential
from app.services.credentials import decrypt_payload


def export_project_snapshot(project_name: str, temp_dir: str, git_sha: str | None) -> str:
    """git-archive the project repo at git_sha into <temp_dir>/project; symlink galaxy_roles/collections. Returns the export dir."""
    proj_git = os.path.join(settings.CONTENT_ROOT, project_name)
    proj_export = os.path.join(temp_dir, "project")
    os.makedirs(proj_export, exist_ok=True)

    repo = Repo(proj_git)
    sha = git_sha or repo.head.commit.hexsha

    archive_path = os.path.join(temp_dir, "archive.tar")
    with open(archive_path, "wb") as f:
        repo.archive(f, format="tar", treeish=sha)

    with tarfile.open(archive_path, "r") as tar:
        tar.extractall(path=proj_export)

    for extra in ["galaxy_roles", "collections"]:
        src = os.path.join(proj_git, extra)
        dst = os.path.join(proj_export, extra)
        if os.path.exists(src) and not os.path.exists(dst):
            os.symlink(src, dst)

    return proj_export


def export_inventory_snapshot(temp_dir: str, inventory_rel_path: str, inventory_git_sha: str | None) -> str:
    """git-archive the shared inventory repo into <temp_dir>/inventory. Returns the absolute inventory file path.
    Raises RuntimeError(f"inventory missing at pinned sha: {inventory_rel_path}") if the pinned file is absent."""
    inv_export = os.path.join(temp_dir, "inventory")
    os.makedirs(inv_export, exist_ok=True)
    inv_repo = Repo(os.path.join(settings.CONTENT_ROOT, settings.INVENTORY_REPO_NAME))
    inv_sha = inventory_git_sha or inv_repo.head.commit.hexsha
    inv_archive = os.path.join(temp_dir, "inventory.tar")
    with open(inv_archive, "wb") as f:
        inv_repo.archive(f, format="tar", treeish=inv_sha)
    with tarfile.open(inv_archive, "r") as tar:
        tar.extractall(path=inv_export)
    inventory_path = os.path.join(inv_export, inventory_rel_path)
    if not os.path.exists(inventory_path):
        raise RuntimeError(f"inventory missing at pinned sha: {inventory_rel_path}")
    return inventory_path


def materialize_credentials(db, temp_dir: str, credential_ids: list[int], snapshot: dict) -> tuple[str, list[str]]:
    """Create <temp_dir>/env, write ssh_key (0600) / passwords JSON / vault_pw (0600), build the ansible cmdline flags.
    Returns (env_dir, cmdline_extra)."""
    env_dir = os.path.join(temp_dir, "env")
    os.makedirs(env_dir, exist_ok=True)

    passwords = {}
    cmdline_extra = []
    need_ask_pass = False
    need_ask_become_pass = False
    user_arg: str | None = None

    if snapshot.get("mode") == "check":
        cmdline_extra.extend(["--check", "--diff"])

    if snapshot.get("become"):
        cmdline_extra.append("--become")
        if snapshot.get("become_user"):
            cmdline_extra.append(f"--become-user={snapshot['become_user']}")
        if snapshot.get("become_method"):
            cmdline_extra.append(f"--become-method={snapshot['become_method']}")

    if credential_ids:
        creds = db.query(Credential).filter(Credential.id.in_(credential_ids)).all()
        for c in creds:
            dec = decrypt_payload(c.payload_enc)
            if c.username and user_arg is None:
                user_arg = c.username
                cmdline_extra.append(f"--user={user_arg}")
            if c.kind == "ssh_key":
                key_file = os.path.join(env_dir, "ssh_key")
                with open(key_file, "w") as kf:
                    kf.write(dec)
                os.chmod(key_file, 0o600)
            elif c.kind == "ssh_password":
                passwords[r"^SSH password:\s*?$"] = dec
                need_ask_pass = True
            elif c.kind == "become_password":
                passwords[r"^BECOME password.*:\s*?$"] = dec
                need_ask_become_pass = True
            elif c.kind == "vault_password":
                v_file = os.path.join(temp_dir, "vault_pw")
                with open(v_file, "w") as vf:
                    vf.write(dec)
                os.chmod(v_file, 0o600)
                cmdline_extra.extend(["--vault-password-file", v_file])

    if need_ask_pass:
        cmdline_extra.append("--ask-pass")
    if need_ask_become_pass:
        cmdline_extra.append("--ask-become-pass")

    if passwords:
        with open(os.path.join(env_dir, "passwords"), "w") as pf:
            json.dump(passwords, pf)

    return env_dir, cmdline_extra
