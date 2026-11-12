"""Actual RTL campaigns and independent transaction/cycle cross-checks."""
import gzip
import json
from pathlib import Path
import random
import shutil
from g4_reference import encode,HEADER,oracle_arrays
from g4_trace_check import verify
from g4_tools import compile_controller,execute


def write_cases(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(' '.join(map(str,row))+'\n' for row in rows.values()))


def run_suite(root,toolchain,config,rows,label,initial=None,compress=False):
    base=root/'10_Experiments/g4';name=config['name'];suite=f'{name}_{label}'
    path=base/'cases'/(suite+'.txt');write_cases(path,rows)
    trace=base/'raw'/(suite+'.trace');trace.parent.mkdir(exist_ok=True)
    args=[toolchain['vvp'],'-M',toolchain['ivl'],f'10_Experiments/g4/build/{name}.vvp',
          '+CASES='+path.relative_to(root).as_posix(),'+TRACE='+trace.relative_to(root).as_posix()]
    if initial is not None:
        initpath=base/'cases'/(suite+'_initial.hex')
        initpath.write_text(''.join(f'{b:02x}\n' for b in initial));args.append('+INIT='+initpath.relative_to(root).as_posix())
    execute(root,toolchain,args,base/'logs'/(suite+'.log'),timeout=300)
    checked=verify(root,trace,config,rows,initial)
    if compress:
        with trace.open('rb') as source,gzip.open(str(trace)+'.gz','wb') as dest:shutil.copyfileobj(source,dest)
        # Only this generated trace is removed, after it has been cross-checked
        # and losslessly compressed; never remove a user-provided path.
        if not trace.resolve().is_relative_to((base/'raw').resolve()):raise ValueError('unexpected generated path')
        trace.unlink()
    (base/(suite+'_report.json')).write_text(json.dumps(checked,indent=2)+'\n')
    return checked


