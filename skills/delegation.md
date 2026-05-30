# Delegation — Stateless Subagent Handoff

Split batch processing across subagents to keep the main agent's context clean. Subagents are pure functions: receive input, return output, get destroyed. No shared state, no context accumulation.

**MCP access**: `skill://delegation` — load via `get_skill("delegation")`.

**MANDATORY: Use parallel execution by default.** Do NOT run subagents one-at-a-time unless the user explicitly asks for sequential mode. Spawn all subagents for a batch group in a single message — each gets different rows, zero conflict.

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

## How to Execute (MANDATORY — parallel by default)

**Spawn ALL subagents in ONE message.** Each gets different rows — zero conflict.

```
Main agent (ONE message with N Agent tool calls)
  ├─ Subagent A: batch rows 1-5    ─┐
  ├─ Subagent B: batch rows 6-10   ─┤ ALL run simultaneously
  ├─ Subagent C: batch rows 11-15  ─┤
  ├─ Subagent D: batch rows 16-20  ─┤
  └─ Subagent E: batch rows 21-25  ─┘

  Wait for all to finish → validate each output → write CSVs → update progress.jsonl
```

**Why this is safe:**
- Each subagent gets different rows → no overlap
- Each writes to different part file (part1.csv, part2.csv, ...)
- Main agent appends to progress.jsonl ONLY after all subagents done

**Number of subagents per wave:**
- First wave: 3 subagents (test quality)
- If output OK → scale to 5+ subagents per wave
- Cap at 10 per wave (rate limit safety)

**Sequential mode** only if user explicitly says "run one at a time" or first wave shows quality issues needing per-batch inspection.

## Post-Subagent Validation

Main agent checks each subagent output before writing:

```
1. grep for English words in premise + hypothesis → none allowed
2. label == original label for every row → else discard row
3. rule + tier are valid values (not hallucinated)
4. hypothesis != original hypothesis (transformation actually applied)
```

Fail 2+ rows in a batch → re-spawn subagent with same batch, different wording.

## Multi-Agent Collaboration (shared progress.jsonl)

When multiple agents work on the same dataset, `progress.jsonl` lives in a shared location (git repo, shared drive). Agents coordinate via the log — no lock server, no database.

### Workflow

```
1. Read progress.jsonl → see what's claimed, what's done
2. Claim next available rows:
   echo '{"id":"alice-3","event":"claim","agent":"alice","rows":"51-100",...}' >> progress.jsonl
3. Sync claim (git push / save to shared drive)
4. Process rows 51-100
5. Append row.done events, sync again
```

### Conflict: two agents claim same rows

Rule: **earlier timestamp wins.** Loser unclaims and picks new rows.

```bash
# Check if someone else claimed my rows
grep '"rows":"51-100"' progress.jsonl | grep -v '"agent":"alice"'

# If conflict and I lost → unclaim
echo '{"id":"alice-99","event":"unclaim","agent":"alice","rows":"51-100","reason":"conflict"}' >> progress.jsonl
```

### Per-agent files

Each agent writes to its own CSV: `alice_part1.csv`, `bob_part1.csv`. No file conflict. Merge all at the end.

## Model Selection

| Agent | Model | Why |
|-------|-------|-----|
| Main | Largest available | Orchestration, tracking, validation |
| Subagent | Smallest available | Cheap, fast, stateless — context destroyed after each batch |

Use whatever subagent mechanism your harness provides. No hardcoded model names — pick the cheapest capable model you have access to.
