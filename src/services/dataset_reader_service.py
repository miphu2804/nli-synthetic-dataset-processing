from pathlib import Path

import pandas as pd

from src.app_config import app_config
from src.schemas import DatasetReadResponse


class DatasetReaderService:
    """Facade over pandas for lightweight dataset batch reading."""

    def read_dataset(
        self,
        path: str,
        batch_size: int | None = None,
        batch_offset: int = 0,
        sheet_name: str | int | None = None,
        sep: str | None = None,
    ) -> DatasetReadResponse:
        resolved_path = Path(path).expanduser().resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"Dataset not found: {resolved_path}")

        normalized_batch_size = batch_size or app_config.DEFAULT_PREVIEW_ROWS
        dataframe, exact_row_count = self._load_dataframe(
            resolved_path,
            batch_size=normalized_batch_size,
            batch_offset=batch_offset,
            sheet_name=sheet_name,
            sep=sep,
        )

        return DatasetReadResponse(
            path=str(resolved_path),
            format=resolved_path.suffix.lower().lstrip(".") or "unknown",
            row_count=exact_row_count,
            column_count=int(dataframe.shape[1]),
            columns=[str(column) for column in dataframe.columns.tolist()],
            dtypes={
                str(column): str(dtype) for column, dtype in dataframe.dtypes.items()
            },
            null_counts={
                str(column): int(count)
                for column, count in dataframe.isnull().sum().items()
            },
            batch_size=normalized_batch_size,
            batch_offset=batch_offset,
            rows=self._to_records(dataframe),
        )

    def _load_dataframe(
        self,
        resolved_path: Path,
        batch_size: int,
        batch_offset: int,
        sheet_name: str | int | None,
        sep: str | None,
    ) -> tuple[pd.DataFrame, int]:
        suffix = resolved_path.suffix.lower()
        if suffix == ".csv":
            return (
                self._read_delimited_batch(
                    resolved_path,
                    sep=sep or ",",
                    batch_size=batch_size,
                    batch_offset=batch_offset,
                ),
                self._count_lines(resolved_path),
            )
        if suffix in {".tsv", ".txt"}:
            return (
                self._read_delimited_batch(
                    resolved_path,
                    sep=sep or "\t",
                    batch_size=batch_size,
                    batch_offset=batch_offset,
                ),
                self._count_lines(resolved_path),
            )
        if suffix == ".json":
            df = pd.read_json(resolved_path)
            return df.iloc[batch_offset : batch_offset + batch_size], int(df.shape[0])
        if suffix == ".jsonl":
            df = pd.read_json(resolved_path, lines=True)
            return df.iloc[batch_offset : batch_offset + batch_size], int(df.shape[0])
        if suffix in {".xlsx", ".xls"}:
            df = pd.read_excel(resolved_path, sheet_name=sheet_name or 0)
            return df.iloc[batch_offset : batch_offset + batch_size], int(df.shape[0])
        if suffix == ".parquet":
            df = pd.read_parquet(resolved_path)
            return df.iloc[batch_offset : batch_offset + batch_size], int(df.shape[0])
        if suffix == ".feather":
            df = pd.read_feather(resolved_path)
            return df.iloc[batch_offset : batch_offset + batch_size], int(df.shape[0])
        raise ValueError(
            "Unsupported dataset format. Supported: csv, tsv, txt, json, jsonl, xlsx, xls, parquet, feather."
        )

    def _read_delimited_batch(
        self,
        path: Path,
        sep: str,
        batch_size: int,
        batch_offset: int,
    ) -> pd.DataFrame:
        skip = max(0, batch_offset)
        return pd.read_csv(
            path,
            sep=sep,
            skiprows=lambda index: index != 0 and index <= skip,
            nrows=batch_size,
        )

    @staticmethod
    def _to_records(df: pd.DataFrame) -> list[dict[str, object]]:
        return [
            {str(k): v for k, v in row.items()}
            for row in df.where(pd.notnull(df), None).to_dict(orient="records")
        ]

    @staticmethod
    def _count_lines(path: Path) -> int:
        total = 0
        reader = pd.read_csv(
            path, usecols=[0], chunksize=100_000, dtype_backend="numpy_nullable"
        )
        for chunk in reader:
            total += len(chunk)
        return total
