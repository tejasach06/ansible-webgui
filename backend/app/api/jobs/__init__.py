from fastapi import APIRouter

from app.api.jobs import lifecycle, queries, stream

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
router.include_router(stream.router)
router.include_router(lifecycle.router)
router.include_router(queries.router)

__all__ = ["router"]
