# Ghi chú từng trang: `2402.12368v2`

Nguồn:
- [HTML](https://arxiv.org/html/2402.12368v2)
- [PDF](https://arxiv.org/pdf/2402.12368v2)

Tên paper:
- `A Synthetic Data Approach for Domain Generalization of NLI Models`

Mục tiêu của note này:
- đọc theo từng trang
- highlight ý quan trọng
- comment tiếng Việt ngắn gọn, dễ dùng cho research note và proposal

## Phần bạn cần nhất: phương pháp synthetic data của paper
Nếu chỉ nhìn theo góc `paper này làm synthetic data như thế nào`, thì phần cốt lõi thực ra là 8 ý sau.

### 1. Không sinh trực tiếp NLI pair ngay từ đầu
**Trang liên quan:** 2, 3

**Ý chính**
- Paper không bắt đầu bằng cách lấy một `(premise, hypothesis)` có sẵn rồi sửa nhẹ.
- Họ tách pipeline thành 2 tầng:
  1. sinh `premise`
  2. từ `premise` đó mới sinh ra `(hypothesis, label)`

**Vì sao quan trọng**
- Cách này giúp họ kiểm soát được domain và độ dài premise trước khi bàn đến nhãn NLI.

### 2. Sinh premise theo `domain + length`
**Trang liên quan:** 3, 4, 5

**Ý chính**
- Họ few-shot prompt một LLM để sinh các text theo:
  - domain
  - length
- Length chỉ có 2 mức:
  - `short`
  - `paragraph`

**Vì sao quan trọng**
- Đây chính là lớp synthetic data đầu tiên: chưa phải NLI hoàn chỉnh, mà là synthetic premises có phân phối được kiểm soát.

### 3. Không tin hoàn toàn vào domain do model tự nghĩ ra
**Trang liên quan:** 4

**Ý chính**
- Ban đầu model tự sinh domain mới, nhưng kết quả bị:
  - lệch về vài domain
  - trùng nghĩa
  - noisy
- Sau đó tác giả xem khoảng 1000 mẫu và chốt thủ công `38 domain`.

**Vì sao quan trọng**
- Đây là một bước `human curation` trong pipeline synthetic data.
- Nghĩa là paper này không theo kiểu “generate full auto rồi dùng luôn”.

### 4. Sinh hypothesis và label từ premise bằng một model đã học từ MNLI
**Trang liên quan:** 4, 5

**Ý chính**
- Sau khi có premise, tác giả dùng một model khác để sinh:
  - `hypothesis`
  - `label`
- Model này được `prompt-tune` trên training split của `MNLI`.

**Vì sao quan trọng**
- Synthetic data ở đây không chỉ là dịch hay paraphrase.
- Nó là `premise-conditioned generation` cho task NLI.

### 5. Họ chọn `prompt-tuning`, không chỉ prompt thường và cũng không fine-tune đầy đủ
**Trang liên quan:** 4

**Ý chính**
- Tác giả nói rõ vì sao họ dùng `prompt-tuning`:
  - cập nhật ít tham số hơn
  - regularization tốt hơn
  - tránh memorization
- Họ cũng thử prompt thường nhưng chất lượng không đủ tốt.

**Vì sao quan trọng**
- Điểm này cho thấy synthetic data quality phụ thuộc rất mạnh vào cách huấn luyện generator.

### 6. Họ chủ động làm dữ liệu cân bằng theo `label + domain + premise length`
**Trang liên quan:** 2, 5

**Ý chính**
- Dữ liệu cuối được thiết kế để tương đối cân bằng theo:
  - label
  - domain
  - premise length
- Label distribution của GNLI khá đều:
  - entailment
  - contradiction
  - neutral

**Vì sao quan trọng**
- Đây là đóng góp lớn nhất về mặt synthetic data method.
- Không phải chỉ sinh thật nhiều, mà sinh có kiểm soát phân phối.

### 7. Họ cố tránh kiểu hypothesis quá đơn giản
**Trang liên quan:** 1, 4, 5

**Ý chính**
- Paper nhấn mạnh hypothesis nên được tạo theo cách `creative`, không chỉ:
  - lấy subset của premise
  - thêm phủ định đơn giản
  - sửa vài token
- Tác giả nói model nhỏ hơn thường rơi vào các kiểu synthetic quá nông như vậy.

**Vì sao quan trọng**
- Đây là insight rất đáng học cho proposal của bạn:
  - nếu chỉ dịch rồi sửa chút ít, dữ liệu synthetic dễ quá
  - model có thể học shortcut thay vì reasoning

### 8. Cuối cùng vẫn phải kiểm tra chất lượng bằng người thật
**Trang liên quan:** 6

**Ý chính**
- Họ lấy `500` ví dụ synthetic để human annotate.
- So sánh label do model sinh ra với human majority / unanimous.
- Kết quả cho thấy label của model đủ tốt nhưng không hoàn hảo.

**Vì sao quan trọng**
- Đây là bước chứng minh synthetic data có usable quality.
- Bài học cho bạn:
  - nếu làm tiếng Việt, nên có ít nhất một tập kiểm tra tay nhỏ
  - không nên chỉ tin vào output của generator và validator tự động

## Tóm tắt phương pháp synthetic data của paper trong 1 dòng
`Sinh premise đa domain, đa độ dài -> dùng model đã học từ MNLI để sinh hypothesis + label -> cân bằng phân phối -> kiểm tra chất lượng bằng human evaluation`

## Nếu rút ra thành bài học cho đề tài của bạn
Từ paper này, các ý nên lấy là:

1. Đừng chỉ dịch cặp NLI có sẵn một cách ngẫu nhiên.
2. Hãy kiểm soát dữ liệu theo `domain + premise length + label`.
3. Nếu có bước generate thêm, nên generate từ `premise` theo cách có kiểm soát.
4. Cần một bước validation nhỏ để biết synthetic Vietnamese data có thật sự ổn không.

## Trang 1
**Highlight**
- Paper đặt vấn đề: NLI rất quan trọng, nhưng hiệu năng trên dữ liệu `out-of-domain` vẫn chưa rõ.
- Tác giả đề xuất một bộ synthetic data lớn để giúp model NLI generalize tốt hơn sang domain mới.
- Dữ liệu của họ có:
  - premise đa dạng về domain
  - premise đa dạng về độ dài
  - hypothesis không chỉ là sửa nhẹ vài token
  - label có độ chính xác cao
- Kết quả nổi bật:
  - `685K` synthetic examples
  - trên `TRUE benchmark`, `T5-small` tốt hơn khoảng `7%` so với phương án train tốt nhất trước đó
  - model nhỏ hưởng lợi rõ hơn model lớn

**Comment tiếng Việt**
- Đây là trang để hiểu đúng động cơ paper: họ không cố làm dataset “đẹp” theo nghĩa hình thức, mà muốn tạo dữ liệu đủ đa dạng để model không bị lệ thuộc vào style của một vài bộ NLI cũ như MNLI.
- Ý rất hợp với đề tài của bạn: nếu chỉ dịch dataset sang tiếng Việt mà phân phối dữ liệu vẫn lệch, model vẫn có thể yếu khi gặp domain lạ.

## Trang 2
**Highlight**
- Tác giả nhấn mạnh họ bao phủ gần `40 domain` thực tế.
- Pipeline tổng quát có ba bước:
  1. sinh tên domain
  2. sinh premise theo domain và độ dài
  3. sinh hypothesis và label theo premise
- Họ cố tình làm dữ liệu cân bằng theo:
  - domain
  - label
  - premise length
- Đánh giá chính trên `TRUE`, là benchmark factual consistency gồm `11 task` unseen.

**Comment tiếng Việt**
- Đây là ý quan trọng nhất để bạn mượn: synthetic data không chỉ cần “đúng nhãn”, mà còn phải cân bằng theo nhiều chiều.
- Với scope của bạn, bản dịch tiếng Việt cũng nên được theo dõi theo:
  - domain
  - độ dài premise
  - label
- Nếu không, bạn chỉ đang có “bản dịch của dữ liệu cũ”, chưa chắc đã có “bộ dữ liệu tiếng Việt tốt hơn”.

## Trang 3
**Highlight**
- Figure 1 mô tả pipeline tạo `General-NLI`:
  - sinh premise đa domain, đa độ dài
  - dùng model khác để sinh `(hypothesis, label)` từ premise
- Tác giả giải thích vì sao họ không sinh tất cả một lần:
  - muốn kiểm soát domain
  - muốn kiểm soát độ dài
  - muốn kiểm soát label
- Họ chọn cách chia thành `2 bước lớn`:
  1. tạo premise
  2. tạo hypothesis + label

**Comment tiếng Việt**
- Đây là chỗ khác biệt lớn với nhiều pipeline synthetic data đơn giản.
- Nếu áp dụng vào research của bạn, ý đáng học là:
  - đừng chỉ cầm `(premise, hypothesis)` tiếng Anh rồi dịch một phát
  - hãy xem liệu có nên tách `chọn nguồn / nhóm domain / nhóm độ dài` trước khi dịch không
- Nói ngắn: paper này dạy cách kiểm soát phân phối dữ liệu ngay từ đầu.

## Trang 4
**Highlight**
- Tác giả không định nghĩa domain quá cứng.
- Họ coi domain như tổ hợp của:
  - genre
  - topic
  - platform
  - spoken/written style
- Ban đầu họ few-shot prompt mô hình bằng `8 seed domains`.
- Sau khi generate thử, họ thấy domain bị lệch và trùng lặp.
- Vì vậy họ lọc thủ công và chốt `38 domain` đa dạng.

**Comment tiếng Việt**
- Ý rất đáng chú ý: để model tự sinh domain hoàn toàn thì phân phối dễ bị lệch.
- Với bài của bạn, điều này gợi ý:
  - nếu dịch SNLI/MNLI/XNLI, nên thống kê domain hoặc ít nhất kiểu premise
  - đừng mặc định dữ liệu nguồn đã cân bằng đủ cho tiếng Việt
- Điểm thực dụng ở đây là: vẫn có bước `manual curation`, không hoàn toàn phó mặc cho model.

## Trang 5
**Highlight**
- Figure 2 cho thấy prompt sinh text theo `domain` và `length`.
- Figure 3 cho thấy prompt sinh `(hypothesis, label)` từ một premise.
- Bộ dữ liệu cuối có `684,929` ví dụ.
- Label khá cân bằng:
  - entailment `35.4%`
  - contradiction `31.1%`
  - neutral `33.5%`
- Dữ liệu cũng được cân bằng theo độ dài premise và domain.

**Comment tiếng Việt**
- Đây là trang rất hữu ích nếu bạn muốn biện minh vì sao proposal của mình phải quan tâm đến `label balance`.
- Một điểm hay nữa: họ chỉ ra prompt-tuning giúp phân phối label synthetic phản chiếu phân phối huấn luyện tốt hơn so với in-context generation thuần.
- Nếu bạn không prompt-tune mà chỉ dùng dịch máy / LLM dịch trực tiếp, bạn nên cẩn thận vì phân phối label sau dịch có thể không còn giữ đúng như kỳ vọng.

## Trang 6
**Highlight**
- Table 4 cho ví dụ synthetic từ nhiều domain khác nhau.
- Tác giả làm human annotation cho `500` ví dụ.
- `490/500` có majority label từ 3 annotator.
- Cohen's kappa trung bình giữa annotator khoảng `67.97%`.
- Độ chính xác label do model sinh ra:
  - `80.41%` so với majority label
  - `89.53%` trên tập unanimous

**Comment tiếng Việt**
- Đây là trang chứng minh dữ liệu synthetic của họ không phải “rác LLM”.
- Cũng nên nhìn thẳng vào điểm yếu: vẫn có ambiguity, nhất là khi premise chưa đủ context.
- Bài học cho pipeline dịch tiếng Việt của bạn:
  - sau khi dịch, các sample mơ hồ nên được coi là `ambiguous`
  - không nên ép giữ mọi sample
  - có thể cần một nhánh `discard / review / keep`

## Trang 7
**Highlight**
- Phần thực nghiệm bắt đầu.
- Họ train cả `3-way classifier` và `binary classifier`.
- TRUE benchmark được dùng để đo khả năng factual consistency trên dữ liệu unseen.
- GNLI vượt MNLI trên tất cả bộ test trong TRUE.
- Trung bình:
  - hơn MNLI `8.58%` với T5-small
  - hơn MNLI `6.88%` với T5-large
  - hơn MNLI `2.96%` với T5-XXL
- GNLI cũng vượt các lựa chọn mạnh trước đó như ANLI/WANLI trên trung bình.

**Comment tiếng Việt**
- Đây là bằng chứng mạnh nhất cho luận điểm “synthetic data đúng cách giúp generalization”.
- Điểm quan trọng với proposal của bạn:
  - đừng chỉ đo accuracy trên test split cùng kiểu dữ liệu
  - nên có ít nhất một đánh giá theo kiểu unseen / cross-domain / hard split

## Trang 8
**Highlight**
- Table 5 cho kết quả chi tiết trên từng tập của TRUE benchmark.
- GNLI đứng đầu hoặc gần đứng đầu ở rất nhiều ô, nhất là với model nhỏ và vừa.
- Trang này cũng mở đầu cho câu hỏi: cần bao nhiêu synthetic data là đủ.
- Họ thử train với nhiều kích thước GNLI khác nhau.

**Comment tiếng Việt**
- Trang này cho bạn một ý rất thực dụng: không phải cứ synthetic càng nhiều càng tốt vô hạn.
- Trong proposal của bạn, có thể thêm câu hỏi nghiên cứu kiểu:
  - dịch bao nhiêu sample là đủ?
  - thêm bao nhiêu synthetic Vietnamese sample thì bắt đầu bão hòa?
- Đây là một hướng ablation rất hợp lý.

## Trang 9
**Highlight**
- Table 6 đo cross-dataset performance giữa:
  - MNLI
  - ANLI
  - WANLI
  - GNLI
- Kết luận:
  - mỗi dataset vẫn có style riêng
  - model thường mạnh nhất trên test set cùng kiểu dữ liệu với tập train
- Tuy vậy, GNLI vẫn cạnh tranh tốt và khi cộng với dataset khác thì thường giúp cải thiện.
- Phần kết luận nhấn mạnh:
  - cân bằng theo domain
  - cân bằng theo length
  - cân bằng theo label
  giúp model domain-general hơn.
- Phần limitation:
  - không release dataset
  - cần nhiều bước LLM nên tốn compute hơn
  - premise có thể chứa thông tin hư cấu
  - mới chỉ làm trên tiếng Anh

**Comment tiếng Việt**
- Đây là trang cực hợp với đề tài của bạn.
- Vì sao?
  - nó nói thẳng rằng `data distribution matters`
  - tức là chỉ dịch sang tiếng Việt thôi chưa đủ, bạn còn phải kiểm soát phân phối dữ liệu tiếng Việt sau dịch
- Phần limitation cũng giúp bạn viết proposal trung thực hơn:
  - pipeline nhiều bước sẽ tốn compute
  - bản dịch có thể vẫn mơ hồ
  - hiệu quả trên tiếng Việt là câu hỏi thực nghiệm, chưa thể mặc định

## Trang 10
**Highlight**
- Chủ yếu là phần references.

**Comment tiếng Việt**
- Không có đóng góp kỹ thuật mới ở trang này.
- Có thể bỏ qua khi đọc nhanh.

## Trang 11
**Highlight**
- Tiếp tục references.
- Có các citation liên quan đến:
  - WANLI
  - debiasing NLI
  - synthetic data generation

**Comment tiếng Việt**
- Nếu bạn viết related work, đây là nơi gợi lại các paper nên trích cùng chủ đề.
- Nhưng bản thân trang này không có nội dung method mới.

## Trang 12
**Highlight**
- Vẫn là references.

**Comment tiếng Việt**
- Không cần phân tích sâu.

## Trang 13
**Highlight**
- Appendix:
  - seed examples dùng để prompt
  - running time
  - hyper-parameters cho prompt tuning và T5 fine-tuning
- Prompt-tuning FLAN-PaLM 540B khá tốn tài nguyên:
  - 256 TPU v4
  - khoảng 110 giờ

**Comment tiếng Việt**
- Đây là trang giúp bạn tránh ảo tưởng triển khai.
- Nếu proposal của bạn làm trong điều kiện tài nguyên hạn chế, không nên bê nguyên setup của họ.
- Bài học thực tế:
  - mình có thể mượn ý tưởng pipeline
  - nhưng phải đơn giản hóa implementation cho phù hợp nguồn lực

## Trang 14
**Highlight**
- Appendix A liệt kê seed texts theo domain và độ dài.
- Ví dụ các domain:
  - news headlines
  - shopping reviews
  - wikipedia
  - movie reviews

**Comment tiếng Việt**
- Đây là chỗ rất hay để học cách khởi tạo domain coverage.
- Nếu bạn muốn dịch dataset NLI sang tiếng Việt rồi còn mở rộng thêm, bạn có thể bắt chước cách nghĩ:
  - chuẩn bị một danh sách `domain buckets`
  - sau đó đo dataset của mình đang thiếu bucket nào

## Trang 15
**Highlight**
- Bảng hyper-parameters tốt nhất cho:
  - binary models
  - 3-way models
- Có cấu hình riêng theo:
  - T5 small
  - T5 large
  - T5 XXL
  - từng loại dataset train

**Comment tiếng Việt**
- Trang này hữu ích nếu bạn muốn tái lập tương đối trung thực thực nghiệm.
- Với proposal của bạn, nó chủ yếu có giá trị tham khảo cách setup thí nghiệm, không phải điểm học thuật cốt lõi.

## Chốt nhanh cho đề tài của bạn
Nếu rút từ paper này ra các ý thật sự nên dùng cho research của bạn, mình chốt 4 ý:

1. Đừng chỉ dịch dữ liệu. Hãy kiểm soát phân phối sau dịch theo `domain + label + premise length`.
2. Đừng chỉ đo điểm tổng. Hãy đo khả năng generalize trên các nhóm unseen hoặc hard split.
3. Synthetic/generative bước bổ sung chỉ nên dùng để lấp các vùng coverage còn thiếu.
4. Pipeline mạnh là pipeline có `quality control`, không phải pipeline generate thật nhiều.

## Đề xuất áp dụng trực tiếp
Với scope hiện tại của bạn, bản áp dụng hợp lý nhất là:

- lấy `SNLI/MNLI/XNLI` làm nguồn
- dịch sang tiếng Việt bằng Generator
- cho nhiều Validator chấm lại nhãn trên bản tiếng Việt
- theo dõi agreement / label drift
- chia và phân tích dữ liệu theo:
  - domain
  - premise length
  - reasoning phenomena nếu làm thêm được
- chỉ generate thêm cho những nhóm còn thiếu hoặc drift nhiều
