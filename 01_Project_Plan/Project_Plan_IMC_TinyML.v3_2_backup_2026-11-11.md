> **Trạng thái thực thi mới nhất — 23/10/2026:** Xem [README hiện hành](../README.md),
> [báo cáo G8](../02_Research/G8_deliverables.md) và
> [lộ trình khi chưa có phần cứng](../06_FPGA/HARDWARE_ROADMAP.md).
> Các phần kế hoạch bên dưới là baseline thiết kế lịch sử; trạng thái “đề xuất”
> không phủ nhận các đợt G2–G8 đã thực thi. Chưa có calibration hoặc bằng chứng
> hoàn thành mục tiêu nghiên cứu/đủ điều kiện nộp bài.

# KẾ HOẠCH NGHIÊN CỨU: RECAP-CIM

## Recovery-Aware Fused Mapping for Intermittent TinyML on Volatile SRAM Compute-in-Memory

**Tên tiếng Việt:** Đồng tối ưu ánh xạ và phục hồi suy luận TinyML trên SRAM-CIM khi nguồn điện gián đoạn.

| Thông tin | Nội dung |
|---|---|
| Phiên bản | 3.2 — rà soát tính nhất quán trước triển khai |
| Ngày cập nhật | 14/10/2026 |
| Nguồn lực hiện có | Máy tính để huấn luyện và mô phỏng; chưa giả định FPGA, PDK, giấy phép EDA hoặc ngân sách tape-out |
| Loại nghiên cứu | Phương pháp ánh xạ tự động và đồng thiết kế phần cứng/phần mềm, được đánh giá bằng mô phỏng có căn cứ và kiểm chứng RTL |
| Ứng dụng chính | Keyword spotting với DS-CNN INT8 |
| Mục tiêu công bố | Một bài nghiên cứu có phản biện tại hội nghị/tạp chí IEEE phù hợp với mức bằng chứng đạt được |
| Trạng thái | Đề xuất nghiên cứu; chưa có kết quả hiệu năng được xác minh |

> Hướng mới đề xuất là lựa chọn đồng thời cách chia phép tính, tái sử dụng trọng số và trạng thái cần lưu để giảm chi phí phục hồi của SRAM-CIM sau mất nguồn. Tính mới là giả thuyết cần kiểm tra bằng khảo sát đầy đủ và thực nghiệm; không tuyên bố "first", không cam kết được nhận bài, không ghi mục tiêu như kết quả đã đạt.

---

## 1. Tóm tắt và quyết định định hướng

SRAM-CIM có thể giảm một phần di chuyển dữ liệu khi suy luận. Tuy nhiên, SRAM mất nội dung khi mất nguồn hoàn toàn. Trọng số thường trú trong mảng, activation, partial sum và trạng thái bộ điều khiển có thể phải được nạp hoặc tính lại. Vì vậy, ánh xạ tối ưu cho nguồn liên tục chưa chắc tối ưu khi nguồn gián đoạn.

Đề tài tập trung vào một tình huống cụ thể: thực hiện cặp **depthwise convolution (DW) → requantization/activation → pointwise convolution (PW)** của DS-CNN trên một hệ thống dùng SRAM-CIM cho PW và datapath số cho DW. Khi nguồn xuống thấp, hệ thống phải lựa chọn giữa lưu đầu ra DW để khôi phục nhanh hoặc bỏ đầu ra DW và tính lại từ đầu vào bền vững. Quyết định này phụ thuộc kích thước tensor, mức tái sử dụng, tiến độ PW, trọng số còn trong SRAM và chi phí bộ nhớ không mất dữ liệu (NVM).

**Giả thuyết trung tâm:** Đồng tối ưu điểm lưu trạng thái, thứ tự và kích thước tile, với chi phí nạp lại trọng số được mô hình hóa rõ ràng, có thể giảm năng lượng để hoàn thành suy luận so với ánh xạ CIM thông thường ghép thêm checkpoint theo lớp hoặc theo tile cố định.

Kế hoạch cơ sở sử dụng máy tính: benchmark thật, mô hình INT8 chính xác theo bit, simulator theo sự kiện/chu kỳ, thuật toán ánh xạ và RTL bộ điều khiển phục hồi. Không đặt chế tạo chip là điều kiện để hoàn thành đề tài. Các kết luận về SRAM-CIM vật lý phải giới hạn theo dữ liệu macro và mức kiểm chứng có được.

### 1.1 Vì sao chọn hướng này?

| Hướng | Đánh giá | Quyết định |
|---|---|---|
| SRAM-CIM + INT8 + TinyML nói chung | Đã có nhiều công trình; khó bảo vệ tính mới chỉ bằng tổ hợp này | Không dùng làm đóng góp trung tâm |
| Thiết kế cell analog/ADC mới | Có thể có đóng góp mạch, nhưng cần PDK và kiểm chứng transistor/layout | Để ngoài phạm vi cơ sở |
| Điều chỉnh số tile theo năng lượng | Đã có hướng thích nghi mức song song như Viadotto [R3] | Dùng làm đối chứng khi phù hợp |
| Đồng tối ưu phục hồi và ánh xạ DW–PW trên SRAM-CIM dễ mất dữ liệu | Có cơ chế cụ thể, thí nghiệm được với nguồn lực hiện có, có khả năng tạo khác biệt | Hướng được chọn; kiểm tra tính mới ở G1 |

### 1.2 Ranh giới phạm vi

- Một kiểu số học chính: INT8 weight/activation, tích lũy INT32 và quy tắc requantization cố định.
- Một đóng góp phương pháp chính: recovery-aware mapper, đi kèm bộ điều khiển thực hiện quyết định đã sinh.
- Hai workload cho bài đầy đủ: DS-CNN KWS và một mạng depthwise-separable thứ hai có dữ liệu thật.
- Không thêm on-chip learning, early exit hoặc precision thích nghi vào bài cơ sở.
- Không giả định SRAM giữ trọng số qua mất nguồn; retention chỉ là một biến thể đánh giá.
- Không khẳng định perpetual/always-on batteryless KWS nếu chưa đánh giá cả thu âm và tiền xử lý.

---

## 2. Khoảng trống nghiên cứu và kiểm tra tính mới

### 2.1 Các nghiên cứu gần nhất

| Công trình | Điều đã có | Hệ quả cho RECAP-CIM |
|---|---|---|
| PSCNN, ISCAS 2022 [R1] | SRAM-CIM cho KWS, lập trình và tối ưu thực thi mạng nhị phân | Không tuyên bố SRAM-CIM KWS là mới; không so TOPS/W nhị phân trực tiếp với INT8 |
| KWS với in-SRAM computing và on-chip learning, TVLSI 2022 [R2] | KWS, mô hình nhận biết IMC, bù sai số và học trên chip | Không lấy QAT, KWS hoặc học trên chip làm khác biệt chung |
| Viadotto, ACM TECS 2025 [R3] | CIM trên CRAM không mất dữ liệu, mức song song thích nghi với nguồn | **Quan trọng:** Viadotto dùng CRAM (không mất dữ liệu) → không cùng problem domain với volatile SRAM. So sánh chỉ ở mức mapping strategy |
| CHRYSALIS, ISCA 2024 [R4] | Công cụ đồng thiết kế năng lượng, phần cứng suy luận và dataflow | Không tuyên bố đồng tối ưu năng lượng/dataflow hoặc tìm tile tối ưu là mới |
| Chime, IEEE TMSCS 2016 [R5] | Đặt checkpoint để giảm chi phí tính lại, có thích nghi với năng lượng | Cần đọc full text để xác định phạm vi mô hình trạng thái và trọng số; không mặc định việc thiếu mô hình SRAM-CIM trong một công trình là bằng chứng tính mới toàn lĩnh vực |
| FreeML, 2024 [R6] | Suy luận thích nghi năng lượng và tiết kiệm bộ nhớ trên hệ thống batteryless | Không thêm early exit rồi xem đó là đóng góp mới |
| FERMI-ML, 2025 [R7] | Macro SRAM cho TinyML và precision cấu hình được, đánh giá post-layout | Macro CIM/TinyML có thể làm nền tảng; không lấy số macro làm số toàn hệ thống |

Đây là khảo sát định hướng, không phải khảo sát đầy đủ chứng minh tính mới. Tên tuổi công trình không thay thế cho việc đọc phương pháp, thuật toán và mô hình chi phí của chúng.

### 2.2 Phát biểu tính mới dự kiến (cần xác minh ở G1)

> RECAP-CIM khảo sát việc đồng lựa chọn cấu hình tile DW–PW, trạng thái trọng số trong SRAM, trạng thái trung gian cần lưu hoặc tính lại, và thứ tự tái sử dụng trọng số trên SRAM-CIM dễ mất dữ liệu; mục tiêu là giảm chi phí hoàn thành suy luận sau các lần mất nguồn mà giữ nguyên kết quả INT8.

**Điểm khác biệt dự kiến cần xác minh ở G1:**

| So sánh | Chime [R5] | Viadotto [R3] | RECAP-CIM (dự kiến) |
|----------|-------------|---------------|----------------------|
| **Xét trạng thái trọng số trong SRAM** | Cần xác minh | Không (CRAM) | Có (cần xác minh) |
| **DW–PW fusion structure** | Cần xác minh | Cần xác minh | Có (cần xác minh) |
| **Đồng tối ưu tile + recovery policy** | Cần xác minh | Cần xác minh | Có (cần xác minh) |
| **Weight reload cost trong decision** | Cần xác minh | Cần xác minh | Có (cần xác minh) |
| **Chi phí ghi vs recovery phân biệt** | Cần xác minh | Cần xác minh | Có (cần xác minh) |

> **Lưu ý quan trọng:** Bảng trên là "dự kiến" — cần xác minh bằng đọc full text của các công trình trước khi khẳng định. "Khác với X" ≠ "chưa từng được công bố".

**Ba thành phần cần được chứng minh cùng nhau (sau G1):**

1. **Mô hình chi phí có trạng thái cư trú trọng số:** phân biệt trọng số đang có trong SRAM, trọng số phải nạp do đổi tile và trọng số phải nạp do mất nguồn.
2. **Lựa chọn trạng thái phục hồi theo cấu trúc DW–PW:** xác định khi nào lưu activation DW là rẻ hơn tính lại; tính cả chi phí đọc đầu vào bền vững, nạp trọng số và lưu partial sum PW.
3. **Mapper tạo phương án thực thi hợp lệ:** sinh tile, thứ tự vòng lặp, điểm commit và recovery descriptor; bộ điều khiển thực thi được, đầu ra khớp reference sau power failure.

Double buffering, CRC, checkpoint và fusion là kỹ thuật đã biết. Vai trò của chúng là thực hiện phương pháp đúng; không mặc định tính chúng là đóng góp mới riêng.

