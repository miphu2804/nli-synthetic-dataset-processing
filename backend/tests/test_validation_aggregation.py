import math
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from src.utils.nli_labels import require_canonical_label
from src.utils.validation_aggregation import (
    apply_paraphrases,
    attach_masked_text,
    build_retained_dataset,
    build_review_dataset,
    build_validation_vote_table,
    compute_fleiss_kappa,
    compute_hypothesis_label_pmi,
    flag_pmi_artifacts,
    promote_revalidated_paraphrases,
)


class RequireCanonicalLabelTest(unittest.TestCase):
    def test_accepts_numeric_forms(self) -> None:
        self.assertEqual(require_canonical_label(0), "entailment")
        self.assertEqual(require_canonical_label("1"), "neutral")
        self.assertEqual(require_canonical_label(2), "contradiction")

    def test_accepts_canonical_names(self) -> None:
        self.assertEqual(require_canonical_label("entailment"), "entailment")
        self.assertEqual(require_canonical_label("neutral"), "neutral")
        self.assertEqual(require_canonical_label("contradiction"), "contradiction")

    def test_rejects_unknown_label(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported NLI label"):
            require_canonical_label("garbage")

    def test_rejects_non_entailment(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported NLI label"):
            require_canonical_label("non-entailment")

    def test_rejects_empty_string(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported NLI label"):
            require_canonical_label("")


class InvalidLabelAggregationTest(unittest.TestCase):
    def test_vote_table_rejects_invalid_model_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p1 = root / "model1.csv"
            p2 = root / "model2.csv"
            pd.DataFrame(
                [{"source_uid": "r1", "predicted_label": "garbage", "reason": "ok"}]
            ).to_csv(p1, index=False)
            pd.DataFrame(
                [{"source_uid": "r1", "predicted_label": "entailment", "reason": "ok"}]
            ).to_csv(p2, index=False)
            with self.assertRaisesRegex(ValueError, "Unsupported NLI label"):
                build_validation_vote_table({"m1": p1, "m2": p2}, {"r1": "entailment"})

    def test_vote_table_rejects_invalid_expected_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p1 = root / "m1.csv"
            p2 = root / "m2.csv"
            for p in (p1, p2):
                pd.DataFrame(
                    [
                        {
                            "source_uid": "r1",
                            "predicted_label": "entailment",
                            "reason": "ok",
                        }
                    ]
                ).to_csv(p, index=False)
            with self.assertRaisesRegex(ValueError, "Unsupported NLI label"):
                build_validation_vote_table({"m1": p1, "m2": p2}, {"r1": "garbage"})

    def test_kappa_rejects_invalid_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p1 = root / "m1.csv"
            p2 = root / "m2.csv"
            pd.DataFrame(
                [{"source_uid": "r1", "predicted_label": "garbage", "reason": "ok"}]
            ).to_csv(p1, index=False)
            pd.DataFrame(
                [{"source_uid": "r1", "predicted_label": "entailment", "reason": "ok"}]
            ).to_csv(p2, index=False)
            with self.assertRaisesRegex(ValueError, "Unsupported NLI label"):
                compute_fleiss_kappa({"m1": p1, "m2": p2})


class AgreementPolicyTest(unittest.TestCase):
    def test_min_agreement_less_than_one_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("m1", "m2", "m3"):
                pd.DataFrame(
                    [
                        {
                            "source_uid": "r1",
                            "predicted_label": "entailment",
                            "reason": "ok",
                        }
                    ]
                ).to_csv(root / f"{name}.csv", index=False)
            paths = {name: root / f"{name}.csv" for name in ("m1", "m2", "m3")}
            with self.assertRaisesRegex(ValueError, "min_agreement"):
                build_validation_vote_table(
                    paths, {"r1": "entailment"}, min_agreement=0
                )

    def test_min_agreement_greater_than_model_count_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("m1", "m2", "m3"):
                pd.DataFrame(
                    [
                        {
                            "source_uid": "r1",
                            "predicted_label": "entailment",
                            "reason": "ok",
                        }
                    ]
                ).to_csv(root / f"{name}.csv", index=False)
            paths = {name: root / f"{name}.csv" for name in ("m1", "m2", "m3")}
            with self.assertRaisesRegex(ValueError, "min_agreement"):
                build_validation_vote_table(
                    paths, {"r1": "entailment"}, min_agreement=4
                )


class UidCoverageTest(unittest.TestCase):
    """Regression tests for duplicate/missing UID detection in verdict frames."""

    @staticmethod
    def _write(root: Path, model_rows: dict[str, list[dict]]) -> dict[str, Path]:
        paths = {}
        for name, rows in model_rows.items():
            path = root / f"{name}.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            paths[name] = path
        return paths

    def test_vote_table_rejects_duplicate_uid_in_model_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._write(
                root,
                {
                    "m1": [
                        {
                            "source_uid": "r1",
                            "predicted_label": "entailment",
                            "reason": "ok",
                        },
                        {
                            "source_uid": "r1",
                            "predicted_label": "neutral",
                            "reason": "ok",
                        },
                    ],
                    "m2": [
                        {
                            "source_uid": "r1",
                            "predicted_label": "entailment",
                            "reason": "ok",
                        },
                    ],
                },
            )
            with self.assertRaisesRegex(ValueError, "duplicate source_uid"):
                build_validation_vote_table(paths, {"r1": "entailment"})

    def test_vote_table_rejects_null_uid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._write(
                root,
                {
                    "m1": [
                        {
                            "source_uid": None,
                            "predicted_label": "entailment",
                            "reason": "ok",
                        }
                    ],
                    "m2": [
                        {
                            "source_uid": None,
                            "predicted_label": "entailment",
                            "reason": "ok",
                        }
                    ],
                },
            )
            with self.assertRaisesRegex(ValueError, "null source_uid"):
                build_validation_vote_table(paths, {})

    def test_vote_table_rejects_blank_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._write(
                root,
                {
                    "m1": [
                        {
                            "source_uid": "r1",
                            "predicted_label": "entailment",
                            "reason": "   ",
                        }
                    ],
                    "m2": [
                        {
                            "source_uid": "r1",
                            "predicted_label": "entailment",
                            "reason": "ok",
                        }
                    ],
                },
            )
            with self.assertRaisesRegex(ValueError, "blank reason"):
                build_validation_vote_table(paths, {"r1": "entailment"})

    def test_vote_table_rejects_null_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._write(
                root,
                {
                    "m1": [
                        {
                            "source_uid": "r1",
                            "predicted_label": "entailment",
                            "reason": None,
                        }
                    ],
                    "m2": [
                        {
                            "source_uid": "r1",
                            "predicted_label": "entailment",
                            "reason": "ok",
                        }
                    ],
                },
            )
            with self.assertRaisesRegex(ValueError, "blank reason"):
                build_validation_vote_table(paths, {"r1": "entailment"})

    def test_vote_table_rejects_common_uid_omission(self) -> None:
        """All models omit the same UID that is in expected_labels."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._write(
                root,
                {
                    "m1": [
                        {
                            "source_uid": "r1",
                            "predicted_label": "entailment",
                            "reason": "ok",
                        }
                    ],
                    "m2": [
                        {
                            "source_uid": "r1",
                            "predicted_label": "entailment",
                            "reason": "ok",
                        }
                    ],
                },
            )
            with self.assertRaisesRegex(ValueError, "not covered"):
                build_validation_vote_table(
                    paths, {"r1": "entailment", "r2": "neutral"}
                )

    def test_vote_table_rejects_extra_uid_not_in_expected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._write(
                root,
                {
                    "m1": [
                        {
                            "source_uid": "r1",
                            "predicted_label": "entailment",
                            "reason": "ok",
                        },
                        {
                            "source_uid": "r99",
                            "predicted_label": "neutral",
                            "reason": "ok",
                        },
                    ],
                    "m2": [
                        {
                            "source_uid": "r1",
                            "predicted_label": "entailment",
                            "reason": "ok",
                        },
                        {
                            "source_uid": "r99",
                            "predicted_label": "neutral",
                            "reason": "ok",
                        },
                    ],
                },
            )
            with self.assertRaisesRegex(ValueError, "not in expected labels"):
                build_validation_vote_table(paths, {"r1": "entailment"})

    def test_vote_table_rejects_missing_reason_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._write(
                root,
                {
                    "m1": [{"source_uid": "r1", "predicted_label": "entailment"}],
                    "m2": [{"source_uid": "r1", "predicted_label": "entailment"}],
                },
            )
            with self.assertRaisesRegex(ValueError, "missing required columns"):
                build_validation_vote_table(paths, {"r1": "entailment"})

    def test_model_name_collision_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p1 = root / "gpt-4o.csv"
            p2 = root / "gpt 4o.csv"
            for p in (p1, p2):
                pd.DataFrame(
                    [{"source_uid": "r1", "predicted_label": "entailment"}]
                ).to_csv(p, index=False)
            with self.assertRaisesRegex(ValueError, "collide"):
                build_validation_vote_table(
                    {"gpt-4o": p1, "gpt 4o": p2}, {"r1": "entailment"}
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
        self.assertEqual(vote_table.loc[0, "gpt4o_label"], "neutral")

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
            pd.DataFrame(
                [{"source_uid": "row-1", "predicted_label": 1, "reason": "ok"}]
            ).to_csv(first, index=False)
            pd.DataFrame(
                [{"source_uid": "row-2", "predicted_label": 1, "reason": "ok"}]
            ).to_csv(second, index=False)

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

    def test_apply_paraphrases_rejects_null_uid_in_flagged_rows(self) -> None:
        dataset = pd.DataFrame([{"source_uid": "row-1", "hypothesis": "h1"}])
        flagged = pd.DataFrame([{"source_uid": None, "artifact_tokens": "x"}])
        paraphrases = pd.DataFrame([{"source_uid": "row-1", "hypothesis": "h1-new"}])
        with self.assertRaisesRegex(ValueError, "null source_uid"):
            apply_paraphrases(dataset, flagged, paraphrases)

    def test_apply_paraphrases_rejects_duplicate_uid_in_flagged_rows(self) -> None:
        dataset = pd.DataFrame(
            [
                {"source_uid": "row-1", "hypothesis": "h1"},
                {"source_uid": "row-2", "hypothesis": "h2"},
            ]
        )
        flagged = pd.DataFrame(
            [
                {"source_uid": "row-1", "artifact_tokens": "x"},
                {"source_uid": "row-1", "artifact_tokens": "y"},
            ]
        )
        paraphrases = pd.DataFrame([{"source_uid": "row-1", "hypothesis": "h1-new"}])
        with self.assertRaisesRegex(ValueError, "duplicate source_uid"):
            apply_paraphrases(dataset, flagged, paraphrases)

    def test_apply_paraphrases_rejects_missing_artifact_tokens_column(self) -> None:
        dataset = pd.DataFrame([{"source_uid": "row-1", "hypothesis": "h1"}])
        flagged = pd.DataFrame([{"source_uid": "row-1"}])
        paraphrases = pd.DataFrame([{"source_uid": "row-1", "hypothesis": "h1-new"}])
        with self.assertRaisesRegex(ValueError, "artifact_tokens"):
            apply_paraphrases(dataset, flagged, paraphrases)

    def test_apply_paraphrases_rejects_null_artifact_tokens(self) -> None:
        dataset = pd.DataFrame([{"source_uid": "row-1", "hypothesis": "h1"}])
        flagged = pd.DataFrame([{"source_uid": "row-1", "artifact_tokens": None}])
        paraphrases = pd.DataFrame([{"source_uid": "row-1", "hypothesis": "h1-new"}])
        with self.assertRaisesRegex(ValueError, "null artifact_tokens"):
            apply_paraphrases(dataset, flagged, paraphrases)

    def test_apply_paraphrases_rejects_uid_not_in_flagged(self) -> None:
        dataset = pd.DataFrame(
            [
                {"source_uid": "row-1", "hypothesis": "h1", "label": "entailment"},
                {"source_uid": "row-2", "hypothesis": "h2", "label": "neutral"},
            ]
        )
        flagged = pd.DataFrame([{"source_uid": "row-1", "artifact_tokens": "x"}])
        paraphrases = pd.DataFrame(
            [
                {"source_uid": "row-1", "hypothesis": "h1-new"},
                {"source_uid": "row-2", "hypothesis": "h2-new"},
            ]
        )
        with self.assertRaisesRegex(ValueError, "not in flagged"):
            apply_paraphrases(dataset, flagged, paraphrases)

    def test_apply_paraphrases_rejects_flagged_uid_missing_from_paraphrases(
        self,
    ) -> None:
        dataset = pd.DataFrame(
            [
                {"source_uid": "row-1", "hypothesis": "h1", "label": "entailment"},
                {"source_uid": "row-2", "hypothesis": "h2", "label": "neutral"},
            ]
        )
        flagged = pd.DataFrame(
            [
                {"source_uid": "row-1", "artifact_tokens": "x"},
                {"source_uid": "row-2", "artifact_tokens": "y"},
            ]
        )
        paraphrases = pd.DataFrame([{"source_uid": "row-1", "hypothesis": "h1-new"}])
        with self.assertRaisesRegex(ValueError, "not in paraphrases"):
            apply_paraphrases(dataset, flagged, paraphrases)

    def test_apply_paraphrases_rejects_empty_rewrite(self) -> None:
        dataset = pd.DataFrame(
            [{"source_uid": "row-1", "hypothesis": "h1", "label": "entailment"}]
        )
        flagged = pd.DataFrame([{"source_uid": "row-1", "artifact_tokens": "x"}])
        paraphrases = pd.DataFrame([{"source_uid": "row-1", "hypothesis": ""}])
        with self.assertRaisesRegex(ValueError, "empty"):
            apply_paraphrases(dataset, flagged, paraphrases)

    def test_apply_paraphrases_rejects_unchanged_rewrite(self) -> None:
        dataset = pd.DataFrame(
            [{"source_uid": "row-1", "hypothesis": "h1", "label": "entailment"}]
        )
        flagged = pd.DataFrame([{"source_uid": "row-1", "artifact_tokens": "x"}])
        paraphrases = pd.DataFrame([{"source_uid": "row-1", "hypothesis": "h1"}])
        with self.assertRaisesRegex(ValueError, "unchanged"):
            apply_paraphrases(dataset, flagged, paraphrases)

    def test_apply_paraphrases_rejects_rewrite_containing_artifact_token(self) -> None:
        dataset = pd.DataFrame(
            [{"source_uid": "row-1", "hypothesis": "foo bar", "label": "entailment"}]
        )
        flagged = pd.DataFrame([{"source_uid": "row-1", "artifact_tokens": "foo"}])
        paraphrases = pd.DataFrame(
            [{"source_uid": "row-1", "hypothesis": "new foo baz"}]
        )
        with self.assertRaisesRegex(ValueError, "artifact"):
            apply_paraphrases(dataset, flagged, paraphrases)

    def test_apply_paraphrases_zero_flagged_with_empty_paraphrases_succeeds(
        self,
    ) -> None:
        dataset = pd.DataFrame(
            [{"source_uid": "row-1", "hypothesis": "h1", "label": "entailment"}]
        )
        flagged = pd.DataFrame(columns=["source_uid", "artifact_tokens"]).astype(str)
        paraphrases = pd.DataFrame(columns=["source_uid", "hypothesis"])
        result, replaced = apply_paraphrases(dataset, flagged, paraphrases)
        self.assertEqual(replaced, 0)
        self.assertEqual(list(result["hypothesis"]), ["h1"])

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
        flagged = pd.DataFrame([{"source_uid": "row-2", "artifact_tokens": "cue"}])
        paraphrases = pd.DataFrame(
            [
                {"source_uid": "row-2", "hypothesis": "h2-rewritten"},
            ]
        )

        processed, replaced = apply_paraphrases(dataset, flagged, paraphrases)

        self.assertEqual(replaced, 1)
        self.assertEqual(list(processed.columns), list(dataset.columns))
        self.assertEqual(list(processed["hypothesis"]), ["h1", "h2-rewritten", "h3"])
        self.assertEqual(list(processed["label"]), [0, 1, 2])

    def test_apply_paraphrases_rejects_unknown_uid(self) -> None:
        dataset = pd.DataFrame([{"source_uid": "row-1", "hypothesis": "h1"}])
        flagged = pd.DataFrame([{"source_uid": "row-9", "artifact_tokens": "x"}])
        paraphrases = pd.DataFrame([{"source_uid": "row-9", "hypothesis": "x-new"}])
        with self.assertRaisesRegex(ValueError, "not found in dataset"):
            apply_paraphrases(dataset, flagged, paraphrases)

    def test_apply_paraphrases_rejects_duplicate_uid(self) -> None:
        dataset = pd.DataFrame([{"source_uid": "row-1", "hypothesis": "h1"}])
        flagged = pd.DataFrame([{"source_uid": "row-1", "artifact_tokens": "x"}])
        paraphrases = pd.DataFrame(
            [
                {"source_uid": "row-1", "hypothesis": "a-new"},
                {"source_uid": "row-1", "hypothesis": "b-new"},
            ]
        )
        with self.assertRaisesRegex(ValueError, "duplicate source_uid"):
            apply_paraphrases(dataset, flagged, paraphrases)

    def test_promote_revalidated_paraphrases_filters_failed_rewrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_paths = self._write_revalidation_label_files(root)
            dataset = pd.DataFrame(
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
            )
            revalidation = pd.DataFrame(
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
            )

            promoted, review, votes = promote_revalidated_paraphrases(
                dataset,
                revalidation,
                model_paths,
                {"row-2": "neutral", "row-3": "contradiction"},
            )

        self.assertEqual(list(promoted["source_uid"]), ["row-1", "row-2"])
        self.assertEqual(list(review["source_uid"]), ["row-3"])
        self.assertEqual(
            dict(zip(votes["source_uid"], votes["decision"])),
            {"row-2": "keep", "row-3": "review"},
        )

    def test_promote_revalidated_paraphrases_rejects_missing_dataset_uid(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_paths = self._write_revalidation_label_files(root, rows=("row-9",))
            dataset = pd.DataFrame(
                [{"source_uid": "row-1", "premise": "p1", "hypothesis": "h1"}]
            )
            revalidation = pd.DataFrame(
                [
                    {
                        "source_uid": "row-9",
                        "premise": "p9",
                        "hypothesis": "h9",
                        "label": "",
                    }
                ]
            )
            with self.assertRaisesRegex(ValueError, "not found"):
                promote_revalidated_paraphrases(
                    dataset,
                    revalidation,
                    model_paths,
                    {"row-9": "neutral"},
                )

    def test_promote_revalidated_paraphrases_rejects_duplicate_queue_uid(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_paths = self._write_revalidation_label_files(root, rows=("row-2",))
            dataset = pd.DataFrame(
                [{"source_uid": "row-2", "premise": "p2", "hypothesis": "h2"}]
            )
            revalidation = pd.DataFrame(
                [
                    {
                        "source_uid": "row-2",
                        "premise": "p2",
                        "hypothesis": "h2",
                        "label": "",
                    },
                    {
                        "source_uid": "row-2",
                        "premise": "p2b",
                        "hypothesis": "h2b",
                        "label": "",
                    },
                ]
            )
            with self.assertRaisesRegex(ValueError, "duplicate source_uid"):
                promote_revalidated_paraphrases(
                    dataset,
                    revalidation,
                    model_paths,
                    {"row-2": "neutral"},
                )

    def test_promote_revalidated_paraphrases_rejects_invalid_expected_label(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_paths = self._write_revalidation_label_files(root, rows=("row-2",))
            dataset = pd.DataFrame(
                [{"source_uid": "row-2", "premise": "p2", "hypothesis": "h2"}]
            )
            revalidation = pd.DataFrame(
                [
                    {
                        "source_uid": "row-2",
                        "premise": "p2",
                        "hypothesis": "h2",
                        "label": "",
                    }
                ]
            )
            with self.assertRaisesRegex(ValueError, "Unsupported NLI label"):
                promote_revalidated_paraphrases(
                    dataset,
                    revalidation,
                    model_paths,
                    {"row-2": "garbage"},
                )

    @staticmethod
    def _write_revalidation_label_files(
        root: Path,
        rows: tuple[str, ...] = ("row-2", "row-3"),
    ) -> dict[str, Path]:
        labels_by_model = {
            "gpt4o": {"row-2": "neutral", "row-3": "entailment", "row-9": "neutral"},
            "deepseek": {"row-2": "neutral", "row-3": "neutral", "row-9": "neutral"},
            "llama": {
                "row-2": "entailment",
                "row-3": "contradiction",
                "row-9": "neutral",
            },
        }
        paths = {}
        for model_name, labels in labels_by_model.items():
            path = root / f"{model_name}.csv"
            pd.DataFrame(
                [
                    {
                        "source_uid": source_uid,
                        "predicted_label": labels[source_uid],
                        "reason": "ok",
                    }
                    for source_uid in rows
                ]
            ).to_csv(path, index=False)
            paths[model_name] = path
        return paths

    @staticmethod
    def _write_model_label_files(root: Path) -> dict[str, Path]:
        model_rows = {
            "gpt4o": [
                {"source_uid": "row-1", "predicted_label": 1, "reason": "ok"},
                {"source_uid": "row-2", "predicted_label": 0, "reason": "ok"},
                {"source_uid": "row-3", "predicted_label": 0, "reason": "ok"},
            ],
            "deepseek": [
                {"source_uid": "row-1", "predicted_label": 1, "reason": "ok"},
                {"source_uid": "row-2", "predicted_label": 0, "reason": "ok"},
                {"source_uid": "row-3", "predicted_label": 1, "reason": "ok"},
            ],
            "llama": [
                {"source_uid": "row-1", "predicted_label": 1, "reason": "ok"},
                {"source_uid": "row-2", "predicted_label": 1, "reason": "ok"},
                {"source_uid": "row-3", "predicted_label": 2, "reason": "ok"},
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
                        {
                            "source_uid": "row-3",
                            "predicted_label": "contradiction",
                            "reason": "ok",
                        },
                    ],
                    "deepseek": [
                        {"source_uid": "row-1", "predicted_label": 0, "reason": "ok"},
                        {"source_uid": "row-2", "predicted_label": 1, "reason": "ok"},
                        {"source_uid": "row-3", "predicted_label": 2, "reason": "ok"},
                    ],
                    "llama": [
                        {
                            "source_uid": "row-1",
                            "predicted_label": "entailment",
                            "reason": "ok",
                        },
                        {"source_uid": "row-2", "predicted_label": 1, "reason": "ok"},
                        {
                            "source_uid": "row-3",
                            "predicted_label": "contradiction",
                            "reason": "ok",
                        },
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
                        {"source_uid": "row-1", "predicted_label": 0, "reason": "ok"},
                        {"source_uid": "row-2", "predicted_label": 1, "reason": "ok"},
                        {"source_uid": "row-3", "predicted_label": 2, "reason": "ok"},
                        {"source_uid": "row-4", "predicted_label": 0, "reason": "ok"},
                    ],
                    "deepseek": [
                        {"source_uid": "row-1", "predicted_label": 0, "reason": "ok"},
                        {"source_uid": "row-2", "predicted_label": 1, "reason": "ok"},
                        {"source_uid": "row-3", "predicted_label": 1, "reason": "ok"},
                        {"source_uid": "row-4", "predicted_label": 0, "reason": "ok"},
                    ],
                    "llama": [
                        {"source_uid": "row-1", "predicted_label": 0, "reason": "ok"},
                        {"source_uid": "row-2", "predicted_label": 2, "reason": "ok"},
                        {"source_uid": "row-3", "predicted_label": 2, "reason": "ok"},
                        {"source_uid": "row-4", "predicted_label": 1, "reason": "ok"},
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
                        {"source_uid": "row-1", "predicted_label": 0, "reason": "ok"},
                    ],
                },
            )
            with self.assertRaises(ValueError):
                compute_fleiss_kappa(paths)


if __name__ == "__main__":
    unittest.main()
