"""Executable one DW-PW microtile with byte-level persistent payloads.

Functional crash tests work with unknown energy. Coupled-source execution
requires explicit, complete costs. This is not a physical CIM macro model.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import numpy as np
from .integer import depthwise, pw_accumulate, requantize
from .cost import CostModel, Ledger
from .storage import TwoSlotStore, PAYLOAD_START, META_BYTES, MARKER, digest


class PowerLoss(Exception):
    pass


class Horizon(Exception):
    pass


@dataclass(frozen=True)
class Policy:
    save_z: bool
    keep_ps: bool
    chunk_ci: int = 16

    @property
    def name(self):
        return f'z{int(self.save_z)}_ps{int(self.keep_ps)}_ci{self.chunk_ci}'


class Simulator:
    def __init__(self, fixture, policy, cost=None, reservoir=None, faults=None,
                 slot_bytes=4096, nvm_bytes=262144, bank_bytes=1024, sram_bytes=8192):
        fixture=Path(fixture)
        self.spec=json.loads(fixture.with_suffix('.json').read_text())
        with np.load(fixture,allow_pickle=False) as values:
            # Immutable NVM owns these arrays, never mutated by runtime.
            self.nvm={k:values[k].copy() for k in ['x','wd','bd','wp','bp']}
            self.expected=values['y'].copy()
        self.identity=self.spec['identity']
        if digest(self.nvm['x'].tobytes())!=self.identity['input_id']:
            raise ValueError('anchor identity mismatch')
        for a in self.nvm.values():
            a.flags.writeable=False
        self.ci=self.nvm['x'].shape[-1]
        self.co=self.nvm['wp'].shape[-1]
        if policy.chunk_ci<=0:
            raise ValueError('positive chunk size required')
        self.policy=policy
        self.bank_bytes=bank_bytes
        weight_sizes=[self.nvm[w].nbytes+self.nvm[b].nbytes for w,b in [('wd','bd'),('wp','bp')]]
        if max(weight_sizes)>bank_bytes:
            raise ValueError('weight packet exceeds bank capacity')
        # Conservative logical layout, including two bank reservations and scratch.
        shape=self.expected.shape
        self.z_bytes=int(np.prod(shape[:-1]))*self.ci
        self.ps_bytes=int(np.prod(shape))*4
        self.sram_reserved_bytes=(2*bank_bytes+self.nvm['x'].nbytes+self.z_bytes+self.ps_bytes+
            self.expected.nbytes+max(4*self.z_bytes,self.ps_bytes)+2048+32)
        if self.sram_reserved_bytes>sram_bytes:
            raise ValueError('logical SRAM capacity exceeded')
        self.store=TwoSlotStore(self.identity,slot_bytes,nvm_bytes,sum(a.nbytes for a in self.nvm.values()))
        self.cost=cost or CostModel({}, {}, None)
        self.ledger=Ledger(self.identity,self.cost)
        self.reservoir=reservoir
        if reservoir and self.cost.leakage_w is None:
            raise ValueError('source simulation requires complete costs')
        self.faults=faults or {}
        self.attempted=set()
        self.losses=0
        self.unexpected_losses=0
        self.event_counter=0
        self.executed_faults=[]
        self._clear()
        self.failure_reason=None

    def _clear(self):
        self.booted=False
        self.x=self.z=self.ps=self.output=None
        self.weight_banks={}
        self.offset=0
        self.progress_d=0
        self.record=None
        self.slot=None
        self.pending_txn=None

    def _loss(self, unexpected=True):
        self.losses+=1
        self.unexpected_losses+=int(unexpected)
        self.ledger.record('POWER_LOSS','unexpected' if unexpected else 'scheduled_off','control',0)
        self._clear()

    def _step(self, action, phase, kind, units, mutation=None, replay=False, torn_write=False):
        index=self.event_counter
        self.event_counter+=1
        fault_fraction=self.faults.get(index)
        fraction=1.0 if fault_fraction is None else float(fault_fraction)
        if not 0<=fraction<=1:
            raise ValueError('fault fraction outside [0,1]')
        energy,duration=self.cost.estimate(kind,units)
        start=None if self.reservoir is None else self.reservoir.time
        brownout=False
        ended=False
        if self.reservoir:
            if energy is None or duration is None or duration<=0 and energy>0:
                raise ValueError('complete positive-time costs required for source simulation')
            planned=duration*fraction
            elapsed,brownout=self.reservoir.advance(planned,energy/duration if duration else 0)
            # Time integration roundoff must never turn a completed transfer into
            # a torn byte write (especially a one-byte atomic marker).
            if abs(elapsed-planned)>1e-12 or brownout:
                fraction=min(fraction,max(0.0,elapsed/duration)) if duration else fraction
            ended=self.reservoir.time>=self.reservoir.horizon-1e-12 and elapsed+1e-12<planned
        self.ledger.record(action,phase,kind,units,fraction,replay,start)
        if mutation and (fraction>=1.0-1e-12 or torn_write):
            mutation(fraction)
        if brownout or fault_fraction is not None:
            self.executed_faults.append(dict(primitive_index=index,action=action,phase=phase,
                                            fraction=fraction,source='brownout' if brownout else 'injected'))
            raise PowerLoss()
        if ended:
            raise Horizon()

    def _read(self, action, phase, n):
        # SRAM validity is promoted only after the complete sequence returns.
        for pos in range(0,n,32):
            self._step(action,phase,'read_byte',min(32,n-pos))

    def _write(self, slot, offset, raw, action, phase, atomic=False):
        width=1 if atomic else 32
        for pos in range(0,len(raw),width):
            packet=raw[pos:pos+width]
            def mutate(fraction, pos=pos, packet=packet):
                n=len(packet) if fraction>=1.0-1e-12 else (0 if atomic else int(len(packet)*fraction))
                self.store.slots[slot][offset+pos:offset+pos+n]=packet[:n]
            self._step(action,phase,'write_byte',len(packet),mutate,torn_write=True)

    def boot(self):
        self._step('BOOT_RECOVER','startup','boot',1)
        # Full-slot read includes integrity scanning; restore reads are additional.
        self._read('BOOT_RECOVER','validate_slots',2*self.store.slot_bytes)
        self.slot,self.record=self.store.latest()
        if self.record:
            r=self.record
            expected_shapes={'z':(*self.expected.shape[:-1],self.ci),'ps':self.expected.shape,'output':self.expected.shape}
            if not 0<=r['offset']<=self.ci or (r['offset']>0 and 'ps' not in r['arrays'] and not r['output_committed']):
                raise ValueError('PS offset/payload invariant violated')
            for name,ref in r['arrays'].items():
                if name not in expected_shapes or tuple(ref['shape'])!=tuple(expected_shapes[name]):
                    raise ValueError('incompatible tensor descriptor')
                dtype='|i1' if name in ('z','output') else '<i4'
                if ref['dtype']!=dtype or ref['bytes']!=int(np.prod(ref['shape']))*np.dtype(dtype).itemsize:
                    raise ValueError('invalid tensor encoding')
                if ref['offset']<0 or ref['offset']+ref['bytes']>r['payload_bytes']:
                    raise ValueError('invalid payload reference')
            if r['output_committed'] != ('output' in r['arrays']):
                raise ValueError('output marker/payload mismatch')
            self.progress_d=r['offset']
        self.booted=True

    def _restore(self, name):
        self._read('RESTORE_PAYLOAD',name,self.record['arrays'][name]['bytes'])
        return self.store.payload(self.slot,self.record,name)

    def _load(self, name):
        tile_id=f'{name}_ci0:{self.ci}_co0:{self.co}'
        if name in self.weight_banks:
            bank=self.weight_banks[name]
            if bank['weight_tile_id']!=tile_id:
                raise ValueError('stale weight tag')
            return bank['weights'],bank['bias']
        w,b=('wd','bd') if name=='dw' else ('wp','bp')
        n=self.nvm[w].nbytes+self.nvm[b].nbytes
        self._read('LOAD_WEIGHT',name,n)
        self._step('LOAD_WEIGHT',name+'_bank_program','bank_byte',n)
        weights,bias=self.nvm[w].copy(),self.nvm[b].copy()
        self.weight_banks[name]=dict(weight_tile_id=tile_id,layout_id=self.identity['layout_id'],
             valid_region=list(weights.shape),capacity_bytes=self.bank_bytes,weights=weights,bias=bias)
        return weights,bias

    def _compute(self, action, key, kind, units, mutation):
        replay=key in self.attempted
        self.attempted.add(key)
        self._step(action,key,kind,units,mutation,replay=replay)

    def _commit(self, final=False):
        generation=1 if self.record is None else self.record['generation']+1
        target=0 if self.slot is None else 1-self.slot
        if final:
            z=ps=None
            offset=self.ci
            output=self.output
        else:
            z=self.z if self.policy.save_z else None
            ps=self.ps if self.policy.keep_ps else None
            offset=self.offset if self.policy.keep_ps else self.progress_d
            output=None
            # Preserve a previous durable prefix, even if policy no longer saves PS.
            if not self.policy.keep_ps and self.record and 'ps' in self.record['arrays']:
                ps=self._restore('ps')
            if not self.policy.save_z and self.record and 'z' in self.record['arrays']:
                z=self._restore('z')
        record,payload,header=self.store.encode(generation,offset,z,ps,output)
        self.pending_txn=dict(generation=generation,target_slot=target,phase='invalidate')
        action='COMMIT_OUTPUT' if final else 'COMMIT_CHECKPOINT'
        self._write(target,0,b'\x00',action,'invalidate',atomic=True)
        for name,ref in record['arrays'].items():
            start=ref['offset']
            save_action={'z':'SAVE_DW','ps':'SAVE_PW_PS','output':'COMMIT_OUTPUT'}[name]
            self.pending_txn['phase']='payload_'+name
            self._write(target,PAYLOAD_START+start,payload[start:start+ref['bytes']],save_action,'payload_'+name)
        self.pending_txn['phase']='metadata'
        self._write(target,1,header,action,'metadata')
        self.pending_txn['phase']='publish'
        self._write(target,0,bytes([MARKER]),action,'publish',atomic=True)
        self.slot,self.record=target,record
        self.progress_d=offset
        self.pending_txn=None

    def unit_bound(self):
        # Upper bound includes boot+full integrity scan, all possible restores,
        # anchor/weight reload, full DW/PW, COW payload and maximum metadata.
        read=2*self.store.slot_bytes+sum(a.nbytes for a in self.nvm.values())+2*self.z_bytes+2*self.ps_bytes+self.expected.nbytes
        write=2+self.z_bytes+self.ps_bytes+self.expected.nbytes+META_BYTES+36
        bank=sum(self.nvm[k].nbytes for k in ('wd','bd','wp','bp'))
        units={'read_byte':read,'write_byte':write,'bank_byte':bank,'boot':1,
               'dw_mac':self.z_bytes*self.nvm['wd'].shape[0]*self.nvm['wd'].shape[1],
               'pw_mac':int(np.prod(self.expected.shape))*self.ci,'requant':self.expected.size}
        estimates=[self.cost.estimate(k,v)[0] for k,v in units.items()]
        return None if any(v is None for v in estimates) else sum(estimates)

    def _admit_unit(self):
        if not self.reservoir:
            return
        bound=self.unit_bound()
        if bound is None:
            raise ValueError('unknown conservative admission bound')
        if bound>self.reservoir.capacity:
            raise ValueError('capacitor cannot reserve one progress unit')
        if self.reservoir.admit(bound):
            return
        if self.booted or self.pending_txn is not None:
            self._loss(unexpected=False)
        while not self.reservoir.admit(bound):
            remaining=self.reservoir.horizon-self.reservoir.time
            if remaining<=1e-12:
                raise Horizon()
            elapsed,_=self.reservoir.advance(min(0.001,remaining),0,stop_at_empty=False)
            self.ledger.record('WAIT_CHARGE','powered_off','wait_s',elapsed,start_s=self.reservoir.time-elapsed)

    def run(self, max_events=100000):
        try:
            while self.output is None or not self.record or not self.record['output_committed']:
                if self.event_counter>=max_events:
                    self.failure_reason='event_limit'
                    break
                try:
                    self._admit_unit()
                    if not self.booted:
                        self.boot()
                    if self.record and self.record['output_committed']:
                        self.output=self._restore('output')
                        break
                    if self.z is None:
                        if self.record and 'z' in self.record['arrays']:
                            self.z=self._restore('z')
                        else:
                            if self.x is None:
                                self._read('READ_INPUT','immutable_anchor',self.nvm['x'].nbytes)
                                self.x=self.nvm['x'].copy()
                            weights,bias=self._load('dw')
                            def compute_dw(_):
                                self.z=depthwise(self.x,weights,bias,self.spec['dw'])
                            self._compute('COMPUTE_DW','full_dw','dw_mac',self.z_bytes*weights.shape[0]*weights.shape[1],compute_dw)
                    weights,bias=self._load('pw')
                    if self.ps is None:
                        if self.record and 'ps' in self.record['arrays']:
                            restored=self._restore('ps')
                            self.ps=restored
                            self.offset=self.progress_d
                        else:
                            self.ps=np.broadcast_to(bias,self.expected.shape).copy().astype(np.int32)
                            self.offset=0
                    start=self.offset
                    stop=min(start+self.policy.chunk_ci,self.ci)
                    def compute_pw(_):
                        self.ps=pw_accumulate(self.z,weights,self.ps,start,stop,self.spec['pw']['input_zero_point'])
                        self.offset=stop
                    self._compute('COMPUTE_PW',f'ci{start}:{stop}','pw_mac',int(np.prod(self.expected.shape))*(stop-start),compute_pw)
                    if stop==self.ci:
                        self._step('REQUANTIZE','pw_output','requant',self.expected.size,
                                   lambda _:setattr(self,'output',requantize(self.ps,self.spec['pw'])))
                        self._commit(final=True)
                    else:
                        self._commit()
                except PowerLoss:
                    self._loss()
        except Horizon:
            self.failure_reason='horizon'
        completed=self.output is not None and self.record is not None and self.record['output_committed']
        mismatches=None if not completed else int(np.count_nonzero(self.output!=self.expected))
        if mismatches:
            raise AssertionError('recovered output differs from golden')
        return dict(policy=self.policy.name,completed=completed,mismatches=mismatches,
                    power_losses=self.losses,unexpected_losses=self.unexpected_losses,
                    progress_v=self.offset,progress_d=self.progress_d,failure_reason=self.failure_reason,
                    nvm_reserved_bytes=2*self.store.slot_bytes+self.store.immutable_bytes,
                    sram_reserved_bytes=self.sram_reserved_bytes,
                    ledger=self.ledger.summary(),source_time_s=None if not self.reservoir else self.reservoir.time,
                    source_balance_error_j=None if not self.reservoir else self.reservoir.balance_error(),
                    events=self.event_counter)
