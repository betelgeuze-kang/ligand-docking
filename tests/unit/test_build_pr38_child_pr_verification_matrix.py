from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pr38_child_pr_verification_matrix as mod


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _acceptance_payload(*, missing_focused_test: bool = False) -> dict[str, object]:
    return {
        "summary": {
            "status": "pr38_split_acceptance_packet_ready",
            "split_acceptance_ready": True,
        },
        "rows": [
            {
                "sequence": 1,
                "slice_id": "ci_runner_hygiene",
                "changed_file_count": 7,
                "integration_touchpoint_count": 0,
                "focused_test_command": "pytest ci",
                "claim_boundary": "No product image claim.",
                "slice_acceptance_ready": True,
            },
            {
                "sequence": 2,
                "slice_id": "f2g_f2h_preflight",
                "changed_file_count": 5,
                "integration_touchpoint_count": 0,
                "focused_test_command": "pytest f2g",
                "claim_boundary": "No G1 claim.",
                "slice_acceptance_ready": True,
            },
            {
                "sequence": 3,
                "slice_id": "public_benchmark_phase2",
                "changed_file_count": 14,
                "integration_touchpoint_count": 0,
                "focused_test_command": "" if missing_focused_test else "pytest benchmark",
                "claim_boundary": "No benchmark claim.",
                "slice_acceptance_ready": True,
            },
            {
                "sequence": 4,
                "slice_id": "developer_preview_reproducibility",
                "changed_file_count": 12,
                "integration_touchpoint_count": 0,
                "focused_test_command": "pytest developer-preview",
                "claim_boundary": "No Developer Preview exit claim.",
                "slice_acceptance_ready": True,
            },
            {
                "sequence": 5,
                "slice_id": "api_operator_cockpit",
                "changed_file_count": 18,
                "integration_touchpoint_count": 2,
                "focused_test_command": "pytest api",
                "claim_boundary": "No API readiness claim.",
                "slice_acceptance_ready": True,
            },
            {
                "sequence": 6,
                "slice_id": "docs_tests_reconciliation",
                "changed_file_count": 9,
                "integration_touchpoint_count": 0,
                "focused_test_command": "pytest docs",
                "claim_boundary": "No docs readiness claim.",
                "slice_acceptance_ready": True,
            },
            {
                "sequence": 7,
                "slice_id": "source_of_truth_refresh",
                "changed_file_count": 8,
                "integration_touchpoint_count": 5,
                "focused_test_command": "pytest source",
                "claim_boundary": "No paid-pilot claim.",
                "slice_acceptance_ready": True,
            },
        ],
    }


