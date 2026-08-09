from fastapi import APIRouter

from app.api.jobs import lifecycle, queries, stream

router = APIRouter()
router.include_router(stream.router, prefix="/api/jobs", tags=["jobs"])
router.include_router(lifecycle.router, prefix="/api/jobs", tags=["jobs"])
router.include_router(queries.router, prefix="/api/jobs", tags=["jobs"])

__all__ = ["router"]
