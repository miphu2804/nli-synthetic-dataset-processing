from __future__ import annotations

import re
from pathlib import Path

from src.app_config import app_config
from src.schemas.prompt_refinement_schema import (
    PromptLockConfirmationResponse,
    PromptRefinementEvidencePackResponse,
    PromptRefinementRoundResponse,
)
from src.services.prompt_refinement.evaluator import (
    KAPPA_THRESHOLD,
    PromptRefinementEvaluator,
)
from src.services.prompt_refinement.evidence_pack import (
    PromptRefinementEvidencePackWriter,
)
from src.services.prompt_refinement.mlflow_store import PromptRefinementMlflowStore

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class PromptRefinementService:
    """Facade for prompt calibration evaluation, evidence, and locking."""

    def __init__(self, skills_dir: Path = Path("skills")) -> None:
        self._skills_dir = skills_dir
        self._evaluator = PromptRefinementEvaluator()
        self._mlflow_store = PromptRefinementMlflowStore()
        self._evidence_writer = PromptRefinementEvidencePackWriter()

    def evaluate_round(
        self,
        verdicts_dir: str | Path,
        calibration_input: str | Path,
        round_number: int,
        change_summary: str,
        tracking_uri: str = app_config.MLFLOW_URL,
        experiment_name: str = app_config.MLFLOW_EXPERIMENT_NAME,
        artifact_root: str | None = app_config.MLFLOW_ARTIFACT_ROOT,
        session_id: str | None = None,
        generator_skill_name: str = "generator",
    ) -> PromptRefinementRoundResponse:
        """Compute kappa, version current skills, and log one MLflow round."""
        self._validate_round_args(round_number, change_summary)
        if session_id is not None and not SESSION_ID_PATTERN.fullmatch(session_id):
            raise ValueError(
                "session_id may only contain letters, digits, '.', '_', or '-'."
            )
        self._validate_generator_skill_name(generator_skill_name)

        evaluation = self._evaluator.evaluate_inputs(
            verdicts_dir,
            calibration_input,
            include_summary_fields=False,
        )
        generator_skill_file = f"{generator_skill_name}.md"
        generator_text = self._read_skill(generator_skill_file)
        validator_text = self._read_skill("validator.md")
        bundle_id = f"round-{round_number:02d}"

        registration = self._mlflow_store.log_evaluated_round(
            evaluation,
            round_number=round_number,
            change_summary=change_summary,
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            artifact_root=artifact_root,
            session_id=session_id,
            generator_skill_name=generator_skill_name,
            generator_skill_file=generator_skill_file,
            generator_text=generator_text,
            validator_text=validator_text,
            bundle_id=bundle_id,
        )

        return PromptRefinementRoundResponse(
            kappa=evaluation.kappa,
            threshold=KAPPA_THRESHOLD,
            decision=evaluation.decision,
            n_items=int(evaluation.kappa_result["n_items"]),
            n_raters=int(evaluation.kappa_result["n_raters"]),
            models=sorted(evaluation.model_label_paths),
            generator_prompt_version=registration.generator_prompt_version,
            validator_prompt_version=registration.validator_prompt_version,
            bundle_id=registration.bundle_id,
            mlflow_run_id=registration.run_id,
            mlflow_run_url=registration.run_url,
            n_disagreements=evaluation.n_disagreements,
            mlflow_session_run_id=registration.session_run_id,
        )

    def prepare_evidence_pack(
        self,
        verdicts_dir: str | Path,
        calibration_input: str | Path,
        output_root: str | Path,
        round_number: int,
        generator_skill_name: str = "generator",
        bundle_id: str | None = None,
        mlflow_run_id: str | None = None,
        generator_prompt_version: int | None = None,
        validator_prompt_version: int | None = None,
    ) -> PromptRefinementEvidencePackResponse:
        """Write a local evidence pack for post-failure editor subagents."""
        if round_number < 1:
            raise ValueError("round_number must be at least 1.")
        self._validate_generator_skill_name(generator_skill_name)

        evaluation = self._evaluator.evaluate_inputs(verdicts_dir, calibration_input)
        generator_text = self._read_skill(f"{generator_skill_name}.md")
        validator_text = self._read_skill("validator.md")
        return self._evidence_writer.write_evidence_pack(
            evaluation,
            output_root=output_root,
            round_number=round_number,
            generator_skill_name=generator_skill_name,
            bundle_id=bundle_id,
            mlflow_run_id=mlflow_run_id,
            generator_prompt_version=generator_prompt_version,
            validator_prompt_version=validator_prompt_version,
            generator_text=generator_text,
            validator_text=validator_text,
        )

    def confirm_prompt_lock(
        self,
        lock_run_id: str,
        tracking_uri: str = app_config.MLFLOW_URL,
    ) -> PromptLockConfirmationResponse:
        return self._mlflow_store.confirm_prompt_lock(lock_run_id, tracking_uri)

    @staticmethod
    def _validate_round_args(round_number: int, change_summary: str) -> None:
        if round_number < 1:
            raise ValueError("round_number must be at least 1.")
        if not change_summary.strip():
            raise ValueError("change_summary must not be empty.")

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

    @staticmethod
    def _build_run_url(
        tracking_uri: str,
        experiment_id: str,
        run_id: str,
    ) -> str | None:
        return PromptRefinementMlflowStore.build_run_url(
            tracking_uri,
            experiment_id,
            run_id,
        )
