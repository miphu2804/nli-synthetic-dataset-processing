from __future__ import annotations

import tempfile
from pathlib import Path

import mlflow
from mlflow import MlflowClient
from src.app_config import app_config
from src.schemas.prompt_refinement_schema import (
    PromptBundleRegistration,
    PromptLockConfirmationResponse,
    PromptRoundEvaluation,
)
from src.services.prompt_refinement.evaluator import KAPPA_THRESHOLD

GENERATOR_PROMPT_NAME = "nli-generator"
VALIDATOR_PROMPT_NAME = "nli-validator"


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
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_registry_uri(tracking_uri)
        client = MlflowClient(
            tracking_uri=tracking_uri,
            registry_uri=tracking_uri,
        )
        experiment_id = self._resolve_experiment(
            client,
            experiment_name,
            artifact_root,
        )

        session_run_id = None
        round_tags = {
            "decision": evaluation.decision,
            "change_summary": change_summary,
            "bundle_id": bundle_id,
            "generator_skill_name": generator_skill_name,
        }
        if session_id:
            session_run_id = self._resolve_session_run(
                client,
                experiment_id,
                session_id,
            )
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

        run_url = self.build_run_url(tracking_uri, experiment_id, run_id)
        return PromptBundleRegistration(
            run_id=run_id,
            run_url=run_url,
            session_run_id=session_run_id,
            bundle_id=bundle_id,
            generator_prompt_version=generator_version,
            validator_prompt_version=validator_version,
        )

    def confirm_prompt_lock(
        self,
        lock_run_id: str,
        tracking_uri: str = app_config.MLFLOW_URL,
    ) -> PromptLockConfirmationResponse:
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_registry_uri(tracking_uri)
        client = MlflowClient(
            tracking_uri=tracking_uri,
            registry_uri=tracking_uri,
        )

        run = client.get_run(lock_run_id)
        if run is None:
            raise ValueError(f"MLflow run not found: {lock_run_id}")

        if run.info.status != "FINISHED":
            raise ValueError(
                f"Run {lock_run_id} did not finish successfully "
                f"(status {run.info.status}); refusing to lock."
            )
        if run.data.tags.get("decision") != "eligible_to_lock":
            raise ValueError(
                f"Run {lock_run_id} is not an eligible_to_lock round "
                f"(decision {run.data.tags.get('decision')!r})."
            )

        kappa = run.data.metrics.get("fleiss_kappa")
        if kappa is None or float(kappa) < KAPPA_THRESHOLD:
            raise ValueError(
                f"Run {lock_run_id} is not eligible to lock "
                f"(kappa {kappa} < {KAPPA_THRESHOLD})."
            )

        generator_uri = run.data.params.get("generator_prompt_uri")
        validator_uri = run.data.params.get("validator_prompt_uri")
        if not generator_uri or not validator_uri:
            raise ValueError(
                f"Run {lock_run_id} is missing required prompt URIs. "
                "This does not appear to be a valid eligible round."
            )

        generator_version = self._prompt_version_from_uri(
            client,
            generator_uri,
            GENERATOR_PROMPT_NAME,
        )
        validator_version = self._prompt_version_from_uri(
            client,
            validator_uri,
            VALIDATOR_PROMPT_NAME,
        )

        # MLflow has no multi-alias transaction. Set both; if the second write
        # fails, surface the inconsistency loudly rather than leaving 'locked'
        # pointing at a mixed bundle. confirm_prompt_lock is idempotent, so a
        # re-run repairs it.
        client.set_prompt_alias(GENERATOR_PROMPT_NAME, "locked", generator_version)
        try:
            client.set_prompt_alias(VALIDATOR_PROMPT_NAME, "locked", validator_version)
        except Exception as exc:
            raise RuntimeError(
                f"Locked {GENERATOR_PROMPT_NAME} -> v{generator_version} but failed "
                f"to lock {VALIDATOR_PROMPT_NAME} -> v{validator_version}: {exc}. "
                "The 'locked' bundle is inconsistent; re-run confirm_prompt_lock "
                "to repair."
            ) from exc

        session_run_id = run.data.tags.get("mlflow.parentRunId")
        if session_run_id:
            client.set_tag(session_run_id, "session_locked", "true")

        client.set_tag(lock_run_id, "lock_confirmed", "true")

        if session_run_id:
            try:
                client.set_terminated(session_run_id, status="FINISHED")
            except Exception:
                pass

        bundle_id = run.data.tags.get("bundle_id", "")
        run_url = self.build_run_url(
            tracking_uri,
            run.info.experiment_id,
            lock_run_id,
        )

        return PromptLockConfirmationResponse(
            decision="lock_prompt",
            bundle_id=bundle_id,
            generator_prompt_version=generator_version,
            validator_prompt_version=validator_version,
            kappa=float(kappa),
            threshold=KAPPA_THRESHOLD,
            mlflow_run_id=lock_run_id,
            mlflow_run_url=run_url,
        )

    @staticmethod
    def _resolve_experiment(
        client: MlflowClient,
        experiment_name: str,
        artifact_root: str | None,
    ) -> str:
        experiment = client.get_experiment_by_name(experiment_name)
        if experiment is not None:
            return experiment.experiment_id
        return client.create_experiment(
            experiment_name,
            artifact_location=artifact_root,
        )

    @staticmethod
    def _resolve_session_run(
        client: MlflowClient,
        experiment_id: str,
        session_id: str,
    ) -> str:
        """Resolve or create a parent run grouping refinement rounds by session."""
        filter_string = f"tags.calibration_session_id = '{session_id}'"
        runs = client.search_runs(
            experiment_ids=[experiment_id],
            filter_string=filter_string,
            order_by=["start_time ASC"],
        )
        if runs:
            existing = runs[0]
            locked = existing.data.tags.get("session_locked") == "true"
            if locked or existing.info.status != "RUNNING":
                raise ValueError(
                    f"Session '{session_id}' is already finalized "
                    f"(status {existing.info.status}); use a new session_id."
                )
            return existing.info.run_id
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

    @staticmethod
    def build_run_url(
        tracking_uri: str,
        experiment_id: str,
        run_id: str,
    ) -> str | None:
        if tracking_uri.startswith(("http://", "https://")):
            return f"{tracking_uri.rstrip('/')}/#/experiments/{experiment_id}/runs/{run_id}"
        return None

    @staticmethod
    def _prompt_version_from_uri(
        client: MlflowClient,
        uri: str,
        expected_name: str,
    ) -> int:
        try:
            prompt_name, version_text = client.parse_prompt_uri(uri.strip())
        except Exception as exc:
            raise ValueError(
                f"Prompt URI {uri!r} is not a valid MLflow prompt URI."
            ) from exc
        if prompt_name != expected_name:
            raise ValueError(
                f"Prompt URI {uri!r} is not a reference to {expected_name!r}; "
                f"got {prompt_name!r}."
            )
        try:
            version = int(version_text)
        except ValueError as exc:
            raise ValueError(
                f"Prompt URI {uri!r} resolved to non-numeric version "
                f"{version_text!r}."
            ) from exc
        if version < 1:
            raise ValueError(
                f"Prompt URI {uri!r} has a non-positive version; refusing to lock."
            )
        return version
