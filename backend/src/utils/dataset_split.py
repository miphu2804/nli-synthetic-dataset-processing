import random
from dataclasses import dataclass
from typing import Any

import pandas as pd

SPLIT_NAMES: tuple[str, str, str] = ("train", "dev", "test")


@dataclass(frozen=True)
class GroupedSplitResult:
    splits: dict[str, pd.DataFrame]
    manifest: dict[str, Any]


@dataclass(frozen=True)
class _Group:
    key: str
    indices: list[int]

    @property
    def size(self) -> int:
        return len(self.indices)


def split_dataset_by_group(
    dataframe: pd.DataFrame,
    *,
    group_column: str = "premise",
    label_column: str = "label",
    train_ratio: float = 0.8,
    dev_ratio: float = 0.1,
    test_ratio: float = 0.1,
    seed: int = 13,
) -> GroupedSplitResult:
    ratios = {
        "train": train_ratio,
        "dev": dev_ratio,
        "test": test_ratio,
    }
    _validate_split_input(dataframe, group_column, label_column, ratios)

    groups = _build_groups(dataframe, group_column)
    shuffled_groups = groups[:]
    random.Random(seed).shuffle(shuffled_groups)

    assignments = _assign_groups(shuffled_groups, len(dataframe), ratios)
    splits = {
        split_name: dataframe.loc[_flatten_indices(groups_for_split)].copy()
        for split_name, groups_for_split in assignments.items()
    }
    manifest = _build_manifest(
        splits=splits,
        assignments=assignments,
        total_rows=len(dataframe),
        total_groups=len(groups),
        group_column=group_column,
        label_column=label_column,
        ratios=ratios,
        seed=seed,
    )
    return GroupedSplitResult(splits=splits, manifest=manifest)


def _validate_split_input(
    dataframe: pd.DataFrame,
    group_column: str,
    label_column: str,
    ratios: dict[str, float],
) -> None:
    if dataframe.empty:
        raise ValueError("Input dataset is empty.")
    missing_columns = [
        column
        for column in (group_column, label_column)
        if column not in dataframe.columns
    ]
    if missing_columns:
        raise ValueError(
            f"Dataset is missing required columns: {', '.join(missing_columns)}"
        )
    if dataframe[group_column].isnull().any():
        raise ValueError(f"Dataset contains null {group_column} values.")
    if dataframe[label_column].isnull().any():
        raise ValueError(f"Dataset contains null {label_column} values.")
    if ratios["train"] <= 0:
        raise ValueError("train_ratio must be greater than 0.")
    if any(ratio < 0 for ratio in ratios.values()):
        raise ValueError("Split ratios must be non-negative.")
    ratio_sum = sum(ratios.values())
    if abs(ratio_sum - 1.0) > 1e-9:
        raise ValueError("Split ratios must sum to 1.0.")


def _build_groups(dataframe: pd.DataFrame, group_column: str) -> list[_Group]:
    groups: list[_Group] = []
    grouped = dataframe.groupby(group_column, sort=False, dropna=False)
    for key, group in grouped:
        groups.append(_Group(key=str(key), indices=list(group.index)))
    return groups


def _assign_groups(
    groups: list[_Group],
    total_rows: int,
    ratios: dict[str, float],
) -> dict[str, list[_Group]]:
    split_order = {name: index for index, name in enumerate(SPLIT_NAMES)}
    active_splits = [name for name in SPLIT_NAMES if ratios[name] > 0]
    targets = {name: total_rows * ratios[name] for name in SPLIT_NAMES}
    assignments: dict[str, list[_Group]] = {name: [] for name in SPLIT_NAMES}
    row_counts = {name: 0 for name in SPLIT_NAMES}

    for group in groups:
        split_name = max(
            active_splits,
            key=lambda name: (
                targets[name] - row_counts[name],
                -split_order[name],
            ),
        )
        assignments[split_name].append(group)
        row_counts[split_name] += group.size

    # Tiny datasets can be ratio-optimal while leaving dev/test empty. If enough
    # groups exist, move the smallest donor groups so each positive split exists.
    for split_name in active_splits:
        if assignments[split_name]:
            continue
        donor_name = _find_donor_split(assignments, row_counts, targets, active_splits)
        if donor_name is None:
            break
        moved_group = min(
            assignments[donor_name],
            key=lambda group: (group.size, group.key),
        )
        assignments[donor_name].remove(moved_group)
        assignments[split_name].append(moved_group)
        row_counts[donor_name] -= moved_group.size
        row_counts[split_name] += moved_group.size

    return assignments


def _find_donor_split(
    assignments: dict[str, list[_Group]],
    row_counts: dict[str, int],
    targets: dict[str, float],
    active_splits: list[str],
) -> str | None:
    donors = [name for name in active_splits if len(assignments[name]) > 1]
    if not donors:
        return None
    return max(
        donors,
        key=lambda name: (
            row_counts[name] - targets[name],
            len(assignments[name]),
        ),
    )


def _flatten_indices(groups: list[_Group]) -> list[int]:
    indices = [index for group in groups for index in group.indices]
    return sorted(indices)


def _build_manifest(
    *,
    splits: dict[str, pd.DataFrame],
    assignments: dict[str, list[_Group]],
    total_rows: int,
    total_groups: int,
    group_column: str,
    label_column: str,
    ratios: dict[str, float],
    seed: int,
) -> dict[str, Any]:
    return {
        "seed": seed,
        "group_column": group_column,
        "label_column": label_column,
        "ratios": ratios,
        "total_rows": total_rows,
        "total_groups": total_groups,
        "splits": {
            split_name: {
                "rows": len(split_df),
                "groups": len(assignments[split_name]),
                "label_distribution": _label_distribution(split_df, label_column),
            }
            for split_name, split_df in splits.items()
        },
    }


def _label_distribution(dataframe: pd.DataFrame, label_column: str) -> dict[str, int]:
    if dataframe.empty:
        return {}
    counts = dataframe[label_column].astype(str).value_counts().sort_index()
    return {str(label): int(count) for label, count in counts.items()}
