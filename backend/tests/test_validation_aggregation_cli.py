import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.utils.validation_aggregation_cli import (
    build_verdict_candidates,
    discover_verdict_files,
    main,
    run_aggregation,
)


class ValidationAggregationCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.verdicts_dir = self.root / "verdicts"
        self.verdicts_dir.mkdir()
        self.output_dir = self.root / "output"
        self.masked_path = self.root / "masked.csv"

        pd.DataFrame(
            [
                {"source_uid": "row-1", "premise": "p1", "hypothesis": "khi nop thue"},
                {"source_uid": "row-2", "premise": "p2", "hypothesis": "du mien thue"},
            ]
        ).to_csv(self.masked_path, index=False)

        pd.DataFrame(
            [
                {
                    "source_uid": "row-1",
                    "predicted_label": "entailment",
                    "reason": "Supported.",
                },
                {
                    "source_uid": "row-2",
                    "predicted_label": "non-entailment",
                    "reason": "Not supported.",
                },
            ]
        ).to_csv(self.verdicts_dir / "gpt4o.csv", index=False)
        pd.DataFrame(
            [
                {
                    "source_uid": "row-1",
                    "predicted_label": "entailment",
                    "reason": "Supported.",
                },
                {
                    "source_uid": "row-2",
                    "predicted_label": "non-entailment",
                    "reason": "Not supported.",
                },
            ]
        ).to_csv(self.verdicts_dir / "deepseek.csv", index=False)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_discover_verdict_files_finds_csv_files(self) -> None:
        found = discover_verdict_files(self.verdicts_dir)
        self.assertEqual(sorted(p.name for p in found), ["deepseek.csv", "gpt4o.csv"])

    def test_discover_verdict_files_returns_empty_for_missing_dir(self) -> None:
        self.assertEqual(discover_verdict_files(self.root / "nonexistent"), [])

    def test_build_verdict_candidates_marks_valid_and_invalid_files(self) -> None:
        bad = self.verdicts_dir / "bad.csv"
        pd.DataFrame([{"only_col": 1}]).to_csv(bad, index=False)

        paths = discover_verdict_files(self.verdicts_dir)
        candidates = build_verdict_candidates(paths)
        valid_names = {c.model_name for c in candidates if c.is_valid}
        invalid_names = {c.model_name for c in candidates if not c.is_valid}
        self.assertEqual(valid_names, {"gpt4o", "deepseek"})
        self.assertEqual(invalid_names, {"bad"})

    def test_build_verdict_candidates_infers_model_name_from_stem(self) -> None:
        paths = discover_verdict_files(self.verdicts_dir)
        candidates = build_verdict_candidates(paths)
        self.assertEqual(
            sorted(c.model_name for c in candidates), ["deepseek", "gpt4o"]
        )

    def test_run_aggregation_writes_votes_and_pmi(self) -> None:
        paths = discover_verdict_files(self.verdicts_dir)
        valid_candidates = [c for c in build_verdict_candidates(paths) if c.is_valid]
        self.output_dir.mkdir()

        result = run_aggregation(
            valid_candidates=valid_candidates,
            masked_dataset_path=self.masked_path,
            output_dir=self.output_dir,
            min_joint_count=1,
        )

        votes = pd.read_csv(result["votes_output"])
        self.assertEqual(len(votes), 2)
        self.assertIn("consensus_label", votes.columns)
        self.assertIn("agreement_status", votes.columns)
        self.assertTrue(all(votes["agreement_status"] == "unanimous"))
        self.assertTrue(Path(result["pmi_output"]).exists())
        self.assertEqual(result["total_rows"], 2)
        self.assertEqual(result["unanimous"], 2)
        self.assertEqual(result["majority"], 0)
        self.assertEqual(result["review"], 0)

    def test_run_aggregation_pmi_filters_by_min_joint_count(self) -> None:
        paths = discover_verdict_files(self.verdicts_dir)
        valid_candidates = [c for c in build_verdict_candidates(paths) if c.is_valid]
        self.output_dir.mkdir()

        result_loose = run_aggregation(
            valid_candidates=valid_candidates,
            masked_dataset_path=self.masked_path,
            output_dir=self.output_dir,
            min_joint_count=1,
        )
        result_strict = run_aggregation(
            valid_candidates=valid_candidates,
            masked_dataset_path=self.masked_path,
            output_dir=self.output_dir,
            min_joint_count=999,
        )
        self.assertGreater(result_loose["pmi_tokens"], result_strict["pmi_tokens"])

    def test_main_noninteractive_run_exits_zero(self) -> None:
        exit_code = main(
            [
                "--verdicts-dir",
                str(self.verdicts_dir),
                "--masked-input",
                str(self.masked_path),
                "--output-dir",
                str(self.output_dir),
                "--min-joint-count",
                "1",
                "--yes",
                "--quiet",
            ]
        )
        self.assertEqual(exit_code, 0)
        self.assertTrue((self.output_dir / "validation_votes.csv").exists())
        self.assertTrue((self.output_dir / "pmi_consensus.csv").exists())

    def test_main_fails_with_missing_verdicts_dir(self) -> None:
        exit_code = main(
            [
                "--verdicts-dir",
                str(self.root / "nonexistent"),
                "--masked-input",
                str(self.masked_path),
                "--output-dir",
                str(self.output_dir),
                "--yes",
                "--quiet",
            ]
        )
        self.assertEqual(exit_code, 2)

    def test_main_fails_with_only_one_valid_verdict_file(self) -> None:
        lone_dir = self.root / "lone"
        lone_dir.mkdir()
        pd.DataFrame(
            [
                {
                    "source_uid": "row-1",
                    "predicted_label": "entailment",
                    "reason": "Supported.",
                }
            ]
        ).to_csv(lone_dir / "only_one.csv", index=False)

        exit_code = main(
            [
                "--verdicts-dir",
                str(lone_dir),
                "--masked-input",
                str(self.masked_path),
                "--output-dir",
                str(self.output_dir),
                "--yes",
                "--quiet",
            ]
        )
        self.assertEqual(exit_code, 2)

    def test_main_fails_with_missing_masked_input(self) -> None:
        exit_code = main(
            [
                "--verdicts-dir",
                str(self.verdicts_dir),
                "--masked-input",
                str(self.root / "nonexistent.csv"),
                "--output-dir",
                str(self.output_dir),
                "--yes",
                "--quiet",
            ]
        )
        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
