# G3 — Mapper bản đầu và protocol microbenchmark

## Phạm vi hiện thực

G3 giữ nguyên engine/artifact G2, bổ sung `recap/g3_workload.py`,
`recap/g3_simulator.py` và `g3_experiments.py`. Backend vẫn là mô hình số
học digital INT8/INT32, chưa là macro SRAM-CIM đã characterization.

Workload cố định lấy từ golden MLPerf Tiny: cặp DW–PW đầu tiên, output
DW/PW tại y=1:5, x=1:3, 64 input channels, PW output channels 0:16.
Tất cả mapping phải commit cùng **128 phần tử output INT8**.
Không thay số lượng công việc khi đổi tile.

## Descriptor và memory

- Spatial tiles: 1×1, 1×2, 2×2, 4×2; CO blocks: 4 hoặc 16.
- CI execution chunks: 16 hoặc 64; `save_z` × `keep_ps`: bốn tổ hợp.
  Tổng 64 cấu hình, 40 hành vi phân biệt do flags tương đương khi CI=64.
- Descriptor generator tạo **75 descriptor duy nhất** cho 8 spatial/CO
  partitions; halo được đọc/tính đúng; coverage mỗi output đúng một lần.
- CI chunk hiện là execution/checkpoint prefix. Weight bank chứa toàn CI
  của block CO; chưa phải mapper bit-slicing/packing/partial weight load.
- Hai bank DW/PW 2048 B. Tag chứa SHA-256 của weight+bias+layout, tránh
  nhầm hai block CO có cùng shape. Có reuse giữa descriptor khi nguồn
  chưa mất; input/Z chỉ reuse khi spatial dependency hash khớp.
- Logical SRAM 16384 B. Mỗi descriptor giữ immutable anchor/weight copies
  và hai checkpoint slots riêng, align 256 B theo payload lớn nhất.
- NVM budget 262144 B tính cả hai slots **của mọi descriptor**, immutable
  copies, bảng descriptor 128 B/job, completion byte/job và toàn bộ TFLite
  blob 53936 B như một reservation bảo thủ. Không giả định free memory
  hoặc bỏ output đã commit để khiến tile nhỏ vừa capacity.

Đây là memory organization prototype có replication, chưa tối ưu global
allocator/reclamation. Python/NumPy temporaries nằm trên PC; logical SRAM
reservation không phải peak RSS hoặc kết quả synthesis target.

## Output frontier và crash ordering

Mỗi job giữ output thật trong slot cuối đã publish. Sau output commit mới
publish completion byte của job vào một bảng NVM monotone prefix. Bảng
này được đọc khi cold boot để xác nhận descriptor đang phục hồi.

Nếu mất nguồn sau output publish nhưng trước completion byte, lần boot
tiếp theo restore output và hoàn tất publication bảng. Nếu completion byte
đã publish, output tương ứng phải tồn tại. Engine không đánh dấu hoàn tất
workload bằng số label, cache của Python hoặc offset volatile.

Atomic một-byte completion/slot markers và persistence ordering tiếp tục
là **giả định mô phỏng**, chưa được chứng minh trên FRAM vật lý. Fault
campaign bao phủ cả output/frontier boundary mới.

## Boot và admission

G2 đọc toàn bộ hai slot cố định mỗi boot. G3 đọc hai header areas, rồi đọc
payload của các slot đã publish để kiểm tra integrity; mọi traffic được
charge. Không dùng một tag hợp lệ trong host để bỏ đọc payload cần thiết.

Khi SRAM còn sống, admission xét đúng Z/input/PS/banks/offset hiện tại.
Cold admission dùng bound bảo thủ cho các nhánh restore/replay, boot,
metadata tối đa, payload và marker. Không ghi có harvest tương lai. Chi phí
thật mỗi committed unit được assert không vượt bound. Chỉ tắt nguồn có
chủ đích khi không đủ reserve; `WAIT_CHARGE` và off load giả định bằng 0
giống G2. Trong source runs không chèn fault ngoại sinh, unexpected
depletion phải bằng 0.

Nếu không có cold unit nào vừa capacitor, run là incomplete với lý do
`admission_capacity`; không bỏ case khỏi mẫu số completion hoặc bootstrap.
Nếu tới cuối horizon chưa đủ output thì cũng là incomplete. Admission vẫn
bảo thủ, chưa là characterization hay bằng chứng forward progress trên
mọi harvest trace.

