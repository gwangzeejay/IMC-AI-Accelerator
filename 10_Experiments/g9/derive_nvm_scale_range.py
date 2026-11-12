"""Derive the grounded nvm_energy_scale range for G9 from datasheet currents.

Chip-only, streaming estimate: E_byte = VDD * I * (8 SPI clocks / f_SCK).
Compared with the inherited G6 assumed coefficients (read 1 nJ/B, write 2 nJ/B at 200 ns/B).
Not measured transaction or board energy; SPI master/IO, level shifting, controller and
converter losses are NOT included, so true energy is higher (unquantified).
All numbers below are transcribed from the cited datasheet tables (see locators).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
G6_READ_J, G6_WRITE_J, T_BYTE_S, VDD = 1e-9, 2e-9, 200e-9, 3.3

DEVICES = [
    dict(name='Infineon FM25V20A (FRAM)', tech='FRAM', source='fm25v20a_rev_j.pdf (local, sha256 63c9dfae...), Table 11, p.19',
         read_ma=dict(typ=2.4, max=3.0), write_ma=dict(typ=2.4, max=3.0), note='no write delay; 40 MHz'),
    dict(name='RAMXEED/Fujitsu MB85RS2MTA (FRAM)', tech='FRAM', source='MB85RS2MTA-DS6v1-E.pdf, DC table, PDF p.13 (IDD @40 MHz: 1.9 typ / 2.3 max)',
         read_ma=dict(typ=1.9, max=2.3), write_ma=dict(typ=1.9, max=2.3), note='single operating-current row applied to read and write; VDD 3.3 V column; "takes no wait time"'),
    dict(name='Everspin MR25H10 (MRAM)', tech='MRAM', source='MR25H10 Rev. 9.5 (3/2018), Table 3.4, PDF p.12 (distributor copy, not the vendor site)',
         read_ma=dict(typ=6.0, max=10.0), write_ma=dict(typ=23.0, max=27.0), note='"No write delays"; 40 MHz'),
]
EXCLUDED = [dict(name='Winbond W25Q64PW (NOR flash, 1.8 V)', reason='Needs erase before program and programs in <=256 B pages; not a byte-granular atomic-log medium. Reference numbers: program 8 mA typ x 1.8 V x 0.12 ms typ = 1.73 uJ per page (6.75 nJ/B if full; write ratio ~3.4x G6); 4 KB sector erase 30 ms typ x 8 mA x 1.8 V = 432 uJ (105 nJ/B amortised; ratio ~53x, beyond the grid). W25Q64PW Rev D, DC table PDF p.66, AC p.69.')]

def e(ma):
    return VDD * ma * 1e-3 * T_BYTE_S

rows, ratios = [], []
for d in DEVICES:
    for cond in ('typ', 'max'):
        er, ew = e(d['read_ma'][cond]), e(d['write_ma'][cond])
        r = dict(device=d['name'], condition=cond, read_j_per_byte=er, write_j_per_byte=ew, ratio_read=er / G6_READ_J, ratio_write=ew / G6_WRITE_J)
        rows.append(r)
        ratios += [r['ratio_read'], r['ratio_write']]
lo, hi = min(ratios), max(ratios)
out = dict(schema='g9_nvm_scale_range_v1', derived='2026-11-11', vdd_v=VDD, t_byte_s=T_BYTE_S, g6_read_j=G6_READ_J, g6_write_j=G6_WRITE_J,
           devices=DEVICES, excluded=EXCLUDED, rows=rows, grounded_nvm_scale_range=[round(lo, 3), round(hi, 3)],
           rule='range = [min, max] over included devices, typ and max conditions, of device_energy/G6_coefficient for read and write separately; byte-addressable no-erase NVM only',
           limitations=['Chip-only lower bound; SPI master/IO, level shifting, controller, converter, startup are not included.',
                        'One scale multiplies read and write equally; G6 write/read = 2 while FRAM ~1 and MRAM ~3.8, so no single scale matches every device.',
                        'MR25H10 figures come from a distributor copy of Rev 9.5; MB85RS2MTA assumes the same IDD for read and write.',
                        'On-chip embedded NVM (far lower pJ/byte) and flash with erase (far higher) are outside this range and outside the verdict.'])
path = ROOT / '02_Research/hardware_selection/nvm_scale_range.json'
path.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
print(out['grounded_nvm_scale_range'])
for r in rows:
    print(f"{r['device'][:28]:28} {r['condition']}: read x{r['ratio_read']:.3f}  write x{r['ratio_write']:.3f}")
