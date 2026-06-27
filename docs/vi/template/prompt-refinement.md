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
- session_id: <OPTIONAL_SESSION_ID>
- round_number: <N>
- validator_models: <THREE_REAL_INDEPENDENT_MODEL_IDENTIFIERS>
- max_rounds: <N>

MCP resources bắt buộc:
- skill://instructor
- skill://prompt_refinement
- skill://validator
- skill://<generator_skill_name>

Task:
1. Chỉ đọc các MCP resources bắt buộc và calibration_source đã được cung cấp.
2. Giữ cố định tập source_uid đã chọn cho session này.
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
  session_id="<OPTIONAL_SESSION_ID>",
  generator_skill_name="<GENERATOR_SKILL_NAME>"
)

Auto-refine sau failed round:
1. Nếu decision=eligible_to_lock, dừng và report. Không lock nếu chưa approve.
2. Nếu decision=refine_prompt và round_number < max_rounds, inspect MLflow
   artifacts của evaluated run, nhất là disagreement_rows.csv,
   prompt_bundle.json, calibration manifest, và verdict files.
3. Spawn đúng hai editor subagents bằng static editor templates nếu cần review:
   - validator-rubric reviewer
   - generator-policy reviewer
4. Chỉ đưa cho editors phần evidence được harness chủ động export từ evaluated
   MLflow round. Editors chỉ trả proposals theo schema:
   target: generator | validator | no_change
   evidence_uids: [...]
   diagnosis: ...
   proposed_patch: ...
   expected_effect: ...
   risk: ...
   change_summary: ...
6. Reject proposal nếu dựa vào hidden labels làm validator-facing evidence,
   dùng PMI, xem một model là ground truth, đổi policy quá rộng mà không có
   source_uid evidence, làm lộ label hoặc peer verdict cho validator
   subagents, yêu cầu editor gọi MCP hoặc edit files, không tóm tắt được thành
   một change_summary nhỏ, hoặc cố nới rubric để bỏ qua bad calibration rows.
7. Selection rules:
   - Ưu tiên no_change và dừng nếu cả hai proposals đều chỉ ra vấn đề ở
     calibration rows.
   - Ưu tiên proposal nhỏ nhất, chỉ chạm một target.
   - Ưu tiên generator-policy change khi rows mơ hồ về nghĩa, tiếng Việt không
     tự nhiên, source-fidelity drift, hoặc label drift.
   - Ưu tiên validator-rubric change khi generated rows ổn nhưng ranh giới các
     class chưa rõ.
   - Nếu evidence lẫn lộn, dừng và hỏi operator.
8. Apply một instruction change, tạo round-<NN+1>, giữ nguyên source_uid set,
   rerun ba validator models, rồi gọi evaluate_prompt_refinement_round lại.
9. Dừng khi eligible_to_lock, max_rounds, blocker, hoặc không có proposal hợp lệ.

Rules:
- Không đọc hidden labels ngoài bước chuẩn bị calibration_source.
- Validator subagents phải luôn blind. Không lộ label, expected label, hoặc
  peer verdict cho họ.
- Editor subagents là reviewer sau failed round. Họ chỉ được dùng label trong
  evidence pack để chẩn đoán failed round và trả proposal.
- Validator subagents do not call MCP tools hoặc ghi runtime state.
- Editor subagents do not call MCP tools, edit files, ghi runtime state, chạy
  evaluation, hoặc quyết định lock status.
- Không inspect các file repo không liên quan.
- Không sửa generator hoặc validator instructions trong lúc round đang chạy.
- Không dùng PMI trong loop này.
- Không gọi confirm_prompt_lock nếu chưa được approve rõ ràng.
- Nếu MCP hoặc MLflow unavailable, báo blocker; không tự start server.

Report:
- verdict file paths
- kappa và decision
- disagreement artifact path nếu có
- generator và validator prompt versions
- bundle ID
- MLflow run ID
- blockers hoặc câu hỏi còn mở
```
