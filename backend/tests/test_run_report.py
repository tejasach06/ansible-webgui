from uuid import uuid4

import pytest
from test_content_api import login

from app.db.models import Inventory, InventoryFormat, JobMode, JobRun, JobStatus, Playbook, Project
from app.services.run_report import ReportBuilder


async def _persist_report(db, builder: ReportBuilder):
    if builder.pending_plays:
        db.add_all(builder.pending_plays)
        await db.flush()
        builder.pending_plays.clear()
    if builder.pending_tasks:
        for task in builder.pending_tasks:
            if not task.play_id:
                task.play_id = task._report_play.id
        db.add_all(builder.pending_tasks)
        await db.flush()
        builder.pending_tasks.clear()
    if builder.pending_results:
        for result in builder.pending_results:
            if not result.task_id:
                result.task_id = result._report_task.id
        db.add_all(builder.pending_results)
        await db.flush()
        builder.pending_results.clear()


@pytest.mark.asyncio(loop_scope="session")
async def test_report_builder_normalizes_events_and_report_sorts_failures_first(client, db):
    suffix = uuid4().hex
    project = Project(name=f"report-{suffix}", git_path=f"/tmp/report-{suffix}")
    db.add(project)
    await db.flush()
    playbook = Playbook(project_id=project.id, rel_path="playbooks/site.yml", name=f"site-{suffix}")
    inventory = Inventory(name=f"report-inv-{suffix}", rel_path=f"inventories/{suffix}.yml", format=InventoryFormat.yaml)
    db.add_all([playbook, inventory])
    await db.flush()
    job = JobRun(
        playbook_id=playbook.id,
        inventory_id=inventory.id,
        mode=JobMode.live,
        status=JobStatus.successful,
        requested_by=1,
        params_snapshot={},
    )
    db.add(job)
    await db.flush()

    events = [
        {"event": "playbook_on_play_start", "uuid": "play-1", "event_data": {"play_uuid": "play-1", "play": "Deploy"}},
        {"event": "playbook_on_task_start", "uuid": "task-1", "event_data": {"task_uuid": "task-1", "task": "Ping", "task_action": "ping"}},
        {"event": "runner_on_ok", "host": "h1", "event_data": {"task_uuid": "task-1", "host": "h1", "res": {"changed": False}, "duration": 0.1}},
        {"event": "playbook_on_task_start", "uuid": "task-2", "event_data": {"task_uuid": "task-2", "task": "Install", "task_action": "package"}},
        {"event": "runner_on_failed", "host": "h2", "event_data": {"task_uuid": "task-2", "host": "h2", "ignore_errors": False, "res": {}, "duration": 0.2}},
    ]
    builder = ReportBuilder(job.id)
    for counter, event in enumerate(events, start=1):
        builder.process(event, counter)
    await _persist_report(db, builder)
    await db.commit()

    await login(client)
    res = await client.get(f"/api/jobs/{job.id}/report")

    assert res.status_code == 200
    body = res.json()
    assert body["totals"] == {"ok": 1, "changed": 0, "failed": 1, "unreachable": 0, "skipped": 0}
    assert body["hosts"][0]["host"] == "h2"
    assert body["plays"][0]["tasks"][0]["duration_ms"] == 100