### 2.3 G1 — mốc bắt buộc xác minh tính mới ở tuần 4

- Đọc khoảng 20–30 công trình sát nhất; ưu tiên full text và tài liệu/mã nguồn của tác giả.
- Tìm các từ khóa: intermittent SRAM-CIM; recovery-aware mapping; checkpoint/recomputation; fused depthwise-pointwise; volatile weight reload; NVM traffic; intermittent inference dataflow.
- Bổ sung công trình mới đến thời điểm chuẩn bị nộp.
- **Lập bảng từng quyết định của thuật toán** (state, action, transition cost), đối chiếu với Chime, Viadotto, CHRYSALIS và các công trình gần hơn được tìm thấy. Mỗi nhận xét "X chưa có" phải dẫn đến trang/công thức cụ thể trong paper gốc.
- Tách rõ "công trình không báo cáo tính năng" với "công trình không có tính năng"; không suy luận vắng mặt từ abstract.
- Nếu tổ hợp quyết định đã được công bố hoặc khác biệt chỉ là đổi tên, phải sửa vấn đề nghiên cứu trước khi triển khai lớn.

**Điều kiện qua G1:** có một phát biểu khác biệt kỹ thuật rõ ràng, một baseline gần nhất và một thí nghiệm có thể bác bỏ hoặc xác nhận lợi ích của khác biệt đó.

### 2.4 Song song: Chọn hardware configuration (tuần 2-4)

**Ưu tiên cao:** Việc chọn SRAM-CIM macro và NVM ảnh hưởng trực tiếp đến kết luận SAVE_DW vs REPLAY_DW. Thực hiện song song với G1.

**Deliverable tuần 4:**
- Một SRAM-CIM macro có dữ liệu: throughput, precision, compute energy, weight loading energy, loading latency
- Một NVM có dữ liệu: read/write energy, write endurance, persistence latency
- Bảng tham số với nguồn và nhãn `measured`/`post-layout`/`reported`/`assumed`

**Nếu không tìm được dữ liệu đáng tin:**
- Giới hạn miền tham số dựa trên công nghệ (ví dụ: NOR flash vs FRAM vs MRAM)
- Báo sensitivity trên miền rộng
- Không dùng số năng lượng tuyệt đối làm kết luận chính

---

## 3. Câu hỏi nghiên cứu, giả thuyết và tiêu chí thành công

| Câu hỏi | Giả thuyết cần kiểm tra | Phép kiểm tra |
|---|---|---|
| RQ1: Ánh xạ tối ưu cho nguồn liên tục mất hiệu quả bao nhiêu khi SRAM mất trọng số? | Chi phí nạp lại và lưu trạng thái làm thay đổi lựa chọn tile/dataflow | Đo breakdown và đổi thứ hạng mapping theo cùng supply trace |
| RQ2: Lưu hay tính lại trung gian DW trong điều kiện nào có lợi? | Tồn tại miền chi phí mà mỗi lựa chọn thắng; luôn lưu hoặc luôn tính lại đều có trường hợp kém | Sweep kích thước tensor, NVM cost, SRAM size và tiến độ PW |
| RQ3: Đồng tối ưu hai quyết định có tốt hơn tối ưu từng quyết định riêng? | Mapper kết hợp cho lợi ích vượt quá một thành phần đơn lẻ | Ablation với cùng hardware budget và cùng arithmetic |
| RQ4: Phục hồi có bảo toàn kết quả và tiến độ không? | Với input bền vững và commit hợp lệ, đầu ra INT8 khớp reference bất kể vị trí mất nguồn | Fault injection có hệ thống; mô hình trạng thái; RTL trace comparison |
| RQ5: Lợi ích có bền vững trước sai số mô hình năng lượng? | Xu hướng không chỉ tồn tại ở một bộ tham số thuận lợi | Tham số có nguồn, validation tách riêng, sensitivity và corner cases |

### 3.1 Tiêu chí nội bộ — không phải kết quả hoặc yêu cầu cố định của IEEE

- Kết quả sau phục hồi khớp theo bit với reference INT8 trong tất cả test đã thực hiện; không chỉ kiểm tra nhãn phân loại.
- Metric chính là `E_completed = E_load,total / N_completed`, với tử số tính mọi năng lượng thực tế trong khoảng đánh giá, kể cả các lần thử thất bại và tác vụ chưa hoàn thành. Định nghĩa đầy đủ và cách xử lý mẫu chưa hoàn thành ở mục 7.6 là quy tắc duy nhất dùng trong mọi thí nghiệm.
- Mục tiêu cải thiện ban đầu: giảm ít nhất 20% `E_completed` so với baseline thích nghi gần nhất trên test traces. Đây là mốc nội bộ để xem xét tiếp tục, không phải kết quả đã đạt hoặc điều kiện nhận bài.
- Chỉ kết luận cải thiện năng lượng với mức hoàn thành tương đương khi cả completion rate và tỷ lệ đúng hạn của A không thấp hơn B quá `delta = 0.05`, tức **5 điểm phần trăm tuyệt đối**. Ví dụ, 80% so với 75% nằm ở biên dung sai; không được gọi hai tỷ lệ này là bằng nhau.
- Độ trễ p95 được định nghĩa trên mọi input ở mục 7.6. Nếu p95 không hữu hạn, báo rõ hạn chế; không dùng phép so sánh `infinity <= infinity` để kết luận không tăng độ trễ. Không kết luận tốt hơn toàn diện khi chỉ thỏa tiêu chí năng lượng/completion.
- Báo cáo từng thành phần đánh đổi, khoảng tin cậy và trường hợp không cải thiện. Ngưỡng 20%/5 điểm phần trăm phải được chốt trước tuning, không sửa sau khi thấy test results.
- Overhead trực tuyến được báo riêng bằng cycles/decision, J/decision, dung lượng descriptor và area khi có flow phù hợp. Mốc tham khảo 10% cho energy/area chỉ áp dụng khi tử và mẫu cùng đơn vị, cùng phạm vi khối; không so thời gian mapper ngoại tuyến với inference energy.
- Không đánh đổi accuracy bằng precision/early exit trong bài cơ sở. Độ chính xác phụ thuộc mô hình INT8 được chọn, không gán trước 94%.
- Công cụ phải chạy được trên ít nhất hai workload và nhiều chế độ năng lượng cho bản journal đầy đủ. Một bài ngắn có thể chỉ dùng KWS nhưng kết luận phải giới hạn tương ứng.

---

## 4. Hệ thống và phương pháp được đề xuất

### 4.1 Kiến trúc nghiên cứu

```mermaid
flowchart LR
    M[Model INT8 và cấu hình phần cứng] --> C[Mapper ngoại tuyến]
    C --> D[Tile và recovery descriptors]
    P[Trace nguồn và mô hình tụ] --> S[Bộ điều khiển thực thi]
    D --> S
    N[NVM: input, model, checkpoints] <--> S
    S --> W[SRAM-CIM cho pointwise và FC]
    S --> V[Datapath số cho depthwise]
    V --> A[Buffer activation và partial sum]
    W <--> A
    A --> O[Output được commit]
```

Datapath DW thông thường là lựa chọn ban đầu để tránh giả định DW luôn tận dụng tốt mảng CIM. Thử DW trên CIM chỉ là cấu hình so sánh nếu macro và mapping hỗ trợ.

**Phân biệt mức mô hình:** SRAM-CIM trong simulator là backend có interface, timing và cost model được mô tả. Mã Verilog nhân/cộng quanh SRAM hoặc FPGA BRAM chỉ chứng minh hành vi thực thi. Chỉ gọi triển khai là SRAM-CIM vật lý khi có cấu trúc memory-compute được kiểm chứng phù hợp.

### 4.2 Không gian quyết định

Với mỗi cặp DW–PW, mapper xét:

- Kích thước tile không gian `T_h × T_w`, kể cả halo đầu vào DW.
- Khối kênh đầu vào `T_ci` và khối kênh đầu ra `T_co`.
- Thứ tự duyệt kênh và tile không gian: ảnh hưởng tái sử dụng weight và activation.
- Biên fusion: giữ trung gian DW trong SRAM, hoặc materialize vào NVM ở một ranh giới được chọn.
- **Trạng thái trọng số:** chi tiết theo mục 4.4.1
- Policy phục hồi `SAVE_DW` hoặc `REPLAY_DW` tại các biên đã được mapper xác nhận hợp lệ.
- Granularity commit của đầu ra/partial sum PW; không đổi thứ tự toán học nếu việc đổi gây khác kết quả requantization hoặc overflow.

Các lựa chọn bị ràng buộc bởi SRAM, NVM bandwidth, năng lượng khả dụng, độ rộng accumulator và tính hợp lệ của dependency. Policy trực tuyến chỉ chọn trong tập descriptor hợp lệ đã sinh ngoại tuyến.

### 4.3 Mô hình năng lượng để ra quyết định

Với một chu kỳ nguồn đang hoạt động, không giả định có thể biết trước lần mất nguồn tiếp theo:

\[
E_{cap}(t)=\frac{1}{2}C\max\left(0,V(t)^2-V_{off}^2\right).
\]

Năng lượng ở tải phải tính hiệu suất chuyển đổi, năng lượng khởi động và sai số cảm biến. Điều kiện admission bảo thủ cho một đơn vị tiến độ:

\[
E_{unit}(d,r)+E_{commit}(d)+E_{margin}\le E_{available}(t).
\]

Ở đây `d` là descriptor, `r` là trạng thái trọng số cư trú; `E_unit` bao gồm đọc input, nạp weight, DW, PW, xử lý số và leakage. Không cộng năng lượng tương lai chưa thu được vào bảo đảm an toàn. Kết quả thu hoạch được trong lúc chạy vẫn được đưa vào mô phỏng nguồn thực tế.

**Hai quyết định độc lập:** `save_z` cho biết có lưu activation DW, `keep_ps` cho biết có lưu partial sum PW mới. Policy `q = (save_z, keep_ps)` có tối đa bốn tổ hợp hợp lệ; mapper phải kiểm tra dependency trước khi chọn. `SAVE_DW`/`REPLAY_DW` chỉ mô tả quyết định đầu tiên, không mặc định tiến độ PW được giữ hay bị bỏ.

