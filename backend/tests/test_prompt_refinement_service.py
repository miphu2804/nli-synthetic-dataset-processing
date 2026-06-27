import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from src.services.prompt_refinement import PromptRefinementService


class PromptRefinementServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.verdicts_dir = self.root / "verdicts"
        self.verdicts_dir.mkdir()
        self.skills_dir = self.root / "skills"
        self.skills_dir.mkdir()
        (self.skills_dir / "generator.md").write_text(
            "# Generator\nGenerate clear hypotheses.\n", encoding="utf-8"
        )
        (self.skills_dir / "generator_plain.md").write_text(
            "# Plain Generator\nTranslate without extra adversarial transforms.\n",
            encoding="utf-8",
        )
        (self.skills_dir / "validator.md").write_text(
            "# Validator\nAssign one supported NLI label.\n", encoding="utf-8"
        )
        self.calibration_input = self.root / "calibration.csv"
        pd.DataFrame(
            [
                {
                    "source_uid": "row-1",
                    "premise": "p1",
                    "hypothesis": "h1",
                    "label": "entailment",
                },
                {
                    "source_uid": "row-2",
                    "premise": "p2",
                    "hypothesis": "h2",
                    "label": "neutral",
                },
            ]
        ).to_csv(self.calibration_input, index=False)
        self.tracking_uri = f"sqlite:///{self.root / 'mlflow.db'}"
        self.artifact_root = (self.root / "artifacts").as_uri()
        self.service = PromptRefinementService(skills_dir=self.skills_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_verdicts(self, labels_by_model: dict[str, list[str]]) -> None:
        for model, labels in labels_by_model.items():
            pd.DataFrame(
                [
                    {
                        "source_uid": f"row-{index}",
                        "predicted_label": label,
                        "reason": "Lý do hợp lệ.",
                    }
                    for index, label in enumerate(labels, start=1)
                ]
            ).to_csv(self.verdicts_dir / f"{model}.csv", index=False)

    def _evaluate(self):
        return self.service.evaluate_round(
            verdicts_dir=self.verdicts_dir,
            calibration_input=self.calibration_input,
            round_number=1,
            change_summary="Initial calibration.",
            tracking_uri=self.tracking_uri,
            experiment_name="test-calibration",
            artifact_root=self.artifact_root,
        )

    def test_requires_exactly_three_verdict_files(self) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
            }
        )

        with self.assertRaisesRegex(ValueError, "exactly 3"):
            self._evaluate()

    def test_logs_eligible_round_without_locking_prompts(self) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
                "model-c": ["entailment", "neutral"],
            }
        )

        result = self._evaluate()

        self.assertEqual(result.decision, "eligible_to_lock")
        self.assertEqual(result.kappa, 1.0)
        self.assertEqual(result.n_items, 2)
        self.assertEqual(result.n_raters, 3)
        self.assertEqual(result.models, ["model-a", "model-b", "model-c"])
        self.assertEqual(result.n_disagreements, 0)
        self.assertIsNone(result.mlflow_session_run_id)

        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        generator_candidate = client.get_prompt_version_by_alias(
            "nli-generator", "candidate"
        )
        validator_candidate = client.get_prompt_version_by_alias(
            "nli-validator", "candidate"
        )
        self.assertEqual(
            int(generator_candidate.version), result.generator_prompt_version
        )
        self.assertEqual(
            int(validator_candidate.version), result.validator_prompt_version
        )
        with self.assertRaises(MlflowException):
            client.get_prompt_version_by_alias("nli-generator", "locked")

        run = client.get_run(result.mlflow_run_id)
        self.assertEqual(run.data.metrics["fleiss_kappa"], 1.0)
        self.assertEqual(run.data.metrics["n_disagreements"], 0)
        self.assertEqual(run.data.tags["decision"], "eligible_to_lock")
        artifact_paths = {
            artifact.path for artifact in client.list_artifacts(result.mlflow_run_id)
        }
        self.assertIn("prompt_bundle.json", artifact_paths)
        self.assertIn("disagreement_rows.csv", artifact_paths)
        self.assertIn("verdicts", artifact_paths)

    def test_evaluate_round_versions_selected_generator_skill(self) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
                "model-c": ["entailment", "neutral"],
            }
        )

        result = self.service.evaluate_round(
            verdicts_dir=self.verdicts_dir,
            calibration_input=self.calibration_input,
            round_number=1,
            change_summary="Plain generator calibration.",
            tracking_uri=self.tracking_uri,
            experiment_name="test-calibration",
            artifact_root=self.artifact_root,
            generator_skill_name="generator_plain",
        )

        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        generator_candidate = client.get_prompt_version_by_alias(
            "nli-generator", "candidate"
        )
        run = client.get_run(result.mlflow_run_id)

        self.assertIn("without extra adversarial", generator_candidate.template)
        self.assertEqual(run.data.params["generator_skill_name"], "generator_plain")
        self.assertEqual(run.data.params["generator_skill_file"], "generator_plain.md")

    def test_evaluate_round_marks_run_failed_when_prompt_registration_fails(
        self,
    ) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
                "model-c": ["entailment", "neutral"],
            }
        )

        original_register_prompt = MlflowClient.register_prompt
        observed_run_ids: list[str] = []

        def fail_validator_prompt(self_client, *args, **kwargs):
            if not observed_run_ids:
                runs = self_client.search_runs(
                    experiment_ids=["1"],
                    filter_string="attributes.run_name = 'prompt-refinement-round-01'",
                )
                observed_run_ids.extend(run.info.run_id for run in runs)
            if kwargs.get("name") == "nli-validator":
                raise MlflowException("validator prompt registration failed")
            return original_register_prompt(self_client, *args, **kwargs)

        with patch.object(
            MlflowClient,
            "register_prompt",
            fail_validator_prompt,
        ):
            with self.assertRaisesRegex(
                MlflowException,
                "validator prompt registration failed",
            ):
                self._evaluate()

        self.assertEqual(len(observed_run_ids), 1)
        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        run = client.get_run(observed_run_ids[0])
        self.assertEqual(run.info.status, "FAILED")

    def test_confirmed_eligible_round_sets_locked_aliases(self) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
                "model-c": ["entailment", "neutral"],
            }
        )

        result = self._evaluate()

        self.assertEqual(result.decision, "eligible_to_lock")
        lock_result = self.service.confirm_prompt_lock(
            lock_run_id=result.mlflow_run_id,
            tracking_uri=self.tracking_uri,
        )
        self.assertEqual(lock_result.decision, "lock_prompt")
        self.assertEqual(
            lock_result.generator_prompt_version, result.generator_prompt_version
        )
        self.assertEqual(
            lock_result.validator_prompt_version, result.validator_prompt_version
        )

        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        self.assertEqual(
            int(client.get_prompt_version_by_alias("nli-generator", "locked").version),
            result.generator_prompt_version,
        )
        self.assertEqual(
            int(client.get_prompt_version_by_alias("nli-validator", "locked").version),
            result.validator_prompt_version,
        )

    def test_rejects_lock_confirmation_below_threshold(self) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "entailment"],
                "model-b": ["neutral", "neutral"],
                "model-c": ["contradiction", "contradiction"],
            }
        )

        result = self._evaluate()

        self.assertEqual(result.decision, "refine_prompt")
        with self.assertRaisesRegex(ValueError, "eligible"):
            self.service.confirm_prompt_lock(
                lock_run_id=result.mlflow_run_id,
                tracking_uri=self.tracking_uri,
            )

        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        with self.assertRaises(MlflowException):
            client.get_prompt_version_by_alias("nli-generator", "locked")

    def test_logs_low_agreement_round_for_refinement_without_locking(self) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "entailment"],
                "model-b": ["neutral", "neutral"],
                "model-c": ["contradiction", "contradiction"],
            }
        )

        result = self._evaluate()

        self.assertEqual(result.decision, "refine_prompt")
        self.assertLess(result.kappa, result.threshold)
        self.assertGreater(result.n_disagreements, 0)
        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        run = client.get_run(result.mlflow_run_id)
        self.assertGreater(run.data.metrics["n_disagreements"], 0)
        with self.assertRaises(MlflowException):
            client.get_prompt_version_by_alias("nli-generator", "locked")

    def test_session_id_creates_parent_run_and_logs_step_metrics(self) -> None:
        """Test that session_id groups multiple rounds and creates a parent run."""
        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
                "model-c": ["entailment", "neutral"],
            }
        )
        session_id = "test-session-001"

        # Evaluate round 1 with session_id
        result1 = self.service.evaluate_round(
            verdicts_dir=self.verdicts_dir,
            calibration_input=self.calibration_input,
            round_number=1,
            change_summary="Round 1 calibration.",
            tracking_uri=self.tracking_uri,
            experiment_name="test-calibration",
            artifact_root=self.artifact_root,
            session_id=session_id,
        )

        # Evaluate round 2 with same session_id (to simulate a second round)
        # First, clear the verdict files and rewrite for round 2
        shutil.rmtree(self.verdicts_dir)
        self.verdicts_dir.mkdir()
        self._write_verdicts(
            {
                "model-a": ["entailment", "contradiction"],
                "model-b": ["entailment", "contradiction"],
                "model-c": ["entailment", "contradiction"],
            }
        )
        result2 = self.service.evaluate_round(
            verdicts_dir=self.verdicts_dir,
            calibration_input=self.calibration_input,
            round_number=2,
            change_summary="Round 2 calibration.",
            tracking_uri=self.tracking_uri,
            experiment_name="test-calibration",
            artifact_root=self.artifact_root,
            session_id=session_id,
        )

        # Verify session run was created and reused
        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        self.assertIsNotNone(result1.mlflow_session_run_id)
        self.assertIsNotNone(result2.mlflow_session_run_id)
        self.assertEqual(result1.mlflow_session_run_id, result2.mlflow_session_run_id)

        session_run_id = result1.mlflow_session_run_id
        session_run = client.get_run(session_run_id)
        self.assertEqual(
            session_run.data.tags.get("calibration_session_id"), session_id
        )
        self.assertEqual(session_run.data.tags.get("run_type"), "calibration_session")

        # Verify round runs have parent tag
        round1_run = client.get_run(result1.mlflow_run_id)
        round2_run = client.get_run(result2.mlflow_run_id)
        self.assertEqual(round1_run.data.tags.get("mlflow.parentRunId"), session_run_id)
        self.assertEqual(round2_run.data.tags.get("mlflow.parentRunId"), session_run_id)

        # Verify session run has step metrics for both rounds
        kappa_history = client.get_metric_history(session_run_id, "fleiss_kappa")
        self.assertEqual(len(kappa_history), 2)
        self.assertEqual(kappa_history[0].step, 1)
        self.assertEqual(kappa_history[1].step, 2)

        disagreement_history = client.get_metric_history(
            session_run_id, "n_disagreements"
        )
        self.assertEqual(len(disagreement_history), 2)
        self.assertEqual(disagreement_history[0].step, 1)
        self.assertEqual(disagreement_history[1].step, 2)

    def test_lock_references_evaluated_version_not_current_files(self) -> None:
        """Regression test for lock-by-reference bug fix.

        Ensure that confirm_prompt_lock locks to the prompt version that was
        registered at evaluation time, not the current file contents.
        """
        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
                "model-c": ["entailment", "neutral"],
            }
        )

        # Evaluate round (all agree, eligible to lock)
        result = self._evaluate()
        self.assertEqual(result.decision, "eligible_to_lock")
        original_validator_version = result.validator_prompt_version

        # Now modify validator.md file
        (self.skills_dir / "validator.md").write_text(
            "# Validator Modified\nNew instructions here.\n", encoding="utf-8"
        )

        # Confirm lock of the original eligible round
        lock_result = self.service.confirm_prompt_lock(
            lock_run_id=result.mlflow_run_id,
            tracking_uri=self.tracking_uri,
        )

        # Assert locked alias points to the original version, not a new one
        self.assertEqual(
            lock_result.validator_prompt_version, original_validator_version
        )
        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        locked_validator = client.get_prompt_version_by_alias("nli-validator", "locked")
        self.assertEqual(int(locked_validator.version), original_validator_version)

        # Verify no new version was created (locked version == candidate version)
        candidate_validator = client.get_prompt_version_by_alias(
            "nli-validator", "candidate"
        )
        self.assertEqual(
            int(candidate_validator.version),
            original_validator_version,
            "Locked and candidate should point to the same version; "
            "confirm_prompt_lock did not register a new version.",
        )

    def test_mixed_numeric_and_named_labels_agree(self) -> None:
        # Equivalent numeric/named labels must normalize to agreement so the
        # disagreement count matches kappa.
        for model, labels in {
            "model-a": [0, 1],
            "model-b": ["entailment", "neutral"],
            "model-c": ["0", 1],
        }.items():
            pd.DataFrame(
                [
                    {
                        "source_uid": f"row-{index}",
                        "predicted_label": label,
                        "reason": "Lý do hợp lệ.",
                    }
                    for index, label in enumerate(labels, start=1)
                ]
            ).to_csv(self.verdicts_dir / f"{model}.csv", index=False)

        result = self._evaluate()

        self.assertEqual(result.kappa, 1.0)
        self.assertEqual(result.n_disagreements, 0)
        self.assertEqual(result.decision, "eligible_to_lock")

    def test_invalid_session_id_rejected_before_registration(self) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
                "model-c": ["entailment", "neutral"],
            }
        )

        with self.assertRaisesRegex(ValueError, "session_id"):
            self.service.evaluate_round(
                verdicts_dir=self.verdicts_dir,
                calibration_input=self.calibration_input,
                round_number=1,
                change_summary="Initial calibration.",
                tracking_uri=self.tracking_uri,
                experiment_name="test-calibration",
                artifact_root=self.artifact_root,
                session_id="team's session",
            )

        # No prompt versions should have been registered on early rejection.
        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        self.assertIsNone(client.get_prompt("nli-generator"))

    def test_confirm_lock_rejects_unfinished_run(self) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
                "model-c": ["entailment", "neutral"],
            }
        )
        result = self._evaluate()

        # Simulate a run that logged eligible metrics but ended up FAILED.
        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        client.set_terminated(result.mlflow_run_id, status="FAILED")

        with self.assertRaisesRegex(ValueError, "did not finish"):
            self.service.confirm_prompt_lock(
                lock_run_id=result.mlflow_run_id,
                tracking_uri=self.tracking_uri,
            )
        with self.assertRaises(MlflowException):
            client.get_prompt_version_by_alias("nli-generator", "locked")

    def test_session_allows_different_calibration_uid_set(self) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
                "model-c": ["entailment", "neutral"],
            }
        )
        self.service.evaluate_round(
            verdicts_dir=self.verdicts_dir,
            calibration_input=self.calibration_input,
            round_number=1,
            change_summary="Round 1.",
            tracking_uri=self.tracking_uri,
            experiment_name="test-calibration",
            artifact_root=self.artifact_root,
            session_id="sess-001",
        )

        # Round 2 can use a different source UID set. Each round still validates
        # that its verdicts and calibration input contain the same UIDs.
        other_calibration = self.root / "calibration2.csv"
        pd.DataFrame(
            [
                {
                    "source_uid": "x-1",
                    "premise": "p",
                    "hypothesis": "h",
                    "label": "entailment",
                },
                {
                    "source_uid": "x-2",
                    "premise": "p",
                    "hypothesis": "h",
                    "label": "neutral",
                },
            ]
        ).to_csv(other_calibration, index=False)
        shutil.rmtree(self.verdicts_dir)
        self.verdicts_dir.mkdir()
        for model in ("model-a", "model-b", "model-c"):
            pd.DataFrame(
                [
                    {
                        "source_uid": "x-1",
                        "predicted_label": "entailment",
                        "reason": "ok",
                    },
                    {"source_uid": "x-2", "predicted_label": "neutral", "reason": "ok"},
                ]
            ).to_csv(self.verdicts_dir / f"{model}.csv", index=False)

        result = self.service.evaluate_round(
            verdicts_dir=self.verdicts_dir,
            calibration_input=other_calibration,
            round_number=2,
            change_summary="Round 2 different set.",
            tracking_uri=self.tracking_uri,
            experiment_name="test-calibration",
            artifact_root=self.artifact_root,
            session_id="sess-001",
        )

        self.assertEqual(result.mlflow_session_run_id is not None, True)

    def test_lock_terminates_session_run(self) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
                "model-c": ["entailment", "neutral"],
            }
        )
        result = self.service.evaluate_round(
            verdicts_dir=self.verdicts_dir,
            calibration_input=self.calibration_input,
            round_number=1,
            change_summary="Round 1.",
            tracking_uri=self.tracking_uri,
            experiment_name="test-calibration",
            artifact_root=self.artifact_root,
            session_id="sess-lock",
        )
        self.assertIsNotNone(result.mlflow_session_run_id)

        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        self.assertEqual(
            client.get_run(result.mlflow_session_run_id).info.status, "RUNNING"
        )

        self.service.confirm_prompt_lock(
            lock_run_id=result.mlflow_run_id,
            tracking_uri=self.tracking_uri,
        )
        self.assertEqual(
            client.get_run(result.mlflow_session_run_id).info.status, "FINISHED"
        )

    def _eval_session(self, *, round_number, uids, session_id):
        cal = self.root / f"cal-{round_number}.csv"
        pd.DataFrame(
            [
                {
                    "source_uid": u,
                    "premise": "p",
                    "hypothesis": "h",
                    "label": "entailment",
                }
                for u in uids
            ]
        ).to_csv(cal, index=False)
        shutil.rmtree(self.verdicts_dir)
        self.verdicts_dir.mkdir()
        for model in ("model-a", "model-b", "model-c"):
            pd.DataFrame(
                [
                    {"source_uid": u, "predicted_label": "entailment", "reason": "ok"}
                    for u in uids
                ]
            ).to_csv(self.verdicts_dir / f"{model}.csv", index=False)
        return self.service.evaluate_round(
            verdicts_dir=self.verdicts_dir,
            calibration_input=cal,
            round_number=round_number,
            change_summary=f"Round {round_number}.",
            tracking_uri=self.tracking_uri,
            experiment_name="test-calibration",
            artifact_root=self.artifact_root,
            session_id=session_id,
        )

    def test_existing_session_can_be_reused(self) -> None:
        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        experiment_id = client.create_experiment(
            "test-calibration", artifact_location=self.artifact_root
        )
        legacy = client.create_run(
            experiment_id=experiment_id,
            run_name="calibration-session-legacy",
            tags={
                "calibration_session_id": "legacy",
                "run_type": "calibration_session",
            },
        )

        first = self._eval_session(round_number=1, uids=["a", "b"], session_id="legacy")
        second = self._eval_session(
            round_number=2, uids=["x", "y"], session_id="legacy"
        )

        self.assertEqual(first.mlflow_session_run_id, legacy.info.run_id)
        self.assertEqual(second.mlflow_session_run_id, legacy.info.run_id)

    def test_finalized_session_rejects_new_rounds(self) -> None:
        result = self._eval_session(
            round_number=1, uids=["a", "b"], session_id="sess-fin"
        )
        self.service.confirm_prompt_lock(
            lock_run_id=result.mlflow_run_id,
            tracking_uri=self.tracking_uri,
        )
        with self.assertRaisesRegex(ValueError, "already finalized"):
            self._eval_session(round_number=2, uids=["a", "b"], session_id="sess-fin")

    def test_locked_marker_blocks_reuse_when_termination_fails(self) -> None:
        from unittest.mock import patch

        result = self._eval_session(
            round_number=1, uids=["a", "b"], session_id="sess-mark"
        )
        original = MlflowClient.set_terminated

        def fail_session(self_client, run_id, *args, **kwargs):
            if run_id == result.mlflow_session_run_id:
                raise MlflowException("transient")
            return original(self_client, run_id, *args, **kwargs)

        with patch.object(MlflowClient, "set_terminated", fail_session):
            self.service.confirm_prompt_lock(
                lock_run_id=result.mlflow_run_id,
                tracking_uri=self.tracking_uri,
            )

        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        session_run = client.get_run(result.mlflow_session_run_id)
        # Termination failed (still RUNNING) but the durable marker is set.
        self.assertEqual(session_run.info.status, "RUNNING")
        self.assertEqual(session_run.data.tags.get("session_locked"), "true")
        with self.assertRaisesRegex(ValueError, "already finalized"):
            self._eval_session(round_number=2, uids=["a", "b"], session_id="sess-mark")

    def test_confirm_lock_rejects_wrong_prompt_uri_name(self) -> None:
        client = MlflowClient(
            tracking_uri=self.tracking_uri,
            registry_uri=self.tracking_uri,
        )
        experiment_id = client.create_experiment(
            "test-calibration",
            artifact_location=self.artifact_root,
        )
        run = client.create_run(
            experiment_id=experiment_id,
            tags={
                "decision": "eligible_to_lock",
                "bundle_id": "round-01",
            },
        )
        client.log_metric(run.info.run_id, "fleiss_kappa", 1.0)
        client.log_param(run.info.run_id, "generator_prompt_uri", "prompts:/other/1")
        client.log_param(
            run.info.run_id,
            "validator_prompt_uri",
            "prompts:/nli-validator/1",
        )
        client.set_terminated(run.info.run_id, status="FINISHED")

        with self.assertRaisesRegex(ValueError, "nli-generator"):
            self.service.confirm_prompt_lock(
                lock_run_id=run.info.run_id,
                tracking_uri=self.tracking_uri,
            )

    def test_partial_locked_alias_write_raises_and_is_repairable(self) -> None:
        from unittest.mock import patch

        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
                "model-c": ["entailment", "neutral"],
            }
        )
        result = self._evaluate()
        self.assertEqual(result.decision, "eligible_to_lock")

        original = MlflowClient.set_prompt_alias

        def fail_validator(self_client, name, alias, version, *args, **kwargs):
            if alias == "locked" and name == "nli-validator":
                raise MlflowException("transient alias failure")
            return original(self_client, name, alias, version, *args, **kwargs)

        with patch.object(MlflowClient, "set_prompt_alias", fail_validator):
            with self.assertRaisesRegex(RuntimeError, "inconsistent"):
                self.service.confirm_prompt_lock(
                    lock_run_id=result.mlflow_run_id,
                    tracking_uri=self.tracking_uri,
                )

        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        # Generator alias got locked, validator did not, run not marked confirmed.
        self.assertEqual(
            int(client.get_prompt_version_by_alias("nli-generator", "locked").version),
            result.generator_prompt_version,
        )
        with self.assertRaises(MlflowException):
            client.get_prompt_version_by_alias("nli-validator", "locked")
        self.assertNotIn(
            "lock_confirmed", client.get_run(result.mlflow_run_id).data.tags
        )

        # Re-running repairs the bundle (idempotent).
        lock_result = self.service.confirm_prompt_lock(
            lock_run_id=result.mlflow_run_id,
            tracking_uri=self.tracking_uri,
        )
        self.assertEqual(lock_result.decision, "lock_prompt")
        self.assertEqual(
            int(client.get_prompt_version_by_alias("nli-validator", "locked").version),
            result.validator_prompt_version,
        )

    def test_existing_session_with_existing_rounds_can_be_reused(self) -> None:
        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        experiment_id = client.create_experiment(
            "test-calibration", artifact_location=self.artifact_root
        )
        legacy = client.create_run(
            experiment_id=experiment_id,
            run_name="calibration-session-old",
            tags={
                "calibration_session_id": "old",
                "run_type": "calibration_session",
            },
        )
        # A pre-existing child round does not block reuse.
        client.create_run(
            experiment_id=experiment_id,
            run_name="prompt-refinement-round-01",
            tags={"mlflow.parentRunId": legacy.info.run_id},
        )

        result = self._eval_session(round_number=1, uids=["a", "b"], session_id="old")

        self.assertEqual(result.mlflow_session_run_id, legacy.info.run_id)


if __name__ == "__main__":
    unittest.main()
