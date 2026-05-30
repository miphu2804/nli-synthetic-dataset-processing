# Giải thích Generator Skill

## Ý tưởng chung

Skill này nhận vào 1 tập **premise** (câu tiền đề luật pháp tiếng Việt), rồi sinh ra **3 hypothesis** (câu giả thuyết) cho mỗi premise, với 3 nhãn khác nhau:

| Label | Nghĩa |
|-------|-------|
| `entailment` | Hypothesis được suy ra từ premise (đúng) |
| `contradiction` | Hypothesis mâu thuẫn trực tiếp với premise (sai) |
| `neutral` | Hypothesis không mâu thuẫn nhưng cũng không được premise hỗ trợ (không xác định) |

## Mỗi premise sinh hypothesis như thế nào?

Lấy premise gốc:

> **P:** *"Người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý có thể bị áp dụng hình thức khiển trách."*

**1 premise → 3 hypothesis**, mỗi hypothesis 1 rule, 3 tier khác nhau:

### H1 — entailment (Surface — Voice flip)
Chỉ đảo câu chủ động ↔ bị động, nghĩa không đổi.
> *"Hình thức khiển trách có thể được áp dụng đối với người từ đủ 16 tuổi đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý."*

### H2 — contradiction (Structural — Scope shift)
Đổi "từ đủ 16" thành "dưới 16" → mâu thuẫn trực tiếp.
> *"Người dưới 16 tuổi phạm tội nghiêm trọng do vô ý có thể bị khiển trách."*

### H3 — neutral (Deep Semantic — Fallacious reasoning)
Suy luận nghe có lý nhưng sai logic: "some → all".
> *"Vì người từ đủ 16 đến dưới 18 tuổi có thể bị khiển trách, nên mọi người dưới 18 tuổi phạm tội đều bị khiển trách."*

---

**Premise thứ 2** sẽ dùng rule thuộc tier khác để đảm bảo luân phiên:

> **P:** *"Cơ quan điều tra phải thông báo cho gia đình bị can trong vòng 24 giờ kể từ khi bắt giữ."*

### H1 — entailment (Deep Semantic — Logical consequence)
Suy ra hệ quả logic: đã phải thông báo trong 24h → chậm quá 24h là sai luật.
> *"Việc thông báo cho gia đình bị can sau 48 giờ kể từ khi bắt giữ là vi phạm quy định tố tụng."*

### H2 — contradiction (Surface — Number distortion)
Đổi "24" thành "72" → mâu thuẫn.
> *"Cơ quan điều tra phải thông báo cho gia đình bị can trong vòng 72 giờ kể từ khi bắt giữ."*

### H3 — neutral (Structural — Irrelevant link)
Gắn thêm điều khoản không liên quan.
> *"Cơ quan điều tra phải thông báo cho gia đình bị can trong vòng 24 giờ và có quyền tịch thu tài sản của bị can."*

→ **Quy tắc**: 2 premise liên tiếp không dùng chung tổ hợp tier.

---

## Adversarial là gì và phân bổ thế nào?

**Adversarial = độ khó để model phân biệt được đúng/sai.** Có 3 mức:

| Tier | Độ khó | Đặc điểm |
|------|--------|----------|
| **Surface** | Dễ (model đúng ≥90%) | Thay đổi bề mặt: đảo câu, đổi số, đổi từ đồng nghĩa. Model dễ phát hiện. |
| **Structural** | Vừa (80-90%) | Thay đổi cấu trúc: thêm mệnh đề phụ, đổi phạm vi, tham chiếu chéo. Ngữ pháp vẫn đúng nhưng phức tạp hơn. |
| **Deep Semantic** | Khó (<80%) | Suy luận nhiều bước, logic nghe có lý nhưng sai, độ trùng từ vựng cao với premise. Model dễ nhầm. |

### Ví dụ cùng 1 premise, 3 mức adversarial

Cùng premise về tuổi 16-18 và khiển trách ở trên, xét riêng label `contradiction`:

