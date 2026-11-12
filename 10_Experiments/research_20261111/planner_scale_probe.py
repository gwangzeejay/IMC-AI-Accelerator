"""Inspect first-tile planning times under the frozen G8 cost assumptions.

Each stage is queried from a fresh runtime with an empty weight bank, full
100-uJ capacitor and frontier zero. These are planning diagnostics, with no
inference execution, recharge, boot scan or physical measurements.
"""

import hashlib
import json
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "09_Simulation"))

from g6_model import Model
from g8_runtime import Runtime


def main():
    protocol_path = ROOT / "10_Experiments/g8/20261023-v2/protocol.json"
    protocol = json.loads(protocol_path.read_text())
    scenario = dict(
        id="g8_planning_scale_probe", seed=0, family="diagnostic",
        capacity_j=100e-6, trace=[[0.0, 0.002]], horizon_s=24.0,
    )
    rows = []
    models = {}
    for workload in protocol["workloads"]:
        model = Model(ROOT, workload)
        models[workload] = model.model_hash
        for stage, descriptor in enumerate(model.stages):
            runtime = Runtime(ROOT, model, protocol, scenario, "RECAP_redo")
            plan = runtime.choose(stage, 0)
            duration = plan["score_time"] * plan["n"] * plan["co"]
            exposure = protocol["planning_outage_rate_hz"] * duration
            rows.append(
                dict(
                    workload=workload, stage=stage, kind=descriptor["kind"],
                    ci=descriptor["ci"], co=descriptor["co"],
                    spatial_tile=plan["n"], channel_tile=plan["co"],
                    ci_chunk=plan["chunk"], save_dw=plan["z"], keep_ps=plan["ps"],
                    nominal_tile_duration_s=duration,
                    hazard_times_tile_duration=exposure,
                    poisson_reset_probability_during_nominal_tile=-math.expm1(-exposure),
                )
            )
    sources = [protocol_path, Path(__file__), ROOT / "09_Simulation/g8_runtime.py", ROOT / "09_Simulation/g6_runtime.py", ROOT / "09_Simulation/g6_model.py"]
    report = dict(
        date="2026-11-11", calibrated=False,
        scope="First-tile cold-bank planning query per stage under inherited G8 assumed costs; no inference run",
        excluded=["Idle/recharge", "boot and destination scanning", "full-inference probability", "physical power measurements"],
        planning_hazard_hz=protocol["planning_outage_rate_hz"],
        model_sha256=models,
        source_sha256={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        rows=rows,
    )
    destination = Path(__file__).with_suffix(".json")
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    fused = [r for r in rows if r["kind"] == "fused"]
    print(json.dumps(dict(
        stages=len(rows), fused_stages=len(fused),
        minimum_fused_tile_duration_s=min(r["nominal_tile_duration_s"] for r in fused),
        maximum_fused_tile_duration_s=max(r["nominal_tile_duration_s"] for r in fused),
        maximum_fused_reset_probability=max(r["poisson_reset_probability_during_nominal_tile"] for r in fused),
    ), indent=2))


if __name__ == "__main__":
    main()
