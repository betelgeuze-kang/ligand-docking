"""Prepare one explicitly computational PR49/7XTB numerical-development input.

No experimental endpoint, protected outcome or learned score is consumed.
The source serotonin centroid locates the pocket, not a PR49 reference pose.
Run with the pinned external OpenFF runtime and PYTHONPATH set to the checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np

BASE = Path('/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs')
RECEPTOR = BASE / 'engine-v2-7xtb-openmm-projection-20260929'
LIGANDS = BASE / 'engine-v2-5ht6-pr49-pr59-openff-projection-20260929'
SOURCE = BASE / 'engine-v2-7xtb-source-observation-20260929T031420Z/7XTB.cif'
DEFAULT_OUTPUT = BASE / 'engine-v2-pr49-d3-complex-20260929-final2'
SOURCE_SHA = 'e81b271ee863340c0e1e65101be7695849bdd56f408c887b03b89929cc4e9cb7'
RECEPTOR_MANIFEST_SHA = 'a761368e162a3ce5b502702d9ba689451386e0dd424619da371df8e4d0a16f12'
LIGAND_MANIFEST_SHA = '4f1d9740814e5d8c9fe4429567fa50e23e1d04bdf40dfebe981cc84a0775fc1c'
FF_SHA = '1b24deb47970bae2d179a5b4e023d4a57c9c78614fe431f1670e3f75e0012c3a'
RADII = {'H': 1.20, 'C': 1.70, 'N': 1.55, 'O': 1.52, 'S': 1.80, 'Cl': 1.75}
PROTOCOL = {
    'schema_version': 'pr49_7xtb_geometry_only_initial_pose_protocol_v3',
    'case_selection': 'PR49 selected for bounded numerical development only; no fair assay contrast',
    'anchor': 'centroid of 13 public 7XTB model1 labelF SRO501 heavy atoms',
    'orientation': '24 proper signed permutation matrices, identity first then lexicographic',
    'offsets_angstrom': [-4, -2, 0, 2, 4],
    'offset_maximum_norm_angstrom': 5.0,
    'order': 'offset squared norm, lexicographic offset, orientation index; first passing candidate',
    'pocket_all_heavy_maximum_radius_angstrom': 10.0,
    'all_atom_minimum_distance_angstrom': 1.0,
    'heavy_atom_minimum_distance_angstrom': 2.0,
    'all_atom_minimum_radius_sum_ratio': 0.60,
    'heavy_atom_minimum_radius_sum_ratio': 0.72,
    'radius_table_angstrom': RADII,
    'collision_scope': 'explicit severe-overlap thresholds; not universal physical validity',
    'ligand_coordinate_quantization_angstrom': 0.0001,
    'energy_force_or_assay_used_for_pose_selection': False,
    'reference_PR49_pose_available': False,
    'fallback_after_exhausted_discrete_grid': {
        'method': 'scipy differential_evolution of geometric threshold deficits only',
        'seed': 20260929, 'workers': 1, 'maxiter': 1000, 'popsize': 12,
        'translation_bounds_angstrom': [-4, 4], 'rotation_vector_component_bounds_radian': [-3.141592653589793, 3.141592653589793],
        'mutation': 0.8, 'recombination': 0.7, 'polish': False,
        'termination': 'first exactly printed-coordinate threshold pass or fixed budget exhaustion',
        'thresholds_unchanged_after_discrete_failure': True,
    },
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def write(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)


def ref(path):
    path = path.resolve(strict=True)
    return {'path': str(path), 'sha256': sha(path.read_bytes()), 'source_id': path.name}


def checked_manifest(root, expected, row=None):
    raw = (root / 'manifest.v1.json').read_bytes()
    if sha(raw) != expected:
        raise ValueError('SOURCE_PREPARATION_MANIFEST_HASH_MISMATCH')
    value = json.loads(raw)
    files = value['files'] if row is None else value['rows'][row]['files']
    folder = root if row is None else root / row
    for name, identity in files.items():
        data = (folder / name).read_bytes()
        if sha(data) != identity['sha256'] or len(data) != identity['bytes']:
            raise ValueError('SOURCE_PREPARATION_ARTIFACT_HASH_MISMATCH:' + name)
    return value


def proper_rotations():
    matrices = []
    for permutation in itertools.permutations(range(3)):
        for signs in itertools.product((-1, 1), repeat=3):
            matrix = np.zeros((3, 3), dtype=float)
            for i, j in enumerate(permutation):
                matrix[i, j] = signs[i]
            if round(np.linalg.det(matrix)) == 1:
                matrices.append(matrix)
    matrices.sort(key=lambda matrix: (not np.array_equal(matrix, np.eye(3)), tuple(matrix.flat)))
    return matrices


def rigid_transform(coordinates, matrix, translation):
    matrix = np.asarray(matrix, dtype=float)
    translation = np.asarray(translation, dtype=float)
    if (matrix.shape != (3, 3) or translation.shape != (3,)
            or not np.isfinite(matrix).all() or not np.isfinite(translation).all()
            or not np.allclose(matrix.T @ matrix, np.eye(3), atol=1e-12, rtol=0)
            or abs(np.linalg.det(matrix) - 1) > 1e-12):
        raise ValueError('INVALID_PROPER_RIGID_TRANSFORM')
    return np.asarray(coordinates) @ matrix.T + translation


def geometry_metrics(receptor, receptor_elements, ligand, ligand_elements, center, trees=None):
    receptor = np.asarray(receptor); ligand = np.asarray(ligand)
    heavy_r = np.array([e != 'H' for e in receptor_elements])
    heavy_l = np.array([e != 'H' for e in ligand_elements])
    if trees is not None:
        minima = [[], [], [], []]
        ligand_radii = np.array([RADII[element] for element in ligand_elements])
        for element, tree in trees.items():
            distances = tree.query(ligand, workers=1)[0]
            ratios = distances / (ligand_radii + RADII[element])
            minima[0].append(float(distances.min())); minima[2].append(float(ratios.min()))
            if element != 'H':
                minima[1].append(float(distances[heavy_l].min())); minima[3].append(float(ratios[heavy_l].min()))
        return {'minimum_all_atom_distance_angstrom': min(minima[0]),
            'minimum_heavy_atom_distance_angstrom': min(minima[1]),
            'minimum_all_atom_radius_sum_ratio': min(minima[2]),
            'minimum_heavy_atom_radius_sum_ratio': min(minima[3]),
            'maximum_ligand_heavy_radius_angstrom': float(np.linalg.norm(ligand[heavy_l]-center, axis=1).max()),
            'receptor_atoms_checked': len(receptor), 'ligand_atoms_checked': len(ligand)}
    distances = np.linalg.norm(ligand[:, None, :] - receptor[None, :, :], axis=2)
    radii = np.array([RADII[e] for e in ligand_elements])[:, None] + np.array(
        [RADII[e] for e in receptor_elements])[None, :]
    heavy = np.ix_(heavy_l, heavy_r)
    return {
        'minimum_all_atom_distance_angstrom': float(distances.min()),
        'minimum_heavy_atom_distance_angstrom': float(distances[heavy].min()),
        'minimum_all_atom_radius_sum_ratio': float((distances / radii).min()),
        'minimum_heavy_atom_radius_sum_ratio': float((distances / radii)[heavy].min()),
        'maximum_ligand_heavy_radius_angstrom': float(np.linalg.norm(ligand[heavy_l] - center, axis=1).max()),
        'receptor_atoms_checked': len(receptor), 'ligand_atoms_checked': len(ligand),
    }


def accepted(metrics):
    return (metrics['minimum_all_atom_distance_angstrom'] >= PROTOCOL['all_atom_minimum_distance_angstrom']
            and metrics['minimum_heavy_atom_distance_angstrom'] >= PROTOCOL['heavy_atom_minimum_distance_angstrom']
            and metrics['minimum_all_atom_radius_sum_ratio'] >= PROTOCOL['all_atom_minimum_radius_sum_ratio']
            and metrics['minimum_heavy_atom_radius_sum_ratio'] >= PROTOCOL['heavy_atom_minimum_radius_sum_ratio']
            and metrics['maximum_ligand_heavy_radius_angstrom'] <= PROTOCOL['pocket_all_heavy_maximum_radius_angstrom'])


def pocket_anchor(source):
    from betelgeuze_engine_v2.molecular.mmcif_syntax import parse_cif_block
    raw = source.read_bytes()
    if sha(raw) != SOURCE_SHA:
        raise ValueError('SOURCE_7XTB_HASH_MISMATCH')
    block = parse_cif_block(raw.decode('ascii'))
    rows = []
    for loop in block.loops:
        if '_atom_site' not in loop.categories:
            continue
        for tokens in loop.rows:
            row = {key: token.value for key, token in zip(loop.tags, tokens)}
            if row['_atom_site.label_asym_id'] == 'F':
                if (row['_atom_site.label_comp_id'] != 'SRO' or row['_atom_site.auth_seq_id'] != '501'
                        or row['_atom_site.pdbx_pdb_model_num'] != '1' or row['_atom_site.type_symbol'] == 'H'):
                    raise ValueError('SOURCE_ANCHOR_SELECTION_MISMATCH')
                rows.append({'atom_site_id': row['_atom_site.id'], 'atom_name': row['_atom_site.label_atom_id'],
                             'xyz_angstrom': [float(row['_atom_site.cartn_' + axis]) for axis in 'xyz']})
    if len(rows) != 13:
        raise ValueError('SOURCE_ANCHOR_ATOM_COUNT_MISMATCH')
    return np.mean([row['xyz_angstrom'] for row in rows], axis=0), rows


def choose_pose(receptor, receptor_elements, ligand, ligand_elements, center):
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation
    from scipy.optimize import differential_evolution
    heavy_l = np.array([element != 'H' for element in ligand_elements])
    origin = ligand[heavy_l].mean(axis=0)
    trees = {element: cKDTree(receptor[np.array(receptor_elements) == element]) for element in sorted(set(receptor_elements))}
    offsets = [values for values in itertools.product(PROTOCOL['offsets_angstrom'], repeat=3)
               if sum(x*x for x in values) <= PROTOCOL['offset_maximum_norm_angstrom'] ** 2]
    offsets.sort(key=lambda values: (sum(x*x for x in values), values))
    attempts = []
    class FoundPose(Exception):
        pass
    selected = None
    def attempt(matrix, offset, stage, rotation_index=None):
        nonlocal selected
        translation = center + np.array(offset) - matrix @ origin
        exact = rigid_transform(ligand, matrix, translation)
        printed = np.round(exact, 4)
        metrics = geometry_metrics(receptor, receptor_elements, printed, ligand_elements, center, trees)
        offset_violation = max(0.0, float(np.linalg.norm(offset))-PROTOCOL['offset_maximum_norm_angstrom'])
        passed = accepted(metrics) and offset_violation == 0
        attempts.append({'ordinal': len(attempts), 'stage': stage, 'offset_angstrom': list(map(float, offset)),
                         'rotation_index': rotation_index, 'rotation_matrix': matrix.tolist(),
                         'accepted': passed, 'offset_norm_violation_angstrom': offset_violation, **metrics})
        if passed:
            direct = geometry_metrics(receptor, receptor_elements, printed, ligand_elements, center)
            if any(abs(direct[key]-metrics[key]) > 1e-12 for key in direct):
                raise ValueError('TREE_AND_EXPLICIT_ALL_PAIR_GEOMETRY_DIFFER')
            before = np.linalg.norm(ligand[:, None]-ligand[None, :], axis=2)
            after = np.linalg.norm(printed[:, None]-printed[None, :], axis=2)
            drift = float(np.abs(before-after).max())
            if drift > 0.00018:
                raise ValueError('RIGID_DISTANCE_INVARIANCE_FAILED_AFTER_QUANTIZATION')
            selected = printed, {'rotation_matrix': matrix.tolist(), 'translation_angstrom': translation.tolist(),
                'source_heavy_centroid_angstrom': origin.tolist(), 'target_heavy_centroid_angstrom': printed[heavy_l].mean(axis=0).tolist(),
                'all_pair_distance_maximum_change_angstrom': drift,
                'exact_transform_maximum_rounding_error_angstrom': float(np.abs(exact-printed).max()),
                'attempts': attempts, 'selected_ordinal': len(attempts)-1, 'selection': 'first_threshold_pass_without_physical_scoring',
                'all_receptor_atoms_explicitly_rechecked_for_selected_pose': True}
            raise FoundPose
        deficits = [max(0.0, PROTOCOL[p]-metrics[m]) for p, m in (
            ('all_atom_minimum_distance_angstrom', 'minimum_all_atom_distance_angstrom'),
            ('heavy_atom_minimum_distance_angstrom', 'minimum_heavy_atom_distance_angstrom'),
            ('all_atom_minimum_radius_sum_ratio', 'minimum_all_atom_radius_sum_ratio'),
            ('heavy_atom_minimum_radius_sum_ratio', 'minimum_heavy_atom_radius_sum_ratio'))]
        deficits += [offset_violation, max(0.0, metrics['maximum_ligand_heavy_radius_angstrom']-PROTOCOL['pocket_all_heavy_maximum_radius_angstrom'])]
        return sum(value*value for value in deficits)
    try:
        for offset in offsets:
            for rotation_index, matrix in enumerate(proper_rotations()):
                attempt(matrix, offset, 'discrete_grid', rotation_index)
        settings = PROTOCOL['fallback_after_exhausted_discrete_grid']
        differential_evolution(lambda v: attempt(Rotation.from_rotvec(v[3:]).as_matrix(), v[:3], 'continuous_geometry'),
            [(-4,4)]*3+[(-np.pi,np.pi)]*3, seed=settings['seed'], workers=1,
            maxiter=settings['maxiter'], popsize=settings['popsize'], mutation=settings['mutation'],
            recombination=settings['recombination'], polish=False, tol=0, atol=0)
    except FoundPose:
        return selected
    error = ValueError('NO_INITIAL_POSE_PASSES_FROZEN_GEOMETRY_PROTOCOL')
    error.geometry_attempts = attempts
    raise error


def reparameterize_unconstrained(ligand_path, output):
    from rdkit import Chem
    from openff.toolkit import ForceField, Molecule, Topology
    from openff.interchange import Interchange
    from openff.units import unit as off_unit
    from openmm import NonbondedForce, XmlSerializer, unit
    import openforcefields
    ff_path = Path(openforcefields.__file__).parent / 'offxml/openff-2.2.1.offxml'
    if sha(ff_path.read_bytes()) != FF_SHA:
        raise ValueError('OPENFF_FORCEFIELD_HASH_MISMATCH')
    original_xml = (ligand_path / 'openmm-system.xml').read_text()
    original = XmlSerializer.deserialize(original_xml)
    if original.getNumConstraints() != 14:
        raise ValueError('ORIGINAL_CONSTRAINT_INVENTORY_CHANGED')
    old_nb = next(force for force in original.getForces() if isinstance(force, NonbondedForce))
    mol = Chem.SDMolSupplier(str(ligand_path / 'ligand.sdf'), removeHs=False)[0]
    if mol is None:
        raise ValueError('SOURCE_LIGAND_SDF_INVALID')
    molecule = Molecule.from_rdkit(mol, hydrogens_are_explicit=True)
    charges = [old_nb.getParticleParameters(i)[0].value_in_unit(unit.elementary_charge) for i in range(molecule.n_atoms)]
    molecule.partial_charges = np.array(charges) * off_unit.elementary_charge
    ff = ForceField(str(ff_path))
    ff.deregister_parameter_handler('Constraints')
    system = Interchange.from_smirnoff(ff, Topology.from_molecules([molecule]), charge_from_molecules=[molecule]).to_openmm(combine_nonbonded_forces=True)
    if system.getNumConstraints() != 0:
        raise ValueError('UNCONSTRAINED_SYSTEM_STILL_HAS_CONSTRAINTS')
    new_xml = XmlSerializer.serialize(system)
    old_root, new_root = ET.fromstring(original_xml), ET.fromstring(new_xml)
    old_forces = {force.attrib['type']: force for force in old_root.find('Forces')}
    new_forces = {force.attrib['type']: force for force in new_root.find('Forces')}
    if set(old_forces) != set(new_forces):
        raise ValueError('UNEXPECTED_FORCE_CLASS_CHANGE')
    unchanged = []
    for name in old_forces:
        if name == 'HarmonicBondForce':
            continue
        if ET.tostring(old_forces[name]) != ET.tostring(new_forces[name]):
            raise ValueError('UNEXPECTED_FORCE_PARAMETER_CHANGE:' + name)
        unchanged.append(name)
    old_bonds = {tuple(sorted((int(row.attrib['p1']), int(row.attrib['p2'])))): dict(row.attrib)
                 for row in old_forces['HarmonicBondForce'].find('Bonds')}
    new_bonds = {tuple(sorted((int(row.attrib['p1']), int(row.attrib['p2'])))): dict(row.attrib)
                 for row in new_forces['HarmonicBondForce'].find('Bonds')}
    if any(new_bonds.get(pair) != row for pair, row in old_bonds.items()):
        raise ValueError('PREEXISTING_BONDED_PARAMETER_CHANGED')
    added = sorted(set(new_bonds)-set(old_bonds))
    constrained = sorted(tuple(sorted(map(int, original.getConstraintParameters(i)[:2]))) for i in range(original.getNumConstraints()))
    if added != constrained:
        raise ValueError('REMOVED_CONSTRAINT_AND_ADDED_HARMONIC_BOND_PAIRS_DIFFER')
    if ET.tostring(old_root.find('Particles')) != ET.tostring(new_root.find('Particles')):
        raise ValueError('PARTICLE_MASSES_OR_ORDER_CHANGED')
    write(output / 'ligand-unconstrained-openmm-system.xml', new_xml.encode())
    write(output / 'unconstrained-forcefield.offxml', ff.to_string().encode())
    receipt = {'original_system': ref(ligand_path / 'openmm-system.xml'),
        'new_system': ref(output / 'ligand-unconstrained-openmm-system.xml'),
        'original_constraint_count': original.getNumConstraints(), 'new_constraint_count': 0,
        'original_system_D3_admission_required': 'REJECT_UNSUPPORTED_CONSTRAINTS; original never silently stripped',
        'original_system_D3_admission_executed_by_this_preparer': False,
        'new_state': 'explicit separate unconstrained computational model; no constrained-dynamics equivalence claimed',
        'forcefield_source_sha256': FF_SHA, 'forcefield_without_constraints': ref(output / 'unconstrained-forcefield.offxml'),
        'charges': 'exact original serialized NAGL predicted AM1-BCC-like charges reused; no charge refit',
        'unchanged_serialized_force_classes': sorted(unchanged),
        'old_harmonic_bond_count': len(old_bonds), 'new_harmonic_bond_count': len(new_bonds),
        'new_harmonic_bond_pairs_zero_based': [list(pair) for pair in added],
        'new_harmonic_bonds': [new_bonds[pair] for pair in added],
        'atom_order_element_sequence_unchanged': True, 'particle_masses_unchanged': True}
    write(output / 'parameterization-difference.json', encoded(receipt))
    return receipt


def prepared_request(output):
    ligand = LIGANDS / 'PR49'
    return {'schema_version': 'prepared_gromacs_components_v1',
        'protein_pdb': ref(RECEPTOR / 'receptor-prepared.pdb'),
        'protein_chains': [{'chain_id': chain, 'molecule_itp': ref(RECEPTOR / f'receptor-{chain}.itp')} for chain in ('A', 'B')],
        'protein_atomtypes': ref(RECEPTOR / 'atomtypes.itp'), 'protein_defaults': ref(RECEPTOR / 'defaults.itp'),
        'ligand_sdf': ref(output / 'ligand-registered.sdf'), 'ligand_gro': ref(output / 'ligand-registered.gro'),
        'ligand_itp': ref(ligand / 'ligand.itp'), 'ligand_atomtypes': ref(ligand / 'atomtypes.itp'),
        'ligand_defaults': ref(ligand / 'defaults.itp'), 'ligand_atomtype_name_mapping': {},
        'ligand_residue_name_mapping': {'itp': 'PR49', 'gro': 'PR49'}, 'naming_convention': 'exact',
        'pdb_element_policy': 'reject_missing',
        'source_declarations': {'coordinate_frame_id': '7XTB_original_cartesian_angstrom_development',
            'prepared_state_id': 'PR49_neutral_unconstrained_geometry_registered_development_v1',
            'parameter_source_id': 'amber14_receptor_OpenFF221_unconstrained_ligand',
            'charge_source_id': 'amber14_receptor_original_NAGL1_ligand'},
        'source_relationship': 'independent components; computational ligand rigid placement verified by separate registration receipt; no observed PR49 pose'}


def build(output):
    from rdkit import Chem
    from betelgeuze_engine.product.prepared_gromacs_input import load_prepared_gromacs_components
    from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes, canonical_system_sha256
    start = time.perf_counter()
    checked_manifest(RECEPTOR, RECEPTOR_MANIFEST_SHA)
    checked_manifest(LIGANDS, LIGAND_MANIFEST_SHA, 'PR49')
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'prepare-complex-source.py', Path(__file__).read_bytes())
    write(output / 'geometry-protocol.json', encoded(PROTOCOL))
    ligand_path = LIGANDS / 'PR49'
    center, source_rows = pocket_anchor(SOURCE)
    receptor_rows = [line for line in (RECEPTOR / 'receptor-prepared.pdb').read_text().splitlines() if line.startswith(('ATOM  ', 'HETATM'))]
    receptor_xyz = np.array([[float(row[a:b]) for a, b in ((30,38),(38,46),(46,54))] for row in receptor_rows])
    receptor_elements = [row[76:78].strip() for row in receptor_rows]
    mol = Chem.SDMolSupplier(str(ligand_path / 'ligand.sdf'), removeHs=False)[0]
    if mol is None or len(receptor_rows) != 4376 or mol.GetNumAtoms() != 39:
        raise ValueError('SOURCE_PREPARATION_ATOM_COUNTS_CHANGED')
    ligand_xyz = np.array(mol.GetConformer().GetPositions())
    ligand_elements = [atom.GetSymbol() for atom in mol.GetAtoms()]
    geometry_start = time.perf_counter()
    try:
        registered, geometry = choose_pose(receptor_xyz, receptor_elements, ligand_xyz, ligand_elements, center)
    except ValueError as error:
        write(output / 'preparation-failure.json', encoded({'error': str(error), 'geometry_attempts': getattr(error, 'geometry_attempts', []),
            'wall_seconds': time.perf_counter()-geometry_start, 'protocol': ref(output / 'geometry-protocol.json')}))
        raise
    geometry['search_wall_seconds'] = time.perf_counter()-geometry_start
    geometry['pocket_center_angstrom'] = center.tolist()
    geometry['public_source_anchor_rows'] = source_rows
    geometry['protocol'] = ref(output / 'geometry-protocol.json')
    geometry['source'] = ref(SOURCE)
    geometry['ligand_source'] = ref(ligand_path / 'ligand.sdf')
    geometry['source_atom_mapping'] = [{'prepared_index_zero_based': i, 'source_index_zero_based': i, 'element': element} for i, element in enumerate(ligand_elements)]
    geometry['physical_binding_pose_or_pose_recovery_claimed'] = False
    geometry['upstream_coordinate_registration_verified'] = True
    write(output / 'registration.json', encoded(geometry))
    sdf = (ligand_path / 'ligand.sdf').read_bytes().splitlines(keepends=True)
    gro = (ligand_path / 'ligand.gro').read_bytes().splitlines(keepends=True)
    for i, xyz in enumerate(registered):
        sdf[i+4] = ''.join(f'{x:10.4f}' for x in xyz).encode()+sdf[i+4][30:]
        ending = b'\r\n' if gro[i+2].endswith(b'\r\n') else b'\n'
        gro[i+2] = gro[i+2][:20] + ''.join(f'{x/10:15.10f}' for x in xyz).encode()+ending
    write(output / 'ligand-registered.sdf', b''.join(sdf))
    write(output / 'ligand-registered.gro', b''.join(gro))
    parameterization = reparameterize_unconstrained(ligand_path, output)
    request = json.loads(encoded(prepared_request(output)))
    write(output / 'prepared-input.json', encoded(request))
    reader_start = time.perf_counter()
    receptor, ligand, receptor_parameters, ligand_parameters, evidence = load_prepared_gromacs_components(request)
    reader_seconds = time.perf_counter()-reader_start
    if ligand.coordinates[0].tolist() != registered.tolist() or receptor.coordinates[0].tolist() != receptor_xyz.tolist():
        raise ValueError('ACTUAL_READER_COORDINATE_ROUNDTRIP_MISMATCH')
    write(output / 'receptor-canonical.json', canonical_system_json_bytes(receptor))
    write(output / 'ligand-canonical.json', canonical_system_json_bytes(ligand))
    write(output / 'cross-parameters.json', encoded({'receptor': receptor_parameters, 'ligand': ligand_parameters}))
    write(output / 'reader-evidence.json', encoded(evidence))
    report = {'schema_version': 'pr49_7xtb_computational_complex_preparation_v1',
        'status': 'DEVELOPMENT_INPUT_PREPARED_NOT_SCIENTIFICALLY_QUALIFIED',
        'source_manifest_sha256': {'receptor': RECEPTOR_MANIFEST_SHA, 'ligand': LIGAND_MANIFEST_SHA},
        'receptor_atoms': receptor.atom_count, 'ligand_atoms': ligand.atom_count,
        'receptor_system_sha256': canonical_system_sha256(receptor), 'ligand_system_sha256': canonical_system_sha256(ligand),
        'registration': ref(output / 'registration.json'), 'parameterization_difference': ref(output / 'parameterization-difference.json'),
        'prepared_input': ref(output / 'prepared-input.json'),
        'implementation': ref(output / 'prepare-complex-source.py'), 'reader_wall_seconds': reader_seconds,
        'runtime_versions': {'python': sys.version, 'numpy': np.__version__,
            'scipy': __import__('scipy').__version__, 'rdkit': __import__('rdkit').__version__},
        'whole_preparation_wall_seconds': time.perf_counter()-start,
        'scientific_authority': {'observed_PR49_pose': False, 'redocking_reference': False,
            'assay_state_equivalence': False, 'affinity_or_ranking_validation': False,
            'fit_calibration_or_evaluation_admission': False, 'protected_outcomes_read': False},
        'original_constraints_preserved_and_require_D3_rejection': parameterization['original_constraint_count'] == 14,
        'files': {path.name: {'sha256': sha(path.read_bytes()), 'bytes': path.stat().st_size} for path in sorted(output.iterdir())}}
    write(output / 'manifest.v1.json', encoded(report))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build(args.output.resolve())
    print(json.dumps({'output': str(args.output.resolve()), 'status': result['status'],
                      'receptor_atoms': result['receptor_atoms'], 'ligand_atoms': result['ligand_atoms']}, sort_keys=True))
