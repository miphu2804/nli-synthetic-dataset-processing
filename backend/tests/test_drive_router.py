import unittest

import httpx
from fastapi import FastAPI
from src.routers.drive_router import drive_router, drive_service


class DriveRouterTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        # Reset the module-level singleton for test isolation
        drive_service.__init__()
        app = FastAPI()
        app.include_router(drive_router)
        self.transport = httpx.ASGITransport(app=app)

    async def test_auth_status_not_authenticated_initially(self) -> None:
        async with httpx.AsyncClient(
            transport=self.transport, base_url="http://test"
        ) as client:
            response = await client.get("/api/drive/auth/status")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["authenticated"])
        self.assertIsNone(data["user_email"])
        self.assertTrue(data["stub"])

    async def test_auth_flow(self) -> None:
        async with httpx.AsyncClient(
            transport=self.transport, base_url="http://test"
        ) as client:
            # Start auth
            start = await client.post("/api/drive/auth/start")
            self.assertEqual(start.status_code, 200)
            self.assertEqual(start.json()["user_code"], "ABCD-1234")
            self.assertTrue(start.json()["stub"])

            # First complete -- still pending
            complete1 = await client.post("/api/drive/auth/complete")
            self.assertFalse(complete1.json()["authenticated"])
            self.assertEqual(complete1.json()["status"], "pending")

            # Second complete -- now authenticated
            complete2 = await client.post("/api/drive/auth/complete")
            self.assertTrue(complete2.json()["authenticated"])
            self.assertEqual(complete2.json()["user_email"], "demo@stub.local")
            self.assertTrue(complete2.json()["stub"])

            # Status reflects authentication
            status = await client.get("/api/drive/auth/status")
            self.assertTrue(status.json()["authenticated"])

    async def test_browse_files_returns_stub_data(self) -> None:
        async with httpx.AsyncClient(
            transport=self.transport, base_url="http://test"
        ) as client:
            response = await client.get("/api/drive/files?folder_id=root")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["folder_id"], "root")
        self.assertGreater(len(data["files"]), 0)
        self.assertGreater(len(data["subfolders"]), 0)
        self.assertTrue(data["stub"])

    async def test_download_returns_stub_response(self) -> None:
        async with httpx.AsyncClient(
            transport=self.transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/drive/download",
                json={"file_id": "file-001", "destination_path": "data/original/"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["drive_file_id"], "file-001")
        self.assertTrue(data["stub"])

    async def test_upload_returns_stub_response(self) -> None:
        async with httpx.AsyncClient(
            transport=self.transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/drive/upload",
                json={"local_path": "data/test.csv", "file_name": "test.csv"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["file_name"], "test.csv")
        self.assertTrue(data["stub"])