def campaign(root,toolchain,configs):
    summaries={};rng=random.Random(82500)
    for name,config in configs.items():
        compile_controller(root,toolchain,name)
        rows={}
        for z in (0,1):
            for ps in (0,1):
                for stalls in (0,1):
                    cid=len(rows);rows[cid]=[cid,z,ps,-1,-1,0,0,100+cid,stalls,0,0]
        rows[8]=[8,1,1,-1,-1,0,0,108,1,1,0]
        rows[9]=[9,1,1,-1,-1,0,0,109,1,0,2]
        discovery=run_suite(root,toolchain,config,rows,'baseline')
        events={cid:[] for cid in rows}
        trace=root/f'10_Experiments/g4/raw/{name}_baseline.trace'
        for line in trace.read_text().splitlines():
            parts=line.split()
            if parts[0]=='T':
                cid,cycle,wr,addr,data,phase,blocked=map(int,parts[1:]);events[cid].append((wr,addr,data,phase))
        faults={};kinds={}
        def add(z,ps,c1,c2=-1,mode=0,persist=0,switch=0,kind='phase'):
            cid=len(faults);faults[cid]=[cid,z,ps,c1,c2,mode,persist,2000+cid,1,switch,0];kinds[cid]=kind
        for cid in (0,2,4,6):
            z,ps=rows[cid][1:3];groups=[];group=[]
            for index,event in enumerate(events[cid]):
                if event[0]:
                    if group and event[3]!=group[-1][1][3]:groups.append(group);group=[]
                    group.append((index,event))
            if group:groups.append(group)
            boundaries=sorted({group[i][0] for group in groups for i in (0,len(group)//2,len(group)-1)})
            for point in boundaries:
                add(z,ps,point,kind='write_boundary_after_ack')
                add(z,ps,point,mode=1,kind='pending_write_old')
                add(z,ps,point,mode=1,persist=1,kind='pending_write_new')
            publish=next(i for i,e in enumerate(events[cid]) if e[3]==12)
            for phase,cursor in ((2,60),(3,1),(5,0)):
                add(z,ps,publish,phase*100000+cursor,kind='boot_or_restore_reinterruption')
            for phase,cursor in ((7,0),(8,30),(9,0),(10,1),(11,30),(12,0),(13,0)):
                add(z,ps,phase*100000+cursor,kind='internal_state_cut')
        switch_publish=[i for i,e in enumerate(events[8]) if e[3]==12][1]
        add(1,1,switch_publish,switch=1,kind='preserve_previous_nonzero_ps_prefix')
        for _ in range(500):
            z=rng.randrange(2);ps=rng.randrange(2);cid=z*4+ps*2
            first=rng.randrange(len(events[cid]));second=first+rng.randrange(1,1500)
            add(z,ps,first,second,rng.randrange(2),rng.randrange(2),kind='seeded_multi_loss')
        result=run_suite(root,toolchain,config,faults,'faults',compress=True)
        if any(r['losses']<1 for r in result['results']):raise AssertionError('scheduled first fault not exercised')
        # Persistence/identity and old-prefix cases are generated independently
        # of RTL bytes by Python zlib/struct, not by replaying RTL output files.
        arrays=oracle_arrays(root,config);identity=tuple(bytes.fromhex(x) for x in config['identity'])
        h0,p0=encode(identity,1,16,None,arrays['ps'][16])
        h1,p1=encode(identity,2,32,arrays['z'],arrays['ps'][32])
        initial=bytearray(2*config['slot_bytes']+1)
        for slot,h,p in [(0,h0,p0),(1,h1,p1)]:
            b=slot*config['slot_bytes'];initial[b:b+HEADER]=h;initial[b+HEADER:b+HEADER+len(p)]=p
        directed=[]
        for label in ('payload_crc','metadata_crc','wrong_identity','missing_marker','old_prefix_keep_false','generation_wrap','output_before_frontier','orphan_frontier'):
            mem=bytearray(initial);error=0;keep=1
            base=config['slot_bytes']
            if label=='payload_crc':mem[base+HEADER]^=1
            elif label=='metadata_crc':mem[base+104]^=1
            elif label=='wrong_identity':
                wrong=(b'\xff'*32,identity[1],identity[2]);h,p=encode(wrong,2,32,arrays['z'],arrays['ps'][32]);mem[base:base+HEADER]=h
            elif label=='missing_marker':mem[base]=0
            elif label=='old_prefix_keep_false':mem[base]=0;keep=0
            elif label=='generation_wrap':
                h,p=encode(identity,0xffffffff,16,None,arrays['ps'][16]);mem[:HEADER]=h;mem[base]=0;error=1
            elif label=='output_before_frontier':
                h,p=encode(identity,2,64,output=arrays['output']);mem[base:base+HEADER]=h;mem[base+HEADER:base+HEADER+len(p)]=p
            else:mem[base+HEADER]^=1;mem[-1]=1;error=1
            row={0:[0,0,keep,-1,-1,0,0,3000,1,0,error]}
            directed.append(run_suite(root,toolchain,config,row,'directed_'+label,mem))
        summaries[name]=dict(baseline_cases=discovery['cases'],fault_cases=result['cases'],
            directed_cases=sum(r['cases'] for r in directed),executed_losses=sum(r['losses'] for r in result['results']),
            transactions=sum(r['transactions'] for r in [discovery,result,*directed]),
            cycle_checks=sum(r['cycle_checks'] for r in [discovery,result,*directed]),
            restored_bytes=sum(r['restored_bytes'] for r in [discovery,result,*directed]),
            fault_categories={k:sum(v==k for v in kinds.values()) for k in sorted(set(kinds.values()))},mismatches=0)
        print(name,json.dumps(summaries[name]),flush=True)
    report=dict(status='PASS_RTL_TRANSACTION_REFINEMENT',scope='two model-backed microtiles; finite faults and simulation assertions; binary-v1 metadata',
                configs=summaries,total_cases=sum(r['baseline_cases']+r['fault_cases']+r['directed_cases'] for r in summaries.values()),
                fault_cases=sum(r['fault_cases'] for r in summaries.values()),executed_losses=sum(r['executed_losses'] for r in summaries.values()),
                checked_transactions=sum(r['transactions'] for r in summaries.values()),cycle_checks=sum(r['cycle_checks'] for r in summaries.values()),
                mismatches=0,seed=82500,formal_proof_performed=False)
    (root/'10_Experiments/g4/rtl_summary.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
