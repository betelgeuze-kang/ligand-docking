"""Independent synthetic structural records; no builder or molecular evaluations."""
from collections import Counter
import copy
import hashlib
import json
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from docs.research.human_5ht6_sro_numerical_preparation import verify_sro as verifier


HEAVY = ("OH", "CZ3", "CH2", "CZ2", "CE2", "NE1", "CD1", "CG", "CD2", "CE3", "CB", "CA", "NZ")
HEAVY_BONDS = (("OH", "CZ3", 1, False), ("CZ3", "CE3", 2, True), ("CZ3", "CH2", 1, True),
    ("CH2", "CZ2", 2, True), ("CZ2", "CE2", 1, True), ("CE2", "NE1", 1, True),
    ("CE2", "CD2", 2, True), ("NE1", "CD1", 1, True), ("CD1", "CG", 2, True),
    ("CG", "CB", 1, False), ("CG", "CD2", 1, True), ("CD2", "CE3", 1, True),
    ("CB", "CA", 1, False), ("CA", "NZ", 1, False))
PARENTS = {"HOH": "OH", "HH2": "CH2", "HZ2": "CZ2", "HNE1": "NE1", "HD1": "CD1", "HE3": "CE3",
           "HB1": "CB", "HB2": "CB", "HA1": "CA", "HA2": "CA", "HNZ1": "NZ", "HNZ2": "NZ", "HNZ3": "NZ"}


def fixture():
    names = [*HEAVY, *PARENTS]
    aromatic_names = {name for pair in HEAVY_BONDS if pair[3] for name in pair[:2]}
    elements = {name: "H" if name in PARENTS else "O" if name == "OH" else "N" if name in ("NZ", "NE1") else "C"
                for name in names}
    component = {name: {"comp_id": "SRO", "atom_id": name, "type_symbol": elements[name],
                        "pdbx_aromatic_flag": "Y" if name in aromatic_names else "N"}
                 for name in names if name != "HNZ3"}
    xyz = np.array([[float(10 + i), 20., 30.] for i in range(13)]
                   + [[float(10 + HEAVY.index(parent)), 21., 30.] for parent in PARENTS.values()])
    observed = [{"id": str(8089 + i), "label_atom_id": name, "type_symbol": elements[name],
                 "cartn_x": str(xyz[i, 0]), "cartn_y": str(xyz[i, 1]), "cartn_z": str(xyz[i, 2])}
                for i, name in enumerate(HEAVY)]
    source_bonds = [{"comp_id": "SRO", "atom_id_1": a, "atom_id_2": b,
                     "value_order": "sing" if order == 1 else "doub", "pdbx_aromatic_flag": "Y" if aromatic else "N"}
                    for a, b, order, aromatic in HEAVY_BONDS]
    source_bonds += [{"comp_id": "SRO", "atom_id_1": parent, "atom_id_2": name,
                      "value_order": "sing", "pdbx_aromatic_flag": "N"} for name, parent in PARENTS.items() if name != "HNZ3"]
    source = {"observed": observed, "component_atoms": component, "component_bonds": source_bonds,
              "heavy_bonds": {tuple(sorted((a, b))): {"order": float(order), "aromatic": aromatic}
                              for a, b, order, aromatic in HEAVY_BONDS}, "hydrogen_parents": PARENTS}
    counts, atoms, provenance = Counter(), [], []
    for index, name in enumerate(names):
        element = elements[name]
        counts[element] += 1
        atoms.append({"index": index, "name": name, "element": element,
                      "atomic_number": {"H": 1, "C": 6, "N": 7, "O": 8}[element],
                      "formal_charge": int(name == "NZ"), "partial_charge_e": float(name == "NZ"),
                      "mass_da": {"H": 1., "C": 12., "N": 14., "O": 16.}[element], "aromatic": name in aromatic_names})
        parent = None if index < 13 else PARENTS[name]
        provenance.append({"index_zero_based": index, "name": name, "reader_atom_name": element + str(counts[element]),
            "element": element, "origin": "observed_source_heavy" if index < 13 else "generated_hydrogen",
            "source_atom_site_id": str(8089 + index) if index < 13 else None,
            "source_component_atom_name": None if name == "HNZ3" else name,
            "parent_index_zero_based": None if parent is None else names.index(parent), "parent_name": parent,
            "coordinates_angstrom": xyz[index].tolist(), "source_coordinates_decimal": [str(x) for x in xyz[index]] if index < 13 else None,
            "formal_charge": int(name == "NZ"), "aromatic": name in aromatic_names,
            "hydrogen_method_protocol_key": None if index < 13 else "generated_hydrogens_method"})
    mapped = []
    for row in source_bonds:
        i, j = sorted((names.index(row["atom_id_1"]), names.index(row["atom_id_2"])))
        mapped.append({"atom_i": i, "atom_j": j, "order": 1. if row["value_order"] == "sing" else 2.,
                       "aromatic": row["pdbx_aromatic_flag"] == "Y", "source_component_bond": row})
    mapped.append({"atom_i": 12, "atom_j": 25, "order": 1., "aromatic": False, "source_component_bond": None})
    mapped.sort(key=lambda row: (row["atom_i"], row["atom_j"]))
    bonds = [{"index": i, **{key: row[key] for key in ("atom_i", "atom_j", "order", "aromatic")}}
             for i, row in enumerate(mapped)]
    system = {"topology": {"atoms": atoms, "bonds": bonds, "coordinate_unit": "angstrom"},
              "coordinates": {"coordinate_unit": "angstrom", "coordinates": xyz[None]},
              "provenance": {"scientifically_validated": False, "product_qualified": False}}
    return system, {"atoms": provenance, "bonds": mapped}, source


