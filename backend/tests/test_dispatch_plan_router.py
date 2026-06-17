import unittest

import httpx
from fastapi import FastAPI
from src.routers.dispatch_plan_router import dispatch_plan_router


class DispatchPlanRouterTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(dispatch_plan_router)
        self.transport = httpx.ASGITransport(app=app)

    async def test_calculate_dispatch_plan_returns_parallel_worker_count(self) -> None:
        async with httpx.AsyncClient(
            transport=self.transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/dispatch-plan/calculate",
                json={"samples": 100},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "samples": 100,
                "batch_size": 20,
                "total_batches": 5,
                "max_parallel_workers": 10,
                "parallel_workers": 5,
                "dispatch_strategy": "sliding_window",
            },
        )
