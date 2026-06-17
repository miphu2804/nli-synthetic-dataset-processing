import csv
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
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
from src.services.dataset_reader_service import DatasetReaderService
from src.services.dataset_writer_service import DatasetWriterService
from src.services.dispatch_planning_service import DEFAULT_GENERATION_BATCH_SIZE
from src.services.progress_tracking_service import (
    ActiveClaim,
    ProgressTrackingService,
    RunState,
)


class GenerationRunService:
    REQUIRED_COLUMNS = ("premise", "hypothesis", "label")
    OUTPUT_COLUMNS = ("source_uid", "premise", "hypothesis", "label")

    def __init__(
        self,
        dataset_reader_service: DatasetReaderService,
        dataset_writer_service: DatasetWriterService,
        progress_tracking_service: ProgressTrackingService,
    ) -> None:
        """Wire the dataset reader/writer and progress-tracking collaborators used by every run operation."""
        self._dataset_reader_service = dataset_reader_service
        self._dataset_writer_service = dataset_writer_service
        self._progress_tracking_service = progress_tracking_service

    def start_generation_run(
        self,
        input_path: str,
        output_path: str | None = None,
        row_offset: int = 0,
        row_limit: int | None = None,
        batch_size: int = DEFAULT_GENERATION_BATCH_SIZE,
        agent_id: str = "main",
    ) -> StartGenerationRunResponse:
        """Create a generation run: validate args, slice the target rows, write the manifest, and log the run.start event.

        Side effects: creates run directories, writes manifest.json, and appends a run.start event to the progress log.
        """
        self._validate_run_args(row_offset, row_limit, batch_size)

        dataset_summary = self._dataset_reader_service.read_dataset(
            path=input_path,
            batch_size=1,
            batch_offset=0,
        )
        uid_column = self._resolve_uid_column(dataset_summary.columns)
        self._validate_columns(dataset_summary.columns)

        _, total_target_rows = self._resolve_target_slice(
            input_path, dataset_summary, uid_column, row_offset, row_limit
        )
        resolved_output_path = self._resolve_output_path(input_path, output_path)
        run_id = f"run-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
        manifest = GenerationRunManifest(
            run_id=run_id,
            input_path=str(Path(input_path).expanduser().resolve()),
            output_path=str(resolved_output_path),
            uid_column=uid_column,
            row_offset=row_offset,
            batch_size=batch_size,
            row_limit=row_limit,
            total_source_rows=dataset_summary.row_count,
            total_target_rows=total_target_rows,
            columns=dataset_summary.columns,
            created_at=self._now_iso(),
        )

        self._progress_tracking_service.ensure_run_directories(run_id)
        self._write_manifest(manifest)
        self._progress_tracking_service.append_event(
            run_id,
            agent_id,
            "run.start",
            {
                "ts": self._now_iso(),
                "total_source_rows": manifest.total_source_rows,
                "total_target_rows": manifest.total_target_rows,
                "input_path": manifest.input_path,
                "output_path": manifest.output_path,
                "row_offset": manifest.row_offset,
            },
        )
        progress = self._progress_tracking_service.build_progress_snapshot(
            run_id,
            manifest.total_target_rows,
        )
        return StartGenerationRunResponse(
            status="started",
            run_id=run_id,
            input_path=manifest.input_path,
            output_path=manifest.output_path,
            uid_column=manifest.uid_column,
            row_offset=manifest.row_offset,
            batch_size=manifest.batch_size,
            row_limit=manifest.row_limit,
            total_source_rows=manifest.total_source_rows,
            total_target_rows=manifest.total_target_rows,
            progress=progress,
        )

    def claim_next_batch(
        self,
        run_id: str,
        agent_id: str,
    ) -> ClaimNextBatchResponse:
        """Lock the next batch of unclaimed rows for agent_id and return them; reports complete/waiting when none are available.

        Side effects: appends a claim event to the progress log.
        """
        manifest = self._read_manifest(run_id)
        state = self._progress_tracking_service.build_run_state(run_id)
        progress = self._progress_tracking_service.build_progress_snapshot(
            run_id,
            manifest.total_target_rows,
        )
        if progress.pending_rows == 0 and progress.claimed_rows == 0:
            return ClaimNextBatchResponse(
                status="complete", run_id=run_id, progress=progress
            )

        source_df = self._load_target_dataframe(manifest)
        accounted_uids = set(state.done_rows) | set(state.skipped_rows)
        claimed_uids = {
            self._uid_key(source_uid)
            for claim in state.active_claims.values()
            for source_uid in claim.source_uids
        }
        available_rows = [
            row
            for row in source_df.to_dict(orient="records")
            if self._uid_key(row[manifest.uid_column]) not in accounted_uids
            and self._uid_key(row[manifest.uid_column]) not in claimed_uids
        ]
        if not available_rows:
            return ClaimNextBatchResponse(
                status="waiting", run_id=run_id, progress=progress
            )

        selected_rows = available_rows[: manifest.batch_size]
        batch_id = f"batch-{state.claim_count + 1:05d}"
        claimed_source_uids = [row[manifest.uid_column] for row in selected_rows]
        self._progress_tracking_service.append_event(
            run_id,
            agent_id,
            "claim",
            {
                "ts": self._now_iso(),
                "batch_id": batch_id,
                "source_uids": claimed_source_uids,
                "row_count": len(claimed_source_uids),
            },
        )
        normalized_rows = [
            self._normalize_source_row(row, manifest.uid_column)
            for row in selected_rows
        ]
        progress = self._progress_tracking_service.build_progress_snapshot(
            run_id,
            manifest.total_target_rows,
        )
        return ClaimNextBatchResponse(
            status="claimed",
            run_id=run_id,
            batch=ClaimedBatch(
                batch_id=batch_id,
                agent=agent_id,
                rows=[GeneratedRow.model_validate(item) for item in normalized_rows],
            ),
            progress=progress,
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
        """Commit a claimed batch: validate rows against the claim, write outputs, log row/batch events, and return updated progress.

        Side effects: writes the batch output CSV (when rows exist) and appends row.done/row.skip/batch.done events.
        """
        manifest = self._read_manifest(run_id)
        state = self._progress_tracking_service.build_run_state(run_id)
        claim = self._get_owned_claim(state, batch_id, agent_id)

        normalized_rows, normalized_skips = self._validate_batch_result(
            claim.source_uids,
            rows,
            self._source_label_map(manifest),
            skipped_rows,
        )
        output_path = self._write_batch_outputs(run_id, batch_id, normalized_rows)
        self._log_row_events(
            run_id, agent_id, batch_id, normalized_rows, normalized_skips
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
        progress = self._progress_tracking_service.build_progress_snapshot(
            run_id,
            manifest.total_target_rows,
        )
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
        """Return the current progress snapshot for the run."""
        manifest = self._read_manifest(run_id)
        return self._progress_tracking_service.build_progress_snapshot(
            run_id,
            manifest.total_target_rows,
        )

    def release_batch_claim(
        self,
        run_id: str,
        agent_id: str,
        batch_id: str,
        reason: str,
    ) -> ReleaseBatchClaimResponse:
        """Release agent_id's claim on batch_id so its rows become available again.

        Side effects: appends an unclaim event to the progress log.
        """
        manifest = self._read_manifest(run_id)
        state = self._progress_tracking_service.build_run_state(run_id)
        self._get_owned_claim(state, batch_id, agent_id)
        self._progress_tracking_service.append_event(
            run_id,
            agent_id,
            "unclaim",
            {
                "ts": self._now_iso(),
                "batch_id": batch_id,
                "reason": reason,
            },
        )
        progress = self._progress_tracking_service.build_progress_snapshot(
            run_id,
            manifest.total_target_rows,
        )
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
        """Merge all batch outputs into the final dataset, verify the run, and clean up run/batch state on success.

        Raises ValueError if claims remain, rows are unresolved, or verification fails. Side effects: writes the
        merged output, appends merge.done/run.end events, and deletes run + output directories when verified.
        """
        manifest = self._read_manifest(run_id)
        state = self._progress_tracking_service.build_run_state(run_id)
        if state.active_claims:
            raise ValueError("Cannot finalize while active claims remain.")
        accounted_rows = len(state.done_rows) + len(state.skipped_rows)
        if accounted_rows != manifest.total_target_rows:
            raise ValueError("Cannot finalize while pending rows remain unresolved.")

        output_files = [
            self._progress_tracking_service.resolve_output_file(run_id, event["file"])
            for event in state.completed_batches.values()
            if event.get("file")
        ]
        rows_written = self._merge_batch_outputs(
            output_files,
            Path(manifest.output_path),
        )
        self._progress_tracking_service.append_event(
            run_id,
            agent_id,
            "merge.done",
            {
                "ts": self._now_iso(),
                "processed": rows_written,
                "file": manifest.output_path,
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
                "output_path": manifest.output_path,
            },
        )
        progress = self._progress_tracking_service.build_progress_snapshot(
            run_id,
            manifest.total_target_rows,
        )
        verification = self._progress_tracking_service.verify_progress_log(
            run_id,
            total_target_rows=manifest.total_target_rows,
            require_batch_files=True,
        )
        if not verification.ok:
            raise ValueError("Cannot cleanup run because progress verification failed.")
        if rows_written != len(state.done_rows):
            raise ValueError(
                "Cannot cleanup run because final output row count does not match completed rows."
            )
        self._progress_tracking_service.cleanup_outputs(run_id)
        self._progress_tracking_service.cleanup_run(run_id)
        return FinalizeGenerationRunResponse(
            status="finalized",
            run_id=run_id,
            output_path=manifest.output_path,
            rows_written=rows_written,
            state_cleaned=True,
            progress=progress,
        )

    def verify_progress_log(
        self,
        run_id: str,
        agent_id: str | None = None,
    ) -> ProgressVerificationResponse:
        """Verify the progress log integrity and reconcile the snapshot row counts against the manifest total."""
        manifest = self._read_manifest(run_id)
        verification = self._progress_tracking_service.verify_progress_log(
            run_id,
            total_target_rows=manifest.total_target_rows,
            agent_id=agent_id,
            require_batch_files=True,
        )
        progress = self._progress_tracking_service.build_progress_snapshot(
            run_id,
            manifest.total_target_rows,
        )
        accounted_rows = (
            progress.done_rows
            + progress.skipped_rows
            + progress.claimed_rows
            + progress.pending_rows
        )
        if accounted_rows != manifest.total_target_rows:
            verification.count_mismatches.append(
                f"snapshot rows {accounted_rows} do not reconcile to total_target_rows={manifest.total_target_rows}"
            )
        verification.active_claims = [item.batch_id for item in progress.active_claims]
        verification.ok = verification.ok and not verification.count_mismatches
        return verification

    def list_generation_runs(self) -> ListGenerationRunsResponse:
        """List all known generation runs by reading each run's manifest.json."""
        runs_root = self._progress_tracking_service.get_run_dir("placeholder").parent
        runs: list[GenerationRunListItem] = []
        if runs_root.exists():
            for manifest_path in sorted(runs_root.glob("*/manifest.json")):
                manifest = GenerationRunManifest.model_validate_json(
                    manifest_path.read_text(encoding="utf-8")
                )
                runs.append(
                    GenerationRunListItem(
                        run_id=manifest.run_id,
                        input_path=manifest.input_path,
                        output_path=manifest.output_path,
                        created_at=manifest.created_at,
                    )
                )
        return ListGenerationRunsResponse(runs=runs)

    @staticmethod
    def _validate_run_args(
        row_offset: int, row_limit: int | None, batch_size: int
    ) -> None:
        """Validate run pagination args; raise ValueError if offset/limit/batch_size are out of range."""
        if row_offset < 0:
            raise ValueError("row_offset must be at least 0.")
        if row_limit is not None and row_limit < 1:
            raise ValueError("row_limit must be at least 1.")
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1.")

    def _resolve_target_slice(
        self,
        input_path: str,
        dataset_summary,
        uid_column: str,
        row_offset: int,
        row_limit: int | None,
    ) -> tuple[pd.DataFrame, int]:
        """Compute the target row window from offset/limit and return (target_dataframe, total_target_rows).

        Validates that the window is non-empty and its source_uids are present and unique.
        """
        available_rows = max(dataset_summary.row_count - row_offset, 0)
        if available_rows == 0:
            raise ValueError("row_offset must point to an available dataset row.")
        total_target_rows = min(row_limit or available_rows, available_rows)
        target_dataframe = self._read_dataframe(input_path).iloc[
            row_offset : row_offset + total_target_rows
        ]
        self._validate_source_uids(target_dataframe[uid_column].tolist())
        return target_dataframe, total_target_rows

    @staticmethod
    def _get_owned_claim(state: RunState, batch_id: str, agent_id: str) -> ActiveClaim:
        """Return the active claim for batch_id owned by agent_id; raise ValueError if it is unclaimed or owned by another agent."""
        claim = state.active_claims.get(batch_id)
        if claim is None:
            raise ValueError(f"Batch is not actively claimed: {batch_id}")
        if claim.agent != agent_id:
            raise ValueError(
                f"Batch {batch_id} is claimed by {claim.agent}, not {agent_id}."
            )
        return claim

    def _source_label_map(
        self, manifest: GenerationRunManifest
    ) -> dict[str, str | int]:
        """Map each target row's uid_key to its source label, used to verify submitted labels match the dataset."""
        return {
            self._uid_key(row[manifest.uid_column]): row["label"]
            for row in self._load_target_dataframe(manifest).to_dict(orient="records")
        }

    def _write_batch_outputs(
        self, run_id: str, batch_id: str, normalized_rows: list[GeneratedRow]
    ) -> Path | None:
        """Write committed batch rows to the run's outputs/{batch_id}.csv and return its path; return None when there are no rows."""
        if not normalized_rows:
            return None
        output_path = (
            self._progress_tracking_service.get_outputs_dir(run_id) / f"{batch_id}.csv"
        )
        self._dataset_writer_service.write_dataset(
            DatasetWriteRequest(
                rows=[row.model_dump(mode="json") for row in normalized_rows],
                output=DatasetOutputConfig(path=str(output_path)),
            )
        )
        return output_path

    def _log_row_events(
        self,
        run_id: str,
        agent_id: str,
        batch_id: str,
        normalized_rows: list[GeneratedRow],
        normalized_skips: list[SkippedRow],
    ) -> None:
        """Append a row.done event per written row and a row.skip event per skipped row to the progress log."""
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

    def _load_target_dataframe(self, manifest: GenerationRunManifest) -> pd.DataFrame:
        """Return the manifest's target row window (offset .. offset+total_target_rows) from the input dataset."""
        dataframe = self._read_dataframe(manifest.input_path)
        return dataframe.iloc[
            manifest.row_offset : manifest.row_offset + manifest.total_target_rows
        ]

    def _read_manifest(self, run_id: str) -> GenerationRunManifest:
        """Load and parse the run's manifest.json; raise FileNotFoundError if the run does not exist."""
        manifest_path = (
            self._progress_tracking_service.get_run_dir(run_id) / "manifest.json"
        )
        if not manifest_path.exists():
            raise FileNotFoundError(f"Run manifest not found: {run_id}")
        return GenerationRunManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )

    def _write_manifest(self, manifest: GenerationRunManifest) -> None:
        """Persist the manifest as JSON to the run's manifest.json."""
        manifest_path = (
            self._progress_tracking_service.get_run_dir(manifest.run_id)
            / "manifest.json"
        )
        manifest_path.write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _validate_columns(self, columns: list[str]) -> None:
        """Raise ValueError if any REQUIRED_COLUMNS are missing from the dataset columns."""
        missing_columns = [
            column for column in self.REQUIRED_COLUMNS if column not in columns
        ]
        if missing_columns:
            missing = ", ".join(missing_columns)
            raise ValueError(f"Dataset is missing required columns: {missing}")

    def _validate_source_uids(self, source_uids: list[str | int]) -> None:
        """Raise ValueError if the source_uids contain empty or duplicate values."""
        if any(pd.isna(source_uid) for source_uid in source_uids):
            raise ValueError("Dataset slice contains empty source_uid values.")
        uid_keys = [self._uid_key(source_uid) for source_uid in source_uids]
        if len(set(uid_keys)) != len(uid_keys):
            raise ValueError("Dataset slice contains duplicate source_uid values.")

    @staticmethod
    def _resolve_uid_column(columns: list[str]) -> str:
        """Return the uid column name ('source_uid' or 'uid'); raise ValueError if neither is present."""
        if "source_uid" in columns:
            return "source_uid"
        if "uid" in columns:
            return "uid"
        raise ValueError("Dataset must contain either uid or source_uid.")

    def _validate_batch_result(
        self,
        claimed_source_uids: list[str | int],
        rows: list[dict],
        source_labels: dict[str, str | int],
        skipped_rows: list[dict] | None = None,
    ) -> tuple[list[GeneratedRow], list[SkippedRow]]:
        """Parse and validate submitted rows/skips against the claim: uids must match exactly, labels must match the source, and text fields must be non-empty.

        Returns the normalized (rows, skips); raises ValueError on any mismatch or empty field.
        """
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
            if self._label_key(row.label) != self._label_key(
                source_labels[self._uid_key(row.source_uid)]
            ):
                raise ValueError("Batch result label must match the source label.")
        return normalized_rows, normalized_skips

    @classmethod
    def _merge_batch_outputs(
        cls, output_files: list[Path], final_output_path: Path
    ) -> int:
        """Concatenate all batch output CSVs into final_output_path and return the total rows written.

        Raises if a batch file is missing or its schema does not match OUTPUT_COLUMNS.
        """
        final_output_path.parent.mkdir(parents=True, exist_ok=True)
        rows_written = 0

        with final_output_path.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, fieldnames=cls.OUTPUT_COLUMNS)
            writer.writeheader()
            for file_path in sorted(output_files):
                if not file_path.exists():
                    raise FileNotFoundError(f"Missing batch output file: {file_path}")
                with file_path.open("r", encoding="utf-8", newline="") as source:
                    reader = csv.DictReader(source)
                    if reader.fieldnames != list(cls.OUTPUT_COLUMNS):
                        raise ValueError(f"Batch output schema mismatch: {file_path}")
                    for row in reader:
                        writer.writerow(row)
                        rows_written += 1

        return rows_written

    @staticmethod
    def _normalize_source_row(row: dict, uid_column: str) -> dict:
        """Project a source dataset row into the {source_uid, premise, hypothesis, label} shape handed to agents."""
        return {
            "source_uid": row[uid_column],
            "premise": row["premise"],
            "hypothesis": row["hypothesis"],
            "label": row["label"],
        }

    @staticmethod
    def _resolve_output_path(input_path: str, output_path: str | None) -> Path:
        """Return the resolved output path, defaulting to data/generated/{stem}_nli_adversarials.csv when none is given."""
        if output_path:
            return Path(output_path).expanduser().resolve()
        input_stem = Path(input_path).stem
        return (Path("data/generated") / f"{input_stem}_nli_adversarials.csv").resolve()

    @staticmethod
    def _read_dataframe(input_path: str) -> pd.DataFrame:
        """Read the input dataset as a DataFrame, selecting parquet or CSV by file suffix."""
        path = Path(input_path)
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path)

    @staticmethod
    def _uid_key(source_uid: str | int) -> str:
        """Return the canonical string key for a source_uid so int/str values compare consistently."""
        return str(source_uid)

    @staticmethod
    def _label_key(label: str | int) -> str:
        """Return the canonical string key for a label so int/str values compare consistently."""
        return str(label)

    @staticmethod
    def _now_iso() -> str:
        """Return the current UTC time as an ISO-8601 string with a trailing Z and no microseconds."""
        return (
            datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