| Thành phần | `save_z = 1` | `save_z = 0` | Quy tắc |
|---|---|---|---|
| Ghi DW | Ghi đúng vùng `Z_DW` cần phục hồi | Không ghi DW mới | Tính cả transaction overhead |
| Đọc hoặc tính lại DW sau mất nguồn | Đọc vùng đã commit; tính lại vùng còn thiếu nếu cần | Đọc anchor bền vững, nạp weight còn thiếu và tính lại DW | Phải đủ activation cho mọi đóng góp PW cần replay |
| Ghi PS của PW | Phụ thuộc `keep_ps` | Phụ thuộc `keep_ps` | Quyết định này không phụ thuộc riêng vào SAVE/REPLAY DW |
| Khôi phục PS của PW | Đọc PS đã commit nếu có | Đọc PS đã commit nếu có | PS và offset phải cùng generation |
| Tính lại PW | Phần đóng góp chưa được checkpoint bảo toàn | Phần đóng góp chưa được checkpoint bảo toàn | Không tính lại output đã commit |

Ví dụ, PW đã cộng 16 kênh nhưng checkpoint gần nhất chỉ bảo toàn 8 kênh. Nếu không lưu PS mới, sau reboot khôi phục PS/offset của checkpoint cũ và tính lại kênh 9–16. Chỉ bắt đầu từ kênh 1 khi không có PS bền vững trước đó. Đọc đủ `Z_DW` không khôi phục được PS PW đã mất.

**Chi phí ghi khi chuẩn bị checkpoint:**

\[
E_{stage}(s,q)=save_z\,E_{write}(Z_q)+keep_{ps}\,E_{write}(PS_q)+E_{metadata+commit}(s,q).
\]

`Z_q` và `PS_q` là các payload mới thực sự phải ghi; checkpoint đã có có thể được tham chiếu nếu còn hợp lệ. Khi `keep_ps = 1`, **cả SAVE_DW và REPLAY_DW đều chịu chi phí ghi PS**. Khi không có payload mới, metadata/commit vẫn có thể phát sinh; không mặc định tổng chi phí ghi bằng 0.

**Chi phí phục hồi thực tế:**

\[
E_{recovery}=E_{boot}+E_{read\ metadata}+E_{restore\ payloads}+E_{weight\ reload}+E_{DW\ replay}+E_{PW\ replay}.
\]

Mỗi thành phần tính một lần: `restore payloads` là đọc PS/Z đã commit và vận chuyển tương ứng; `weight reload` gồm đọc NVM, vận chuyển và nạp weight vào bank; `DW/PW replay` chỉ là compute cho đóng góp phải tính lại. Nếu năng lượng operator đã bao gồm memory access, phải tách hoặc loại phần trùng trước khi cộng.

Một ước lượng cục bộ có thể dùng để xếp hạng policy là:

\[
\widehat J(s,q)=E_{stage}(s,q)+p_{loss}(s,q,\Delta_q)\,\widehat E_{recovery}(s,q).
\]

Đây là ước lượng cho một cửa sổ với tối đa một lần mất nguồn, **không phải hàm mục tiêu đầy đủ của toàn suy luận**. Nó chỉ áp dụng khi checkpoint ứng viên đã được publish thành công. Nếu mất nguồn trong lúc ghi, recovery dùng checkpoint cũ và chi phí ghi dở vẫn được tính trong simulator. Các lần boot/replay thất bại lặp lại phải được mô phỏng theo sự kiện, không được rút gọn thành một tích `p_loss × E_recovery`.

So sánh hai policy phải bắt đầu từ cùng trạng thái/anchor và cùng lượng công việc cần hoàn thành. Nếu chúng bảo toàn tiến độ khác nhau, phải tính đủ phần công việc mất và replay; không loại các chi phí đó dưới nhãn "chi phí chung".

### 4.4 Thuật toán chi tiết

#### 4.4.1 Trạng thái và chuyển trạng thái

```text
s = (input_id, model_hash, descriptor_id,
     progress_v, progress_d, z_valid_v, ps_valid_v,
     weight_banks, anchor_refs, committed_record,
     pending_txn, power_state, energy_bin, source_features)
```

| Thành phần | Định nghĩa |
|---|---|
| `input_id`, `model_hash` | Nhận dạng input/model; mọi payload phải gắn với đúng hai giá trị này |
| `descriptor_id` | Xác định block, tile không gian, halo, khối kênh, thứ tự duyệt và cấu hình số học |
| `progress_v` | Tiến độ mới còn trong SRAM; không được coi là durable progress |
| `progress_d` | Tiến độ từ checkpoint cuối đã publish; gồm output frontier và offset đóng góp PW cho từng khối đầu ra |
| `z_valid_v`, `ps_valid_v` | Vùng Z/PS hợp lệ trong SRAM, kèm tensor/tile ID và offset; giá trị số thực nằm trong memory model |
| `weight_banks` | Mỗi bank có `(weight_tile_id, layout_id, valid_region, capacity_bytes)`; chỉ dùng vùng đã nạp hoàn tất |
| `anchor_refs` | Reference tới input DW bất biến trong NVM, phạm vi không gian/kênh và dependency; tính cả halo |
| `committed_record` | Generation cuối hợp lệ, các reference/range của Z/PS và `progress_d` tương ứng |
| `pending_txn` | Generation ứng viên, payload references và pha ghi; chưa có hiệu lực phục hồi |
| `power_state`, `energy_bin` | OFF/BOOTING/RUNNING/WAITING và lượng năng lượng quan sát được; admission dùng giá trị bảo thủ, không chỉ nhãn NOMINAL/MARGINAL |
| `source_features` | Đặc trưng nguồn quan sát được từ quá khứ/hiện tại; không chứa tương lai của test trace |

Simulator giữ cả nội dung SRAM/NVM và transaction status. Trạng thái rút gọn cho mapper chỉ hợp lệ khi vẫn phân biệt được chi phí/next states cần thiết; state truncation không được làm thay đổi semantics phục hồi. Bản đầu dùng đóng góp PW theo **prefix kênh liên tiếp cho từng khối đầu ra** để đơn giản hóa kiểm tra; mở rộng thứ tự kênh chỉ khi có mô tả coverage chính xác.

Ví dụ, bank chứa `W_tile_2` và bank chứa `W_tile_3` đều có thể được gọi là PARTIAL, nhưng bước cần `W_tile_2` có reload cost khác nhau. Vì vậy ALL/PARTIAL/NONE chỉ là nhãn thống kê, không đủ làm khóa trạng thái của mapper.

| Action/event | Điều kiện và cập nhật |
|---|---|
| `READ_INPUT(region)` | Anchor hoặc payload nguồn phải bền vững và đúng ID; đọc hoàn tất mới đánh dấu vùng SRAM hợp lệ; không làm một anchor mới trở thành durable |
| `LOAD_WEIGHT(tile, bank)` | Kiểm tra capacity/layout, thay thế theo policy; cập nhật valid region sau transfer hoàn tất; tính cả NVM read và SRAM load |
| `COMPUTE_DW(region)` | Input/weight đủ và admission đạt; tạo Z đã requantize/activate đúng reference trong SRAM; chỉ cập nhật `progress_v`/`z_valid_v` |
| `COMPUTE_PW(region)` | Z và weight đủ, offset đúng; cộng đúng prefix đóng góp vào PS trong SRAM; chỉ cập nhật `progress_v`/`ps_valid_v` |
| `SAVE_DW(region)` | Ghi Z vào vùng copy-on-write của `pending_txn`; **chưa cập nhật** `committed_record` hoặc `progress_d` |
| `SAVE_PW_PS(region, offset)` | Ghi PS và offset tương ứng vào `pending_txn`; chưa coi chúng là checkpoint hợp lệ |
| `COMMIT_CHECKPOINT` | Chờ payload bền vững, ghi metadata rồi publish atomic marker; chỉ sau bước này cập nhật `committed_record`/`progress_d` |
| `COMMIT_OUTPUT(region)` | PW đủ đóng góp và xử lý số hoàn tất; ghi output copy-on-write rồi publish record; chỉ sau commit mới tăng output frontier |
| `WAIT_CHARGE` | Không có action hợp lệ với năng lượng hiện tại; thời gian/nguồn/leakage vẫn được mô phỏng, không được dừng đồng hồ đánh giá |
| `POWER_LOSS` (event) | Mất nguồn hoàn toàn xóa SRAM, weight tags, `progress_v` và pending runtime state; record đã commit vẫn giữ; payload ghi dở không có hiệu lực |
| `BOOT_RECOVER` | Đủ năng lượng boot; kiểm tra record hợp lệ gần nhất, phục hồi descriptor/`progress_d`; mọi SRAM-valid flag và weight tag vẫn rỗng cho tới restore/load thật |
| `RESTORE_PAYLOAD(region)` | Chỉ đọc payload mà record hợp lệ tham chiếu; đánh dấu SRAM-valid sau read hoàn tất, khôi phục PS cùng offset |

Replay DW/PW sử dụng chính các action compute trên; ledger gắn nhãn replay cho phần công việc phải làm lại. `POWER_LOSS` là sự kiện của source/fault model, không phải action do mapper chọn. Nếu boot/restore cũng bị gián đoạn, phục hồi lần sau vẫn bắt đầu từ record hợp lệ gần nhất.

Thay đổi kích thước/thứ tự tile chỉ được phép tại biên có descriptor và durable dependencies tương thích. Không diễn giải PS của tile cũ thành PS của tile mới. Nếu checkpoint không có PS mới, `progress_v` sau restore quay về offset của PS cũ hoặc về 0 nếu chưa có PS bền vững.

#### 4.4.2 Ledger chi phí thực tế

| Thành phần | Khi tính năng lượng |
|---|---|
| NVM read/write | Mỗi transaction thực sự đã thực hiện, kể cả ghi dở hoặc retry; tính page/erase/IO overhead theo backend |
| Weight load | Mỗi lần nạp vùng weight còn thiếu do đổi tile hoặc reboot; không charge toàn tile nếu backend hỗ trợ partial load và dữ liệu đủ căn cứ |
| DW/PW compute | Mỗi compute action, kể cả replay; tách memory access nếu đã tính trong dòng NVM/weight load |
| Metadata/commit | Khi ghi record/marker, không cộng một lần riêng cho mỗi payload nếu metadata được ghi chung |
| Boot/restore | Mỗi lần thực sự boot/read/restore; nếu mất nguồn giữa chừng, vẫn charge phần đã tiêu thụ |
| Controller/standby/leakage | Theo thời gian hoạt động và trạng thái nguồn; không cộng lại phần đã nằm trong profile whole-block |

Mỗi energy event có `input_id`, action ID, phase, byte/cycle count, đơn vị J và source parameter. Tổng ledger phải khớp tổng năng lượng lấy từ load model trong sai số số học/time step đã định trước. Xác suất chỉ dùng để dự đoán/ra quyết định; **không cộng thêm `p_loss × recovery_cost` vào ledger** đã mô phỏng recovery thật.

#### 4.4.3 Mô hình mất nguồn và tính nhân quả

