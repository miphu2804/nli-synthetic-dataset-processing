# Validator Flow

The validator phase checks generated Vietnamese NLI rows with labels masked from
the validator. The trusted runtime keeps the hidden label internally and computes
whether each submitted verdict matches it.

## State Machine

```text
START
  -> read skill://instructor
  -> read skill://execution
  -> read skill://progress_tracking
  -> read skill://validator
  -> start_validation_run(from_sample, to_sample)
       creates .pipeline/validation/runs/{run_id}
       creates data/batches/{run_id}
  -> claim_next_validation_batch
       returns source_uid, premise, hypothesis, masked_label
  -> predict labels without reading hidden labels
  -> submit_validation_result
       writes trusted accepted/rejected comparison to batch CSV
  -> claim_next_validation_batch
       claimed  -> repeat predict and submit
       waiting  -> inspect active claims or release abandoned claim
       complete -> verify_validation_progress_log
  -> finalize_validation_run
       success -> validation_results.csv exists
               -> .pipeline/validation/runs/{run_id} removed
               -> data/batches/{run_id} removed
       failure -> runtime artifacts remain for debugging
```

## Claimed Row Schema

```csv
source_uid,premise,hypothesis,masked_label
```

## Verdict Schema

```csv
source_uid,predicted_label,reason
```

## Final Output Schema

```csv
source_uid,premise,hypothesis,expected_label,predicted_label,accepted,reason
```

## Notes

- Use only `premise`, `hypothesis`, and the label rubric.
- Do not infer hidden labels from row order, metadata, batch id, or prior outputs.
- If labels are numeric in the run, return the exact numeric label id.
