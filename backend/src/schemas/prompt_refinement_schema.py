from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel


@dataclass(frozen=True)
class PromptRoundEvaluation:
    verdict_paths: list[Path]
    model_label_paths: dict[str, Path]
    kappa_result: dict[str, Any]
    kappa: float
    decision: str
    calibration_path: Path
    sample_count: int
    calibration: pd.DataFrame
    disagreements: pd.DataFrame
    n_disagreements: int
    label_distribution: dict[str, int]
    model_summaries: list[dict[str, Any]]


@dataclass(frozen=True)
class PromptBundleRegistration:
    run_id: str
    session_run_id: str | None
    bundle_id: str
    generator_prompt_version: int
    validator_prompt_version: int


class PromptRefinementRoundResponse(BaseModel):
    kappa: float
    threshold: float
    decision: Literal["refine_prompt", "eligible_to_lock"]
    n_items: int
    n_raters: int
    models: list[str]
    generator_prompt_version: int
    validator_prompt_version: int
    bundle_id: str
    mlflow_run_id: str
    n_disagreements: int
    mlflow_session_run_id: str | None = None


class PromptRefinementEvidencePackResponse(BaseModel):
    status: Literal["prepared"]
    evidence_dir: str
    disagreement_rows_path: str
    disagreement_calibration_rows_path: str
    round_summary_path: str
    generator_instructions_path: str
    validator_instructions_path: str
    decision: Literal["refine_prompt", "eligible_to_lock"]
    kappa: float
    n_disagreements: int
    models: list[str]


class PromptLockConfirmationResponse(BaseModel):
    decision: Literal["lock_prompt"]
    bundle_id: str
    generator_prompt_version: int
    validator_prompt_version: int
    kappa: float
    threshold: float
    mlflow_run_id: str
