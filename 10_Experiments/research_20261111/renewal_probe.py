"""Analytical checkpoint study with failures inside compute and write phases.

This dimensionless model has an independent Poisson reset process, constant
power in each phase, a reliable restart with fixed energy cost, and persistent
segment boundaries. It excludes recharge, finite horizons, weight-bank state,
and a physical memory protocol. It is a research diagnostic for G9 design.
"""

import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


OUT = Path(__file__).resolve().parent
SEED = 20261111


def segment_energy(phases, hazard, restart_energy):
    """Expected energy until one persistent boundary, including failed tries.

    A phase is (duration, power). Every reset returns to the beginning of
    this segment. The energy of a partial phase is charged up to the reset.
    Restart consumes fixed energy and is assumed reliable. On completion,
    the final phase publishes the segment, so no later reset rolls it back.
    """
    duration = sum(seconds for seconds, _ in phases)
    if hazard == 0:
        return sum(seconds * power for seconds, power in phases)
    elapsed = 0.0
    attempt_energy = 0.0
    for seconds, power in phases:
        survival = math.exp(-hazard * elapsed)
        attempt_energy += power * survival * (-math.expm1(-hazard * seconds)) / hazard
        elapsed += seconds
    success_probability = math.exp(-hazard * duration)
    expected_failures = math.expm1(hazard * duration)
    return attempt_energy / success_probability + restart_energy * expected_failures


def policies(checkpoint_duration):
    """One unit of useful compute at unit power, plus common final write.

    The checkpoint has twice compute power. Its duration determines its
    energy and exposure to resets. An interrupted checkpoint leaves the
    previous persistent boundary valid. A successful midpoint checkpoint
    preserves exactly half of the useful computation.
    """
    final_write = (0.02, 2.0)
    return {
        "replay_whole": [[(1.0, 1.0), final_write]],
        "checkpoint_half": [
            [(0.5, 1.0), (checkpoint_duration, 2.0)],
            [(0.5, 1.0), final_write],
        ],
    }


def expected_energy(segments, hazard, restart_energy):
    return sum(segment_energy(phases, hazard, restart_energy) for phases in segments)


def monte_carlo(segments, hazard, restart_energy, trials, seed):
    """Simulate reset timestamps directly, without the analytical recurrence."""
    rng = np.random.default_rng(seed)
    energy = np.zeros(trials)
    for phases in segments:
        duration = sum(seconds for seconds, _ in phases)
        unfinished = np.arange(trials)
        while unfinished.size:
            reset_time = rng.exponential(1.0 / hazard, unfinished.size)
            consumed = np.zeros(unfinished.size)
            elapsed = 0.0
            for seconds, power in phases:
                consumed += power * np.clip(reset_time - elapsed, 0.0, seconds)
                elapsed += seconds
            failed = reset_time < duration
            energy[unfinished] += consumed + restart_energy * failed
            unfinished = unfinished[failed]
    return float(energy.mean()), float(energy.std(ddof=1) / math.sqrt(trials))


