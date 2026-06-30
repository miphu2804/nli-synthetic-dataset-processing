import json
import random
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils.tabular_io import read_tabular

SPLIT_NAMES: tuple[str, str, str] = ("train", "dev", "test")
SPLIT_STRATEGY = "grouped-stratified"
TRAIN_RATIO = 0.8
DEV_RATIO = 0.1
TEST_RATIO = 0.1
SPLIT_SEED = 13
GROUP_COLUMN = "premise"
LABEL_COLUMN = "label"
_MISSING_DOMAIN_VALUE = "__missing__"


@dataclass(frozen=True)
class GroupedSplitResult:
    splits: dict[str, pd.DataFrame]
    manifest: dict[str, Any]


class DatasetSplitService:
    def split(
        self,
        input_path,
        output_dir,
        group_column: str,
        label_column: str,
        domain_column: str | None,
        train_ratio: float,
        dev_ratio: float,
        test_ratio: float,
        seed: int,
    ) -> dict:
        input_path = Path(input_path)
        output_dir = Path(output_dir)
        dataframe = read_tabular(input_path)
        result = split_dataset_by_group(
            dataframe,
            group_column=group_column,
            label_column=label_column,
            domain_column=domain_column,
            train_ratio=train_ratio,
            dev_ratio=dev_ratio,
            test_ratio=test_ratio,
            seed=seed,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_paths = {
            "train": output_dir / "train.csv",
            "dev": output_dir / "dev.csv",
            "test": output_dir / "test.csv",
            "manifest": output_dir / "split_manifest.json",
        }
        with tempfile.TemporaryDirectory(dir=output_dir) as staging_dir:
            staging = Path(staging_dir)
            for split_name in SPLIT_NAMES:
                result.splits[split_name].to_csv(
                    staging / f"{split_name}.csv",
                    index=False,
                )
            (staging / "split_manifest.json").write_text(
                json.dumps(
                    result.manifest, ensure_ascii=False, indent=2, sort_keys=True
                )
                + "\n"
            )
            for split_name in SPLIT_NAMES:
                shutil.move(
                    str(staging / f"{split_name}.csv"), output_paths[split_name]
                )
            shutil.move(
                str(staging / "split_manifest.json"),
                output_paths["manifest"],
            )

        return {
            "train_output": output_paths["train"],
            "dev_output": output_paths["dev"],
            "test_output": output_paths["test"],
            "manifest_output": output_paths["manifest"],
            "total_rows": result.manifest["total_rows"],
            "total_groups": result.manifest["total_groups"],
            "strategy": result.manifest["strategy"],
            "domain_status": result.manifest["domain"]["status"],
            "train_rows": result.manifest["splits"]["train"]["rows"],
            "dev_rows": result.manifest["splits"]["dev"]["rows"],
            "test_rows": result.manifest["splits"]["test"]["rows"],
        }


@dataclass(frozen=True)
class _Group:
    key: str
    indices: list[int]
    label_counts: dict[str, int]
    domain_counts: dict[str, int]

    @property
    def size(self) -> int:
        return len(self.indices)


@dataclass(frozen=True)
class _DomainConfig:
    requested_column: str | None
    active_column: str | None
    status: str
    distribution: dict[str, int]
    values: pd.Series | None

    @property
    def is_active(self) -> bool:
        return self.active_column is not None and self.values is not None


def split_dataset_by_group(
    dataframe: pd.DataFrame,
    *,
    group_column: str = GROUP_COLUMN,
    label_column: str = LABEL_COLUMN,
    train_ratio: float = TRAIN_RATIO,
    dev_ratio: float = DEV_RATIO,
    test_ratio: float = TEST_RATIO,
    seed: int = SPLIT_SEED,
    domain_column: str | None = None,
) -> GroupedSplitResult:
    ratios = {
        "train": train_ratio,
        "dev": dev_ratio,
        "test": test_ratio,
    }
    _validate_split_input(dataframe, group_column, label_column, ratios)

    domain_config = _build_domain_config(dataframe, domain_column)
    groups = _build_groups(
        dataframe,
        group_column=group_column,
        label_column=label_column,
        domain_values=domain_config.values if domain_config.is_active else None,
    )
    label_distribution = _value_distribution(dataframe[label_column].astype(str))
    shuffled_groups = groups[:]
    random.Random(seed).shuffle(shuffled_groups)

    assignments = _assign_groups(
        shuffled_groups,
        total_rows=len(dataframe),
        ratios=ratios,
        label_distribution=label_distribution,
        domain_distribution=domain_config.distribution,
    )
    splits = {
        split_name: dataframe.loc[_flatten_indices(groups_for_split)].copy()
        for split_name, groups_for_split in assignments.items()
    }
    manifest = _build_manifest(
        dataframe=dataframe,
        splits=splits,
        assignments=assignments,
        total_rows=len(dataframe),
        total_groups=len(groups),
        group_column=group_column,
        label_column=label_column,
        ratios=ratios,
        seed=seed,
        domain_config=domain_config,
    )
    return GroupedSplitResult(splits=splits, manifest=manifest)


def _validate_split_input(
    dataframe: pd.DataFrame,
    group_column: str,
    label_column: str,
    ratios: dict[str, float],
) -> None:
    _validate_required_split_columns(dataframe, group_column, label_column)
    _validate_split_ratios(ratios)


def _validate_required_split_columns(
    dataframe: pd.DataFrame,
    group_column: str,
    label_column: str,
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


def _validate_split_ratios(ratios: dict[str, float]) -> None:
    if ratios["train"] <= 0:
        raise ValueError("train_ratio must be greater than 0.")
    if any(ratio < 0 for ratio in ratios.values()):
        raise ValueError("Split ratios must be non-negative.")
    ratio_sum = sum(ratios.values())
    if abs(ratio_sum - 1.0) > 1e-9:
        raise ValueError("Split ratios must sum to 1.0.")


def _build_domain_config(
    dataframe: pd.DataFrame,
    domain_column: str | None,
) -> _DomainConfig:
    if not domain_column:
        return _DomainConfig(
            requested_column=None,
            active_column=None,
            status="not_requested",
            distribution={},
            values=None,
        )
    if domain_column not in dataframe.columns:
        return _DomainConfig(
            requested_column=domain_column,
            active_column=None,
            status="missing",
            distribution={},
            values=None,
        )

    normalized = dataframe[domain_column].map(_normalize_optional_value)
    if normalized.isnull().all():
        return _DomainConfig(
            requested_column=domain_column,
            active_column=None,
            status="empty",
            distribution={},
            values=None,
        )
    values = normalized.fillna(_MISSING_DOMAIN_VALUE).astype(str)
    return _DomainConfig(
        requested_column=domain_column,
        active_column=domain_column,
        status="used",
        distribution=_value_distribution(values),
        values=values,
    )


def _normalize_optional_value(value: Any) -> str | None:
    if pd.isna(value):
        return None
    normalized = str(value).strip()
    return normalized or None


def _build_groups(
    dataframe: pd.DataFrame,
    *,
    group_column: str,
    label_column: str,
    domain_values: pd.Series | None,
) -> list[_Group]:
    groups: list[_Group] = []
    grouped = dataframe.groupby(group_column, sort=False, dropna=False)
    label_values = dataframe[label_column].astype(str)
    for key, group in grouped:
        indices = list(group.index)
        label_counts = _value_distribution(label_values.loc[indices])
        domain_counts = (
            _value_distribution(domain_values.loc[indices])
            if domain_values is not None
            else {}
        )
        groups.append(
            _Group(
                key=str(key),
                indices=indices,
                label_counts=label_counts,
                domain_counts=domain_counts,
            )
        )
    return groups


def _assign_groups(
    groups: list[_Group],
    *,
    total_rows: int,
    ratios: dict[str, float],
    label_distribution: dict[str, int],
    domain_distribution: dict[str, int],
) -> dict[str, list[_Group]]:
    split_order = {name: index for index, name in enumerate(SPLIT_NAMES)}
    active_splits = _active_split_names(ratios)
    row_targets = {name: total_rows * ratios[name] for name in SPLIT_NAMES}
    label_targets = _scaled_targets(label_distribution, ratios)
    domain_targets = _scaled_targets(domain_distribution, ratios)
    assignments: dict[str, list[_Group]] = {name: [] for name in SPLIT_NAMES}
    row_counts = {name: 0 for name in SPLIT_NAMES}
    split_label_counts = _empty_split_counts(label_distribution)
    split_domain_counts = _empty_split_counts(domain_distribution)

    assigned_rows = 0
    for _, group in _ordered_groups(
        groups,
        label_distribution=label_distribution,
        domain_distribution=domain_distribution,
    ):
        split_name = _select_split_for_group(
            group=group,
            active_splits=active_splits,
            split_order=split_order,
            row_counts=row_counts,
            row_targets=row_targets,
            assigned_rows=assigned_rows,
            total_rows=total_rows,
            split_label_counts=split_label_counts,
            label_targets=label_targets,
            label_distribution=label_distribution,
            split_domain_counts=split_domain_counts,
            domain_targets=domain_targets,
            domain_distribution=domain_distribution,
        )
        _add_group_to_split(
            group=group,
            split_name=split_name,
            assignments=assignments,
            row_counts=row_counts,
            split_label_counts=split_label_counts,
            split_domain_counts=split_domain_counts,
        )
        assigned_rows += group.size

    _backfill_empty_splits(
        assignments=assignments,
        row_counts=row_counts,
        targets=row_targets,
        active_splits=active_splits,
        split_label_counts=split_label_counts,
        split_domain_counts=split_domain_counts,
    )
    return assignments


def _active_split_names(ratios: dict[str, float]) -> list[str]:
    return [name for name in SPLIT_NAMES if ratios[name] > 0]


def _empty_split_counts(distribution: dict[str, int]) -> dict[str, dict[str, int]]:
    return {
        split_name: {value: 0 for value in distribution} for split_name in SPLIT_NAMES
    }


def _ordered_groups(
    groups: list[_Group],
    *,
    label_distribution: dict[str, int],
    domain_distribution: dict[str, int],
) -> list[tuple[int, _Group]]:
    return sorted(
        enumerate(groups),
        key=lambda item: (
            -item[1].size,
            -_group_rarity_score(
                item[1],
                label_distribution=label_distribution,
                domain_distribution=domain_distribution,
            ),
            item[0],
        ),
    )


def _select_split_for_group(
    *,
    group: _Group,
    active_splits: list[str],
    split_order: dict[str, int],
    row_counts: dict[str, int],
    row_targets: dict[str, float],
    assigned_rows: int,
    total_rows: int,
    split_label_counts: dict[str, dict[str, int]],
    label_targets: dict[str, dict[str, float]],
    label_distribution: dict[str, int],
    split_domain_counts: dict[str, dict[str, int]],
    domain_targets: dict[str, dict[str, float]],
    domain_distribution: dict[str, int],
) -> str:
    return min(
        active_splits,
        key=lambda name: (
            _row_priority_key(
                split_name=name,
                group=group,
                row_counts=row_counts,
                row_targets=row_targets,
                assigned_rows=assigned_rows,
                total_rows=total_rows,
            ),
            _distribution_priority_key(
                split_name=name,
                group=group,
                split_label_counts=split_label_counts,
                label_targets=label_targets,
                label_distribution=label_distribution,
                split_domain_counts=split_domain_counts,
                domain_targets=domain_targets,
                domain_distribution=domain_distribution,
            ),
            split_order[name],
        ),
    )


def _add_group_to_split(
    *,
    group: _Group,
    split_name: str,
    assignments: dict[str, list[_Group]],
    row_counts: dict[str, int],
    split_label_counts: dict[str, dict[str, int]],
    split_domain_counts: dict[str, dict[str, int]],
) -> None:
    assignments[split_name].append(group)
    row_counts[split_name] += group.size
    _apply_counts(split_label_counts[split_name], group.label_counts, direction=1)
    _apply_counts(split_domain_counts[split_name], group.domain_counts, direction=1)


def _scaled_targets(
    distribution: dict[str, int],
    ratios: dict[str, float],
) -> dict[str, dict[str, float]]:
    return {
        split_name: {
            value: count * ratios[split_name] for value, count in distribution.items()
        }
        for split_name in SPLIT_NAMES
    }


def _group_rarity_score(
    group: _Group,
    *,
    label_distribution: dict[str, int],
    domain_distribution: dict[str, int],
) -> float:
    score = 0.0
    for label, count in group.label_counts.items():
        score += count / max(1, label_distribution[label])
    for domain, count in group.domain_counts.items():
        score += count / max(1, domain_distribution[domain])
    return score


def _row_priority_key(
    *,
    split_name: str,
    group: _Group,
    row_counts: dict[str, int],
    row_targets: dict[str, float],
    assigned_rows: int,
    total_rows: int,
) -> tuple[float, float, float, float]:
    projected_rows = row_counts[split_name] + group.size
    target_rows = row_targets[split_name]
    overshoot_rows = max(0.0, projected_rows - target_rows)
    target_progress = (assigned_rows + group.size) / max(1, total_rows)
    projected_progress = projected_rows / max(1.0, target_rows)
    return (
        1.0 if overshoot_rows > 0 else 0.0,
        abs(projected_progress - target_progress),
        overshoot_rows,
        abs(projected_rows - target_rows),
    )


def _distribution_priority_key(
    *,
    split_name: str,
    group: _Group,
    split_label_counts: dict[str, dict[str, int]],
    label_targets: dict[str, dict[str, float]],
    label_distribution: dict[str, int],
    split_domain_counts: dict[str, dict[str, int]],
    domain_targets: dict[str, dict[str, float]],
    domain_distribution: dict[str, int],
) -> tuple[float, float]:
    label_loss = _distribution_loss(
        current_counts=split_label_counts[split_name],
        added_counts=group.label_counts,
        target_counts=label_targets[split_name],
        global_counts=label_distribution,
    )
    domain_loss = _distribution_loss(
        current_counts=split_domain_counts[split_name],
        added_counts=group.domain_counts,
        target_counts=domain_targets[split_name],
        global_counts=domain_distribution,
    )
    return (label_loss, domain_loss)


def _distribution_loss(
    *,
    current_counts: dict[str, int],
    added_counts: dict[str, int],
    target_counts: dict[str, float],
    global_counts: dict[str, int],
) -> float:
    if not global_counts:
        return 0.0
    loss = 0.0
    for value, global_count in global_counts.items():
        projected = current_counts.get(value, 0) + added_counts.get(value, 0)
        loss += abs(projected - target_counts.get(value, 0.0)) / max(1, global_count)
    return loss / len(global_counts)


def _apply_counts(
    accumulator: dict[str, int],
    counts: dict[str, int],
    *,
    direction: int,
) -> None:
    for value, count in counts.items():
        accumulator[value] = accumulator.get(value, 0) + (direction * count)


def _backfill_empty_splits(
    *,
    assignments: dict[str, list[_Group]],
    row_counts: dict[str, int],
    targets: dict[str, float],
    active_splits: list[str],
    split_label_counts: dict[str, dict[str, int]] | None = None,
    split_domain_counts: dict[str, dict[str, int]] | None = None,
) -> None:
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
        if split_label_counts is not None:
            _apply_counts(
                split_label_counts[donor_name],
                moved_group.label_counts,
                direction=-1,
            )
            _apply_counts(
                split_label_counts[split_name],
                moved_group.label_counts,
                direction=1,
            )
        if split_domain_counts is not None:
            _apply_counts(
                split_domain_counts[donor_name],
                moved_group.domain_counts,
                direction=-1,
            )
            _apply_counts(
                split_domain_counts[split_name],
                moved_group.domain_counts,
                direction=1,
            )


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
    dataframe: pd.DataFrame,
    splits: dict[str, pd.DataFrame],
    assignments: dict[str, list[_Group]],
    total_rows: int,
    total_groups: int,
    group_column: str,
    label_column: str,
    ratios: dict[str, float],
    seed: int,
    domain_config: _DomainConfig,
) -> dict[str, Any]:
    manifest = {
        "strategy": SPLIT_STRATEGY,
        "seed": seed,
        "group_column": group_column,
        "label_column": label_column,
        "ratios": ratios,
        "total_rows": total_rows,
        "total_groups": total_groups,
        "label_distribution": _label_distribution(dataframe, label_column),
        "domain": _domain_manifest(domain_config),
        "splits": {
            split_name: _split_manifest_entry(
                split_name=split_name,
                split_df=split_df,
                assignments=assignments,
                label_column=label_column,
                domain_config=domain_config,
            )
            for split_name, split_df in splits.items()
        },
    }
    return manifest


def _split_manifest_entry(
    *,
    split_name: str,
    split_df: pd.DataFrame,
    assignments: dict[str, list[_Group]],
    label_column: str,
    domain_config: _DomainConfig,
) -> dict[str, Any]:
    entry = {
        "rows": len(split_df),
        "groups": len(assignments[split_name]),
        "label_distribution": _label_distribution(split_df, label_column),
    }
    if domain_config.is_active:
        entry["domain_distribution"] = _domain_distribution(
            split_df,
            domain_config.active_column,
        )
    return entry


def _domain_manifest(domain_config: _DomainConfig) -> dict[str, Any]:
    manifest = {
        "requested_column": domain_config.requested_column,
        "used_column": domain_config.active_column,
        "status": domain_config.status,
        "used": domain_config.is_active,
    }
    if domain_config.distribution:
        manifest["distribution"] = domain_config.distribution
    return manifest


def _label_distribution(dataframe: pd.DataFrame, label_column: str) -> dict[str, int]:
    if dataframe.empty:
        return {}
    return _value_distribution(dataframe[label_column].astype(str))


def _domain_distribution(
    dataframe: pd.DataFrame,
    domain_column: str | None,
) -> dict[str, int]:
    if (
        dataframe.empty
        or domain_column is None
        or domain_column not in dataframe.columns
    ):
        return {}
    normalized = dataframe[domain_column].map(_normalize_optional_value)
    if normalized.isnull().all():
        return {}
    return _value_distribution(normalized.fillna(_MISSING_DOMAIN_VALUE).astype(str))


def _value_distribution(values: pd.Series) -> dict[str, int]:
    counts = values.astype(str).value_counts().sort_index()
    return {str(value): int(count) for value, count in counts.items()}