def formats(system, provenance):
    atoms, bonds = system["topology"]["atoms"], system["topology"]["bonds"]
    xyz = system["coordinates"]["coordinates"][0]
    sdf = ["synthetic arithmetic fixture", "", "", f'{26:3d}{27:3d}  0  0  0  0            999 V2000']
    for atom, point in zip(atoms, xyz, strict=True):
        sdf.append(''.join(f'{value:10.4f}' for value in point) + f' {atom["element"]:<3} 0  0  0  0  0  0  0  0  0  0  0  0')
    for bond in bonds:
        sdf.append(f'{bond["atom_i"]+1:3d}{bond["atom_j"]+1:3d}{int(bond["order"]):3d}  0  0  0  0')
    sdf += ["M  CHG  1  13   1", "M  END", "$$$$"]
    gro = ["synthetic fixture", "26"]
    for i, (row, point) in enumerate(zip(provenance["atoms"], xyz, strict=True)):
        gro.append(f'{1:5d}{"SRO":<5}{row["reader_atom_name"]:>5}{i+1:5d}' + ''.join(f'{x/10:15.10f}' for x in point))
    gro.append('10 10 10')
    return ('\n'.join(sdf) + '\n').encode(), ('\n'.join(gro) + '\n').encode()


def parameter_fixture(system, provenance):
    root = ET.Element('System')
    particles = ET.SubElement(root, 'Particles')
    forces = ET.SubElement(root, 'Forces')
    nb = ET.SubElement(forces, 'Force', type='NonbondedForce')
    nb_particles = ET.SubElement(nb, 'Particles')
    bonds = ET.SubElement(ET.SubElement(forces, 'Force', type='HarmonicBondForce'), 'Bonds')
    angles = ET.SubElement(ET.SubElement(forces, 'Force', type='HarmonicAngleForce'), 'Angles')
    torsions = ET.SubElement(ET.SubElement(forces, 'Force', type='PeriodicTorsionForce'), 'Torsions')
    adjacent = {i: set() for i in range(26)}
    for row in system['topology']['bonds']:
        i, j = row['atom_i'], row['atom_j']
        adjacent[i].add(j)
        adjacent[j].add(i)
        ET.SubElement(bonds, 'Bond', p1=str(i), p2=str(j), d='.1', k='100')
    for center, neighbors in adjacent.items():
        for i in sorted(neighbors):
            for j in sorted(neighbors):
                if i < j:
                    ET.SubElement(angles, 'Angle', p1=str(i), p2=str(center), p3=str(j), a='1.9', k='20')
    ET.SubElement(torsions, 'Torsion', p1='0', p2='1', p3='2', p4='3', k='-2', periodicity='2', phase='0')
    itp, types, reader = ['[ atoms ]'], ['[ atomtypes ]'], []
    for i, atom in enumerate(system['topology']['atoms']):
        q, mass = atom['partial_charge_e'], atom['mass_da']
        ET.SubElement(particles, 'Particle', mass=str(mass))
        ET.SubElement(nb_particles, 'Particle', q=str(q), sig='.3', eps='.4184')
        name = provenance['atoms'][i]['reader_atom_name']
        itp.append(f'{i+1} X{i} 1 SRO {name} {i+1} {q} {mass}')
        types.append(f'X{i} {atom["atomic_number"]} {mass} 0 A .3 .4184')
        reader.append({'atom_index': i, 'charge_e': q, 'sigma_angstrom': 3., 'epsilon_kcal_per_mol': .1})
    itp.append('[ bonds ]')
    itp += [f'{row["atom_i"]+1} {row["atom_j"]+1} 1' for row in system['topology']['bonds']]
    return root, ('\n'.join(itp)+'\n').encode(), ('\n'.join(types)+'\n').encode(), {'ligand': reader}


