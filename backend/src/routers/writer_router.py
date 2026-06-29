from fastapi import APIRouter, HTTPException
from src.schemas import DatasetWriteRequest, DatasetWriteResponse
from src.services import DataProcessingService

writer_router = APIRouter(prefix="/api/datasets", tags=["writer"])
data_processing_service = DataProcessingService()


@writer_router.post("/write", response_model=DatasetWriteResponse)
async def write_dataset(request: DatasetWriteRequest) -> DatasetWriteResponse:
    try:
        return data_processing_service.write_dataset(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
