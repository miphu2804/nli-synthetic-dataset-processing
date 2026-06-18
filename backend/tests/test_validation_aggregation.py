import math
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from src.utils.validation_aggregation import (
    apply_paraphrases,
    attach_masked_text,
    build_retained_dataset,
    build_review_dataset,
    build_validation_vote_table,
    compute_fleiss_kappa,
    compute_hypothesis_label_pmi,
    flag_pmi_artifacts,
)


class FlagPmiArtifactsTest(unittest.TestCase):
    def _dataset(self) -> pd.DataFrame:
        # "alpha" leaks entailment, "beta" leaks neutral, "shared" is balanced.
        return pd.DataFrame(
            [
                {
                    "source_uid": 1,
                    "hypothesis": "alpha shared",
                    "expected_label": "entailment",
                },
                {
                    "source_uid": 2,
                    "hypothesis": "alpha shared",
                    "expected_label": "entailment",
                },
                {
                    "source_uid": 3,
                    "hypothesis": "beta shared",
                    "expected_label": "neutral",
                },
                {
                    "source_uid": 4,
                    "hypothesis": "beta shared",
                    "expected_label": "neutral",
                },
            ]
        )

    def test_flags_label_leaking_tokens_and_rows(self) -> None:
        artifact_tokens, flagged_rows = flag_pmi_artifacts(
            self._dataset(),
            pmi_threshold=0.5,
            min_joint_count=1,
        )

        self.assertEqual(set(artifact_tokens["token"]), {"alpha", "beta"})
        self.assertNotIn("shared", set(artifact_tokens["token"]))
        self.assertEqual(len(flagged_rows), 4)
        row1 = flagged_rows.loc[flagged_rows["source_uid"] == 1].iloc[0]
        self.assertEqual(row1["artifact_tokens"], "alpha")

    def test_high_threshold_flags_nothing(self) -> None:
        artifact_tokens, flagged_rows = flag_pmi_artifacts(
            self._dataset(),
            pmi_threshold=10.0,
            min_joint_count=1,
        )

        self.assertEqual(len(artifact_tokens), 0)
        self.assertEqual(len(flagged_rows), 0)

    def test_missing_column_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            flag_pmi_artifacts(pd.DataFrame([{"source_uid": 1, "hypothesis": "x"}]))


