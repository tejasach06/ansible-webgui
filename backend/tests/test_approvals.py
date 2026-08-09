import pytest
from app.services.approvals import freeze_params_snapshot, approve_job_run
from app.db.models import JobRun, JobStatus, Project, Playbook, Inventory, InventoryFormat

@pytest.mark.asyncio(loop_scope="session")
async def test_self_approval_forbidden(db):
    project = Project(name="test-project", git_path="/tmp/test-repo")
    db.add(project)
    await db.flush()
    playbook = Playbook(project_id=project.id, rel_path="site.yml", name="site.yml")
    inventory = Inventory(name="hosts", rel_path="hosts.yml", format=InventoryFormat.yaml)
    db.add_all([playbook, inventory])
    await db.flush()

    job = JobRun(
        playbook_id=playbook.id,
        inventory_id=inventory.id,
        mode="live",
        status=JobStatus.pending_approval,
        requested_by=1,
        params_snapshot={}
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    with pytest.raises(ValueError, match="self_approval_forbidden"):
        await approve_job_run(db, job, approver_id=1)
