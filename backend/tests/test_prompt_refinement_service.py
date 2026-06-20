import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from src.services.prompt_refinement_service import PromptRefinementService


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
        (self.skills_dir / "validator.md").write_text(
            "# Validator\nAssign one canonical label.\n", encoding="utf-8"
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
        # Equivalent numeric/named labels must canonicalize to agreement so the
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

    def test_session_rejects_different_calibration_uid_set(self) -> None:
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

        # Round 2 with a completely different source UID set must be rejected.
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

        with self.assertRaisesRegex(ValueError, "anchored to a different"):
            self.service.evaluate_round(
                verdicts_dir=self.verdicts_dir,
                calibration_input=other_calibration,
                round_number=2,
                change_summary="Round 2 wrong set.",
                tracking_uri=self.tracking_uri,
                experiment_name="test-calibration",
                artifact_root=self.artifact_root,
                session_id="sess-001",
            )

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


if __name__ == "__main__":
    unittest.main()