Mất nguồn trong đánh giá chính được sinh bởi trace công suất thu hoạch **ghép với tiêu thụ thực tế, tụ và ngưỡng nguồn**. Thay đổi policy có thể thay đổi thời điểm mất nguồn; không dùng một failure rate cố định chung để thay thế cơ chế này.

Nếu dùng ước lượng cục bộ ở mục 4.3, định nghĩa:

\[
p_{loss}(s,q,\Delta_q)=P\left(\text{mất trạng thái SRAM trước lần sử dụng phụ thuộc tiếp theo}\mid s,q,\Delta_q,\text{history quan sát được}\right).
\]

- `Delta_q` là thời lượng cửa sổ cụ thể cho descriptor/policy, có đơn vị s; công bố rõ điểm bắt đầu/kết thúc. Không trộn xác suất trong cửa sổ với số failure/giây.
- Ước lượng phải xét năng lượng hiện tại, thời lượng/mức tiêu thụ của action và lịch sử nguồn. Dùng cost model của action hiện tại là hợp lệ; dùng giá trị tương lai thật của test trace để chọn action là không hợp lệ.
- Fit và chọn hyperparameters trên training/validation traces; freeze estimator và policy trước test. Cập nhật online từ prefix đã quan sát chỉ được phép nếu quy tắc cập nhật đã chốt trước và baseline có thông tin tương đương.
- Khi thiếu dữ liệu estimator, dùng policy tĩnh/threshold được chọn trên training traces và gắn nhãn heuristic; không gán một average failure rate không rõ cửa sổ làm xác suất.
- Báo calibration và ablation nếu predictor được dùng. Không xem predictor là đóng góp mới riêng của bài cơ sở.
- Admission vẫn dùng năng lượng dự trữ bảo thủ, không thay thế bằng kỳ vọng có nhân xác suất. Nếu reserve đủ và cost bound chính xác trong mô hình lý tưởng, failure do cạn năng lượng **bên trong đơn vị đã admission** phải bằng 0. Power-off giữa các đơn vị/WAIT_CHARGE và fault bất ngờ được phân biệt rõ; không bịa thêm failure để tạo lợi ích.

#### 4.4.4 Thuật toán tối ưu và phạm vi bảo đảm

Với input arrivals và horizon đánh giá cố định như mục 7.6, mục tiêu trên training scenarios là:

\[
\min_{\pi\in\Pi_{causal}}\frac{\sum_{h\in H_{train}} w_h E_h(\pi)}{\sum_{h\in H_{train}} w_h N_{completed,h}(\pi)}.
\]

`w_h` là trọng số scenario chốt trước; `E_h` bao gồm toàn bộ năng lượng trong horizon, kể cả incomplete. Mẫu số bằng 0 là phương án không khả thi cho mục tiêu này. Tính ratio của các tổng như trên, không tự đổi thành trung bình các ratio. `Pi_causal` chỉ gồm policy dùng state/history có thể quan sát; training scenarios phục vụ đánh giá policy, không cho runtime đọc tương lai của scenario.

**Ràng buộc:**

1. SRAM và NVM đủ capacity, kể cả payload copy-on-write, halo, descriptor và checkpoint cũ còn sống.
2. Admission ở mục 4.3 đạt; dependency và transaction ordering ở mục 4.4.1/5.3 hợp lệ.
3. Output đã commit khớp INT8 reference; không cộng lặp hoặc bỏ đóng góp.
4. Completion rate và đúng hạn đạt các ngưỡng feasibility đặt trước từ baseline/tolerance ở mục 3.1, trên training scenarios; kiểm tra lại trên test và báo nếu không đạt.

Forward progress là tính chất cần kiểm tra **có điều kiện**: phải tồn tại các khoảng năng lượng đủ cho boot, một đơn vị tiến độ hợp lệ và commit. Không biến câu "số incomplete có giới hạn" thành bảo đảm vô điều kiện. Các trace không đủ năng lượng vẫn được báo kết quả thất bại.

**Lộ trình giải khả thi:**

1. Sinh tập descriptor/policy hữu hạn với tile, thứ tự duyệt và lựa chọn `(save_z, keep_ps)`; lọc dependency/footprint/admission.
2. Trên microbenchmark, liệt kê **policy nhân quả** trong tập đã định, chạy cùng training scenarios và chọn phương án khả thi có ratio nhỏ nhất. Nghiệm tối ưu chỉ trong tập policy được liệt kê và cùng cost/source model.
3. Với mạng lớn, dùng DP hoặc beam search để sinh/prune ứng viên rồi đánh giá đầy đủ bằng coupled-source simulator. Hành động được chọn từ state quan sát được; không được dùng branch tương lai của test trace để chọn action.
4. DP giá trị kỳ vọng, nếu triển khai, cần transition model `P(s'|s,a)` đã xác định. Một bước Bellman cho objective cộng có dạng `V_j(s) = min_a [c(s,a) + sum_s' P(s'|s,a) V_{j+1}(s')]`. Ratio objective cần bước xử lý riêng, chẳng hạn tìm kiếm hệ số `lambda` cho cost `E - lambda*N_completed` (lambda có đơn vị J/suy luận) và kiểm tra feasibility; không tuyên bố Bellman với cost chỉ có E đã giải chính xác bài toán ratio.
5. State truncation và beam pruning là heuristic trừ khi có chứng minh bảo toàn tối ưu. Đo khoảng cách với nghiệm policy nhỏ, mapper time/memory và beam-width sensitivity; chọn phương pháp tại G2.

| Bài toán được tính | Độ phức tạp với transition/cost O(1) |
|---|---|
| Liệt kê chuỗi action độ dài tối đa H, branching A | Tăng theo hàm mũ, worst-case O(A^H) cho số chuỗi; chưa tính chi phí chạy mỗi scenario |
| Liệt kê policy trên decision graph | Phụ thuộc số decision nodes và branching; phải báo số policy thực tế, không mặc định O(S^3) |
| Một lượt finite-horizon DP, S states, A actions, tối đa B successor states/action | O(H*S*A*B); cộng overhead xử lý ratio/constraint nếu có |
| Beam search, width k, A ứng viên/action, giữ top k bằng sort | O(H*k*A*log(k*A)); cộng chi phí simulator/cost evaluation khi khác O(1) |

H là số bước quyết định, không phải số giây của trace. Chuỗi action biết trước trace có thể dùng làm **oracle**, phải gắn nhãn và không gọi là policy triển khai được. Mapper ngoại tuyến báo giây và peak RAM trên máy tính. Runtime descriptor selection báo cycles/J/memory trên thiết bị, không so trực tiếp hai loại chi phí.

#### 4.4.5 Quy tắc số học

- Giữ đúng zero point, scale, bias, rounding, saturation và vị trí activation của mô hình reference.
- Fusion không được bỏ requantization giữa DW và PW.
- Ghi rõ INT8 signed/unsigned ở mọi interface; nếu bit-slicing bù hai, hệ số bit dấu phải được xử lý đúng.
- Chứng minh giới hạn tích lũy với số hạng lớn nhất; quy định overflow/accumulator width cho từng layer.
- Thay đổi vị trí checkpoint không được thay đổi trạng thái toán học. Đầu ra phục hồi phải khớp INT8 reference, không chỉ gần đúng.

---

## 5. Phục hồi đúng sau mất nguồn

### 5.1 Hai lựa chọn hợp lệ

**SAVE_DW:** Lưu trung gian DW cần cho phần PW chưa hoàn thành vào NVM. Lựa chọn `keep_ps` quyết định có lưu PS PW mới hay không; metadata phải khớp đúng payload và tiến độ thực sự bảo toàn. Sau reboot chỉ đọc Z/PS thuộc record đã publish.

**REPLAY_DW:** Không lưu trung gian DW. Sau reboot, đọc anchor input từ NVM, nạp trọng số DW, tính lại. Partial sum PW:
- **Giữ PW progress:** phải lưu partial sum PW (chi phí ghi tương đương SAVE_DW)
- **Không giữ PW progress:** tính lại PW từ đầu (chi phí tính lại có thể lớn)

**Quy tắc so sánh công bằng:** So sánh từ cùng trạng thái ban đầu và cùng công việc đích. Khi so riêng SAVE/REPLAY DW, giữ `keep_ps` và phạm vi PS giống nhau để tách tác động. Khi mapper xét cả bốn tổ hợp, tính đủ chi phí phục hồi khác nhau; không giả định tất cả tổ hợp giữ cùng tiến độ PW. Nếu không có PS mới đã commit, quay về PS/offset của checkpoint cũ, không dùng offset còn sót trong metadata ứng viên.

### 5.2 Đơn vị tiến độ và cấu trúc lưu bền vững

Checkpoint/commit record dự kiến gồm:

```text
generation, model_hash, input_id, descriptor_id,
block_id, tile_coordinates, channel_ranges,
z_payload_ranges[], ps_payload_ranges[], ps_ci_offsets[],
committed_output_frontier, recovery_policy,
anchor_references[], payload_references[], payload_lengths[],
layout_and_arithmetic_id, integrity_check, commit_marker
```

Record chỉ mô tả dữ liệu/tiến độ có thể khôi phục từ NVM, không lưu `ci_sram_valid` như một bảo đảm qua reboot. `ps_ci_offsets` đi cùng đúng PS payload và khối output; output frontier chỉ tăng sau commit output. SRAM-valid bitmap luôn rỗng ngay sau cold reboot và chỉ tăng sau restore/compute thật. Model/input/layout/arithmetic được nhận dạng riêng để không phục hồi nhầm dữ liệu.

Anchor và payload cũ phải bất biến trong khi còn dependency. `pending_txn` có thể tham chiếu payload cũ hợp lệ hoặc vùng mới copy-on-write; không được cập nhật record hiện hành chỉ vì một SAVE action đã ghi xong payload.

### 5.3 Giao thức commit

1. Tính toán vào buffer tạm; checkpoint/đầu ra đã commit vẫn bất biến.
2. Ghi payload mới vào vùng chưa được checkpoint hiện hành tham chiếu. Có thể dùng hai slot hoặc copy-on-write; tính đủ dung lượng và chi phí.
3. Chờ NVM xác nhận dữ liệu bền vững theo thứ tự ghi đã quy định.
4. Ghi metadata và cuối cùng publish một commit marker trong đơn vị ghi nguyên tử được backend bảo đảm.
5. Sau reboot, chỉ chọn generation có record hợp lệ và payload đã hoàn tất; bỏ bản ghi đang dở.
6. Chỉ thu hồi slot/anchor cũ khi checkpoint mới đã commit và không còn dependency tới dữ liệu cũ.

