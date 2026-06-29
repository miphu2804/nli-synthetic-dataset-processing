import json

import pandas as pd
import pytest
from src.schemas import (
    DatasetConversionRequest,
    DatasetConversionResponse,
    DatasetOutputConfig,
    DatasetWriteRequest,
)
from src.services.data_processing_service import DataProcessingService


def test_conversion_schema_defaults() -> None:
    request = DatasetConversionRequest(input_path="dataset.tsv")
    assert request.output_path is None
    assert request.sheet_name is None
    assert request.sep is None

    response = DatasetConversionResponse(
        status="converted",
        input_path="/tmp/dataset.tsv",
        input_format="tsv",
        output_path="/tmp/dataset.csv",
        rows_written=2,
        column_count=2,
        columns=["premise", "label"],
    )
    assert response.output_format == "csv"


def test_csv_window_matches_full_read_and_preserves_total_row_count(
    tmp_path, monkeypatch
):
    path = tmp_path / "dataset.csv"
    source = pd.DataFrame(
        [
            {
                "source_uid": "row-1",
                "premise": "First premise",
                "hypothesis": "First hypothesis",
                "label": 0,
            },
            {
                "source_uid": "row-2",
                "premise": "Premise with\nan embedded newline",
                "hypothesis": "Second hypothesis",
                "label": 1,
            },
            {
                "source_uid": "row-3",
                "premise": "Third premise",
                "hypothesis": "Third hypothesis",
                "label": 2,
            },
            {
                "source_uid": "row-4",
                "premise": "Fourth premise",
                "hypothesis": "Fourth hypothesis",
                "label": 0,
            },
        ]
    )
    source.to_csv(path, index=False)
    full_read = pd.read_csv(path)
    read_csv = pd.read_csv
    read_calls = []

    def track_windowed_reads(*args, **kwargs):
        read_calls.append(kwargs)
        assert kwargs.get("chunksize") or "nrows" in kwargs
        return read_csv(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", track_windowed_reads)

    reader = DataProcessingService()
    actual = reader.read_dataframe(str(path), row_offset=1, row_limit=2)
    response = reader.read_dataset(str(path), batch_offset=1, batch_size=2)

    pd.testing.assert_frame_equal(actual, full_read.iloc[1:3])
    assert response.row_count == len(full_read)
    assert response.rows == full_read.iloc[1:3].to_dict(orient="records")
    assert any(call.get("chunksize") for call in read_calls)
    assert any(call.get("nrows") == 2 for call in read_calls)


def test_parquet_window_matches_full_read_and_preserves_total_row_count(
    tmp_path, monkeypatch
):
    path = tmp_path / "dataset.parquet"
    source = pd.DataFrame(
        [
            {"source_uid": f"row-{index}", "value": index, "text": f"text-{index}"}
            for index in range(6)
        ]
    )
    source.to_parquet(path, index=False, row_group_size=2)
    full_read = pd.read_parquet(path)
    monkeypatch.setattr(
        pd,
        "read_parquet",
        lambda *_args, **_kwargs: pytest.fail("full Parquet read is not allowed"),
    )

    reader = DataProcessingService()
    actual = reader.read_dataframe(str(path), row_offset=1, row_limit=3)
    response = reader.read_dataset(str(path), batch_offset=1, batch_size=3)

    pd.testing.assert_frame_equal(actual, full_read.iloc[1:4])
    assert response.row_count == len(full_read)
    assert response.rows == full_read.iloc[1:4].to_dict(orient="records")


def test_writer_supports_parquet_default_csv_and_rejects_unknown_suffix(
    tmp_path, monkeypatch
):
    rows = [
        {"source_uid": "row-1", "premise": "Premise 1", "label": 0},
        {"source_uid": "row-2", "premise": "Premise 2", "label": 1},
    ]
    writer = DataProcessingService()
    reader = DataProcessingService()

    parquet_path = tmp_path / "written.parquet"
    parquet_response = writer.write_dataset(
        DatasetWriteRequest(
            rows=rows,
            output=DatasetOutputConfig(path=str(parquet_path)),
        )
    )

    assert parquet_response.output_format == "parquet"
    pd.testing.assert_frame_equal(
        reader.read_dataframe(str(parquet_path)),
        pd.DataFrame(rows),
    )

    monkeypatch.chdir(tmp_path)
    csv_response = writer.write_dataset(DatasetWriteRequest(rows=rows))
    expected_csv_path = tmp_path / "outputs" / "output.csv"

    assert csv_response.output_format == "csv"
    assert csv_response.output_path == str(expected_csv_path)
    pd.testing.assert_frame_equal(pd.read_csv(expected_csv_path), pd.DataFrame(rows))

    with pytest.raises(
        ValueError,
        match=r"Unsupported format: \.json\. Supported: \.csv, \.parquet\.",
    ):
        writer.write_dataset(
            DatasetWriteRequest(
                rows=rows,
                output=DatasetOutputConfig(path=str(tmp_path / "written.json")),
            )
        )


def test_convert_to_csv_supports_common_tabular_formats(tmp_path):
    service = DataProcessingService()
    source = pd.DataFrame(
        [
            {"source_uid": "row-1", "premise": "Premise 1", "label": 0},
            {"source_uid": "row-2", "premise": "Premise 2", "label": 1},
        ]
    )

    csv_path = tmp_path / "source.csv"
    source.to_csv(csv_path, index=False)
    csv_response = service.convert_to_csv(str(csv_path))
    assert csv_response.output_path == str(tmp_path / "source_canonical.csv")
    pd.testing.assert_frame_equal(pd.read_csv(csv_response.output_path), source)

    tsv_path = tmp_path / "source.tsv"
    source.to_csv(tsv_path, index=False, sep="\t")
    tsv_response = service.convert_to_csv(str(tsv_path))
    assert tsv_response.output_path == str(tmp_path / "source.csv")
    pd.testing.assert_frame_equal(pd.read_csv(tsv_response.output_path), source)

    parquet_path = tmp_path / "source.parquet"
    source.to_parquet(parquet_path, index=False)
    explicit_output = tmp_path / "explicit-output.csv"
    parquet_response = service.convert_to_csv(
        str(parquet_path),
        output_path=str(explicit_output),
    )
    assert parquet_response.output_path == str(explicit_output)
    pd.testing.assert_frame_equal(pd.read_csv(explicit_output), source)

    xlsx_path = tmp_path / "source.xlsx"
    source.to_excel(xlsx_path, index=False)
    xlsx_response = service.convert_to_csv(str(xlsx_path))
    pd.testing.assert_frame_equal(pd.read_csv(xlsx_response.output_path), source)

    jsonl_path = tmp_path / "source.jsonl"
    jsonl_path.write_text(
        "\n".join(json.dumps(row) for row in source.to_dict(orient="records")) + "\n",
        encoding="utf-8",
    )
    jsonl_response = service.convert_to_csv(str(jsonl_path))
    pd.testing.assert_frame_equal(pd.read_csv(jsonl_response.output_path), source)

    json_path = tmp_path / "source.json"
    json_path.write_text(
        json.dumps(source.to_dict(orient="records")),
        encoding="utf-8",
    )
    json_response = service.convert_to_csv(str(json_path))
    pd.testing.assert_frame_equal(pd.read_csv(json_response.output_path), source)


def test_convert_to_csv_rejects_unsupported_missing_and_nested_inputs(tmp_path):
    service = DataProcessingService()
    unsupported_path = tmp_path / "source.txt"
    unsupported_path.write_text("not tabular", encoding="utf-8")
    with pytest.raises(
        ValueError,
        match=r"Unsupported conversion format: \.txt\.",
    ):
        service.convert_to_csv(str(unsupported_path))

    with pytest.raises(FileNotFoundError, match="Dataset not found"):
        service.convert_to_csv(str(tmp_path / "missing.csv"))

    nested_json_path = tmp_path / "nested.json"
    nested_json_path.write_text(
        json.dumps([{"source_uid": "row-1", "meta": {"difficulty": "hard"}}]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Nested JSON values are not supported"):
        service.convert_to_csv(str(nested_json_path))

    csv_path = tmp_path / "valid.csv"
    pd.DataFrame([{"source_uid": "row-1", "label": 0}]).to_csv(csv_path, index=False)
    with pytest.raises(ValueError, match="output_path must end with .csv"):
        service.convert_to_csv(
            str(csv_path),
            output_path=str(tmp_path / "bad.parquet"),
        )
