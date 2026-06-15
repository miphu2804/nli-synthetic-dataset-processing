import asyncio
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from fastmcp import FastMCP

from src.providers import register_validation_tools


class ValidationProviderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.pipeline_dir = self.root / ".pipeline" / "validation"
        self.input_path = self.root / "generated.csv"
        pd.DataFrame(
            [
                {"source_uid": 1, "premise": "p1", "hypothesis": "h1", "label": 1},
                {"source_uid": 2, "premise": "p2", "hypothesis": "h2", "label": 0},
            ]
        ).to_csv(self.input_path, index=False)
        self.mcp = FastMCP("test-mcp")
        register_validation_tools(self.mcp, self.pipeline_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_validation_tools_register_without_self(self) -> None:
        async def scenario() -> None:
            tool = await self.mcp.get_tool("claim_next_validation_batch")
            self.assertNotIn("self", tool.parameters["properties"])

        asyncio.run(scenario())

    def test_start_validation_run_tool_uses_sample_range_schema(self) -> None:
        async def scenario() -> None:
            tool = await self.mcp.get_tool("start_validation_run")

            self.assertIn("from_sample", tool.parameters["properties"])
            self.assertIn("to_sample", tool.parameters["properties"])
            self.assertNotIn("row_offset", tool.parameters["properties"])
            self.assertNotIn("row_limit", tool.parameters["properties"])

        asyncio.run(scenario())

    def test_validation_tool_round_trip_uses_masked_rows(self) -> None:
        async def scenario() -> None:
            started = await self.mcp.call_tool(
                "start_validation_run",
                {
                    "input_path": str(self.input_path),
                    "output_dir": str(self.root / "validation-output"),
                    "from_sample": 1,
                    "to_sample": 2,
                    "batch_size": 2,
                },
            )
            run_id = started.structured_content["run_id"]
            claimed = await self.mcp.call_tool(
                "claim_next_validation_batch",
                {"run_id": run_id, "agent_id": "judge-a"},
            )
            first_row = claimed.structured_content["batch"]["rows"][0]

            self.assertEqual(first_row["masked_label"], "[MASK]")
            self.assertNotIn("label", first_row)

            submitted = await self.mcp.call_tool(
                "submit_validation_result",
                {
                    "run_id": run_id,
                    "agent_id": "judge-a",
                    "batch_id": claimed.structured_content["batch"]["batch_id"],
                    "verdicts": [
                        {
                            "source_uid": 1,
                            "predicted_label": 1,
                            "reason": "Supported.",
                        },
                        {
                            "source_uid": 2,
                            "predicted_label": 1,
                            "reason": "Mismatch.",
                        },
                    ],
                },
            )
            self.assertEqual(submitted.structured_content["accepted_count"], 1)
            self.assertEqual(submitted.structured_content["rejected_count"], 1)
            self.assertEqual(submitted.structured_content["rows_validated"], 2)

            finalized = await self.mcp.call_tool(
                "finalize_validation_run",
                {"run_id": run_id},
            )
            self.assertEqual(finalized.structured_content["total_rows"], 2)
            self.assertEqual(finalized.structured_content["accepted_rows"], 1)
            self.assertEqual(finalized.structured_content["rejected_rows"], 1)
            self.assertTrue(
                finalized.structured_content["output_path"].endswith(
                    "validation_results.csv"
                )
            )

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
