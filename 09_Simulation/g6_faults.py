"""Finite graph crash checks plus 1000 random model-backed large-slot schedules."""
import random
import numpy as np
from g6_storage import Store
from g6_runtime import Runtime
from g5_experiments import dump


class DiagnosticRuntime(Runtime):
    def choose(self,stage,f):
        a=super().choose(stage,f);d=self.model.stages[stage]
        if d['kind']=='fused':a.update(chunk=min(16,d['ci']),z=True,ps=True)
        return a


def campaign(root,models,p,diagnostics,out):
    graph=[]
    for name,model in models.items():
        item=diagnostics[name];s=dict(id='diagnostic_'+name,seed=351000,family='diagnostic',
            capacity_j=100e-6,trace=[[0,.1]],horizon_s=8)
        for action in ('checkpoint_partial','checkpoint_output','layer_log','graph_root'):
            runtime=DiagnosticRuntime(root,model,p,s,fault=dict(action=action,cut=70))
            row=runtime.run([dict(item,arrival_s=0,deadline_s=8)])
            if row['completed']!=1 or not row['fault_executed'] or row['losses']!=1:raise AssertionError('G6 graph recovery')
            graph.append(dict(workload=name,action=action,completed=1,losses=1,output=row['outputs'][0]['output']))
        print('G6 full graph faults PASS:',name,flush=True)
    rng=random.Random(p['fault_seed']);details=[];losses=0;bytes_applied=0
    for trial in range(p['random_fault_schedules']):
        name=p['workloads'][trial%len(p['workloads'])];m=models[name];x=diagnostics[name]['x']
        stage=len(m.stages)-2;d=m.stages[stage];n=min(8,d['pixels']);co=min(64,d['co'])
        # Real model fixture anchor, not an end-to-end execution shortcut.
        ref=m.reference(x);source=ref[d['ops'][0]-1];z=m.dw(stage,source,0,n)
        expected=ref[d['ops'][-1]].reshape(-1,d['co'])[:n,:co]
        bias=m.bias(stage,n,0,co);full=m.pw(stage,z,bias,0,d['ci'],0,co);own=m.finish(stage,full,0,co)
        np.testing.assert_array_equal(own,expected)
        save,keep=bool(rng.getrandbits(1)),bool(rng.getrandbits(1))
        store=Store(m,x,p,invocation=f'large_fault_{trial}')
        ps16=m.pw(stage,z,bias,0,16,0,co)
        ops,_=store.scratch_ops(stage,0,n,co,16 if keep else 0,z.tobytes() if save else None,ps16.astype('<i4').tobytes() if keep else None)
        store.apply(ops);bytes_applied+=len(ops)
        executed=0
        for _ in range(rng.randint(1,4)):
            old=store.scratch(stage,0,n,co)
            if old['output'] is not None:break
            if rng.random()<.35:
                ops,_=store.scratch_ops(stage,0,n,co,d['ci'],out=own.tobytes())
            else:
                prefix=min(d['ci'],old['offset']+16);ps=m.pw(stage,z,bias,0,max(1,prefix),0,co)
                ops,_=store.scratch_ops(stage,0,n,co,prefix if keep else old['offset'],
                    z.tobytes() if save else old['z'],ps.astype('<i4').tobytes() if keep else old['ps'])
            cut=rng.randrange(len(ops)+1);store.apply(ops,cut);bytes_applied+=cut;executed+=1
            recovered=store.scratch(stage,0,n,co)
            if recovered is None:raise AssertionError('lost both valid slots')
            if recovered['output'] is not None:np.testing.assert_array_equal(np.frombuffer(recovered['output'],dtype=np.int8).reshape(n,co),expected)
        recovered=store.scratch(stage,0,n,co)
        if recovered['output'] is None:
            zz=m.dw(stage,source,0,n) if recovered['z'] is None else np.frombuffer(recovered['z'],dtype=np.int8).reshape(n,d['ci'])
            ps=bias.copy() if recovered['ps'] is None else np.frombuffer(recovered['ps'],dtype='<i4').reshape(n,co).copy()
            if recovered['offset']<d['ci']:ps=m.pw(stage,zz,ps,recovered['offset'],d['ci'],0,co)
            final=m.finish(stage,ps,0,co);np.testing.assert_array_equal(final,expected)
            ops,_=store.scratch_ops(stage,0,n,co,d['ci'],out=final.tobytes());store.apply(ops);bytes_applied+=len(ops)
        losses+=executed;details.append(dict(trial=trial,workload=name,save_dw=save,keep_ps=keep,losses=executed,ci=d['ci'],output_elements=n*co))
    result=dict(status='PASS_FINITE_G6_FAULTS',full_network_cases=len(graph),full_network_losses=len(graph),
        random_large_slot_schedules=len(details),random_executed_losses=losses,applied_byte_transactions=bytes_applied,
        random_scope='model-derived large DW/PW tile only; random 1-4 interrupted commit schedules; not 1000 full-network runs',
        mismatches=0,graph_cases=graph,random_details=details)
    dump(out/'faults.json',result);return result
