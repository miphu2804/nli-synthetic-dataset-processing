from fastapi import APIRouter, HTTPException

from src.schemas import DatasetWriteRequest, DatasetWriteResponse
from src.services import DatasetWriterService

writer_router = APIRouter(prefix="/api/datasets", tags=["writer"])
dataset_writer_service = DatasetWriterService()


@writer_router.post("/write", response_model=DatasetWriteResponse)
async def write_dataset(request: DatasetWriteRequest) -> DatasetWriteResponse:
    try:
        return dataset_writer_service.write_dataset(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
