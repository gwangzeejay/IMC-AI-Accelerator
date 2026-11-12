"""G9 literature-adapted baselines on the unchanged G8 backend.

Adds three policies; G2-G8 sources and frozen evidence are untouched. Every
cost remains an assumption (calibrated=False). These are ADAPTATIONS to this
backend's action space, not reproductions of the cited systems:

* B5a_inas      iNAS-style execution/preservation design explorer. Candidate
                (tile, preservation batch S=CI chunk) with the C0 SRAM check
                (already in plans) and C1 atomicity (one power cycle's work must
                fit the capacitor). Objective: minimum nominal energy per
                output, a stand-in for iNAS end-to-end latency in the
                recharge-dominated regime. Adapted from the public iNAS code
                (IEExplorer/explore_intpow.py, CostModel/cnn.py), not from the
                paper. iNAS has no DW-save action, so z is always False.
* B5b_chime_dp  Chime-style checkpoint placement: dynamic programming over CI
                boundaries minimizing expected cost under an exponential failure
                hazard with restart-to-last-checkpoint. Positions need not be
                periodic. Hazard is the same fixed planning rate used by G8.
* B6_loopindex  Finest-granularity progress preservation. In this backend it is
                the limiting case of the periodic family (interval = the finest
                CI chunk) and coincides with B4_periodic at that interval; the
                in-place NVM accumulation of the cited mechanism is not
                representable here (see test_b6_is_periodic_limit).
"""
import itertools
import math
from g8_runtime import Runtime as G8Runtime
from g6_runtime import Capacity

NEW_METHODS = ('B5a_inas', 'B5b_chime_dp', 'B6_loopindex')


def segment_expected(cost, seconds, recovery, rate):
    """Expected cost of one checkpoint segment with restart-to-start on failure.

    Exponential hazard `rate` over `seconds` of active time. Wasted partial work
    is charged: E = cost*expm1(x)/x + expm1(x)*recovery, x = rate*seconds. The
    x -> 0 limit is `cost`. Returns inf if the exponent would overflow.
    """
    if cost < 0 or seconds < 0 or recovery < 0 or rate < 0 or not all(map(math.isfinite, (cost, seconds, recovery, rate))):
        raise ValueError('invalid segment inputs')
    x = rate * seconds
    if x < 1e-12:
        return cost
    if x > 50:
        return math.inf
    m = math.expm1(x)
    return cost * m / x + m * recovery


def optimal_checkpoints(m, seg_cost):
    """DP over boundaries 0..m. seg_cost(i, j) may be inf (infeasible).

    Returns (best_total, saved_boundaries) where saved excludes 0 and m.
    Ties keep the longer earlier segment (fewer checkpoints).
    """
    if m < 1:
        raise ValueError('m must be >= 1')
    best = [math.inf] * (m + 1)
    prev = [0] * (m + 1)
    best[0] = 0.
    for j in range(1, m + 1):
        for i in range(j):
            if best[i] == math.inf:
                continue
            total = best[i] + seg_cost(i, j)
            if total < best[j]:
                best[j], prev[j] = total, i
    saved = []
    j = m
    while j > 0 and best[m] < math.inf:
        i = prev[j]
        if i > 0:
            saved.append(i)
        j = i
    return best[m], tuple(sorted(saved))


def brute_force_checkpoints(m, seg_cost):
    """Exhaustive reference for tests (small m)."""
    best, arg = math.inf, ()
    for r in range(m):
        for subset in itertools.combinations(range(1, m), r):
            cuts = (0,) + subset + (m,)
            total = sum(seg_cost(a, b) for a, b in zip(cuts, cuts[1:]))
            if total < best:
                best, arg = total, subset
    return best, arg


