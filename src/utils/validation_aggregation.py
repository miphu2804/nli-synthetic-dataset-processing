import math
import re
from collections import Counter
from pathlib import Path

import pandas as pd

SOURCE_UID_COLUMN = "source_uid"
PREDICTED_LABEL_COLUMN = "predicted_label"


def build_validation_vote_table(
    model_label_paths: dict[str, str | Path],
    min_agreement: int = 2,
) -> pd.DataFrame:
    if not model_label_paths:
        raise ValueError("model_label_paths must include at least one model file.")

    label_tables = [
        _read_model_label_column(model_name, path)
        for model_name, path in model_label_paths.items()
    ]
    _validate_same_source_uids(label_tables)

    vote_table = label_tables[0]
    for label_table in label_tables[1:]:
        vote_table = vote_table.merge(label_table, on=SOURCE_UID_COLUMN, how="inner")

    label_columns = [
        column for column in vote_table.columns if column.endswith("_label")
    ]
    vote_rows = []
    for _, row in vote_table.iterrows():
        labels = [str(row[column]) for column in label_columns]
        counts = Counter(labels)
        consensus_label, consensus_size = counts.most_common(1)[0]
        agreement_status = _agreement_status(
            consensus_size, len(label_columns), min_agreement
        )
        vote_rows.append(
            {
                SOURCE_UID_COLUMN: row[SOURCE_UID_COLUMN],
                **{column: row[column] for column in label_columns},
                **{
                    f"vote_count_{label}": counts[label]
                    for label in sorted(counts.keys())
                },
                "consensus_label": consensus_label,
                "consensus_size": consensus_size,
                "agreement_status": agreement_status,
            }
        )
    return pd.DataFrame(vote_rows)


def attach_masked_text(
    masked_dataset: pd.DataFrame,
    vote_table: pd.DataFrame,
) -> pd.DataFrame:
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


def compute_hypothesis_label_pmi(
    dataframe: pd.DataFrame,
    label_column: str = "consensus_label",
    text_column: str = "hypothesis",
    min_joint_count: int = 1,
) -> pd.DataFrame:
    required_columns = [text_column, label_column]
    missing_columns = [
        column for column in required_columns if column not in dataframe.columns
    ]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"PMI dataframe is missing required columns: {missing}")

    token_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    joint_counts: Counter[tuple[str, str]] = Counter()
    total_tokens = 0

    for _, row in dataframe.iterrows():
        label = str(row[label_column])
        tokens = _tokenize(str(row[text_column]))
        for token in tokens:
            token_counts[token] += 1
            label_counts[label] += 1
            joint_counts[(token, label)] += 1
            total_tokens += 1

    if total_tokens == 0:
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
        p_token_label = joint_count / total_tokens
        p_token = token_counts[token] / total_tokens
        p_label = label_counts[label] / total_tokens
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


def _read_model_label_column(model_name: str, path: str | Path) -> pd.DataFrame:
    dataframe = _read_table(path)
    required_columns = [SOURCE_UID_COLUMN, PREDICTED_LABEL_COLUMN]
    missing_columns = [
        column for column in required_columns if column not in dataframe.columns
    ]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Model label file is missing required columns: {missing}")

    label_column = f"{_normalize_model_name(model_name)}_label"
    return dataframe[[SOURCE_UID_COLUMN, PREDICTED_LABEL_COLUMN]].rename(
        columns={PREDICTED_LABEL_COLUMN: label_column}
    )


def _validate_same_source_uids(label_tables: list[pd.DataFrame]) -> None:
    expected_uids = set(label_tables[0][SOURCE_UID_COLUMN].astype(str))
    for label_table in label_tables[1:]:
        current_uids = set(label_table[SOURCE_UID_COLUMN].astype(str))
        if current_uids != expected_uids:
            raise ValueError(
                "All model label files must contain the same source_uid set."
            )


def _agreement_status(
    consensus_size: int,
    model_count: int,
    min_agreement: int,
) -> str:
    if consensus_size == model_count:
        return "unanimous"
    if consensus_size >= min_agreement:
        return "majority"
    return "review"


def _read_table(path: str | Path) -> pd.DataFrame:
    table_path = Path(path)
    if table_path.suffix.lower() == ".parquet":
        return pd.read_parquet(table_path)
    return pd.read_csv(table_path)


def _normalize_model_name(model_name: str) -> str:
    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", model_name.strip().lower()).strip("_")
    if not normalized:
        raise ValueError("model_name must contain at least one alphanumeric character.")
    return normalized


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)
