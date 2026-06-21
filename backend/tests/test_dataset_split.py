import unittest

import pandas as pd
from src.utils.dataset_split import split_dataset_by_group


class DatasetSplitTest(unittest.TestCase):
    def test_split_dataset_by_group_keeps_premises_in_one_split(self) -> None:
        dataframe = pd.DataFrame(
            [
                {"source_uid": "1a", "premise": "p1", "hypothesis": "h1", "label": 0},
                {"source_uid": "1b", "premise": "p1", "hypothesis": "h2", "label": 1},
                {"source_uid": "2a", "premise": "p2", "hypothesis": "h3", "label": 0},
                {"source_uid": "3a", "premise": "p3", "hypothesis": "h4", "label": 2},
                {"source_uid": "4a", "premise": "p4", "hypothesis": "h5", "label": 1},
                {"source_uid": "5a", "premise": "p5", "hypothesis": "h6", "label": 2},
            ]
        )

        result = split_dataset_by_group(
            dataframe,
            train_ratio=0.6,
            dev_ratio=0.2,
            test_ratio=0.2,
            seed=7,
        )

        premise_sets = {
            name: set(split["premise"])
            for name, split in result.splits.items()
            if not split.empty
        }
        self.assertTrue(premise_sets["train"].isdisjoint(premise_sets["dev"]))
        self.assertTrue(premise_sets["train"].isdisjoint(premise_sets["test"]))
        self.assertTrue(premise_sets["dev"].isdisjoint(premise_sets["test"]))
        self.assertEqual(
            sum(len(split) for split in result.splits.values()),
            len(dataframe),
        )
        self.assertEqual(result.manifest["total_groups"], 5)

    def test_split_dataset_by_group_is_deterministic_for_same_seed(self) -> None:
        dataframe = pd.DataFrame(
            [
                {
                    "source_uid": f"row-{index}",
                    "premise": f"premise-{index // 2}",
                    "hypothesis": f"hypothesis-{index}",
                    "label": index % 3,
                }
                for index in range(12)
            ]
        )

        first = split_dataset_by_group(dataframe, seed=42)
        second = split_dataset_by_group(dataframe, seed=42)

        for split_name in ("train", "dev", "test"):
            self.assertEqual(
                list(first.splits[split_name]["source_uid"]),
                list(second.splits[split_name]["source_uid"]),
            )

    def test_split_dataset_by_group_handles_small_dataset(self) -> None:
        dataframe = pd.DataFrame(
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
        )

        result = split_dataset_by_group(dataframe, seed=5)

        self.assertEqual(
            sum(len(split) for split in result.splits.values()),
            len(dataframe),
        )
        self.assertEqual(result.manifest["total_groups"], 2)

    def test_split_dataset_by_group_rejects_invalid_ratios(self) -> None:
        dataframe = pd.DataFrame(
            [{"source_uid": "row-1", "premise": "p1", "hypothesis": "h1", "label": 0}]
        )

        with self.assertRaises(ValueError):
            split_dataset_by_group(
                dataframe,
                train_ratio=0.7,
                dev_ratio=0.2,
                test_ratio=0.2,
            )

    def test_split_dataset_by_group_rejects_missing_group_column(self) -> None:
        dataframe = pd.DataFrame(
            [{"source_uid": "row-1", "hypothesis": "h1", "label": 0}]
        )

        with self.assertRaises(ValueError):
            split_dataset_by_group(dataframe)


if __name__ == "__main__":
    unittest.main()
