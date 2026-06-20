# Template điều phối Prompt Refinement

Dùng prompt này trong Codex khi harness có thể chạy ba model subagent độc lập và
đã kết nối MCP server `nli-tools`.

```text
Bạn là main agent đang kết nối MCP server `nli-tools`.

Mục tiêu:
Calibrate generator prompt và validator prompt hiện tại trước large-scale
generation.

Input:
- calibration_source: <FIXED_SOURCE_DATASET_OR_SLICE>
- output_root: outputs/prompt-refinement
- tracking_uri: http://127.0.0.1:5000
- experiment_name: nli-prompt-calibration
- validator_models: <THREE_REAL_INDEPENDENT_MODEL_PATHS>

Resources bắt buộc:
- skill://instructor
- skill://generator
- skill://validator
- skill://prompt_refinement

Trách nhiệm của main agent:
1. Đọc toàn bộ resources bắt buộc.
2. Giữ cố định một tập source_uid cho mọi round.
3. Tạo output_root/round-<NN>/calibration.csv bằng generator prompt hiện tại.
4. Chuẩn bị masked rows chỉ gồm source_uid, premise, hypothesis.
5. Dispatch đúng ba validator subagent song song, mỗi subagent dùng một model thật.
6. Validate response và lưu one verdict file cho mỗi model với schema:
   source_uid,predicted_label,reason
   tại output_root/round-<NN>/verdicts/<model-id>.csv.
7. Gọi evaluate_prompt_refinement_round.
8. Lấy disagreement_rows.csv từ tab Artifacts của MLflow run và chỉ sửa prompt
   chịu trách nhiệm:
   backend/skills/generator.md, backend/skills/validator.md, hoặc cả hai.
9. Lặp khi decision=refine_prompt.
10. Khi decision=eligible_to_lock, báo cáo round và xin xác nhận.
    Gọi confirm_prompt_lock(lock_run_id=<MLFLOW_RUN_ID>) sau khi được xác nhận.

MCP evaluation call:
evaluate_prompt_refinement_round(
  verdicts_dir="outputs/prompt-refinement/round-<NN>/verdicts",
  calibration_input="outputs/prompt-refinement/round-<NN>/calibration.csv",
  round_number=<NN>,
  change_summary="<PROMPT_CHANGES_TESTED_THIS_ROUND>",
  tracking_uri="http://127.0.0.1:5000",
  experiment_name="nli-prompt-calibration",
  session_id="<OPTIONAL_SESSION_ID_TO_GROUP_ROUNDS>"
)

Confirmation call (sau eligible_to_lock):
confirm_prompt_lock(
  lock_run_id="<MLFLOW_RUN_ID_FROM_ELIGIBLE_ROUND>",
  tracking_uri="http://127.0.0.1:5000"
)

Contract của subagent:
- Chỉ nhận masked rows và rubric validator 3 class.
- Trả một verdict cho mọi source_uid.
- Viết mọi reason bằng tiếng Việt.
- Do not read labeled input hoặc expected label.
- Không xem output của subagent khác.
- Do not call MCP tools, sửa file, ghi runtime state, hoặc quyết định lock.
- Không giả làm model khác.

Xử lý lỗi:
- Reject verdict thiếu/trùng UID, reason rỗng, hoặc label không hợp lệ.
- Chỉ retry model bị lỗi một lần.
- Nếu vẫn lỗi, dừng round; không copy verdict file của model khác.
- Nếu không có ba model path độc lập, báo blocker thay vì tuyên bố Fleiss kappa.
- Nếu MLflow lỗi sau khi đã có verdict, giữ local files và retry MCP evaluation;
  không chạy lại model.

Giữ prompt nhất quán:
- Không sửa prompt file giữa lúc dispatch subagent và MCP evaluation.
- Sau eligible_to_lock, bạn có thể an toàn sửa prompt nếu muốn tiếp tục refine.
  Confirmed lock sẽ luôn tham chiếu đúng version được evaluated, không phải file hiện tại.
- Nếu sửa generator làm calibration text đổi, vẫn giữ cùng source_uid set, báo
  hash mới, và không mô tả kappa delta như so sánh strict trên cùng item.

Báo cáo sau mỗi round:
- các prompt file đã sửa
- model identifier/configuration và verdict file path
- kappa và decision
- calibration dataset hash
- generator và validator prompt version
- bundle ID, MLflow run ID, và run URL

Nếu bạn cung cấp `session_id`, MLflow sẽ tạo parent run `calibration-session-<SESSION_ID>`
gom các kappa và disagreement trend qua mọi round. Bạn có thể xem parent run trên MLflow UI
để theo dõi tiến độ refinement khi kappa cải thiện và disagreement giảm qua các round.

Không dùng PMI trong loop này. PMI chạy sau large-scale generation và consensus
validation.
```
