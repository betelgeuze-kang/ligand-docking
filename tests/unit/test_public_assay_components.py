"""Fresh synthetic counterexamples, with actual intake and training consumers."""
from copy import deepcopy
import json

import pytest

from tools.product import public_assay_dataset as intake
from tools.product import train_public_assay_selector as trainer
from tools.product import public_assay_components as components
from tests.unit.test_public_assay_dataset import inputs, source_row
from tests.unit.test_public_assay_selector import rows, bundle, write_context


@pytest.mark.parametrize('reserved', ['calibration', 'development_test', 'test'])
def test_rejected_other_endpoint_bridge_propagates_reserved_before_cohort(reserved):
    values = rows()
    values[5]['source_provenance']['row']['role'] = reserved
    bridge = deepcopy(values[0])
    bridge.update(record_id='synthetic:bridge', target_state_sha256='b'*64,
                  eligible_for_split_assignment=False, admission_issues=['not_a_fit_row'])
    bridge['chemical_identity'] = deepcopy(values[5]['chemical_identity'])
    bridge['observations'] = []
    accepted, ledger = trainer.cohort([*values, bridge], 'a'*64, 'IC50')
    assert len(ledger) == 60
    assert len(accepted) == 50
    assert not {r['record_id'] for r in values[:10]} & {r['record_id'] for r in accepted}


def test_reserved_row_observations_are_not_read_before_admission():
    class Forbidden:
        def __iter__(self):
            raise AssertionError('reserved_observations_were_read')
    values = rows()
    values[0]['source_provenance']['row']['role'] = 'test'
    values[0]['observations'] = Forbidden()
    accepted, ledger = trainer.cohort(values, 'a'*64, 'IC50')
    assert len(accepted) == 55 and len(ledger) == 60


def test_actual_trainer_keeps_unselected_bridge_in_split_graph(tmp_path):
    source = bundle(tmp_path)
    values = rows()
    bridge = deepcopy(values[0])
    bridge.update(record_id='synthetic:bridge', target_state_sha256='b'*64,
                  eligible_for_split_assignment=False, admission_issues=['not_a_fit_row'])
    bridge['chemical_identity'] = deepcopy(values[5]['chemical_identity'])
    bridge['observations'] = []
    with (source/'records.jsonl').open('a') as f:
        f.write(intake.json_text(bridge)+'\n')
    with (source/'ledger.jsonl').open('a') as f:
        f.write(intake.json_text({'record_id':bridge['record_id'], 'target_state_sha256':'b'*64,
                                'status':'normalized', 'reason':'not_a_fit_row'})+'\n')
    summary = json.loads((source/'summary.json').read_text())
    summary.update(records_sha256=intake.file_sha(source/'records.jsonl'),
                   ledger_sha256=intake.file_sha(source/'ledger.jsonl'), requested_target_rows=61)
    (source/'summary.json').write_text(json.dumps(summary))
    write_context(source, [*values, bridge])
    report = trainer.run(input_dir=source, summary_sha256=intake.file_sha(source/'summary.json'),
                         target_state='a'*64, endpoint='IC50', output_dir=tmp_path/'trained')
    assignments = {r['record_id']:r for line in (tmp_path/'trained/split.jsonl').read_text().splitlines()
                   if (r:=json.loads(line))}
    assert assignments[values[0]['record_id']]['group'] == assignments[values[5]['record_id']]['group']
    assert report['model_endpoint_rows'] == 60


def test_intake_uses_other_target_rejected_bridge_before_values(tmp_path):
    a = source_row(**{'BindingDB Reactant_set_id':'a', 'BindingDB MonomerID':'a',
                     'Ligand SMILES':'CCCCCC', 'Article DOI':'synthetic:doc-a'})
    b = source_row(**{'BindingDB Reactant_set_id':'b', 'BindingDB MonomerID':'b',
                     'Ligand SMILES':'CCCCCCN', 'Article DOI':'synthetic:doc-a',
                     'UniProt (SwissProt) Primary ID of Target Chain 1':'OTHER'})
    c = source_row(**{'BindingDB Reactant_set_id':'c', 'BindingDB MonomerID':'c',
                     'Ligand SMILES':'CCCCCCN', 'Article DOI':'synthetic:doc-c', 'role':'test',
                     'UniProt (SwissProt) Primary ID of Target Chain 1':'OTHER'})
    accepted, ledger, summary = intake.build_dataset(**inputs(tmp_path, [a,b,c]))
    assert not accepted
    assert len(ledger) == summary['requested_target_rows'] == 1
    assert ledger[0]['reason'] == 'reserved_identity_component'


