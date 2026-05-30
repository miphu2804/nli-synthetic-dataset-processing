# Giải thích Generator Skill

## Ý tưởng chung

Dataset gốc đã có sẵn `premise`, `hypothesis`, `label` — là các cặp NLI đã được gán nhãn (thường tiếng Anh). Skill này hướng dẫn agent:
1. **Dịch cả premise lẫn hypothesis** sang tiếng Việt
2. **Biến đổi adversarial** hypothesis (hoặc premise) để tăng độ khó
3. **Giữ nguyên label gốc**

Mỗi dòng input → 1 dòng output (không sinh thêm). Label từ dataset gốc quyết định rule nào được dùng.

## 3 label

| Label | Nghĩa | Rule được dùng |
|-------|-------|---------------|
| `entailment` | Hypothesis được suy ra từ premise | 9 rule entailment |
| `contradiction` | Hypothesis mâu thuẫn với premise | 5 rule contradiction |
| `neutral` | Không mâu thuẫn, không được hỗ trợ | 5 rule neutral |

## 3 Adversarial Tier

**Adversarial = độ khó để model phân biệt đúng/sai.**

| Tier | Độ khó | Cách thay đổi | Model detect bằng |
|------|--------|--------------|-------------------|
| **Surface** | Dễ (≥90%) | 1-2 từ, số, giọng câu | Pattern matching |
| **Structural** | Vừa (80-90%) | Mệnh đề, phạm vi, cấu trúc | Syntax tree diff |
| **Deep Semantic** | Khó (<80%) | Logic ngầm, từ gần giống hệt | Real reasoning |

### Ví dụ cùng 1 premise, cùng label contradiction

> Premise: *"Người từ đủ 16 tuổi...có thể bị khiển trách."*

| Tier | Rule | Hypothesis | Tại sao khó |
|------|------|-----------|------------|
| Surface | Number distortion | "...từ đủ **14** tuổi..." | Số khác, nhìn là biết |
| Structural | Scope shift | "...**dưới 16** tuổi..." | Cần hiểu "dưới 16" ≠ "từ đủ 16" |
| Deep Semantic | Direct negation | "...**không phải chịu** bất kỳ..." | 90% từ giống premise, 2-3 từ đảo toàn bộ nghĩa |

## 19 Rule

### Entailment (9) — giữ nghĩa, đổi hình thức
Voice flip, Synonym swap, Clause restructure, Conditional rephrase, Number equivalence, Complexity expand, Logical consequence, General to specific, Related clause link

### Contradiction (5) — mâu thuẫn trực tiếp
Direct negation, Scope shift, Modifier flip, Severity escalation, Number distortion

### Neutral (5) — không mâu thuẫn, không được hỗ trợ
Fallacious reasoning, Unsupported claim, Rule misapplication, Irrelevant link, Independent statement

## Cách chạy

Agent đọc 3 skill: `generator` → `progress_tracking` → `delegation` → `execution`

```
1. Load skills + đọc dataset
2. Init progress.jsonl (run.start với prev_hash:"0")
3. Loop batch 5-10 dòng:
   a. Claim row trong progress.jsonl
   b. Dịch premise + hypothesis sang tiếng Việt
   c. Gán rule dựa trên label gốc, tier luân phiên
   d. Áp dụng adversarial transform
   e. Validate (label preserved? còn English? grammar OK?)
   f. Ghi CSV + append row.done vào progress.jsonl
4. Merge part files → output cuối
```

## Output Schema

`source_uid, premise, hypothesis, label, rule, tier, reason`

| Cột | Mô tả |
|-----|-------|
| `source_uid` | ID từ dataset gốc |
| `premise` | Tiếng Việt (đã dịch) |
| `hypothesis` | Tiếng Việt (đã dịch + adversarial transform) |
| `label` | Giữ nguyên từ dataset gốc |
| `rule` | Rule biến đổi đã áp dụng |
| `tier` | surface / structural / deep_semantic |
| `reason` | Giải thích ngắn tại sao rule này được áp dụng |
