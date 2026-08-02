from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from tools.verify_engine_v2_phase25_cohort_admission import verify_policy


_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> dict[str, object]:
    return json.loads((_ROOT / name).read_text(encoding="utf-8"))


def _rehash_policy(policy: dict[str, object]) -> None:
    projection = dict(policy)
    projection.pop("policy_sha256", None)
    raw = json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    policy["policy_sha256"] = hashlib.sha256(raw).hexdigest()


def _rehash_payload(payload: dict[str, object], field: str) -> None:
    projection = dict(payload)
    projection.pop(field, None)
    raw = json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    payload[field] = hashlib.sha256(raw).hexdigest()


def _inputs() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    return (
        _load("config/engine_v2_phase25_cohort_admission.json"),
        _load("config/engine_v2_public_redocking_stage0_threshold_evidence.json"),
        _load("config/engine_v2_public_redocking_contamination_registry.json"),
        _load("config/engine_v2_fresh_redocking_holdout_manifest.json"),
    )


def test_tracked_phase25_cohort_policy_is_valid() -> None:
    verify_policy(*_inputs())


def test_threshold_membership_cannot_expand_the_failure_atlas() -> None:
    policy, threshold, registry, fresh = _inputs()
    widened = copy.deepcopy(policy)
    admission = widened["current_admission"]
    assert isinstance(admission, dict)
    admitted = admission["admitted_case_ids"]
    assert isinstance(admitted, list)
    admitted.append("7A9E_R4W")
    admission["admitted_case_count"] = 8
    _rehash_policy(widened)

    with pytest.raises(ValueError, match="admitted_case_ids"):
        verify_policy(widened, threshold, registry, fresh)


def test_v9_v10_freeze_cannot_be_removed_with_a_valid_self_hash() -> None:
    policy, threshold, registry, fresh = _inputs()
    weakened = copy.deepcopy(policy)
    stop_rule = weakened["local_refinement_experiment_stop_rule"]
    assert isinstance(stop_rule, dict)
    stop_rule["new_refinement_versions_prohibited_while_frozen"] = []
    _rehash_policy(weakened)

    with pytest.raises(ValueError, match="prohibited refinement versions"):
        verify_policy(weakened, threshold, registry, fresh)


def test_expansion_cannot_authorize_fresh_execution_with_a_valid_self_hash() -> None:
    policy, threshold, registry, fresh = _inputs()
    weakened = copy.deepcopy(policy)
    expansion = weakened["expansion_gate"]
    assert isinstance(expansion, dict)
    claim_boundary = expansion["claim_boundary"]
    assert isinstance(claim_boundary, dict)
    claim_boundary["fresh_execution_authorized"] = True
    _rehash_policy(weakened)

    with pytest.raises(ValueError, match="expansion claim boundary"):
        verify_policy(weakened, threshold, registry, fresh)


def test_ab_semantics_cannot_change_with_a_valid_self_hash() -> None:
    policy, threshold, registry, fresh = _inputs()
    weakened = copy.deepcopy(policy)
    stop_rule = weakened["local_refinement_experiment_stop_rule"]
    assert isinstance(stop_rule, dict)
    profile = stop_rule["ab_profile"]
    assert isinstance(profile, dict)
    profile["experimental"] = "post_result_best_state"
    _rehash_policy(weakened)

    with pytest.raises(ValueError, match="A/B profile"):
        verify_policy(weakened, threshold, registry, fresh)


def test_unknown_execution_authority_is_rejected() -> None:
    policy, threshold, registry, fresh = _inputs()
    weakened = copy.deepcopy(policy)
    authority = weakened["authority_boundary"]
    assert isinstance(authority, dict)
    authority["historical_ab_execution_authorized"] = True
    _rehash_policy(weakened)

    with pytest.raises(ValueError, match="authority boundary"):
        verify_policy(weakened, threshold, registry, fresh)


def test_bool_as_int_cannot_bypass_authority_boundary() -> None:
    policy, threshold, registry, fresh = _inputs()
    weakened = copy.deepcopy(policy)
    authority = weakened["authority_boundary"]
    assert isinstance(authority, dict)
    authority["new_execution_authorized"] = 0
    _rehash_policy(weakened)

    with pytest.raises(ValueError, match="new_execution_authorized"):
        verify_policy(weakened, threshold, registry, fresh)


