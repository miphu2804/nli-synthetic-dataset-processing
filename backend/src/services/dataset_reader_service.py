from pathlib import Path

import pandas as pd
from src.schemas import DatasetReadResponse


class DatasetReaderService:
    """Expose raw DataFrame and response reads with format dispatch in one helper."""

    def read_dataframe(
        self,
        path: str,
        row_offset: int = 0,
        row_limit: int | None = None,
    ) -> pd.DataFrame:
        """Read and return a raw DataFrame slice from a supported dataset."""
        dataframe, _, _, _ = self._read_dataframe_slice(path, row_offset, row_limit)
        return dataframe

    def read_dataset(
        self,
        path: str,
        batch_size: int | None = None,
        batch_offset: int = 0,
    ) -> DatasetReadResponse:
        """Return a structured response from a format-dispatched DataFrame slice."""
        dataframe, total_rows, resolved_path, file_extension = (
            self._read_dataframe_slice(path, batch_offset, batch_size)
        )

        return self._build_response(
            path=resolved_path,
            file_extension=file_extension,
            total_rows=total_rows,
            dataframe=dataframe,
        )

    def _read_dataframe_slice(
        self,
        path: str,
        row_offset: int,
        row_limit: int | None,
    ) -> tuple[pd.DataFrame, int, Path, str]:
        """Resolve path, detect format, and return a DataFrame slice with metadata."""
        resolved_path = Path(path).expanduser().resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"Dataset not found: {resolved_path}")
        file_extension = self._get_file_extension(resolved_path)

        if file_extension == ".csv":
            dataframe, total_rows = self._read_csv_batch(
                resolved_path, row_offset, row_limit
            )
        elif file_extension == ".parquet":
            dataframe, total_rows = self._read_parquet_batch(
                resolved_path, row_offset, row_limit
            )
        else:
            raise ValueError(
                f"Unsupported format: {file_extension}. Supported: .csv, .parquet."
            )
        return dataframe, total_rows, resolved_path, file_extension

    @staticmethod
    def _get_file_extension(path: Path) -> str:
        """Extract file extension with dot prefix, lowercased."""
        return path.suffix.lower()

    def _read_csv_batch(
        self,
        path: Path,
        row_offset: int,
        row_limit: int | None,
    ) -> tuple[pd.DataFrame, int]:
        """Load full CSV, count via shape, then slice one batch."""
        dataframe = pd.read_csv(path)
        total_rows = int(dataframe.shape[0])
        dataframe = dataframe.iloc[row_offset : row_offset + (row_limit or total_rows)]
        return dataframe, total_rows

    def _read_parquet_batch(
        self,
        path: Path,
        row_offset: int,
        row_limit: int | None,
    ) -> tuple[pd.DataFrame, int]:
        """Load full parquet, slice one batch, report total."""
        dataframe = pd.read_parquet(path)
        total_rows = int(dataframe.shape[0])
        dataframe = dataframe.iloc[row_offset : row_offset + (row_limit or total_rows)]
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
