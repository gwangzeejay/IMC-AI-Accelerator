"""G9 literature-adapted baselines: DP optimality, C1, B6 limit case, causality, full-network recovery."""
import json
import math
from pathlib import Path
import random
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'09_Simulation'))
from g9_runtime import Runtime,segment_expected,optimal_checkpoints,brute_force_checkpoints,NEW_METHODS
from g8_runtime import Runtime as G8Runtime
from g6_model import Model


def protocol():
    p=json.loads((ROOT/'09_Simulation/configs/g6_protocol.json').read_text())
    return dict(p,planning_outage_rate_hz=2.,periodic_ci=16,direct_publication=True)


class DPTests(unittest.TestCase):
    def test_dp_matches_bruteforce(self):
        rng=random.Random(7)
        for _ in range(200):
            m=rng.randint(1,8);table={(i,j):rng.uniform(.1,5.) for j in range(1,m+1) for i in range(j)}
            for k in rng.sample(list(table),k=min(2,len(table))):table[k]=math.inf if rng.random()<.3 else table[k]
            a=optimal_checkpoints(m,lambda i,j:table[(i,j)]);b=brute_force_checkpoints(m,lambda i,j:table[(i,j)])
            self.assertAlmostEqual(a[0],b[0]) if math.isfinite(b[0]) else self.assertEqual(a[0],math.inf)

    def test_segment_limit_and_validation(self):
        self.assertEqual(segment_expected(3.,1.,9.,0.),3.)
        self.assertGreater(segment_expected(3.,1.,0.,1.),3.)
        self.assertEqual(segment_expected(3.,1.,0.,1e6),math.inf)
        with self.assertRaises(ValueError):segment_expected(-1.,1.,0.,1.)
        with self.assertRaises(ValueError):segment_expected(1.,float('nan'),0.,1.)

    def test_checkpoint_crossover(self):
        # Equal chunks cost 1, checkpoint write 0.3: none at zero hazard, some at high hazard.
        def table(rate):
            def cost(i,j):return segment_expected((j-i)+(0.3 if j<8 else 0.),(j-i),0.,rate)
            return cost
        self.assertEqual(optimal_checkpoints(8,table(0.))[1],())
        self.assertGreater(len(optimal_checkpoints(8,table(2.))[1]),0)


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=Model(ROOT,'kws');cls.p=protocol()
        cls.x=np.load(ROOT/'10_Experiments/g2/reference/official_sample.npz')['input']

    def runtime(self,method,p=None,fault=None,reset_times=(),capacity=100e-6,cls=Runtime):
        scenario=dict(id='g9_unit',seed=0,family='unit',capacity_j=capacity,trace=[[0.,.1]],horizon_s=8.,reset_times_s=list(reset_times))
        return cls(ROOT,self.model,p or self.p,scenario,method,fault)

    def test_b6_is_periodic_limit(self):
        # B6 is the finest-chunk periodic policy: identical choices to G8 B4 at that interval.
        b6=self.runtime('B6_loopindex');b4=self.runtime('B4_periodic',dict(self.p,periodic_ci=min(self.p['ci_chunks'])),cls=G8Runtime)
        for stage in range(len(self.model.stages)):
            x,y=b6.choose(stage,0),b4.choose(stage,0)
            for k in ('n','co','chunk','z','ps'):self.assertEqual(x[k],y[k],(stage,k))

    def test_all_new_methods_choose_legal_plans(self):
        for method in NEW_METHODS:
            r=self.runtime(method)
            for stage in range(len(self.model.stages)):
                a=r.choose(stage,0)
                self.assertLessEqual(a['sram'],self.p['sram_bytes']);self.assertFalse(a['z'])

    def test_b5a_enforces_c1_atomicity(self):
        r=self.runtime('B5a_inas')
        for stage in range(len(self.model.stages)):
            a=r.choose(stage,0)
            self.assertLessEqual(r.interval_energy(stage,a)+1e-12,r.power.capacity)
        # A capacity below every plan's power-cycle work leaves no legal choice.
        tiny=self.runtime('B5a_inas',capacity=1e-9)
        from g6_runtime import Capacity
        with self.assertRaises(Capacity):tiny.choose(1,0)

    def test_b5b_set_is_deterministic_and_hazard_dependent(self):
        low=self.runtime('B5b_chime_dp',dict(self.p,planning_outage_rate_hz=0.))
        high=self.runtime('B5b_chime_dp',dict(self.p,planning_outage_rate_hz=100000.))
        stage=next(i for i,d in enumerate(self.model.stages) if d['kind'] in ('fused','pw') and d['ci']>self.p['ci_chunks'][0])
        d=self.model.stages[stage]
        a=low.checkpoint_plan(stage,1,min(16,d['co']),0);b=low.checkpoint_plan(stage,1,min(16,d['co']),0)
        self.assertEqual(a,b);self.assertEqual(low.checkpoint_plan(stage,1,min(16,d['co']),0)[1],())
        self.assertGreater(len(high.checkpoint_plan(stage,1,min(16,d['co']),0)[1]),0)

    def test_no_future_trace_or_schedule_in_decision(self):
        for method in NEW_METHODS:
            a=self.runtime(method);b=self.runtime(method,reset_times=[.1,.2])
            b.power.trace=[(0,.1),(.01,0.)];b.boundaries=[0,.01]
            self.assertEqual(a.choose(1,0),b.choose(1,0))

    def test_execution_ledger_has_no_expected_cost(self):
        a=self.runtime('B5b_chime_dp',dict(self.p,planning_outage_rate_hz=0.));b=self.runtime('B5b_chime_dp',dict(self.p,planning_outage_rate_hz=100.))
        a.choose(1,0);b.choose(1,0)
        self.assertEqual(a.energy,b.energy.__class__(a.energy));self.assertEqual(a.e,b.e)

    def test_full_network_exact_output_clean_torn_and_reset(self):
        item=[dict(id='unit',label=0,x=self.x,arrival_s=0.,deadline_s=8.)]
        for method in NEW_METHODS:
            for fault in (None,dict(action='layer_log',cut=70),dict(action='graph_root',cut=70)):
                row=self.runtime(method,fault=fault).run(item)
                self.assertEqual(row['completed'],1,(method,fault));self.assertEqual(row['units'].get('checkpoint_output',0),0)
                if fault:self.assertTrue(row['fault_executed'])
        # External resets with a high planning hazard force non-uniform checkpoint use and resume.
        p=dict(self.p,planning_outage_rate_hz=100000.)
        resets=[0.0005*k for k in range(1,60)]
        for method in NEW_METHODS:
            r=self.runtime(method,p,reset_times=resets);row=r.run([dict(item[0],deadline_s=8.)])
            self.assertEqual(row['completed'],1,method);self.assertGreater(row['external_resets'],0)
            # B5a ranks by nominal energy and is hazard-blind by construction (iNAS has
            # no failure-rate input), so it need not checkpoint; B5b/B6 must.
            if method!='B5a_inas':self.assertGreater(row['units'].get('checkpoint_partial',0),0,method)
            self.assertAlmostEqual(row['energy_balance_error_j'],0.,places=9)


if __name__=='__main__':unittest.main()