def test_narrative_remainder_cannot_gain_a_roster() -> None:
    policy, threshold, registry, fresh = _inputs()
    weakened = copy.deepcopy(policy)
    evidence = weakened["distinguished_non_admission_evidence"]
    assert isinstance(evidence, dict)
    narrative = evidence["narrative_remainder"]
    assert isinstance(narrative, dict)
    narrative["ordered_case_ids"] = ["invented_case"]
    _rehash_policy(weakened)

    with pytest.raises(ValueError, match="narrative remainder"):
        verify_policy(weakened, threshold, registry, fresh)


def test_threshold_difference_reason_cannot_be_relabelled() -> None:
    policy, threshold, registry, fresh = _inputs()
    weakened = copy.deepcopy(policy)
    relationships = weakened["cohort_relationships"]
    assert isinstance(relationships, dict)
    rows = relationships["source_paired_not_failure_atlas"]
    assert isinstance(rows, list)
    assert isinstance(rows[0], dict)
    rows[0]["reason"] = "failure_atlas_member"
    _rehash_policy(weakened)

    with pytest.raises(ValueError, match="source-paired minus failure-atlas"):
        verify_policy(weakened, threshold, registry, fresh)


def test_jointly_resealed_threshold_artifact_and_policy_are_rejected() -> None:
    policy, threshold, registry, fresh = _inputs()
    reports = threshold["source_reports_sha256"]
    assert isinstance(reports, dict)
    first_path = next(iter(reports))
    reports[first_path] = "0" * 64
    _rehash_payload(threshold, "evidence_sha256")
    evidence = policy["distinguished_non_admission_evidence"]
    assert isinstance(evidence, dict)
    authority = evidence["stage0_threshold_authority"]
    assert isinstance(authority, dict)
    authority["evidence_self_sha256"] = threshold["evidence_sha256"]
    _rehash_policy(policy)

    with pytest.raises(ValueError, match="threshold authority is not the frozen"):
        verify_policy(policy, threshold, registry, fresh)


def test_jointly_resealed_registry_artifact_and_policy_are_rejected() -> None:
    policy, threshold, registry, fresh = _inputs()
    registry["historical_300_claim_role"] = "promotion"
    _rehash_payload(registry, "registry_sha256")
    expansion = policy["expansion_gate"]
    assert isinstance(expansion, dict)
    scope = expansion["scope_identity"]
    assert isinstance(scope, dict)
    scope["historical_registry_self_sha256"] = registry["registry_sha256"]
    _rehash_policy(policy)

    with pytest.raises(ValueError, match="historical contamination registry"):
        verify_policy(policy, threshold, registry, fresh)


def test_jointly_resealed_fresh_manifest_is_rejected() -> None:
    policy, threshold, registry, fresh = _inputs()
    cases = fresh["cases"]
    assert isinstance(cases, list)
    assert isinstance(cases[0], dict)
    cases[0]["case_id"] = "MUTATED"
    fresh["case_ids_sha256"] = hashlib.sha256(
        json.dumps(
            [row["case_id"] for row in cases],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    _rehash_payload(fresh, "manifest_sha256")

    with pytest.raises(ValueError, match="cohort scope overlaps"):
        verify_policy(policy, threshold, registry, fresh)


def test_clearance_policy_and_cohort_binding_cannot_drift() -> None:
    policy, threshold, registry, fresh = _inputs()
    stop_rule = policy["local_refinement_experiment_stop_rule"]
    assert isinstance(stop_rule, dict)
    profile = stop_rule["ab_profile"]
    assert isinstance(profile, dict)
    profile["clearance_policy_sha256"] = "0" * 64
    _rehash_policy(policy)

    with pytest.raises(ValueError, match="A/B profile"):
        verify_policy(policy, threshold, registry, fresh)


def test_no_go_precedence_cannot_be_removed() -> None:
    policy, threshold, registry, fresh = _inputs()
    stop_rule = policy["local_refinement_experiment_stop_rule"]
    assert isinstance(stop_rule, dict)
    decision = stop_rule["decision_logic"]
    assert isinstance(decision, dict)
    decision["no_go_trigger_precedence"] = False
    _rehash_policy(policy)

    with pytest.raises(ValueError, match="decision logic"):
        verify_policy(policy, threshold, registry, fresh)