def main():
    restart_energy = 0.2
    trials = 100_000
    validation = []
    for case, (hazard, checkpoint_duration) in enumerate(
        [(0.1, 0.01), (0.5, 0.05), (1.0, 0.1), (3.0, 0.2)]
    ):
        for index, (name, segments) in enumerate(policies(checkpoint_duration).items()):
            expected = expected_energy(segments, hazard, restart_energy)
            observed, standard_error = monte_carlo(
                segments, hazard, restart_energy, trials, SEED + case * 10 + index
            )
            standardized_error = abs(observed - expected) / standard_error
            if standardized_error > 6:
                raise AssertionError((name, hazard, expected, observed, standard_error))
            validation.append(
                dict(
                    policy=name,
                    hazard=hazard,
                    checkpoint_duration=checkpoint_duration,
                    analytic_energy=expected,
                    simulated_mean=observed,
                    simulated_standard_error=standard_error,
                    error_in_standard_errors=standardized_error,
                    trials=trials,
                )
            )

    # Constant-power closed form, zero-reset limit, and checkpoint overhead.
    for hazard in (0.01, 0.1, 1.0, 3.0):
        actual = segment_energy([(1.0, 1.0)], hazard, 0.0)
        assert math.isclose(actual, math.expm1(hazard) / hazard, rel_tol=1e-12)
    nominal = policies(0.05)
    assert math.isclose(expected_energy(nominal["replay_whole"], 0, 0.2), 1.04)
    assert math.isclose(expected_energy(nominal["checkpoint_half"], 0, 0.2), 1.14)
    one_segment = segment_energy([(1.0, 1.0)], 1.0, 0.0)
    assert one_segment > 1.0  # A single chunk still has reset exposure.

    hazard_axis = np.geomspace(0.01, 3.0, 180)
    checkpoint_axis = np.geomspace(0.001, 0.5, 160)
    reduction = np.empty((checkpoint_axis.size, hazard_axis.size))
    for row, checkpoint_duration in enumerate(checkpoint_axis):
        plans = policies(float(checkpoint_duration))
        for column, hazard in enumerate(hazard_axis):
            replay = expected_energy(plans["replay_whole"], float(hazard), restart_energy)
            saved = expected_energy(plans["checkpoint_half"], float(hazard), restart_energy)
            reduction[row, column] = 100.0 * (1.0 - saved / replay)

    fig, ax = plt.subplots(figsize=(9.2, 5.8), constrained_layout=True)
    grid = ax.pcolormesh(
        hazard_axis, checkpoint_axis, reduction, cmap="RdBu", vmin=-60, vmax=60,
        shading="auto", rasterized=True,
    )
    contour = ax.contour(hazard_axis, checkpoint_axis, reduction, levels=[0], colors="black")
    ax.clabel(contour, fmt="break-even", fontsize=9, inline=False, manual=[(0.5, 0.05)])
    ax.set(xscale="log", yscale="log")
    ax.set_xlabel("Reset rate × useful compute duration (dimensionless)")
    ax.set_ylabel("Checkpoint duration / useful compute duration")
    ax.set_title("When does a midpoint checkpoint reduce expected energy?", loc="left")
    fig.colorbar(grid, ax=ax, label="Expected energy reduction vs whole-block replay (%)", extend="both")
    fig.text(
        0.01, -0.035,
        "Illustrative Poisson model · interruptible compute and writes · reliable restart cost 0.2\n"
        "Checkpoint/write power 2× compute · final write duration 0.02 · hardware coefficients uncalibrated",
        fontsize=9,
    )
    fig.savefig(OUT / "checkpoint_frontier.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    examples = []
    for hazard in (0.01, 0.1, 0.5, 1.0, 3.0):
        plans = policies(0.05)
        values = {name: expected_energy(p, hazard, restart_energy) for name, p in plans.items()}
        examples.append(
            dict(
                hazard=hazard,
                checkpoint_duration=0.05,
                **values,
                relative_energy_reduction=1.0 - values["checkpoint_half"] / values["replay_whole"],
            )
        )
    result = dict(
        study="Dimensionless interruptible-operation renewal probe",
        date="2026-11-11",
        calibrated=False,
        scope="Analytical diagnosis and Monte Carlo validation for proposed G9 model",
        assumptions=[
            "Independent exponential reset times with a fixed rate",
            "Piecewise constant phase power and deterministic phase duration",
            "Successful segment boundaries remain persistent",
            "Checkpoint publication is atomic only at segment completion",
            "Reliable restart with fixed energy; its duration is excluded",
            "No capacitor, recharge, finite horizon, deadlines, or memory corruption",
            "Dimensionless coefficients selected for illustration, not fitted to RECAP results",
        ],
        restart_energy=restart_energy,
        monte_carlo_checks=validation,
        closed_form_and_zero_hazard_checks="PASS",
        examples=examples,
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        figure_sha256=hashlib.sha256((OUT / "checkpoint_frontier.png").read_bytes()).hexdigest(),
    )
    (OUT / "renewal_probe.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(checks=len(validation), max_error_se=max(v["error_in_standard_errors"] for v in validation), examples=examples), indent=2))


if __name__ == "__main__":
    main()
