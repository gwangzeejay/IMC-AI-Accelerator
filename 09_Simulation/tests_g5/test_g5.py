import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'09_Simulation'))
from g4_reference import decode
from g5_storage import Store
from g5_runtime import Runtime
from g5_experiments import aggregate,bootstrap,comparison


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.p=json.loads((ROOT/'09_Simulation/configs/g5_protocol.json').read_text())
        self.x=np.zeros((1,49,10,1),dtype=np.int8)
        self.s=Store('11'*32,self.x,self.p)

    def test_scratch_every_ack_boundary_preserves_old_or_new(self):
        s=self.s;n=4;co=64
        ops,_=s.scratch_ops(1,0,n,co,16,z=bytes(256),ps=bytes(1024));s.apply(ops)
        ops,_=s.scratch_ops(1,0,n,co,32,z=bytes([1])*256,ps=bytes([2])*1024)
        before=bytes(s.memory)
        for cut in range(len(ops)+1):
            s.memory[:]=before;s.apply(ops,cut);r=s.scratch(1,0,n,co)
            self.assertIsNotNone(r)
            self.assertIn(r['offset'],(16,32))
            self.assertEqual(r['z'],bytes(256) if r['offset']==16 else bytes([1])*256)
            self.assertEqual(r['ps'],bytes(1024) if r['offset']==16 else bytes([2])*1024)

    def test_output_every_boundary_never_publishes_torn_bytes(self):
        s=self.s;ops,_=s.scratch_ops(1,0,4,64,64,out=bytes(range(256)))
        for cut in range(len(ops)+1):
            s.memory[:]=bytes(len(s.memory));s.apply(ops,cut);r=s.scratch(1,0,4,64)
            if r is not None:self.assertEqual(r['output'],bytes(range(256)))
        self.assertEqual(s.scratch(1,0,4,64)['offset'],64)

    def test_layer_log_every_boundary(self):
        s=self.s;ops,_=s.log_ops(0,0,4,64,0,bytes(range(256)))
        for cut in range(len(ops)+1):
            s.memory[:]=bytes(len(s.memory));s.apply(ops,cut);r=s.scan(0)
            self.assertIn(r['frontier'],(0,256))
            if r['frontier']:self.assertEqual(r['array'][:256].tobytes(),bytes(range(256)))

    def test_root_every_boundary(self):
        s=self.s;ops,_=s.root_ops(0,b'old');s.apply(ops)
        ops,_=s.root_ops(1,b'new');before=bytes(s.memory)
        for cut in range(len(ops)+1):
            s.memory[:]=before;s.apply(ops,cut)
            self.assertIn(s.stage(),(0,1))
            self.assertEqual(s.root()['output'][4:36],hashlib.sha256(b'old' if s.stage()==0 else b'new').digest())

    def test_stale_input_rejected_without_erasing(self):
        ops,_=self.s.root_ops(0,b'old');self.s.apply(ops)
        other=Store('11'*32,self.x+1,self.p);other.memory=self.s.memory
        self.assertIsNone(other.root())

    def test_same_feature_different_arrival_rejected(self):
        a=Store('11'*32,self.x,self.p,invocation='arrival0')
        ops,_=a.root_ops(5,b'done');a.apply(ops)
        b=Store('11'*32,self.x,self.p,invocation='arrival1');b.memory=a.memory
        self.assertIsNone(b.root())

    def test_crc_and_identity_corruption_fail_closed(self):
        s=self.s;ops,_=s.scratch_ops(1,0,4,64,64,out=bytes(256));s.apply(ops)
        before=bytes(s.memory)
        for address in (8,40,72,104,116,120,124,255):
            s.memory[:]=before;s.memory[s.scratch_base+address]^=1
            self.assertIsNone(s.scratch(1,0,4,64))

    def test_capacity_and_full_layer_coverage(self):
        s=self.s;offset=0;f=0
        while f<8000:
            ops,_=s.log_ops(0,f,1,16,offset,bytes([f%127])*16);s.apply(ops)
            offset+=140;f+=16
        self.assertEqual(offset,self.p['layer_log_bytes'])
        self.assertEqual(s.scan(0)['frontier'],8000)
        self.assertLessEqual(s.reserved_bytes,self.p['nvm_bytes'])

    def test_source_integrity_checked_after_root(self):
        s=self.s;offset=f=0
        while f<8000:
            n=min(8,125-f//64);payload=bytes(n*64)
            ops,_=s.log_ops(0,f,n,64,offset,payload);s.apply(ops)
            offset+=124+len(payload);f+=len(payload)
        ops,_=s.root_ops(0,bytes(8000));s.apply(ops)
        self.assertEqual(s.restore()[0],0)
        s.memory[124]^=1
        with self.assertRaises(ValueError):s.restore()

    def test_no_future_harvest_policy_input(self):
        class Dummy:pass
        scenario=dict(id='x',seed=0,family='x',capacity_j=25e-6,trace=[[0,0],[1,100]],horizon_s=2)
        a=Runtime(ROOT,Dummy(),self.p,scenario,'RECAP')
        b=Runtime(ROOT,Dummy(),self.p,dict(scenario,trace=[[0,0],[1,0]]),'RECAP')
        self.assertEqual(a.choose(1,0),b.choose(1,0))

    def test_zero_harvest_terminates_at_horizon(self):
        class Dummy:model_hash='11'*32
        p=dict(self.p,initial_energy_fraction=0)
        scenario=dict(id='zero',seed=0,family='zero',capacity_j=25e-6,trace=[[0,0]],horizon_s=.1)
        r=Runtime(ROOT,Dummy(),p,scenario,'RECAP').run([dict(id='zero',label=0,x=self.x,arrival_s=0,deadline_s=.1)])
        self.assertEqual(r['completed'],0);self.assertIsNone(r['energy_per_completed_j'])
        self.assertTrue(r['p95_is_infinite'])

    def test_bootstrap_keeps_undefined_replicates(self):
        row=dict(scenario_id='x',family='x',total_inputs=1,completed=0,energy_j=1,on_time_rate=0,
            statuses=[dict(arrival_s=0,deadline_s=1)],outputs=[],losses=0)
        p=dict(self.p,bootstrap_replicates=10)
        b=bootstrap([row],[row],p)
        self.assertEqual(b['undefined_replicates'],10);self.assertIsNone(b['energy_reduction_ci95'])
        self.assertFalse(comparison([row],[row],p)['latency_nonregression_finite_only'])


if __name__=='__main__':unittest.main()
