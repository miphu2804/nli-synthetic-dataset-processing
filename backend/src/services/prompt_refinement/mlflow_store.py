from __future__ import annotations

import tempfile
from pathlib import Path

from mlflow import MlflowClient
from src.schemas.prompt_refinement_schema import (
    PromptBundleRegistration,
    PromptRoundEvaluation,
)
from src.services.prompt_refinement.mlflow_support import (
    GENERATOR_PROMPT_NAME,
    VALIDATOR_PROMPT_NAME,
    create_mlflow_client,
)


class PromptRefinementMlflowStore:
    """MLflow prompt registry and round logging side effects."""

    def log_evaluated_round(
        self,
        evaluation: PromptRoundEvaluation,
        *,
        round_number: int,
        change_summary: str,
        tracking_uri: str,
        experiment_name: str,
        artifact_root: str | None,
        session_id: str | None,
        generator_skill_name: str,
        generator_skill_file: str,
        generator_text: str,
        validator_text: str,
        bundle_id: str,
    ) -> PromptBundleRegistration:
        client = create_mlflow_client(tracking_uri)
        experiment = self._get_experiment_by_name(client, experiment_name)
        if experiment is None:
            experiment_id = self._create_experiment(
                client,
                experiment_name,
                artifact_root,
            )
        else:
            experiment_id = experiment.experiment_id

        session_run_id = None
        round_tags = {
            "decision": evaluation.decision,
            "change_summary": change_summary,
            "bundle_id": bundle_id,
            "generator_skill_name": generator_skill_name,
        }
        if session_id:
            session_run = self._get_active_session_run(
                client,
                experiment_id,
                session_id,
            )
            if session_run is None:
                session_run_id = self._create_session_run(
                    client,
                    experiment_id,
                    session_id,
                )
            else:
                session_run_id = session_run.info.run_id
            round_tags["mlflow.parentRunId"] = session_run_id

        run = client.create_run(
            experiment_id=experiment_id,
            run_name=f"prompt-refinement-round-{round_number:02d}",
            tags=round_tags,
        )
        run_id = run.info.run_id
        try:
            generator_prompt = client.register_prompt(
                name=GENERATOR_PROMPT_NAME,
                template=generator_text,
                commit_message=change_summary,
                tags={"round": str(round_number), "bundle_id": bundle_id},
            )
            validator_prompt = client.register_prompt(
                name=VALIDATOR_PROMPT_NAME,
                template=validator_text,
                commit_message=change_summary,
                tags={"round": str(round_number), "bundle_id": bundle_id},
            )
            generator_version = int(generator_prompt.version)
            validator_version = int(validator_prompt.version)
            self._log_round(
                client=client,
                run_id=run_id,
                round_number=round_number,
                evaluation=evaluation,
                generator_prompt=generator_prompt,
                validator_prompt=validator_prompt,
                bundle_id=bundle_id,
                generator_skill_name=generator_skill_name,
                generator_skill_file=generator_skill_file,
            )
            client.set_prompt_alias(
                GENERATOR_PROMPT_NAME, "candidate", generator_version
            )
            client.set_prompt_alias(
                VALIDATOR_PROMPT_NAME, "candidate", validator_version
            )
            client.set_terminated(run_id, status="FINISHED")
        except Exception:
            client.set_terminated(run_id, status="FAILED")
            raise

        if session_run_id:
            try:
                client.log_metric(
                    session_run_id,
                    "fleiss_kappa",
                    evaluation.kappa,
                    step=round_number,
                )
                client.log_metric(
                    session_run_id,
                    "n_disagreements",
                    evaluation.n_disagreements,
                    step=round_number,
                )
            except Exception:
                pass

        return PromptBundleRegistration(
            run_id=run_id,
            session_run_id=session_run_id,
            bundle_id=bundle_id,
            generator_prompt_version=generator_version,
            validator_prompt_version=validator_version,
        )

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
    def _get_active_session_run(
        client: MlflowClient,
        experiment_id: str,
        session_id: str,
    ):
        """Return the active parent run for a session, if one already exists."""
        filter_string = f"tags.calibration_session_id = '{session_id}'"
        runs = client.search_runs(
            experiment_ids=[experiment_id],
            filter_string=filter_string,
            order_by=["start_time ASC"],
        )
        if not runs:
            return None

        existing = runs[0]
        locked = existing.data.tags.get("session_locked") == "true"
        if locked or existing.info.status != "RUNNING":
            raise ValueError(
                f"Session '{session_id}' is already finalized "
                f"(status {existing.info.status}); use a new session_id."
            )
        return existing

    @staticmethod
    def _create_session_run(
        client: MlflowClient,
        experiment_id: str,
        session_id: str,
    ) -> str:
        run = client.create_run(
            experiment_id=experiment_id,
            run_name=f"calibration-session-{session_id}",
            tags={
                "calibration_session_id": session_id,
                "run_type": "calibration_session",
            },
        )
        return run.info.run_id

    def _log_round(
        self,
        *,
        client: MlflowClient,
        run_id: str,
        round_number: int,
        evaluation: PromptRoundEvaluation,
        generator_prompt,
        validator_prompt,
        bundle_id: str,
        generator_skill_name: str,
        generator_skill_file: str,
    ) -> None:
        generator_uri = f"prompts:/{generator_prompt.name}/{generator_prompt.version}"
        validator_uri = f"prompts:/{validator_prompt.name}/{validator_prompt.version}"
        params = {
            "round_number": round_number,
            "generator_prompt_uri": generator_uri,
            "validator_prompt_uri": validator_uri,
            "generator_skill_name": generator_skill_name,
            "generator_skill_file": generator_skill_file,
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
        client.link_prompt_version_to_run(run_id, generator_prompt)
        client.link_prompt_version_to_run(run_id, validator_prompt)

        bundle = {
            "bundle_id": bundle_id,
            "generator_prompt_uri": generator_uri,
            "generator_skill_name": generator_skill_name,
            "generator_skill_file": generator_skill_file,
            "validator_prompt_uri": validator_uri,
            "fleiss_kappa": evaluation.kappa,
        }
        client.log_dict(run_id, bundle, "prompt_bundle.json")
        client.log_dict(
            run_id,
            {
                "path": str(evaluation.calibration_path.resolve()),
                "sample_count": evaluation.sample_count,
            },
            "calibration_dataset_manifest.json",
        )

        with tempfile.TemporaryDirectory() as temporary_dir:
            temporary_root = Path(temporary_dir)
            disagreement_path = temporary_root / "disagreement_rows.csv"
            evaluation.disagreements.to_csv(disagreement_path, index=False)
            client.log_artifact(run_id, str(disagreement_path))
            for model, verdict_path in evaluation.model_label_paths.items():
                copied_path = temporary_root / f"{model}{verdict_path.suffix.lower()}"
                copied_path.write_bytes(verdict_path.read_bytes())
                client.log_artifact(run_id, str(copied_path), artifact_path="verdicts")
