"""Synthetic profile integration only: no molecular field or docking run."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
import torch

from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, coordinates_hex
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig
from betelgeuze_product.cpu_refinement_v1_3.kernel import make_observation
from betelgeuze_product.cpu_refinement_shape_v1.profile import ShapeProfile, make_shape_observation


class System:
    def __init__(self, xyz):
        self.coordinates = xyz
        self.atom_count = xyz.shape[1]
    def with_coordinates(self, xyz, operation):
        return System(xyz)


def components(evaluated):
    e = float(evaluated.term.energy[0])
    return {'ligand_internal': e, 'cross_lennard_jones': 0., 'cross_screened_coulomb': 0., 'total': e}


class Evaluator:
    parameters = SimpleNamespace(base_parameters=SimpleNamespace(cutoff_angstrom=6.))
    def __init__(self):
        self.calls = []
        self.fail = False
    def evaluate(self, system, neighbors):
        self.calls.append(coordinates_hex(system.coordinates))
        if self.fail:
            raise FloatingPointError('synthetic base failure')
        x = system.coordinates
        return SimpleNamespace(term=SimpleNamespace(energy=(x*x).sum().reshape(1), forces=-2*x),
                               constraint_observations=())
    def identity(self):
        return {'synthetic': True}


def calculation(ref, xyz, strength, **ids):
    x = torch.tensor([xyz], dtype=torch.float64)
    delta = x[:, 0] - x[:, 1]
    r = torch.linalg.vector_norm(delta)
    if r < 1e-8:
        raise FloatingPointError('synthetic domain')
    error = r - 2.
    f = -strength * error * delta / r
    return float(.5 * strength * error**2), torch.stack((f[0], -f[0])).tolist()


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.setattr(execution, 'build_compact_radius_graph', lambda *args: object())
    monkeypatch.setattr(execution, 'components_document', components)
    monkeypatch.setattr(execution, '_intact', lambda *args: None)
    system = System(torch.tensor([[[-1., .1, 0.], [1., 0., .2]]], dtype=torch.float64))
    config = SolverConfig(max_objective_attempts=17, max_accepted_steps=4,
                          max_backtracks=3, max_restart_verifications=2)
    def run(path, strength=None, **kwargs):
        evaluator = Evaluator()
        profile = None if strength is None else ShapeProfile(None, strength, lambda _: {}, calculation)
        result = execution._minimize_profile(system, config, evaluator=evaluator,
            identity={'synthetic': 'one', 'strength': strength}, run_dir=path,
            implementation_sources=lambda: {}, result_schema='synthetic/1', profile=profile, **kwargs)
        return result, evaluator, profile
    return system, config, run


def test_zero_trajectory_dispatch_and_stop_equal(harness, tmp_path):
    _, _, run = harness
    old, ev0, _ = run(tmp_path/'old')
    new, ev1, _ = run(tmp_path/'shape0', 0.)
    assert ev0.calls == ev1.calls
    a, b = old['checkpoint']['state'], new['checkpoint']['state']
    for key in ['attempts', 'accepted', 'status', 'history', 'line_search', 'skipped_curvature']:
        assert a[key] == b[key]
    for key in ['initial', 'current']:
        assert a[key] == b[key]['base_observation']
        assert a[key]['forces'] == b[key]['forces']
        assert a[key]['energy'] == b[key]['energy']
    assert new['work']['optimizer_shape_calls'] == 0
    assert old['work']['optimizer_force_calls'] == new['work']['optimizer_force_calls']


@pytest.mark.parametrize('strength', [0., 100., 1000.])
def test_replay_has_no_dispatch(harness, tmp_path, monkeypatch, strength):
    system, config, run = harness
    result, evaluator, profile = run(tmp_path/'run', strength)
    monkeypatch.setattr(evaluator, 'evaluate', lambda *args: pytest.fail('replay dispatched'))
    checked = execution._verify_profile(system, config, evaluator=evaluator,
        identity={'synthetic': 'one', 'strength': strength}, run_dir=tmp_path/'run',
        implementation_sources=lambda: {}, result_schema='synthetic/1', profile=profile)
    assert checked == result


def test_pause_resume_retains_direction(harness, tmp_path):
    system, config, run = harness
    whole, _, _ = run(tmp_path/'whole', 100.)
    paused, _, _ = run(tmp_path/'split', 100., pause_after_objective_attempts=2)
    resumed, _, _ = run(tmp_path/'split', 100., resume=True)
    assert paused['status'] == 'checkpointed'
    assert whole['checkpoint']['state'] == resumed['checkpoint']['state']
    assert resumed['work']['restart_verification_attempts'] == 1
    assert resumed['work']['restart_base_force_calls'] == 1
    assert resumed['work']['restart_shape_calls'] == 1


def test_schema_and_strength_drift_rejected(harness, tmp_path):
    system, config, run = harness
    run(tmp_path/'run', 100.)
    with pytest.raises(ResearchError):
        run(tmp_path/'run', 1000., resume=True)
    with pytest.raises(ResearchError):
        run(tmp_path/'run', None, resume=True)


def test_shape_failure_counts_base_success(harness):
    system, config, _ = harness
    evaluator = Evaluator()
    def fail(*args, **kwargs):
        raise FloatingPointError('synthetic overflow')
    profile = ShapeProfile(None, 100., lambda _: {}, fail)
    receipt = profile.invoke(system, evaluator, config, {'attempt': 1, 'coordinates': coordinates_hex(system.coordinates)})
    assert receipt['observation'] is None
    assert receipt['work']['force_calls'] == receipt['work']['failed_force_calls'] == 1
    assert receipt['shape_work']['base_force_calls'] == 1
    assert receipt['shape_work']['failed_base_force_calls'] == 0
    assert receipt['shape_work']['shape_calls'] == receipt['shape_work']['failed_shape_calls'] == 1


def test_zero_no_shape_function_or_distance_guard(harness):
    system, config, _ = harness
    system.coordinates.zero_()
    def forbidden(*args, **kwargs):
        pytest.fail('lambda zero shape calculation leaked')
    profile = ShapeProfile(None, 0., forbidden, forbidden)
    receipt = profile.invoke(system, Evaluator(), config, {'attempt': 1, 'coordinates': coordinates_hex(system.coordinates)})
    assert receipt['observation'] is not None
    assert receipt['shape_work']['shape_calls'] == 0


def test_base_failure_passed_through_without_shape(harness):
    system, config, _ = harness
    evaluator = Evaluator()
    evaluator.fail = True
    profile = ShapeProfile(None, 100., lambda _: {}, lambda *args: pytest.fail('shape after base failure'))
    receipt = profile.invoke(system, evaluator, config, {'attempt': 1, 'coordinates': coordinates_hex(system.coordinates)})
    assert receipt['failure'] == 'retryable'
    assert receipt['shape_work']['failed_base_force_calls'] == 1
    assert receipt['shape_work']['shape_calls'] == 0


def test_cancellation_is_not_base_stationarity():
    xyz = torch.tensor([[[-1., 0., 0.], [1., 0., 0.]]], dtype=torch.float64)
    base = make_observation(1, xyz, 2., xyz, {'ligand_internal': 2., 'cross_lennard_jones': 0., 'cross_screened_coulomb': 0., 'total': 2.})
    observation = make_shape_observation(base, 1., -xyz, 100.)
    profile = ShapeProfile(None, 100., None, None)
    result = profile.result_fields({'current': observation, 'status': 'force_converged'}, SolverConfig())
    assert result['restrained_stationary']
    assert not result['unpenalized_stationary']
    assert result['convergence_basis'].startswith('augmented')
    bad = deepcopy(observation)
    bad['components']['ligand_internal'] = 3.0.hex()
    with pytest.raises(ResearchError):
        profile.validate_observation(bad, 2)


def test_unfinished_shape_call_is_unknown_not_reissued(harness, tmp_path):
    system, config, _ = harness
    calls = []
    class Interrupted(BaseException):
        pass
    def interrupted(*args, **kwargs):
        calls.append(1)
        raise Interrupted()
    profile = ShapeProfile(None, 100., lambda _: {}, interrupted)
    evaluator = Evaluator()
    args = dict(evaluator=evaluator, identity={'synthetic': 'pending'}, run_dir=tmp_path/'pending',
                implementation_sources=lambda: {}, result_schema='synthetic/1', profile=profile)
    with pytest.raises(Interrupted):
        execution._minimize_profile(system, config, **args)
    for resume in [False, True]:
        with pytest.raises(execution.PendingWorkError) as error:
            if resume:
                execution._minimize_profile(system, config, resume=True, **args)
            else:
                execution._verify_profile(system, config, **args)
        assert error.value.work['actual_force_calls'] is None
        assert error.value.work['unknown_pending_attempts'] == 1
    assert calls == [1]
    assert len(evaluator.calls) == 1


def test_failed_shape_terminal_receipt_replays_exactly(harness, tmp_path):
    system, config, _ = harness
    def overflow(*args, **kwargs):
        raise FloatingPointError('synthetic nonfinite penalty')
    profile = ShapeProfile(None, 100., lambda _: {}, overflow)
    evaluator = Evaluator()
    args = dict(evaluator=evaluator, identity={'synthetic': 'overflow'}, run_dir=tmp_path/'overflow',
                implementation_sources=lambda: {}, result_schema='synthetic/1', profile=profile)
    result = execution._minimize_profile(system, config, **args)
    assert result['status'] == 'evaluation_failed'
    assert result['work']['optimizer_base_force_calls'] == 1
    assert result['work']['optimizer_failed_base_force_calls'] == 0
    assert result['work']['optimizer_failed_shape_calls'] == 1
    assert execution._verify_profile(system, config, **args) == result
    assert len(evaluator.calls) == 1


def test_restart_full_shape_force_direction_mismatch(harness, tmp_path):
    system, config, _ = harness
    evaluator = Evaluator()
    profile = ShapeProfile(None, 100., lambda _: {}, calculation)
    args = dict(evaluator=evaluator, identity={'synthetic': 'restart'}, run_dir=tmp_path/'restart',
                implementation_sources=lambda: {}, result_schema='synthetic/1', profile=profile)
    execution._minimize_profile(system, config, pause_after_objective_attempts=1, **args)
    def reverse(ref, xyz, strength, **ids):
        energy, forces = calculation(ref, xyz, strength, **ids)
        return energy, [[-v for v in row] for row in forces]
    changed = ShapeProfile(None, 100., lambda _: {}, reverse)
    # Deliberately unchanged synthetic binding to exercise full observed parity,
    # not the public source-binding check which independently rejects real drift.
    with pytest.raises(ResearchError, match='restart full energy/force'):
        execution._minimize_profile(system, config, resume=True, **dict(args, profile=changed))
    before = len(evaluator.calls)
    with pytest.raises(ResearchError, match='recorded restart'):
        execution._verify_profile(system, config, **args)
    assert len(evaluator.calls) == before
