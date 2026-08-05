from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess

import pytest

from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_ab import (
    EXPECTED_OUTPUT_ROOT,
    EXPECTED_POLICY_SHA256,
    RESERVATION_SCHEMA_ID,
    OneShotABAuthorityError,
    OneShotABVerdictInputs,
    authorization_decision,
    build_verdict,
    create_run_start_receipt,
    load_json_document,
    reserve_one_shot_execution,
    resolve_output_root,
    sha256_payload,
    verify_one_shot_policy,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_POLICY_PATH = _REPO_ROOT / "config/engine_v2_source_paired_clearance_one_shot_ab.json"
_PHASE25_PATH = _REPO_ROOT / "config/engine_v2_phase25_cohort_admission.json"
_ACTIVATION_PATH = _REPO_ROOT / "config/engine_v2_source_paired_clearance_activation.json"


def _documents() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    return (
        load_json_document(_POLICY_PATH, name="policy"),
        load_json_document(_PHASE25_PATH, name="phase25"),
        load_json_document(_ACTIVATION_PATH, name="activation"),
    )


def _reseal(payload: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(payload)
    result.pop("policy_sha256", None)
    result["policy_sha256"] = sha256_payload(result)
    return result


def _reseal_receipt(payload: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(payload)
    result.pop("receipt_sha256", None)
    result["receipt_sha256"] = sha256_payload(result)
    return result


def _git(repository_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository_root), *arguments],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def _initialize_checkout(repository_root: Path) -> str:
    if not (repository_root / ".git").exists():
        _git(repository_root, "init", "-q")
        _git(repository_root, "config", "user.name", "one-shot-test")
        _git(repository_root, "config", "user.email", "one-shot-test@example.invalid")
        (repository_root / ".gitignore").write_text(
            ".betelgeuze\n.betelgeuze/\n",
            encoding="utf-8",
        )
        (repository_root / "tracked.txt").write_text("clean\n", encoding="utf-8")
        _git(repository_root, "add", ".gitignore", "tracked.txt")
        _git(repository_root, "commit", "-q", "-m", "initialize test checkout")
    return _git(repository_root, "rev-parse", "--verify", "HEAD^{commit}")


def test_one_shot_policy_verifies_against_both_source_policies(tmp_path: Path) -> None:
    policy, phase25, activation = _documents()
    verify_one_shot_policy(
        policy,
        phase25_policy=phase25,
        activation_policy=activation,
    )
    assert policy["policy_sha256"] == EXPECTED_POLICY_SHA256
    assert resolve_output_root(policy, repository_root=tmp_path) == (
        tmp_path / EXPECTED_OUTPUT_ROOT
    )
    _initialize_checkout(tmp_path)
    decision = authorization_decision(
        policy,
        phase25_policy=phase25,
        activation_policy=activation,
        repository_root=tmp_path,
    )
    assert decision.authorized is True
    assert decision.blockers == ()


def test_resealed_fresh_authority_escalation_is_rejected() -> None:
    policy, phase25, activation = _documents()
    changed = copy.deepcopy(policy)
    changed["authority"]["fresh_holdout_execution_authorized"] = True
    changed = _reseal(changed)
    with pytest.raises(OneShotABAuthorityError, match="identity is not frozen"):
        verify_one_shot_policy(
            changed,
            phase25_policy=phase25,
            activation_policy=activation,
        )


def test_resealed_cohort_drift_is_rejected() -> None:
    policy, phase25, activation = _documents()
    changed = copy.deepcopy(policy)
    changed["cohort"]["historical_case_ids"][0] = "UNKNOWN_CASE"
    changed["cohort"]["historical_case_ids_sha256"] = sha256_payload(
        changed["cohort"]["historical_case_ids"]
    )
    changed = _reseal(changed)
    with pytest.raises(OneShotABAuthorityError, match="identity is not frozen"):
        verify_one_shot_policy(
            changed,
            phase25_policy=phase25,
            activation_policy=activation,
        )


def test_source_policy_crosswire_is_rejected() -> None:
    policy, phase25, activation = _documents()
    changed = copy.deepcopy(activation)
    changed["policy_sha256"] = "0" * 64
    with pytest.raises(OneShotABAuthorityError, match="activation policy cross-wire"):
        verify_one_shot_policy(
            policy,
            phase25_policy=phase25,
            activation_policy=changed,
        )


def test_reservation_and_run_start_are_atomic_and_owner_only(tmp_path: Path) -> None:
    policy, phase25, activation = _documents()
    source_commit = _initialize_checkout(tmp_path)
    reservation = reserve_one_shot_execution(
        policy=policy,
        phase25_policy=phase25,
        activation_policy=activation,
        repository_root=tmp_path,
        source_commit_git_sha1=source_commit,
        operator_id="solo-operator",
        execution_environment_sha256="2" * 64,
    )
    output_root = tmp_path / EXPECTED_OUTPUT_ROOT
    reservation_path = output_root / "execution-reservation.json"
    assert reservation_path.stat().st_mode & 0o777 == 0o600
    assert output_root.stat().st_mode & 0o777 == 0o700
    assert output_root.parent.stat().st_mode & 0o777 == 0o700
    assert reservation["reserved_run_ordinal"] == 1
    assert reservation["source_commit_git_sha1"] == source_commit
    assert reservation["durable_output_root"] == EXPECTED_OUTPUT_ROOT.as_posix()

    with pytest.raises(OneShotABAuthorityError, match="already_exists"):
        reserve_one_shot_execution(
            policy=policy,
            phase25_policy=phase25,
            activation_policy=activation,
            repository_root=tmp_path,
            source_commit_git_sha1=source_commit,
            operator_id="solo-operator",
            execution_environment_sha256="2" * 64,
        )

    run_start = create_run_start_receipt(
        policy=policy,
        reservation=reservation,
        repository_root=tmp_path,
    )
    run_start_path = output_root / "run-start.json"
    assert run_start_path.stat().st_mode & 0o777 == 0o600
    assert run_start["required_scorer_backend"] == "rust_cpu_required"
    assert run_start["expected_scored_candidate_rows"] == 1024
    assert run_start["source_commit_git_sha1"] == source_commit
    assert run_start["durable_output_root"] == EXPECTED_OUTPUT_ROOT.as_posix()
    with pytest.raises(OneShotABAuthorityError, match="refusing to overwrite"):
        create_run_start_receipt(
            policy=policy,
            reservation=reservation,
            repository_root=tmp_path,
        )


def test_reservation_rejects_declared_source_not_equal_to_head(tmp_path: Path) -> None:
    policy, phase25, activation = _documents()
    _initialize_checkout(tmp_path)
    with pytest.raises(OneShotABAuthorityError, match="does not equal"):
        reserve_one_shot_execution(
            policy=policy,
            phase25_policy=phase25,
            activation_policy=activation,
            repository_root=tmp_path,
            source_commit_git_sha1="f" * 40,
            operator_id="operator",
            execution_environment_sha256="2" * 64,
        )


def test_dirty_checkout_blocks_authorization(tmp_path: Path) -> None:
    policy, phase25, activation = _documents()
    _initialize_checkout(tmp_path)
    (tmp_path / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    decision = authorization_decision(
        policy,
        phase25_policy=phase25,
        activation_policy=activation,
        repository_root=tmp_path,
    )
    assert decision.authorized is False
    assert any("clean Git checkout" in blocker for blocker in decision.blockers)


def test_run_start_rechecks_checkout_head_and_cleanliness(tmp_path: Path) -> None:
    policy, phase25, activation = _documents()
    source_commit = _initialize_checkout(tmp_path)
    reservation = reserve_one_shot_execution(
        policy=policy,
        phase25_policy=phase25,
        activation_policy=activation,
        repository_root=tmp_path,
        source_commit_git_sha1=source_commit,
        operator_id="operator",
        execution_environment_sha256="2" * 64,
    )
    (tmp_path / "tracked.txt").write_text("changed after reservation\n", encoding="utf-8")
    with pytest.raises(OneShotABAuthorityError, match="clean Git checkout"):
        create_run_start_receipt(
            policy=policy,
            reservation=reservation,
            repository_root=tmp_path,
        )


def test_run_start_requires_the_exact_durable_reservation(tmp_path: Path) -> None:
    policy, phase25, activation = _documents()
    source_commit = _initialize_checkout(tmp_path)
    reservation = reserve_one_shot_execution(
        policy=policy,
        phase25_policy=phase25,
        activation_policy=activation,
        repository_root=tmp_path,
        source_commit_git_sha1=source_commit,
        operator_id="operator",
        execution_environment_sha256="2" * 64,
    )
    changed = copy.deepcopy(reservation)
    changed["operator_id"] = "different-operator"
    changed = _reseal_receipt(changed)
    with pytest.raises(OneShotABAuthorityError, match="durable reservation"):
        create_run_start_receipt(
            policy=policy,
            reservation=changed,
            repository_root=tmp_path,
        )


def test_run_start_rejects_reconstructed_reservation_without_durable_file(
    tmp_path: Path,
) -> None:
    policy, _, _ = _documents()
    source_commit = _initialize_checkout(tmp_path)
    reservation: dict[str, object] = {
        "schema_id": RESERVATION_SCHEMA_ID,
        "policy_sha256": EXPECTED_POLICY_SHA256,
        "source_commit_git_sha1": source_commit,
        "operator_id": "operator",
        "execution_environment_sha256": "2" * 64,
        "durable_output_root": EXPECTED_OUTPUT_ROOT.as_posix(),
        "maximum_lifetime_run_count": 1,
        "reserved_run_ordinal": 1,
        "fresh_holdout_execution_authorized": False,
        "product_execution_authorized": False,
        "public_or_scientific_claim_authorized": False,
    }
    reservation["receipt_sha256"] = sha256_payload(reservation)
    with pytest.raises(OneShotABAuthorityError, match="cannot be opened safely"):
        create_run_start_receipt(
            policy=policy,
            reservation=reservation,
            repository_root=tmp_path,
        )


def test_symlinked_evidence_root_is_rejected(tmp_path: Path) -> None:
    policy, phase25, activation = _documents()
    source_commit = _initialize_checkout(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    (tmp_path / ".betelgeuze").symlink_to(outside, target_is_directory=True)
    with pytest.raises(OneShotABAuthorityError, match="escapes|symlink"):
        reserve_one_shot_execution(
            policy=policy,
            phase25_policy=phase25,
            activation_policy=activation,
            repository_root=tmp_path,
            source_commit_git_sha1=source_commit,
            operator_id="operator",
            execution_environment_sha256="2" * 64,
        )


def test_preexisting_result_blocks_authorization(tmp_path: Path) -> None:
    policy, phase25, activation = _documents()
    _initialize_checkout(tmp_path)
    output_root = tmp_path / EXPECTED_OUTPUT_ROOT
    output_root.mkdir(mode=0o700, parents=True)
    (output_root / "result.json").write_text("{}\n", encoding="utf-8")
    decision = authorization_decision(
        policy,
        phase25_policy=phase25,
        activation_policy=activation,
        repository_root=tmp_path,
    )
    assert decision.authorized is False
    assert "one_shot_result_already_exists" in decision.blockers


def _verdict_inputs(*, improved: bool) -> OneShotABVerdictInputs:
    return OneShotABVerdictInputs(
        preparation_failure_case_ids=("6M73_FNR",),
        baseline_top1_recovery_case_ids=("6T88_MWQ",),
        experimental_top1_recovery_case_ids=("6T88_MWQ",),
        baseline_top5_recovery_case_ids=("6T88_MWQ",),
        experimental_top5_recovery_case_ids=("6T88_MWQ",),
        baseline_exact_valid_case_ids=("6T88_MWQ",),
        experimental_exact_valid_case_ids=(
            ("6T88_MWQ", "5SD5_HWI") if improved else ("6T88_MWQ",)
        ),
        baseline_proposal_oracle_case_ids=("6T88_MWQ",),
        experimental_proposal_oracle_case_ids=(
            ("6T88_MWQ", "5SD5_HWI") if improved else ("6T88_MWQ",)
        ),
        baseline_invalid_top1_case_ids=(
            "5SD5_HWI",
            "5SIS_JSM",
            "6M2B_EZO",
            "6TW5_9M2",
            "6TW7_NZB",
        ),
        experimental_invalid_top1_case_ids=(
            ("5SIS_JSM", "6M2B_EZO", "6TW5_9M2", "6TW7_NZB")
            if improved
            else (
                "5SD5_HWI",
                "5SIS_JSM",
                "6M2B_EZO",
                "6TW5_9M2",
                "6TW7_NZB",
            )
        ),
        baseline_candidate_count=512,
        experimental_candidate_count=512,
        source_control_preserved=True,
        score_term_semantics_fully_verified=True,
        result_dependent_allocation_observed=False,
        shadow_eligible_candidate_count=1,
        selected_penetrating_without_validity_change_count=0,
    )


def test_verdict_go_requires_case_level_improvement_and_all_invariants() -> None:
    receipt = build_verdict(
        _verdict_inputs(improved=True), policy_sha256=EXPECTED_POLICY_SHA256
    )
    assert receipt["verdict"] == "GO_CONTINUE_FIXED_32_CASE"
    assert receipt["fresh_holdout_execution_authorized"] is False
    assert receipt["profile_promotion_authority"] is False


def test_verdict_no_go_closes_local_refinement_without_claim_authority() -> None:
    receipt = build_verdict(
        _verdict_inputs(improved=False), policy_sha256=EXPECTED_POLICY_SHA256
    )
    assert receipt["verdict"] == "NO_GO_CLOSE_LOCAL_REFINEMENT"
    assert receipt["no_go_criteria"]["no_exact_valid_case_increase"] is True
    assert receipt["product_execution_authorized"] is False
    assert receipt["public_or_scientific_claim_authorized"] is False


def test_policy_file_is_canonical_json() -> None:
    payload = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
    assert payload["policy_sha256"] == EXPECTED_POLICY_SHA256
    assert payload["cohort"]["expected_scored_candidate_rows"] == 1024
