"""Shape-general INT8 DW/PW workload adapter, with isolated reference CPU head."""
import copy
import hashlib
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','3')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS','0')
import numpy as np
from recap.integer import quantize_multiplier,requantize,pw_accumulate


class Model:
    def __init__(self,root,name,fused=True):
        import tensorflow as tf
        import flatbuffers
        from tensorflow.lite.python import schema_py_generated as s
        self.name=name;self.fused=fused
        path=root/('05_Model_Training/reference_mlperf/kws_ref_model.tflite' if name=='kws' else '05_Model_Training/reference_vww/vww_96_int8.tflite')
        self.blob=path.read_bytes();self.model_hash=hashlib.sha256(self.blob).hexdigest()
        self.golden=tf.lite.Interpreter(model_content=self.blob,experimental_preserve_all_tensors=True,num_threads=1,
            experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)
        self.golden.allocate_tensors();self.ops=self.golden._get_ops_details()
        self.details={int(t['index']):t for t in self.golden.get_tensor_details()}
        self.input_shape=tuple(map(int,self.golden.get_input_details()[0]['shape']))
        self.output_shape=tuple(map(int,self.golden.get_output_details()[0]['shape']))
        self.flat=s.ModelT.InitFromObj(s.Model.GetRootAsModel(self.blob,0));graph=self.flat.subgraphs[0]
        self.constants={int(t):self.golden.get_tensor(int(t)) for op in self.ops for t in op['inputs'][1:] if t>=0}
        self.q={}
        for op in self.ops:
            if op['op_name'] not in ('CONV_2D','DEPTHWISE_CONV_2D'):continue
            i=int(op['index']);xi,wi,bi=map(int,op['inputs']);yi=int(op['outputs'][0]);o=graph.operators[i].builtinOptions
            qi,qw,qo=[self.details[t]['quantization_parameters'] for t in (xi,wi,yi)]
            if np.any(qw['zero_points']) or len(qi['scales'])!=1 or len(qo['scales'])!=1:raise ValueError('quantization')
            count=self.constants[bi].size;scales=list(qw['scales'])
            if len(scales)==1:scales*=count
            pairs=[quantize_multiplier(float(qi['scales'][0])*float(w)/float(qo['scales'][0])) for w in scales]
            if o.fusedActivationFunction not in (s.ActivationFunctionType.NONE,s.ActivationFunctionType.RELU):raise ValueError('activation')
            if o.dilationHFactor!=1 or o.dilationWFactor!=1 or getattr(o,'depthMultiplier',1)!=1:raise ValueError('dilation/multiplier')
            self.q[i]=dict(input_zero_point=int(qi['zero_points'][0]),output_zero_point=int(qo['zero_points'][0]),
                multipliers=[a for a,b in pairs],shifts=[b for a,b in pairs],
                activation_min=int(qo['zero_points'][0]) if o.fusedActivationFunction==s.ActivationFunctionType.RELU else -128,
                activation_max=127,padding='SAME' if o.padding==s.Padding.SAME else 'VALID',stride=[o.strideH,o.strideW])
        self.stages=[];i=0
        while i<len(self.ops):
            op=self.ops[i];kind=op['op_name'];ids=[i]
            if kind=='CONV_2D':k='conv' if i==0 else 'pw'
            elif kind=='DEPTHWISE_CONV_2D':
                k='fused' if fused else 'dw'
                if fused:
                    if self.ops[i+1]['op_name']!='CONV_2D':raise ValueError('DW/PW adjacency')
                    ids.append(i+1)
            elif kind=='AVERAGE_POOL_2D':k='head';ids=list(range(i,len(self.ops)))
            else:raise ValueError('unsupported graph '+kind)
            inp=int(self.ops[ids[0]]['inputs'][0]);out=int(self.ops[ids[-1]]['outputs'][0])
            ins=tuple(map(int,self.details[inp]['shape']));outs=tuple(map(int,self.details[out]['shape']))
            ci=ins[-1] if k in ('fused','pw') else 1
            co=outs[-1];pixels=int(np.prod(outs[:-1]));shape=outs
            self.stages.append(dict(kind=k,ops=ids,input=inp,output=out,inshape=ins,outshape=shape,ci=ci,co=co,pixels=pixels,size=int(np.prod(outs)),input_bytes=int(np.prod(ins))))
            i=ids[-1]+1
        # Isolate the complete CPU head from computed final convolution output.
        head=self.stages[-1];m=copy.deepcopy(self.flat);g=m.subgraphs[0]
        ids=sorted({int(t) for i in head['ops'] for t in list(g.operators[i].inputs)+list(g.operators[i].outputs) if t>=0})
        remap={v:j for j,v in enumerate(ids)};operators=[copy.deepcopy(g.operators[i]) for i in head['ops']]
        for op in operators:
            op.inputs=np.array([remap[int(t)] if t>=0 else -1 for t in op.inputs],dtype=np.int32)
            op.outputs=np.array([remap[int(t)] for t in op.outputs],dtype=np.int32)
        g.tensors=[g.tensors[i] for i in ids];g.operators=operators
        g.inputs=np.array([remap[head['input']]],dtype=np.int32);g.outputs=np.array([remap[head['output']]],dtype=np.int32)
        builder=flatbuffers.Builder(4096);offset=m.Pack(builder);builder.Finish(offset,file_identifier=b'TFL3')
        self.head_blob=bytes(builder.Output())
        self.head=tf.lite.Interpreter(model_content=self.head_blob,num_threads=1,experimental_preserve_all_tensors=True,
            experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)
        self.head.allocate_tensors();self.head_remap=remap;self.cache={};self.conv_cache={};self.finish_cache={}

    def reference(self,x):
        self.golden.set_tensor(int(self.golden.get_input_details()[0]['index']),x);self.golden.invoke()
        return [self.golden.get_tensor(int(op['outputs'][0])) for op in self.ops]

    def weights(self,i):return [self.constants[int(t)] for t in self.ops[i]['inputs'][1:]]

    def _patches(self,i,x,p,n):
        q=self.q[i];op=self.ops[i];w,_=self.weights(i)
        kh,kw=map(int,w.shape[1:3]);sh,sw=q['stride'];outshape=self.details[int(op['outputs'][0])]['shape']
        oh,ow=map(int,outshape[1:3]);h,ww=x.shape[1:3]
        ph=max((oh-1)*sh+kh-h,0) if q['padding']=='SAME' else 0
        pw=max((ow-1)*sw+kw-ww,0) if q['padding']=='SAME' else 0
        pad=np.pad(x,((0,0),(ph//2,ph-ph//2),(pw//2,pw-pw//2),(0,0)),constant_values=q['input_zero_point'])
        return np.stack([pad[0,(v//ow)*sh:(v//ow)*sh+kh,(v%ow)*sw:(v%ow)*sw+kw] for v in range(p,p+n)])

    def conv(self,stage,x,p,n,c,co):
        key=(stage,hashlib.sha256(x.tobytes()).digest(),p,n,c,co)
        if key in self.conv_cache:return self.conv_cache[key].copy()
        i=self.stages[stage]['ops'][0];w,b=self.weights(i);q=self.q[i]
        patches=self._patches(i,x,p,n).astype(np.int64)
        acc=(patches.reshape(n,-1)-q['input_zero_point'])@w[c:c+co].reshape(co,-1).astype(np.int64).T+b[c:c+co]
        result=requantize(acc,dict(q,multipliers=q['multipliers'][c:c+co],shifts=q['shifts'][c:c+co]))
        if len(self.conv_cache)>30000:self.conv_cache.clear()
        self.conv_cache[key]=result.copy();return result

    def dw(self,stage,x,p,n,c=0,co=None):
        i=self.stages[stage]['ops'][0];w,b=self.weights(i);q=self.q[i];co=x.shape[-1] if co is None else co
        key=(i,hashlib.sha256(x.tobytes()).digest(),p,n,c,co)
        if key in self.cache:return self.cache[key].copy()
        patches=self._patches(i,x,p,n)[...,c:c+co].astype(np.int64)
        acc=((patches-q['input_zero_point'])*w[0,:,:,c:c+co].astype(np.int64)).sum(axis=(1,2))+b[c:c+co]
        result=requantize(acc,dict(q,multipliers=q['multipliers'][c:c+co],shifts=q['shifts'][c:c+co]))
        if len(self.cache)>100000:self.cache.clear()
        self.cache[key]=result.copy();return result

    def pw_op(self,stage):return self.stages[stage]['ops'][-1]
    def bias(self,stage,n,c,co):return np.broadcast_to(self.weights(self.pw_op(stage))[1][c:c+co],(n,co)).astype(np.int32).copy()
    def pw(self,stage,z,ps,start,stop,c,co):
        i=self.pw_op(stage);w,_=self.weights(i)
        return pw_accumulate(z,w[c:c+co,0,0,:].T.copy(),ps,start,stop,self.q[i]['input_zero_point'])
    def finish(self,stage,ps,c,co):
        key=(stage,hashlib.sha256(ps.tobytes()).digest(),ps.shape,c,co)
        if key in self.finish_cache:return self.finish_cache[key].copy()
        q=self.q[self.pw_op(stage)]
        result=requantize(ps,dict(q,multipliers=q['multipliers'][c:c+co],shifts=q['shifts'][c:c+co]))
        if len(self.finish_cache)>100000:self.finish_cache.clear()
        self.finish_cache[key]=result.copy();return result
    def cpu(self,x,all_outputs=False):
        self.head.set_tensor(int(self.head.get_input_details()[0]['index']),x);self.head.invoke()
        if all_outputs:return [self.head.get_tensor(self.head_remap[int(self.ops[i]['outputs'][0])]) for i in self.stages[-1]['ops']]
        return self.head.get_tensor(int(self.head.get_output_details()[0]['index']))
    def uninterrupted(self,x):
        outputs=[]
        for stage,d in enumerate(self.stages):
            n=d['pixels'];co=d['co'];kind=d['kind']
            if kind=='head':outputs.extend(self.cpu(x,True));break
            if kind=='conv':y=self.conv(stage,x,0,n,0,co)
            elif kind=='dw':y=self.dw(stage,x,0,n)
            else:
                z=self.dw(stage,x,0,n) if kind=='fused' else x.reshape(n,-1)
                if kind=='fused':outputs.append(z.reshape(1,*self.details[int(self.ops[d['ops'][0]]['outputs'][0])]['shape'][1:]))
                y=self.finish(stage,self.pw(stage,z,self.bias(stage,n,0,co),0,d['ci'],0,co),0,co)
            x=y.reshape(d['outshape']);outputs.append(x)
        return outputs
