# Template điều phối Prompt Refinement

Dùng prompt này khi Codex đã kết nối MCP server `nli-tools`.

```text
Bạn là main agent đang kết nối MCP server `nli-tools`.

Mục tiêu:
Chạy một calibration prompt refinement cho generator policy và validator rubric đã chọn.

Input:
- calibration_source: <FIXED_LABELED_DATASET_OR_SLICE>
- sample_count: <N>
- generator_skill_name: <generator_plain_OR_generator_adversarial_OR_generator>
- output_root: data/prompt-refinement/<SESSION_ID_OR_DATASET_ID>
- validator_models: <THREE_REAL_INDEPENDENT_MODEL_IDENTIFIERS>

Skills cần load từ skill lookup của `nli-tools` đang connect:
- instructor
- prompt_refinement
- validator
- <generator_skill_name>

Task:
1. Chỉ đọc skills bắt buộc và calibration_source đã được cung cấp.
2. Giữ cố định source_uid set đã chọn cho calibration này.
3. Tạo output_root/calibration/calibration.csv với:
   source_uid,premise,hypothesis,label
4. Chỉ đưa cho validator masked rows:
   source_uid,premise,hypothesis
5. Chạy đúng ba validator model/subagent độc lập.
   Nếu không có ba model độc lập, dừng và báo blocker.
6. Lưu one verdict file cho mỗi model tại:
   output_root/calibration/verdicts/<model-id>.csv

Verdict schema:
source_uid,predicted_label,reason

Reject verdict nếu thiếu UID, trùng UID, label không hợp lệ, reason rỗng, hoặc
không đủ UID coverage. Chỉ retry model lỗi một lần.

Sau đó gọi:
evaluate_prompt_refinement(
  verdicts_dir="output_root/calibration/verdicts",
  calibration_input="output_root/calibration/calibration.csv",
  generator_skill_name="<GENERATOR_SKILL_NAME>"
)

Xử lý decision:
1. Nếu decision=accepted, dừng và report kết quả calibration.
2. Nếu decision=needs_prompt_update, dừng automatic execution. Inspect
   disagreement_rows.csv đã log, prompt snapshots, verdict files, và calibration
   rows.
3. Report rejected sample count, disagreement evidence, và next step nhỏ nhất có
   evidence để user duyệt. Không sửa prompt nếu user chưa approve follow-up đó.

Rules:
- Không đọc hidden labels ngoài bước chuẩn bị calibration_source.
- Validator subagents phải luôn blind. Không lộ label, expected label values,
  hoặc peer verdict cho họ.
- Validator subagents do not call MCP tools hoặc ghi runtime state.
- Không inspect các file repo không liên quan.
- Không sửa generator hoặc validator instructions trong lúc calibration đang chạy.
- Không dùng PMI trong loop này.
- Không yêu cầu backend propose prompt edits; main agent sở hữu evidence review
  và recommendation cho user.
- Không register prompt versions, promote aliases, hoặc lock prompts.
- Nếu thiếu required skills, tools, hoặc ba validator execution độc lập, báo
  blocker.

Report:
- verdict file paths
- kappa và decision
- rejected sample count
- disagreement_rows.csv
- next step hoặc blocker do agent đề xuất
- bundle ID
- MLflow run ID
- blockers hoặc câu hỏi còn mở
```
