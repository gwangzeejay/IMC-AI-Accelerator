import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
import zlib
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'09_Simulation'))
from g4_reference import encode,decode,latest,commit_transactions,oracle_arrays,HEADER


class BinaryProtocolTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/'10_Experiments/g4/vectors/g2_micro/config.json').read_text())
        self.identity=tuple(bytes.fromhex(x) for x in self.config['identity'])
        self.arrays=oracle_arrays(ROOT,self.config)
        self.memory=bytearray(2*self.config['slot_bytes']+1)

    def install(self,slot,header,payload):
        base=slot*self.config['slot_bytes'];self.memory[base:base+HEADER]=header
        self.memory[base+HEADER:base+HEADER+len(payload)]=payload

    def test_crc_known_vector(self):
        self.assertEqual(zlib.crc32(b'123456789'),0xcbf43926)

    def test_full_identity_and_record_roundtrip(self):
        h,p=encode(self.identity,1,16,self.arrays['z'],self.arrays['ps'][16]);self.install(0,h,p)
        r=latest(self.memory,self.config)
        self.assertEqual(r['offset'],16);self.assertEqual(r['z'],self.arrays['z']);self.assertEqual(r['ps'],self.arrays['ps'][16])
        self.assertEqual(h[8:40],self.identity[0]);self.assertEqual(h[40:72],self.identity[1]);self.assertEqual(h[72:104],self.identity[2])

    def test_unpublished_record_ignored(self):
        h,p=encode(self.identity,1,16,ps=self.arrays['ps'][16]);self.install(0,h,p);self.memory[0]=0
        self.assertIsNone(latest(self.memory,self.config))

    def test_crc_payload_and_metadata_corruption_rejected(self):
        for pos in (104,HEADER):
            h,p=encode(self.identity,1,16,ps=self.arrays['ps'][16]);self.memory=bytearray(len(self.memory));self.install(0,h,p);self.memory[pos]^=1
            self.assertIsNone(latest(self.memory,self.config))

    def test_wrong_identity_not_restored(self):
        wrong=(b'\xff'*32,self.identity[1],self.identity[2]);h,p=encode(wrong,1,16,ps=self.arrays['ps'][16]);self.install(0,h,p)
        self.assertIsNone(latest(self.memory,self.config))

    def test_fallback_and_latest_generation(self):
        for slot in (0,1):
            h,p=encode(self.identity,slot+1,16*(slot+1),ps=self.arrays['ps'][16*(slot+1)]);self.install(slot,h,p)
        self.assertEqual(latest(self.memory,self.config)['generation'],2)
        self.memory[self.config['slot_bytes']+HEADER]^=1
        self.assertEqual(latest(self.memory,self.config)['generation'],1)

    def test_save_false_keep_false_preserves_old_nonzero_prefix(self):
        h,p=encode(self.identity,1,16,ps=self.arrays['ps'][16]);self.install(0,h,p)
        ops,_=commit_transactions(self.memory,self.config,False,False,False,32,self.arrays)
        for kind,addr,data in ops:self.memory[addr]=data
        r=latest(self.memory,self.config)
        self.assertEqual(r['offset'],16);self.assertEqual(r['ps'],self.arrays['ps'][16]);self.assertNotEqual(r['ps'],self.arrays['ps'][32])

    def test_output_publication_before_frontier(self):
        ops,_=commit_transactions(self.memory,self.config,False,False,True,64,self.arrays)
        for kind,addr,data in ops[:-1]:self.memory[addr]=data
        r=latest(self.memory,self.config)
        self.assertEqual(r['output'],self.arrays['output']);self.assertEqual(self.memory[-1],0)
        self.assertEqual(ops[-1],('W',2*self.config['slot_bytes'],1))

    def test_malformed_flags_and_prefix_rejected_with_valid_crc(self):
        h,p=encode(self.identity,1,32);self.install(0,h,p)
        self.assertIsNone(latest(self.memory,self.config))
        h,p=encode(self.identity,1,64,self.arrays['z'],output=self.arrays['output']);self.install(0,h,p)
        self.assertIsNone(latest(self.memory,self.config))

    def test_json_to_binary_semantics_do_not_imply_equal_traffic(self):
        h,p=encode(self.identity,1,16,self.arrays['z'],self.arrays['ps'][16]);self.install(0,h,p)
        cfg=json.loads((ROOT/'10_Experiments/g4/vectors/g2_micro/config.json').read_text())
        with np.load(ROOT/cfg['source'],allow_pickle=False) as f:
            expected_ps=np.broadcast_to(f['bp'],f['y'].shape).copy().astype(np.int32)
        self.assertEqual(len(h),124)
        self.assertEqual(len(p),cfg['z_bytes']+cfg['ps_bytes'])
        self.assertEqual(len(expected_ps.tobytes()),cfg['ps_bytes'])


if __name__=='__main__':unittest.main()
