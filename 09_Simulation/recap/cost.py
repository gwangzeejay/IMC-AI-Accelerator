"""Event ledger. Missing energy is contagious, never silently replaced by zero."""
from dataclasses import dataclass
import math


@dataclass
class CostModel:
    energy_j_per_unit: dict
    seconds_per_unit: dict
    leakage_w: float | None = None
    provenance: str = 'uncalibrated'
    calibrated: bool = False

    def __post_init__(self):
        for mapping in (self.energy_j_per_unit,self.seconds_per_unit):
            if any(v is not None and (not math.isfinite(v) or v < 0) for v in mapping.values()):
                raise ValueError('cost must be finite and nonnegative or null')
        if self.leakage_w is not None and (not math.isfinite(self.leakage_w) or self.leakage_w < 0):
            raise ValueError('invalid leakage')

    def estimate(self, kind, units):
        e,t = self.energy_j_per_unit.get(kind),self.seconds_per_unit.get(kind)
        duration = None if t is None else t*units
        energy = None if e is None or duration is None or self.leakage_w is None else e*units+self.leakage_w*duration
        return energy,duration


class Ledger:
    def __init__(self, identity, cost):
        self.identity,self.cost,self.events=identity,cost,[]

    def record(self, action, phase, kind, units, fraction=1.0, replay=False, start_s=None):
        energy,duration=self.cost.estimate(kind,units)
        event=dict(event_id=len(self.events),**self.identity,action=action,phase=phase,unit_kind=kind,
                   requested_units=units,completed_fraction=fraction,charged_units=units*fraction,
                   energy_j=None if energy is None else energy*fraction,
                   duration_s=None if duration is None else duration*fraction,replay=replay,
                   start_s=start_s,parameter_source=self.cost.provenance)
        self.events.append(event)
        return event

    def summary(self):
        breakdown={}
        for event in self.events:
            row=breakdown.setdefault(event['action'],dict(events=0,units=0,replay_units=0,energy_j=0.0))
            row['events']+=1
            row['units']+=event['charged_units']
            if event['replay']:
                row['replay_units']+=event['charged_units']
            if event['energy_j'] is None:
                row['energy_j']=None
            elif row['energy_j'] is not None:
                row['energy_j']+=event['energy_j']
        total=None if any(e['energy_j'] is None for e in self.events) else sum(e['energy_j'] for e in self.events)
        return dict(total_energy_j=total,calibrated=self.cost.calibrated,provenance=self.cost.provenance,
                    unknown_event_count=sum(e['energy_j'] is None for e in self.events),breakdown=breakdown)
