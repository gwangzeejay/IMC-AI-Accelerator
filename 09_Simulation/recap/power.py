"""Analytic piecewise-constant harvest coupled to actual load at capacitor rail."""
import bisect
import math


class Reservoir:
    def __init__(self, capacitance_f, v_max, v_off, trace, initial_energy_j, horizon_s):
        values=[capacitance_f,v_max,v_off,initial_energy_j,horizon_s]
        if not all(math.isfinite(v) for v in values) or capacitance_f <= 0 or not v_max > v_off >= 0 or horizon_s <= 0:
            raise ValueError('invalid capacitor/horizon')
        self.capacity=0.5*capacitance_f*(v_max*v_max-v_off*v_off)
        if not 0 <= initial_energy_j <= self.capacity:
            raise ValueError('initial energy out of range')
        self.trace=[(float(t),float(p)) for t,p in trace]
        if not self.trace or self.trace[0][0]!=0 or any(not math.isfinite(t) or not math.isfinite(p) or p<0 for t,p in self.trace):
            raise ValueError('trace must start at zero with finite nonnegative power')
        if any(a[0]>=b[0] for a,b in zip(self.trace,self.trace[1:])):
            raise ValueError('trace times must strictly increase')
        self.energy=initial_energy_j
        self.initial=initial_energy_j
        self.time=0.0
        self.horizon=horizon_s
        self.harvested=self.consumed=self.spilled=0.0

    def admit(self, bound_j, margin_j=0.0):
        if bound_j is None:
            raise ValueError('cannot admit unknown energy')
        if not math.isfinite(bound_j) or not math.isfinite(margin_j) or bound_j<0 or margin_j<0:
            raise ValueError('invalid reserve')
        return self.energy >= bound_j+margin_j

    def advance(self, seconds, load_w, stop_at_empty=True):
        if not math.isfinite(seconds) or seconds<0 or not math.isfinite(load_w) or load_w<0:
            raise ValueError('invalid time/load')
        start=self.time
        end=min(start+seconds,self.horizon)
        brownout=False
        while self.time < end-1e-15:
            i=bisect.bisect_right([t for t,_ in self.trace],self.time)-1
            harvest=self.trace[i][1]
            boundary=self.trace[i+1][0] if i+1<len(self.trace) else math.inf
            dt=min(end-self.time,boundary-self.time)
            net=harvest-load_w
            if net<0 and stop_at_empty and self.energy+net*dt <= 0:
                dt=self.energy/(-net)
                brownout=True
            before=self.energy
            self.energy=max(0.0,min(self.capacity,before+net*dt))
            self.harvested+=harvest*dt
            self.consumed+=load_w*dt
            self.spilled+=max(0.0,before+net*dt-self.capacity)
            self.time+=dt
            if brownout:
                break
        return self.time-start,brownout

    def balance_error(self):
        return self.initial+self.harvested-self.consumed-self.spilled-self.energy
