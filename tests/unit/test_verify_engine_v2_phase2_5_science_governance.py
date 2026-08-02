from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

import tools.verify_engine_v2_phase2_5_science_governance as governance_verifier
from tools.verify_engine_v2_phase2_5_science_governance import (
    EXPECTED_POLICY_SHA256,
    verify_phase2_5_science_governance,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "config/engine_v2_phase2_5_science_governance.json"
REFERENCE_PATHS = (
    "tools/build_engine_v2_source_paired_failure_atlas.py",
    "config/engine_v2_public_redocking_contamination_registry.json",
    "config/engine_v2_fresh_redocking_holdout_manifest.json",
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _policy() -> dict[str, object]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _reseal(payload: dict[str, object], field: str) -> None:
    projection = copy.deepcopy(payload)
    projection.pop(field)
    payload[field] = hashlib.sha256(_canonical_bytes(projection)).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _copy_reference_repo(tmp_path: Path) -> Path:
    for relative in REFERENCE_PATHS:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, destination)
    return tmp_path


def _verify_resealed_semantic_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    policy: dict[str, object],
    *,
    match: str,
) -> None:
    _reseal(policy, "policy_sha256")
    mutated = tmp_path / "semantic-mutation.json"
    _write_json(mutated, policy)
    monkeypatch.setattr(
        governance_verifier,
        "EXPECTED_POLICY_SHA256",
        policy["policy_sha256"],
    )
    with pytest.raises(ValueError, match=match):
        verify_phase2_5_science_governance(mutated, REPO_ROOT)


def test_frozen_phase2_5_policy_verifies() -> None:
    assert (
        verify_phase2_5_science_governance(POLICY_PATH, REPO_ROOT)
        == EXPECTED_POLICY_SHA256
    )


def test_policy_is_preexecution_and_fail_closed() -> None:
    policy = _policy()
    phase2 = policy["phase2_historical_one_shot_ab"]
    execution = phase2["lifetime_execution"]

    assert execution == {
        "atomic_consume_implementation_available": False,
        "completed_runs": 0,
        "execution_authorized": False,
        "external_authority_available": False,
        "external_authority_receipt_sha256": None,
        "external_authority_type": "append_only_worm_atomic_single_consume",
        "failed_or_partial_attempt_consumes_run": True,
        "maximum_runs": 1,
        "overwrite_allowed": False,
        "partial_result_aggregate_replacement_allowed": False,
        "rerun_allowed": False,
        "resume_allowed": False,
        "run_budget_consumed": False,
    }
    assert policy["authority_boundary"]["protected_experiment_executed"] is False


def test_phase2_case_level_guardrails_and_no_go_precedence_are_frozen() -> None:
    policy = _policy()
    phase2 = policy["phase2_historical_one_shot_ab"]
    guardrails = phase2["go_decision"]["all_guardrails_required"]
    recovery_regression = phase2["no_go_decision"]["triggers"][3]
    penetration = phase2["no_go_decision"]["triggers"][4]

    assert guardrails[0]["baseline_case_ids_must_equal"] == ["6M73_FNR"]
    assert guardrails[0]["experimental_case_ids_must_equal"] == ["6M73_FNR"]
    assert guardrails[1]["baseline_case_ids"] == ["6T88_MWQ"]
    assert guardrails[1]["operator"] == "baseline_subset_of_experimental"
    assert guardrails[2]["baseline_case_ids"] == ["6T88_MWQ"]
    assert guardrails[2]["operator"] == "baseline_subset_of_experimental"
    assert recovery_regression["any_conditions"][0]["baseline_case_ids"] == ["6T88_MWQ"]
    assert recovery_regression["any_conditions"][1]["baseline_case_ids"] == ["6T88_MWQ"]
    assert penetration["evaluation_scope"] == (
        "each_selected_replacement_candidate_case_pair"
    )
    assert penetration["quantifier"] == "any"
    assert penetration["all_conditions"][1]["identity_join"] == [
        "case_id",
        "proposal_index",
        "source_proposal_fingerprint_sha256",
    ]
    assert phase2["go_decision"]["no_go_trigger_precedence"] is True
    assert (
        phase2["no_go_decision"]["any_trigger_closes_local_torsion_clearance_epic"]
        is True
    )


