from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pr38_split_acceptance_packet as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _payloads(*, apply_ready: bool = True) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    split = {
        "summary": {
            "status": "pr38_split_review_packet_ready",
            "split_review_ready": True,
            "changed_file_count": 2,
            "hunk_split_review_required_count": 1,
        },
        "slices": [
            {
                "slice_id": "slice_a",
                "changed_file_count": 1,
                "focused_test_command": "pytest a",
                "claim_boundary": "No claim A.",
            },
            {
                "slice_id": "slice_b",
                "changed_file_count": 1,
                "focused_test_command": "pytest b",
                "claim_boundary": "No claim B.",
            },
        ],
    }
    plan = {
        "summary": {
            "status": "pr38_child_pr_extraction_plan_ready",
            "extraction_plan_ready": True,
            "total_changed_file_count": 2,
            "source_of_truth_registry_reconciles_last": True,
        },
        "rows": [
            {
                "sequence": 1,
                "slice_id": "slice_a",
                "changed_file_count": 1,
                "integration_touchpoint_count": 0,
                "focused_test_command": "pytest a",
                "claim_boundary": "No claim A.",
                "child_pr_ready_to_extract": True,
            },
            {
                "sequence": 2,
                "slice_id": "slice_b",
                "changed_file_count": 1,
                "integration_touchpoint_count": 1,
                "focused_test_command": "pytest b",
                "claim_boundary": "No claim B.",
                "child_pr_ready_to_extract": True,
            },
        ],
    }
    bundle = {
        "summary": {
            "status": "pr38_slice_patch_bundle_ready",
            "patch_bundle_ready": True,
            "bundled_changed_file_count": 2,
        },
        "rows": [
            {"slice_id": "slice_a", "patch_path": "a.patch", "patch_sha256": "sha-a", "patch_nonempty": True},
            {"slice_id": "slice_b", "patch_path": "b.patch", "patch_sha256": "sha-b", "patch_nonempty": True},
        ],
    }
    apply = {
        "summary": {
            "status": "pr38_slice_patch_apply_preflight_ready" if apply_ready else "blocked",
            "patch_apply_preflight_ready": apply_ready,
            "slice_patch_count": 2,
        },
        "rows": [
            {"slice_id": "slice_a", "apply_check_ready": True, "apply_check_status": "apply_check_passed"},
            {
                "slice_id": "slice_b",
                "apply_check_ready": apply_ready,
                "apply_check_status": "apply_check_passed" if apply_ready else "apply_check_failed",
            },
        ],
    }
    return split, plan, bundle, apply


def _write_payloads(root: Path, *, apply_ready: bool = True) -> tuple[Path, Path, Path, Path]:
    split, plan, bundle, apply = _payloads(apply_ready=apply_ready)
    paths = (root / "split.json", root / "plan.json", root / "bundle.json", root / "apply.json")
    for path, payload in zip(paths, (split, plan, bundle, apply), strict=True):
        _write_json(path, payload)
    return paths


def test_split_acceptance_packet_requires_all_receipts_and_preserves_claim_lock(tmp_path: Path) -> None:
    split, plan, bundle, apply = _write_payloads(tmp_path)

    payload = mod.build_pr38_split_acceptance_packet(
        split_packet_json=split,
        extraction_plan_json=plan,
        patch_bundle_json=bundle,
        apply_preflight_json=apply,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "pr38_split_acceptance_packet_ready"
    assert summary["split_acceptance_ready"] is True
    assert summary["required_receipts_ready"] is True
    assert summary["count_alignment_ready"] is True
    assert summary["ready_child_pr_count"] == 2
    assert summary["paid_pilot_wording_allowed"] is False
    assert summary["branch_commit_work_allowed_by_this_packet"] is False
    assert summary["product_mode_expected_fail_closed_blockers"] == mod.KNOWN_PRODUCT_MODE_BLOCKERS
    rows = {row["slice_id"]: row for row in payload["rows"]}
    assert rows["slice_b"]["integration_touchpoint_count"] == 1
    assert rows["slice_a"]["slice_acceptance_ready"] is True
    assert rows["slice_a"]["acceptance_blockers"] == []


def test_split_acceptance_packet_blocks_failed_apply_check(tmp_path: Path) -> None:
    split, plan, bundle, apply = _write_payloads(tmp_path, apply_ready=False)

    payload = mod.build_pr38_split_acceptance_packet(
        split_packet_json=split,
        extraction_plan_json=plan,
        patch_bundle_json=bundle,
        apply_preflight_json=apply,
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "blocked_pr38_split_acceptance_packet"
    assert payload["summary"]["split_acceptance_ready"] is False
    assert payload["summary"]["blocked_slice_ids"] == ["slice_b"]
    rows = {row["slice_id"]: row for row in payload["rows"]}
    assert rows["slice_b"]["acceptance_blockers"] == ["patch_apply_check_failed"]


def test_main_writes_split_acceptance_packet_artifacts(tmp_path: Path) -> None:
    split, plan, bundle, apply = _write_payloads(tmp_path)
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    rc = mod.main(
        [
            "--root",
            str(tmp_path),
            "--split-packet-json",
            str(split),
            "--extraction-plan-json",
            str(plan),
            "--patch-bundle-json",
            str(bundle),
            "--apply-preflight-json",
            str(apply),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "pr38_split_acceptance_packet_ready"
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["slice_id"] for row in rows] == ["slice_a", "slice_b"]
    assert out_md.read_text(encoding="utf-8").startswith("# PR #38 Split Acceptance Packet")
