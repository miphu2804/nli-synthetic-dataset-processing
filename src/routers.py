import httpx
from fastapi import APIRouter, HTTPException

from src.dataset_reader_schema import DatasetReadRequest, DatasetReadResponse
from src.dataset_reader_service import DatasetReaderService
from src.dataset_translate_schema import (
    DatasetTranslateRequest,
    DatasetTranslateResponse,
)
from src.openai_translation_service import OpenAITranslationService

router = APIRouter(prefix="/api/datasets", tags=["datasets"])
dataset_reader_service = DatasetReaderService()
translation_service = OpenAITranslationService()


@router.post("/read", response_model=DatasetReadResponse)
async def read_dataset(request: DatasetReadRequest) -> DatasetReadResponse:
    try:
        return dataset_reader_service.read_dataset(
            path=request.path,
            limit=request.limit,
            sample_rows=request.sample_rows,
            sheet_name=request.sheet_name,
            sep=request.sep,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/translate", response_model=DatasetTranslateResponse)
async def translate_dataset(request: DatasetTranslateRequest) -> DatasetTranslateResponse:
    try:
        return await translation_service.translate_dataset(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI request failed: {exc}") from exc
