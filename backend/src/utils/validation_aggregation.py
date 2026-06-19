import math
import re
from collections import Counter
from pathlib import Path

import pandas as pd
from src.utils.nli_labels import CANONICAL_LABEL_NAMES_IN_ORDER, require_canonical_label

SOURCE_UID_COLUMN = "source_uid"
PREDICTED_LABEL_COLUMN = "predicted_label"


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


def compute_fleiss_kappa(
    model_label_paths: dict[str, str | Path],
    categories: list[str] | None = None,
) -> dict:
    """Compute Fleiss' Kappa inter-model agreement across the models' label files.

    Returns a dict with the kappa score, item/rater counts, the resolved categories, and per-category
    proportions. Raises if fewer than 2 models, no items, or labels fall outside the provided categories.
    """
    merged, label_columns = _merge_model_labels(model_label_paths)
    n_raters = len(label_columns)
    n_items = len(merged)
    if n_raters < 2:
        raise ValueError("Fleiss' Kappa requires at least 2 models (raters).")
    if n_items < 1:
        raise ValueError("Fleiss' Kappa requires at least 1 item.")

    item_labels = [
        [require_canonical_label(row[column]) for column in label_columns]
        for _, row in merged.iterrows()
    ]
    if categories is None:
        categories = list(CANONICAL_LABEL_NAMES_IN_ORDER)
    categories = _resolve_kappa_categories(item_labels, categories)
    kappa, per_category_proportion = _fleiss_kappa_from_counts(
        item_labels, categories, n_raters
    )

    return {
        "kappa": float(kappa),
        "n_items": n_items,
        "n_raters": n_raters,
        "categories": categories,
        "per_category_proportion": per_category_proportion,
    }


def _resolve_kappa_categories(
    item_labels: list[list[str]],
    categories: list[str] | None,
) -> list[str]:
    """Return the kappa category list: sorted observed labels when none given, else validate every label is allowed.

    Raises ValueError if an observed label falls outside the provided categories.
    """
    if categories is None:
        return sorted({label for labels in item_labels for label in labels})
    allowed = set(categories)
    unknown = sorted(
        {label for labels in item_labels for label in labels if label not in allowed}
    )
    if unknown:
        raise ValueError(
            f"Labels outside the provided categories: {', '.join(unknown)}"
        )
    return categories


def _fleiss_kappa_from_counts(
    item_labels: list[list[str]],
    categories: list[str],
    n_raters: int,
) -> tuple[float, dict[str, float]]:
    """Compute Fleiss' Kappa and per-category proportions from per-item label assignments.

    Builds the item-by-category count matrix, then kappa = (P_bar - P_e) / (1 - P_e), where P_bar is the
    mean per-item agreement and P_e the expected agreement from category marginals. Returns (kappa, proportions).
    """
    n_items = len(item_labels)
    counts = []
    for labels in item_labels:
        label_count = Counter(labels)
        counts.append([label_count.get(category, 0) for category in categories])

    p_i_values = [
        (sum(value * value for value in row) - n_raters) / (n_raters * (n_raters - 1))
        for row in counts
    ]
    p_bar = sum(p_i_values) / n_items

    per_category_proportion = {}
    for index, category in enumerate(categories):
        category_total = sum(row[index] for row in counts)
        per_category_proportion[category] = category_total / (n_items * n_raters)

    p_e = sum(value * value for value in per_category_proportion.values())
    kappa = 1.0 if (1 - p_e) == 0 else (p_bar - p_e) / (1 - p_e)
    return kappa, per_category_proportion


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


