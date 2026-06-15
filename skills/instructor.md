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

## Tool Map

Generation tools:

```text
start_generation_run
calculate_dispatch_plan
claim_next_batch
submit_batch_result
get_run_progress
release_batch_claim
verify_progress_log
finalize_generation_run
list_generation_runs
```

Validation tools:

```text
start_validation_run
claim_next_validation_batch
submit_validation_result
get_validation_progress
release_validation_batch_claim
verify_validation_progress_log
finalize_validation_run
list_validation_runs
```

## Resource Map

Load only the resources needed by the current phase:

| Resource | When to read |
|----------|--------------|
| `skill://execution` | Before processing. Understand runtime boundaries. |
| `skill://progress_tracking` | Before starting or resuming a local run. |
| `skill://generator` | Before generating rows. Learn transformation rules and self-checks. |
| `skill://delegation` | When processing at least 100 assigned rows with subagents. |
| `skill://aggregator` | Before finalizing a completed local run. |
| `skill://validator` | Before validating generated rows with masked labels. |

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

After generation is finalized, run MCP validation:

```text
load execution
  -> load progress_tracking
  -> load validator
  -> start_validation_run
  -> claim_next_validation_batch
  -> assign predicted_label from premise and hypothesis only
  -> submit_validation_result
  -> repeat until claim_next_validation_batch returns complete
  -> verify_validation_progress_log
  -> finalize_validation_run
```

The validation runtime masks labels before returning claimed rows. Validators
must not read the original labeled file directly after the run starts.

## Guardrails

- Preserve each source label.
- Do not generate text with Python templates.
- Do not manually edit `.pipeline/runs/{run_id}/progress.jsonl`.
- Do not let subagents call MCP tools or mutate runtime state.
