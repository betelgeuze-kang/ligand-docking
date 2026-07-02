#!/usr/bin/env python3
"""Build a read-only child-PR extraction plan for PR #38.

This consumes the PR #38 split review packet and turns it into an ordered
merge/extraction plan. It is intentionally non-mutating: no branch creation,
staging, commits, pushes, PR comments, external benchmark jobs, or claim
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
DEFAULT_OUT_JSON = ".betelgeuze/pr38_child_pr_extraction_plan_current.json"
DEFAULT_OUT_CSV = ".betelgeuze/pr38_child_pr_extraction_plan_current.csv"
DEFAULT_OUT_MD = ".betelgeuze/pr38_child_pr_extraction_plan_current.md"

PACKET_TYPE = "pr38_child_pr_extraction_plan"
SCHEMA_VERSION = "pr38_child_pr_extraction_plan_v1"

CLAIM_BOUNDARY = (
    "PR #38 child-PR extraction plan only; it orders local review slices and names verification gates. It does "
    "not create branches, stage, commit, push, post comments, merge PR #38, run external benchmarks, submit CASP "
    "targets, promote paid-pilot wording, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "claim_promotion_allowed": False,
}

_ORDERED_SLICES: list[dict[str, Any]] = [
    {
        "sequence": 1,
        "slice_id": "f2g_f2h_preflight",
        "draft_branch_name": "codex/pr38-f2g-f2h-preflight",
        "draft_pr_title": "[codex] Split PR38 F2g/F2h preflight work order",
        "depends_on_slice_ids": [],
        "merge_reason": "Small non-promoting work-order slice with no integration touchpoints.",
        "special_review_note": "Verify it reports missing authoritative inputs without placeholder solver surfaces.",
    },
    {
        "sequence": 2,
        "slice_id": "public_benchmark_phase2",
        "draft_branch_name": "codex/pr38-public-benchmark-phase2",
        "draft_pr_title": "[codex] Split PR38 public benchmark Phase 2 audit surfaces",
        "depends_on_slice_ids": [],
        "merge_reason": "Benchmark receipt-prep surfaces are mostly isolated and should remain claim-locked.",
        "special_review_note": "Do not attach or imply real external receipts; keep external beta language locked.",
    },
    {
        "sequence": 3,
        "slice_id": "gpcr_hard_decoy_closure",
        "draft_branch_name": "codex/pr38-gpcr-hard-decoy-closure-tools",
        "draft_pr_title": "[codex] Split PR38 GPCR hard-decoy closure tools",
        "depends_on_slice_ids": [],
        "merge_reason": "Large but domain-contained diagnostic/replay surface with no API integration touchpoint.",
        "special_review_note": "Keep broad GPCR/router claims locked until registered numeric thresholds and ledger approval.",
    },
    {
        "sequence": 4,
        "slice_id": "pocketmd_lite_recovery",
        "draft_branch_name": "codex/pr38-pocketmd-lite-recovery",
        "draft_pr_title": "[codex] Split PR38 PocketMD Lite recovery surfaces",
        "depends_on_slice_ids": [],
        "merge_reason": "PocketMD Lite is large and touches API/import integration, so review after isolated science surfaces.",
        "special_review_note": "Review API/import hunks manually; recovered frames are collector inputs, not claim-grade metrics.",
    },
    {
        "sequence": 5,
        "slice_id": "source_of_truth_refresh",
        "draft_branch_name": "codex/pr38-source-of-truth-refresh",
        "draft_pr_title": "[codex] Split PR38 source-of-truth refresh path",
        "depends_on_slice_ids": [
            "f2g_f2h_preflight",
            "public_benchmark_phase2",
            "gpcr_hard_decoy_closure",
            "pocketmd_lite_recovery",
        ],
        "merge_reason": "Final release/source-of-truth wiring should land after dependent tools exist on main.",
        "special_review_note": (
            "A gap-scan-only hunk may be peeled earlier, but release refresh registry hunks should reconcile last."
        ),
    },
]


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


def _by_slice(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("slice_id")): row for row in rows if _text(row.get("slice_id"))}


def _slice_file_rows(split_payload: dict[str, Any], slice_id: str) -> list[dict[str, Any]]:
    rows = split_payload.get("rows")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and _text(row.get("slice_id")) == slice_id]


def build_pr38_child_pr_extraction_plan(
    *,
    split_packet_json: str | Path = DEFAULT_SPLIT_PACKET_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    split_path = _resolve(split_packet_json, root=root_path)
    split_payload = _read_json(split_path, root=root_path)
    split_summary = split_payload.get("summary") if isinstance(split_payload.get("summary"), dict) else {}
    split_slices = _by_slice(split_payload.get("slices") if isinstance(split_payload.get("slices"), list) else [])
    split_ready = bool(split_summary.get("split_review_ready") is True)
    rows: list[dict[str, Any]] = []

    for spec in _ORDERED_SLICES:
        slice_id = spec["slice_id"]
        slice_summary = split_slices.get(slice_id, {})
        file_rows = _slice_file_rows(split_payload, slice_id)
        integration_paths = sorted(
            _text(row.get("file_path")) for row in file_rows if bool(row.get("integration_touchpoint"))
        )
        slice_ready = bool(slice_summary.get("slice_ready_for_child_pr_review") is True)
        depends_on = list(spec["depends_on_slice_ids"])
        rows.append(
            {
                "sequence": spec["sequence"],
                "slice_id": slice_id,
                "draft_branch_name": spec["draft_branch_name"],
                "draft_pr_title": spec["draft_pr_title"],
                "depends_on_slice_ids": depends_on,
                "depends_on_slice_count": len(depends_on),
                "changed_file_count": int(slice_summary.get("changed_file_count") or 0),
                "integration_touchpoint_count": len(integration_paths),
                "integration_touchpoint_paths": integration_paths,
                "hunk_split_review_required": bool(integration_paths),
                "task_spec_path": _text(slice_summary.get("task_spec_path")),
                "focused_test_command": _text(slice_summary.get("focused_test_command")),
                "claim_boundary": _text(slice_summary.get("claim_boundary")),
                "merge_reason": spec["merge_reason"],
                "special_review_note": spec["special_review_note"],
                "child_pr_ready_to_extract": split_ready and slice_ready,
                **_READ_ONLY_FLAGS,
            }
        )

    missing_slice_ids = [
        spec["slice_id"]
        for spec in _ORDERED_SLICES
        if spec["slice_id"] not in split_slices
    ]
    not_ready_slice_ids = [row["slice_id"] for row in rows if not row["child_pr_ready_to_extract"]]
    ready = split_ready and not missing_slice_ids and not not_ready_slice_ids
    source_row = next((row for row in rows if row["slice_id"] == "source_of_truth_refresh"), {})
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "pr38_child_pr_extraction_plan_ready" if ready else "blocked_pr38_child_pr_extraction_plan",
        "extraction_plan_ready": ready,
        "split_packet_json": str(split_path),
        "split_packet_status": _text(split_summary.get("status")) or "missing",
        "split_review_ready": split_ready,
        "child_pr_count": len(rows),
        "ready_child_pr_count": sum(1 for row in rows if row["child_pr_ready_to_extract"]),
        "not_ready_child_pr_count": len(not_ready_slice_ids),
        "not_ready_slice_ids": not_ready_slice_ids,
        "missing_slice_count": len(missing_slice_ids),
        "missing_slice_ids": missing_slice_ids,
        "total_changed_file_count": sum(int(row["changed_file_count"]) for row in rows),
        "integration_touchpoint_count": sum(int(row["integration_touchpoint_count"]) for row in rows),
        "hunk_split_review_required_count": sum(int(row["integration_touchpoint_count"]) for row in rows),
        "hunk_split_review_required_child_pr_count": sum(1 for row in rows if row["hunk_split_review_required"]),
        "source_of_truth_sequence": int(source_row.get("sequence") or 0),
        "source_of_truth_depends_on_slice_count": int(source_row.get("depends_on_slice_count") or 0),
        "source_of_truth_registry_reconciles_last": int(source_row.get("sequence") or 0) == len(rows)
        and int(source_row.get("depends_on_slice_count") or 0) == 4,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "After explicit human approval to create branches/commits, extract child PRs in sequence and run each "
            "row's focused tests plus ai-verify before review."
            if ready
            else "Repair the split review packet or missing slice readiness before attempting extraction."
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
        "# PR #38 Child PR Extraction Plan",
        "",
        f"- status: `{s['status']}`",
        f"- split_packet_status: `{s['split_packet_status']}`",
        f"- child_pr_count: `{s['child_pr_count']}`",
        f"- total_changed_file_count: `{s['total_changed_file_count']}`",
        f"- integration_touchpoint_count: `{s['integration_touchpoint_count']}`",
        f"- source_of_truth_registry_reconciles_last: `{s['source_of_truth_registry_reconciles_last']}`",
        "",
        "| seq | slice | files | depends on | integration touchpoints | branch |",
        "| --: | --- | --: | --- | --: | --- |",
    ]
    for row in payload["rows"]:
        depends_on = ";".join(row["depends_on_slice_ids"])
        lines.append(
            "| {seq} | `{slice_id}` | {files} | `{depends}` | {touchpoints} | `{branch}` |".format(
                seq=row["sequence"],
                slice_id=row["slice_id"],
                files=row["changed_file_count"],
                depends=depends_on,
                touchpoints=row["integration_touchpoint_count"],
                branch=row["draft_branch_name"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the PR #38 child-PR extraction plan.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--split-packet-json", default=DEFAULT_SPLIT_PACKET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_pr38_child_pr_extraction_plan(
        split_packet_json=args.split_packet_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    return 0 if payload["summary"]["extraction_plan_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
