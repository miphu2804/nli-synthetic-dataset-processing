const BASE = import.meta.env.VITE_API_ENDPOINT || "http://localhost:8000";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// Types

export interface HealthResponse {
  status: string;
}

export interface McpToolInfo {
  name: string;
  description: string;
}

export interface McpStatusResponse {
  server_name: string;
  connected: boolean;
  tool_count: number;
  tools: McpToolInfo[];
}

export interface FileInfo {
  path: string;
  name: string;
  size_bytes: number;
  rows: number | null;
  kind: string;
}

export interface DatasetListResponse {
  inputs: FileInfo[];
  outputs: FileInfo[];
}

export interface DatasetReadResponse {
  path: string;
  format: string;
  row_count: number;
  column_count: number;
  columns: string[];
  dtypes: Record<string, string>;
  null_counts: Record<string, number>;
  rows: Record<string, unknown>[];
}

export interface DriveAuthStatus {
  authenticated: boolean;
  user_email: string | null;
  stub: boolean;
}

export interface DriveAuthStartResponse {
  user_code: string;
  verification_url: string;
  expires_in: number;
  status: string;
  stub: boolean;
}

export interface DriveAuthCompleteResponse {
  authenticated: boolean;
  user_email: string | null;
  status: string;
  stub: boolean;
}

export interface DriveFileInfo {
  file_id: string;
  name: string;
  mime_type: string;
  size_bytes: number | null;
}

export interface BrowseDriveFilesResponse {
  folder_id: string;
  folder_name: string;
  files: DriveFileInfo[];
  subfolders: DriveFileInfo[];
  next_page_token: string | null;
  stub: boolean;
}

export interface DriveDownloadResponse {
  drive_file_id: string;
  local_path: string;
  file_name: string;
  mime_type: string;
  size_bytes: number | null;
  stub: boolean;
}

export interface DriveUploadResponse {
  drive_file_id: string;
  web_view_link: string;
  file_name: string;
  stub: boolean;
}

// API functions

export function getHealth() {
  return request<HealthResponse>("/health");
}

export function getMcpStatus() {
  return request<McpStatusResponse>("/api/mcp/status");
}

export function listDatasets() {
  return request<DatasetListResponse>("/api/datasets/list");
}

export function readDataset(
  path: string,
  batch_size = 20,
  batch_offset = 0
) {
  return request<DatasetReadResponse>("/api/datasets/read", {
    method: "POST",
    body: JSON.stringify({ path, batch_size, batch_offset }),
  });
}

export function listSkills() {
  return request<string[]>("/api/skills/");
}

export function getSkill(name: string) {
  return request<{ name: string; content: string }>(`/api/skills/${name}`);
}

// Drive stubs
export function driveAuthStatus() {
  return request<DriveAuthStatus>("/api/drive/auth/status");
}

export function driveAuthStart() {
  return request<DriveAuthStartResponse>("/api/drive/auth/start", {
    method: "POST",
  });
}

export function driveAuthComplete() {
  return request<DriveAuthCompleteResponse>("/api/drive/auth/complete", {
    method: "POST",
  });
}

export function browseDriveFiles(folderId = "root", pageToken = "") {
  const params = new URLSearchParams({ folder_id: folderId, page_token: pageToken });
  return request<BrowseDriveFilesResponse>(`/api/drive/files?${params}`);
}

export function driveDownload(fileId: string, destinationPath = "data/original/") {
  return request<DriveDownloadResponse>("/api/drive/download", {
    method: "POST",
    body: JSON.stringify({ file_id: fileId, destination_path: destinationPath }),
  });
}

export function driveUpload(localPath: string, folderId?: string, fileName?: string) {
  return request<DriveUploadResponse>("/api/drive/upload", {
    method: "POST",
    body: JSON.stringify({
      local_path: localPath,
      folder_id: folderId || undefined,
      file_name: fileName || undefined,
    }),
  });
}
