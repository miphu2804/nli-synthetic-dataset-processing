# NLI Synthetic Data Pipeline

![Hình 1. Pipeline tổng quát](/Users/miphu/.codex/generated_images/019e6d60-76bf-7520-8a2f-6641c30b220e/ig_01344286f0388718016a17ef34ce648191b413e2993d2dc24c.png)

*Hình 1. Pipeline tổng quát để tạo synthetic data cho NLI từ dữ liệu có sẵn.*

## 1. Mục tiêu của đề tài

Hướng phù hợp nhất cho đề tài này là cải thiện dữ liệu NLI trước, sau đó mới benchmark các base model và enhanced model trên dữ liệu gốc, dữ liệu synthetic và một tập hard cases riêng. Nói cách khác, trọng tâm giai đoạn đầu chưa phải là sửa kiến trúc model, mà là xây dựng được một pipeline biến đổi dữ liệu đủ chặt chẽ: biết biến đổi từ đâu, biến đổi theo quy tắc nào, kiểm tra lại nhãn ra sao, và làm thế nào để synthetic data thực sự giúp model học suy luận thay vì chỉ học mẹo bề mặt.

Nếu chỉ tăng số lượng mẫu một cách đại trà, mô hình có thể đạt điểm cao hơn nhưng chưa chắc hiểu quan hệ suy luận tốt hơn. Vì vậy, giá trị của hướng làm này nằm ở chỗ dữ liệu mới phải vừa đa dạng, vừa có kiểm soát, vừa có cơ chế xác minh đủ chặt để tránh kéo thêm nhiễu vào quá trình huấn luyện.

## 2. ViLegalNLI cho mình học được gì

Paper **ViLegalNLI** không đi theo hướng quen thuộc là chỉ dịch dữ liệu NLI từ tiếng Anh sang tiếng Việt rồi giữ nguyên nhãn. Điểm đáng học nhất của paper này nằm ở chỗ tác giả xây dựng dữ liệu bằng một quy trình bán tự động nhưng có kiểm soát. Cụ thể, họ chọn premise từ văn bản pháp luật, dùng LLM để sinh hypothesis theo những quy tắc định trước, sau đó kiểm định lại nhãn bằng nhiều model khác nhau, rồi còn kiểm tra artifact để giảm tình trạng model học shortcut.

Bỏ phần domain legal sang một bên, cấu trúc của pipeline này rất đáng tham khảo cho bài toán NLI tổng quát. Ý chính không phải là sinh thêm thật nhiều câu, mà là sinh câu mới theo quan hệ suy luận có chủ đích, rồi chỉ giữ lại những mẫu đã đi qua bước xác minh đủ chặt. Đây chính là điểm có thể tái sử dụng cho ViNLI, ViANLI, XNLI hoặc các bộ translated từ SNLI và MNLI.

## 3. Minh chứng rằng paper dùng pipeline biến đổi có kiểm soát

Trong phần mô tả phương pháp, paper nêu khá rõ rằng ViLegalNLI được xây dựng bằng ba thành phần chính: `controlled hypothesis generation`, `cross-model validation` và `artifact mitigation`. Điều này quan trọng vì nó cho thấy dữ liệu không được tạo ngẫu nhiên. LLM chỉ đóng vai trò sinh các giả thuyết mới theo khung đã thiết kế, còn quyết định giữ hay loại mẫu phải đi qua bước kiểm định chéo.

Một chi tiết rất đáng chú ý là ở **Bảng 6**: paper liệt kê trực tiếp các **generation rules** cho hai phía nhãn. Với **Entailment**, tác giả dùng các phép biến đổi như:

