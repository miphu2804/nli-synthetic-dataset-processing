import csv
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from src.services.data_processing_service import DataProcessingService
from src.services.progress_tracking_service import ProgressTrackingService
from src.services.validation_run_service import ValidationRunService


class ValidationRunServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.pipeline_dir = self.root / ".pipeline" / "validation"
        self.input_path = self.root / "generated.csv"
        pd.DataFrame(
            [
                {"source_uid": 1, "premise": "p1", "hypothesis": "h1", "label": 1},
                {"source_uid": 2, "premise": "p2", "hypothesis": "h2", "label": 0},
                {"source_uid": 3, "premise": "p3", "hypothesis": "h3", "label": 1},
            ]
        ).to_csv(self.input_path, index=False)
        self.service = ValidationRunService(
            data_processing_service=DataProcessingService(),
            progress_tracking_service=ProgressTrackingService(self.pipeline_dir),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_claimed_validation_rows_mask_original_label(self) -> None:
        started = self.service.start_validation_run(
            input_path=str(self.input_path),
            output_dir=str(self.root / "validation-output"),
            batch_size=2,
        )

        claim = self.service.claim_next_validation_batch(started.run_id, "judge-a")

        self.assertEqual(claim.status, "claimed")
        self.assertEqual(len(claim.batch.rows), 2)
        self.assertEqual(claim.batch.rows[0].label, "")
        self.assertFalse(hasattr(claim.batch.rows[0], "masked_label"))

    def test_submit_validation_result_marks_accepted_rows(self) -> None:
        started = self.service.start_validation_run(
            input_path=str(self.input_path),
            output_dir=str(self.root / "validation-output"),
            batch_size=3,
        )
        claim = self.service.claim_next_validation_batch(started.run_id, "judge-a")

        submitted = self.service.submit_validation_result(
            run_id=started.run_id,
            agent_id="judge-a",
            batch_id=claim.batch.batch_id,
            verdicts=[
                {
                    "source_uid": 1,
                    "predicted_label": 1,
                    "reason": "Supported by premise.",
                },
                {
                    "source_uid": 2,
                    "predicted_label": 1,
                    "reason": "Predicted support.",
                },
                {
                    "source_uid": 3,
                    "predicted_label": 1,
                    "reason": "Supported by premise.",
                },
            ],
        )

        self.assertEqual(submitted.rows_validated, 3)
        self.assertEqual(submitted.accepted_count, 2)
        self.assertEqual(submitted.rejected_count, 1)
        self.assertEqual(submitted.progress.done_rows, 3)

    def test_submit_validation_result_matches_string_labels_to_numeric_gold(
        self,
    ) -> None:
        started = self.service.start_validation_run(
            input_path=str(self.input_path),
            output_dir=str(self.root / "validation-output"),
            batch_size=3,
        )
        claim = self.service.claim_next_validation_batch(started.run_id, "judge-a")

        submitted = self.service.submit_validation_result(
            run_id=started.run_id,
            agent_id="judge-a",
            batch_id=claim.batch.batch_id,
            verdicts=[
                {
                    "source_uid": 1,  # gold 1 = neutral
                    "predicted_label": "neutral",
                    "reason": "Tiền đề không đủ thông tin để xác nhận giả thuyết.",
                },
                {
                    "source_uid": 2,  # gold 0 = entailment
                    "predicted_label": "Entailment",
                    "reason": "Tiền đề hỗ trợ trực tiếp giả thuyết.",
                },
                {
                    "source_uid": 3,  # gold 1 = neutral, predicted lệch
                    "predicted_label": "contradiction",
                    "reason": "Giả thuyết mâu thuẫn với tiền đề.",
                },
            ],
        )

        self.assertEqual(submitted.accepted_count, 2)
        self.assertEqual(submitted.rejected_count, 1)

    def test_submit_validation_result_writes_intermediate_csv_under_data_batches(
        self,
    ) -> None:
        started = self.service.start_validation_run(
            input_path=str(self.input_path),
            output_dir=str(self.root / "validation-output"),
            batch_size=1,
        )
        claim = self.service.claim_next_validation_batch(started.run_id, "judge-a")

        submitted = self.service.submit_validation_result(
            run_id=started.run_id,
            agent_id="judge-a",
            batch_id=claim.batch.batch_id,
            verdicts=[
                {
                    "source_uid": 1,
                    "predicted_label": 1,
                    "reason": "Supported.",
                }
            ],
        )

        output_path = Path(submitted.output_path).resolve()
        self.assertTrue(
            output_path.is_relative_to(
                (self.root / "data" / "batches" / started.run_id).resolve()
            )
        )
        self.assertFalse(
            (self.pipeline_dir / "runs" / started.run_id / "outputs").exists()
        )

    def test_submit_validation_result_rejects_invalid_label(self) -> None:
        started = self.service.start_validation_run(
            input_path=str(self.input_path),
            output_dir=str(self.root / "validation-output"),
            batch_size=3,
        )
        claim = self.service.claim_next_validation_batch(started.run_id, "judge-a")

        with self.assertRaises(ValueError):
            self.service.submit_validation_result(
                run_id=started.run_id,
                agent_id="judge-a",
                batch_id=claim.batch.batch_id,
                verdicts=[
                    {
                        "source_uid": 1,
                        "predicted_label": "garbage",
                        "reason": "Invalid label.",
                    },
                    {
                        "source_uid": 2,
                        "predicted_label": "entailment",
                        "reason": "ok",
                    },
                    {
                        "source_uid": 3,
                        "predicted_label": "neutral",
                        "reason": "ok",
                    },
                ],
            )

    def test_submit_validation_result_raises_on_invalid_source_label(self) -> None:
        """Strict validation on hidden expected label must raise before writing output."""
        bad_input = self.root / "bad_labels.csv"
        pd.DataFrame(
            [
                {
                    "source_uid": 1,
                    "premise": "p1",
                    "hypothesis": "h1",
                    "label": "garbage",
                },
                {"source_uid": 2, "premise": "p2", "hypothesis": "h2", "label": 0},
            ]
        ).to_csv(bad_input, index=False)
        started = self.service.start_validation_run(
            input_path=str(bad_input),
            output_dir=str(self.root / "validation-output-bad"),
            batch_size=2,
        )
        claim = self.service.claim_next_validation_batch(started.run_id, "judge-a")
        output_path = (
            self.root
            / "data"
            / "batches"
            / started.run_id
            / f"{claim.batch.batch_id}.csv"
        )

        with self.assertRaises(ValueError):
            self.service.submit_validation_result(
                run_id=started.run_id,
                agent_id="judge-a",
                batch_id=claim.batch.batch_id,
                verdicts=[
                    {"source_uid": 1, "predicted_label": "entailment", "reason": "ok"},
                    {"source_uid": 2, "predicted_label": "neutral", "reason": "ok"},
                ],
            )

        self.assertFalse(
            output_path.exists(),
            "output must not be written when source label is invalid",
        )

    def test_submit_validation_result_rejects_rows_outside_claim(self) -> None:
        started = self.service.start_validation_run(
            input_path=str(self.input_path),
            output_dir=str(self.root / "validation-output"),
            batch_size=1,
        )
        claim = self.service.claim_next_validation_batch(started.run_id, "judge-a")

        with self.assertRaisesRegex(ValueError, "must match the claimed batch exactly"):
            self.service.submit_validation_result(
                run_id=started.run_id,
                agent_id="judge-a",
                batch_id=claim.batch.batch_id,
                verdicts=[
                    {
                        "source_uid": 999,
                        "predicted_label": 1,
                        "reason": "Wrong row.",
                    }
                ],
            )

    def test_finalize_writes_one_validation_results_output(self) -> None:
        started = self.service.start_validation_run(
            input_path=str(self.input_path),
            output_dir=str(self.root / "validation-output"),
            batch_size=3,
        )
        claim = self.service.claim_next_validation_batch(started.run_id, "judge-a")
        self.service.submit_validation_result(
            run_id=started.run_id,
            agent_id="judge-a",
            batch_id=claim.batch.batch_id,
            verdicts=[
                {
                    "source_uid": 1,
                    "predicted_label": 1,
                    "reason": "Supported.",
                },
                {
                    "source_uid": 2,
                    "predicted_label": 1,
                    "reason": "Mismatch.",
                },
                {
                    "source_uid": 3,
                    "predicted_label": 1,
                    "reason": "Supported.",
                },
            ],
        )

        finalized = self.service.finalize_validation_run(started.run_id)

        self.assertEqual(finalized.total_rows, 3)
        self.assertEqual(finalized.accepted_rows, 2)
        self.assertEqual(finalized.rejected_rows, 1)
        self.assertTrue(Path(finalized.output_path).exists())
        with Path(finalized.output_path).open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(
            list(rows[0].keys()),
            [
                "source_uid",
                "premise",
                "hypothesis",
                "expected_label",
                "predicted_label",
                "accepted",
                "reason",
            ],
        )
        self.assertEqual(rows[0]["reason"], "Supported.")
        self.assertEqual(rows[0]["accepted"], "True")
        self.assertEqual(rows[1]["accepted"], "False")
        self.assertFalse(
            (self.pipeline_dir / "runs" / started.run_id).exists(),
            "Successful finalize must remove local validation run state.",
        )
        self.assertFalse(
            (self.root / "data" / "batches" / started.run_id).exists(),
            "Successful finalize must remove local validation batch outputs.",
        )


if __name__ == "__main__":
    unittest.main()
