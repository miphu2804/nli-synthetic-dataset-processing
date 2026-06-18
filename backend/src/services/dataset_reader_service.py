from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
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
            dataframe, total_rows = self._read_csv_window(
                resolved_path, row_offset, row_limit
            )
        elif file_extension == ".parquet":
            dataframe, total_rows = self._read_parquet_window(
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

    def _read_csv_window(
        self,
        path: Path,
        row_offset: int,
        row_limit: int | None,
    ) -> tuple[pd.DataFrame, int]:
        """Count parsed CSV records and read only the requested row window."""
        total_rows = 0
        # CSV records may contain quoted newlines, so count parsed one-column chunks
        # instead of physical lines while avoiding full-file materialization.
        for chunk in pd.read_csv(path, usecols=[0], chunksize=100_000):
            total_rows += int(chunk.shape[0])

        dataframe = pd.read_csv(
            path,
            skiprows=range(1, row_offset + 1),
            nrows=row_limit or total_rows,
        )
        slice_start = min(row_offset, total_rows)
        dataframe.index = pd.RangeIndex(
            start=slice_start,
            stop=slice_start + len(dataframe),
        )
        return dataframe, total_rows

    def _read_parquet_window(
        self,
        path: Path,
        row_offset: int,
        row_limit: int | None,
    ) -> tuple[pd.DataFrame, int]:
        """Read only row groups overlapping the requested Parquet window."""
        parquet_file = pq.ParquetFile(path)
        total_rows = int(parquet_file.metadata.num_rows)
        window_end = min(row_offset + (row_limit or total_rows), total_rows)

        row_groups = []
        row_group_start = 0
        first_row_group_start = 0
        for row_group_index in range(parquet_file.num_row_groups):
            row_group_rows = parquet_file.metadata.row_group(row_group_index).num_rows
            row_group_end = row_group_start + row_group_rows
            if row_group_end > row_offset and row_group_start < window_end:
                if not row_groups:
                    first_row_group_start = row_group_start
                row_groups.append(row_group_index)
            row_group_start = row_group_end

        if row_groups:
            table = parquet_file.read_row_groups(row_groups)
            table = table.slice(
                max(row_offset - first_row_group_start, 0),
                max(window_end - row_offset, 0),
            )
        else:
            table = parquet_file.schema_arrow.empty_table()

        dataframe = table.to_pandas()
        if isinstance(dataframe.index, pd.RangeIndex):
            slice_start = min(row_offset, total_rows)
            dataframe.index = pd.RangeIndex(
                start=slice_start,
                stop=slice_start + len(dataframe),
            )
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
