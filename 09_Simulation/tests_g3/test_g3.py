import json
from pathlib import Path
import sys
import unittest
from dataclasses import replace
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'09_Simulation'))
from recap.g3_workload import Mapping,mappings
from recap.g3_simulator import G3Simulator,run_workload
from g3_experiments import scenarios,rank_policies,paired_bootstrap,compare,cost_model,canonical_hash

PROTOCOL=json.loads((ROOT/'09_Simulation/configs/g3_protocol.json').read_text())
DIRECTORY=ROOT/'10_Experiments/g3/descriptors'
CATALOG=json.loads((DIRECTORY/'catalog.json').read_text())


def scenario(capacity=.001,power=.001,horizon=1):
    return dict(id='unit',family='unit',seed=0,capacity_j=capacity,trace=[[0,power]],horizon_s=horizon)


def row(name,sid='a',completed=1,energy=1):
    return dict(method=name,scenario_id=sid,family='one',completed=completed,total_inputs=1,
                energy_j=energy,on_time=completed,completion_s=.1 if completed else None)


class DescriptorTests(unittest.TestCase):
    def test_fixed_output_all_eight_spatial_co_partitions(self):
        cost=cost_model(ROOT,PROTOCOL)
        for (h,w) in PROTOCOL['spatial_tiles']:
            for co in PROTOCOL['co_tiles']:
                r=run_workload(DIRECTORY,CATALOG,Mapping(h,w,co,64,False,False),cost,scenario(),PROTOCOL)
                self.assertEqual(r['completed'],1)
                self.assertEqual(r['mismatches'],0)
                self.assertEqual(r['output_hash'],CATALOG['expected_output_sha256'])
                self.assertEqual(r['jobs_completed'],r['job_count'])

    def test_all_four_flags_with_actual_chunked_progress(self):
        for z in (False,True):
            for ps in (False,True):
                r=run_workload(DIRECTORY,CATALOG,Mapping(4,2,16,16,z,ps),cost_model(ROOT,PROTOCOL),scenario(),PROTOCOL)
                self.assertEqual(r['completed'],1)
                self.assertEqual(r['mismatches'],0)
                self.assertLessEqual(r['max_admission_excess_j'],1e-12)

    def test_nvm_capacity_includes_retained_outputs_and_copies(self):
        small=dict(PROTOCOL,nvm_bytes=1)
        r=run_workload(DIRECTORY,CATALOG,Mapping(4,2,16,64,False,False),cost_model(ROOT,PROTOCOL),scenario(),small)
        self.assertEqual(r['completed'],0)
        self.assertEqual(r['failure_reason'],'nvm_capacity')
        self.assertIsNone(r['metrics']['energy_per_completed_j'])

    def test_capacity_infeasible_never_becomes_completed(self):
        r=run_workload(DIRECTORY,CATALOG,Mapping(4,2,16,64,False,False),cost_model(ROOT,PROTOCOL),scenario(1e-9),PROTOCOL)
        self.assertEqual(r['completed'],0)
        self.assertEqual(r['failure_reason'],'admission_capacity')

    def test_weight_cache_reuse_changes_traffic_not_output(self):
        mapping=Mapping(1,1,4,64,False,False)
        a=run_workload(DIRECTORY,CATALOG,mapping,cost_model(ROOT,PROTOCOL),scenario(),PROTOCOL)
        b=run_workload(DIRECTORY,CATALOG,mapping,cost_model(ROOT,PROTOCOL),scenario(),PROTOCOL,reuse_weights=False)
        self.assertEqual(a['output_hash'],b['output_hash'])
        self.assertLess(a['breakdown']['LOAD_WEIGHT']['units'],b['breakdown']['LOAD_WEIGHT']['units'])


