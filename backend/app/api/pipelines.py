import anyio
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from git import Repo
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import settings
from app.db.models import JobRun, JobTemplate, Pipeline, PipelineRun, PipelineStatus, PipelineStep, Project, User
from app.db.session import get_db
from app.services.audit import audit
from app.services.content import get_inventory_repo_path, get_project_repo_path
from app.services.rbac_scope import assert_project_perm, visible_project_ids

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])

class PipelineStepIn(BaseModel):
    template_id: int
    requires_approval: bool = False
    continue_on_failure: bool = False

class PipelineCreate(BaseModel):
    project_id: int
    name: str
    description: str | None = None
    steps: list[PipelineStepIn]

class PipelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    steps: list[PipelineStepIn] | None = None

@router.get("")
async def list_pipelines(
    project_id: int | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Pipeline)
    visible_ids = await visible_project_ids(db, user)
    if visible_ids is not None:
        query = query.where(Pipeline.project_id.in_(visible_ids))
    if project_id is not None:
        query = query.where(Pipeline.project_id == project_id)
    pipelines = (await db.execute(query)).scalars().all()
    return [
        {
            "id": p.id,
            "project_id": p.project_id,
            "name": p.name,
            "description": p.description,
            "enabled": p.enabled,
            "created_by": p.created_by,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in pipelines
    ]

@router.post("")
async def create_pipeline(
    req: PipelineCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await assert_project_perm(db, user, req.project_id, "pipeline.write")
    if not req.steps:
        raise HTTPException(status_code=422, detail={"code": "pipeline_empty", "message": "Pipeline steps cannot be empty"})

    tmpl_ids = [s.template_id for s in req.steps]
    tmpls = (await db.execute(select(JobTemplate).where(JobTemplate.id.in_(tmpl_ids)))).scalars().all()
    for t in tmpls:
        if t.project_id != req.project_id:
            raise HTTPException(status_code=422, detail={"code": "template_project_mismatch", "message": "Template does not belong to project"})

    pipeline = Pipeline(
        project_id=req.project_id,
        name=req.name,
        description=req.description,
        enabled=True,
        created_by=user.id,
    )
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)

    for pos, s in enumerate(req.steps):
        step = PipelineStep(
            pipeline_id=pipeline.id,
            position=pos,
            template_id=s.template_id,
            requires_approval=s.requires_approval,
            continue_on_failure=s.continue_on_failure,
        )
        db.add(step)

    await db.commit()
    await audit(db, "pipeline_created", actor_user_id=user.id, object_type="pipeline", object_id=pipeline.id, detail={"project_id": req.project_id})
    return {"id": pipeline.id, "name": pipeline.name}

@router.get("/runs")
async def list_pipeline_runs(
    pipeline_id: int | None = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    limit = min(limit, 200)
    query = select(PipelineRun)
    visible_ids = await visible_project_ids(db, user)
    if visible_ids is not None:
        query = query.join(Pipeline, PipelineRun.pipeline_id == Pipeline.id).where(Pipeline.project_id.in_(visible_ids))
    if pipeline_id is not None:
        query = query.where(PipelineRun.pipeline_id == pipeline_id)
    query = query.order_by(PipelineRun.created_at.desc()).limit(limit)
    runs = (await db.execute(query)).scalars().all()
    return [
        {
            "id": r.id,
            "pipeline_id": r.pipeline_id,
            "status": r.status,
            "requested_by": r.requested_by,
            "current_position": r.current_position,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in runs
    ]

@router.get("/runs/{run_id}")
async def get_pipeline_run(
    run_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    prun = (await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))).scalar_one_or_none()
    if not prun:
        raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "Pipeline run not found"})

    pipeline = (await db.execute(select(Pipeline).where(Pipeline.id == prun.pipeline_id))).scalar_one_or_none()
    if pipeline:
        await assert_project_perm(db, user, pipeline.project_id, "read")

    steps = (await db.execute(
        select(PipelineStep, JobTemplate.name)
        .join(JobTemplate, PipelineStep.template_id == JobTemplate.id)
        .where(PipelineStep.pipeline_id == prun.pipeline_id)
        .order_by(PipelineStep.position.asc())
    )).all()

    child_jobs = (await db.execute(
        select(JobRun).where(JobRun.pipeline_run_id == run_id)
    )).scalars().all()
    job_by_step_id = {j.pipeline_step_id: j for j in child_jobs}

    step_runs = []
    for step, tmpl_name in steps:
        cj = job_by_step_id.get(step.id)
        step_runs.append({
            "position": step.position,
            "template_name": tmpl_name,
            "job_run_id": cj.id if cj else None,
            "status": cj.status.value if cj and hasattr(cj.status, "value") else (str(cj.status) if cj else "pending"),
        })

    return {
        "id": prun.id,
        "pipeline_id": prun.pipeline_id,
        "status": prun.status,
        "requested_by": prun.requested_by,
        "current_position": prun.current_position,
        "created_at": prun.created_at.isoformat() if prun.created_at else None,
        "started_at": prun.started_at.isoformat() if prun.started_at else None,
        "finished_at": prun.finished_at.isoformat() if prun.finished_at else None,
        "steps": step_runs,
    }

