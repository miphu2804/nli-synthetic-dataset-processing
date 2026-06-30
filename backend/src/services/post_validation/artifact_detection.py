import math
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from src.utils.tabular_io import read_tabular

PMI_THRESHOLD = 1.0
MIN_JOINT_COUNT = 3


class ArtifactDetectionService:
    def detect(
        self,
        input_path,
        output_dir,
        label_column: str,
        text_column: str,
        uid_column: str,
        pmi_threshold: float,
        min_joint_count: int,
    ) -> dict:
        input_path = Path(input_path)
        output_dir = Path(output_dir)
        dataframe = read_tabular(input_path)
        artifact_tokens, flagged_rows = flag_pmi_artifacts(
            dataframe,
            label_column=label_column,
            text_column=text_column,
            uid_column=uid_column,
            pmi_threshold=pmi_threshold,
            min_joint_count=min_joint_count,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        tokens_output = output_dir / "pmi_artifact_tokens.csv"
        rows_output = output_dir / "pmi_flagged_rows.csv"
        artifact_tokens.to_csv(tokens_output, index=False)
        flagged_rows.to_csv(rows_output, index=False)
        return {
            "tokens_output": tokens_output,
            "rows_output": rows_output,
            "total_rows": len(dataframe),
            "artifact_tokens": len(artifact_tokens),
            "flagged_rows": len(flagged_rows),
        }


def tokenize_artifact_text(text: str) -> list[str]:
    """Tokenize text into lowercase unicode word tokens (\\w+ matches)."""
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


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
        tokens = set(tokenize_artifact_text(str(row[text_column])))
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
        tokens = set(tokenize_artifact_text(str(row[text_column])))
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
