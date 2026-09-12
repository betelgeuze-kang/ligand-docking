"""Fresh synthetic controls for request-local canonical validation reuse."""
from contextlib import nullcontext
from contextvars import copy_context
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor

import pytest

from betelgeuze_engine.product import prepared_validation as validation
from betelgeuze_engine.product import prepared_rigid_poses as poses
from betelgeuze_engine_v2.molecular import AllAtomSystem
from betelgeuze_engine_v2.molecular.validation import MolecularValidationError
from betelgeuze_engine_v2.stack_round3_molecular import MolecularIntegrityError
from tests.unit.test_v2_prepared_cross_interaction import (
    _system, _state_with_nested_tensor_metadata, _mutate_without_parent_tensor_version,
)
from tests.unit.test_prepared_rigid_poses import _request, _pose


def _observe_owner(monkeypatch):
    original = validation.require_valid_all_atom_system
    calls = []

    def observed(system, **kwargs):
        calls.append(system)
        return original(system, **kwargs)

    monkeypatch.setattr(validation, "require_valid_all_atom_system", observed)
    return calls


def test_exact_live_object_reuses_owner_report_with_full_integrity_each_time(monkeypatch):
    system = _system([[0, 0, 0]], [0.2])
    calls = _observe_owner(monkeypatch)
    original = AllAtomSystem.assert_integrity
    checks = []

    def checked(self):
        checks.append(self)
        return original(self)

    monkeypatch.setattr(AllAtomSystem, "assert_integrity", checked)
    with validation.prepared_validation_scope():
        first = validation.require_valid_prepared_system(system)
        before = len(checks)
        second = validation.require_valid_prepared_system(system)
        assert second is first
        assert len(checks) == before + 1
    assert len(calls) == 1
    assert first.valid and not first.scientific_claim_ready


@pytest.mark.parametrize("kind", ["numpy", "data", "system_metadata", "atom_metadata", "provenance_metadata"])
def test_cache_hit_rejects_changes_that_do_not_increment_tensor_version(kind):
    system = _state_with_nested_tensor_metadata()[0]
    with validation.prepared_validation_scope():
        validation.require_valid_prepared_system(system)
        _mutate_without_parent_tensor_version(system, kind)
        with pytest.raises(MolecularIntegrityError, match="changed after construction"):
            validation.require_valid_prepared_system(system)


def test_nested_and_later_requests_validate_independently(monkeypatch):
    system = _system([[0, 0, 0]], [0.2])
    calls = _observe_owner(monkeypatch)
    with validation.prepared_validation_scope():
        outer = validation.require_valid_prepared_system(system)
        with validation.prepared_validation_scope():
            inner = validation.require_valid_prepared_system(system)
            assert inner is not outer and inner == outer
        assert validation.require_valid_prepared_system(system) is outer
    validation.require_valid_prepared_system(system)
    with validation.prepared_validation_scope():
        validation.require_valid_prepared_system(system)
    assert len(calls) == 4


def test_exception_closes_scope_and_does_not_leave_reusable_admission(monkeypatch):
    system = _system([[0, 0, 0]], [0.2])
    calls = _observe_owner(monkeypatch)
    with pytest.raises(RuntimeError, match="interrupted"):
        with validation.prepared_validation_scope():
            validation.require_valid_prepared_system(system)
            raise RuntimeError("interrupted")
    assert validation._REQUEST_VALIDATION.get() is None
    validation.require_valid_prepared_system(system)
    assert len(calls) == 2


def test_equal_reconstructed_objects_are_freshly_validated(monkeypatch):
    first = _system([[0, 0, 0]], [0.2])
    second = replace(first)
    calls = _observe_owner(monkeypatch)
    with validation.prepared_validation_scope():
        a = validation.require_valid_prepared_system(first)
        b = validation.require_valid_prepared_system(second)
        assert a.system_sha256 == b.system_sha256
    assert len(calls) == 2


