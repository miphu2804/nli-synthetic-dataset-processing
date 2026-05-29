from typing import Any, Literal

from pydantic import BaseModel, Field

from src.schemas.dataset_translate_schema import DatasetOutputConfig


class DatasetWriteRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    output: DatasetOutputConfig = Field(default_factory=DatasetOutputConfig)


class DatasetWriteResponse(BaseModel):
    status: Literal["written"]
    output_format: Literal["csv"] = "csv"
    output_path: str
    rows_written: int
    message: str | None = None