**Surface — Number distortion (dễ phát hiện):**
> *"Người từ đủ 14 tuổi..."*

→ Số khác rõ ràng, model chỉ cần nhìn số là biết sai.

**Structural — Scope shift (vừa):**
> *"Người dưới 16 tuổi..."*

→ Đổi phạm vi, cần hiểu "từ đủ 16" ≠ "dưới 16" mới bắt được.

**Deep Semantic — Direct negation (khó):**
> *"Người từ đủ 16 đến dưới 18 tuổi phạm tội nghiêm trọng do vô ý không phải chịu bất kỳ hình thức xử lý nào."*

→ Từ vựng gần giống hệt premise, chỉ khác "có thể bị khiển trách" → "không phải chịu...". Model dễ bị đánh lừa vì overlap quá cao.

### Phân bổ tier cho 1 premise

Mỗi premise lấy 3 rule từ **3 tier khác nhau**, mỗi tier 1 rule:

```
Premise #1:
  entailment    ← Voice flip             (Surface)
  contradiction ← Scope shift            (Structural)
  neutral       ← Fallacious reasoning   (Deep Semantic)

Premise #2:
  entailment    ← Logical consequence    (Deep Semantic)
  contradiction ← Number distortion      (Surface)
  neutral       ← Irrelevant link        (Structural)

Premise #3:
  entailment    ← Conditional rephrase   (Structural)
  contradiction ← Direct negation        (Deep Semantic)
  neutral       ← Independent statement  (Surface)
```

### Phân bổ trên cả batch (100 premise)

| Chỉ tiêu | Tỷ lệ |
|----------|-------|
| Label (entailment / contradiction / neutral) | 33% / 33% / 33% |
| Tier (surface / structural / deep_semantic) | ~33% / 33% / 33% |
| Mỗi rule | dàn đều, rule nào ít dùng sẽ được ưu tiên |

---

## Cách chạy thực tế (Agent-in-the-loop)

**Quan trọng:** Dataset gốc đã có sẵn `premise`, `hypothesis`, `label` — là các cặp NLI đã được gán nhãn (thường bằng tiếng Anh). Nhiệm vụ là:
1. **Dịch cả premise lẫn hypothesis** sang tiếng Việt
2. **Biến đổi adversarial** hypothesis (hoặc premise) để tăng độ khó
3. **Giữ nguyên label gốc**

Generator này **không có API endpoint** — chính AI agent là người thực thi.

```
Phase 0: Setup
├─ Đọc dataset, verify có cột: premise, hypothesis, label
├─ In: tổng số dòng, preview 3 dòng đầu
├─ Xác nhận với user:
│   ├─ Xử lý bao nhiêu dòng? (mặc định: hết)
│   ├─ Output filename? (mặc định: {tên_file}_nli_adversarials.csv)
│   └─ Bắt đầu
└─ Mỗi chunk đọc 5-10 dòng

Phase 1: Loop từng chunk (5-10 dòng/chunk)
│
├─ B1: Đọc chunk
│   Dùng read_dataset với batch_size nhỏ
│
├─ B2: Dịch CẢ premise VÀ hypothesis sang tiếng Việt
│   ⚠️ Không được giữ cái nào tiếng Anh
│   Dịch cùng nhau để giữ đúng mối quan hệ logic
│
├─ B3: Gán adversarial rule dựa trên label gốc
│   Label entailment → rule trong nhóm entailment (9 rule)
│   Label contradiction → rule trong nhóm contradiction (5 rule)
│   Label neutral → rule trong nhóm neutral (5 rule)
│   Tier luân phiên: Surface → Structural → Deep Semantic
│
├─ B4: Áp dụng biến đổi adversarial
│   Biến đổi hypothesis (và/hoặc premise) theo rule đã chọn
│   Surface: thay đổi nhẹ về từ vựng/cú pháp
│   Structural: thay đổi mệnh đề, phạm vi
│   Deep Semantic: suy luận nhiều bước, thay đổi tinh vi, overlap cao
│   ⚠️ Label gốc phải được giữ nguyên sau biến đổi
│
├─ B5: Validate
│   ├─ Label có còn đúng không?
│   ├─ Rule đã được áp dụng rõ ràng chưa?
│   ├─ Có từ khóa lộ label không?
│   ├─ Cả premise và hypothesis đều tiếng Việt chưa?
│   └─ Ngữ pháp tự nhiên không?
│
├─ B6: Ghi chunk bằng write_dataset
│   output.path phải là full file path
│   Mỗi chunk → 1 file riêng
│
└─ B7: Báo cáo tiến độ

Phase 2: Lặp đến khi hết target

Phase 3: Merge + Final report
```

