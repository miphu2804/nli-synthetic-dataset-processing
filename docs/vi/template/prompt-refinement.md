# Template điều phối Prompt Refinement

Dùng prompt này khi Codex đã kết nối MCP server `nli-tools` và operator đã tự
khởi động các service cần thiết.

```text
Bạn là main agent đang kết nối MCP server `nli-tools`.

Mục tiêu:
Chạy một round prompt refinement cho generator policy và validator rubric đã chọn.

Input:
- calibration_source: <FIXED_LABELED_DATASET_OR_SLICE>
- sample_count: <N>
- generator_skill_name: <generator_plain_OR_generator_adversarial_OR_generator>
- output_root: data/prompt-refinement/<SESSION_ID_OR_DATASET_ID>
- tracking_uri: <MLFLOW_TRACKING_URI>
- experiment_name: <MLFLOW_EXPERIMENT_NAME>
- round_number: <N>
- validator_models: <THREE_REAL_INDEPENDENT_MODEL_IDENTIFIERS>

MCP resources bắt buộc:
- skill://instructor
- skill://prompt_refinement
- skill://validator
- skill://<generator_skill_name>

Task:
1. Chỉ đọc MCP resources bắt buộc và calibration_source đã được cung cấp.
2. Giữ cố định source_uid set đã chọn cho chuỗi round cần so sánh.
3. Tạo output_root/round-<NN>/calibration.csv với:
   source_uid,premise,hypothesis,label
4. Chỉ đưa cho validator masked rows:
   source_uid,premise,hypothesis
5. Chạy đúng ba validator model/subagent độc lập.
   Nếu không có ba model độc lập, dừng và báo blocker.
6. Lưu one verdict file cho mỗi model tại:
   output_root/round-<NN>/verdicts/<model-id>.csv

Verdict schema:
source_uid,predicted_label,reason

Reject verdict nếu thiếu UID, trùng UID, label không hợp lệ, reason rỗng, hoặc
không đủ UID coverage. Chỉ retry model lỗi một lần.

Sau đó gọi:
evaluate_prompt_refinement_round(
  verdicts_dir="output_root/round-<NN>/verdicts",
  calibration_input="output_root/round-<NN>/calibration.csv",
  round_number=<NN>,
  change_summary="<PROMPT_CHANGES_TESTED_THIS_ROUND>",
  tracking_uri="<MLFLOW_TRACKING_URI>",
  experiment_name="<MLFLOW_EXPERIMENT_NAME>",
  generator_skill_name="<GENERATOR_SKILL_NAME>"
)

Xử lý decision:
1. Nếu decision=accepted, dừng và report kết quả round.
2. Nếu decision=needs_prompt_update, dừng và report proposal artifact:
   prompt_augment_proposal.json
3. Kèm disagreement_rows.csv trong cùng MLflow run để user tự quyết định prompt
   nào cần update thủ công.

Rules:
- Không đọc hidden labels ngoài bước chuẩn bị calibration_source.
- Validator subagents phải luôn blind. Không lộ label, expected label values,
  hoặc peer verdict cho họ.
- Validator subagents do not call MCP tools hoặc ghi runtime state.
- Không inspect các file repo không liên quan.
- Không sửa generator hoặc validator instructions trong lúc round đang chạy.
- Không dùng PMI trong loop này.
- Không register prompt versions, promote aliases, hoặc lock prompts.
- Nếu MCP hoặc MLflow unavailable, báo blocker; không tự start services.

Report:
- verdict file paths
- kappa và decision
- prompt_augment_proposal.json nếu có
- disagreement_rows.csv
- bundle ID
- MLflow run ID
- blockers hoặc câu hỏi còn mở
```
