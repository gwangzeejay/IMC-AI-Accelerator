"""Check RTL bus/restore bytes against independent Python binary-wire simulator."""
from collections import deque
import gzip
from g4_reference import latest,commit_transactions,oracle_arrays


def verify(root,trace,config,cases,initial=None):
    arrays=oracle_arrays(root,config)
    memory=None;queue=deque();restore=deque();stats=[];current=None;committing=None
    cycle_checks=0;transactions=0;restore_bytes=0;measurements=[]
    def boot_queue():
        return deque(('R',addr,None,0) for addr in range(2*config['slot_bytes']+1))
    def record(): return latest(memory,config)
    opener=gzip.open(trace,'rt',encoding='utf-8') if trace.suffix=='.gz' else trace.open(encoding='utf-8')
    with opener as f:
        for line_number,line in enumerate(f,1):
            fields=line.split();kind=fields[0];nums=[int(x) for x in fields[1:]]
            def require(condition,message):
                if not condition:raise AssertionError(f'{trace.name}:{line_number}: {message}; {line.strip()}')
            if kind=='S':
                cid=nums[0];memory=bytearray(initial) if initial is not None else bytearray(2*config['slot_bytes']+1)
                queue=boot_queue();restore=deque();committing=None
                current=dict(case_id=cid,reads=0,writes=0,restores=0,losses=0,cycles=0,passed=False)
                continue
            require(current is not None and nums[0]==current['case_id'],'case ID mismatch')
            if kind=='T':
                _,cycle,write,addr,value,phase,blocked=nums
                require(bool(queue),'unexpected memory transaction')
                op,expected_addr,expected_value,expected_phase=queue.popleft()
                require(op==('W' if write else 'R') and addr==expected_addr and phase==expected_phase,'memory order/address/phase mismatch')
                require(value==(expected_value if write else memory[addr]),'memory data differs from reference')
                if write:
                    memory[addr]=value;current['writes']+=1
                    if committing: committing['stalls']+=blocked
                else:
                    current['reads']+=1
                transactions+=1
                if not queue and not write:
                    r=record()
                    if r:
                        restore=deque(enumerate(r['payload']))
                        if r['flags']&4 and memory[-1]==0:queue.append(('W',2*config['slot_bytes'],1,13))
            elif kind=='R':
                _,cycle,addr,value=nums
                require(bool(restore),'unexpected SRAM restore')
                expected=restore.popleft();require((addr,value)==expected,'restored tensor/PS byte mismatch')
                current['restores']+=1;restore_bytes+=1
            elif kind=='B':
                _,cycle,prefix,flags,generation=nums;r=record()
                require(not restore,'boot completed before restore')
                expected=(r['offset'],r['flags'],r['generation']) if r else (0,0,0)
                require((prefix,flags,generation)==expected,'boot record metadata mismatch')
            elif kind=='C':
                _,cycle,save,keep,final,prefix=nums
                require(not queue and not restore,'new commit before transaction/restore complete')
                old=record()
                invalid=prefix>64 or final and prefix!=64 or old and (old['generation']==0xffffffff or keep and prefix<old['offset'])
                if invalid:
                    committing=None;continue
                ops,length=commit_transactions(memory,config,save,keep,final,prefix,arrays)
                for i,(op,addr,value) in enumerate(ops):
                    if i==0:phase=9
                    elif i<=length:phase=10
                    elif i<=length+123:phase=11
                    elif i==length+124:phase=12
                    else:phase=13
                    queue.append((op,addr,value,phase))
                committing=dict(start=cycle,length=length,final=final,stalls=0)
            elif kind=='D':
                _,cycle,prefix,flags,generation=nums;r=record()
                require(r is not None and (prefix,flags,generation)==(r['offset'],r['flags'],r['generation']),'publication metadata differs')
                require(not queue,'commit done before persistence ACK')
                if committing:
                    expected=2*committing['length']+246+committing['final']+committing['stalls']
                    require(cycle-committing['start']==expected,f'cycle latency mismatch: expected {expected}, got {cycle-committing["start"]}')
                    measurements.append(dict(case_id=current['case_id'],payload_bytes=committing['length'],
                        final=committing['final'],stall_cycles=committing['stalls'],rtl_cycles=cycle-committing['start'],reference_cycles=expected))
                    cycle_checks+=1;committing=None
            elif kind=='U':
                _,cycle,addr,value=nums
                require(bool(queue) and queue[0][0]=='W' and (addr,value)==queue[0][1:3],'unacknowledged persistence not matching pending write')
                memory[addr]=value
            elif kind=='X':
                current['losses']+=1;queue=boot_queue();restore=deque();committing=None
            elif kind=='P':
                _,cycle,losses,acks=nums;r=record()
                require(r is not None and r['flags']==4 and r['output']==arrays['output'] and memory[-1]==1,'published output differs from golden')
                require(current['losses']==losses and current['reads']+current['writes']==acks,'event counts mismatch')
                require(not queue and not restore,'completed with pending work')
                current.update(cycles=cycle,passed=True);stats.append(current)
            elif kind=='E':
                require(cases[current['case_id']][-1]!=0,'unexpected fail-closed error')
                current.update(cycles=nums[1],passed=True,expected_error=True);stats.append(current)
            else:require(False,'unknown trace event')
    if len(stats)!=len(cases):raise AssertionError('missing case results')
    return dict(cases=len(stats),transactions=transactions,restored_bytes=restore_bytes,
                cycle_checks=cycle_checks,mismatches=0,results=stats,cycle_measurements=measurements)
