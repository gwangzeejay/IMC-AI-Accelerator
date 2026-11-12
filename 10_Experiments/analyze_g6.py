"""Post-hoc mechanism diagnostics; never tune policies or alter held-out results."""
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'09_Simulation'))
from g5_experiments import sha,dump,comparison
from g6_model import Model
from g6_runtime import Runtime


def run():
    out=ROOT/'10_Experiments/g6';dest=ROOT/'10_Experiments/g6_analysis';dest.mkdir(exist_ok=True)
    p=json.loads((out/'protocol_snapshot.json').read_text());result=json.loads((out/'results.json').read_text())
    scenarios={a['id']:a for a in json.loads((out/'scenarios.json').read_text())}
    rows=[json.loads(line) for line in (out/'raw/main.jsonl').read_text().splitlines()]
    material=[a for a in result['losing_trace_comparisons'] if a['completion_difference']<0 or
        (a['relative_energy_reduction'] is not None and a['relative_energy_reduction'] < -1e-6 and abs(a['a_energy_j']-a['b_energy_j'])>1e-9)]
    dump(dest/'material_loss_cases.json',dict(scope='descriptive numerical-noise filter, not statistical significance or a changed success criterion',
        energy_ratio_threshold=1e-6,absolute_energy_threshold_j=1e-9,raw_negative_records=len(result['losing_trace_comparisons']),cases=material))
    steady={}
    for name in p['workloads']:
        totals={}
        for method in ('RECAP','B1_layer'):
            c=Counter()
            for row in rows:
                if row['workload']==name and row['method']==method and scenarios[row['scenario_id']]['source_kind']=='steady':c.update(row['breakdown_j'])
            totals[method]=dict(total_j=sum(c.values()),scratch_j=sum(v for k,v in c.items() if k.startswith('checkpoint')),
                log_j=sum(v for k,v in c.items() if k.startswith('layer_log')),weight_load_j=c['weight_load'])
        delta=totals['RECAP']['total_j']-totals['B1_layer']['total_j']
        steady[name]=dict(ledger=totals,extra_recap_energy_j=delta,
            scratch_fraction_of_difference=None if delta<=0 else totals['RECAP']['scratch_j']/delta,
            scope='same source/arrivals; interpret component difference only with completion counts and finite horizon')
    budget=[]
    for name in p['workloads']:
        for domain in ('stochastic','measured'):
            part=[r for r in rows if r['workload']==name and r['method']=='RECAP' and
                (scenarios[r['scenario_id']]['source_kind'] in ('mild','severe') if domain=='stochastic' else scenarios[r['scenario_id']]['source_kind'].startswith('eth'))]
            available=0
            for row in part:
                s=scenarios[row['scenario_id']];trace=s['trace']
                available+=s['capacity_j']*p['initial_energy_fraction']+sum(v*((trace[i+1][0] if i+1<len(trace) else s['horizon_s'])-t) for i,(t,v) in enumerate(trace))
            consumed=sum(r['energy_j'] for r in part)
            budget.append(dict(workload=name,domain=domain,assumed_rail_supply_plus_initial_capacitor_j=available,
                consumed_j=consumed,consumed_fraction=consumed/available,
                scope='source-budget diagnostic only; energy/commit denominator remains all completed arrivals, not harvested energy'))
    dominance=[]
    for name in p['workloads']:
        model=Model(ROOT,name);s=dict(id='objective_diagnostic',seed=0,family='diagnostic',capacity_j=100e-6,trace=[[0,.1]],horizon_s=8)
        runtime=Runtime(ROOT,model,p,s)
        comparisons=0;strictly_costlier=0
        for stage,d in enumerate(model.stages):
            if d['kind']!='fused':continue
            plans=runtime.plans(stage,0);baseline={(a['n'],a['co'],a['chunk']):a for a in plans if not a['z'] and not a['ps']}
            for a in plans:
                if not a['z'] and not a['ps']:continue
                b=baseline[(a['n'],a['co'],a['chunk'])];comparisons+=1
                strictly_costlier+=a['score_energy']>b['score_energy']+1e-15
        chosen=Counter()
        for r in rows:
            if r['workload']==name and r['method']=='RECAP':chosen.update(r['chosen'])
        dominance.append(dict(workload=name,diagnostic_same_geometry_chunk_pairs=comparisons,
            save_state_strictly_costlier=strictly_costlier,main_selected_save_dw_jobs=sum(v for k,v in chosen.items() if '_z1' in k),
            main_selected_keep_ps_jobs=sum(v for k,v in chosen.items() if k.endswith('ps1')),
            interpretation='Current nominal per-job objective lacks expected redo credit; saving state adds cost without modeled objective benefit. This is an algorithm limitation, not proof that saving is useless.'))
    report=dict(status='G6_POST_HOC_MECHANISM_DIAGNOSTICS',recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        policies_refitted=False,heldout_inference_rerun=False,primary_metrics_unchanged=True,
        material_loss_comparisons=len(material),steady_checkpoint_ledger=steady,source_budget=budget,
        state_objective_dominance=dominance,
        interpretation_scope='descriptive diagnostics after primary test; no causal hardware validation or new confirmed improvement')
    dump(dest/'analysis.json',report)
    dump(dest/'manifest.json',dict(command='python 10_Experiments/analyze_g6.py',g6_run_manifest_sha256=sha(ROOT/'10_Experiments/manifests/g6_run.json'),
        sha256={'10_Experiments/analyze_g6.py':sha(Path(__file__))}|{f.relative_to(ROOT).as_posix():sha(f) for f in dest.glob('*.json') if f.name!='manifest.json'}))
    print(json.dumps(dict(status=report['status'],material_loss_comparisons=len(material),state_objective_dominance=dominance)))


if __name__=='__main__':run()
