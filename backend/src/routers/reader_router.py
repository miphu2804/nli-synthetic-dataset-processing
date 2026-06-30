from pathlib import Path

from fastapi import APIRouter, HTTPException

from src.schemas import (
    DatasetConversionRequest,
    DatasetConversionResponse,
    DatasetListResponse,
    DatasetReadRequest,
    DatasetReadResponse,
)
from src.schemas.dataset_reader_schema import FileInfo
from src.services import DataProcessingService
from src.utils.project_paths import resolve_data_path

reader_router = APIRouter(prefix="/api/datasets", tags=["reader"])
data_processing_service = DataProcessingService()

SUPPORTED_EXTENSIONS = {".csv", ".parquet"}


def _list_files_in_dir(directory: Path, kind: str) -> list[FileInfo]:
    if not directory.exists() or not directory.is_dir():
        return []
    results: list[FileInfo] = []
    for entry in sorted(directory.iterdir()):
        if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTENSIONS:
            file_kind = entry.suffix.lstrip(".").lower()
            results.append(
                FileInfo(
                    path=str(entry.resolve()),
                    name=entry.name,
                    size_bytes=entry.stat().st_size,
                    kind=file_kind if file_kind in ("csv", "parquet") else "csv",
                )
            )
    return results


@reader_router.get("/list", response_model=DatasetListResponse)
async def list_datasets() -> DatasetListResponse:
    inputs: list[FileInfo] = []
    inputs.extend(_list_files_in_dir(resolve_data_path("original"), "input"))
    inputs.extend(_list_files_in_dir(resolve_data_path("processed"), "input"))

    outputs: list[FileInfo] = []
    outputs.extend(_list_files_in_dir(resolve_data_path("generated"), "output"))
    outputs.extend(_list_files_in_dir(resolve_data_path("validated"), "output"))

    return DatasetListResponse(inputs=inputs, outputs=outputs)


@reader_router.post("/read", response_model=DatasetReadResponse)
async def read_dataset(request: DatasetReadRequest) -> DatasetReadResponse:
    try:
        return data_processing_service.read_dataset(
            path=request.path,
            batch_size=request.batch_size,
            batch_offset=request.batch_offset,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@reader_router.post("/convert-to-csv", response_model=DatasetConversionResponse)
async def convert_to_csv(
    request: DatasetConversionRequest,
) -> DatasetConversionResponse:
    try:
        return data_processing_service.convert_to_csv(
            input_path=request.input_path,
            output_path=request.output_path,
            sheet_name=request.sheet_name,
            sep=request.sep,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
