"""Export pinned MLPerf Tiny tensors. No training or accuracy claim is made."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '09_Simulation'))
import numpy as np
from recap.integer import quantize_multiplier, depthwise, pointwise, accumulator_bound


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export(destination):
    import tensorflow as tf
    from tensorflow.lite.python import schema_py_generated as schema
    source = ROOT / '05_Model_Training/reference_mlperf'
    manifest = json.loads((source/'source_manifest.json').read_text())
    for item in manifest['files']:
        if sha(source/item['path']) != item['sha256']:
            raise ValueError('source checksum mismatch: '+item['path'])
    model = source/'kws_ref_model.tflite'
    interpreter = tf.lite.Interpreter(
        model_content=model.read_bytes(), experimental_preserve_all_tensors=True,
        experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF,
        num_threads=1)
    interpreter.allocate_tensors()
    details = {d['index']: d for d in interpreter.get_tensor_details()}
    ops = interpreter._get_ops_details()
    graph = schema.ModelT.InitFromObj(schema.Model.GetRootAsModel(model.read_bytes(),0)).subgraphs[0]
    literal = (source/'kws_input_data.cc').read_text().split('= {',1)[1].rsplit('};',1)[0]
    values = [int(v) for v in re.findall(r'-?\d+', literal)]
    input_info = interpreter.get_input_details()[0]
    sample = np.asarray(values, dtype=np.int8).reshape(input_info['shape'])
    rng = np.random.default_rng(20261015)
    fixtures = {'official_sample': sample,
                'unit_min': np.full_like(sample,-128),
                'unit_max': np.full_like(sample,127),
                'unit_seed20261015': rng.integers(-128,128,size=sample.shape,dtype=np.int8)}
    destination.mkdir(parents=True,exist_ok=True)

    def spec(op, dw):
        inp, weight, _ = map(int,op['inputs'])
        out = int(op['outputs'][0])
        qi, qw, qo = (details[t]['quantization_parameters'] for t in (inp,weight,out))
        if len(qi['scales']) != 1 or len(qo['scales']) != 1 or np.any(qw['zero_points'] != 0):
            raise ValueError('unsupported quantization')
        scales = [float(qi['scales'][0])*float(w)/float(qo['scales'][0]) for w in qw['scales']]
        expected_axis = 3 if dw else 0
        if qw['quantized_dimension'] != expected_axis:
            raise ValueError('unsupported weight quantization axis')
        options = graph.operators[op['index']].builtinOptions
        if options.fusedActivationFunction not in (schema.ActivationFunctionType.NONE, schema.ActivationFunctionType.RELU):
            raise ValueError('unsupported activation')
        if options.dilationHFactor != 1 or options.dilationWFactor != 1:
            raise ValueError('unsupported dilation')
        if dw and options.depthMultiplier != 1:
            raise ValueError('unsupported depth multiplier')
        pairs = [quantize_multiplier(s) for s in scales]
        return dict(input_zero_point=int(qi['zero_points'][0]), output_zero_point=int(qo['zero_points'][0]),
                    multipliers=[p[0] for p in pairs], shifts=[p[1] for p in pairs],
                    activation_min=int(qo['zero_points'][0]) if options.fusedActivationFunction == schema.ActivationFunctionType.RELU else -128,
                    activation_max=127, padding='SAME' if options.padding == schema.Padding.SAME else 'VALID',
                    stride=[options.strideH,options.strideW], rounding='tflite_gemmlowp_two_rounding')

    checks = []
    pair_specs = []
    for n in range(1,len(ops)-1):
        dw,pw = ops[n:n+2]
        if dw['op_name'] != 'DEPTHWISE_CONV_2D' or pw['op_name'] != 'CONV_2D':
            continue
        wshape = details[int(pw['inputs'][1])]['shape']
        if tuple(wshape[1:3]) != (1,1):
            raise ValueError('PW must be 1x1')
        pair_specs.append((dw,pw,spec(dw,True),spec(pw,False)))
    official_arrays = None
    for fixture_name, value in fixtures.items():
        interpreter.set_tensor(input_info['index'],value)
        interpreter.invoke()
        arrays = {'input':value,'output':interpreter.get_tensor(interpreter.get_output_details()[0]['index'])}
        for k,(dw,pw,ds,ps) in enumerate(pair_specs):
            x=interpreter.get_tensor(int(dw['inputs'][0]))
            wd=interpreter.get_tensor(int(dw['inputs'][1]))[0]
            bd=interpreter.get_tensor(int(dw['inputs'][2]))
            wp=interpreter.get_tensor(int(pw['inputs'][1]))[:,0,0,:].T.copy()
            bp=interpreter.get_tensor(int(pw['inputs'][2]))
            z=interpreter.get_tensor(int(dw['outputs'][0]))
            y=interpreter.get_tensor(int(pw['outputs'][0]))
            own_z=depthwise(x,wd,bd,ds)
            own_y=pointwise(own_z,wp,bp,ps)
            dz,dy=int(np.count_nonzero(own_z != z)),int(np.count_nonzero(own_y != y))
            checks.append(dict(fixture=fixture_name,pair=k,dw_mismatches=dz,pw_mismatches=dy,
                               dw_elements=z.size,pw_elements=y.size))
            if dz or dy:
                raise AssertionError(checks[-1])
            for name,t in dict(x=x,wd=wd,bd=bd,wp=wp,bp=bp,z=z,y=y).items():
                arrays[f'pair{k}_{name}']=t
        np.savez_compressed(destination/(fixture_name+'.npz'),**arrays)
        if fixture_name == 'official_sample':
            official_arrays=arrays
    dw,pw,ds,ps=pair_specs[0]
    # Interior 2x2 spatial tile, full 64 input channels, first 4 output channels.
    a=official_arrays
    micro={k:a['pair0_'+k] for k in ['wd','bd']}
    micro.update(x=a['pair0_x'][:,:4,:4,:].copy(),wp=a['pair0_wp'][:,:4].copy(),bp=a['pair0_bp'][:4].copy(),
                 z=a['pair0_z'][:,1:3,1:3,:].copy(),y=a['pair0_y'][:,1:3,1:3,:4].copy())
    ds=dict(ds,padding='VALID')
    ps=dict(ps,multipliers=ps['multipliers'][:4],shifts=ps['shifts'][:4])
    np.testing.assert_array_equal(depthwise(micro['x'],micro['wd'],micro['bd'],ds),micro['z'])
    np.testing.assert_array_equal(pointwise(micro['z'],micro['wp'],micro['bp'],ps),micro['y'])
    np.savez_compressed(destination/'microtile.npz',**micro)
    identity=dict(model_hash=sha(model),input_id=hashlib.sha256(micro['x'].tobytes()).hexdigest(),
                  descriptor_id='pair0_y1:3_x1:3_ci0:64_co0:4_VALID_halo1_v1',
                  arithmetic_id='int8_int32_gemmlowp_double_v1',layout_id='NHWC_KH_KW_C_CI_CO_v1')
    (destination/'microtile.json').write_text(json.dumps(dict(identity=identity,dw=ds,pw=ps,
          provenance='Official MLPerf sample, interior crop; no dataset accuracy measurement',
          dw_accumulator_abs_bounds=accumulator_bound(micro['wd'],micro['bd'],ds['input_zero_point']),
          pw_accumulator_abs_bounds=accumulator_bound(micro['wp'],micro['bp'],ps['input_zero_point'])),indent=2)+'\n')
    inventory=[]
    total_macs=0
    for op in ops:
        if op['op_name'] in ('CONV_2D','DEPTHWISE_CONV_2D','FULLY_CONNECTED'):
            ws=details[int(op['inputs'][1])]['shape']
            outputs=int(np.prod(details[int(op['outputs'][0])]['shape']))
            terms=int(ws[1]*ws[2]) if op['op_name']=='DEPTHWISE_CONV_2D' else int(np.prod(ws[1:]))
            macs=outputs*terms
            total_macs+=macs
            inventory.append(dict(op=int(op['index']),kind=op['op_name'],macs=macs))
    constants={int(t) for op in ops for t in op['inputs'][1:] if t>=0}
    weight_ids={int(op['inputs'][1]) for op in ops if op['op_name'] in ('CONV_2D','DEPTHWISE_CONV_2D','FULLY_CONNECTED')}
    report=dict(status='PASS_REFERENCE_SCOPE',repository_commit=manifest['commit'],model_sha256=sha(model),
                model_file_bytes=model.stat().st_size,input_shape=list(sample.shape),
                weight_bytes=sum(interpreter.get_tensor(t).nbytes for t in weight_ids),
                constant_tensor_bytes=sum(interpreter.get_tensor(t).nbytes for t in constants),
                macs=total_macs,operator_inventory=inventory,verified_pairs=len(pair_specs),fixtures=len(fixtures),
                checks=checks,accuracy=None,accuracy_reason='One unlabeled official sample plus three arithmetic stress fixtures; not a test dataset',
                activation_peak_bytes=None,activation_peak_reason='TFLite arena/scratch and full intermittent liveness not characterized',
                tensorflow=tf.__version__,numpy=np.__version__,reference_resolver='BUILTIN_REF',
                microtile_identity=identity)
    (destination/'reference_report.json').write_text(json.dumps(report,indent=2)+'\n')
    artifacts={p.name:sha(p) for p in sorted(destination.iterdir()) if p.is_file() and p.name!='artifact_hashes.json'}
    (destination/'artifact_hashes.json').write_text(json.dumps(artifacts,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['status','verified_pairs','fixtures','weight_bytes','macs']}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'10_Experiments/g2/reference')
    export(parser.parse_args().output)
