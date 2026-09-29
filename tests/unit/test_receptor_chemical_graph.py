"""Charge/tautomer/source rejection against pinned public chemistry subsets."""
from copy import deepcopy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from tools.product.receptor_chemical_graph import (
    ReceptorChemicalGraphError, derive_receptor_chemical_graph, digest, json_bytes,
)

FIXTURE = Path(__file__).parents[1] / 'fixtures/receptor_chemical_graph/standard_residue_sources.json'


def _f(value):
    return {'$float_hex': float(value).hex()}


@pytest.fixture
def case():
    source = json.loads(FIXTURE.read_text())
    xml = ET.fromstring(source['forcefield_xml'])
    templates = {r.attrib['name']: r for r in xml.findall('./Residues/Residue')}
    elements = {r.attrib['name']: r.attrib['element'] for r in xml.findall('./AtomTypes/Type')}
    sequence = 'NGLY ARG ASP GLU LYS HIE CYX TRP CYS CYX CPRO'.split()
    atoms, residues, assignments, edges, names = [], [], [], [], []
    for ri, template in enumerate(sequence):
        row = templates[template]
        indices, mapping = [], {}
        for atom in row.findall('Atom'):
            name = atom.attrib['name']
            canonical_name = 'H' if name == 'H1' else name
            i = len(atoms)
            element = elements[atom.attrib['type']]
            atoms.append({'index': i, 'name': canonical_name, 'element': element,
                'atomic_number': {'H': 1, 'C': 6, 'N': 7, 'O': 8, 'S': 16}[element], 'residue_index': ri,
                'partial_charge_e': _f(atom.attrib['charge']), 'mass_da': _f(1 if element == 'H' else 12),
                'formal_charge': 0, 'aromatic': False, 'stereo': 'unspecified',
                'metadata': {'synthetic_LJ': {'sigma': _f(0.3141592653589793)}, 'original_annotation': 'missing'}})
            indices.append(i); mapping[name] = i
        base = template[1:] if len(template) == 4 else template
        residues.append({'index': ri, 'chain_index': 0, 'name': {'HIE': 'HIS', 'CYX': 'CYS'}.get(base, base),
                         'sequence_number': ri + 1, 'atom_indices': indices})
        names.append(mapping)
        assignments.append({'residue_index': ri, 'amber_template': template,
                            'atom_name_map': {'H': 'H1'} if template.startswith('N') else {}})
        edges.extend(tuple(sorted((mapping[b.attrib['atomName1']], mapping[b.attrib['atomName2']]))) for b in row.findall('Bond'))
        if ri:
            edges.append((names[ri - 1]['C'], mapping['N']))
    edges.append((names[6]['SG'], names[9]['SG']))
    bonds = [{'index': i, 'atom_i': a, 'atom_j': b, 'order': _f(1), 'aromatic': False, 'metadata': {'unchanged': True}}
             for i, (a, b) in enumerate(sorted(edges))]
    system = {'topology': {'atoms': atoms, 'bonds': bonds, 'residues': residues,
                          'chains': [{'index': 0, 'chain_id': 'A', 'residue_indices': list(range(len(sequence)))}]},
              'coordinates': {'coordinates': {'$tensor': {'dtype': 'float64', 'shape': [1, len(atoms), 3],
                'values': [_f((i % 37) * 0.125) for i in range(3 * len(atoms))]}}},
              'provenance': {'operations': [], 'parent_sha256': [], 'metadata': {}}}
    document = {'schema_id': 'betelgeuze.engine_v2_canonical_system/1.0.0', 'system': system, 'system_sha256': digest(json_bytes(system))}
    return {'document': document, 'cif': source['cif'].encode(), 'ff': source['forcefield_xml'].encode(),
            'assignments': assignments, 'disulfides': [(6, 9)], 'names': names}


def _run(case, *, net=0, source_hashes=None):
    raw = json_bytes(case['document'])
    return derive_receptor_chemical_graph(raw, cif_bytes=case['cif'], forcefield_xml_bytes=case['ff'],
        assignments=case['assignments'], disulfide_residue_pairs=case['disulfides'], expected_net_charge=net,
        expected_source_hashes=source_hashes or {'canonical': digest(raw), 'cif': digest(case['cif']), 'forcefield': digest(case['ff'])})


def _rehash(case):
    case['document']['system_sha256'] = digest(json_bytes(case['document']['system']))


def test_source_bound_charge_aromaticity_and_all_immutable_tokens(case):
    original = deepcopy(case)
    raw, receipt = _run(case)
    result = json.loads(raw)
    atoms = result['system']['topology']['atoms']
    names = case['names']
    for ri, name, charge in ((0, 'N', 1), (1, 'NH2', 1), (2, 'OD2', -1), (3, 'OE2', -1),
                            (4, 'NZ', 1), (10, 'OXT', -1)):
        assert atoms[names[ri][name]]['formal_charge'] == charge
    assert atoms[names[5]['NE2']]['aromatic'] and atoms[names[5]['ND1']]['aromatic']
    assert atoms[names[7]['NE1']]['aromatic']
    assert not atoms[names[6]['SG']]['aromatic']
    assert receipt['formal_charge_sum'] == 0
    assert receipt['validation']['all_atom_valences']
    assert receipt['validation']['AMBER_partial_charge_hex_match']
    assert case == original
    before, after = deepcopy(case['document']['system']), deepcopy(result['system'])
    for system in (before, after):
        system.pop('provenance')
        for atom in system['topology']['atoms']:
            atom.pop('formal_charge'); atom.pop('aromatic')
        for bond in system['topology']['bonds']:
            bond.pop('order'); bond.pop('aromatic')
    assert json_bytes(before) == json_bytes(after)
    assert digest(json_bytes(result['system'])) == result['system_sha256']
    assert raw == _run(case)[0]


