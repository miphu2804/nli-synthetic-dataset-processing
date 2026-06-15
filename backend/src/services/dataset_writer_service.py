from pathlib import Path

import pandas as pd

from src.schemas import DatasetWriteRequest, DatasetWriteResponse


class DatasetWriterService:
    """Write translated rows to CSV."""

    def write_dataset(self, request: DatasetWriteRequest) -> DatasetWriteResponse:
        if not request.rows:
            raise ValueError("rows must not be empty.")

        output_path = self._resolve_output_path(
            explicit_path=request.output.path,
            file_name=request.output.file_name,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        dataframe = pd.DataFrame(request.rows)
        dataframe.to_csv(output_path, index=False)

        return DatasetWriteResponse(
            status="written",
            output_format="csv",
            output_path=str(output_path),
            rows_written=int(len(dataframe)),
        )

    @staticmethod
    def _resolve_output_path(
        explicit_path: str | None,
        file_name: str | None,
    ) -> Path:
        if explicit_path:
            return Path(explicit_path).expanduser().resolve()

        resolved_file_name = file_name or "translated-output.csv"
        if not resolved_file_name.endswith(".csv"):
            resolved_file_name = f"{resolved_file_name}.csv"

        return Path("outputs").resolve() / resolved_file_name
