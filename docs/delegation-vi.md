# Delegation — Giải thích

## Ý tưởng

Thay vì main agent tự làm hết (context càng lúc càng dài), mỗi batch được giao cho 1 **subagent** xử lý. Subagent là pure function: nhận input → làm → trả output → bị hủy. Không giữ state, không biết batch trước làm gì.

## Phân chia trách nhiệm

| | Main agent | Subagent |
|---|---|---|
| Đọc dataset | ✓ | ✗ |
| Đọc/ghi `progress.jsonl` | ✓ | ✗ |
| Gán rule + tier cho từng row | ✓ | ✗ |
| Dịch sang tiếng Việt | ✗ | ✓ |
| Áp dụng adversarial transform | ✗ | ✓ |
| Validate output | ✓ (kiểm cuối) | ✓ (tự kiểm) |
| Ghi CSV | ✓ | ✗ |

## Subagent prompt

Main agent gửi cho subagent 1 prompt **đầy đủ** — subagent không cần đọc skill nào khác:

```
Bạn là NLI transformer. Đây là 19 rule biến đổi (copy từ generator.md).
Đây là 5 row cần xử lý (JSON). Mỗi row đã có rule được gán sẵn.
Việc của bạn: dịch premise + hypothesis sang tiếng Việt,
               áp dụng rule, giữ nguyên label gốc.
Trả về JSON array 5 phần tử.
```

## Chạy tuần tự vs song song

| Chế độ | Cách | Khi dùng |
|--------|------|----------|
| Tuần tự | 1 subagent/batch, chờ xong rồi batch tiếp | Test, debug |
| Song song | 3-5 subagent cùng lúc, mỗi con batch khác nhau | Production, dataset lớn |

Song song không cần lock vì:
- Mỗi subagent ghi file CSV riêng (part1.csv, part2.csv, ...)
- Mỗi subagent xử lý row khác nhau (không đụng hàng)
- Main agent append progress.jsonl tuần tự sau khi tất cả done

## Model

| Agent | Model | Lý do |
|-------|-------|-------|
| Main | Pro / lớn | Orchestration, validate, tracking |
| Subagent | Flash / nhỏ | Rẻ, nhanh, context nhẹ (~2K tokens/batch) |

## Flow tổng

```
Main agent
  │
  ├─ tail -1 progress.jsonl → biết row 15 done
  ├─ Đọc batch row 16-20
  ├─ Gán rule + tier (luân phiên, ưu tiên rule ít dùng)
  │
  ├─ Spawn subagent ──────────────────────┐
  │   Input: 5 rows + rules + assignments │
  │   Xử lý: dịch + transform + validate  │
  │   Output: 5 rows JSON                 │
  └────────────────────────────────────────┘
  │
  ├─ Validate output (label preserved? còn English?)
  ├─ Ghi part4.csv
  ├─ Append 5 dòng row.done → progress.jsonl
  └─ Báo user: "Done batch 4"
```
