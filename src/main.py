from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

from src.routers import router as dataset_router

app = FastAPI()
app.include_router(dataset_router)

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


mcp = FastMCP.from_fastapi(app, name="dataset-reader-mcp")
app.mount("/mcp", mcp.http_app(path="/"))
