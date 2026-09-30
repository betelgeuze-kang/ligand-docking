"""Prospective SRO coordinate generation and saved-result evaluation, stdlib only.

This module has no molecular evaluator, optimizer, scorer, or execution command.
The packet is a development predeclaration pending independent freeze review.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

FRAME = '7XTB_original_cartesian_angstrom_development'
EVIDENCE_SHA = 'fc26972806d25bf249cfbc6635098ab5b53af73315887d202af5c966aa422286'
INPUT_HASHES = {
    'ligand': 'aee0cdee35491fc44998a14c69c5e888b2de5e6c0c85b35bfedfb0562832445c',
    'parameters': '16d3b25e6492ae8500771d60d6fe5b5db12089b8c7fa64d3f25a6f1230fad217',
    'extensions': '871c1a252c87c0b4f134c8b572f009f99658fea88f1076c9ee3fe1461a0871f6',
    'cross_parameters': '226cb9f4be87b40d312e4b3bdb0dbc785bd6d6e87daa68e2f6abec76dde22d52',
    'receptor': '2c0970bcaf9e994f382e0f0c0fdacbfd1359bef60a10b879f757b31628658c4c',
}
STATE = {'formal_charge_site': 'NZ', 'formal_charge_e': 1, 'formula': 'C10H13N2O+',
         'atom_count': 26, 'heavy_atom_count': 13, 'hydrogen_count': 13,
         'terminal_amine_hydrogen_count': 3, 'indole_NH_retained': True, 'phenol_OH_retained': True,
         'selection': 'single_predeclared_computational_assumption',
         'experimentally_measured_bound_protonation': None, 'assay_chemical_state': None}
AUTHORITY = {'known_reserved_source_development_only': True, 'existing_source_role_unchanged': True,
             'new_source_rights_admitted': False, 'training_admitted': False, 'calibration_admitted': False,
             'independent_evaluation_admitted': False, 'independent_recovery_claim_allowed': False,
             'experimental_labels_used': False, 'protected_evaluation_used': False,
             'scientifically_validated': False, 'product_qualified': False, 'HIP_qualified': False}
CHECKS = ['bond_lengths_preserved', 'declared_chirality_preserved',
          'element_vdw_ligand_overlap_free', 'element_vdw_receptor_overlap_free',
          'inside_declared_pocket', 'ligand_self_clash_free', 'proper_rotation', 'receptor_ligand_clash_free']
SPECS = [
    {'case_id': 'perturbed_01', 'seed': 2026093001, 'translation_direction': [1, 0, 0], 'translation_angstrom': 2.5,
     'rotation_axis': [0, 0, 1], 'rotation_degrees': 0.0},
    {'case_id': 'perturbed_02', 'seed': 2026093002, 'translation_direction': [0, -1, 0], 'translation_angstrom': 2.5,
     'rotation_axis': [1, 0, 0], 'rotation_degrees': 0.0},
    {'case_id': 'perturbed_03', 'seed': 2026093003, 'translation_direction': [0, 0, 1], 'translation_angstrom': 2.5,
     'rotation_axis': [0, 0, 1], 'rotation_degrees': 25.0},
    {'case_id': 'perturbed_04', 'seed': 2026093004, 'translation_direction': [-1, -1, 0], 'translation_angstrom': 2.5,
     'rotation_axis': [1, 1, 1], 'rotation_degrees': -25.0},
]
ATOM_KEYS = ['index', 'name', 'element', 'atomic_number', 'formal_charge', 'isotope_mass_number',
             'aromatic', 'stereo', 'partial_charge_e', 'mass_da']
BOND_KEYS = ['atom_i', 'atom_j', 'order', 'aromatic', 'stereo']

class ProtocolError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise ProtocolError(message)

def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def value_hash(value):
    return digest(encoded(value))

def reference(path):
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    return {'path': str(path), 'sha256': digest(raw), 'bytes': len(raw)}

def read_bound(pin):
    raw = Path(pin['path']).read_bytes()
    require(digest(raw) == pin['sha256'] and len(raw) == pin['bytes'], 'input_hash_mismatch')
    return json.loads(raw)

def publish(path, value):
    with Path(path).open('xb') as stream:
        stream.write(encoded(value))

def decode(value):
    if isinstance(value, dict):
        if set(value) == {'$float_hex'}:
            result = float.fromhex(value['$float_hex'])
            require(math.isfinite(result), 'nonfinite_canonical_number')
            return result
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value

def coordinates(value, count):
    require(isinstance(value, list) and len(value) == count, 'coordinate_atom_count')
    for row in value:
        require(isinstance(row, list) and len(row) == 3, 'coordinate_shape')
        require(all(type(v) in (int, float) and math.isfinite(v) for v in row), 'nonfinite_coordinate')
    return [[float(v) for v in row] for row in value]

def canonical_coordinates(system):
    block = decode(system['coordinates']['coordinates'])['$tensor']
    require(block['dtype'] == 'float64' and block['shape'] == [1, 26, 3], 'canonical_coordinate_contract')
    require(system['coordinates']['coordinate_unit'] == 'angstrom', 'coordinate_units')
    require(len(block['values']) == 78, 'canonical_coordinate_count')
    return coordinates([block['values'][i:i+3] for i in range(0, 78, 3)], 26)

def unit(vector):
    require(len(vector) == 3 and all(type(v) in (int, float) and math.isfinite(v) for v in vector), 'direction_shape')
    norm = math.sqrt(math.fsum(v*v for v in vector))
    require(norm > 0, 'zero_direction')
    return [v/norm for v in vector]

def rigid_transform(xyz, spec, pivot):
    """Rodrigues rotation at the declared pivot followed by declared translation.

    Seeds identify cases and future solver determinism; generation uses explicit
    directions/angles, with no RNG draw or rejection/resampling.
    """
    require(type(spec['seed']) is int, 'seed_required')
    require(spec['translation_angstrom'] > 0 and math.isfinite(spec['translation_angstrom']), 'nonzero_translation_required')
    direction, axis = unit(spec['translation_direction']), unit(spec['rotation_axis'])
    angle = math.radians(spec['rotation_degrees'])
    require(math.isfinite(angle), 'rotation_angle')
    c, s = math.cos(angle), math.sin(angle)
    result = []
    for point in xyz:
        q = [point[i]-pivot[i] for i in range(3)]
        dot = math.fsum(axis[i]*q[i] for i in range(3))
        cross = [axis[1]*q[2]-axis[2]*q[1], axis[2]*q[0]-axis[0]*q[2], axis[0]*q[1]-axis[1]*q[0]]
        result.append([pivot[i]+q[i]*c+cross[i]*s+axis[i]*dot*(1-c)+direction[i]*spec['translation_angstrom'] for i in range(3)])
    return coordinates(result, len(xyz))

def chemistry_projection(system):
    topology = decode(system['topology'])
    atoms = [{key: row[key] for key in ATOM_KEYS} for row in topology['atoms']]
    bonds = [{key: row[key] for key in BOND_KEYS} for row in topology['bonds']]
    return {'schema_id': 'sro_coordinate_free_chemistry/1', 'atoms': atoms, 'bonds': bonds,
            'computational_microstate': deepcopy(STATE), 'coordinate_frame_id': FRAME}

def validate_chemistry(chemistry):
    require(set(chemistry) == {'schema_id', 'atoms', 'bonds', 'computational_microstate', 'coordinate_frame_id'}, 'chemistry_fields_or_reference_leak')
    require(chemistry['schema_id'] == 'sro_coordinate_free_chemistry/1' and chemistry['coordinate_frame_id'] == FRAME, 'chemistry_schema_frame')
    require(chemistry['computational_microstate'] == STATE, 'unsupported_state')
    atoms = chemistry['atoms']
    require(len(atoms) == 26 and [a['index'] for a in atoms] == list(range(26)), 'undeclared_atom_count_or_order')
    require(all(set(a) == set(ATOM_KEYS) for a in atoms), 'atom_fields_or_reference_leak')
    require(len({a['name'] for a in atoms}) == 26, 'duplicate_atom_name')
    require(Counter(a['element'] for a in atoms) == {'C': 10, 'H': 13, 'N': 2, 'O': 1}, 'undeclared_elements')
    require(all(type(a['formal_charge']) is int and a['formal_charge'] == (1 if a['name'] == 'NZ' else 0) for a in atoms), 'undeclared_formal_state')
    require(all(type(a['atomic_number']) is int and a['atomic_number'] == {'C':6,'H':1,'N':7,'O':8}[a['element']] and a['isotope_mass_number'] is None for a in atoms), 'unsupported_atom_or_isotope')
    require(all(type(a['partial_charge_e']) in (int,float) and math.isfinite(a['partial_charge_e']) and type(a['mass_da']) in (int,float) and math.isfinite(a['mass_da']) and a['mass_da'] > 0 for a in atoms), 'nonfinite_charge_or_mass')
    require(abs(math.fsum(a['partial_charge_e'] for a in atoms)-1) < 1e-10, 'partial_charge_state')
    require(all(a['element'] != 'H' for a in atoms[:13]) and all(a['element'] == 'H' for a in atoms[13:]), 'heavy_atom_order')
    require(len(chemistry['bonds']) == 27, 'undeclared_bonds')
    seen = set()
    for bond in chemistry['bonds']:
        require(set(bond) == set(BOND_KEYS), 'bond_fields_or_reference_leak')
        i, j = bond['atom_i'], bond['atom_j']
        require(type(i) is int and type(j) is int and 0 <= i < j < 26, 'bond_atom_mapping')
        require((i, j) not in seen and bond['order'] in (1, 2, 3), 'duplicate_or_unsupported_bond')
        seen.add((i, j))
    return chemistry

def automorphisms(chemistry):
    """Enumerate heavy graph symmetries, independent of source atom names/xyz.

    Aromatic edges share one label irrespective of Kekule order. Vertex labels
    preserve element, formal charge, isotope, aromatic flag, explicit H count,
    and stereo. Nonaromatic order and bond stereo are preserved. Charges/masses
    remain bound chemistry and do not silently restrict chemical symmetry.
    """
    atoms, bonds = chemistry['atoms'], chemistry['bonds']
    heavy = [a['index'] for a in atoms if a['element'] != 'H']
    require(len(heavy) <= 20, 'symmetry_size_unsupported')
    hydrogen_counts = Counter()
    edges = {}
    for b in bonds:
        i, j = b['atom_i'], b['atom_j']
        if i in heavy and j in heavy:
            label = ('aromatic' if b['aromatic'] else b['order'], b['stereo'])
            edges[i, j] = edges[j, i] = label
        elif i in heavy:
            hydrogen_counts[i] += 1
        elif j in heavy:
            hydrogen_counts[j] += 1
    colors = {i: (atoms[i]['element'], atoms[i]['formal_charge'], atoms[i]['isotope_mass_number'],
                  atoms[i]['aromatic'], atoms[i]['stereo'], hydrogen_counts[i],
                  sum((i, j) in edges for j in heavy)) for i in heavy}
    targets = {i: [j for j in heavy if colors[i] == colors[j]] for i in heavy}
    order = sorted(heavy, key=lambda i: (len(targets[i]), i))
    output = []
    def visit(mapping, used):
        if len(mapping) == len(heavy):
            output.append([mapping[i] for i in heavy])
            require(len(output) <= 4096, 'symmetry_count_unsupported')
            return
        i = order[len(mapping)]
        for j in targets[i]:
            if j in used or any(edges.get((i, k)) != edges.get((j, l)) for k, l in mapping.items()):
                continue
            visit({**mapping, i: j}, used | {j})
    visit({}, set())
    require(output, 'no_symmetry_mapping')
    return sorted(output)

def receptor_frame_rmsd(xyz, reference_xyz, heavy_indices, mappings):
    xyz = coordinates(xyz, len(xyz))
    reference_xyz = coordinates(reference_xyz, len(heavy_indices))
    require(mappings and all(sorted(m) == sorted(heavy_indices) for m in mappings), 'invalid_symmetry_mapping')
    direct = math.sqrt(math.fsum((xyz[i][a]-reference_xyz[k][a])**2 for k, i in enumerate(heavy_indices) for a in range(3))/len(heavy_indices))
    values = [math.sqrt(math.fsum((xyz[i][a]-reference_xyz[k][a])**2 for k, i in enumerate(mapping) for a in range(3))/len(heavy_indices)) for mapping in mappings]
    best = min(range(len(values)), key=lambda i: (values[i], mappings[i]))
    return {'direct_heavy_rmsd_angstrom': direct, 'symmetry_heavy_rmsd_angstrom': values[best],
            'minimum_mapping': mappings[best], 'translation_or_rotation_fit': False}

def protocol_definition(pins, chemistry_sha, evaluator_sha, pocket, solver):
    return {'schema_id': 'sro_pose_recovery_predeclaration/1', 'status': 'PROSPECTIVE_PENDING_ROOT_FREEZE_REVIEW',
            'authority': deepcopy(AUTHORITY), 'coordinate_frame_id': FRAME, 'computational_microstate': deepcopy(STATE),
            'original_five_prepared_input_hashes': {k: pins[k]['sha256'] for k in INPUT_HASHES},
            'coordinate_free_chemistry_sha256': chemistry_sha, 'generator_evaluator_source_sha256': evaluator_sha,
            'perturbations': deepcopy(SPECS), 'perturbation_count': 4,
            'pivot_policy': 'prepared_13_heavy_atom_centroid; generation_only; absent_from_calculation_inputs',
            'seed_policy': 'case_identifiers_and_solver_seeds; no_rng_draws_or_rejection_resampling',
            'transform_policy': 'proper_rigid_body_all_26_atoms; no_internal_or_state_change',
            'control': {'case_id': 'observed_start_control', 'role': 'stability_control_only', 'seed': 2026093000,
                        'recovery_denominator_member': False, 'zero_perturbation': True,
                        'retained_same_input_control_replay_allowed': True},
            'execution_order': [s['case_id'] for s in SPECS] + ['observed_start_control'],
            'arm': 'native_cartesian_lbfgs', 'AI_arm_included': False,
            'future_runtime': {'wheel_sha256': '00814229724d90cca5b81d00c2a78a4ae6dfe983e95930552ca693d2c13484b8',
                               'reference_free_runtime_adapter_status': 'NOT_IMPLEMENTED_NOT_AUTHORIZED_TO_EXECUTE'},
            'budget': {'candidate_count': 4, 'control_count_separate': 1, 'one_start_per_case': True,
                       'objective_attempts_per_case': 417, 'accepted_steps_per_case': 416,
                       'restart_verification_force_calls_per_case_separate': 2, 'score_calls_per_case': 2,
                       'endpoint_oracle_states_per_case_separate': 2, 'wall_timeout_per_case_seconds': 7200,
                       'unstarted_failed_rejected_cases_remain_in_denominator': True,
                       'retry_or_replacement_or_best_trajectory_selection': False},
            'solver': solver, 'pocket': pocket,
            'admission': {'maximum_raw_atom_force_kcal_per_mol_angstrom': 0.001,
                          'maximum_internal_energy_increase_kcal_per_mol': 5.0,
                          'maximum_bond_change_angstrom': 0.15, 'required_geometry_checks': CHECKS,
                          'all_checks_complete_and_true': True, 'strict_dimensionless_score_improvement': True,
                          'last_accepted_state_only': True, 'same_math_energy_tolerance_kcal_per_mol': 1e-8,
                          'same_math_force_component_tolerance_kcal_per_mol_angstrom': 1e-8},
            'recovery': {'metric': 'minimum_over_declared_heavy_graph_automorphisms_receptor_frame_no_fit',
                         'minimum_initial_rmsd_angstrom': 2.25, 'maximum_final_rmsd_angstrom': 2.0,
                         'minimum_rmsd_improvement_angstrom': 0.5,
                         'success_requires_refined_admission': True, 'known_start_counts_as_recovery': False,
                         'threshold_role': 'predeclared_development_error_target_not_experimental_accuracy'},
            'reference_access': {'reference_file_role': 'evaluation_only', 'reference_allowed_for_generation': True,
                                 'reference_allowed_for_force_score_optimizer_or_AI_selection': False,
                                 'original_ligand_and_provenance_paths_allowed_for_runtime': False,
                                 'observed_control_allowed_in_generated_candidate_pool': False},
            'accounting': 'report_AI_inference_force_score_restart_oracle_and_enclosing_cost_scopes_separately; never_sum_nested_timings',
            'failure_policy': 'fatal_or_watchdog_stops_campaign_no_retry; retain_every_case_missing_work_unknown',
            'molecular_calls_performed_by_this_tool': 0}

def generate_packet(evidence_path, output):
    """Read only preparation/identity artifacts; never read historical endpoints."""
    evidence_path, output = Path(evidence_path).resolve(), Path(output)
    require(digest(evidence_path.read_bytes()) == EVIDENCE_SHA, 'installed_evidence_identity')
    evidence = json.loads(evidence_path.read_bytes())
    pins = deepcopy(evidence['prepared_inputs'])
    require(set(pins) == set(INPUT_HASHES), 'prepared_input_set')
    for name, pin in pins.items():
        require(pin['sha256'] == INPUT_HASHES[name], 'prepared_input_identity')
        read_bound(pin)
    prepared = Path(pins['ligand']['path']).parent
    manifest_pin = reference(prepared/'manifest.v1.json')
    manifest = read_bound(manifest_pin)
    additional = {}
    for name in ('protocol.json', 'atom-provenance.json', 'source-graph.json'):
        pin = {**manifest['files'][name], 'path': str(prepared/name)}
        additional[name] = pin
    prep_protocol, provenance, source_graph = [read_bound(additional[n]) for n in ('protocol.json', 'atom-provenance.json', 'source-graph.json')]
    require(prep_protocol['computational_microstate'] == manifest['computational_microstate'] == STATE, 'unsupported_state')
    require(prep_protocol['authority'] == manifest['scientific_authority'] and prep_protocol['authority']['reserved_source_role_unchanged'] is True, 'source_authority_binding')
    require(all(v is False for k, v in prep_protocol['authority'].items() if k not in ('numerical_development_only','reserved_source_role_unchanged')), 'unsupported_source_rights')
    ligand = read_bound(pins['ligand'])['system']
    xyz = canonical_coordinates(ligand)
    chemistry = validate_chemistry(chemistry_projection(ligand))
    mappings = automorphisms(chemistry)
    observed = source_graph['observed_atoms']
    require(len(observed) == 13 and len(provenance['atoms']) == 26, 'source_atom_count')
    source_map = []
    reference_xyz = []
    for i, row in enumerate(observed):
        atom, original = provenance['atoms'][i], chemistry['atoms'][i]
        require(atom['name'] == row['label_atom_id'] == original['name'] and atom['source_atom_site_id'] == row['id'], 'source_heavy_mapping')
        source_xyz = [float(row['Cartn_'+a]) for a in 'xyz']
        require(xyz[i] == atom['coordinates_angstrom'] == source_xyz, 'source_heavy_coordinate_binding')
        require(atom['origin'] == 'observed_source_heavy' and row['occupancy'] == '1.00' and row['label_alt_id'] == '.', 'source_observation_unsupported')
        source_map.append({'canonical_index': i, 'name': original['name'], 'element': original['element'], 'source_atom_site_id': row['id']})
        reference_xyz.append(source_xyz)
    request = read_bound(evidence['request'])
    require(request['solver']['force_tolerance'] == 0.001 and request['solver']['max_objective_attempts'] == 417, 'retained_solver_gates')
    require(read_bound(pins['cross_parameters'])['max_internal_increase_kcal_per_mol'] == 5.0, 'retained_strain_gate')
    source_sha = digest(Path(__file__).read_bytes())
    protocol = protocol_definition(pins, value_hash(chemistry), source_sha, request['pocket'], request['solver'])
    pivot = [math.fsum(p[a] for p in xyz[:13])/13 for a in range(3)]
    cases = [{'case_id': s['case_id'], 'role': 'generated_perturbation', 'seed': s['seed'],
              'coordinate_frame_id': FRAME, 'coordinates_angstrom': rigid_transform(xyz, s, pivot)} for s in SPECS]
    control = {'case_id': 'observed_start_control', 'role': 'stability_control_only', 'seed': 2026093000,
               'coordinate_frame_id': FRAME, 'coordinates_angstrom': xyz}
    evaluation_reference = {'schema_id': 'sro_evaluation_reference/1', 'role': 'evaluation_only', 'coordinate_frame_id': FRAME,
        'heavy_atom_map': source_map, 'coordinates_angstrom': reference_xyz, 'allowed_symmetry_mappings': mappings,
        'symmetry_definition': 'graph_elements_formal_charge_isotope_aromatic_stereo_explicitH_and_bond_order; aromatic_Kekule_normalized',
        'source_uncertainty': 'reserved_3.3_angstrom_cryoEM_model_occupancy1_no_altloc; no_per_atom_ground_truth; bound_protonation_unknown',
        'independent_or_heldout_reference': False}
    metrics = {c['case_id']: receptor_frame_rmsd(c['coordinates_angstrom'], reference_xyz, list(range(13)), mappings) for c in cases+[control]}
    require(all(metrics[c['case_id']]['symmetry_heavy_rmsd_angstrom'] >= 2.25 for c in cases), 'perturbation_below_predeclared_minimum')
    output.mkdir(parents=True, exist_ok=False)
    (output/'calculation_inputs').mkdir()
    (output/'evaluation_only').mkdir()
    (output/'stability_control').mkdir()
    publish(output/'protocol.json', protocol)
    publish(output/'calculation_inputs/chemistry.json', chemistry)
    publish(output/'calculation_inputs/candidates.json', {'schema_id': 'sro_perturbed_candidate_pool/1', 'cases': cases})
    publish(output/'calculation_inputs/input_contract.json', {
        'schema_id': 'sro_reference_free_calculation_contract/1', 'coordinate_frame_id': FRAME,
        'chemistry_sha256': value_hash(chemistry), 'candidate_pool_sha256': value_hash({'schema_id': 'sro_perturbed_candidate_pool/1', 'cases': cases}),
        'parameter_refs': {k: pins[k] for k in ('parameters','extensions','cross_parameters','receptor')},
        'original_prepared_ligand_sha256_identity_only': pins['ligand']['sha256'],
        'solver': request['solver'], 'pocket': request['pocket'],
        'source_ligand_or_provenance_or_evaluation_reference_path': None,
        'runtime_adapter_status': 'NOT_IMPLEMENTED_NOT_AUTHORIZED_TO_EXECUTE'})
    publish(output/'stability_control/candidate.json', control)
    publish(output/'evaluation_only/reference.json', evaluation_reference)
    publish(output/'evaluation_only/initial_metrics.json', {'schema_id': 'sro_initial_coordinate_metrics/1', 'cases': metrics,
            'scope': 'coordinate_arithmetic_only_no_results_observed'})
    publish(output/'lineage.json', {'installed_identity_evidence': reference(evidence_path), 'five_original_inputs': pins,
                                  'preparation_manifest': manifest_pin, 'preparation_sources': additional,
                                  'retained_request': evidence['request'], 'historical_results_read': False})
    publish(output/'freeze_status.json', {'schema_id': 'sro_prospective_freeze_status/1', 'root_review': 'PENDING',
                                       'execution_authorized': False, 'observed_recovery_results': 0,
                                       'force_score_native_graph_optimizer_OpenMM_calls': 0})
    with (output/'generator_evaluator_source.py').open('xb') as stream:
        stream.write(Path(__file__).read_bytes())
    files = {p.relative_to(output).as_posix(): {'sha256': digest(p.read_bytes()), 'bytes': len(p.read_bytes())}
             for p in sorted(output.rglob('*')) if p.is_file()}
    manifest = {'schema_id': 'sro_prospective_packet_manifest/1', 'files': files,
                'protocol_sha256': files['protocol.json']['sha256'], 'status': 'PROSPECTIVE_NOT_EXECUTED'}
    publish(output/'manifest.json', manifest)
    verify_packet(output)
    return manifest

def verify_packet(packet):
    packet = Path(packet).resolve()
    manifest = json.loads((packet/'manifest.json').read_bytes())
    require(manifest['schema_id'] == 'sro_prospective_packet_manifest/1' and manifest['status'] == 'PROSPECTIVE_NOT_EXECUTED', 'packet_status')
    files = manifest['files']
    require({p.relative_to(packet).as_posix() for p in packet.rglob('*') if p.is_file()} == set(files)|{'manifest.json'}, 'packet_extra_or_missing_file')
    for name, pin in files.items():
        path = packet/name
        require(path.resolve().is_relative_to(packet) and not path.is_symlink(), 'packet_symlink_or_escape')
        require(digest(path.read_bytes()) == pin['sha256'] and len(path.read_bytes()) == pin['bytes'], 'packet_file_hash_mismatch')
    require(manifest['protocol_sha256'] == files['protocol.json']['sha256'], 'manifest_protocol_binding')
    protocol = json.loads((packet/'protocol.json').read_bytes())
    require(protocol['authority'] == AUTHORITY, 'unsupported_source_rights')
    require(protocol['perturbations'] == SPECS and protocol['perturbation_count'] == 4 and protocol['computational_microstate'] == STATE, 'changed_perturbations_or_state')
    chemistry = validate_chemistry(json.loads((packet/'calculation_inputs/chemistry.json').read_bytes()))
    require(value_hash(chemistry) == protocol['coordinate_free_chemistry_sha256'], 'chemistry_binding')
    reference_payload = json.loads((packet/'evaluation_only/reference.json').read_bytes())
    require(reference_payload['role'] == 'evaluation_only' and reference_payload['coordinate_frame_id'] == FRAME, 'reference_role')
    require(reference_payload['allowed_symmetry_mappings'] == automorphisms(chemistry), 'undeclared_symmetry')
    pool = json.loads((packet/'calculation_inputs/candidates.json').read_bytes())
    require(set(pool) == {'schema_id','cases'} and pool['schema_id'] == 'sro_perturbed_candidate_pool/1', 'candidate_pool_fields')
    require([c['case_id'] for c in pool['cases']] == [s['case_id'] for s in SPECS], 'candidate_count_or_order')
    for c, s in zip(pool['cases'], SPECS):
        require(set(c) == {'case_id','role','seed','coordinate_frame_id','coordinates_angstrom'}, 'candidate_fields_or_reference_leak')
        require(c['role'] == 'generated_perturbation' and c['seed'] == s['seed'] and c['coordinate_frame_id'] == FRAME, 'candidate_identity')
        coordinates(c['coordinates_angstrom'], 26)
    lineage = json.loads((packet/'lineage.json').read_bytes())
    for k, pin in lineage['five_original_inputs'].items():
        require(pin['sha256'] == INPUT_HASHES[k], 'original_hash_changed')
        read_bound(pin)
    read_bound(lineage['preparation_manifest'])
    for pin in lineage['preparation_sources'].values():
        read_bound(pin)
    read_bound(lineage['installed_identity_evidence'])
    request = read_bound(lineage['retained_request'])
    source_sha = digest((packet/'generator_evaluator_source.py').read_bytes())
    require(source_sha == digest(Path(__file__).read_bytes()), 'generator_evaluator_bytes_changed')
    expected_protocol = protocol_definition(lineage['five_original_inputs'], value_hash(chemistry), source_sha,
                                            request['pocket'], request['solver'])
    require(protocol == expected_protocol, 'protocol_definition_changed')
    original_system = read_bound(lineage['five_original_inputs']['ligand'])['system']
    require(chemistry == chemistry_projection(original_system), 'prepared_chemistry_projection_changed')
    original_xyz = canonical_coordinates(original_system)
    pivot = [math.fsum(p[a] for p in original_xyz[:13])/13 for a in range(3)]
    for candidate, spec in zip(pool['cases'], SPECS):
        require(candidate['coordinates_angstrom'] == rigid_transform(original_xyz, spec, pivot), 'candidate_transform_changed')
    control = json.loads((packet/'stability_control/candidate.json').read_bytes())
    require(control == {'case_id': 'observed_start_control', 'role': 'stability_control_only', 'seed': 2026093000,
                        'coordinate_frame_id': FRAME, 'coordinates_angstrom': original_xyz}, 'control_changed_or_mixed')
    source_graph = read_bound(lineage['preparation_sources']['source-graph.json'])
    observed = source_graph['observed_atoms']
    expected_map = [{'canonical_index': i, 'name': row['label_atom_id'], 'element': row['type_symbol'],
                     'source_atom_site_id': row['id']} for i, row in enumerate(observed)]
    require(reference_payload['heavy_atom_map'] == expected_map and reference_payload['coordinates_angstrom'] == original_xyz[:13],
            'evaluation_reference_mapping_or_coordinates_changed')
    contract = json.loads((packet/'calculation_inputs/input_contract.json').read_bytes())
    expected_contract = {
        'schema_id': 'sro_reference_free_calculation_contract/1', 'coordinate_frame_id': FRAME,
        'chemistry_sha256': value_hash(chemistry), 'candidate_pool_sha256': value_hash(pool),
        'parameter_refs': {k: lineage['five_original_inputs'][k] for k in ('parameters','extensions','cross_parameters','receptor')},
        'original_prepared_ligand_sha256_identity_only': lineage['five_original_inputs']['ligand']['sha256'],
        'solver': request['solver'], 'pocket': request['pocket'],
        'source_ligand_or_provenance_or_evaluation_reference_path': None,
        'runtime_adapter_status': 'NOT_IMPLEMENTED_NOT_AUTHORIZED_TO_EXECUTE'}
    require(contract == expected_contract, 'calculation_contract_changed_or_reference_leak')
    initial = json.loads((packet/'evaluation_only/initial_metrics.json').read_bytes())
    expected_metrics = {c['case_id']: receptor_frame_rmsd(c['coordinates_angstrom'], reference_payload['coordinates_angstrom'], list(range(13)), reference_payload['allowed_symmetry_mappings']) for c in pool['cases']+[control]}
    require(initial == {'schema_id': 'sro_initial_coordinate_metrics/1', 'cases': expected_metrics, 'scope': 'coordinate_arithmetic_only_no_results_observed'}, 'initial_metrics_changed')
    require(json.loads((packet/'freeze_status.json').read_bytes()) == {'schema_id': 'sro_prospective_freeze_status/1', 'root_review': 'PENDING', 'execution_authorized': False, 'observed_recovery_results': 0, 'force_score_native_graph_optimizer_OpenMM_calls': 0}, 'prospective_status_changed')
    return {'passed': True, 'protocol_sha256': manifest['protocol_sha256'], 'manifest_sha256': digest((packet/'manifest.json').read_bytes()),
            'generated_perturbations': 4, 'stability_controls_separate': 1, 'molecular_calls': 0}

def review_binding(packet, review):
    verified = verify_packet(packet)
    require(set(review) == {'schema_id','protocol_sha256','manifest_sha256','reviewed_before_execution','reviewed_at','reviewer','execution_scope'}, 'review_fields')
    require(review['schema_id'] == 'sro_recovery_freeze_review/1' and review['reviewed_before_execution'] is True, 'preexecution_review_required')
    require(review['protocol_sha256'] == verified['protocol_sha256'] and review['manifest_sha256'] == verified['manifest_sha256'], 'review_hash_mismatch')
    require(review['execution_scope'] == 'separately_authorized_future_execution' and review['reviewer'], 'review_authority_missing')
    moment = datetime.fromisoformat(review['reviewed_at'])
    require(moment.utcoffset() is not None, 'review_timezone_required')
    return moment

def evaluate_saved_results(packet, submitted, review):
    """Calculate metrics from a strictly bound future saved-result export.

    Saved molecular receipts are assertions here, not independently verified
    force/oracle execution. This tool never grants scientific/source admission.
    """
    packet = Path(packet)
    reviewed = review_binding(packet, review)
    protocol = json.loads((packet/'protocol.json').read_bytes())
    require(set(submitted) == {'schema_id','protocol_sha256','authority','case_results'}, 'result_fields')
    require(submitted['schema_id'] == 'sro_saved_recovery_results/1' and submitted['authority'] == AUTHORITY, 'unsupported_result_role_or_rights')
    require(submitted['protocol_sha256'] == value_hash(protocol), 'result_protocol_binding')
    chemistry = json.loads((packet/'calculation_inputs/chemistry.json').read_bytes())
    ref = json.loads((packet/'evaluation_only/reference.json').read_bytes())
    candidates = json.loads((packet/'calculation_inputs/candidates.json').read_bytes())['cases']
    candidates += [json.loads((packet/'stability_control/candidate.json').read_bytes())]
    by_id = {c['case_id']: c for c in candidates}
    rows = {}
    submitted_order = [v['case_id'] for v in submitted['case_results']]
    require(all(k in by_id for k in submitted_order), 'undeclared_case')
    expected_order = protocol['execution_order']
    require(submitted_order == [k for k in expected_order if k in submitted_order], 'execution_order_or_duplicate_changed')
    fatal_seen = False
    required = {'case_id','status','started_at','input_coordinates_sha256','chemistry_sha256','original_input_hashes',
                'endpoint_policy','coordinates_angstrom','forces_kcal_per_mol_angstrom','initial_internal_energy_kcal_per_mol',
                'final_internal_energy_kcal_per_mol','baseline_dimensionless_score','final_dimensionless_score',
                'geometry_complete','geometry_checks','numerical_audit','work','actual_receipt_refs'}
    for result in submitted['case_results']:
        retained_control = result['case_id'] == 'observed_start_control' and result['status'] == 'retained_control'
        require(not fatal_seen or retained_control, 'execution_after_fatal_stop')
        require(set(result) == required, 'result_case_fields')
        case_id = result['case_id']
        require(case_id in by_id and case_id not in rows, 'undeclared_or_duplicate_case')
        candidate = by_id[case_id]
        started = datetime.fromisoformat(result['started_at'])
        require(started.utcoffset() is not None and (started > reviewed or retained_control), 'result_precedes_freeze_review')
        require(result['input_coordinates_sha256'] == value_hash(candidate['coordinates_angstrom']), 'result_wrong_start')
        require(result['chemistry_sha256'] == protocol['coordinate_free_chemistry_sha256'] and result['original_input_hashes'] == INPUT_HASHES, 'result_state_or_receptor_changed')
        require(result['endpoint_policy'] == 'last_accepted_state', 'retrospective_best_state_forbidden')
        require(result['status'] in ('completed','failed','watchdog','preflight_rejected','retained_control'), 'result_status')
        require(result['status'] != 'retained_control' or retained_control, 'retained_generated_case_forbidden')
        for pin in result['actual_receipt_refs']:
            read_bound(pin)
        require(result['actual_receipt_refs'], 'saved_receipts_required')
        work = result['work']
        work_keys = {'objective_attempts','initial_successful_objectives','accepted_steps','rejected_attempts','failed_attempts','unknown_pending_attempts',
                     'restart_force_calls','score_calls','oracle_states','AI_inference_calls','proposal_calls'}
        require(set(work) == work_keys and all(v is None or (type(v) is int and v >= 0) for v in work.values()), 'work_accounting_shape')
        require(all(work[k] is not None for k in ('objective_attempts','initial_successful_objectives','accepted_steps','rejected_attempts','failed_attempts')), 'known_attempt_counts_required')
        require(work['objective_attempts'] <= 417 and work['accepted_steps'] <= 416, 'objective_budget_exceeded')
        require(work['restart_force_calls'] is not None and work['restart_force_calls'] <= 2 and work['score_calls'] is not None and work['score_calls'] <= 2, 'separate_budget_exceeded')
        require(work['oracle_states'] is None or work['oracle_states'] <= 2, 'oracle_state_budget_exceeded')
        require(work['AI_inference_calls'] == work['proposal_calls'] == 0, 'undeclared_AI_or_proposals')
        require(work['initial_successful_objectives'] in (0,1), 'initial_objective_accounting')
        known = work['initial_successful_objectives']+work['accepted_steps']+work['rejected_attempts']+work['failed_attempts']
        require(work['objective_attempts'] >= known if work['unknown_pending_attempts'] is None else work['objective_attempts'] == known+work['unknown_pending_attempts'], 'attempt_accounting_incomplete')
        initial = receptor_frame_rmsd(candidate['coordinates_angstrom'], ref['coordinates_angstrom'], list(range(13)), ref['allowed_symmetry_mappings'])
        if result['status'] not in ('completed','retained_control'):
            fatal_seen = result['status'] in ('failed','watchdog')
            rows[case_id] = {'status': result['status'], 'admitted': False, 'recovery_success': False, 'initial': initial, 'final': None, 'work': work}
            continue
        require(work['initial_successful_objectives'] == 1 and work['unknown_pending_attempts'] == 0 and work['score_calls'] == 2 and work['oracle_states'] == 2, 'completed_work_incomplete')
        xyz = coordinates(result['coordinates_angstrom'], 26)
        forces = coordinates(result['forces_kcal_per_mol_angstrom'], 26)
        force = max(math.sqrt(math.fsum(v*v for v in f)) for f in forces)
        scalars = ['initial_internal_energy_kcal_per_mol','final_internal_energy_kcal_per_mol','baseline_dimensionless_score','final_dimensionless_score']
        require(all(type(result[k]) in (int,float) and math.isfinite(result[k]) for k in scalars), 'nonfinite_result_quantity')
        require(type(result['geometry_complete']) is bool and set(result['geometry_checks']) == set(CHECKS)
                and all(type(v) is bool for v in result['geometry_checks'].values()), 'geometry_checks_missing_or_undeclared')
        audit = result['numerical_audit']
        require(set(audit) == {'endpoint_count','maximum_energy_error_kcal_per_mol','maximum_force_component_error_kcal_per_mol_angstrom'}, 'numerical_audit_fields')
        require(audit['endpoint_count'] == 2 and all(type(audit[k]) in (int,float) and math.isfinite(audit[k]) and audit[k] >= 0 for k in audit if k != 'endpoint_count'), 'numerical_audit_incomplete')
        bond_delta = max(abs(math.dist(xyz[b['atom_i']], xyz[b['atom_j']])-math.dist(candidate['coordinates_angstrom'][b['atom_i']], candidate['coordinates_angstrom'][b['atom_j']])) for b in chemistry['bonds'])
        gates = {'raw_force': force <= .001,
                 'strain': result['final_internal_energy_kcal_per_mol']-result['initial_internal_energy_kcal_per_mol'] <= 5,
                 'bond_change': bond_delta <= .15,
                 'geometry': result['geometry_complete'] and all(result['geometry_checks'].values()),
                 'same_math_energy': audit['maximum_energy_error_kcal_per_mol'] <= 1e-8,
                 'same_math_force': audit['maximum_force_component_error_kcal_per_mol_angstrom'] <= 1e-8,
                 'ordering_score': result['final_dimensionless_score'] < result['baseline_dimensionless_score']}
        final = receptor_frame_rmsd(xyz, ref['coordinates_angstrom'], list(range(13)), ref['allowed_symmetry_mappings'])
        admitted = all(gates.values())
        improvement = initial['symmetry_heavy_rmsd_angstrom']-final['symmetry_heavy_rmsd_angstrom']
        success = candidate['role'] == 'generated_perturbation' and admitted and initial['symmetry_heavy_rmsd_angstrom'] >= 2.25 and final['symmetry_heavy_rmsd_angstrom'] <= 2.0 and improvement >= .5
        rows[case_id] = {'status': result['status'], 'admitted': admitted, 'gates': gates, 'maximum_raw_atom_force': force,
                        'maximum_bond_change_angstrom': bond_delta, 'initial': initial, 'final': final,
                        'rmsd_improvement_angstrom': improvement, 'recovery_success': success, 'work': work}
    for case_id in by_id:
        if case_id not in rows:
            rows[case_id] = {'status': 'not_observed', 'admitted': False, 'recovery_success': False, 'work': None}
    generated = [rows[s['case_id']] for s in SPECS]
    return {'schema_id': 'sro_saved_recovery_coordinate_evaluation/1', 'protocol_sha256': value_hash(protocol),
            'evidence_scope': 'coordinate_arithmetic_and_saved_assertions; runtime_receipts_not_independently_authenticated',
            'authority': AUTHORITY, 'recovery_denominator': 4, 'recovery_success_count': sum(r['recovery_success'] for r in generated),
            'missing_generated_count': sum(r['status'] == 'not_observed' for r in generated),
            'generated_cases': {s['case_id']: rows[s['case_id']] for s in SPECS},
            'stability_control_separate': rows['observed_start_control'], 'molecular_calls': 0,
            'scientific_pose_recovery_validated': False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    generate = commands.add_parser('generate')
    generate.add_argument('--evidence', type=Path, required=True)
    generate.add_argument('--output', type=Path, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('--packet', type=Path, required=True)
    evaluate = commands.add_parser('evaluate-saved')
    evaluate.add_argument('--packet', type=Path, required=True)
    evaluate.add_argument('--results', type=Path, required=True)
    evaluate.add_argument('--freeze-review', type=Path, required=True)
    evaluate.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'generate':
        result = generate_packet(args.evidence, args.output)
    elif args.command == 'verify':
        result = verify_packet(args.packet)
    else:
        result = evaluate_saved_results(args.packet, json.loads(args.results.read_bytes()), json.loads(args.freeze_review.read_bytes()))
        publish(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))

if __name__ == '__main__':
    main()
