import pytest
from app.db.models import Pipeline, PipelineStep, PipelineRun, PipelineStatus, JobRun, JobStatus, JobTemplate, Playbook, Inventory, Project, User, Role

@pytest.mark.asyncio(loop_scope="session")
async def test_pipeline_approval_flow(db, client):
    # Setup test project and template
    project = Project(name="pipe-proj", git_path="/data/content/pipe-proj", default_branch="main")
    db.add(project)
    await db.commit()

    playbook = Playbook(project_id=project.id, rel_path="playbooks/site.yml", name="site")
    inventory = Inventory(rel_path="inventories/hosts-pipe.ini", name="hosts-pipe", format="ini")
    db.add_all([playbook, inventory])
    await db.commit()

    template1 = JobTemplate(project_id=project.id, name="t1", playbook_id=playbook.id, inventory_id=inventory.id, requires_approval=True)
    template2 = JobTemplate(project_id=project.id, name="t2", playbook_id=playbook.id, inventory_id=inventory.id, requires_approval=False)
    db.add_all([template1, template2])
    await db.commit()

    pipeline = Pipeline(project_id=project.id, name="pipe1", created_by=1)
    db.add(pipeline)
    await db.commit()

    step1 = PipelineStep(pipeline_id=pipeline.id, position=0, template_id=template1.id, requires_approval=True)
    step2 = PipelineStep(pipeline_id=pipeline.id, position=1, template_id=template2.id, requires_approval=False)
    db.add_all([step1, step2])
    await db.commit()

    # Create user 1 (requester)
    req_user = User(username="pipe_user1", email="pu1@local", password_hash="hash", is_active=True)
    approver = User(username="pipe_user2", email="pu2@local", password_hash="hash", is_active=True)
    db.add_all([req_user, approver])
    await db.commit()

    prun = PipelineRun(pipeline_id=pipeline.id, status=PipelineStatus.queued, requested_by=req_user.id, params_snapshot={"git_sha": "abc", "inventory_git_sha": "def"})
    db.add(prun)
    await db.commit()

    # Assert pending approval state for step 1
    child1 = JobRun(template_id=template1.id, playbook_id=playbook.id, inventory_id=inventory.id, mode="live", status=JobStatus.pending_approval, requested_by=req_user.id, params_snapshot={"git_sha": "abc"}, pipeline_run_id=prun.id, pipeline_step_id=step1.id)
    db.add(child1)
    prun.status = PipelineStatus.running
    await db.commit()

    assert prun.status == PipelineStatus.running
    assert child1.status == JobStatus.pending_approval

    # Self-approval forbidden check
    from app.services.approvals import approve_job_run
    with pytest.raises(ValueError, match="self_approval_forbidden"):
        await approve_job_run(db, child1, req_user.id, "self approve")

    # Approval by user 2 succeeds
    approved_child = await approve_job_run(db, child1, approver.id, "approved")
    assert approved_child.status == JobStatus.queued
    assert approved_child.approved_by == approver.id
