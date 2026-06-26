from __future__ import annotations

import json
from pathlib import Path

from src.schemas.prompt_refinement_schema import (
    PromptRefinementEvidencePackResponse,
    PromptRoundEvaluation,
)
from src.services.prompt_refinement.evaluator import KAPPA_THRESHOLD


class PromptRefinementEvidencePackWriter:
    """Write local evidence files for prompt-refinement editor review."""

    def write_evidence_pack(
        self,
        evaluation: PromptRoundEvaluation,
        *,
        output_root: str | Path,
        round_number: int,
        generator_skill_name: str,
        bundle_id: str | None,
        mlflow_run_id: str | None,
        generator_prompt_version: int | None,
        validator_prompt_version: int | None,
        generator_text: str,
        validator_text: str,
    ) -> PromptRefinementEvidencePackResponse:
        calibration = evaluation.calibration.copy()
        disagreement_uids = set(evaluation.disagreements["source_uid"].astype(str))
        disagreement_calibration = calibration[
            calibration["source_uid"].isin(disagreement_uids)
        ].reset_index(drop=True)

        evidence_dir = Path(output_root) / f"round-{round_number:02d}" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)

        disagreement_rows_path = evidence_dir / "disagreement_rows.csv"
        disagreement_calibration_rows_path = (
            evidence_dir / "disagreement_calibration_rows.csv"
        )
        generator_instructions_path = evidence_dir / "current_generator_instructions.md"
        validator_instructions_path = evidence_dir / "current_validator_instructions.md"
        round_summary_path = evidence_dir / "round_summary.json"

        evaluation.disagreements.to_csv(disagreement_rows_path, index=False)
        disagreement_calibration.to_csv(
            disagreement_calibration_rows_path,
            index=False,
        )
        generator_instructions_path.write_text(generator_text, encoding="utf-8")
        validator_instructions_path.write_text(validator_text, encoding="utf-8")

        summary = {
            "round_number": round_number,
            "decision": evaluation.decision,
            "kappa": evaluation.kappa,
            "threshold": KAPPA_THRESHOLD,
            "n_items": int(evaluation.kappa_result["n_items"]),
            "n_raters": int(evaluation.kappa_result["n_raters"]),
            "n_disagreements": int(evaluation.n_disagreements),
            "sample_count": evaluation.sample_count,
            "label_distribution": evaluation.label_distribution,
            "models": evaluation.model_summaries,
            "generator_skill_name": generator_skill_name,
            "bundle_id": bundle_id,
            "mlflow_run_id": mlflow_run_id,
            "generator_prompt_version": generator_prompt_version,
            "validator_prompt_version": validator_prompt_version,
            "artifacts": {
                "disagreement_rows": str(disagreement_rows_path),
                "disagreement_calibration_rows": str(
                    disagreement_calibration_rows_path
                ),
                "current_generator_instructions": str(generator_instructions_path),
                "current_validator_instructions": str(validator_instructions_path),
            },
        }
        round_summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return PromptRefinementEvidencePackResponse(
            status="prepared",
            evidence_dir=str(evidence_dir),
            disagreement_rows_path=str(disagreement_rows_path),
            disagreement_calibration_rows_path=str(disagreement_calibration_rows_path),
            round_summary_path=str(round_summary_path),
            generator_instructions_path=str(generator_instructions_path),
            validator_instructions_path=str(validator_instructions_path),
            decision=evaluation.decision,
            kappa=evaluation.kappa,
            n_disagreements=int(evaluation.n_disagreements),
            models=sorted(evaluation.model_label_paths),
        )
