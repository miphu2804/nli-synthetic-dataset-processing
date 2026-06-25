# Validator Prompt Template

Use this prompt when the Codex harness is already connected to MCP server
`nli-tools`.

```text
You are connected to MCP server `nli-tools`.

Available MCP resources:
- skill://instructor
- skill://execution
- skill://progress_tracking
- skill://validator

Available validation tools:
- start_validation_run
- claim_next_validation_batch
- submit_validation_result
- get_validation_progress
- release_validation_batch_claim
- verify_validation_progress_log
- finalize_validation_run
- list_validation_runs

Goal:
Validate generated Vietnamese NLI rows through blanked labels:
- input_path: <GENERATED_CSV_WITH_HIDDEN_LABELS>
- output_dir: data/validated/<RUN_OR_MODEL_ID>
- from_sample: <ONE_BASED_FIRST_SAMPLE>
- to_sample: <ONE_BASED_LAST_SAMPLE_INCLUSIVE>
- batch_size: 20

Flow:
1. Read MCP resources in this order:
   - skill://instructor
   - skill://execution
   - skill://progress_tracking
   - skill://validator
2. Call start_validation_run with from_sample and to_sample.
3. Loop:
   - claim_next_validation_batch
   - assign predicted_label from premise and hypothesis only
   - submit_validation_result with one verdict per claimed source_uid
   - continue until claim_next_validation_batch returns complete
4. Call verify_validation_progress_log.
5. Call finalize_validation_run.
6. Report run_id, output_path, total_rows, accepted_rows, rejected_rows, and
   unresolved issues.

Rules:
- Use MCP resource reads for the listed `skill://...` resources before calling
  validation tools.
- Claimed rows expose only source_uid, premise, hypothesis, and `label=""`.
- Do not read or infer hidden labels from the original file, metadata, row order,
  batch id, or prior outputs.
- Return exactly one canonical name: entailment, neutral, or contradiction.
- Finalize writes validation_results.csv and cleans both .pipeline run state and
  data/batches/{run_id} after successful verification.
```
