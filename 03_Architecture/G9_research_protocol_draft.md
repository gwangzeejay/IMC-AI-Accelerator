# Đề xuất protocol G9 cho RECAP-CIM

Ngày 11/11/2026. Trạng thái **DRAFT, chưa khóa trước thí nghiệm chính**. Tài liệu này chuyển kết quả khảo sát nguồn và kiểm nghiệm G8 thành thiết kế nghiên cứu có thể triển khai. Seed, profile phần cứng và dataset mới sẽ được chốt sau development. Lượt kiểm tra toán học trong `research_20261111` đã chạy với mô hình không thứ nguyên riêng.

**Câu hỏi trung tâm là khi nào cần lưu activation depthwise và partial sum pointwise để tăng tiến độ suy luận bền vững trên SRAM-CIM có trọng số dễ mất.** Yếu tố cần chứng minh là tác động kết hợp của trọng số cư trú, vị trí cắt trong thao tác và trạng thái thực sự đã commit lên lựa chọn tối ưu. Khảo sát Chime, Circadia, iNAS và CHRYSALIS là cơ sở để thu hẹp đóng góp. [Tổng hợp nguồn](../02_Research/Research_strategy_2026-11-11.md).

## Hợp đồng hệ thống

KWS và VWW hiện có tiếp tục cung cấp workload cơ sở. Một inference chỉ được tính commit khi output đã bền vững và khớp output INT8 của reference. Các điểm reset phải tác động lên thao tác đang chạy. Chỉ số hạn chót tính từ thời điểm sự kiện/input xuất hiện, gồm cả thời gian chờ và khôi phục trong phạm vi đã khai báo. Mô hình đầu tiên có thể giữ head CPU reference như G8 và báo rõ thời gian/năng lượng của head.

Mỗi lần khởi động phải phân biệt mức reset có căn cứ. Reset CPU có thể làm mất thanh ghi điều khiển. Brownout có thể còn giữ một phần SRAM nếu rail và thời gian mất nguồn đáp ứng đặc tính thiết bị. Rail mất hoàn toàn làm mất bank SRAM và mọi trạng thái volatile. Mức giữ lại phải có profile điện áp/thời gian hoặc dùng như can thiệp mô hình giả định. Các lần reset G8 đang xả tụ về 0 vẫn thuộc nhóm mất hoàn toàn. Đưa retention vào nghiên cứu cần bổ sung đường điện và cơ chế kiểm tính hợp lệ của dữ liệu.

Một action bao gồm descriptor của tile, CI chunk, hành động lưu DW, hành động lưu PS và biên publish được phép. State được dùng để quyết định phải chứa tối thiểu những trường sau.

| Trường | Ý nghĩa và điều kiện đúng |
|---|---|
| Layer, tile, CI prefix | Vị trí tính toán được phục hồi từ record đã commit |
| Descriptor identity | Geometry, model/input identity, quantization và version của layout |
| Durable DW/PS flags | Có đúng payload còn dùng và đúng frontier, CRC/identity hợp lệ |
| Weight-bank residency | Tag trọng số và miền nguồn giữ bank, reset hoàn toàn đưa về cold |
| Năng lượng hiện tại | Quan sát tại thời điểm quyết định, cộng chi phí đo/điều khiển |
| Thời gian còn lại | Deadline trừ thời gian thực hiện đã trôi qua |
| Thông tin nguồn quá khứ | Nếu dùng predictor, toàn bộ lịch sử đầu vào và thời điểm phải causal |

Hợp đồng copy-on-write giữ nguyên nguyên tắc dữ liệu cũ còn hợp lệ cho đến khi record mới publish. Lựa chọn geometry mới chỉ diễn ra ở biên tương thích với descriptor và dependency. Điều kiện ACK bền vững, kích thước ghi nguyên tử và CRC phải được kiểm bằng adapter/backend được dùng trong phép đo.

## Mô hình quyết định

