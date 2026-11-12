"""Fixed-horizon counts and nearest-rank p95, including unfinished inputs."""
import math


def summarize_inputs(inputs, horizon_s, total_energy_j):
    if horizon_s<=0 or not inputs:
        raise ValueError('positive horizon and nonempty input list required')
    completed=failed=on_time=0
    latencies=[]
    for item in inputs:
        arrival,deadline=item['arrival_s'],item['deadline_s']
        if not all(math.isfinite(x) for x in (arrival,deadline)) or not 0<=arrival<=deadline<=horizon_s:
            raise ValueError('arrival/deadline outside observation')
        done=item.get('committed_s')
        if done is not None:
            if not math.isfinite(done) or not arrival<=done<=horizon_s or item.get('failed',False):
                raise ValueError('invalid terminal input status')
            completed+=1
            on_time+=int(done<=deadline)
            latencies.append(done-arrival)
        else:
            failed+=int(item.get('failed',False))
            latencies.append(math.inf)
    p95=sorted(latencies)[math.ceil(.95*len(inputs))-1]
    return dict(completed=completed,failed=failed,incomplete=len(inputs)-completed-failed,
                completion_rate=completed/len(inputs),on_time_rate=on_time/len(inputs),
                throughput_per_s=completed/horizon_s,
                energy_per_completed_j=None if completed==0 or total_energy_j is None else total_energy_j/completed,
                p95_latency_s=None if math.isinf(p95) else p95,p95_is_infinite=math.isinf(p95))
