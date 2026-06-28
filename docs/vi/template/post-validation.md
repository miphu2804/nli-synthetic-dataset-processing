# Template Post-Validation Pipeline

Dùng prompt này khi Codex đã kết nối MCP server `nli-tools` và đã có đúng ba
file verdict độc lập cho cùng một generated dataset.

```text
Bạn là main agent đang kết nối MCP server `nli-tools`.

Mục tiêu:
Chạy cleanup sau three-model validation:
consensus + PMI -> optional paraphrase -> revalidation promotion -> final split.

Input:
- verdicts_dir: <DIR_WITH_EXACTLY_THREE_VALIDATION_VERDICT_FILES>
- masked_input: <MASKED_VALIDATION_DATASET_USED_BY_VALIDATORS>
- expected_input: <ORIGINAL_GENERATED_DATASET_WITH_TRUSTED_LABELS>
- output_dir: data/validated/<RUN_OR_DATASET_ID>
- split_output_dir: data/splits/<RUN_OR_DATASET_ID>
- pmi_threshold: 1.0
- min_joint_count: 3
- split_seed: 13
- split_ratios: train=0.8, dev=0.1, test=0.1
- split_domain_column: <OPTIONAL_DOMAIN_OR_SUBDOMAIN_COLUMN>

MCP resources bắt buộc:
- skill://instructor
- skill://validator

Task:
1. Chỉ đọc các MCP resources bắt buộc.
2. Gọi run_consensus_pmi với:
   verdicts_dir, masked_input, expected_input, output_dir,
   uid_column="source_uid", label_column="label", text_column="hypothesis",
   pmi_threshold=<PMI_THRESHOLD>, min_joint_count=<MIN_JOINT_COUNT>.
3. Inspect output_dir/pmi_flagged_rows.csv.
4. Nếu pmi_flagged_rows.csv không có data rows:
   - Set final_dataset = output_dir/validated_dataset.csv.
   - Skip paraphrase và revalidation.
5. Nếu pmi_flagged_rows.csv có data rows:
   - Rewrite only flagged hypotheses.
   - Ghi output_dir/paraphrases.csv với đúng schema:
     source_uid,hypothesis
   - Tập source_uid phải khớp chính xác pmi_flagged_rows.csv.
   - Không rewrite premise hoặc label.
   - Không thêm, bỏ, hoặc tự suy row.
   - Chạy:
     python -m src.cli apply-paraphrase
       --input output_dir/validated_dataset.csv
       --flagged-rows output_dir/pmi_flagged_rows.csv
       --paraphrases output_dir/paraphrases.csv
       --output output_dir/paraphrased_dataset.csv
   - Lệnh này tạo output_dir/paraphrase_revalidation_masked.csv.
   - Dispatch đúng ba validator subagents độc lập trên
     output_dir/paraphrase_revalidation_masked.csv.
   - Chỉ đưa mỗi subagent:
     source_uid,premise,hypothesis
   - Không gọi start_validation_run trên paraphrase_revalidation_masked.csv vì
     label column của file này intentionally blank.
   - Lưu một revalidation verdict file cho mỗi model tại:
     output_dir/revalidation_verdicts/<model-id>.csv
     với schema:
     source_uid,predicted_label,reason
   - Gọi promote_paraphrase_revalidation với:
     input_path=output_dir/paraphrased_dataset.csv,
     revalidation_input=output_dir/paraphrase_revalidation_masked.csv,
     verdicts_dir=output_dir/revalidation_verdicts,
     expected_input=output_dir/validated_dataset.csv.
   - Set final_dataset thành path promoted_dataset.csv do tool trả về.
6. Chạy final split:
   python -m src.cli split
     --input <final_dataset>
     --output-dir data/splits/<RUN_OR_DATASET_ID>
     --group-column premise
     --label-column label
     --train-ratio 0.8
     --dev-ratio 0.1
     --test-ratio 0.1
     --seed 13
     [--domain-column <OPTIONAL_DOMAIN_OR_SUBDOMAIN_COLUMN>]
7. Report toàn bộ output paths và các row còn cần manual review nếu có.

Rules:
- run_consensus_pmi và promote_paraphrase_revalidation là deterministic MCP
  tools. Không override decision của chúng bằng tay.
- PMI quyết định row nào suspicious. Không để AI thêm row ngoài PMI queue vào
  paraphrase queue.
- AI chỉ được rewrite flagged hypotheses và phải cố giữ nguyên NLI relation.
- Revalidation gate quyết định rewritten rows có được promote không.
- Split chỉ chạy trên publishable final dataset: promoted_dataset.csv nếu đã
  chạy paraphrase promotion, nếu không thì validated_dataset.csv.
- Final split mặc định là grouped-stratified và vẫn phải giữ mỗi premise group
  nằm trọn trong đúng một split.
- PMI không phải prompt refinement. Không sửa generator hoặc validator prompts ở
  bước này.
- Nếu deterministic stage fail, dừng và báo blocker thay vì tự patch output.

Report:
- consensus/PMI output directory
- validated_dataset.csv
- review_dataset.csv
- pmi_artifact_tokens.csv
- pmi_flagged_rows.csv và flagged row count
- paraphrases.csv nếu có tạo
- paraphrased_dataset.csv nếu có tạo
- paraphrase_revalidation_masked.csv nếu có tạo
- revalidation verdict files nếu có tạo
- promoted_dataset.csv nếu có tạo
- paraphrase_revalidation_review.csv nếu có tạo
- final dataset dùng để split
- train.csv, dev.csv, test.csv, split_manifest.json
- split strategy và domain-column status nếu có yêu cầu domain column
- blockers hoặc unresolved manual review rows
```
