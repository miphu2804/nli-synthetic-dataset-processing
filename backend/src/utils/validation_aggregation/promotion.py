from pathlib import Path

import pandas as pd
from src.utils.validation_aggregation.dataset_builders import attach_masked_text
from src.utils.validation_aggregation.model_labels import SOURCE_UID_COLUMN
from src.utils.validation_aggregation.voting import build_validation_vote_table


def promote_revalidated_paraphrases(
    paraphrased_dataset: pd.DataFrame,
    revalidation_queue: pd.DataFrame,
    model_label_paths: dict[str, str | Path],
    expected_labels: dict[str, str | int],
    uid_column: str = SOURCE_UID_COLUMN,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Promote paraphrased rows that pass semantic revalidation.

    The input dataset is the full paraphrased candidate. The revalidation queue
    identifies changed rows. Changed rows with a `keep` decision remain in the
    promoted dataset; changed rows with `review` or `discard` are removed from
    the publishable output and written to the review artifact.
    """
    if len(model_label_paths) != 3:
        raise ValueError(
            f"Paraphrase promotion requires exactly 3 verdict files, "
            f"found {len(model_label_paths)}."
        )
    _validate_dataset_uids(paraphrased_dataset, uid_column, "paraphrased dataset")
    _validate_revalidation_queue(revalidation_queue, uid_column)

    changed_uids = set(revalidation_queue[uid_column].astype(str))
    dataset_uids = set(paraphrased_dataset[uid_column].astype(str))
    missing_from_dataset = sorted(changed_uids - dataset_uids)
    if missing_from_dataset:
        raise ValueError(
            "Revalidation UID(s) not found in paraphrased dataset: "
            f"{', '.join(missing_from_dataset[:5])}"
        )

    normalized_expected_labels = {
        str(key): value for key, value in expected_labels.items()
    }
    missing_expected = sorted(
        uid for uid in changed_uids if uid not in normalized_expected_labels
    )
    if missing_expected:
        raise ValueError(
            "Revalidation UID(s) missing trusted expected labels: "
            f"{', '.join(missing_expected[:5])}"
        )

    revalidation_expected_labels = {
        uid: normalized_expected_labels[uid] for uid in sorted(changed_uids)
    }
    vote_table = build_validation_vote_table(
        model_label_paths,
        revalidation_expected_labels,
    )

    accepted_uids = set(
        vote_table.loc[vote_table["decision"] == "keep", SOURCE_UID_COLUMN].astype(str)
    )
    rejected_uids = changed_uids - accepted_uids
    promoted_mask = (
        paraphrased_dataset[uid_column]
        .astype(str)
        .map(lambda uid: uid not in changed_uids or uid in accepted_uids)
    )
    promoted = paraphrased_dataset[promoted_mask].reset_index(drop=True)

    rejected_votes = vote_table[
        vote_table[SOURCE_UID_COLUMN].astype(str).isin(rejected_uids)
    ].reset_index(drop=True)
    review = attach_masked_text(
        revalidation_queue.rename(columns={uid_column: SOURCE_UID_COLUMN}),
        rejected_votes,
    )
    return promoted, review, vote_table.reset_index(drop=True)


def _validate_dataset_uids(
    dataframe: pd.DataFrame,
    uid_column: str,
    frame_name: str,
) -> None:
    if uid_column not in dataframe.columns:
        raise ValueError(f"{frame_name} is missing required column: {uid_column}")
    if dataframe[uid_column].isnull().any():
        raise ValueError(f"{frame_name} contains null {uid_column} values.")
    uid_strs = dataframe[uid_column].astype(str)
    duplicates = sorted(uid_strs[uid_strs.duplicated()].unique())
    if duplicates:
        raise ValueError(
            f"{frame_name} contains duplicate {uid_column}: "
            f"{', '.join(duplicates[:5])}"
        )


def _validate_revalidation_queue(
    revalidation_queue: pd.DataFrame,
    uid_column: str,
) -> None:
    required_columns = [uid_column, "premise", "hypothesis", "masked_label"]
    missing = [
        column
        for column in required_columns
        if column not in revalidation_queue.columns
    ]
    if missing:
        raise ValueError(
            f"revalidation queue is missing required columns: {', '.join(missing)}"
        )
    _validate_dataset_uids(revalidation_queue, uid_column, "revalidation queue")
    if set(revalidation_queue["masked_label"].astype(str)) != {"[MASK]"}:
        raise ValueError("revalidation queue masked_label values must all be [MASK].")