def test_manual_structure_and_three_formats_are_consistent_without_physics():
    system, provenance, source = fixture()
    checked = verifier.verify_structure(system, provenance, source)
    assert checked['heavy_atoms_exact'] == 13 and checked['generated_hydrogens'] == 13
    assert checked['formal_charge'] == checked['partial_charge_sum'] == 1
    sdf, gro = formats(system, provenance)
    assert verifier.verify_coordinate_formats(system, provenance, sdf, gro)['sdf_bonds'] == 27


@pytest.mark.parametrize('change,reason', [
    ('heavy_coordinate', 'source_heavy_coordinates_changed'), ('wrong_charge_site', 'formal_charge_not_NZ'),
    ('extra_hydrogen', 'prepared_atom_or_bond_count'), ('aromaticity', 'atom_aromaticity_mismatch'),
    ('bond_order', 'source_graph_or_hydrogen_parent_changed'), ('hydrogen_parent', 'generated_hydrogen_provenance_mismatch'),
    ('invented_hydrogen_observation', 'generated_hydrogen_provenance_mismatch'), ('charge_sum', 'partial_charge_total'),
    ('method_missing', 'hydrogen_method_provenance'), ('scientific_claim', 'unsupported_qualification'),
])
def test_structural_tampering_is_rejected(change, reason):
    system, provenance, source = fixture()
    atoms = system['topology']['atoms']
    if change == 'heavy_coordinate':
        system['coordinates']['coordinates'][0, 0, 0] += .0001
        provenance['atoms'][0]['coordinates_angstrom'][0] += .0001
    elif change == 'wrong_charge_site':
        atoms[12]['formal_charge'], atoms[5]['formal_charge'] = 0, 1
    elif change == 'extra_hydrogen':
        atoms.append(copy.deepcopy(atoms[-1]))
    elif change == 'aromaticity':
        atoms[5]['aromatic'] = False
    elif change == 'bond_order':
        system['topology']['bonds'][0]['order'] = 2.
    elif change == 'hydrogen_parent':
        provenance['atoms'][-1]['parent_name'] = 'OH'
    elif change == 'invented_hydrogen_observation':
        provenance['atoms'][-1]['source_atom_site_id'] = '8102'
    elif change == 'charge_sum':
        atoms[-1]['partial_charge_e'] = .01
    elif change == 'method_missing':
        provenance['atoms'][-1]['hydrogen_method_protocol_key'] = None
    else:
        system['provenance']['scientifically_validated'] = True
    with pytest.raises(verifier.PreparationVerificationError, match=reason):
        verifier.verify_structure(system, provenance, source)


@pytest.mark.parametrize('format_name', ['sdf', 'gro'])
def test_coordinate_roundtrip_rejects_a_small_source_frame_change(format_name):
    system, provenance, _ = fixture()
    sdf, gro = formats(system, provenance)
    if format_name == 'sdf':
        sdf = sdf.replace(b'   10.0000', b'   10.0001', 1)
    else:
        gro = gro.replace(b'   1.0000000000', b'   1.0000000001', 1)
    with pytest.raises(verifier.PreparationVerificationError, match='coordinate_roundtrip'):
        verifier.verify_coordinate_formats(system, provenance, sdf, gro)


