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
    path: str = Field(description="Resolved absolute path to the dataset file.")
    format: str = Field(description="File format (csv, parquet, etc.).")
    row_count: int = Field(description="Total number of data rows in the dataset.")
    column_count: int = Field(description="Number of columns in the dataset.")
    columns: list[str] = Field(description="Column names.")
    dtypes: dict[str, str] = Field(description="Column name to pandas dtype mapping.")
    null_counts: dict[str, int] = Field(description="Number of null values per column.")
    rows: list[dict[str, Any]] = Field(
        description="Batch of data rows as key-value pairs."
    )
