# Progress Tracking — Giải thích

## Ý tưởng

`progress.jsonl` là append-only JSONL event log. **File này chính là state** — không database, không memory. Mỗi agent có hash chain riêng, chain không đụng nhau.

## Event Format

Mỗi dòng event phải có:

| Field | Mô tả |
|-------|-------|
| `id` | Per-agent monotonic (`alice-1`, `bob-3`, ...) |
| `ts` | ISO timestamp |
| `event` | Loại event: `run.start`, `claim`, `row.done`, `row.skip`, `batch.done`, `run.end` |
| `agent` | Ai ghi event này |
| `prev_hash` | SHA-256 của dòng trước **cùng agent** |

## Per-Agent Hash Chain

Mỗi agent có chain riêng. 2 agent append cùng lúc không làm vỡ hash của nhau.

```
alice: {"agent":"alice","prev_hash":"0"} → hash "abc" → {"agent":"alice","prev_hash":"abc"} → ...
bob:   {"agent":"bob","prev_hash":"0"}   → hash "xyz" → {"agent":"bob","prev_hash":"xyz"}   → ...
```

Sửa 1 dòng → hash thay đổi → `prev_hash` dòng sau của agent đó không khớp → phát hiện ngay.

## Các loại event

| Event | Khi ghi | Dữ liệu chính |
|-------|--------|--------------|
| `run.start` | Bắt đầu session | — |
| `claim` | Đăng ký row sẽ xử lý | `rows: "1-50"` |
| `unclaim` | Trả lại row (lỗi, conflict) | `rows`, `reason` |
| `row.done` | Mỗi row xong | `source_uid` |
| `row.skip` | Row fail sau 3 lần retry | `source_uid`, `reason`, `retries` |
| `batch.done` | Batch ghi file xong | `batch`, `rows`, `file` |
| `run.end` | Session kết thúc | `processed` |

## Tại sao cần claim?

Trước khi xử lý row 1-50, agent ghi claim → agent khác thấy claim → skip, xử lý từ row 51. **Không duplicate work.**

Nếu 2 agent cùng claim 1 row → timestamp sớm hơn thắng. Agent thua unclaim và chọn row mới.

## Query thường dùng

```bash
# Tổng row đã done (tất cả agent)
grep -c '"event":"row.done"' progress.jsonl

# Row nào đã bị claim?
grep '"event":"claim"' progress.jsonl

# Row của tôi đã done
grep '"event":"row.done"' progress.jsonl | grep -c '"agent":"alice"'

# Verify chain của alice
grep '"agent":"alice"' progress.jsonl | python3 -c "
import hashlib, json, sys
prev = '0'
for i, line in enumerate(sys.stdin, 1):
    obj = json.loads(line)
    assert obj['prev_hash'] == prev, f'Broken at {i}'
    prev = hashlib.sha256(line.rstrip('\n').encode()).hexdigest()
print(f'alice OK: {i} events')
"
```

## File location

```
.pipeline/progress.jsonl    ← tracked (per-agent hash chain, claim support)
.pipeline/outputs/          ← gitignored (CSV per agent)
```
