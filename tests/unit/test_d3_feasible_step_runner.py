"""A one-step audit must cover the original, actual last native state and retained state."""
import copy

import pytest
import torch

from betelgeuze_product.cpu_refinement_v1_2.provenance import digest
from docs.research.human_5ht6_d3_complex.feasible_step_development_experiment import select_audit_coordinates


def states():
    original = torch.tensor([[1., 2., 3.]], dtype=torch.float64)
    last = original + .01
    observations = {digest(x.tolist()): {"coordinates": x.tolist()} for x in (original, last)}
    return original, last, observations


@pytest.mark.parametrize("retained_last", [False, True])
def test_original_and_last_audit_covers_both_valid_one_step_outcomes(retained_last):
    original, last, observations = states()
    retained = last if retained_last else original
    audited = select_audit_coordinates(original, retained, observations, list(observations))
    assert torch.equal(audited, last)


def test_no_completed_trial_audits_original_and_reports_one_unique_state():
    original, _, _ = states()
    observations = {digest(original.tolist()): {"coordinates": original.tolist()}}
    assert torch.equal(select_audit_coordinates(original, original, observations, list(observations)), original)


def test_unobserved_retained_intermediate_cannot_escape_numerical_audit():
    original, _, observations = states()
    with pytest.raises(ValueError, match="retained_not_original_or_last"):
        select_audit_coordinates(original, original + .005, observations, list(observations))


def test_explicit_native_order_handles_a_repeated_original_after_another_state():
    original, last, observations = states()
    order = [digest(original.tolist()), digest(last.tolist()), digest(original.tolist())]
    assert torch.equal(select_audit_coordinates(original, original, observations, order), original)
    with pytest.raises(ValueError, match="retained_not_original_or_last"):
        select_audit_coordinates(original, last, observations, order)


def test_unknown_chronological_native_state_is_rejected():
    original, _, observations = states()
    with pytest.raises(ValueError, match="order_unknown"):
        select_audit_coordinates(original, original, observations, [*observations, "not-observed"])


@pytest.mark.parametrize("corruption", ["first_coordinate", "last_coordinate", "first_order", "missing", "shape", "nonfinite"])
def test_source_observation_selection_rejects_corrupt_or_missing_coordinates(corruption):
    original, _, observations = states()
    observations = copy.deepcopy(observations)
    if corruption == "first_coordinate":
        next(iter(observations.values()))["coordinates"][0][0] += .1
    elif corruption == "last_coordinate":
        next(reversed(observations.values()))["coordinates"][0][0] += .1
    elif corruption == "first_order":
        observations = dict(reversed(list(observations.items())))
    elif corruption == "missing":
        observations = {}
    elif corruption == "shape":
        next(reversed(observations.values()))["coordinates"] = [[1., 2.]]
    elif corruption == "nonfinite":
        next(reversed(observations.values()))["coordinates"][0][0] = float("nan")
    with pytest.raises(ValueError):
        select_audit_coordinates(original, original, observations, list(observations))
