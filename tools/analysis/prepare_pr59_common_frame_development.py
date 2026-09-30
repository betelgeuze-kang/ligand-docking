"""Reproduce PR59 preparation using the retained PR49 development protocol.

Creates a separate computational pose and unconstrained model. Original
coordinates/XML remain immutable. No assay endpoint, role, admission or fit
record is read or created. Every supported XML term is translated or rejected.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from dataclasses import replace
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np

BASE = Path('/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs')
PR59 = BASE / 'engine-v2-5ht6-pr49-pr59-openff-projection-20260929/PR59'
PR49_REQUEST = BASE / 'engine-v2-pr49-aromatic-annotation-20260930-wjlhkyh8/derived/request.json'
PAIR_PROTOCOL = BASE / 'engine-v2-pr49-pr59-source-geometry-20260930-e70eb8e4-bbd597fa/protocol-final.json'
PR49_REQUEST_SHA = '064969aa0ce6428da76b2697e2266ded8c1690af1e65949ab34afb00e22d5ef1'
PAIR_PROTOCOL_SHA = 'd54e6a13cfd62d39a5cafce138853292feb6faa813b7a65f61c42b6b5537da9a'
PREPARER_SHA = '42820d79d5187bb0346bc31415fc7f4e0d7561ac0321b6e10a60a1beb50287e5'
VERIFIER_SHA = '662feffd5ba9f16186840f64510cdaa4a4c85f26ece6d6a2d145ff4ebe73675f'
FORCES = {'NonbondedForce', 'HarmonicBondForce', 'HarmonicAngleForce',
          'PeriodicTorsionForce', 'CMMotionRemover'}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def reference(path):
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    return {'path': str(path), 'sha256': sha(raw)}


def bound(ref):
    raw = Path(ref['path']).read_bytes()
    require(sha(raw) == ref['sha256'], 'bound_input_hash_mismatch')
    return raw


def write(path, value):
    raw = value if isinstance(value, bytes) else encoded(value)
    with Path(path).open('xb') as stream:
        stream.write(raw)
    return reference(path)


def load_module(name, path, expected):
    require(sha(path.read_bytes()) == expected, 'pr49_protocol_implementation_hash_mismatch')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unconstrained_difference(original_xml, new_xml, expected_constraints):
    """Require regeneration to restore precisely the constrained bond pairs."""
    require(type(expected_constraints) is int and expected_constraints > 0,
            'explicit_positive_original_constraint_inventory_required')
    old, new = ET.fromstring(original_xml), ET.fromstring(new_xml)
    require(old.tag == new.tag == 'System', 'openmm_system_required')
    require(len(old.findall('Constraints')) == len(new.findall('Constraints')) == 1,
            'unique_constraint_section_required')
    constraints = list(old.find('Constraints'))
    require(len(constraints) == expected_constraints and len(new.find('Constraints')) == 0,
            'original_or_derived_constraint_inventory_changed')
    constrained = []
    for row in constraints:
        require(row.tag == 'Constraint' and set(row.attrib) == {'p1', 'p2', 'd'},
                'unsupported_constraint_record')
        constrained.append(tuple(sorted((int(row.get('p1')), int(row.get('p2'))))))
    require(len(set(constrained)) == len(constrained), 'duplicate_constraint_pair')
    require(ET.tostring(old.find('Particles')) == ET.tostring(new.find('Particles')),
            'particle_masses_or_order_changed')
    require(not any(len(root.find('VirtualSites')) for root in (old, new) if root.find('VirtualSites') is not None),
            'virtual_sites_unsupported')
    tables = []
    for root in (old, new):
        forces = list(root.find('Forces'))
        table = {row.get('type'): row for row in forces}
        require(len(table) == len(forces) and set(table) == FORCES,
                'unsupported_or_duplicate_force_class')
        tables.append(table)
    old_forces, new_forces = tables
    for name in FORCES - {'HarmonicBondForce'}:
        require(ET.tostring(old_forces[name]) == ET.tostring(new_forces[name]),
                'nonbond_force_or_parameter_changed:' + name)
    bond_tables = []
    for table in tables:
        rows = list(table['HarmonicBondForce'].find('Bonds'))
        bonds = {tuple(sorted((int(row.get('p1')), int(row.get('p2'))))): dict(row.attrib) for row in rows}
        require(len(bonds) == len(rows), 'duplicate_harmonic_bond_pair')
        bond_tables.append(bonds)
    old_bonds, new_bonds = bond_tables
    require(all(new_bonds.get(pair) == row for pair, row in old_bonds.items()),
            'preexisting_harmonic_bond_changed')
    added = sorted(set(new_bonds) - set(old_bonds))
    require(added == sorted(constrained), 'restored_bonds_do_not_equal_original_constraint_pairs')
    return {'original_constraint_count': len(constraints), 'new_constraint_count': 0,
            'old_harmonic_bond_count': len(old_bonds), 'new_harmonic_bond_count': len(new_bonds),
            'new_harmonic_bond_pairs_zero_based': [list(pair) for pair in added],
            'new_harmonic_bonds': [new_bonds[pair] for pair in added],
            'unchanged_serialized_force_classes': sorted(FORCES - {'HarmonicBondForce'}),
            'particle_masses_unchanged': True,
            'constrained_dynamics_equivalence_claimed': False}


def regenerate_unconstrained(pr49, source_molecule, output):
    from openff.toolkit import ForceField, Molecule, Topology
    from openff.interchange import Interchange
    from openff.units import unit as off_unit
    from openmm import NonbondedForce, XmlSerializer, unit
    import openforcefields
    ff_path = Path(openforcefields.__file__).parent / 'offxml/openff-2.2.1.offxml'
    require(sha(ff_path.read_bytes()) == pr49.FF_SHA, 'openff_forcefield_hash_mismatch')
    original_raw = (PR59 / 'openmm-system.xml').read_bytes()
    original = XmlSerializer.deserialize(original_raw.decode())
    require(original.getNumConstraints() == 17, 'original_constraint_inventory_changed')
    nb = [force for force in original.getForces() if isinstance(force, NonbondedForce)]
    require(len(nb) == 1, 'unique_original_nonbonded_force_required')
    molecule = Molecule.from_rdkit(source_molecule, hydrogens_are_explicit=True)
    require(molecule.n_atoms == original.getNumParticles() == 43, 'source_particle_atom_order_count_mismatch')
    charges = [nb[0].getParticleParameters(i)[0].value_in_unit(unit.elementary_charge)
               for i in range(molecule.n_atoms)]
    molecule.partial_charges = np.array(charges) * off_unit.elementary_charge
    ff = ForceField(str(ff_path))
    ff.deregister_parameter_handler('Constraints')
    system = Interchange.from_smirnoff(ff, Topology.from_molecules([molecule]),
        charge_from_molecules=[molecule]).to_openmm(combine_nonbonded_forces=True)
    new_raw = XmlSerializer.serialize(system).encode()
    difference = unconstrained_difference(original_raw, new_raw, 17)
    difference.update(original_system=reference(PR59 / 'openmm-system.xml'),
        new_system=write(output / 'ligand-unconstrained-openmm-system.xml', new_raw),
        forcefield_source=reference(ff_path),
        forcefield_without_constraints=write(output / 'unconstrained-forcefield.offxml', ff.to_string().encode()),
        charges='Original serialized NAGL predicted AM1-BCC-like tokens reused; no refit',
        policy='Same PR49 OpenFF221 regeneration with Constraints handler deregistered; separate declared model')
    write(output / 'parameterization-difference.json', difference)
    return new_raw, difference


def annotated_ligand(original, source_raw, registered_raw, map_raw, gro_raw):
    from rdkit import Chem, rdBase
    from betelgeuze_engine_v2.molecular.serialization import canonical_system_sha256
    def molecule(raw):
        rows = list(Chem.ForwardSDMolSupplier(io.BytesIO(raw), sanitize=False, removeHs=False))
        require(len(rows) == 1 and rows[0] is not None, 'single_valid_source_sdf_required')
        return rows[0]
    source, registered = molecule(source_raw), molecule(registered_raw)
    require(source.GetNumAtoms() == registered.GetNumAtoms() == original.atom_count == 43,
            'complete_source_atom_correspondence_required')
    left, right = source_raw.splitlines(), registered_raw.splitlines()
    require(len(left) == len(right) and all(a[30:] == b[30:] if 4 <= i < 47 else a == b
                for i, (a, b) in enumerate(zip(left, right))), 'noncoordinate_source_bytes_changed')
    names = list(csv.DictReader(io.StringIO(map_raw.decode())))
    gro = gro_raw.decode().splitlines()
    require(len(names) == 43 and int(gro[1]) == 43 and len(gro) == 46,
            'complete_csv_gro_alias_mapping_required')
    require(registered.GetConformer().GetPositions().tolist() == original.coordinates[0].tolist(),
            'registered_canonical_coordinate_mismatch')
    correspondence = []
    for i, (atom, source_atom, registered_atom, row) in enumerate(zip(
            original.atoms, source.GetAtoms(), registered.GetAtoms(), names)):
        require(int(row['prepared_index']) - 1 == i and row['element'] == atom.element
                and atom.name == atom.element + str(i + 1), 'canonical_csv_atom_order_mismatch')
        require(gro[i + 2][10:15].strip() == row['prepared_atom_name']
                and int(gro[i + 2][15:20]) - 1 == i, 'gro_alias_atom_order_mismatch')
        require((source_atom.GetAtomicNum(), source_atom.GetIsotope(), source_atom.GetFormalCharge()) ==
                (registered_atom.GetAtomicNum(), registered_atom.GetIsotope(), registered_atom.GetFormalCharge()) ==
                (atom.atomic_number, atom.isotope_mass_number or 0, atom.formal_charge), 'source_atom_chemistry_changed')
        require(int(right[i + 4][39:42]) == 0 and atom.stereo in {'none', 'unspecified'},
                'unsupported_explicit_sdf_atom_stereo')
        for axis, token in enumerate(gro[i + 2][20:].split()):
            require(axis < 3 and Decimal(token) * 10 == Decimal(right[i + 4][axis * 10:(axis + 1) * 10].decode()),
                    'sdf_gro_coordinate_mismatch')
        if atom.element == 'H':
            require(source_atom.GetDegree() == 1 and row['origin'] == 'computed_implicit_hydrogen'
                    and row['source_graph_atom_index'] == '', 'hydrogen_source_correspondence_mismatch')
            parent = next(iter(source_atom.GetNeighbors())).GetIdx()
            require(int(row['source_graph_parent_atom_index']) - 1 == parent, 'hydrogen_parent_map_mismatch')
        else:
            require(row['origin'] == 'source_neutral_graph_heavy'
                    and int(row['source_graph_atom_index']) - 1 == i, 'heavy_source_correspondence_mismatch')
            parent = None
        correspondence.append({'index_zero_based': i, 'canonical_name': atom.name,
            'prepared_csv_and_gro_alias': row['prepared_atom_name'], 'element': atom.element,
            'origin': row['origin'], 'hydrogen_parent_index_zero_based': parent})
    require(len(original.bonds) == source.GetNumBonds() == registered.GetNumBonds(), 'bond_count_changed')
    for bond in original.bonds:
        old = source.GetBondBetweenAtoms(bond.atom_i, bond.atom_j)
        new = registered.GetBondBetweenAtoms(bond.atom_i, bond.atom_j)
        require(old is not None and new is not None and old.GetBondTypeAsDouble() == new.GetBondTypeAsDouble() == bond.order,
                'source_integer_bond_order_changed')
        require(old.GetStereo() == new.GetStereo() == Chem.BondStereo.STEREONONE,
                'unsupported_explicit_sdf_bond_stereo')
    perceived = Chem.Mol(registered)
    Chem.SanitizeMol(perceived)
    Chem.AssignStereochemistry(perceived, cleanIt=True, force=True)
    atoms = tuple(replace(atom, aromatic=perceived.GetAtomWithIdx(i).GetIsAromatic())
                  for i, atom in enumerate(original.atoms))
    bonds = tuple(replace(bond, aromatic=perceived.GetBondBetweenAtoms(bond.atom_i, bond.atom_j).GetIsAromatic())
                  for bond in original.bonds)
    metadata = deepcopy(dict(original.provenance.metadata))
    metadata['aromatic_annotation'] = {'schema_version': 'source_bound_sdf_aromatic_annotation_v1',
        'registered_sdf_sha256': sha(registered_raw), 'source_atom_map_sha256': sha(map_raw),
        'parent_canonical_sha256': canonical_system_sha256(original),
        'policy': 'RDKit perceived aromatic flags only; original integer bond orders retained',
        'rdkit_version': rdBase.rdkitVersion, 'coordinates_changed': False, 'partial_charges_changed': False,
        'formal_charges_changed': False, 'isotopes_changed': False, 'stereo_changed': False,
        'assayed_state_verified': False}
    provenance = replace(original.provenance,
        operations=(*original.provenance.operations, 'source_bound_sdf_aromatic_annotation_only_v1'),
        parent_sha256=(*original.provenance.parent_sha256, canonical_system_sha256(original)), metadata=metadata)
    return replace(original, atoms=atoms, bonds=bonds, provenance=provenance), correspondence, perceived


def build(output, workspace):
    from rdkit import Chem
    from betelgeuze_engine.product.prepared_gromacs_input import load_prepared_gromacs_components
    from betelgeuze_engine_v2.molecular.serialization import (
        all_atom_system_from_canonical_json, canonical_system_json_bytes, canonical_system_sha256,
        canonical_topology_sha256, canonical_coordinates_sha256)
    from betelgeuze_product import installed_native_v4_registered_binding as binding
    from betelgeuze_product.native_v4_chemical_identity import chemical_identity
    from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import CrossParameters, FixedReceptorEnvironment
    from betelgeuze_product.cpu_refinement_v1_2.evidence_contracts import request_binding
    from tools.product.openmm_d3_translation import convert_openmm_system, TranslationSettings, OpenMMD3TranslationError
    start = time.perf_counter()
    require(not output.exists(), 'output_already_exists')
    pr49 = load_module('pr49_retained_preparer', workspace / 'docs/research/human_5ht6_d3_complex/prepare_complex.py', PREPARER_SHA)
    verifier = load_module('pr49_retained_verifier', workspace / 'docs/research/human_5ht6_d3_complex/verify_registration.py', VERIFIER_SHA)
    pair = json.loads(bound({'path': str(PAIR_PROTOCOL), 'sha256': PAIR_PROTOCOL_SHA}))
    request = json.loads(bound({'path': str(PR49_REQUEST), 'sha256': PR49_REQUEST_SHA}))
    bound(pair['geometry_policy_reference'])
    require(sha(encoded(pr49.PROTOCOL)) == pair['geometry_policy_reference']['sha256'], 'pr49_frozen_geometry_policy_changed')
    require(request['receptor'] == pair['receptor'] and request['pocket']['coordinate_frame_id'] == pair['coordinate_frame_id'],
            'pr49_receptor_or_frame_differs_from_geometry_protocol')
    receptor = all_atom_system_from_canonical_json(bound(request['receptor']))
    old_cross = json.loads(bound(request['cross_parameters']))
    require(old_cross['receptor_system_sha256'] == canonical_system_sha256(receptor), 'pr49_cross_receptor_binding_mismatch')
    pr49.checked_manifest(pr49.RECEPTOR, pr49.RECEPTOR_MANIFEST_SHA)
    projection = pr49.checked_manifest(pr49.LIGANDS, pr49.LIGAND_MANIFEST_SHA, 'PR59')
    source_refs = {'pair_protocol': reference(PAIR_PROTOCOL), 'pr49_request': reference(PR49_REQUEST),
        'source_cif': pair['source_cif'], 'receptor': request['receptor'],
        'pr49_cross_parameters': request['cross_parameters'], 'pr49_geometry_policy': pair['geometry_policy_reference']}
    for name in projection['rows']['PR59']['files']:
        source_refs['pr59_' + name] = reference(PR59 / name)
    source_refs['projection_manifest'] = reference(pr49.LIGANDS / 'manifest.v1.json')
    source_refs['receptor_manifest'] = reference(pr49.RECEPTOR / 'manifest.v1.json')
    for ref in source_refs.values():
        bound(ref)
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'implementation.py', Path(__file__).read_bytes())
    write(output / 'input-pins.json', source_refs)
    write(output / 'geometry-protocol.json', encoded(pr49.PROTOCOL))
    center, source_rows = pr49.pocket_anchor(pr49.SOURCE)
    require(center.tolist() == request['pocket']['center_angstrom'], 'same_pr49_pocket_anchor_required')
    molecule = Chem.SDMolSupplier(str(PR59 / 'ligand.sdf'), removeHs=False)[0]
    require(molecule is not None and molecule.GetNumAtoms() == 43, 'pr59_source_atom_count_changed')
    ligand_xyz = np.array(molecule.GetConformer().GetPositions())
    elements = [atom.GetSymbol() for atom in molecule.GetAtoms()]
    require(sum(e != 'H' for e in elements) == 26, 'pr59_heavy_atom_inventory_changed')
    geometry_start = time.perf_counter()
    try:
        registered, registration = pr49.choose_pose(receptor.coordinates[0].numpy(),
            [atom.element for atom in receptor.atoms], ligand_xyz, elements, center)
    except ValueError as error:
        write(output / 'preparation-failure.json', {'reason': str(error),
            'geometry_attempts': getattr(error, 'geometry_attempts', []),
            'search_wall_seconds': time.perf_counter() - geometry_start})
        raise
    registration.update(search_wall_seconds=time.perf_counter() - geometry_start,
        candidate_id='PR59', coordinate_frame_id=pair['coordinate_frame_id'],
        pocket_center_angstrom=center.tolist(), public_source_anchor_rows=source_rows,
        protocol=reference(output / 'geometry-protocol.json'), source=pair['source_cif'],
        ligand_source=reference(PR59 / 'ligand.sdf'),
        source_atom_mapping=[{'prepared_index_zero_based': i, 'source_index_zero_based': i, 'element': e}
                             for i, e in enumerate(elements)],
        physical_binding_pose_or_pose_recovery_claimed=False)
    write(output / 'registration.json', registration)
    sdf = (PR59 / 'ligand.sdf').read_bytes().splitlines(keepends=True)
    gro = (PR59 / 'ligand.gro').read_bytes().splitlines(keepends=True)
    for i, xyz in enumerate(registered):
        sdf[i + 4] = ''.join(f'{x:10.4f}' for x in xyz).encode() + sdf[i + 4][30:]
        ending = b'\r\n' if gro[i + 2].endswith(b'\r\n') else b'\n'
        gro[i + 2] = gro[i + 2][:20] + ''.join(f'{x / 10:15.10f}' for x in xyz).encode() + ending
    write(output / 'ligand-registered.sdf', b''.join(sdf))
    write(output / 'ligand-registered.gro', b''.join(gro))
    verified = verifier.verify_geometry(receptor.coordinates[0].numpy(), [a.element for a in receptor.atoms],
        (PR59 / 'ligand.sdf').read_bytes(), b''.join(sdf), registration, pr49.PROTOCOL)
    write(output / 'registration-verification.json', verified)
    prepared = pr49.prepared_request(output)
    for key, filename in [('ligand_itp', 'ligand.itp'), ('ligand_atomtypes', 'atomtypes.itp'), ('ligand_defaults', 'defaults.itp')]:
        prepared[key] = pr49.ref(PR59 / filename)
    prepared['ligand_residue_name_mapping'] = {'itp': 'PR59', 'gro': 'PR59'}
    prepared['source_declarations']['prepared_state_id'] = 'PR59_neutral_unconstrained_geometry_registered_development_v1'
    prepared['source_relationship'] = 'independent components; same PR49 frozen geometric rigid-placement protocol; no observed PR59 pose'
    write(output / 'prepared-input.json', prepared)
    read_receptor, original_ligand, _, _, reader = load_prepared_gromacs_components(prepared)
    require(read_receptor.coordinates[0].tolist() == receptor.coordinates[0].tolist(), 'same_receptor_coordinate_frame_required')
    write(output / 'ligand-reader-parent.json', canonical_system_json_bytes(original_ligand))
    ligand, correspondence, perceived = annotated_ligand(original_ligand, (PR59 / 'ligand.sdf').read_bytes(),
        b''.join(sdf), (PR59 / 'atom-provenance.csv').read_bytes(), b''.join(gro))
    require(canonical_coordinates_sha256(ligand) == canonical_coordinates_sha256(original_ligand), 'annotation_coordinates_changed')
    ligand_ref = write(output / 'ligand-canonical.json', canonical_system_json_bytes(ligand))
    write(output / 'atom-correspondence.json', correspondence)
    settings = TranslationSettings('PR59_OpenFF221_unconstrained_development_v1', 100.0, 90.0)
    try:
        convert_openmm_system((PR59 / 'openmm-system.xml').read_bytes(), ligand, settings)
    except OpenMMD3TranslationError as error:
        original_rejection = {'status': 'rejected', 'code': error.code, 'reason': str(error),
                              'source': reference(PR59 / 'openmm-system.xml')}
    else:
        raise ValueError('original_constrained_system_unexpectedly_admitted')
    require(original_rejection['code'] == 'constrained_bond_terms_missing', 'unexpected_original_constraint_rejection')
    write(output / 'original-constrained-rejection.json', original_rejection)
    xml, difference = regenerate_unconstrained(pr49, molecule, output)
    conversion = convert_openmm_system(xml, ligand, settings)
    parameters_ref = write(output / 'parameters.json', conversion.base_parameters.to_dict())
    extensions_ref = write(output / 'extensions.json', conversion.parameters.to_dict())
    write(output / 'translation-inventory.json', conversion.inventory)
    cross = deepcopy(old_cross)
    cross.update(ligand_topology_sha256=canonical_topology_sha256(ligand),
                 ligand_base_parameters_sha256=conversion.base_parameters.fingerprint_sha256)
    cross_ref = write(output / 'cross_parameters.json', cross)
    new_request = deepcopy(request)
    new_request.update(ligand=ligand_ref, parameters=parameters_ref, extensions=extensions_ref, cross_parameters=cross_ref)
    request_binding(new_request)
    request_ref = write(output / 'request.json', new_request)
    origin = {'schema_version': binding.CHARGE_ORIGIN_SCHEMA,
        'openmm_system': reference(output / 'ligand-unconstrained-openmm-system.xml'),
        'ligand_source_sha256': ligand_ref['sha256'], 'ligand_system_sha256': canonical_system_sha256(ligand),
        'atom_mapping': [{'particle_index': i, 'ligand_atom_index': i, 'atom_name': atom.name,
            'element': atom.element, 'atomic_number': atom.atomic_number,
            'isotope_mass_number': atom.isotope_mass_number, 'formal_charge': atom.formal_charge}
            for i, atom in enumerate(ligand.atoms)]}
    origin_ref = write(output / 'charge-origin.json', origin)
    identity = chemical_identity(projection['rows']['PR59']['source_graph']['canonical_isomeric_smiles'])
    FixedReceptorEnvironment(receptor, CrossParameters.from_dict(cross)).validate_ligand(ligand, conversion.base_parameters)
    component_results = {}
    for name, function, arguments in (
        ('source_graph_identity', binding._ligand_identity, (ligand, identity)),
        ('xml_decimal_charge_representation', binding._charge_screen, (origin_ref, new_request, ligand, conversion.base_parameters)),
        ('registered_geometry', binding._pose_geometry_status, (receptor, ligand, new_request))):
        try:
            component_results[name] = {'status': 'passed', 'observation': function(*arguments)}
        except ValueError as error:
            component_results[name] = {'status': 'blocked', 'reason': str(error)}
    component_results['parameters_extensions_cross_metadata'] = {'status': 'passed'}
    write(output / 'component-checks.json', component_results)
    for ref in source_refs.values():
        bound(ref)
    report = {'schema_id': 'pr59_common_frame_development_preparation/1',
        'status': 'components_passed' if all(r['status'] == 'passed' for r in component_results.values()) else 'component_blocked',
        'candidate_id': 'PR59', 'request': request_ref, 'charge_origin': origin_ref,
        'atom_count': ligand.atom_count, 'heavy_atom_count': 26, 'bond_count': len(ligand.bonds),
        'aromatic_atom_count': sum(a.GetIsAromatic() for a in perceived.GetAtoms()),
        'aromatic_bond_count': sum(b.GetIsAromatic() for b in perceived.GetBonds()),
        'original_constraint_count': difference['original_constraint_count'], 'new_constraint_count': 0,
        'original_constrained_model_rejected': original_rejection,
        'same_pr49_receptor_pocket_frame_solver': True, 'same_pr49_cross_formula_and_receptor_parameters': True,
        'same_pr49_frozen_initial_pose_protocol': True,
        'geometry_search_wall_seconds': registration['search_wall_seconds'],
        'geometry_attempt_count': len(registration['attempts']), 'selected_ordinal': registration['selected_ordinal'],
        'whole_preparation_wall_seconds': time.perf_counter() - start,
        'component_results': component_results, 'original_input_pins_unchanged': True,
        'force_calls': 0, 'score_calls': 0, 'fit_calls': 0,
        'source_roles_assigned': False, 'native_source_admission': False,
        'assayed_microstate_equivalence_verified': False, 'observed_PR59_pose_available': False,
        'affinity_or_pose_recovery_or_HIP_or_service_validated': False,
        'constrained_dynamics_equivalence_claimed': False,
        'runtime_versions': {'python': sys.version, 'numpy': np.__version__,
            'scipy': __import__('scipy').__version__, 'rdkit': __import__('rdkit').__version__,
            'openmm': __import__('openmm').__version__},
        'files': {p.name: {'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size}
                  for p in sorted(output.iterdir())}}
    write(output / 'manifest.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    result = build(args.output.resolve(), args.workspace.resolve())
    print(json.dumps({key: result[key] for key in ('status', 'atom_count', 'bond_count', 'geometry_attempt_count')}, sort_keys=True))


if __name__ == '__main__':
    main()