class G3RecoveryTests(unittest.TestCase):
    def sim(self,policy=None,faults=None):
        m=policy or Mapping(4,2,16,16,True,True)
        jobs=CATALOG['catalog'][f'h{m.h}w{m.w}_co{m.co}']['jobs']
        return G3Simulator(DIRECTORY/jobs[0]['path'],m.policy,slot_bytes=jobs[0]['slot_bytes'],
            bank_bytes=PROTOCOL['bank_bytes'],sram_bytes=PROTOCOL['sram_bytes'],
            frontier=bytearray(len(jobs)),job_index=0,faults=faults)

    def test_final_output_and_frontier_crash_order(self):
        base=self.sim();base.run()
        index=next(i for i,e in enumerate(base.ledger.events) if e['action']=='COMMIT_FRONTIER')
        for fraction in (0,.5,1):
            sim=self.sim(faults={index:fraction})
            r=sim.run()
            self.assertTrue(r['completed'])
            self.assertEqual(r['mismatches'],0)
            self.assertEqual(sim.frontier[0],1)

    def test_checkpoint_publish_crash(self):
        base=self.sim();base.run()
        index=next(i for i,e in enumerate(base.ledger.events) if e['action']=='COMMIT_CHECKPOINT' and e['phase']=='publish')
        for fraction in (0,.5,1):
            sim=self.sim(faults={index:fraction})
            self.assertEqual(sim.run()['mismatches'],0)

    def test_weight_tag_uses_payload_not_just_shape(self):
        sim=self.sim();sim.run()
        before=sim._tag('pw')
        changed=sim.nvm['wp'].copy();changed[0,0]=int(changed[0,0])+1 if int(changed[0,0])<127 else -128
        sim.nvm['wp']=changed
        self.assertNotEqual(before,sim._tag('pw'))
        sim._load('pw')
        self.assertEqual(sim.weight_banks['pw']['weight_tile_id'],sim._tag('pw'))

    def test_nonprefix_frontier_rejected(self):
        m=Mapping(1,1,4,16,True,True)
        sim=self.sim(m)
        sim.frontier[-1]=1
        with self.assertRaises(ValueError): sim.boot()


class EvaluationTests(unittest.TestCase):
    def test_disjoint_fixed_split_seeds(self):
        groups=[scenarios(PROTOCOL,s) for s in ('train','validation','test')]
        self.assertEqual([len(g) for g in groups],[6,6,18])
        seeds=[r['seed'] for g in groups for r in g]
        self.assertEqual(len(seeds),len(set(seeds)))
        self.assertTrue(all(r['seed']>=71000 for r in groups[2]))

    def test_protocol_goal_frozen(self):
        self.assertEqual(PROTOCOL['energy_reduction_goal'],.2)
        self.assertEqual(PROTOCOL['completion_tolerance_absolute'],.05)
        self.assertEqual(PROTOCOL['feasibility_reference'],'B3_micro')
        self.assertEqual(len(mappings(PROTOCOL)),64)

    def test_reject_incomplete_scenario_grid(self):
        with self.assertRaises(ValueError):
            rank_policies([row('a','one'),row('a','two'),row('b','one')],[row('ref')])

    def test_completion_constraint_beats_apparently_low_energy(self):
        rows=[row('cheap','one'),row('cheap','two',0,0),row('safe','one',1,2),row('safe','two',1,2)]
        ranked=rank_policies(rows,[row('ref','one'),row('ref','two')])
        self.assertEqual([r['method'] for r in ranked],['safe'])

    def test_no_energy_claim_at_lower_completion(self):
        a=[row('a','one',1,.1),row('a','two',0,.1)]
        b=[row('b','one'),row('b','two')]
        c=compare(a,b)
        self.assertGreater(c['relative_energy_reduction'],.2)
        self.assertFalse(c['noninferior_point_estimate'])
        self.assertFalse(c['meets_goal_point_estimate'])
        self.assertFalse(c['latency_nonregression_finite_only'])

    def test_bootstrap_does_not_hide_zero_denominators(self):
        a=[row('a','one',1,.1),row('a','two',0,.1)]
        b=[row('b','one'),row('b','two')]
        r=paired_bootstrap(a,b,200,10)
        self.assertGreater(r['undefined_replicates'],0)
        self.assertIsNone(r['energy_reduction_ci95'])

    def test_bootstrap_reproducible_and_paired(self):
        a=[row('a','one'),row('a','two')];b=[row('b','one',1,2),row('b','two',1,2)]
        self.assertEqual(paired_bootstrap(a,b,20,10),paired_bootstrap(a,b,20,10))
        with self.assertRaises(ValueError): paired_bootstrap(a,b[:1],20,10)

    def test_cost_profile_not_calibration(self):
        c=cost_model(ROOT,PROTOCOL,300,4)
        self.assertFalse(c.calibrated)
        self.assertIn('ASSUMED',c.provenance)


if __name__=='__main__': unittest.main()
