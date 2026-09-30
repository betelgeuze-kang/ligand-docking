"""Source-bound chemistry transfer for explicitly prepared standard protein residues.

This bounded adapter does not prepare proteins, choose protonation states, repair
connectivity, infer integer charge from partial charge, or change coordinates.
The caller supplies the exact AMBER microstate and any atom-name alias. Embedded
CCD chemistry supplies a fixed Kekule/resonance representation. Unknown or
inconsistent atom, bond, microstate and valence declarations are rejected.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import math
import xml.etree.ElementTree as ET

ALGORITHM = 'source_bound_standard_protein_chemical_graph_v1'
_STANDARD = frozenset('ALA ARG ASN ASP CYS GLN GLU GLY ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL HIE CYX'.split())
_CHARGES = {'ARG': {'NH2': 1}, 'LYS': {'NZ': 1}, 'ASP': {'OD2': -1}, 'GLU': {'OE2': -1}}
_NET = {'ARG': 1, 'LYS': 1, 'ASP': -1, 'GLU': -1}
_VALENCE = {('H', 0): 1, ('C', 0): 4, ('N', 0): 3, ('N', 1): 4,
            ('O', 0): 2, ('O', -1): 1, ('S', 0): 2}


class ReceptorChemicalGraphError(ValueError):
    """Fail-closed chemical-source or graph validation error."""


def _require(condition, code):
    if not condition:
        raise ReceptorChemicalGraphError(code)


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _pair(a, b):
    return tuple(sorted((a, b)))


def _float(value):
    _require(isinstance(value, dict) and set(value) == {'$float_hex'}, 'NON_CANONICAL_FLOAT')
    result = float.fromhex(value['$float_hex'])
    _require(math.isfinite(result), 'NONFINITE_CANONICAL_FLOAT')
    return result


def _ccd(cif_bytes):
    from betelgeuze_engine_v2.molecular.mmcif_syntax import parse_cif_block
    block = parse_cif_block(cif_bytes.decode())
    atoms, bonds = {}, {}
    for loop in block.loops:
        if '_chem_comp_atom.comp_id' in loop.tags:
            for row in loop.rows:
                r = dict(zip(loop.tags, (t.value for t in row)))
                key = (r['_chem_comp_atom.comp_id'], r['_chem_comp_atom.atom_id'])
                flag = r['_chem_comp_atom.pdbx_aromatic_flag']
                _require(key not in atoms and flag in ('Y', 'N'), 'AMBIGUOUS_CCD_ATOM')
                atoms[key] = (r['_chem_comp_atom.type_symbol'], flag == 'Y')
        if '_chem_comp_bond.comp_id' in loop.tags:
            for row in loop.rows:
                r = dict(zip(loop.tags, (t.value for t in row)))
                key = (r['_chem_comp_bond.comp_id'], _pair(r['_chem_comp_bond.atom_id_1'], r['_chem_comp_bond.atom_id_2']))
                order = r['_chem_comp_bond.value_order'].upper()
                flag = r['_chem_comp_bond.pdbx_aromatic_flag']
                _require(key not in bonds and order in ('SING', 'DOUB', 'TRIP') and flag in ('Y', 'N'), 'AMBIGUOUS_CCD_BOND')
                bonds[key] = ({'SING': 1, 'DOUB': 2, 'TRIP': 3}[order], flag == 'Y')
    _require(bool(atoms) and bool(bonds), 'MISSING_CCD_CHEMISTRY')
    return atoms, bonds


def _amber(xml_bytes):
    root = ET.fromstring(xml_bytes)
    types = {r.attrib['name']: r.attrib['element'] for r in root.findall('./AtomTypes/Type')}
    templates = {}
    for r in root.findall('./Residues/Residue'):
        name = r.attrib['name']
        _require(name not in templates, 'DUPLICATE_AMBER_TEMPLATE')
        atoms = {a.attrib['name']: {'element': types[a.attrib['type']], 'partial_charge_hex': float(a.attrib['charge']).hex()}
                 for a in r.findall('Atom')}
        _require(len(atoms) == len(r.findall('Atom')), 'DUPLICATE_AMBER_ATOM')
        bonds = {_pair(b.attrib['atomName1'], b.attrib['atomName2']) for b in r.findall('Bond')}
        _require(len(bonds) == len(r.findall('Bond')), 'DUPLICATE_AMBER_BOND')
        external = Counter(b.attrib['atomName'] for b in r.findall('ExternalBond'))
        templates[name] = (atoms, bonds, external)
    return templates


def _template_parts(name):
    terminal = name[0] if len(name) == 4 and name[0] in ('N', 'C') else ''
    base = name[1:] if terminal else name
    _require(base in _STANDARD, 'UNSUPPORTED_AMBER_MICROSTATE:' + name)
    return base, terminal


def derive_receptor_chemical_graph(canonical_bytes, *, cif_bytes, forcefield_xml_bytes,
                                  assignments, disulfide_residue_pairs,
                                  expected_source_hashes, expected_net_charge):
    """Return new canonical bytes and a complete, deterministic derivation receipt.

    ``expected_source_hashes`` must bind ``canonical``, ``cif`` and ``forcefield``.
    Assignments cover residues exactly once and have keys ``residue_index``,
    ``amber_template``, ``atom_name_map`` (canonical name -> AMBER alias only).
    Formal charge localization is explicit: ARG NH2+, LYS NZ+, ASP OD2-, GLU
    OE2-, N-terminal N+, C-terminal OXT-. CCD bond order must satisfy that
    localization; a different resonance or histidine tautomer fails validation.
    """
    sources = {'canonical': digest(canonical_bytes), 'cif': digest(cif_bytes), 'forcefield': digest(forcefield_xml_bytes)}
    _require(set(expected_source_hashes) == set(sources), 'INCOMPLETE_SOURCE_BINDING')
    for key, observed in sources.items():
        _require(expected_source_hashes[key] == observed, 'SOURCE_HASH_MISMATCH:' + key)
    original = json.loads(canonical_bytes)
    _require(original.get('schema_id') == 'betelgeuze.engine_v2_canonical_system/1.0.0', 'UNSUPPORTED_CANONICAL_SCHEMA')
    _require(digest(json_bytes(original['system'])) == original['system_sha256'], 'CANONICAL_SYSTEM_HASH_MISMATCH')
    result = deepcopy(original)
    system = result['system']
    topology = system['topology']
    atoms, bonds, residues, chains = (topology[k] for k in ('atoms', 'bonds', 'residues', 'chains'))
    _require([a['index'] for a in atoms] == list(range(len(atoms))), 'ATOM_INDEX_COVERAGE')
    _require([r['index'] for r in residues] == list(range(len(residues))), 'RESIDUE_INDEX_COVERAGE')
    _require([b['index'] for b in bonds] == list(range(len(bonds))), 'BOND_INDEX_COVERAGE')
    _require(sorted(a for r in residues for a in r['atom_indices']) == list(range(len(atoms))), 'RESIDUE_ATOM_COVERAGE')
    _require(len(assignments) == len(residues), 'ASSIGNMENT_COVERAGE')
    by_residue = {a['residue_index']: a for a in assignments}
    _require(set(by_residue) == set(range(len(residues))), 'ASSIGNMENT_COVERAGE')
    ccd_atoms, ccd_bonds = _ccd(cif_bytes)
    templates = _amber(forcefield_xml_bytes)
    chemical_atoms, chemical_bonds, residue_rows = [], [], []
    info = {}
    for residue in residues:
        ri = residue['index']
        assignment = by_residue[ri]
        _require(set(assignment) == {'residue_index', 'amber_template', 'atom_name_map'}, 'ASSIGNMENT_FIELDS')
        template = assignment['amber_template']
        base, terminal = _template_parts(template)
        component = {'HIE': 'HIS', 'CYX': 'CYS'}.get(base, base)
        _require(residue['name'] == component, 'RESIDUE_TEMPLATE_NAME_MISMATCH')
        _require(template in templates, 'AMBER_TEMPLATE_NOT_FOUND')
        ff_atoms, ff_bonds, external = templates[template]
        indices = residue['atom_indices']
        names = {atoms[i]['name']: i for i in indices}
        _require(len(names) == len(indices), 'DUPLICATE_RESIDUE_ATOM_NAME')
        aliases = assignment['atom_name_map']
        _require(aliases in ({}, {'H': 'H1'}) and (not aliases or terminal == 'N'), 'UNSUPPORTED_ATOM_ALIAS')
        _require(set(aliases) <= set(names), 'UNUSED_ATOM_ALIAS')
        mapped = {name: aliases.get(name, name) for name in names}
        _require(set(mapped.values()) == set(ff_atoms) and len(set(mapped.values())) == len(names), 'AMBER_ATOM_COVERAGE:' + str(ri))
        chain = chains[residue['chain_index']]
        _require(chain['index'] == residue['chain_index'] and ri in chain['residue_indices'], 'CHAIN_RESIDUE_MEMBERSHIP')
        _require((terminal == 'N') == (ri == chain['residue_indices'][0]), 'N_TERMINAL_ASSIGNMENT_MISMATCH')
        _require((terminal == 'C') == (ri == chain['residue_indices'][-1]), 'C_TERMINAL_ASSIGNMENT_MISMATCH')
        local_charge = dict(_CHARGES.get(base, {}))
        if terminal == 'N':
            local_charge['N'] = 1
        if terminal == 'C':
            local_charge['OXT'] = -1
        _require(set(local_charge) <= set(names), 'FORMAL_CHARGE_ATOM_MISSING')
        for name, i in names.items():
            atom = atoms[i]
            ff_atom = ff_atoms[mapped[name]]
            _require(atom['residue_index'] == ri and atom['element'] == ff_atom['element'], 'AMBER_ATOM_IDENTITY_MISMATCH')
            _require(_float(atom['partial_charge_e']).hex() == ff_atom['partial_charge_hex'], 'AMBER_PARTIAL_CHARGE_MISMATCH:' + str(i))
            # N-terminal H3 is an explicit AMBER-only extension to embedded CCD.
            ccd = ccd_atoms.get((component, name))
            if ccd is None:
                _require(terminal == 'N' and mapped[name] in ('H1', 'H2', 'H3') and atom['element'] == 'H', 'CCD_ATOM_NOT_FOUND:' + component + ':' + name)
                aromatic = False
            else:
                _require(ccd[0] == atom['element'], 'CCD_ELEMENT_MISMATCH')
                aromatic = ccd[1]
            atom['formal_charge'] = local_charge.get(name, 0)
            atom['aromatic'] = aromatic
            chemical_atoms.append({'index': i, 'name': name, 'residue_index': ri, 'amber_template': template,
                'amber_atom_name': mapped[name], 'ccd_component': component, 'formal_charge': atom['formal_charge'], 'aromatic': aromatic})
        info[ri] = {'base': base, 'terminal': terminal, 'template': template, 'component': component,
                    'names': names, 'mapped': mapped, 'ff_bonds': ff_bonds, 'external': external}
        expected = _NET.get(base, 0) + (terminal == 'N') - (terminal == 'C')
        _require(sum(atoms[i]['formal_charge'] for i in indices) == expected, 'RESIDUE_CHARGE_MISMATCH')
        residue_rows.append({'residue_index': ri, 'chain': chain['chain_id'], 'residue_number': residue['sequence_number'],
                             'residue_name': residue['name'], 'amber_template': template, 'formal_charge': expected})
    declared_disulfides = {_pair(*pair) for pair in disulfide_residue_pairs}
    _require(len(declared_disulfides) == len(disulfide_residue_pairs), 'DUPLICATE_DISULFIDE_DECLARATION')
    observed_disulfides, internal, external, actual_edges = set(), defaultdict(set), defaultdict(Counter), set()
    valence = Counter()
    for bond in bonds:
        i, j = bond['atom_i'], bond['atom_j']
        _require(0 <= i < j < len(atoms) and (i, j) not in actual_edges, 'BOND_ENDPOINT_OR_DUPLICATE')
        actual_edges.add((i, j))
        left, right = atoms[i], atoms[j]
        ri, rj = left['residue_index'], right['residue_index']
        li, rinfo = info[ri], info[rj]
        if ri == rj:
            pair = _pair(left['name'], right['name'])
            ff_pair = _pair(li['mapped'][left['name']], li['mapped'][right['name']])
            _require(ff_pair in li['ff_bonds'], 'NON_AMBER_INTERNAL_BOND')
            internal[ri].add(ff_pair)
            ccd = ccd_bonds.get((li['component'], pair))
            if ccd is None:
                _require(li['terminal'] == 'N' and set(ff_pair) in ({'N', 'H1'}, {'N', 'H2'}, {'N', 'H3'}), 'CCD_BOND_NOT_FOUND')
                order, aromatic, origin = 1, False, 'explicit_AMBER_N_terminal_hydrogen'
            else:
                order, aromatic = ccd
                origin = 'embedded_CCD_Kekule'
        else:
            external[ri][li['mapped'][left['name']]] += 1
            external[rj][rinfo['mapped'][right['name']]] += 1
            if left['name'] == right['name'] == 'SG':
                _require(li['base'] == rinfo['base'] == 'CYX' and _pair(ri, rj) in declared_disulfides, 'UNDECLARED_DISULFIDE')
                observed_disulfides.add(_pair(ri, rj))
                origin = 'explicit_AMBER_CYX_disulfide'
            else:
                _require(left['name'] == 'C' and right['name'] == 'N', 'UNKNOWN_INTER_RESIDUE_BOND')
                chain = chains[residues[ri]['chain_index']]
                _require(residues[ri]['chain_index'] == residues[rj]['chain_index'] and
                         chain['residue_indices'].index(rj) == chain['residue_indices'].index(ri) + 1,
                         'NONCONSECUTIVE_PEPTIDE_BOND')
                origin = 'explicit_AMBER_peptide'
            order, aromatic = 1, False
        bond['order'] = {'$float_hex': float(order).hex()}
        bond['aromatic'] = aromatic
        _require(not aromatic or (left['aromatic'] and right['aromatic']), 'AROMATIC_BOND_ATOM_MISMATCH')
        valence[i] += order
        valence[j] += order
        chemical_bonds.append({'index': bond['index'], 'atom_i': i, 'atom_j': j, 'order': order,
                               'aromatic': aromatic, 'chemical_source': origin})
    for ri, row in info.items():
        _require(internal[ri] == row['ff_bonds'], 'AMBER_INTERNAL_BOND_COVERAGE:' + str(ri))
        _require(external[ri] == row['external'], 'AMBER_EXTERNAL_BOND_COVERAGE:' + str(ri))
    _require(observed_disulfides == declared_disulfides, 'DISULFIDE_COVERAGE')
    for atom in atoms:
        key = (atom['element'], atom['formal_charge'])
        _require(key in _VALENCE and valence[atom['index']] == _VALENCE[key],
                 'ATOM_VALENCE_MISMATCH:' + str(atom['index']) + ':' + atom['name'])
    net_charge = sum(a['formal_charge'] for a in atoms)
    _require(type(expected_net_charge) is int and net_charge == expected_net_charge, 'WHOLE_SYSTEM_CHARGE_MISMATCH')
    graph = {'schema_id': ALGORITHM, 'atoms': chemical_atoms, 'bonds': chemical_bonds,
             'residue_microstates': residue_rows, 'disulfide_residue_pairs': sorted(declared_disulfides)}
    lineage = {'algorithm': ALGORITHM, 'parent_canonical_file_sha256': sources['canonical'],
        'parent_canonical_system_sha256': original['system_sha256'], 'source_hashes': sources,
        'assignments_sha256': digest(json_bytes(assignments)), 'chemical_graph_sha256': digest(json_bytes(graph)),
        'formal_charge_method': 'explicit_declared_AMBER_microstates_not_partial_charge_rounding',
        'resonance_convention': 'embedded_CCD_integer_Kekule_ARG_NH2_positive_ASP_OD2_negative_GLU_OE2_negative_terminal_OXT_negative',
        'histidine_convention': 'HIE_only_NE2_H_neutral_ND1_unprotonated_CCD_Kekule_required_by_valence',
        'scope': 'source_bound_chemical_graph_only_not_scientific_or_product_qualification'}
    provenance = system['provenance']
    provenance['parent_sha256'] = list(dict.fromkeys([*provenance.get('parent_sha256', []), original['system_sha256']]))
    provenance['operations'] = [*provenance.get('operations', []), ALGORITHM]
    provenance.setdefault('metadata', {})['receptor_chemical_graph'] = lineage
    provenance['scientifically_validated'] = False
    provenance['product_qualified'] = False
    # Keep the original preparation and source-annotation metadata unchanged.
    # Prove that every field outside the explicitly permitted chemistry/lineage
    # fields, including every encoded float token and LJ record, is identical.
    before = deepcopy(original['system'])
    after = deepcopy(system)
    for view in (before, after):
        view.pop('provenance')
        for atom in view['topology']['atoms']:
            atom.pop('formal_charge'); atom.pop('aromatic')
        for bond in view['topology']['bonds']:
            bond.pop('order'); bond.pop('aromatic')
    _require(json_bytes(before) == json_bytes(after), 'IMMUTABLE_FIELD_CHANGED')
    result['system_sha256'] = digest(json_bytes(system))
    output = json_bytes(result)
    receipt = {'schema_id': ALGORITHM + '_receipt', 'status': 'SOURCE_BOUND_CHEMICAL_GRAPH_VALIDATED_RESEARCH_ONLY',
        'lineage': lineage, 'derived_canonical_file_sha256': digest(output), 'derived_canonical_system_sha256': result['system_sha256'],
        'atom_count': len(atoms), 'bond_count': len(bonds), 'residue_count': len(residues), 'formal_charge_sum': net_charge,
        'bond_order_counts': dict(sorted(Counter(str(_float(b['order'])) for b in bonds).items())),
        'aromatic_atoms': sum(a['aromatic'] for a in atoms), 'aromatic_bonds': sum(b['aromatic'] for b in bonds),
        'validation': {'all_atom_valences': True, 'all_residue_charges': True, 'whole_system_charge': True,
            'complete_AMBER_atom_and_adjacency_mapping': True, 'AMBER_partial_charge_hex_match': True,
            'all_nonchemical_fields_exact': True, 'coordinate_mass_partial_charge_LJ_hex_preserved': True,
            'source_annotation_metadata_preserved': True}, 'chemical_graph': graph}
    return output, receipt
