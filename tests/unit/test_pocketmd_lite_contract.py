from __future__ import annotations

import copy
from dataclasses import replace
import json

import pandas as pd
import pytest

import betelgeuze_engine.product.pocketmd_admission_authority as admission_module
from betelgeuze_engine.product.pocketmd_admission_authority import (
    derive_pocketmd_admission_batch,
    validate_pocketmd_admission_batch,
)
from betelgeuze_engine.product.selection_score_authority import SelectionScoreAuthority
from betelgeuze_product.pocketmd_lite_contract import (
    BAND_ABSTAIN,
    BAND_COARSE_ONLY,
    BAND_GREEN,
    BAND_RED,
    BAND_YELLOW,
    PocketMdAdmissionPolicy,
    PocketMdLiteError,
    build_pocketmd_lite_assessment,
    build_pocketmd_lite_report,
    decide_pocketmd_admission,
    is_refine_selected,
)


_AUTHORITY = SelectionScoreAuthority.create(
    score_column="binding_score_composite_v7",
    score_direction="ascending",
)
_BOUND_POLICY = PocketMdAdmissionPolicy.create(
    selection_policy_sha256=_AUTHORITY.policy_sha256,
    selection_authority_schema_version=_AUTHORITY.schema_version,
)


def _assessment(candidate: dict, **kwargs):
    batch = derive_pocketmd_admission_batch(
        pd.DataFrame([candidate]),
        authority=_AUTHORITY,
        policy=_BOUND_POLICY,
        entry_id_column="entry_id",
    )
    return build_pocketmd_lite_report(
        [candidate],
        admission_batch=batch,
        **kwargs,
    )["rows"][0]


def _green_candidate(entry_id: str = "LIG-1") -> dict:
    return {
        "entry_id": entry_id,
        "target": "ADRB2",
        "family": "gpcr",
        "binding_energy_mmpbsa_kcal_mol_proxy": -7.0,
        "binding_score_composite_v7": -8.0,
        "upstream_topk_selected": True,
        "rank_pct": 0.01,
        "authority_rank_global": 1,
        "authority_population_size": 100,
        "local_min_ligand_rmsd_a": 1.5,
        "hbond_persistence": 0.8,
        "contact_persistence": 0.75,
        "clash_count": 0,
    }


def test_direct_compatibility_boolean_cannot_authorize_refinement() -> None:
    assert is_refine_selected(family="gpcr", target="ADRB2", rank_pct=0.01) is False
    assert (
        is_refine_selected(
            family="transporter",
            target="ADRB2",
            base_proxy_value=-7.0,
            upstream_topk_selected=True,
            rank_pct=0.01,
            authority_rank_global=1,
            authority_population_size=100,
            selection_policy_sha256=_AUTHORITY.policy_sha256,
            selection_authority_schema_version="selection_score_authority_v2",
        )
        is False
    )
    assert (
        is_refine_selected(
            family="gpcr",
            target="ADRB2",
            base_proxy_value=-7.0,
            upstream_topk_selected=True,
            rank_pct=0.01,
            authority_rank_global=1,
            authority_population_size=100,
            selection_policy_sha256=_AUTHORITY.policy_sha256,
            selection_authority_schema_version="selection_score_authority_v2",
        )
        is False
    )


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"target_selected_count": 8}, "target_cap_reached"),
        ({"job_selected_count": 32}, "job_cap_reached"),
        ({"cumulative_cost": 32.0}, "cost_budget_exceeded"),
        ({"rank_pct": float("nan")}, "invalid_rank_pct"),
        ({"rank_pct": float("inf")}, "invalid_rank_pct"),
        ({"base_proxy_value": float("inf")}, "base_proxy_ineligible"),
    ],
)
def test_admission_caps_budget_and_nonfinite_rank_fail_closed(overrides, reason) -> None:
    kwargs = {
        "family": "gpcr",
        "target": "ADRB2",
        "base_proxy_value": -7.0,
        "upstream_topk_selected": True,
        "rank_pct": 0.01,
        "authority_rank_global": 1,
        "authority_population_size": 100,
        "target_selected_count": 0,
        "job_selected_count": 0,
        "cumulative_cost": 0.0,
    }
    decision = decide_pocketmd_admission(
        **{**kwargs, **overrides},
        policy=_BOUND_POLICY,
    )
    assert decision["admitted"] is False
    assert reason in decision["reason_codes"]


def test_selected_for_refine_flag_cannot_override_admission() -> None:
    candidate = {
        **_green_candidate(),
        "family": "transporter",
        "rank_pct": 0.5,
        "selected_for_refine": True,
    }
    assessment = _assessment(candidate)
    assert assessment["selected_for_refine"] is False
    assert assessment["selected_for_refine_override_ignored"] is True
    assert assessment["band"] == BAND_COARSE_ONLY
    assert assessment["reason_code"] == "ineligible_family"


