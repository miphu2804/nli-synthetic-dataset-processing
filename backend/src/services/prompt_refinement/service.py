from __future__ import annotations

import re
from pathlib import Path

from src.app_config import app_config
from src.schemas.prompt_refinement_schema import PromptRefinementResponse
from src.services.prompt_refinement.evaluator import (
    KAPPA_THRESHOLD,
    PromptRefinementEvaluator,
)
from src.services.prompt_refinement.mlflow_store import PromptRefinementMlflowStore

SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class PromptRefinementService:
    """Facade for prompt calibration evaluation."""

    def __init__(
        self,
        skills_dir: Path = Path("skills"),
        evaluator: PromptRefinementEvaluator | None = None,
        mlflow_store: PromptRefinementMlflowStore | None = None,
    ) -> None:
        self._skills_dir = skills_dir
        self._evaluator = evaluator or PromptRefinementEvaluator()
        self._mlflow_store = mlflow_store or PromptRefinementMlflowStore()

    def evaluate(
        self,
        verdicts_dir: str | Path,
        calibration_input: str | Path,
        tracking_uri: str = app_config.MLFLOW_URL,
        experiment_name: str = app_config.MLFLOW_EXPERIMENT_NAME,
        artifact_root: str | None = app_config.MLFLOW_ARTIFACT_ROOT,
        generator_skill_name: str = "generator",
    ) -> PromptRefinementResponse:
        """Compute kappa and log one calibration run."""
        self._validate_generator_skill_name(generator_skill_name)

        evaluation = self._evaluator.evaluate_inputs(
            verdicts_dir,
            calibration_input,
        )
        generator_skill_file = f"{generator_skill_name}.md"
        validator_skill_file = "validator.md"
        generator_text = self._read_skill(generator_skill_file)
        validator_text = self._read_skill(validator_skill_file)
        bundle_id = "calibration"

        logged_run = self._mlflow_store.log_evaluation(
            evaluation,
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            artifact_root=artifact_root,
            generator_skill_name=generator_skill_name,
            generator_skill_file=generator_skill_file,
            generator_text=generator_text,
            validator_skill_file=validator_skill_file,
            validator_text=validator_text,
            bundle_id=bundle_id,
        )

        return PromptRefinementResponse(
            kappa=evaluation.kappa,
            threshold=KAPPA_THRESHOLD,
            decision=evaluation.decision,
            n_items=int(evaluation.kappa_result["n_items"]),
            n_raters=int(evaluation.kappa_result["n_raters"]),
            models=sorted(evaluation.model_label_paths),
            bundle_id=logged_run.bundle_id,
            mlflow_run_id=logged_run.run_id,
            rejected_sample_count=evaluation.rejected_sample_count,
        )

    @staticmethod
    def _validate_generator_skill_name(generator_skill_name: str) -> None:
        if not SKILL_NAME_PATTERN.fullmatch(generator_skill_name):
            raise ValueError(
                "generator_skill_name may only contain letters, digits, '_' or '-'."
            )

    def _read_skill(self, name: str) -> str:
        path = self._skills_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Prompt skill not found: {path}")
        return path.read_text(encoding="utf-8")
