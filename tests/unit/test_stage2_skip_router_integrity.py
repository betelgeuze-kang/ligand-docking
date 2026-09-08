"""New synthetic routing controls; no chemistry, models, or external workloads."""
from __future__ import annotations

import copy

import pytest

from tools.product.stage2_skip_router import apply_stage2_skip_router, route_stage2_candidate


def _measured(**overrides):
    row = dict(prior_rank_proxy=.95, affinity_hint=0., onsps_norm=0., mw_norm=0.)
    row.update(overrides)
    return row


@pytest.mark.parametrize("field", ["affinity_hint", "onsps_norm", "mw_norm"])
@pytest.mark.parametrize("missing", [None, "", "bad", float("nan"), float("inf"), -1., 1.1, True])
def test_unusable_auxiliary_never_becomes_a_low_value(field, missing):
    row = _measured(**{field: missing})
    assert len(apply_stage2_skip_router([row])[0]) == 1
    assert route_stage2_candidate(**row)["stage2_skip_applied"] is False


@pytest.mark.parametrize("field", ["affinity_hint", "onsps_norm", "mw_norm"])
def test_absent_auxiliary_differs_from_measured_zero(field):
    row = _measured()
    del row[field]
    assert len(apply_stage2_skip_router([row])[0]) == 1
    assert route_stage2_candidate(**row)["stage2_skip_applied"] is False
    assert apply_stage2_skip_router([_measured()])[0] == []
    assert route_stage2_candidate(**_measured())["stage2_skip_applied"] is True


@pytest.mark.parametrize("declaration", [
    {"is_ood": True}, {"is_ood": "true"}, {"ood": "1"}, {"out_of_distribution": 1},
    {"is_ood": None}, {"is_ood": "unknown"}, {"is_ood": float("nan")},
    {"role": "ood_eval"}, {"split": "near_ood_eval"}, {"dataset_split": "far-ood-eval"},
    {"routing_evidence_status": "insufficient"}, {"routing_evidence_status": "ood"},
    {"routing_evidence_status": "unknown"}, {"routing_evidence_status": "insufficient_or_invalid"},
    {"split": "out_of_distribution"}, {"dataset_split": "out-of-distribution"},
    {"role": "out of distribution"},
])
def test_declared_ood_or_insufficient_evidence_is_retained(declaration):
    selected, summary = apply_stage2_skip_router([_measured(**declaration)])
    assert len(selected) == 1
    assert summary["stage2_skip_eligible_count"] == summary["stage2_skip_count"] == 0


@pytest.mark.parametrize("declaration", [{"is_ood": False}, {"is_ood": "false"},
                                          {"is_ood": "0.0"}, {"routing_evidence_status": "valid"}])
def test_usable_explicit_declarations_allow_measured_positive_control(declaration):
    assert apply_stage2_skip_router([_measured(**declaration)])[0] == []


@pytest.mark.parametrize("kwargs", [{"is_ood": True}, {"is_ood": "unknown"},
                                   {"routing_evidence_status": "insufficient"}])
def test_direct_entry_honors_evidence_veto(kwargs):
    assert route_stage2_candidate(**_measured(), **kwargs)["stage2_skip_applied"] is False


def test_aliases_preserve_zero_and_do_not_hide_invalid_primary_evidence():
    row = dict(rank_pct="0.95", ligand_affinity_hint="0", ligand_onsps_norm="0", ligand_mw_norm="0")
    assert apply_stage2_skip_router([row])[0] == []
    for field in ("affinity_hint", "onsps_norm", "mw_norm", "prior_rank_proxy"):
        assert len(apply_stage2_skip_router([dict(row, **{field: "bad"})])[0]) == 1
    assert len(apply_stage2_skip_router([dict(row, prior_rank_proxy=0.)])[0]) == 1


def test_target_controls_tail_eligibility_without_filling_a_quota():
    row = _measured(prior_rank_proxy=.5)
    assert route_stage2_candidate(**row, skip_fraction_target=.1)["stage2_skip_applied"] is False
    assert route_stage2_candidate(**row, skip_fraction_target=.6)["stage2_skip_applied"] is True
    assert route_stage2_candidate(**_measured(), skip_fraction_target=0.)["stage2_skip_applied"] is False
    rows = [dict(id="unknown"), _measured(id="tail")]
    selected, summary = apply_stage2_skip_router(rows, skip_fraction_target=1.)
    assert [row["id"] for row in selected] == ["unknown"]
    assert summary["stage2_skip_count"] == 1
    # A rank threshold does not itself cap the realized batch fraction.
    assert apply_stage2_skip_router([_measured()] * 4, skip_fraction_target=.1)[1]["stage2_skip_count"] == 4


@pytest.mark.parametrize("fraction,count", [(0., 0), (.19, 0), (.4, 2), (1., 4)])
def test_separate_hard_cap_uses_total_denominator_and_only_eligible_rows(fraction, count):
    rows = [_measured(id="mid", prior_rank_proxy=.7), _measured(id="tail", prior_rank_proxy=1.),
            _measured(id="tie", prior_rank_proxy=1.), _measured(id="tail2", prior_rank_proxy=.9),
            {"id": "unknown"}]
    before = copy.deepcopy(rows)
    selected, summary = apply_stage2_skip_router(rows, max_skip_fraction=fraction)
    assert rows == before
    assert summary["stage2_skip_count"] == count
    assert summary["stage2_skip_eligible_count"] == 4
    assert summary["row_count"] == summary["stage2_full_count"] + count == 5
    assert summary["stage2_skip_fraction"] <= fraction
    assert "unknown" in [row["id"] for row in selected]
    if count == 2:
        assert [row["id"] for row in summary["skipped_rows"]] == ["tail", "tie"]
        assert selected[0]["stage2_skip_reason"] == "skip_hard_cap_requires_full_trajectory"
        assert selected[0]["stage2_skip_eligible"] is True


@pytest.mark.parametrize("value", [-1., 1.1, "bad", float("nan"), float("inf"), True])
def test_invalid_hard_cap_fails_before_routing(value):
    with pytest.raises(ValueError, match="max_skip_fraction"):
        apply_stage2_skip_router([_measured()], max_skip_fraction=value)


def test_disable_has_explicit_reason_independent_of_target_and_cap():
    selected, summary = apply_stage2_skip_router([_measured()], enabled=False,
                                                  skip_fraction_target=1., max_skip_fraction=1.)
    assert len(selected) == 1
    assert selected[0]["stage2_skip_reason"] == "router_disabled"
    assert selected[0]["stage2_skip_eligible"] is False
    assert summary["router_enabled"] is False
    assert route_stage2_candidate(**_measured(), enabled=False)["stage2_skip_applied"] is False


def test_empty_batch_has_truthful_zero_accounting():
    selected, summary = apply_stage2_skip_router([], max_skip_fraction=.5)
    assert selected == []
    assert summary["row_count"] == summary["stage2_skip_count"] == summary["stage2_full_count"] == 0
    assert summary["stage2_skip_fraction"] == 0.


def test_reenable_revalidates_inputs_instead_of_trusting_prior_disabled_output():
    retained, _ = apply_stage2_skip_router([_measured()], enabled=False)
    selected, summary = apply_stage2_skip_router(retained, enabled=True)
    assert selected == []
    assert summary["stage2_skip_count"] == 1
