import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from src.schemas import (
    DatasetConversionResponse,
    DatasetReadResponse,
    DatasetWriteRequest,
    DatasetWriteResponse,
)


class DataProcessingService:
    """File-level tabular reads, writes, and CSV conversion."""

    CONVERSION_FORMATS = (
        ".csv",
        ".tsv",
        ".parquet",
        ".xlsx",
        ".xls",
        ".jsonl",
        ".json",
    )

    def read_dataframe(
        self,
        path: str,
        row_offset: int = 0,
        row_limit: int | None = None,
    ) -> pd.DataFrame:
        """Read and return a raw DataFrame slice from a supported runtime dataset."""
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

    def write_dataset(self, request: DatasetWriteRequest) -> DatasetWriteResponse:
        if not request.rows:
            raise ValueError("rows must not be empty.")

        output_path = self._resolve_output_path(
            explicit_path=request.output.path,
            file_name=request.output.file_name,
        )
        file_extension = output_path.suffix.lower()
        if file_extension not in {".csv", ".parquet"}:
            raise ValueError(
                f"Unsupported format: {file_extension}. Supported: .csv, .parquet."
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        dataframe = pd.DataFrame(request.rows)
        output_format = file_extension.lstrip(".")
        if output_format == "parquet":
            dataframe.to_parquet(output_path, index=False)
        else:
            dataframe.to_csv(output_path, index=False)

        return DatasetWriteResponse(
            status="written",
            output_format=output_format,
            output_path=str(output_path),
            rows_written=int(len(dataframe)),
        )

    def convert_to_csv(
        self,
        input_path: str,
        output_path: str | None = None,
        *,
        sheet_name: str | int | None = None,
        sep: str | None = None,
    ) -> DatasetConversionResponse:
        """Normalize a supported tabular file to canonical CSV."""
        resolved_input = Path(input_path).expanduser().resolve()
        if not resolved_input.exists():
            raise FileNotFoundError(f"Dataset not found: {resolved_input}")

        file_extension = self._get_file_extension(resolved_input)
        dataframe = self._read_conversion_dataframe(
            resolved_input,
            file_extension,
            sheet_name=sheet_name,
            sep=sep,
        )
        self._reject_nested_values(dataframe)

        resolved_output = self._resolve_csv_output_path(resolved_input, output_path)
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(resolved_output, index=False)

        return DatasetConversionResponse(
            status="converted",
            input_path=str(resolved_input),
            input_format=file_extension.lstrip("."),
            output_path=str(resolved_output),
            rows_written=int(len(dataframe)),
            column_count=int(dataframe.shape[1]),
            columns=dataframe.columns.astype(str).tolist(),
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

    def _read_conversion_dataframe(
        self,
        path: Path,
        file_extension: str,
        *,
        sheet_name: str | int | None,
        sep: str | None,
    ) -> pd.DataFrame:
        if file_extension == ".csv":
            return pd.read_csv(path, sep=sep or ",")
        if file_extension == ".tsv":
            return pd.read_csv(path, sep=sep or "\t")
        if file_extension == ".parquet":
            return pd.read_parquet(path)
        if file_extension in {".xlsx", ".xls"}:
            try:
                return pd.read_excel(
                    path, sheet_name=0 if sheet_name is None else sheet_name
                )
            except ImportError as exc:
                raise ValueError(f"Could not read Excel file: {exc}") from exc
        if file_extension == ".jsonl":
            return pd.read_json(path, lines=True)
        if file_extension == ".json":
            return self._read_json_records(path)
        supported = ", ".join(self.CONVERSION_FORMATS)
        raise ValueError(
            f"Unsupported conversion format: {file_extension}. Supported: {supported}."
        )

    @staticmethod
    def _read_json_records(path: Path) -> pd.DataFrame:
        with path.open("r", encoding="utf-8") as handle:
            payload: Any = json.load(handle)
        if not isinstance(payload, list) or any(
            not isinstance(item, dict) for item in payload
        ):
            raise ValueError(
                "JSON conversion supports a top-level array of records only."
            )
        return pd.DataFrame(payload)

    @staticmethod
    def _reject_nested_values(dataframe: pd.DataFrame) -> None:
        for column in dataframe.columns:
            if (
                dataframe[column]
                .map(lambda value: isinstance(value, (dict, list)))
                .any()
            ):
                raise ValueError(
                    "Nested JSON values are not supported; provide flat records."
                )

    @staticmethod
    def _resolve_output_path(
        explicit_path: str | None,
        file_name: str | None,
    ) -> Path:
        if explicit_path:
            resolved_path = Path(explicit_path).expanduser().resolve()
            if not resolved_path.suffix:
                resolved_path = resolved_path.with_suffix(".csv")
            return resolved_path

        resolved_file_name = Path(file_name or "output")
        if not resolved_file_name.suffix:
            resolved_file_name = resolved_file_name.with_suffix(".csv")

        return Path("outputs").resolve() / resolved_file_name

    @staticmethod
    def _resolve_csv_output_path(input_path: Path, output_path: str | None) -> Path:
        if output_path:
            resolved_path = Path(output_path).expanduser().resolve()
            if resolved_path.suffix and resolved_path.suffix.lower() != ".csv":
                raise ValueError("output_path must end with .csv.")
            if not resolved_path.suffix:
                resolved_path = resolved_path.with_suffix(".csv")
            return resolved_path
        if input_path.suffix.lower() == ".csv":
            return input_path.with_name(f"{input_path.stem}_canonical.csv").resolve()
        return input_path.with_suffix(".csv").resolve()

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