Giả định minimum atomic write unit và persistence ordering phải được công bố. CRC giúp phát hiện dữ liệu lỗi, không thay thế bảo đảm nguyên tử. Nếu backend không có atomic marker thích hợp, cần giao thức metadata bổ sung và kiểm chứng tương ứng.

### 5.4 Các bất biến cần kiểm chứng

- Output đã commit cho một `input_id` không bị đổi bởi replay.
- Checkpoint mới không phá dữ liệu mà checkpoint cũ còn cần.
- Partial sum và offset luôn tương ứng với cùng tập đóng góp; không bỏ sót hoặc cộng lặp.
- Payload staging chỉ trở thành trạng thái phục hồi sau atomic publish; failure trước publish luôn dùng record cũ.
- Cold reboot xóa mọi weight tag và SRAM-valid flag, kể cả các flag từng được ghi vào diagnostic log.
- Không phát `result_valid` khi còn đầu ra chưa commit.
- Power failure trong compute, DMA, payload write, metadata write hoặc commit đều phục hồi về một trạng thái hợp lệ.
- Forward progress chỉ được kết luận nếu có các khoảng nguồn đủ cho ít nhất một đơn vị tiến độ và commit; payload không thể lớn hơn năng lượng tối đa của tụ mà vẫn giả định hoàn tất.

---

## 6. Dữ liệu, benchmark và mô hình

### 6.1 Benchmark chính

**Keyword spotting:** sử dụng pipeline DS-CNN và Speech Commands của một phiên bản/commit cố định của MLPerf Tiny [R8]. Dùng mô hình INT8 reference khi phù hợp, tránh huấn luyện một mạng mới trước khi có baseline phần cứng đúng.

Ghi lại dataset version, danh sách lớp, chia train/validation/test, hash model, cách tiền xử lý, input shape thực tế, số MAC và dung lượng weight/activation. Không giữ các shape hoặc số MAC từ plan cũ nếu chưa kiểm tra model đã chọn. Dữ liệu tổng hợp chỉ phục vụ unit test, không phục vụ báo cáo accuracy KWS.

### 6.2 Workload thứ hai cho bài đầy đủ

Ưu tiên MobileNet nhỏ cho Visual Wake Words từ MLPerf Tiny [R8], vì có cặp DW–PW và footprint khác KWS. Chỉ chọn cấu hình có thể thực hiện dưới giới hạn bộ nhớ đã công bố. Nếu dùng width multiplier hoặc thay đổi model, gắn nhãn cấu hình nghiên cứu riêng, không nhận là kết quả MLPerf chính thức.

### 6.3 Phạm vi sensing và deadline

- Thí nghiệm cơ sở bắt đầu từ một input đã được capture và lưu bền vững; tính chi phí lưu/cấp input trong mức đánh giá tương ứng.
- Công bố riêng "inference-only" và "sensing + preprocessing + inference" nếu mức thứ hai có đủ dữ liệu để mô hình hóa.
- Với KWS, đo độ trễ từ timestamp của input. Một quyết định đúng nhưng đến sau deadline được tính là trễ.
- Không suy luận khả năng nhận wake word liên tục từ số suy luận offline/giây.

---

## 7. Phương pháp đánh giá với nguồn lực hiện có

### 7.1 Ba mức bằng chứng

| Mức | Việc thực hiện | Kết luận được phép |
|---|---|---|
| A — bắt buộc | INT8 reference, event/cycle simulator, trace nguồn, fault injection, mapper | Tính đúng trong mô hình và lợi ích theo các tham số/giả định được công bố |
| B — bắt buộc cho bài có tuyên bố phần cứng | RTL controller, traffic generator, backend functional model; đối chiếu chu kỳ/transaction; tổng hợp khi có flow/library phù hợp | Controller thực hiện được, overhead và timing trong phạm vi flow đã chạy |
| C — nâng cấp | FPGA, đo nguồn/NVM, custom macro SPICE/post-layout hoặc silicon khi có điều kiện | Chỉ thêm kết luận vật lý tương ứng với dữ liệu thực sự đo/mô phỏng |

Nguồn lực hiện tại ưu tiên A và B. Nếu B chưa tổng hợp được, không báo area/power ASIC. Flow tổng hợp standard cell của controller không xác minh năng lượng macro SRAM-CIM. Không đặt mặc định "65 nm, <2 mm², >5 TOPS/W".

### 7.2 Cost model và giới hạn độ tin cậy

- **Chọn macro digital SRAM-CIM có dữ liệu multi-bit đủ để xác định throughput, precision, compute energy và cách loading weight.** Việc chọn macro là deliverable tuần 4 (song song với G1), không giả định số đã có trong repo.
- **Chọn NVM cụ thể có dữ liệu read/write energy, latency, endurance, transaction granularity và persistence ordering.** FRAM, NOR flash hoặc MRAM là các ứng viên cần đối chiếu dữ liệu, không mặc định công nghệ nào có lợi cho policy đề xuất. Với flash, phải tính page program, erase, copy-on-write/garbage collection và atomicity theo backend được chọn.
- Mỗi tham số có đơn vị, phạm vi khối, công nghệ, nguồn và nhãn `measured`, `post-layout`, `reported` hoặc `assumed`.
- Không dùng efficiency binary để dự đoán INT8; không trộn energy macro với whole-chip power.
- Nếu paper không cung cấp weight-load energy hay NVM transaction cost, dùng khoảng giả định có giải thích và sensitivity, không ghi một giá trị duy nhất như số đo.
- Simulator phải tính mọi lần read/write/reload/commit, kể cả retry, boot, controller, leakage và dữ liệu bị bỏ sau failure.
- So sánh relative giữa policy trên cùng backend có thể kiểm chứng tốt hơn số năng lượng tuyệt đối; vẫn kiểm tra xem lợi ích có đổi dấu khi tham số thay đổi.
- Cross-check số chu kỳ/traffic với RTL ở các cấu hình nhỏ và tách validation cases khỏi cases dùng để fit cost model. Với năng lượng không có phép đo độc lập, ghi rõ chưa validate vật lý.

### 7.3 Mô hình nguồn

- Mô phỏng `V_on > V_off`, tụ, tổn hao chuyển đổi và brownout; xử lý nguồn ở bước thời gian đủ nhỏ để bắt các transaction. Chốt cùng initial capacitor state, initial NVM/model/input placement và cold/warm-start rule cho mọi baseline. Kiểm tra timestep convergence trước thí nghiệm chính.
- Sweep dung lượng tụ khởi đầu `10/47/100/470 µF` và công suất thu hoạch `10/30/100/300 µW`; đây là miền khảo sát đề xuất, không phải đặc tính hệ thống đã đo.
- Ba nhóm nguồn: steady/interruption-free; nguồn biến động tổng hợp; ít nhất một nhóm trace thực có nguồn gốc tái lập được cho bài journal đầy đủ.
- Tìm trace công khai phù hợp hoặc dữ liệu nguồn do tác giả công bố. Nếu không có trace thực, giới hạn tuyên bố vào simulated intermittent supply và ghi hạn chế đó.
- Supply trace giống nhau cho mọi phương pháp. Thời điểm mất nguồn phát sinh từ tiêu thụ năng lượng và mô hình tụ; không ép các phương pháp có cùng số failure trong thí nghiệm chính.
- Dùng outage sequence cố định riêng cho kiểm tra tính đúng/chi phí phục hồi, không thay thế đánh giá nguồn ghép với tải.

### 7.4 Baseline tối thiểu

| ID | Phương pháp | Mục đích |
|---|---|---|
| B0 | Conventional digital backend (non-CIM), chạy cả policy baseline và policy RECAP, cùng INT8/footprint được đối chiếu | Đối chứng backend cho phân tích tính đặc thù; không dùng một phép so tuyệt đối với B5 để quy lợi ích cho policy |
| B1 | SRAM-CIM với mapping tối ưu nguồn liên tục, checkpoint ở biên layer | Baseline thông thường |
| B2 | SRAM-CIM với checkpoint theo tile cố định, luôn lưu trạng thái còn sống | Tách lợi ích của granularity checkpoint |
| B3 | SRAM-CIM với energy-adaptive tile, không đồng tối ưu trạng thái DW và weight reload | Baseline thích nghi gần nhất trên cùng backend |
| B4 | Mapper/checkpoint theo chi phí từ phương pháp gần nhất có thể tái hiện | Đối chứng mạnh với prior art, chọn chính xác sau G1 |
| B5 | RECAP-CIM đầy đủ | Phương pháp đề xuất |
| O1 | Tối ưu vét cạn trên microbenchmark hoặc oracle biết trước trace | Upper bound; không coi là baseline triển khai được |

**Đối chứng backend × policy:** Chạy bốn cấu hình `(CIM, baseline policy)`, `(CIM, RECAP)`, `(digital, baseline policy)`, `(digital, RECAP)`. Tính cải thiện RECAP so với baseline **bên trong mỗi backend** rồi so hai mức cải thiện. So trực tiếp B0 với B5 đồng thời đổi backend và policy nên không tách được nguyên nhân. Giữ workload/source/memory constraints có thể đối chiếu và công bố khác biệt hardware cost. Nếu chưa có dữ liệu backend digital đủ đáng tin, không kết luận lợi ích đặc thù CIM.

Nếu policy cải thiện tương tự trên cả hai backend, có thể trình bày kết quả như một phương pháp intermittent mapping tổng quát được đánh giá trên SRAM-CIM; không suy luận rằng kết quả mất giá trị hoặc CIM không còn liên quan. Tên bài và phạm vi đóng góp phải phản ánh bằng chứng ở mục 10.1.

B4 không được bỏ chỉ vì B1/B2 dễ thắng. Nếu không tái hiện được một công trình, dùng implementation được mô tả rõ, ghi "inspired by"; không gọi nó là reproduction chính xác. Viadotto dùng NVM-CIM khác SRAM-CIM, nên chủ yếu so quyết định điều khiển trên backend chung, không ghép số throughput tuyệt đối từ hai công nghệ.

### 7.5 Ablation bắt buộc

1. Full mapper nhưng đặt chi phí reload weight bằng 0 trong quyết định; simulator vẫn tính reload thật.
2. Always-save DW so với always-replay DW và lựa chọn theo chi phí.
3. Mapping cố định + policy phục hồi; mapping thích nghi + policy phục hồi cố định; đồng tối ưu cả hai.
4. Fusion thông thường tối ưu cho nguồn liên tục so với fusion được chọn theo chi phí phục hồi.
5. Checkpoint toàn bộ trạng thái còn sống so với checkpoint tối thiểu hợp lệ.
6. Không gián đoạn, gián đoạn nhẹ/nặng và trường hợp nguồn không đủ để tiến độ; báo cáo overhead hoặc thất bại tương ứng.
7. **Backend × policy:** Bốn cấu hình ở mục 7.4 để tách lợi ích của policy khỏi khác biệt CIM/digital backend; báo cả điều kiện không thể đối chiếu.

