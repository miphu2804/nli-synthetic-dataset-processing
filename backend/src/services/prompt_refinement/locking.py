from __future__ import annotations

from dataclasses import dataclass

from mlflow import MlflowClient
from src.app_config import app_config
from src.schemas.prompt_refinement_schema import PromptLockConfirmationResponse
from src.services.prompt_refinement.evaluator import KAPPA_THRESHOLD
from src.services.prompt_refinement.mlflow_support import (
    GENERATOR_PROMPT_NAME,
    VALIDATOR_PROMPT_NAME,
    create_mlflow_client,
)


@dataclass(frozen=True)
class LockablePromptRound:
    run_id: str
    session_run_id: str | None
    bundle_id: str
    kappa: float
    generator_prompt_version: int
    validator_prompt_version: int


class PromptRefinementLockService:
    def __init__(self) -> None:
        self._create_client = create_mlflow_client

    def confirm_prompt_lock(
        self,
        lock_run_id: str,
        tracking_uri: str = app_config.MLFLOW_URL,
    ) -> PromptLockConfirmationResponse:
        client = self._create_client(tracking_uri)
        lockable_round = self._load_lockable_round(client, lock_run_id)
        self._set_locked_aliases(client, lockable_round)
        self._mark_lock_confirmed(client, lockable_round)
        return self._build_response(lockable_round)

    def _load_lockable_round(
        self,
        client: MlflowClient,
        lock_run_id: str,
    ) -> LockablePromptRound:
        run = client.get_run(lock_run_id)
        if run is None:
            raise ValueError(f"MLflow run not found: {lock_run_id}")

        self._validate_run_status(run, lock_run_id)
        self._validate_run_decision(run, lock_run_id)
        kappa = self._extract_kappa(run, lock_run_id)
        generator_prompt_version = self._extract_prompt_version(
            client,
            run.data.params.get("generator_prompt_uri"),
            expected_name=GENERATOR_PROMPT_NAME,
        )
        validator_prompt_version = self._extract_prompt_version(
            client,
            run.data.params.get("validator_prompt_uri"),
            expected_name=VALIDATOR_PROMPT_NAME,
        )

        return LockablePromptRound(
            run_id=lock_run_id,
            session_run_id=run.data.tags.get("mlflow.parentRunId"),
            bundle_id=run.data.tags.get("bundle_id", ""),
            kappa=kappa,
            generator_prompt_version=generator_prompt_version,
            validator_prompt_version=validator_prompt_version,
        )

    @staticmethod
    def _validate_run_status(run, lock_run_id: str) -> None:
        if run.info.status != "FINISHED":
            raise ValueError(
                f"Run {lock_run_id} did not finish successfully "
                f"(status {run.info.status}); refusing to lock."
            )

    @staticmethod
    def _validate_run_decision(run, lock_run_id: str) -> None:
        if run.data.tags.get("decision") != "eligible_to_lock":
            raise ValueError(
                f"Run {lock_run_id} is not an eligible_to_lock round "
                f"(decision {run.data.tags.get('decision')!r})."
            )

    @staticmethod
    def _extract_kappa(run, lock_run_id: str) -> float:
        kappa = run.data.metrics.get("fleiss_kappa")
        if kappa is None or float(kappa) < KAPPA_THRESHOLD:
            raise ValueError(
                f"Run {lock_run_id} is not eligible to lock "
                f"(kappa {kappa} < {KAPPA_THRESHOLD})."
            )
        return float(kappa)

    @staticmethod
    def _extract_prompt_version(
        client: MlflowClient,
        prompt_uri: str | None,
        *,
        expected_name: str,
    ) -> int:
        if not prompt_uri:
            raise ValueError(
                "The eligible round is missing a required prompt URI. "
                "This does not appear to be a valid prompt-refinement run."
            )

        try:
            prompt_name, version_text = client.parse_prompt_uri(prompt_uri.strip())
        except Exception as exc:
            raise ValueError(
                f"Prompt URI {prompt_uri!r} is not a valid MLflow prompt URI."
            ) from exc
        if prompt_name != expected_name:
            raise ValueError(
                f"Prompt URI {prompt_uri!r} is not a reference to {expected_name!r}; "
                f"got {prompt_name!r}."
            )

        try:
            version = int(version_text)
        except ValueError as exc:
            raise ValueError(
                f"Prompt URI {prompt_uri!r} resolved to non-numeric version "
                f"{version_text!r}."
            ) from exc
        if version < 1:
            raise ValueError(
                f"Prompt URI {prompt_uri!r} has a non-positive version; "
                "refusing to lock."
            )
        return version

    @staticmethod
    def _set_locked_aliases(
        client: MlflowClient,
        lockable_round: LockablePromptRound,
    ) -> None:
        client.set_prompt_alias(
            GENERATOR_PROMPT_NAME,
            "locked",
            lockable_round.generator_prompt_version,
        )
        try:
            client.set_prompt_alias(
                VALIDATOR_PROMPT_NAME,
                "locked",
                lockable_round.validator_prompt_version,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Locked {GENERATOR_PROMPT_NAME} -> "
                f"v{lockable_round.generator_prompt_version} but failed to lock "
                f"{VALIDATOR_PROMPT_NAME} -> "
                f"v{lockable_round.validator_prompt_version}: {exc}. "
                "The 'locked' bundle is inconsistent; re-run confirm_prompt_lock "
                "to repair."
            ) from exc

    @staticmethod
    def _mark_lock_confirmed(
        client: MlflowClient,
        lockable_round: LockablePromptRound,
    ) -> None:
        if lockable_round.session_run_id:
            client.set_tag(lockable_round.session_run_id, "session_locked", "true")
        client.set_tag(lockable_round.run_id, "lock_confirmed", "true")

        if lockable_round.session_run_id:
            try:
                client.set_terminated(lockable_round.session_run_id, status="FINISHED")
            except Exception:
                pass

    @staticmethod
    def _build_response(
        lockable_round: LockablePromptRound,
    ) -> PromptLockConfirmationResponse:
        return PromptLockConfirmationResponse(
            decision="lock_prompt",
            bundle_id=lockable_round.bundle_id,
            generator_prompt_version=lockable_round.generator_prompt_version,
            validator_prompt_version=lockable_round.validator_prompt_version,
            kappa=lockable_round.kappa,
            threshold=KAPPA_THRESHOLD,
            mlflow_run_id=lockable_round.run_id,
        )