class ValidationAggregationTest(unittest.TestCase):
    def test_build_validation_vote_table_merges_three_model_label_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model_paths = self._write_model_label_files(root)

            # row-1: all 3 predict 1, expected 1 -> 3 agree -> keep
            # row-2: predict 0,0,1, expected 2 -> 0 agree -> discard
            # row-3: predict 0,1,2, expected 1 -> 1 agree -> review
            expected_labels = {"row-1": 1, "row-2": 2, "row-3": 1}
            vote_table = build_validation_vote_table(model_paths, expected_labels)

        self.assertEqual(
            list(vote_table["source_uid"]),
            ["row-1", "row-2", "row-3"],
        )
        self.assertEqual(vote_table.loc[0, "gpt4o_label"], 1)

        self.assertEqual(vote_table.loc[0, "expected_label"], 1)
        self.assertEqual(vote_table.loc[0, "agree_count"], 3)
        self.assertEqual(vote_table.loc[0, "decision"], "keep")

        self.assertEqual(vote_table.loc[1, "expected_label"], 2)
        self.assertEqual(vote_table.loc[1, "agree_count"], 0)
        self.assertEqual(vote_table.loc[1, "decision"], "discard")

        self.assertEqual(vote_table.loc[2, "expected_label"], 1)
        self.assertEqual(vote_table.loc[2, "agree_count"], 1)
        self.assertEqual(vote_table.loc[2, "decision"], "review")

    def test_build_validation_vote_table_requires_same_source_uids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "gpt4o.csv"
            second = root / "deepseek.csv"
            pd.DataFrame([{"source_uid": "row-1", "predicted_label": 1}]).to_csv(
                first, index=False
            )
            pd.DataFrame([{"source_uid": "row-2", "predicted_label": 1}]).to_csv(
                second, index=False
            )

            with self.assertRaisesRegex(ValueError, "same source_uid set"):
                build_validation_vote_table(
                    {"gpt4o": first, "deepseek": second},
                    {"row-1": 1, "row-2": 1},
                )

    def test_compute_hypothesis_label_pmi_uses_masked_text_and_consensus(self) -> None:
        masked = pd.DataFrame(
            [
                {"source_uid": "row-1", "premise": "p", "hypothesis": "khi nop thue"},
                {"source_uid": "row-2", "premise": "p", "hypothesis": "khi khai thue"},
                {"source_uid": "row-3", "premise": "p", "hypothesis": "du mien thue"},
            ]
        )
        vote_table = pd.DataFrame(
            [
                {"source_uid": "row-1", "consensus_label": "1"},
                {"source_uid": "row-2", "consensus_label": "1"},
                {"source_uid": "row-3", "consensus_label": "0"},
            ]
        )

        pmi_table = compute_hypothesis_label_pmi(
            attach_masked_text(masked, vote_table),
            label_column="consensus_label",
        )

        khi_label_one = pmi_table[
            (pmi_table["token"] == "khi") & (pmi_table["label"] == "1")
        ].iloc[0]
        self.assertGreater(khi_label_one["pmi"], 0)
        self.assertEqual(khi_label_one["joint_count"], 2)

    def test_compute_hypothesis_label_pmi_counts_per_example_not_occurrence(
        self,
    ) -> None:
        # "x" repeats within one hypothesis; example-level PMI counts it once.
        dataframe = pd.DataFrame(
            [
                {"source_uid": "row-1", "hypothesis": "x x y", "label": "A"},
                {"source_uid": "row-2", "hypothesis": "y", "label": "B"},
            ]
        )

        pmi_table = compute_hypothesis_label_pmi(dataframe, label_column="label")

        x_row = pmi_table[
            (pmi_table["token"] == "x") & (pmi_table["label"] == "A")
        ].iloc[0]
        # occurrence-level counting would report token_count=2, joint_count=2.
        self.assertEqual(x_row["token_count"], 1)
        self.assertEqual(x_row["joint_count"], 1)
        # P(x,A)=1/2, P(x)=1/2, P(A)=1/2 -> PMI = log(2).
        self.assertAlmostEqual(x_row["pmi"], math.log(2))

    def test_build_retained_dataset_keeps_only_kept_rows(self) -> None:
        masked = pd.DataFrame(
            [
                {"source_uid": "row-1", "premise": "p1", "hypothesis": "h1"},
                {"source_uid": "row-2", "premise": "p2", "hypothesis": "h2"},
                {"source_uid": "row-3", "premise": "p3", "hypothesis": "h3"},
            ]
        )
        vote_table = pd.DataFrame(
            [
                {"source_uid": "row-1", "expected_label": 1, "decision": "keep"},
                {"source_uid": "row-2", "expected_label": 0, "decision": "discard"},
                {"source_uid": "row-3", "expected_label": 2, "decision": "review"},
            ]
        )

        retained = build_retained_dataset(masked, vote_table)

        self.assertEqual(
            list(retained.columns),
            ["source_uid", "premise", "hypothesis", "label"],
        )
        self.assertEqual(list(retained["source_uid"]), ["row-1"])
        self.assertEqual(retained.loc[0, "label"], 1)

    def test_build_review_dataset_keeps_only_review_rows(self) -> None:
        masked = pd.DataFrame(
            [
                {"source_uid": "row-1", "premise": "p1", "hypothesis": "h1"},
                {"source_uid": "row-2", "premise": "p2", "hypothesis": "h2"},
                {"source_uid": "row-3", "premise": "p3", "hypothesis": "h3"},
            ]
        )
        vote_table = pd.DataFrame(
            [
                {"source_uid": "row-1", "expected_label": 1, "decision": "keep"},
                {"source_uid": "row-2", "expected_label": 0, "decision": "review"},
                {"source_uid": "row-3", "expected_label": 2, "decision": "discard"},
            ]
        )

        review = build_review_dataset(masked, vote_table)

        self.assertEqual(list(review["source_uid"]), ["row-2"])
        # text columns lead, expected_label is preserved (not renamed to label)
        self.assertEqual(
            list(review.columns)[:3], ["source_uid", "premise", "hypothesis"]
        )
        self.assertIn("expected_label", review.columns)
        self.assertNotIn("label", review.columns)

    def test_build_review_dataset_raises_on_missing_masked_uid(self) -> None:
        masked = pd.DataFrame(
            [{"source_uid": "row-1", "premise": "p1", "hypothesis": "h1"}]
        )
        vote_table = pd.DataFrame(
            [{"source_uid": "row-2", "expected_label": 0, "decision": "review"}]
        )
        with self.assertRaisesRegex(ValueError, "row-2"):
            build_review_dataset(masked, vote_table)

    def test_build_retained_dataset_raises_on_missing_masked_uid(self) -> None:
        masked = pd.DataFrame(
            [{"source_uid": "row-1", "premise": "p1", "hypothesis": "h1"}]
        )
        vote_table = pd.DataFrame(
            [
                {"source_uid": "row-1", "expected_label": 1, "decision": "keep"},
                {"source_uid": "row-2", "expected_label": 0, "decision": "keep"},
            ]
        )
        with self.assertRaisesRegex(ValueError, "row-2"):
            build_retained_dataset(masked, vote_table)

    def test_build_retained_dataset_raises_on_duplicate_masked_uid(self) -> None:
        masked = pd.DataFrame(
            [
                {"source_uid": "row-1", "premise": "p1", "hypothesis": "h1"},
                {"source_uid": "row-1", "premise": "p1b", "hypothesis": "h1b"},
            ]
        )
        vote_table = pd.DataFrame(
            [{"source_uid": "row-1", "expected_label": 1, "decision": "keep"}]
        )
        with self.assertRaisesRegex(ValueError, "duplicate source_uid"):
            build_retained_dataset(masked, vote_table)

    def test_build_retained_dataset_requires_vote_columns(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            build_retained_dataset(
                pd.DataFrame(
                    [{"source_uid": "row-1", "premise": "p", "hypothesis": "h"}]
                ),
                pd.DataFrame([{"source_uid": "row-1"}]),
            )

    def test_apply_paraphrases_overwrites_only_flagged_rows(self) -> None:
        dataset = pd.DataFrame(
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
                {
                    "source_uid": "row-3",
                    "premise": "p3",
                    "hypothesis": "h3",
                    "label": 2,
                },
            ]
        )
        paraphrases = pd.DataFrame(
            [
                {"source_uid": "row-2", "hypothesis": "h2-rewritten"},
            ]
        )

        processed, replaced = apply_paraphrases(dataset, paraphrases)

        self.assertEqual(replaced, 1)
        self.assertEqual(list(processed.columns), list(dataset.columns))
        self.assertEqual(list(processed["hypothesis"]), ["h1", "h2-rewritten", "h3"])
        self.assertEqual(list(processed["label"]), [0, 1, 2])

    def test_apply_paraphrases_rejects_unknown_uid(self) -> None:
        dataset = pd.DataFrame([{"source_uid": "row-1", "hypothesis": "h1"}])
        paraphrases = pd.DataFrame([{"source_uid": "row-9", "hypothesis": "x"}])
        with self.assertRaisesRegex(ValueError, "unknown source_uid"):
            apply_paraphrases(dataset, paraphrases)

    def test_apply_paraphrases_rejects_duplicate_uid(self) -> None:
        dataset = pd.DataFrame([{"source_uid": "row-1", "hypothesis": "h1"}])
        paraphrases = pd.DataFrame(
            [
                {"source_uid": "row-1", "hypothesis": "a"},
                {"source_uid": "row-1", "hypothesis": "b"},
            ]
        )
        with self.assertRaisesRegex(ValueError, "duplicate source_uid"):
            apply_paraphrases(dataset, paraphrases)

    @staticmethod
    def _write_model_label_files(root: Path) -> dict[str, Path]:
        model_rows = {
            "gpt4o": [
                {"source_uid": "row-1", "predicted_label": 1},
                {"source_uid": "row-2", "predicted_label": 0},
                {"source_uid": "row-3", "predicted_label": 0},
            ],
            "deepseek": [
                {"source_uid": "row-1", "predicted_label": 1},
                {"source_uid": "row-2", "predicted_label": 0},
                {"source_uid": "row-3", "predicted_label": 1},
            ],
            "llama": [
                {"source_uid": "row-1", "predicted_label": 1},
                {"source_uid": "row-2", "predicted_label": 1},
                {"source_uid": "row-3", "predicted_label": 2},
            ],
        }
        paths = {}
        for model_name, rows in model_rows.items():
            path = root / f"{model_name}.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            paths[model_name] = path
        return paths


