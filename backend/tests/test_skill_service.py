import unittest
from pathlib import Path

from src.services.skill_service import SkillService


class SkillServiceTest(unittest.TestCase):
    def test_validator_skill_describes_masked_validation_contract(self) -> None:
        skill = SkillService().get_skill("validator")

        self.assertIn('"label": ""', skill)
        self.assertIn("predicted_label", skill)
        self.assertIn("reason", skill)
        self.assertNotIn("confidence", skill)
        self.assertNotIn("rationale", skill)
        self.assertNotIn("artifact_flags", skill)

    def test_generator_policy_skills_are_explicit(self) -> None:
        skill_service = SkillService()

        plain = skill_service.get_skill("generator_plain")
        adversarial = skill_service.get_skill("generator_adversarial")
        instructor = skill_service.get_skill("instructor")

        self.assertIn("Do not add a new", plain)
        self.assertIn("adversarial transformation", plain)
        self.assertIn("label-compatible adversarial transformation", adversarial)
        self.assertIn("skill://generator_plain", instructor)
        self.assertIn("skill://generator_adversarial", instructor)

    def test_prompt_refinement_skill_uses_mcp_kappa_and_explicit_lock(self) -> None:
        skill_service = SkillService()

        skill = skill_service.get_skill("prompt_refinement")
        instructor = skill_service.get_skill("instructor")

        self.assertIn("evaluate_prompt_refinement_round", skill)
        self.assertIn("confirm_prompt_lock", skill)
        self.assertIn("0.85", skill)
        self.assertIn("eligible_to_lock", skill)
        self.assertIn("exactly three", skill.lower())
        self.assertIn("skill://prompt_refinement", instructor)

    def test_prompt_refinement_documents_main_agent_subagent_boundaries(self) -> None:
        skill = SkillService().get_skill("prompt_refinement")
        repository_root = Path(__file__).resolve().parents[2]
        english_template = (
            repository_root / "docs/en/template/prompt-refinement.md"
        ).read_text(encoding="utf-8")
        vietnamese_template = (
            repository_root / "docs/vi/template/prompt-refinement.md"
        ).read_text(encoding="utf-8")

        for document in (skill, english_template, vietnamese_template):
            self.assertIn("main agent", document.lower())
            self.assertIn("subagent", document.lower())
            self.assertIn("do not call mcp", document.lower())
            self.assertIn("expected label", document.lower())
            self.assertIn("one verdict file", document.lower())
            self.assertIn("evaluate_prompt_refinement_round", document)

    def test_prompt_refinement_documents_editor_candidate_workflow(self) -> None:
        skill = SkillService().get_skill("prompt_refinement")
        repository_root = Path(__file__).resolve().parents[2]
        english_template = (
            repository_root / "docs/en/template/prompt-refinement.md"
        ).read_text(encoding="utf-8")
        vietnamese_template = (
            repository_root / "docs/vi/template/prompt-refinement.md"
        ).read_text(encoding="utf-8")

        for document in (skill, english_template, vietnamese_template):
            lower_document = document.lower()
            self.assertIn("max_rounds", document)
            self.assertIn("evidence/", document)
            self.assertIn("prepare_prompt_refinement_evidence_pack", document)
            self.assertIn("prepare_prompt_refinement_editor_tasks", document)
            self.assertIn("validator-rubric reviewer", document)
            self.assertIn("generator-policy reviewer", document)
            self.assertTrue(
                "source_uid set" in document or "source uid set" in lower_document
            )
            self.assertIn("pmi", lower_document)

    def test_editor_templates_are_proposal_only_and_single_target(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        documents = [
            (
                repository_root
                / "docs/en/template/prompt-refinement-editor-validator-rubric.md"
            ).read_text(encoding="utf-8"),
            (
                repository_root
                / "docs/en/template/prompt-refinement-editor-generator-policy.md"
            ).read_text(encoding="utf-8"),
            (
                repository_root
                / "docs/vi/template/prompt-refinement-editor-validator-rubric.md"
            ).read_text(encoding="utf-8"),
            (
                repository_root
                / "docs/vi/template/prompt-refinement-editor-generator-policy.md"
            ).read_text(encoding="utf-8"),
        ]

        for document in documents:
            lower_document = document.lower()
            self.assertIn("do not call mcp", lower_document)
            self.assertTrue(
                "do not edit files" in lower_document
                or "không edit files" in lower_document
            )
            self.assertTrue(
                "do not run evaluation" in lower_document
                or "không chạy evaluation" in lower_document
            )
            self.assertTrue(
                "inspect only" in lower_document or "chỉ inspect" in lower_document
            )
            self.assertIn("target: ", document)
            self.assertIn("no_change", document)
            self.assertTrue(
                "do not return `both`" in lower_document
                or "không được trả target là `both`" in lower_document
            )

    def test_prompt_refinement_templates_avoid_repo_and_server_leakage(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        documents = [
            *(
                path.read_text(encoding="utf-8")
                for path in sorted(
                    (repository_root / "docs/en/template").glob("prompt-refinement*.md")
                )
            ),
            *(
                path.read_text(encoding="utf-8")
                for path in sorted(
                    (repository_root / "docs/vi/template").glob("prompt-refinement*.md")
                )
            ),
        ]
        forbidden_literals = [
            "/Users/",
            "You are in repo",
            "Bạn đang ở repo",
            "uv run mlflow",
            "mlflow server",
            "uv run uvicorn",
            "docker compose",
            "backend/skills/",
            "backend/src/",
        ]

        for document in documents:
            for forbidden in forbidden_literals:
                self.assertNotIn(forbidden, document)

    def test_prompt_refinement_main_templates_name_exactly_two_editor_roles(
        self,
    ) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        documents = [
            (repository_root / "docs/en/template/prompt-refinement.md").read_text(
                encoding="utf-8"
            ),
            (repository_root / "docs/vi/template/prompt-refinement.md").read_text(
                encoding="utf-8"
            ),
        ]

        for document in documents:
            self.assertEqual(document.count("validator-rubric reviewer"), 1)
            self.assertEqual(document.count("generator-policy reviewer"), 1)
            self.assertIn("blind", document.lower())
            self.assertTrue(
                "post-failure reviewers" in document.lower()
                or "reviewer sau failed round" in document.lower()
            )

    def test_post_validation_templates_cover_pmi_revalidation_and_split(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        documents = [
            (repository_root / "docs/en/template/post-validation.md").read_text(
                encoding="utf-8"
            ),
            (repository_root / "docs/vi/template/post-validation.md").read_text(
                encoding="utf-8"
            ),
        ]

        for document in documents:
            lower_document = document.lower()
            self.assertIn("run_consensus_pmi", document)
            self.assertIn("promote_paraphrase_revalidation", document)
            self.assertIn("python -m src.cli apply-paraphrase", document)
            self.assertIn("python -m src.cli split", document)
            self.assertIn("pmi_flagged_rows.csv", document)
            self.assertIn("paraphrase_revalidation_masked.csv", document)
            self.assertIn("revalidation_verdicts", document)
            self.assertIn("validated_dataset.csv", document)
            self.assertIn("promoted_dataset.csv", document)
            self.assertIn("split_manifest.json", document)
            self.assertTrue(
                "do not call start_validation_run" in lower_document
                or "không gọi start_validation_run" in lower_document
            )
            self.assertIn("deterministic", lower_document)
            self.assertIn("pmi", lower_document)
            self.assertTrue(
                "do not edit generator or validator prompts" in lower_document
                or "không sửa generator hoặc validator prompts" in lower_document
            )

    def test_agent_templates_use_data_output_convention(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        templates = [
            repository_root / "docs/en/template/generator.md",
            repository_root / "docs/vi/template/generator.md",
            repository_root / "docs/en/template/validator.md",
            repository_root / "docs/vi/template/validator.md",
            repository_root / "docs/en/template/post-validation.md",
            repository_root / "docs/vi/template/post-validation.md",
            repository_root / "docs/en/template/prompt-refinement.md",
            repository_root / "docs/vi/template/prompt-refinement.md",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in templates)

        self.assertNotIn("outputs/", combined)
        self.assertNotIn("backend/outputs", combined)
        self.assertNotIn("DATA_GENERATED_OUTPUT", combined)
        self.assertNotIn("DATA_VALIDATED_OUTPUT", combined)
        self.assertNotIn("POST_VALIDATION_OUTPUT_DIR", combined)
        self.assertNotIn("FINAL_SPLIT_OUTPUT_DIR", combined)
        self.assertNotIn("PROMPT_REFINEMENT_OUTPUT_DIR", combined)
        self.assertIn("data/generated/", combined)
        self.assertIn("data/validated/", combined)
        self.assertIn("data/splits/", combined)
        self.assertIn("data/prompt-refinement/", combined)


if __name__ == "__main__":
    unittest.main()
