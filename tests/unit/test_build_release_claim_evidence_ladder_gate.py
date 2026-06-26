from __future__ import annotations

import json
from pathlib import Path

from tools.product.build_release_claim_evidence_ladder_gate import (
    build_release_claim_evidence_ladder_gate,
)

HEAD_SHA = "abc123def456"


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def _local_green(path: Path) -> Path:
    return _write(path, {"evidence_scope": "local_observed", "status": "local_smoke_ready", "green": True})


def _remote_green(path: Path) -> Path:
    return _write(
        path,
        {
            "summary": {
                "status": "release_ci_remote_green_ready",
                "pass": True,
                "rocm_self_hosted_runner_ready": True,
                "release_tag_rocm_gate_green": True,
                "weekly_rocm_schedule_green": True,
            }
        },
    )


def _head_runs_green(path: Path) -> Path:
    return _write(
        path,
        {
            "workflow_runs": [
                {
                    "id": 1,
                    "name": "product-image-smoke",
                    "head_sha": HEAD_SHA,
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        },
    )


def _all_green(tmp_path: Path) -> dict:
    return {
        "local_receipt_json": _local_green(tmp_path / "local.json"),
        "remote_receipt_json": _remote_green(tmp_path / "remote.json"),
        "head_runs_json": _head_runs_green(tmp_path / "head.json"),
        "main_head_sha": HEAD_SHA,
    }


def test_full_ladder_green_supports_runtime_claim(tmp_path: Path) -> None:
    payload = build_release_claim_evidence_ladder_gate(root=tmp_path, **_all_green(tmp_path))
    s = payload["summary"]
    assert s["status"] == "release_claim_ladder_ready"
    assert s["pass"] is True
    assert s["highest_supported_claim"] == "runtime_green"
    assert s["claim_promotion"]["tests_pass_locally"] is True
    assert s["claim_promotion"]["ci_wired_and_green_on_main"] is True
    assert s["claim_promotion"]["runtime_or_production_claim"] is True
    assert payload["blockers"] == []


def test_local_only_does_not_imply_remote_or_runtime(tmp_path: Path) -> None:
    payload = build_release_claim_evidence_ladder_gate(
        root=tmp_path,
        local_receipt_json=_local_green(tmp_path / "local.json"),
        remote_receipt_json="",
        head_runs_json="",
        main_head_sha=HEAD_SHA,
    )
    s = payload["summary"]
    assert s["highest_supported_claim"] == "local_only"
    assert s["status"] == "blocked_release_claim_ladder"
    assert s["local_observed_green"] is True
    assert s["remote_green"] is False
    assert s["runtime_green"] is False
    assert s["claim_promotion"]["ci_wired_and_green_on_main"] is False


def test_unlabeled_local_receipt_is_not_accepted(tmp_path: Path) -> None:
    # Green, but not scoped local_observed -> must not count (honest labelling).
    unlabeled = _write(tmp_path / "local.json", {"status": "smoke_ready", "green": True})
    payload = build_release_claim_evidence_ladder_gate(
        root=tmp_path, local_receipt_json=unlabeled, main_head_sha=HEAD_SHA
    )
    s = payload["summary"]
    assert s["local_observed_green"] is False
    assert s["highest_supported_claim"] == "none"
    codes = {b["code"] for b in payload["blockers"]}
    assert "local_observed_green" in codes


def test_remote_green_without_head_run_is_not_promoted(tmp_path: Path) -> None:
    # The key gap: remote CI receipt is green, but the current main HEAD has NO
    # product-image workflow run. Remote-green must NOT be inferred.
    args = _all_green(tmp_path)
    args["head_runs_json"] = _write(tmp_path / "head.json", {"workflow_runs": []})
    payload = build_release_claim_evidence_ladder_gate(root=tmp_path, **args)
    s = payload["summary"]
    assert s["remote_green"] is True
    assert s["merge_commit_workflow_run_present"] is False
    assert s["remote_green_attributable_to_head"] is False
    assert s["highest_supported_claim"] == "local_only"
    assert s["claim_promotion"]["ci_wired_and_green_on_main"] is False
    codes = {b["code"] for b in payload["blockers"]}
    assert "merge_commit_workflow_run_present" in codes


def test_head_run_for_different_sha_does_not_attribute(tmp_path: Path) -> None:
    args = _all_green(tmp_path)
    args["head_runs_json"] = _write(
        tmp_path / "head.json",
        {
            "workflow_runs": [
                {
                    "name": "product-image-smoke",
                    "head_sha": "some-other-sha",
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        },
    )
    payload = build_release_claim_evidence_ladder_gate(root=tmp_path, **args)
    s = payload["summary"]
    assert s["merge_commit_workflow_run_present"] is False
    assert s["highest_supported_claim"] == "local_only"


def test_head_run_present_but_failed_blocks_attribution(tmp_path: Path) -> None:
    args = _all_green(tmp_path)
    args["head_runs_json"] = _write(
        tmp_path / "head.json",
        {
            "workflow_runs": [
                {
                    "name": "product-image-smoke",
                    "head_sha": HEAD_SHA,
                    "status": "completed",
                    "conclusion": "failure",
                }
            ]
        },
    )
    payload = build_release_claim_evidence_ladder_gate(root=tmp_path, **args)
    s = payload["summary"]
    assert s["merge_commit_workflow_run_present"] is True
    assert s["remote_green_attributable_to_head"] is False
    assert s["highest_supported_claim"] == "local_only"
    codes = {b["code"] for b in payload["blockers"]}
    assert "remote_green_attributable_to_head" in codes


def test_remote_attributable_but_no_runtime_caps_at_remote_green(tmp_path: Path) -> None:
    # Remote CI green + attributable to HEAD, but no ROCm runtime evidence.
    args = _all_green(tmp_path)
    args["remote_receipt_json"] = _write(
        tmp_path / "remote.json",
        {
            "summary": {
                "status": "release_ci_remote_green_ready",
                "pass": True,
                "rocm_self_hosted_runner_ready": False,
                "release_tag_rocm_gate_green": False,
                "weekly_rocm_schedule_green": False,
            }
        },
    )
    payload = build_release_claim_evidence_ladder_gate(root=tmp_path, **args)
    s = payload["summary"]
    assert s["remote_green_attributable_to_head"] is True
    assert s["highest_supported_claim"] == "remote_green"
    assert s["runtime_green"] is False
    assert s["claim_promotion"]["ci_wired_and_green_on_main"] is True
    assert s["claim_promotion"]["runtime_or_production_claim"] is False
    codes = {b["code"] for b in payload["blockers"]}
    assert "runtime_green" in codes


def test_never_mutates_external_state(tmp_path: Path) -> None:
    payload = build_release_claim_evidence_ladder_gate(root=tmp_path, **_all_green(tmp_path))
    assert payload["summary"]["external_state_mutated"] is False
    assert all(row["external_state_mutated"] is False for row in payload["rows"])
    assert "does not run tests" in payload["summary"]["claim_boundary"]
