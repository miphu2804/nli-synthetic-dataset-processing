import unittest

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


if __name__ == "__main__":
    unittest.main()
