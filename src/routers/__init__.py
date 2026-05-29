from fastapi import APIRouter

from src.routers.reader_router import reader_router
from src.routers.translate_router import translate_router

router = APIRouter(prefix="/api/datasets", tags=["datasets"])
router.include_router(reader_router)
router.include_router(translate_router)
