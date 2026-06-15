import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.utils.validation_aggregation import (
    attach_masked_text,
    build_validation_vote_table,
    compute_hypothesis_label_pmi,
)


class ValidationAggregationTest(unittest.TestCase):
    def test_build_validation_vote_table_merges_three_model_label_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model_paths = self._write_model_label_files(root)

            vote_table = build_validation_vote_table(model_paths)

        self.assertEqual(
            list(vote_table["source_uid"]),
            ["row-1", "row-2", "row-3"],
        )
        self.assertEqual(vote_table.loc[0, "gpt4o_label"], 1)
        self.assertEqual(vote_table.loc[0, "consensus_label"], "1")
        self.assertEqual(vote_table.loc[0, "consensus_size"], 3)
        self.assertEqual(vote_table.loc[0, "agreement_status"], "unanimous")
        self.assertEqual(vote_table.loc[1, "vote_count_0"], 2)
        self.assertEqual(vote_table.loc[1, "agreement_status"], "majority")
        self.assertEqual(vote_table.loc[2, "agreement_status"], "review")

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
                build_validation_vote_table({"gpt4o": first, "deepseek": second})

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
