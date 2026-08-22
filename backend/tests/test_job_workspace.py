import json

from app.db.models import CredentialKind
from app.services.credentials import encrypt_payload
from app.tasks.job_workspace import materialize_credentials


class _CredsQuery:
    def __init__(self, creds):
        self._creds = creds

    def filter(self, _condition):
        return self

    def all(self):
        return self._creds


class _Db:
    def __init__(self, creds):
        self._creds = creds

    def query(self, _model):
        return _CredsQuery(self._creds)


class _Credential:
    def __init__(self, cred_id, kind, username, payload, become_same_as_ssh=False):
        self.id = cred_id
        self.kind = kind
        self.username = username
        self.payload_enc = encrypt_payload(payload)
        self.become_same_as_ssh = become_same_as_ssh

def test_materialize_password_credentials_adds_prompt_flags_and_one_user(tmp_path):
    creds = [
        _Credential(1, CredentialKind.ssh_password, "tejas", "ssh-secret"),
        _Credential(2, CredentialKind.become_password, "tejas", "become-secret"),
    ]

    env_dir, cmdline_extra = materialize_credentials(
        _Db(creds), str(tmp_path), [1, 2], {"mode": "check", "become": True}
    )

    assert "--ask-pass" in cmdline_extra
    assert "--ask-become-pass" in cmdline_extra
    assert cmdline_extra.count("--user=tejas") == 1
    with open(f"{env_dir}/passwords") as fh:
        assert json.load(fh) == {
            "^SSH password:\\s*?$": "ssh-secret",
            "^BECOME password.*:\\s*?$": "become-secret",
        }


def test_materialize_ssh_password_with_become_same_as_ssh_adds_both_prompts_and_passwords(tmp_path):
    creds = [
        _Credential(1, CredentialKind.ssh_password, "tejas", "ssh-secret", become_same_as_ssh=True),
    ]

    env_dir, cmdline_extra = materialize_credentials(
        _Db(creds), str(tmp_path), [1], {"mode": "check", "become": True}
    )

    assert "--ask-pass" in cmdline_extra
    assert "--ask-become-pass" in cmdline_extra
    assert cmdline_extra.count("--user=tejas") == 1
    with open(f"{env_dir}/passwords") as fh:
        assert json.load(fh) == {
            "^SSH password:\\s*?$": "ssh-secret",
            "^BECOME password.*:\\s*?$": "ssh-secret",
        }
