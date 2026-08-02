from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pr38_split_acceptance_packet as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _payloads(*, apply_ready: bool = True) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    slice_ids = ["slice_a", "slice_b", "slice_c", "slice_d", "slice_e"]
    split = {
        "summary": {
            "status": "pr38_split_review_packet_ready",
            "split_review_ready": True,
            "changed_file_count": len(slice_ids),
            "minimum_child_pr_count": mod.MINIMUM_CHILD_PR_COUNT,
            "minimum_child_pr_count_met": True,
            "hunk_split_review_required_count": 1,
        },
        "slices": [
            {
                "slice_id": slice_id,
                "changed_file_count": 1,
                "focused_test_command": f"pytest {slice_id}",
                "claim_boundary": f"No claim {slice_id}.",
            }
            for slice_id in slice_ids
        ],
    }
    plan = {
        "summary": {
            "status": "pr38_child_pr_extraction_plan_ready",
            "extraction_plan_ready": True,
            "total_changed_file_count": len(slice_ids),
            "minimum_child_pr_count": mod.MINIMUM_CHILD_PR_COUNT,
            "minimum_child_pr_count_met": True,
            "source_of_truth_registry_reconciles_last": True,
        },
        "rows": [
            {
                "sequence": index,
                "slice_id": slice_id,
                "changed_file_count": 1,
                "integration_touchpoint_count": 1 if slice_id == "slice_b" else 0,
                "focused_test_command": f"pytest {slice_id}",
                "claim_boundary": f"No claim {slice_id}.",
                "child_pr_ready_to_extract": True,
            }
            for index, slice_id in enumerate(slice_ids, start=1)
        ],
    }
    bundle = {
        "summary": {
            "status": "pr38_slice_patch_bundle_ready",
            "patch_bundle_ready": True,
            "bundled_changed_file_count": len(slice_ids),
        },
        "rows": [
            {
                "slice_id": slice_id,
                "patch_path": f"{slice_id}.patch",
                "patch_sha256": f"sha-{slice_id}",
                "patch_nonempty": True,
            }
            for slice_id in slice_ids
        ],
    }
    apply = {
        "summary": {
            "status": "pr38_slice_patch_apply_preflight_ready" if apply_ready else "blocked",
            "patch_apply_preflight_ready": apply_ready,
            "slice_patch_count": len(slice_ids),
        },
        "rows": [
            {
                "slice_id": slice_id,
                "apply_check_ready": apply_ready if slice_id == "slice_b" else True,
                "apply_check_status": "apply_check_passed"
                if (apply_ready or slice_id != "slice_b")
                else "apply_check_failed",
            }
            for slice_id in slice_ids
        ],
    }
    return split, plan, bundle, apply


def _launch_payload(slice_ids: list[str]) -> dict[str, object]:
    ready = len(slice_ids) >= mod.MINIMUM_CHILD_PR_COUNT
    return {
        "summary": {
            "status": "pr38_child_pr_launch_command_pack_ready"
            if ready
            else "blocked_pr38_child_pr_launch_command_pack",
            "launch_command_pack_ready": ready,
            "child_pr_count": len(slice_ids),
            "minimum_child_pr_count": mod.MINIMUM_CHILD_PR_COUNT,
            "minimum_child_pr_count_met": ready,
            "body_file_count": len(slice_ids),
            "operator_launch_requires_human_approval": True,
            "branch_commit_push_pr_mutation_required": True,
            "shell_pack_prints_commands_only": True,
            "post_push_remote_ci_waits_for_expected_head_sha": True,
            "post_push_remote_ci_requires_all_dispatched_runs_observed": True,
            "execution_enabled": False,
            "external_state_mutated": False,
            "branches_created": False,
            "commits_created": False,
            "pushes_executed": False,
            "pull_requests_created": False,
            "claim_promotion_allowed": False,
            "out_dir": "bodies",
        },
        "rows": [
            {
                "sequence": index,
                "slice_id": slice_id,
                "draft_branch_name": f"codex/pr38-{slice_id}",
                "draft_pr_title": f"[codex] Split PR38 {slice_id}",
                "patch_path": f"{slice_id}.patch",
                "pr_body_path": f"bodies/{index:02d}-{slice_id}-body.md",
                "operator_launch_requires_human_approval": True,
                "branch_commit_push_pr_mutation_required": True,
                "execution_enabled": False,
                "external_state_mutated": False,
                "branches_created": False,
                "commits_created": False,
                "pushes_executed": False,
                "pull_requests_created": False,
                "claim_promotion_allowed": False,
            }
            for index, slice_id in enumerate(slice_ids, start=1)
        ],
    }


