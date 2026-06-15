from pathlib import Path
from typing import Final

import pandas as pd

MASKED_LABEL_VALUE: Final = "[MASK]"
VALIDATION_PAYLOAD_COLUMNS: Final = (
    "source_uid",
    "premise",
    "hypothesis",
    "masked_label",
)


def build_masked_validation_dataset(
    dataframe: pd.DataFrame,
    uid_column: str,
    label_column: str = "label",
) -> pd.DataFrame:
    required_columns = [uid_column, "premise", "hypothesis", label_column]
    missing_columns = [
        column for column in required_columns if column not in dataframe.columns
    ]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Dataset is missing required columns: {missing}")

    masked_dataframe = dataframe[[uid_column, "premise", "hypothesis"]].copy()
    masked_dataframe = masked_dataframe.rename(columns={uid_column: "source_uid"})
    masked_dataframe["masked_label"] = MASKED_LABEL_VALUE
    return masked_dataframe[list(VALIDATION_PAYLOAD_COLUMNS)]


def write_masked_validation_dataset(
    dataframe: pd.DataFrame,
    output_path: str | Path,
    uid_column: str,
    label_column: str = "label",
) -> Path:
    masked_dataframe = build_masked_validation_dataset(
        dataframe,
        uid_column=uid_column,
        label_column=label_column,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".parquet":
        masked_dataframe.to_parquet(path, index=False)
    else:
        masked_dataframe.to_csv(path, index=False)
    return path
