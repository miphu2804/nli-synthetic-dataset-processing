# Progress Tracking — Giải thích

## Ý tưởng

Thay vì ghi log vào stdout (session tắt là mất), mọi hành động được ghi vào file `progress.jsonl` — append-only, mỗi dòng 1 event. File này **chính là state** của pipeline.

## Hash chain

Mỗi dòng chứa `prev_hash` = SHA-256 của dòng trước. Nếu ai sửa 1 dòng → hash của dòng đó thay đổi → `prev_hash` của dòng sau không khớp → toàn bộ chain phía sau vỡ.

```
Dòng 1: {"id":1,"event":"run.start","prev_hash":"0"}
          → hash(dòng1) = "abc"
Dòng 2: {"id":2,"event":"row.done","prev_hash":"abc",...}
          → hash(dòng2) = "def"
Dòng 3: {"id":3,"event":"row.done","prev_hash":"def",...}

Verify: hash(dòng2) == "def" == dòng3.prev_hash ✓
        Sửa dòng2 → hash(dòng2) ≠ "def" → dòng3.prev_hash sai ✗
```

## Các loại event

| Event | Khi nào ghi | Dữ liệu |
|-------|------------|---------|
| `run.start` | Bắt đầu run | `total_rows`, `batch_size`, `output` |
| `row.done` | Mỗi row xử lý xong | `source_uid` |
| `row.skip` | Row bị bỏ qua sau 3 lần retry | `source_uid`, `reason`, `retries` |
| `batch.done` | Mỗi batch ghi file xong | `batch`, `rows`, `file` |
| `batch.fail` | Batch ghi file thất bại | `batch`, `error` |
| `run.end` | Run hoàn thành | `processed`, `skipped` |

## Tại sao cần progress.jsonl?

1. **Resume sau crash**: `grep -c '"event":"row.done"' progress.jsonl` → biết đã xong bao nhiêu row
2. **Chống giả mạo**: hash chain đảm bảo log không bị sửa
3. **Subagent check**: agent mới đọc log là biết trạng thái, không cần shared memory
4. **Audit**: trace lại toàn bộ run, biết row nào xử lý lúc nào

## Query thường dùng

```bash
# Đang dừng ở đâu?
grep -c '"event":"row.done"' progress.jsonl

# Row nào bị skip?
grep '"event":"row.skip"' progress.jsonl

# Verify hash chain
python3 -c "
import hashlib, json
prev = '0'
with open('progress.jsonl') as f:
    for i, line in enumerate(f, 1):
        obj = json.loads(line)
        assert obj['prev_hash'] == prev, f'Broken at {i}'
        prev = hashlib.sha256(line.rstrip('\n').encode()).hexdigest()
print(f'OK: {i} events')
"
```
