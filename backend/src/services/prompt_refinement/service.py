from __future__ import annotations

import re
from pathlib import Path

from src.app_config import app_config
from src.schemas.prompt_refinement_schema import (
    PromptAugmentProposalResponse,
    PromptRefinementRoundResponse,
)
from src.services.prompt_refinement.augment_strategy import (
    PromptAugmentContext,
    PromptAugmentStrategy,
)
from src.services.prompt_refinement.evaluator import (
    KAPPA_THRESHOLD,
    PromptRefinementEvaluator,
)
from src.services.prompt_refinement.mlflow_store import PromptRefinementMlflowStore

SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class PromptRefinementService:
    """Facade for prompt calibration evaluation and manual update proposals."""

    def __init__(
        self,
        skills_dir: Path = Path("skills"),
        evaluator: PromptRefinementEvaluator | None = None,
        augment_strategy: PromptAugmentStrategy | None = None,
        mlflow_store: PromptRefinementMlflowStore | None = None,
    ) -> None:
        self._skills_dir = skills_dir
        self._evaluator = evaluator or PromptRefinementEvaluator()
        self._augment_strategy = augment_strategy or PromptAugmentStrategy()
        self._mlflow_store = mlflow_store or PromptRefinementMlflowStore()

    def evaluate_round(
        self,
        verdicts_dir: str | Path,
        calibration_input: str | Path,
        round_number: int,
        change_summary: str,
        tracking_uri: str = app_config.MLFLOW_URL,
        experiment_name: str = app_config.MLFLOW_EXPERIMENT_NAME,
        artifact_root: str | None = app_config.MLFLOW_ARTIFACT_ROOT,
        generator_skill_name: str = "generator",
    ) -> PromptRefinementRoundResponse:
        """Compute kappa, propose manual prompt updates, and log one round."""
        self._validate_round_args(round_number, change_summary)
        self._validate_generator_skill_name(generator_skill_name)

        evaluation = self._evaluator.evaluate_round_inputs(
            verdicts_dir,
            calibration_input,
        )
        generator_skill_file = f"{generator_skill_name}.md"
        validator_skill_file = "validator.md"
        generator_text = self._read_skill(generator_skill_file)
        validator_text = self._read_skill(validator_skill_file)
        bundle_id = f"round-{round_number:02d}"
        proposal = None
        if evaluation.kappa < KAPPA_THRESHOLD:
            proposal = self._augment_strategy.propose(
                PromptAugmentContext(
                    evaluation=evaluation,
                    threshold=KAPPA_THRESHOLD,
                    generator_skill_name=generator_skill_name,
                    generator_skill_file=generator_skill_file,
                    validator_skill_file=validator_skill_file,
                )
            )

        logged_round = self._mlflow_store.log_evaluated_round(
            evaluation,
            round_number=round_number,
            change_summary=change_summary,
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            artifact_root=artifact_root,
            generator_skill_name=generator_skill_name,
            generator_skill_file=generator_skill_file,
            generator_text=generator_text,
            validator_skill_file=validator_skill_file,
            validator_text=validator_text,
            bundle_id=bundle_id,
            proposal=proposal,
        )
        proposal_response = (
            None
            if proposal is None
            else PromptAugmentProposalResponse(
                reason=proposal.reason,
                suggested_action=proposal.suggested_action,
                evidence_uids=proposal.evidence_uids,
            )
        )

        return PromptRefinementRoundResponse(
            kappa=evaluation.kappa,
            threshold=KAPPA_THRESHOLD,
            decision=evaluation.decision,
            n_items=int(evaluation.kappa_result["n_items"]),
            n_raters=int(evaluation.kappa_result["n_raters"]),
            models=sorted(evaluation.model_label_paths),
            bundle_id=logged_round.bundle_id,
            mlflow_run_id=logged_round.run_id,
            n_disagreements=evaluation.n_disagreements,
            proposal=proposal_response,
            proposal_artifact_path=logged_round.proposal_artifact_path,
        )

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