- chuyển đổi chủ động - bị động nhưng giữ nguyên nghĩa (**active-passive transformation**)
- thay thế thực thể bằng tham chiếu pháp lý tương đương (**equivalent legal reference substitution**)
- cải biên giữa danh ngữ và mệnh đề (**noun phrase-clause reformulation**)
- viết lại điều kiện nhưng vẫn giữ nguyên logic (**conditional reformulation**)
- thay đổi số lượng theo cách tương đương (**equivalent quantity modification**)
- mở rộng độ phức tạp câu nhưng không đổi nghĩa (**complexity expansion without semantic change**)
- suy ra hệ quả logic (**logical consequence derivation**)
- áp dụng quy tắc từ tổng quát đến cụ thể (**general-to-specific rule application**)
- liên kết với điều khoản liên quan mà không đổi nội dung suy luận (**related provision linking without semantic shift**)

Với **Non-entailment**, paper dùng các biến đổi như:

- tạo mâu thuẫn về cấu trúc (**structural contradiction**)
- thay đổi thực thể, thời gian hoặc hành động (**entity, temporal, or action alteration**)
- tạo bất nhất ngữ nghĩa (**semantic inconsistency introduction**)
- thêm điều kiện mâu thuẫn (**conflicting condition insertion**)
- sửa giá trị số (**numerical value alteration**)
- tạo lập luận không hợp lệ (**invalid reasoning construction**)
- thêm giả định không được hỗ trợ (**unsupported assumption insertion**)
- áp dụng sai quy tắc pháp lý tổng quát (**misapplication of general legal rules**)
- nối sang điều khoản không liên quan (**irrelevant provision linking**)
- tạo phát biểu độc lập, không thể suy ra từ premise (**independent statement generation**)

Nhìn từ góc độ xây dựng dữ liệu, đây chính là một pipeline biến đổi trên dữ liệu có sẵn: bắt đầu từ premise, sinh ra hypothesis mới theo từng nhóm quy tắc, sau đó kiểm tra lại nhãn bằng nhiều model và tiếp tục lọc artifact. Vì vậy, paper này là một bằng chứng khá mạnh để lập luận rằng hướng biến đổi có kiểm soát cộng với xác minh nhiều tầng là hoàn toàn khả thi cho NLI tiếng Việt.

## 4. Cách áp dụng ý tưởng đó cho đề tài của mình

Nếu chuyển ý tưởng của ViLegalNLI sang bài toán NLI tổng quát, có thể bắt đầu từ các bộ dữ liệu đã có sẵn trên thị trường như ViNLI, ViANLI, XNLI hoặc các bản dịch của SNLI và MNLI. Thay vì dùng toàn bộ dữ liệu một cách thụ động, nên chọn ra các cặp premise-hypothesis có chất lượng tốt làm seed pairs. Đây nên là những mẫu mà premise đủ thông tin, hypothesis rõ nghĩa và nhãn tương đối chắc chắn.

Từ seed pairs đó, bước tiếp theo là áp dụng các controlled transformations. Mỗi phép biến đổi nên đi kèm với một giả thuyết nghiên cứu rõ ràng về việc nhãn có thể thay đổi thế nào. Ví dụ, thêm phủ định thường có xu hướng đẩy một mẫu từ entailment sang contradiction; thay đổi lượng từ có thể làm quan hệ suy luận yếu đi thành neutral; đổi thực thể hoặc đổi số liệu thường tạo ra contradiction hoặc ít nhất là làm mất quan hệ entailment ban đầu.

Sau khi sinh ra mẫu mới, không nên tin hoàn toàn vào nhãn do quy tắc suy ra hoặc do LLM tự gán. Vẫn cần một bước xác minh nhãn. Cách làm hợp lý là dùng hai hoặc ba teacher model để kiểm định lại, sau đó chỉ giữ những mẫu có majority agreement. Những mẫu mà các model bất đồng nhưng vẫn có vẻ hợp lý không nhất thiết phải bỏ đi ngay; có thể tách chúng thành một hard set riêng để dùng trong giai đoạn huấn luyện sau hoặc dùng như tập đánh giá độ bền của mô hình.

