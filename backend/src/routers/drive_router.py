from fastapi import APIRouter
from src.schemas.drive_schema import (
    BrowseDriveFilesResponse,
    DriveAuthCompleteResponse,
    DriveAuthStartResponse,
    DriveAuthStatus,
    DriveDownloadRequest,
    DriveDownloadResponse,
    DriveUploadRequest,
    DriveUploadResponse,
)
from src.services.drive_service import DriveService

drive_router = APIRouter(prefix="/api/drive", tags=["drive"])
drive_service = DriveService()


@drive_router.get("/auth/status", response_model=DriveAuthStatus)
async def auth_status() -> DriveAuthStatus:
    return drive_service.get_auth_status()


@drive_router.post("/auth/start", response_model=DriveAuthStartResponse)
async def auth_start() -> DriveAuthStartResponse:
    return drive_service.start_auth()


@drive_router.post("/auth/complete", response_model=DriveAuthCompleteResponse)
async def auth_complete() -> DriveAuthCompleteResponse:
    return drive_service.complete_auth()


@drive_router.get("/files", response_model=BrowseDriveFilesResponse)
async def browse_files(
    folder_id: str = "root", page_token: str = ""
) -> BrowseDriveFilesResponse:
    token = page_token if page_token else None
    return drive_service.browse_folder(folder_id=folder_id, page_token=token)


@drive_router.post("/download", response_model=DriveDownloadResponse)
async def download_file(request: DriveDownloadRequest) -> DriveDownloadResponse:
    return drive_service.download_file(
        file_id=request.file_id,
        destination_path=request.destination_path,
    )


@drive_router.post("/upload", response_model=DriveUploadResponse)
async def upload_file(request: DriveUploadRequest) -> DriveUploadResponse:
    return drive_service.upload_file(
        local_path=request.local_path,
        folder_id=request.folder_id,
        file_name=request.file_name,
    )