class ComputeFleissKappaTest(unittest.TestCase):
    @staticmethod
    def _write(root: Path, model_rows: dict[str, list[dict]]) -> dict[str, Path]:
        paths = {}
        for model_name, rows in model_rows.items():
            path = root / f"{model_name}.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            paths[model_name] = path
        return paths

    def test_perfect_agreement_returns_kappa_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Mix numeric and string forms that canonicalize equal.
            paths = self._write(
                root,
                {
                    "gpt4o": [
                        {"source_uid": "row-1", "predicted_label": "entailment"},
                        {"source_uid": "row-2", "predicted_label": "neutral"},
                        {"source_uid": "row-3", "predicted_label": "contradiction"},
                    ],
                    "deepseek": [
                        {"source_uid": "row-1", "predicted_label": 0},
                        {"source_uid": "row-2", "predicted_label": 1},
                        {"source_uid": "row-3", "predicted_label": 2},
                    ],
                    "llama": [
                        {"source_uid": "row-1", "predicted_label": "entailment"},
                        {"source_uid": "row-2", "predicted_label": 1},
                        {"source_uid": "row-3", "predicted_label": "contradiction"},
                    ],
                },
            )
            result = compute_fleiss_kappa(paths)
            self.assertAlmostEqual(result["kappa"], 1.0)
            self.assertEqual(result["n_items"], 3)
            self.assertEqual(result["n_raters"], 3)

    def test_partial_agreement_between_zero_and_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._write(
                root,
                {
                    "gpt4o": [
                        {"source_uid": "row-1", "predicted_label": 0},
                        {"source_uid": "row-2", "predicted_label": 1},
                        {"source_uid": "row-3", "predicted_label": 2},
                        {"source_uid": "row-4", "predicted_label": 0},
                    ],
                    "deepseek": [
                        {"source_uid": "row-1", "predicted_label": 0},
                        {"source_uid": "row-2", "predicted_label": 1},
                        {"source_uid": "row-3", "predicted_label": 1},
                        {"source_uid": "row-4", "predicted_label": 0},
                    ],
                    "llama": [
                        {"source_uid": "row-1", "predicted_label": 0},
                        {"source_uid": "row-2", "predicted_label": 2},
                        {"source_uid": "row-3", "predicted_label": 2},
                        {"source_uid": "row-4", "predicted_label": 1},
                    ],
                },
            )
            result = compute_fleiss_kappa(paths)
            self.assertGreater(result["kappa"], 0.0)
            self.assertLess(result["kappa"], 1.0)
            self.assertEqual(result["n_items"], 4)
            self.assertEqual(result["n_raters"], 3)

    def test_fewer_than_two_models_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._write(
                root,
                {
                    "gpt4o": [
                        {"source_uid": "row-1", "predicted_label": 0},
                    ],
                },
            )
            with self.assertRaises(ValueError):
                compute_fleiss_kappa(paths)


if __name__ == "__main__":
    unittest.main()