def apply_paraphrases(
    dataset: pd.DataFrame,
    flagged_rows: pd.DataFrame,
    paraphrases: pd.DataFrame,
    uid_column: str = "source_uid",
    text_column: str = "hypothesis",
    artifact_tokens_column: str = "artifact_tokens",
) -> tuple[pd.DataFrame, int]:
    """Overwrite hypotheses for exactly the PMI-flagged rows with their paraphrased rewrites.

    Requires flagged_rows UID set == paraphrases UID set ⊆ dataset UID set.
    Each rewrite must be non-empty, changed, and must not contain any token listed
    in that row's artifact_tokens_column. Returns (paraphrased_dataset, replaced_count).
    Row order and columns of ``dataset`` are preserved.
    """
    for frame_name, frame in (("dataset", dataset), ("paraphrases", paraphrases)):
        missing = [c for c in (uid_column, text_column) if c not in frame.columns]
        if missing:
            raise ValueError(
                f"{frame_name} is missing required columns: {', '.join(missing)}"
            )
    missing_flagged_cols = [
        c for c in (uid_column, artifact_tokens_column) if c not in flagged_rows.columns
    ]
    if missing_flagged_cols:
        raise ValueError(
            f"flagged_rows is missing required columns: {', '.join(missing_flagged_cols)}"
        )

    if flagged_rows[uid_column].isnull().any():
        raise ValueError("flagged_rows contains null source_uid values.")
    if flagged_rows[artifact_tokens_column].isnull().any():
        raise ValueError("flagged_rows contains null artifact_tokens values.")
    flagged_uid_strs_list = [str(uid) for uid in flagged_rows[uid_column]]
    flagged_uid_dups = [
        uid for uid, count in Counter(flagged_uid_strs_list).items() if count > 1
    ]
    if flagged_uid_dups:
        raise ValueError(
            f"flagged_rows contains duplicate source_uid: {', '.join(sorted(flagged_uid_dups)[:5])}"
        )

    flagged_uids = set(flagged_uid_strs_list)
    paraphrase_uids_list = [str(uid) for uid in paraphrases[uid_column]]
    paraphrase_uids = set(paraphrase_uids_list)

    if len(paraphrase_uids) != len(paraphrase_uids_list):
        raise ValueError("paraphrases contains duplicate source_uid values.")

    missing_from_paraphrases = sorted(flagged_uids - paraphrase_uids)
    if missing_from_paraphrases:
        raise ValueError(
            f"Flagged UID(s) not in paraphrases: "
            f"{', '.join(missing_from_paraphrases[:5])}"
        )
    extra_in_paraphrases = sorted(paraphrase_uids - flagged_uids)
    if extra_in_paraphrases:
        raise ValueError(
            f"Paraphrase UID(s) not in flagged rows: "
            f"{', '.join(extra_in_paraphrases[:5])}"
        )

    dataset_uids = {str(uid) for uid in dataset[uid_column]}
    unknown = sorted(flagged_uids - dataset_uids)
    if unknown:
        raise ValueError(
            f"Flagged UID(s) not found in dataset: {', '.join(unknown[:5])}"
        )

    # Build original text lookup and artifact-tokens lookup.
    original_texts = {
        str(uid): text for uid, text in zip(dataset[uid_column], dataset[text_column])
    }
    artifact_lookup: dict[str, set[str]] = {}
    for uid, tokens_str in zip(
        flagged_rows[uid_column], flagged_rows[artifact_tokens_column]
    ):
        tokens = set(_tokenize(str(tokens_str))) if tokens_str else set()
        artifact_lookup[str(uid)] = tokens

    replacements: dict[str, str] = {}
    for uid, new_text in zip(paraphrases[uid_column], paraphrases[text_column]):
        uid_str = str(uid)
        original = original_texts[uid_str]
        new = str(new_text).strip()
        if not new:
            raise ValueError(f"Paraphrase for {uid_str!r} is empty.")
        if new == original:
            raise ValueError(
                f"Paraphrase for {uid_str!r} is unchanged from the original."
            )
        artifact_tokens = artifact_lookup.get(uid_str, set())
        if artifact_tokens:
            rewrite_tokens = set(_tokenize(new))
            still_present = sorted(artifact_tokens & rewrite_tokens)
            if still_present:
                raise ValueError(
                    f"Paraphrase for {uid_str!r} still contains artifact "
                    f"token(s): {', '.join(still_present)}"
                )
        replacements[uid_str] = new

    if not replacements:
        return dataset.reset_index(drop=True), 0

    processed = dataset.copy()
    processed[text_column] = [
        replacements.get(str(uid), original)
        for uid, original in zip(processed[uid_column], processed[text_column])
    ]
    return processed.reset_index(drop=True), len(replacements)


