from pydantic import BaseModel, Field


class DatasetTranslateRequest(BaseModel):
    path: str = Field(description="Absolute or relative path to the input dataset.")
    output_path: str | None = Field(
        default=None,
        description="Optional output CSV path. Defaults to <input>.translated.vi.csv",
    )
    text_columns: list[str] = Field(
        default_factory=lambda: ["premise", "hypothesis"],
        description="Dataset columns to translate into Vietnamese.",
    )
    target_language: str = Field(default="Vietnamese")
    batch_size: int = Field(default=10, ge=1, le=100)
    model: str | None = Field(default=None)
    limit_rows: int | None = Field(
        default=None,
        ge=1,
        description="Optional limit for testing on a subset of rows.",
    )


class DatasetTranslateResponse(BaseModel):
    input_path: str
    output_path: str
    rows_processed: int
    translated_columns: list[str]
    model: str
