from pathlib import Path

import pandas as pd
from src.schemas import DatasetWriteRequest, DatasetWriteResponse


class DatasetWriterService:
    """Write rows to CSV or Parquet."""

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
