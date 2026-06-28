import re
from pathlib import Path

import pandas as pd
from src.utils.nli_labels import to_label_name
from src.utils.tabular_io import read_tabular

SOURCE_UID_COLUMN = "source_uid"
PREDICTED_LABEL_COLUMN = "predicted_label"


def _normalize_model_name(model_name: str) -> str:
    """Normalize a model name to a lowercase alphanumeric/underscore slug; raise if it has no alphanumeric characters."""
    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", model_name.strip().lower()).strip("_")
    if not normalized:
        raise ValueError("model_name must contain at least one alphanumeric character.")
    return normalized


def _read_model_prediction_table(model_name: str, path: str | Path) -> pd.DataFrame:
    """Read a model prediction file and return a [source_uid, {model}_label] frame.

    Raises if required columns are missing, any source_uid is null or duplicate, any
    reason is blank, or any predicted_label is outside the three-class domain.
    """
    dataframe = read_tabular(path)
    required_columns = [SOURCE_UID_COLUMN, PREDICTED_LABEL_COLUMN, "reason"]
    missing_columns = [
        column for column in required_columns if column not in dataframe.columns
    ]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(
            f"Model prediction file is missing required columns: {missing}"
        )

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
        to_label_name
    )
    label_column = f"{_normalize_model_name(model_name)}_label"
    return dataframe[[SOURCE_UID_COLUMN, PREDICTED_LABEL_COLUMN]].rename(
        columns={PREDICTED_LABEL_COLUMN: label_column}
    )


def _validate_same_source_uids(prediction_tables: list[pd.DataFrame]) -> None:
    """Raise ValueError unless every model prediction table covers the exact same source_uid set."""
    expected_uids = set(prediction_tables[0][SOURCE_UID_COLUMN].astype(str))
    for prediction_table in prediction_tables[1:]:
        current_uids = set(prediction_table[SOURCE_UID_COLUMN].astype(str))
        if current_uids != expected_uids:
            raise ValueError(
                "All model prediction files must contain the same source_uid set."
            )


def _merge_model_predictions(
    model_prediction_paths: dict[str, str | Path],
) -> tuple[pd.DataFrame, list[str]]:
    """Read each model prediction file, validate shared source_uids, and inner-join them.

    Returns (merged_dataframe, label_columns) where label_columns are the per-model '*_label' columns.
    Raises ValueError if no model files are given, model names collide, or UID sets differ.
    """
    if not model_prediction_paths:
        raise ValueError("model_prediction_paths must include at least one model file.")
    normalized_names = [_normalize_model_name(name) for name in model_prediction_paths]
    if len(set(normalized_names)) != len(normalized_names):
        raise ValueError("Model names collide after normalization.")
    prediction_tables = [
        _read_model_prediction_table(model_name, path)
        for model_name, path in model_prediction_paths.items()
    ]
    _validate_same_source_uids(prediction_tables)
    merged = prediction_tables[0]
    for prediction_table in prediction_tables[1:]:
        merged = merged.merge(prediction_table, on=SOURCE_UID_COLUMN, how="inner")
    label_columns = [column for column in merged.columns if column.endswith("_label")]
    return merged, label_columns
