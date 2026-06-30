import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.cli import (
    build_verdict_candidates,
    default_consensus_output_dir,
    default_output_path,
    discover_dataset_files,
    discover_verdict_files,
    infer_uid_column,
    main,
    run_aggregation,
    run_consensus_pmi,
    run_pmi,
    run_promote_paraphrase,
    run_split,
)
from src.utils.project_paths import resolve_data_path


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

            masked = pd.read_csv(output_path, keep_default_na=False)
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            list(masked.columns),
            ["source_uid", "premise", "hypothesis", "label"],
        )
        self.assertEqual(masked.to_dict(orient="records")[0]["label"], "")


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
                    "predicted_label": "contradiction",
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
                    "predicted_label": "contradiction",
                    "reason": "Not supported.",
                },
            ]
        ).to_csv(self.verdicts_dir / "deepseek.csv", index=False)
        pd.DataFrame(
            [
                {
                    "source_uid": "row-1",
                    "predicted_label": "entailment",
                    "reason": "Supported.",
                },
                {
                    "source_uid": "row-2",
                    "predicted_label": "neutral",
                    "reason": "Unclear.",
                },
            ]
        ).to_csv(self.verdicts_dir / "llama.csv", index=False)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_discover_verdict_files_finds_csv_files(self) -> None:
        found = discover_verdict_files(self.verdicts_dir)
        self.assertEqual(
            sorted(p.name for p in found),
            ["deepseek.csv", "gpt4o.csv", "llama.csv"],
        )

    def test_discover_verdict_files_returns_empty_for_missing_dir(self) -> None:
        self.assertEqual(discover_verdict_files(self.root / "nonexistent"), [])

    def test_build_verdict_candidates_marks_valid_and_invalid_files(self) -> None:
        bad = self.verdicts_dir / "bad.csv"
        pd.DataFrame([{"only_col": 1}]).to_csv(bad, index=False)

        paths = discover_verdict_files(self.verdicts_dir)
        candidates = build_verdict_candidates(paths)
        valid_names = {c.model_name for c in candidates if c.is_valid}
        invalid_names = {c.model_name for c in candidates if not c.is_valid}
        self.assertEqual(valid_names, {"gpt4o", "deepseek", "llama"})
        self.assertEqual(invalid_names, {"bad"})

    def test_build_verdict_candidates_infers_model_name_from_stem(self) -> None:
        paths = discover_verdict_files(self.verdicts_dir)
        candidates = build_verdict_candidates(paths)
        self.assertEqual(
            sorted(c.model_name for c in candidates), ["deepseek", "gpt4o", "llama"]
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

    def test_main_fails_with_only_two_valid_verdict_files(self) -> None:
        two_dir = self.root / "two"
        two_dir.mkdir()
        for name in ("alpha", "beta"):
            pd.DataFrame(
                [
                    {
                        "source_uid": "row-1",
                        "predicted_label": "entailment",
                        "reason": "ok",
                    },
                    {
                        "source_uid": "row-2",
                        "predicted_label": "neutral",
                        "reason": "ok",
                    },
                ]
            ).to_csv(two_dir / f"{name}.csv", index=False)

        exit_code = main(
            [
                "aggregate",
                "--verdicts-dir",
                str(two_dir),
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

    def test_run_aggregation_raises_on_masked_uid_mismatch(self) -> None:
        """masked_dataset must cover ALL rows including discarded ones."""
        paths = discover_verdict_files(self.verdicts_dir)
        valid_candidates = [c for c in build_verdict_candidates(paths) if c.is_valid]
        self.output_dir.mkdir()

        # Write a masked dataset that is missing row-2 (a discard row).
        incomplete_masked = self.root / "incomplete_masked.csv"
        pd.DataFrame(
            [{"source_uid": "row-1", "premise": "p1", "hypothesis": "khi nop thue"}]
        ).to_csv(incomplete_masked, index=False)

        with self.assertRaises(ValueError):
            run_aggregation(
                valid_candidates=valid_candidates,
                masked_dataset_path=incomplete_masked,
                output_dir=self.output_dir,
                expected_labels=self.expected_labels,
            )

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

    def test_default_consensus_output_dir_uses_expected_input_stem(self) -> None:
        self.assertEqual(
            default_consensus_output_dir(Path("data/generated/foo.csv")),
            resolve_data_path("validated", "foo"),
        )

    def test_run_consensus_pmi_writes_all_artifacts(self) -> None:
        paths = discover_verdict_files(self.verdicts_dir)
        valid_candidates = [c for c in build_verdict_candidates(paths) if c.is_valid]
        self.output_dir.mkdir()

        result = run_consensus_pmi(
            valid_candidates=valid_candidates,
            masked_dataset_path=self.masked_path,
            expected_input_path=self.expected_path,
            output_dir=self.output_dir,
            uid_column="source_uid",
            label_column="label",
            text_column="hypothesis",
            pmi_threshold=0.0,
            min_joint_count=1,
        )

        self.assertTrue((self.output_dir / "validation_votes.csv").exists())
        self.assertTrue((self.output_dir / "validated_dataset.csv").exists())
        self.assertTrue((self.output_dir / "review_dataset.csv").exists())
        self.assertTrue((self.output_dir / "pmi_artifact_tokens.csv").exists())
        self.assertTrue((self.output_dir / "pmi_flagged_rows.csv").exists())
        self.assertEqual(result["keep"], 1)
        self.assertEqual(result["pmi_total_rows"], 1)

    def test_main_consensus_pmi_subcommand_exits_zero(self) -> None:
        exit_code = main(
            [
                "consensus-pmi",
                "--verdicts-dir",
                str(self.verdicts_dir),
                "--masked-input",
                str(self.masked_path),
                "--expected-input",
                str(self.expected_path),
                "--output-dir",
                str(self.output_dir),
                "--pmi-threshold",
                "0.0",
                "--min-joint-count",
                "1",
                "--yes",
                "--quiet",
            ]
        )
        self.assertEqual(exit_code, 0)
        self.assertTrue((self.output_dir / "validation_votes.csv").exists())
        self.assertTrue((self.output_dir / "pmi_flagged_rows.csv").exists())


class AggregationOutputSafetyTest(unittest.TestCase):
    """Validation failures must not create or overwrite final aggregate outputs."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.verdicts_dir = self.root / "verdicts"
        self.verdicts_dir.mkdir()
        self.output_dir = self.root / "output"
        self.output_dir.mkdir()
        self.masked_path = self.root / "masked.csv"
        self.expected_path = self.root / "expected.csv"

        pd.DataFrame(
            [
                {"source_uid": "row-1", "premise": "p1", "hypothesis": "h1"},
                {"source_uid": "row-2", "premise": "p2", "hypothesis": "h2"},
            ]
        ).to_csv(self.masked_path, index=False)
        pd.DataFrame(
            [
                {"source_uid": "row-1", "label": 0},
                {"source_uid": "row-2", "label": 0},
            ]
        ).to_csv(self.expected_path, index=False)

        for name in ("gpt4o", "deepseek", "llama"):
            pd.DataFrame(
                [
                    {
                        "source_uid": "row-1",
                        "predicted_label": "entailment",
                        "reason": "ok",
                    },
                    {
                        "source_uid": "row-2",
                        "predicted_label": "contradiction",
                        "reason": "ok",
                    },
                ]
            ).to_csv(self.verdicts_dir / f"{name}.csv", index=False)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_validation_failure_leaves_no_output_files(self) -> None:
        # Use an invalid masked dataset (empty) to trigger a failure.
        bad_masked = self.root / "bad_masked.csv"
        pd.DataFrame([{"wrong_col": 1}]).to_csv(bad_masked, index=False)

        exit_code = main(
            [
                "aggregate",
                "--verdicts-dir",
                str(self.verdicts_dir),
                "--masked-input",
                str(bad_masked),
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
        self.assertFalse((self.output_dir / "validation_votes.csv").exists())
        self.assertFalse((self.output_dir / "validated_dataset.csv").exists())
        self.assertFalse((self.output_dir / "review_dataset.csv").exists())

    def test_validation_failure_does_not_overwrite_existing_outputs(self) -> None:
        sentinel_content = "source_uid,label\nold-row,entailment\n"
        for fname in (
            "validation_votes.csv",
            "validated_dataset.csv",
            "review_dataset.csv",
        ):
            (self.output_dir / fname).write_text(sentinel_content)

        bad_masked = self.root / "bad_masked.csv"
        pd.DataFrame([{"wrong_col": 1}]).to_csv(bad_masked, index=False)

        exit_code = main(
            [
                "aggregate",
                "--verdicts-dir",
                str(self.verdicts_dir),
                "--masked-input",
                str(bad_masked),
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
        for fname in (
            "validation_votes.csv",
            "validated_dataset.csv",
            "review_dataset.csv",
        ):
            self.assertEqual((self.output_dir / fname).read_text(), sentinel_content)


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
        self.flagged_rows_path = self.root / "flagged_rows.csv"
        pd.DataFrame([{"source_uid": "row-2", "artifact_tokens": "cue"}]).to_csv(
            self.flagged_rows_path, index=False
        )
        self.paraphrases_path = self.root / "paraphrases.csv"
        pd.DataFrame([{"source_uid": "row-2", "hypothesis": "h2-rewritten"}]).to_csv(
            self.paraphrases_path, index=False
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_main_apply_paraphrase_writes_paraphrased_dataset_and_revalidation(
        self,
    ) -> None:
        exit_code = main(
            [
                "apply-paraphrase",
                "--input",
                str(self.input_path),
                "--flagged-rows",
                str(self.flagged_rows_path),
                "--paraphrases",
                str(self.paraphrases_path),
                "--quiet",
            ]
        )
        self.assertEqual(exit_code, 0)
        output_path = self.root / "paraphrased_dataset.csv"
        self.assertTrue(output_path.exists())
        processed = pd.read_csv(output_path)
        self.assertEqual(list(processed["hypothesis"]), ["h1", "h2-rewritten"])
        revalidation_path = self.root / "paraphrase_revalidation_masked.csv"
        self.assertTrue(revalidation_path.exists())
        revalidation = pd.read_csv(revalidation_path, keep_default_na=False)
        self.assertEqual(list(revalidation["source_uid"]), ["row-2"])
        self.assertEqual(list(revalidation["label"]), [""])

    def test_main_apply_paraphrase_fails_on_unknown_uid(self) -> None:
        flagged_path = self.root / "flagged_unknown.csv"
        pd.DataFrame([{"source_uid": "row-9", "artifact_tokens": "x"}]).to_csv(
            flagged_path, index=False
        )
        pd.DataFrame([{"source_uid": "row-9", "hypothesis": "x-new"}]).to_csv(
            self.paraphrases_path, index=False
        )
        exit_code = main(
            [
                "apply-paraphrase",
                "--input",
                str(self.input_path),
                "--flagged-rows",
                str(flagged_path),
                "--paraphrases",
                str(self.paraphrases_path),
                "--quiet",
            ]
        )
        self.assertEqual(exit_code, 2)


class PromoteParaphraseCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_path = self.root / "paraphrased_dataset.csv"
        self.revalidation_path = self.root / "paraphrase_revalidation_masked.csv"
        self.expected_path = self.root / "validated_dataset.csv"
        self.verdicts_dir = self.root / "verdicts"
        self.verdicts_dir.mkdir()
        pd.DataFrame(
            [
                {
                    "source_uid": "row-1",
                    "premise": "p1",
                    "hypothesis": "h1",
                    "label": "entailment",
                },
                {
                    "source_uid": "row-2",
                    "premise": "p2",
                    "hypothesis": "h2-rewritten",
                    "label": "neutral",
                },
                {
                    "source_uid": "row-3",
                    "premise": "p3",
                    "hypothesis": "h3-rewritten",
                    "label": "contradiction",
                },
            ]
        ).to_csv(self.input_path, index=False)
        pd.DataFrame(
            [
                {
                    "source_uid": "row-1",
                    "premise": "p1",
                    "hypothesis": "h1",
                    "label": "entailment",
                },
                {
                    "source_uid": "row-2",
                    "premise": "p2",
                    "hypothesis": "h2",
                    "label": "neutral",
                },
                {
                    "source_uid": "row-3",
                    "premise": "p3",
                    "hypothesis": "h3",
                    "label": "contradiction",
                },
            ]
        ).to_csv(self.expected_path, index=False)
        pd.DataFrame(
            [
                {
                    "source_uid": "row-2",
                    "premise": "p2",
                    "hypothesis": "h2-rewritten",
                    "label": "",
                },
                {
                    "source_uid": "row-3",
                    "premise": "p3",
                    "hypothesis": "h3-rewritten",
                    "label": "",
                },
            ]
        ).to_csv(self.revalidation_path, index=False)
        labels_by_model = {
            "gpt4o": {"row-2": "neutral", "row-3": "entailment"},
            "deepseek": {"row-2": "neutral", "row-3": "neutral"},
            "llama": {"row-2": "entailment", "row-3": "contradiction"},
        }
        for model_name, labels in labels_by_model.items():
            pd.DataFrame(
                [
                    {
                        "source_uid": source_uid,
                        "predicted_label": label,
                        "reason": "ok",
                    }
                    for source_uid, label in labels.items()
                ]
            ).to_csv(self.verdicts_dir / f"{model_name}.csv", index=False)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_run_promote_paraphrase_writes_outputs(self) -> None:
        valid_candidates = [
            candidate
            for candidate in build_verdict_candidates(
                discover_verdict_files(self.verdicts_dir)
            )
            if candidate.is_valid
        ]
        output_path = self.root / "promoted_dataset.csv"
        review_output_path = self.root / "paraphrase_revalidation_review.csv"
        votes_output_path = self.root / "paraphrase_revalidation_votes.csv"

        result = run_promote_paraphrase(
            input_path=self.input_path,
            revalidation_input_path=self.revalidation_path,
            verdict_candidates=valid_candidates,
            expected_input_path=self.expected_path,
            output_path=output_path,
            review_output_path=review_output_path,
            votes_output_path=votes_output_path,
            uid_column="source_uid",
            label_column="label",
        )

        promoted = pd.read_csv(output_path)
        review = pd.read_csv(review_output_path)
        votes = pd.read_csv(votes_output_path)
        self.assertEqual(list(promoted["source_uid"]), ["row-1", "row-2"])
        self.assertEqual(list(review["source_uid"]), ["row-3"])
        self.assertEqual(set(votes["decision"]), {"keep", "review"})
        self.assertEqual(result["accepted_rewrites"], 1)
        self.assertEqual(result["review_rewrites"], 1)

    def test_main_promote_paraphrase_subcommand_exits_zero(self) -> None:
        exit_code = main(
            [
                "promote-paraphrase",
                "--input",
                str(self.input_path),
                "--revalidation-input",
                str(self.revalidation_path),
                "--verdicts-dir",
                str(self.verdicts_dir),
                "--expected-input",
                str(self.expected_path),
                "--quiet",
            ]
        )
        self.assertEqual(exit_code, 0)
        promoted = pd.read_csv(self.root / "promoted_dataset.csv")
        self.assertEqual(list(promoted["source_uid"]), ["row-1", "row-2"])
        self.assertTrue((self.root / "paraphrase_revalidation_review.csv").exists())
        self.assertTrue((self.root / "paraphrase_revalidation_votes.csv").exists())

    def test_main_promote_paraphrase_fails_with_two_verdict_files(self) -> None:
        (self.verdicts_dir / "llama.csv").unlink()
        exit_code = main(
            [
                "promote-paraphrase",
                "--input",
                str(self.input_path),
                "--revalidation-input",
                str(self.revalidation_path),
                "--verdicts-dir",
                str(self.verdicts_dir),
                "--expected-input",
                str(self.expected_path),
                "--quiet",
            ]
        )
        self.assertEqual(exit_code, 2)


class DatasetSplitCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_path = self.root / "promoted_dataset.csv"
        self.output_dir = self.root / "split"
        pd.DataFrame(
            [
                {
                    "source_uid": "1a",
                    "premise": "p1",
                    "hypothesis": "h1",
                    "label": 0,
                    "domain": "tax",
                },
                {
                    "source_uid": "1b",
                    "premise": "p1",
                    "hypothesis": "h2",
                    "label": 1,
                    "domain": "tax",
                },
                {
                    "source_uid": "2a",
                    "premise": "p2",
                    "hypothesis": "h3",
                    "label": 0,
                    "domain": "labor",
                },
                {
                    "source_uid": "3a",
                    "premise": "p3",
                    "hypothesis": "h4",
                    "label": 1,
                    "domain": "labor",
                },
                {
                    "source_uid": "4a",
                    "premise": "p4",
                    "hypothesis": "h5",
                    "label": 2,
                    "domain": "tax",
                },
                {
                    "source_uid": "5a",
                    "premise": "p5",
                    "hypothesis": "h6",
                    "label": 2,
                    "domain": "labor",
                },
            ]
        ).to_csv(self.input_path, index=False)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_run_split_writes_csvs_and_manifest(self) -> None:
        result = run_split(
            input_path=self.input_path,
            output_dir=self.output_dir,
            group_column="premise",
            label_column="label",
            domain_column="domain",
            train_ratio=0.6,
            dev_ratio=0.2,
            test_ratio=0.2,
            seed=11,
        )

        self.assertTrue(result["train_output"].exists())
        self.assertTrue(result["dev_output"].exists())
        self.assertTrue(result["test_output"].exists())
        self.assertTrue(result["manifest_output"].exists())
        manifest = json.loads(result["manifest_output"].read_text())
        self.assertEqual(manifest["total_rows"], 6)
        self.assertEqual(manifest["total_groups"], 5)
        self.assertEqual(manifest["strategy"], "grouped-stratified")
        self.assertEqual(manifest["domain"]["status"], "used")

    def test_main_split_subcommand_exits_zero_and_groups_by_premise(self) -> None:
        exit_code = main(
            [
                "split",
                "--input",
                str(self.input_path),
                "--output-dir",
                str(self.output_dir),
                "--train-ratio",
                "0.6",
                "--dev-ratio",
                "0.2",
                "--test-ratio",
                "0.2",
                "--domain-column",
                "domain",
                "--seed",
                "11",
                "--quiet",
            ]
        )

        self.assertEqual(exit_code, 0)
        splits = {
            name: pd.read_csv(self.output_dir / f"{name}.csv")
            for name in ("train", "dev", "test")
        }
        premise_sets = {
            name: set(split["premise"])
            for name, split in splits.items()
            if not split.empty
        }
        self.assertTrue(premise_sets["train"].isdisjoint(premise_sets["dev"]))
        self.assertTrue(premise_sets["train"].isdisjoint(premise_sets["test"]))
        self.assertTrue(premise_sets["dev"].isdisjoint(premise_sets["test"]))
        self.assertTrue((self.output_dir / "split_manifest.json").exists())
        manifest = json.loads((self.output_dir / "split_manifest.json").read_text())
        self.assertEqual(manifest["strategy"], "grouped-stratified")
        self.assertEqual(manifest["domain"]["status"], "used")
        self.assertEqual(
            sum(manifest["splits"]["train"]["label_distribution"].values()),
            len(splits["train"]),
        )
        self.assertIn("domain_distribution", manifest["splits"]["train"])

    def test_main_split_fails_on_invalid_ratios(self) -> None:
        exit_code = main(
            [
                "split",
                "--input",
                str(self.input_path),
                "--output-dir",
                str(self.output_dir),
                "--train-ratio",
                "0.7",
                "--dev-ratio",
                "0.2",
                "--test-ratio",
                "0.2",
                "--quiet",
            ]
        )

        self.assertEqual(exit_code, 2)
        self.assertFalse((self.output_dir / "train.csv").exists())


if __name__ == "__main__":
    unittest.main()
