# Project Overview

This project exposes a local MCP runtime for two main phases:

- **Generator:** create Vietnamese NLI rows from a labeled source slice. Use
  `skill://generator_plain` for ANLI-derived rows that already contain an
  adversarial relation, or `skill://generator_adversarial` when creating a new
  controlled adversarial variant.
- **Validator:** validate generated rows with blank labels and trusted runtime
  comparison against the hidden source label.

## Architecture

```text
Codex harness
  -> reads MCP resources
  -> uses from_sample/to_sample ranges
  -> calls MCP tools sequentially
  -> receives final data outputs
```

MCP server:

```text
nli-data-processing-mcp-server
  Generation:
    start_generation_run
    claim_next_batch
    submit_batch_result
    verify_progress_log
    finalize_generation_run

  Validation:
    start_validation_run
    claim_next_validation_batch
    submit_validation_result
    verify_validation_progress_log
    finalize_validation_run
```

## Ownership

| Owner | Responsibility |
|-------|----------------|
| User | Assigns `from_sample` and `to_sample` ranges |
| Codex harness | Reads resources, calls MCP tools, self-checks generated rows |
| Subagent | Transforms already-claimed generation rows and returns JSON only |
| MCP runtime | Claims batches, writes progress, writes batch CSVs, merges, verifies, and cleans up |

## Sample Ranges

Public MCP start tools use one-based inclusive sample ranges:

```text
from_sample=1, to_sample=20  -> samples 1 through 20
from_sample=21, to_sample=40 -> samples 21 through 40
```

Internally the services still store zero-based `row_offset` and `row_limit` in
the run manifest and responses. Harness prompts should use `from_sample` and
`to_sample`.

## Runtime State

Runtime state is local and resumable while a run is active.

```text
.pipeline/runs/{run_id}/manifest.json
.pipeline/runs/{run_id}/progress.jsonl
.pipeline/validation/runs/{run_id}/manifest.json
.pipeline/validation/runs/{run_id}/progress.jsonl
data/batches/{run_id}/
```

Batch CSVs are runtime artifacts, not final outputs. Successful finalization
merges the batch files, checks progress consistency and row counts, then deletes
both the run state and `data/batches/{run_id}`. Failed verification keeps those
artifacts for debugging.
