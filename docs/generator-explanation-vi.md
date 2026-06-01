# Generator - Giải thích

Agent mới bắt đầu từ `skill://instructor` để hiểu NLI task, resource map và flow
tổng quát. `skill://generator` chỉ chứa rule và self-check của generation phase.

Dataset gốc có `premise`, `hypothesis`, `label`. Ba label NLI:

| Label | Ý nghĩa |
|-------|---------|
| `entailment` | Premise hỗ trợ hypothesis |
| `contradiction` | Hypothesis mâu thuẫn với premise |
| `neutral` | Hypothesis không được hỗ trợ nhưng cũng không mâu thuẫn |

Generation phase:

1. Dịch cả premise và hypothesis sang tiếng Việt.
2. Chọn một trong 19 rule phù hợp label.
3. Transform hypothesis để khó phân loại hơn.
4. Giữ nguyên label gốc.
5. Self-check generation output trước khi submit.

Không dùng tier. Main agent chỉ gửi rule cần thiết cho từng batch để giảm token.
Validation phase độc lập sẽ được bổ sung sau.

## Chia Slice

Mỗi người tự nhận một slice zero-based:

```text
Người 1: row_offset=0,     row_limit=10000
Người 2: row_offset=10000, row_limit=10000
```

## Flow MCP

```text
start_generation_run
  → calculate_dispatch_plan(samples=total_target_rows, batch_size=batch_size)
  → claim batch
  → nếu >= 100 row: load skill://delegation và dispatch song song
  → nếu < 100 row: main agent transform trực tiếp
  → self-check, submit batch và refill slot
  → load skill://aggregator
  → finalize_generation_run
```

```text
total_batches = ceil(samples / batch_size)
parallel_workers = min(total_batches, max_parallel_workers)
```

Mặc định: `batch_size=20`, `max_parallel_workers=10`.

## Output

```csv
source_uid,premise,hypothesis,label
```
