import json
import math
from pathlib import Path
import sys
import unittest
import numpy as np

SIM=Path(__file__).resolve().parents[1]
ROOT=SIM.parent
sys.path.insert(0,str(SIM))
from recap.integer import (high_mul, rounding_divide_pot, multiply_quantized,
    quantize_multiplier, depthwise, pointwise, accumulator_bound, I32_MIN, I32_MAX)
from recap.cost import CostModel, Ledger
from recap.power import Reservoir
from recap.storage import TwoSlotStore, MARKER, PAYLOAD_START
from recap.simulator import Simulator, Policy
from recap.metrics import summarize_inputs
from mapper import choose_policy

FIXTURE=ROOT/'10_Experiments/g2/reference/microtile.npz'


class IntegerTests(unittest.TestCase):
    def test_gemmlowp_edges(self):
        self.assertEqual(high_mul(I32_MIN,I32_MIN),I32_MAX)
        self.assertEqual(high_mul(1,1<<30),1)
        self.assertEqual(high_mul(-1,1<<30),0)
        self.assertEqual(rounding_divide_pot(-3,1),-2)
        self.assertEqual(rounding_divide_pot(3,1),2)
        m,s=quantize_multiplier(1.0)
        for x in (-128,-1,0,1,127):
            self.assertEqual(multiply_quantized(x,m,s),x)

    def test_reject_accumulator_overflow(self):
        with self.assertRaises(OverflowError):
            accumulator_bound(np.full((200000,1),127,dtype=np.int8),np.array([0],dtype=np.int32),-128)
        with self.assertRaises(OverflowError):
            multiply_quantized(I32_MAX,1<<30,1)

    def test_padding_is_input_zero_point_and_stride(self):
        m,s=quantize_multiplier(1)
        spec=dict(input_zero_point=7,output_zero_point=0,multipliers=[m],shifts=[s],
                  activation_min=-128,activation_max=127,padding='SAME',stride=[2,2])
        x=np.full((1,3,3,1),8,dtype=np.int8)
        y=depthwise(x,np.ones((3,3,1),dtype=np.int8),np.zeros(1,dtype=np.int32),spec)
        np.testing.assert_array_equal(y,np.full((1,2,2,1),4,dtype=np.int8))

    def test_activation_and_signedness(self):
        m,s=quantize_multiplier(1)
        spec=dict(input_zero_point=0,output_zero_point=-128,multipliers=[m],shifts=[s],activation_min=-128,activation_max=127)
        y=pointwise(np.array([[[[127]]]],dtype=np.int8),np.array([[127]],dtype=np.int8),np.zeros(1,dtype=np.int32),spec)
        self.assertEqual(int(y.item()),127)
        with self.assertRaises(TypeError):
            pointwise(np.ones((1,1,1,1),dtype=np.uint8),np.ones((1,1),dtype=np.int8),np.zeros(1,dtype=np.int32),spec)


