#!/usr/bin/env python3
"""Build the PR #38 child-PR verification matrix.

This read-only matrix turns the split acceptance packet into per-child-PR
verification requirements: focused tests, ai-verify, product-mode expectations,
hunk review, and claim-boundary review. It does not run tests, create branches,
stage, commit, push, post comments, merge PR #38, or promote claims.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_pr38_split_acceptance_packet import KNOWN_PRODUCT_MODE_BLOCKERS

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ACCEPTANCE_PACKET_JSON = ".betelgeuze/pr38_split_acceptance_packet_current.json"
DEFAULT_OUT_JSON = ".betelgeuze/pr38_child_pr_verification_matrix_current.json"
DEFAULT_OUT_CSV = ".betelgeuze/pr38_child_pr_verification_matrix_current.csv"
DEFAULT_OUT_MD = ".betelgeuze/pr38_child_pr_verification_matrix_current.md"

PACKET_TYPE = "pr38_child_pr_verification_matrix"
SCHEMA_VERSION = "pr38_child_pr_verification_matrix_v1"

AI_VERIFY_COMMAND = "./scripts/ai-verify.sh"
PRODUCT_VERIFY_COMMAND = "AI_VERIFY_MODE=product ./scripts/ai-verify.sh"

PRODUCT_MODE_REQUIRED_SLICE_IDS = {
    "public_benchmark_phase2",
    "gpcr_hard_decoy_closure",
    "pocketmd_lite_recovery",
    "source_of_truth_refresh",
}

CLAIM_BOUNDARY = (
    "PR #38 child-PR verification matrix only; it records required local verification and claim-boundary checks "
    "for already-prepared split slices. It does not create branches, stage, commit, push, post comments, merge "
    "PR #38, mark product-mode readiness green, promote paid-pilot wording, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "claim_promotion_allowed": False,
    "patches_applied": False,
    "branches_created": False,
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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def build_pr38_child_pr_verification_matrix(
    *,
    acceptance_packet_json: str | Path = DEFAULT_ACCEPTANCE_PACKET_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    acceptance_payload = _read_json(acceptance_packet_json, root=root_path)
    acceptance_summary = _summary(acceptance_payload)
    rows: list[dict[str, Any]] = []

    for row_in in _rows(acceptance_payload):
        slice_id = _text(row_in.get("slice_id"))
        focused_test_command = _text(row_in.get("focused_test_command"))
        claim_boundary = _text(row_in.get("claim_boundary"))
        product_mode_required = slice_id in PRODUCT_MODE_REQUIRED_SLICE_IDS
        blockers: list[str] = []
        if row_in.get("slice_acceptance_ready") is not True:
            blockers.append("slice_acceptance_not_ready")
        if not focused_test_command:
            blockers.append("focused_test_command_missing")
        if not claim_boundary:
            blockers.append("claim_boundary_missing")
        rows.append(
            {
                "sequence": int(row_in.get("sequence") or len(rows) + 1),
                "slice_id": slice_id,
                "changed_file_count": int(row_in.get("changed_file_count") or 0),
                "integration_touchpoint_count": int(row_in.get("integration_touchpoint_count") or 0),
                "hunk_split_review_required": int(row_in.get("integration_touchpoint_count") or 0) > 0,
                "focused_test_required": True,
                "focused_test_command": focused_test_command,
                "ai_verify_required": True,
                "ai_verify_command": AI_VERIFY_COMMAND,
                "product_mode_required": product_mode_required,
                "product_mode_command": PRODUCT_VERIFY_COMMAND if product_mode_required else "",
                "product_mode_expected_result": (
                    "fail_closed_known_readiness_blockers" if product_mode_required else "not_required_for_this_slice"
                ),
                "product_mode_expected_blockers": KNOWN_PRODUCT_MODE_BLOCKERS if product_mode_required else [],
                "claim_boundary_review_required": True,
                "claim_boundary": claim_boundary,
                "paid_pilot_wording_allowed": False,
                "branch_commit_work_allowed_by_this_matrix": False,
                "verification_blockers": blockers,
                "child_pr_verification_matrix_ready": not blockers,
                **_READ_ONLY_FLAGS,
            }
        )

    blocked_rows = [row for row in rows if not row["child_pr_verification_matrix_ready"]]
    ready = acceptance_summary.get("split_acceptance_ready") is True and bool(rows) and not blocked_rows
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "pr38_child_pr_verification_matrix_ready" if ready else "blocked_pr38_child_pr_verification_matrix",
        "verification_matrix_ready": ready,
        "acceptance_packet_status": _text(acceptance_summary.get("status")) or "missing",
        "split_acceptance_ready": bool(acceptance_summary.get("split_acceptance_ready") is True),
        "child_pr_count": len(rows),
        "ready_child_pr_count": sum(1 for row in rows if row["child_pr_verification_matrix_ready"]),
        "blocked_child_pr_count": len(blocked_rows),
        "blocked_slice_ids": [row["slice_id"] for row in blocked_rows],
        "focused_test_required_count": len(rows),
        "ai_verify_required_count": len(rows),
        "product_mode_required_count": sum(1 for row in rows if row["product_mode_required"]),
        "hunk_split_review_required_count": sum(1 for row in rows if row["hunk_split_review_required"]),
        "claim_boundary_review_required_count": len(rows),
        "product_mode_expected_fail_closed_blockers": KNOWN_PRODUCT_MODE_BLOCKERS,
        "paid_pilot_wording_allowed": False,
        "branch_commit_work_allowed_by_this_matrix": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "After explicit human approval for branch/commit work, run each row's focused test command and "
            "ai-verify before child PR review; product-mode rows should remain fail-closed on known blockers."
            if ready
            else "Repair blocked verification rows before branch extraction or review."
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
        "# PR #38 Child PR Verification Matrix",
        "",
        f"- status: `{s['status']}`",
        f"- acceptance_packet_status: `{s['acceptance_packet_status']}`",
        f"- child_pr_count: `{s['child_pr_count']}`",
        f"- focused_test_required_count: `{s['focused_test_required_count']}`",
        f"- ai_verify_required_count: `{s['ai_verify_required_count']}`",
        f"- product_mode_required_count: `{s['product_mode_required_count']}`",
        f"- paid_pilot_wording_allowed: `{s['paid_pilot_wording_allowed']}`",
        "",
        "| seq | slice | focused test | ai-verify | product-mode | claim review |",
        "| --: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| {seq} | `{slice_id}` | `{focused}` | `{ai}` | `{product}` | `{claim}` |".format(
                seq=row["sequence"],
                slice_id=row["slice_id"],
                focused=row["focused_test_required"],
                ai=row["ai_verify_required"],
                product=row["product_mode_required"],
                claim=row["claim_boundary_review_required"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the PR #38 child-PR verification matrix.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--acceptance-packet-json", default=DEFAULT_ACCEPTANCE_PACKET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_pr38_child_pr_verification_matrix(
        acceptance_packet_json=args.acceptance_packet_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    return 0 if payload["summary"]["verification_matrix_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
