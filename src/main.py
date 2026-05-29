from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

from src.routers.reader_router import reader_router
from src.routers.skill_router import skill_router
from src.routers.translate_router import translate_router
from src.routers.writer_router import writer_router
from src.services.skill_service import SkillService

app = FastAPI()
app.include_router(reader_router)
app.include_router(skill_router)
app.include_router(translate_router)
app.include_router(writer_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def get_health() -> dict[str, str]:
    return {"status": "ok"}


mcp = FastMCP.from_fastapi(app, name="nli-data-processing-mcp-server")
mcp_app = mcp.http_app(path="/")
app.router.lifespan_context = mcp_app.lifespan
app.mount("/mcp", mcp_app)

skill_service = SkillService()


@mcp.resource("skill://{name}")
def get_skill_resource(name: str) -> str:
    return skill_service.get_skill(name)
