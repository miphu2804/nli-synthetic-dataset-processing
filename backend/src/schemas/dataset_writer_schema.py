from typing import Any, Literal

from pydantic import BaseModel, Field


class DatasetOutputConfig(BaseModel):
    format: Literal["csv"] = "csv"
    path: str | None = Field(
        default=None,
        description="Full output file path (e.g., data/output.csv), not a directory.",
    )
    file_name: str | None = Field(
        default=None,
        description="Optional file name. Ignored if path is a full file path.",
    )


class DatasetWriteRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    output: DatasetOutputConfig = Field(default_factory=DatasetOutputConfig)


class DatasetWriteResponse(BaseModel):
    status: Literal["written"]
    output_format: Literal["csv"] = "csv"
    output_path: str
    rows_written: int
    message: str | None = None
