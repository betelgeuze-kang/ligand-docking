import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import compare_contact_diversity_selection as m
import run_contact_selection_synthetic as runner
FIXTURE=ROOT/'tests/fixtures/contact_selection_synthetic.json'
PROTOCOL_SHA='5e4174ac18cd21f8fe3da494e7ffab0c2e33631f4c692b532ae273ca0f7e1f03'


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.protocol=json.loads(FIXTURE.read_text())
        self.data=copy.deepcopy(self.protocol['cases'][0]['selection_input'])

    def bind(self):
        self.data['contact_report_sha256']=m.sha(self.data['contact_report'])

    def test_protocol_frozen(self):
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),PROTOCOL_SHA)

    def test_three_arms(self):
        r=m.select(self.data)
        self.assertEqual(r['arms']['energy_only']['selected_ids'],['a','b'])
        self.assertEqual(r['arms']['energy_rmsd']['selected_ids'],['a','b'])
        self.assertEqual(r['arms']['energy_rmsd_contact']['selected_ids'],['a','c'])
        self.assertEqual(r['comparison_status'],'observed')

    def test_fixed_help_harm_noeffect(self):
        r=runner.run(self.protocol)
        self.assertEqual(len(r['cases']),7)
        self.assertTrue(r['cases'][0]['arms']['energy_rmsd_contact']['target_retained'])
        self.assertFalse(r['cases'][1]['arms']['energy_rmsd_contact']['target_retained'])
        self.assertTrue(r['cases'][1]['arms']['energy_rmsd']['target_retained'])
        self.assertTrue(all(a['target_retained'] for a in r['cases'][2]['arms'].values()))

    def test_labels_not_seen(self):
        a,b=self.protocol['cases'][:2]
        self.assertEqual(m.select(a['selection_input']),m.select(b['selection_input']))
        self.data['reference_rmsd']=0
        with self.assertRaises(m.InputError):m.select(self.data)

    def test_underfill(self):
        r=m.select(self.protocol['cases'][3]['selection_input'])
        a=r['arms']['energy_rmsd_contact']
        self.assertEqual(a['selected_ids'],['a']);self.assertEqual(a['unfilled_slots'],1)
        self.assertEqual(a['status'],'observed')

    def test_missing_contact_preserves_baseline(self):
        r=m.select(self.protocol['cases'][4]['selection_input'])
        self.assertEqual(r['arms']['energy_rmsd']['selected_ids'],['a','b'])
        self.assertEqual(r['arms']['energy_rmsd_contact']['status'],'unknown')
        self.assertEqual(r['candidate_counts']['eligible'],4)

    def test_empty_union_not_zero_similarity(self):
        r=m.select(self.protocol['cases'][5]['selection_input'])
        a=r['arms']['energy_rmsd_contact']
        self.assertEqual(a['status'],'unknown')
        self.assertEqual(a['decisions'][1]['reason'],'contact_comparison_unknown_empty_union')

    def test_missing_candidate_denominator(self):
        r=m.select(self.protocol['cases'][6]['selection_input'])
        self.assertEqual(r['candidate_counts']['expected'],5)
        self.assertEqual(r['candidate_counts']['missing'],1)
        self.assertEqual(r['comparison_status'],'unknown')

    def test_unknown_candidate_not_passed(self):
        self.data['expected_candidate_ids'].append('u');self.data['candidates'].append({'candidate_id':'u','status':'unknown'})
        r=m.select(self.data)
        self.assertEqual(r['unknown_candidate_ids'],['u']);self.assertEqual(r['comparison_status'],'unknown')

    def test_ineligible_failed_same_cohort(self):
        for cid,status in [('i','ineligible'),('f','failed')]:
            self.data['expected_candidate_ids'].append(cid);self.data['candidates'].append({'candidate_id':cid,'status':status})
        r=m.select(self.data)
        self.assertEqual(r['candidate_counts']['expected'],6)
        self.assertTrue(all(a['admissible_candidate_ids']==['a','b','c','d'] for a in r['arms'].values()))

    def test_false_admission_rejected(self):
        self.data['candidates'][0]['pose_valid']=False
        with self.assertRaises(m.InputError):m.select(self.data)

    def test_score_direction(self):
        self.data['score_descriptor']['direction']='maximize'
        self.assertEqual(m.select(self.data)['arms']['energy_only']['selected_ids'],['d','c'])

    def test_input_order_permutation(self):
        expected=m.select(self.data)
        self.data['candidates'].reverse();self.data['rmsd']['pairs'].reverse();self.data['contact_bindings'].reverse()
        actual=m.select(self.data)
        self.assertEqual(expected['arms'],actual['arms'])

    def test_tie_key(self):
        for row in self.data['candidates']:row['score']=0
        self.data['candidates'].reverse()
        self.assertEqual(m.select(self.data)['arms']['energy_only']['selected_ids'],['a','b'])

    def test_rmsd_inclusive(self):
        self.data['policy']['rmsd_min_angstrom']=1
        self.assertEqual(m.select(self.data)['arms']['energy_rmsd']['selected_ids'],['a','b'])
        self.data['policy']['rmsd_min_angstrom']=1.01
        self.assertEqual(m.select(self.data)['arms']['energy_rmsd']['selected_ids'],['a','c'])

    def test_contact_boundary(self):
        self.data['policy']['contact_distance_min']=0
        self.assertEqual(m.select(self.data)['arms']['energy_rmsd_contact']['selected_ids'],['a','b'])

    def test_missing_pair(self):
        self.data['rmsd']['pairs'].pop()
        r=m.select(self.data)
        self.assertEqual(r['arms']['energy_only']['status'],'observed')
        self.assertEqual(r['arms']['energy_rmsd']['status'],'unknown')
        self.assertEqual(r['candidate_counts']['eligible'],4)

    def test_context_and_binding_mismatch(self):
        for key in ('frame','atom_mapping_sha256'):
            data=copy.deepcopy(self.data);data['rmsd'][key]='bad'
            with self.assertRaises(m.InputError):m.select(data)
        self.data['contact_bindings'][0]['coordinates_sha256']='f'*64
        with self.assertRaises(m.InputError):m.select(self.data)

    def test_digest_mismatch(self):
        self.data['contact_report']['poses'][0]['contact_residue_ids']=[]
        with self.assertRaises(m.InputError):m.select(self.data)

    def test_unavailable_cannot_be_empty(self):
        self.data['contact_report']['poses'][0]['fingerprint_state']='unavailable';self.bind()
        with self.assertRaises(m.InputError):m.select(self.data)

    def test_duplicate_and_bad_numbers(self):
        with self.assertRaises(m.InputError):m.load_bytes(b'{"x":1,"x":2}')
        for val in (float('nan'),float('inf'),True):
            data=copy.deepcopy(self.data);data['candidates'][0]['score']=val
            with self.assertRaises(m.InputError):m.select(data)
        self.data['expected_candidate_ids'].append('a')
        with self.assertRaises(m.InputError):m.select(self.data)

    def test_empty_cohort_not_scientific_pass(self):
        self.data['candidates']=[];self.data['expected_candidate_ids']=[];self.data['contact_bindings']=[];self.data['rmsd']['pairs']=[]
        self.assertEqual(m.select(self.data)['comparison_status'],'unknown')

    def test_budget_and_depth(self):
        with self.assertRaises(m.InputError):m.load_bytes(b' '*(m.MAX_BYTES+1))
        with self.assertRaises(m.InputError):m.load_bytes(b'['*30+b'0'+b']'*30)

    def test_cli_deterministic_and_safe_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'input.json';raw=(m.canonical(self.data)+'\n').encode();path.write_bytes(raw)
            command=[sys.executable,'-I','-S',str(ROOT/'tools/compare_contact_diversity_selection.py'),str(path),'--expected-sha256',hashlib.sha256(raw).hexdigest()]
            a=subprocess.run(command,capture_output=True);b=subprocess.run(command,capture_output=True)
            self.assertEqual(a.returncode,0);self.assertEqual(a.stdout,b.stdout)
            command[4]=str(Path(temp)/'private-absent')
            c=subprocess.run(command,capture_output=True)
            self.assertEqual(c.returncode,2);self.assertNotIn(b'private-absent',c.stderr)


if __name__=='__main__':unittest.main()