class RecoveryTests(unittest.TestCase):
    def base(self,policy=Policy(True,True)):
        sim=Simulator(FIXTURE,policy)
        result=sim.run()
        self.assertTrue(result['completed'])
        return sim

    def test_publish_visibility_and_cold_state(self):
        base=self.base()
        cut=next(i for i,e in enumerate(base.ledger.events) if e['action']=='COMMIT_CHECKPOINT' and e['phase']=='publish')
        for fraction,expected in [(0,0),(.5,0),(1,16)]:
            sim=Simulator(FIXTURE,Policy(True,True),faults={cut:fraction})
            sim.run(max_events=cut+1)
            self.assertIsNone(sim.ps)
            self.assertIsNone(sim.pending_txn)
            self.assertEqual(sim.weight_banks,{})
            _,r=sim.store.latest()
            self.assertEqual(0 if r is None else r['offset'],expected)
            self.assertEqual(sim.run()['mismatches'],0)

    def test_save_without_ps_never_promotes_offset(self):
        base=self.base(Policy(True,False))
        cut=next(i for i,e in enumerate(base.ledger.events) if e['phase']=='publish')
        sim=Simulator(FIXTURE,Policy(True,False),faults={cut:1})
        sim.run(max_events=cut+1)
        _,r=sim.store.latest()
        self.assertEqual(r['offset'],0)
        self.assertNotIn('ps',r['arrays'])
        self.assertIn('z',r['arrays'])
        self.assertEqual(sim.run()['mismatches'],0)

    def test_previous_nonzero_prefix_survives_keep_ps_false(self):
        base=self.base()
        cut=next(i for i,e in enumerate(base.ledger.events) if e['phase']=='publish')
        sim=Simulator(FIXTURE,Policy(True,True))
        sim.run(max_events=cut+1)
        self.assertEqual(sim.progress_d,16)
        sim.policy=Policy(False,False)
        class Pause(Exception): pass
        original=sim._commit
        def pause(final=False):
            original(final)
            raise Pause()
        sim._commit=pause
        with self.assertRaises(Pause): sim.run()
        self.assertEqual(sim.offset,32)
        self.assertEqual(sim.record['offset'],16)
        saved=sim.store.payload(sim.slot,sim.record,'ps')
        self.assertFalse(np.array_equal(saved,sim.ps))
        sim._commit=original
        sim._loss()
        sim.policy=Policy(True,True)
        self.assertEqual(sim.run()['mismatches'],0)

    def test_payload_and_metadata_corruption_fall_back(self):
        for location in (PAYLOAD_START,37):
            sim=self.base()
            latest,_=sim.store.latest()
            sim.store.slots[latest][location]^=1
            sim._loss()
            self.assertEqual(sim.run()['mismatches'],0)

    def test_identity_mismatch_is_not_restored(self):
        sim=self.base()
        sim.store.identity=dict(sim.identity,input_id='different_input')
        self.assertIsNone(sim.store.latest()[1])

    def test_capacity_rejected(self):
        with self.assertRaises(ValueError): Simulator(FIXTURE,Policy(True,True),nvm_bytes=8192)
        with self.assertRaises(ValueError): Simulator(FIXTURE,Policy(True,True),sram_bytes=512)
        with self.assertRaises(ValueError): Simulator(FIXTURE,Policy(True,True),bank_bytes=32)
        with self.assertRaises(ValueError): TwoSlotStore({},slot_bytes=128)

    def test_replay_is_accounted_not_added_twice(self):
        base=self.base(Policy(False,False))
        index=next(i for i,e in enumerate(base.ledger.events) if e['action']=='COMPUTE_PW')
        sim=Simulator(FIXTURE,Policy(False,False),faults={index:1})
        r=sim.run()
        self.assertEqual(r['mismatches'],0)
        self.assertGreater(r['ledger']['breakdown']['COMPUTE_PW']['replay_units'],0)
        self.assertIsNone(r['ledger']['total_energy_j'])

    def test_restore_interrupted_repeatedly(self):
        base=self.base()
        publish=next(i for i,e in enumerate(base.ledger.events) if e['phase']=='publish')
        probe=Simulator(FIXTURE,Policy(True,True),faults={publish:1})
        probe.run()
        primitives=[e for e in probe.ledger.events if e['action']!='POWER_LOSS']
        restore=next(i for i,e in enumerate(primitives) if e['action']=='RESTORE_PAYLOAD')
        sim=Simulator(FIXTURE,Policy(True,True),faults={publish:1,restore:.5,restore+1:.5})
        r=sim.run()
        self.assertEqual(r['unexpected_losses'],3)
        self.assertEqual(r['mismatches'],0)

    def test_underpowered_horizon_reports_incomplete(self):
        cost=CostModel(**json.loads((SIM/'configs/g2_assumed_debug.json').read_text()))
        sim=Simulator(FIXTURE,Policy(True,True),cost,Reservoir(1e-5,3.3,2,[(0,0)],0,.01))
        r=sim.run()
        self.assertFalse(r['completed'])
        self.assertEqual(r['failure_reason'],'horizon')
        self.assertEqual(r['power_losses'],0)


