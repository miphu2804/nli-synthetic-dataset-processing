# Delegation - Giải thích

## Nguyên tắc

Chỉ đọc `skill://delegation` khi xử lý ít nhất `100` row được giao. Với ít hơn
`100` row, main agent có thể transform trực tiếp.

Main agent local là MCP caller duy nhất. MCP runtime tool ghi progress. Subagent
chỉ xử lý text:

```text
Main agent claim batch qua MCP
  → gửi rows + rule cần dùng cho subagent
  → subagent dịch và transform
  → subagent trả JSON
  → main agent self-check generation output và submit qua MCP
```

Subagent không đọc `progress.jsonl`, không gọi MCP và không biết các batch khác.
Validation phase độc lập sẽ được bổ sung sau, không nằm trong delegation flow.

## Parallel

Main agent tính pool trước:

```text
total_batches = ceil(samples / batch_size)
parallel_workers = min(total_batches, max_parallel_workers)
```

Mặc định `batch_size=20`, cap `10`. Main agent claim đủ slot theo thứ tự, spawn
song song ngay. Batch nào xong trước thì self-check, submit và refill slot ngay.
Không scale chậm từ 3 lên 5 worker.

## Local Scope

Mỗi người chạy pipeline local riêng. Không push `.pipeline` lên Git và không
sync qua shared drive. Việc chia dataset dùng `row_offset` và `row_limit`.
