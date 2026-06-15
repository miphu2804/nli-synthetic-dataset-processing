from pathlib import Path

import pandas as pd

from src.schemas import DatasetReadResponse

DEFAULT_BATCH_SIZE = 5


class DatasetReaderService:
    """Template method — skeleton read_dataset dispatches to format-specific batch readers."""

    def read_dataset(
        self,
        path: str,
        batch_size: int | None = None,
        batch_offset: int = 0,
    ) -> DatasetReadResponse:
        """Resolve path, detect format, dispatch to batch reader, build response."""
        resolved_path = Path(path).expanduser().resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"Dataset not found: {resolved_path}")
        file_extension = self._get_file_extension(resolved_path)

        if file_extension == ".csv":
            dataframe, total_rows = self._read_csv_batch(
                resolved_path, batch_size, batch_offset
            )
        elif file_extension == ".parquet":
            dataframe, total_rows = self._read_parquet_batch(
                resolved_path, batch_size, batch_offset
            )
        else:
            raise ValueError(
                f"Unsupported format: {file_extension}. Supported: .csv, .parquet."
            )

        batch_size = batch_size or DEFAULT_BATCH_SIZE
        return self._build_response(
            path=resolved_path,
            file_extension=file_extension,
            total_rows=total_rows,
            dataframe=dataframe,
        )

    @staticmethod
    def _get_file_extension(path: Path) -> str:
        """Extract file extension with dot prefix, lowercased."""
        return path.suffix.lower()

    def _read_csv_batch(
        self,
        path: Path,
        batch_size: int | None,
        batch_offset: int,
    ) -> tuple[pd.DataFrame, int]:
        """Load full CSV, count via shape, then slice one batch."""
        dataframe = pd.read_csv(path)
        total_rows = int(dataframe.shape[0])
        dataframe = dataframe.iloc[
            batch_offset : batch_offset + (batch_size or total_rows)
        ]
        return dataframe, total_rows

    def _read_parquet_batch(
        self,
        path: Path,
        batch_size: int | None,
        batch_offset: int,
    ) -> tuple[pd.DataFrame, int]:
        """Load full parquet, slice one batch, report total."""
        dataframe = pd.read_parquet(path)
        total_rows = int(dataframe.shape[0])
        dataframe = dataframe.iloc[
            batch_offset : batch_offset + (batch_size or len(dataframe))
        ]
        return dataframe, total_rows

    def _build_response(
        self,
        path: Path,
        file_extension: str,
        total_rows: int,
        dataframe: pd.DataFrame,
    ) -> DatasetReadResponse:
        return DatasetReadResponse(
            path=str(path),
            format=file_extension.lstrip("."),
            row_count=total_rows,
            column_count=dataframe.shape[1],
            columns=dataframe.columns.astype(str).tolist(),
            dtypes={
                str(column): str(dtype) for column, dtype in dataframe.dtypes.items()
            },
            null_counts={
                str(column): int(count)
                for column, count in dataframe.isna().sum().items()
            },
            rows=[
                {str(key): value for key, value in row.items()}
                for row in dataframe.to_dict(orient="records")
            ],
        )
