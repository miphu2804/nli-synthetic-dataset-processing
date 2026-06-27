from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PromptRoundEvaluation:
    model_label_paths: dict[str, Path]
    kappa_result: dict[str, Any]
    kappa: float
    decision: str
    calibration_path: Path
    sample_count: int
    disagreements: pd.DataFrame
    n_disagreements: int


@dataclass(frozen=True)
class PromptAugmentProposal:
    reason: str
    suggested_action: str
    evidence_uids: list[str]


@dataclass(frozen=True)
class PromptRoundLog:
    run_id: str
    bundle_id: str
    proposal_artifact_path: str | None
