import csv
from pathlib import Path

import pandas as pd

from src.schemas.generation_runtime_schema import ProgressVerificationResponse
from src.schemas.validation_runtime_schema import (
    ClaimedValidationBatch,
    ClaimNextValidationBatchResponse,
    FinalizeValidationRunResponse,
    ListValidationRunsResponse,
    MaskedValidationRow,
    ReleaseValidationBatchClaimResponse,
    StartValidationRunResponse,
    SubmitValidationResultResponse,
    ValidationRunListItem,
    ValidationRunManifest,
    ValidatorVerdict,
)
from src.services.base_run_service import DEFAULT_BATCH_SIZE, BaseRunService
from src.services.data_processing_service import DataProcessingService
from src.services.progress_tracking_service import ProgressTrackingService
from src.utils.nli_labels import to_label_name
from src.utils.project_paths import resolve_data_path, resolve_runtime_path
from src.utils.validation_masking import build_masked_validation_dataset

FINAL_ROW_COUNT_ERROR = (
    "Cannot cleanup run because final output row count does not match validated rows."
)


class ValidationRunService(BaseRunService):
    """Validate generated NLI rows with blank labels over the shared run lifecycle."""

    OUTPUT_COLUMNS = (
        "source_uid",
        "premise",
        "hypothesis",
        "expected_label",
        "predicted_label",
        "accepted",
        "reason",
    )
    RUN_ID_PREFIX = "validation"
    BATCH_ID_PREFIX = "validation-batch"
    RUN_SETTINGS_CLASS = ValidationRunManifest
    RUN_SETTINGS_NOT_FOUND_MESSAGE = "Validation run manifest not found"

    def __init__(
        self,
        data_processing_service: DataProcessingService,
        progress_tracking_service: ProgressTrackingService,
    ) -> None:
        """Wire tabular data IO and progress tracking dependencies."""
        super().__init__(data_processing_service, progress_tracking_service)

    def start_validation_run(
        self,
        input_path: str,
        output_dir: str | None = None,
        row_offset: int = 0,
        row_limit: int | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        agent_id: str = "main",
    ) -> StartValidationRunResponse:
        """Create a validation run, persist its settings, and append the validation.start event."""
        summary, uid_column, total_target_rows = self._prepare_new_run(
            input_path,
            row_offset,
            row_limit,
            batch_size,
        )
        run_settings = ValidationRunManifest(
            run_id=self._make_run_id(),
            input_path=str(resolve_runtime_path(input_path)),
            output_dir=str(self._resolve_output_dir(input_path, output_dir)),
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
            "output_dir": run_settings.output_dir,
            "row_offset": run_settings.row_offset,
        }
        progress = self._persist_new_run(
            run_settings,
            agent_id,
            "validation.start",
            start_payload,
        )
        return StartValidationRunResponse(
            status="started",
            run_id=run_settings.run_id,
            input_path=run_settings.input_path,
            output_dir=run_settings.output_dir,
            uid_column=run_settings.uid_column,
            row_offset=run_settings.row_offset,
            batch_size=run_settings.batch_size,
            row_limit=run_settings.row_limit,
            total_source_rows=run_settings.total_source_rows,
            total_target_rows=run_settings.total_target_rows,
            progress=progress,
        )

    def claim_next_validation_batch(
        self,
        run_id: str,
        agent_id: str,
    ) -> ClaimNextValidationBatchResponse:
        """Claim the next available batch and return its rows with the label blanked."""
        result = self._claim_next_batch(run_id, agent_id)
        if result["status"] != "claimed":
            return ClaimNextValidationBatchResponse(
                status=result["status"],
                run_id=run_id,
                progress=result["progress"],
            )
        masked_rows = build_masked_validation_dataset(
            pd.DataFrame(result["selected_rows"]),
            uid_column=result["uid_column"],
        ).to_dict(orient="records")
        return ClaimNextValidationBatchResponse(
            status="claimed",
            run_id=run_id,
            batch=ClaimedValidationBatch(
                batch_id=result["batch_id"],
                agent=agent_id,
                rows=[MaskedValidationRow.model_validate(row) for row in masked_rows],
            ),
            progress=result["progress"],
        )

    def submit_validation_result(
        self,
        run_id: str,
        agent_id: str,
        batch_id: str,
        verdicts: list[dict],
    ) -> SubmitValidationResultResponse:
        """Validate verdicts, build accepted/rejected result rows, write them, and append progress events."""
        run_settings = self._load_run_settings(run_id)
        state = self._progress_tracking_service.build_run_state(run_id)
        claim = self._get_owned_claim(state, batch_id, agent_id)
        source_rows = {
            self._uid_key(row[run_settings.uid_column]): row
            for row in self._load_target_dataframe(run_settings).to_dict(
                orient="records"
            )
        }
        normalized_verdicts = self._validate_verdicts(claim.source_uids, verdicts)
        rows = [
            self._build_output_row(
                source_rows[self._uid_key(verdict.source_uid)],
                run_settings.uid_column,
                verdict,
            )
            for verdict in normalized_verdicts
        ]
        output_path = (
            self._progress_tracking_service.get_outputs_dir(run_id) / f"{batch_id}.csv"
        )
        self._write_rows(output_path, rows)
        accepted_count = sum(1 for row in rows if row["accepted"])
        counts = {"accepted": accepted_count, "rejected": len(rows) - accepted_count}
        self._log_validation_events(
            run_id,
            agent_id,
            batch_id,
            rows,
            output_path.name,
            counts,
        )
        progress = self._progress_snapshot(run_id, run_settings.total_target_rows)
        return SubmitValidationResultResponse(
            status="committed",
            run_id=run_id,
            batch_id=batch_id,
            rows_validated=len(rows),
            accepted_count=counts["accepted"],
            rejected_count=counts["rejected"],
            output_path=str(output_path),
            progress=progress,
        )

    def get_validation_progress(self, run_id: str):
        """Return the current validation progress snapshot."""
        return self._get_progress(run_id)

    def release_validation_batch_claim(
        self,
        run_id: str,
        agent_id: str,
        batch_id: str,
        reason: str,
    ) -> ReleaseValidationBatchClaimResponse:
        """Release an owned validation batch and append an unclaim event."""
        progress = self._release_claim(run_id, agent_id, batch_id, reason)
        return ReleaseValidationBatchClaimResponse(
            status="released",
            run_id=run_id,
            batch_id=batch_id,
            progress=progress,
        )

    def finalize_validation_run(
        self,
        run_id: str,
        agent_id: str = "validator-aggregator",
    ) -> FinalizeValidationRunResponse:
        """Merge validation results, verify the run, and clean temporary state."""
        run_settings, state, output_files = self._collect_finalize_outputs(run_id)
        output_path = Path(run_settings.output_dir) / "validation_results.csv"
        counts = self._merge_validation_outputs(output_files, output_path)
        self._progress_tracking_service.append_event(
            run_id,
            agent_id,
            "validation.merge.done",
            {
                "ts": self._now_iso(),
                "file": output_path.name,
                "total_rows": counts["total"],
                "accepted_rows": counts["accepted"],
                "rejected_rows": counts["rejected"],
            },
        )
        self._progress_tracking_service.append_event(
            run_id,
            agent_id,
            "validation.end",
            {
                "ts": self._now_iso(),
                "output_dir": run_settings.output_dir,
                "processed": counts["total"],
            },
        )
        progress = self._verify_and_cleanup(
            run_id,
            run_settings.total_target_rows,
            counts["total"],
            len(state.done_rows),
            FINAL_ROW_COUNT_ERROR,
        )
        return FinalizeValidationRunResponse(
            status="finalized",
            run_id=run_id,
            output_path=str(output_path),
            total_rows=counts["total"],
            accepted_rows=counts["accepted"],
            rejected_rows=counts["rejected"],
            state_cleaned=True,
            progress=progress,
        )

    def verify_validation_progress_log(
        self,
        run_id: str,
        agent_id: str | None = None,
    ) -> ProgressVerificationResponse:
        """Check validation progress-log consistency and row reconciliation."""
        return self._verify_progress_log(run_id, agent_id)

    def list_validation_runs(self) -> ListValidationRunsResponse:
        """List all persisted validation runs."""
        runs = [
            ValidationRunListItem(
                run_id=run_settings.run_id,
                input_path=run_settings.input_path,
                output_dir=run_settings.output_dir,
                created_at=run_settings.created_at,
            )
            for run_settings in self._all_run_settings()
        ]
        return ListValidationRunsResponse(runs=runs)

    def _validate_columns(self, columns):
        """Raise ValueError if required columns are missing, hinting when the label was pre-masked."""
        missing_columns = [
            column for column in self.REQUIRED_COLUMNS if column not in columns
        ]
        if missing_columns:
            missing = ", ".join(missing_columns)
            hint = (
                " (pass the original generated file with a 'label' column, "
                "not a pre-masked file)"
                if "label" in missing_columns
                else ""
            )
            raise ValueError(f"Dataset is missing required columns: {missing}{hint}")

    def _validate_verdicts(self, claimed_source_uids, verdicts):
        """Validate submitted verdicts against the owned claim and return the normalized verdicts."""
        normalized_verdicts = [
            ValidatorVerdict.model_validate(item) for item in verdicts
        ]
        if not normalized_verdicts:
            raise ValueError("Validation result must include verdicts.")
        claimed_keys = {self._uid_key(item) for item in claimed_source_uids}
        returned_keys = {self._uid_key(item.source_uid) for item in normalized_verdicts}
        if len(returned_keys) != len(normalized_verdicts):
            raise ValueError("Duplicate source_uid values detected in verdicts.")
        if returned_keys != claimed_keys:
            raise ValueError(
                "Validation result source_uids must match the claimed batch exactly."
            )
        for verdict in normalized_verdicts:
            if not verdict.reason.strip():
                raise ValueError("reason must not be empty.")
        return normalized_verdicts

    def _build_output_row(self, source_row, uid_column, verdict):
        """Build a result row pairing a source row with its verdict and acceptance flag."""
        expected_label = source_row["label"]
        accepted = self._labels_match(expected_label, verdict.predicted_label)
        return {
            "source_uid": source_row[uid_column],
            "premise": source_row["premise"],
            "hypothesis": source_row["hypothesis"],
            "expected_label": expected_label,
            "predicted_label": verdict.predicted_label,
            "accepted": accepted,
            "reason": verdict.reason,
        }

    def _log_validation_events(
        self,
        run_id,
        agent_id,
        batch_id,
        rows,
        file_name,
        counts,
    ):
        """Append a row.done event per validated row and a batch.done summary event."""
        for row in rows:
            self._progress_tracking_service.append_event(
                run_id,
                agent_id,
                "row.done",
                {
                    "ts": self._now_iso(),
                    "batch_id": batch_id,
                    "source_uid": row["source_uid"],
                    "accepted": row["accepted"],
                },
            )
        self._progress_tracking_service.append_event(
            run_id,
            agent_id,
            "batch.done",
            {
                "ts": self._now_iso(),
                "batch_id": batch_id,
                "file": file_name,
                "row_count": len(rows),
                "accepted_count": counts["accepted"],
                "rejected_count": counts["rejected"],
            },
        )

    def _merge_validation_outputs(self, output_files, output_path):
        """Concatenate validation result CSVs into output_path and return {total, accepted, rejected}."""
        counts = {"total": 0, "accepted": 0, "rejected": 0}

        def tally(row):
            if row["accepted"].strip().lower() == "true":
                counts["accepted"] += 1
            else:
                counts["rejected"] += 1

        counts["total"] = self._merge_batch_csv(
            output_files,
            output_path,
            row_hook=tally,
        )
        return counts

    def _write_rows(self, output_path, rows):
        """Write validation result rows to output_path as a CSV with the OUTPUT_COLUMNS header."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.OUTPUT_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _labels_match(expected_label, predicted_label):
        """Return True if expected and predicted labels match after normalization.

        Raises ValueError if expected_label is not a valid NLI label.
        """
        return to_label_name(expected_label) == to_label_name(predicted_label)

    @staticmethod
    def _resolve_output_dir(input_path, output_dir):
        """Resolve the configured or default validation output directory."""
        if output_dir:
            return resolve_runtime_path(output_dir)
        input_stem = Path(input_path).stem
        return resolve_data_path("validated", input_stem)