### 7.6 Metrics và cách tổng hợp

**Khoảng đánh giá:** chốt `T_eval`, input IDs, arrival timestamps và deadline cho mọi baseline. Tất cả deadline của tập input đánh giá phải nằm trước hoặc tại `T_eval`; dừng phát input đủ sớm để có cùng thời gian quan sát. Không loại input khó/không hoàn thành sau khi đã thấy kết quả. Khi dùng trace thực ngắn, chọn tập input và horizon chung trước tuning.

\[
E_{completed}=\frac{E_{load,total}(0,T_{eval})}{N_{completed}},\qquad
Throughput=\frac{N_{completed}}{T_{eval}}.
\]

`E_load,total` bao gồm compute, mọi NVM transaction, weight load, boot/restore/replay, controller và leakage/standby tại tải trong phạm vi hệ thống đã khai báo. Tính cả hoạt động của những input chưa hoàn thành hoặc thất bại, không chỉ input completed. Conversion loss phía harvester/capacitor được báo riêng nếu tử số ở tải; không trộn energy domains hoặc coi năng lượng thu hoạch được là năng lượng tiêu thụ. Cold-start/model-load/preprocessing inclusion phải giống nhau giữa baseline và RECAP.

**Định nghĩa trạng thái cuối của input — ba nhóm không giao nhau:**

- `completed`: output cuối đã commit và khớp INT8 reference trước hoặc tại `T_eval`, có timestamp hoàn thành.
- `failed`: bị drop hoặc kết thúc với output không hợp lệ/lỗi không khôi phục theo quy tắc chốt trước.
- `incomplete`: vẫn pending/running khi hết horizon, chưa thuộc hai nhóm trên.

`N_total = N_completed + N_failed + N_incomplete`. Một power failure giữa chừng **không tự biến input thành failed**; số power failures/restarts được đếm riêng. `completion_rate = N_completed/N_total`; `on_time_rate = N_completed_before_deadline/N_total`. Output đúng nhưng trễ được tính completed và không đúng hạn. Khi `N_completed = 0`, `E_completed` không xác định: báo "không hoàn thành", không dùng 0 J hay bỏ case.

**Độ trễ trên toàn tập input:**

\[
L_i=\begin{cases}
t_{complete,i}-t_{arrival,i}, & \text{input i completed},\\
+\infty, & \text{input i failed hoặc incomplete}.
\end{cases}
\]

Tính p95 bằng nearest-rank: phần tử thứ `ceil(0.95*N_total)` của danh sách `L_i` đã sắp tăng. Nếu phần tử đó là vô cực, báo **p95 không hữu hạn trong horizon**; không thay bằng thời gian còn lại tới `T_eval` như thể đã hoàn thành. Có thể báo thêm p95 có điều kiện trên completed, nhưng phải gắn nhãn và không dùng nó thay metric toàn tập.

**Quy tắc so sánh:** dùng `E_completed`, completion rate và đúng hạn cùng nhau. A có cải thiện năng lượng với mức hoàn thành tương đương khi cả hai mẫu số năng lượng dương, energy A thấp hơn B, `completion_rate(A) >= completion_rate(B)-0.05` và `on_time_rate(A) >= on_time_rate(B)-0.05`. Gắn rõ đây là non-inferiority tolerance 5 điểm phần trăm, không phải cùng completion rate.

Chỉ thêm kết luận "không tăng p95" khi cả hai p95 hữu hạn và `p95(A) <= p95(B)`. Nếu A hữu hạn và B không hữu hạn, báo cải thiện quan sát được; nếu cả hai không hữu hạn, không suy luận từ `infinity <= infinity`. Nếu A không hữu hạn nhưng B hữu hạn, không đạt tiêu chí độ trễ. Báo riêng trade-off và khoảng tin cậy, không gọi energy improvement là tốt hơn mọi mặt.

Với thí nghiệm một input outstanding, dùng các episode input/source/horizon giống nhau và reset state theo quy tắc đã chốt. Với luồng input, arrival schedule là cố định chung, queue/drop rule giống nhau; không phát input nhanh hơn chỉ vì một phương pháp hoàn thành sớm hơn rồi coi hai tập input là đồng nhất.

Báo thêm checkpoint bytes, NVM writes/erase, weight reload bytes, replay MACs, SRAM/NVM footprint và controller overhead. Nếu tổng hợp TOPS/W, ghi MAC=1 hay 2 operations, precision và energy scope; không dùng peak TOPS/W làm bằng chứng chính.

### 7.7 Số lần chạy và thống kê

- Ít nhất 3 nhóm trace nguồn; khởi đầu ít nhất 10 seed/trace tổng hợp độc lập cho mỗi cấu hình chính.
- Chia trace tuning/validation/test; policy không được chỉnh theo test traces.
- Báo từng trường hợp và paired improvement trên cùng trace; tổng hợp median hoặc geometric mean khi phù hợp.
- Khoảng tin cậy 95% bằng bootstrap theo trace/seed độc lập; không coi các inference liên tiếp trong một trace là mẫu độc lập.
- Fault injection: vét cạn vị trí failure trên microtile nhỏ ở mỗi pha commit; thêm ít nhất 1.000 lịch failure ngẫu nhiên có seed cho cấu hình lớn.
- Chạy sensitivity với NVM cost, load bandwidth, compute cost, leakage và safety margin; chọn miền từ nguồn dữ liệu, bổ sung stress case để kiểm tra giới hạn.

---

## 8. Kế hoạch triển khai trong repository

Các đường dẫn dưới đây là cấu trúc cần tạo hoặc cập nhật khi thực hiện, không phải các artifact đã tồn tại.

```text
02_Research/
  novelty_matrix.md           # Đối chiếu quyết định với prior art (state/action/cost)
  references.bib             # DOI và citation đã kiểm tra
  hardware_selection.md       # SRAM-CIM macro + NVM với dữ liệu
03_Architecture/
  recovery_spec.md           # Dependency, descriptor và commit protocol
  cost_model_schema.md      # Đơn vị, nguồn và phạm vi tham số
  algorithm_spec.md          # State, action, transition, cost function chi tiết
04_RTL/
  recovery_controller.sv     # Bộ điều khiển, không giả danh macro vật lý
  descriptor_engine.sv
  nvm_transaction_model.sv
05_Model_Training/
  export_reference_int8.py   # Model/dataset thật và golden tensors
09_Simulation/
  recap_simulator.py         # Nguồn ghép với tải, memory traffic, failure
  mapper.py                  # DP/beam search với state/action/cost rõ ràng
  fault_injection.py
  configs/                  # Model/backend/NVM/trace parameters
  traces/                   # Trace hoặc manifest tải trace + provenance
10_Experiments/
  manifests/                # Commit/hash/seed/config của từng run
  raw/                      # CSV/JSON gốc
  plots/                    # Figure tái sinh từ dữ liệu gốc
  reproduce.md
07_IEEE_Paper/
  recap_cim_paper.tex        # Chỉ đưa kết quả đã xác minh
```

### 8.1 Tận dụng và sửa phần cũ

- Lưu bản v1 và bản trước lần rà soát này (v3.1) trong các file backup hiện có; không mặc định các phiên bản trung gian đã được sao lưu nếu không có artifact tương ứng.
- Chương trình huấn luyện hiện dùng dữ liệu ngẫu nhiên: thay pipeline đánh giá bằng benchmark thật trước khi đưa accuracy vào bài.
- `imc_array.v` hiện là behavioral model: xác định lại vai trò backend, sửa lỗi bộ đếm và interface kết quả; kiểm chứng MVM trước khi dùng làm golden backend.
- `compare_results.py` và test-vector generator có thể tái sử dụng sau khi kiểm tra signedness, requantization và tiêu chí so sánh.
- Assertions hiện có chưa phải bằng chứng formal đã chạy; bổ sung properties cho commit/replay và lưu kết quả tool thật.
- ASIC Tcl hiện là flow tham khảo; không coi việc có script là đã chạy synthesis/PnR.
- README, architecture specification và bài LaTeX cũ còn chứa kết quả/tuyên bố chưa xác minh. Khi bước vào triển khai, cập nhật đồng bộ chúng theo plan v3.2; hiện không dùng các con số đó làm baseline hoặc kết quả.

### 8.2 Môi trường công cụ

Python cho reference/simulator/mapper; framework ML phù hợp model reference; Verilator hoặc Icarus Verilog cho RTL; Yosys cho tổng hợp logic khi backend hỗ trợ; SymbiYosys hoặc tool tương đương cho properties nhỏ nếu sẵn có. Ghi phiên bản, dependency lock và cách chạy trên máy cá nhân; WSL/Linux là tùy chọn triển khai, không giả định đã cài.

Không dùng tool thương mại hoặc PDK chưa có quyền truy cập. Thông số macro được trích từ nguồn có thể kiểm tra; nếu có PDK sau này, tạo một nhánh đánh giá riêng và không trộn công nghệ với kết quả cơ sở.

---

## 9. Lộ trình 32 tuần và mốc quyết định

Tuần tính từ ngày bắt đầu triển khai được chốt. Lộ trình dự kiến cho một người làm nghiên cứu đều đặn trên máy tính; điều chỉnh sau hai tuần profiling. Mọi giai đoạn dưới đây cộng thành 32 tuần, không bao gồm chế tạo chip.

| Tuần | Công việc | Deliverable/mốc quyết định |
|---|---|---|
| 1–4 | Đọc prior art, chốt khoảng trống, kiểm tra model KWS và môi trường + **chọn SRAM-CIM macro và NVM** | **G1:** novelty matrix (state/action/cost), research question, baseline gần nhất, **hardware selection với dữ liệu** |
| 5–8 | INT8 reference, state/action/commit spec, cost ledger, backend macro, simulator nguồn/memory cơ sở | G2: golden tensors, microtile recovery đúng, baseline breakdown; chọn phương pháp mapper |
| 9–12 | Thử SAVE_DW/REPLAY_DW và mapping trên microbenchmark; mapper bản đầu | G3: lợi ích hoặc giới hạn có thể tái lập; chọn tiếp tục/sửa hướng |
| 13–16 | Hiện thực protocol đã chốt trong RTL controller; so transaction với simulator | G4: correctness/fault tests đạt, invariants được kiểm tra |
| 17–20 | Tích hợp mapper/runtime, KWS end-to-end, baseline thích nghi và overhead | G5: kết quả trên test traces, không chỉ traces dùng tuning |
| 21–24 | Workload thứ hai, trace thực nếu có, sensitivity và toàn bộ ablation | G6: đánh giá đa workload; phân tích trường hợp thua |
| 25–28 | Tái lập, cross-validation mô hình, kiểm tra novelty mới, figure và bảng | Bộ artifact chạy lại được; lựa chọn venue theo bằng chứng |
| 29–32 | Viết bài tiếng Anh, review nội bộ, chỉnh sửa và chuẩn bị submission | G7: bản thảo đủ bằng chứng hoặc báo cáo rõ phần còn thiếu |

