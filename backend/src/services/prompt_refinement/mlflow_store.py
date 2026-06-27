from __future__ import annotations

import tempfile
from pathlib import Path

import mlflow
from mlflow import MlflowClient
from src.services.prompt_refinement.models import (
    PromptAugmentProposal,
    PromptRoundEvaluation,
    PromptRoundLog,
)

PROPOSAL_ARTIFACT_PATH = "prompt_augment_proposal.json"


class PromptRefinementMlflowStore:
    """Log prompt-refinement round evidence without promoting prompt versions."""

    def log_evaluated_round(
        self,
        evaluation: PromptRoundEvaluation,
        *,
        round_number: int,
        change_summary: str,
        tracking_uri: str,
        experiment_name: str,
        artifact_root: str | None,
        generator_skill_name: str,
        generator_skill_file: str,
        generator_text: str,
        validator_skill_file: str,
        validator_text: str,
        bundle_id: str,
        proposal: PromptAugmentProposal | None,
    ) -> PromptRoundLog:
        client = self._create_mlflow_client(tracking_uri)
        experiment = self._get_experiment_by_name(client, experiment_name)
        if experiment is None:
            experiment_id = self._create_experiment(
                client,
                experiment_name,
                artifact_root,
            )
        else:
            experiment_id = experiment.experiment_id

        run = self._create_round_run(
            client,
            experiment_id=experiment_id,
            round_number=round_number,
            tags=self._build_round_tags(
                evaluation=evaluation,
                change_summary=change_summary,
                bundle_id=bundle_id,
                generator_skill_name=generator_skill_name,
            ),
        )
        run_id = run.info.run_id
        try:
            proposal_artifact_path = self._log_round_metadata_and_artifacts(
                client=client,
                run_id=run_id,
                round_number=round_number,
                evaluation=evaluation,
                bundle_id=bundle_id,
                generator_skill_name=generator_skill_name,
                generator_skill_file=generator_skill_file,
                generator_text=generator_text,
                validator_skill_file=validator_skill_file,
                validator_text=validator_text,
                proposal=proposal,
            )
            client.set_terminated(run_id, status="FINISHED")
        except Exception:
            client.set_terminated(run_id, status="FAILED")
            raise

        return PromptRoundLog(
            run_id=run_id,
            bundle_id=bundle_id,
            proposal_artifact_path=proposal_artifact_path,
        )

    @staticmethod
    def _create_mlflow_client(tracking_uri: str) -> MlflowClient:
        mlflow.set_tracking_uri(tracking_uri)
        return MlflowClient(tracking_uri=tracking_uri)

    @staticmethod
    def _get_experiment_by_name(
        client: MlflowClient,
        experiment_name: str,
    ):
        return client.get_experiment_by_name(experiment_name)

    @staticmethod
    def _create_experiment(
        client: MlflowClient,
        experiment_name: str,
        artifact_root: str | None,
    ) -> str:
        return client.create_experiment(
            experiment_name,
            artifact_location=artifact_root,
        )

    @staticmethod
    def _build_round_tags(
        *,
        evaluation: PromptRoundEvaluation,
        change_summary: str,
        bundle_id: str,
        generator_skill_name: str,
    ) -> dict[str, str]:
        return {
            "decision": evaluation.decision,
            "change_summary": change_summary,
            "bundle_id": bundle_id,
            "generator_skill_name": generator_skill_name,
        }

    @staticmethod
    def _create_round_run(
        client: MlflowClient,
        *,
        experiment_id: str,
        round_number: int,
        tags: dict[str, str],
    ):
        return client.create_run(
            experiment_id=experiment_id,
            run_name=f"prompt-refinement-round-{round_number:02d}",
            tags=tags,
        )

    def _log_round_metadata_and_artifacts(
        self,
        *,
        client: MlflowClient,
        run_id: str,
        round_number: int,
        evaluation: PromptRoundEvaluation,
        bundle_id: str,
        generator_skill_name: str,
        generator_skill_file: str,
        generator_text: str,
        validator_skill_file: str,
        validator_text: str,
        proposal: PromptAugmentProposal | None,
    ) -> str | None:
        params = {
            "round_number": round_number,
            "generator_skill_name": generator_skill_name,
            "generator_skill_file": generator_skill_file,
            "validator_skill_file": validator_skill_file,
            "sample_count": evaluation.sample_count,
            "model_names": ",".join(sorted(evaluation.model_label_paths)),
        }
        for key, value in params.items():
            client.log_param(run_id, key, value)
        client.log_metric(run_id, "fleiss_kappa", evaluation.kappa)
        client.log_metric(run_id, "n_disagreements", evaluation.n_disagreements)
        for label, proportion in evaluation.kappa_result[
            "per_category_proportion"
        ].items():
            client.log_metric(run_id, f"{label}_proportion", float(proportion))

        client.log_dict(
            run_id,
            {
                "bundle_id": bundle_id,
                "decision": evaluation.decision,
                "generator_skill_name": generator_skill_name,
                "generator_skill_file": generator_skill_file,
                "validator_skill_file": validator_skill_file,
                "fleiss_kappa": evaluation.kappa,
                "n_disagreements": evaluation.n_disagreements,
            },
            "round_summary.json",
        )
        client.log_dict(
            run_id,
            {
                "path": str(evaluation.calibration_path.resolve()),
                "sample_count": evaluation.sample_count,
            },
            "calibration_dataset_manifest.json",
        )
        proposal_artifact_path = self._log_proposal(client, run_id, proposal)
        self._log_file_artifacts(
            client=client,
            run_id=run_id,
            evaluation=evaluation,
            generator_skill_file=generator_skill_file,
            generator_text=generator_text,
            validator_skill_file=validator_skill_file,
            validator_text=validator_text,
        )
        return proposal_artifact_path

    @staticmethod
    def _log_proposal(
        client: MlflowClient,
        run_id: str,
        proposal: PromptAugmentProposal | None,
    ) -> str | None:
        if proposal is None:
            return None
        client.log_dict(
            run_id,
            {
                "reason": proposal.reason,
                "suggested_action": proposal.suggested_action,
                "evidence_uids": proposal.evidence_uids,
            },
            PROPOSAL_ARTIFACT_PATH,
        )
        return PROPOSAL_ARTIFACT_PATH

    @staticmethod
    def _log_file_artifacts(
        *,
        client: MlflowClient,
        run_id: str,
        evaluation: PromptRoundEvaluation,
        generator_skill_file: str,
        generator_text: str,
        validator_skill_file: str,
        validator_text: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            temporary_root = Path(temporary_dir)
            disagreement_path = temporary_root / "disagreement_rows.csv"
            evaluation.disagreements.to_csv(disagreement_path, index=False)
            client.log_artifact(run_id, str(disagreement_path))

            generator_path = temporary_root / generator_skill_file
            generator_path.write_text(generator_text, encoding="utf-8")
            client.log_artifact(run_id, str(generator_path), artifact_path="prompts")

            validator_path = temporary_root / validator_skill_file
            validator_path.write_text(validator_text, encoding="utf-8")
            client.log_artifact(run_id, str(validator_path), artifact_path="prompts")

            for model, verdict_path in evaluation.model_label_paths.items():
                copied_path = temporary_root / f"{model}{verdict_path.suffix.lower()}"
                copied_path.write_bytes(verdict_path.read_bytes())
                client.log_artifact(run_id, str(copied_path), artifact_path="verdicts")