def test_phase2_requires_the_complete_activation_v2_authority() -> None:
    evidence = _policy()["phase2_historical_one_shot_ab"]["evidence_requirements"]

    assert evidence["activation_policy_sha256"] == (
        "988d0bb47bfa6ff934887e1e12b5a512b55aaf40033a04963d141c4ffefe212c"
    )
    assert evidence["activation_receipt_schema_id"].endswith("/2.0.0")
    assert evidence["activation_snapshot_schema_id"].endswith("/1.2.0")
    assert evidence["activated_state_independent_rederivation_required"] is True
    assert (
        evidence["authenticated_geometry_independent_clearance_rederivation_required"]
        is True
    )
    assert evidence["authenticated_torsion_move_replay_required"] is True
    assert evidence["exact_snapshot_runtime_type_required"] is True
    assert evidence["all_allocated_targets_required"] is True
    assert evidence["case_source_frozen_archive_member_authority_required"] is True
    assert evidence["historical_case_source_authority_sha256"] == (
        "4c083af473c369bf35fc34fdf4fe797ddbb2ef60b5474a78d6354415e3aa06bc"
    )
    assert evidence["current_v7_candidate_full_64_slot_lineage_required"] is True
    assert evidence["current_v7_lineage_receipt_schema_id"].endswith("/1.0.0")
    assert evidence["source_proposal_receipt_full_64_slot_lineage_required"] is True
    assert evidence["scorer_authority_bound_to_authenticated_input_required"] is True
    assert evidence["authenticated_rmsd_receipts_required"] is True
    assert evidence["non_target_and_retained_target_evidence_equality_required"] is True


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        ("preparation_failure_identity", "Phase 2 Go decision drifted"),
        ("top1_recovery_identity", "Phase 2 Go decision drifted"),
        ("top5_recovery_identity", "Phase 2 No-Go decision drifted"),
        ("penetration_identity_join", "Phase 2 No-Go decision drifted"),
        ("no_go_precedence", "Phase 2 Go decision drifted"),
        ("activation_policy_identity", "Phase 2 evidence requirements drifted"),
        ("activation_receipt_schema", "Phase 2 evidence requirements drifted"),
        ("activation_snapshot_schema", "Phase 2 evidence requirements drifted"),
        ("activation_all_targets", "Phase 2 evidence requirements drifted"),
        ("activation_state_rederivation", "Phase 2 evidence requirements drifted"),
        ("activation_clearance_rederivation", "Phase 2 evidence requirements drifted"),
        ("activation_torsion_replay", "Phase 2 evidence requirements drifted"),
        ("activation_snapshot_exact_type", "Phase 2 evidence requirements drifted"),
        ("activation_case_source_authority", "Phase 2 evidence requirements drifted"),
        ("activation_current_v7_lineage", "Phase 2 evidence requirements drifted"),
        ("activation_scorer_binding", "Phase 2 evidence requirements drifted"),
    ),
)
def test_resealed_phase2_case_level_semantic_drift_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    match: str,
) -> None:
    policy = _policy()
    phase2 = policy["phase2_historical_one_shot_ab"]
    guardrails = phase2["go_decision"]["all_guardrails_required"]
    triggers = phase2["no_go_decision"]["triggers"]

    if mutation == "preparation_failure_identity":
        guardrails[0]["experimental_case_ids_must_equal"] = ["5SD5_HWI"]
    elif mutation == "top1_recovery_identity":
        guardrails[1]["baseline_case_ids"] = ["5SD5_HWI"]
    elif mutation == "top5_recovery_identity":
        triggers[3]["any_conditions"][1]["baseline_case_ids"] = ["5SD5_HWI"]
    elif mutation == "penetration_identity_join":
        triggers[4]["all_conditions"][1]["identity_join"] = ["case_id"]
    elif mutation == "no_go_precedence":
        phase2["go_decision"]["no_go_trigger_precedence"] = False
    elif mutation == "activation_policy_identity":
        phase2["evidence_requirements"]["activation_policy_sha256"] = "0" * 64
    elif mutation == "activation_receipt_schema":
        phase2["evidence_requirements"]["activation_receipt_schema_id"] = (
            "betelgeuze.engine_v2_source_paired_clearance_selection_activation_"
            "receipt/1.0.0"
        )
    elif mutation == "activation_snapshot_schema":
        phase2["evidence_requirements"]["activation_snapshot_schema_id"] = (
            "betelgeuze.engine_v2_source_paired_torsion_rescue_activation_snapshot/1.1.0"
        )
    elif mutation == "activation_all_targets":
        phase2["evidence_requirements"]["all_allocated_targets_required"] = False
    elif mutation == "activation_state_rederivation":
        phase2["evidence_requirements"][
            "activated_state_independent_rederivation_required"
        ] = False
    elif mutation == "activation_clearance_rederivation":
        phase2["evidence_requirements"][
            "authenticated_geometry_independent_clearance_rederivation_required"
        ] = False
    elif mutation == "activation_torsion_replay":
        phase2["evidence_requirements"][
            "authenticated_torsion_move_replay_required"
        ] = False
    elif mutation == "activation_snapshot_exact_type":
        phase2["evidence_requirements"]["exact_snapshot_runtime_type_required"] = False
    elif mutation == "activation_case_source_authority":
        phase2["evidence_requirements"]["historical_case_source_authority_sha256"] = (
            "0" * 64
        )
    elif mutation == "activation_current_v7_lineage":
        phase2["evidence_requirements"][
            "current_v7_candidate_full_64_slot_lineage_required"
        ] = False
    elif mutation == "activation_scorer_binding":
        phase2["evidence_requirements"][
            "scorer_authority_bound_to_authenticated_input_required"
        ] = False
    else:  # pragma: no cover - the parametrization is frozen above.
        raise AssertionError(f"unknown mutation: {mutation}")

    _verify_resealed_semantic_failure(
        tmp_path,
        monkeypatch,
        policy,
        match=match,
    )


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (
            (
                "phase2_historical_one_shot_ab",
                "lifetime_execution",
                "execution_authorized",
            ),
            True,
        ),
        (("phase2_historical_one_shot_ab", "lifetime_execution", "completed_runs"), 1),
        (
            (
                "phase3_global_orientation_track",
                "activation",
                "implementation_authorized",
            ),
            True,
        ),
        (
            ("phase4_corpus_authority", "d1_fixed_decision_32", "case_ids_sha256"),
            "a" * 64,
        ),
        (("phase4_corpus_authority", "fresh_128", "post_result_tuning_allowed"), True),
        (("phase5_scorer_v2_gate", "scorer_v2_training_authorized"), True),
    ),
)
def test_resealed_authority_mutation_is_rejected(
    tmp_path: Path, path: tuple[str, ...], value: object
) -> None:
    policy = _policy()
    target = policy
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    _reseal(policy, "policy_sha256")
    mutated = tmp_path / "policy.json"
    _write_json(mutated, policy)

    with pytest.raises(ValueError, match="frozen identity"):
        verify_phase2_5_science_governance(mutated, REPO_ROOT)


