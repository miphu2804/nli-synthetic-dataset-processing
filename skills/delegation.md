# Delegation — Stateless Subagent Handoff

Split batch processing across subagents to keep the main agent's context clean. Subagents are pure functions: receive input, return output, get destroyed. No shared state, no context accumulation.

## Architecture

```
Main agent (orchestrator)          Subagent (worker)
───────────────────────────        ──────────────────
Track progress (progress.jsonl)    Transform one batch
Assign rules + tiers               No access to log
Spawn subagents                    No awareness of other batches
Validate output                    No awareness of previous runs
Write CSV + update log             Pure function
```

## Responsibility Split

| | Main agent | Subagent |
|---|---|---|
| Read dataset | Yes | No |
| Read/write `progress.jsonl` | Yes | No |
| Assign rules + tiers per row | Yes | No |
| Translate to Vietnamese | — | Yes |
| Apply adversarial transform | — | Yes |
| Validate transformation | Yes (post-check) | Yes (self-check) |
| Write CSV | Yes | No |
| Merge part files | Yes | No |

## Subagent Prompt Template

Main agent builds this per batch. The prompt is **self-contained** — subagent needs nothing else.

```
You are an NLI adversarial data transformer.

## Transformation rules
[main agent copies the 19 rule tables from generator skill here:
 - Entailment rules (9)
 - Contradiction rules (5)
 - Neutral rules (5)]

## Anti-artifact constraints
[main agent copies the cue-word table from generator skill]

## Batch to process
Input rows (JSON array). Each row has:
- source_uid: original row id
- premise: original premise text
- hypothesis: original hypothesis text
- label: entailment / neutral / contradiction (DO NOT CHANGE)
- rule: the transformation rule to apply
- tier: surface / structural / deep_semantic

{json_batch_data}

## Instructions
1. Translate BOTH premise AND hypothesis to Vietnamese. No English left behind.
2. Apply the assigned rule to transform the hypothesis.
3. The original label MUST be preserved.
4. For each row, write a short reason explaining what was changed.
5. Return a JSON array:

[
  {
    "source_uid": "...",
    "premise": "... (Vietnamese)",
    "hypothesis": "... (Vietnamese, transformed)",
    "label": "... (unchanged)",
    "rule": "...",
    "tier": "...",
    "reason": "..."
  },
  ...
]
```

## Parallel Execution

If the harness supports spawning multiple subagents:

```
Main agent
  ├─ Subagent A: batch rows 1-5    ─┐
  ├─ Subagent B: batch rows 6-10   ─┤ run simultaneously
  └─ Subagent C: batch rows 11-15  ─┘

  Wait all → validate → write → done
```

Each subagent gets different rows → no conflict. No locking needed because:
- Each writes to different part file (part1.csv, part2.csv, ...)
- Each batch has unique rows
- Progress log append is serial (main agent does it after all done)

## Sequential vs Parallel

| Mode | When to use | Benefit |
|------|------------|---------|
| Sequential | Small batches, 1-at-a-time | Simple, easier to debug |
| Parallel (2-3 agents) | Medium dataset, testing | 2-3x faster |
| Parallel (5+ agents) | Large dataset, production | Max speed, watch rate limits |

Start sequential to verify quality, then scale to parallel.

## Post-Subagent Validation

Main agent checks each subagent output before writing:

```
1. grep for English words in premise + hypothesis → none allowed
2. label == original label for every row → else discard row
3. rule + tier are valid values (not hallucinated)
4. hypothesis != original hypothesis (transformation actually applied)
```

Fail 2+ rows in a batch → re-spawn subagent with same batch, different wording.

## Model Selection

| Agent | Model | Why |
|-------|-------|-----|
| Main | Pro / largest | Orchestration, tracking, validation |
| Subagent | Flash / smallest | Cheap, fast, stateless — context destroyed after each batch |

Configuration example (Claude Code):
```
CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash
ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-v4-pro[1m]
```
