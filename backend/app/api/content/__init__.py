from fastapi import APIRouter

from app.api.content import files, history, roles

router = APIRouter(prefix="/api/content", tags=["content"])
router.include_router(files.router)
router.include_router(history.router)
router.include_router(roles.router)

__all__ = ["router"]
