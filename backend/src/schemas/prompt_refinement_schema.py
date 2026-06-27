from typing import Literal

from pydantic import BaseModel


class PromptAugmentProposalResponse(BaseModel):
    reason: str
    suggested_action: str
    evidence_uids: list[str]


class PromptRefinementRoundResponse(BaseModel):
    kappa: float
    threshold: float
    decision: Literal["needs_prompt_update", "accepted"]
    n_items: int
    n_raters: int
    models: list[str]
    bundle_id: str
    mlflow_run_id: str
    n_disagreements: int
    proposal: PromptAugmentProposalResponse | None = None
    proposal_artifact_path: str | None = None
