"""G3 descriptor-specific admission and durable multi-job workload driver.

G2 is kept unchanged for its existing artifact. Costs remain assumptions.
Each descriptor has dedicated two-slot storage, plus a monotone atomic-byte
completion table. Completed outputs are retained in their actual NVM slots.
"""
import json
from pathlib import Path
import numpy as np
from .simulator import Simulator, Policy, Horizon
from .storage import PAYLOAD_START, META_BYTES, digest
from .power import Reservoir
from .metrics import summarize_inputs


class AdmissionInfeasible(Exception):
    pass


class G3Simulator(Simulator):
    def __init__(self,*args,frontier,job_index,reuse_weights=True,warm=None,spatial_key=None,
                 adaptive=False,**kwargs):
        self.frontier=frontier
        self.job_index=job_index
        self.reuse_weights=reuse_weights
        self.adaptive=adaptive
        self.spatial_key=spatial_key
        self.admitted_units=[]
        self.unit_start_energy=None
        self.current_bound=None
        super().__init__(*args,**kwargs)
        if warm and warm['alive']:
            self.booted=True
            if reuse_weights:
                self.weight_banks=dict(warm['banks'])
            if warm['spatial_key']==spatial_key:
                self.x,self.z=warm['x'],warm['z']

    def _clear(self):
        super()._clear()
        self.descriptor_loaded=False

    def _tag(self,name):
        w,b=('wd','bd') if name=='dw' else ('wp','bp')
        return digest(self.nvm[w].tobytes()+self.nvm[b].tobytes()+self.identity['layout_id'].encode())

    def _load(self,name):
        tag=self._tag(name)
        bank=self.weight_banks.get(name)
        if bank and bank['weight_tile_id']==tag:
            return bank['weights'],bank['bias']
        self.weight_banks.pop(name,None)
        result=super()._load(name)
        self.weight_banks[name]['weight_tile_id']=tag
        return result

    def boot(self):
        self._step('BOOT_RECOVER','startup','boot',1)
        self._read('BOOT_RECOVER','frontier_table',len(self.frontier))
        first=next((i for i,v in enumerate(self.frontier) if not v),len(self.frontier))
        if first not in (self.job_index,self.job_index+1) or any(self.frontier[first:]):
            raise ValueError('non-prefix durable frontier')
        self._read('BOOT_RECOVER','validate_headers',2*PAYLOAD_START)
        # Header/marker bytes have now been read. Integrity reads must include
        # each published payload, not merely trust a cached host-side tag.
        for slot in self.store.slots:
            if slot[0]==0xA5:
                try:
                    n=int.from_bytes(slot[1:5],'little')
                    if not 0<n<=META_BYTES: continue
                    r=json.loads(bytes(slot[37:37+n]))
                    size=r['payload_bytes']
                    if 0<=size<=self.store.slot_bytes-PAYLOAD_START:
                        self._read('BOOT_RECOVER','validate_payload',size)
                except (ValueError,KeyError,TypeError,UnicodeError):
                    continue
        self.slot,self.record=self.store.latest()
        if self.record:
            r=self.record
            if not 0<=r['offset']<=self.ci or (r['offset']>0 and 'ps' not in r['arrays'] and not r['output_committed']):
                raise ValueError('PS offset/payload mismatch')
            for name,ref in r['arrays'].items():
                expected=(*self.expected.shape[:-1],self.ci) if name=='z' else self.expected.shape
                dtype='|i1' if name in ('z','output') else '<i4'
                if name not in ('z','ps','output') or tuple(ref['shape'])!=tuple(expected) or ref['dtype']!=dtype:
                    raise ValueError('invalid recovery tensor')
                if ref['bytes']!=int(np.prod(expected))*np.dtype(dtype).itemsize or ref['offset']<0 or ref['offset']+ref['bytes']>r['payload_bytes']:
                    raise ValueError('invalid recovery range')
            if r['output_committed']!=('output' in r['arrays']):
                raise ValueError('output flag mismatch')
            self.progress_d=r['offset']
        self.booted=True

    def _publish_frontier(self):
        if self.frontier[self.job_index]:
            return
        def publish(fraction):
            if fraction>=1.0-1e-12:
                self.frontier[self.job_index]=1
        self._step('COMMIT_FRONTIER','atomic_publish','write_byte',1,publish,torn_write=True)

    def _restore(self,name):
        result=super()._restore(name)
        if name=='output':
            self._publish_frontier()
        return result

    def _commit(self,final=False):
        super()._commit(final)
        if final:
            self._publish_frontier()
        if self.reservoir and self.unit_start_energy is not None:
            actual=self.reservoir.consumed-self.unit_start_energy
            self.admitted_units[-1]['actual_energy_j']=actual
            if actual>self.current_bound+1e-12:
                raise AssertionError(f'admission underestimate: {actual} > {self.current_bound}')
        if not self.reuse_weights:
            self.weight_banks={}

    def unit_bound(self,cold=None,chunk=None):
        cold=(not self.booted) if cold is None else cold
        chunk=self.policy.chunk_ci if chunk is None else chunk
        nout=self.expected.size
        weights=sum(self.nvm[k].nbytes for k in ('wd','bd','wp','bp'))
        read=0 if self.descriptor_loaded else 128
        dw=pw=bank=write=boot=requant=0
        if cold:
            boot=1
            # Every possible committed payload is bounded by Z+PS or output.
            read+=len(self.frontier)+2*PAYLOAD_START+2*max(self.z_bytes+self.ps_bytes,nout)
            # Conservative cold branch: cover restore and replay alternatives.
            read+=self.nvm['x'].nbytes+weights+2*self.z_bytes+2*self.ps_bytes+nout
            bank=weights
            dw=self.z_bytes*self.nvm['wd'].shape[0]*self.nvm['wd'].shape[1]
            pw=nout*min(chunk,self.ci)
            # Unknown durable prefix may already be the last chunk, so cover
            # final output as well as intermediate checkpoint/reused payloads.
            write=3+META_BYTES+36+max(self.z_bytes+self.ps_bytes,nout)
            requant=nout
        else:
            r=self.record
            if self.z is None:
                if r and 'z' in r['arrays']:
                    read+=self.z_bytes
                else:
                    if self.x is None: read+=self.nvm['x'].nbytes
                    if self.weight_banks.get('dw',{}).get('weight_tile_id')!=self._tag('dw'):
                        n=self.nvm['wd'].nbytes+self.nvm['bd'].nbytes
                        read+=n;bank+=n
                    dw=self.z_bytes*self.nvm['wd'].shape[0]*self.nvm['wd'].shape[1]
            if self.weight_banks.get('pw',{}).get('weight_tile_id')!=self._tag('pw'):
                n=self.nvm['wp'].nbytes+self.nvm['bp'].nbytes
                read+=n;bank+=n
            offset=self.offset if self.ps is not None else self.progress_d
            if self.ps is None and r and 'ps' in r['arrays']: read+=self.ps_bytes
            final=offset+chunk>=self.ci
            pw=nout*min(chunk,self.ci-offset)
            payload=nout if final else ((self.z_bytes if self.policy.save_z or r and 'z' in r['arrays'] else 0)+
                (self.ps_bytes if self.policy.keep_ps or r and 'ps' in r['arrays'] else 0))
            if not final and r:
                if not self.policy.save_z and 'z' in r['arrays']: read+=self.z_bytes
                if not self.policy.keep_ps and 'ps' in r['arrays']: read+=self.ps_bytes
            write=2+int(final)+META_BYTES+36+payload
            requant=nout if final else 0
        units=dict(read_byte=read,write_byte=write,bank_byte=bank,dw_mac=dw,pw_mac=pw,boot=boot,requant=requant)
        estimates=[self.cost.estimate(k,v)[0] for k,v in units.items()]
        if any(e is None for e in estimates): return None
        return sum(estimates)

    def _choose_chunk(self,cold,available):
        if not self.adaptive: return
        fitting=[c for c in (16,32,64) if self.unit_bound(cold,c)<=available]
        chunk=max(fitting) if fitting else 16
        self.policy=Policy(self.policy.save_z,self.policy.keep_ps,chunk)

    def _admit_unit(self):
        if self.reservoir:
            self._choose_chunk(not self.booted,self.reservoir.energy)
            bound=self.unit_bound()
            if bound is None: raise ValueError('unknown G3 energy')
            if not self.reservoir.admit(bound):
                if self.booted:
                    self._loss(False)
                self._choose_chunk(True,self.reservoir.capacity)
                bound=self.unit_bound(True)
                if bound>self.reservoir.capacity+1e-15:
                    raise AdmissionInfeasible('cold progress unit exceeds capacitor capacity')
                while not self.reservoir.admit(bound):
                    remaining=self.reservoir.horizon-self.reservoir.time
                    if remaining<=1e-12: raise Horizon()
                    dt,_=self.reservoir.advance(min(.002,remaining),0,stop_at_empty=False)
                    self.ledger.record('WAIT_CHARGE','powered_off','wait_s',dt,start_s=self.reservoir.time-dt)
            self.current_bound=bound
            self.unit_start_energy=self.reservoir.consumed
            self.admitted_units.append(dict(bound_j=bound,cold=not self.booted,ci=self.policy.chunk_ci))
        if not self.descriptor_loaded:
            self._read('SELECT_DESCRIPTOR','descriptor',128)
            self.descriptor_loaded=True


