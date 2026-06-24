import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

import mlflow
import pandas as pd
from mlflow import MlflowClient
from src.schemas.validation_runtime_schema import (
    PromptLockConfirmationResponse,
    PromptRefinementRoundResponse,
)
from src.utils.nli_labels import require_canonical_label
from src.utils.validation_aggregation import compute_fleiss_kappa

KAPPA_THRESHOLD = 0.85
GENERATOR_PROMPT_NAME = "nli-generator"
VALIDATOR_PROMPT_NAME = "nli-validator"
DATASET_SUFFIXES = {".csv", ".parquet"}
VERDICT_COLUMNS = {"source_uid", "predicted_label", "reason"}
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class PromptRefinementService:
    """Evaluate and record one agent-operated prompt calibration round."""

    def __init__(self, skills_dir: Path = Path("skills")) -> None:
        self._skills_dir = skills_dir

    def evaluate_round(
        self,
        verdicts_dir: str | Path,
        calibration_input: str | Path,
        round_number: int,
        change_summary: str,
        tracking_uri: str = "http://127.0.0.1:5000",
        experiment_name: str = "nli-prompt-calibration",
        artifact_root: str | None = None,
        session_id: str | None = None,
        generator_skill_name: str = "generator",
    ) -> PromptRefinementRoundResponse:
        """Compute kappa, version current skills, and log one MLflow round."""
        if round_number < 1:
            raise ValueError("round_number must be at least 1.")
        if not change_summary.strip():
            raise ValueError("change_summary must not be empty.")
        if session_id is not None and not SESSION_ID_PATTERN.fullmatch(session_id):
            raise ValueError(
                "session_id may only contain letters, digits, '.', '_', or '-'."
            )
        if not SKILL_NAME_PATTERN.fullmatch(generator_skill_name):
            raise ValueError(
                "generator_skill_name may only contain letters, digits, '_' or '-'."
            )

        # Phase 1 — discover verdicts, compute agreement, validate calibration.
        verdict_paths = self._discover_verdicts(Path(verdicts_dir))
        model_label_paths = {path.stem: path for path in verdict_paths}
        kappa_result = compute_fleiss_kappa(model_label_paths)
        calibration_path = Path(calibration_input)
        dataset_hash, sample_count, uid_set_hash = self._validate_calibration_input(
            calibration_path,
            verdict_paths[0],
        )
        kappa = float(kappa_result["kappa"])
        disagreements = self._build_disagreement_rows(model_label_paths)
        n_disagreements = len(disagreements)

        # Phase 2 — derive the round decision and prompt-bundle inputs.
        decision = self._decision(kappa)
        generator_skill_file = f"{generator_skill_name}.md"
        generator_text = self._read_skill(generator_skill_file)
        validator_text = self._read_skill("validator.md")
        bundle_id = f"round-{round_number:02d}-{dataset_hash[:8]}"

        # Phase 3 — connect MLflow, resolve experiment, resolve session run.
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
        # Resolve session run first so a mismatched calibration UID set is
        # rejected before any prompt version is registered (no orphans).
        session_run_id = None
        round_tags = {
            "decision": decision,
            "change_summary": change_summary,
            "bundle_id": bundle_id,
            "generator_skill_name": generator_skill_name,
        }
        if session_id:
            session_run_id = self._resolve_session_run(
                client, experiment_id, session_id, uid_set_hash
            )
            round_tags["mlflow.parentRunId"] = session_run_id

        # Phase 4 — run lifecycle: create the round run, then register, log,
        # and alias the prompt bundle inside the try so any failure marks the
        # run FAILED for traceability rather than leaving it active.
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
                sample_count=sample_count,
                dataset_hash=dataset_hash,
                model_label_paths=model_label_paths,
                kappa_result=kappa_result,
                generator_prompt=generator_prompt,
                validator_prompt=validator_prompt,
                bundle_id=bundle_id,
                generator_skill_name=generator_skill_name,
                generator_skill_file=generator_skill_file,
                calibration_path=calibration_path,
                disagreements=disagreements,
                n_disagreements=n_disagreements,
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

        # Phase 5 — session trend metrics (auxiliary, best-effort): never let
        # them fail an already-finished round. Logged after finalization.
        if session_run_id:
            try:
                client.log_metric(
                    session_run_id, "fleiss_kappa", kappa, step=round_number
                )
                client.log_metric(
                    session_run_id,
                    "n_disagreements",
                    n_disagreements,
                    step=round_number,
                )
            except Exception:
                pass

        # Phase 6 — assemble the response.
        run_url = self._build_run_url(tracking_uri, experiment_id, run_id)
        return PromptRefinementRoundResponse(
            kappa=kappa,
            threshold=KAPPA_THRESHOLD,
            decision=decision,
            n_items=int(kappa_result["n_items"]),
            n_raters=int(kappa_result["n_raters"]),
            models=sorted(model_label_paths),
            generator_prompt_version=generator_version,
            validator_prompt_version=validator_version,
            calibration_dataset_sha256=dataset_hash,
            bundle_id=bundle_id,
            mlflow_run_id=run_id,
            mlflow_run_url=run_url,
            n_disagreements=n_disagreements,
            mlflow_session_run_id=session_run_id,
        )

    def confirm_prompt_lock(
        self,
        lock_run_id: str,
        tracking_uri: str = "http://127.0.0.1:5000",
    ) -> PromptLockConfirmationResponse:
        """Lock the exact prompt bundle of a previously eligible refinement round.

        Reads the eligible round by its MLflow run_id, verifies kappa is at
        threshold, extracts the prompt versions that were registered in that
        round, and sets the 'locked' alias to those exact versions (does not
        register new versions).

        Args:
            lock_run_id: MLflow run ID of an eligible_to_lock round.
            tracking_uri: MLflow tracking and prompt registry URI.

        Returns:
            PromptLockConfirmationResponse with locked bundle details.

        Raises:
            ValueError if run not found, kappa is below threshold, or required
            params are missing.
        """
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

        generator_version = self._parse_prompt_uri(generator_uri, GENERATOR_PROMPT_NAME)
        validator_version = self._parse_prompt_uri(validator_uri, VALIDATOR_PROMPT_NAME)

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
        # Locking ends the calibration session. Persist the parent's durable
        # lock marker BEFORE marking the child confirmed: if that write fails we
        # must not report a confirmed lock while the session is still reusable
        # by a later evaluate_round. Termination follows (best-effort) so the
        # parent no longer shows as active in the UI.
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
        calibration_dataset_sha256 = run.data.params.get(
            "calibration_dataset_sha256", ""
        )
        run_url = self._build_run_url(tracking_uri, run.info.experiment_id, lock_run_id)

        return PromptLockConfirmationResponse(
            decision="lock_prompt",
            bundle_id=bundle_id,
            generator_prompt_version=generator_version,
            validator_prompt_version=validator_version,
            kappa=float(kappa),
            threshold=KAPPA_THRESHOLD,
            calibration_dataset_sha256=calibration_dataset_sha256,
            mlflow_run_id=lock_run_id,
            mlflow_run_url=run_url,
        )

    @staticmethod
    def _decision(kappa: float) -> str:
        if kappa >= KAPPA_THRESHOLD:
            return "eligible_to_lock"
        return "refine_prompt"

    @staticmethod
    def _parse_prompt_uri(uri: str, expected_name: str) -> int:
        """Parse prompts:/<name>/<version>, enforcing the full URI shape.

        Matching the exact `prompts:/<name>/<version>` form (not just a trailing
        segment) and requiring a positive integer version prevents a malformed
        or tampered run from redirecting the 'locked' alias to a different
        prompt or an unintended version.
        """
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

    @staticmethod
    def _build_run_url(
        tracking_uri: str, experiment_id: str, run_id: str
    ) -> str | None:
        """Build MLflow run URL from tracking URI, experiment ID, and run ID."""
        if tracking_uri.startswith(("http://", "https://")):
            return f"{tracking_uri.rstrip('/')}/#/experiments/{experiment_id}/runs/{run_id}"
        return None

    def _read_skill(self, name: str) -> str:
        path = self._skills_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Prompt skill not found: {path}")
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _discover_verdicts(verdicts_dir: Path) -> list[Path]:
        if not verdicts_dir.is_dir():
            raise FileNotFoundError(f"Verdicts directory not found: {verdicts_dir}")
        valid_paths = []
        for path in sorted(verdicts_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in DATASET_SUFFIXES:
                continue
            dataframe = PromptRefinementService._read_table(path)
            if VERDICT_COLUMNS.issubset(dataframe.columns):
                valid_paths.append(path)
        if len(valid_paths) != 3:
            raise ValueError(
                f"Prompt refinement requires exactly 3 valid verdict files, "
                f"found {len(valid_paths)}."
            )
        return valid_paths

    @staticmethod
    def _validate_calibration_input(
        calibration_path: Path,
        verdict_path: Path,
    ) -> tuple[str, int, str]:
        if not calibration_path.exists():
            raise FileNotFoundError(
                f"Calibration dataset not found: {calibration_path}"
            )
        calibration = PromptRefinementService._read_table(calibration_path)
        uid_column = (
            "source_uid"
            if "source_uid" in calibration.columns
            else "uid" if "uid" in calibration.columns else None
        )
        if uid_column is None or "label" not in calibration.columns:
            raise ValueError(
                "Calibration dataset must contain source_uid or uid, plus label."
            )
        if calibration[uid_column].isnull().any():
            raise ValueError("Calibration dataset contains null source UID values.")
        calibration_uids = calibration[uid_column].astype(str)
        if calibration_uids.duplicated().any():
            raise ValueError(
                "Calibration dataset contains duplicate source UID values."
            )
        verdict = PromptRefinementService._read_table(verdict_path)
        verdict_uids = set(verdict["source_uid"].astype(str))
        if set(calibration_uids) != verdict_uids:
            raise ValueError(
                "Calibration dataset source UIDs must match verdict source UIDs."
            )
        digest = hashlib.sha256(calibration_path.read_bytes()).hexdigest()
        # Hash of the source UID set only (order-independent), used to anchor a
        # session so later rounds cannot mix an incomparable calibration set.
        uid_set_hash = hashlib.sha256(
            "\n".join(sorted(set(calibration_uids))).encode("utf-8")
        ).hexdigest()
        return digest, len(calibration), uid_set_hash

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
        uid_set_hash: str,
    ) -> str:
        """Resolve or create a parent run grouping refinement rounds by session.

        The session is anchored to a calibration UID-set hash on first use. A
        later round whose calibration UID set differs is rejected, since a kappa
        trend across incomparable item sets would be meaningless. (Content/hash
        changes for the same UID set remain allowed as separate rounds.)
        The run is left RUNNING to accept step metrics until the bundle is locked.
        """
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
            anchored = existing.data.tags.get("calibration_uid_set_sha256")
            if anchored is None:
                # Legacy session created before anchoring existed. Only back-fill
                # if it has no recorded rounds yet; otherwise its historical UID
                # set is unverifiable and must not be assumed from this round.
                children = client.search_runs(
                    experiment_ids=[experiment_id],
                    filter_string=(
                        f"tags.mlflow.parentRunId = '{existing.info.run_id}'"
                    ),
                )
                if children:
                    raise ValueError(
                        f"Session '{session_id}' predates UID-set anchoring and "
                        "already has rounds; its calibration set cannot be "
                        "verified. Use a new session_id."
                    )
                client.set_tag(
                    existing.info.run_id,
                    "calibration_uid_set_sha256",
                    uid_set_hash,
                )
            elif anchored != uid_set_hash:
                raise ValueError(
                    f"Session '{session_id}' is anchored to a different "
                    "calibration UID set; refusing to mix incomparable rounds. "
                    "Use a new session_id for a different calibration set."
                )
            return existing.info.run_id
        run = client.create_run(
            experiment_id=experiment_id,
            run_name=f"calibration-session-{session_id}",
            tags={
                "calibration_session_id": session_id,
                "run_type": "calibration_session",
                "calibration_uid_set_sha256": uid_set_hash,
            },
        )
        return run.info.run_id

    def _log_round(
        self,
        client: MlflowClient,
        run_id: str,
        round_number: int,
        sample_count: int,
        dataset_hash: str,
        model_label_paths: dict[str, Path],
        kappa_result: dict,
        generator_prompt,
        validator_prompt,
        bundle_id: str,
        generator_skill_name: str,
        generator_skill_file: str,
        calibration_path: Path,
        disagreements: pd.DataFrame,
        n_disagreements: int,
    ) -> None:
        generator_uri = f"prompts:/{generator_prompt.name}/{generator_prompt.version}"
        validator_uri = f"prompts:/{validator_prompt.name}/{validator_prompt.version}"
        params = {
            "round_number": round_number,
            "generator_prompt_uri": generator_uri,
            "validator_prompt_uri": validator_uri,
            "generator_skill_name": generator_skill_name,
            "generator_skill_file": generator_skill_file,
            "calibration_dataset_sha256": dataset_hash,
            "sample_count": sample_count,
            "model_names": ",".join(sorted(model_label_paths)),
            "git_commit": self._git_commit(),
        }
        for key, value in params.items():
            client.log_param(run_id, key, value)
        client.log_metric(run_id, "fleiss_kappa", float(kappa_result["kappa"]))
        client.log_metric(run_id, "n_disagreements", n_disagreements)
        for label, proportion in kappa_result["per_category_proportion"].items():
            client.log_metric(run_id, f"{label}_proportion", float(proportion))
        client.link_prompt_version_to_run(run_id, generator_prompt)
        client.link_prompt_version_to_run(run_id, validator_prompt)

        bundle = {
            "bundle_id": bundle_id,
            "generator_prompt_uri": generator_uri,
            "generator_skill_name": generator_skill_name,
            "generator_skill_file": generator_skill_file,
            "validator_prompt_uri": validator_uri,
            "calibration_dataset_sha256": dataset_hash,
            "fleiss_kappa": float(kappa_result["kappa"]),
        }
        client.log_dict(run_id, bundle, "prompt_bundle.json")
        client.log_dict(
            run_id,
            {
                "path": str(calibration_path.resolve()),
                "sha256": dataset_hash,
                "sample_count": sample_count,
            },
            "calibration_dataset_manifest.json",
        )

        with tempfile.TemporaryDirectory() as temporary_dir:
            temporary_root = Path(temporary_dir)
            disagreement_path = temporary_root / "disagreement_rows.csv"
            disagreements.to_csv(disagreement_path, index=False)
            client.log_artifact(run_id, str(disagreement_path))
            for model, verdict_path in model_label_paths.items():
                copied_path = temporary_root / f"{model}{verdict_path.suffix.lower()}"
                copied_path.write_bytes(verdict_path.read_bytes())
                client.log_artifact(run_id, str(copied_path), artifact_path="verdicts")

    @staticmethod
    def _build_disagreement_rows(
        model_label_paths: dict[str, Path],
    ) -> pd.DataFrame:
        merged = None
        label_columns = []
        for model, path in model_label_paths.items():
            dataframe = PromptRefinementService._read_table(path)[
                ["source_uid", "predicted_label", "reason"]
            ].copy()
            # Canonicalize labels so equivalent numeric/named forms (e.g. 0 and
            # "entailment") count as agreement, matching compute_fleiss_kappa.
            dataframe["predicted_label"] = dataframe["predicted_label"].apply(
                require_canonical_label
            )
            dataframe = dataframe.rename(
                columns={
                    "predicted_label": f"{model}_label",
                    "reason": f"{model}_reason",
                }
            )
            label_columns.append(f"{model}_label")
            merged = (
                dataframe
                if merged is None
                else merged.merge(dataframe, on="source_uid", how="inner")
            )
        assert merged is not None
        disagreement_mask = merged[label_columns].astype(str).nunique(axis=1) > 1
        return merged[disagreement_mask].reset_index(drop=True)

    @staticmethod
    def _read_table(path: Path) -> pd.DataFrame:
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path)

    def _git_commit(self) -> str:
        try:
            return subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self._skills_dir.parent,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (FileNotFoundError, subprocess.CalledProcessError):
            return "unknown"
