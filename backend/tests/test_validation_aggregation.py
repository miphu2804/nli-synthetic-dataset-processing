import tempfile
import unittest
from pathlib import Path

import pandas as pd
from src.utils.validation_aggregation import (
    attach_masked_text,
    build_validation_vote_table,
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


if __name__ == "__main__":
    unittest.main()
