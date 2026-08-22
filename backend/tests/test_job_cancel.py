from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api.jobs import lifecycle
from app.core.config import settings
from app.db.models import Inventory, InventoryFormat, JobMode, JobRun, JobStatus, Playbook, Project, User

from test_content_api import login


class FakeRedis:
    def __init__(self):
        self.sets = []

    async def set(self, key, value):
        self.sets.append((key, value))


async def _job(db, status: JobStatus, celery_task_id: str | None = None):
    suffix = uuid4().hex
    user = (
        await db.execute(select(User).where(User.username == settings.BOOTSTRAP_ADMIN_USER))
    ).unique().scalar_one()
    project = Project(name=f"cancel-{status.value}-{suffix}", git_path=f"/tmp/cancel-{suffix}")
    db.add(project)
    await db.flush()
    playbook = Playbook(project_id=project.id, rel_path="playbooks/site.yml", name=f"site-{suffix}")
    inventory = Inventory(name=f"hosts-{suffix}", rel_path=f"hosts-{suffix}.yml", format=InventoryFormat.yaml)
    db.add_all([playbook, inventory])
    await db.flush()
    job = JobRun(
        playbook_id=playbook.id,
        inventory_id=inventory.id,
        mode=JobMode.live,
        status=status,
        requested_by=user.id,
        celery_task_id=celery_task_id,
        params_snapshot={},
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


def _stub_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(lifecycle.aioredis, "from_url", lambda _url: fake)
    return fake


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_pending_approval_marks_job_canceled(client, db, monkeypatch):
    job = await _job(db, JobStatus.pending_approval)
    _stub_redis(monkeypatch)
    await login(client)

    res = await client.post(f"/api/jobs/{job.id}/cancel", headers={"X-Requested-With": "XMLHttpRequest"})

    assert res.status_code == 200
    assert res.json()["status"] == "canceled"
    await db.refresh(job)
    assert job.status == JobStatus.canceled


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_successful_job_returns_bad_state(client, db, monkeypatch):
    job = await _job(db, JobStatus.successful)
    _stub_redis(monkeypatch)
    await login(client)

    res = await client.post(f"/api/jobs/{job.id}/cancel", headers={"X-Requested-With": "XMLHttpRequest"})

    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "bad_state"
    await db.refresh(job)
    assert job.status == JobStatus.successful


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_running_sets_redis_flag_and_leaves_status_running(client, db, monkeypatch):
    job = await _job(db, JobStatus.running)
    redis = _stub_redis(monkeypatch)
    await login(client)

    res = await client.post(f"/api/jobs/{job.id}/cancel", headers={"X-Requested-With": "XMLHttpRequest"})

    assert res.status_code == 200
    assert res.json()["status"] == "running"
    assert redis.sets == [(f"job:{job.id}:cancel", "1")]
    await db.refresh(job)
    assert job.status == JobStatus.running
