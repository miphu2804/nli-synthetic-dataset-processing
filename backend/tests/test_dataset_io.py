import pandas as pd
import pytest
from src.schemas import DatasetOutputConfig, DatasetWriteRequest
from src.services.dataset_reader_service import DatasetReaderService
from src.services.dataset_writer_service import DatasetWriterService


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

    reader = DatasetReaderService()
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

    reader = DatasetReaderService()
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
    writer = DatasetWriterService()
    reader = DatasetReaderService()

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
