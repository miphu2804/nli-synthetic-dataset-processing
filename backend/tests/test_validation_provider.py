import asyncio
import tempfile
import unittest
from pathlib import Path

import fastmcp
import pandas as pd
from fastmcp import FastMCP
from pydantic import ValidationError

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

    def test_prompt_refinement_tool_exposes_explicit_mlflow_parameters(self) -> None:
        async def scenario() -> None:
            tool = await self.mcp.get_tool("evaluate_prompt_refinement")
            properties = tool.parameters["properties"]

            self.assertIn("verdicts_dir", properties)
            self.assertIn("calibration_input", properties)
            self.assertIn("tracking_uri", properties)
            self.assertIn("experiment_name", properties)
            self.assertIn("generator_skill_name", properties)
            self.assertNotIn("round_number", properties)
            self.assertNotIn("change_summary", properties)
            self.assertNotIn("confirm_lock", properties)
            self.assertNotIn("session_id", properties)

        asyncio.run(scenario())

    def test_prompt_refinement_proposal_tool_is_not_backend_owned(self) -> None:
        async def scenario() -> None:
            tool_names = {tool.name for tool in await self.mcp.list_tools()}

            self.assertNotIn("propose_prompt_refinement_update", tool_names)

        asyncio.run(scenario())

    def test_prompt_refinement_evidence_pack_tool_is_not_backend_owned(self) -> None:
        async def scenario() -> None:
            tool_names = {tool.name for tool in await self.mcp.list_tools()}

            self.assertNotIn("prepare_prompt_refinement_evidence_pack", tool_names)

        asyncio.run(scenario())

    def test_prompt_refinement_editor_tasks_tool_is_not_backend_owned(self) -> None:
        async def scenario() -> None:
            tool_names = {tool.name for tool in await self.mcp.list_tools()}

            self.assertNotIn("prepare_prompt_refinement_editor_tasks", tool_names)

        asyncio.run(scenario())

    def test_prompt_refinement_lock_tool_is_not_backend_owned(self) -> None:
        async def scenario() -> None:
            tool_names = {tool.name for tool in await self.mcp.list_tools()}

            self.assertNotIn("confirm_prompt_lock", tool_names)

        asyncio.run(scenario())

    def test_deterministic_stage_tools_expose_explicit_parameters(self) -> None:
        async def scenario() -> None:
            consensus = await self.mcp.get_tool("run_consensus_pmi")
            consensus_properties = consensus.parameters["properties"]
            for name in (
                "verdicts_dir",
                "masked_input",
                "expected_input",
                "output_dir",
                "pmi_threshold",
                "min_joint_count",
            ):
                self.assertIn(name, consensus_properties)
            self.assertNotIn("self", consensus_properties)

            promote = await self.mcp.get_tool("promote_paraphrase_revalidation")
            promote_properties = promote.parameters["properties"]
            for name in (
                "input_path",
                "revalidation_input",
                "verdicts_dir",
                "expected_input",
                "output_path",
                "review_output",
                "votes_output",
            ):
                self.assertIn(name, promote_properties)
            self.assertNotIn("self", promote_properties)

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

            self.assertEqual(first_row["label"], "")
            self.assertNotIn("masked_label", first_row)

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

    def test_run_consensus_pmi_tool_writes_artifacts(self) -> None:
        verdicts_dir = self.root / "consensus-verdicts"
        verdicts_dir.mkdir()
        masked_path = self.root / "masked.csv"
        expected_path = self.root / "expected.csv"
        output_dir = self.root / "consensus-output"
        pd.DataFrame(
            [
                {"source_uid": "row-1", "premise": "p1", "hypothesis": "alpha"},
                {"source_uid": "row-2", "premise": "p2", "hypothesis": "beta"},
            ]
        ).to_csv(masked_path, index=False)
        pd.DataFrame(
            [
                {
                    "source_uid": "row-1",
                    "premise": "p1",
                    "hypothesis": "alpha",
                    "label": "entailment",
                },
                {
                    "source_uid": "row-2",
                    "premise": "p2",
                    "hypothesis": "beta",
                    "label": "entailment",
                },
            ]
        ).to_csv(expected_path, index=False)
        labels_by_model = {
            "gpt4o": {"row-1": "entailment", "row-2": "neutral"},
            "deepseek": {"row-1": "entailment", "row-2": "contradiction"},
            "llama": {"row-1": "entailment", "row-2": "neutral"},
        }
        for model_name, labels in labels_by_model.items():
            pd.DataFrame(
                [
                    {
                        "source_uid": source_uid,
                        "predicted_label": label,
                        "reason": "ok",
                    }
                    for source_uid, label in labels.items()
                ]
            ).to_csv(verdicts_dir / f"{model_name}.csv", index=False)

        async def scenario() -> None:
            result = await self.mcp.call_tool(
                "run_consensus_pmi",
                {
                    "verdicts_dir": str(verdicts_dir),
                    "masked_input": str(masked_path),
                    "expected_input": str(expected_path),
                    "output_dir": str(output_dir),
                    "pmi_threshold": 0.0,
                    "min_joint_count": 1,
                },
            )
            content = result.structured_content
            self.assertEqual(content["total_rows"], 2)
            self.assertEqual(content["keep"], 1)
            self.assertTrue(Path(content["validated_output"]).exists())
            self.assertTrue(Path(content["pmi_rows_output"]).exists())

        asyncio.run(scenario())

    def test_promote_paraphrase_revalidation_tool_writes_outputs(self) -> None:
        input_path = self.root / "paraphrased_dataset.csv"
        revalidation_path = self.root / "paraphrase_revalidation_masked.csv"
        expected_path = self.root / "validated_dataset.csv"
        verdicts_dir = self.root / "promotion-verdicts"
        verdicts_dir.mkdir()
        pd.DataFrame(
            [
                {
                    "source_uid": "row-1",
                    "premise": "p1",
                    "hypothesis": "h1",
                    "label": "entailment",
                },
                {
                    "source_uid": "row-2",
                    "premise": "p2",
                    "hypothesis": "h2-rewritten",
                    "label": "neutral",
                },
            ]
        ).to_csv(input_path, index=False)
        pd.DataFrame(
            [
                {
                    "source_uid": "row-1",
                    "premise": "p1",
                    "hypothesis": "h1",
                    "label": "entailment",
                },
                {
                    "source_uid": "row-2",
                    "premise": "p2",
                    "hypothesis": "h2",
                    "label": "neutral",
                },
            ]
        ).to_csv(expected_path, index=False)
        pd.DataFrame(
            [
                {
                    "source_uid": "row-2",
                    "premise": "p2",
                    "hypothesis": "h2-rewritten",
                    "label": "",
                }
            ]
        ).to_csv(revalidation_path, index=False)
        labels_by_model = {
            "gpt4o": "neutral",
            "deepseek": "neutral",
            "llama": "entailment",
        }
        for model_name, label in labels_by_model.items():
            pd.DataFrame(
                [
                    {
                        "source_uid": "row-2",
                        "predicted_label": label,
                        "reason": "ok",
                    }
                ]
            ).to_csv(verdicts_dir / f"{model_name}.csv", index=False)

        async def scenario() -> None:
            result = await self.mcp.call_tool(
                "promote_paraphrase_revalidation",
                {
                    "input_path": str(input_path),
                    "revalidation_input": str(revalidation_path),
                    "verdicts_dir": str(verdicts_dir),
                    "expected_input": str(expected_path),
                },
            )
            content = result.structured_content
            self.assertEqual(content["promoted_rows"], 2)
            self.assertEqual(content["accepted_rewrites"], 1)
            self.assertTrue(Path(content["output_path"]).exists())
            self.assertTrue(Path(content["votes_output_path"]).exists())

        asyncio.run(scenario())

    def test_submit_validation_result_rejects_invalid_label_through_mcp(self) -> None:
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
            batch_id = claimed.structured_content["batch"]["batch_id"]

            with self.assertRaises((fastmcp.exceptions.ToolError, ValidationError)):
                await self.mcp.call_tool(
                    "submit_validation_result",
                    {
                        "run_id": run_id,
                        "agent_id": "judge-a",
                        "batch_id": batch_id,
                        "verdicts": [
                            {
                                "source_uid": 1,
                                "predicted_label": "garbage",
                                "reason": "Invalid.",
                            },
                            {
                                "source_uid": 2,
                                "predicted_label": "neutral",
                                "reason": "ok",
                            },
                        ],
                    },
                )

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
