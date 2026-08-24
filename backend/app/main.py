from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api import (
    audit,
    auth,
    content,
    credentials,
    inventories,
    job_templates,
    jobs,
    notifications,
    pipelines,
    playbooks,
    projects,
    schedules,
    users,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.db.seed import seed_roles_and_admin
    from app.db.session import AsyncSessionLocal, init_db
    from app.services.content import ensure_inventory_repo
    await init_db()
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
async def generic_exception_handler(_request: Request, exc: Exception):
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


_static_root = Path(settings.STATIC_ROOT)
_index_file = _static_root / "index.html"

if _static_root.is_dir():
    app.mount("/assets", StaticFiles(directory=_static_root / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Not Found"})
        candidate = (_static_root / full_path).resolve()
        if full_path and candidate.is_file() and _static_root.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_index_file, headers={"Cache-Control": "no-store, must-revalidate"})