Với action a từ state s, mô hình phải có cả nhánh hoàn tất và nhánh mất nguồn trong từng phase. Một biểu diễn thích hợp cho bộ giải trên block nhỏ là phương trình Bellman.

\[
V(s)=\min_{a\in A(s)}\left\{p_a\,[e_a+V(s_a^+)]+\int_0^{t_a} f_a(u)\,[e_a(u)+e_r(s,a,u)+V(s_r)]\,du\right\}.
\]

Ở đây p là xác suất sống qua toàn action, f là mật độ mất nguồn trước khi action hoàn tất, e(u) là năng lượng đã dùng đến thời điểm cắt, e_r là chi phí khôi phục và s_r là state thực sự khôi phục được. Recharge tác động đến thời gian và hạn chót. Nếu khôi phục cũng có thể bị cắt thì cần biểu diễn nó thành các action/state có thể gián đoạn, tránh cộng một hằng recovery duy nhất. Có thể dùng hazard không đổi để kiểm toán học trước, rồi thay bằng mô hình nguồn có bộ nhớ hoặc quy trình chuyển trạng thái có thời lượng. Quy hoạch động trên không gian rời rạc chỉ cho nghiệm của mô hình đã chọn.

Trong bài toán có deadline, giữ thêm thời gian còn lại vào state và tính xác suất hoàn tất đúng hạn cho mỗi action. Ưu tiên thỏa xác suất/constraint hoàn thành đã khóa, sau đó tối thiểu năng lượng kỳ vọng trong các lựa chọn khả thi. Khi không có action khả thi, hành vi đợi, tiếp tục hoặc loại sự kiện phải được mô tả và tính vào tỷ lệ kết quả trên mọi sự kiện đến. Nhãn đúng của input chỉ dùng trong đánh giá offline. Hệ số dự đoán được fit trên development hoặc lịch sử đã quan sát.

Một bộ chọn triển khai gọn có thể dùng bảng lookup được sinh offline từ profile. Bộ lookup nhận mức năng lượng, deadline và residency, trả descriptor/action. Báo kích thước bảng, worst-case thời gian tra và năng lượng quyết định. Khảo sát độ nhạy với lượng tử hóa state phải cho biết bao nhiêu năng lượng/đúng hạn bị mất so oracle block nhỏ.

## Chuỗi thực nghiệm

| Mốc | Phép kiểm | Bằng chứng cần lưu |
|---|---|---|
| G9-A | Sửa việc B4 chuyển CI16 thành CI64 sau restore trong nhánh G9 | Test cắt sau checkpoint đã ACK, giữ cùng chu kỳ và frontier qua nhiều lần reboot |
| G9-B | Dựng cost profile riêng từ nguồn và mô hình per-action | Version/hash công cụ, macro, precision, điện áp, bank/load bandwidth, transaction và những trường chưa biết |
| G9-C | Oracle block nhỏ, quét cut trong compute/write/reload | Tất cả bốn tổ hợp DW/PS, byte NVM, MAC redo, trạng thái cold/warm, energy/time và correctness |
| G9-D | Đối chứng tối ưu trên cùng backend | State/action/objective mapping, test nhỏ có đáp án, khoảng cách tới oracle |
| G9-E | Khóa policy/protocol và chạy toàn mạng trên tập mới | Manifest trước chạy, dữ liệu thô đủ grid, mọi ca thua/incomplete, CI ghép cặp |
| G9-F | Tái lập từ môi trường tách biệt | Dependency/model/data manifests, lệnh bootstrap, metric comparison và lỗi nếu có |

Để giữ truy vết G2–G8, triển khai nghiên cứu mới trong module G9 hoặc snapshot/worktree đã kiểm soát. Snapshot cần có Git commit và manifest có thể đọc lại. Một bản sửa lên G6 đang bị bind vào manifest cũ sẽ làm audit lịch sử thất bại. Quy trình phát triển G9 phải phân biệt rõ phiên bản thuật toán và phiên bản bằng chứng.