def _launch_payload(acceptance_payload: dict[str, object]) -> dict[str, object]:
    rows_in = acceptance_payload["rows"]
    assert isinstance(rows_in, list)
    rows = [
        {
            "sequence": row["sequence"],
            "slice_id": row["slice_id"],
            "draft_branch_name": f"codex/pr38-{str(row['slice_id']).replace('_', '-')}",
            "draft_pr_title": f"[codex] Split PR38 {row['slice_id']}",
            "patch_path": f".betelgeuze/pr38_slice_patch_bundle_current/{row['sequence']:02d}-{row['slice_id']}.patch",
            "pr_body_path": f"bodies/{row['sequence']:02d}-{row['slice_id']}-body.md",
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
        for row in rows_in
        if isinstance(row, dict)
    ]
    return {
        "summary": {
            "status": "pr38_child_pr_launch_command_pack_ready",
            "launch_command_pack_ready": True,
            "child_pr_count": len(rows),
            "minimum_child_pr_count": mod.MINIMUM_CHILD_PR_COUNT,
            "minimum_child_pr_count_met": True,
            "body_file_count": len(rows),
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
        },
        "rows": rows,
    }


def _remote_preflight_payload(*, ready: bool) -> dict[str, object]:
    return {
        "summary": {
            "status": (
                "pr38_ci_runner_hygiene_remote_rerun_preflight_ready"
                if ready
                else "blocked_pr38_ci_runner_hygiene_remote_rerun_preflight"
            ),
            "remote_rerun_preflight_ready": ready,
            "operator_remote_ci_dispatch_preconditions_ready": ready,
            "blockers": []
            if ready
            else [
                "ci_runner_hygiene_wrong_branch_for_remote_rerun",
                "ci_runner_hygiene_required_patch_files_uncommitted",
                "ci_runner_hygiene_patch_not_published_for_remote_rerun",
            ],
            "primary_blocker": ""
            if ready
            else "ci_runner_hygiene_wrong_branch_for_remote_rerun",
            "remote_ci_rerun_current_patch_published": ready,
            "remote_ci_rerun_after_push_required": not ready,
            "latest_product_api_worker_run_id": "28733222237",
            "latest_product_image_build_smoke_run_id": "28733222606",
            "latest_product_image_smoke_run_id": "28733223018",
            "latest_remote_ci_observed_checkout_clean_mode": "true",
            "latest_remote_rerun_cannot_validate_local_patch": not ready,
            "next_required_step": (
                "Human owner may run the printed gh workflow commands."
                if ready
                else "Commit and push the ci_runner_hygiene child branch, then rerun this preflight before any gh workflow run command."
            ),
        }
    }


def test_verification_matrix_requires_focused_tests_ai_verify_and_claim_review(tmp_path: Path) -> None:
    acceptance = tmp_path / "acceptance.json"
    payload_in = _acceptance_payload()
    launch = tmp_path / "launch.json"
    _write_json(acceptance, payload_in)
    _write_json(launch, _launch_payload(payload_in))

    payload = mod.build_pr38_child_pr_verification_matrix(
        acceptance_packet_json=acceptance,
        launch_command_pack_json=launch,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "pr38_child_pr_verification_matrix_ready"
    assert summary["verification_matrix_ready"] is True
    assert summary["blockers"] == []
    assert summary["blocker_count"] == 0
    assert summary["primary_blocker"] == ""
    assert summary["verification_matrix_blockers"] == []
    assert summary["verification_matrix_blocker_count"] == 0
    assert summary["upstream_acceptance_ready"] is True
    assert summary["upstream_acceptance_blocker_count"] == 0
    assert summary["upstream_acceptance_blockers"] == []
    assert summary["launch_command_pack_status"] == "pr38_child_pr_launch_command_pack_ready"
    assert summary["launch_command_pack_ready"] is True
    assert summary["launch_command_pack_blockers"] == []
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
    assert summary["child_pr_rows_ready"] is True
    assert summary["all_child_prs_ready"] is True
    assert summary["minimum_child_pr_count"] == mod.MINIMUM_CHILD_PR_COUNT
    assert summary["minimum_child_pr_count_met"] is True
    assert summary["draft_branch_name_mismatch_count"] == 0
    assert summary["draft_branch_name_mismatch_slice_ids"] == []
    assert summary["ci_runner_hygiene_remote_rerun_preflight_present"] is False
    assert summary["ci_runner_hygiene_remote_rerun_preflight_ready"] is False
    assert summary["ci_runner_hygiene_remote_rerun_preflight_blockers"] == []
    assert summary["focused_test_required_count"] == 7
    assert summary["ai_verify_required_count"] == 7
    assert summary["product_mode_required_count"] == 6
    assert summary["product_mode_expected_result"] == "pass_product_smoke_claim_boundaries_locked"
    assert summary["product_mode_claim_boundary_expected_locks"] == (
        mod.PRODUCT_MODE_CLAIM_LOCK_EXPECTATIONS
    )
    assert summary["hunk_split_review_required_count"] == 2
    assert summary["paid_pilot_wording_allowed"] is False
    rows = {row["slice_id"]: row for row in payload["rows"]}
    assert rows["ci_runner_hygiene"]["product_mode_required"] is True
    assert rows["ci_runner_hygiene"]["draft_branch_name"] == "codex/pr38-ci-runner-hygiene"
    assert rows["ci_runner_hygiene"]["expected_draft_branch_name"] == (
        "codex/pr38-ci-runner-hygiene"
    )
    assert rows["ci_runner_hygiene"]["draft_branch_name_matches_expected"] is True
    assert rows["ci_runner_hygiene"]["pr_body_path"] == "bodies/01-ci_runner_hygiene-body.md"
    assert rows["ci_runner_hygiene"]["launch_command_pack_row_ready"] is True
    assert rows["ci_runner_hygiene"]["operator_launch_requires_human_approval"] is True
    assert rows["ci_runner_hygiene"][
        "ci_runner_hygiene_remote_rerun_preflight_required"
    ] is False
    assert rows["f2g_f2h_preflight"]["product_mode_required"] is True
    assert rows["f2g_f2h_preflight"]["product_mode_expected_result"] == (
        "pass_product_smoke_claim_boundaries_locked"
    )
    assert rows["public_benchmark_phase2"]["product_mode_required"] is True
    assert rows["developer_preview_reproducibility"]["product_mode_required"] is True
    assert rows["api_operator_cockpit"]["product_mode_required"] is True
    assert rows["docs_tests_reconciliation"]["product_mode_required"] is False
    assert rows["api_operator_cockpit"]["hunk_split_review_required"] is True
    assert rows["source_of_truth_refresh"]["hunk_split_review_required"] is True
    assert rows["source_of_truth_refresh"]["child_pr_verification_matrix_ready"] is True
    assert rows["public_benchmark_phase2"]["product_mode_expected_blockers"] == mod.KNOWN_PRODUCT_MODE_BLOCKERS
    assert rows["public_benchmark_phase2"]["product_mode_claim_boundary_expected_locks"] == (
        mod.PRODUCT_MODE_CLAIM_LOCK_EXPECTATIONS
    )


def test_verification_matrix_surfaces_blocked_ci_remote_rerun_preflight(
    tmp_path: Path,
) -> None:
    acceptance = tmp_path / "acceptance.json"
    payload_in = _acceptance_payload()
    launch = tmp_path / "launch.json"
    remote_preflight = tmp_path / "remote-preflight.json"
    _write_json(acceptance, payload_in)
    _write_json(launch, _launch_payload(payload_in))
    _write_json(remote_preflight, _remote_preflight_payload(ready=False))

    payload = mod.build_pr38_child_pr_verification_matrix(
        acceptance_packet_json=acceptance,
        launch_command_pack_json=launch,
        ci_runner_hygiene_remote_rerun_preflight_json=remote_preflight,
        root=tmp_path,
    )

    summary = payload["summary"]
    rows = {row["slice_id"]: row for row in payload["rows"]}

    assert summary["status"] == "blocked_pr38_child_pr_verification_matrix"
    assert summary["verification_matrix_ready"] is False
    assert summary["blockers"] == [
        "ci_runner_hygiene:ci_runner_hygiene_remote_rerun_preflight_not_ready"
    ]
    assert summary["blocker_count"] == 1
    assert summary["primary_blocker"] == (
        "ci_runner_hygiene:ci_runner_hygiene_remote_rerun_preflight_not_ready"
    )
    assert summary["verification_matrix_blockers"] == summary["blockers"]
    assert summary["child_pr_rows_ready"] is False
    assert summary["blocked_slice_ids"] == ["ci_runner_hygiene"]
    assert summary["ci_runner_hygiene_remote_rerun_preflight_present"] is True
    assert summary["ci_runner_hygiene_remote_rerun_preflight_ready"] is False
    assert summary["ci_runner_hygiene_remote_rerun_preflight_status"] == (
        "blocked_pr38_ci_runner_hygiene_remote_rerun_preflight"
    )
    assert summary["ci_runner_hygiene_remote_rerun_preflight_primary_blocker"] == (
        "ci_runner_hygiene_wrong_branch_for_remote_rerun"
    )
    assert summary["ci_runner_hygiene_remote_rerun_preflight_blockers"] == [
        "ci_runner_hygiene_wrong_branch_for_remote_rerun",
        "ci_runner_hygiene_required_patch_files_uncommitted",
        "ci_runner_hygiene_patch_not_published_for_remote_rerun",
    ]
    assert summary["ci_runner_hygiene_remote_rerun_after_push_required"] is True
    assert (
        summary["ci_runner_hygiene_latest_remote_rerun_cannot_validate_local_patch"]
        is True
    )
    assert summary["ci_runner_hygiene_latest_remote_ci_observed_checkout_clean_mode"] == (
        "true"
    )
    assert summary["ci_runner_hygiene_latest_product_api_worker_run_id"] == (
        "28733222237"
    )
    assert summary["next_required_step"] == (
        "Commit and push the ci_runner_hygiene child branch, then rerun this preflight before any gh workflow run command."
    )
    assert rows["ci_runner_hygiene"][
        "ci_runner_hygiene_remote_rerun_preflight_required"
    ] is True
    assert rows["ci_runner_hygiene"][
        "ci_runner_hygiene_remote_rerun_preflight_ready"
    ] is False
    assert rows["ci_runner_hygiene"][
        "ci_runner_hygiene_latest_remote_rerun_cannot_validate_local_patch"
    ] is True
    assert "ci_runner_hygiene_remote_rerun_preflight_not_ready" in rows[
        "ci_runner_hygiene"
    ]["verification_blockers"]


def test_verification_matrix_blocks_missing_focused_test_command(tmp_path: Path) -> None:
    acceptance = tmp_path / "acceptance.json"
    payload_in = _acceptance_payload(missing_focused_test=True)
    launch = tmp_path / "launch.json"
    _write_json(acceptance, payload_in)
    _write_json(launch, _launch_payload(payload_in))

    payload = mod.build_pr38_child_pr_verification_matrix(
        acceptance_packet_json=acceptance,
        launch_command_pack_json=launch,
        root=tmp_path,
    )

    assert payload["summary"]["status"] == "blocked_pr38_child_pr_verification_matrix"
    assert payload["summary"]["verification_matrix_ready"] is False
    assert payload["summary"]["upstream_acceptance_ready"] is True
    assert payload["summary"]["child_pr_rows_ready"] is False
    assert payload["summary"]["all_child_prs_ready"] is False
    assert payload["summary"]["blocked_slice_ids"] == ["public_benchmark_phase2"]
    rows = {row["slice_id"]: row for row in payload["rows"]}
    assert rows["public_benchmark_phase2"]["verification_blockers"] == ["focused_test_command_missing"]


def test_verification_matrix_blocks_branch_name_mismatch(tmp_path: Path) -> None:
    acceptance = tmp_path / "acceptance.json"
    payload_in = _acceptance_payload()
    launch_payload = _launch_payload(payload_in)
    launch_rows = launch_payload["rows"]
    assert isinstance(launch_rows, list)
    launch_rows[0]["draft_branch_name"] = "codex/pr38-ci_runner_hygiene"
    launch = tmp_path / "launch.json"
    _write_json(acceptance, payload_in)
    _write_json(launch, launch_payload)

    payload = mod.build_pr38_child_pr_verification_matrix(
        acceptance_packet_json=acceptance,
        launch_command_pack_json=launch,
        root=tmp_path,
    )

    summary = payload["summary"]
    rows = {row["slice_id"]: row for row in payload["rows"]}

    assert summary["status"] == "blocked_pr38_child_pr_verification_matrix"
    assert summary["child_pr_rows_ready"] is False
    assert summary["blocked_slice_ids"] == ["ci_runner_hygiene"]
    assert summary["draft_branch_name_mismatch_count"] == 1
    assert summary["draft_branch_name_mismatch_slice_ids"] == ["ci_runner_hygiene"]
    assert rows["ci_runner_hygiene"]["draft_branch_name_matches_expected"] is False
    assert rows["ci_runner_hygiene"]["expected_draft_branch_name"] == (
        "codex/pr38-ci-runner-hygiene"
    )
    assert rows["ci_runner_hygiene"]["verification_blockers"] == [
        "launch_command_pack_draft_branch_mismatch:"
        "codex/pr38-ci_runner_hygiene!=codex/pr38-ci-runner-hygiene"
    ]


def test_verification_matrix_blocks_missing_launch_command_pack(tmp_path: Path) -> None:
    acceptance = tmp_path / "acceptance.json"
    _write_json(acceptance, _acceptance_payload())

    payload = mod.build_pr38_child_pr_verification_matrix(
        acceptance_packet_json=acceptance,
        launch_command_pack_json=tmp_path / "missing-launch.json",
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pr38_child_pr_verification_matrix"
    assert summary["verification_matrix_ready"] is False
    assert summary["launch_command_pack_ready"] is False
    assert summary["launch_command_pack_blockers"] == [
        "launch_command_pack_not_ready:missing",
        "launch_command_pack_alignment_not_ready",
        "launch_command_pack_safety_contract_not_ready",
    ]
    rows = {row["slice_id"]: row for row in payload["rows"]}
    assert rows["ci_runner_hygiene"]["verification_blockers"] == [
        "launch_command_pack_row_missing"
    ]


def test_verification_matrix_inherits_product_mode_blockers_from_acceptance_packet(
    tmp_path: Path,
) -> None:
    acceptance = tmp_path / "acceptance.json"
    payload_in = _acceptance_payload()
    payload_in["summary"] = {
        **dict(payload_in["summary"]),
        "status": "blocked_pr38_split_acceptance_packet",
        "split_acceptance_ready": False,
        "split_structural_acceptance_ready": True,
        "product_mode_verification_ready": False,
        "product_mode_expected_result": "blocked_product_mode_verification",
        "product_mode_expected_fail_closed_blockers": [
            "receipt_runner_hygiene_not_ready",
            "receipt_container_output_uid_gid_not_pinned",
        ],
        "blockers": [
            "product_mode:receipt_runner_hygiene_not_ready",
            "product_mode:receipt_container_output_uid_gid_not_pinned",
        ],
        "next_required_step": "Resolve runner hygiene blockers before treating child PRs as verified.",
    }
    launch = tmp_path / "launch.json"
    _write_json(acceptance, payload_in)
    _write_json(launch, _launch_payload(payload_in))

    payload = mod.build_pr38_child_pr_verification_matrix(
        acceptance_packet_json=acceptance,
        launch_command_pack_json=launch,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pr38_child_pr_verification_matrix"
    assert summary["verification_matrix_ready"] is False
    assert summary["upstream_acceptance_ready"] is False
    assert summary["upstream_acceptance_blocker_count"] == 2
    assert summary["upstream_acceptance_blockers"] == [
        "product_mode:receipt_runner_hygiene_not_ready",
        "product_mode:receipt_container_output_uid_gid_not_pinned",
    ]
    assert summary["child_pr_rows_ready"] is True
    assert summary["all_child_prs_ready"] is True
    assert summary["product_mode_verification_ready"] is False
    assert summary["product_mode_expected_result"] == "blocked_product_mode_verification"
    assert summary["product_mode_expected_fail_closed_blockers"] == [
        "receipt_runner_hygiene_not_ready",
        "receipt_container_output_uid_gid_not_pinned",
    ]
    assert (
        summary["next_required_step"]
        == "Resolve runner hygiene blockers before treating child PRs as verified."
    )
    rows = {row["slice_id"]: row for row in payload["rows"]}
    assert rows["ci_runner_hygiene"]["product_mode_expected_result"] == (
        "blocked_product_mode_verification"
    )
    assert rows["ci_runner_hygiene"]["product_mode_expected_blockers"] == [
        "receipt_runner_hygiene_not_ready",
        "receipt_container_output_uid_gid_not_pinned",
    ]


def test_main_writes_verification_matrix_artifacts(tmp_path: Path) -> None:
    acceptance = tmp_path / "acceptance.json"
    payload_in = _acceptance_payload()
    launch = tmp_path / "launch.json"
    _write_json(acceptance, payload_in)
    _write_json(launch, _launch_payload(payload_in))
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    rc = mod.main(
        [
            "--root",
            str(tmp_path),
            "--acceptance-packet-json",
            str(acceptance),
            "--launch-command-pack-json",
            str(launch),
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
    assert payload["summary"]["status"] == "pr38_child_pr_verification_matrix_ready"
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["slice_id"] for row in rows] == [
        "ci_runner_hygiene",
        "f2g_f2h_preflight",
        "public_benchmark_phase2",
        "developer_preview_reproducibility",
        "api_operator_cockpit",
        "docs_tests_reconciliation",
        "source_of_truth_refresh",
    ]
    assert out_md.read_text(encoding="utf-8").startswith("# PR #38 Child PR Verification Matrix")
