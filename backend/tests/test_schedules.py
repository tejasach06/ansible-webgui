from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_content_api import login

from app.core.config import settings
from app.db.models import Inventory, InventoryFormat, JobRun, JobStatus, JobTemplate, Playbook, Project, Schedule
from app.services.content import ensure_inventory_repo, get_project_repo_path, init_project_repo
from app.tasks.run_scheduled import run_scheduled
from app.tasks.worker import celery_app

MUTATE = {"X-Requested-With": "XMLHttpRequest"}


@pytest.mark.asyncio(loop_scope="session")
async def test_schedules_task_registered_and_executes(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))
    await ensure_inventory_repo(db)
    await login(client)

    assert "run_scheduled" in celery_app.tasks

    # Create project, playbook, inventory, template
    p_name = f"sched-proj-{uuid4().hex[:8]}"
    project = Project(name=p_name, git_path=str(tmp_path / p_name), default_branch="main")
    db.add(project)
    await db.commit()
    await init_project_repo(db, project, "admin", "admin@example.com")

    playbook_file = get_project_repo_path(project.name) / "playbooks" / "ping.yml"
    playbook_file.parent.mkdir(parents=True, exist_ok=True)
    playbook_file.write_text("- hosts: all\n  tasks: []\n")
    playbook = Playbook(project_id=project.id, rel_path="playbooks/ping.yml", name="ping")

    inventory = Inventory(rel_path="inventories/hosts.ini", name="hosts-ini", format=InventoryFormat.ini)
    db.add_all([playbook, inventory])
    await db.commit()

    template = JobTemplate(
        project_id=project.id,
        name=f"tmpl-{uuid4().hex[:8]}",
        playbook_id=playbook.id,
        inventory_id=inventory.id,
    )
    db.add(template)
    await db.commit()

    # Create schedule via API
    sched_res = await client.post(
        "/api/schedules",
        json={
            "template_id": template.id,
            "name": f"nightly-{uuid4().hex[:8]}",
            "cron_expr": "0 2 * * *",
            "timezone": "UTC",
        },
        headers=MUTATE,
    )
    assert sched_res.status_code == 200
    sched_id = sched_res.json()["id"]

    mock_delay = MagicMock()
    monkeypatch.setattr("app.tasks.run_scheduled.run_job.delay", mock_delay)

    # Run the scheduled task synchronously
    run_scheduled(sched_id)

    assert mock_delay.called

    # Verify JobRun was created and schedule updated
    job = (await db.execute(select(JobRun).where(JobRun.template_id == template.id))).scalar_one_or_none()
    assert job is not None
    assert job.status == JobStatus.queued
    assert job.mode == "live"
    assert job.inventory_id == inventory.id

    sched = (await db.execute(select(Schedule).where(Schedule.id == sched_id))).scalar_one()
    assert sched.last_job_run_id == job.id
    assert sched.next_run_at is not None
