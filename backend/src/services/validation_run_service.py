import csv
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

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
from src.services.dataset_reader_service import DatasetReaderService
from src.services.dispatch_planning_service import DEFAULT_GENERATION_BATCH_SIZE
from src.services.progress_tracking_service import ProgressTrackingService
from src.utils.validation_masking import build_masked_validation_dataset


class ValidationRunService:
    REQUIRED_COLUMNS = ("premise", "hypothesis", "label")
    OUTPUT_COLUMNS = (
        "source_uid",
        "premise",
        "hypothesis",
        "expected_label",
        "predicted_label",
        "accepted",
        "reason",
    )

    def __init__(
        self,
        dataset_reader_service: DatasetReaderService,
        progress_tracking_service: ProgressTrackingService,
    ) -> None:
        self._dataset_reader_service = dataset_reader_service
        self._progress_tracking_service = progress_tracking_service

    def start_validation_run(
        self,
        input_path: str,
        output_dir: str | None = None,
        row_offset: int = 0,
        row_limit: int | None = None,
        batch_size: int = DEFAULT_GENERATION_BATCH_SIZE,
        agent_id: str = "main",
    ) -> StartValidationRunResponse:
        if row_offset < 0:
            raise ValueError("row_offset must be at least 0.")
        if row_limit is not None and row_limit < 1:
            raise ValueError("row_limit must be at least 1.")
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1.")

        dataset_summary = self._dataset_reader_service.read_dataset(
            path=input_path,
            batch_size=1,
            batch_offset=0,
        )
        uid_column = self._resolve_uid_column(dataset_summary.columns)
        self._validate_columns(dataset_summary.columns)

        available_rows = max(dataset_summary.row_count - row_offset, 0)
        if available_rows == 0:
            raise ValueError("row_offset must point to an available dataset row.")
        total_target_rows = min(row_limit or available_rows, available_rows)
        target_dataframe = self._read_dataframe(input_path).iloc[
            row_offset : row_offset + total_target_rows
        ]
        self._validate_source_uids(target_dataframe[uid_column].tolist())

        run_id = (
            f"validation-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
        )
        manifest = ValidationRunManifest(
            run_id=run_id,
            input_path=str(Path(input_path).expanduser().resolve()),
            output_dir=str(self._resolve_output_dir(input_path, output_dir)),
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
            "validation.start",
            {
                "ts": self._now_iso(),
                "total_source_rows": manifest.total_source_rows,
                "total_target_rows": manifest.total_target_rows,
                "input_path": manifest.input_path,
                "output_dir": manifest.output_dir,
                "row_offset": manifest.row_offset,
            },
        )
        progress = self._progress_tracking_service.build_progress_snapshot(
            run_id,
            manifest.total_target_rows,
        )
        return StartValidationRunResponse(
            status="started",
            run_id=run_id,
            input_path=manifest.input_path,
            output_dir=manifest.output_dir,
            uid_column=manifest.uid_column,
            row_offset=manifest.row_offset,
            batch_size=manifest.batch_size,
            row_limit=manifest.row_limit,
            total_source_rows=manifest.total_source_rows,
            total_target_rows=manifest.total_target_rows,
            progress=progress,
        )

    def claim_next_validation_batch(
        self,
        run_id: str,
        agent_id: str,
    ) -> ClaimNextValidationBatchResponse:
        manifest = self._read_manifest(run_id)
        state = self._progress_tracking_service.build_run_state(run_id)
        progress = self._progress_tracking_service.build_progress_snapshot(
            run_id,
            manifest.total_target_rows,
        )
        if progress.pending_rows == 0 and progress.claimed_rows == 0:
            return ClaimNextValidationBatchResponse(
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
            return ClaimNextValidationBatchResponse(
                status="waiting", run_id=run_id, progress=progress
            )

        selected_rows = available_rows[: manifest.batch_size]
        batch_id = f"validation-batch-{state.claim_count + 1:05d}"
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
        masked_rows = build_masked_validation_dataset(
            pd.DataFrame(selected_rows),
            uid_column=manifest.uid_column,
        ).to_dict(orient="records")
        progress = self._progress_tracking_service.build_progress_snapshot(
            run_id,
            manifest.total_target_rows,
        )
        return ClaimNextValidationBatchResponse(
            status="claimed",
            run_id=run_id,
            batch=ClaimedValidationBatch(
                batch_id=batch_id,
                agent=agent_id,
                rows=[MaskedValidationRow.model_validate(row) for row in masked_rows],
            ),
            progress=progress,
        )

    def submit_validation_result(
        self,
        run_id: str,
        agent_id: str,
        batch_id: str,
        verdicts: list[dict],
    ) -> SubmitValidationResultResponse:
        manifest = self._read_manifest(run_id)
        state = self._progress_tracking_service.build_run_state(run_id)
        claim = state.active_claims.get(batch_id)
        if claim is None:
            raise ValueError(f"Batch is not actively claimed: {batch_id}")
        if claim.agent != agent_id:
            raise ValueError(
                f"Batch {batch_id} is claimed by {claim.agent}, not {agent_id}."
            )

        source_rows = {
            self._uid_key(row[manifest.uid_column]): row
            for row in self._load_target_dataframe(manifest).to_dict(orient="records")
        }
        normalized_verdicts = self._validate_verdicts(claim.source_uids, verdicts)
        rows = [
            self._build_output_row(
                source_rows[self._uid_key(verdict.source_uid)],
                manifest,
                verdict,
            )
            for verdict in normalized_verdicts
        ]

        output_path = (
            self._progress_tracking_service.get_outputs_dir(run_id) / f"{batch_id}.csv"
        )
        self._write_rows(output_path, rows)
        counts = self._count_acceptance(rows)
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
                "file": output_path.name,
                "row_count": len(rows),
                "accepted_count": counts["accepted"],
                "rejected_count": counts["rejected"],
            },
        )
        progress = self._progress_tracking_service.build_progress_snapshot(
            run_id,
            manifest.total_target_rows,
        )
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
        manifest = self._read_manifest(run_id)
        return self._progress_tracking_service.build_progress_snapshot(
            run_id,
            manifest.total_target_rows,
        )

    def release_validation_batch_claim(
        self,
        run_id: str,
        agent_id: str,
        batch_id: str,
        reason: str,
    ) -> ReleaseValidationBatchClaimResponse:
        manifest = self._read_manifest(run_id)
        state = self._progress_tracking_service.build_run_state(run_id)
        claim = state.active_claims.get(batch_id)
        if claim is None:
            raise ValueError(f"Batch is not actively claimed: {batch_id}")
        if claim.agent != agent_id:
            raise ValueError(
                f"Batch {batch_id} is claimed by {claim.agent}, not {agent_id}."
            )
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
        output_path = Path(manifest.output_dir) / "validation_results.csv"
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
                "output_dir": manifest.output_dir,
                "processed": counts["total"],
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
        if counts["total"] != len(state.done_rows):
            raise ValueError(
                "Cannot cleanup run because final output row count does not match validated rows."
            )
        self._progress_tracking_service.cleanup_outputs(run_id)
        self._progress_tracking_service.cleanup_run(run_id)
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

    def list_validation_runs(self) -> ListValidationRunsResponse:
        runs_root = self._progress_tracking_service.get_run_dir("placeholder").parent
        runs: list[ValidationRunListItem] = []
        if runs_root.exists():
            for manifest_path in sorted(runs_root.glob("*/manifest.json")):
                manifest = ValidationRunManifest.model_validate_json(
                    manifest_path.read_text(encoding="utf-8")
                )
                runs.append(
                    ValidationRunListItem(
                        run_id=manifest.run_id,
                        input_path=manifest.input_path,
                        output_dir=manifest.output_dir,
                        created_at=manifest.created_at,
                    )
                )
        return ListValidationRunsResponse(runs=runs)

    def _load_target_dataframe(self, manifest: ValidationRunManifest) -> pd.DataFrame:
        dataframe = self._read_dataframe(manifest.input_path)
        return dataframe.iloc[
            manifest.row_offset : manifest.row_offset + manifest.total_target_rows
        ]

    def _read_manifest(self, run_id: str) -> ValidationRunManifest:
        manifest_path = (
            self._progress_tracking_service.get_run_dir(run_id) / "manifest.json"
        )
        if not manifest_path.exists():
            raise FileNotFoundError(f"Validation run manifest not found: {run_id}")
        return ValidationRunManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )

    def _write_manifest(self, manifest: ValidationRunManifest) -> None:
        manifest_path = (
            self._progress_tracking_service.get_run_dir(manifest.run_id)
            / "manifest.json"
        )
        manifest_path.write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _validate_columns(self, columns: list[str]) -> None:
        missing_columns = [
            column for column in self.REQUIRED_COLUMNS if column not in columns
        ]
        if missing_columns:
            missing = ", ".join(missing_columns)
            hint = (
                " (pass the original generated file with a 'label' column, not a pre-masked file)"
                if "label" in missing_columns
                else ""
            )
            raise ValueError(f"Dataset is missing required columns: {missing}{hint}")

    def _validate_source_uids(self, source_uids: list[str | int]) -> None:
        if any(pd.isna(source_uid) for source_uid in source_uids):
            raise ValueError("Dataset slice contains empty source_uid values.")
        uid_keys = [self._uid_key(source_uid) for source_uid in source_uids]
        if len(set(uid_keys)) != len(uid_keys):
            raise ValueError("Dataset slice contains duplicate source_uid values.")

    def _validate_verdicts(
        self,
        claimed_source_uids: list[str | int],
        verdicts: list[dict],
    ) -> list[ValidatorVerdict]:
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

    def _build_output_row(
        self,
        source_row: dict,
        manifest: ValidationRunManifest,
        verdict: ValidatorVerdict,
    ) -> dict[str, str | int | bool]:
        expected_label = source_row["label"]
        accepted = self._labels_match(expected_label, verdict.predicted_label)
        return {
            "source_uid": source_row[manifest.uid_column],
            "premise": source_row["premise"],
            "hypothesis": source_row["hypothesis"],
            "expected_label": expected_label,
            "predicted_label": verdict.predicted_label,
            "accepted": accepted,
            "reason": verdict.reason,
        }

    @classmethod
    def _merge_validation_outputs(
        cls,
        output_files: list[Path],
        output_path: Path,
    ) -> dict[str, int]:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        counts = {"total": 0, "accepted": 0, "rejected": 0}
        with output_path.open("w", encoding="utf-8", newline="") as destination:
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
                        counts["total"] += 1
                        if cls._csv_bool(row["accepted"]):
                            counts["accepted"] += 1
                        else:
                            counts["rejected"] += 1
        return counts

    @classmethod
    def _write_rows(cls, output_path: Path, rows: list[dict]) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=cls.OUTPUT_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _labels_match(expected_label: str | int, predicted_label: str | int) -> bool:
        return str(expected_label) == str(predicted_label)

    @staticmethod
    def _count_acceptance(rows: list[dict]) -> dict[str, int]:
        counts = {"accepted": 0, "rejected": 0}
        for row in rows:
            if row["accepted"]:
                counts["accepted"] += 1
            else:
                counts["rejected"] += 1
        return counts

    @staticmethod
    def _csv_bool(value: str) -> bool:
        return value.strip().lower() == "true"

    @staticmethod
    def _resolve_uid_column(columns: list[str]) -> str:
        if "source_uid" in columns:
            return "source_uid"
        if "uid" in columns:
            return "uid"
        raise ValueError("Dataset must contain either uid or source_uid.")

    @staticmethod
    def _resolve_output_dir(input_path: str, output_dir: str | None) -> Path:
        if output_dir:
            return Path(output_dir).expanduser().resolve()
        input_stem = Path(input_path).stem
        return (Path("data/validated") / input_stem).resolve()

    @staticmethod
    def _read_dataframe(input_path: str) -> pd.DataFrame:
        path = Path(input_path)
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path)

    @staticmethod
    def _uid_key(source_uid: str | int) -> str:
        return str(source_uid)

    @staticmethod
    def _now_iso() -> str:
        return (
            datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
