"""Synthetic boundary tests: no external source, charge model or force evaluation."""
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / 'docs/research/human_5ht6_sro_numerical_preparation/prepare_sro.py'
spec = importlib.util.spec_from_file_location('sro_preparer_under_test', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def source_and_mapping():
    names = 'OH CZ3 CH2 CZ2 CE2 NE1 CD1 CG CD2 CE3 CB CA NZ'.split()
    aromatic = set('CZ3 CH2 CZ2 CE2 NE1 CD1 CG CD2 CE3'.split())
    elements = {n: ('O' if n == 'OH' else 'N' if n in ('NE1', 'NZ') else 'C') for n in names}
    hp = {'HOH': 'OH', 'HH2': 'CH2', 'HZ2': 'CZ2', 'HNE1': 'NE1', 'HD1': 'CD1',
          'HE3': 'CE3', 'HB1': 'CB', 'HB2': 'CB', 'HA1': 'CA', 'HA2': 'CA', 'HNZ1': 'NZ', 'HNZ2': 'NZ'}
    edges = [('OH','CZ3',1), ('CZ3','CE3',2), ('CZ3','CH2',1), ('CH2','CZ2',2),
        ('CZ2','CE2',1), ('CE2','NE1',1), ('CE2','CD2',2), ('NE1','CD1',1),
        ('CD1','CG',2), ('CG','CB',1), ('CG','CD2',1), ('CD2','CE3',1), ('CB','CA',1), ('CA','NZ',1)]
    observed = [{'label_atom_id': n, 'type_symbol': elements[n], 'id': str(100+i),
        'label_comp_id': 'SRO', 'label_asym_id': 'F', 'label_entity_id': '6', 'auth_asym_id': 'R',
        'auth_seq_id': '501', 'pdbx_PDB_model_num': '1', 'label_alt_id': '.', 'pdbx_formal_charge': '?',
        'occupancy': '1.00', 'Cartn_x': f'{i}.125', 'Cartn_y': '2.250', 'Cartn_z': '3.500'} for i, n in enumerate(names)]
    ca = [{'atom_id': n, 'type_symbol': elements[n], 'pdbx_aromatic_flag': 'Y' if n in aromatic else 'N'} for n in names]
    ca += [{'atom_id': h, 'type_symbol': 'H', 'pdbx_aromatic_flag': 'N'} for h in hp]
    bonds = [{'atom_id_1': a, 'atom_id_2': b, 'value_order': 'sing' if order == 1 else 'doub',
        'pdbx_aromatic_flag': 'Y' if a in aromatic and b in aromatic else 'N'} for a, b, order in edges]
    bonds += [{'atom_id_1': p, 'atom_id_2': h, 'value_order': 'sing', 'pdbx_aromatic_flag': 'N'} for h, p in hp.items()]
    graph = {'observed_atoms': observed, 'component_atoms': ca, 'component_bonds': bonds, 'deposited_em_buffer_pH': ['7.4']}
    hp['HNZ3'] = 'NZ'
    all_names = names + list(hp)
    atoms = []
    for i, n in enumerate(all_names):
        row = observed[i] if i < 13 else None
        atoms.append({'index_zero_based': i, 'name': n, 'reader_atom_name': f'X{i+1}',
            'element': elements[n] if row else 'H', 'formal_charge': 1 if n == 'NZ' else 0,
            'aromatic': n in aromatic, 'coordinates_angstrom': [float(row[k]) for k in ('Cartn_x','Cartn_y','Cartn_z')] if row else [0.,0.,0.],
            'origin': 'observed_source_heavy' if row else 'generated_hydrogen', 'source_atom_site_id': row['id'] if row else None,
            'source_coordinates_decimal': [row[k] for k in ('Cartn_x','Cartn_y','Cartn_z')] if row else None,
            'parent_name': hp[n] if n in hp else None, 'parent_index_zero_based': names.index(hp[n]) if n in hp else None})
    mapped = []
    for b in bonds + [{'atom_id_1':'NZ','atom_id_2':'HNZ3','value_order':'sing','pdbx_aromatic_flag':'N'}]:
        a, c = sorted((all_names.index(b['atom_id_1']), all_names.index(b['atom_id_2'])))
        mapped.append({'atom_i':a, 'atom_j':c, 'order':1 if b['value_order']=='sing' else 2, 'aromatic':b['pdbx_aromatic_flag']=='Y'})
    return graph, {'atoms':atoms, 'bonds':mapped}


def test_valid_synthetic_contract_is_accepted(source_and_mapping):
    module.validate_prepared_mapping(*source_and_mapping)


@pytest.mark.parametrize('delta', [0.0001, 1.0])
def test_source_heavy_coordinate_drift_is_rejected(source_and_mapping, delta):
    graph, mapping = source_and_mapping
    mapping['atoms'][4]['coordinates_angstrom'][0] += delta
    with pytest.raises(ValueError, match='SOURCE_HEAVY_COORDINATE_DRIFT'):
        module.validate_prepared_mapping(graph, mapping)


def test_duplicate_source_atom_name_is_rejected(source_and_mapping):
    graph, mapping = source_and_mapping
    graph['observed_atoms'][2]['label_atom_id'] = graph['observed_atoms'][1]['label_atom_id']
    with pytest.raises(ValueError, match='DUPLICATE'):
        module.validate_prepared_mapping(graph, mapping)


@pytest.mark.parametrize('site,value', [('NZ',0), ('NE1',1), ('OH',-1)])
def test_microstate_charge_change_is_rejected(source_and_mapping, site, value):
    graph, mapping = source_and_mapping
    next(a for a in mapping['atoms'] if a['name']==site)['formal_charge'] = value
    with pytest.raises(ValueError, match='FORMAL_CHARGE_STATE_CHANGED'):
        module.validate_prepared_mapping(graph, mapping)


def test_alternative_protocol_state_is_rejected(source_and_mapping):
    state = deepcopy(module.STATE)
    state['formula'] = 'C10H12N2O'
    with pytest.raises(ValueError, match='UNSUPPORTED_COMPUTATIONAL_MICROSTATE'):
        module.validate_prepared_mapping(*source_and_mapping, state=state)


def test_hydrogen_parent_reassignment_is_rejected(source_and_mapping):
    graph, mapping = source_and_mapping
    mapping['atoms'][-1]['parent_name'] = 'NE1'
    with pytest.raises(ValueError, match='HYDROGEN_PARENT_CHANGED'):
        module.validate_prepared_mapping(graph, mapping)


def test_source_bond_order_drift_is_rejected(source_and_mapping):
    graph, mapping = source_and_mapping
    mapping['bonds'][1]['order'] = 1
    with pytest.raises(ValueError, match='SOURCE_BOND_MISMATCH'):
        module.validate_prepared_mapping(graph, mapping)


def test_replaced_source_bond_is_rejected_by_binding_hash():
    original = b'data_synthetic\nSRO CZ3 CE3 doub Y\n'
    altered = original.replace(b'doub', b'sing')
    expected = hashlib.sha256(original).hexdigest()
    module.check_source_bytes(original, expected)
    with pytest.raises(ValueError, match='SOURCE_CIF_HASH_MISMATCH'):
        module.check_source_bytes(altered, expected)


def test_source_bond_duplicate_is_rejected(source_and_mapping):
    graph, _ = source_and_mapping
    graph['component_bonds'][-1] = deepcopy(graph['component_bonds'][-2])
    with pytest.raises(ValueError, match='SOURCE_BOND_IDENTITY_DUPLICATE'):
        module.validate_source_graph(graph)
