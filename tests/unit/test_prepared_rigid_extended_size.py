"""Extended real-file pose execution and durable resume, with synthetic sites."""
import copy
import hashlib
import pytest
from betelgeuze_engine.product import prepared_rigid_poses as poses
from betelgeuze_engine.product import prepared_pose_journal as store
from tools.product import score_prepared_cross_interactions as consumer
from tests.unit.test_prepared_cross_extended_size import _large_prepared
from tests.unit.test_prepared_rigid_poses import _pose
from tests.unit.test_score_prepared_cross_interactions import _case
from tests.unit.test_prepared_pose_resume import numerical_rows


def request_for(path, count, partition):
    case = _case(_large_prepared(path, count))
    case['evaluation']['pocket_radius_angstrom'] = 1000.
    return dict(schema_version=poses.SCHEMA, prepared_input=case['prepared_input'],
                evaluation=case['evaluation'], execution=dict(projection_partition=partition,
                preparation_reuse='request', ligand_size_profile='extended_512_v1'),
                poses=[_pose('first'), _pose('shift', .5), _pose('invalid')])


@pytest.mark.parametrize('count', [315, 512])
@pytest.mark.parametrize('partition', ['source_order_v1', 'spatial_median_v1'])
def test_extended_interruption_resume_preserves_full_results_and_failed_rows(tmp_path, monkeypatch, count, partition):
    request = request_for(tmp_path/'inputs', count, partition)
    request['poses'][-1]['rotation_matrix'][0][0] = -1.
    journal = tmp_path/'checkpoint'
    original = store.PoseJournal.commit
    def interrupted(self, row, shared, execution):
        original(self, row, shared, execution)
        raise KeyboardInterrupt('stop after first durable row')
    with monkeypatch.context() as patch:
        patch.setattr(store.PoseJournal, 'commit', interrupted)
        with pytest.raises(KeyboardInterrupt):
            consumer.evaluate_request(request, checkpoint_dir=journal)
    resumed = consumer.evaluate_request(request, checkpoint_dir=journal, resume=True)
    continuous = consumer.evaluate_request(request)
    assert numerical_rows(resumed) == numerical_rows(continuous)
    assert resumed['resume_observation']['restored_rows'] == 1
    assert resumed['resume_observation']['newly_completed_rows'] == 2
    assert resumed['denominator'] == dict(requested=3, evaluated=2, failed=1, skipped=0)
    for row in resumed['rows'][:2]:
        result = row['result']
        assert len(result['quantities']['ligand_cross_forces_kcal_per_mol_angstrom']) == count
        assert len(result['sources']['ligand']['nonbonded_parameters']) == count
        assert result['pair_accounting']['requested_cross_pairs'] == count
        assert result['input_domain']['ligand_size_profile'] == 'extended_512_v1'
    def forbidden(*a, **kw):
        pytest.fail('completed resume reached loading or physics')
    monkeypatch.setattr(poses, 'load_prepared_gromacs_components', forbidden)
    monkeypatch.setattr(poses, 'evaluate_prepared_cross_interaction', forbidden)
    again = consumer.evaluate_request(request, checkpoint_dir=journal, resume=True)
    assert numerical_rows(again) == numerical_rows(resumed)
    before = hashlib.sha256((journal/'completion.sqlite3').read_bytes()).hexdigest()
    changed = copy.deepcopy(request)
    changed['execution']['ligand_size_profile'] = 'standard_256_v1'
    with pytest.raises(ValueError, match='checkpoint_request_input_runtime_mismatch'):
        consumer.evaluate_request(changed, checkpoint_dir=journal, resume=True)
    assert hashlib.sha256((journal/'completion.sqlite3').read_bytes()).hexdigest() == before


@pytest.mark.parametrize('profile', [None, True, 512, [], {}, 'unbounded'])
def test_bad_profile_fails_before_loading(tmp_path, monkeypatch, profile):
    def forbidden(*a, **kw):
        pytest.fail('invalid execution reached loading')
    monkeypatch.setattr(poses, 'load_prepared_gromacs_components', forbidden)
    request = dict(schema_version=poses.SCHEMA, prepared_input={}, evaluation={},
                   execution=dict(projection_partition='source_order_v1', preparation_reuse='request',
                                  ligand_size_profile=profile), poses=[_pose('one')])
    report = consumer.evaluate_request(request)
    assert report['denominator']['failed'] == 1
    assert 'ligand_size_profile' in report['rows'][0]['reason']


@pytest.mark.parametrize('count,profile', [(257, None), (513, 'extended_512_v1')])
def test_pose_size_limits_remain_failed_in_denominator(tmp_path, count, profile):
    request = request_for(tmp_path/'inputs', count, 'source_order_v1')
    if profile is None:
        del request['execution']['ligand_size_profile']
    report = consumer.evaluate_request(request)
    assert report['denominator'] == dict(requested=3, evaluated=0, failed=3, skipped=0)
    assert all('bounded' in row['reason'] for row in report['rows'])