def test_green_band_is_claim_safe() -> None:
    assessment = _assessment(_green_candidate())
    assert assessment["band"] == BAND_GREEN
    assert assessment["claim_safe"] is True
    assert assessment["local_min_survived"] is True
    assert assessment["review_flags"] == []


def test_unbound_single_candidate_assessment_cannot_be_claim_safe() -> None:
    fake_policy = PocketMdAdmissionPolicy.create(
        selection_policy_sha256="0" * 64,
        selection_authority_schema_version="selection_score_authority_v2",
    )
    assessment = build_pocketmd_lite_assessment(
        _green_candidate(),
        admission_policy=fake_policy,
    )

    assert assessment["selected_for_refine"] is False
    assert assessment["claim_safe"] is False
    assert assessment["band"] == BAND_COARSE_ONLY
    assert "untrusted_or_missing_derived_admission" in assessment["admission"]["reason_codes"]


def test_untrusted_or_crosswired_admission_receipt_is_rejected() -> None:
    candidate_a = _green_candidate("a")
    candidate_b = _green_candidate("b")
    batch = derive_pocketmd_admission_batch(
        pd.DataFrame([candidate_a, candidate_b]),
        authority=_AUTHORITY,
        policy=PocketMdAdmissionPolicy.create(
            rank_threshold_pct=1.0,
            selection_policy_sha256=_AUTHORITY.policy_sha256,
            selection_authority_schema_version=_AUTHORITY.schema_version,
        ),
        entry_id_column="entry_id",
    )
    policy = batch.policy()

    untrusted = build_pocketmd_lite_assessment(
        candidate_a,
        admission={},
        admission_policy=policy,
    )
    assert untrusted["claim_safe"] is False
    assert untrusted["band"] == BAND_COARSE_ONLY
    receipt_for_a = next(receipt for receipt in batch.receipts if receipt.entry_id == "a")
    detached = build_pocketmd_lite_assessment(
        candidate_a,
        admission=receipt_for_a,
        admission_policy=policy,
    )
    assert detached["claim_safe"] is False
    assert "detached_admission_receipt_ignored" in detached["admission"]["reason_codes"]

    with pytest.raises(PocketMdLiteError, match="population binding"):
        build_pocketmd_lite_report(
            [candidate_b, candidate_a],
            admission_batch=batch,
        )


def test_admission_batch_rejects_decision_forgery_and_population_replay() -> None:
    candidate = {
        **_green_candidate("same-id"),
        "family": "transporter",
        "smiles": "CCO",
    }
    batch = derive_pocketmd_admission_batch(
        pd.DataFrame([candidate]),
        authority=_AUTHORITY,
        policy=_BOUND_POLICY,
        entry_id_column="entry_id",
    )
    receipt = batch.receipts[0]
    forged_decision = {
        **receipt.decision(),
        "admitted": True,
        "reason_codes": [],
        "primary_reason": "",
    }
    forged_receipt = replace(
        receipt,
        decision_json=json.dumps(
            forged_decision,
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    forged_batch = replace(batch, receipts=(forged_receipt,))
    with pytest.raises(PocketMdLiteError, match="authentication mismatch"):
        build_pocketmd_lite_report([candidate], admission_batch=forged_batch)

    authenticate = next(
        cell.cell_contents
        for cell in validate_pocketmd_admission_batch.__closure__ or ()
        if callable(cell.cell_contents)
        and getattr(cell.cell_contents, "__name__", "") == "authenticate"
    )
    resigned_receipt = replace(
        forged_receipt,
        authentication_sha256=authenticate(
            admission_module._receipt_unsigned(forged_receipt)
        ),
    )
    resigned_batch = replace(batch, receipts=(resigned_receipt,))
    resigned_batch = replace(
        resigned_batch,
        authentication_sha256=authenticate(
            admission_module._batch_unsigned(resigned_batch)
        ),
    )
    with pytest.raises(PocketMdLiteError, match="decision semantics mismatch"):
        build_pocketmd_lite_report(
            [candidate],
            admission_batch=resigned_batch,
        )

    replay_candidate = {
        **candidate,
        "smiles": "[Na+]",
    }
    with pytest.raises(PocketMdLiteError, match="population binding"):
        build_pocketmd_lite_report(
            [replay_candidate],
            admission_batch=batch,
        )


def test_failed_survival_is_red() -> None:
    candidate = {**_green_candidate(), "local_min_ligand_rmsd_a": 3.5}
    assessment = _assessment(candidate)
    assert assessment["band"] == BAND_RED
    assert assessment["claim_safe"] is False
    assert assessment["reason_code"] == "local_min_did_not_survive"


def test_weak_persistence_or_clash_is_yellow() -> None:
    weak = _assessment(
        {**_green_candidate(), "hbond_persistence": 0.3}
    )
    clash = _assessment(
        {**_green_candidate(), "clash_count": 2}
    )
    assert weak["band"] == BAND_YELLOW
    assert "weak_hbond_persistence" in weak["review_flags"]
    assert clash["band"] == BAND_YELLOW
    assert "residual_clash" in clash["review_flags"]


@pytest.mark.parametrize("value", [None, float("nan"), float("inf")])
def test_missing_or_nonfinite_refinement_evidence_abstains(value) -> None:
    assessment = _assessment(
        {**_green_candidate(), "hbond_persistence": value}
    )
    assert assessment["band"] == BAND_ABSTAIN
    assert assessment["claim_safe"] is False
    assert assessment["reason_code"] == "missing_or_nonfinite_refinement_evidence"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("local_min_ligand_rmsd_a", -0.1),
        ("hbond_persistence", 1.1),
        ("contact_persistence", -0.1),
        ("clash_count", 0.5),
    ],
)
def test_out_of_range_refinement_evidence_abstains(field, value) -> None:
    assessment = _assessment(
        {**_green_candidate(), field: value}
    )
    assert assessment["band"] == BAND_ABSTAIN
    assert assessment["claim_safe"] is False
    assert assessment["reason_code"] == "invalid_refinement_evidence"


