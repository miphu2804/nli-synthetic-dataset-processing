import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.services.post_validation.dataset_builders import (
    build_retained_dataset,
    build_review_dataset,
)
from src.services.post_validation.voting import build_validation_vote_table
from src.utils.project_paths import resolve_data_path
from src.utils.tabular_io import read_tabular, read_tabular_columns

DATASET_SUFFIXES = (".csv", ".parquet")
VERDICT_REQUIRED_COLUMNS = {"source_uid", "predicted_label", "reason"}


@dataclass(frozen=True)
class VerdictFileCandidate:
    path: Path
    columns: list[str]
    model_name: str
    is_valid: bool


class ValidationAggregationService:
    def aggregate(
        self,
        valid_candidates: list[VerdictFileCandidate],
        masked_dataset_path: Path,
        output_dir: Path,
        expected_labels: dict,
    ) -> dict:
        model_prediction_paths = {
            candidate.model_name: candidate.path for candidate in valid_candidates
        }
        vote_table = build_validation_vote_table(
            model_prediction_paths, expected_labels
        )
        masked_df = read_tabular(masked_dataset_path)
        _validate_masked_dataset(masked_df, expected_labels)
        retained_df = build_retained_dataset(masked_df, vote_table)
        review_df = build_review_dataset(masked_df, vote_table)

        votes_output = output_dir / "validation_votes.csv"
        validated_output = output_dir / "validated_dataset.csv"
        review_output = output_dir / "review_dataset.csv"
        with tempfile.TemporaryDirectory(dir=output_dir) as staging_dir:
            staging = Path(staging_dir)
            vote_table.to_csv(staging / "validation_votes.csv", index=False)
            retained_df.to_csv(staging / "validated_dataset.csv", index=False)
            review_df.to_csv(staging / "review_dataset.csv", index=False)
            shutil.move(str(staging / "validation_votes.csv"), votes_output)
            shutil.move(str(staging / "validated_dataset.csv"), validated_output)
            shutil.move(str(staging / "review_dataset.csv"), review_output)

        decision_counts = vote_table["decision"].value_counts().to_dict()
        return {
            "votes_output": votes_output,
            "validated_output": validated_output,
            "review_output": review_output,
            "total_rows": len(vote_table),
            "keep": decision_counts.get("keep", 0),
            "discard": decision_counts.get("discard", 0),
            "review": decision_counts.get("review", 0),
            "retained_rows": len(retained_df),
            "review_rows": len(review_df),
        }


def discover_verdict_files(verdicts_dir: Path) -> list[Path]:
    if not verdicts_dir.exists():
        return []
    return [
        path
        for path in sorted(verdicts_dir.iterdir())
        if path.is_file() and path.suffix.lower() in DATASET_SUFFIXES
    ]


def build_verdict_candidates(paths: list[Path]) -> list[VerdictFileCandidate]:
    candidates: list[VerdictFileCandidate] = []
    for path in paths:
        try:
            columns = read_tabular_columns(path)
        except Exception:
            columns = []
        is_valid = VERDICT_REQUIRED_COLUMNS.issubset(columns)
        candidates.append(
            VerdictFileCandidate(
                path=path,
                columns=columns,
                model_name=path.stem,
                is_valid=is_valid,
            )
        )
    return candidates


def load_expected_labels(
    path: Path, uid_column: str, label_column: str
) -> dict[str, object]:
    dataframe = read_tabular(path)
    for column in (uid_column, label_column):
        if column not in dataframe.columns:
            raise ValueError(f"Expected-label dataset is missing column: {column}")
    if dataframe[uid_column].isnull().any():
        raise ValueError(f"Expected-label dataset contains null {uid_column} values.")
    uid_strs = dataframe[uid_column].astype(str)
    duplicates = sorted(uid_strs[uid_strs.duplicated()].unique())
    if duplicates:
        raise ValueError(
            f"Expected-label dataset contains duplicate {uid_column}: "
            f"{', '.join(duplicates[:5])}"
        )
    return {
        str(uid): label
        for uid, label in zip(dataframe[uid_column], dataframe[label_column])
    }


def default_consensus_output_dir(expected_input_path: Path) -> Path:
    return resolve_data_path("validated", expected_input_path.stem)


def _validate_masked_dataset(masked_df, expected_labels: dict) -> None:
    if "source_uid" not in masked_df.columns:
        raise ValueError("masked dataset is missing required column: source_uid")
    if masked_df["source_uid"].isnull().any():
        raise ValueError("masked dataset contains null source_uid values.")
    masked_uid_strs = masked_df["source_uid"].astype(str)
    duplicates = sorted(masked_uid_strs[masked_uid_strs.duplicated()].unique())
    if duplicates:
        raise ValueError(
            f"masked dataset contains duplicate source_uid: {', '.join(duplicates[:5])}"
        )
    masked_uid_set = set(masked_uid_strs)
    expected_uid_set = set(str(key) for key in expected_labels)
    if masked_uid_set != expected_uid_set:
        missing = sorted(expected_uid_set - masked_uid_set)
        extra = sorted(masked_uid_set - expected_uid_set)
        parts = []
        if missing:
            parts.append(f"masked dataset is missing UIDs: {', '.join(missing[:5])}")
        if extra:
            parts.append(
                "masked dataset has extra UIDs not in expected labels: "
                f"{', '.join(extra[:5])}"
            )
        raise ValueError("; ".join(parts))
