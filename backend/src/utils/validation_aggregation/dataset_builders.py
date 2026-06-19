from collections import Counter

import pandas as pd
from src.utils.validation_aggregation.model_labels import SOURCE_UID_COLUMN


def attach_masked_text(
    masked_dataset: pd.DataFrame,
    vote_table: pd.DataFrame,
) -> pd.DataFrame:
    """Inner-join the masked dataset's premise/hypothesis text onto the vote table by source_uid; raise if text columns are missing."""
    required_columns = [SOURCE_UID_COLUMN, "premise", "hypothesis"]
    missing_columns = [
        column for column in required_columns if column not in masked_dataset.columns
    ]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Masked dataset is missing required columns: {missing}")
    return masked_dataset[required_columns].merge(
        vote_table,
        on=SOURCE_UID_COLUMN,
        how="inner",
    )


def _assert_masked_coverage(
    masked_dataset: pd.DataFrame,
    subset: pd.DataFrame,
    decision_name: str,
) -> None:
    """Raise if any subset source_uid is missing from (or duplicated in) masked_dataset.

    Guards the text join in build_retained_dataset / build_review_dataset against
    silently dropping rows (missing uid) or inflating them (one-to-many on a
    duplicated uid).
    """
    if SOURCE_UID_COLUMN not in masked_dataset.columns:
        raise ValueError(
            f"Masked dataset is missing required columns: {SOURCE_UID_COLUMN}"
        )
    masked_uid_counts = Counter(str(uid) for uid in masked_dataset[SOURCE_UID_COLUMN])
    subset_uids = [str(uid) for uid in subset[SOURCE_UID_COLUMN]]

    missing_uids = sorted({uid for uid in subset_uids if masked_uid_counts[uid] == 0})
    if missing_uids:
        raise ValueError(
            f"Expected {len(subset_uids)} {decision_name} rows, but masked dataset "
            f"is missing {len(missing_uids)} source_uid(s): {', '.join(missing_uids)}"
        )
    duplicate_uids = sorted({uid for uid in subset_uids if masked_uid_counts[uid] > 1})
    if duplicate_uids:
        raise ValueError(
            f"Masked dataset has duplicate source_uid(s) for {decision_name} rows: "
            f"{', '.join(duplicate_uids)}"
        )


def build_retained_dataset(
    masked_dataset: pd.DataFrame,
    vote_table: pd.DataFrame,
) -> pd.DataFrame:
    """Build the publishable dataset from vote-table rows decided 'keep', joined with masked text and relabeled expected_label -> label."""
    required_columns = ["decision", "expected_label"]
    missing_columns = [
        column for column in required_columns if column not in vote_table.columns
    ]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Vote table is missing required columns: {missing}")

    kept = vote_table[vote_table["decision"] == "keep"]
    _assert_masked_coverage(masked_dataset, kept, "kept")

    analysis_df = attach_masked_text(masked_dataset, kept)
    retained = analysis_df[
        [SOURCE_UID_COLUMN, "premise", "hypothesis", "expected_label"]
    ].rename(columns={"expected_label": "label"})
    return retained.reset_index(drop=True)


def build_review_dataset(
    masked_dataset: pd.DataFrame,
    vote_table: pd.DataFrame,
) -> pd.DataFrame:
    """Build the manual-review queue from vote-table rows decided 'review' (agree==1).

    Joins masked premise/hypothesis text onto the review rows and keeps the full
    vote context (per-model labels, expected_label, agree_count) so a human can
    see the disagreement. expected_label is NOT renamed to label — these rows are
    unverified and must not be published as-is.
    """
    required_columns = ["decision", "expected_label"]
    missing_columns = [
        column for column in required_columns if column not in vote_table.columns
    ]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Vote table is missing required columns: {missing}")

    review = vote_table[vote_table["decision"] == "review"]
    _assert_masked_coverage(masked_dataset, review, "review")

    analysis_df = attach_masked_text(masked_dataset, review)
    leading = [SOURCE_UID_COLUMN, "premise", "hypothesis"]
    rest = [column for column in analysis_df.columns if column not in leading]
    return analysis_df[leading + rest].reset_index(drop=True)
