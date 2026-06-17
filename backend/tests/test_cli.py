import tempfile
import unittest
from pathlib import Path

import pandas as pd
from src.cli import (
    build_verdict_candidates,
    default_output_path,
    discover_dataset_files,
    discover_verdict_files,
    infer_uid_column,
    main,
    run_aggregation,
    run_pmi,
)


class ValidationMaskingCliTest(unittest.TestCase):
    def test_infer_uid_column_prefers_source_uid(self) -> None:
        self.assertEqual(infer_uid_column(["uid", "source_uid"]), "source_uid")
        self.assertEqual(infer_uid_column(["uid"]), "uid")
        self.assertIsNone(infer_uid_column(["id"]))

    def test_default_output_path_adds_validation_masked_suffix(self) -> None:
        self.assertEqual(
            default_output_path(Path("data/generated/foo.csv")),
            Path("data/generated/foo_validation_masked.csv"),
        )

    def test_discover_dataset_files_finds_csv_and_parquet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "nested").mkdir()
            (root / "a.csv").write_text("source_uid,premise,hypothesis,label\n")
            (root / "nested" / "b.parquet").write_text("")
            (root / "c.txt").write_text("")

            discovered = discover_dataset_files([root])

        self.assertEqual(
            sorted(path.name for path in discovered),
            ["a.csv", "b.parquet"],
        )

    def test_main_writes_masked_dataset_with_noninteractive_args(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "generated.csv"
            output_path = root / "masked.csv"
            pd.DataFrame(
                [
                    {
                        "source_uid": "row-1",
                        "premise": "p",
                        "hypothesis": "h",
                        "label": 1,
                    }
                ]
            ).to_csv(input_path, index=False)

            exit_code = main(
                [
                    "mask",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--yes",
                    "--quiet",
                ]
            )

            masked = pd.read_csv(output_path)
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            list(masked.columns),
            ["source_uid", "premise", "hypothesis", "masked_label"],
        )
        self.assertNotIn("label", masked.columns)


class ValidationAggregationCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.verdicts_dir = self.root / "verdicts"
        self.verdicts_dir.mkdir()
        self.output_dir = self.root / "output"
        self.masked_path = self.root / "masked.csv"
        self.expected_path = self.root / "expected.csv"

        pd.DataFrame(
            [
                {"source_uid": "row-1", "premise": "p1", "hypothesis": "khi nop thue"},
                {"source_uid": "row-2", "premise": "p2", "hypothesis": "du mien thue"},
            ]
        ).to_csv(self.masked_path, index=False)

        # row-1 expected entailment (both models predict entailment) -> keep
        # row-2 expected entailment (both models predict non-entailment) -> discard
        pd.DataFrame(
            [
                {
                    "source_uid": "row-1",
                    "premise": "p1",
                    "hypothesis": "khi nop thue",
                    "label": 0,
                },
                {
                    "source_uid": "row-2",
                    "premise": "p2",
                    "hypothesis": "du mien thue",
                    "label": 0,
                },
            ]
        ).to_csv(self.expected_path, index=False)
        self.expected_labels = {"row-1": 0, "row-2": 0}

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

    def test_run_aggregation_writes_votes_and_validated_dataset(self) -> None:
        paths = discover_verdict_files(self.verdicts_dir)
        valid_candidates = [c for c in build_verdict_candidates(paths) if c.is_valid]
        self.output_dir.mkdir()

        result = run_aggregation(
            valid_candidates=valid_candidates,
            masked_dataset_path=self.masked_path,
            output_dir=self.output_dir,
            expected_labels=self.expected_labels,
        )

        votes = pd.read_csv(result["votes_output"])
        self.assertEqual(len(votes), 2)
        self.assertIn("expected_label", votes.columns)
        self.assertIn("agree_count", votes.columns)
        self.assertIn("decision", votes.columns)
        self.assertEqual(set(votes["decision"]), {"keep", "discard"})
        self.assertEqual(result["total_rows"], 2)
        self.assertEqual(result["keep"], 1)
        self.assertEqual(result["discard"], 1)
        self.assertEqual(result["review"], 0)

        validated = pd.read_csv(result["validated_output"])
        self.assertEqual(
            list(validated.columns),
            ["source_uid", "premise", "hypothesis", "label"],
        )
        self.assertEqual(list(validated["source_uid"]), ["row-1"])
        self.assertEqual(validated.loc[0, "label"], 0)
        self.assertEqual(result["retained_rows"], 1)

    def test_main_noninteractive_run_exits_zero(self) -> None:
        exit_code = main(
            [
                "aggregate",
                "--verdicts-dir",
                str(self.verdicts_dir),
                "--masked-input",
                str(self.masked_path),
                "--expected-input",
                str(self.expected_path),
                "--label-column",
                "label",
                "--output-dir",
                str(self.output_dir),
                "--yes",
                "--quiet",
            ]
        )
        self.assertEqual(exit_code, 0)
        self.assertTrue((self.output_dir / "validation_votes.csv").exists())
        self.assertFalse((self.output_dir / "pmi_consensus.csv").exists())
        self.assertTrue((self.output_dir / "validated_dataset.csv").exists())

    def test_main_fails_with_missing_verdicts_dir(self) -> None:
        exit_code = main(
            [
                "aggregate",
                "--verdicts-dir",
                str(self.root / "nonexistent"),
                "--masked-input",
                str(self.masked_path),
                "--expected-input",
                str(self.expected_path),
                "--label-column",
                "label",
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
                "aggregate",
                "--verdicts-dir",
                str(lone_dir),
                "--masked-input",
                str(self.masked_path),
                "--expected-input",
                str(self.expected_path),
                "--label-column",
                "label",
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
                "aggregate",
                "--verdicts-dir",
                str(self.verdicts_dir),
                "--masked-input",
                str(self.root / "nonexistent.csv"),
                "--expected-input",
                str(self.expected_path),
                "--label-column",
                "label",
                "--output-dir",
                str(self.output_dir),
                "--yes",
                "--quiet",
            ]
        )
        self.assertEqual(exit_code, 2)


class ValidationPmiCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_path = self.root / "validated.csv"
        pd.DataFrame(
            [
                {
                    "source_uid": 1,
                    "hypothesis": "alpha shared",
                    "label": "entailment",
                },
                {
                    "source_uid": 2,
                    "hypothesis": "alpha shared",
                    "label": "entailment",
                },
                {
                    "source_uid": 3,
                    "hypothesis": "beta shared",
                    "label": "neutral",
                },
                {
                    "source_uid": 4,
                    "hypothesis": "beta shared",
                    "label": "neutral",
                },
            ]
        ).to_csv(self.input_path, index=False)
        self.output_dir = self.root / "pmi-out"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_run_pmi_writes_token_and_flagged_outputs(self) -> None:
        result = run_pmi(
            input_path=self.input_path,
            output_dir=self.output_dir,
            label_column="label",
            text_column="hypothesis",
            uid_column="source_uid",
            pmi_threshold=0.5,
            min_joint_count=1,
        )

        self.assertEqual(result["flagged_rows"], 4)
        self.assertEqual(result["artifact_tokens"], 2)
        self.assertTrue((self.output_dir / "pmi_artifact_tokens.csv").exists())
        self.assertTrue((self.output_dir / "pmi_flagged_rows.csv").exists())

    def test_main_pmi_subcommand_exits_zero(self) -> None:
        exit_code = main(
            [
                "pmi",
                "--input",
                str(self.input_path),
                "--output-dir",
                str(self.output_dir),
                "--pmi-threshold",
                "0.5",
                "--min-joint-count",
                "1",
                "--quiet",
            ]
        )
        self.assertEqual(exit_code, 0)

    def test_main_pmi_fails_on_missing_input(self) -> None:
        exit_code = main(["pmi", "--input", str(self.root / "nope.csv"), "--quiet"])
        self.assertEqual(exit_code, 2)


class ValidationKappaCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.verdicts_dir = self.root / "verdicts"
        self.verdicts_dir.mkdir()
        model_rows = {
            "gpt4o": [0, 1, 2, 0],
            "deepseek": [0, 1, 1, 0],
            "llama": [0, 2, 2, 1],
        }
        for model_name, labels in model_rows.items():
            pd.DataFrame(
                [
                    {
                        "source_uid": f"row-{index}",
                        "predicted_label": label,
                        "reason": "ok",
                    }
                    for index, label in enumerate(labels)
                ]
            ).to_csv(self.verdicts_dir / f"{model_name}.csv", index=False)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_main_kappa_subcommand_exits_zero(self) -> None:
        exit_code = main(["kappa", "--verdicts-dir", str(self.verdicts_dir), "--quiet"])
        self.assertEqual(exit_code, 0)

    def test_main_kappa_fails_on_missing_dir(self) -> None:
        exit_code = main(
            ["kappa", "--verdicts-dir", str(self.root / "nope"), "--quiet"]
        )
        self.assertEqual(exit_code, 2)

    def test_main_kappa_fails_with_only_one_valid_file(self) -> None:
        lone_dir = self.root / "lone"
        lone_dir.mkdir()
        pd.DataFrame(
            [{"source_uid": "row-0", "predicted_label": 0, "reason": "ok"}]
        ).to_csv(lone_dir / "only_one.csv", index=False)
        exit_code = main(["kappa", "--verdicts-dir", str(lone_dir), "--quiet"])
        self.assertEqual(exit_code, 2)


class ApplyParaphraseCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_path = self.root / "validated_dataset.csv"
        pd.DataFrame(
            [
                {
                    "source_uid": "row-1",
                    "premise": "p1",
                    "hypothesis": "h1",
                    "label": 0,
                },
                {
                    "source_uid": "row-2",
                    "premise": "p2",
                    "hypothesis": "h2",
                    "label": 1,
                },
            ]
        ).to_csv(self.input_path, index=False)
        self.paraphrases_path = self.root / "paraphrases.csv"
        pd.DataFrame([{"source_uid": "row-2", "hypothesis": "h2-rewritten"}]).to_csv(
            self.paraphrases_path, index=False
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_main_apply_paraphrase_writes_processed_dataset(self) -> None:
        exit_code = main(
            [
                "apply-paraphrase",
                "--input",
                str(self.input_path),
                "--paraphrases",
                str(self.paraphrases_path),
                "--quiet",
            ]
        )
        self.assertEqual(exit_code, 0)
        output_path = self.root / "processed_dataset.csv"
        self.assertTrue(output_path.exists())
        processed = pd.read_csv(output_path)
        self.assertEqual(list(processed["hypothesis"]), ["h1", "h2-rewritten"])

    def test_main_apply_paraphrase_fails_on_unknown_uid(self) -> None:
        pd.DataFrame([{"source_uid": "row-9", "hypothesis": "x"}]).to_csv(
            self.paraphrases_path, index=False
        )
        exit_code = main(
            [
                "apply-paraphrase",
                "--input",
                str(self.input_path),
                "--paraphrases",
                str(self.paraphrases_path),
                "--quiet",
            ]
        )
        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
