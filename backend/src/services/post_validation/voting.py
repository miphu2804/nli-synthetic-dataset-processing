from pathlib import Path

import pandas as pd

from src.services.post_validation.model_predictions import (
    SOURCE_UID_COLUMN,
    _merge_model_predictions,
)
from src.utils.nli_labels import to_label_name


def build_validation_vote_table(
    model_prediction_paths: dict[str, str | Path],
    expected_labels: dict[str | int, str | int],
    min_agreement: int = 2,
) -> pd.DataFrame:
    """Build a per-row vote table from multiple model predictions scored against expected_labels.

    Each row records the per-model predicted labels, the count of models agreeing with the expected label, and a
    keep/review/discard decision (see _classify_decision). Raises if a row has no expected_label.
    """
    vote_table, label_columns = _merge_model_predictions(model_prediction_paths)

    _validate_min_agreement(min_agreement, model_count=len(label_columns))
    expected_labels_by_uid = _normalize_expected_labels(expected_labels)
    _validate_expected_uid_coverage(vote_table, expected_labels_by_uid)

    vote_rows = [
        _build_vote_row(
            row=row,
            label_columns=label_columns,
            expected_labels_by_uid=expected_labels_by_uid,
            min_agreement=min_agreement,
        )
        for _, row in vote_table.iterrows()
    ]
    return pd.DataFrame(vote_rows)


def _validate_min_agreement(min_agreement: int, *, model_count: int) -> None:
    if not 1 <= min_agreement <= model_count:
        raise ValueError(
            f"min_agreement must be between 1 and {model_count} (got {min_agreement})."
        )


def _normalize_expected_labels(
    expected_labels: dict[str | int, str | int],
) -> dict[str, str | int]:
    expected_labels_by_uid: dict[str, str | int] = {}
    for source_uid, label in expected_labels.items():
        uid_key = str(source_uid)
        if uid_key in expected_labels_by_uid:
            raise ValueError(f"expected labels contain duplicate source_uid: {uid_key}")
        expected_labels_by_uid[uid_key] = label
    return expected_labels_by_uid


def _validate_expected_uid_coverage(
    vote_table: pd.DataFrame,
    expected_labels_by_uid: dict[str, str | int],
) -> None:
    verdict_uids = set(vote_table[SOURCE_UID_COLUMN].astype(str))
    expected_uids = set(expected_labels_by_uid)
    missing = sorted(expected_uids - verdict_uids)
    extra = sorted(verdict_uids - expected_uids)
    if missing or extra:
        parts = []
        if missing:
            parts.append(
                f"{len(missing)} expected UID(s) not covered by verdicts: "
                f"{', '.join(missing[:5])}"
            )
        if extra:
            parts.append(
                f"{len(extra)} verdict UID(s) not in expected labels: "
                f"{', '.join(extra[:5])}"
            )
        raise ValueError("; ".join(parts))


def _build_vote_row(
    *,
    row: pd.Series,
    label_columns: list[str],
    expected_labels_by_uid: dict[str, str | int],
    min_agreement: int,
) -> dict:
    source_uid = row[SOURCE_UID_COLUMN]
    expected_label_raw = expected_labels_by_uid[str(source_uid)]
    expected = to_label_name(expected_label_raw)
    agree_count = sum(1 for column in label_columns if row[column] == expected)
    return {
        SOURCE_UID_COLUMN: source_uid,
        **{column: row[column] for column in label_columns},
        "expected_label": expected_label_raw,
        "agree_count": agree_count,
        "decision": _classify_decision(agree_count, min_agreement),
    }


def _classify_decision(agree_count: int, min_agreement: int) -> str:
    """Map an agreement count to a decision: 'keep' when >= min_agreement, 'discard' when zero, else 'review'."""
    if agree_count >= min_agreement:
        return "keep"
    if agree_count == 0:
        return "discard"
    return "review"
