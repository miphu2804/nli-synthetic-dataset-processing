from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.services.post_validation import compute_fleiss_kappa
from src.services.prompt_refinement.models import PromptRefinementEvaluation
from src.utils.nli_labels import to_label_name
from src.utils.tabular_io import read_tabular

KAPPA_THRESHOLD = 0.85
DATASET_SUFFIXES = {".csv", ".parquet"}
VERDICT_COLUMNS = {"source_uid", "predicted_label", "reason"}


class PromptRefinementEvaluator:
    """Evaluate calibration/verdict inputs without MLflow side effects."""

    def evaluate_inputs(
        self,
        verdicts_dir: str | Path,
        calibration_input: str | Path,
    ) -> PromptRefinementEvaluation:
        verdict_paths = self._discover_valid_verdict_files(Path(verdicts_dir))
        model_prediction_paths = {path.stem: path for path in verdict_paths}
        kappa_result = compute_fleiss_kappa(model_prediction_paths)
        calibration_path = Path(calibration_input)
        sample_count = self._load_validated_calibration(
            calibration_path, verdict_paths[0]
        )
        kappa = float(kappa_result["kappa"])
        disagreements = self._build_disagreement_rows(model_prediction_paths)

        return PromptRefinementEvaluation(
            model_prediction_paths=model_prediction_paths,
            kappa_result=kappa_result,
            kappa=kappa,
            decision=self.decide_outcome(kappa),
            calibration_path=calibration_path,
            sample_count=sample_count,
            disagreements=disagreements,
            rejected_sample_count=len(disagreements),
        )

    @staticmethod
    def decide_outcome(kappa: float) -> str:
        if kappa >= KAPPA_THRESHOLD:
            return "accepted"
        return "needs_prompt_update"

    @classmethod
    def _discover_valid_verdict_files(cls, verdicts_dir: Path) -> list[Path]:
        if not verdicts_dir.is_dir():
            raise FileNotFoundError(f"Verdicts directory not found: {verdicts_dir}")
        valid_paths = []
        for path in sorted(verdicts_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in DATASET_SUFFIXES:
                continue
            dataframe = cls._read_dataset(path)
            if VERDICT_COLUMNS.issubset(dataframe.columns):
                valid_paths.append(path)
        if len(valid_paths) != 3:
            raise ValueError(
                f"Prompt refinement requires exactly 3 valid verdict files, "
                f"found {len(valid_paths)}."
            )
        return valid_paths

    @classmethod
    def _load_validated_calibration(
        cls,
        calibration_path: Path,
        verdict_path: Path,
    ) -> int:
        if not calibration_path.exists():
            raise FileNotFoundError(
                f"Calibration dataset not found: {calibration_path}"
            )
        calibration = cls._read_dataset(calibration_path)
        if (
            "source_uid" not in calibration.columns
            or "label" not in calibration.columns
        ):
            raise ValueError("Calibration dataset must contain source_uid and label.")
        if calibration["source_uid"].isnull().any():
            raise ValueError("Calibration dataset contains null source UID values.")
        calibration_uids = calibration["source_uid"].astype(str)
        if calibration_uids.duplicated().any():
            raise ValueError(
                "Calibration dataset contains duplicate source UID values."
            )
        verdict = cls._read_dataset(verdict_path)
        verdict_uids = set(verdict["source_uid"].astype(str))
        if set(calibration_uids) != verdict_uids:
            raise ValueError(
                "Calibration dataset source UIDs must match verdict source UIDs."
            )
        return len(calibration)

    @classmethod
    def _build_disagreement_rows(
        cls,
        model_prediction_paths: dict[str, Path],
    ) -> pd.DataFrame:
        merged = None
        label_columns = []
        for model, path in model_prediction_paths.items():
            dataframe: pd.DataFrame = (
                cls._read_dataset(path)
                .loc[:, ["source_uid", "predicted_label", "reason"]]
                .copy()
            )
            # Normalize labels so equivalent numeric/named forms (e.g. 0 and
            # "entailment") count as agreement, matching compute_fleiss_kappa.
            dataframe["predicted_label"] = dataframe["predicted_label"].apply(
                to_label_name
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
    def _read_dataset(path: Path) -> pd.DataFrame:
        return read_tabular(path)
