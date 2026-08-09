import pytest

from app.db.models import JobMode, JobRun, JobStatus
from test_content_api import login


@pytest.mark.asyncio(loop_scope="session")
async def test_relaunch_running_rejected(client, db):
    job = JobRun(playbook_id=1, inventory_id=1, mode=JobMode.check, status=JobStatus.running, requested_by=1, params_snapshot={"mode": "check"})
    db.add(job)
    await db.commit()
    await login(client)
    res = await client.post(f"/api/jobs/{job.id}/relaunch", json={"hosts": "all"}, headers={"X-Requested-With": "XMLHttpRequest"})
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "bad_state"


@pytest.mark.asyncio(loop_scope="session")
async def test_relaunch_failed_without_failed_hosts_rejected(client, db):
    job = JobRun(playbook_id=1, inventory_id=1, mode=JobMode.check, status=JobStatus.successful, requested_by=1, params_snapshot={"mode": "check"})
    db.add(job)
    await db.commit()
    await login(client)
    res = await client.post(f"/api/jobs/{job.id}/relaunch", json={"hosts": "failed"}, headers={"X-Requested-With": "XMLHttpRequest"})
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "no_failed_hosts"
