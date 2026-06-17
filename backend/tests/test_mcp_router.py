import unittest

import httpx
from fastapi import FastAPI
from fastmcp import FastMCP
from src.routers.mcp_router import init_mcp_router, mcp_router


class McpRouterTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(mcp_router)
        mcp = FastMCP.from_fastapi(app, name="nli-test-mcp-server")

        @mcp.tool
        def tool_a(x: str) -> str:
            """Alpha tool"""
            return x

        @mcp.tool
        def tool_b(y: int) -> int:
            """Beta tool"""
            return y

        init_mcp_router(mcp)
        self.transport = httpx.ASGITransport(app=app)

    async def test_mcp_status_returns_tool_list(self) -> None:
        async with httpx.AsyncClient(
            transport=self.transport, base_url="http://test"
        ) as client:
            response = await client.get("/api/mcp/status")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["connected"])
        self.assertEqual(data["server_name"], "nli-test-mcp-server")
        self.assertGreaterEqual(data["tool_count"], 2)
        tool_names = {t["name"] for t in data["tools"]}
        self.assertIn("tool_a", tool_names)
        self.assertIn("tool_b", tool_names)
