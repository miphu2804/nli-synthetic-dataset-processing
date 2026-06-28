from pathlib import Path

import pandas as pd


def read_tabular(path: str | Path) -> pd.DataFrame:
    table_path = Path(path)
    if table_path.suffix.lower() == ".parquet":
        return pd.read_parquet(table_path)
    return pd.read_csv(table_path)


def read_tabular_columns(path: str | Path) -> list[str]:
    table_path = Path(path)
    if table_path.suffix.lower() == ".parquet":
        return list(pd.read_parquet(table_path, columns=[]).columns)
    return list(pd.read_csv(table_path, nrows=0).columns)
