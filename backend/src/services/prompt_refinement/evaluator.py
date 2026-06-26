from __future__ import annotations

from pathlib import Path

import pandas as pd
from src.schemas.prompt_refinement_schema import PromptRoundEvaluation
from src.utils.nli_labels import require_canonical_label
from src.utils.validation_aggregation import compute_fleiss_kappa

KAPPA_THRESHOLD = 0.85
DATASET_SUFFIXES = {".csv", ".parquet"}
VERDICT_COLUMNS = {"source_uid", "predicted_label", "reason"}


class PromptRefinementEvaluator:
    """Evaluate calibration/verdict inputs without MLflow side effects."""

    def evaluate_inputs(
        self,
        verdicts_dir: str | Path,
        calibration_input: str | Path,
        *,
        include_summary_fields: bool = True,
    ) -> PromptRoundEvaluation:
        verdict_paths = self.discover_verdicts(Path(verdicts_dir))
        model_label_paths = {path.stem: path for path in verdict_paths}
        kappa_result = compute_fleiss_kappa(model_label_paths)
        calibration_path = Path(calibration_input)
        (
            sample_count,
            calibration,
            uid_column,
        ) = self.validate_calibration_input(calibration_path, verdict_paths[0])
        kappa = float(kappa_result["kappa"])
        disagreements = self.build_disagreement_rows(model_label_paths)

        calibration_with_source_uid = calibration.copy()
        calibration_with_source_uid["source_uid"] = calibration_with_source_uid[
            uid_column
        ].astype(str)

        return PromptRoundEvaluation(
            verdict_paths=verdict_paths,
            model_label_paths=model_label_paths,
            kappa_result=kappa_result,
            kappa=kappa,
            decision=self.decision(kappa),
            calibration_path=calibration_path,
            sample_count=sample_count,
            calibration=calibration_with_source_uid,
            calibration_uid_column=uid_column,
            disagreements=disagreements,
            n_disagreements=len(disagreements),
            label_distribution=(
                self.label_distribution(calibration) if include_summary_fields else {}
            ),
            model_summaries=(
                self.model_summaries(model_label_paths)
                if include_summary_fields
                else []
            ),
        )

    @staticmethod
    def decision(kappa: float) -> str:
        if kappa >= KAPPA_THRESHOLD:
            return "eligible_to_lock"
        return "refine_prompt"

    @classmethod
    def discover_verdicts(cls, verdicts_dir: Path) -> list[Path]:
        if not verdicts_dir.is_dir():
            raise FileNotFoundError(f"Verdicts directory not found: {verdicts_dir}")
        valid_paths = []
        for path in sorted(verdicts_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in DATASET_SUFFIXES:
                continue
            dataframe = cls.read_table(path)
            if VERDICT_COLUMNS.issubset(dataframe.columns):
                valid_paths.append(path)
        if len(valid_paths) != 3:
            raise ValueError(
                f"Prompt refinement requires exactly 3 valid verdict files, "
                f"found {len(valid_paths)}."
            )
        return valid_paths

    @classmethod
    def validate_calibration_input(
        cls,
        calibration_path: Path,
        verdict_path: Path,
    ) -> tuple[int, pd.DataFrame, str]:
        if not calibration_path.exists():
            raise FileNotFoundError(
                f"Calibration dataset not found: {calibration_path}"
            )
        calibration = cls.read_table(calibration_path)
        uid_column = (
            "source_uid"
            if "source_uid" in calibration.columns
            else "uid" if "uid" in calibration.columns else None
        )
        if uid_column is None or "label" not in calibration.columns:
            raise ValueError(
                "Calibration dataset must contain source_uid or uid, plus label."
            )
        if calibration[uid_column].isnull().any():
            raise ValueError("Calibration dataset contains null source UID values.")
        calibration_uids = calibration[uid_column].astype(str)
        if calibration_uids.duplicated().any():
            raise ValueError(
                "Calibration dataset contains duplicate source UID values."
            )
        verdict = cls.read_table(verdict_path)
        verdict_uids = set(verdict["source_uid"].astype(str))
        if set(calibration_uids) != verdict_uids:
            raise ValueError(
                "Calibration dataset source UIDs must match verdict source UIDs."
            )
        return len(calibration), calibration, uid_column

    @staticmethod
    def uid_column(dataframe: pd.DataFrame) -> str:
        if "source_uid" in dataframe.columns:
            return "source_uid"
        if "uid" in dataframe.columns:
            return "uid"
        raise ValueError("Dataset must contain source_uid or uid.")

    @staticmethod
    def label_distribution(dataframe: pd.DataFrame) -> dict[str, int]:
        if "label" not in dataframe.columns:
            raise ValueError("Calibration dataset must contain label.")
        labels = dataframe["label"].apply(require_canonical_label)
        return {
            str(label): int(count) for label, count in labels.value_counts().items()
        }

    @classmethod
    def model_summaries(cls, model_label_paths: dict[str, Path]) -> list[dict]:
        summaries = []
        for model, path in sorted(model_label_paths.items()):
            dataframe = cls.read_table(path)
            labels = dataframe["predicted_label"].apply(require_canonical_label)
            summaries.append(
                {
                    "model": model,
                    "path": str(path),
                    "n_rows": int(len(dataframe)),
                    "label_distribution": {
                        str(label): int(count)
                        for label, count in labels.value_counts().items()
                    },
                }
            )
        return summaries

    @classmethod
    def build_disagreement_rows(
        cls,
        model_label_paths: dict[str, Path],
    ) -> pd.DataFrame:
        merged = None
        label_columns = []
        for model, path in model_label_paths.items():
            dataframe = cls.read_table(path)[
                ["source_uid", "predicted_label", "reason"]
            ].copy()
            # Canonicalize labels so equivalent numeric/named forms (e.g. 0 and
            # "entailment") count as agreement, matching compute_fleiss_kappa.
            dataframe["predicted_label"] = dataframe["predicted_label"].apply(
                require_canonical_label
            )
            dataframe = dataframe.rename(
                columns={
                    "predicted_label": f"{model}_label",
                    "reason": f"{model}_reason",
                }
            )
            label_columns.append(f"{model}_label")
            merged = (
                dataframe
                if merged is None
                else merged.merge(dataframe, on="source_uid", how="inner")
            )
        assert merged is not None
        disagreement_mask = merged[label_columns].astype(str).nunique(axis=1) > 1
        return merged[disagreement_mask].reset_index(drop=True)

    @staticmethod
    def read_table(path: Path) -> pd.DataFrame:
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path)