def test_supported_signed_torsion_and_unit_projection_are_checked_without_energy():
    system, provenance, _ = fixture()
    xml, itp, types, reader = parameter_fixture(system, provenance)
    result = verifier.verify_parameters(system, provenance, ET.tostring(xml), itp, types, reader)
    assert result['signed_negative_torsion_terms'] == 1 and result['angles'] == 46
    assert 'not_full_bonded' in result['itp_scope']


@pytest.mark.parametrize('change,reason', [
    ('constraint', 'unconstrained_26'), ('unknown_force', 'unsupported_or_missing_force'),
    ('missing_bond', 'xml_bond_coverage'), ('missing_angle', 'xml_angle_coverage'),
    ('wrong_charge', 'xml_charge_projection'), ('reader_units', 'reader_nonbonded_unit_projection'),
    ('invalid_torsion', 'xml_torsion_graph'), ('nonfinite', 'nonfinite'),
])
def test_parameter_projection_tampering_is_rejected(change, reason):
    system, provenance, _ = fixture()
    xml, itp, types, reader = parameter_fixture(system, provenance)
    if change == 'constraint':
        ET.SubElement(ET.SubElement(xml, 'Constraints'), 'Constraint', p1='0', p2='1', d='.1')
    elif change == 'unknown_force':
        ET.SubElement(xml.find('Forces'), 'Force', type='CustomBondForce')
    elif change == 'missing_bond':
        bonds = xml.find('./Forces/Force[@type="HarmonicBondForce"]/Bonds')
        bonds.remove(bonds[0])
    elif change == 'missing_angle':
        angles = xml.find('./Forces/Force[@type="HarmonicAngleForce"]/Angles')
        angles.remove(angles[0])
    elif change == 'wrong_charge':
        nb = xml.find('./Forces/Force[@type="NonbondedForce"]/Particles')
        nb[12].set('q', '0')
        nb[5].set('q', '1')
    elif change == 'reader_units':
        reader['ligand'][0]['sigma_angstrom'] = .3
    elif change == 'invalid_torsion':
        torsion = xml.find('./Forces/Force[@type="PeriodicTorsionForce"]/Torsions/Torsion')
        torsion.set('p4', '25')
    else:
        reader['ligand'][0]['epsilon_kcal_per_mol'] = float('nan')
    with pytest.raises(verifier.PreparationVerificationError, match=reason):
        verifier.verify_parameters(system, provenance, ET.tostring(xml), itp, types, reader)


def test_canonical_hash_is_checked_independently_of_a_product_loader():
    payload = {'coordinates': {'$tensor': {'shape': [1, 1, 3], 'dtype': 'float64',
                'values': [{'$float_hex': value.hex()} for value in (1., 2., 3.)]}}}
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    document = {'schema_id': 'betelgeuze.engine_v2_canonical_system/1.0.0', 'system': payload,
                'system_sha256': hashlib.sha256(encoded).hexdigest()}
    system, _ = verifier.parse_canonical(json.dumps(document).encode())
    np.testing.assert_array_equal(system['coordinates'], [[[1., 2., 3.]]])
    document['system']['coordinates']['$tensor']['values'][0]['$float_hex'] = (1.1).hex()
    with pytest.raises(verifier.PreparationVerificationError, match='canonical_system_digest'):
        verifier.parse_canonical(json.dumps(document).encode())


def test_forcefield_derivation_only_permits_constraint_removal_and_unit_factor_reordering():
    original = b'<SMIRNOFF><Constraints/><Bonds><Bond smirks="X" k="2 * mole ** -1 * kilocalorie ** 1"/></Bonds></SMIRNOFF>'
    derived = b'<SMIRNOFF><Bonds><Bond smirks="X" k="2 * kilocalorie ** 1 * mole ** -1"/></Bonds></SMIRNOFF>'
    assert verifier.verify_forcefield_derivation(original, derived)['parameter_values_and_smirks_preserved']
    with pytest.raises(verifier.PreparationVerificationError, match='forcefield_changed_beyond_constraints'):
        verifier.verify_forcefield_derivation(original, derived.replace(b'k="2 ', b'k="3 '))


def test_duplicate_json_keys_cannot_shadow_provenance():
    with pytest.raises(verifier.PreparationVerificationError, match='duplicate_json_key'):
        verifier.parse_canonical(b'{"schema_id":"a","schema_id":"b"}')


