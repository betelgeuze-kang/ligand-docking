"""Numerical audit coverage must follow call chronology and committed states."""
import copy
import hashlib

import pytest
import torch

from docs.research.human_5ht6_d3_complex import feasible_step_core as base
from docs.research.human_5ht6_d3_complex.feasible_trajectory_development_experiment import (
    observation_index, select_audit_attempts,
)


def xyz(x):
    return torch.tensor([[x, 0., 0.]], dtype=torch.float64)


def observation(i, x, energy=0.):
    point = xyz(x)
    return {"objective_point_attempt": i, "coordinates_angstrom": point.tolist(),
            "coordinate_bytes_sha256": hashlib.sha256(base.coordinate_key(point.numpy())).hexdigest(),
            "status": "completed", "stage": "completed", "total_energy_kcal_mol": energy,
            "total_gradient_kcal_mol_angstrom": [[1., 0., 0.]],
            "internal_energy_kcal_mol": 0., "internal_gradient_kcal_mol_angstrom": [[0., 0., 0.]]}


def test_audit_keeps_accepted_intermediate_after_rejected_tail():
    rows = [observation(1, 0), observation(2, -.05), observation(3, -.10), observation(4, -.075)]
    selected, _ = select_audit_attempts(xyz(0), xyz(-.05),
        {"accepted_objective_point_attempts": [2], "source_integrity_valid": True}, rows)
    assert [i for i, _ in selected] == [2, 4]
    assert torch.equal(selected[0][1], xyz(-.05))


def test_every_accepted_state_is_covered_without_double_counting_last_attempt():
    rows = [observation(1, 0), observation(2, -.05), observation(3, -.10)]
    selected, _ = select_audit_attempts(xyz(0), xyz(-.10),
        {"accepted_objective_point_attempts": [2, 3], "source_integrity_valid": True}, rows)
    assert [i for i, _ in selected] == [2, 3]


def test_failed_native_tail_retains_prior_successful_observation():
    rows = [observation(1, 0), observation(2, -.05), observation(3, -.10)]
    rows[-1].update(status="failed", stage="additional_internal_force", error={"reason": "deliberate"})
    selected, _ = select_audit_attempts(xyz(0), xyz(-.05),
        {"accepted_objective_point_attempts": [2], "source_integrity_valid": True}, rows)
    assert [i for i, _ in selected] == [2]
    assert len(rows) == 3


def test_repeated_coordinates_keep_call_ids_and_reject_disagreeing_measurement():
    rows = [observation(1, 0), observation(2, -.05), observation(3, 0)]
    indexed, compatible = observation_index(rows)
    assert list(indexed) == [1, 2, 3]
    assert len(compatible) == 2
    rows[-1]["internal_energy_kcal_mol"] = 1.
    with pytest.raises(ValueError, match="repeated_native_state_disagrees"):
        observation_index(rows)


@pytest.mark.parametrize("ids", [[1, 1], [2, 1], [1, 3]])
def test_duplicate_reordered_or_missing_call_rejected(ids):
    with pytest.raises(ValueError, match="native_observation_order_mismatch"):
        observation_index([observation(ids[0], 0), observation(ids[1], -.05)])


@pytest.mark.parametrize("accepted,retained", [([3], -.05), ([2, 2], -.05), ([2], -.1), ([1], 0)])
def test_unknown_duplicate_or_wrong_retained_state_rejected(accepted, retained):
    with pytest.raises(ValueError):
        select_audit_attempts(xyz(0), xyz(retained),
            {"accepted_objective_point_attempts": accepted, "source_integrity_valid": True},
            [observation(1, 0), observation(2, -.05)])


def test_invalid_source_cannot_start_numerical_claim():
    with pytest.raises(ValueError, match="retained_not_last_published_incumbent"):
        select_audit_attempts(xyz(0), xyz(0),
            {"accepted_objective_point_attempts": [], "source_integrity_valid": False}, [observation(1, 0)])


@pytest.mark.parametrize("field,value", [
    ("coordinate_bytes_sha256", "0" * 64),
    ("total_gradient_kcal_mol_angstrom", [[float("nan"), 0., 0.]]),
    ("total_energy_kcal_mol", float("inf")),
    ("status", "started"),
])
def test_invalid_native_payload_rejected(field, value):
    row = observation(1, 0)
    row[field] = copy.deepcopy(value)
    with pytest.raises(ValueError):
        observation_index([row])