def compute_hypothesis_label_pmi(
    dataframe: pd.DataFrame,
    label_column: str = "consensus_label",
    text_column: str = "hypothesis",
    min_joint_count: int = 1,
) -> pd.DataFrame:
    """Compute example-level pointwise mutual information between hypothesis tokens and labels (paper Eq. 2).

    PMI(w, y) = log( P(w, y) / (P(w) P(y)) ), where probabilities are over examples: P(w) is the fraction of
    hypotheses containing token w, P(y) the fraction of examples with label y, P(w, y) the fraction with both.
    Returns a DataFrame of (token, label, pmi, token_count, label_count, joint_count) — counts are example
    counts — for pairs meeting min_joint_count, sorted by descending PMI. Empty frame when there are no examples
    or no qualifying pairs.
    """
    required_columns = [text_column, label_column]
    missing_columns = [
        column for column in required_columns if column not in dataframe.columns
    ]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"PMI dataframe is missing required columns: {missing}")

    (
        token_counts,
        label_counts,
        joint_counts,
        n_examples,
    ) = _count_token_label_cooccurrence(dataframe, label_column, text_column)

    if n_examples == 0:
        return pd.DataFrame(
            columns=[
                "token",
                "label",
                "pmi",
                "token_count",
                "label_count",
                "joint_count",
            ]
        )

    PMI_COLUMNS = ["token", "label", "pmi", "token_count", "label_count", "joint_count"]
    rows = []
    for (token, label), joint_count in joint_counts.items():
        if joint_count < min_joint_count:
            continue
        p_token_label = joint_count / n_examples
        p_token = token_counts[token] / n_examples
        p_label = label_counts[label] / n_examples
        rows.append(
            {
                "token": token,
                "label": label,
                "pmi": math.log(p_token_label / (p_token * p_label)),
                "token_count": token_counts[token],
                "label_count": label_counts[label],
                "joint_count": joint_count,
            }
        )
    if not rows:
        return pd.DataFrame(columns=PMI_COLUMNS)
    return pd.DataFrame(rows).sort_values(
        ["pmi", "joint_count", "token"],
        ascending=[False, False, True],
        ignore_index=True,
    )