def test_policy_hash_is_deterministic_and_tamper_evident() -> None:
    first = PocketMdAdmissionPolicy.create()
    second = PocketMdAdmissionPolicy.create()
    assert first.policy_sha256 == second.policy_sha256
    assert (
        first.policy_sha256
        != PocketMdAdmissionPolicy.create(topk_global=1).policy_sha256
    )
    assert (
        first.policy_sha256
        != PocketMdAdmissionPolicy.create(base_proxy_column="other_proxy").policy_sha256
    )

    tampered = copy.deepcopy(first.to_dict())
    tampered["cost_budget"] = 64.0
    with pytest.raises(PocketMdLiteError, match="policy_sha256 mismatch"):
        PocketMdAdmissionPolicy.from_mapping(tampered)

    with pytest.raises(PocketMdLiteError, match="job caps must be positive"):
        PocketMdAdmissionPolicy(**{**vars(first), "max_per_job": 0})


def test_batch_report_enforces_target_and_budget_caps_in_order() -> None:
    policy = PocketMdAdmissionPolicy.create(
        rank_threshold_pct=1.0,
        max_per_target=1,
        max_per_job=2,
        cost_budget=2.0,
        unit_cost=1.0,
        selection_policy_sha256=_AUTHORITY.policy_sha256,
        selection_authority_schema_version=_AUTHORITY.schema_version,
        topk_global=4,
        topk_per_target=0,
    )
    candidates = [
        {**_green_candidate("a"), "rank_pct": 0.1},
        {**_green_candidate("b"), "rank_pct": 0.2},
        {**_green_candidate("c"), "target": "DRD2", "rank_pct": 0.3},
        {**_green_candidate("d"), "target": "HTR2A", "rank_pct": 0.4},
    ]
    admission_batch = derive_pocketmd_admission_batch(
        pd.DataFrame(candidates),
        authority=_AUTHORITY,
        policy=policy,
        entry_id_column="entry_id",
    )
    report = build_pocketmd_lite_report(
        candidates,
        admission_batch=admission_batch,
    )
    summary = report["summary"]
    assert summary["refined_count"] == 2
    assert summary["coarse_only_count"] == 2
    assert summary["admitted_target_counts"] == {"ADRB2": 1, "DRD2": 1}
    assert summary["admitted_cost"] == 2.0
    assert summary["admission_reason_counts"]["target_cap_reached"] == 1
    assert summary["admission_reason_counts"]["job_cap_reached"] == 1
    assert report["rows"][0]["caller_rank_pct_ignored"] is True
    assert report["rows"][0]["caller_upstream_topk_selected_ignored"] is True


@pytest.mark.parametrize(
    ("threshold_name", "value"),
    [
        ("hbond_persistence_min", float("nan")),
        ("contact_persistence_min", float("inf")),
        ("local_min_survival_rmsd_a", -1.0),
        ("max_clash_count", 0.5),
    ],
)
def test_invalid_grading_thresholds_fail_closed(threshold_name, value) -> None:
    with pytest.raises(PocketMdLiteError, match="threshold"):
        _assessment(
            _green_candidate(),
            **{threshold_name: value},
        )


def test_missing_entry_id_and_non_numeric_metric_raise() -> None:
    with pytest.raises(PocketMdLiteError, match="entry_id"):
        build_pocketmd_lite_assessment({"family": "gpcr"})
    with pytest.raises(PocketMdLiteError, match="hbond_persistence"):
        _assessment(
            {**_green_candidate(), "hbond_persistence": "high"}
        )


def test_empty_population_cannot_issue_admission_batch() -> None:
    with pytest.raises(PocketMdLiteError, match="non-empty"):
        derive_pocketmd_admission_batch(
            pd.DataFrame(columns=list(_green_candidate())),
            authority=_AUTHORITY,
            policy=_BOUND_POLICY,
            entry_id_column="entry_id",
        )
