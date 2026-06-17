from typing import Any, Literal

from pydantic import BaseModel, Field
from src.schemas.generation_runtime_schema import RunProgressSnapshot


class MaskedValidationRow(BaseModel):
    source_uid: str | int = Field(description="Original generated row identifier.")
    premise: str
    hypothesis: str
    masked_label: Literal["[MASK]"] = "[MASK]"


class ValidatorVerdict(BaseModel):
    source_uid: str | int = Field(description="Original generated row identifier.")
    predicted_label: str | int
    reason: str = Field(
        min_length=1,
        description="Explanation for why the validator assigned predicted_label.",
    )


class ValidationRunManifest(BaseModel):
    run_id: str
    input_path: str
    output_dir: str
    uid_column: str
    row_offset: int = Field(default=0, ge=0)
    batch_size: int = Field(ge=1)
    row_limit: int | None = Field(default=None, ge=1)
    total_source_rows: int = Field(ge=0)
    total_target_rows: int = Field(ge=0)
    columns: list[str] = Field(default_factory=list)
    created_at: str


class ClaimedValidationBatch(BaseModel):
    batch_id: str
    agent: str
    rows: list[MaskedValidationRow] = Field(default_factory=list)


class StartValidationRunResponse(BaseModel):
    status: Literal["started"]
    run_id: str
    input_path: str
    output_dir: str
    uid_column: str
    row_offset: int
    batch_size: int
    row_limit: int | None = None
    total_source_rows: int
    total_target_rows: int
    progress: RunProgressSnapshot


class ClaimNextValidationBatchResponse(BaseModel):
    status: Literal["claimed", "waiting", "complete"]
    run_id: str
    batch: ClaimedValidationBatch | None = None
    progress: RunProgressSnapshot


class SubmitValidationResultResponse(BaseModel):
    status: Literal["committed"]
    run_id: str
    batch_id: str
    rows_validated: int
    accepted_count: int
    rejected_count: int
    output_path: str
    progress: RunProgressSnapshot


class FinalizeValidationRunResponse(BaseModel):
    status: Literal["finalized"]
    run_id: str
    output_path: str
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    state_cleaned: bool
    progress: RunProgressSnapshot


class ReleaseValidationBatchClaimResponse(BaseModel):
    status: Literal["released"]
    run_id: str
    batch_id: str
    progress: RunProgressSnapshot


class ValidationRunListItem(BaseModel):
    run_id: str
    input_path: str
    output_dir: str
    created_at: str


class ListValidationRunsResponse(BaseModel):
    runs: list[ValidationRunListItem] = Field(default_factory=list)


class ValidationProgressVerificationResponse(BaseModel):
    ok: bool
    run_id: str
    checked_agents: list[str] = Field(default_factory=list)
    broken_hashes: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_done_source_uids: list[str | int] = Field(default_factory=list)
    done_skip_overlap_source_uids: list[str | int] = Field(default_factory=list)
    missing_batch_files: list[str] = Field(default_factory=list)
    count_mismatches: list[str] = Field(default_factory=list)
    active_claims: list[str] = Field(default_factory=list)