def _product_receipts(
    *,
    ready: bool = True,
    raw_custody_ready: bool = True,
) -> tuple[dict[str, object], dict[str, object]]:
    preflight = {
        "summary": {
            "status": "product_image_smoke_preflight_ready" if ready else "blocked_product_image_smoke_preflight",
            "preflight_ready": ready,
            "receipt_runner_hygiene_ready": ready,
            "required_runner_hygiene_schema_version": "product_image_runner_hygiene_v1",
            "receipt_runner_hygiene_schema_version": "product_image_runner_hygiene_v1"
            if ready
            else "",
            "receipt_runner_hygiene_refresh_required": not ready,
            "receipt_runner_hygiene_verification_command": (
                "PRODUCT_IMAGE_VERIFY_MODE=rocm-runtime "
                "PRODUCT_IMAGE_CONTAINER_UID_GID=\"$(id -u):$(id -g)\" "
                "bash deploy/verify_product_image.sh"
            ),
            "receipt_runner_hygiene_blockers": []
            if ready
            else [
                "receipt_runner_smoke_dir_inside_workspace",
                "receipt_container_output_uid_gid_not_pinned",
                "receipt_workspace_runner_smoke_dir_cleanup_not_ready",
            ],
        }
    }
    gate = {
        "summary": {
            "status": "product_release_source_of_truth_gate_ready"
            if ready
            else "blocked_product_release_source_of_truth_gate",
        },
        "rows": [
            {
                "artifact_id": mod.PRODUCT_IMAGE_PREFLIGHT_SOURCE_ROW_ID,
                "status": "pass" if ready else "fail",
                "observed_status": "product_image_smoke_preflight_ready"
                if ready
                else "blocked_product_image_smoke_preflight",
                "missing_true_fields": []
                if ready
                else [
                    "clean_container_smoke_ready",
                    "receipt_runner_hygiene_schema_ready",
                    "receipt_runner_hygiene_ready",
                    "receipt_runner_smoke_dir_outside_workspace",
                    "receipt_container_output_uid_gid_pinned",
                    "receipt_workspace_runner_smoke_dir_cleanup_ready",
                ],
                "failed_text_exact_fields": []
                if ready
                else [
                    "receipt_runner_hygiene_schema_version",
                ],
            },
            {
                "artifact_id": mod.RUNNER_HOST_PREFLIGHT_SOURCE_ROW_ID,
                "status": "pass" if ready else "fail",
                "observed_status": "github_self_hosted_runner_host_preflight_ready"
                if ready
                else "blocked_github_self_hosted_runner_host_preflight",
                "missing_true_fields": []
                if ready
                else [
                    "local_runner_host_ready",
                    "product_image_rocm_runtime_ready",
                    "product_image_receipt_runner_hygiene_ready",
                ],
                "failed_int_exact_fields": [],
            },
            {
                "artifact_id": mod.RELEASE_CI_REMOTE_GREEN_SOURCE_ROW_ID,
                "status": "pass" if ready else "fail",
                "observed_status": "release_ci_remote_green_ready"
                if ready
                else "blocked_release_ci_remote_green",
                "missing_true_fields": []
                if ready
                else [
                    "pass",
                    "main_required_checks_ready",
                    "weekly_rocm_schedule_green",
                    "failure_artifacts_preserved",
                    "release_tag_rocm_gate_green",
                ],
                "failed_int_exact_fields": [] if ready else ["blocker_count"],
            },
            {
                "artifact_id": mod.BM5_CAPRI_RAW_CUSTODY_SOURCE_ROW_ID,
                "status": "pass" if raw_custody_ready else "fail",
                "observed_status": "bm5_capri_raw_data_custody_plan_ready",
                "missing_true_fields": []
                if raw_custody_ready
                else ["raw_data_custody_clear"],
                "failed_int_exact_fields": []
                if raw_custody_ready
                else [
                    "operator_action_required_count",
                    "raw_data_git_tracked_file_count",
                ],
            }
        ],
    }
    return preflight, gate


def _write_payloads(
    root: Path,
    *,
    apply_ready: bool = True,
    product_ready: bool = True,
    raw_custody_ready: bool = True,
    ) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    split, plan, bundle, apply = _payloads(apply_ready=apply_ready)
    launch = _launch_payload([str(row["slice_id"]) for row in plan["rows"]])
    preflight, gate = _product_receipts(
        ready=product_ready,
        raw_custody_ready=raw_custody_ready,
    )
    paths = (
        root / "split.json",
        root / "plan.json",
        root / "bundle.json",
        root / "apply.json",
        root / "launch.json",
        root / "product_image_preflight.json",
        root / "source_of_truth_gate.json",
    )
    for path, payload in zip(
        paths,
        (split, plan, bundle, apply, launch, preflight, gate),
        strict=True,
    ):
        _write_json(path, payload)
    return paths


