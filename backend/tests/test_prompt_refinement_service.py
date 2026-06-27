import json
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
                        "reason": "Ly do hop le.",
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

    def _client(self) -> MlflowClient:
        return MlflowClient(tracking_uri=self.tracking_uri)

    def test_requires_exactly_three_verdict_files(self) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
            }
        )

        with self.assertRaisesRegex(ValueError, "exactly 3"):
            self._evaluate()

    def test_logs_accepted_round_without_prompt_versions_or_proposal(self) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
                "model-c": ["entailment", "neutral"],
            }
        )

        result = self._evaluate()

        self.assertEqual(result.decision, "accepted")
        self.assertEqual(result.kappa, 1.0)
        self.assertEqual(result.n_items, 2)
        self.assertEqual(result.n_raters, 3)
        self.assertEqual(result.models, ["model-a", "model-b", "model-c"])
        self.assertEqual(result.n_disagreements, 0)
        self.assertIsNone(result.proposal)
        self.assertIsNone(result.proposal_artifact_path)

        client = self._client()
        run = client.get_run(result.mlflow_run_id)
        self.assertEqual(run.data.metrics["fleiss_kappa"], 1.0)
        self.assertEqual(run.data.metrics["n_disagreements"], 0)
        self.assertEqual(run.data.tags["decision"], "accepted")
        self.assertNotIn("generator_prompt_uri", run.data.params)
        self.assertNotIn("validator_prompt_uri", run.data.params)

        artifact_paths = {
            artifact.path for artifact in client.list_artifacts(result.mlflow_run_id)
        }
        self.assertIn("round_summary.json", artifact_paths)
        self.assertIn("disagreement_rows.csv", artifact_paths)
        self.assertIn("prompts", artifact_paths)
        self.assertIn("verdicts", artifact_paths)
        self.assertNotIn("prompt_augment_proposal.json", artifact_paths)

        with self.assertRaises(MlflowException):
            client.get_prompt_version_by_alias("nli-generator", "candidate")

    def test_evaluate_round_logs_selected_generator_skill_snapshot(self) -> None:
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

        client = self._client()
        run = client.get_run(result.mlflow_run_id)
        prompt_artifacts = {
            artifact.path
            for artifact in client.list_artifacts(result.mlflow_run_id, "prompts")
        }

        self.assertEqual(run.data.params["generator_skill_name"], "generator_plain")
        self.assertEqual(run.data.params["generator_skill_file"], "generator_plain.md")
        self.assertIn("prompts/generator_plain.md", prompt_artifacts)
        self.assertIn("prompts/validator.md", prompt_artifacts)

    def test_evaluate_round_marks_run_failed_when_artifact_logging_fails(
        self,
    ) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "neutral"],
                "model-b": ["entailment", "neutral"],
                "model-c": ["entailment", "neutral"],
            }
        )

        original_log_artifact = MlflowClient.log_artifact

        def fail_disagreement_artifact(
            self_client, run_id, local_path, *args, **kwargs
        ):
            if str(local_path).endswith("disagreement_rows.csv"):
                raise MlflowException("artifact logging failed")
            return original_log_artifact(
                self_client, run_id, local_path, *args, **kwargs
            )

        with patch.object(MlflowClient, "log_artifact", fail_disagreement_artifact):
            with self.assertRaisesRegex(MlflowException, "artifact logging failed"):
                self._evaluate()

        client = self._client()
        experiment = client.get_experiment_by_name("test-calibration")
        self.assertIsNotNone(experiment)
        runs = client.search_runs([experiment.experiment_id])
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].info.status, "FAILED")

    def test_logs_low_agreement_round_with_manual_update_proposal(self) -> None:
        self._write_verdicts(
            {
                "model-a": ["entailment", "entailment"],
                "model-b": ["neutral", "neutral"],
                "model-c": ["contradiction", "contradiction"],
            }
        )

        result = self._evaluate()

        self.assertEqual(result.decision, "needs_prompt_update")
        self.assertLess(result.kappa, result.threshold)
        self.assertGreater(result.n_disagreements, 0)
        self.assertIsNotNone(result.proposal)
        self.assertEqual(
            result.proposal_artifact_path,
            "prompt_augment_proposal.json",
        )
        assert result.proposal is not None
        self.assertIn("below", result.proposal.reason)
        self.assertEqual(result.proposal.evidence_uids, ["row-1", "row-2"])

        client = self._client()
        run = client.get_run(result.mlflow_run_id)
        self.assertGreater(run.data.metrics["n_disagreements"], 0)
        self.assertEqual(run.data.tags["decision"], "needs_prompt_update")
        artifact_path = client.download_artifacts(
            result.mlflow_run_id,
            result.proposal_artifact_path,
        )
        proposal = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
        self.assertEqual(proposal["evidence_uids"], ["row-1", "row-2"])
        self.assertIn("manually update", proposal["suggested_action"])

    def test_mixed_numeric_and_named_labels_agree(self) -> None:
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
                        "reason": "Ly do hop le.",
                    }
                    for index, label in enumerate(labels, start=1)
                ]
            ).to_csv(self.verdicts_dir / f"{model}.csv", index=False)

        result = self._evaluate()

        self.assertEqual(result.kappa, 1.0)
        self.assertEqual(result.n_disagreements, 0)
        self.assertEqual(result.decision, "accepted")
        self.assertIsNone(result.proposal)


if __name__ == "__main__":
    unittest.main()
