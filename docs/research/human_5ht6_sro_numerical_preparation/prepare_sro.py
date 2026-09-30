"""Prepare one source-bound SRO numerical-development case, without evaluation.

The declared NZ+1 state is an assumption. Only hydrogen coordinates are created.
Use the already retained OpenFF runtime; this program never downloads models.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[3]
BASE = Path('/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs')
SOURCE = BASE / 'engine-v2-7xtb-source-observation-20260929T031420Z/7XTB.cif'
SOURCE_SHA = 'e81b271ee863340c0e1e65101be7695849bdd56f408c887b03b89929cc4e9cb7'
RECEPTOR = BASE / 'engine-v2-7xtb-openmm-projection-20260929'
RECEPTOR_MANIFEST_SHA = 'a761368e162a3ce5b502702d9ba689451386e0dd424619da371df8e4d0a16f12'
RECEPTOR_CHEMICAL = BASE / 'engine-v2-7xtb-chemical-graph-20260929-final1'
RECEPTOR_CANONICAL_SHA = '2c0970bcaf9e994f382e0f0c0fdacbfd1359bef60a10b879f757b31628658c4c'
DEFAULT_OUTPUT = BASE / 'engine-v2-sro-numerical-preparation-20260929-v1'
FF_NAME = 'openff-2.2.1.offxml'
FF_SHA = '1b24deb47970bae2d179a5b4e023d4a57c9c78614fe431f1670e3f75e0012c3a'
MODEL_NAME = 'openff-gnn-am1bcc-1.0.0.pt'
MODEL_SHA = '7981e7f5b0b1e424c9e10a40d9e7606d96dcd3dd2b095cb4eeff6829f92238ee'
FRAME = '7XTB_original_cartesian_angstrom_development'
STATE = {'formal_charge_site': 'NZ', 'formal_charge_e': 1,
         'formula': 'C10H13N2O+', 'atom_count': 26, 'heavy_atom_count': 13,
         'hydrogen_count': 13, 'terminal_amine_hydrogen_count': 3,
         'indole_NH_retained': True, 'phenol_OH_retained': True,
         'selection': 'single_predeclared_computational_assumption',
         'experimentally_measured_bound_protonation': None,
         'assay_chemical_state': None}
PROTOCOL = {
    'schema_id': 'human_5ht6_sro_predeclaration/1.0.0',
    'computational_microstate': STATE,
    'source': {'pdb_id': '7XTB', 'component_id': 'SRO', 'model': '1',
               'label_asym_id': 'F', 'entity_id': '6', 'auth_asym_id': 'R',
               'auth_seq_id': '501', 'deposited_em_buffer_pH': '7.4',
               'atom_site_formal_charge_token': '?', 'component_atom_charge_column_present': False,
               'pH_determines_observed_microstate': False},
    'coordinate_frame_id': FRAME,
    'heavy_coordinates': 'all 13 source decimal coordinates unchanged; no rigid placement or centering',
    'generated_hydrogens_method': 'RDKit Chem.AddHs(addCoords=True); no embedding or optimization; quantize H only to 0.0001 angstrom',
    'generated_hydrogen_names': 'retain 12 CCD hydrogen names and add HNZ3 on NZ; all hydrogen coordinates generated',
    'sdf_bonds': 'exact source heavy Kekule integer bond orders; source aromatic flags retained separately in canonical graph',
    'reader_atom_aliases': 'element plus sequential element count; explicit same-index source-name mapping, no chemical aliases inferred',
    'parameterization': {'forcefield': FF_NAME, 'forcefield_sha256': FF_SHA,
        'charge_model': MODEL_NAME, 'charge_model_sha256': MODEL_SHA,
        'charge_role': 'NAGL predicted AM1-BCC-like computational partial charges, not experimental charge or toolkit AM1-BCC',
        'constraints': 'remove Constraints handler before new parameter assignment; never strip constraints from an existing system',
        'retraining': False, 'new_model_download': False},
    'state_or_pose_selected_using_energy_force_or_score': False,
    'preparation_force_energy_minimization_evaluations': 0,
    'later_same_math_audit': {'executed_by_preparer': False, 'states': 'initial plus 3 fixed perturbations',
        'seed': 20260929, 'perturbation_max_component_angstrom': 0.001,
        'energy_absolute_tolerance_kcal_mol': 1e-8,
        'force_absolute_tolerance_kcal_mol_angstrom': 1e-8},
    'authority': {'numerical_development_only': True, 'reserved_source_role_unchanged': True,
        'training_admitted': False, 'calibration_admitted': False, 'independent_evaluation_admitted': False,
        'pose_recovery_admitted': False, 'scientifically_validated': False,
        'product_qualified': False, 'protected_context_read': False,
        'experimental_Ki_used': False, 'independent_pose_recovery_claimed': False},
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def write(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)


def ref(path):
    path = path.resolve(strict=True)
    raw = path.read_bytes()
    return {'path': str(path), 'sha256': sha(raw), 'bytes': len(raw)}


def reader_ref(path):
    row = ref(path)
    return {'path': row['path'], 'sha256': row['sha256'], 'source_id': path.name}


def check_source_bytes(raw, expected=SOURCE_SHA):
    if sha(raw) != expected:
        raise ValueError('SOURCE_CIF_HASH_MISMATCH')


def validate_declared_state(state):
    if state != STATE:
        raise ValueError('UNSUPPORTED_COMPUTATIONAL_MICROSTATE')


def category(block, name):
    prefix = name.lower() + '.'
    found = []
    for loop in block.loops:
        if any(tag.lower().startswith(prefix) for tag in loop.tags):
            if not all(tag.lower().startswith(prefix) for tag in loop.tags):
                raise ValueError('MIXED_SOURCE_CIF_CATEGORY')
            keys = [token.value[len(prefix):] for token in loop.tag_tokens]
            found.extend(dict(zip(keys, (token.value for token in row), strict=True)) for row in loop.rows)
    scalars = {tag[len(prefix):]: token.value for tag, token in block.scalar_values.items()
               if tag.lower().startswith(prefix)}
    if scalars:
        if found:
            raise ValueError('MIXED_SCALAR_LOOP_CATEGORY')
        found.append(scalars)
    return found


def extract_source(raw):
    check_source_bytes(raw)
    from betelgeuze_engine_v2.molecular.mmcif_syntax import parse_cif_block
    block = parse_cif_block(raw.decode('utf-8'))
    observed = [row for row in category(block, '_atom_site')
                if row['label_comp_id'] == 'SRO']
    component_atoms = [row for row in category(block, '_chem_comp_atom') if row['comp_id'] == 'SRO']
    component_bonds = [row for row in category(block, '_chem_comp_bond') if row['comp_id'] == 'SRO']
    em_buffers = category(block, '_em_buffer')
    graph = {'observed_atoms': observed, 'component_atoms': component_atoms,
             'component_bonds': component_bonds, 'deposited_em_buffer_pH': [row.get('pH', row.get('ph')) for row in em_buffers]}
    validate_source_graph(graph)
    return graph


def validate_source_graph(graph):
    atoms = graph['observed_atoms']
    names = [row['label_atom_id'] for row in atoms]
    if len(names) != 13 or len(set(names)) != len(names):
        raise ValueError('SOURCE_HEAVY_ATOM_NAME_COVERAGE_OR_DUPLICATE')
    if len({row['id'] for row in atoms}) != 13:
        raise ValueError('SOURCE_ATOM_ID_DUPLICATE')
    for row in atoms:
        expected = {'label_comp_id': 'SRO', 'label_asym_id': 'F', 'label_entity_id': '6',
            'auth_asym_id': 'R', 'auth_seq_id': '501', 'pdbx_PDB_model_num': '1',
            'label_alt_id': '.', 'pdbx_formal_charge': '?'}
        if any(row[key] != value for key, value in expected.items()) or Decimal(row['occupancy']) != 1:
            raise ValueError('SOURCE_OBSERVATION_IDENTITY_OR_STATE_CHANGED')
        if any(not Decimal(row[key]).is_finite() for key in ('Cartn_x', 'Cartn_y', 'Cartn_z')):
            raise ValueError('NONFINITE_SOURCE_COORDINATE')
    components = graph['component_atoms']
    component_names = [row['atom_id'] for row in components]
    if len(components) != 25 or len(set(component_names)) != 25 or any('charge' in row for row in components):
        raise ValueError('SOURCE_COMPONENT_ATOM_STATE_CHANGED')
    heavy = {row['atom_id']: row for row in components if row['type_symbol'] != 'H'}
    if set(names) != set(heavy) or Counter(row['type_symbol'] for row in atoms) != {'C': 10, 'N': 2, 'O': 1}:
        raise ValueError('SOURCE_HEAVY_COMPONENT_COVERAGE_CHANGED')
    if any(row['type_symbol'] != heavy[row['label_atom_id']]['type_symbol'] for row in atoms):
        raise ValueError('SOURCE_ELEMENT_MISMATCH')
    pairs = set()
    for bond in graph['component_bonds']:
        a, b = bond['atom_id_1'], bond['atom_id_2']
        pair = tuple(sorted((a, b)))
        if a == b or a not in component_names or b not in component_names or pair in pairs:
            raise ValueError('SOURCE_BOND_IDENTITY_DUPLICATE_OR_MISSING_ATOM')
        if bond['value_order'].lower() not in ('sing', 'doub') or bond['pdbx_aromatic_flag'] not in ('Y', 'N'):
            raise ValueError('UNSUPPORTED_SOURCE_BOND_STATE')
        pairs.add(pair)
    if len(pairs) != 26 or sum(a in heavy and b in heavy for a, b in pairs) != 14:
        raise ValueError('SOURCE_BOND_COVERAGE_CHANGED')
    if graph['deposited_em_buffer_pH'] != ['7.4']:
        raise ValueError('SOURCE_EM_BUFFER_PH_CHANGED')


def expected_hydrogen_parents(graph):
    elements = {row['atom_id']: row['type_symbol'] for row in graph['component_atoms']}
    parents = {}
    for bond in graph['component_bonds']:
        a, b = bond['atom_id_1'], bond['atom_id_2']
        if elements[a] == 'H' or elements[b] == 'H':
            hydrogen, parent = (a, b) if elements[a] == 'H' else (b, a)
            if elements[parent] == 'H' or hydrogen in parents or bond['value_order'].lower() != 'sing':
                raise ValueError('SOURCE_HYDROGEN_PARENT_INVALID')
            parents[hydrogen] = parent
    if len(parents) != 12 or parents.get('HNE1') != 'NE1' or parents.get('HOH') != 'OH':
        raise ValueError('SOURCE_HYDROGEN_PARENT_COVERAGE_CHANGED')
    parents['HNZ3'] = 'NZ'
    return parents


def validate_prepared_mapping(graph, mapping, state=STATE):
    """Reject source drift and unsupported state without trusting RDKit or readers."""
    validate_declared_state(state)
    validate_source_graph(graph)
    atoms = mapping['atoms']
    if len(atoms) != 26 or [a['index_zero_based'] for a in atoms] != list(range(26)):
        raise ValueError('PREPARED_ATOM_COVERAGE_CHANGED')
    if len({a['name'] for a in atoms}) != 26 or len({a['reader_atom_name'] for a in atoms}) != 26:
        raise ValueError('PREPARED_ATOM_NAME_DUPLICATE')
    source = graph['observed_atoms']
    components = {a['atom_id']: a for a in graph['component_atoms']}
    parents = expected_hydrogen_parents(graph)
    names = {a['name']: a['index_zero_based'] for a in atoms}
    for index, atom in enumerate(atoms):
        if atom['formal_charge'] != (1 if atom['name'] == 'NZ' else 0):
            raise ValueError('PREPARED_FORMAL_CHARGE_STATE_CHANGED')
        xyz = atom['coordinates_angstrom']
        if len(xyz) != 3 or any(not math.isfinite(v) for v in xyz):
            raise ValueError('NONFINITE_PREPARED_COORDINATE')
        if index < 13:
            row = source[index]
            rawxyz = [row[key] for key in ('Cartn_x', 'Cartn_y', 'Cartn_z')]
            if atom['name'] != row['label_atom_id'] or atom['element'] != row['type_symbol'] or atom['source_atom_site_id'] != row['id']:
                raise ValueError('PREPARED_SOURCE_ATOM_MAPPING_CHANGED')
            if atom['source_coordinates_decimal'] != rawxyz or any(Decimal(str(v)) != Decimal(s) for v, s in zip(xyz, rawxyz, strict=True)):
                raise ValueError('SOURCE_HEAVY_COORDINATE_DRIFT')
            if atom['origin'] != 'observed_source_heavy' or atom['parent_name'] is not None or atom['parent_index_zero_based'] is not None:
                raise ValueError('HEAVY_ORIGIN_CHANGED')
        else:
            if atom['name'] not in parents or atom['element'] != 'H' or atom['origin'] != 'generated_hydrogen':
                raise ValueError('GENERATED_HYDROGEN_IDENTITY_CHANGED')
            parent = parents[atom['name']]
            if atom['parent_name'] != parent or atom['parent_index_zero_based'] != names[parent] or atom['source_atom_site_id'] is not None or atom['source_coordinates_decimal'] is not None:
                raise ValueError('GENERATED_HYDROGEN_PARENT_CHANGED')
        if atom['aromatic'] != (components.get(atom['name'], {}).get('pdbx_aromatic_flag') == 'Y'):
            raise ValueError('PREPARED_AROMATIC_STATE_CHANGED')
    expected = {}
    for bond in graph['component_bonds']:
        pair = tuple(sorted((names[bond['atom_id_1']], names[bond['atom_id_2']])))
        expected[pair] = (1 if bond['value_order'].lower() == 'sing' else 2, bond['pdbx_aromatic_flag'] == 'Y')
    expected[tuple(sorted((names['NZ'], names['HNZ3'])))] = (1, False)
    got = {}
    for bond in mapping['bonds']:
        pair = (bond['atom_i'], bond['atom_j'])
        if pair in got or pair[0] >= pair[1]:
            raise ValueError('PREPARED_BOND_DUPLICATE_OR_ORDER')
        got[pair] = (bond['order'], bond['aromatic'])
    if got != expected:
        raise ValueError('PREPARED_SOURCE_BOND_MISMATCH')


def construct_hydrogens(graph):
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Geometry import Point3D
    parents = expected_hydrogen_parents(graph)
    heavy = graph['observed_atoms']
    indices = {row['label_atom_id']: i for i, row in enumerate(heavy)}
    counts = Counter(parents.values())
    rw = Chem.RWMol()
    for row in heavy:
        name = row['label_atom_id']
        atom = Chem.Atom(row['type_symbol'])
        atom.SetFormalCharge(1 if name == 'NZ' else 0)
        atom.SetNoImplicit(True)
        atom.SetNumExplicitHs(counts[name])
        rw.AddAtom(atom)
    for bond in graph['component_bonds']:
        a, b = bond['atom_id_1'], bond['atom_id_2']
        if a in indices and b in indices:
            rw.AddBond(indices[a], indices[b], Chem.BondType.SINGLE if bond['value_order'].lower() == 'sing' else Chem.BondType.DOUBLE)
    mol = rw.GetMol()
    Chem.SanitizeMol(mol)
    conf = Chem.Conformer(13)
    for index, row in enumerate(heavy):
        conf.SetAtomPosition(index, Point3D(*[float(row[k]) for k in ('Cartn_x', 'Cartn_y', 'Cartn_z')]))
    mol.AddConformer(conf)
    mol = Chem.AddHs(mol, addCoords=True)
    if mol.GetNumAtoms() != 26 or rdMolDescriptors.CalcMolFormula(mol) != STATE['formula']:
        raise ValueError('GENERATED_MICROSTATE_FORMULA_MISMATCH')
    conf = mol.GetConformer()
    components = {row['atom_id']: row for row in graph['component_atoms']}
    hnames = {name: [h for h, parent in parents.items() if parent == name] for name in indices}
    heavy_names = list(indices)
    names = list(heavy_names)
    prepared = []
    element_counts = Counter()
    for index, atom in enumerate(mol.GetAtoms()):
        if index < 13:
            row = heavy[index]
            name = heavy_names[index]
            parent = None
            source_xyz = [row[k] for k in ('Cartn_x', 'Cartn_y', 'Cartn_z')]
        else:
            neighbors = atom.GetNeighbors()
            if len(neighbors) != 1 or neighbors[0].GetIdx() >= 13:
                raise ValueError('RDKIT_GENERATED_H_PARENT_INVALID')
            parent = neighbors[0].GetIdx()
            name = hnames[heavy_names[parent]].pop(0)
            names.append(name)
            source_xyz = None
            xyz = conf.GetAtomPosition(index)
            conf.SetAtomPosition(index, [round(xyz[axis], 4) for axis in range(3)])
        element_counts[atom.GetSymbol()] += 1
        prepared.append({'index_zero_based': index, 'name': name,
            'reader_atom_name': f'{atom.GetSymbol()}{element_counts[atom.GetSymbol()]}',
            'element': atom.GetSymbol(), 'formal_charge': atom.GetFormalCharge(),
            'aromatic': components.get(name, {}).get('pdbx_aromatic_flag') == 'Y',
            'origin': 'observed_source_heavy' if index < 13 else 'generated_hydrogen',
            'source_atom_site_id': heavy[index]['id'] if index < 13 else None,
            'source_component_atom_name': name if name in components else None,
            'source_coordinates_decimal': source_xyz,
            'parent_index_zero_based': parent, 'parent_name': heavy_names[parent] if parent is not None else None,
            'coordinates_angstrom': list(conf.GetAtomPosition(index)),
            'hydrogen_method_protocol_key': 'generated_hydrogens_method' if index >= 13 else None})
    by_name = {name: index for index, name in enumerate(names)}
    bonds = []
    for row in graph['component_bonds']:
        i, j = sorted((by_name[row['atom_id_1']], by_name[row['atom_id_2']]))
        bonds.append({'atom_i': i, 'atom_j': j, 'order': 1 if row['value_order'].lower() == 'sing' else 2,
            'aromatic': row['pdbx_aromatic_flag'] == 'Y', 'source_component_bond': row})
    i, j = sorted((by_name['NZ'], by_name['HNZ3']))
    bonds.append({'atom_i': i, 'atom_j': j, 'order': 1, 'aromatic': False, 'source_component_bond': None})
    mapping = {'schema_id': 'sro_source_and_generated_atom_mapping/1.0.0', 'index_policy': 'zero based; all readers preserve atom order',
        'atoms': prepared, 'bonds': sorted(bonds, key=lambda b: (b['atom_i'], b['atom_j']))}
    validate_prepared_mapping(graph, mapping)
    return mol, mapping


def installed_sources():
    import openforcefields
    import openff.nagl_models
    import openff.toolkit
    import openff.interchange
    import openmm
    from rdkit import rdBase
    ff = Path(openforcefields.__file__).parent / 'offxml' / FF_NAME
    model = Path(openff.nagl_models.__file__).parent / 'models/am1bcc' / MODEL_NAME
    if ref(ff)['sha256'] != FF_SHA or ref(model)['sha256'] != MODEL_SHA:
        raise ValueError('PINNED_FORCEFIELD_OR_MODEL_HASH_MISMATCH')
    versions = {'python': sys.version, 'rdkit': rdBase.rdkitVersion, 'openff_toolkit': openff.toolkit.__version__,
        'openff_interchange': openff.interchange.__version__, 'openmm': openmm.version.version}
    if versions['openff_toolkit'] != '0.18.0' or versions['openff_interchange'] != '0.5.2' or not versions['openmm'].startswith('8.6.1'):
        raise ValueError('PINNED_RUNTIME_VERSION_MISMATCH')
    return ff, model, versions


def parameterize(mol, output):
    from openff.toolkit import ForceField, Molecule, Topology
    from openff.interchange import Interchange
    from openmm import XmlSerializer
    ff_path, model_path, versions = installed_sources()
    write(output / 'runtime-and-parameter-sources.json', encoded({'forcefield': ref(ff_path), 'charge_model': ref(model_path), 'runtime_versions': versions,
        'charge_inference_role': PROTOCOL['parameterization']['charge_role'], 'model_inference_count_requested': 1,
        'training_or_retraining': False, 'source_experimental_charge_inferred': False}))
    off = Molecule.from_rdkit(mol, hydrogens_are_explicit=True)
    if off.n_atoms != mol.GetNumAtoms() or any(a.atomic_number != b.GetAtomicNum() for a, b in zip(off.atoms, mol.GetAtoms(), strict=True)):
        raise ValueError('OPENFF_ATOM_MAPPING_CHANGED')
    if {tuple(sorted((b.atom1_index, b.atom2_index))) for b in off.bonds} != {tuple(sorted((b.GetBeginAtomIdx(), b.GetEndAtomIdx()))) for b in mol.GetBonds()}:
        raise ValueError('OPENFF_BOND_ADJACENCY_CHANGED')
    try:
        off.assign_partial_charges(partial_charge_method=MODEL_NAME)
    except Exception as exc:
        raise ValueError('NAGL_COMPUTATIONAL_CHARGE_ASSIGNMENT_UNSUPPORTED: ' + str(exc)) from exc
    ff = ForceField(str(ff_path))
    if 'Constraints' not in ff.registered_parameter_handlers:
        raise ValueError('PINNED_FORCEFIELD_CONSTRAINTS_HANDLER_MISSING')
    ff.deregister_parameter_handler('Constraints')
    write(output / 'unconstrained-forcefield.offxml', ff.to_string().encode())
    try:
        interchange = Interchange.from_smirnoff(ff, Topology.from_molecules([off]), charge_from_molecules=[off])
        system = interchange.to_openmm(combine_nonbonded_forces=True)
    except Exception as exc:
        raise ValueError('OPENFF_UNCONSTRAINED_PARAMETERIZATION_UNSUPPORTED: ' + str(exc)) from exc
    if system.getNumConstraints() != 0 or system.getNumParticles() != 26:
        raise ValueError('UNCONSTRAINED_PARTICLE_CONTRACT_FAILED')
    write(output / 'ligand-unconstrained-openmm-system.xml', XmlSerializer.serialize(system).encode())
    return system, versions


def render_readers(system, mapping, output):
    from openmm import NonbondedForce, unit
    atoms = mapping['atoms']
    nbs = [f for f in system.getForces() if isinstance(f, NonbondedForce)]
    if len(nbs) != 1 or nbs[0].getNumParticles() != 26 or nbs[0].getNonbondedMethod() != NonbondedForce.NoCutoff:
        raise ValueError('UNSUPPORTED_NONBONDED_SYSTEM')
    nb = nbs[0]
    sdf = ['SRO_NZplus1_development', '  source-bound SRO', 'generated H only; source heavy coordinates retained',
           f'{26:3d}{27:3d}  0  0  0  0            999 V2000']
    gro = ['SRO source frame; generated H; numerical development', '26']
    types = ['; Reader nonbonded projection only; full terms in XML', '[ atomtypes ]']
    itp = ['; Adjacency/nonbonded reader projection only; not a GROMACS force field', '[ moleculetype ]', 'SRO 3', '', '[ atoms ]']
    particles = []
    for i, atom in enumerate(atoms):
        xyz = atom['coordinates_angstrom']
        sdf.append(''.join(f'{x:10.4f}' for x in xyz) + f' {atom["element"]:<3s} 0  0  0  0  0  0  0  0  0  0  0  0')
        gro.append(f'{1:5d}{"SRO":<5s}{atom["reader_atom_name"]:>5s}{i+1:5d}' + ''.join(f'{x / 10:15.10f}' for x in xyz))
        q, sig, eps = nb.getParticleParameters(i)
        row = {'atom_index': i, 'charge_e': float(q.value_in_unit(unit.elementary_charge)),
            'sigma_nm': float(sig.value_in_unit(unit.nanometer)), 'epsilon_kj_mol': float(eps.value_in_unit(unit.kilojoule_per_mole)),
            'mass_da': float(system.getParticleMass(i).value_in_unit(unit.dalton))}
        if any(not math.isfinite(x) for x in row.values()) or row['mass_da'] <= 0 or row['sigma_nm'] < 0 or row['epsilon_kj_mol'] < 0:
            raise ValueError('INVALID_PARTICLE_PARAMETER')
        particles.append(row)
        z = {'H': 1, 'C': 6, 'N': 7, 'O': 8}[atom['element']]
        typ = f'S{i+1:03d}'
        types.append(f'{typ} {z} {row["mass_da"]!r} 0 A {row["sigma_nm"]!r} {row["epsilon_kj_mol"]!r}')
        itp.append(f'{i+1} {typ} 1 SRO {atom["reader_atom_name"]} {i+1} {row["charge_e"]!r} {row["mass_da"]!r}')
    total = sum(row['charge_e'] for row in particles)
    if abs(total - 1) > 1e-8:
        raise ValueError('PARTIAL_CHARGE_SUM_NOT_DECLARED_PLUS_ONE')
    itp += ['', '[ bonds ]', '; ai aj funct: adjacency only']
    for bond in mapping['bonds']:
        i, j = bond['atom_i'] + 1, bond['atom_j'] + 1
        sdf.append(f'{i:3d}{j:3d}{bond["order"]:3d}  0  0  0  0')
        itp.append(f'{i} {j} 1')
    nz = next(i for i, a in enumerate(atoms) if a['name'] == 'NZ') + 1
    sdf += [f'M  CHG  1{nz:4d}{1:4d}', 'M  END', '$$$$']
    gro.append('   10.00000   10.00000   10.00000')
    for name, lines in [('ligand.sdf', sdf), ('ligand.gro', gro), ('ligand.itp', itp), ('atomtypes.itp', types)]:
        write(output / name, ('\n'.join(lines) + '\n').encode())
    write(output / 'defaults.itp', b'; reader projection only; no bonded/exclusion semantics\n[ defaults ]\n1 2 no 1.0 1.0\n')
    write(output / 'particle-parameters.json', encoded({'particles': particles, 'partial_charge_sum_e': total,
        'charge_role': PROTOCOL['parameterization']['charge_role']}))
    return {'atoms': 26, 'heavy_atoms': 13, 'hydrogens': 13, 'bonds': 27, 'formal_charge_sum_e': 1,
        'partial_charge_sum_e': total, 'openmm_constraints': 0, 'openmm_exceptions': nb.getNumExceptions(),
        'openmm_forces': [f.__class__.__name__ for f in system.getForces()]}


def checked_receptor():
    raw = (RECEPTOR / 'manifest.v1.json').read_bytes()
    if sha(raw) != RECEPTOR_MANIFEST_SHA:
        raise ValueError('RECEPTOR_PREPARATION_MANIFEST_CHANGED')
    manifest = json.loads(raw)
    for name in ('receptor-prepared.pdb', 'receptor-A.itp', 'receptor-B.itp', 'atomtypes.itp', 'defaults.itp', 'openmm-system.xml'):
        row = manifest['files'][name]
        content = (RECEPTOR / name).read_bytes()
        if sha(content) != row['sha256'] or len(content) != row['bytes']:
            raise ValueError('RECEPTOR_INPUT_CHANGED:' + name)
    if ref(RECEPTOR_CHEMICAL / 'receptor-canonical.json')['sha256'] != RECEPTOR_CANONICAL_SHA:
        raise ValueError('RECEPTOR_CHEMICAL_CANONICAL_CHANGED')
    return {'prepared_manifest': ref(RECEPTOR / 'manifest.v1.json'),
        'chemical_manifest': ref(RECEPTOR_CHEMICAL / 'manifest.v1.json'),
        'canonical': ref(RECEPTOR_CHEMICAL / 'receptor-canonical.json'),
        'openmm_xml': ref(RECEPTOR / 'openmm-system.xml'),
        'atom_provenance': ref(RECEPTOR / 'atom-provenance.csv')}


def read_and_bind(output, mapping):
    from betelgeuze_engine.product.prepared_gromacs_input import load_prepared_gromacs_components
    from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes, canonical_system_sha256, all_atom_system_from_canonical_json
    request = {'schema_version': 'prepared_gromacs_components_v1',
        'protein_pdb': reader_ref(RECEPTOR / 'receptor-prepared.pdb'),
        'protein_chains': [{'chain_id': c, 'molecule_itp': reader_ref(RECEPTOR / f'receptor-{c}.itp')} for c in ('A', 'B')],
        'protein_atomtypes': reader_ref(RECEPTOR / 'atomtypes.itp'), 'protein_defaults': reader_ref(RECEPTOR / 'defaults.itp'),
        'ligand_sdf': reader_ref(output / 'ligand.sdf'), 'ligand_gro': reader_ref(output / 'ligand.gro'),
        'ligand_itp': reader_ref(output / 'ligand.itp'), 'ligand_atomtypes': reader_ref(output / 'atomtypes.itp'),
        'ligand_defaults': reader_ref(output / 'defaults.itp'), 'ligand_atomtype_name_mapping': {},
        'ligand_residue_name_mapping': {'itp': 'SRO', 'gro': 'SRO'}, 'naming_convention': 'exact',
        'pdb_element_policy': 'reject_missing',
        'source_declarations': {'coordinate_frame_id': FRAME, 'prepared_state_id': 'SRO_NZplus1_generatedH_observedHeavy_development_v1',
            'parameter_source_id': 'amber14_receptor_OpenFF221_unconstrained_SRO', 'charge_source_id': 'amber14_receptor_NAGL1_SRO_computational'},
        'source_relationship': 'SRO observed heavy source coordinates; generated computational H and NZ+1 assumption; receptor independently prepared in same source frame; no measured-state or independent-evaluation admission'}
    write(output / 'prepared-input.json', encoded(request))
    receptor, ligand, _, ligand_parameters, evidence = load_prepared_gromacs_components(request)
    corrected = all_atom_system_from_canonical_json((RECEPTOR_CHEMICAL / 'receptor-canonical.json').read_bytes())
    if not receptor.coordinates.equal(corrected.coordinates) or receptor.atom_count != corrected.atom_count:
        raise ValueError('RECEPTOR_READER_COORDINATES_CHANGED')
    if ligand.coordinates[0].tolist() != [a['coordinates_angstrom'] for a in mapping['atoms']]:
        raise ValueError('READER_COORDINATE_ROUNDTRIP_DRIFT')
    write(output / 'ligand-reader-canonical.json', canonical_system_json_bytes(ligand))
    # Source chemistry binding is explicit; no graph, charge or coordinate guessing.
    atoms = tuple(replace(atom, name=row['name'], formal_charge=row['formal_charge'], aromatic=row['aromatic'],
        metadata={**atom.metadata, 'source_and_generated_atom_mapping': row}) for atom, row in zip(ligand.atoms, mapping['atoms'], strict=True))
    by_pair = {(b['atom_i'], b['atom_j']): b for b in mapping['bonds']}
    bonds = []
    for bond in ligand.bonds:
        row = by_pair[(bond.atom_i, bond.atom_j)]
        if bond.order != row['order']:
            raise ValueError('SDF_SOURCE_KEKULE_BOND_ORDER_CHANGED')
        bonds.append(replace(bond, aromatic=row['aromatic'], source='7XTB_SRO_component_plus_declared_HNZ3', metadata=row))
    ligand = replace(ligand, atoms=atoms, bonds=tuple(bonds),
        provenance=replace(ligand.provenance,
            operations=ligand.provenance.operations + ('explicit_source_atom_names_and_component_aromatic_flags',),
            parent_sha256=ligand.provenance.parent_sha256 + (SOURCE_SHA, canonical_system_sha256(ligand)),
            metadata={**ligand.provenance.metadata, 'source_coordinates_frame': FRAME,
                'computational_microstate': STATE, 'role': 'numerical_development_reserved_source_role_unchanged'}))
    write(output / 'ligand-canonical.json', canonical_system_json_bytes(ligand))
    evidence['source_aromatic_and_name_binding'] = {'mapping': ref(output / 'atom-provenance.json'),
        'reader_canonical': ref(output / 'ligand-reader-canonical.json'), 'bound_canonical': ref(output / 'ligand-canonical.json'),
        'changes': ['explicit source names replacing reader aliases', 'source component aromatic flags'],
        'coordinates_or_parameters_changed': False, 'scientifically_validated': False}
    write(output / 'reader-evidence.json', encoded(evidence))
    write(output / 'reader-parameters.json', encoded({'ligand': ligand_parameters, 'scope': 'reader nonbonded projection only; full bonded terms and exceptions are in XML'}))
    return ligand, corrected


def geometry(ligand, receptor, mapping):
    import numpy as np
    lxyz = ligand.coordinates[0].numpy()
    rxyz = receptor.coordinates[0].numpy()
    distances = np.linalg.norm(lxyz[:, None, :] - rxyz[None, :, :], axis=2)
    i, j = np.unravel_index(int(distances.argmin()), distances.shape)
    rh = np.array([atom.element != 'H' for atom in receptor.atoms])
    heavy = distances[:13, rh]
    h_lengths = [float(np.linalg.norm(lxyz[row['index_zero_based']] - lxyz[row['parent_index_zero_based']]))
                 for row in mapping['atoms'][13:]]
    return {'source_heavy_coordinate_change_angstrom': 0.0,
        'heavy_atoms_exactly_preserved': 13, 'generated_hydrogens': 13,
        'source_centroid_angstrom': lxyz[:13].mean(axis=0).tolist(),
        'minimum_receptor_ligand_distance_angstrom': float(distances[i, j]),
        'closest_pair': {'ligand_index': int(i), 'ligand_name': ligand.atoms[i].name,
            'receptor_index': int(j), 'receptor_name': receptor.atoms[j].name,
            'receptor_residue_index': receptor.atoms[j].residue_index},
        'minimum_heavy_receptor_ligand_distance_angstrom': float(heavy.min()),
        'generated_H_parent_distance_min_angstrom': min(h_lengths),
        'generated_H_parent_distance_max_angstrom': max(h_lengths),
        'geometry_role': 'descriptive distances only; no pose rejection, relaxation, selection or physical validation',
        'force_energy_or_minimization_evaluations': 0}


def build(output):
    started = time.perf_counter()
    output.mkdir(parents=True, exist_ok=False)
    # Persist the protocol and exact implementation before molecular construction or inference.
    write(output / 'protocol.json', encoded(PROTOCOL))
    write(output / 'prepare-sro-source.py', Path(__file__).read_bytes())
    stage = 'source_validation'
    try:
        validate_declared_state(PROTOCOL['computational_microstate'])
        graph = extract_source(SOURCE.read_bytes())
        graph['source'] = ref(SOURCE)
        write(output / 'source-graph.json', encoded(graph))
        receptor_refs = checked_receptor()
        stage = 'hydrogen_generation'
        mol, mapping = construct_hydrogens(graph)
        write(output / 'atom-provenance.json', encoded(mapping))
        stage = 'parameterization'
        system, versions = parameterize(mol, output)
        stage = 'reader_projection'
        counts = render_readers(system, mapping, output)
        ligand, receptor = read_and_bind(output, mapping)
        stage = 'geometry_observation'
        observations = geometry(ligand, receptor, mapping)
        write(output / 'geometry.json', encoded(observations))
        from betelgeuze_engine_v2.molecular.serialization import canonical_system_sha256, canonical_topology_sha256
        manifest = {'schema_id': 'human_5ht6_sro_numerical_preparation/1.0.0',
            'status': 'PREPARED_NUMERICAL_DEVELOPMENT_NOT_SCIENTIFICALLY_QUALIFIED',
            'source': ref(SOURCE), 'receptor_refs': receptor_refs, 'protocol': ref(output / 'protocol.json'),
            'implementation': ref(output / 'prepare-sro-source.py'), 'coordinate_frame_id': FRAME,
            'computational_microstate': STATE, 'source_bound_protonation_known': False,
            'source_deposited_em_buffer_pH': '7.4', 'source_assay_chemical_state_known': False,
            'counts': counts, 'runtime_versions': versions,
            'ligand_system_sha256': canonical_system_sha256(ligand),
            'ligand_topology_sha256': canonical_topology_sha256(ligand),
            'receptor_system_sha256': canonical_system_sha256(receptor),
            'force_energy_minimization_evaluations': 0, 'scientific_authority': PROTOCOL['authority'],
            'wall_seconds': time.perf_counter() - started,
            'files': {p.name: {'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size} for p in sorted(output.iterdir())}}
        write(output / 'manifest.v1.json', encoded(manifest))
        return manifest
    except Exception as exc:
        write(output / 'preparation-failure.json', encoded({'status': 'FAILED_PREPARATION_NOT_ADMITTED', 'stage': stage,
            'error_type': type(exc).__name__, 'error': str(exc), 'protocol': ref(output / 'protocol.json'),
            'force_energy_minimization_evaluations': 0, 'outputs_preserved': True,
            'wall_seconds': time.perf_counter() - started}))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build(args.output.resolve())
    print(json.dumps({'status': result['status'], 'output': str(args.output.resolve()),
        'counts': result['counts'], 'manifest': ref(args.output / 'manifest.v1.json')}, sort_keys=True))
