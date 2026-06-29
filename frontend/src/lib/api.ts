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
