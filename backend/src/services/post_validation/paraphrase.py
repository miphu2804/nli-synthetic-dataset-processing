from collections import Counter
from pathlib import Path

import pandas as pd
from src.services.post_validation.artifact_detection import tokenize_artifact_text
from src.services.post_validation.promotion import promote_revalidated_paraphrases
from src.services.post_validation.validation_aggregation import (
    VerdictFileCandidate,
    load_expected_labels,
)
from src.utils.tabular_io import read_tabular

SOURCE_UID_COLUMN = "source_uid"
TEXT_COLUMN = "hypothesis"
ARTIFACT_TOKENS_COLUMN = "artifact_tokens"
REVALIDATION_COLUMNS = [SOURCE_UID_COLUMN, "premise", TEXT_COLUMN, "label"]


class ParaphraseService:
    def apply(
        self,
        input_path: Path,
        flagged_rows_path: Path,
        paraphrases_path: Path,
        output_path: Path,
        revalidation_path: Path,
    ) -> dict:
        dataset = read_tabular(input_path)
        flagged_rows = read_tabular(flagged_rows_path)
        paraphrases = read_tabular(paraphrases_path)
        paraphrased, replaced = apply_paraphrases(
            dataset,
            flagged_rows,
            paraphrases,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        paraphrased.to_csv(output_path, index=False)

        revalidation = build_paraphrase_revalidation_queue(paraphrased, paraphrases)
        revalidation.to_csv(revalidation_path, index=False)

        return {
            "output_path": output_path,
            "revalidation_path": revalidation_path,
            "total_rows": len(paraphrased),
            "replaced_rows": replaced,
        }

    def promote(
        self,
        input_path: Path,
        revalidation_input_path: Path,
        verdict_candidates: list[VerdictFileCandidate],
        expected_input_path: Path,
        output_path: Path,
        review_output_path: Path,
        votes_output_path: Path,
        uid_column: str,
        label_column: str,
    ) -> dict:
        dataset = read_tabular(input_path)
        revalidation_queue = read_tabular(revalidation_input_path)
        expected_labels = load_expected_labels(
            expected_input_path,
            uid_column,
            label_column,
        )
        model_prediction_paths = {
            candidate.model_name: candidate.path for candidate in verdict_candidates
        }
        promoted, review, votes = promote_revalidated_paraphrases(
            paraphrased_dataset=dataset,
            revalidation_queue=revalidation_queue,
            model_prediction_paths=model_prediction_paths,
            expected_labels=expected_labels,
            uid_column=uid_column,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        review_output_path.parent.mkdir(parents=True, exist_ok=True)
        votes_output_path.parent.mkdir(parents=True, exist_ok=True)
        promoted.to_csv(output_path, index=False)
        review.to_csv(review_output_path, index=False)
        votes.to_csv(votes_output_path, index=False)
        decision_counts = votes["decision"].value_counts().to_dict()
        return {
            "output_path": output_path,
            "review_output_path": review_output_path,
            "votes_output_path": votes_output_path,
            "total_rows": len(dataset),
            "promoted_rows": len(promoted),
            "revalidated_rows": len(votes),
            "accepted_rewrites": decision_counts.get("keep", 0),
            "review_rewrites": decision_counts.get("review", 0),
            "discarded_rewrites": decision_counts.get("discard", 0),
        }


def apply_paraphrases(
    dataset: pd.DataFrame,
    flagged_rows: pd.DataFrame,
    paraphrases: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """Overwrite exactly the PMI-flagged hypotheses with paraphrased rewrites."""
    flagged_uids = _validate_flagged_rows(flagged_rows)
    paraphrase_uids = _validate_paraphrases(paraphrases)
    _validate_uid_sets(flagged_uids, paraphrase_uids, dataset)

    artifact_lookup = _build_artifact_lookup(flagged_rows)
    replacements = _build_replacements(dataset, paraphrases, artifact_lookup)
    if not replacements:
        return dataset.reset_index(drop=True), 0

    processed = dataset.copy()
    processed[TEXT_COLUMN] = [
        replacements.get(str(uid), original)
        for uid, original in zip(processed[SOURCE_UID_COLUMN], processed[TEXT_COLUMN])
    ]
    return processed.reset_index(drop=True), len(replacements)


def build_paraphrase_revalidation_queue(
    paraphrased_dataset: pd.DataFrame,
    paraphrases: pd.DataFrame,
) -> pd.DataFrame:
    """Build the blank-label revalidation queue for changed paraphrase rows."""
    _require_columns(
        "paraphrased dataset",
        paraphrased_dataset,
        [SOURCE_UID_COLUMN, "premise", TEXT_COLUMN],
    )
    _require_columns("paraphrases", paraphrases, [SOURCE_UID_COLUMN])

    changed_uids = {str(uid) for uid in paraphrases[SOURCE_UID_COLUMN]}
    revalidation = paraphrased_dataset[
        paraphrased_dataset[SOURCE_UID_COLUMN].astype(str).isin(changed_uids)
    ][[SOURCE_UID_COLUMN, "premise", TEXT_COLUMN]].copy()
    revalidation["label"] = ""
    return revalidation[REVALIDATION_COLUMNS].reset_index(drop=True)


def _validate_flagged_rows(flagged_rows: pd.DataFrame) -> set[str]:
    _require_columns(
        "flagged_rows",
        flagged_rows,
        [SOURCE_UID_COLUMN, ARTIFACT_TOKENS_COLUMN],
    )
    if flagged_rows[SOURCE_UID_COLUMN].isnull().any():
        raise ValueError("flagged_rows contains null source_uid values.")
    if flagged_rows[ARTIFACT_TOKENS_COLUMN].isnull().any():
        raise ValueError("flagged_rows contains null artifact_tokens values.")

    flagged_uid_strs = [str(uid) for uid in flagged_rows[SOURCE_UID_COLUMN]]
    duplicates = _duplicates(flagged_uid_strs)
    if duplicates:
        raise ValueError(
            "flagged_rows contains duplicate source_uid: "
            f"{', '.join(duplicates[:5])}"
        )
    return set(flagged_uid_strs)


def _validate_paraphrases(paraphrases: pd.DataFrame) -> set[str]:
    _require_columns("paraphrases", paraphrases, [SOURCE_UID_COLUMN, TEXT_COLUMN])
    paraphrase_uid_strs = [str(uid) for uid in paraphrases[SOURCE_UID_COLUMN]]
    duplicates = _duplicates(paraphrase_uid_strs)
    if duplicates:
        raise ValueError("paraphrases contains duplicate source_uid values.")
    return set(paraphrase_uid_strs)


def _validate_uid_sets(
    flagged_uids: set[str],
    paraphrase_uids: set[str],
    dataset: pd.DataFrame,
) -> None:
    _require_columns("dataset", dataset, [SOURCE_UID_COLUMN, TEXT_COLUMN])

    missing_from_paraphrases = sorted(flagged_uids - paraphrase_uids)
    if missing_from_paraphrases:
        raise ValueError(
            "Flagged UID(s) not in paraphrases: "
            f"{', '.join(missing_from_paraphrases[:5])}"
        )

    extra_in_paraphrases = sorted(paraphrase_uids - flagged_uids)
    if extra_in_paraphrases:
        raise ValueError(
            "Paraphrase UID(s) not in flagged rows: "
            f"{', '.join(extra_in_paraphrases[:5])}"
        )

    dataset_uids = {str(uid) for uid in dataset[SOURCE_UID_COLUMN]}
    unknown = sorted(flagged_uids - dataset_uids)
    if unknown:
        raise ValueError(
            f"Flagged UID(s) not found in dataset: {', '.join(unknown[:5])}"
        )


def _build_artifact_lookup(flagged_rows: pd.DataFrame) -> dict[str, set[str]]:
    return {
        str(uid): set(tokenize_artifact_text(str(tokens_str)))
        for uid, tokens_str in zip(
            flagged_rows[SOURCE_UID_COLUMN],
            flagged_rows[ARTIFACT_TOKENS_COLUMN],
        )
    }


def _build_replacements(
    dataset: pd.DataFrame,
    paraphrases: pd.DataFrame,
    artifact_lookup: dict[str, set[str]],
) -> dict[str, str]:
    original_texts = {
        str(uid): text
        for uid, text in zip(dataset[SOURCE_UID_COLUMN], dataset[TEXT_COLUMN])
    }

    replacements: dict[str, str] = {}
    for uid, new_text in zip(paraphrases[SOURCE_UID_COLUMN], paraphrases[TEXT_COLUMN]):
        uid_str = str(uid)
        original = original_texts[uid_str]
        new = str(new_text).strip()
        if not new:
            raise ValueError(f"Paraphrase for {uid_str!r} is empty.")
        if new == original:
            raise ValueError(
                f"Paraphrase for {uid_str!r} is unchanged from the original."
            )

        still_present = sorted(
            artifact_lookup.get(uid_str, set()) & set(tokenize_artifact_text(new))
        )
        if still_present:
            raise ValueError(
                f"Paraphrase for {uid_str!r} still contains artifact "
                f"token(s): {', '.join(still_present)}"
            )
        replacements[uid_str] = new
    return replacements


def _require_columns(
    frame_name: str,
    dataframe: pd.DataFrame,
    required_columns: list[str],
) -> None:
    missing = [column for column in required_columns if column not in dataframe.columns]
    if missing:
        raise ValueError(
            f"{frame_name} is missing required columns: {', '.join(missing)}"
        )


def _duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)