Cuối cùng, giống như ViLegalNLI, nên có thêm một bước giảm artifact. Nếu một số token hoặc pattern trong hypothesis quá dễ gợi nhãn, model có thể đạt điểm cao nhưng không thực sự suy luận. Khi đó, cần chạy hypothesis-only baseline hoặc phân tích token-label correlation để tìm ra các shortcut, rồi viết lại hypothesis ở những mẫu quá lộ tín hiệu.

## 5. Ví dụ dễ hiểu cho pipeline biến đổi

![Hình 2. Ví dụ biến đổi nhãn](/Users/miphu/.codex/generated_images/019e6d60-76bf-7520-8a2f-6641c30b220e/ig_01344286f0388718016a17ef7f785c81918c61139810f180b0.png)

*Hình 2. Ví dụ đơn giản về cách một chỉnh sửa nhỏ có thể làm đổi nhãn NLI.*

Ví dụ thứ nhất là phép thêm phủ định. Giả sử có premise: **“Nam đã hoàn thành báo cáo.”** Hypothesis gốc là **“Nam đã làm xong báo cáo.”**, nhãn là **Entailment**. Nếu sửa hypothesis thành **“Nam chưa làm xong báo cáo.”**, quan hệ suy luận thay đổi ngay lập tức. Trong trường hợp này, nhãn hợp lý sẽ chuyển thành **Contradiction**. Điểm hay của ví dụ này là chỉ cần sửa một chi tiết rất nhỏ, nhưng tác động logic lại rõ ràng.

Ví dụ thứ hai là thay đổi lượng từ. Premise là **“Tất cả sinh viên đã nộp bài trước hạn.”** Nếu hypothesis là **“Một số sinh viên đã nộp bài trước hạn.”** thì đây vẫn là **Entailment**, vì nếu tất cả đã nộp thì đương nhiên tồn tại một số người đã nộp. Nhưng nếu đảo ngược theo hướng từ **“một số”** thành **“tất cả”**, quan hệ này không còn chắc nữa, và nhãn có thể rơi về **Neutral** hoặc **Contradiction** tùy premise cụ thể.

Ví dụ thứ ba là thay đổi số liệu. Premise: **“Có 3 sinh viên đạt điểm tuyệt đối.”** Hypothesis gốc: **“Có 3 sinh viên đạt điểm tuyệt đối.”**, nhãn **Entailment**. Nếu đổi hypothesis thành **“Có 5 sinh viên đạt điểm tuyệt đối.”**, nhãn hợp lý sẽ chuyển sang **Contradiction**. Đây là một dạng biến đổi đơn giản nhưng rất hữu ích vì nhiều model vẫn dễ bị đánh lừa khi bề mặt câu gần như giữ nguyên.

## 6. Ba hướng mở rộng có thể phát triển thành contribution

### 6.1. Label-Transition-Guided Minimal Edit

Ý tưởng ở đây là không để LLM sinh dữ liệu quá tự do, mà chỉ cho phép sửa rất ít chi tiết trong hypothesis theo một danh sách phép biến đổi đã định nghĩa trước. Mỗi phép biến đổi đi kèm một quy tắc chuyển nhãn dự kiến. Điểm mạnh của hướng này là nhãn mới không phụ thuộc hoàn toàn vào trực giác của LLM, nên dễ kiểm soát hơn và cũng dễ trình bày thành contribution học thuật hơn.

### 6.2. Teacher-Disagreement Curriculum Selection

Thông thường, khi các model bất đồng nhau về nhãn, người ta xem đó là nhiễu rồi loại bỏ. Nhưng có thể nhìn ngược lại: chính những mẫu gây bất đồng đó lại phản ánh vùng mà model hiện tại còn yếu. Vì vậy, có thể chia synthetic data thành clean set và hard set, huấn luyện theo curriculum, tức là cho model học từ phần sạch trước rồi mới sang phần khó. Hướng này có ý nghĩa vì nó tận dụng disagreement như một tín hiệu hữu ích thay vì coi đó chỉ là lỗi.

