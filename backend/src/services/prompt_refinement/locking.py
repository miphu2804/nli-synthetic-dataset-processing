from __future__ import annotations

import re

import mlflow
from mlflow import MlflowClient
from src.app_config import app_config
from src.schemas.prompt_refinement_schema import PromptLockConfirmationResponse
from src.services.prompt_refinement.evaluator import KAPPA_THRESHOLD
from src.services.prompt_refinement.mlflow_store import (
    GENERATOR_PROMPT_NAME,
    VALIDATOR_PROMPT_NAME,
    PromptRefinementMlflowStore,
)


class PromptLockingService:
    """Confirm locks for already evaluated and eligible MLflow prompt bundles."""

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

        generator_version = self.parse_prompt_uri(generator_uri, GENERATOR_PROMPT_NAME)
        validator_version = self.parse_prompt_uri(validator_uri, VALIDATOR_PROMPT_NAME)

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
        run_url = PromptRefinementMlflowStore.build_run_url(
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
    def parse_prompt_uri(uri: str, expected_name: str) -> int:
        """Parse prompts:/<name>/<version>, enforcing the full URI shape."""
        match = re.fullmatch(rf"prompts:/{re.escape(expected_name)}/(\d+)", uri.strip())
        if match is None:
            raise ValueError(
                f"Prompt URI {uri!r} is not a valid reference to {expected_name!r}; "
                "expected format prompts:/<name>/<version>. Refusing to lock."
            )
        version = int(match.group(1))
        if version < 1:
            raise ValueError(
                f"Prompt URI {uri!r} has a non-positive version; refusing to lock."
            )
        return version
