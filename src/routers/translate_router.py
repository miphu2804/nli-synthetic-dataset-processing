import httpx
from fastapi import APIRouter, HTTPException

from src.schemas import (
    DatasetTranslateRequest,
    DatasetTranslateResponse,
    DatasetWriteRequest,
    DatasetWriteResponse,
)
from src.services import DatasetWriterService, OpenAITranslationService

translate_router = APIRouter()
translation_service = OpenAITranslationService()
dataset_writer_service = DatasetWriterService()


@translate_router.post("/translate", response_model=DatasetTranslateResponse)
async def translate_dataset(request: DatasetTranslateRequest) -> DatasetTranslateResponse:
    try:
        return await translation_service.translate_dataset(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI request failed: {exc}") from exc


@translate_router.post("/write", response_model=DatasetWriteResponse)
async def write_dataset(request: DatasetWriteRequest) -> DatasetWriteResponse:
    try:
        return dataset_writer_service.write_dataset(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