def test_three_name_domains_require_explicit_same_index_binding():
    system, provenance, _ = fixture()
    reader = copy.deepcopy(system)
    for index, atom in enumerate(reader['topology']['atoms']):
        atom['name'] = atom['element'] + str(index + 1)
        atom['metadata'] = {'prepared_gromacs_source': {
            'atom_name': provenance['atoms'][index]['reader_atom_name'],
            'canonical_atom_name': atom['name'], 'canonical_atom_index': index,
            'source_atom_index': index + 1}}
    assert verifier.verify_reader_binding(system, reader, provenance)['explicit_atom_aliases_checked'] == 26
    # The first carbon is C1 in GRO/ITP, C2 in the raw reader, and CZ3 in source.
    assert provenance['atoms'][1]['reader_atom_name'] == 'C1'
    assert reader['topology']['atoms'][1]['name'] == 'C2'
    assert system['topology']['atoms'][1]['name'] == 'CZ3'
    reader['topology']['atoms'][1]['metadata']['prepared_gromacs_source']['source_atom_index'] = 3
    with pytest.raises(verifier.PreparationVerificationError, match='reader_alias_binding'):
        verifier.verify_reader_binding(system, reader, provenance)


def protocol_fixture():
    state = {'formal_charge_site': 'NZ', 'formal_charge_e': 1, 'formula': 'C10H13N2O+',
             'atom_count': 26, 'heavy_atom_count': 13, 'hydrogen_count': 13,
             'terminal_amine_hydrogen_count': 3, 'indole_NH_retained': True, 'phenol_OH_retained': True,
             'selection': 'single_predeclared_computational_assumption',
             'experimentally_measured_bound_protonation': None, 'assay_chemical_state': None}
    authority = {name: False for name in ('training_admitted', 'calibration_admitted',
        'independent_evaluation_admitted', 'pose_recovery_admitted', 'scientifically_validated',
        'product_qualified', 'protected_context_read', 'experimental_Ki_used', 'independent_pose_recovery_claimed')}
    authority.update(numerical_development_only=True, reserved_source_role_unchanged=True)
    frame = '7XTB_original_cartesian_angstrom_development'
    protocol = {'computational_microstate': copy.deepcopy(state), 'source': {
        'deposited_em_buffer_pH': '7.4', 'atom_site_formal_charge_token': '?',
        'component_atom_charge_column_present': False, 'pH_determines_observed_microstate': False},
        'generated_hydrogens_method': 'RDKit Chem.AddHs(addCoords=True); no embedding or optimization; quantize H only to 0.0001 angstrom',
        'state_or_pose_selected_using_energy_force_or_score': False,
        'preparation_force_energy_minimization_evaluations': 0, 'coordinate_frame_id': frame,
        'authority': copy.deepcopy(authority)}
    manifest = {'computational_microstate': state, 'source_deposited_em_buffer_pH': '7.4',
        'source_bound_protonation_known': False, 'source_assay_chemical_state_known': False,
        'force_energy_minimization_evaluations': 0, 'coordinate_frame_id': frame, 'scientific_authority': authority}
    return protocol, manifest


def test_buffer_ph_does_not_establish_bound_microstate_or_assay_state():
    protocol, manifest = protocol_fixture()
    result = verifier.verify_protocol(protocol, manifest)
    assert result['deposited_em_buffer_pH'] == '7.4'
    assert result['bound_ligand_protonation_known'] is False


@pytest.mark.parametrize('change,reason', [
    ('ph_inference', 'source_unknowns_conflated'), ('assay_known', 'manifest_source_state_claim'),
    ('scientific_claim', 'unsupported_authority'), ('force_selected', 'unexpected_preparation_evaluation_claim')])
def test_preparation_metadata_cannot_promote_computational_assumptions(change, reason):
    protocol, manifest = protocol_fixture()
    if change == 'ph_inference':
        protocol['source']['pH_determines_observed_microstate'] = True
    elif change == 'assay_known':
        manifest['source_assay_chemical_state_known'] = True
    elif change == 'scientific_claim':
        protocol['authority']['scientifically_validated'] = True
        manifest['scientific_authority']['scientifically_validated'] = True
    else:
        protocol['state_or_pose_selected_using_energy_force_or_score'] = True
    with pytest.raises(verifier.PreparationVerificationError, match=reason):
        verifier.verify_protocol(protocol, manifest)
