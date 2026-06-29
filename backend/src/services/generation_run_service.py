from pathlib import Path

from src.schemas import DatasetOutputConfig, DatasetWriteRequest
from src.schemas.generation_runtime_schema import (
    ClaimedBatch,
    ClaimNextBatchResponse,
    FinalizeGenerationRunResponse,
    GeneratedRow,
    GenerationRunListItem,
    GenerationRunManifest,
    ListGenerationRunsResponse,
    ProgressVerificationResponse,
    ReleaseBatchClaimResponse,
    SkippedRow,
    StartGenerationRunResponse,
    SubmitBatchResultResponse,
)
from src.services.base_run_service import DEFAULT_BATCH_SIZE, BaseRunService
from src.services.data_processing_service import DataProcessingService
from src.services.progress_tracking_service import ProgressTrackingService

FINAL_ROW_COUNT_ERROR = (
    "Cannot cleanup run because final output row count does not match completed rows."
)


class GenerationRunService(BaseRunService):
    """Generate adversarial NLI rows over the shared run lifecycle."""

    OUTPUT_COLUMNS = ("source_uid", "premise", "hypothesis", "label")
    RUN_ID_PREFIX = "run"
    BATCH_ID_PREFIX = "batch"
    RUN_SETTINGS_CLASS = GenerationRunManifest
    RUN_SETTINGS_NOT_FOUND_MESSAGE = "Run manifest not found"

    def __init__(
        self,
        data_processing_service: DataProcessingService,
        progress_tracking_service: ProgressTrackingService,
    ) -> None:
        """Wire tabular data IO and progress tracking dependencies."""
        super().__init__(data_processing_service, progress_tracking_service)
        self._data_processing_service = data_processing_service

    def start_generation_run(
        self,
        input_path: str,
        output_path: str | None = None,
        row_offset: int = 0,
        row_limit: int | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        agent_id: str = "main",
    ) -> StartGenerationRunResponse:
        """Create a generation run, persist its settings, and append the run.start event."""
        summary, uid_column, total_target_rows = self._prepare_new_run(
            input_path,
            row_offset,
            row_limit,
            batch_size,
        )
        run_settings = GenerationRunManifest(
            run_id=self._make_run_id(),
            input_path=str(Path(input_path).expanduser().resolve()),
            output_path=str(self._resolve_output_path(input_path, output_path)),
            uid_column=uid_column,
            row_offset=row_offset,
            batch_size=batch_size,
            row_limit=row_limit,
            total_source_rows=summary.row_count,
            total_target_rows=total_target_rows,
            columns=summary.columns,
            created_at=self._now_iso(),
        )
        start_payload = {
            "ts": self._now_iso(),
            "total_source_rows": run_settings.total_source_rows,
            "total_target_rows": run_settings.total_target_rows,
            "input_path": run_settings.input_path,
            "output_path": run_settings.output_path,
            "row_offset": run_settings.row_offset,
        }
        progress = self._persist_new_run(
            run_settings,
            agent_id,
            "run.start",
            start_payload,
        )
        return StartGenerationRunResponse(
            status="started",
            run_id=run_settings.run_id,
            input_path=run_settings.input_path,
            output_path=run_settings.output_path,
            uid_column=run_settings.uid_column,
            row_offset=run_settings.row_offset,
            batch_size=run_settings.batch_size,
            row_limit=run_settings.row_limit,
            total_source_rows=run_settings.total_source_rows,
            total_target_rows=run_settings.total_target_rows,
            progress=progress,
        )

    def claim_next_batch(
        self,
        run_id: str,
        agent_id: str,
    ) -> ClaimNextBatchResponse:
        """Claim the next available batch and return its rows projected for agents."""
        result = self._claim_next_batch(run_id, agent_id)
        if result["status"] != "claimed":
            return ClaimNextBatchResponse(
                status=result["status"],
                run_id=run_id,
                progress=result["progress"],
            )
        rows = [
            GeneratedRow.model_validate(
                self._normalize_source_row(row, result["uid_column"])
            )
            for row in result["selected_rows"]
        ]
        return ClaimNextBatchResponse(
            status="claimed",
            run_id=run_id,
            batch=ClaimedBatch(
                batch_id=result["batch_id"],
                agent=agent_id,
                rows=rows,
            ),
            progress=result["progress"],
        )

    def submit_batch_result(
        self,
        run_id: str,
        agent_id: str,
        batch_id: str,
        rows: list[dict],
        skipped_rows: list[dict] | None = None,
        batch_stats: dict | None = None,
    ) -> SubmitBatchResultResponse:
        """Validate generated rows and skips, write the batch output, and append progress events."""
        run_settings = self._load_run_settings(run_id)
        state = self._progress_tracking_service.build_run_state(run_id)
        claim = self._get_owned_claim(state, batch_id, agent_id)
        normalized_rows, normalized_skips = self._validate_batch_result(
            claim.source_uids,
            rows,
            self._source_label_map(run_settings),
            skipped_rows,
        )
        output_path = self._write_batch_outputs(run_id, batch_id, normalized_rows)
        self._log_row_events(
            run_id,
            agent_id,
            batch_id,
            normalized_rows,
            normalized_skips,
        )
        self._progress_tracking_service.append_event(
            run_id,
            agent_id,
            "batch.done",
            {
                "ts": self._now_iso(),
                "batch_id": batch_id,
                "file": output_path.name if output_path else None,
                "row_count": len(claim.source_uids),
                "written_count": len(normalized_rows),
                "skipped_count": len(normalized_skips),
                "stats": batch_stats or {},
            },
        )
        progress = self._progress_snapshot(run_id, run_settings.total_target_rows)
        return SubmitBatchResultResponse(
            status="committed",
            run_id=run_id,
            batch_id=batch_id,
            rows_written=len(normalized_rows),
            rows_skipped=len(normalized_skips),
            output_path=str(output_path) if output_path else None,
            progress=progress,
        )

    def get_run_progress(self, run_id: str):
        """Return the current generation progress snapshot."""
        return self._get_progress(run_id)

    def release_batch_claim(
        self,
        run_id: str,
        agent_id: str,
        batch_id: str,
        reason: str,
    ) -> ReleaseBatchClaimResponse:
        """Release an owned generation batch and append an unclaim event."""
        progress = self._release_claim(run_id, agent_id, batch_id, reason)
        return ReleaseBatchClaimResponse(
            status="released",
            run_id=run_id,
            batch_id=batch_id,
            progress=progress,
        )

    def finalize_generation_run(
        self,
        run_id: str,
        agent_id: str = "aggregator",
    ) -> FinalizeGenerationRunResponse:
        """Merge generation outputs, verify the run, and clean temporary state."""
        run_settings, state, output_files = self._collect_finalize_outputs(run_id)
        rows_written = self._merge_batch_csv(
            output_files,
            Path(run_settings.output_path),
        )
        self._progress_tracking_service.append_event(
            run_id,
            agent_id,
            "merge.done",
            {
                "ts": self._now_iso(),
                "processed": rows_written,
                "file": run_settings.output_path,
                "cleanup": False,
            },
        )
        self._progress_tracking_service.append_event(
            run_id,
            agent_id,
            "run.end",
            {
                "ts": self._now_iso(),
                "processed": rows_written,
                "skipped": len(state.skipped_rows),
                "output_path": run_settings.output_path,
            },
        )
        progress = self._verify_and_cleanup(
            run_id,
            run_settings.total_target_rows,
            rows_written,
            len(state.done_rows),
            FINAL_ROW_COUNT_ERROR,
        )
        return FinalizeGenerationRunResponse(
            status="finalized",
            run_id=run_id,
            output_path=run_settings.output_path,
            rows_written=rows_written,
            state_cleaned=True,
            progress=progress,
        )

    def verify_progress_log(
        self,
        run_id: str,
        agent_id: str | None = None,
    ) -> ProgressVerificationResponse:
        """Check generation progress-log consistency and row reconciliation."""
        return self._verify_progress_log(run_id, agent_id)

    def list_generation_runs(self) -> ListGenerationRunsResponse:
        """List all persisted generation runs."""
        runs = [
            GenerationRunListItem(
                run_id=run_settings.run_id,
                input_path=run_settings.input_path,
                output_path=run_settings.output_path,
                created_at=run_settings.created_at,
            )
            for run_settings in self._all_run_settings()
        ]
        return ListGenerationRunsResponse(runs=runs)

    def _source_label_map(self, run_settings):
        """Map each target source UID to its original label."""
        return {
            self._uid_key(row[run_settings.uid_column]): row["label"]
            for row in self._load_target_dataframe(run_settings).to_dict(
                orient="records"
            )
        }

    def _write_batch_outputs(self, run_id, batch_id, normalized_rows):
        """Write generated rows to a batch CSV and return its path, or None when empty."""
        if not normalized_rows:
            return None
        output_path = (
            self._progress_tracking_service.get_outputs_dir(run_id) / f"{batch_id}.csv"
        )
        self._data_processing_service.write_dataset(
            DatasetWriteRequest(
                rows=[row.model_dump(mode="json") for row in normalized_rows],
                output=DatasetOutputConfig(path=str(output_path)),
            )
        )
        return output_path

    def _log_row_events(
        self,
        run_id,
        agent_id,
        batch_id,
        normalized_rows,
        normalized_skips,
    ):
        """Append row.done and row.skip events for a committed batch."""
        for row in normalized_rows:
            self._progress_tracking_service.append_event(
                run_id,
                agent_id,
                "row.done",
                {
                    "ts": self._now_iso(),
                    "batch_id": batch_id,
                    "source_uid": row.source_uid,
                },
            )
        for skipped_row in normalized_skips:
            self._progress_tracking_service.append_event(
                run_id,
                agent_id,
                "row.skip",
                {
                    "ts": self._now_iso(),
                    "batch_id": batch_id,
                    "source_uid": skipped_row.source_uid,
                    "reason": skipped_row.reason,
                    "retries": skipped_row.retries,
                },
            )

    def _validate_batch_result(
        self,
        claimed_source_uids,
        rows,
        source_labels,
        skipped_rows=None,
    ):
        """Validate submitted generation rows and skips against the owned claim."""
        normalized_rows = [GeneratedRow.model_validate(item) for item in rows]
        normalized_skips = [
            SkippedRow.model_validate(item) for item in (skipped_rows or [])
        ]
        if not normalized_rows and not normalized_skips:
            raise ValueError("Batch result must include written rows or skipped rows.")
        claimed_keys = {self._uid_key(item) for item in claimed_source_uids}
        returned_keys = {self._uid_key(item.source_uid) for item in normalized_rows} | {
            self._uid_key(item.source_uid) for item in normalized_skips
        }
        if len(returned_keys) != len(normalized_rows) + len(normalized_skips):
            raise ValueError("Duplicate source_uid values detected in batch result.")
        if returned_keys != claimed_keys:
            raise ValueError(
                "Batch result source_uids must match the claimed batch exactly."
            )
        for row in normalized_rows:
            if not row.premise.strip():
                raise ValueError("premise must not be empty.")
            if not row.hypothesis.strip():
                raise ValueError("hypothesis must not be empty.")
            if str(row.label) != str(source_labels[self._uid_key(row.source_uid)]):
                raise ValueError("Batch result label must match the source label.")
        return normalized_rows, normalized_skips

    @staticmethod
    def _normalize_source_row(row, uid_column):
        """Project a source row into the public generated-row shape."""
        return {
            "source_uid": row[uid_column],
            "premise": row["premise"],
            "hypothesis": row["hypothesis"],
            "label": row["label"],
        }

    @staticmethod
    def _resolve_output_path(input_path, output_path):
        """Resolve the configured or default generation output path."""
        if output_path:
            return Path(output_path).expanduser().resolve()
        input_stem = Path(input_path).stem
        return (Path("data/generated") / f"{input_stem}_nli_adversarials.csv").resolve()
