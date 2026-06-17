import tempfile
import unittest
from pathlib import Path

import pandas as pd
from src.utils.validation_masking import (
    build_masked_validation_dataset,
    write_masked_validation_dataset,
)


class ValidationMaskingTest(unittest.TestCase):
    def test_build_masked_validation_dataset_drops_label_values(self) -> None:
        source = pd.DataFrame(
            [
                {
                    "uid": 7,
                    "premise": "p",
                    "hypothesis": "h",
                    "label": 1,
                    "extra": "keep-in-source-only",
                }
            ]
        )

        masked = build_masked_validation_dataset(source, uid_column="uid")

        self.assertEqual(
            list(masked.columns),
            ["source_uid", "premise", "hypothesis", "masked_label"],
        )
        self.assertEqual(masked.to_dict(orient="records")[0]["masked_label"], "[MASK]")
        self.assertNotIn("label", masked.columns)
        self.assertNotIn("extra", masked.columns)
        self.assertIn("label", source.columns)

    def test_build_masked_validation_dataset_requires_label_column(self) -> None:
        source = pd.DataFrame([{"uid": 7, "premise": "p", "hypothesis": "h"}])

        with self.assertRaisesRegex(ValueError, "label"):
            build_masked_validation_dataset(source, uid_column="uid")

    def test_write_masked_validation_dataset_persists_safe_columns(self) -> None:
        source = pd.DataFrame(
            [
                {
                    "source_uid": "row-1",
                    "premise": "p",
                    "hypothesis": "h",
                    "label": 0,
                }
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "validation_masked.csv"

            written_path = write_masked_validation_dataset(
                source,
                output_path=output_path,
                uid_column="source_uid",
            )

            masked = pd.read_csv(written_path)
        self.assertEqual(
            list(masked.columns),
            ["source_uid", "premise", "hypothesis", "masked_label"],
        )
        self.assertNotIn("label", masked.columns)


if __name__ == "__main__":
    unittest.main()