def test_disconnected_other_target_reserved_row_does_not_block_positive(tmp_path):
    a = source_row(**{'BindingDB Reactant_set_id':'a', 'BindingDB MonomerID':'a',
                     'Ligand SMILES':'CCCCCC', 'Article DOI':'synthetic:doc-a'})
    c = source_row(**{'BindingDB Reactant_set_id':'c', 'BindingDB MonomerID':'c',
                     'Ligand SMILES':'CCCCCCC', 'Article DOI':'synthetic:doc-c', 'role':'test',
                     'UniProt (SwissProt) Primary ID of Target Chain 1':'OTHER'})
    accepted, ledger, summary = intake.build_dataset(**inputs(tmp_path, [a,c]))
    assert len(accepted) == len(ledger) == summary['requested_target_rows'] == 1
    assert accepted[0]['assay_conditions']['pH_source'] == '0'


def test_external_reserved_metadata_blocks_intake_before_observation_projection(tmp_path, monkeypatch):
    row = source_row()
    node = components.node_from_raw(row, intake.chemical_identity(row['Ligand SMILES']),
                                   node_id='external:reserved', record_id='external:record',
                                   ligand_id='', extra_declarations=[{'split':'calibration'}])
    def forbidden(*args, **kwargs):
        raise AssertionError('normalization_or_observation_called_for_reserved_component')
    monkeypatch.setattr(intake, 'normalize_record', forbidden)
    accepted, ledger, summary = intake.build_dataset(**inputs(tmp_path), reserved_context=[node])
    assert not accepted and ledger[0]['reason'] == 'reserved_identity_component'
    assert summary['identity_context_external_rows'] == 1


@pytest.mark.parametrize('source', ['mapping', 'assay'])
def test_other_target_joined_reservation_propagates_without_assay_text_projection(tmp_path, source):
    row = source_row(**{'BindingDB Reactant_set_id':'a', 'BindingDB MonomerID':'a'})
    other = source_row(**{'BindingDB Reactant_set_id':'b', 'BindingDB MonomerID':'b',
                         'UniProt (SwissProt) Primary ID of Target Chain 1':'OTHER'})
    args = inputs(tmp_path, [row, other])
    if source == 'mapping':
        args['mapping_path'].write_text('REACTANT_SET_ID\tENTRYID_ASSAYID\trole\na\t001_01\t\nb\t002_01\tcalibration\n')
    else:
        args['mapping_path'].write_text('REACTANT_SET_ID\tENTRYID_ASSAYID\na\t001_01\nb\t002_01\n')
        args['assay_path'].write_text('ENTRYID\tASSAYID\tDESCRIPTION\trole\n001\t01\tsynthetic\t\n002\t01\tDO_NOT_PROJECT_THIS_TEXT\tdevelopment_test\n')
    for key in ['mapping','assay']:
        args[key+'_sha256'] = intake.file_sha(args[key+'_path'])
    accepted, ledger, summary = intake.build_dataset(**args)
    assert not accepted and ledger[0]['reason'] == 'reserved_identity_component'
    assert 'DO_NOT_PROJECT_THIS_TEXT' not in intake.json_text(summary['identity_context'])


def test_duplicate_context_nodes_are_rejected_instead_of_last_policy_winning():
    node = components.normalized_node(rows()[0])
    other = deepcopy(node)
    other['policy_declarations'].append({'role':'test'})
    with pytest.raises(ValueError, match='duplicate_identity_context_node'):
        components.component_index([node, other])


def test_context_graph_order_and_labels_do_not_change_components():
    values = rows()
    nodes = [components.normalized_node(row) for row in values]
    expected = components.component_index(nodes)
    for row in values:
        row['observations'] = [{'endpoint':'Ki', 'negative_log10_molar':99999}]
    assert components.component_index(list(reversed([components.normalized_node(row) for row in values]))) == expected


def test_unknown_policy_is_blocked_and_measured_zero_is_not_a_false_reservation():
    values = rows()
    values[0]['source_provenance']['row'].update(evaluation_only='0')
    assert len(trainer.cohort(values, 'a'*64, 'IC50')[0]) == 60
    values[0]['source_provenance']['row']['evaluation_only'] = 'unknown'
    assert len(trainer.cohort(values, 'a'*64, 'IC50')[0]) == 55


@pytest.mark.parametrize('text', ['{"role":"test","role":"fit"}', '{"evaluation_only":NaN}'])
def test_context_json_cannot_overwrite_or_invent_policy_fields(text):
    with pytest.raises(ValueError):
        components.loads(text)


