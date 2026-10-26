"""Stdlib tests: synthetic geometry only, never import an execution engine."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'tools/project_prepared_cross_contacts.py'
spec = importlib.util.spec_from_file_location('saved_projection', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
FIXTURE = ROOT / 'tests/fixtures/prepared_cross_contacts_synthetic.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.raw = FIXTURE.read_bytes()
        self.data = json.loads(self.raw)

    def project(self, data=None):
        raw = mod.serialize_json(self.data if data is None else data)
        return mod.project_prepared_cross(raw, expected_sha256=sha(raw))

    def reject(self, data=None, raw=None):
        raw = raw if raw is not None else mod.serialize_json(self.data if data is None else data)
        with self.assertRaises(mod.ProjectionError):
            mod.project_prepared_cross(raw, expected_sha256=sha(raw))

    def system(self, data=None):
        return (self.data if data is None else data)['sources']['receptor']['system']['system']

    def tensor(self, data=None):
        return self.system(data)['coordinates']['coordinates']['$tensor']

    def test_projection_and_receipt(self):
        contacts, receipt = self.project()
        self.assertEqual(contacts['schema_version'], 'residue_contacts_input.v1')
        self.assertEqual(contacts['comparisons'], [])
        self.assertEqual(contacts['poses'][0]['pose_id'], 'synthetic_saved_unchanged')
        self.assertEqual(contacts['receptor']['atoms'][1], {'atom_id':'receptor:atom:00001','residue_id':'receptor:residue:00000','element':'H','xyz':[1.0,0.0,0.0]})
        residues = contacts['receptor']['residues']
        self.assertEqual(residues[0]['chain'], '')
        self.assertNotEqual(residues[0]['residue_id'], residues[1]['residue_id'])
        self.assertEqual(residues[0]['resnum'], residues[1]['resnum'])
        projected = mod.serialize_json(contacts)
        self.assertEqual(receipt['projected_sha256'], sha(projected))
        self.assertEqual(receipt['projected_bytes'], len(projected))
        self.assertEqual(receipt['distance_ops'], 6)
        self.assertFalse(any(receipt['claims'].values()))
        self.assertEqual(self.project(), self.project())

    def test_no_mutation(self):
        previous = copy.deepcopy(self.data)
        self.project()
        self.assertEqual(self.data, previous)

    def test_hash_required_and_mismatch(self):
        with self.assertRaises(TypeError):
            mod.project_prepared_cross(self.raw)
        for digest in ['0'*64, '', 'A'*64, None, True]:
            with self.subTest(digest=digest), self.assertRaises(mod.ProjectionError):
                mod.project_prepared_cross(self.raw, expected_sha256=digest)
        with self.assertRaises(mod.ProjectionError):
            mod.project_prepared_cross(self.raw.decode(), expected_sha256=sha(self.raw))

    def test_strict_json(self):
        for raw in [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":-Infinity}', b'{"a":1e999}', b'\xff', b'{', b'[]', b'null', b'['*65+b'0'+b']'*65]:
            with self.subTest(raw=raw[:30]):
                self.reject(raw=raw)
        # Brackets and escaped quotes inside a string are not structural depth.
        self.data['unrelated'] = '["' * 100
        self.project()
        self.data['unrelated'] = {'deep': [float('inf')]}
        self.reject(raw=json.dumps(self.data).encode())

    def test_duplicate_nested_and_depth_boundary(self):
        raw = self.raw.replace(b'"dtype": "float64"', b'"dtype":"float64","dtype":"float64"')
        self.reject(raw=raw)
        for n in [63, 64]:
            value = 1
            for _ in range(n):
                value = [value]
            self.data['unrelated'] = value
            if n == 63:
                self.project()
            else:
                self.reject()

    def test_missing_required_fields(self):
        paths = [('schema_id',), ('status',), ('source_declarations',), ('sources',),
                 ('source_declarations','coordinate_frame_id'), ('source_declarations','prepared_state_id')]
        for path in paths:
            d = copy.deepcopy(self.data)
            node = d
            for p in path[:-1]: node = node[p]
            del node[path[-1]]
            with self.subTest(path=path): self.reject(d)
        for key in ['topology','coordinates','provenance']:
            d = copy.deepcopy(self.data)
            del self.system(d)[key]
            with self.subTest(key=key): self.reject(d)
        for key in list(self.system()['topology']):
            d = copy.deepcopy(self.data)
            del self.system(d)['topology'][key]
            with self.subTest(key=key): self.reject(d)

    def test_invalid_shape_types_values(self):
        for shape in [[True,3,3], [1,True,3], [1,3,True], [1,3.0,3], [1,3,2], [2,3,3], [3,3], None, {}, '1,3,3']:
            d = copy.deepcopy(self.data); self.tensor(d)['shape'] = shape
            with self.subTest(shape=shape): self.reject(d)
        for value in [[], [0]*9, None, [{'$float_hex':'0x0.0p+0'}]*8]:
            d = copy.deepcopy(self.data); self.tensor(d)['values'] = value
            with self.subTest(value=value): self.reject(d)
        self.tensor()['dtype'] = 'float32'; self.reject()

    def test_floathex_malformed(self):
        for token in ['nan','inf','-Infinity','1.0','0x1p0',' 0x1.0p+0','0x1.0p+9999','0x1.0p+500','0x1.0p-9999','0x1.00000000000001p+0','0x1.0p+0 junk', '', True, None]:
            d = copy.deepcopy(self.data); self.tensor(d)['values'][0] = {'$float_hex':token}
            with self.subTest(token=token): self.reject(d)
        for value in [{'$float_hex':'0x1.0p+0','extra':0}, {}, []]:
            d = copy.deepcopy(self.data); self.tensor(d)['values'][0] = value
            with self.subTest(value=value): self.reject(d)

    def test_exact_floathex_signed_zero_and_subnormal(self):
        for value in [-0.0, 0.0, float.fromhex('0x0.0000000000001p-1022'), 1e150]:
            self.tensor()['values'][0] = {'$float_hex': value.hex()}
            contacts, _ = self.project()
            self.assertEqual(contacts['receptor']['atoms'][0]['xyz'][0].hex(),value.hex())
        self.system()['topology']['cell_vectors'] = [[1,0,0],[0,1,0],[0,0,1]]
        self.reject()

    def test_indices_and_partitions(self):
        changes = [('atoms',0,'index',True), ('atoms',1,'index',0), ('atoms',0,'residue_index',2),
                   ('atoms',0,'residue_index',False), ('residues',0,'index',1),
                   ('residues',0,'chain_index',1), ('residues',0,'atom_indices',[0,0]),
                   ('residues',0,'atom_indices',[1,0]), ('residues',0,'atom_indices',[False,1]),
                   ('residues',1,'atom_indices',[1,2]), ('chains',0,'index',True),
                   ('chains',0,'residue_indices',[0,0]), ('chains',0,'residue_indices',[1,0]),
                   ('residues',0,'sequence_number',True)]
        for group,index,key,value in changes:
            d=copy.deepcopy(self.data); self.system(d)['topology'][group][index][key]=value
            with self.subTest(change=(group,key,value)): self.reject(d)

    def test_frame_units_periodic_and_schema(self):
        for key in ['coordinate_frame_id','prepared_state_id']:
            d=copy.deepcopy(self.data); self.system(d)['provenance']['metadata']['state_declarations'][key]='other'
            self.reject(d)
        for side in ['topology','coordinates']:
            for key,value in [('coordinate_unit','nm'), ('cell_periodic',False), ('cell_periodic',[False]*3)]:
                d=copy.deepcopy(self.data); self.system(d)[side][key]=value
                self.reject(d)
        self.system()['coordinates']['cell_vectors'] = [[1,0,0]]; self.reject()
        for change in ['source','wrapper','topology']:
            d=copy.deepcopy(json.loads(self.raw))
            node=d if change=='source' else d['sources']['receptor']['system'] if change=='wrapper' else self.system(d)['topology']
            node['schema_id']='wrong'; self.reject(d)

    def test_text_and_declared_hashes(self):
        for value in ['', None, 1, '\ud800', 'x'*129, 'hello\nworld']:
            d=copy.deepcopy(self.data); self.system(d)['topology']['atoms'][0]['name']=value
            self.reject(d)
        for key in ['name','element','residue_index','index']:
            d=copy.deepcopy(self.data); del self.system(d)['topology']['atoms'][0][key]; self.reject(d)
        self.data['sources']['receptor']['system']['system_sha256']='2'*64
        self.reject()

    def test_private_source_identity_not_echoed(self):
        marker='/private/example/saved-input.pdb'
        self.system()['topology']['source']['id']=marker
        self.system()['topology']['system_id']=marker
        contacts,receipt=self.project()
        self.assertNotIn(marker,mod.serialize_json(receipt).decode())
        self.assertEqual(receipt['source_identity']['receptor']['source_id_sha256'],sha(marker.encode()))

    def test_receipt_hashes_all_source_labels(self):
        marker = '/private/example/label'
        self.data['status'] = marker
        for key in ['coordinate_frame_id', 'prepared_state_id']:
            self.data['source_declarations'][key] = marker
            for role in ['receptor','ligand']:
                self.data['sources'][role]['system']['system']['provenance']['metadata']['state_declarations'][key] = marker
        contacts, receipt = self.project()
        self.assertNotIn(marker, mod.serialize_json(receipt).decode())
        self.assertEqual(contacts['coordinate_frame'], marker)
        self.assertEqual(contacts['poses'][0]['pose_id'], marker)
        for key in ['declared_status_sha256','declared_saved_state_id_sha256','coordinate_frame_sha256']:
            self.assertEqual(receipt[key],sha(marker.encode()))
        self.assertFalse(receipt['unrelated_source_fields_interpreted'])
        self.assertFalse(receipt['canonical_system_hashes_recomputed'])

    def test_budgets(self):
        for key,value in [('source_bytes',len(self.raw)-1), ('atoms_per_side',2), ('residues_per_side',1), ('distance_ops',5), ('projected_bytes',10)]:
            with self.subTest(key=key), patch.dict(mod.LIMITS,{key:value}), self.assertRaises(mod.ProjectionError):
                mod.project_prepared_cross(self.raw,expected_sha256=sha(self.raw))
        self.reject(raw=b' '*(mod.LIMITS['source_bytes']+1))

    def test_cli_receipt_exact_stdout_and_no_mutation(self):
        original=FIXTURE.read_bytes()
        for flags in [[], ['-O'], ['-S'], ['-O','-S']]:
            cmd=[sys.executable,*flags,str(SCRIPT),str(FIXTURE),'--expected-sha256',sha(original)]
            contacts=subprocess.run(cmd,capture_output=True,check=True)
            receipt=subprocess.run(cmd+['--format','receipt'],capture_output=True,check=True)
            self.assertEqual(contacts.stderr,b'')
            self.assertEqual(receipt.stderr,b'')
            r=json.loads(receipt.stdout)
            self.assertEqual(r['projected_sha256'],sha(contacts.stdout))
            self.assertEqual(r['projected_bytes'],len(contacts.stdout))
            self.assertTrue(contacts.stdout.endswith(b'\n'))
            self.assertFalse(contacts.stdout.endswith(b'\n\n'))
        self.assertEqual(FIXTURE.read_bytes(),original)

    def test_cli_errors_no_partial_output_or_path(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'private-source.json'; path.write_bytes(b'{')
            for args in [[str(path),'--expected-sha256',sha(b'{')], [str(path/'absent'),'--expected-sha256','0'*64], [str(path),'--expected-sha256','0'*64]]:
                p=subprocess.run([sys.executable,str(SCRIPT),*args],capture_output=True)
                self.assertEqual(p.returncode,2); self.assertEqual(p.stdout,b'')
                self.assertNotIn(temp.encode(),p.stderr)


if __name__ == '__main__':
    unittest.main()
