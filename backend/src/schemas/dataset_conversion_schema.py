from typing import Literal

from pydantic import BaseModel, Field


class DatasetConversionRequest(BaseModel):
    input_path: str = Field(description="Path to a local tabular dataset file.")
    output_path: str | None = Field(
        default=None,
        description="Optional CSV output path. Defaults next to the input file.",
    )
    sheet_name: str | int | None = Field(
        default=None,
        description="Optional Excel sheet name or index. Defaults to the first sheet.",
    )
    sep: str | None = Field(
        default=None,
        description="Optional separator override for CSV or TSV input.",
    )


class DatasetConversionResponse(BaseModel):
    status: Literal["converted"]
    input_path: str
    input_format: str
    output_path: str
    output_format: Literal["csv"] = "csv"
    rows_written: int
    column_count: int
    columns: list[str]
