from typing import Any

from pydantic import BaseModel, Field


class DatasetReadRequest(BaseModel):
    path: str = Field(description="Absolute or relative path to a local dataset file.")
    limit: int = Field(default=5, ge=1, le=100)
    sample_rows: int = Field(default=1000, ge=1, le=10000)
    sheet_name: str | int | None = Field(
        default=None,
        description="Optional Excel sheet name or index.",
    )
    sep: str | None = Field(
        default=None,
        description="Optional separator override for delimited text files.",
    )


class DatasetReadResponse(BaseModel):
    path: str
    format: str
    row_count: int
    column_count: int
    columns: list[str]
    dtypes: dict[str, str]
    null_counts: dict[str, int]
    preview: list[dict[str, Any]]
