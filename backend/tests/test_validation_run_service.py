import csv
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.services.dataset_reader_service import DatasetReaderService
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
            dataset_reader_service=DatasetReaderService(),
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
        self.assertEqual(claim.batch.rows[0].masked_label, "[MASK]")
        self.assertFalse(hasattr(claim.batch.rows[0], "label"))

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