@router.post("/runs/{run_id}/cancel")
async def cancel_pipeline_run(
    run_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    prun = (await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))).scalar_one_or_none()
    if not prun:
        raise HTTPException(status_code=404, detail={"code": "run_not_found", "message": "Pipeline run not found"})

    pipeline = (await db.execute(select(Pipeline).where(Pipeline.id == prun.pipeline_id))).scalar_one_or_none()
    if pipeline:
        await assert_project_perm(db, user, pipeline.project_id, "job.cancel")

    redis_client = aioredis.from_url(settings.REDIS_URL)
    await redis_client.set(f"pipeline:{run_id}:cancel", "1")
    await redis_client.aclose()

    # Cancel active child job
    child_job = (await db.execute(
        select(JobRun).where(
            JobRun.pipeline_run_id == run_id,
            JobRun.status.in_(["queued", "running", "pending_approval"])
        )
    )).scalar_one_or_none()

    if child_job:
        redis_client2 = aioredis.from_url(settings.REDIS_URL)
        await redis_client2.set(f"job:{child_job.id}:cancel", "1")
        await redis_client2.aclose()

    prun.status = PipelineStatus.canceled
    await db.commit()
    await audit(db, "pipeline_canceled", actor_user_id=user.id, object_type="pipeline_run", object_id=prun.id)
    return {"status": "ok"}

@router.get("/{pipeline_id}")
async def get_pipeline(
    pipeline_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    pipeline = (await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))).scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=404, detail={"code": "pipeline_not_found", "message": "Pipeline not found"})
    await assert_project_perm(db, user, pipeline.project_id, "read")

    steps = (await db.execute(
        select(PipelineStep, JobTemplate.name)
        .join(JobTemplate, PipelineStep.template_id == JobTemplate.id)
        .where(PipelineStep.pipeline_id == pipeline_id)
        .order_by(PipelineStep.position.asc())
    )).all()

    return {
        "id": pipeline.id,
        "project_id": pipeline.project_id,
        "name": pipeline.name,
        "description": pipeline.description,
        "enabled": pipeline.enabled,
        "created_by": pipeline.created_by,
        "steps": [
            {
                "id": s.id,
                "position": s.position,
                "template_id": s.template_id,
                "template_name": tmpl_name,
                "requires_approval": s.requires_approval,
                "continue_on_failure": s.continue_on_failure,
            }
            for s, tmpl_name in steps
        ],
    }