class PowerCostTests(unittest.TestCase):
    def test_unknown_is_not_zero(self):
        cost=CostModel({'read_byte':1e-9},{'read_byte':1e-6},None)
        ledger=Ledger({},cost)
        ledger.record('READ','test','read_byte',4)
        self.assertIsNone(ledger.summary()['total_energy_j'])
        with self.assertRaises(ValueError): Reservoir(1,2,1,[(0,0)],0,1).admit(None)

    def test_same_harvest_different_load_different_failure(self):
        r=Reservoir(2,2,1,[(0,.5)],1,10)
        elapsed,lost=r.advance(4,1.5)
        self.assertTrue(lost)
        self.assertAlmostEqual(elapsed,1)
        r2=Reservoir(2,2,1,[(0,.5)],1,10)
        elapsed2,lost2=r2.advance(4,.6)
        self.assertFalse(lost2)
        self.assertEqual(elapsed2,4)
        self.assertAlmostEqual(r.balance_error(),0)

    def test_conservative_admission_and_spillage(self):
        r=Reservoir(1,2,1,[(0,10)],1,10)
        self.assertFalse(r.admit(1.1))
        self.assertTrue(r.admit(.9,.1))
        r.advance(1,0)
        self.assertAlmostEqual(r.energy,1.5)
        self.assertAlmostEqual(r.balance_error(),0)

    def test_piecewise_boundary_and_partial_cost(self):
        r=Reservoir(1,3,1,[(0,2),(.5,0)],1,2)
        dt,lost=r.advance(2,1)
        self.assertTrue(lost)
        self.assertAlmostEqual(dt,2)
        self.assertAlmostEqual(r.balance_error(),0)
        cost=CostModel({'compute':2},{'compute':1},0,'test',False)
        ledger=Ledger({},cost)
        ledger.record('COMPUTE','partial','compute',10,.25)
        self.assertEqual(ledger.summary()['total_energy_j'],5)

    def test_coupled_ledgers_and_reserved_units(self):
        cost=CostModel(**json.loads((SIM/'configs/g2_assumed_debug.json').read_text()))
        for p in (Policy(False,False),Policy(False,True),Policy(True,False),Policy(True,True)):
            reservoir=Reservoir(1e-4,3.3,2,[(0,0)],.0001,1)
            sim=Simulator(FIXTURE,p,cost,reservoir)
            r=sim.run()
            self.assertTrue(r['completed'])
            self.assertEqual(r['unexpected_losses'],0)
            self.assertAlmostEqual(reservoir.consumed,r['ledger']['total_energy_j'],places=12)
            self.assertAlmostEqual(reservoir.balance_error(),0,places=12)

    def test_completed_transfer_roundoff_never_tears_marker(self):
        cost=CostModel(**json.loads((SIM/'configs/g2_assumed_debug.json').read_text()))
        sim=Simulator(FIXTURE,Policy(True,True),cost,Reservoir(1e-5,3.3,2,[(0,.0004)],0,1))
        r=sim.run()
        self.assertTrue(r['completed'])
        self.assertEqual(r['unexpected_losses'],0)
        self.assertEqual(sim.store.latest()[1]['offset'],64)


class MetricsMapperTests(unittest.TestCase):
    def test_fixed_horizon_undefined_energy_and_infinite_p95(self):
        inputs=[dict(arrival_s=0,deadline_s=1,committed_s=.5),dict(arrival_s=0,deadline_s=1)]
        r=summarize_inputs(inputs,1,4)
        self.assertEqual(r['energy_per_completed_j'],4)
        self.assertTrue(r['p95_is_infinite'])
        self.assertEqual(r['incomplete'],1)
        self.assertIsNone(summarize_inputs(inputs[1:],1,4)['energy_per_completed_j'])
        self.assertIsNone(summarize_inputs(inputs,1,None)['energy_per_completed_j'])

    def test_mapper_ratio_of_sums_and_constraints(self):
        rows=[dict(policy='a',energy_j=10,completed=10,total_inputs=10,on_time=10,weight=1),
              dict(policy='a',energy_j=90,completed=1,total_inputs=10,on_time=1,weight=1),
              dict(policy='b',energy_j=200,completed=20,total_inputs=20,on_time=20,weight=1)]
        self.assertEqual(choose_policy(rows)['policy'],'a')
        self.assertEqual(choose_policy(rows,minimum_completion=.9)['policy'],'b')
        rows[0]['energy_j']=None
        with self.assertRaises(ValueError): choose_policy(rows)

    def test_mapper_zero_completions_infeasible(self):
        with self.assertRaises(ValueError):
            choose_policy([dict(policy='x',energy_j=1,completed=0,total_inputs=1,on_time=0,weight=1)])


if __name__=='__main__':
    unittest.main()
