# Post-Validation Pipeline Template

Use this prompt when Codex is connected to MCP server `nli-tools` and three
independent validation verdict files already exist for the same generated
dataset.

```text
You are the main agent connected to MCP server `nli-tools`.

Goal:
Run post-validation cleanup after three-model validation:
consensus + PMI -> optional paraphrase -> revalidation promotion -> final split.

Inputs:
- verdicts_dir: <DIR_WITH_EXACTLY_THREE_VALIDATION_VERDICT_FILES>
- masked_input: <MASKED_VALIDATION_DATASET_USED_BY_VALIDATORS>
- expected_input: <ORIGINAL_GENERATED_DATASET_WITH_TRUSTED_LABELS>
- output_dir: data/validated/<RUN_OR_DATASET_ID>
- split_output_dir: data/splits/<RUN_OR_DATASET_ID>
- pmi_threshold: 1.0
- min_joint_count: 3
- split_seed: 13
- split_ratios: train=0.8, dev=0.1, test=0.1

Required MCP resources:
- skill://instructor
- skill://validator

Task:
1. Read only the required MCP resources.
2. Call run_consensus_pmi with:
   verdicts_dir, masked_input, expected_input, output_dir,
   uid_column="source_uid", label_column="label", text_column="hypothesis",
   pmi_threshold=<PMI_THRESHOLD>, min_joint_count=<MIN_JOINT_COUNT>.
3. Inspect output_dir/pmi_flagged_rows.csv.
4. If pmi_flagged_rows.csv has no data rows:
   - Set final_dataset = output_dir/validated_dataset.csv.
   - Skip paraphrase and revalidation.
5. If pmi_flagged_rows.csv has data rows:
   - Rewrite only the flagged hypotheses.
   - Write output_dir/paraphrases.csv with exactly:
     source_uid,hypothesis
   - Include exactly the source_uid set from pmi_flagged_rows.csv.
   - Do not rewrite premise or label.
   - Do not add, drop, or infer rows.
   - Run:
     python -m src.cli apply-paraphrase
       --input output_dir/validated_dataset.csv
       --flagged-rows output_dir/pmi_flagged_rows.csv
       --paraphrases output_dir/paraphrases.csv
       --output output_dir/paraphrased_dataset.csv
       --uid-column source_uid
       --text-column hypothesis
   - This creates output_dir/paraphrase_revalidation_masked.csv.
   - Dispatch exactly three independent validator subagents on
     output_dir/paraphrase_revalidation_masked.csv.
   - Give each subagent only:
     source_uid,premise,hypothesis
   - Do not call start_validation_run on paraphrase_revalidation_masked.csv
     because its label column is intentionally blank.
   - Save one revalidation verdict file per model under:
     output_dir/revalidation_verdicts/<model-id>.csv
     with schema:
     source_uid,predicted_label,reason
   - Call promote_paraphrase_revalidation with:
     input_path=output_dir/paraphrased_dataset.csv,
     revalidation_input=output_dir/paraphrase_revalidation_masked.csv,
     verdicts_dir=output_dir/revalidation_verdicts,
     expected_input=output_dir/validated_dataset.csv.
   - Set final_dataset to the promoted_dataset.csv path returned by the tool.
6. Run final split:
   python -m src.cli split
     --input <final_dataset>
     --output-dir data/splits/<RUN_OR_DATASET_ID>
     --group-column premise
     --label-column label
     --train-ratio 0.8
     --dev-ratio 0.1
     --test-ratio 0.1
     --seed 13
7. Report all output paths and any rows left for manual review.

Rules:
- run_consensus_pmi and promote_paraphrase_revalidation are deterministic MCP
  tools. Do not override their decisions manually.
- PMI decides which rows are suspicious. Do not let AI add extra rows to the
  paraphrase queue.
- AI may rewrite only flagged hypotheses and must preserve the NLI relation as
  much as possible.
- Revalidation gates rewritten rows before promotion.
- Split only the publishable final dataset: promoted_dataset.csv if paraphrase
  promotion ran, otherwise validated_dataset.csv.
- PMI is not prompt refinement. Do not edit generator or validator prompts here.
- If a deterministic stage fails, stop and report the blocker instead of
  patching outputs by hand.

Report:
- consensus/PMI output directory
- validated_dataset.csv
- review_dataset.csv
- pmi_artifact_tokens.csv
- pmi_flagged_rows.csv and flagged row count
- paraphrases.csv if created
- paraphrased_dataset.csv if created
- paraphrase_revalidation_masked.csv if created
- revalidation verdict files if created
- promoted_dataset.csv if created
- paraphrase_revalidation_review.csv if created
- final dataset used for split
- train.csv, dev.csv, test.csv, split_manifest.json
- blockers or unresolved manual review rows
```
