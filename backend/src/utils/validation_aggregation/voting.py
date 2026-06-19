from pathlib import Path

import pandas as pd
from src.utils.nli_labels import require_canonical_label
from src.utils.validation_aggregation.model_labels import (
    SOURCE_UID_COLUMN,
    _merge_model_labels,
)


def build_validation_vote_table(
    model_label_paths: dict[str, str | Path],
    expected_labels: dict[str, str | int],
    min_agreement: int = 2,
) -> pd.DataFrame:
    """Build a per-row vote table from multiple models' labels scored against expected_labels.

    Each row records the per-model labels, the count of models agreeing with the expected label, and a
    keep/review/discard decision (see _classify_decision). Raises if a row has no expected_label.
    """
    vote_table, label_columns = _merge_model_labels(model_label_paths)

    model_count = len(label_columns)
    if not 1 <= min_agreement <= model_count:
        raise ValueError(
            f"min_agreement must be between 1 and {model_count} (got {min_agreement})."
        )

    verdict_uids = set(vote_table[SOURCE_UID_COLUMN].astype(str))
    expected_uids = set(str(k) for k in expected_labels)
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

    vote_rows = []
    for _, row in vote_table.iterrows():
        source_uid = row[SOURCE_UID_COLUMN]
        uid_key = str(source_uid)
        expected_label_raw = expected_labels[uid_key]
        expected = require_canonical_label(expected_label_raw)
        agree_count = sum(1 for column in label_columns if row[column] == expected)
        decision = _classify_decision(agree_count, min_agreement)
        vote_rows.append(
            {
                SOURCE_UID_COLUMN: source_uid,
                **{column: row[column] for column in label_columns},
                "expected_label": expected_label_raw,
                "agree_count": agree_count,
                "decision": decision,
            }
        )
    return pd.DataFrame(vote_rows)


def _classify_decision(agree_count: int, min_agreement: int) -> str:
    """Map an agreement count to a decision: 'keep' when >= min_agreement, 'discard' when zero, else 'review'."""
    if agree_count >= min_agreement:
        return "keep"
    if agree_count == 0:
        return "discard"
    return "review"