@router.patch("/{pipeline_id}")
async def update_pipeline(
    pipeline_id: int,
    req: PipelineUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    pipeline = (await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))).scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=404, detail={"code": "pipeline_not_found", "message": "Pipeline not found"})
    await assert_project_perm(db, user, pipeline.project_id, "pipeline.write")

    if req.name is not None:
        pipeline.name = req.name
    if req.description is not None:
        pipeline.description = req.description
    if req.enabled is not None:
        pipeline.enabled = req.enabled

    if req.steps is not None:
        if not req.steps:
            raise HTTPException(status_code=422, detail={"code": "pipeline_empty", "message": "Pipeline steps cannot be empty"})
        tmpl_ids = [s.template_id for s in req.steps]
        tmpls = (await db.execute(select(JobTemplate).where(JobTemplate.id.in_(tmpl_ids)))).scalars().all()
        for t in tmpls:
            if t.project_id != pipeline.project_id:
                raise HTTPException(status_code=422, detail={"code": "template_project_mismatch", "message": "Template does not belong to project"})

        # Delete old steps
        old_steps = (await db.execute(select(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id))).scalars().all()
        for os_step in old_steps:
            await db.delete(os_step)

        # Create new steps
        for pos, s in enumerate(req.steps):
            db.add(PipelineStep(
                pipeline_id=pipeline.id,
                position=pos,
                template_id=s.template_id,
                requires_approval=s.requires_approval,
                continue_on_failure=s.continue_on_failure,
            ))

    await db.commit()
    await audit(db, "pipeline_updated", actor_user_id=user.id, object_type="pipeline", object_id=pipeline.id)
    return {"id": pipeline.id, "name": pipeline.name}

@router.delete("/{pipeline_id}", status_code=204)
async def delete_pipeline(
    pipeline_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    pipeline = (await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))).scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=404, detail={"code": "pipeline_not_found", "message": "Pipeline not found"})
    await assert_project_perm(db, user, pipeline.project_id, "pipeline.write")

    active_run = (await db.execute(
        select(PipelineRun).where(
            PipelineRun.pipeline_id == pipeline_id,
            PipelineRun.status.in_([PipelineStatus.queued, PipelineStatus.running, PipelineStatus.pending_approval])
        )
    )).scalar_one_or_none()
    if active_run:
        raise HTTPException(status_code=409, detail={"code": "pipeline_busy", "message": "Pipeline has active run"})

    await db.delete(pipeline)
    await db.commit()
    await audit(db, "pipeline_deleted", actor_user_id=user.id, object_type="pipeline", object_id=pipeline_id)
    return

@router.post("/{pipeline_id}/run")
async def run_pipeline_endpoint(
    pipeline_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    pipeline = (await db.execute(select(Pipeline).where(Pipeline.id == pipeline_id))).scalar_one_or_none()
    if not pipeline:
        raise HTTPException(status_code=404, detail={"code": "pipeline_not_found", "message": "Pipeline not found"})
    await assert_project_perm(db, user, pipeline.project_id, "job.request")

    active_run = (await db.execute(
        select(PipelineRun).where(
            PipelineRun.pipeline_id == pipeline_id,
            PipelineRun.status.in_([PipelineStatus.queued, PipelineStatus.running, PipelineStatus.pending_approval])
        )
    )).scalar_one_or_none()
    if active_run:
        raise HTTPException(status_code=409, detail={"code": "pipeline_busy", "message": "Pipeline has active run"})

    project = (await db.execute(select(Project).where(Project.id == pipeline.project_id))).scalar_one_or_none()
    repo_path = get_project_repo_path(project.name)
    git_sha = await anyio.to_thread.run_sync(lambda: Repo(repo_path).head.commit.hexsha)
    inventory_repo_path = get_inventory_repo_path()
    inventory_git_sha = await anyio.to_thread.run_sync(lambda: Repo(inventory_repo_path).head.commit.hexsha)

    params_snapshot = {
        "git_sha": git_sha,
        "inventory_git_sha": inventory_git_sha,
    }

    prun = PipelineRun(
        pipeline_id=pipeline.id,
        status=PipelineStatus.queued,
        requested_by=user.id,
        current_position=0,
        params_snapshot=params_snapshot,
    )
    db.add(prun)
    await db.commit()
    await db.refresh(prun)

    from app.tasks.run_pipeline import run_pipeline
    task = run_pipeline.delay(prun.id)
    prun.celery_task_id = task.id
    await db.commit()
    await audit(db, "pipeline_requested", actor_user_id=user.id, object_type="pipeline_run", object_id=prun.id, detail={"pipeline_id": pipeline.id})

    return {"id": prun.id, "status": prun.status}
