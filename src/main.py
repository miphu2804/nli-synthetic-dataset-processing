from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.app_config import app_config
from src.dataset_reader_service import DatasetReaderService
from src.mcp_server import MCPAdapter
from src.openai_translation_service import OpenAITranslationService
from src.routers import router as dataset_router

dataset_reader_service = DatasetReaderService()
translation_service = OpenAITranslationService()
mcp_adapter = MCPAdapter(
    dataset_reader_service=dataset_reader_service,
    translation_service=translation_service,
)
mcp_http_app = mcp_adapter.http_app()

app = FastAPI(title=app_config.APP_NAME, lifespan=mcp_http_app.lifespan)
app.include_router(dataset_router)
app.mount(app_config.MCP_MOUNT_PATH, mcp_http_app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
