from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PromptRefinementEvaluation:
    model_label_paths: dict[str, Path]
    kappa_result: dict[str, Any]
    kappa: float
    decision: str
    calibration_path: Path
    sample_count: int
    disagreements: pd.DataFrame
    rejected_sample_count: int


@dataclass(frozen=True)
class PromptRefinementProposal:
    reason: str
    suggested_action: str
    evidence_uids: list[str]


@dataclass(frozen=True)
class PromptRefinementLog:
    run_id: str
    bundle_id: str
