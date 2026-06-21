# Fix 04 — Deterministic Stage MCP Wrappers

Proposed branch: `fix/deterministic-stage-mcp-wrappers`

Status: implemented on `fix/deterministic-stage-mcp-wrappers`.

## Problem

The validation runtime exposes MCP tools for per-run validation and prompt
refinement, but deterministic offline stages are still CLI-only. The docs state
that aggregate, PMI, and apply-paraphrase are operator-run, and the monitor run
confirmed no MCP wrappers for these CLI stages.

This is not the first fix to implement. MCP exposure should come after the
operator-facing CLI contract is complete for revalidation and promotion,
otherwise the MCP surface would encode an incomplete workflow.

## Verified Evidence

- `backend/src/providers/validation_provider.py` exposes validation-run tools,
  `evaluate_prompt_refinement_round`, and `confirm_prompt_lock`.
- `backend/src/cli.py` exposes `mask`, `aggregate`, `pmi`, `kappa`, and
  `apply-paraphrase`.
- `docs/vi/flow/validator.md` says deterministic `aggregate`, `pmi`, and
  `apply-paraphrase` stages are still run manually by the operator.
- Prior validation memory notes explicitly warn against exposing MCP wrappers
  before revalidation and promotion are closed.

## Scope

- Add thin MCP wrappers only around stable deterministic functions.
- Keep wrappers as transport adapters: validate arguments, call existing service
  or utility code, return structured paths and counts.
- Preserve CLI behavior.
- Add provider tests proving tool registration and no `self` leakage.

## Dependencies

- Complete `fix/paraphrase-revalidation-promotion` first.
- Decide the canonical artifact output paths from
  `fix/persist-consensus-pmi-artifacts`.

## Out Of Scope

- Do not put model calls inside MCP wrappers.
- Do not let MCP tools infer hidden labels from masked files alone.
- Do not add abstraction layers beyond the existing provider/service pattern.

## Acceptance Criteria

- MCP has wrappers for the stable deterministic stages only.
- Each wrapper returns row counts and output paths.
- Existing CLI tests still pass.
- Provider tests verify the tools are registered and schema exposes explicit
  inputs.

## Implemented Fix

- Added `run_consensus_pmi` MCP wrapper over the existing deterministic
  aggregate + PMI contract.
- Added `promote_paraphrase_revalidation` MCP wrapper over the existing
  paraphrase promotion contract.
- Kept `aggregate`, `pmi`, and `apply-paraphrase` as CLI/operator stages.
- Added provider tests for schema exposure and runtime artifact writes.

## Verification

```bash
cd backend
uv run pytest -q
uv run python - <<'PY'
import asyncio
from fastmcp import FastMCP
from src.providers import register_validation_tools

async def main():
    mcp = FastMCP("check")
    register_validation_tools(mcp)
    tools = sorted((await mcp.get_tools()).keys())
    print("\n".join(tools))

asyncio.run(main())
PY
```