### 9.1 G1 — Novelty và Hardware Selection song song

**Deliverable 1: Novelty Matrix**
- Bảng đối chiếu từng quyết định (state, action, transition cost) với Chime, Viadotto, CHRYSALIS
- Mỗi nhận xét "X chưa có" phải dẫn đến trang/công thức cụ thể trong paper gốc
- Xác định điểm khác biệt dự kiến: weight residency + DW-PW structure
- Phát biểu tính mới đã được cập nhật dựa trên xác minh

**Deliverable 2: Hardware Selection**
- Một SRAM-CIM macro: throughput, precision, compute energy, weight loading
- Một NVM: read/write energy, latency, endurance
- Bảng tham số với nguồn và độ tin cậy

**Điều kiện qua G1:** Cả hai deliverable phải hoàn thành. Nếu không tìm được hardware data đáng tin, phải giới hạn miền tham số rõ ràng.

### 9.2 G3 — quyết định có đáng tiếp tục không?

Trước khi đầu tư nhiều vào RTL, chạy benchmark nhỏ có cả weight reload và checkpoint. Nếu replay DW chỉ thắng khi đặt NVM write cost phi thực tế, hoặc tối ưu kết hợp không vượt baseline gần nhất, không mở rộng giả thuyết bằng số liệu thuận lợi. Điều chỉnh problem statement hoặc chuyển sang một kết quả hẹp hơn về miền lựa chọn policy nếu phân tích đó có tính mới đủ rõ.

### 9.3 Kết quả tối thiểu và kết quả nâng cấp

- **Kết quả tối thiểu có thể xem xét bài ngắn:** khác biệt kỹ thuật qua G1, KWS thật, baseline mạnh, simulator có nguồn tham số, recovery đúng, sensitivity và artifact tái lập. Khả năng nộp còn phụ thuộc chất lượng kết quả và scope venue.
- **Kết quả cho bản đầy đủ:** mapper tự động, hai workload, đánh giá trace chưa dùng tuning, cross-check RTL, model validation có căn cứ, overhead và toàn bộ ablation.
- **Nâng cấp khi có phần cứng:** đo NVM/nguồn, FPGA controller, macro SPICE/post-layout. Không đưa các việc này vào critical path hiện tại.

---

## 10. Định hướng công bố IEEE

Không có một ngưỡng TOPS/W, số trang hoặc tỷ lệ cải thiện chung bảo đảm "đạt chuẩn IEEE". Chọn venue theo đóng góp và bằng chứng, sau đó tuân thủ hướng dẫn tác giả tại thời điểm nộp.

| Venue | Vai trò trong kế hoạch | Điều kiện phù hợp |
|---|---|---|
| IEEE Embedded Systems Letters | Lựa chọn bài ngắn đầu tiên nếu kết quả tập trung | Một cơ chế rõ, đánh giá kỹ và artifact; tài liệu hiện tại quy định tối đa 4 trang, gồm references [R9] |
| IEEE TCAD | Mục tiêu bản đầy đủ, có yêu cầu nghiên cứu cao | Mapper/thuật toán đồng thiết kế thực sự mới, khảo sát đủ, validation mạnh và đánh giá mở rộng; scope bao gồm phương pháp mô hình hóa và HW/SW co-design [R10] |
| IEEE ISCAS | Lựa chọn khi đóng góp controller/kiến trúc mạch đã được kiểm chứng đủ | Paper phải phù hợp track của kỳ hội nghị, có kết quả thiết kế cụ thể và đánh giá circuit/system [R11] |
| IEEE TVLSI | Hướng nâng cấp nếu có bằng chứng triển khai sâu hơn | Microarchitecture, memory integration và đánh giá ở mức thiết kế thích hợp với scope [R12] |

**Khuyến nghị với nguồn lực hiện tại:** hướng tới kết quả tập trung đủ mạnh để cân nhắc ESL; xây dựng artifact theo mức đầy đủ để TCAD là mục tiêu nghiên cứu dài hơn. Không xem ESL là tự động dễ nhn hoặc TCAD làậ kết quả chắc chắn. Chốt một venue sau G6; kiểm tra deadline/format mới nhất, không đặt lịch nộp vào kỳ hội nghị đã qua.

Không dùng JSSC làm mục tiêu cơ sở khi chưa có đóng góp mạch và kiểm chứng phần cứng tương ứng. Không nộp cùng một bản thảo đồng thời cho nhiều venue. Nếu mở rộng bài hội nghị thành journal, xác định rõ phần mới và disclosure theo hướng dẫn nơi nộp.

### 10.1 Tên và luận điểm bài báo dự kiến

**Tên chính:** "RECAP-CIM: Recovery-Aware Fused Mapping for Intermittent TinyML on Volatile SRAM Compute-in-Memory".

**Tên thay thế nếu kết quả chủ yếu hỗ trợ phương pháp tổng quát:** "Recovery-Aware Mapping of Depthwise-Separable TinyML Inference under Intermittent Power". Chốt tiêu đề dựa trên mức validation backend và đối chứng backend × policy; kết quả policy hữu ích trên cả CIM và digital không tự động loại bỏ vai trò CIM khỏi bài, nhưng không đủ để tuyên bố cơ chế chỉ có lợi cho CIM.

**Luận điểm dự kiến:** **Trong miền điều kiện được đánh giá, việc đồng tối ưu DW–PW mapping và trạng thái phục hồi, với chi phí nạp lại weight được tính đúng, giảm chi phí hoàn thành suy luận mà giữ nguyên đầu ra INT8.** Chỉ thay phần định tính bằng số sau khi chạy thực nghiệm.

### 10.2 Bố cục và hình cần có

1. Introduction: vấn đề SRAM-CIM mất dữ liệu và một ví dụ mapping nguồn liên tục bị đổi thứ hạng.
2. Related work: đối chiếu với CIM KWS, intermittent mapping và checkpoint/recomputation.
3. System/problem model: cấu trúc DW–PW, source/NVM model, giới hạn số học và quyết định tối ưu.
4. Method: cost model, mapper, descriptor selection và commit protocol.
5. Validation/evaluation: reference, RTL cross-check, baseline mạnh, ablation, sensitivity và limitations.
6. Conclusion: chỉ tổng kết kết quả đã đo/mô phỏng, phạm vi tổng quát hóa và phần chưa kiểm chứng.

Hình dự kiến: architecture; hai recovery paths; breakdown weight-load/checkpoint/replay; heatmap miền SAVE_DW/REPLAY_DW; performance trên test traces; ablation; trade-off SRAM/NVM; mapping runtime và khoảng cách với oracle nhỏ. Mỗi hình phải sinh lại từ dữ liệu gốc.

---

## 11. Rủi ro và cách xử lý

| Rủi ro | Dấu hiệu | Cách xử lý |
|---|---|---|
| Ý tưởng trùng prior art | Baseline gần nhất đã có cùng quyết định và objective | Sửa hướng tại G1, không chỉ đổi tên framework |
| Chi phí recovery không đáng kể | Breakdown chủ yếu là compute và mọi policy tương đương | Báo miền không có lợi; chỉ tiếp tục nếu tồn tại vấn đề thực tế có nguồn tham số |
| Thiếu dữ liệu macro/NVM | Absolute energy dựa phần lớn vào giả định | Sensitivity, báo relative trong phạm vi model; nâng validation trước claim rộng |
| Replay làm sai INT8 | Bỏ requantization hoặc cộng lại partial sum | Golden tensors, offset invariant, test edge cases trước performance |
| Checkpoint không crash-safe | Failure giữa payload và metadata phá anchor cũ | Copy-on-write, atomic marker assumption, fault injection ở mọi pha |
| Fusion tăng reload/buffer | Weight reuse hoặc SRAM capacity kém đi | Cho mapper chọn fusion/không fusion; không ép fusion luôn tốt |
| Chỉ thắng baseline yếu | Không vượt adaptive mapper cùng backend | Tái hiện baseline gần nhất và ablation, điều chỉnh luận điểm |
| Runtime quá nặng | Descriptor selection tốn đáng kể năng lượng/area | Chuyển phần tìm kiếm offline, runtime dùng LUT/so sánh đơn giản |
| Không có trace thực | Đánh giá nguồn chỉ tổng hợp | Giới hạn claim; tiếp tục tìm trace công khai, không gọi nguồn tổng hợp là số đo |
| Không có FPGA/EDA | Không thể đo phần cứng | Hoàn thành A/B ở mức hỗ trợ được; chọn venue/claim đúng mức bằng chứng |
| Lợi ích không đặc thù SRAM-CIM | Policy có cải thiện tương tự trong cả hai backend của đối chứng 2×2 | Giới hạn claim theo bằng chứng; đóng góp vẫn có giá trị cho intermittent inference chung |

---

## 12. Điều kiện trước khi nộp bài

- [ ] Phát biểu đóng góp có khác biệt kỹ thuật so với prior art gần nhất (novelty matrix đã hoàn thành với dẫn chứng cụ thể).
- [ ] Novelty matrix được cập nhật gần ngày nộp; DOI/năm/tác giả đã kiểm tra từ full text.
- [ ] Hardware selection (SRAM-CIM macro + NVM) đã hoàn thành với dữ liệu có nguồn.
- [ ] Model/dataset thật, split độc lập và golden INT8 được lưu cùng hash.
- [ ] **Định nghĩa năng lượng thống nhất** được tuân thủ trong mọi thí nghiệm.
- [ ] Chi phí weight reload, checkpoint, replay, boot và leakage không bị bỏ sót hoặc đếm lặp.
- [ ] Phân biệt rõ chi phí ghi phát sinh trước failure và chi phí phục hồi chỉ khi failure.
- [ ] State machine cho một cặp DW-PW đã được xác định và kiểm chứng trên microbenchmark.
- [ ] Tất cả baseline dùng cùng hardware budget, input, nguồn và deadline rule.
- [ ] Fault tests và validation không có mismatch chưa giải quyết; báo rõ phạm vi chứng minh.
- [ ] Tham số reported/assumed và kết quả simulated/measured được phân biệt.
- [ ] Có baseline thích nghi gần nhất, ablation, sensitivity và trường hợp không hoàn thành.
- [ ] Đối chứng backend × policy (2×2) đã thực hiện với dữ liệu đủ căn cứ, hoặc claim được giới hạn rõ khi không thể đối chiếu; không quy khác biệt backend thành lợi ích policy.
- [ ] p95 của incomplete/failed và nhóm input đánh giá tuân theo mục 7.6; không loại năng lượng retry/incomplete khỏi tử số.
- [ ] Mọi SAVE action chỉ tạo payload staging; durable progress chỉ đổi sau atomic publish, kể cả PS và offset.
- [ ] Raw data, seed, configs và lệnh tái lập sinh được bảng/hình trong bài.
- [ ] Không còn số accuracy, energy, area hoặc TOPS/W không có nguồn artifact.
- [ ] Title/abstract giới hạn đúng loại bằng chứng; không tuyên bố chip hoặc always-on batteryless từ behavioral simulation.
- [ ] Format, disclosure và hướng dẫn tác giả mới nhất của venue đã được kiểm tra; phần nội dung AI hỗ trợ được khai báo khi venue yêu cầu [R9].