---

## Bảng tổng hợp 19 rule

### Entailment (9 rule)
Giữ nguyên nghĩa, thay đổi hình thức.

| Rule | Kỹ thuật | Ví dụ ngắn |
|------|----------|-----------|
| Voice flip | Chủ động ↔ bị động | "có thể bị khiển trách" → "khiển trách có thể được áp dụng" |
| Synonym swap | Từ đồng nghĩa pháp lý | "người từ đủ 16" → "người chưa thành niên từ 16" |
| Clause restructure | Cụm danh từ ↔ mệnh đề | "việc áp dụng hình thức..." |
| Conditional rephrase | Viết lại dạng nếu-thì | "Trong trường hợp...thì..." |
| Number equivalence | Cùng 1 số, cách viết khác | "từ đủ 16" = "từ 16" |
| Complexity expand | Chèn mệnh đề phụ | "...theo quy định của Bộ luật Hình sự..." |
| Logical consequence | Suy hệ quả logic | "không bị coi là tội phạm đặc biệt nghiêm trọng" |
| General to specific | Luật chung → case cụ thể | "người 17 tuổi phạm tội trộm cắp..." |
| Related clause link | Dẫn điều khoản liên quan thật | "...theo khoản 3 Điều 40" |

### Contradiction (5 rule)
Mâu thuẫn trực tiếp với premise.

| Rule | Kỹ thuật | Ví dụ ngắn |
|------|----------|-----------|
| Direct negation | Phủ định claim chính | "có thể bị" → "không phải chịu" |
| Scope shift | Đối tượng ngoài phạm vi | "từ đủ 16" → "dưới 16" |
| Modifier flip | Đảo yếu tố then chốt | "vô ý" → "cố ý" |
| Severity escalation | Leo thang mức độ | "nghiêm trọng" → "đặc biệt nghiêm trọng" |
| Number distortion | Đổi số làm sai luật | "16" → "14" |

### Neutral (5 rule)
Không mâu thuẫn, không được premise hỗ trợ.

| Rule | Kỹ thuật | Ví dụ ngắn |
|------|----------|-----------|
| Fallacious reasoning | Logic nghe đúng nhưng sai | "some → all" |
| Unsupported claim | Thêm điều premise không nói | "phải bồi thường thiệt hại" |
| Rule misapplication | Áp sai luật cho case này | "phạt tù" thay vì "khiển trách" |
| Irrelevant link | Gắn điều khoản không liên quan | "bị tịch thu tài sản" |
| Independent statement | Câu đúng nhưng khác chủ đề | chính sách khoan hồng chung |

---

## Tóm tắt nhanh

| Tham số | Giá trị |
|---------|--------|
| Hypothesis / premise | 3 (1 entailment + 1 contradiction + 1 neutral) |
| Rule / hypothesis | 1, không trùng rule trong cùng 1 premise |
| Tier / premise | 3 tier khác nhau cho 3 hypothesis |
| Batch size | 100 premise = 300 rows |
| Tỷ lệ label | 1:1:1 |
| Tỷ lệ tier | 1:1:1 |
| Validate | 5 gate, fail → retry rule khác, fail 3 lần → skip |
| Output | CSV: `source_uid, premise, hypothesis, label, rule, tier` |
| Tên file mặc định | `{tên_file_gốc}_nli_adversarials.csv` |
