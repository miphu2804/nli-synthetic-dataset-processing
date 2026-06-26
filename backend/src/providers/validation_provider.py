from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.tools import tool
from pydantic import Field
from src.app_config import app_config
from src.cli import (
    build_verdict_candidates,
    default_consensus_output_dir,
    discover_verdict_files,
)
from src.cli import run_consensus_pmi as run_consensus_pmi_stage
from src.cli import run_promote_paraphrase as run_promote_paraphrase_stage
from src.providers.base import ToolProvider
from src.services.base_run_service import DEFAULT_BATCH_SIZE
from src.services.dataset_reader_service import DatasetReaderService
from src.services.progress_tracking_service import ProgressTrackingService
from src.services.prompt_refinement import PromptRefinementService
from src.services.validation_run_service import ValidationRunService


class ValidationToolProvider(ToolProvider):
    def __init__(
        self,
        validation_run_service: ValidationRunService,
        prompt_refinement_service: PromptRefinementService,
    ) -> None:
        self._validation_run_service = validation_run_service
        self._prompt_refinement_service = prompt_refinement_service

    @tool(
        name="start_validation_run",
        description=(
            "Create one local validation run over generated NLI rows. "
            "Call once before claiming masked validation batches."
        ),
    )
    def start_validation_run(
        self,
        input_path: Annotated[
            str,
            Field(
                description=(
                    "Path to the generated CSV or Parquet file inside the server container. "
                    "Must contain a 'label' column with the expected labels — "
                    "do NOT pass a validator-facing file with blank label values. "
                    "Labels are blanked internally before being returned to validators."
                )
            ),
        ],
        output_dir: Annotated[
            str | None,
            Field(description="Directory for the final validation_results.csv output."),
        ] = None,
        from_sample: Annotated[
            int,
            Field(
                ge=1,
                description="One-based first generated sample number assigned to this run.",
            ),
        ] = 1,
        to_sample: Annotated[
            int | None,
            Field(
                ge=1,
                description="One-based last generated sample number assigned to this run, inclusive.",
            ),
        ] = None,
        batch_size: Annotated[
            int,
            Field(ge=1, description="Rows returned by each claim. Default: 20."),
        ] = DEFAULT_BATCH_SIZE,
        agent_id: Annotated[
            str,
            Field(description="Progress writer identifier. Use main for normal runs."),
        ] = "main",
    ) -> dict[str, Any]:
        row_offset, row_limit = self.sample_range_to_offset_limit(
            from_sample=from_sample,
            to_sample=to_sample,
        )
        return self._validation_run_service.start_validation_run(
            input_path=input_path,
            output_dir=output_dir,
            row_offset=row_offset,
            row_limit=row_limit,
            batch_size=batch_size,
            agent_id=agent_id,
        ).model_dump(mode="json")

    @tool(
        name="claim_next_validation_batch",
        description=(
            "Claim the next validation batch with labels blanked. The returned rows "
            "include premise, hypothesis, source_uid and an empty label field only."
        ),
    )
    def claim_next_validation_batch(
        self,
        run_id: str,
        agent_id: str,
    ) -> dict[str, Any]:
        return self._validation_run_service.claim_next_validation_batch(
            run_id=run_id,
            agent_id=agent_id,
        ).model_dump(mode="json")

    @tool(
        name="submit_validation_result",
        description=(
            "Submit validator verdicts for one claimed masked batch. The runtime "
            "compares predicted_label to the hidden source label."
        ),
    )
    def submit_validation_result(
        self,
        run_id: str,
        agent_id: str,
        batch_id: str,
        verdicts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._validation_run_service.submit_validation_result(
            run_id=run_id,
            agent_id=agent_id,
            batch_id=batch_id,
            verdicts=verdicts,
        ).model_dump(mode="json")

    @tool(
        name="get_validation_progress",
        description="Inspect progress for an active local validation run.",
    )
    def get_validation_progress(self, run_id: str) -> dict[str, Any]:
        return self._validation_run_service.get_validation_progress(run_id).model_dump(
            mode="json"
        )

    @tool(
        name="release_validation_batch_claim",
        description="Release an active local validation claim so it can be retried.",
    )
    def release_validation_batch_claim(
        self,
        run_id: str,
        agent_id: str,
        batch_id: str,
        reason: str,
    ) -> dict[str, Any]:
        return self._validation_run_service.release_validation_batch_claim(
            run_id=run_id,
            agent_id=agent_id,
            batch_id=batch_id,
            reason=reason,
        ).model_dump(mode="json")

    @tool(
        name="finalize_validation_run",
        description=(
            "Merge validation batch outputs into validation_results.csv, verify "
            "progress, then cleanup local run state and batch outputs."
        ),
    )
    def finalize_validation_run(
        self,
        run_id: str,
        agent_id: str = "validator-aggregator",
    ) -> dict[str, Any]:
        return self._validation_run_service.finalize_validation_run(
            run_id=run_id,
            agent_id=agent_id,
        ).model_dump(mode="json")

    @tool(
        name="verify_validation_progress_log",
        description="Verify the integrity of a validation run progress log.",
    )
    def verify_validation_progress_log(
        self,
        run_id: str,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        return self._validation_run_service.verify_validation_progress_log(
            run_id=run_id,
            agent_id=agent_id,
        ).model_dump(mode="json")

    @tool(
        name="list_validation_runs",
        description="List unfinished validation runs in the local pipeline directory.",
    )
    def list_validation_runs(self) -> dict[str, Any]:
        return self._validation_run_service.list_validation_runs().model_dump(
            mode="json"
        )

    @tool(
        name="evaluate_prompt_refinement_round",
        description=(
            "Compute Fleiss kappa from exactly three independent verdict files, "
            "version the selected generator skill and validator prompt, and log the "
            "calibration round to an explicitly configured MLflow server."
        ),
    )
    def evaluate_prompt_refinement_round(
        self,
        verdicts_dir: Annotated[
            str,
            Field(
                description=(
                    "Directory containing exactly three CSV or Parquet verdict files."
                )
            ),
        ],
        calibration_input: Annotated[
            str,
            Field(
                description=(
                    "Fixed calibration CSV or Parquet used by all three validators."
                )
            ),
        ],
        round_number: Annotated[
            int,
            Field(ge=1, description="One-based refinement round number."),
        ],
        change_summary: Annotated[
            str,
            Field(description="Short description of prompt changes in this round."),
        ],
        tracking_uri: Annotated[
            str,
            Field(description="MLflow tracking and prompt registry URI."),
        ] = app_config.MLFLOW_URL,
        experiment_name: Annotated[
            str,
            Field(description="MLflow experiment used for prompt calibration rounds."),
        ] = app_config.MLFLOW_EXPERIMENT_NAME,
        session_id: Annotated[
            str | None,
            Field(
                default=None,
                description=(
                    "Optional id grouping rounds of one calibration session to view "
                    "kappa trend on the parent calibration-session-* run."
                ),
            ),
        ] = None,
        generator_skill_name: Annotated[
            str,
            Field(
                description=(
                    "Generator skill stem to version for this round. Use generator "
                    "for legacy prompts, generator_plain for ANLI-style translation, "
                    "or generator_adversarial for controlled adversarial generation."
                )
            ),
        ] = "generator",
    ) -> dict[str, Any]:
        return self._prompt_refinement_service.evaluate_round(
            verdicts_dir=verdicts_dir,
            calibration_input=calibration_input,
            round_number=round_number,
            change_summary=change_summary,
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
            session_id=session_id,
            generator_skill_name=generator_skill_name,
        ).model_dump(mode="json")

    @tool(
        name="prepare_prompt_refinement_evidence_pack",
        description=(
            "Build the local evidence pack for editor subagents after a prompt "
            "refinement round returns refine_prompt. This does not spawn agents, "
            "edit prompts, or call MLflow."
        ),
    )
    def prepare_prompt_refinement_evidence_pack(
        self,
        verdicts_dir: Annotated[
            str,
            Field(
                description=(
                    "Directory containing exactly three CSV or Parquet verdict files."
                )
            ),
        ],
        calibration_input: Annotated[
            str,
            Field(description="Calibration CSV or Parquet used by the failed round."),
        ],
        output_root: Annotated[
            str,
            Field(
                description="Prompt refinement output root containing round folders."
            ),
        ],
        round_number: Annotated[
            int,
            Field(ge=1, description="One-based failed refinement round number."),
        ],
        generator_skill_name: Annotated[
            str,
            Field(description="Generator skill stem used by the failed round."),
        ] = "generator",
        bundle_id: Annotated[
            str | None,
            Field(description="Optional bundle id returned by the evaluation round."),
        ] = None,
        mlflow_run_id: Annotated[
            str | None,
            Field(
                description="Optional MLflow run id returned by the evaluation round."
            ),
        ] = None,
        generator_prompt_version: Annotated[
            int | None,
            Field(description="Optional generator prompt version from the round."),
        ] = None,
        validator_prompt_version: Annotated[
            int | None,
            Field(description="Optional validator prompt version from the round."),
        ] = None,
    ) -> dict[str, Any]:
        return self._prompt_refinement_service.prepare_evidence_pack(
            verdicts_dir=verdicts_dir,
            calibration_input=calibration_input,
            output_root=output_root,
            round_number=round_number,
            generator_skill_name=generator_skill_name,
            bundle_id=bundle_id,
            mlflow_run_id=mlflow_run_id,
            generator_prompt_version=generator_prompt_version,
            validator_prompt_version=validator_prompt_version,
        ).model_dump(mode="json")

    @tool(
        name="confirm_prompt_lock",
        description=(
            "Lock the exact prompt bundle of a previously eligible refinement "
            "round by its MLflow run id; does not register new prompt versions."
        ),
    )
    def confirm_prompt_lock(
        self,
        lock_run_id: Annotated[
            str,
            Field(
                description=("MLflow run id of an eligible_to_lock evaluation result.")
            ),
        ],
        tracking_uri: Annotated[
            str,
            Field(description="MLflow tracking and prompt registry URI."),
        ] = app_config.MLFLOW_URL,
    ) -> dict[str, Any]:
        return self._prompt_refinement_service.confirm_prompt_lock(
            lock_run_id=lock_run_id,
            tracking_uri=tracking_uri,
        ).model_dump(mode="json")

    @tool(
        name="run_consensus_pmi",
        description=(
            "Run deterministic consensus aggregation and PMI artifact detection "
            "over exactly three validator verdict files."
        ),
    )
    def run_consensus_pmi(
        self,
        verdicts_dir: Annotated[
            str,
            Field(description="Directory containing exactly three verdict files."),
        ],
        masked_input: Annotated[
            str,
            Field(description="Masked validation dataset path."),
        ],
        expected_input: Annotated[
            str,
            Field(description="Original dataset path with trusted labels."),
        ],
        output_dir: Annotated[
            str | None,
            Field(
                description=(
                    "Output directory for aggregate and PMI artifacts. Defaults to "
                    "data/validated/<expected-input-stem>."
                )
            ),
        ] = None,
        uid_column: Annotated[
            str,
            Field(description="Row identifier column. Default: source_uid."),
        ] = "source_uid",
        label_column: Annotated[
            str,
            Field(
                description="Trusted label column in expected_input. Default: label."
            ),
        ] = "label",
        text_column: Annotated[
            str,
            Field(description="Text column used by PMI. Default: hypothesis."),
        ] = "hypothesis",
        pmi_threshold: Annotated[
            float,
            Field(description="Minimum PMI for a token-label artifact. Default: 1.0."),
        ] = 1.0,
        min_joint_count: Annotated[
            int,
            Field(ge=1, description="Minimum joint token-label count. Default: 3."),
        ] = 3,
    ) -> dict[str, Any]:
        verdicts_path = Path(verdicts_dir).expanduser()
        masked_input_path = Path(masked_input).expanduser()
        expected_input_path = Path(expected_input).expanduser()
        resolved_output_dir = (
            Path(output_dir).expanduser()
            if output_dir
            else default_consensus_output_dir(expected_input_path)
        )
        valid_candidates = self._load_valid_verdict_candidates(verdicts_path)
        resolved_output_dir.mkdir(parents=True, exist_ok=True)
        result = run_consensus_pmi_stage(
            valid_candidates=valid_candidates,
            masked_dataset_path=masked_input_path,
            expected_input_path=expected_input_path,
            output_dir=resolved_output_dir,
            uid_column=uid_column,
            label_column=label_column,
            text_column=text_column,
            pmi_threshold=pmi_threshold,
            min_joint_count=min_joint_count,
        )
        return self._jsonable_paths(result)

    @tool(
        name="promote_paraphrase_revalidation",
        description=(
            "Promote paraphrased rows that pass deterministic semantic "
            "revalidation from exactly three verdict files."
        ),
    )
    def promote_paraphrase_revalidation(
        self,
        input_path: Annotated[
            str,
            Field(description="Paraphrased candidate dataset path."),
        ],
        revalidation_input: Annotated[
            str,
            Field(description="Changed-row revalidation queue path with blank labels."),
        ],
        verdicts_dir: Annotated[
            str,
            Field(description="Directory containing exactly three verdict files."),
        ],
        expected_input: Annotated[
            str,
            Field(description="Trusted label dataset for changed row UIDs."),
        ],
        output_path: Annotated[
            str | None,
            Field(
                description=(
                    "Promoted dataset output path. Defaults to promoted_dataset.csv "
                    "next to input_path."
                )
            ),
        ] = None,
        review_output: Annotated[
            str | None,
            Field(
                description=(
                    "Review output path. Defaults to "
                    "paraphrase_revalidation_review.csv next to output_path."
                )
            ),
        ] = None,
        votes_output: Annotated[
            str | None,
            Field(
                description=(
                    "Vote table output path. Defaults to "
                    "paraphrase_revalidation_votes.csv next to output_path."
                )
            ),
        ] = None,
        uid_column: Annotated[
            str,
            Field(description="Row identifier column. Default: source_uid."),
        ] = "source_uid",
        label_column: Annotated[
            str,
            Field(
                description="Trusted label column in expected_input. Default: label."
            ),
        ] = "label",
    ) -> dict[str, Any]:
        input = Path(input_path).expanduser()
        output = (
            Path(output_path).expanduser()
            if output_path
            else input.with_name("promoted_dataset.csv")
        )
        review = (
            Path(review_output).expanduser()
            if review_output
            else output.with_name("paraphrase_revalidation_review.csv")
        )
        votes = (
            Path(votes_output).expanduser()
            if votes_output
            else output.with_name("paraphrase_revalidation_votes.csv")
        )
        valid_candidates = self._load_valid_verdict_candidates(
            Path(verdicts_dir).expanduser()
        )
        result = run_promote_paraphrase_stage(
            input_path=input,
            revalidation_input_path=Path(revalidation_input).expanduser(),
            verdict_candidates=valid_candidates,
            expected_input_path=Path(expected_input).expanduser(),
            output_path=output,
            review_output_path=review,
            votes_output_path=votes,
            uid_column=uid_column,
            label_column=label_column,
        )
        return self._jsonable_paths(result)

    @staticmethod
    def _load_valid_verdict_candidates(verdicts_dir: Path) -> list[Any]:
        candidates = build_verdict_candidates(discover_verdict_files(verdicts_dir))
        valid_candidates = [candidate for candidate in candidates if candidate.is_valid]
        if len(valid_candidates) != 3:
            raise ValueError(
                f"Need exactly 3 valid verdict files, found {len(valid_candidates)} "
                "(columns: source_uid, predicted_label, reason)."
            )
        return valid_candidates

    @staticmethod
    def _jsonable_paths(result: dict[str, Any]) -> dict[str, Any]:
        return {
            key: str(value) if isinstance(value, Path) else value
            for key, value in result.items()
        }


def register_validation_tools(
    mcp: FastMCP,
    pipeline_dir: Path | None = None,
) -> ValidationToolProvider:
    validation_run_service = ValidationRunService(
        dataset_reader_service=DatasetReaderService(),
        progress_tracking_service=ProgressTrackingService(
            pipeline_dir=pipeline_dir or Path(".pipeline/validation")
        ),
    )
    provider = ValidationToolProvider(
        validation_run_service=validation_run_service,
        prompt_refinement_service=PromptRefinementService(),
    )
    provider.register(mcp)
    return provider
