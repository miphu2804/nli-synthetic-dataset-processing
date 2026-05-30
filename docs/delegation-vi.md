# Delegation — Giải thích

## Ý tưởng

Main agent đọc dataset + assign rule. Subagent xử lý batch (dịch + transform). Subagent là pure function — không state, không biết batch trước. Làm xong bị hủy. Context main agent không bị dồn.

## Phân chia

| | Main agent | Subagent |
|---|---|---|
| Đọc dataset + progress.jsonl | ✓ | ✗ |
| Claim row + gán rule + tier | ✓ | ✗ |
| Dịch sang tiếng Việt | ✗ | ✓ |
| Adversarial transform | ✗ | ✓ |
| Validate cuối + ghi CSV | ✓ | ✗ |
| Append progress.jsonl | ✓ | ✗ |

## Subagent prompt (main agent build)

Main agent copy 19 rule từ generator.md vào prompt, kèm batch data. Subagent không cần đọc skill.

```
You are an NLI adversarial transformer.
[19 rule tables + anti-artifact constraints]
[Batch JSON: 5 rows với source_uid, premise, hypothesis, label, assigned rule, tier]
1. Translate BOTH premise and hypothesis to Vietnamese
2. Apply assigned rule to hypothesis
3. Label unchanged
4. Return JSON array
```

## Parallel (MANDATORY)

**Spawn tất cả subagent trong 1 message.** Mỗi con batch khác nhau → không conflict.

```
Main agent (1 message với N subagent)
  ├─ Subagent A: rows 1-5   ─┐
  ├─ Subagent B: rows 6-10  ─┤ chạy cùng lúc
  └─ Subagent C: rows 11-15 ─┘
```

Wave đầu 3 subagent (test chất lượng), OK thì scale lên 5+. Cap 10/lần.

Sequential chỉ khi user nói "chạy từng cái một".

## Multi-Agent (nhiều người cùng làm)

Khi nhiều agent cùng xử lý 1 dataset, mỗi agent:
1. Đọc `progress.jsonl` → xem row nào đã claim, đã done
2. Claim row tiếp theo → echo `claim` event
3. Xử lý batch → ghi CSV riêng (`alice_part1.csv`)
4. Append `row.done` events
5. Sync log (git push / shared drive)

Không cần database, không cần lock server. Claim + append-only là đủ.

## Model

| Agent | Model |
|-------|-------|
| Main | Lớn nhất có sẵn |
| Subagent | Nhỏ nhất có sẵn |

Không hardcode tên model. Dùng subagent nếu harness hỗ trợ.

## Flow

```
Main agent
  ├─ Check progress.jsonl → row nào done, row nào claimed
  ├─ Claim batch tiếp theo
  ├─ Đọc batch + gán rule
  ├─ Spawn subagent(s)
  ├─ Validate output
  ├─ Ghi CSV part file
  ├─ Append progress.jsonl
  └─ Báo user: "Done batch N"
```