def test_warning_policy_is_reapplied_to_reused_reports():
    system = replace(_system([[0, 0, 0]], [0.2]), system_id="")
    with validation.prepared_validation_scope():
        report = validation.require_valid_prepared_system(system)
        assert report.warnings
        with pytest.raises(MolecularValidationError):
            validation.require_valid_prepared_system(system, warnings_as_errors=True)
        assert validation.require_valid_prepared_system(system) is report


def test_invalid_system_is_not_cached_or_made_valid(monkeypatch):
    system = replace(_system([[0, 0, 0]], [0.2]), coordinate_unit="nanometer")
    calls = _observe_owner(monkeypatch)
    with validation.prepared_validation_scope():
        for _ in range(2):
            with pytest.raises(MolecularValidationError):
                validation.require_valid_prepared_system(system)
        assert validation._REQUEST_VALIDATION.get()[1] == {}
    assert len(calls) == 2


def test_entry_count_is_bounded_and_eviction_revalidates(monkeypatch):
    monkeypatch.setattr(validation, "_MAX_ENTRIES", 2)
    systems = [_system([[float(i), 0, 0]], [0.2]) for i in range(3)]
    calls = _observe_owner(monkeypatch)
    with validation.prepared_validation_scope():
        for system in systems:
            validation.require_valid_prepared_system(system)
        assert len(validation._REQUEST_VALIDATION.get()[1]) == 2
        validation.require_valid_prepared_system(systems[0])
    assert len(calls) == 4


def test_copied_context_does_not_share_cache_across_threads(monkeypatch):
    system = _system([[0, 0, 0]], [0.2])
    calls = _observe_owner(monkeypatch)
    with validation.prepared_validation_scope():
        first = validation.require_valid_prepared_system(system)
        context = copy_context()
        with ThreadPoolExecutor(max_workers=1) as executor:
            second = executor.submit(context.run, validation.require_valid_prepared_system, system).result()
        assert second == first and second is not first
    assert len(calls) == 2


def _without_observation_costs(value):
    if isinstance(value, dict):
        return {key: _without_observation_costs(child) for key, child in value.items() if key != "cost"}
    if isinstance(value, list):
        return [_without_observation_costs(child) for child in value]
    return value


def test_real_rigid_consumer_preserves_results_and_failures_against_uncached_owner(tmp_path, monkeypatch):
    request = _request(tmp_path)
    request["poses"] += [_pose("overlap", -4), _pose("outside", 100)]
    cached = poses.evaluate_rigid_pose_request(request)
    monkeypatch.setattr(poses, "prepared_validation_scope", nullcontext)
    uncached = poses.evaluate_rigid_pose_request(request)
    assert cached["denominator"] == uncached["denominator"] == {
        "requested": 4, "evaluated": 2, "failed": 2, "skipped": 0,
    }
    # Source coordinates, atom/parameter identities, all force components,
    # every geometry observation and failure remain identical. Timing is an
    # independent observation, including the existing preparation aggregate.
    for report in (cached, uncached):
        report["preparation_observation"].pop("load_wall_seconds")
    assert _without_observation_costs(cached) == _without_observation_costs(uncached)


@pytest.mark.parametrize("kind", ["numpy", "data", "system_metadata", "atom_metadata", "provenance_metadata"])
def test_real_physics_rejects_mutated_cached_validation_at_original_boundaries(monkeypatch, kind):
    from tests.unit.test_v2_prepared_cross_interaction import _evaluate
    from betelgeuze_engine.product import v2_cross_interaction as cross
    state = _state_with_nested_tensor_metadata()
    original = cross._validate_component_minimum_distance

    def mutate(system, side):
        original(system, side)
        if side == "ligand":
            _mutate_without_parent_tensor_version(state[0], kind)

    with validation.prepared_validation_scope():
        validation.require_valid_prepared_system(state[0])
        validation.require_valid_prepared_system(state[1])
        monkeypatch.setattr(cross, "_validate_component_minimum_distance", mutate)
        with pytest.raises(MolecularIntegrityError):
            _evaluate(*state)
