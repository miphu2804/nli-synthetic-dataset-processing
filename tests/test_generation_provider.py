import asyncio
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from fastmcp import FastMCP

from src.providers import register_dispatch_planning_tools, register_generation_tools


class GenerationProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.pipeline_dir = self.root / ".pipeline"
        self.input_path = self.root / "input.csv"
        pd.DataFrame(
            [
                {"uid": 1, "premise": "p1", "hypothesis": "h1", "label": 0},
                {"uid": 2, "premise": "p2", "hypothesis": "h2", "label": 1},
                {"uid": 3, "premise": "p3", "hypothesis": "h3", "label": 2},
                {"uid": 4, "premise": "p4", "hypothesis": "h4", "label": 1},
            ]
        ).to_csv(self.input_path, index=False)
        self.mcp = FastMCP("test-mcp")
        register_generation_tools(self.mcp, self.pipeline_dir)
        register_dispatch_planning_tools(self.mcp)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_bound_methods_register_without_self(self) -> None:
        async def scenario() -> None:
            tool = await self.mcp.get_tool("claim_next_batch")
            self.assertNotIn("self", tool.parameters["properties"])

        asyncio.run(scenario())

    def test_start_run_tool_exposes_twenty_as_default_batch_size(self) -> None:
        async def scenario() -> None:
            tool = await self.mcp.get_tool("start_generation_run")

            self.assertEqual(
                tool.parameters["properties"]["batch_size"]["default"],
                20,
            )
            self.assertIn("from_sample", tool.parameters["properties"])
            self.assertIn("to_sample", tool.parameters["properties"])
            self.assertNotIn("row_offset", tool.parameters["properties"])
            self.assertNotIn("row_limit", tool.parameters["properties"])

        asyncio.run(scenario())

    def test_calculate_dispatch_plan_tool_returns_adaptive_worker_count(self) -> None:
        async def scenario() -> None:
            result = await self.mcp.call_tool(
                "calculate_dispatch_plan",
                {"samples": 100},
            )

            self.assertEqual(result.structured_content["batch_size"], 20)
            self.assertEqual(result.structured_content["total_batches"], 5)
            self.assertEqual(result.structured_content["parallel_workers"], 5)

        asyncio.run(scenario())

    def test_claim_submit_progress_round_trip_and_independent_batch_commit(
        self,
    ) -> None:
        async def scenario() -> None:
            started = await self.mcp.call_tool(
                "start_generation_run",
                {
                    "input_path": str(self.input_path),
                    "output_path": str(self.root / "output.csv"),
                    "from_sample": 2,
                    "to_sample": 3,
                    "batch_size": 1,
                },
            )
            run_id = started.structured_content["run_id"]
            self.assertEqual(started.structured_content["row_offset"], 1)

            claim_one = await self.mcp.call_tool(
                "claim_next_batch",
                {"run_id": run_id, "agent_id": "agent-a"},
            )
            claim_two = await self.mcp.call_tool(
                "claim_next_batch",
                {"run_id": run_id, "agent_id": "agent-b"},
            )

            commit_one = await self.mcp.call_tool(
                "submit_batch_result",
                {
                    "run_id": run_id,
                    "agent_id": "agent-a",
                    "batch_id": claim_one.structured_content["batch"]["batch_id"],
                    "rows": [
                        {
                            "source_uid": claim_one.structured_content["batch"]["rows"][
                                0
                            ]["source_uid"],
                            "premise": "vp1",
                            "hypothesis": "vh1",
                            "label": 1,
                        }
                    ],
                },
            )
            self.assertEqual(commit_one.structured_content["progress"]["done_rows"], 1)

            progress = await self.mcp.call_tool(
                "get_run_progress",
                {"run_id": run_id},
            )
            self.assertEqual(progress.structured_content["claimed_rows"], 1)
            self.assertEqual(progress.structured_content["done_rows"], 1)

            commit_two = await self.mcp.call_tool(
                "submit_batch_result",
                {
                    "run_id": run_id,
                    "agent_id": "agent-b",
                    "batch_id": claim_two.structured_content["batch"]["batch_id"],
                    "rows": [
                        {
                            "source_uid": claim_two.structured_content["batch"]["rows"][
                                0
                            ]["source_uid"],
                            "premise": "vp2",
                            "hypothesis": "vh2",
                            "label": 2,
                        }
                    ],
                },
            )
            self.assertEqual(commit_two.structured_content["progress"]["done_rows"], 2)
            complete = await self.mcp.call_tool(
                "claim_next_batch",
                {"run_id": run_id, "agent_id": "agent-a"},
            )
            self.assertEqual(complete.structured_content["status"], "complete")

        asyncio.run(scenario())
