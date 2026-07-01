import asyncio
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from fastmcp import FastMCP

from src.providers import register_generation_tools


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

    def test_artifact_submission_round_trip(self) -> None:
        async def scenario() -> None:
            started = await self.mcp.call_tool(
                "start_generation_run",
                {
                    "input_path": str(self.input_path),
                    "output_path": str(self.root / "output.csv"),
                    "from_sample": 1,
                    "to_sample": 2,
                    "batch_size": 2,
                },
            )
            run_id = started.structured_content["run_id"]
            claim = await self.mcp.call_tool(
                "claim_next_batch",
                {"run_id": run_id, "agent_id": "agent-a"},
            )
            batch = claim.structured_content["batch"]
            rows_path = Path(batch["artifact_targets"]["rows_csv_path"])
            skips_path = Path(batch["artifact_targets"]["skipped_rows_csv_path"])
            pd.DataFrame(
                [
                    {
                        "source_uid": batch["rows"][0]["source_uid"],
                        "premise": "vp1",
                        "hypothesis": "vh1",
                        "label": batch["rows"][0]["label"],
                    }
                ]
            ).to_csv(rows_path, index=False)
            pd.DataFrame(
                [
                    {
                        "source_uid": batch["rows"][1]["source_uid"],
                        "reason": "fail",
                        "retries": 3,
                    }
                ]
            ).to_csv(skips_path, index=False)

            submitted = await self.mcp.call_tool(
                "submit_batch_result_from_artifacts",
                {
                    "run_id": run_id,
                    "agent_id": "agent-a",
                    "batch_id": batch["batch_id"],
                    "rows_csv_path": str(rows_path),
                    "skipped_rows_csv_path": str(skips_path),
                },
            )

            self.assertEqual(submitted.structured_content["rows_written"], 1)
            self.assertEqual(submitted.structured_content["rows_skipped"], 1)

        asyncio.run(scenario())
