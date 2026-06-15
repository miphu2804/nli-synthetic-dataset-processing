from fastapi import APIRouter

mcp_router = APIRouter(prefix="/api/mcp", tags=["mcp"])
_mcp_instance = None


def init_mcp_router(mcp) -> None:
    global _mcp_instance
    _mcp_instance = mcp


@mcp_router.get("/status")
async def get_mcp_status():
    try:
        tools = await _mcp_instance.list_tools()
        return {
            "server_name": getattr(
                _mcp_instance, "name", "nli-data-processing-mcp-server"
            ),
            "connected": True,
            "tool_count": len(tools),
            "tools": [
                {"name": t.name, "description": t.description or ""} for t in tools
            ],
        }
    except Exception:
        return {
            "server_name": getattr(
                _mcp_instance, "name", "nli-data-processing-mcp-server"
            ),
            "connected": False,
            "tool_count": 0,
            "tools": [],
        }
