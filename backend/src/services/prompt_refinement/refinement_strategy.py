from __future__ import annotations

from dataclasses import dataclass

from src.services.prompt_refinement.models import (
    PromptRefinementEvaluation,
    PromptRefinementProposal,
)


@dataclass(frozen=True)
class PromptRefinementContext:
    evaluation: PromptRefinementEvaluation
    threshold: float
    generator_skill_file: str
    validator_skill_file: str


class PromptRefinementStrategy:
    """Build a manual prompt-update proposal from calibration evidence."""

    def propose(self, context: PromptRefinementContext) -> PromptRefinementProposal:
        evidence_uids = (
            context.evaluation.disagreements["source_uid"].astype(str).head(10).tolist()
            if context.evaluation.rejected_sample_count
            else []
        )
        reason = (
            f"Fleiss kappa {context.evaluation.kappa:.4f} is below "
            f"the {context.threshold:.2f} threshold."
        )
        if evidence_uids:
            reason += (
                " Validator disagreement is concentrated in the listed source_uid "
                "rows; inspect their premises, hypotheses, labels, and model "
                "reasons before editing prompts."
            )
        else:
            reason += (
                " No row-level disagreement artifact was produced, so inspect the "
                "class distribution and verdict files before editing prompts."
            )

        return PromptRefinementProposal(
            reason=reason,
            suggested_action=(
                "Review the MLflow artifacts, then manually update the smallest "
                f"responsible instruction in {context.generator_skill_file} or "
                f"{context.validator_skill_file}. Keep the same source_uid set "
                "for the next comparable calibration."
            ),
            evidence_uids=evidence_uids,
        )
