import csv
from datetime import UTC, datetime
from uuid import uuid4

import pandas as pd

DEFAULT_BATCH_SIZE = 20


class BaseRunService:
    """Shared run-lifecycle helpers reused by the generation and validation services.

    Subclasses set the class-level configuration (run id / batch id prefixes and
    the persisted settings model) and assemble their own public responses. This
    base owns the parts that are identical for both: argument validation, dataset
    slicing, claim selection, progress consistency checks, and finalize checks/cleanup.
    """

    REQUIRED_COLUMNS = ("premise", "hypothesis", "label")
    RUN_ID_PREFIX = ""
    BATCH_ID_PREFIX = ""
    RUN_SETTINGS_CLASS = None
    RUN_SETTINGS_NOT_FOUND_MESSAGE = "Run manifest not found"

    def __init__(self, data_processing_service, progress_tracking_service) -> None:
        """Store tabular data IO and progress tracking dependencies."""
        self._data_processing_service = data_processing_service
        self._progress_tracking_service = progress_tracking_service

    def _prepare_new_run(self, input_path, row_offset, row_limit, batch_size):
        """Validate arguments and resolve the target slice; return (dataset_summary, uid_column, total_target_rows)."""
        self._validate_run_args(row_offset, row_limit, batch_size)
        dataset_summary = self._data_processing_service.read_dataset(
            path=input_path,
            batch_size=1,
            batch_offset=0,
        )
        uid_column = self._resolve_uid_column(dataset_summary.columns)
        self._validate_columns(dataset_summary.columns)
        _, total_target_rows = self._resolve_target_slice(
            input_path,
            dataset_summary,
            uid_column,
            row_offset,
            row_limit,
        )
        return dataset_summary, uid_column, total_target_rows

    def _make_run_id(self) -> str:
        """Return a new unique run id prefixed for this run type."""
        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        return f"{self.RUN_ID_PREFIX}-{stamp}-{uuid4().hex[:8]}"

    def _persist_new_run(self, run_settings, agent_id, start_event_name, start_payload):
        """Create run directories, save settings, append the start event, and return a progress snapshot."""
        self._progress_tracking_service.ensure_run_directories(run_settings.run_id)
        self._save_run_settings(run_settings)
        self._progress_tracking_service.append_event(
            run_settings.run_id,
            agent_id,
            start_event_name,
            start_payload,
        )
        return self._progress_snapshot(
            run_settings.run_id,
            run_settings.total_target_rows,
        )

    def _claim_next_batch(self, run_id, agent_id):
        """Select the next batch and record the claim; return a dict describing the outcome.

        ``status`` is "complete", "waiting", or "claimed". A claimed result also
        carries "batch_id", "selected_rows", and "uid_column" so the caller can
        project the rows into its own row model. Side effect: appends a claim
        event when a batch is claimed.
        """
        run_settings = self._load_run_settings(run_id)
        state = self._progress_tracking_service.build_run_state(run_id)
        progress = self._progress_snapshot(run_id, run_settings.total_target_rows)
        if progress.pending_rows == 0 and progress.claimed_rows == 0:
            return {"status": "complete", "progress": progress}

        source_dataframe = self._load_target_dataframe(run_settings)
        accounted_uids = set(state.done_rows) | set(state.skipped_rows)
        claimed_uids = {
            self._uid_key(source_uid)
            for claim in state.active_claims.values()
            for source_uid in claim.source_uids
        }
        available_rows = [
            row
            for row in source_dataframe.to_dict(orient="records")
            if self._uid_key(row[run_settings.uid_column]) not in accounted_uids
            and self._uid_key(row[run_settings.uid_column]) not in claimed_uids
        ]
        if not available_rows:
            return {"status": "waiting", "progress": progress}

        selected_rows = available_rows[: run_settings.batch_size]
        batch_id = f"{self.BATCH_ID_PREFIX}-{state.claim_count + 1:05d}"
        claimed_source_uids = [row[run_settings.uid_column] for row in selected_rows]
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
        return {
            "status": "claimed",
            "batch_id": batch_id,
            "selected_rows": selected_rows,
            "uid_column": run_settings.uid_column,
            "progress": self._progress_snapshot(
                run_id,
                run_settings.total_target_rows,
            ),
        }

    def _progress_snapshot(self, run_id, total_target_rows):
        """Return the progress snapshot for a run."""
        return self._progress_tracking_service.build_progress_snapshot(
            run_id,
            total_target_rows,
        )

    def _get_progress(self, run_id):
        """Return the current progress snapshot for a persisted run."""
        run_settings = self._load_run_settings(run_id)
        return self._progress_snapshot(run_id, run_settings.total_target_rows)

    def _verify_progress_log(self, run_id, agent_id=None):
        """Check progress-log consistency and reconcile snapshot row counts against the run total."""
        run_settings = self._load_run_settings(run_id)
        verification = self._progress_tracking_service.verify_progress_log(
            run_id,
            total_target_rows=run_settings.total_target_rows,
            agent_id=agent_id,
            require_batch_files=True,
        )
        progress = self._progress_snapshot(run_id, run_settings.total_target_rows)
        accounted_rows = (
            progress.done_rows
            + progress.skipped_rows
            + progress.claimed_rows
            + progress.pending_rows
        )
        if accounted_rows != run_settings.total_target_rows:
            verification.count_mismatches.append(
                f"snapshot rows {accounted_rows} do not reconcile to "
                f"total_target_rows={run_settings.total_target_rows}"
            )
        verification.active_claims = [item.batch_id for item in progress.active_claims]
        verification.ok = verification.ok and not verification.count_mismatches
        return verification

    def _release_claim(self, run_id, agent_id, batch_id, reason):
        """Validate ownership, append an unclaim event, and return the updated progress snapshot."""
        run_settings = self._load_run_settings(run_id)
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
        return self._progress_snapshot(run_id, run_settings.total_target_rows)

    def _collect_finalize_outputs(self, run_id):
        """Ensure the run can finalize and return (run_settings, state, output_files).

        Raises ValueError if claims are still active or rows remain unresolved.
        """
        run_settings = self._load_run_settings(run_id)
        state = self._progress_tracking_service.build_run_state(run_id)
        if state.active_claims:
            raise ValueError("Cannot finalize while active claims remain.")
        accounted_rows = len(state.done_rows) + len(state.skipped_rows)
        if accounted_rows != run_settings.total_target_rows:
            raise ValueError("Cannot finalize while pending rows remain unresolved.")
        output_files = [
            self._progress_tracking_service.resolve_output_file(run_id, event["file"])
            for event in state.completed_batches.values()
            if event.get("file")
        ]
        return run_settings, state, output_files

    def _merge_batch_csv(self, output_files, output_path, row_hook=None):
        """Concatenate batch CSVs into output_path and return the rows written.

        Uses ``self.OUTPUT_COLUMNS`` for the merged header and per-batch schema
        check. When ``row_hook`` is provided, it is called with each written row
        so subclasses can accumulate their own statistics.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rows_written = 0
        with output_path.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, fieldnames=self.OUTPUT_COLUMNS)
            writer.writeheader()
            for file_path in sorted(output_files):
                if not file_path.exists():
                    raise FileNotFoundError(f"Missing batch output file: {file_path}")
                with file_path.open("r", encoding="utf-8", newline="") as source:
                    reader = csv.DictReader(source)
                    if reader.fieldnames != list(self.OUTPUT_COLUMNS):
                        raise ValueError(f"Batch output schema mismatch: {file_path}")
                    for row in reader:
                        writer.writerow(row)
                        rows_written += 1
                        if row_hook is not None:
                            row_hook(row)
        return rows_written

    def _verify_and_cleanup(
        self,
        run_id,
        total_target_rows,
        merged_row_count,
        done_row_count,
        row_count_error,
    ):
        """Verify the run, confirm the merged row count, delete run state, and return the final snapshot.

        Raises ValueError if verification fails or the merged row count does not
        match the number of completed rows.
        """
        progress = self._progress_snapshot(run_id, total_target_rows)
        verification = self._progress_tracking_service.verify_progress_log(
            run_id,
            total_target_rows=total_target_rows,
            require_batch_files=True,
        )
        if not verification.ok:
            raise ValueError("Cannot cleanup run because progress verification failed.")
        if merged_row_count != done_row_count:
            raise ValueError(row_count_error)
        self._progress_tracking_service.cleanup_outputs(run_id)
        self._progress_tracking_service.cleanup_run(run_id)
        return progress

    def _all_run_settings(self):
        """Read and return the persisted settings of every run found on disk."""
        runs_root = self._progress_tracking_service.get_run_dir("placeholder").parent
        run_settings_list = []
        if runs_root.exists():
            for settings_path in sorted(runs_root.glob("*/manifest.json")):
                run_settings_list.append(
                    self.RUN_SETTINGS_CLASS.model_validate_json(
                        settings_path.read_text(encoding="utf-8")
                    )
                )
        return run_settings_list

    def _load_run_settings(self, run_id):
        """Load run settings from the run's manifest.json or raise FileNotFoundError."""
        settings_path = (
            self._progress_tracking_service.get_run_dir(run_id) / "manifest.json"
        )
        if not settings_path.exists():
            raise FileNotFoundError(f"{self.RUN_SETTINGS_NOT_FOUND_MESSAGE}: {run_id}")
        return self.RUN_SETTINGS_CLASS.model_validate_json(
            settings_path.read_text(encoding="utf-8")
        )

    def _save_run_settings(self, run_settings):
        """Persist run settings to the run's manifest.json file."""
        settings_path = (
            self._progress_tracking_service.get_run_dir(run_settings.run_id)
            / "manifest.json"
        )
        settings_path.write_text(
            run_settings.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _load_target_dataframe(self, run_settings):
        """Read and return the row window described by the persisted run settings."""
        return self._data_processing_service.read_dataframe(
            run_settings.input_path,
            row_offset=run_settings.row_offset,
            row_limit=run_settings.total_target_rows,
        )

    @staticmethod
    def _validate_run_args(row_offset, row_limit, batch_size):
        """Raise ValueError when pagination or batch-size arguments are invalid."""
        if row_offset < 0:
            raise ValueError("row_offset must be at least 0.")
        if row_limit is not None and row_limit < 1:
            raise ValueError("row_limit must be at least 1.")
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1.")

    def _resolve_target_slice(
        self,
        input_path,
        dataset_summary,
        uid_column,
        row_offset,
        row_limit,
    ):
        """Return the validated target row window and its row count."""
        available_rows = max(dataset_summary.row_count - row_offset, 0)
        if available_rows == 0:
            raise ValueError("row_offset must point to an available dataset row.")
        total_target_rows = min(row_limit or available_rows, available_rows)
        target_dataframe = self._data_processing_service.read_dataframe(
            input_path,
            row_offset=row_offset,
            row_limit=total_target_rows,
        )
        self._validate_source_uids(target_dataframe[uid_column].tolist())
        return target_dataframe, total_target_rows

    def _validate_columns(self, columns):
        """Raise ValueError if required dataset columns are missing."""
        missing_columns = [
            column for column in self.REQUIRED_COLUMNS if column not in columns
        ]
        if missing_columns:
            missing = ", ".join(missing_columns)
            raise ValueError(f"Dataset is missing required columns: {missing}")

    def _validate_source_uids(self, source_uids):
        """Raise ValueError if source UIDs contain empty or duplicate values."""
        if any(pd.isna(source_uid) for source_uid in source_uids):
            raise ValueError("Dataset slice contains empty source_uid values.")
        uid_keys = [self._uid_key(source_uid) for source_uid in source_uids]
        if len(set(uid_keys)) != len(uid_keys):
            raise ValueError("Dataset slice contains duplicate source_uid values.")

    @staticmethod
    def _resolve_uid_column(columns):
        """Return source_uid or uid, preferring source_uid when both exist."""
        if "source_uid" in columns:
            return "source_uid"
        if "uid" in columns:
            return "uid"
        raise ValueError("Dataset must contain either uid or source_uid.")

    @staticmethod
    def _get_owned_claim(state, batch_id, agent_id):
        """Return an owned active claim or raise ValueError for invalid ownership."""
        claim = state.active_claims.get(batch_id)
        if claim is None:
            raise ValueError(f"Batch is not actively claimed: {batch_id}")
        if claim.agent != agent_id:
            raise ValueError(
                f"Batch {batch_id} is claimed by {claim.agent}, not {agent_id}."
            )
        return claim

    @staticmethod
    def _uid_key(source_uid):
        """Return a normalized string key for a source UID."""
        return str(source_uid)

    @staticmethod
    def _now_iso():
        """Return the current UTC time as an ISO-8601 string without microseconds."""
        return (
            datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