## Mapper và baselines

Mapper v1 liệt kê policy tĩnh nhân quả, chạy trên training scenarios, lọc
completion/on-time không kém **B3 adaptive** quá 5 điểm phần trăm, rồi
xếp theo ratio tổng energy / tổng completed. Bốn hành vi khác nhau tốt
nhất được xem xét trên validation nếu có đủ ứng viên. Chọn và freeze trước
khi chạy test. Không dùng tương lai trace để chọn runtime action.

| ID G3 | Cấu hình prototype |
|---|---|
| B1_micro | 4×2, CO16, CI64, không intermediate checkpoint |
| B2_micro | 2×2, CO4, CI16, lưu Z+PS |
| B3_micro | Mapping B2, chọn CI16/32/64 bằng energy hiện tại/capacity và admission bound; luôn giữ save flags B2 |
| RECAP_proto | Spatial/CO/CI/save flags chọn bằng train/validation |
| fixed_mapping_joint_recovery | Chỉ fit bốn save flags trên mapping B2; báo rõ nếu không policy nào khả thi |
| no_weight_reuse | Mapping đã freeze, tắt bank reuse; giữ nguyên arithmetic và dependencies |
| matched_SAVE / matched_REPLAY | Mapping đã freeze, ép CI16 và `keep_ps=true`, chỉ thay `save_z` |

B1/B2/B3 là baseline do dự án hiện thực ở microbenchmark. Chưa tái hiện
B4 CIM-Tuner/Chime, chưa có đối chứng B0 non-CIM hay B5 full-network.
Enumeration không chứng minh tối ưu trên mọi descriptor/order/policy động;
không có DP/beam gap hoặc runtime controller characterization ở bản này.

## Chi phí, splits và statistics

Protocol nguồn: `09_Simulation/configs/g3_protocol.json`, version 1.1.
Cost là G2 debug với DW compute energy ×30 ở main run, thời gian giữ
nguyên. Đây là **giả định phân tích**, không phải số đo. Sensitivity dùng
DW energy ×1/30/300 và NVM write energy ×0.5/1/4; không fit lại mapping.

Sáu families là capacitor usable energy 10/25/100 uJ × mean harvest
12/60 uW; mọi số đều là giả định tại capacitor rail. Trace gồm 20 đoạn
ngẫu nhiên, có đoạn harvest=0; horizon 1 s, arrival 0, deadline 1 s.
Mỗi family có 1 train seed, 1 validation seed và 3 test seeds độc lập:
**6 train, 6 validation, 18 test**.

Fit chỉ nhận train/validation. `frozen_mapper.json` có hash protocol,
fit IDs, thời điểm freeze và selection; file không được đổi trong test.
Bootstrap 2000 lần, paired theo trace seed và stratified theo family;
không coi nhiều jobs trong cùng trace là independent samples. Replicate
không có completed denominator phải được báo và CI vô điều kiện để `null`,
không lọc bỏ để làm CI đẹp. p95 có incomplete là vô hạn theo plan.

## Correction log và chẩn đoán bổ sung

Lần harness thử ban đầu dùng nhầm B2 làm feasibility reference. Đã sửa về
B3 theo yêu cầu plan, không đổi hệ số/candidate grid/ngưỡng 20%/5 điểm phần
trăm. Bộ test seed base 51000 đã xem được **retire**; final dùng base
71000. Artifact cũ giữ trong `g3/_diagnostics/initial_B2_feasibility_reference/`.
Đây là sửa lỗi protocol, không coi kết quả thử đó là held-out evidence.

Main held-out CI16 SAVE/REPLAY đều incomplete; không tính tỷ lệ tiết kiệm
với mẫu số 0. Sau main analysis bổ sung **exploratory recovery episodes**:
một descriptor, giữ cùng committed prefix CI=16, không outage hoặc một
cold loss ngay sau prefix đó, rồi chạy tới output. Phép can thiệp đồng bộ
theo state khác với outages cùng wall-clock; chỉ tách chi phí checkpoint/
restore/recompute, không thay thế main source benchmark và không dùng
để refit mapper. Có 36 evaluated episodes và 18 boundary probes.
