"""A chemistry annotation transfer must not repair an unrelated cross binding."""
import hashlib
import json

import pytest

from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json
from docs.research.human_5ht6_d3_complex.bind_chemical_request import bind
from tests.unit.test_cpu_explicit_chemistry_workflow import request_fixture


def test_rebinding_rejects_cross_parameters_for_a_different_parent(tmp_path):
    request = request_fixture(tmp_path)
    request['schema_id'] = 'cpu_fixed_receptor_request/1.0.0'
    cross_path = tmp_path / 'cross_parameters-explicit.json'
    cross = json.loads(cross_path.read_bytes())
    cross['receptor_system_sha256'] = '0' * 64
    raw = json.dumps(cross).encode()
    cross_path.write_bytes(raw)
    request['cross_parameters']['sha256'] = hashlib.sha256(raw).hexdigest()
    source = tmp_path / 'request.json'
    source.write_text(json.dumps(request))
    packet = tmp_path / 'packet'
    packet.mkdir()
    receptor_raw = (tmp_path / 'receptor-explicit.json').read_bytes()
    (packet / 'receptor-canonical.json').write_bytes(receptor_raw)
    system = all_atom_system_from_canonical_json(receptor_raw)
    manifest = {
        'schema_id': 'human_5ht6_7xtb_source_bound_receptor_chemical_graph_v1',
        'files': {'receptor-canonical.json': {
            'sha256': hashlib.sha256(receptor_raw).hexdigest(), 'bytes': len(receptor_raw)}},
        'parent_refs': {'canonical': request['receptor']},
        'receptor_system_sha256': canonical_system_sha256(system),
    }
    (packet / 'manifest.v1.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='receptor'):
        bind(source, packet, tmp_path / 'output')
    assert not (tmp_path / 'output').exists()
