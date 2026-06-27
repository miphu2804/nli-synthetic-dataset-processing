from __future__ import annotations

import tempfile
from pathlib import Path

import mlflow
from mlflow import MlflowClient
from src.services.prompt_refinement.models import (
    PromptRefinementEvaluation,
    PromptRefinementLog,
)


class PromptRefinementMlflowStore:
    """Log prompt-refinement evidence without promoting prompt versions."""

    def log_evaluation(
        self,
        evaluation: PromptRefinementEvaluation,
        *,
        tracking_uri: str,
        experiment_name: str,
        artifact_root: str | None,
        generator_skill_name: str,
        generator_skill_file: str,
        generator_text: str,
        validator_skill_file: str,
        validator_text: str,
        bundle_id: str,
    ) -> PromptRefinementLog:
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

        run = self._create_calibration_run(
            client,
            experiment_id=experiment_id,
            tags=self._build_calibration_tags(
                evaluation=evaluation,
                bundle_id=bundle_id,
                generator_skill_name=generator_skill_name,
            ),
        )
        run_id = run.info.run_id
        try:
            self._log_calibration_metadata_and_artifacts(
                client=client,
                run_id=run_id,
                evaluation=evaluation,
                bundle_id=bundle_id,
                generator_skill_name=generator_skill_name,
                generator_skill_file=generator_skill_file,
                generator_text=generator_text,
                validator_skill_file=validator_skill_file,
                validator_text=validator_text,
            )
            client.set_terminated(run_id, status="FINISHED")
        except Exception:
            client.set_terminated(run_id, status="FAILED")
            raise

        return PromptRefinementLog(
            run_id=run_id,
            bundle_id=bundle_id,
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
    def _build_calibration_tags(
        *,
        evaluation: PromptRefinementEvaluation,
        bundle_id: str,
        generator_skill_name: str,
    ) -> dict[str, str]:
        return {
            "decision": evaluation.decision,
            "bundle_id": bundle_id,
            "generator_skill_name": generator_skill_name,
        }

    @staticmethod
    def _create_calibration_run(
        client: MlflowClient,
        *,
        experiment_id: str,
        tags: dict[str, str],
    ):
        return client.create_run(
            experiment_id=experiment_id,
            run_name="prompt-refinement-calibration",
            tags=tags,
        )

    def _log_calibration_metadata_and_artifacts(
        self,
        *,
        client: MlflowClient,
        run_id: str,
        evaluation: PromptRefinementEvaluation,
        bundle_id: str,
        generator_skill_name: str,
        generator_skill_file: str,
        generator_text: str,
        validator_skill_file: str,
        validator_text: str,
    ) -> None:
        params = {
            "generator_skill_name": generator_skill_name,
            "generator_skill_file": generator_skill_file,
            "validator_skill_file": validator_skill_file,
            "sample_count": evaluation.sample_count,
            "model_names": ",".join(sorted(evaluation.model_label_paths)),
        }
        for key, value in params.items():
            client.log_param(run_id, key, value)
        client.log_metric(run_id, "fleiss_kappa", evaluation.kappa)
        client.log_metric(
            run_id,
            "rejected_sample_count",
            evaluation.rejected_sample_count,
        )
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
                "rejected_sample_count": evaluation.rejected_sample_count,
            },
            "calibration_summary.json",
        )
        client.log_dict(
            run_id,
            {
                "path": str(evaluation.calibration_path.resolve()),
                "sample_count": evaluation.sample_count,
            },
            "calibration_dataset_manifest.json",
        )
        self._log_file_artifacts(
            client=client,
            run_id=run_id,
            evaluation=evaluation,
            generator_skill_file=generator_skill_file,
            generator_text=generator_text,
            validator_skill_file=validator_skill_file,
            validator_text=validator_text,
        )

    @staticmethod
    def _log_file_artifacts(
        *,
        client: MlflowClient,
        run_id: str,
        evaluation: PromptRefinementEvaluation,
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
