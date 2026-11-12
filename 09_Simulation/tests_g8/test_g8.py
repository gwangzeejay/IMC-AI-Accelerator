"""Boundary recovery, ranking causality and renewal-oracle tests for G8."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'09_Simulation'))
from g8_runtime import Runtime,OutageReservoir,expected_remaining
from g6_model import Model
from g6_storage import Store
from g5_runtime import Interrupted


def protocol():
    p=json.loads((ROOT/'09_Simulation/configs/g6_protocol.json').read_text())
    return dict(p,planning_outage_rate_hz=2.,periodic_ci=16,direct_publication=True)


class RenewalTests(unittest.TestCase):
    def test_matches_independent_linear_system(self):
        for keep in (False,True):
            costs=[2.,3.,5.,7.];q=[.1,.3,.4];recovery=[1.,2.,4.]
            a=np.eye(4);b=np.array(costs)
            for i in range(3):
                a[i,i+1]-=1-q[i];a[i,i+1 if keep else 0]-=q[i]
                b[i]+=q[i]*recovery[i]
            self.assertAlmostEqual(expected_remaining(costs,q,recovery,keep),np.linalg.solve(a,b)[0],places=12)

    def test_zero_hazard_no_replay_credit(self):
        self.assertEqual(expected_remaining([1.,2.,3.],[0.,0.],[9.,9.],False),6.)
        self.assertEqual(expected_remaining([1.,2.,3.],[0.,0.],[9.,9.],True),6.)

    def test_checkpoint_crossover(self):
        plain=lambda q:expected_remaining([1.,1.,1.],[q,q],[0.,0.],False)
        saved=lambda q:expected_remaining([1.2,1.2,1.],[q,q],[0.,0.],True)
        self.assertLess(plain(0),saved(0));self.assertLess(saved(.5),plain(.5))

    def test_invalid_probabilities_and_dimensions(self):
        for q in (1.,-1.,float('nan')):
            with self.assertRaises(ValueError):expected_remaining([1.,1.],[q],[0.],False)
        with self.assertRaises(ValueError):expected_remaining([],[],[],False)

    def test_external_disconnect_conserves_energy(self):
        r=OutageReservoir(1.,3.,1.,[(0.,.1)],1.,2.,reset_times=[.5,1.])
        dt,brown=r.advance(2.,.2)
        self.assertTrue(brown);self.assertAlmostEqual(dt,.5)
        self.assertEqual(r.external_resets,1);self.assertEqual(r.energy,0.)
        self.assertAlmostEqual(r.balance_error(),0.,places=12)
        r.advance(1.5,0.,stop_at_empty=False)
        self.assertEqual(r.external_resets,2);self.assertAlmostEqual(r.time,2.)
        self.assertAlmostEqual(r.balance_error(),0.,places=12)


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=Model(ROOT,'kws');cls.p=protocol()
        cls.x=np.load(ROOT/'10_Experiments/g2/reference/official_sample.npz')['input']

    def runtime(self,p=None,method='RECAP_redo',fault=None,reset_times=()):
        scenario=dict(id='g8_unit',seed=0,family='unit',capacity_j=100e-6,trace=[[0.,.1]],horizon_s=8.,reset_times_s=list(reset_times))
        return Runtime(ROOT,self.model,p or self.p,scenario,method,fault)

    def test_no_future_trace_or_schedule_in_decision(self):
        a=self.runtime();b=self.runtime(reset_times=[.1,.2])
        b.power.trace=[(0,.1),(.01,0.)];b.boundaries=[0,.01]
        self.assertEqual(a.choose(1,0),b.choose(1,0))

    def test_real_planner_changes_state_with_hazard(self):
        base=dict(self.p,tiles=[[1,16]],ci_chunks=[16])
        low=self.runtime(dict(base,planning_outage_rate_hz=0.)).choose(1,0)
        high=self.runtime(dict(base,planning_outage_rate_hz=100000.)).choose(1,0)
        self.assertFalse(low['ps']);self.assertTrue(high['ps'])

    def test_expected_cost_not_added_to_execution_ledger(self):
        a=self.runtime(dict(self.p,planning_outage_rate_hz=0.))
        b=self.runtime(dict(self.p,planning_outage_rate_hz=100.))
        aa=next(x for x in a.plans(1,0) if x['chunk']==16 and not x['ps'] and not x['z'])
        bb=next(x for x in b.plans(1,0) if x['chunk']==16 and not x['ps'] and not x['z'])
        self.assertGreater(bb['score_expected'],aa['score_expected'])
        self.assertEqual(a.energy,b.energy);self.assertEqual(a.e,b.e)

    def test_direct_log_every_byte_cut(self):
        s=Store(self.model,self.x,self.p,'g8_direct');out=bytes(range(16))
        ops,_=s.log_ops(1,0,1,16,0,out)
        for cut in range(len(ops)+1):
            s.memory=bytearray(len(s.memory));s.apply(ops,cut);r=s.scan(1)
            self.assertEqual(r['frontier'],16 if cut==len(ops) else 0)
            if r['frontier']:self.assertEqual(r['array'][:16].tobytes(),out)

    def test_committed_log_survives_torn_suffix(self):
        s=Store(self.model,self.x,self.p,'g8_suffix');a=bytes(range(16));b=bytes(range(16,32))
        ops,_=s.log_ops(1,0,1,16,0,a);s.apply(ops);initial=bytes(s.memory)
        ops,_=s.log_ops(1,16,1,16,140,b)
        for cut in range(len(ops)+1):
            s.memory=bytearray(initial);s.apply(ops,cut);r=s.scan(1)
            self.assertEqual(r['frontier'],32 if cut==len(ops) else 16)
            self.assertEqual(r['array'][:16].tobytes(),a)

    def test_external_reset_tears_action_without_admission_error(self):
        r=self.runtime(reset_times=[1e-4]);mut=[]
        with self.assertRaises(Interrupted):r.spend(1e-6,.001,'probe',100,mut.append)
        self.assertAlmostEqual(mut[0],.1);self.assertEqual(r.depletions,0)
        self.assertAlmostEqual(r.energy['probe'],1e-7)
        self.assertAlmostEqual(r.power.balance_error(),0.,places=12)

    def test_all_policies_share_publication(self):
        for method in ('B1_layer','B3_adaptive','RECAP_nominal','RECAP_redo','B4_periodic'):
            r=self.runtime(method=method)
            self.assertTrue(r.direct_publication)
            a=r.choose(1,0)
            self.assertLessEqual(a['sram'],self.p['sram_bytes'])

    def test_vww_layer_mapping_all_stage_geometries(self):
        model=Model(ROOT,'vww')
        s=dict(id='vww_geometry',seed=0,family='unit',capacity_j=100e-6,trace=[[0.,.1]],horizon_s=8.)
        r=Runtime(ROOT,model,self.p,s,'B1_layer')
        for stage,d in enumerate(model.stages):
            a=r.choose(stage,0)
            if a['co']<d['co']:self.assertEqual(a['n'],1)

    def test_full_network_direct_and_torn_log(self):
        for fault in (None,dict(action='layer_log',cut=70),dict(action='graph_root',cut=70)):
            r=self.runtime(fault=fault)
            row=r.run([dict(id='unit',label=0,x=self.x,arrival_s=0.,deadline_s=8.)])
            self.assertEqual(row['completed'],1)
            self.assertEqual(row['units'].get('checkpoint_output',0),0)
            if fault:self.assertTrue(row['fault_executed'])


if __name__=='__main__':unittest.main()
