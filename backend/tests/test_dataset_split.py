import unittest

import pandas as pd
from src.utils.dataset_split import split_dataset_by_group


def _distribution_error(
    splits: dict[str, pd.DataFrame],
    *,
    column: str,
    ratios: dict[str, float],
) -> float:
    dataframe = pd.concat(splits.values(), ignore_index=True)
    totals = dataframe[column].astype(str).value_counts().to_dict()
    error = 0.0
    for split_name, split_df in splits.items():
        counts = split_df[column].astype(str).value_counts().to_dict()
        for value, total in totals.items():
            expected = total * ratios[split_name]
            error += abs(counts.get(value, 0) - expected) / max(1, total)
    return error


def _row_count_tolerance(
    splits: dict[str, pd.DataFrame],
    *,
    total_rows: int,
    ratios: dict[str, float],
) -> dict[str, float]:
    return {
        split_name: abs(len(split_df) - (total_rows * ratios[split_name]))
        for split_name, split_df in splits.items()
    }


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

        first = split_dataset_by_group(dataframe, seed=42, domain_column="domain")
        second = split_dataset_by_group(dataframe, seed=42, domain_column="domain")

        for split_name in ("train", "dev", "test"):
            self.assertEqual(
                list(first.splits[split_name]["source_uid"]),
                list(second.splits[split_name]["source_uid"]),
            )
        self.assertEqual(first.manifest, second.manifest)

    def test_grouped_stratified_improves_label_balance_over_grouped_shuffle(
        self,
    ) -> None:
        dataframe = pd.DataFrame(
            [
                {"source_uid": "g1a", "premise": "p1", "hypothesis": "h1", "label": 0},
                {"source_uid": "g1b", "premise": "p1", "hypothesis": "h2", "label": 0},
                {"source_uid": "g2a", "premise": "p2", "hypothesis": "h3", "label": 0},
                {"source_uid": "g2b", "premise": "p2", "hypothesis": "h4", "label": 0},
                {"source_uid": "g3a", "premise": "p3", "hypothesis": "h5", "label": 1},
                {"source_uid": "g3b", "premise": "p3", "hypothesis": "h6", "label": 1},
                {"source_uid": "g4a", "premise": "p4", "hypothesis": "h7", "label": 1},
                {"source_uid": "g4b", "premise": "p4", "hypothesis": "h8", "label": 1},
                {"source_uid": "g5a", "premise": "p5", "hypothesis": "h9", "label": 2},
                {"source_uid": "g5b", "premise": "p5", "hypothesis": "h10", "label": 2},
                {"source_uid": "g6a", "premise": "p6", "hypothesis": "h11", "label": 2},
                {"source_uid": "g6b", "premise": "p6", "hypothesis": "h12", "label": 2},
            ]
        )
        ratios = {"train": 0.5, "dev": 0.25, "test": 0.25}

        stratified = split_dataset_by_group(
            dataframe,
            train_ratio=ratios["train"],
            dev_ratio=ratios["dev"],
            test_ratio=ratios["test"],
            seed=2,
            strategy="grouped-stratified",
        )
        grouped_shuffle = split_dataset_by_group(
            dataframe,
            train_ratio=ratios["train"],
            dev_ratio=ratios["dev"],
            test_ratio=ratios["test"],
            seed=2,
            strategy="grouped-shuffle",
        )

        stratified_error = _distribution_error(
            stratified.splits,
            column="label",
            ratios=ratios,
        )
        grouped_shuffle_error = _distribution_error(
            grouped_shuffle.splits,
            column="label",
            ratios=ratios,
        )
        self.assertLess(stratified_error, grouped_shuffle_error)
        self.assertEqual(stratified.manifest["strategy"], "grouped-stratified")

    def test_grouped_stratified_can_use_domain_distribution(self) -> None:
        dataframe = pd.DataFrame(
            [
                {
                    "source_uid": "g1a",
                    "premise": "p1",
                    "hypothesis": "h1",
                    "label": 0,
                    "domain": "tax",
                },
                {
                    "source_uid": "g1b",
                    "premise": "p1",
                    "hypothesis": "h2",
                    "label": 1,
                    "domain": "tax",
                },
                {
                    "source_uid": "g2a",
                    "premise": "p2",
                    "hypothesis": "h3",
                    "label": 0,
                    "domain": "tax",
                },
                {
                    "source_uid": "g2b",
                    "premise": "p2",
                    "hypothesis": "h4",
                    "label": 1,
                    "domain": "tax",
                },
                {
                    "source_uid": "g3a",
                    "premise": "p3",
                    "hypothesis": "h5",
                    "label": 0,
                    "domain": "labor",
                },
                {
                    "source_uid": "g3b",
                    "premise": "p3",
                    "hypothesis": "h6",
                    "label": 1,
                    "domain": "labor",
                },
                {
                    "source_uid": "g4a",
                    "premise": "p4",
                    "hypothesis": "h7",
                    "label": 0,
                    "domain": "labor",
                },
                {
                    "source_uid": "g4b",
                    "premise": "p4",
                    "hypothesis": "h8",
                    "label": 1,
                    "domain": "labor",
                },
            ]
        )
        ratios = {"train": 0.5, "dev": 0.25, "test": 0.25}

        with_domain = split_dataset_by_group(
            dataframe,
            train_ratio=ratios["train"],
            dev_ratio=ratios["dev"],
            test_ratio=ratios["test"],
            seed=5,
            domain_column="domain",
        )
        without_domain = split_dataset_by_group(
            dataframe,
            train_ratio=ratios["train"],
            dev_ratio=ratios["dev"],
            test_ratio=ratios["test"],
            seed=5,
        )

        with_domain_error = _distribution_error(
            with_domain.splits,
            column="domain",
            ratios=ratios,
        )
        without_domain_error = _distribution_error(
            without_domain.splits,
            column="domain",
            ratios=ratios,
        )
        self.assertLessEqual(with_domain_error, without_domain_error)
        self.assertEqual(with_domain.manifest["domain"]["status"], "used")
        self.assertEqual(with_domain.manifest["domain"]["distribution"]["labor"], 4)
        self.assertIn(
            "domain_distribution",
            with_domain.manifest["splits"]["train"],
        )

    def test_grouped_stratified_respects_row_targets_in_many_group_case(self) -> None:
        sizes = [3] * 14 + [2] * 19
        rows = []
        source_uid = 0
        for group_index, size in enumerate(sizes):
            label = group_index % 3
            domain = "tax" if group_index % 2 == 0 else "labor"
            premise = f"premise-{group_index:02d}"
            for row_index in range(size):
                source_uid += 1
                rows.append(
                    {
                        "source_uid": f"row-{source_uid}",
                        "premise": premise,
                        "hypothesis": f"hypothesis-{group_index}-{row_index}",
                        "label": label,
                        "domain": domain,
                    }
                )
        dataframe = pd.DataFrame(rows)
        ratios = {"train": 0.8, "dev": 0.1, "test": 0.1}

        result = split_dataset_by_group(
            dataframe,
            train_ratio=ratios["train"],
            dev_ratio=ratios["dev"],
            test_ratio=ratios["test"],
            seed=13,
            domain_column="domain",
        )

        tolerance = max(sizes)
        row_count_error = _row_count_tolerance(
            result.splits,
            total_rows=len(dataframe),
            ratios=ratios,
        )
        self.assertLessEqual(row_count_error["train"], tolerance)
        self.assertLessEqual(row_count_error["dev"], tolerance)
        self.assertLessEqual(row_count_error["test"], tolerance)
        self.assertGreater(len(result.splits["train"]), len(result.splits["dev"]))
        self.assertGreater(len(result.splits["train"]), len(result.splits["test"]))
        self.assertEqual(result.manifest["total_groups"], len(sizes))

    def test_missing_or_empty_domain_column_does_not_fail(self) -> None:
        dataframe = pd.DataFrame(
            [
                {
                    "source_uid": "row-1",
                    "premise": "p1",
                    "hypothesis": "h1",
                    "label": 0,
                    "domain": "",
                },
                {
                    "source_uid": "row-2",
                    "premise": "p2",
                    "hypothesis": "h2",
                    "label": 1,
                    "domain": "",
                },
            ]
        )

        missing = split_dataset_by_group(dataframe, domain_column="subdomain")
        empty = split_dataset_by_group(dataframe, domain_column="domain")

        self.assertEqual(missing.manifest["domain"]["status"], "missing")
        self.assertEqual(empty.manifest["domain"]["status"], "empty")
        self.assertEqual(
            sum(len(split) for split in empty.splits.values()),
            len(dataframe),
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
