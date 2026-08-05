from __future__ import annotations

import copy
from pathlib import Path
import subprocess

import pytest

from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_ab import (
    EXPECTED_OUTPUT_ROOT,
    EXPECTED_POLICY_SHA256,
    OneShotABAuthorityError,
    create_run_start_receipt,
    load_json_document,
    reserve_one_shot_execution,
    sha256_payload,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_result import (
    EXPECTED_BASELINE_PROFILE_ID,
    EXPECTED_EXPERIMENTAL_PROFILE_ID,
    build_arm_summary,
    build_result_document,
    verify_result_document,
    write_result_once,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_POLICY_PATH = _REPO_ROOT / "config/engine_v2_source_paired_clearance_one_shot_ab.json"
_PHASE25_PATH = _REPO_ROOT / "config/engine_v2_phase25_cohort_admission.json"
_ACTIVATION_PATH = _REPO_ROOT / "config/engine_v2_source_paired_clearance_activation.json"


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
    _git(repository_root, "init", "-q")
    _git(repository_root, "config", "user.name", "one-shot-result-test")
    _git(
        repository_root,
        "config",
        "user.email",
        "one-shot-result-test@example.invalid",
    )
    (repository_root / ".gitignore").write_text(".betelgeuze/\n", encoding="utf-8")
    (repository_root / "tracked.txt").write_text("clean\n", encoding="utf-8")
    _git(repository_root, "add", ".gitignore", "tracked.txt")
    _git(repository_root, "commit", "-q", "-m", "initialize result test checkout")
    return _git(repository_root, "rev-parse", "--verify", "HEAD^{commit}")


def _run_start(tmp_path: Path) -> tuple[dict[str, object], dict[str, object], Path]:
    policy = load_json_document(_POLICY_PATH, name="policy")
    phase25 = load_json_document(_PHASE25_PATH, name="phase25")
    activation = load_json_document(_ACTIVATION_PATH, name="activation")
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
    run_start = create_run_start_receipt(
        policy=policy,
        reservation=reservation,
        repository_root=tmp_path,
    )
    return policy, run_start, tmp_path


def _arms(*, improved: bool) -> tuple[dict[str, object], dict[str, object]]:
    baseline = build_arm_summary(
        profile_id=EXPECTED_BASELINE_PROFILE_ID,
        preparation_failure_case_ids=("6M73_FNR",),
        top1_recovery_case_ids=("6T88_MWQ",),
        top5_recovery_case_ids=("6T88_MWQ",),
        exact_valid_case_ids=("6T88_MWQ",),
        proposal_oracle_case_ids=("6T88_MWQ",),
        invalid_top1_case_ids=(
            "5SD5_HWI",
            "5SIS_JSM",
            "6M2B_EZO",
            "6TW5_9M2",
            "6TW7_NZB",
        ),
        arm_evidence_file_sha256="3" * 64,
        arm_evidence_self_sha256="4" * 64,
    )
    experimental = build_arm_summary(
        profile_id=EXPECTED_EXPERIMENTAL_PROFILE_ID,
        preparation_failure_case_ids=("6M73_FNR",),
        top1_recovery_case_ids=("6T88_MWQ",),
        top5_recovery_case_ids=("6T88_MWQ",),
        exact_valid_case_ids=(
            ("5SD5_HWI", "6T88_MWQ") if improved else ("6T88_MWQ",)
        ),
        proposal_oracle_case_ids=(
            ("5SD5_HWI", "6T88_MWQ") if improved else ("6T88_MWQ",)
        ),
        invalid_top1_case_ids=(
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
        arm_evidence_file_sha256="5" * 64,
        arm_evidence_self_sha256="6" * 64,
    )
    return baseline, experimental


def _result(run_start: dict[str, object], *, improved: bool) -> dict[str, object]:
    baseline, experimental = _arms(improved=improved)
    return build_result_document(
        run_start=run_start,
        baseline_arm=baseline,
        experimental_arm=experimental,
        source_control_preserved=True,
        result_dependent_allocation_observed=False,
        shadow_eligible_candidate_count=2,
        selected_penetrating_without_validity_change_count=0,
        changed_slot_count=1 if improved else 0,
        changed_slots_sha256="7" * 64,
        cross_arm_evidence_sha256="8" * 64,
    )


def _reseal_result(payload: dict[str, object]) -> dict[str, object]:
    changed = copy.deepcopy(payload)
    changed.pop("result_sha256", None)
    changed["result_sha256"] = sha256_payload(changed)
    return changed


def _reseal_receipt(payload: dict[str, object]) -> dict[str, object]:
    changed = copy.deepcopy(payload)
    changed.pop("receipt_sha256", None)
    changed["receipt_sha256"] = sha256_payload(changed)
    return changed


def test_result_rederives_go_verdict_from_both_arms(tmp_path: Path) -> None:
    _, run_start, _ = _run_start(tmp_path)
    result = _result(run_start, improved=True)
    verify_result_document(result, run_start=run_start)
    assert result["verdict"]["verdict"] == "GO_CONTINUE_FIXED_32_CASE"
    assert result["policy_sha256"] == EXPECTED_POLICY_SHA256


def test_result_rederives_no_go_verdict_from_both_arms(tmp_path: Path) -> None:
    _, run_start, _ = _run_start(tmp_path)
    result = _result(run_start, improved=False)
    verify_result_document(result, run_start=run_start)
    assert result["verdict"]["verdict"] == "NO_GO_CLOSE_LOCAL_REFINEMENT"


def test_resealed_forged_verdict_is_rejected(tmp_path: Path) -> None:
    _, run_start, _ = _run_start(tmp_path)
    result = _result(run_start, improved=False)
    changed = copy.deepcopy(result)
    changed["verdict"]["verdict"] = "GO_CONTINUE_FIXED_32_CASE"
    verdict = dict(changed["verdict"])
    verdict.pop("receipt_sha256", None)
    verdict["receipt_sha256"] = sha256_payload(verdict)
    changed["verdict"] = verdict
    changed = _reseal_result(changed)
    with pytest.raises(OneShotABAuthorityError, match="rederived document"):
        verify_result_document(changed, run_start=run_start)


def test_resealed_arm_outcomes_cannot_keep_a_stale_verdict(tmp_path: Path) -> None:
    _, run_start, _ = _run_start(tmp_path)
    result = _result(run_start, improved=True)
    changed = copy.deepcopy(result)
    changed["experimental_arm"]["exact_valid_case_ids"] = ["6T88_MWQ"]
    changed["experimental_arm"]["proposal_oracle_case_ids"] = ["6T88_MWQ"]
    changed["experimental_arm"]["invalid_top1_case_ids"] = [
        "5SD5_HWI",
        "5SIS_JSM",
        "6M2B_EZO",
        "6TW5_9M2",
        "6TW7_NZB",
    ]
    changed = _reseal_result(changed)
    with pytest.raises(OneShotABAuthorityError, match="rederived document"):
        verify_result_document(changed, run_start=run_start)


def test_changed_slots_cannot_exceed_shadow_eligible_count(tmp_path: Path) -> None:
    _, run_start, _ = _run_start(tmp_path)
    baseline, experimental = _arms(improved=True)
    with pytest.raises(OneShotABAuthorityError, match="changed slots"):
        build_result_document(
            run_start=run_start,
            baseline_arm=baseline,
            experimental_arm=experimental,
            source_control_preserved=True,
            result_dependent_allocation_observed=False,
            shadow_eligible_candidate_count=1,
            selected_penetrating_without_validity_change_count=0,
            changed_slot_count=2,
            changed_slots_sha256="7" * 64,
            cross_arm_evidence_sha256="8" * 64,
        )


def test_result_write_is_atomic_and_single_use(tmp_path: Path) -> None:
    policy, run_start, repo_root = _run_start(tmp_path)
    result = _result(run_start, improved=False)
    write_result_once(
        policy=policy,
        run_start=run_start,
        result=result,
        repository_root=repo_root,
    )
    result_path = repo_root / EXPECTED_OUTPUT_ROOT / "result.json"
    assert result_path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(OneShotABAuthorityError, match="refusing to overwrite"):
        write_result_once(
            policy=policy,
            run_start=run_start,
            result=result,
            repository_root=repo_root,
        )


def test_result_write_requires_exact_durable_run_start(tmp_path: Path) -> None:
    policy, run_start, repo_root = _run_start(tmp_path)
    result = _result(run_start, improved=False)
    changed = copy.deepcopy(run_start)
    changed["execution_environment_sha256"] = "9" * 64
    changed = _reseal_receipt(changed)
    with pytest.raises(OneShotABAuthorityError, match="durable run-start"):
        write_result_once(
            policy=policy,
            run_start=changed,
            result=result,
            repository_root=repo_root,
        )


def test_result_write_rejects_missing_durable_run_start(tmp_path: Path) -> None:
    policy, run_start, repo_root = _run_start(tmp_path)
    result = _result(run_start, improved=False)
    (repo_root / EXPECTED_OUTPUT_ROOT / "run-start.json").unlink()
    with pytest.raises(OneShotABAuthorityError, match="cannot be opened safely"):
        write_result_once(
            policy=policy,
            run_start=run_start,
            result=result,
            repository_root=repo_root,
        )


def test_result_write_rechecks_clean_checkout(tmp_path: Path) -> None:
    policy, run_start, repo_root = _run_start(tmp_path)
    result = _result(run_start, improved=False)
    (repo_root / "tracked.txt").write_text("dirty before result\n", encoding="utf-8")
    with pytest.raises(OneShotABAuthorityError, match="clean Git checkout"):
        write_result_once(
            policy=policy,
            run_start=run_start,
            result=result,
            repository_root=repo_root,
        )


def test_result_write_rejects_policy_payload_with_stale_hash(tmp_path: Path) -> None:
    policy, run_start, repo_root = _run_start(tmp_path)
    result = _result(run_start, improved=False)
    changed_policy = copy.deepcopy(policy)
    changed_policy["execution"]["result_filename"] = "alternate-result.json"
    with pytest.raises(OneShotABAuthorityError, match="one-shot policy self-hash"):
        write_result_once(
            policy=changed_policy,
            run_start=run_start,
            result=result,
            repository_root=repo_root,
        )


def test_result_never_authorizes_fresh_product_or_claims(tmp_path: Path) -> None:
    _, run_start, _ = _run_start(tmp_path)
    result = _result(run_start, improved=True)
    assert result["fresh_holdout_execution_authorized"] is False
    assert result["stage0_admission_authority"] is False
    assert result["profile_promotion_authority"] is False
    assert result["product_execution_authorized"] is False
    assert result["customer_pose_emission_authorized"] is False
    assert result["public_or_scientific_claim_authorized"] is False
