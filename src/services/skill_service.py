from pathlib import Path

SKILLS_DIR = Path("skills")


class SkillService:
    def get_skill(self, name: str) -> str:
        skill_path = SKILLS_DIR / f"{name}.md"
        if not skill_path.exists():
            raise FileNotFoundError(f"Skill not found: {name}")
        return skill_path.read_text()

    def list_skills(self) -> list[str]:
        skill_files = SKILLS_DIR.glob("*.md")
        return sorted(
            skill_path.stem for skill_path in skill_files if skill_path.is_file()
        )
