import math
import re
from collections import Counter

import pandas as pd


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


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase unicode word tokens (\\w+ matches)."""
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)
