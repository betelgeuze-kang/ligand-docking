from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[2] / 'docs/evidence/scripts/installed_pair_endpoint_openmm_20260930.py'
spec = importlib.util.spec_from_file_location('pair_endpoint', SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def oracle_and_protocol(tmp_path):
    oracle_file = tmp_path / 'oracle.py'
    oracle_file.write_text('synthetic reference API')
    trace_file = tmp_path / 'trace.py'
    trace_file.write_text('synthetic read-only trace API')
    oracle = SimpleNamespace(__file__=str(oracle_file), ENERGY_ABSOLUTE_TOLERANCE=1e-8,
        FORCE_ABSOLUTE_TOLERANCE=1e-8, _reference_context=lambda system, openmm: (system, object()))
    protocol = {'schema_id': 'installed_pair_final_source_openmm_protocol/1', 'planned_candidates': ['PR49', 'PR59'],
        'energy_absolute_tolerance_kcal_per_mol': 1e-8,
        'force_component_absolute_tolerance_kcal_per_mol_angstrom': 1e-8,
        'oracle_source': audit.ref(oracle_file), 'wrapper_source': audit.ref(SOURCE), 'trace_source': audit.ref(trace_file),
        'models': {'PR49': {'candidate': 'PR49'}, 'PR59': {'candidate': 'PR59'}}}
    return oracle, protocol


def test_executing_source_must_be_the_actual_pinned_module(tmp_path):
    oracle, protocol = oracle_and_protocol(tmp_path)
    audit.validate_protocol(protocol, oracle)
    other = tmp_path / 'different_oracle.py'
    other.write_text('synthetic reference API')
    oracle.__file__ = str(other)
    with pytest.raises(ValueError, match='executing_source_not_protocol_pinned:oracle_source'):
        audit.validate_protocol(protocol, oracle)


def test_counted_context_preserves_completed_and_failed_reference_attempts(tmp_path):
    oracle, _ = oracle_and_protocol(tmp_path)
    original = oracle._reference_context
    work = {'attempted_getState_energy_force_observations': 0, 'completed_getState_energy_force_observations': 0,
        'failed_getState_energy_force_observations': 0, 'interrupted_getState_completion_unknown': 0}
    class Context:
        def getState(self, fail=False):
            if fail:
                raise RuntimeError('synthetic getState failure')
            return 'state'
    with audit.counted_reference_contexts(oracle, work):
        context, _ = oracle._reference_context(Context(), None)
        assert context.getState() == 'state'
        with pytest.raises(RuntimeError):
            context.getState(fail=True)
    assert oracle._reference_context is original
    assert work == {'attempted_getState_energy_force_observations': 2,
        'completed_getState_energy_force_observations': 1, 'failed_getState_energy_force_observations': 1,
        'interrupted_getState_completion_unknown': 0}


def test_first_candidate_failure_does_not_erase_second_or_requested_denominator(tmp_path):
    oracle, protocol = oracle_and_protocol(tmp_path)
    def evaluate(model, oracle, trace_hash):
        if model['candidate'] == 'PR49':
            raise ValueError('synthetic endpoint unavailable')
        return {'same_math_point_passed': True, 'source_XML_internal_plus_declared_cross_point_passed': True,
            'full_retained_trace_source_domain_claim_passed': True, 'same_math_total': {'passed': True}}
    summary = audit.run_protocol(protocol, oracle, tmp_path, evaluate=evaluate)
    assert summary['point_denominator'] == {'requested': 2, 'evaluated': 1, 'blocked': 1,
        'same_math_passed': 1, 'direct_source_passed': 1}
    assert summary['status'] == 'blocked' and summary['new_native_force_calls'] == 0
    assert (tmp_path / 'PR49-final-openmm.json').exists() and (tmp_path / 'PR59-final-openmm.json').exists()
    assert summary['reference_work']['attempted_getState_energy_force_observations'] == 0


def test_invalid_protocol_preserves_two_blocked_candidates_without_reference_calls(tmp_path):
    oracle, protocol = oracle_and_protocol(tmp_path)
    protocol['force_component_absolute_tolerance_kcal_per_mol_angstrom'] = 1e-7
    def forbidden(*args):
        raise AssertionError('reference must not be invoked')
    summary = audit.run_protocol(protocol, oracle, tmp_path, evaluate=forbidden)
    assert summary['point_denominator']['requested'] == summary['point_denominator']['blocked'] == 2
    assert summary['point_denominator']['evaluated'] == 0
    assert summary['reference_work']['attempted_getState_energy_force_observations'] == 0


@pytest.mark.parametrize('token', ['nan', 'inf', '0x1p+0'])
def test_saved_energy_requires_canonical_finite_binary64(token):
    with pytest.raises(ValueError):
        audit.scalar(token)


def test_interrupt_preserves_partial_reference_work_and_stops_remaining_candidate(tmp_path):
    oracle, protocol = oracle_and_protocol(tmp_path)
    attempted_models = []
    class InterruptedContext:
        def getState(self, **kwargs):
            raise KeyboardInterrupt('synthetic reference interruption')
    def evaluate(model, oracle, trace_hash):
        attempted_models.append(model['candidate'])
        context, _ = oracle._reference_context(InterruptedContext(), None)
        context.getState(getEnergy=True, getForces=True)
    summary = audit.run_protocol(protocol, oracle, tmp_path, evaluate=evaluate)
    assert attempted_models == ['PR49']
    assert summary['point_denominator']['requested'] == summary['point_denominator']['blocked'] == 2
    assert summary['point_denominator']['evaluated'] == 0
    assert summary['interruption'] == 'KeyboardInterrupt'
    assert summary['reference_work'] == {'attempted_getState_energy_force_observations': 1,
        'completed_getState_energy_force_observations': 0, 'failed_getState_energy_force_observations': 1,
        'interrupted_getState_completion_unknown': 1}
    second = audit.json.loads((tmp_path / 'PR59-final-openmm.json').read_bytes())
    assert second['reference_execution_skipped_after_interruption'] is True
    assert second['reference_work']['attempted_getState_energy_force_observations'] == 0
