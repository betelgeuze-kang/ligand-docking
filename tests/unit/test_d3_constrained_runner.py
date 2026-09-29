"""Reject independent-oracle and optimizer state/derivative mismatches."""
import copy

import pytest

from betelgeuze_product.cpu_refinement_v1_2.provenance import digest
from docs.research.human_5ht6_d3_complex.constrained_development_experiment import verify_optimizer_derivatives


def documents():
    xyz = [[1.0, 2.0, 3.0]]
    native = {"internal_energy": -3.0, "cross_components": {"cross": 5.0},
              "internal_forces": [[1.0, 2.0, 3.0]], "cross_forces": [[.5, .25, .125]]}
    reference = {"internal_energy": -3.0, "cross_energy": 5.0,
                 "internal_forces": native["internal_forces"], "cross_forces": native["cross_forces"]}
    observation = {"energy": 2.0, "internal_energy": -3.0,
                   "total_gradient": [[-1.5, -2.25, -3.125]], "internal_gradient": [[-1.0, -2.0, -3.0]]}
    audit = {"snapshots": [{"coordinates_angstrom": xyz, "native": native,
                            "reference_same_math": copy.deepcopy(reference)}]}
    return audit, {digest(xyz): observation}


def test_total_and_strain_derivatives_are_bound_to_both_native_and_independent_reference():
    audit, observations = documents()
    result = verify_optimizer_derivatives(audit, observations)
    assert result[0]["passed"]
    assert len(result[0]["absolute_errors"]) == 8
    assert set(result[0]["absolute_errors"].values()) == {0.0}


@pytest.mark.parametrize("field", ["energy", "internal_energy", "total_gradient", "internal_gradient"])
def test_wrong_optimizer_energy_or_derivative_is_rejected(field):
    audit, observations = documents()
    row = next(iter(observations.values()))
    if isinstance(row[field], list):
        row[field][0][0] += 1e-5
    else:
        row[field] += 1e-5
    with pytest.raises(ValueError, match="optimizer_derivative"):
        verify_optimizer_derivatives(audit, observations)


@pytest.mark.parametrize("field", ["internal_forces", "cross_forces", "internal_energy", "cross_energy"])
def test_native_agreement_does_not_hide_independent_reference_mismatch(field):
    audit, observations = documents()
    row = audit["snapshots"][0]["reference_same_math"]
    if isinstance(row[field], list):
        row[field][0][0] += 1e-5
    else:
        row[field] += 1e-5
    with pytest.raises(ValueError, match="optimizer_derivative"):
        verify_optimizer_derivatives(audit, observations)


def test_coordinate_state_must_have_an_actual_optimizer_observation():
    audit, observations = documents()
    audit["snapshots"][0]["coordinates_angstrom"][0][0] += .1
    with pytest.raises(KeyError):
        verify_optimizer_derivatives(audit, observations)
