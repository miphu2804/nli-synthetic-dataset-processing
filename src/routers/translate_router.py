import httpx
from fastapi import APIRouter, HTTPException

from src.schemas import DatasetTranslateRequest, DatasetTranslateResponse
from src.services import TranslationService

translate_router = APIRouter(prefix="/api/datasets", tags=["translate"])
translation_service = TranslationService()


@translate_router.post("/translate", response_model=DatasetTranslateResponse)
async def translate_dataset(
    request: DatasetTranslateRequest,
) -> DatasetTranslateResponse:
    try:
        return await translation_service.translate_dataset(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"Translation request failed: {exc}"
        ) from exc
