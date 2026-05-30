from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.dataset_writer_schema import DatasetOutputConfig


class DatasetGenerateRequest(BaseModel):
    path: str = Field(description="Path to input CSV/parquet with premise column.")
    premise_column: str = Field(default="premise")
    uid_column: str = Field(default="uid")
    batch_size: int = Field(default=100, ge=1, le=500)
    model: str | None = Field(default=None)
    output: DatasetOutputConfig = Field(default_factory=DatasetOutputConfig)
    append: bool = Field(
        default=True,
        description="Append to existing output file. False = overwrite.",
    )


class LabelDistribution(BaseModel):
    entailment: int = 0
    contradiction: int = 0
    neutral: int = 0


class TierDistribution(BaseModel):
    surface: int = 0
    structural: int = 0
    deep_semantic: int = 0


class GenerateProgress(BaseModel):
    batches_completed: int = 0
    total_batches: int = 0
    rows_written: int = 0
    skipped_premises: int = 0


class DatasetGenerateResponse(BaseModel):
    status: Literal["completed", "partial", "error"]
    output_path: str
    total_premises: int
    total_hypotheses: int
    label_distribution: LabelDistribution = Field(default_factory=LabelDistribution)
    tier_distribution: TierDistribution = Field(default_factory=TierDistribution)
    progress: GenerateProgress = Field(default_factory=GenerateProgress)
    message: str | None = None
