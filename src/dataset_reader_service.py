from pathlib import Path

import pandas as pd

from src.app_config import app_config
from src.dataset_reader_schema import DatasetReadResponse


class DatasetReaderService:
    """Facade over pandas for lightweight dataset inspection."""

    def read_dataset(
        self,
        path: str,
        limit: int | None = None,
        sample_rows: int | None = None,
        sheet_name: str | int | None = None,
        sep: str | None = None,
    ) -> DatasetReadResponse:
        resolved_path = Path(path).expanduser().resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"Dataset not found: {resolved_path}")

        preview_limit = limit or app_config.DEFAULT_PREVIEW_ROWS
        sample_limit = sample_rows or app_config.DEFAULT_SAMPLE_ROWS

        dataframe = self._load_dataframe(
            resolved_path,
            sheet_name=sheet_name,
            sep=sep,
        )

        sample = dataframe.head(sample_limit)
        preview = dataframe.head(preview_limit).where(pd.notnull(dataframe), None)

        return DatasetReadResponse(
            path=str(resolved_path),
            format=resolved_path.suffix.lower().lstrip(".") or "unknown",
            row_count=int(dataframe.shape[0]),
            column_count=int(dataframe.shape[1]),
            columns=[str(column) for column in dataframe.columns.tolist()],
            dtypes={str(column): str(dtype) for column, dtype in dataframe.dtypes.items()},
            null_counts={
                str(column): int(count) for column, count in sample.isnull().sum().items()
            },
            preview=preview.to_dict(orient="records"),
        )

    def _load_dataframe(
        self,
        resolved_path: Path,
        sheet_name: str | int | None,
        sep: str | None,
    ) -> pd.DataFrame:
        suffix = resolved_path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(resolved_path, sep=sep or ",")
        if suffix in {".tsv", ".txt"}:
            return pd.read_csv(resolved_path, sep=sep or "\t")
        if suffix == ".json":
            return pd.read_json(resolved_path)
        if suffix == ".jsonl":
            return pd.read_json(resolved_path, lines=True)
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(resolved_path, sheet_name=sheet_name or 0)
        if suffix == ".parquet":
            return pd.read_parquet(resolved_path)
        if suffix == ".feather":
            return pd.read_feather(resolved_path)
        raise ValueError(
            "Unsupported dataset format. Supported: csv, tsv, txt, json, jsonl, xlsx, xls, parquet, feather."
        )
