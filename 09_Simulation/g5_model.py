"""Full pinned KWS arithmetic with an explicitly hybrid CPU classification head.

No golden intermediate tensor enters execution. Golden interpreter is separate.
Host NumPy scratch is not an embedded allocation or measured timing claim.
"""
import copy
import hashlib
import os
from pathlib import Path
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')
import numpy as np
from recap.integer import quantize_multiplier, requantize, depthwise, pw_accumulate


def sha(data):
    return hashlib.sha256(data).hexdigest()


class KWS:
    def __init__(self, root):
        import tensorflow as tf
        import flatbuffers
        from tensorflow.lite.python import schema_py_generated as s
        self.blob = (root/'05_Model_Training/reference_mlperf/kws_ref_model.tflite').read_bytes()
        self.model_hash = sha(self.blob)
        if self.model_hash != 'aeea436800704fce17b17292e4412630ad856e9d777c044c64ef748a880bd0ae':
            raise ValueError('unpinned model')
        self.tf_version = tf.__version__
        self.golden = tf.lite.Interpreter(model_content=self.blob,
            experimental_preserve_all_tensors=True, num_threads=1,
            experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)
        self.golden.allocate_tensors()
        self.details = {d['index']:d for d in self.golden.get_tensor_details()}
        self.ops = self.golden._get_ops_details()
        self.flat = s.ModelT.InitFromObj(s.Model.GetRootAsModel(self.blob,0))
        self.graph = self.flat.subgraphs[0]
        self.constants = {int(t):self.golden.get_tensor(int(t)) for op in self.ops
            for t in op['inputs'][1:] if t >= 0}
        self.specs = {}
        for i in [0,1,2,3,4,5,6,7,8,11]:
            op=self.ops[i]; inp,w,b=map(int,op['inputs']); out=int(op['outputs'][0])
            qi,qw,qo=[self.details[t]['quantization_parameters'] for t in (inp,w,out)]
            if len(qi['scales'])!=1 or len(qo['scales'])!=1 or np.any(qw['zero_points']):
                raise ValueError('unsupported quantization')
            scales=list(qw['scales'])
            count=self.constants[b].size
            if len(scales)==1: scales*=count
            pairs=[quantize_multiplier(float(qi['scales'][0])*float(v)/float(qo['scales'][0])) for v in scales]
            o=self.graph.operators[i].builtinOptions
            relu=o.fusedActivationFunction==s.ActivationFunctionType.RELU
            if o.fusedActivationFunction not in (s.ActivationFunctionType.NONE,s.ActivationFunctionType.RELU):
                raise ValueError('activation')
            self.specs[i]=dict(input_zero_point=int(qi['zero_points'][0]),
                output_zero_point=int(qo['zero_points'][0]),multipliers=[q for q,_ in pairs],
                shifts=[v for _,v in pairs],activation_min=int(qo['zero_points'][0]) if relu else -128,
                activation_max=127,padding='SAME' if getattr(o,'padding',0)==s.Padding.SAME else 'VALID',
                stride=[getattr(o,'strideH',1),getattr(o,'strideW',1)])
        # A real standalone SOFTMAX subgraph takes OUR computed logits as input.
        # Invoking the original whole graph here would overwrite them and cheat.
        m=copy.deepcopy(self.flat);g=m.subgraphs[0];op=copy.deepcopy(g.operators[12])
        ids=list(map(int,op.inputs))+list(map(int,op.outputs)); mapping={v:i for i,v in enumerate(ids)}
        g.tensors=[g.tensors[v] for v in ids]
        op.inputs=np.array([mapping[int(v)] for v in op.inputs],dtype=np.int32)
        op.outputs=np.array([mapping[int(v)] for v in op.outputs],dtype=np.int32)
        g.inputs=op.inputs.copy();g.outputs=op.outputs.copy();g.operators=[op]
        builder=flatbuffers.Builder(1024);off=m.Pack(builder);builder.Finish(off,file_identifier=b'TFL3')
        self.softmax_blob=bytes(builder.Output())
        self.softmax=tf.lite.Interpreter(model_content=self.softmax_blob,num_threads=1,
            experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)
        self.softmax.allocate_tensors()
        self.dw_cache={}
        qi,qw,qo=[self.details[t]['quantization_parameters'] for t in (32,16,33)]
        self.fc_scale=float(qi['scales'][0])*float(qw['scales'][0])/float(qo['scales'][0])

    def weights(self,i):
        return [self.constants[int(t)] for t in self.ops[i]['inputs'][1:]]

    def reference(self,x):
        self.golden.set_tensor(0,x);self.golden.invoke()
        return [self.golden.get_tensor(int(op['outputs'][0])) for op in self.ops]

    def first(self,x,p,n,c,co):
        w,b=self.weights(0);q=self.specs[0];sh,sw=q['stride']
        kh,kw=w.shape[1:3];h,ww=x.shape[1:3];oh,ow=25,5
        ph=max((oh-1)*sh+kh-h,0);pw=max((ow-1)*sw+kw-ww,0)
        pad=np.pad(x.astype(np.int64),((0,0),(ph//2,ph-ph//2),(pw//2,pw-pw//2),(0,0)),
            constant_values=q['input_zero_point'])
        patches=np.stack([pad[0,(v//ow)*sh:(v//ow)*sh+kh,(v%ow)*sw:(v%ow)*sw+kw,:] for v in range(p,p+n)])
        acc=(patches.reshape(n,-1)-q['input_zero_point']) @ w[c:c+co].reshape(co,-1).astype(np.int64).T+b[c:c+co]
        spec=dict(q,multipliers=q['multipliers'][c:c+co],shifts=q['shifts'][c:c+co])
        return requantize(acc,spec)

    def dw(self,stage,x,p,n):
        # Host-only mathematical memoization accelerates repeated trace policies.
        # Runtime ALWAYS charges the full replay/load/compute ledger on cache hits.
        key=(stage,sha(x.tobytes()),p,n)
        if key in self.dw_cache:return self.dw_cache[key].copy()
        i=2*stage-1;w,b=self.weights(i);q=self.specs[i]
        # Work on only requested output pixels, with zero-point SAME halo.
        pad=np.pad(x,((0,0),(1,1),(1,1),(0,0)),constant_values=q['input_zero_point'])
        pieces=[]
        for v in range(p,p+n):
            yy,xx=divmod(v,5)
            patch=pad[:,yy:yy+3,xx:xx+3,:]
            pieces.append(depthwise(patch,w[0],b,dict(q,padding='VALID')).reshape(64))
        result=np.stack(pieces)
        if len(self.dw_cache)>4096:self.dw_cache.clear()
        self.dw_cache[key]=result.copy()
        return result

    def pw(self,stage,z,ps,start,stop,c,co):
        i=2*stage;w,_=self.weights(i)
        return pw_accumulate(z,w[c:c+co,0,0,:].T.copy(),ps,start,stop,self.specs[i]['input_zero_point'])

    def bias(self,stage,n,c,co):
        return np.broadcast_to(self.weights(2*stage)[1][c:c+co],(n,co)).astype(np.int32).copy()

    def finish(self,stage,ps,c,co):
        q=self.specs[2*stage]
        return requantize(ps,dict(q,multipliers=q['multipliers'][c:c+co],shifts=q['shifts'][c:c+co]))

    def tail(self,x,intermediates=False):
        # SAME quantization pool: signed round-to-nearest, ties away from zero.
        sums=x.astype(np.int64).sum(axis=(1,2));count=x.shape[1]*x.shape[2]
        pool=(np.sign(sums)*((np.abs(sums)+count//2)//count)).astype(np.int8).reshape(1,1,1,64)
        fc_in=pool.reshape(1,64);w,b=self.weights(11)
        acc=(fc_in.astype(np.int64)-self.specs[11]['input_zero_point']) @ w.astype(np.int64).T+b
        if np.any(acc<-(1<<31)) or np.any(acc>(1<<31)-1):raise OverflowError('FC INT32')
        # TF 2.21 BUILTIN_REF per-tensor FC explicitly uses a float64 scale
        # overload, unlike DW/PW gemmlowp. Match that CPU reference head exactly;
        # do not mislabel this requantization as an integer accelerator kernel.
        # Source: tensorflow/lite/kernels/internal/reference/integer_ops/
        # fully_connected.h, floating-scale overload at v2.21.0.
        scaled=acc.astype(np.float64)*self.fc_scale
        rounded=np.where(scaled>=0,np.floor(scaled+.5),np.ceil(scaled-.5)).astype(np.int64)
        logits=np.clip(rounded+self.specs[11]['output_zero_point'],-128,127).astype(np.int8)
        self.softmax.set_tensor(int(self.softmax.get_input_details()[0]['index']),logits)
        self.softmax.invoke()
        out=self.softmax.get_tensor(int(self.softmax.get_output_details()[0]['index']))
        return [pool,fc_in,logits,out] if intermediates else out

    def uninterrupted(self,x):
        ys=[]
        a=self.first(x,0,125,0,64).reshape(1,25,5,64);ys.append(a)
        for stage in range(1,5):
            z=self.dw(stage,a,0,125)
            ps=self.pw(stage,z,self.bias(stage,125,0,64),0,64,0,64)
            a=self.finish(stage,ps,0,64).reshape(1,25,5,64)
            ys.extend([z.reshape(1,25,5,64),a])
        ys.extend(self.tail(a,True))
        return ys