def test_chemical_assignment_is_independent_of_coordinates(case):
    _, first = _run(case)
    case['document']['system']['coordinates']['coordinates']['$tensor']['values'][0] = _f(98765.4321)
    _rehash(case)
    raw, changed = _run(case)
    assert first['lineage']['chemical_graph_sha256'] == changed['lineage']['chemical_graph_sha256']
    assert json.loads(raw)['system']['coordinates'] == case['document']['system']['coordinates']


def test_source_tampering_rejected_before_chemistry(case):
    raw = json_bytes(case['document'])
    bound = {'canonical': digest(raw), 'cif': digest(case['cif']), 'forcefield': digest(case['ff'])}
    case['cif'] += b'\n# changed\n'
    with pytest.raises(ReceptorChemicalGraphError, match='SOURCE_HASH_MISMATCH:cif'):
        _run(case, source_hashes=bound)


def test_stale_canonical_semantic_digest_rejected(case):
    case['document']['system']['topology']['atoms'][0]['formal_charge'] = 11
    with pytest.raises(ReceptorChemicalGraphError, match='CANONICAL_SYSTEM_HASH_MISMATCH'):
        _run(case)


def test_unknown_microstate_does_not_fall_back_to_residue_name(case):
    case['assignments'][5]['amber_template'] = 'HIP'
    with pytest.raises(ReceptorChemicalGraphError, match='UNSUPPORTED_AMBER_MICROSTATE'):
        _run(case)


def test_partial_charge_is_never_rebalanced_or_rounded(case):
    atom = case['document']['system']['topology']['atoms'][0]
    atom['partial_charge_e'] = _f(0.123456789)
    _rehash(case)
    with pytest.raises(ReceptorChemicalGraphError, match='AMBER_PARTIAL_CHARGE_MISMATCH'):
        _run(case)


def test_wrong_HIE_kekule_tautomer_is_rejected(case):
    # Keep ring connectivity/aromatic flags, but move the double bond onto NE2-H.
    lines = case['cif'].decode().splitlines()
    for i, line in enumerate(lines):
        if line.startswith('HIS ND1 CE1 doub '):
            lines[i] = line.replace(' doub ', ' sing ')
        if line.startswith('HIS CE1 NE2 sing '):
            lines[i] = line.replace(' sing ', ' doub ')
    case['cif'] = ('\n'.join(lines) + '\n').encode()
    with pytest.raises(ReceptorChemicalGraphError, match='ATOM_VALENCE_MISMATCH'):
        _run(case)


def test_guanidinium_resonance_must_match_formal_charge_localization(case):
    lines = case['cif'].decode().splitlines()
    for i, line in enumerate(lines):
        if line.startswith('ARG CZ NH1 sing '):
            lines[i] = line.replace(' sing ', ' doub ')
        if line.startswith('ARG CZ NH2 doub '):
            lines[i] = line.replace(' doub ', ' sing ')
    case['cif'] = ('\n'.join(lines) + '\n').encode()
    with pytest.raises(ReceptorChemicalGraphError, match='ATOM_VALENCE_MISMATCH'):
        _run(case)


def test_undeclared_disulfide_rejected(case):
    case['disulfides'] = []
    with pytest.raises(ReceptorChemicalGraphError, match='UNDECLARED_DISULFIDE'):
        _run(case)


def test_missing_internal_bond_rejected(case):
    bonds = case['document']['system']['topology']['bonds']
    bonds.pop(0)
    for index, bond in enumerate(bonds):
        bond['index'] = index
    _rehash(case)
    with pytest.raises(ReceptorChemicalGraphError, match='AMBER_INTERNAL_BOND_COVERAGE'):
        _run(case)


def test_nonconsecutive_crosslink_rejected(case):
    bonds = case['document']['system']['topology']['bonds']
    ri, rj = case['names'][0]['C'], case['names'][1]['N']
    for bond in bonds:
        if (bond['atom_i'], bond['atom_j']) == (ri, rj):
            bond['atom_j'] = case['names'][2]['N']
    _rehash(case)
    with pytest.raises(ReceptorChemicalGraphError, match='NONCONSECUTIVE_PEPTIDE_BOND'):
        _run(case)


def test_duplicate_atom_names_rejected(case):
    case['document']['system']['topology']['atoms'][1]['name'] = 'N'
    _rehash(case)
    with pytest.raises(ReceptorChemicalGraphError, match='DUPLICATE_RESIDUE_ATOM_NAME'):
        _run(case)


def test_wrong_total_charge_rejected(case):
    with pytest.raises(ReceptorChemicalGraphError, match='WHOLE_SYSTEM_CHARGE_MISMATCH'):
        _run(case, net=11)
