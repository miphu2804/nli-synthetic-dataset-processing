from src.schemas.drive_schema import (
    BrowseDriveFilesResponse,
    DriveAuthCompleteResponse,
    DriveAuthStartResponse,
    DriveAuthStatus,
    DriveDownloadResponse,
    DriveFileInfo,
    DriveUploadResponse,
)


class DriveService:
    def __init__(self) -> None:
        self._authenticated = False
        self._user_email: str | None = None
        self._pending_auth = False
        self._complete_call_count = 0

    def get_auth_status(self) -> DriveAuthStatus:
        return DriveAuthStatus(
            authenticated=self._authenticated,
            user_email=self._user_email,
        )

    def start_auth(self) -> DriveAuthStartResponse:
        self._pending_auth = True
        self._complete_call_count = 0
        return DriveAuthStartResponse(
            user_code="ABCD-1234",
            verification_url="https://www.google.com/device",
            expires_in=900,
        )

    def complete_auth(self) -> DriveAuthCompleteResponse:
        self._complete_call_count += 1
        if self._complete_call_count >= 2:
            self._authenticated = True
            self._user_email = "demo@stub.local"
            self._pending_auth = False
            return DriveAuthCompleteResponse(
                authenticated=True,
                user_email="demo@stub.local",
            )
        return DriveAuthCompleteResponse(
            authenticated=False,
            status="pending",
        )

    def browse_folder(
        self, folder_id: str = "root", page_token: str | None = None
    ) -> BrowseDriveFilesResponse:
        subfolders = [
            DriveFileInfo(
                file_id="folder-001",
                name="Datasets",
                mime_type="application/vnd.google-apps.folder",
            ),
            DriveFileInfo(
                file_id="folder-002",
                name="Exports",
                mime_type="application/vnd.google-apps.folder",
            ),
        ]
        files = [
            DriveFileInfo(
                file_id="file-001",
                name="nli_train.csv",
                mime_type="text/csv",
                size_bytes=1024000,
            ),
            DriveFileInfo(
                file_id="file-002",
                name="nli_dev.parquet",
                mime_type="application/octet-stream",
                size_bytes=512000,
            ),
        ]
        folder_name = "My Drive" if folder_id == "root" else folder_id
        return BrowseDriveFilesResponse(
            folder_id=folder_id,
            folder_name=folder_name,
            files=files,
            subfolders=subfolders,
        )

    def download_file(
        self, file_id: str, destination_path: str
    ) -> DriveDownloadResponse:
        return DriveDownloadResponse(
            drive_file_id=file_id,
            local_path=f"{destination_path.rstrip('/')}/{file_id}.csv",
            file_name=f"{file_id}.csv",
            mime_type="text/csv",
            size_bytes=1024000,
        )

    def upload_file(
        self,
        local_path: str,
        folder_id: str | None = None,
        file_name: str | None = None,
    ) -> DriveUploadResponse:
        name = file_name or local_path.rsplit("/", 1)[-1]
        return DriveUploadResponse(
            drive_file_id="uploaded-file-001",
            web_view_link=f"https://drive.google.com/file/d/uploaded-file-001/view",
            file_name=name,
        )
