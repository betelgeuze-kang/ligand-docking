from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_ab import (
    OneShotABAuthorityError,
    sha256_payload,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_evidence import (
    build_external_evidence_envelope,
    verify_external_evidence_file,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_result import (
    EXPECTED_BASELINE_PROFILE_ID,
    EXPECTED_EXPERIMENTAL_PROFILE_ID,
    build_arm_summary,
)


def _sha_rows(prefix: str, count: int) -> tuple[str, ...]:
    return tuple(
        hashlib.sha256(f"{prefix}:{index}".encode("ascii")).hexdigest()
        for index in range(count)
    )


def _run_start() -> dict[str, object]:
    return {
        "receipt_sha256": "1" * 64,
        "source_commit_git_sha1": "2" * 40,
        "execution_environment_sha256": "3" * 64,
    }


def _arm_summary(profile_id: str) -> dict[str, object]:
    return build_arm_summary(
        profile_id=profile_id,
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
        arm_evidence_file_sha256="4" * 64,
        arm_evidence_self_sha256="5" * 64,
    )


def _write_envelope(path: Path, envelope: dict[str, object]) -> str:
    raw = (json.dumps(envelope, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _bound_arm(
    tmp_path: Path,
    *,
    role: str,
    profile_id: str,
) -> tuple[Path, dict[str, object], dict[str, object]]:
    run_start = _run_start()
    summary = _arm_summary(profile_id)
    envelope = build_external_evidence_envelope(
        role=role,
        run_start=run_start,
        summary=summary,
        case_receipt_sha256s=_sha_rows(f"{role}-case", 8),
        candidate_or_changed_receipt_sha256s=_sha_rows(f"{role}-candidate", 512),
    )
    path = tmp_path / f"{role}.json"
    file_sha256 = _write_envelope(path, envelope)
    summary["arm_evidence_file_sha256"] = file_sha256
    summary["arm_evidence_self_sha256"] = envelope["receipt_sha256"]
    return path, summary, run_start


def _cross_summary(*, changed_slot_count: int = 2) -> dict[str, object]:
    return {
        "source_control_preserved": True,
        "result_dependent_allocation_observed": False,
        "shadow_eligible_candidate_count": 3,
        "selected_penetrating_without_validity_change_count": 0,
        "changed_slot_count": changed_slot_count,
        "changed_slots_sha256": "6" * 64,
        "cross_arm_evidence_sha256": "7" * 64,
    }


def test_bound_arm_evidence_verifies_exact_file_and_manifest(tmp_path: Path) -> None:
    path, summary, run_start = _bound_arm(
        tmp_path,
        role="baseline_arm",
        profile_id=EXPECTED_BASELINE_PROFILE_ID,
    )

    receipt = verify_external_evidence_file(
        path,
        role="baseline_arm",
        run_start=run_start,
        summary=summary,
    )

    assert receipt["file_sha256"] == summary["arm_evidence_file_sha256"]
    assert receipt["receipt_sha256"] == summary["arm_evidence_self_sha256"]


def test_arm_summary_cannot_diverge_from_bound_evidence(tmp_path: Path) -> None:
    path, summary, run_start = _bound_arm(
        tmp_path,
        role="experimental_arm",
        profile_id=EXPECTED_EXPERIMENTAL_PROFILE_ID,
    )
    changed = copy.deepcopy(summary)
    changed["exact_valid_case_ids"] = ["5SD5_HWI", "6T88_MWQ"]

    with pytest.raises(OneShotABAuthorityError, match="summary is cross-wired"):
        verify_external_evidence_file(
            path,
            role="experimental_arm",
            run_start=run_start,
            summary=changed,
        )


def test_arm_file_hash_detects_byte_replacement_after_binding(tmp_path: Path) -> None:
    path, summary, run_start = _bound_arm(
        tmp_path,
        role="baseline_arm",
        profile_id=EXPECTED_BASELINE_PROFILE_ID,
    )
    path.write_bytes(path.read_bytes() + b"\n")

    with pytest.raises(OneShotABAuthorityError, match="file SHA-256"):
        verify_external_evidence_file(
            path,
            role="baseline_arm",
            run_start=run_start,
            summary=summary,
        )


def test_resealed_arm_envelope_cannot_reduce_candidate_denominator(
    tmp_path: Path,
) -> None:
    path, summary, run_start = _bound_arm(
        tmp_path,
        role="baseline_arm",
        profile_id=EXPECTED_BASELINE_PROFILE_ID,
    )
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["payload"]["candidate_receipt_sha256s"].pop()
    envelope.pop("receipt_sha256")
    envelope["receipt_sha256"] = sha256_payload(envelope)
    summary["arm_evidence_file_sha256"] = _write_envelope(path, envelope)
    summary["arm_evidence_self_sha256"] = envelope["receipt_sha256"]

    with pytest.raises(OneShotABAuthorityError, match="exactly 512"):
        verify_external_evidence_file(
            path,
            role="baseline_arm",
            run_start=run_start,
            summary=summary,
        )


def test_cross_arm_evidence_binds_changed_slot_manifest(tmp_path: Path) -> None:
    run_start = _run_start()
    summary = _cross_summary(changed_slot_count=2)
    envelope = build_external_evidence_envelope(
        role="cross_arm",
        run_start=run_start,
        summary=summary,
        case_receipt_sha256s=_sha_rows("cross-case", 8),
        candidate_or_changed_receipt_sha256s=_sha_rows("changed-slot", 2),
    )
    path = tmp_path / "cross-arm.json"
    summary["cross_arm_evidence_sha256"] = _write_envelope(path, envelope)

    verify_external_evidence_file(
        path,
        role="cross_arm",
        run_start=run_start,
        summary=summary,
    )

    changed = copy.deepcopy(summary)
    changed["changed_slot_count"] = 1
    with pytest.raises(OneShotABAuthorityError, match="summary is cross-wired"):
        verify_external_evidence_file(
            path,
            role="cross_arm",
            run_start=run_start,
            summary=changed,
        )
