"""No chemistry/native package imports or benchmark execution."""
import copy
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[2] / 'betelgeuze_product' / 'benchmark_preparation_audit.py'
spec = importlib.util.spec_from_file_location('prep_audit_under_test', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def topology(elements=None, bonds=None):
    return {'schema_id': m.TOPOLOGY_SCHEMA, 'source_sha256': 'a'*64,
            'elements': ['C']*4 if elements is None else elements,
            'bonds': [[0,1],[1,2],[2,3]] if bonds is None else bonds,
            'hydrogen_state': 'unverified'}


def full_parameters():
    return {'atom_parameters': [{'atom_index':i} for i in range(4)],
            'bonds':[{'atom_i':i,'atom_j':i+1} for i in range(3)],
            'angles':[{'atom_i':i,'atom_j':i+1,'atom_k':i+2} for i in range(2)],
            'torsions':[{'atom_i':0,'atom_j':1,'atom_k':2,'atom_l':3}]}


class PreparationDemandTests(unittest.TestCase):
    def test_chain_paths(self):
        d = m.graph_demands(topology())
        self.assertEqual(d['bond_paths'], [[0,1],[1,2],[2,3]])
        self.assertEqual(d['angle_paths'], [[0,1,2],[1,2,3]])
        self.assertEqual(d['proper_paths'], [[0,1,2,3]])
        self.assertEqual(d['shortest_path_pair_counts'], {'1':3,'2':2,'3':1})

    def test_ring_shortest_paths_not_path_endpoints(self):
        d=m.graph_demands(topology(bonds=[[0,1],[1,2],[2,3],[0,3]]))
        self.assertEqual(len(d['proper_paths']),4)
        self.assertEqual(d['shortest_path_pair_counts'], {'1':4,'2':2,'3':0})

    def test_triangle_has_no_four_distinct_proper(self):
        d=m.graph_demands(topology(['C']*3,[[0,1],[1,2],[0,2]]))
        self.assertEqual(d['proper_paths'],[])

    def test_star_angles_not_improper_inference(self):
        d=m.graph_demands(topology(['C','H','H','H'],[[0,1],[0,2],[0,3]]))
        self.assertEqual(len(d['angle_paths']),3)
        self.assertEqual(d['proper_paths'],[])
        self.assertNotIn('improper_paths',d)

    def test_single_atom(self):
        d=m.graph_demands(topology(['C'],[]))
        self.assertEqual(d['angle_paths'],[])

    def test_no_implicit_hydrogen_generation(self):
        d=m.graph_demands(topology(['C'],[]))
        self.assertEqual(d['atom_count'],1)
        self.assertEqual(d['explicit_hydrogen_count'],0)
        self.assertFalse(d['hydrogen_completeness_verified'])

    def test_hydrogen_declaration_not_verification(self):
        t=topology(); t['hydrogen_state']='declared_all_explicit'
        self.assertFalse(m.graph_demands(t)['hydrogen_completeness_verified'])

    def test_missing_all_parameters(self):
        r=m.audit_preparation(topology(),receptor_atom_count=3)
        self.assertEqual(r['index_coverage']['torsions']['missing'],[[0,1,2,3]])
        self.assertEqual(r['index_coverage']['receptor_atom_parameters']['missing'],[[0],[1],[2]])
        self.assertEqual(r['energy_force_evaluations'],0)

    def test_matching_inventory_does_not_admit(self):
        r=m.audit_preparation(topology(),receptor_atom_count=1,base_parameters=full_parameters(),
                              receptor_parameters=[{'atom_index':0}])
        self.assertTrue(all(x['status']=='indices_match' for x in r['index_coverage'].values()))
        self.assertFalse(r['engine_admission_performed'])
        self.assertFalse(r['parameter_value_validation_performed'])
        self.assertFalse(r['parameterization_performed'])
        self.assertIn('independent_start_provenance',r['unverified_requirements'])

    def test_multiple_fourier_terms_same_path(self):
        p=full_parameters(); p['torsions']*=3
        r=m.audit_preparation(topology(),receptor_atom_count=1,base_parameters=p)
        self.assertEqual(r['index_coverage']['torsions']['supplied_term_count'],3)
        self.assertEqual(r['index_coverage']['torsions']['supplied_unique_count'],1)

    def test_duplicate_unique_required_inventory(self):
        p=full_parameters(); p['atom_parameters'].append({'atom_index':0})
        r=m.audit_preparation(topology(),receptor_atom_count=1,base_parameters=p)
        self.assertEqual(r['index_coverage']['atom_parameters']['status'],'indices_mismatch')
        self.assertEqual(r['index_coverage']['atom_parameters']['repeated_index_paths'],[[0]])

    def test_unexpected_valid_path_retained(self):
        p=full_parameters(); p['angles'].append({'atom_i':0,'atom_j':1,'atom_k':3})
        r=m.audit_preparation(topology(),receptor_atom_count=1,base_parameters=p)
        self.assertEqual(r['index_coverage']['angles']['unexpected'],[[0,1,3]])

    def test_absent_not_empty(self):
        a=m.audit_preparation(topology(['C'],[]),receptor_atom_count=1)
        b=m.audit_preparation(topology(['C'],[]),receptor_atom_count=1,base_parameters={'bonds':[]})
        self.assertEqual(a['index_coverage']['bonds']['status'],'not_supplied')
        self.assertEqual(b['index_coverage']['bonds']['status'],'indices_match')

    def test_source_hash_bound(self):
        t=topology(); d=m.graph_demands(t); t['source_sha256']='b'*64
        self.assertNotEqual(d['observation_sha256'],m.graph_demands(t)['observation_sha256'])

    def test_bond_order_invariant_observation_digest(self):
        a=topology(); b=topology(bonds=[[3,2],[2,1],[1,0]])
        self.assertEqual(m.graph_demands(a)['observation_sha256'],m.graph_demands(b)['observation_sha256'])

    def test_input_not_mutated(self):
        t=topology(); p=full_parameters(); before=copy.deepcopy((t,p))
        m.audit_preparation(t,receptor_atom_count=1,base_parameters=p)
        self.assertEqual((t,p),before)

    def test_disconnected(self):
        with self.assertRaises(m.PreparationAuditError): m.graph_demands(topology(bonds=[[0,1],[2,3]]))

    def test_duplicate_reversed_bonds(self):
        with self.assertRaises(m.PreparationAuditError): m.graph_demands(topology(bonds=[[0,1],[1,0],[1,2],[2,3]]))

    def test_boolean_index(self):
        with self.assertRaises(m.PreparationAuditError): m.graph_demands(topology(bonds=[[False,1],[1,2],[2,3]]))

    def test_repeated_atoms(self):
        p=full_parameters(); p['torsions'][0]['atom_l']=0
        with self.assertRaises(m.PreparationAuditError): m.audit_preparation(topology(),receptor_atom_count=1,base_parameters=p)

    def test_capacity(self):
        with self.assertRaises(m.PreparationAuditError): m.graph_demands(topology(['C']*257,[]))
        with self.assertRaises(m.PreparationAuditError): m.audit_preparation(topology(),receptor_atom_count=8193)

    def test_digest_and_fields(self):
        for key,value in [('source_sha256','A'*64),('hydrogen_state','verified'),('schema_id','other')]:
            t=topology();t[key]=value
            with self.assertRaises(m.PreparationAuditError): m.graph_demands(t)
        t=topology();t['coordinates']=[]
        with self.assertRaises(m.PreparationAuditError): m.graph_demands(t)

    def test_noninteger_receptor_count(self):
        for n in (True, 1.0, 0, -1):
            with self.assertRaises(m.PreparationAuditError): m.audit_preparation(topology(),receptor_atom_count=n)


if __name__=='__main__': unittest.main()
