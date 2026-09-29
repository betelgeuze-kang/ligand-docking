import copy

import pytest

from docs.research.human_5ht6_sro_numerical_preparation import bind_numerical_request as module


def xml(particles, extra=''):
    return ('<System><Forces><Force type="NonbondedForce"><Particles>' + particles
            + '</Particles></Force>' + extra + '</Forces></System>').encode()


def test_exact_workflow_reference_is_readable_and_detects_mutation(tmp_path):
    from betelgeuze_product.reference_minimization_workflow import _bound
    path = tmp_path / 'input.json'
    path.write_text('{"value":1}\n')
    ref = module.reference(path)
    request_ref = module.request_reference(ref)
    assert _bound(request_ref) == {'value': 1}
    original = copy.deepcopy(ref)
    path.write_text('{"value":2}\n')
    with pytest.raises(ValueError, match='input_sha256_mismatch'):
        _bound(request_ref)
    with pytest.raises(ValueError, match='bound_file_changed'):
        module.checked(ref)
    assert ref == original


def test_receptor_particle_units_and_order():
    raw = xml('<Particle sig="0.31" eps="4.184" q="-0.2"/>'
              '<Particle sig="0.27" eps="0" q="0.2"/>')
    assert module.receptor_particles(raw, 2) == [(0, 3.1, 1., -.2), (1, 2.7, 0., .2)]


@pytest.mark.parametrize('sigma,epsilon,charge', [
    ('nan', '1', '0'), ('0', '1', '0'), ('0.2', '-1', '0'),
    ('0.2', 'inf', '0'), ('0.2', '1', 'nan'),
])
def test_invalid_nonbonded_particles_fail(sigma, epsilon, charge):
    raw = xml(f'<Particle sig="{sigma}" eps="{epsilon}" q="{charge}"/>')
    with pytest.raises(ValueError, match='invalid_receptor_nonbonded_particle'):
        module.receptor_particles(raw, 1)


def test_nonbonded_missing_duplicate_or_incomplete_fails():
    cases = [
        (b'<System/>', 'receptor_force_inventory_missing'),
        (b'<System><Forces/></System>', 'exactly_one_receptor_nonbonded_force_required'),
        (xml('', '<Force type="NonbondedForce"><Particles/></Force>'),
         'exactly_one_receptor_nonbonded_force_required'),
        (xml(''), 'receptor_particle_coverage'),
    ]
    for raw, reason in cases:
        with pytest.raises(ValueError, match=reason):
            module.receptor_particles(raw, 1)


def test_publication_is_bound_and_refuses_overwrite(tmp_path):
    path = tmp_path / 'receipt.json'
    ref = module.publish(path, {'passed': False})
    module.checked(ref)
    with pytest.raises(FileExistsError):
        module.publish(path, {'passed': True})
    assert module.reference(path) == ref


def test_verified_output_change_cannot_be_rebound(tmp_path):
    path = tmp_path / 'ligand.json'
    path.write_bytes(b'original')
    expected = module.reference(path)
    path.write_bytes(b'mutated!')
    with pytest.raises(ValueError, match='verified_preparation_bytes_changed'):
        module.read_expected(path, expected)


def test_parse_bytes_remain_checked_snapshot_and_later_mutation_is_detected(tmp_path):
    path = tmp_path / 'ligand.json'
    path.write_bytes(b'original')
    raw, bound = module.read_expected(path, module.reference(path))
    path.write_bytes(b'mutated!')
    assert raw == b'original'
    with pytest.raises(ValueError, match='bound_file_changed'):
        module.checked(bound)


@pytest.mark.parametrize('changed', ['manifest.v1.json', 'ligand-canonical.json',
                                    'ligand-unconstrained-openmm-system.xml'])
def test_change_after_independent_verification_fails_before_translation(tmp_path, monkeypatch, changed):
    import json
    from docs.research.human_5ht6_sro_numerical_preparation import verify_sro
    from betelgeuze_product.cpu_refinement_v1_2 import provenance
    prepared = tmp_path / 'prepared'
    prepared.mkdir()
    names = ('ligand-canonical.json', 'ligand-unconstrained-openmm-system.xml')
    for name in names:
        (prepared / name).write_bytes(b'original')
    manifest = {'files': {name: module.reference(prepared / name) for name in names}}
    (prepared / 'manifest.v1.json').write_text(json.dumps(manifest))
    manifest_ref = module.reference(prepared / 'manifest.v1.json')

    def verifier(_prepared):
        path = prepared / changed
        path.write_bytes(b'!' * path.stat().st_size)
        return {'passed': True, 'errors': [], 'manifest': manifest_ref}

    monkeypatch.setattr(verify_sro, 'verify_packet', verifier)
    monkeypatch.setattr(provenance, 'source_manifest', lambda: {})
    output = tmp_path / 'output'
    with pytest.raises(ValueError, match='verified_preparation_bytes_changed'):
        module.build(prepared, output, provenance.digest({}))
    assert not (output / 'parameters.json').exists()
    assert not (output / 'request.json').exists()
    failure = json.loads((output / 'failure.json').read_text())
    assert failure['stage'] == 'independent_preparation_verification'
