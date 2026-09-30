"""Portable stdlib boundary tests; no external archive or molecular dependency."""
from contextlib import ExitStack
from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve()
MODULE = HERE.parents[2]/'docs/research/human_5ht6_sro_pose_recovery/recovery_protocol.py'
if not MODULE.exists():
    MODULE = HERE.parent/'recovery_protocol.py'
spec = importlib.util.spec_from_file_location('sro_recovery', MODULE)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

NAMES = ['OH','CZ3','CH2','CZ2','CE2','NE1','CD1','CG','CD2','CE3','CB','CA','NZ']

def synthetic_chemistry():
    atoms = []
    for i, name in enumerate(NAMES+[f'H{i}' for i in range(13)]):
        element = 'O' if i == 0 else ('N' if i in (5,12) else ('C' if i < 13 else 'H'))
        atoms.append({'index': i, 'name': name, 'element': element,
                      'atomic_number': {'O':8,'N':7,'C':6,'H':1}[element], 'formal_charge': int(i == 12),
                      'isotope_mass_number': None, 'aromatic': False, 'stereo': 'unspecified',
                      'partial_charge_e': float(i == 12), 'mass_da': float({'O':16,'N':14,'C':12,'H':1}[element])})
    pairs = [(i,i+1) for i in range(12)] + [(0,2),(1,3)]
    parents = [0,2,3,5,6,9,10,10,11,11,12,12,12]
    pairs += [(parent,13+i) for i,parent in enumerate(parents)]
    bonds = [{'atom_i': i, 'atom_j':j,'order':1.0,'aromatic':False,'stereo':'none'} for i,j in pairs]
    return {'schema_id':'sro_coordinate_free_chemistry/1','coordinate_frame_id':r.FRAME,
            'computational_microstate':deepcopy(r.STATE),'atoms':atoms,'bonds':bonds}

class RecoveryBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.chem = synthetic_chemistry()
        self.xyz = [[float(i),float(i*i%7),float(i%3)] for i in range(26)]
        block = {'$tensor':{'dtype':'float64','shape':[1,26,3],'values':[{'$float_hex': v.hex()} for row in self.xyz for v in row]}}
        system = {'coordinates': {'coordinate_unit':'angstrom','coordinates':block},
                  'topology': {'atoms':self.chem['atoms'],'bonds':self.chem['bonds']}}
        pins={}
        for name,value in {'ligand':{'system':system},'parameters':{},'extensions':{},'receptor':{},
                           'cross_parameters':{'max_internal_increase_kcal_per_mol':5.0}}.items():
            path=self.root/(name+'.json'); r.publish(path,value); pins[name]=r.reference(path)
        authority={'numerical_development_only':True,'reserved_source_role_unchanged':True,
                   'training_admitted':False,'pose_recovery_admitted':False}
        prep_protocol={'computational_microstate':r.STATE,'authority':authority}
        observed=[{'label_atom_id':a['name'],'id':str(8000+i),'type_symbol':a['element'],
                   'Cartn_x':str(self.xyz[i][0]),'Cartn_y':str(self.xyz[i][1]),'Cartn_z':str(self.xyz[i][2]),
                   'occupancy':'1.00','label_alt_id':'.'} for i,a in enumerate(self.chem['atoms'][:13])]
        provenance={'atoms':[{'name':a['name'],'source_atom_site_id':str(8000+i) if i<13 else None,
                             'coordinates_angstrom':self.xyz[i],'origin':'observed_source_heavy' if i<13 else 'generated_hydrogen'}
                            for i,a in enumerate(self.chem['atoms'])]}
        files={}
        for name,value in {'protocol.json':prep_protocol,'atom-provenance.json':provenance,
                           'source-graph.json':{'observed_atoms':observed}}.items():
            path=self.root/name;r.publish(path,value); pin=r.reference(path); files[name]={k:pin[k] for k in ('bytes','sha256')}
        r.publish(self.root/'manifest.v1.json',{'computational_microstate':r.STATE,'scientific_authority':authority,'files':files})
        request={'solver':{'force_tolerance':.001,'max_objective_attempts':417},'pocket':{'coordinate_frame_id':r.FRAME}}
        r.publish(self.root/'request.json',request)
        evidence={'prepared_inputs':pins,'request':r.reference(self.root/'request.json')}
        self.evidence=self.root/'evidence.json';r.publish(self.evidence,evidence)
        self.hashes={k:v['sha256'] for k,v in pins.items()}
        self.stack.enter_context(patch.object(r,'INPUT_HASHES',self.hashes))
        self.stack.enter_context(patch.object(r,'EVIDENCE_SHA',r.reference(self.evidence)['sha256']))
        self.packet=self.root/'packet'
        r.generate_packet(self.evidence,self.packet)
        self.protocol=json.loads((self.packet/'protocol.json').read_text())
        verified=r.verify_packet(self.packet)
        self.review={'schema_id':'sro_recovery_freeze_review/1','protocol_sha256':verified['protocol_sha256'],
                     'manifest_sha256':verified['manifest_sha256'],'reviewed_before_execution':True,
                     'reviewed_at':'2026-10-01T00:00:00+00:00','reviewer':'synthetic_test_only',
                     'execution_scope':'separately_authorized_future_execution'}
        self.receipt=self.root/'synthetic-saved-receipt.json';r.publish(self.receipt,{'role':'synthetic_no_molecular_execution'})

    def result(self, case='perturbed_01'):
        candidates=json.loads((self.packet/'calculation_inputs/candidates.json').read_text())['cases']
        candidates.append(json.loads((self.packet/'stability_control/candidate.json').read_text()))
        candidate=next(c for c in candidates if c['case_id']==case)
        return {'case_id':case,'status':'completed','started_at':'2026-10-01T00:01:00+00:00',
                'input_coordinates_sha256':r.value_hash(candidate['coordinates_angstrom']),
                'chemistry_sha256':self.protocol['coordinate_free_chemistry_sha256'],'original_input_hashes':self.hashes,
                'endpoint_policy':'last_accepted_state','coordinates_angstrom':deepcopy(self.xyz),
                'forces_kcal_per_mol_angstrom':[[0.,0.,0.] for _ in range(26)],
                'initial_internal_energy_kcal_per_mol':10.,'final_internal_energy_kcal_per_mol':14.,
                'baseline_dimensionless_score':2.,'final_dimensionless_score':1.,'geometry_complete':True,
                'geometry_checks':dict.fromkeys(r.CHECKS,True),
                'numerical_audit':{'endpoint_count':2,'maximum_energy_error_kcal_per_mol':0.,
                                   'maximum_force_component_error_kcal_per_mol_angstrom':0.},
                'work':{'objective_attempts':2,'initial_successful_objectives':1,'accepted_steps':1,'rejected_attempts':0,
                        'failed_attempts':0,'unknown_pending_attempts':0,'restart_force_calls':0,'score_calls':2,
                        'oracle_states':2,'AI_inference_calls':0,'proposal_calls':0},
                'actual_receipt_refs':[r.reference(self.receipt)]}

    def evaluate(self, results):
        return r.evaluate_saved_results(self.packet,{'schema_id':'sro_saved_recovery_results/1',
             'protocol_sha256':r.value_hash(self.protocol),'authority':deepcopy(r.AUTHORITY),'case_results':results},self.review)

    def rehash_packet(self, name):
        manifest=json.loads((self.packet/'manifest.json').read_text())
        raw=(self.packet/name).read_bytes();manifest['files'][name]={'sha256':r.digest(raw),'bytes':len(raw)}
        if name=='protocol.json':manifest['protocol_sha256']=r.digest(raw)
        (self.packet/'manifest.json').write_bytes(r.encoded(manifest))

    def test_all_four_initial_errors_above_acceptance_and_control_separate(self):
        metrics=json.loads((self.packet/'evaluation_only/initial_metrics.json').read_text())['cases']
        self.assertEqual(len(metrics),5)
        for s in r.SPECS:self.assertGreater(metrics[s['case_id']]['symmetry_heavy_rmsd_angstrom'],2.25)
        self.assertEqual(metrics['observed_start_control']['direct_heavy_rmsd_angstrom'],0)
        self.assertEqual(self.protocol['budget']['candidate_count'],4)
        self.assertEqual(self.protocol['budget']['objective_attempts_per_case'],417)

    def test_translation_is_never_fitted_away(self):
        shifted=[[p[0]+3,p[1],p[2]] for p in self.xyz]
        metric=r.receptor_frame_rmsd(shifted,self.xyz[:13],list(range(13)),[list(range(13))])
        self.assertEqual(metric['symmetry_heavy_rmsd_angstrom'],3)
        self.assertFalse(metric['translation_or_rotation_fit'])

    def test_symmetry_uses_chemical_graph_and_not_labels(self):
        atoms=[{'index':i,'name':str(i),'element':'C','formal_charge':0,'isotope_mass_number':None,
                'aromatic':False,'stereo':'unspecified'} for i in range(2)]
        chem={'atoms':atoms,'bonds':[{'atom_i':0,'atom_j':1,'order':1,'aromatic':False,'stereo':'none'}]}
        mappings=r.automorphisms(chem)
        self.assertEqual(mappings,[[0,1],[1,0]])
        metric=r.receptor_frame_rmsd([[2.,0,0],[0.,0,0]],[[0.,0,0],[2.,0,0]],[0,1],mappings)
        self.assertEqual(metric['symmetry_heavy_rmsd_angstrom'],0)
        self.assertEqual(metric['direct_heavy_rmsd_angstrom'],2)
        chem['atoms'][1]['formal_charge']=1
        self.assertEqual(r.automorphisms(chem),[[0,1]])

    def test_rigid_transform_preserves_every_atom_pair_distance(self):
        spec=deepcopy(r.SPECS[3]); pivot=[0.,0.,0.]
        after=r.rigid_transform(self.xyz,spec,pivot)
        for i in range(26):
            for j in range(i):self.assertAlmostEqual(math.dist(self.xyz[i],self.xyz[j]),math.dist(after[i],after[j]),places=11)
        self.assertEqual(after,r.rigid_transform(self.xyz,spec,pivot))

    def test_zero_perturbation_rejected(self):
        spec=deepcopy(r.SPECS[0]);spec['translation_angstrom']=0
        with self.assertRaisesRegex(r.ProtocolError,'nonzero_translation'):r.rigid_transform(self.xyz,spec,[0.,0.,0.])

    def test_nonfinite_coordinate_rejected(self):
        for value in (float('nan'),float('inf'),True):
            with self.subTest(value=value):
                xyz=deepcopy(self.xyz);xyz[0][0]=value
                with self.assertRaises(r.ProtocolError):r.coordinates(xyz,26)

    def test_result_denominator_keeps_missing_and_control_never_recovers(self):
        report=self.evaluate([self.result(),self.result('observed_start_control')])
        self.assertEqual(report['recovery_denominator'],4)
        self.assertEqual(report['recovery_success_count'],1)
        self.assertEqual(report['missing_generated_count'],3)
        self.assertFalse(report['stability_control_separate']['recovery_success'])
        self.assertFalse(report['scientific_pose_recovery_validated'])
        self.assertEqual(report['molecular_calls'],0)

    def test_admission_thresholds_never_relax_for_low_rmsd(self):
        changes={'force':lambda x:x['forces_kcal_per_mol_angstrom'][0].__setitem__(0,.00101),
                 'strain':lambda x:x.__setitem__('final_internal_energy_kcal_per_mol',15.00001),
                 'geometry':lambda x:x['geometry_checks'].__setitem__(r.CHECKS[3],False),
                 'score_tie':lambda x:x.__setitem__('final_dimensionless_score',2.),
                 'energy':lambda x:x['numerical_audit'].__setitem__('maximum_energy_error_kcal_per_mol',1.00001e-8),
                 'numeric_force':lambda x:x['numerical_audit'].__setitem__('maximum_force_component_error_kcal_per_mol_angstrom',1.00001e-8),
                 'bond':lambda x:x['coordinates_angstrom'][0].__setitem__(0,x['coordinates_angstrom'][0][0]+.5)}
        for name,change in changes.items():
            with self.subTest(name=name):
                result=self.result();change(result);report=self.evaluate([result])
                self.assertFalse(report['generated_cases']['perturbed_01']['admitted'])
                self.assertEqual(report['recovery_success_count'],0)

    def test_preflight_rejection_remains_in_denominator_and_zero_work(self):
        result=self.result();result['status']='preflight_rejected'
        result['coordinates_angstrom']=None;result['forces_kcal_per_mol_angstrom']=None
        result['work']=dict.fromkeys(result['work'],0)
        report=self.evaluate([result]);self.assertEqual(report['recovery_denominator'],4)
        self.assertEqual(report['generated_cases']['perturbed_01']['status'],'preflight_rejected')
        self.assertEqual(report['recovery_success_count'],0)

    def test_unreviewed_or_stale_or_after_execution_review_rejected(self):
        mutations={'no_review':('reviewed_before_execution',False),'hash':('protocol_sha256','0'*64),
                   'manifest':('manifest_sha256','0'*64),'time':('reviewed_at','2026-10-02T00:00:00+00:00')}
        for name,(key,value) in mutations.items():
            with self.subTest(name=name):
                original=deepcopy(self.review);self.review[key]=value
                with self.assertRaises(r.ProtocolError):self.evaluate([self.result()])
                self.review=original

    def test_result_binding_state_and_budget_failures(self):
        mutations={'start':lambda x:x.__setitem__('input_coordinates_sha256','0'*64),
                   'state':lambda x:x.__setitem__('chemistry_sha256','0'*64),
                   'receptor':lambda x:x.__setitem__('original_input_hashes',{}),
                   'best_state':lambda x:x.__setitem__('endpoint_policy','best_score_state'),
                   'force_cap':lambda x:x['work'].__setitem__('objective_attempts',418),
                   'score_cap':lambda x:x['work'].__setitem__('score_calls',3),
                   'restart':lambda x:x['work'].__setitem__('restart_force_calls',3),
                   'AI':lambda x:x['work'].__setitem__('AI_inference_calls',1),
                   'pending':lambda x:x['work'].__setitem__('unknown_pending_attempts',None),
                   'missing_geometry':lambda x:x['geometry_checks'].pop(r.CHECKS[0]),
                   'missing_receipts':lambda x:x.__setitem__('actual_receipt_refs',[])}
        for name,change in mutations.items():
            with self.subTest(name=name):
                result=self.result();change(result)
                with self.assertRaises(r.ProtocolError):self.evaluate([result])

    def test_duplicate_or_undeclared_case_rejected(self):
        result=self.result()
        with self.assertRaisesRegex(r.ProtocolError,'duplicate'):self.evaluate([result,result])
        result['case_id']='extra_05'
        with self.assertRaisesRegex(r.ProtocolError,'undeclared'):self.evaluate([result])

    def test_undeclared_rights_rejected(self):
        original=deepcopy(r.AUTHORITY)
        submission={'schema_id':'sro_saved_recovery_results/1','protocol_sha256':r.value_hash(self.protocol),
                    'authority':original,'case_results':[]}
        submission['authority']['training_admitted']=True
        with self.assertRaisesRegex(r.ProtocolError,'rights'):r.evaluate_saved_results(self.packet,submission,self.review)

    def test_calculation_input_reference_leak_rejected_even_after_resealing(self):
        name='calculation_inputs/input_contract.json';data=json.loads((self.packet/name).read_text())
        data['source_ligand_or_provenance_or_evaluation_reference_path']='evaluation_only/reference.json'
        (self.packet/name).write_bytes(r.encoded(data));self.rehash_packet(name)
        with self.assertRaisesRegex(r.ProtocolError,'reference_leak'):r.verify_packet(self.packet)

    def test_perturbation_or_reference_mutation_rejected_even_after_resealing(self):
        name='calculation_inputs/candidates.json';data=json.loads((self.packet/name).read_text())
        data['cases'][0]['coordinates_angstrom'][0][0]+=0.1
        (self.packet/name).write_bytes(r.encoded(data));self.rehash_packet(name)
        with self.assertRaisesRegex(r.ProtocolError,'transform_changed'):r.verify_packet(self.packet)

    def test_original_input_mutation_rejected(self):
        (self.root/'parameters.json').write_bytes(b'{}')
        with self.assertRaisesRegex(r.ProtocolError,'input_hash'):r.verify_packet(self.packet)

    def test_create_only_generation_preserves_existing_packet(self):
        before=(self.packet/'manifest.json').read_bytes()
        with self.assertRaises(FileExistsError):r.generate_packet(self.evidence,self.packet)
        self.assertEqual(before,(self.packet/'manifest.json').read_bytes())

    def test_reference_symmetry_and_gate_changes_rejected_after_resealing(self):
        for kind in ('reference','symmetry','gate'):
            with self.subTest(kind=kind):
                name='protocol.json' if kind=='gate' else 'evaluation_only/reference.json'
                original=(self.packet/name).read_bytes()
                manifest=(self.packet/'manifest.json').read_bytes()
                value=json.loads(original)
                if kind=='reference':value['coordinates_angstrom'][0][0]+=.1
                elif kind=='symmetry':value['allowed_symmetry_mappings'].append(list(reversed(range(13))))
                else:value['admission']['maximum_internal_energy_increase_kcal_per_mol']=50
                (self.packet/name).write_bytes(r.encoded(value));self.rehash_packet(name)
                with self.assertRaises(r.ProtocolError):r.verify_packet(self.packet)
                (self.packet/name).write_bytes(original);(self.packet/'manifest.json').write_bytes(manifest)

    def test_force_uses_atom_vector_norm(self):
        result=self.result();result['forces_kcal_per_mol_angstrom'][0]=[.0008,.0008,0.]
        report=self.evaluate([result]);self.assertFalse(report['generated_cases']['perturbed_01']['gates']['raw_force'])

    def test_no_cases_after_fatal_stop_or_out_of_declared_order(self):
        failed=self.result();failed['status']='watchdog'
        with self.assertRaisesRegex(r.ProtocolError,'fatal_stop'):self.evaluate([failed,self.result('perturbed_02')])
        with self.assertRaisesRegex(r.ProtocolError,'order'):self.evaluate([self.result('perturbed_02'),self.result()])

    def test_atom_state_metadata_leak_and_removed_atoms_rejected(self):
        for kind in ('atom_count','state','leak'):
            with self.subTest(kind=kind):
                chem=deepcopy(self.chem)
                if kind=='atom_count':chem['atoms'].pop()
                elif kind=='state':chem['atoms'][12]['formal_charge']=0
                else:chem['atoms'][0]['source_coordinates_angstrom']=[0,0,0]
                with self.assertRaises(r.ProtocolError):r.validate_chemistry(chem)

    def test_retained_control_can_replay_without_becoming_recovery(self):
        control=self.result('observed_start_control');control['status']='retained_control'
        control['started_at']='2026-09-30T00:00:00+00:00'
        report=self.evaluate([control]);self.assertEqual(report['recovery_success_count'],0)
        self.assertEqual(report['stability_control_separate']['status'],'retained_control')
        generated=self.result();generated['status']='retained_control'
        with self.assertRaises(r.ProtocolError):self.evaluate([generated])

    def test_imports_are_stdlib_and_no_molecular_runner(self):
        import ast
        tree=ast.parse(MODULE.read_text())
        imports=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):imports.extend(n.name.split('.')[0] for n in node.names)
            if isinstance(node,ast.ImportFrom):imports.append(node.module.split('.')[0])
        self.assertFalse(set(imports)&{'torch','numpy','openmm','rdkit','betelgeuze_product','betelgeuze_engine_v2','subprocess'})

if __name__=='__main__':
    unittest.main()