def run_workload(descriptor_dir,catalog,mapping,cost,scenario,protocol,adaptive=False,reuse_weights=True,keep_events=False):
    plan=catalog['catalog'][f'h{mapping.h}w{mapping.w}_co{mapping.co}']
    reservoir=Reservoir(scenario['capacity_j']/3.445,3.3,2.0,scenario['trace'],0,scenario['horizon_s'])
    frontier=bytearray(len(plan['jobs']))
    actual=np.full(tuple(np.load(Path(descriptor_dir)/'expected_output.npy',allow_pickle=False).shape),-128,dtype=np.int8)
    stores=[];ledgers=[];jobs=[];warm=None;losses=unexpected=0;failure=None;max_sram=0;admissions=[]
    nvm_valid=plan['nvm_reserved_bytes']<=protocol['nvm_bytes']
    if nvm_valid:
        for index,job in enumerate(plan['jobs']):
            sim=G3Simulator(Path(descriptor_dir)/job['path'],mapping.policy,cost,reservoir,
                slot_bytes=job['slot_bytes'],nvm_bytes=protocol['nvm_bytes'],bank_bytes=protocol['bank_bytes'],
                sram_bytes=protocol['sram_bytes'],frontier=frontier,job_index=index,warm=warm,
                spatial_key=job['spatial_key'],adaptive=adaptive,reuse_weights=reuse_weights)
            try:
                result=sim.run()
            except AdmissionInfeasible:
                result=dict(completed=False,mismatches=None)
                failure='admission_capacity'
            stores.append(sim.store)
            ledgers.append(sim.ledger)
            losses+=sim.losses;unexpected+=sim.unexpected_losses
            admissions+=sim.admitted_units
            max_sram=max(max_sram,sim.sram_reserved_bytes)
            jobs.append(dict(index=index,completed=result['completed'],mismatches=result['mismatches']))
            if not result['completed']:
                failure=failure or sim.failure_reason
                break
            slot,record=sim.store.latest()
            if not record or not record['output_committed'] or not frontier[index]:
                raise AssertionError('job completed without durable output/frontier')
            output=sim.store.payload(slot,record,'output')
            d=job['descriptor'];w=protocol['workload']
            yy,xx,cc=d['y']-w['y'][0],d['x']-w['x'][0],d['co_start']-w['co'][0]
            actual[:,yy:yy+d['h'],xx:xx+d['w'],cc:cc+d['co_count']]=output
            warm=dict(alive=sim.booted,banks=sim.weight_banks,x=sim.x,z=sim.z,spatial_key=job['spatial_key'])
    else:
        failure='nvm_capacity'
    completed=bool(all(frontier)) and nvm_valid
    completion=reservoir.time if completed else None
    expected=np.load(Path(descriptor_dir)/'expected_output.npy',allow_pickle=False)
    mismatch=None if not completed else int(np.count_nonzero(actual!=expected))
    if mismatch: raise AssertionError('assembled workload mismatch')
    # Entire fixed horizon is observed, including structurally infeasible and
    # completed workloads, with the explicitly assumed zero powered-off load.
    reservoir.advance(reservoir.horizon-reservoir.time,0,stop_at_empty=False)
    energy=sum(l.summary()['total_energy_j'] for l in ledgers)
    if abs(energy-reservoir.consumed)>1e-12 or abs(reservoir.balance_error())>1e-12:
        raise AssertionError('workload source/ledger imbalance')
    if unexpected: raise AssertionError('depletion inside conservatively admitted unit')
    breakdown={}
    for ledger in ledgers:
        for action,row in ledger.summary()['breakdown'].items():
            a=breakdown.setdefault(action,dict(events=0,units=0,replay_units=0,energy_j=0))
            for k in a: a[k]+=row[k]
    result=dict(mapping=mapping.name,scenario_id=scenario['id'],family=scenario['family'],seed=scenario['seed'],
        completed=int(completed),total_inputs=1,on_time=int(completed),weight=1,energy_j=energy,
        completion_s=completion,mismatches=mismatch,output_hash=digest(actual.tobytes()) if completed else None,
        power_losses=losses,unexpected_losses=unexpected,failure_reason=failure,jobs_completed=sum(frontier),
        job_count=len(frontier),nvm_reserved_bytes=plan['nvm_reserved_bytes'],sram_reserved_bytes=max_sram,
        metrics=summarize_inputs([dict(arrival_s=0,deadline_s=reservoir.horizon,committed_s=completion)],reservoir.horizon,energy),
        breakdown=breakdown,source_balance_error_j=reservoir.balance_error(),source_ledger_error_j=energy-reservoir.consumed,
        admission_unit_count=len(admissions),max_admission_excess_j=max([a.get('actual_energy_j',0)-a['bound_j'] for a in admissions]+[0]))
    if keep_events:
        result['events']=[dict(job_index=i,**e) for i,l in enumerate(ledgers) for e in l.events]
    return result
