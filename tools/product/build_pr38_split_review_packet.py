#!/usr/bin/env python3
"""Build a read-only PR #38 split review packet.

The packet maps each changed file in the large PR #38 branch to one proposed
child PR slice and verifies that each slice has a task spec, focused tests, and
an explicit claim boundary. It does not create branches, stage files, post to
GitHub, or mutate external state.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BASE_REF = "origin/main"
DEFAULT_OUT_JSON = ".betelgeuze/pr38_split_review_packet_current.json"
DEFAULT_OUT_CSV = ".betelgeuze/pr38_split_review_packet_current.csv"
DEFAULT_OUT_MD = ".betelgeuze/pr38_split_review_packet_current.md"

PACKET_TYPE = "pr38_split_review_packet"
SCHEMA_VERSION = "pr38_split_review_packet_v1"

CLAIM_BOUNDARY = (
    "PR #38 split review packet only; it maps local changed files to review slices and checks that each slice "
    "has focused verification and claim-boundary text. It does not merge PR #38, create branches, stage, commit, "
    "push, post comments, run external benchmark jobs, submit CASP targets, promote paid-pilot wording, or mutate "
    "external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "claim_promotion_allowed": False,
}


_SLICE_SPECS: list[dict[str, Any]] = [
    {
        "slice_id": "source_of_truth_refresh",
        "title": "source-of-truth gap scan + release refresh path",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-source-of-truth-refresh.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_build_release_source_of_truth_gap5_scan.py "
            "tests/unit/test_build_product_release_source_of_truth_gate.py"
        ),
        "claim_boundary": (
            "No release-ready, paid-pilot-ready, final-refresh-success, or full-commercial-release claim until "
            "source-of-truth and final refresh gates are fresh and verified."
        ),
        "patterns": [
            "betelgeuze_product/capability_surface.py",
            "docs/product_stage_and_roadmap_2026_06_30.md",
            "tests/unit/test_build_product_capability_surface_contract.py",
            "tests/unit/test_build_product_release_source_of_truth_gate.py",
            "tests/unit/test_build_release_source_of_truth_gap5_scan.py",
            "tools/product/build_product_release_source_of_truth_gate.py",
            "tools/product/build_release_source_of_truth_gap5_scan.py",
            "tools/product/run_product_release_current_refresh.py",
        ],
    },
    {
        "slice_id": "public_benchmark_phase2",
        "title": "public benchmark Phase 2 audit surfaces",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-public-benchmark-phase2.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_betelgeuze_product_public_benchmark.py "
            "tests/unit/test_betelgeuze_product_public_benchmark_provenance.py "
            "tests/unit/test_build_public_benchmark_phase2_harness_audit.py "
            "tests/unit/test_build_product_public_benchmark_contract.py "
            "tests/unit/test_build_product_public_benchmark_work_order.py "
            "tests/unit/test_build_pdbbind_casf_pose_affinity_results.py "
            "tests/unit/test_docking_gold_benchmark_metrics.py"
        ),
        "claim_boundary": (
            "No external beta, benchmark-success, or broad docking-accuracy claim until real reviewed benchmark "
            "receipts are attached and ledger-approved."
        ),
        "patterns": [
            "betelgeuze_engine/benchmark/docking_gold.py",
            "betelgeuze_product/public_benchmark.py",
            "betelgeuze_product/public_benchmark_provenance.py",
            "betelgeuze_product/public_benchmark_work_order.py",
            "tests/unit/test_betelgeuze_product_public_benchmark.py",
            "tests/unit/test_betelgeuze_product_public_benchmark_provenance.py",
            "tests/unit/test_build_pdbbind_casf_pose_affinity_results.py",
            "tests/unit/test_build_product_public_benchmark_contract.py",
            "tests/unit/test_build_product_public_benchmark_work_order.py",
            "tests/unit/test_build_public_benchmark_phase2_harness_audit.py",
            "tests/unit/test_docking_gold_benchmark_metrics.py",
            "tools/accounting/build_pdbbind_casf_pose_affinity_results.py",
            "tools/accounting/build_product_public_benchmark_contract.py",
            "tools/product/build_public_benchmark_phase2_harness_audit.py",
        ],
    },
    {
        "slice_id": "gpcr_hard_decoy_closure",
        "title": "GPCR hard-decoy closure tools",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-gpcr-hard-decoy-closure.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_gpcr_hard_decoy_suite.py "
            "tests/unit/test_build_gpcr_hard_decoy_*.py tests/unit/test_build_gpcr_residual_prototype_spec.py"
        ),
        "claim_boundary": (
            "Broad GPCR and hard-decoy closure claims stay locked until DRD2/HTR2A/OPRM1 rows meet the registered "
            "numeric thresholds and ledger approval exists."
        ),
        "patterns": [
            "betelgeuze_product/gpcr_hard_decoy_suite.py",
            "config/gpcr_hard_decoy*.csv",
            "docs/gpcr_hard_decoy_suite_*.md",
            "tests/unit/test_build_gpcr_hard_decoy_*.py",
            "tests/unit/test_build_gpcr_residual_prototype_spec.py",
            "tests/unit/test_gpcr_hard_decoy_suite.py",
            "tools/accounting/build_gpcr_residual_prototype_spec.py",
            "tools/product/build_gpcr_hard_decoy_*.py",
        ],
    },
    {
        "slice_id": "pocketmd_lite_recovery",
        "title": "PocketMD Lite API/reporting/evidence recovery",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-pocketmd-lite-recovery.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_api_product_import.py "
            "tests/unit/test_product_pocketmd_lite_api.py tests/unit/test_pocketmd_lite_contract.py "
            "tests/unit/test_run_ligand_backmapping_scoring.py tests/unit/test_build_pocketmd_lite_*.py"
        ),
        "claim_boundary": (
            "PocketMD Lite recovery outputs are collector inputs only; no green-band or claim-grade metric claim "
            "until reviewed local-min, H-bond, contact, clash, relief, and banding evidence exists."
        ),
        "patterns": [
            "api/main.py",
            "api/product_pocketmd_lite.py",
            "betelgeuze_engine/product/runners/backmapping_scoring.py",
            "betelgeuze_product/pocketmd_lite_contract.py",
            "config/pocketmd_lite_candidates_current.csv",
            "docs/pocketmd_lite_contract.md",
            "tests/unit/test_api_product_import.py",
            "tests/unit/test_build_pocketmd_lite_*.py",
            "tests/unit/test_pocketmd_lite_contract.py",
            "tests/unit/test_product_pocketmd_lite_api.py",
            "tests/unit/test_run_ligand_backmapping_scoring.py",
            "tools/product/build_pocketmd_lite_*.py",
        ],
    },
    {
        "slice_id": "f2g_f2h_preflight",
        "title": "F2g/F2h preflight/work order",
        "task_spec_path": "docs/ai/tasks/TASK-pr38-slice-f2g-f2h-preflight.md",
        "focused_test_command": (
            "python3 -m pytest -q tests/unit/test_build_f2g_f2h_authoritative_surface_recovery_packet.py"
        ),
        "claim_boundary": (
            "F2g/F2h remains non-promoting: no placeholder surfaces, F2g audit, F2h continuation, 0.656 "
            "regeneration, G1 claim, or solver claim without restored authoritative inputs."
        ),
        "patterns": [
            "docs/f2g_f2h_surface_preflight.md",
            "tests/unit/test_build_f2g_f2h_authoritative_surface_recovery_packet.py",
            "tools/accounting/build_f2g_f2h_authoritative_surface_recovery_packet.py",
            "tools/build_f2g_f2h_authoritative_surface_recovery_packet.py",
            "tools/product/build_f2g_f2h_authoritative_surface_recovery_packet.py",
        ],
    },
]

_INTEGRATION_TOUCHPOINTS = {
    "api/main.py",
    "betelgeuze_product/capability_surface.py",
    "tests/unit/test_api_product_import.py",
    "tests/unit/test_build_product_capability_surface_contract.py",
    "tests/unit/test_build_product_release_source_of_truth_gate.py",
    "tools/product/build_product_release_source_of_truth_gate.py",
    "tools/product/run_product_release_current_refresh.py",
}

_TASK_SPEC_REQUIRED_TERMS = ("Do not", "claim", "Verification", "Stop Conditions")


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _read_name_status(path_like: str | Path, *, root: Path = ROOT) -> list[tuple[str, str]]:
    path = _resolve(path_like, root=root)
    rows: list[tuple[str, str]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            rows.append(("?", parts[0]))
            continue
        status = parts[0]
        file_path = parts[-1]
        rows.append((status, file_path))
    return rows


def _git_name_status(*, base_ref: str, root: Path) -> list[tuple[str, str]]:
    proc = subprocess.run(
        ["git", "diff", "--name-status", f"{base_ref}...HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    rows: list[tuple[str, str]] = []
    for raw_line in proc.stdout.splitlines():
        parts = raw_line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0], parts[-1]))
    return rows


def _matches(patterns: list[str], file_path: str) -> bool:
    return any(fnmatch.fnmatchcase(file_path, pattern) for pattern in patterns)


def _slice_for_path(file_path: str) -> tuple[dict[str, Any] | None, list[str]]:
    matches = [spec for spec in _SLICE_SPECS if _matches(spec["patterns"], file_path)]
    return (matches[0] if len(matches) == 1 else None, [spec["slice_id"] for spec in matches])


def _task_spec_status(spec: dict[str, Any], *, root: Path) -> dict[str, Any]:
    path = _resolve(spec["task_spec_path"], root=root)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    missing_terms = [term for term in _TASK_SPEC_REQUIRED_TERMS if term not in text]
    return {
        "task_spec_path": spec["task_spec_path"],
        "task_spec_present": path.exists(),
        "task_spec_has_claim_boundary_terms": not missing_terms,
        "task_spec_missing_terms": missing_terms,
    }


def build_pr38_split_review_packet(
    *,
    changed_files: str | Path | None = None,
    base_ref: str = DEFAULT_BASE_REF,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    name_status_rows = (
        _read_name_status(changed_files, root=root_path)
        if changed_files is not None
        else _git_name_status(base_ref=base_ref, root=root_path)
    )
    rows: list[dict[str, Any]] = []
    for status, file_path in name_status_rows:
        spec, matching_slice_ids = _slice_for_path(file_path)
        assigned = spec is not None
        slice_id = _text(spec.get("slice_id")) if spec else ""
        rows.append(
            {
                "file_path": file_path,
                "git_status": status,
                "assigned": assigned,
                "slice_id": slice_id or "unassigned",
                "matching_slice_ids": matching_slice_ids,
                "integration_touchpoint": file_path in _INTEGRATION_TOUCHPOINTS,
                "hunk_split_review_required": file_path in _INTEGRATION_TOUCHPOINTS,
                "focused_test_command": _text(spec.get("focused_test_command")) if spec else "",
                "claim_boundary": _text(spec.get("claim_boundary")) if spec else "",
            }
        )

    slice_rows: list[dict[str, Any]] = []
    for spec in _SLICE_SPECS:
        slice_id = spec["slice_id"]
        assigned_rows = [row for row in rows if row["slice_id"] == slice_id]
        task_status = _task_spec_status(spec, root=root_path)
        slice_ready = bool(
            assigned_rows
            and task_status["task_spec_present"]
            and task_status["task_spec_has_claim_boundary_terms"]
            and spec.get("focused_test_command")
            and spec.get("claim_boundary")
        )
        slice_rows.append(
            {
                "slice_id": slice_id,
                "title": spec["title"],
                "changed_file_count": len(assigned_rows),
                "integration_touchpoint_count": sum(1 for row in assigned_rows if row["integration_touchpoint"]),
                "slice_ready_for_child_pr_review": slice_ready,
                "focused_test_command": spec["focused_test_command"],
                "claim_boundary": spec["claim_boundary"],
                **task_status,
                **_READ_ONLY_FLAGS,
            }
        )

    unassigned_rows = [row for row in rows if not row["assigned"]]
    ambiguous_rows = [row for row in rows if len(row["matching_slice_ids"]) > 1]
    empty_slices = [row["slice_id"] for row in slice_rows if int(row["changed_file_count"]) == 0]
    missing_task_specs = [row["slice_id"] for row in slice_rows if not row["task_spec_present"]]
    weak_task_specs = [row["slice_id"] for row in slice_rows if not row["task_spec_has_claim_boundary_terms"]]
    ready = not unassigned_rows and not ambiguous_rows and not empty_slices and not missing_task_specs and not weak_task_specs
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "pr38_split_review_packet_ready" if ready else "blocked_pr38_split_review_packet",
        "split_review_ready": ready,
        "base_ref": base_ref,
        "changed_file_count": len(rows),
        "assigned_file_count": sum(1 for row in rows if row["assigned"]),
        "unassigned_file_count": len(unassigned_rows),
        "unassigned_file_paths": [row["file_path"] for row in unassigned_rows],
        "ambiguous_file_count": len(ambiguous_rows),
        "ambiguous_file_paths": [row["file_path"] for row in ambiguous_rows],
        "slice_count": len(slice_rows),
        "empty_slice_count": len(empty_slices),
        "empty_slice_ids": empty_slices,
        "missing_task_spec_count": len(missing_task_specs),
        "missing_task_spec_slice_ids": missing_task_specs,
        "weak_task_spec_count": len(weak_task_specs),
        "weak_task_spec_slice_ids": weak_task_specs,
        "integration_touchpoint_count": sum(1 for row in rows if row["integration_touchpoint"]),
        "hunk_split_review_required_count": sum(1 for row in rows if row["hunk_split_review_required"]),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Create child branches/PRs from the mapped slices, reviewing integration touchpoints hunk-by-hunk."
            if ready
            else "Assign unassigned/ambiguous files or repair missing task specs before child PR extraction."
        ),
        **_READ_ONLY_FLAGS,
    }
    return {"summary": summary, "slices": slice_rows, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# PR #38 Split Review Packet",
        "",
        f"- status: `{s['status']}`",
        f"- changed_file_count: `{s['changed_file_count']}`",
        f"- assigned_file_count: `{s['assigned_file_count']}`",
        f"- unassigned_file_count: `{s['unassigned_file_count']}`",
        f"- ambiguous_file_count: `{s['ambiguous_file_count']}`",
        f"- integration_touchpoint_count: `{s['integration_touchpoint_count']}`",
        f"- hunk_split_review_required_count: `{s['hunk_split_review_required_count']}`",
        "",
        "| slice | files | integration touchpoints | task spec | ready |",
        "| --- | --: | --: | --- | --- |",
    ]
    for row in payload["slices"]:
        lines.append(
            "| `{slice_id}` | {files} | {integration} | `{task}` | `{ready}` |".format(
                slice_id=row["slice_id"],
                files=row["changed_file_count"],
                integration=row["integration_touchpoint_count"],
                task=row["task_spec_path"],
                ready=row["slice_ready_for_child_pr_review"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a PR #38 split review packet.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF)
    parser.add_argument("--changed-files", default=None)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_pr38_split_review_packet(
        changed_files=args.changed_files,
        base_ref=args.base_ref,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    return 0 if payload["summary"]["split_review_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