def test_duplicate_json_key_is_rejected(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        POLICY_PATH.read_text(encoding="utf-8").replace(
            "{", '{\n  "policy_id": "duplicate",', 1
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate JSON key"):
        verify_phase2_5_science_governance(duplicate, REPO_ROOT)


def test_d0_source_authority_drift_is_rejected(tmp_path: Path) -> None:
    repo = _copy_reference_repo(tmp_path)
    d0_source = repo / "tools/build_engine_v2_source_paired_failure_atlas.py"
    d0_source.write_text(
        d0_source.read_text(encoding="utf-8").replace(
            '    "5SD5_HWI",', '    "5SD5_MUTATED",', 1
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="D0 authority case IDs drifted"):
        verify_phase2_5_science_governance(POLICY_PATH, repo)


def test_resealed_d2_registry_drift_is_rejected(tmp_path: Path) -> None:
    repo = _copy_reference_repo(tmp_path)
    path = repo / "config/engine_v2_public_redocking_contamination_registry.json"
    registry = json.loads(path.read_text(encoding="utf-8"))
    registry["contaminated_development_case_count"] = 301
    _reseal(registry, "registry_sha256")
    _write_json(path, registry)

    with pytest.raises(ValueError, match="not the frozen identity"):
        verify_phase2_5_science_governance(POLICY_PATH, repo)


def test_resealed_fresh_manifest_drift_is_rejected(tmp_path: Path) -> None:
    repo = _copy_reference_repo(tmp_path)
    path = repo / "config/engine_v2_fresh_redocking_holdout_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["cases"][0]["case_id"] = "MUTATED"
    manifest["case_ids_sha256"] = hashlib.sha256(
        _canonical_bytes([row["case_id"] for row in manifest["cases"]])
    ).hexdigest()
    _reseal(manifest, "manifest_sha256")
    _write_json(path, manifest)

    with pytest.raises(ValueError, match="not the frozen identity"):
        verify_phase2_5_science_governance(POLICY_PATH, repo)


def test_phase3_quota_and_phase5_entry_gate_are_exact() -> None:
    policy = _policy()
    quotas = policy["phase3_global_orientation_track"]["proposed_profile"][
        "lane_quotas"
    ]
    entry = policy["phase5_scorer_v2_gate"]["entry_conditions"]

    assert list(quotas.values()) == [8, 8, 12, 8, 4, 8, 16]
    assert sum(quotas.values()) == 64
    assert entry["minimum_oracle_case_count"] == 20
    assert entry["admissible_oracle_case_count_verified"] is False
    assert entry["valid_case_coverage_definition"] is None
    assert entry["proposal_profile_frozen"] is False