---

## 13. Tài liệu định hướng và nguồn kiểm tra

Các nguồn dưới đây là điểm xuất phát cho khảo sát. Thông tin công bố phải được kiểm tra lại trong `references.bib` trước khi nộp; số liệu paper không được chuyển thành số liệu của RECAP-CIM.

- **[R1]** S.-H. Kuo và T.-S. Chang, "PSCNN: A 885.86 TOPS/W Programmable SRAM-based Computing-In-Memory Processor for Keyword Spotting", ISCAS 2022. [Bản tác giả](https://arxiv.org/abs/2205.01569).
- **[R2]** Y.-H. Chiang, T.-S. Chang và S.-J. Jou, "A 14uJ/Decision Keyword Spotting Accelerator with In-SRAM-Computing and On Chip Learning for Customization", IEEE TVLSI, 2022. [Bản tác giả](https://arxiv.org/abs/2205.04665); [DOI](https://doi.org/10.1109/TVLSI.2022.3172685).
- **[R3]** K. Akhunov và cộng sự, "Adaptive Computing in Memory Meets Conventional Batteryless Platforms", ACM TECS, 2025. [DOI](https://doi.org/10.1145/3765623); [full text từ imec](https://imec-publications.be/server/api/core/bitstreams/d647c609-d6f6-4f7f-b851-f19a1cc1a2ff/content).
- **[R4]** X. Hou và cộng sự, "A Tale of Two Domains: Exploring Efficient Architecture Design for Truly Autonomous Things", ISCA 2024. [Thông tin từ HKUST](https://researchportal.hkust.edu.hk/en/publications/a-tale-of-two-domains-exploring-efficient-architecture-design-for/); [DOI](https://doi.org/10.1109/ISCA59077.2024.00022); [artifact của tác giả](https://zenodo.org/records/10982940).
- **[R5]** A. Mirhoseini và cộng sự, "Chime: Checkpointing Long Computations on Intermittently Energized IoT Devices", IEEE Transactions on Multi-Scale Computing Systems, 2016. [Thông tin công trình từ Microsoft Research](https://www.microsoft.com/en-us/research/publication/chime-checkpointing-long-computations-on-intermittently-energized-iot-device/); [full text từ nhóm tác giả](https://aceslab.org/w/Special%3Afilepath/Mirhoseini2016.pdf).
- **[R6]** "Memory-efficient Energy-adaptive Inference of Pre-Trained Models on Batteryless Embedded Systems", FreeML, 2024. [Bản tác giả](https://arxiv.org/abs/2405.10426).
- **[R7]** "FERMI-ML: A Flexible and Resource-Efficient Memory-In-Situ SRAM Macro for TinyML acceleration", 2025. [Bản tác giả và metadata](https://arxiv.org/abs/2511.12544).
- **[R8]** MLCommons, MLPerf Tiny. [Repository chính thức](https://github.com/mlcommons/tiny); [benchmark/models](https://github.com/mlcommons/tiny/blob/master/benchmark/README.md); [rules](https://github.com/mlcommons/tiny/blob/master/benchmark/MLPerfTiny_Rules.adoc).
- **[R9]** IEEE CEDA, IEEE Embedded Systems Letters. [Hướng dẫn tác giả](https://ieee-ceda.org/publication/esl/esl-author-instructions); [scope](https://ieee-ceda.org/publication/esl).
- **[R10]** IEEE CEDA, IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems. [Scope và submission links](https://ieee-ceda.org/publications/tcad).
- **[R11]** IEEE CASS, ISCAS. [Giới thiệu hội nghị từ IEEE CASS](https://ieee-cas.org/event/conference/2025-ieee-international-symposium-circuits-and-systems). Link này dùng xác nhận scope chung, không dùng deadline kỳ nộp tiếp theo.
- **[R12]** IEEE CASS, IEEE Transactions on Very Large Scale Integration Systems. [Aims & scope](https://ieee-cas.org/tvlsi-current-issue).

---

## 14. Bảng so sánh novelty dự kiến (Mục mới - cần xác minh ở G1)

> **Lưu ý:** Bảng này là "dự kiến" — cần xác minh bằng đọc full text của các công trình trước khi khẳng định.

### 14.1 So sánh với Chime [R5]

| Quyết định/thành phần | Chime | RECAP-CIM (dự kiến) | Cần xác minh |
|------------------------|-------|----------------------|---------------|
| **Checkpoint granularity** | Theo chunk cấu hình được | Theo tile DW-PW cụ thể | Cần đọc full text |
| **Weight reload cost model** | Cần xác minh | Bank tags, tile/layout ID, vùng byte hợp lệ và reload thật | Cần đọc full text |
| **DW-PW structure** | Cần xác minh | DW → PW fusion được tối ưu | Cần đọc full text |
| **SAVE vs REPLAY decision** | Cần xác minh | Explicit policy choice | Cần đọc full text |
| **Chi phí ghi vs recovery phân biệt** | Cần xác minh | Phân biệt với chi phí recovery | Cần đọc full text |

### 14.2 So sánh với Viadotto [R3]

| Quyết định/thành phần | Viadotto (CRAM) | RECAP-CIM | Khác biệt? |
|------------------------|-----------------|-----------|------------|
| **Volatile vs Non-volatile** | CRAM không mất dữ liệu | SRAM mất trọng số khi mất nguồn | Problem domain khác |
| **Weight state tracking** | NVM không mất dữ liệu do power-off; allocation/layout/residency strategy phải đọc full text | Theo dõi weight bank của SRAM và reset tags khi cold reboot | Khác biệt cần đối chiếu phương pháp |
| **Recovery protocol** | Có controller chống gián đoạn; không kết luận đơn giản hơn chỉ từ loại bộ nhớ | Copy-on-write và atomic publish cho trạng thái volatile | Khác biệt cần đối chiếu full text |
| **Parallelism adaptation** | Thích nghi mức song song | Tối ưu mapping + recovery | Scope khác |

### 14.3 Kết luận novelty

**Điểm khác biệt dự kiến cần xác minh (sau khi đọc full text):**

1. **Đồng tối ưu weight residency và mapping/khôi phục DW–PW:** đối chiếu với mọi công trình gần nhất tìm được, không chỉ Chime/Viadotto. Cần xác minh khác biệt thuật toán và miền vấn đề.
2. **Lựa chọn `(save_z, keep_ps)` trong cùng mapper:** cần xác minh prior art và chứng minh lợi ích so với tối ưu riêng từng quyết định; đặt tên policy không tạo tính mới.
3. **Cost decomposition và commit đúng:** là yêu cầu mô hình hóa/triển khai. Không lấy việc phân biệt write/recovery hoặc dùng checkpoint làm đóng góp mới độc lập nếu chưa có kỹ thuật bổ sung thực sự khác prior art.

Sau G1, phát biểu tính mới phải nêu đúng khác biệt đã có dẫn chứng và phạm vi khảo sát. Khảo sát không tìm thấy công trình trùng không phải chứng minh tuyệt đối rằng chưa từng có; chỉ dùng tuyên bố “first” nếu có cơ sở khảo sát đủ mạnh và thực sự cần thiết.

---

**Điểm xuất phát thực thi:** hoàn thành G1 (novelty matrix với dẫn chứng cụ thể + hardware selection) trước. Đóng góp có giá trị khi một quyết định kỹ thuật mới vượt đối chứng mạnh trong miền điều kiện có căn cứ, giữ đúng kết quả và có thể tái lập; không phụ thuộc vào việc gắn nhiều thuật ngữ vào tên đề tài.

---

## 15. Điều kiện trước khi bắt đầu triển khai đầy đủ

**Bốn đầu ra bắt buộc trước khi mở rộng quy mô:**

1. **Bảng tính novelty có dẫn chứng cụ thể:** Mỗi nhận xét "X chưa có" phải dẫn đến trang/công thức cụ thể trong paper gốc. Baseline gần nhất được xác định rõ.

2. **Cấu hình SRAM-CIM và NVM có tham số có nguồn:** Hoặc miền giả định được giới hạn rõ ràng với justification.

3. **Đặc tả state/action/commit nhất quán:** có bank tags và dependency đủ chi tiết; progress volatile/durable tách riêng; SAVE không đổi record đã publish; ledger tính đủ PS/replay/reload và không cộng trùng.

4. **Microbenchmark một cặp DW–PW:** kiểm tra mọi tổ hợp `(save_z, keep_ps)` hợp lệ, failure trước/sau publish và giữa payload/metadata, khôi phục PS cùng offset, mismatch bằng 0 trong test đã chạy, ledger khớp load energy. Không gọi test hữu hạn là chứng minh đúng cho mọi execution.

Đây là các deliverable cần tạo trong nghiên cứu, không phải kết quả đã hoàn thành của lần rà soát plan. Có thể bắt đầu khảo sát và microbenchmark theo G1/G2; chỉ mở rộng mapper/RTL sau khi các điều kiện trên có artifact đạt yêu cầu.

---

## 16. Ghi nhận rà soát v3.2

Ngày 14/10/2026: thống nhất energy/completion/latency metrics; sửa chi phí REPLAY có giữ PS; tách checkpoint staging khỏi atomic publish; bổ sung state/action/cold-boot semantics; sửa mô hình xác suất, mục tiêu tối ưu và độ phức tạp; tách đối chứng backend và policy; điều chỉnh các khẳng định novelty chưa có bằng chứng.

Lần rà soát này kiểm tra **đặc tả và tính nhất quán tài liệu**. Chưa huấn luyện benchmark mới, chạy mapper/fault tests, chọn macro/NVM cụ thể hoặc validate năng lượng vật lý. Hướng nghiên cứu đủ rõ để bắt đầu G1/G2, còn tính mới và hiệu quả phải được xác minh bằng artifact của các mốc tương ứng.
