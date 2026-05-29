import httpx
from fastapi import APIRouter, HTTPException

from src.schemas import (
    DatasetReadRequest,
    DatasetReadResponse,
    DatasetTranslateRequest,
    DatasetTranslateResponse,
    DatasetWriteRequest,
    DatasetWriteResponse,
)
from src.services import (
    DatasetReaderService,
    DatasetWriterService,
    OpenAITranslationService,
)

router = APIRouter(prefix="/api/datasets", tags=["datasets"])
dataset_reader_service = DatasetReaderService()
translation_service = OpenAITranslationService()
dataset_writer_service = DatasetWriterService()


@router.post("/read", response_model=DatasetReadResponse)
async def read_dataset(request: DatasetReadRequest) -> DatasetReadResponse:
    try:
        return dataset_reader_service.read_dataset(
            path=request.path,
            batch_size=request.batch_size,
            batch_offset=request.batch_offset,
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


@router.post("/write", response_model=DatasetWriteResponse)
async def write_dataset(request: DatasetWriteRequest) -> DatasetWriteResponse:
    try:
        return dataset_writer_service.write_dataset(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