@pytest.mark.parametrize('mode', ['missing', 'hash', 'count', 'omit_node', 'policy'])
def test_actual_trainer_rejects_missing_stale_or_lossy_context_cache(tmp_path, mode):
    source = bundle(tmp_path)
    summary = json.loads((source/'summary.json').read_text())
    nodes = [json.loads(line) for line in (source/'identity-context.jsonl').read_text().splitlines()]
    if mode == 'missing':
        summary.pop('identity_context_sha256')
    elif mode == 'hash':
        (source/'identity-context.jsonl').write_text('[]\n')
    elif mode == 'count':
        summary['identity_context_source_rows'] -= 1
    elif mode == 'omit_node':
        nodes.pop()
        (source/'identity-context.jsonl').write_text(''.join(intake.json_text(node)+'\n' for node in nodes))
        summary.update(identity_context_source_rows=len(nodes), identity_context_sha256=intake.file_sha(source/'identity-context.jsonl'))
    else:
        values = rows()
        values[0]['source_provenance']['row']['role'] = 'calibration'
        (source/'records.jsonl').write_text(''.join(intake.json_text(row)+'\n' for row in values))
        summary['records_sha256'] = intake.file_sha(source/'records.jsonl')
    (source/'summary.json').write_text(json.dumps(summary))
    with pytest.raises(ValueError):
        trainer.run(input_dir=source, summary_sha256=intake.file_sha(source/'summary.json'),
                    target_state='a'*64, endpoint='IC50', output_dir=tmp_path/'trained')
    assert not (tmp_path/'trained').exists()


@pytest.mark.parametrize('location', ['node', 'source', 'joined', 'role', 'line', 'availability'])
def test_external_context_cannot_serialize_nonmetadata_payload(tmp_path, location):
    node = components.node_from_raw({}, None, node_id='external:reserved',
                                   record_id='external:record', ligand_id='')
    payload = {'observations': [{'endpoint': 'IC50', 'value': 'FORBIDDEN'}]}
    if location == 'node':
        node.update(payload)
    elif location == 'source':
        node['source'].update(payload)
    elif location == 'joined':
        node['joined_policy_sources'] = [payload]
    elif location == 'role':
        node['policy_declarations'] = [{'role': payload}]
    elif location == 'line':
        node['source']['source_line'] = payload
    else:
        node['chemical_identity_available'] = payload
    with pytest.raises(ValueError):
        intake.build_dataset(**inputs(tmp_path), reserved_context=[node])


@pytest.mark.parametrize('mode', ['same_size_replacement', 'source_origin', 'source_line_gap', 'external_set', 'source_external_counts'])
def test_bound_context_occurrences_and_external_set_cannot_change(tmp_path, mode):
    source = bundle(tmp_path)
    summary = json.loads((source/'summary.json').read_text())
    nodes = [components.loads(line) for line in (source/'identity-context.jsonl').read_text().splitlines()]
    if mode == 'same_size_replacement':
        nodes[-1]['keys'] = []
    elif mode == 'source_origin':
        nodes[-1]['source']['source_sha256'] = 'e'*64
        summary['identity_context_source_nodes_sha256'] = components.node_set_sha(nodes)
    elif mode == 'source_line_gap':
        nodes[-1]['source']['source_line'] = 1000
        nodes[-1]['node_id'] = 'source:' + components.digest(components.canonical(nodes[-1]['source']))
        summary['identity_context_source_nodes_sha256'] = components.node_set_sha(nodes)
    elif mode == 'external_set':
        nodes.append(components.node_from_raw({}, None, node_id='external:replacement', record_id='external:record', ligand_id=''))
        summary['identity_context_external_rows'] = 1
    else:
        summary['identity_context_source_rows'] -= 1
        summary['identity_context_external_rows'] += 1
    (source/'identity-context.jsonl').write_text(''.join(intake.json_text(node)+'\n' for node in nodes))
    summary['identity_context_sha256'] = intake.file_sha(source/'identity-context.jsonl')
    (source/'summary.json').write_text(json.dumps(summary))
    with pytest.raises(ValueError, match='identity_context_'):
        trainer.run(input_dir=source, summary_sha256=intake.file_sha(source/'summary.json'),
                    target_state='a'*64, endpoint='IC50', output_dir=tmp_path/'trained')
    assert not (tmp_path/'trained').exists()


@pytest.mark.parametrize('declaration', [{'role': 'calibration'}, {'split': 'development_test'}, {'evaluation_only': 'unknown'}])
def test_external_joined_policy_alone_blocks_connected_intake(tmp_path, declaration):
    raw = source_row()
    node = components.node_from_raw(raw, intake.chemical_identity(raw['Ligand SMILES']),
                                   node_id='external:joined-only', record_id='external:joined-record', ligand_id='')
    node['joined_policy_sources'] = [{'source_sha256': 'c'*64, 'source_member': 'synthetic.tsv',
                                     'source_line': 2, 'entry_assay_id': 'synthetic:1',
                                     'declarations': [declaration]}]
    accepted, ledger, summary = intake.build_dataset(**inputs(tmp_path), reserved_context=[node])
    assert accepted == [] and ledger[0]['reason'] == 'reserved_identity_component'
