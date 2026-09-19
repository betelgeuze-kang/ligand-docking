"""Cross-candidate evidence must remain consistent after outer rehashing."""
import json

import pytest

from betelgeuze_product.cpu_refinement_v1_2 import fixed_receptor_workflow as workflow
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError
from tests.unit.test_cpu_fixed_receptor_workflow import request_fixture


@pytest.mark.parametrize('change', ['component_force_calls', 'excess_component_pairs', 'score_calls',
                                   'row_index', 'refined_flag', 'original_coordinates'])
def test_rehashed_candidate_cost_and_coordinate_contradictions_rejected(tmp_path, change):
    from betelgeuze_product.cpu_refinement_v1_2.provenance import digest, decode_coordinates
    from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint
    request = request_fixture(tmp_path)
    workflow.run_request(request, tmp_path / 'out', stop_after=1)
    path = tmp_path / 'out' / 'candidate-00000.json'
    envelope = json.loads(path.read_bytes())
    record = envelope['payload']['record']
    if change in {'component_force_calls', 'excess_component_pairs'}:
        stages = record['execution']['component_evaluations']['stages']
        stages['force.evaluate']['calls'] += 1
        stages['force.evaluate']['completed'] += 1
        if change == 'excess_component_pairs':
            stages['geometry.build']['calls'] += 1
            stages['geometry.build']['completed'] += 1
    elif change == 'score_calls':
        stages = record['execution']['scoring']['stages']
        stages['score.evaluate']['calls'] += 1
        stages['score.evaluate']['completed'] += 1
    else:
        row = record['numerical']['baseline']
        if change == 'row_index':
            row['proposal_index'] += 1
        elif change == 'refined_flag':
            row['refined'] = True
        else:
            row['coordinates_binary64_hex'][0][0] = (99.).hex()
            row['coordinates_sha256'] = coordinate_fingerprint(decode_coordinates(row['coordinates_binary64_hex'], 5)[0])
    record['numerical_sha256'] = digest(record['numerical'])
    envelope['sha256'] = digest(envelope['payload'])
    path.write_text(json.dumps(envelope))
    with pytest.raises(ResearchError):
        workflow.run_request(request, tmp_path / 'out', resume=True)
