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

    def _evaluate(self, *, confirm_lock: bool = False):
        return self.service.evaluate_round(
            verdicts_dir=self.verdicts_dir,
            calibration_input=self.calibration_input,
            round_number=1,
            change_summary="Initial calibration.",
            confirm_lock=confirm_lock,
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

        result = self._evaluate(confirm_lock=True)

        self.assertEqual(result.decision, "lock_prompt")
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

        with self.assertRaisesRegex(ValueError, "below"):
            self._evaluate(confirm_lock=True)

        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        self.assertIsNone(client.get_prompt("nli-generator"))

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
        client = MlflowClient(
            tracking_uri=self.tracking_uri, registry_uri=self.tracking_uri
        )
        with self.assertRaises(MlflowException):
            client.get_prompt_version_by_alias("nli-generator", "locked")


if __name__ == "__main__":
    unittest.main()
