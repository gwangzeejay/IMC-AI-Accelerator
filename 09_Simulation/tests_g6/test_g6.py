import copy
import json
from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'09_Simulation'))
from g6_model import Model
from g6_storage import Store,geometry
from g6_runtime import Runtime
from g5_runtime import Horizon,Interrupted
from g6_inputs import synthetic


class G6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=json.loads((ROOT/'09_Simulation/configs/g6_protocol.json').read_text())
        cls.models={n:Model(ROOT,n) for n in ('kws','vww')}
        cls.x={'kws':np.load(ROOT/'10_Experiments/g2/reference/official_sample.npz')['input'],
            'vww':np.load(ROOT/'05_Model_Training/reference_vww/coco_subset/inputs.npz')['x'][:1]}

    def runtime(self,name='kws',variant='full',**kwargs):
        s=dict(id='unit',seed=0,family='unit',capacity_j=100e-6,trace=[[0,.02]],horizon_s=8)
        return Runtime(ROOT,self.models[name],self.p,s,variant=variant,**kwargs)

    def test_full_arithmetic_matches_all_operators(self):
        for name,m in self.models.items():
            own=m.uninterrupted(self.x[name]);gold=m.reference(self.x[name])
            self.assertEqual(len(own),len(gold))
            for a,b in zip(own,gold):np.testing.assert_array_equal(a,b)

    def test_unfused_arithmetic_identical(self):
        m=Model(ROOT,'vww',False)
        for a,b in zip(m.uninterrupted(self.x['vww']),m.reference(self.x['vww'])):np.testing.assert_array_equal(a,b)

    def test_original_vww_infeasible(self):
        p=dict(self.p,nvm_bytes=self.p['original_nvm_bytes'])
        with self.assertRaises(ValueError):Store(self.models['vww'],self.x['vww'],p)
        self.assertGreater(max(d['input_bytes'] for d in self.models['vww'].stages),self.p['original_sram_bytes'])

    def test_extended_bounds_and_256_channel_prefix(self):
        m=self.models['vww'];s=Store(m,self.x['vww'],self.p);stage=len(m.stages)-2
        self.assertEqual(m.stages[stage]['ci'],256)
        z=bytes(8*256);ps=bytes(8*64*4)
        ops,_=s.scratch_ops(stage,0,8,64,128,z,ps);s.apply(ops)
        r=s.scratch(stage,0,8,64);self.assertEqual(r['offset'],128);self.assertEqual(r['ps'],ps)
        self.assertLessEqual(s.reserved_bytes,self.p['nvm_bytes'])

    def test_variable_tail_geometry_covers_output(self):
        for m in self.models.values():
            for d in m.stages:
                f=0
                while f<d['size']:
                    n,co=max(geometry(self.p,d,f),key=lambda nc:nc[0]*nc[1]);f+=n*co
                self.assertEqual(f,d['size'])

    def test_repeated_input_identity_not_reused(self):
        m=self.models['kws'];a=Store(m,self.x['kws'],self.p,'a');b=Store(m,self.x['kws'],self.p,'b')
        ops,_=a.root_ops(5,b'finished');a.apply(ops);b.memory=a.memory
        self.assertIsNone(b.root())

    def test_ignore_reload_only_changes_decision(self):
        a=self.runtime();b=self.runtime(variant='ignore_reload_decision');stage=1
        pa=a.plans(stage,0);pb=b.plans(stage,0)
        self.assertEqual(a.e,b.e);self.assertEqual(a.t,b.t)
        aa=next(x for x in pa if x['n']==8 and x['co']==64 and x['chunk']==64)
        bb=next(x for x in pb if x['n']==8 and x['co']==64 and x['chunk']==64)
        self.assertEqual(aa['bound'],bb['bound']);self.assertLess(bb['score_energy'],aa['score_energy'])

    def test_weight_residency_real_load_ledger(self):
        r=self.runtime();a=dict(n=1,co=64,c=0,chunk=64,z=False,ps=False)
        r.compute(0,a,execute=True);initial=r.units['weight_load']
        # First KWS conv blob is >2 KiB, cannot remain fully resident.
        r.compute(0,a,execute=True);self.assertGreater(r.units['weight_load'],initial)
        a=dict(n=1,co=16,c=0,chunk=16,z=False,ps=False)
        r.compute(1,a,need_dw=False,execute=True);before=r.units['weight_load']
        r.compute(1,a,need_dw=False,execute=True);self.assertEqual(r.units['weight_load'],before)
        self.assertGreater(r.bank_hits,0)

    def test_future_trace_not_used_by_policy(self):
        a=self.runtime();b=self.runtime()
        b.power.trace=[(0,.02),(1,0)];b.boundaries=[0,1]
        self.assertEqual(a.choose(1,0),b.choose(1,0))

    def test_event_wait_analytic_threshold(self):
        r=self.runtime();r.power.energy=0;r.power.initial=0
        r.observe(10e-6)
        self.assertAlmostEqual(r.power.time,(10e-6+1e-12)/(.02-self.p['retention_w']),places=10)
        self.assertAlmostEqual(r.power.balance_error(),0,places=12)

    def test_zero_harvest_no_zero_time_loop(self):
        r=self.runtime();r.power.trace=[(0,0)];r.boundaries=[0];r.power.energy=0;r.power.initial=0
        with self.assertRaises(Horizon):r.boot(Store(r.model,self.x['kws'],self.p))

    def test_active_leakage_charged_once(self):
        r=self.runtime();r.leak=1e-5;e,t=r.cost('write_byte',100)
        self.assertAlmostEqual(e,r.e['write_byte']*100+r.leak*t)
        ee,tt,ctrl,writes=r.write_cost(48,True)
        self.assertAlmostEqual(ee-r.e['write_byte']*writes-ctrl,r.leak*tt,places=14)

    def test_all_live_aux_capacity_and_crc(self):
        r=self.runtime('vww','all_live');s=Store(r.model,self.x['vww'],self.p,all_live=True)
        ops,length=s.aux_ops(1,0,16,bytes(40000),1);s.apply(ops)
        self.assertLessEqual(s.reserved_bytes,self.p['nvm_bytes']);self.assertEqual(length,40000)

    def test_source_seeds_unique(self):
        scenarios=synthetic(self.p);seeds=[a['seed'] for a in scenarios]
        self.assertEqual(len(seeds),len(set(seeds)));self.assertEqual(sum(a['ci_eligible'] for a in scenarios),40)


if __name__=='__main__':unittest.main()
