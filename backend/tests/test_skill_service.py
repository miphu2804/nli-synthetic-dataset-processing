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


if __name__ == "__main__":
    unittest.main()
