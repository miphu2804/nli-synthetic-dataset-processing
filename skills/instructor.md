# NLI Synthetic Data - Instructor

Read this resource first when processing NLI synthetic data.

## Task Overview

Natural Language Inference (NLI) compares a `premise` and a `hypothesis`:

| Label | Meaning |
|-------|---------|
| `entailment` | The premise supports the hypothesis |
| `contradiction` | The hypothesis conflicts with the premise |
| `neutral` | The hypothesis is neither supported nor contradicted |

This pipeline starts from pre-labeled English NLI pairs. Translate both texts to
natural Vietnamese, apply one label-compatible adversarial transformation and
preserve the original label.

Output schema:

```csv
source_uid,premise,hypothesis,label
```

## Runtime Model

| Owner | Responsibility |
|-------|----------------|
| Main agent | Load resources, call MCP tools, assign work and submit results |
| Subagent | Transform one claimed batch and return JSON only |
| MCP runtime | Claim batches, append progress, merge output and cleanup |

## Resource Map

Load only the resources needed by the current phase:

| Resource | When to read |
|----------|--------------|
| `skill://execution` | Before processing. Understand runtime boundaries. |
| `skill://progress_tracking` | Before starting or resuming a local run. |
| `skill://generator` | Before generating rows. Learn transformation rules and self-checks. |
| `skill://delegation` | When processing at least 100 assigned rows with subagents. |
| `skill://aggregator` | Before finalizing a completed local run. |

## Generation Phase

```text
load execution
  -> load progress_tracking
  -> load generator
  -> start_generation_run
  -> calculate_dispatch_plan
  -> claim_next_batch
  -> transform directly or load delegation and dispatch subagents
  -> self-check generated rows
  -> submit_batch_result
  -> refill free slots until claim_next_batch returns complete
  -> load aggregator
  -> finalize_generation_run
```

## Validation Phase

After generation is finalized, run offline validation:

```text
1. Mask labels    → uv run python -m src.utils.validation_masking_cli
2. Agent validate → each model reads skill://validator and writes source_uid,predicted_label,reason
3. Finalize       → trusted runtime writes one validation_results.csv with expected/predicted labels
4. Analyze PMI    → uv run python -m src.utils.validation_aggregation_cli
```

Read `skill://validator` for the scoring rubric and verdict contract that each validator agent must follow.
Refer to `docs/validation-flow.md` for the full multi-model consensus and PMI flow.

## Guardrails

- Preserve each source label.
- Do not generate text with Python templates.
- Do not manually edit `.pipeline/runs/{run_id}/progress.jsonl`.
- Do not let subagents call MCP tools or mutate runtime state.
