# G8 evidence directory

Current pointers: `CURRENT.json`. Only runs with a final manifest/report and
passing current-source hashes are usable as current evidence. Failed or
superseded attempts are kept explicitly for transparency.

- `20261023-v2`: full G8_1.1 network evaluation.
- `rtl-20261023-v3`: actual Icarus/VVP and Yosys execution for the standalone
  direct publisher, with source/tool/artifact hashes.

Run IDs are immutable. Use a new ID when rerunning. No runner overwrites G2-G6.
An audit checks saved evidence; it is not a fresh experiment replay.
