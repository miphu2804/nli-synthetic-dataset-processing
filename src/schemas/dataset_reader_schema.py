from typing import Any

from pydantic import BaseModel, Field


class DatasetReadRequest(BaseModel):
    path: str = Field(description="Absolute or relative path to a local dataset file.")
    batch_size: int = Field(default=5, ge=1, le=1000)
    batch_offset: int = Field(default=0, ge=0)
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
    batch_size: int
    batch_offset: int
    rows: list[dict[str, Any]]
