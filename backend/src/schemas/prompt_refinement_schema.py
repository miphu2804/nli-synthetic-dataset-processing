from typing import Literal

from pydantic import BaseModel


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
