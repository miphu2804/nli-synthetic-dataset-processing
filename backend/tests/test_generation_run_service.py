import asyncio
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from src.services.dataset_reader_service import DatasetReaderService
from src.services.dataset_writer_service import DatasetWriterService
from src.services.generation_run_service import GenerationRunService
from src.services.progress_tracking_service import ProgressTrackingService


class GenerationRunServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.pipeline_dir = self.root / ".pipeline"
        self.input_path = self.root / "input.csv"
        dataframe = pd.DataFrame(
            [
                {"uid": 1, "premise": "p1", "hypothesis": "h1", "label": 0},
                {"uid": 2, "premise": "p2", "hypothesis": "h2", "label": 1},
                {"uid": 3, "premise": "p3", "hypothesis": "h3", "label": 2},
                {"uid": 4, "premise": "p4", "hypothesis": "h4", "label": 1},
            ]
        )
        dataframe.to_csv(self.input_path, index=False)
        self.service = GenerationRunService(
            dataset_reader_service=DatasetReaderService(),
            dataset_writer_service=DatasetWriterService(),
            progress_tracking_service=ProgressTrackingService(self.pipeline_dir),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_progress_verification_detects_duplicate_done_rows(self) -> None:
        started = self.service.start_generation_run(
            input_path=str(self.input_path),
            output_path=str(self.root / "output.csv"),
            batch_size=2,
        )
        claim = self.service.claim_next_batch(started.run_id, "agent-a")
        self.service.submit_batch_result(
            run_id=started.run_id,
            agent_id="agent-a",
            batch_id=claim.batch.batch_id,
            rows=[
                {
                    "source_uid": 1,
                    "premise": "vp1",
                    "hypothesis": "vh1",
                    "label": 0,
                },
                {
                    "source_uid": 2,
                    "premise": "vp2",
                    "hypothesis": "vh2",
                    "label": 1,
                },
            ],
        )

        progress_path = self.pipeline_dir / "runs" / started.run_id / "progress.jsonl"
        lines = progress_path.read_text(encoding="utf-8").splitlines()
        self.assertTrue(all("prev_hash" not in json.loads(line) for line in lines))
        row_done_index, row_done = next(
            (index, payload)
            for index, payload in (
                (index, json.loads(line)) for index, line in enumerate(lines)
            )
            if payload["event"] == "row.done"
        )
        duplicate = {**row_done, "id": "agent-a-duplicate"}
        lines.insert(
            row_done_index + 1,
            json.dumps(duplicate, ensure_ascii=False, separators=(",", ":")),
        )
        progress_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        verification = self.service.verify_progress_log(started.run_id)
        self.assertFalse(verification.ok)
        self.assertEqual(verification.duplicate_done_source_uids, ["1"])

    def test_claims_do_not_overlap_and_released_batch_can_be_reclaimed(self) -> None:
        started = self.service.start_generation_run(
            input_path=str(self.input_path),
            output_path=str(self.root / "output.csv"),
            batch_size=2,
        )
        first_claim = self.service.claim_next_batch(started.run_id, "agent-a")
        second_claim = self.service.claim_next_batch(started.run_id, "agent-b")

        first_uids = {row.source_uid for row in first_claim.batch.rows}
        second_uids = {row.source_uid for row in second_claim.batch.rows}
        self.assertTrue(first_uids.isdisjoint(second_uids))

        self.service.release_batch_claim(
            run_id=started.run_id,
            agent_id="agent-a",
            batch_id=first_claim.batch.batch_id,
            reason="retry",
        )
        reclaimed = self.service.claim_next_batch(started.run_id, "agent-c")
        reclaimed_uids = {row.source_uid for row in reclaimed.batch.rows}
        self.assertEqual(first_uids, reclaimed_uids)

    def test_submit_batch_rejects_rows_outside_claim(self) -> None:
        started = self.service.start_generation_run(
            input_path=str(self.input_path),
            output_path=str(self.root / "output.csv"),
            batch_size=2,
        )
        claim = self.service.claim_next_batch(started.run_id, "agent-a")
        with self.assertRaisesRegex(ValueError, "must match the claimed batch exactly"):
            self.service.submit_batch_result(
                run_id=started.run_id,
                agent_id="agent-a",
                batch_id=claim.batch.batch_id,
                rows=[
                    {
                        "source_uid": 999,
                        "premise": "bad",
                        "hypothesis": "bad",
                        "label": 0,
                    }
                ],
            )

    def test_submit_batch_rejects_changed_source_label(self) -> None:
        started = self.service.start_generation_run(
            input_path=str(self.input_path),
            output_path=str(self.root / "output.csv"),
            row_limit=1,
            batch_size=1,
        )
        claim = self.service.claim_next_batch(started.run_id, "agent-a")

        with self.assertRaisesRegex(ValueError, "label must match the source label"):
            self.service.submit_batch_result(
                run_id=started.run_id,
                agent_id="agent-a",
                batch_id=claim.batch.batch_id,
                rows=[
                    {
                        "source_uid": 1,
                        "premise": "vp1",
                        "hypothesis": "vh1",
                        "label": 2,
                    }
                ],
            )

    def test_submit_batch_writes_intermediate_csv_under_data_batches(self) -> None:
        started = self.service.start_generation_run(
            input_path=str(self.input_path),
            output_path=str(self.root / "output.csv"),
            row_limit=1,
            batch_size=1,
        )
        claim = self.service.claim_next_batch(started.run_id, "agent-a")

        submitted = self.service.submit_batch_result(
            run_id=started.run_id,
            agent_id="agent-a",
            batch_id=claim.batch.batch_id,
            rows=[
                {
                    "source_uid": 1,
                    "premise": "vp1",
                    "hypothesis": "vh1",
                    "label": 0,
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

    def test_partial_skip_writes_events_and_finalize_reconciles(self) -> None:
        started = self.service.start_generation_run(
            input_path=str(self.input_path),
            output_path=str(self.root / "output.csv"),
            batch_size=2,
        )
        claim_one = self.service.claim_next_batch(started.run_id, "agent-a")
        self.service.submit_batch_result(
            run_id=started.run_id,
            agent_id="agent-a",
            batch_id=claim_one.batch.batch_id,
            rows=[
                {
                    "source_uid": 1,
                    "premise": "vp1",
                    "hypothesis": "vh1",
                    "label": 0,
                }
            ],
            skipped_rows=[{"source_uid": 2, "reason": "fail", "retries": 3}],
        )
        claim_two = self.service.claim_next_batch(started.run_id, "agent-b")
        self.service.submit_batch_result(
            run_id=started.run_id,
            agent_id="agent-b",
            batch_id=claim_two.batch.batch_id,
            rows=[
                {
                    "source_uid": 3,
                    "premise": "vp3",
                    "hypothesis": "vh3",
                    "label": 2,
                },
                {
                    "source_uid": 4,
                    "premise": "vp4",
                    "hypothesis": "vh4",
                    "label": 1,
                },
            ],
        )

        finalized = self.service.finalize_generation_run(started.run_id)
        final_df = pd.read_csv(finalized.output_path)

        self.assertEqual(len(final_df), 3)
        self.assertEqual(finalized.progress.done_rows, 3)
        self.assertEqual(finalized.progress.skipped_rows, 1)
        self.assertFalse(
            (self.pipeline_dir / "runs" / started.run_id).exists(),
            "Successful finalize must remove local run state.",
        )
        self.assertFalse(
            (self.root / "data" / "batches" / started.run_id).exists(),
            "Successful finalize must remove local batch outputs.",
        )

    def test_finalize_can_merge_legacy_run_outputs(self) -> None:
        started = self.service.start_generation_run(
            input_path=str(self.input_path),
            output_path=str(self.root / "output.csv"),
            row_limit=1,
            batch_size=1,
        )
        claim = self.service.claim_next_batch(started.run_id, "agent-a")
        submitted = self.service.submit_batch_result(
            run_id=started.run_id,
            agent_id="agent-a",
            batch_id=claim.batch.batch_id,
            rows=[
                {
                    "source_uid": 1,
                    "premise": "vp1",
                    "hypothesis": "vh1",
                    "label": 0,
                }
            ],
        )
        legacy_dir = self.pipeline_dir / "runs" / started.run_id / "outputs"
        legacy_dir.mkdir(parents=True)
        legacy_output_path = legacy_dir / Path(submitted.output_path).name
        Path(submitted.output_path).replace(legacy_output_path)

        finalized = self.service.finalize_generation_run(started.run_id)

        final_df = pd.read_csv(finalized.output_path)
        self.assertEqual(len(final_df), 1)
        self.assertEqual(final_df.iloc[0]["premise"], "vp1")

    def test_all_skipped_rows_finalize_to_csv_with_expected_header(self) -> None:
        started = self.service.start_generation_run(
            input_path=str(self.input_path),
            output_path=str(self.root / "output.csv"),
            row_limit=2,
            batch_size=2,
        )
        claim = self.service.claim_next_batch(started.run_id, "agent-a")
        self.service.submit_batch_result(
            run_id=started.run_id,
            agent_id="agent-a",
            batch_id=claim.batch.batch_id,
            rows=[],
            skipped_rows=[
                {"source_uid": 1, "reason": "fail", "retries": 3},
                {"source_uid": 2, "reason": "fail", "retries": 3},
            ],
        )

        finalized = self.service.finalize_generation_run(started.run_id)
        final_df = pd.read_csv(finalized.output_path)

        self.assertEqual(
            list(final_df.columns),
            ["source_uid", "premise", "hypothesis", "label"],
        )
        self.assertTrue(final_df.empty)

    def test_finalize_rejects_pending_or_active_claims(self) -> None:
        started = self.service.start_generation_run(
            input_path=str(self.input_path),
            output_path=str(self.root / "output.csv"),
            batch_size=2,
        )
        self.service.claim_next_batch(started.run_id, "agent-a")
        with self.assertRaisesRegex(ValueError, "active claims"):
            self.service.finalize_generation_run(started.run_id)

    def test_finalize_keeps_local_run_state_when_verification_fails(self) -> None:
        started = self.service.start_generation_run(
            input_path=str(self.input_path),
            output_path=str(self.root / "output.csv"),
            row_limit=2,
            batch_size=2,
        )
        claim = self.service.claim_next_batch(started.run_id, "main")
        self.service.submit_batch_result(
            run_id=started.run_id,
            agent_id="main",
            batch_id=claim.batch.batch_id,
            rows=[
                {
                    "source_uid": 1,
                    "premise": "vp1",
                    "hypothesis": "vh1",
                    "label": 0,
                },
                {
                    "source_uid": 2,
                    "premise": "vp2",
                    "hypothesis": "vh2",
                    "label": 1,
                },
            ],
        )
        progress_path = self.pipeline_dir / "runs" / started.run_id / "progress.jsonl"
        lines = progress_path.read_text(encoding="utf-8").splitlines()
        row_done_index, row_done = next(
            (index, payload)
            for index, payload in (
                (index, json.loads(line)) for index, line in enumerate(lines)
            )
            if payload["event"] == "row.done"
        )
        duplicate = {**row_done, "id": "main-duplicate"}
        lines.insert(
            row_done_index + 1,
            json.dumps(duplicate, ensure_ascii=False, separators=(",", ":")),
        )
        progress_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "progress verification failed"):
            self.service.finalize_generation_run(started.run_id)

        self.assertTrue((self.pipeline_dir / "runs" / started.run_id).exists())

    def test_start_run_applies_row_offset_before_claiming_rows(self) -> None:
        started = self.service.start_generation_run(
            input_path=str(self.input_path),
            output_path=str(self.root / "output.csv"),
            row_offset=2,
            row_limit=2,
            batch_size=2,
        )

        claim = self.service.claim_next_batch(started.run_id, "main")

        self.assertEqual(started.row_offset, 2)
        self.assertEqual(started.total_target_rows, 2)
        self.assertEqual([row.source_uid for row in claim.batch.rows], [3, 4])

    def test_start_run_defaults_to_twenty_rows_per_batch(self) -> None:
        started = self.service.start_generation_run(
            input_path=str(self.input_path),
            output_path=str(self.root / "output.csv"),
        )

        self.assertEqual(started.batch_size, 20)

    def test_start_run_rejects_duplicate_source_uids_in_target_slice(self) -> None:
        pd.DataFrame(
            [
                {"uid": 1, "premise": "p1", "hypothesis": "h1", "label": 0},
                {"uid": 1, "premise": "p2", "hypothesis": "h2", "label": 1},
            ]
        ).to_csv(self.input_path, index=False)

        with self.assertRaisesRegex(ValueError, "duplicate source_uid"):
            self.service.start_generation_run(
                input_path=str(self.input_path),
                output_path=str(self.root / "output.csv"),
            )
