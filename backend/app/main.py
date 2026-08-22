from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from app.api import auth, users, credentials, projects, playbooks, inventories, job_templates, jobs, pipelines, content, schedules, audit, notifications

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.seed import seed_roles_and_admin
    from app.db.session import AsyncSessionLocal
    from app.services.content import ensure_inventory_repo
    await seed_roles_and_admin()
    async with AsyncSessionLocal() as db:
        await ensure_inventory_repo(db)
    yield

app = FastAPI(title="Ansible WebGUI API", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(credentials.router)
app.include_router(projects.router)
app.include_router(playbooks.router)
app.include_router(inventories.router)
app.include_router(job_templates.router)
app.include_router(jobs.router)
app.include_router(pipelines.router)
app.include_router(content.router)
app.include_router(schedules.router)
app.include_router(audit.router)
app.include_router(notifications.router)

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return JSONResponse(status_code=exc.status_code, content={"detail": {"code": "error", "message": str(exc.detail)}})
    code = getattr(exc, "code", "internal_error")
    detail = getattr(exc, "detail", str(exc))
    return JSONResponse(
        status_code=getattr(exc, "status_code", 500),
        content={"detail": {"code": code, "message": str(detail)}}
    )

@app.get("/api/health")
async def health():
    return {"status": "ok"}