def test_split_acceptance_packet_requires_all_receipts_and_preserves_claim_lock(tmp_path: Path) -> None:
    split, plan, bundle, apply, launch, preflight, gate = _write_payloads(tmp_path)

    payload = mod.build_pr38_split_acceptance_packet(
        split_packet_json=split,
        extraction_plan_json=plan,
        patch_bundle_json=bundle,
        apply_preflight_json=apply,
        launch_command_pack_json=launch,
        product_image_preflight_json=preflight,
        product_source_of_truth_gate_json=gate,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "pr38_split_acceptance_packet_ready"
    assert summary["split_acceptance_ready"] is True
    assert summary["blocker_count"] == 0
    assert summary["blockers"] == []
    assert summary["primary_blocker"] == ""
    assert summary["split_structural_acceptance_ready"] is True
    assert summary["product_mode_verification_ready"] is True
    assert summary["required_receipts_ready"] is True
    assert summary["count_alignment_ready"] is True
    assert summary["launch_command_pack_status"] == "pr38_child_pr_launch_command_pack_ready"
    assert summary["launch_command_pack_ready"] is True
    assert summary["launch_command_pack_alignment_ready"] is True
    assert summary["launch_command_pack_safe_ready"] is True
    assert (
        summary["launch_command_pack_post_push_remote_ci_waits_for_expected_head_sha"]
        is True
    )
    assert (
        summary[
            "launch_command_pack_post_push_remote_ci_requires_all_dispatched_runs_observed"
        ]
        is True
    )
    assert summary["launch_command_pack_operator_launch_requires_human_approval"] is True
    assert summary["launch_command_pack_shell_prints_commands_only"] is True
    assert summary["launch_command_pack_branches_created"] is False
    assert summary["launch_command_pack_pull_requests_created"] is False
    assert summary["minimum_child_pr_count"] == mod.MINIMUM_CHILD_PR_COUNT
    assert summary["minimum_child_pr_count_met"] is True
    assert summary["required_runner_hygiene_schema_version"] == "product_image_runner_hygiene_v1"
    assert summary["product_image_receipt_runner_hygiene_schema_version"] == "product_image_runner_hygiene_v1"
    assert summary["product_image_receipt_runner_hygiene_refresh_required"] is False
    assert summary["ready_child_pr_count"] == 5
    assert summary["paid_pilot_wording_allowed"] is False
    assert summary["branch_commit_work_allowed_by_this_packet"] is False
    assert summary["product_mode_expected_fail_closed_blockers"] == mod.KNOWN_PRODUCT_MODE_BLOCKERS
    assert summary["product_mode_expected_result"] == mod.PRODUCT_MODE_PASS_RESULT
    assert summary["runner_host_source_of_truth_semantic_status"] == "pass"
    assert summary["release_ci_remote_green_source_of_truth_semantic_status"] == "pass"
    assert summary["bm5_capri_raw_custody_source_of_truth_semantic_status"] == "pass"
    assert summary["product_mode_claim_boundary_expected_locks"] == (
        mod.PRODUCT_MODE_CLAIM_LOCK_EXPECTATIONS
    )
    rows = {row["slice_id"]: row for row in payload["rows"]}
    assert rows["slice_b"]["integration_touchpoint_count"] == 1
    assert rows["slice_b"]["draft_branch_name"] == "codex/pr38-slice_b"
    assert rows["slice_b"]["pr_body_path"] == "bodies/02-slice_b-body.md"
    assert rows["slice_b"]["launch_command_pack_row_ready"] is True
    assert rows["slice_a"]["slice_acceptance_ready"] is True
    assert rows["slice_a"]["acceptance_blockers"] == []


def test_split_acceptance_packet_blocks_when_child_pr_count_is_below_minimum(
    tmp_path: Path,
) -> None:
    split_payload, plan_payload, bundle_payload, apply_payload = _payloads()
    preflight_payload, gate_payload = _product_receipts()
    for payload, row_key, count_key in [
        (split_payload, "slices", "changed_file_count"),
        (plan_payload, "rows", "total_changed_file_count"),
        (bundle_payload, "rows", "bundled_changed_file_count"),
        (apply_payload, "rows", "slice_patch_count"),
    ]:
        payload[row_key] = payload[row_key][:4]
        summary = payload["summary"]
        summary[count_key] = 4
        summary["minimum_child_pr_count"] = mod.MINIMUM_CHILD_PR_COUNT
        summary["minimum_child_pr_count_met"] = False

    launch_payload = _launch_payload([str(row["slice_id"]) for row in plan_payload["rows"]])
    paths = (
        tmp_path / "split.json",
        tmp_path / "plan.json",
        tmp_path / "bundle.json",
        tmp_path / "apply.json",
        tmp_path / "launch.json",
        tmp_path / "product_image_preflight.json",
        tmp_path / "source_of_truth_gate.json",
    )
    for path, payload in zip(
        paths,
        (
            split_payload,
            plan_payload,
                bundle_payload,
                apply_payload,
                launch_payload,
                preflight_payload,
                gate_payload,
            ),
        strict=True,
    ):
        _write_json(path, payload)

    payload = mod.build_pr38_split_acceptance_packet(
        split_packet_json=paths[0],
        extraction_plan_json=paths[1],
        patch_bundle_json=paths[2],
        apply_preflight_json=paths[3],
        launch_command_pack_json=paths[4],
        product_image_preflight_json=paths[5],
        product_source_of_truth_gate_json=paths[6],
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pr38_split_acceptance_packet"
    assert summary["split_structural_acceptance_ready"] is False
    assert summary["minimum_child_pr_count"] == mod.MINIMUM_CHILD_PR_COUNT
    assert summary["minimum_child_pr_count_met"] is False
    assert summary["blockers"] == [
        "required_split_receipts_not_ready",
        "launch_command_pack_not_ready:blocked_pr38_child_pr_launch_command_pack",
        f"minimum_child_pr_count_not_met:4<{mod.MINIMUM_CHILD_PR_COUNT}",
    ]


def test_split_acceptance_packet_blocks_failed_apply_check(tmp_path: Path) -> None:
    split, plan, bundle, apply, launch, preflight, gate = _write_payloads(tmp_path, apply_ready=False)

    payload = mod.build_pr38_split_acceptance_packet(
        split_packet_json=split,
        extraction_plan_json=plan,
        patch_bundle_json=bundle,
        apply_preflight_json=apply,
        launch_command_pack_json=launch,
        product_image_preflight_json=preflight,
        product_source_of_truth_gate_json=gate,
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "blocked_pr38_split_acceptance_packet"
    assert payload["summary"]["split_acceptance_ready"] is False
    assert payload["summary"]["blocker_count"] == 2
    assert payload["summary"]["blockers"] == [
        "required_split_receipts_not_ready",
        "slice_b:patch_apply_check_failed",
    ]
    assert payload["summary"]["primary_blocker"] == "required_split_receipts_not_ready"
    assert payload["summary"]["split_structural_acceptance_ready"] is False
    assert payload["summary"]["product_mode_verification_ready"] is True
    assert payload["summary"]["blocked_slice_ids"] == ["slice_b"]
    rows = {row["slice_id"]: row for row in payload["rows"]}
    assert rows["slice_b"]["acceptance_blockers"] == ["patch_apply_check_failed"]


def test_split_acceptance_packet_blocks_product_mode_when_runner_hygiene_is_not_ready(
    tmp_path: Path,
) -> None:
    split, plan, bundle, apply, launch, preflight, gate = _write_payloads(tmp_path, product_ready=False)

    payload = mod.build_pr38_split_acceptance_packet(
        split_packet_json=split,
        extraction_plan_json=plan,
        patch_bundle_json=bundle,
        apply_preflight_json=apply,
        launch_command_pack_json=launch,
        product_image_preflight_json=preflight,
        product_source_of_truth_gate_json=gate,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pr38_split_acceptance_packet"
    assert summary["split_acceptance_ready"] is False
    assert summary["blocker_count"] == len(summary["blockers"])
    assert summary["primary_blocker"].startswith("product_mode:")
    assert summary["split_structural_acceptance_ready"] is True
    assert summary["product_mode_verification_ready"] is False
    assert summary["product_mode_expected_result"] == mod.PRODUCT_MODE_BLOCKED_RESULT
    assert "receipt_runner_hygiene_not_ready" in summary["product_mode_expected_fail_closed_blockers"]
    assert "product_mode:receipt_runner_hygiene_not_ready" in summary["blockers"]
    assert summary["required_runner_hygiene_schema_version"] == "product_image_runner_hygiene_v1"
    assert summary["product_image_receipt_runner_hygiene_schema_version"] == ""
    assert summary["product_image_receipt_runner_hygiene_refresh_required"] is True
    assert "PRODUCT_IMAGE_CONTAINER_UID_GID" in summary[
        "product_image_receipt_runner_hygiene_verification_command"
    ]
    assert (
        "receipt_container_output_uid_gid_not_pinned"
        in summary["product_mode_expected_fail_closed_blockers"]
    )
    assert (
        f"{mod.PRODUCT_IMAGE_PREFLIGHT_SOURCE_ROW_ID}_missing_true:receipt_runner_hygiene_ready"
        in summary["product_mode_expected_fail_closed_blockers"]
    )
    assert (
        f"{mod.PRODUCT_IMAGE_PREFLIGHT_SOURCE_ROW_ID}_missing_true:receipt_runner_hygiene_schema_ready"
        in summary["product_mode_expected_fail_closed_blockers"]
    )
    assert (
        f"{mod.PRODUCT_IMAGE_PREFLIGHT_SOURCE_ROW_ID}_failed_text_exact:receipt_runner_hygiene_schema_version"
        in summary["product_mode_expected_fail_closed_blockers"]
    )
    assert (
        f"{mod.RUNNER_HOST_PREFLIGHT_SOURCE_ROW_ID}_missing_true:product_image_receipt_runner_hygiene_ready"
        in summary["product_mode_expected_fail_closed_blockers"]
    )
    assert (
        f"{mod.RELEASE_CI_REMOTE_GREEN_SOURCE_ROW_ID}_missing_true:main_required_checks_ready"
        in summary["product_mode_expected_fail_closed_blockers"]
    )
    assert (
        f"{mod.RELEASE_CI_REMOTE_GREEN_SOURCE_ROW_ID}_missing_true:weekly_rocm_schedule_green"
        in summary["product_mode_expected_fail_closed_blockers"]
    )
    assert (
        f"{mod.RELEASE_CI_REMOTE_GREEN_SOURCE_ROW_ID}_failed_int_exact:blocker_count"
        in summary["product_mode_expected_fail_closed_blockers"]
    )
    assert summary["runner_host_source_of_truth_semantic_status"] == "fail"
    assert summary["release_ci_remote_green_source_of_truth_semantic_status"] == "fail"
    assert summary["bm5_capri_raw_custody_source_of_truth_semantic_status"] == "pass"


def test_split_acceptance_packet_blocks_product_mode_when_bm5_capri_raw_custody_is_not_clear(
    tmp_path: Path,
) -> None:
    split, plan, bundle, apply, launch, preflight, gate = _write_payloads(
        tmp_path,
        raw_custody_ready=False,
    )

    payload = mod.build_pr38_split_acceptance_packet(
        split_packet_json=split,
        extraction_plan_json=plan,
        patch_bundle_json=bundle,
        apply_preflight_json=apply,
        launch_command_pack_json=launch,
        product_image_preflight_json=preflight,
        product_source_of_truth_gate_json=gate,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pr38_split_acceptance_packet"
    assert summary["split_structural_acceptance_ready"] is True
    assert summary["product_mode_verification_ready"] is False
    assert summary["product_mode_expected_result"] == mod.PRODUCT_MODE_BLOCKED_RESULT
    assert summary["bm5_capri_raw_custody_source_of_truth_semantic_status"] == "fail"
    assert summary["bm5_capri_raw_custody_source_of_truth_observed_status"] == (
        "bm5_capri_raw_data_custody_plan_ready"
    )
    assert summary["bm5_capri_raw_custody_source_of_truth_missing_true_fields"] == [
        "raw_data_custody_clear"
    ]
    assert summary["bm5_capri_raw_custody_source_of_truth_failed_int_exact_fields"] == [
        "operator_action_required_count",
        "raw_data_git_tracked_file_count",
    ]
    assert (
        f"{mod.BM5_CAPRI_RAW_CUSTODY_SOURCE_ROW_ID}_missing_true:raw_data_custody_clear"
        in summary["product_mode_expected_fail_closed_blockers"]
    )
    assert (
        f"{mod.BM5_CAPRI_RAW_CUSTODY_SOURCE_ROW_ID}_failed_int_exact:raw_data_git_tracked_file_count"
        in summary["product_mode_expected_fail_closed_blockers"]
    )


def test_main_writes_split_acceptance_packet_artifacts(tmp_path: Path) -> None:
    split, plan, bundle, apply, launch, preflight, gate = _write_payloads(tmp_path)
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
            "--launch-command-pack-json",
            str(launch),
            "--product-image-preflight-json",
            str(preflight),
            "--product-source-of-truth-gate-json",
            str(gate),
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
    assert [row["slice_id"] for row in rows] == [
        "slice_a",
        "slice_b",
        "slice_c",
        "slice_d",
        "slice_e",
    ]
    assert out_md.read_text(encoding="utf-8").startswith("# PR #38 Split Acceptance Packet")