class Runtime(G8Runtime):
    def __init__(self, root, model, p, scenario, method='B5a_inas', fault=None):
        super().__init__(root, model, p, scenario, method=method, fault=fault)
        self.interval_cache = {}
        self.dp_cache = {}
        self.base_chunk = min(p['ci_chunks'])

    # ---- helpers -------------------------------------------------------------
    def _plans_with_chunk(self, stage, f, chunk, d):
        return [a for a in self.plans(stage, f) if a['chunk'] == min(chunk, d['ci']) and not a['z']]

    def interval_energy(self, stage, a):
        """Largest single power-cycle workload of a plan (iNAS C1 quantity)."""
        d = self.model.stages[stage]
        key = (stage, a['c'], a['n'], a['co'], a['chunk'], a['ps'], self.bank)
        if key in self.interval_cache:
            return self.interval_cache[key]
        n, co, ci, kind = a['n'], a['co'], d['ci'], d['kind']
        dw_e = 0.
        if kind == 'fused':
            dw_e = sum(self.cost(k, u)[0] for k, u, _ in self.dw_phase(stage, a))
        prefixes = list(range(0, ci, a['chunk'])) if kind in ('fused', 'pw') else [0]
        worst = 0.
        for idx, prefix in enumerate(prefixes):
            e = sum(self.cost(k, u)[0] for k, u, _ in self.compute(stage, a, prefix, need_dw=False))
            if idx == 0:
                e += dw_e
            if prefix + a['chunk'] < ci and a['ps']:
                e += self.write_cost(4 * n * co)[0]
            if idx == len(prefixes) - 1:
                e += self.write_cost(n * co, False)[0]
            worst = max(worst, e)
        if len(self.interval_cache) > 4000:
            self.interval_cache.clear()
        self.interval_cache[key] = worst
        return worst

    def checkpoint_plan(self, stage, n, co, c):
        """Chime-style DP save set for one tile geometry, cold weight bank.

        Deterministic in (stage, n, co, c): a rebooted runtime recomputes the
        same set and resumes from the durable offset without extra state.
        Returns (expected_total_energy, saved_boundaries_in_ci_units, base_chunk).
        """
        key = (stage, n, co, c)
        if key in self.dp_cache:
            return self.dp_cache[key]
        d = self.model.stages[stage]
        ci, g = d['ci'], min(self.base_chunk, d['ci'])
        m = math.ceil(ci / g)
        a = dict(n=n, co=co, c=c, chunk=g, z=False, ps=True)
        saved_bank = self.bank
        self.bank = b''
        try:
            dw_e = dw_t = 0.
            if d['kind'] == 'fused':
                dw = self.dw_phase(stage, a)
                dw_e = sum(self.cost(k, u)[0] for k, u, _ in dw)
                dw_t = sum(self.cost(k, u)[1] for k, u, _ in dw)
            out_e, out_t, _, _ = self.write_cost(n * co, False)
            ps_e, ps_t, _, _ = self.write_cost(4 * n * co)
            boot_e, _ = self.cost('boot', 1)
            rec_e, _ = self.cost('read_byte', 124 + 4 * n * co)
            seg_cache = {}

            def seg(i, j):
                if (i, j) in seg_cache:
                    return seg_cache[(i, j)]
                length = min(ci, j * g) - i * g
                acts = self.compute(stage, dict(a, chunk=length), i * g, need_dw=False)
                e = sum(self.cost(k, u)[0] for k, u, _ in acts)
                t = sum(self.cost(k, u)[1] for k, u, _ in acts)
                bound = e
                if i == 0:
                    e, t = e + dw_e, t + dw_t
                    bound = max(bound, dw_e)
                if j < m:
                    e, t = e + ps_e, t + ps_t
                    bound = max(bound, ps_e)
                else:
                    e, t = e + out_e, t + out_t
                    bound = max(bound, out_e)
                if bound * (1 + self.p['admission_margin_fraction']) + 1e-12 > self.power.capacity:
                    value = math.inf
                else:
                    recovery = boot_e + (rec_e if i > 0 else 0.) + dw_e
                    value = segment_expected(e, t, recovery, self.planning_rate)
                seg_cache[(i, j)] = value
                return value

            total, saved = optimal_checkpoints(m, seg)
        finally:
            self.bank = saved_bank
        result = (total, saved, g)
        if len(self.dp_cache) > 4000:
            self.dp_cache.clear()
        self.dp_cache[key] = result
        return result

    # ---- policy --------------------------------------------------------------
    def choose(self, stage, f):
        if self.method not in NEW_METHODS:
            return super().choose(stage, f)
        d = self.model.stages[stage]
        if not self.plans(stage, f):
            raise Capacity('no memory/energy-feasible mapping')
        if self.control:
            self.action('decision', 1, 'runtime_decision_assumed')
        self.decisions += 1
        chunkable = d['kind'] in ('fused', 'pw')
        reserve_ok = lambda a: a['bound'] <= self.power.energy - self.p['reserve_fraction'] * self.power.capacity
        if self.method == 'B6_loopindex' or (self.method == 'B5a_inas' and not chunkable) or (self.method == 'B5b_chime_dp' and not chunkable):
            chunk = self.base_chunk if self.method == 'B6_loopindex' else d['ci']
            subset = [a for a in self.plans(stage, f) if a['chunk'] == min(chunk, d['ci']) and not a['z'] and a['ps'] == (min(chunk, d['ci']) < d['ci'])]
            if self.method != 'B6_loopindex':
                subset = subset or [a for a in self.plans(stage, f) if not a['z']]
            field = 'score_energy'
        elif self.method == 'B5a_inas':
            subset = [a for a in self.plans(stage, f) if not a['z'] and a['ps'] == (a['chunk'] < d['ci'])]
            cap = self.power.capacity
            subset = [a for a in subset if self.interval_energy(stage, a) * (1 + self.p['admission_margin_fraction']) + 1e-12 <= cap]
            field = 'score_energy'
        else:  # B5b_chime_dp
            g = min(self.base_chunk, d['ci'])
            subset = [dict(a) for a in self._plans_with_chunk(stage, f, g, d) if a['ps'] == (g < d['ci'])]
            field = 'score_dp'
            for a in subset:
                total, saved, _ = self.checkpoint_plan(stage, a['n'], a['co'], a['c'])
                a['score_dp'] = total / (a['n'] * a['co'])
            subset = [a for a in subset if math.isfinite(a['score_dp'])]
        if not subset:
            raise Capacity('baseline contract has no feasible mapping')
        subset = [a for a in subset if reserve_ok(a)] or subset
        chosen = min(subset, key=lambda a: (a[field], a['score_energy'], -a['n'] * a['co'], -a['chunk']))
        self.max_sram = max(self.max_sram, chosen['sram'])
        self.ranking[field] += 1
        self.choices[f"p{chosen['n']}_co{chosen['co']}_ci{chosen['chunk']}_z{int(chosen['z'])}ps{int(chosen['ps'])}"] += 1
        return dict(chosen)

    # ---- execution -----------------------------------------------------------
    def tile(self, store, stage, source, f, a):
        d = self.model.stages[stage]
        if self.method != 'B5b_chime_dp' or d['kind'] not in ('fused', 'pw'):
            return super().tile(store, stage, source, f, a)
        import numpy as np
        kind, n, co = d['kind'], a['n'], a['co']
        p, c = divmod(f, d['co'])
        a['c'] = c
        self.max_sram = max(self.max_sram, self.footprint(stage, a))
        old = store.scratch(stage, f, n, co)
        if old and old['output'] is not None:
            return old['output']
        _, saved, g = self.checkpoint_plan(stage, n, co, c)
        boundaries = sorted(set(saved)) + [math.ceil(d['ci'] / g)]
        ps = self.model.bias(stage, n, c, co) if old is None or old['ps'] is None else np.frombuffer(old['ps'], dtype='<i4').reshape(n, co).copy()
        prefix = old['offset'] if old else 0
        z = source.reshape(-1, d['ci'])[p:p + n].copy() if kind == 'pw' else None
        if z is None:
            self.dw_phase(stage, a, execute=True)
            z = self.model.dw(stage, source, p, n)
        while prefix < d['ci']:
            stop_unit = next(b for b in boundaries if b * g > prefix)
            stop = min(d['ci'], stop_unit * g)
            seg = dict(a, chunk=stop - prefix, z=False, ps=True)
            key = (store.ids[1], stage, f, n, co, prefix, stop)
            actions = self.compute(stage, seg, prefix, need_dw=False, execute=True)
            if key in self.seen:
                self.repeated_range_macs += sum(u for k, u, _ in actions if k in ('dw_mac', 'pw_mac'))
            self.seen.add(key)
            ps = self.model.pw(stage, z, ps, prefix, stop, c, co)
            prefix = stop
            if prefix < d['ci']:
                ops, length = store.scratch_ops(stage, f, n, co, prefix, None, ps.astype('<i4').tobytes())
                self.write(store, ops, length, 'checkpoint_partial')
                old = store.scratch(stage, f, n, co)
        return self.model.finish(stage, ps, c, co).tobytes()