def flag_pmi_artifacts(
    dataframe: pd.DataFrame,
    label_column: str = "expected_label",
    text_column: str = "hypothesis",
    uid_column: str = "source_uid",
    pmi_threshold: float = 1.0,
    min_joint_count: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Detect label-leaking artifact tokens and the rows that carry them.

    Returns (artifact_tokens, flagged_rows):
    - artifact_tokens: the PMI table filtered to (token, label) pairs whose PMI is
      at or above ``pmi_threshold`` — i.e. tokens that leak a specific label.
    - flagged_rows: rows whose ``text_column`` contains an artifact token that
      leaks that row's own ``label_column`` value. These are the hypotheses to
      paraphrase before the dataset is published.

    This only detects/flags; rewriting the flagged hypotheses is a separate step.
    """
    required_columns = [uid_column, text_column, label_column]
    missing_columns = [
        column for column in required_columns if column not in dataframe.columns
    ]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Artifact dataframe is missing required columns: {missing}")

    pmi_table = compute_hypothesis_label_pmi(
        dataframe,
        label_column=label_column,
        text_column=text_column,
        min_joint_count=min_joint_count,
    )
    artifact_tokens = pmi_table[pmi_table["pmi"] >= pmi_threshold].reset_index(
        drop=True
    )
    artifact_pairs = {
        (str(token), str(label))
        for token, label in zip(artifact_tokens["token"], artifact_tokens["label"])
    }

    FLAGGED_COLUMNS = [
        uid_column,
        text_column,
        label_column,
        "artifact_tokens",
        "artifact_count",
    ]
    flagged_rows = _flag_rows_with_artifacts(
        dataframe, artifact_pairs, uid_column, text_column, label_column
    )
    flagged_df = pd.DataFrame(flagged_rows, columns=FLAGGED_COLUMNS)
    return artifact_tokens, flagged_df


def _merge_model_labels(
    model_label_paths: dict[str, str | Path],
) -> tuple[pd.DataFrame, list[str]]:
    """Read each model's predicted-label column, validate they share the same source_uids, and inner-join them.

    Returns (merged_dataframe, label_columns) where label_columns are the per-model '*_label' columns.
    Raises ValueError if no model files are given, model names collide, or UID sets differ.
    """
    if not model_label_paths:
        raise ValueError("model_label_paths must include at least one model file.")
    normalized_names = [_normalize_model_name(name) for name in model_label_paths]
    if len(set(normalized_names)) != len(normalized_names):
        raise ValueError("Model names collide after normalization.")
    label_tables = [
        _read_model_label_column(model_name, path)
        for model_name, path in model_label_paths.items()
    ]
    _validate_same_source_uids(label_tables)
    merged = label_tables[0]
    for label_table in label_tables[1:]:
        merged = merged.merge(label_table, on=SOURCE_UID_COLUMN, how="inner")
    label_columns = [column for column in merged.columns if column.endswith("_label")]
    return merged, label_columns


def _classify_decision(agree_count: int, min_agreement: int) -> str:
    """Map an agreement count to a decision: 'keep' when >= min_agreement, 'discard' when zero, else 'review'."""
    if agree_count >= min_agreement:
        return "keep"
    if agree_count == 0:
        return "discard"
    return "review"


def _count_token_label_cooccurrence(
    dataframe: pd.DataFrame,
    label_column: str,
    text_column: str,
) -> tuple[Counter, Counter, Counter, int]:
    """Count, at the example level, how many hypotheses contain each token, carry each label, and both.

    Matches the paper's Eq. (2): a token is counted at most once per hypothesis (presence, not frequency),
    and a label belongs to the example (not to each token). Returns
    (token_doc_counts, label_doc_counts, joint_doc_counts, n_examples).
    """
    token_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    joint_counts: Counter[tuple[str, str]] = Counter()
    n_examples = 0
    for _, row in dataframe.iterrows():
        label = str(row[label_column])
        tokens = set(_tokenize(str(row[text_column])))
        n_examples += 1
        label_counts[label] += 1
        for token in tokens:
            token_counts[token] += 1
            joint_counts[(token, label)] += 1
    return token_counts, label_counts, joint_counts, n_examples


def _flag_rows_with_artifacts(
    dataframe: pd.DataFrame,
    artifact_pairs: set[tuple[str, str]],
    uid_column: str,
    text_column: str,
    label_column: str,
) -> list[dict]:
    """Scan each row for artifact tokens that leak its own label, returning a flagged-row dict per row that has at least one hit."""
    flagged_rows = []
    for _, row in dataframe.iterrows():
        row_label = str(row[label_column])
        tokens = set(_tokenize(str(row[text_column])))
        hits = sorted(token for token in tokens if (token, row_label) in artifact_pairs)
        if hits:
            flagged_rows.append(
                {
                    uid_column: row[uid_column],
                    text_column: row[text_column],
                    label_column: row[label_column],
                    "artifact_tokens": " ".join(hits),
                    "artifact_count": len(hits),
                }
            )
    return flagged_rows


def _read_model_label_column(model_name: str, path: str | Path) -> pd.DataFrame:
    """Read a model's label file and return a [source_uid, {model}_label] frame.

    Raises if required columns are missing, any source_uid is null or duplicate, any
    reason is blank, or any predicted_label is outside the three-class domain.
    """
    dataframe = _read_table(path)
    required_columns = [SOURCE_UID_COLUMN, PREDICTED_LABEL_COLUMN, "reason"]
    missing_columns = [
        column for column in required_columns if column not in dataframe.columns
    ]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Model label file is missing required columns: {missing}")

    if dataframe[SOURCE_UID_COLUMN].isnull().any():
        raise ValueError(f"Model '{model_name}' contains null source_uid values.")

    uid_strs = dataframe[SOURCE_UID_COLUMN].astype(str)
    duplicates = sorted(uid_strs[uid_strs.duplicated()].unique())
    if duplicates:
        preview = ", ".join(duplicates[:5])
        raise ValueError(
            f"Model '{model_name}' contains duplicate source_uid: {preview}"
        )

    blank_mask = dataframe["reason"].isnull() | (
        dataframe["reason"].astype(str).str.strip() == ""
    )
    if blank_mask.any():
        raise ValueError(f"Model '{model_name}' contains rows with a blank reason.")

    dataframe[PREDICTED_LABEL_COLUMN] = dataframe[PREDICTED_LABEL_COLUMN].apply(
        require_canonical_label
    )
    label_column = f"{_normalize_model_name(model_name)}_label"
    return dataframe[[SOURCE_UID_COLUMN, PREDICTED_LABEL_COLUMN]].rename(
        columns={PREDICTED_LABEL_COLUMN: label_column}
    )


def _validate_same_source_uids(label_tables: list[pd.DataFrame]) -> None:
    """Raise ValueError unless every model label table covers the exact same set of source_uids."""
    expected_uids = set(label_tables[0][SOURCE_UID_COLUMN].astype(str))
    for label_table in label_tables[1:]:
        current_uids = set(label_table[SOURCE_UID_COLUMN].astype(str))
        if current_uids != expected_uids:
            raise ValueError(
                "All model label files must contain the same source_uid set."
            )


def _read_table(path: str | Path) -> pd.DataFrame:
    """Read a table as a DataFrame, selecting parquet or CSV by file suffix."""
    table_path = Path(path)
    if table_path.suffix.lower() == ".parquet":
        return pd.read_parquet(table_path)
    return pd.read_csv(table_path)


def _normalize_model_name(model_name: str) -> str:
    """Normalize a model name to a lowercase alphanumeric/underscore slug; raise if it has no alphanumeric characters."""
    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", model_name.strip().lower()).strip("_")
    if not normalized:
        raise ValueError("model_name must contain at least one alphanumeric character.")
    return normalized


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase unicode word tokens (\\w+ matches)."""
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)