### 6.3. Phenomenon-Coverage-Guided Generation

Vấn đề phổ biến của synthetic data là sinh rất nhiều nhưng phân bố hiện tượng ngôn ngữ lại lệch: có quá nhiều mẫu dễ, nhưng thiếu phủ định, lượng từ, điều kiện, thời gian, nhân quả hoặc coreference. Nếu gắn tag hiện tượng cho từng mẫu, sau đó chỉ sinh thêm ở những vùng còn thiếu coverage, tập dữ liệu cuối cùng sẽ cân bằng hơn và giá trị đánh giá cũng cao hơn. Hướng này phù hợp nếu muốn nhấn mạnh rằng chất lượng và độ bao phủ của dữ liệu quan trọng hơn số lượng tuyệt đối.

## 7. Hướng benchmark sau khi chốt pipeline dữ liệu

![Hình 3. Thiết kế benchmark](/Users/miphu/.codex/generated_images/019e6d60-76bf-7520-8a2f-6641c30b220e/ig_01344286f0388718016a17efce739881918dea9ff3464cb1b3.png)

*Hình 3. Cách tổ chức benchmark để so sánh mô hình nền và mô hình tăng cường.*

Sau khi có pipeline dữ liệu ổn định, phần benchmark nên được tổ chức theo hướng dễ so sánh. Có thể chọn một nhóm base models như **mBERT, XLM-R, PhoBERT, viBERT** hoặc **CafeBERT**. Sau đó, với mỗi backbone, nên so sánh ít nhất hai setting: một setting chỉ fine-tune trên dữ liệu gốc, và một setting fine-tune trên dữ liệu gốc cộng dữ liệu synthetic. Nếu muốn đi xa hơn, có thể thêm một setting thứ ba là curriculum training, tức là train trên clean set trước rồi mới tiếp tục trên hard set.

Phần đánh giá cũng không nên dừng ở một test set duy nhất. Ít nhất nên có ba mặt đánh giá: kết quả trên dữ liệu gốc để xem mô hình có giữ được năng lực cơ bản hay không; kết quả trên tập augmented để xem synthetic data có giúp học thêm hay không; và kết quả trên hard split riêng để kiểm tra model có thực sự cải thiện khả năng suy luận hay chỉ học thêm pattern mới.

## 8. Kết luận ngắn

Nếu viết bài theo hướng này, lập luận trung tâm sẽ khá rõ: thay vì chỉ mở rộng dữ liệu NLI bằng dịch máy hoặc generate tự do, bài làm đề xuất một quy trình biến đổi có kiểm soát trên dữ liệu sẵn có, kết hợp quy tắc chuyển nhãn, xác minh bằng nhiều teacher model và lọc artifact để tạo ra synthetic data hữu ích hơn cho huấn luyện và đánh giá. Điểm này vừa bám sát tinh thần của ViLegalNLI, vừa mở ra chỗ đứng riêng cho bài toán NLI tiếng Việt.

## 9. Tài liệu tham khảo

1. ViLegalNLI: *Natural Language Inference for Vietnamese Legal Texts*. PDF: <https://arxiv.org/pdf/2605.00116>
2. XNLI: *Evaluating Cross-lingual Sentence Representations*. ArXiv: <https://arxiv.org/abs/1809.05053>
3. Self-Instruct: *Aligning Language Models with Self-Generated Instructions*. ArXiv: <https://arxiv.org/abs/2212.10560>
4. Adversarial NLI: *A New Benchmark for Natural Language Understanding*. ArXiv: <https://arxiv.org/abs/1910.14599>
5. Syntactic Data Augmentation Increases Robustness to Inference Heuristics. ACL Anthology: <https://aclanthology.org/2020.acl-main.212/>
