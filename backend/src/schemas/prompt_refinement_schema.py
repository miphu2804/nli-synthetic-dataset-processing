from typing import Literal

from pydantic import BaseModel


class PromptRefinementProposal(BaseModel):
    reason: str
    suggested_action: str
    evidence_uids: list[str]


class PromptRefinementResponse(BaseModel):
    kappa: float
    threshold: float
    decision: Literal["needs_prompt_update", "accepted"]
    n_items: int
    n_raters: int
    models: list[str]
    bundle_id: str
    mlflow_run_id: str
    rejected_sample_count: int


class PromptRefinementProposalResponse(BaseModel):
    kappa: float
    threshold: float
    decision: Literal["needs_prompt_update", "accepted"]
    rejected_sample_count: int
    proposal: PromptRefinementProposal | None = None
