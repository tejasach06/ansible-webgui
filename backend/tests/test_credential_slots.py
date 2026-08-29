import pytest
from app.db.models import CredentialKind, JobMode, JobRun, JobStatus, Playbook, Project, User
from app.services.credential_slots import find_slot_conflict
from app.services.credentials import encrypt_payload
from app.tasks.job_workspace import materialize_credentials
from app.tasks.run_job import run_job
from tests.conftest import TestingSyncSessionLocal


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
    def __init__(self, cred_id, kind, username, payload, become_same_as_ssh=False, name="test-cred"):
        self.id = cred_id
        self.name = name
        self.kind = kind
        self.username = username
        self.payload_enc = encrypt_payload(payload)
        self.become_same_as_ssh = become_same_as_ssh


def test_find_slot_conflict():
    assert find_slot_conflict([
        ("a", CredentialKind.ssh_key),
        ("b", CredentialKind.ssh_password),
    ]) == ("machine", ["a", "b"])

    assert find_slot_conflict([
        ("a", CredentialKind.ssh_key),
        ("v", CredentialKind.vault_password),
        ("b", CredentialKind.become_password),
    ]) is None


def test_materialize_credentials_raises_on_slot_conflict(tmp_path):
    creds = [
        _Credential(1, CredentialKind.ssh_key, "user1", "key1", name="key-a"),
        _Credential(2, CredentialKind.ssh_key, "user1", "key2", name="key-b"),
    ]
    with pytest.raises(RuntimeError, match=r"^credential_slot_conflict:machine"):
        materialize_credentials(_Db(creds), str(tmp_path), [1, 2], {"mode": "check"})


def test_run_job_exception_marks_job_failed(monkeypatch):
    monkeypatch.setattr("app.tasks.run_job.SyncSessionLocal", TestingSyncSessionLocal)

    def raiser(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.tasks.run_job.export_project_snapshot", raiser)

    with TestingSyncSessionLocal() as session:
        user = session.query(User).first()
        assert user is not None, "Admin user must exist from conftest setup"

        project = Project(name="test-slot-proj", git_path="/tmp/fake-git")
        session.add(project)
        session.flush()

        playbook = Playbook(project_id=project.id, name="site.yml", rel_path="site.yml")
        session.add(playbook)
        session.flush()

        job = JobRun(
            playbook_id=playbook.id,
            mode=JobMode.check,
            status=JobStatus.queued,
            requested_by=user.id,
            params_snapshot={"mode": "check", "inventory_rel_path": "x.yml", "credential_ids": []},
        )
        session.add(job)
        session.commit()
        job_id = job.id

    with pytest.raises(RuntimeError, match="boom"):
        run_job(job_id)

    with TestingSyncSessionLocal() as session:
        refreshed = session.query(JobRun).filter(JobRun.id == job_id).one()
        assert refreshed.status == JobStatus.failed
        assert refreshed.finished_at is not None
