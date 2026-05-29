from typing import Any, Literal

from pydantic import BaseModel, Field


class DatasetOutputConfig(BaseModel):
    format: Literal["csv"] = "csv"
    path: str | None = Field(
        default=None,
        description="Output path for CSV writing.",
    )
    file_name: str | None = Field(
        default=None,
        description="Optional target file name.",
    )


class DatasetTranslateRequest(BaseModel):
    path: str = Field(description="Absolute or relative path to the input dataset.")
    text_columns: list[str] = Field(
        default_factory=lambda: ["premise", "hypothesis"],
        description="Dataset columns to translate into Vietnamese.",
    )
    target_language: str = Field(default="Vietnamese")
    batch_size: int = Field(default=10, ge=1, le=100)
    model: str | None = Field(default=None)
    output: DatasetOutputConfig = Field(default_factory=DatasetOutputConfig)
    limit_rows: int | None = Field(
        default=None,
        ge=1,
        description="Optional limit for testing on a subset of rows.",
    )
    pass_through: bool = Field(
        default=False,
        description="Skip API call, return rows as-is for MCP/web manual translation.",
    )


class DatasetTranslateResponse(BaseModel):
    status: Literal["completed", "pass_through"]
    input_path: str
    output_format: Literal["csv"] = "csv"
    output_path: str | None = None
    rows_processed: int
    translated_columns: list[str]
    model: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    message: str | None = None
