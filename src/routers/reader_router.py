from fastapi import APIRouter, HTTPException

from src.schemas import DatasetReadRequest, DatasetReadResponse
from src.services import DatasetReaderService

reader_router = APIRouter(prefix="/api/datasets", tags=["reader"])
dataset_reader_service = DatasetReaderService()


@reader_router.post("/read", response_model=DatasetReadResponse)
async def read_dataset(request: DatasetReadRequest) -> DatasetReadResponse:
    try:
        return dataset_reader_service.read_dataset(
            path=request.path,
            batch_size=request.batch_size,
            batch_offset=request.batch_offset,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
