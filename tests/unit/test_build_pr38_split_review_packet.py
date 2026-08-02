from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pr38_split_review_packet as mod


def _write_task_specs(root: Path) -> None:
    for spec in mod._SLICE_SPECS:
        path = root / spec["task_spec_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Task\n\n## Verification\n\nRun focused tests.\n\n## Stop Conditions\n\nDo not promote claim text.\n",
            encoding="utf-8",
        )


def _write_name_status(root: Path, rows: list[tuple[str, str]]) -> Path:
    path = root / "name-status.txt"
    path.write_text("\n".join(f"{status}\t{file_path}" for status, file_path in rows) + "\n", encoding="utf-8")
    return path


def test_pr38_split_review_packet_assigns_each_slice_and_preserves_claim_boundaries(tmp_path: Path) -> None:
    _write_task_specs(tmp_path)
    changed_files = _write_name_status(
        tmp_path,
        [
            ("M", "deploy/verify_product_image.sh"),
            ("M", "tests/unit/test_ai_design_kiro_wrapper_contract.py"),
            ("A", "tests/unit/test_build_pr38_ci_runner_hygiene_child_pr_gate.py"),
            ("A", "tests/unit/test_build_pr38_ci_runner_hygiene_remote_rerun_preflight.py"),
            ("A", "tests/unit/test_build_pr38_child_pr_verification_matrix.py"),
            ("A", "tests/unit/test_observe_product_ci_runtime_gate_from_github.py"),
            ("A", "tools/product/build_pr38_ci_runner_hygiene_child_pr_gate.py"),
            ("A", "tools/product/build_pr38_ci_runner_hygiene_remote_rerun_preflight.py"),
            ("A", "tools/product/build_pr38_child_pr_verification_matrix.py"),
            ("A", "tools/product/observe_product_ci_runtime_gate_from_github.py"),
            ("M", "tools/product/build_release_source_of_truth_gap5_scan.py"),
            ("M", "betelgeuze_product/public_benchmark.py"),
            ("A", "tools/product/build_gpcr_hard_decoy_claim_unlock_audit.py"),
            ("A", "tools/product/build_competition_benchmark_rollup.py"),
            ("A", "api/product_pocketmd_lite.py"),
            ("A", "tools/product/build_developer_preview_final_gate_audit.py"),
            ("A", "api/product_operator_cockpit.py"),
            ("A", "docs/ai/tasks/TASK-pr38-stabilization-split.md"),
            ("A", "tools/product/build_f2g_f2h_authoritative_surface_recovery_packet.py"),
            ("M", "tools/product/build_product_release_source_of_truth_gate.py"),
        ],
    )

    payload = mod.build_pr38_split_review_packet(changed_files=changed_files, root=tmp_path)

    summary = payload["summary"]
    assert summary["status"] == "pr38_split_review_packet_ready"
    assert summary["changed_file_count"] == 20
    assert summary["assigned_file_count"] == 20
    assert summary["unassigned_file_count"] == 0
    assert summary["minimum_child_pr_count"] == mod.MINIMUM_CHILD_PR_COUNT
    assert summary["nonempty_child_pr_count"] == 10
    assert summary["minimum_child_pr_count_met"] is True
    assert summary["integration_touchpoint_count"] == 2
    assert summary["hunk_split_review_required_count"] == 2
    assert summary["external_state_mutated"] is False
    assert summary["claim_promotion_allowed"] is False
    slices = {row["slice_id"]: row for row in payload["slices"]}
    assert set(slices) == {
        "ci_runner_hygiene",
        "source_of_truth_refresh",
        "public_benchmark_phase2",
        "competition_benchmark_credibility",
        "gpcr_hard_decoy_closure",
        "pocketmd_lite_recovery",
        "developer_preview_reproducibility",
        "api_operator_cockpit",
        "docs_tests_reconciliation",
        "f2g_f2h_preflight",
    }
    assert all(row["slice_ready_for_child_pr_review"] is True for row in payload["slices"])
    assert "paid-pilot" in slices["source_of_truth_refresh"]["claim_boundary"]
    assert "artifact ownership" in slices["ci_runner_hygiene"]["claim_boundary"]
    assert "tests/unit/test_build_product_ci_runtime_gate.py" in slices["ci_runner_hygiene"][
        "focused_test_command"
    ]
    assert "tests/unit/test_build_github_self_hosted_runner_host_preflight.py" in slices[
        "ci_runner_hygiene"
    ]["focused_test_command"]
    assert "tests/unit/test_ai_design_kiro_wrapper_contract.py" in slices[
        "ci_runner_hygiene"
    ]["focused_test_command"]
    assert "tests/unit/test_build_pr38_ci_runner_hygiene_child_pr_gate.py" in slices[
        "ci_runner_hygiene"
    ]["focused_test_command"]
    assert "tests/unit/test_build_pr38_ci_runner_hygiene_remote_rerun_preflight.py" in slices[
        "ci_runner_hygiene"
    ]["focused_test_command"]
    assert "tests/unit/test_build_pr38_child_pr_verification_matrix.py" in slices[
        "ci_runner_hygiene"
    ]["focused_test_command"]
    assert "tests/unit/test_observe_product_ci_runtime_gate_from_github.py" in slices[
        "ci_runner_hygiene"
    ]["focused_test_command"]
    assert "tests/unit/test_release_ci_remote_green_evidence_contract.py" in slices[
        "ci_runner_hygiene"
    ]["focused_test_command"]
    assert "Developer Preview" in slices["developer_preview_reproducibility"]["claim_boundary"]
    assert "credibility evidence" in slices["competition_benchmark_credibility"]["claim_boundary"]
    assert "read-only" in slices["api_operator_cockpit"]["claim_boundary"]
    assert "Broad GPCR" in slices["gpcr_hard_decoy_closure"]["claim_boundary"]
    assert "green-band" in slices["pocketmd_lite_recovery"]["claim_boundary"]


