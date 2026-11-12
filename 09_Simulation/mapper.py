"""G2 finite causal-policy selection; not the full G3 RECAP mapper."""
import math
from recap.simulator import Policy


def candidates(chunks=(8,16,32)):
    return [Policy(z,ps,chunk) for chunk in chunks for z in (False,True) for ps in (False,True)]


def choose_policy(rows, minimum_completion=0.0, minimum_on_time=0.0):
    """Rows are TRAIN scenarios only; ratio of weighted sums, not mean ratios.

    Each row: policy, energy_j, completed, total_inputs, on_time, weight.
    Runtime policies contain no future-trace data. Caller must freeze selected
    policy before a separate held-out test; this helper does not enforce splits.
    """
    if not 0<=minimum_completion<=1 or not 0<=minimum_on_time<=1:
        raise ValueError('invalid feasibility threshold')
    totals={}
    if not rows:
        raise ValueError('empty training scenarios')
    for row in rows:
        energy=row['energy_j']
        if energy is None:
            raise ValueError('cannot optimize unknown energy')
        if not all(math.isfinite(row[k]) for k in ('energy_j','completed','total_inputs','on_time','weight')):
            raise ValueError('nonfinite training result')
        if energy<0 or row['weight']<=0 or not 0<=row['on_time']<=row['completed']<=row['total_inputs'] or row['total_inputs']<=0:
            raise ValueError('invalid training counts/weights')
        entry=totals.setdefault(row['policy'],[0.0,0.0,0.0,0.0])
        for i,key in enumerate(('energy_j','completed','total_inputs','on_time')):
            entry[i]+=row[key]*row['weight']
    feasible=[]
    for policy,(energy,completed,total,on_time) in totals.items():
        if completed>0 and completed/total>=minimum_completion and on_time/total>=minimum_on_time:
            feasible.append((energy/completed,policy))
    if not feasible:
        raise ValueError('no feasible policy with positive completions')
    ratio,policy=min(feasible)
    return dict(policy=policy,energy_per_completed_j=ratio,scope='minimum only in supplied finite training-policy set')
