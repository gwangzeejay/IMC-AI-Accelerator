"""Build a source-bound current report and figures from audited G8 evidence."""
import json
from pathlib import Path
import hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'10_Experiments/g8/20261023-v2'
DERIVED=ROOT/'10_Experiments/g8/quality_20261023'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def percent(v):return 'không xác định' if v is None else f'{v*100:.3f}%'
def agg(rows):
    n=sum(r['completed'] for r in rows);e=sum(r['energy_j'] for r in rows)
    return n,e/n if n else None

def main():
    integrity=read(DERIVED/'integrity_audit.json')
    if integrity['status']!='PASS_PROJECT_INTEGRITY':raise ValueError('Run integrity audit first')
    r=read(RUN/'results.json');p=read(RUN/'protocol.json')
    rows=[json.loads(v) for v in (RUN/'main.jsonl').read_text().splitlines()]
    secondary=[json.loads(v) for v in (RUN/'secondary.jsonl').read_text().splitlines()]
    publication={}
    for work in p['workloads']:
        scratch=[v for v in secondary if v['workload']==work and v['method']=='RECAP_redo' and v['intervention']=='scratch_output']
        ids={v['scenario_id'] for v in scratch}
        direct=[v for v in rows if v['workload']==work and v['method']=='RECAP_redo' and v['scenario_id'] in ids]
        ns,es=agg(scratch);nd,ed=agg(direct)
        publication[work]=dict(scratch_completed=ns,direct_completed=nd,arrivals=sum(v['total_inputs'] for v in direct),
            scratch_j_per_commit=es,direct_j_per_commit=ed,relative_reduction=1-ed/es,
            scope='preset 6-scenario secondary subset; policy may respond to publication cost; not main objective or hardware measurement')
    readiness=dict(date='2026-10-23',scope='Explicit engineering-deliverable rubric; not a measured fraction of research novelty, silicon completion, or publication readiness',
        achieved_points=80,total_points=100,submission_ready=False,calibrated=False,
        gates=[
            dict(name='Scope and current documentation',points=10,passed=True,evidence='README.md; 06_FPGA/HARDWARE_ROADMAP.md'),
            dict(name='Reference arithmetic and operator checks',points=10,passed=True,evidence='G2-G6 tests; G8 equivalence.json'),
            dict(name='Durable recovery and fault checks',points=10,passed=True,evidence='G8 unit tests; six full-network directed faults'),
            dict(name='Implemented redo-aware ranking with independent oracle',points=10,passed=True,evidence='g8_runtime.py; linear-system and causality tests; no superiority claim'),
            dict(name='Common direct-publication primitive and RTL',points=10,passed=True,evidence='284 RTL ACK-cut cases; 2 invalid commands; generic synthesis'),
            dict(name='Runnable common-backend controls',points=10,passed=True,evidence='5 local policies; B4 interval development-selected; not literature reproduction'),
            dict(name='Locked evaluation, raw data and stress interventions',points=10,passed=True,evidence='G8_1.1 freeze; 280 main and 120 secondary rows; abort disclosed'),
            dict(name='Reproduction commands and independent audit',points=10,passed=True,evidence='89 Python tests executed; check_project.py; 2769 preserved legacy hash entries'),
            dict(name='Scientific contribution and strong optimized prior-art comparison',points=10,passed=False,evidence='No main advantage over B3; nearest optimized literature baseline and independent review remain open'),
            dict(name='Source-backed/physical backend validation and deployment',points=10,passed=False,evidence='No board/lab/PDK; cost calibration, full-runtime memory and physical persistence unverified')])
    (DERIVED/'software_readiness.json').write_text(json.dumps(readiness,indent=2)+'\n',encoding='utf-8')
    (DERIVED/'publication_ablation.json').write_text(json.dumps(publication,indent=2)+'\n',encoding='utf-8')
    colors=['#94a3b8','#64748b','#c2a26a','#60a5fa','#0f766e']
    labels=['Layer','Adaptive','Periodic','Nominal','Redo-aware']
    fig,axes=plt.subplots(1,2,figsize=(10.5,4.4),layout='constrained')
    for ax,work in zip(axes,p['workloads']):
        values=[r['workloads'][work]['stochastic']['methods'][m] for m in p['methods']]
        energies=[v['energy_per_completed_j']*1000 for v in values]
        bars=ax.bar(labels,energies,color=colors,width=.65)
        ax.set_title(work.upper()+' | stochastic source')
        ax.set_ylabel('Assumed model mJ / committed inference')
        ax.tick_params(axis='x',rotation=22);ax.spines[['top','right']].set_visible(False)
        ax.set_ylim(0,max(energies)*1.25)
        for b,v in zip(bars,values):
            ax.text(b.get_x()+b.get_width()/2,b.get_height()+max(energies)*.025,
                f"{v['completed']}/{v['total_inputs']}",ha='center',fontsize=9)
    fig.suptitle('G8_1.1 | common direct publication | point estimates, completion counts above bars',fontsize=11)
    fig.savefig(DERIVED/'main_comparison.png',dpi=180);plt.close(fig)
    lines=[]
    for work in p['workloads']:
        for domain in ('stochastic','external_reset'):
            item=r['workloads'][work][domain]
            for m in p['methods']:
                v=item['methods'][m]
                lines.append(f"| {work.upper()} | {domain} | {m} | {v['completed']}/{v['total_inputs']} | {v['energy_per_completed_j']*1000:.6f} |")
    table='\n'.join(lines)
    pubrows='\n'.join(f"| {w.upper()} | {v['direct_completed']}/{v['arrivals']} | {v['scratch_j_per_commit']*1000:.6f} | {v['direct_j_per_commit']*1000:.6f} | {percent(v['relative_reduction'])} |" for w,v in publication.items())
    cirows=[]
    for work in p['workloads']:
        for domain in ('stochastic','external_reset'):
            item=r['workloads'][work][domain]
            for baseline in ('B1_layer','B3_adaptive','B4_periodic'):
                c=item['comparisons'][baseline];ci=c['paired_bootstrap']['energy_reduction_ci95']
                ci_text='không xác định' if ci is None else f'[{percent(ci[0])}; {percent(ci[1])}]'
                cirows.append(f"| {work.upper()} | {domain} | {baseline} | {percent(c['comparison']['relative_energy_reduction'])} | {ci_text} |")
    citable='\n'.join(cirows)
    report=f'''# G8 — Bản hoàn thiện kỹ thuật trên máy tính

Ngày: **23/10/2026**. Đợt hợp lệ: **G8_1.1 / 20261023-v2**;
RTL: **rtl-20261023-v3**. G2–G6 và manifest gốc được giữ nguyên.

## Mức hoàn thiện

**80/100 theo rubric công việc kỹ thuật được khai báo bên dưới.** Đây là
cách quản lý phạm vi: tám nhóm engineering đã có artifact kiểm tra được,
hai nhóm scientific/physical validation còn mở. Không diễn giải thành đã
chế tạo 80% chip, hoàn tất 80% tính mới hoặc sẵn sàng nộp bài.

| Nhóm công việc | Điểm | Trạng thái |
|---|---:|---|
| Phạm vi và tài liệu hiện hành | 10 | Đạt |
| Arithmetic/reference | 10 | Đạt trong phạm vi kiểm tra |
| Durability và fault tests | 10 | Đạt hữu hạn, không phải formal proof |
| Ranking expected-redo và oracle độc lập | 10 | Đã hiện thực; chưa chứng minh lợi ích toàn mạng |
| Direct publication và publisher RTL | 10 | Đã kiểm trên máy |
| Năm control cùng backend/publication | 10 | Đạt; B4 chưa phải prior-art reproduction |
| Protocol freeze, raw results và stress cases | 10 | Đạt; công khai đợt tích hợp bị hủy |
| Lệnh tái lập và audit độc lập | 10 | Đạt trên workspace hiện tại |
| Đóng góp khoa học, đối chứng tối ưu gần nhất, review độc lập | 10 | Còn mở |
| Backend có căn cứ/calibration và xác minh triển khai thực | 10 | Còn mở |

Chi tiết máy đọc: [software_readiness.json](../10_Experiments/g8/quality_20261023/software_readiness.json).

## Những gì đã sửa và thêm

- Thêm `g8_runtime.py`: ranking expected-redo bằng mô hình renewal hữu hạn.
  Expectation chỉ tác động quyết định, không được cộng vào execution ledger.
- Bỏ scratch-output mặc định. Tất cả policy dùng cùng durable layer-log path.
- Thêm rail disconnect tại absolute timestamps chung cho mọi policy; giữ
  charge bị xả khỏi load-energy numerator và kiểm conservation.
- Thêm B4 periodic có interval chọn từ development. Đây là control nội bộ;
  không gọi là thuật toán Chime tối ưu hoặc CIM-Tuner đã được reproduce.
- Thêm 24 ảnh VWW khác G6, bốn development và hai mươi holdout; tách feature
  dùng trong runtime G5/G6 và khóa source/input/protocol trước main.
- Sửa B1 geometry cho VWW CO128/256 và thêm kiểm tra mọi stage. Đợt G8_1.0
  ban đầu bị hủy, không dùng làm bằng chứng. G8_1.1 dùng seed nguồn/reset mới;
  pool feature đã xuất hiện trong đợt tích hợp lỗi nên không nhận là chưa từng chạy.
- Thêm publisher RTL streaming, testbench, generic synthesis, audit độc lập,
  lệnh test chung và hướng dẫn phần cứng cho tình huống không có lab.
- Chuyển README/Makefile/hướng dẫn cũ vào `docs/legacy`, bỏ số 8×/tape-out
  chưa xác minh khỏi trang hiện hành; thêm `.gitignore` và khởi tạo Git cục bộ.
  Chưa tạo commit hoặc remote; cần chọn metadata và tạo snapshot sau review.

## Kiểm chứng đã thực thi

| Kiểm tra | Kết quả |
|---|---|
| Python G2/G3/G4/G5/G6/G8 | **89 tests đạt**: 22 + 17 + 10 + 12 + 14 + 14 |
| Legacy G2–G6 | **2.769 mục SHA-256 khớp** |
| G8 main | **280 hàng**, 28 scenarios × 5 policy × 2 workload |
| G8 secondary | **120 hàng**, năm intervention trên subset preset |
| Output đã commit trong main | **{r['main_completed']}**, đều so với reference |
| G8 independent aggregate audit | **40 ô tổng hợp khớp** |
| Arithmetic development | **304.220 phần tử**, 0 mismatch trên hai input; không phải toàn dataset |
| Directed graph faults | **6 ca full-network**, hai workload × ba điểm cắt |
| Publisher RTL | **284 ACK-cut/stall cases**, hai invalid-command tests |
| Yosys publisher | Generic proc/opt/check đạt; **66 generic cells**, không phải LUT/area/PPA |
| Scratch-output writes trong main | **0** |

Audit: [integrity_audit.json](../10_Experiments/g8/quality_20261023/integrity_audit.json).
RTL: [rtl_report.json](../10_Experiments/g8/rtl-20261023-v3/rtl_report.json).
Các chiến dịch fault/RTL G2–G6 cũ được kiểm hash, chưa chạy lại toàn bộ trong G8.

## Kết quả chính — vẫn dùng cost giả định

Horizon G8 là 24 s, arrivals 0/8/16 s; khác protocol G6. Mọi số năng lượng
dưới đây là **model mJ/commit**, không phải số đo phần cứng.

| Workload | Miền nguồn | Policy | Hoàn thành | Model mJ/commit |
|---|---|---|---:|---:|
{table}

![So sánh chính G8](../10_Experiments/g8/quality_20261023/main_comparison.png)

**RECAP_redo và RECAP_nominal không tạo thêm lợi ích so B3 trong tập chính.**
Chênh lệch VWW cỡ 1e-13 tương đối là nhiễu số, không diễn giải là cải thiện
hay suy giảm có ý nghĩa vật lý. Main chọn SAVE_DW = **{r['selected_save_dw_jobs']}** và
KEEP_PS = **{r['selected_keep_ps_jobs']}**. Test crossover chứng minh ranking có thể
chọn state trong mô hình, chưa chứng minh state-saving hữu ích ở miền chính.
Mục tiêu lợi ích chính 20% so đối chứng thích nghi **chưa đạt**.

Khoảng tin cậy so từng control (paired bootstrap 2.000 lần; ít replicate
độc lập trong mỗi family nên giới hạn tổng quát hóa còn lớn):

| Workload | Miền | RECAP_redo so với | Giảm model energy/commit | CI95 |
|---|---|---|---:|---|
{citable}

Không dùng lợi ích so B1 ở miền reset để thay thế phép so với B3 mạnh hơn.
Các ca chưa hoàn thành, zero source, energy undefined và p95 vô hạn được
giữ trong JSON. Đây là một đợt cùng host, không phải clean-host replay.

## Lợi ích của bỏ scratch-output — đánh giá phụ preset

So cùng policy và cùng sáu source cases đã khai báo, gồm steady và reset;
không trộn kết quả này với tập chính hoặc tuyên bố nó đạt mục tiêu 20%.

| Workload | Direct hoàn thành | Có scratch: model mJ/commit | Direct: model mJ/commit | Giảm |
|---|---:|---:|---:|---:|
{pubrows}

Đây là can thiệp lên đường publication và chi phí planner có thể phản ứng
theo đường đó. Kết quả có ý nghĩa trong model, chưa là tiết kiệm vật lý đo được.

## Bạn nên làm tiếp trên máy tính

1. Tự chạy `run_tests.py` và `check_project.py`; sau đó chạy một G8 run-id mới.
   Giải thích được marker, CRC, PS frontier và energy ledger trước khi bảo vệ.
2. Làm baseline tối ưu gần prior art, không chỉ control periodic; đối chiếu
   đầy đủ state/action/objective. Có thể nhờ giảng viên review từ xa, không cần lab.
3. Cải thiện mô hình expected-redo: outage trong operation, thời gian chờ
   recharge, cold weight reload và boot scan. G8 dùng approximation boundary;
   phải khóa protocol/holdout mới trước khi kiểm các thay đổi này.
4. Dùng thêm trace/data độc lập, xem completion/on-time cùng energy; không
   chỉnh cost giả định để tạo thắng lợi. Lợi ích so B3 vẫn là việc chưa giải quyết.
5. Dựng bootstrap từ checkout sạch hoặc một máy khác. Hiện vẫn cần prior
   artifacts/reference inputs; chưa có clean-host một lệnh đã xác minh.
6. Tạo commit cục bộ với metadata bạn chọn, tách code/evidence được phép chia
   sẻ khỏi dữ liệu có quyền riêng; chưa có public release/DOI.

## Bạn cần làm gì trên phần cứng?

**Hiện chưa cần mua board:** bạn đã xác nhận không có quyền tiếp cận lab.
Mô phỏng + RTL trên máy là phạm vi làm được ngay. Phần chưa thể nghiệm thu
là calibration, physical persistence và triển khai thật, phải giữ là giới hạn.

Nếu sau này hợp tác được với lab: chốt board/macro/NVM; thêm SPI/persistence
adapter; map/synthesize và đo runtime SRAM; power-cycle trong khi ghi; ghi
V(t), I(t) cùng event markers; điền cost profile; so mọi policy trên cùng
input/nguồn/deadline. FPGA logic/RAM không tự chứng minh năng lượng SRAM-CIM.
Xem [lộ trình chi tiết](../06_FPGA/HARDWARE_ROADMAP.md) và
[template calibration](../10_Experiments/calibration_template.json).

## Điều kiện chưa được phép bỏ qua

Chưa chọn macro/calibrate NVM/control, chưa có toàn mạng RTL, compiled CPU
arena, đo năng lượng, formal proof, đối chứng tối ưu gần nhất hoặc independent
human scientific review. Bản thảo G7 vẫn là bản lịch sử chưa sẵn sàng nộp;
chỉnh văn bản không thay thế những bằng chứng còn thiếu này.
'''
    report_path=ROOT/'02_Research/G8_deliverables.md';report_path.write_text(report,encoding='utf-8')
    inputs=[RUN/'results.json',RUN/'main.jsonl',RUN/'secondary.jsonl',DERIVED/'integrity_audit.json',Path(__file__)]
    outputs=[report_path,DERIVED/'software_readiness.json',DERIVED/'publication_ablation.json',DERIVED/'main_comparison.png']
    (DERIVED/'report_manifest.json').write_text(json.dumps(dict(scope='Derived report, not new experimental evidence',source_sha256={v.relative_to(ROOT).as_posix():sha(v) for v in inputs},output_sha256={v.relative_to(ROOT).as_posix():sha(v) for v in outputs}),indent=2)+'\n',encoding='utf-8')
    print('Current G8 report and source-bound figures generated.')

if __name__=='__main__':main()