def test_pr38_split_review_packet_blocks_unassigned_files(tmp_path: Path) -> None:
    _write_task_specs(tmp_path)
    changed_files = _write_name_status(
        tmp_path,
        [
            ("M", "tools/product/build_release_source_of_truth_gap5_scan.py"),
            ("M", "unexpected/new_surface.py"),
        ],
    )

    payload = mod.build_pr38_split_review_packet(changed_files=changed_files, root=tmp_path)

    assert payload["summary"]["status"] == "blocked_pr38_split_review_packet"
    assert payload["summary"]["split_review_ready"] is False
    assert payload["summary"]["unassigned_file_count"] == 1
    assert payload["summary"]["unassigned_file_paths"] == ["unexpected/new_surface.py"]


def test_pr38_split_review_packet_merges_worktree_overlay(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_task_specs(tmp_path)
    monkeypatch.setattr(
        mod,
        "_git_name_status",
        lambda *, base_ref, root: [
            ("M", "betelgeuze_product/public_benchmark.py"),
            ("M", ".env.local"),
        ],
    )
    monkeypatch.setattr(
        mod,
        "_git_worktree_name_status",
        lambda *, root: [
            ("M", "deploy/verify_product_image.sh"),
            ("M", "tools/product/build_developer_preview_final_gate_audit.py"),
            ("M", ".env.test"),
        ],
    )

    payload = mod.build_pr38_split_review_packet(root=tmp_path)
    summary = payload["summary"]
    rows = {row["file_path"]: row for row in payload["rows"]}

    assert summary["worktree_overlay_enabled"] is True
    assert summary["base_changed_file_count"] == 1
    assert summary["worktree_changed_file_count"] == 2
    assert summary["changed_file_count"] == 3
    assert rows["deploy/verify_product_image.sh"]["slice_id"] == "ci_runner_hygiene"
    assert rows["tools/product/build_developer_preview_final_gate_audit.py"]["slice_id"] == (
        "developer_preview_reproducibility"
    )
    assert ".env.local" not in rows
    assert ".env.test" not in rows


def test_main_writes_pr38_split_review_packet_artifacts(tmp_path: Path) -> None:
    _write_task_specs(tmp_path)
    changed_files = _write_name_status(
        tmp_path,
        [
            ("M", "deploy/verify_product_image.sh"),
            ("M", "tools/product/build_release_source_of_truth_gap5_scan.py"),
            ("M", "betelgeuze_product/public_benchmark.py"),
            ("A", "tools/product/build_gpcr_hard_decoy_claim_unlock_audit.py"),
            ("A", "tools/product/build_competition_benchmark_rollup.py"),
            ("A", "api/product_pocketmd_lite.py"),
            ("A", "tools/product/build_developer_preview_final_gate_audit.py"),
            ("A", "api/product_operator_cockpit.py"),
            ("A", "docs/ai/tasks/TASK-pr38-stabilization-split.md"),
            ("A", "tools/product/build_f2g_f2h_authoritative_surface_recovery_packet.py"),
        ],
    )
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    rc = mod.main(
        [
            "--root",
            str(tmp_path),
            "--changed-files",
            str(changed_files),
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
    assert payload["summary"]["status"] == "pr38_split_review_packet_ready"
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert len(rows) == 10
    assert out_md.read_text(encoding="utf-8").startswith("# PR #38 Split Review Packet")
