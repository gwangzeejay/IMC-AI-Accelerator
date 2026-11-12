"""Decision-rule tests for the pre-registered G9 analysis on synthetic rows."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'09_Simulation'));sys.path.insert(0,str(ROOT/'10_Experiments'))
import analyze_g9 as A


def protocol():
    p={}
    for n in ('g6_protocol.json','g8_protocol.json','g9_protocol.json'):p.update(json.loads((ROOT/'09_Simulation/configs'/n).read_text()))
    return p


def row(sc,energy,completed=3,chosen=None):
    return dict(scenario_id=sc,family='f',energy_j=energy,completed=completed,total_inputs=3,on_time_rate=completed/3,
        statuses=[dict(arrival_s=0.,committed_s=1.)]*completed+[dict(arrival_s=0.,committed_s=None)]*(3-completed),
        outputs=[dict(correct=1)]*completed,losses=0,chosen=chosen or {'p1_co16_ci16_z0ps0':1})


def cell(p,recap_e,control_e,saving=True,recap_completed=3):
    sc=[f's{i}' for i in range(p['grid']['replicates_per_cell'])]
    ch={'p1_co16_ci16_z0ps1':1} if saving else {'p1_co16_ci16_z0ps0':1}
    by={pol:[row(s,control_e*(1+.01*i)) for i,s in enumerate(sc)] for pol in p['policies']}
    by[p['recap_primary']]=[row(s,recap_e*(1+.01*i),recap_completed,ch) for i,s in enumerate(sc)]
    return by


class AnalysisTests(unittest.TestCase):
    def test_clear_win_with_mechanism(self):
        p=protocol();c=A.classify_cell(cell(p,.9,1.),p)
        self.assertEqual(c['label'],'win');self.assertTrue(all(v['win'] for v in c['controls'].values()))

    def test_win_without_state_saving_not_counted(self):
        p=protocol();self.assertEqual(A.classify_cell(cell(p,.9,1.,saving=False),p)['label'],'win_without_state_saving')

    def test_below_delta_is_tie(self):
        p=protocol();self.assertEqual(A.classify_cell(cell(p,.99,1.),p)['label'],'tie_or_inconclusive')

    def test_loss_detected(self):
        p=protocol();self.assertEqual(A.classify_cell(cell(p,1.1,1.),p)['label'],'loss_to_some_control')

    def test_noninferiority_blocks_win(self):
        p=protocol();c=A.classify_cell(cell(p,.5,1.,recap_completed=1),p)
        self.assertNotEqual(c['label'],'win')

    def test_one_worse_control_prevents_cell_win(self):
        p=protocol();by=cell(p,.9,1.);by['B5b_chime_dp']=[row(r['scenario_id'],.5) for r in by['B5b_chime_dp']]
        self.assertNotEqual(A.classify_cell(by,p)['label'],'win')

    def test_region_requires_neighbours(self):
        self.assertTrue(A.has_region([(0,0,0),(1,0,0)]));self.assertTrue(A.has_region([(0,0,0),(0,0,1)]))
        self.assertFalse(A.has_region([(0,0,0),(1,1,0)]));self.assertFalse(A.has_region([(0,0,0),(2,0,0)]));self.assertFalse(A.has_region([(0,0,0)]))

    def test_verdict_and_scale_scope(self):
        p=protocol();win=dict(label='win')
        cells={('kws',0,0,0):win,('kws',1,0,0):win,('vww',2,0,0):win,('vww',3,0,0):win}
        self.assertEqual(A.verdict(cells,p)['verdict'],'REGION_BOTH_WORKLOADS')
        self.assertEqual(A.verdict(cells,p,(0.25,1.0))['verdict'],'REGION_ONE_WORKLOAD')
        self.assertEqual(A.verdict(cells,p,(100.,200.))['verdict'],'NO_REGION')

    def test_protocol_is_internally_consistent(self):
        p=protocol();self.assertTrue(set(p['strong_controls'])<=set(p['policies']));self.assertIn(p['recap_primary'],p['policies'])
        self.assertNotIn('B6_loopindex',p['policies']);r=p['grounded_nvm_scale_range'];self.assertEqual(len(r),2);self.assertLess(r[0],r[1]);self.assertGreater(r[0],0)


if __name__=='__main__':unittest.main()
