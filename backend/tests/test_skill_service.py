import unittest
from pathlib import Path

from src.services.skill_service import SkillService


class SkillServiceTest(unittest.TestCase):
    def test_validator_skill_describes_masked_validation_contract(self) -> None:
        skill = SkillService().get_skill("validator")

        self.assertIn("masked_label", skill)
        self.assertIn("predicted_label", skill)
        self.assertIn("reason", skill)
        self.assertNotIn("confidence", skill)
        self.assertNotIn("rationale", skill)
        self.assertNotIn("artifact_flags", skill)

    def test_prompt_refinement_skill_uses_mcp_kappa_and_explicit_lock(self) -> None:
        skill_service = SkillService()

        skill = skill_service.get_skill("prompt_refinement")
        instructor = skill_service.get_skill("instructor")

        self.assertIn("evaluate_prompt_refinement_round", skill)
        self.assertIn("0.85", skill)
        self.assertIn("eligible_to_lock", skill)
        self.assertIn("confirm_lock", skill)
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


if __name__ == "__main__":
    unittest.main()
