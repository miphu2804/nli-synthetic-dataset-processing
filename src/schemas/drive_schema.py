from pydantic import BaseModel


class DriveAuthStatus(BaseModel):
    authenticated: bool = False
    user_email: str | None = None
    stub: bool = True


class DriveAuthStartResponse(BaseModel):
    user_code: str
    verification_url: str
    expires_in: int
    status: str = "pending"
    stub: bool = True


class DriveAuthCompleteResponse(BaseModel):
    authenticated: bool
    user_email: str | None = None
    status: str = "done"
    stub: bool = True


class DriveFileInfo(BaseModel):
    file_id: str
    name: str
    mime_type: str
    size_bytes: int | None = None


class BrowseDriveFilesResponse(BaseModel):
    folder_id: str
    folder_name: str
    files: list[DriveFileInfo]
    subfolders: list[DriveFileInfo]
    next_page_token: str | None = None
    stub: bool = True


class DriveDownloadRequest(BaseModel):
    file_id: str
    destination_path: str = "data/original/"


class DriveUploadRequest(BaseModel):
    local_path: str
    folder_id: str | None = None
    file_name: str | None = None


class DriveDownloadResponse(BaseModel):
    drive_file_id: str
    local_path: str
    file_name: str
    mime_type: str
    size_bytes: int | None = None
    stub: bool = True


class DriveUploadResponse(BaseModel):
    drive_file_id: str
    web_view_link: str
    file_name: str
    stub: bool = True
