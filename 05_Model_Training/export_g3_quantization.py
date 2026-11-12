"""Extract PW per-channel parameters for expanded G3 CO descriptors."""
import json
import os
from pathlib import Path
import sys
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','3')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS','0')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'09_Simulation'))
from recap.integer import quantize_multiplier


def export():
    import tensorflow as tf
    import hashlib
    model=(ROOT/'05_Model_Training/reference_mlperf/kws_ref_model.tflite').read_bytes()
    report=json.loads((ROOT/'10_Experiments/g2/reference/reference_report.json').read_text())
    if hashlib.sha256(model).hexdigest()!=report['model_sha256']:
        raise ValueError('model hash mismatch')
    interpreter=tf.lite.Interpreter(model_content=model,experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)
    interpreter.allocate_tensors()
    op=interpreter._get_ops_details()[2]
    if op['op_name']!='CONV_2D': raise ValueError('unexpected model topology')
    details={d['index']:d for d in interpreter.get_tensor_details()}
    qi,qw,qo=[details[int(t)]['quantization_parameters'] for t in (op['inputs'][0],op['inputs'][1],op['outputs'][0])]
    if any(qw['zero_points']!=0) or qw['quantized_dimension']!=0: raise ValueError('unexpected quantization')
    pairs=[quantize_multiplier(float(qi['scales'][0])*float(w)/float(qo['scales'][0])) for w in qw['scales']]
    spec=dict(input_zero_point=int(qi['zero_points'][0]),output_zero_point=int(qo['zero_points'][0]),
              multipliers=[m for m,s in pairs],shifts=[s for m,s in pairs],activation_min=int(qo['zero_points'][0]),
              activation_max=127,padding='SAME',stride=[1,1],rounding='tflite_gemmlowp_two_rounding')
    out=ROOT/'10_Experiments/g3/descriptors';out.mkdir(parents=True,exist_ok=True)
    (out/'pair0_quantization.json').write_text(json.dumps(dict(model_hash=report['model_sha256'],pw=spec),indent=2)+'\n')
    print('G3 PW quantization exported: 64 output channels')


if __name__=='__main__': export()