**Oracle block nhỏ trước toàn mạng.** Lấy descriptor thực từ các stage DW–PW của KWS/VWW. Chọn các shape có CI/CO nhỏ và lớn, nhiều và ít reuse trọng số, kiểm tail tiles. Quét bốn action lưu/bỏ DW và PS với cùng geometry, nguồn và output target. Bổ sung nhánh ép giữ/hủy weight-bank qua reset để đo riêng tác động residency trong mô hình. Phân tích theo ba tỷ số không thứ nguyên, gồm mức rủi ro reset trên thời gian block, chi phí lưu trạng thái trên chi phí tính lại, và chi phí cold reload trên chi phí tính block. Xác định ngưỡng dùng để lập grid trước khi chạy tập chính.

Một case dùng geometry quá lớn gây infeasible vẫn thuộc dữ liệu. Bộ kiểm phải chứng minh không tính lại MAC đã commit, không dùng offset PS khi payload chưa bền vững, không dùng DW/weight sai tag và không hiển thị output torn. So byte/MAC ledger với oracle độc lập trên case đủ nhỏ để vét cạn.

**Các đối chứng được đề nghị** cần được hiện thực và kiểm trước khi freeze.

| Đối chứng | Vai trò | Yêu cầu so sánh |
|---|---|---|
| B1_layer hiện hành | Đường cơ sở dễ giải thích | Cùng output contract và publication |
| B3_adaptive | Đối chứng nội bộ mạnh đang hòa với RECAP | Cùng tập candidate, memory và quan sát nguồn |
| B4_periodic đã sửa | Tác động của chu kỳ checkpoint | Chọn interval trên development và giữ đúng qua reboot |
| Checkpoint tĩnh tối ưu | Đối chứng gần Circadia/Chime | Tái hiện phương pháp hoặc mô tả adaptation đã giới hạn, không đặt tên như bản tái hiện đầy đủ khi thiếu thành phần |
| Mapping có residency, recovery cố định | Tách lợi ích tiling/reload | Cùng không gian mapping và cùng chi phí planner |
| Mapping cố định, recovery thích nghi | Tách lợi ích quyết định DW/PS | Cùng descriptor qua các action |
| G9 kết hợp | Kiểm tác động tương tác | So riêng từng thành phần và kết hợp |

Oracle biết lịch cắt tương lai có thể cung cấp cận phân tích. Khi đó tên, thông tin đầu vào và phạm vi sử dụng phải nêu rõ trong bảng kết quả. Một oracle hữu hạn trạng thái dùng cùng phân phối nguồn có thể kiểm độ tốt của policy mà không cần cho lịch tương lai vào runtime.

**Đánh giá toàn mạng.** Tập cơ sở nên có synthetic nguồn theo family, reset cưỡng bức và trace dẫn xuất từ đo đạc. Giữ cả steady/zero controls. Tăng số seed độc lập mỗi family theo độ rộng CI development và ngân sách chạy. Mốc khởi đầu để dự toán là 30 seed mỗi family, sau đó khóa số lượng theo phân tích độ chính xác trước khi xem main. Các window trên cùng ngày/một thiết bị phải được bootstrap theo ngày/thiết bị hoặc khối tương quan phù hợp. Nhiều arrival trong một trace dùng chung reservoir là một cụm khi lấy mẫu lại.

Một cấu hình dự toán gồm 2 workload × 6 policy × 4 family × 30 seed × 3 profile tạo 4.320 hàng chính. So với tốc độ trung bình của lượt G8 đã chạy khoảng 545,7 giây/400 hàng và có cả preflight, ước lượng đầu tiên vào khoảng 1,6 giờ cùng host. Đây chỉ là dự toán từ độ lớn hiện có. Cache, planner G9, độ dài trace, số profile và head reference có thể làm thay đổi thời gian đáng kể. Chạy pilot để đo lại trước khi khóa grid. Nhiều seed nguồn trên cùng model/cost profile chỉ mở rộng miền nguồn đã kiểm.

