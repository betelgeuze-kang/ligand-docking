#!/usr/bin/env python3
"""Build the PR #38 split acceptance packet.

This read-only packet joins the split mapping, extraction plan, patch bundle,
and patch-apply preflight receipts into one acceptance surface for human review.
It means the split is locally prepared for explicit branch/commit approval; it
does not mean release readiness, paid-pilot readiness, or scientific claim
promotion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SPLIT_PACKET_JSON = ".betelgeuze/pr38_split_review_packet_current.json"
DEFAULT_EXTRACTION_PLAN_JSON = ".betelgeuze/pr38_child_pr_extraction_plan_current.json"
DEFAULT_PATCH_BUNDLE_JSON = ".betelgeuze/pr38_slice_patch_bundle_current.json"
DEFAULT_APPLY_PREFLIGHT_JSON = ".betelgeuze/pr38_slice_patch_apply_preflight_current.json"
DEFAULT_OUT_JSON = ".betelgeuze/pr38_split_acceptance_packet_current.json"
DEFAULT_OUT_CSV = ".betelgeuze/pr38_split_acceptance_packet_current.csv"
DEFAULT_OUT_MD = ".betelgeuze/pr38_split_acceptance_packet_current.md"

PACKET_TYPE = "pr38_split_acceptance_packet"
SCHEMA_VERSION = "pr38_split_acceptance_packet_v1"

KNOWN_PRODUCT_MODE_BLOCKERS: list[str] = []

PRODUCT_MODE_CLAIM_LOCK_EXPECTATIONS = [
    "paid_pilot_wording_allowed=false",
    "public_benchmark_claim_allowed=false",
    "gpcr_broad_claim_allowed=false",
    "pocketmd_lite_claim_allowed=false",
    "f2g_f2h_placeholder_surface_creation_allowed=false",
    "f2h_continuation_allowed=false",
]

CLAIM_BOUNDARY = (
    "PR #38 split acceptance packet only; it aggregates local split-preparation receipts for reviewer handoff. "
    "It does not create branches, stage, commit, push, post comments, merge PR #38, run external benchmarks, "
    "submit CASP targets, mark product-mode readiness green, promote paid-pilot wording, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "claim_promotion_allowed": False,
    "patches_applied": False,
    "branches_created": False,
    "real_index_mutated": False,
    "worktree_mutated": False,
}


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows_by_slice(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return {}
    return {
        _text(row.get("slice_id")): row
        for row in rows
        if isinstance(row, dict) and _text(row.get("slice_id"))
    }


def _slices_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("slices")
    if not isinstance(rows, list):
        return {}
    return {
        _text(row.get("slice_id")): row
        for row in rows
        if isinstance(row, dict) and _text(row.get("slice_id"))
    }


def _slice_ids(plan_payload: dict[str, Any]) -> list[str]:
    rows = plan_payload.get("rows")
    if not isinstance(rows, list):
        return []
    ordered = sorted(
        (row for row in rows if isinstance(row, dict) and _text(row.get("slice_id"))),
        key=lambda row: int(row.get("sequence") or 0),
    )
    return [_text(row.get("slice_id")) for row in ordered]


def build_pr38_split_acceptance_packet(
    *,
    split_packet_json: str | Path = DEFAULT_SPLIT_PACKET_JSON,
    extraction_plan_json: str | Path = DEFAULT_EXTRACTION_PLAN_JSON,
    patch_bundle_json: str | Path = DEFAULT_PATCH_BUNDLE_JSON,
    apply_preflight_json: str | Path = DEFAULT_APPLY_PREFLIGHT_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    split_payload = _read_json(split_packet_json, root=root_path)
    plan_payload = _read_json(extraction_plan_json, root=root_path)
    bundle_payload = _read_json(patch_bundle_json, root=root_path)
    apply_payload = _read_json(apply_preflight_json, root=root_path)

    split_summary = _summary(split_payload)
    plan_summary = _summary(plan_payload)
    bundle_summary = _summary(bundle_payload)
    apply_summary = _summary(apply_payload)
    split_slices = _slices_by_id(split_payload)
    plan_rows = _rows_by_slice(plan_payload)
    bundle_rows = _rows_by_slice(bundle_payload)
    apply_rows = _rows_by_slice(apply_payload)

    rows: list[dict[str, Any]] = []
    for slice_id in _slice_ids(plan_payload):
        split_row = split_slices.get(slice_id, {})
        plan_row = plan_rows.get(slice_id, {})
        bundle_row = bundle_rows.get(slice_id, {})
        apply_row = apply_rows.get(slice_id, {})
        focused_test_command = _text(plan_row.get("focused_test_command") or split_row.get("focused_test_command"))
        claim_boundary = _text(plan_row.get("claim_boundary") or split_row.get("claim_boundary"))
        blockers: list[str] = []
        if not bool(plan_row.get("child_pr_ready_to_extract")):
            blockers.append("child_pr_not_ready_to_extract")
        if not bool(bundle_row.get("patch_nonempty")):
            blockers.append("patch_empty_or_missing")
        if not bool(apply_row.get("apply_check_ready")):
            blockers.append("patch_apply_check_failed")
        if not focused_test_command:
            blockers.append("focused_test_command_missing")
        if not claim_boundary:
            blockers.append("claim_boundary_missing")
        rows.append(
            {
                "sequence": int(plan_row.get("sequence") or len(rows) + 1),
                "slice_id": slice_id,
                "changed_file_count": int(plan_row.get("changed_file_count") or split_row.get("changed_file_count") or 0),
                "integration_touchpoint_count": int(plan_row.get("integration_touchpoint_count") or 0),
                "patch_path": _text(bundle_row.get("patch_path")),
                "patch_sha256": _text(bundle_row.get("patch_sha256")),
                "apply_check_status": _text(apply_row.get("apply_check_status")),
                "focused_test_command": focused_test_command,
                "claim_boundary": claim_boundary,
                "acceptance_blockers": blockers,
                "slice_acceptance_ready": not blockers,
                **_READ_ONLY_FLAGS,
            }
        )

    row_blockers = [row for row in rows if not row["slice_acceptance_ready"]]
    required_receipts_ready = (
        split_summary.get("split_review_ready") is True
        and plan_summary.get("extraction_plan_ready") is True
        and bundle_summary.get("patch_bundle_ready") is True
        and apply_summary.get("patch_apply_preflight_ready") is True
    )
    count_alignment_ready = (
        int(split_summary.get("changed_file_count") or 0)
        == int(plan_summary.get("total_changed_file_count") or 0)
        == int(bundle_summary.get("bundled_changed_file_count") or 0)
        and int(apply_summary.get("slice_patch_count") or 0) == len(rows)
    )
    ready = bool(required_receipts_ready and count_alignment_ready and rows and not row_blockers)
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "pr38_split_acceptance_packet_ready" if ready else "blocked_pr38_split_acceptance_packet",
        "split_acceptance_ready": ready,
        "split_packet_status": _text(split_summary.get("status")) or "missing",
        "extraction_plan_status": _text(plan_summary.get("status")) or "missing",
        "patch_bundle_status": _text(bundle_summary.get("status")) or "missing",
        "apply_preflight_status": _text(apply_summary.get("status")) or "missing",
        "required_receipts_ready": required_receipts_ready,
        "count_alignment_ready": count_alignment_ready,
        "changed_file_count": int(split_summary.get("changed_file_count") or 0),
        "child_pr_count": len(rows),
        "ready_child_pr_count": sum(1 for row in rows if row["slice_acceptance_ready"]),
        "blocked_child_pr_count": len(row_blockers),
        "blocked_slice_ids": [row["slice_id"] for row in row_blockers],
        "hunk_split_review_required_count": int(split_summary.get("hunk_split_review_required_count") or 0),
        "source_of_truth_registry_reconciles_last": bool(plan_summary.get("source_of_truth_registry_reconciles_last") is True),
        "product_mode_expected_fail_closed_blockers": KNOWN_PRODUCT_MODE_BLOCKERS,
        "product_mode_expected_result": "pass_product_smoke_claim_boundaries_locked",
        "product_mode_claim_boundary_expected_locks": PRODUCT_MODE_CLAIM_LOCK_EXPECTATIONS,
        "paid_pilot_wording_allowed": False,
        "branch_commit_work_allowed_by_this_packet": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Request explicit human approval for branch/commit work, then apply checked patches in order and run "
            "each row's focused tests plus ai-verify before review."
            if ready
            else "Repair blocked slice rows or missing prerequisite receipts before branch extraction."
        ),
        **_READ_ONLY_FLAGS,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# PR #38 Split Acceptance Packet",
        "",
        f"- status: `{s['status']}`",
        f"- split_packet_status: `{s['split_packet_status']}`",
        f"- extraction_plan_status: `{s['extraction_plan_status']}`",
        f"- patch_bundle_status: `{s['patch_bundle_status']}`",
        f"- apply_preflight_status: `{s['apply_preflight_status']}`",
        f"- changed_file_count: `{s['changed_file_count']}`",
        f"- child_pr_count: `{s['child_pr_count']}`",
        f"- blocked_child_pr_count: `{s['blocked_child_pr_count']}`",
        f"- paid_pilot_wording_allowed: `{s['paid_pilot_wording_allowed']}`",
        "",
        "| seq | slice | files | apply check | ready |",
        "| --: | --- | --: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| {seq} | `{slice_id}` | {files} | `{apply_status}` | `{ready}` |".format(
                seq=row["sequence"],
                slice_id=row["slice_id"],
                files=row["changed_file_count"],
                apply_status=row["apply_check_status"],
                ready=row["slice_acceptance_ready"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the PR #38 split acceptance packet.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--split-packet-json", default=DEFAULT_SPLIT_PACKET_JSON)
    parser.add_argument("--extraction-plan-json", default=DEFAULT_EXTRACTION_PLAN_JSON)
    parser.add_argument("--patch-bundle-json", default=DEFAULT_PATCH_BUNDLE_JSON)
    parser.add_argument("--apply-preflight-json", default=DEFAULT_APPLY_PREFLIGHT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_pr38_split_acceptance_packet(
        split_packet_json=args.split_packet_json,
        extraction_plan_json=args.extraction_plan_json,
        patch_bundle_json=args.patch_bundle_json,
        apply_preflight_json=args.apply_preflight_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    return 0 if payload["summary"]["split_acceptance_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
