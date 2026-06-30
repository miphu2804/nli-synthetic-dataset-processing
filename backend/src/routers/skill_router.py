from fastapi import APIRouter, HTTPException

from src.services.skill_service import SkillService

skill_router = APIRouter(prefix="/api/skills", tags=["skill"])
skill_service = SkillService()


@skill_router.get("/")
async def list_skills() -> list[str]:
    return skill_service.list_skills()


@skill_router.get("/{name}")
async def get_skill(name: str) -> dict[str, str]:
    try:
        content = skill_service.get_skill(name)
        return {"name": name, "content": content}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
