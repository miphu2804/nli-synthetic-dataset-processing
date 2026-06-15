from typing import Any, Literal

from pydantic import BaseModel, Field


class GeneratedRow(BaseModel):
    source_uid: str | int = Field(description="Original source row identifier.")
    premise: str
    hypothesis: str
    label: str | int


class SkippedRow(BaseModel):
    source_uid: str | int = Field(description="Original source row identifier.")
    reason: str
    retries: int = Field(default=0, ge=0)


class GenerationRunManifest(BaseModel):
    run_id: str
    input_path: str
    output_path: str
    uid_column: str
    row_offset: int = Field(default=0, ge=0)
    batch_size: int = Field(ge=1)
    row_limit: int | None = Field(default=None, ge=1)
    total_source_rows: int = Field(ge=0)
    total_target_rows: int = Field(ge=0)
    columns: list[str] = Field(default_factory=list)
    created_at: str


class ActiveClaimSummary(BaseModel):
    batch_id: str
    agent: str
    source_uids: list[str | int] = Field(default_factory=list)


class RunProgressSnapshot(BaseModel):
    run_id: str
    total_target_rows: int
    done_rows: int
    skipped_rows: int
    claimed_rows: int
    pending_rows: int
    completed_batches: int
    failed_batches: int
    active_claims: list[ActiveClaimSummary] = Field(default_factory=list)


class StartGenerationRunResponse(BaseModel):
    status: Literal["started"]
    run_id: str
    input_path: str
    output_path: str
    uid_column: str
    row_offset: int
    batch_size: int
    row_limit: int | None = None
    total_source_rows: int
    total_target_rows: int
    progress: RunProgressSnapshot


class ClaimedBatch(BaseModel):
    batch_id: str
    agent: str
    rows: list[GeneratedRow] = Field(default_factory=list)


class ClaimNextBatchResponse(BaseModel):
    status: Literal["claimed", "waiting", "complete"]
    run_id: str
    batch: ClaimedBatch | None = None
    progress: RunProgressSnapshot


class SubmitBatchResultResponse(BaseModel):
    status: Literal["committed"]
    run_id: str
    batch_id: str
    rows_written: int
    rows_skipped: int
    output_path: str | None = None
    progress: RunProgressSnapshot


class FinalizeGenerationRunResponse(BaseModel):
    status: Literal["finalized"]
    run_id: str
    output_path: str
    rows_written: int
    state_cleaned: bool
    progress: RunProgressSnapshot


class ReleaseBatchClaimResponse(BaseModel):
    status: Literal["released"]
    run_id: str
    batch_id: str
    progress: RunProgressSnapshot


class GenerationRunListItem(BaseModel):
    run_id: str
    input_path: str
    output_path: str
    created_at: str


class ListGenerationRunsResponse(BaseModel):
    runs: list[GenerationRunListItem] = Field(default_factory=list)


class ProgressVerificationResponse(BaseModel):
    ok: bool
    run_id: str
    checked_agents: list[str] = Field(default_factory=list)
    broken_hashes: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_done_source_uids: list[str | int] = Field(default_factory=list)
    done_skip_overlap_source_uids: list[str | int] = Field(default_factory=list)
    missing_batch_files: list[str] = Field(default_factory=list)
    count_mismatches: list[str] = Field(default_factory=list)
    active_claims: list[str] = Field(default_factory=list)