Profile chi phí chính phải thỏa đồng thời macro capacity, precision và điện áp, cùng bandwidth đọc/ghi/nạp bank. Một thay đổi điện áp có thể làm đổi energy, latency và operating point nên sweep các quantity tương quan. Lưu “reported” cho tham số nguồn, “derived” cho phép suy ra có công thức, “assumed” cho giá trị giả định và “measured” cho phép đo thực với điều kiện đo. Profile chưa có calibration vẫn mang `calibrated=false`.

## Endpoint và điều kiện ra quyết định

| Endpoint | Công thức/phạm vi |
|---|---|
| Completion per arrival | Số output bền vững / tất cả sự kiện đến |
| On-time per arrival | Số commit trước deadline / tất cả sự kiện đến |
| Correct and timely per arrival | Số dự đoán đúng và đúng hạn / tất cả sự kiện đến, dùng nhãn offline |
| Energy per commit | Tổng năng lượng đã tiêu của mọi attempt / số commit, để undefined nếu mẫu số 0 |
| Energy per on-time commit | Tổng năng lượng / số commit đúng hạn, để undefined nếu mẫu số 0 |
| Recovery overhead | Boot, scan, checkpoint, redo, cold reload và chờ recharge theo phạm vi đã khai báo |
| Resource cost | Worst-case SRAM/NVM thật của runtime/lookup, controller cycles và byte/code footprint |
| State-selection behaviour | Số lần chọn từng action DW/PS theo stage và family |

Chọn trước một endpoint chính và chiều so sánh. Các tiêu chí completion/on-time đi kèm phải cố định trước main. Mục tiêu nội bộ 20% chỉ tiếp tục có hiệu lực nếu protocol mới quyết định giữ nó. Mức cải thiện và CI phải được báo cùng các ca thua. Các comparison/ablation phụ phải được đánh dấu để giữ cách diễn giải tương xứng với số phép thử.

Để claim cơ chế DW/PS có giá trị, cần thấy các state mà oracle chọn khác nhau và policy theo được sự thay đổi, rồi xác nhận tác động trên tập ngoài development. Nếu các phương án lưu luôn bị trội hơn trong profile thực tế, kết quả có thể chuyển thành phân tích miền không cần checkpoint trung gian, nếu có lập luận và kiểm chứng vượt khỏi một implementation. Kết quả hòa có thể chỉ ra một mô hình chi phí thiếu hoặc một candidate space chưa chứa quyết định hữu ích, nên phải kiểm hai khả năng đó trước khi kết luận về công nghệ.

## Nhánh ứng dụng sau G9

Occupancy dùng VWW là ứng viên đầu tiên vì tái dùng được pipeline hiện tại. Thêm chi phí capture, preprocessing, idle và truyền một event ngắn, cùng deadline rút từ ứng dụng. Streaming wake word bổ sung state liên cửa sổ, timestamp và ảnh hưởng của âm thanh mất trong thời gian thiết bị tắt. Cần định nghĩa cửa sổ hợp lệ và dữ liệu đã bỏ lỡ trước khi so chất lượng. Đây là workload được MLPerf Tiny mở rộng từ v1.3 và cần adapter mới cho graph/state. [MLCommons 2026](https://mlcommons.org/2026/07/mlperf-tiny-v1-4-results/).

Retention của SRAM-CIM là nhánh tiếp theo khi có profile rail/retention có căn cứ. Kiểm thời gian tắt, nhiệt độ, bank validity và partial retention trước khi tin dữ liệu còn lại. Định lượng cả năng lượng giữ bank và năng lượng tái nạp. Các kết quả MCU SRAM của TotalRecall/RIPPLE cung cấp prior art và thiết kế thí nghiệm tham khảo. [TotalRecall](https://harriswms.github.io/files/ForgetFailure.pdf) · [RIPPLE](https://link.springer.com/article/10.1007/s11227-025-08205-7).
