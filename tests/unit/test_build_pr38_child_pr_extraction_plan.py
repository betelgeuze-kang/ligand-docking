from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_pr38_child_pr_extraction_plan as mod


def _split_packet() -> dict[str, object]:
    slices = [
        {
            "slice_id": "ci_runner_hygiene",
            "changed_file_count": 7,
            "slice_ready_for_child_pr_review": True,
            "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-ci-runner-hygiene.md",
            "focused_test_command": "pytest ci",
            "claim_boundary": "No product image claim.",
        },
        {
            "slice_id": "source_of_truth_refresh",
            "changed_file_count": 8,
            "slice_ready_for_child_pr_review": True,
            "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-source-of-truth-refresh.md",
            "focused_test_command": "pytest source",
            "claim_boundary": "No paid-pilot claim.",
        },
        {
            "slice_id": "public_benchmark_phase2",
            "changed_file_count": 14,
            "slice_ready_for_child_pr_review": True,
            "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-public-benchmark-phase2.md",
            "focused_test_command": "pytest benchmark",
            "claim_boundary": "No benchmark claim.",
        },
        {
            "slice_id": "gpcr_hard_decoy_closure",
            "changed_file_count": 35,
            "slice_ready_for_child_pr_review": True,
            "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-gpcr-hard-decoy-closure.md",
            "focused_test_command": "pytest gpcr",
            "claim_boundary": "No broad GPCR claim.",
        },
        {
            "slice_id": "competition_benchmark_credibility",
            "changed_file_count": 22,
            "slice_ready_for_child_pr_review": True,
            "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-competition-benchmark-credibility.md",
            "focused_test_command": "pytest competition",
            "claim_boundary": "No ligand commercial claim.",
        },
        {
            "slice_id": "pocketmd_lite_recovery",
            "changed_file_count": 34,
            "slice_ready_for_child_pr_review": True,
            "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-pocketmd-lite-recovery.md",
            "focused_test_command": "pytest pocketmd",
            "claim_boundary": "No green-band claim.",
        },
        {
            "slice_id": "developer_preview_reproducibility",
            "changed_file_count": 12,
            "slice_ready_for_child_pr_review": True,
            "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-developer-preview-reproducibility.md",
            "focused_test_command": "pytest developer-preview",
            "claim_boundary": "No Developer Preview exit claim.",
        },
        {
            "slice_id": "api_operator_cockpit",
            "changed_file_count": 18,
            "slice_ready_for_child_pr_review": True,
            "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-api-operator-cockpit.md",
            "focused_test_command": "pytest api",
            "claim_boundary": "No API readiness claim.",
        },
        {
            "slice_id": "docs_tests_reconciliation",
            "changed_file_count": 9,
            "slice_ready_for_child_pr_review": True,
            "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-docs-tests-reconciliation.md",
            "focused_test_command": "pytest docs",
            "claim_boundary": "No behavior claim.",
        },
        {
            "slice_id": "f2g_f2h_preflight",
            "changed_file_count": 5,
            "slice_ready_for_child_pr_review": True,
            "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-f2g-f2h-preflight.md",
            "focused_test_command": "pytest f2g",
            "claim_boundary": "No G1 claim.",
        },
    ]
    rows = [
        {"slice_id": "ci_runner_hygiene", "file_path": "deploy/verify_product_image.sh", "integration_touchpoint": False},
        {"slice_id": "source_of_truth_refresh", "file_path": "tools/product/build_product_release_source_of_truth_gate.py", "integration_touchpoint": True},
        {"slice_id": "source_of_truth_refresh", "file_path": "docs/product_stage_and_roadmap_2026_06_30.md", "integration_touchpoint": False},
        {"slice_id": "pocketmd_lite_recovery", "file_path": "api/main.py", "integration_touchpoint": True},
        {"slice_id": "public_benchmark_phase2", "file_path": "betelgeuze_product/public_benchmark.py", "integration_touchpoint": False},
        {"slice_id": "competition_benchmark_credibility", "file_path": "tools/product/build_competition_benchmark_rollup.py", "integration_touchpoint": False},
        {"slice_id": "gpcr_hard_decoy_closure", "file_path": "betelgeuze_product/gpcr_hard_decoy_suite.py", "integration_touchpoint": False},
        {"slice_id": "developer_preview_reproducibility", "file_path": "tools/product/build_developer_preview_final_gate_audit.py", "integration_touchpoint": False},
        {"slice_id": "api_operator_cockpit", "file_path": "api/product_operator_cockpit.py", "integration_touchpoint": True},
        {"slice_id": "docs_tests_reconciliation", "file_path": "docs/ai/tasks/TASK-pr38-stabilization-split.md", "integration_touchpoint": False},
        {"slice_id": "f2g_f2h_preflight", "file_path": "docs/f2g_f2h_surface_preflight.md", "integration_touchpoint": False},
    ]
    return {
        "summary": {"status": "pr38_split_review_packet_ready", "split_review_ready": True},
        "slices": slices,
        "rows": rows,
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_child_pr_extraction_plan_orders_source_of_truth_reconciliation_last(tmp_path: Path) -> None:
    split_packet = tmp_path / "split.json"
    _write_json(split_packet, _split_packet())

    payload = mod.build_pr38_child_pr_extraction_plan(split_packet_json=split_packet, root=tmp_path)

    summary = payload["summary"]
    assert summary["status"] == "pr38_child_pr_extraction_plan_ready"
    assert summary["child_pr_count"] == 10
    assert summary["minimum_child_pr_count"] == mod.MINIMUM_CHILD_PR_COUNT
    assert summary["minimum_child_pr_count_met"] is True
    assert summary["ready_child_pr_count"] == 10
    assert summary["source_of_truth_sequence"] == 10
    assert summary["source_of_truth_depends_on_slice_count"] == 9
    assert summary["source_of_truth_registry_reconciles_last"] is True
    assert summary["hunk_split_review_required_count"] == 3
    assert summary["hunk_split_review_required_child_pr_count"] == 3
    assert summary["external_state_mutated"] is False
    rows = {row["slice_id"]: row for row in payload["rows"]}
    assert rows["ci_runner_hygiene"]["sequence"] == 1
    assert rows["f2g_f2h_preflight"]["sequence"] == 2
    assert rows["source_of_truth_refresh"]["depends_on_slice_ids"] == [
        "ci_runner_hygiene",
        "f2g_f2h_preflight",
        "public_benchmark_phase2",
        "competition_benchmark_credibility",
        "gpcr_hard_decoy_closure",
        "pocketmd_lite_recovery",
        "developer_preview_reproducibility",
        "api_operator_cockpit",
        "docs_tests_reconciliation",
    ]
    assert rows["pocketmd_lite_recovery"]["integration_touchpoint_paths"] == ["api/main.py"]
    assert rows["api_operator_cockpit"]["integration_touchpoint_paths"] == ["api/product_operator_cockpit.py"]
    assert rows["source_of_truth_refresh"]["hunk_split_review_required"] is True


def test_child_pr_extraction_plan_blocks_if_split_packet_is_not_ready(tmp_path: Path) -> None:
    split = _split_packet()
    summary = split["summary"]
    assert isinstance(summary, dict)
    summary["split_review_ready"] = False
    summary["status"] = "blocked_pr38_split_review_packet"
    split_packet = tmp_path / "split.json"
    _write_json(split_packet, split)

    payload = mod.build_pr38_child_pr_extraction_plan(split_packet_json=split_packet, root=tmp_path)

    assert payload["summary"]["status"] == "blocked_pr38_child_pr_extraction_plan"
    assert payload["summary"]["extraction_plan_ready"] is False
    assert payload["summary"]["not_ready_child_pr_count"] == 10


def test_main_writes_child_pr_extraction_plan_artifacts(tmp_path: Path) -> None:
    split_packet = tmp_path / "split.json"
    _write_json(split_packet, _split_packet())
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"

    rc = mod.main(
        [
            "--root",
            str(tmp_path),
            "--split-packet-json",
            str(split_packet),
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
    assert payload["summary"]["status"] == "pr38_child_pr_extraction_plan_ready"
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert [row["slice_id"] for row in rows] == [
        "ci_runner_hygiene",
        "f2g_f2h_preflight",
        "public_benchmark_phase2",
        "competition_benchmark_credibility",
        "gpcr_hard_decoy_closure",
        "pocketmd_lite_recovery",
        "developer_preview_reproducibility",
        "api_operator_cockpit",
        "docs_tests_reconciliation",
        "source_of_truth_refresh",
    ]
    assert out_md.read_text(encoding="utf-8").startswith("# PR #38 Child PR Extraction Plan")
