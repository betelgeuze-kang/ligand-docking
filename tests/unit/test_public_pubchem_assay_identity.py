import pytest
from tools.product import public_assay_components as c


def node(raw, name):
    return c.node_from_raw(raw, None, node_id=name, record_id=name, ligand_id='')


def test_shared_pubchem_assay_propagates_evaluation_reservation():
    a = node({'PubChem AID': 1030, 'role': 'fit'}, 'a')
    b = node({'PubChem AID': '1030', 'evaluation_only': True}, 'b')
    graph = c.component_index([a, b])
    assert graph['a']['blocked']
    assert graph['a']['component_id'] == graph['b']['component_id']
    assert a['schema_version'] == c.SCHEMA_V2


@pytest.mark.parametrize('value', [0, -1, True, 1.5, '01030', '+1030', '1e3', '1030.0', [], {}])
def test_malformed_pubchem_assay_id_fails_closed(value):
    with pytest.raises(ValueError, match='invalid_pubchem_assay_id'):
        node({'PubChem AID': value}, 'x')


def test_different_native_namespaces_do_not_collide():
    graph = c.component_index([
        node({'PubChem AID': 1030}, 'a'),
        node({'PubChem AID': 504327}, 'b'),
        node({'ChEMBL Assay ID': 'CHEMBL1030', 'evaluation_only': True}, 'c'),
    ])
    assert len({r['component_id'] for r in graph.values()}) == 3
    assert not graph['a']['blocked']


def test_missing_aid_keeps_previous_schema():
    assert node({}, 'a')['schema_version'] == c.SCHEMA
