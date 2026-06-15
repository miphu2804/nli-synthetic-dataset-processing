import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.utils.validation_masking_cli import (
    default_output_path,
    discover_dataset_files,
    infer_uid_column,
    main,
)


class ValidationMaskingCliTest(unittest.TestCase):
    def test_infer_uid_column_prefers_source_uid(self) -> None:
        self.assertEqual(infer_uid_column(["uid", "source_uid"]), "source_uid")
        self.assertEqual(infer_uid_column(["uid"]), "uid")
        self.assertIsNone(infer_uid_column(["id"]))

    def test_default_output_path_adds_validation_masked_suffix(self) -> None:
        self.assertEqual(
            default_output_path(Path("data/generated/foo.csv")),
            Path("data/generated/foo_validation_masked.csv"),
        )

    def test_discover_dataset_files_finds_csv_and_parquet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "nested").mkdir()
            (root / "a.csv").write_text("source_uid,premise,hypothesis,label\n")
            (root / "nested" / "b.parquet").write_text("")
            (root / "c.txt").write_text("")

            discovered = discover_dataset_files([root])

        self.assertEqual(
            sorted(path.name for path in discovered),
            ["a.csv", "b.parquet"],
        )

    def test_main_writes_masked_dataset_with_noninteractive_args(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "generated.csv"
            output_path = root / "masked.csv"
            pd.DataFrame(
                [
                    {
                        "source_uid": "row-1",
                        "premise": "p",
                        "hypothesis": "h",
                        "label": 1,
                    }
                ]
            ).to_csv(input_path, index=False)

            exit_code = main(
                [
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--yes",
                    "--quiet",
                ]
            )

            masked = pd.read_csv(output_path)
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            list(masked.columns),
            ["source_uid", "premise", "hypothesis", "masked_label"],
        )
        self.assertNotIn("label", masked.columns)


if __name__ == "__main__":
    unittest.main()
