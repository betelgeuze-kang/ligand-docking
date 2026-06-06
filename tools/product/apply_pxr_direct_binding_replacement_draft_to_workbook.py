#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_DRAFT_JSON = RUNS / "pxr_direct_binding_replacement_apply_draft_current.json"
DEFAULT_DRAFT_CSV = RUNS / "pxr_direct_binding_replacement_apply_draft_current.csv"
DEFAULT_WORKBOOK_JSON = RUNS / "pxr_packet_replacement_workbook_current.json"
DEFAULT_WORKBOOK_CSV = RUNS / "pxr_packet_replacement_workbook_current.csv"
DEFAULT_WORKBOOK_MD = RUNS / "pxr_packet_replacement_workbook_current.md"
DEFAULT_OUT_JSON = RUNS / "pxr_direct_binding_replacement_authoritative_workbook_apply_current.json"
DEFAULT_OUT_CSV = RUNS / "pxr_direct_binding_replacement_authoritative_workbook_apply_current.csv"
DEFAULT_OUT_MD = RUNS / "pxr_direct_binding_replacement_authoritative_workbook_apply_current.md"

CLAIM_BOUNDARY = (
    "PXR direct-binding replacement workbook apply receipt only; copies a locally validated PXR direct-binding "
    "draft into the authoritative replacement workbook artifacts. It does not run docking, widen product scope, "
    "upload, submit, email, delete files, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path_like: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    path = _resolve(path_like)
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_csv(path_like: str | Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows_ready(rows: list[dict[str, str]]) -> bool:
    return bool(rows) and all(
        _text(row.get("row_ready_for_apply")).lower() == "yes"
        and not _text(row.get("required_missing_fields"))
        for row in rows
    )


def build_payload(
    *,
    draft_summary: dict[str, Any],
    draft_rows: list[dict[str, str]],
    workbook_csv_path: str = DEFAULT_WORKBOOK_CSV.as_posix(),
    workbook_json_path: str = DEFAULT_WORKBOOK_JSON.as_posix(),
) -> dict[str, Any]:
    overlay_rows = [
        row
        for row in draft_rows
        if _text(row.get("replacement_source")).startswith("chembl_direct_binding::")
    ]
    nonbinder_overlay_rows = [
        row for row in overlay_rows if _text(row.get("replacement_is_binder")) == "0"
    ]
    binder_overlay_rows = [
        row for row in overlay_rows if _text(row.get("replacement_is_binder")) == "1"
    ]
    ready = (
        draft_summary.get("draft_ready") is True
        and _rows_ready(draft_rows)
        and int(draft_summary.get("blocked_row_count_after_draft") or 0) == 0
        and len(overlay_rows) >= 6
        and len(nonbinder_overlay_rows) >= 5
        and len(binder_overlay_rows) >= 1
    )
    summary = {
        "packet_type": "pxr_direct_binding_replacement_authoritative_workbook_apply",
        "status": (
            "pxr_direct_binding_replacement_authoritative_workbook_applied"
            if ready
            else "blocked_pxr_direct_binding_replacement_authoritative_workbook_apply"
        ),
        "workbook_apply_ready": ready,
        "source_draft_ready": draft_summary.get("draft_ready") is True,
        "source_draft_blocked_row_count_after_draft": int(
            draft_summary.get("blocked_row_count_after_draft") or 0
        ),
        "workbook_row_count": len(draft_rows),
        "ready_row_count": sum(
            1
            for row in draft_rows
            if _text(row.get("row_ready_for_apply")).lower() == "yes"
            and not _text(row.get("required_missing_fields"))
        ),
        "direct_binding_overlay_row_count": len(overlay_rows),
        "nonbinder_weak_control_overlay_row_count": len(nonbinder_overlay_rows),
        "binder_direct_overlay_row_count": len(binder_overlay_rows),
        "workbook_csv_artifact": workbook_csv_path,
        "workbook_json_artifact": workbook_json_path,
        "authoritative_replacement_fields_touched": ready,
        "scope_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Rerun PXR fill-readiness, blocked-row promotion, reconciliation, exact-review, source-modality, "
            "curated freeze/materialization, and product scope gates."
            if ready
            else "Fix the direct-binding draft before copying it into the authoritative PXR replacement workbook."
        ),
    }
    return {"summary": summary, "workbook_rows": draft_rows, "applied_rows": overlay_rows}


def _write_workbook_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    rows = payload["workbook_rows"]
    s = payload["summary"]
    lines = [
        "# PXR Packet Replacement Workbook",
        "",
        f"- workbook_row_count: `{s['workbook_row_count']}`",
        f"- ready_row_count: `{s['ready_row_count']}`",
        f"- direct_binding_overlay_row_count: `{s['direct_binding_overlay_row_count']}`",
        f"- nonbinder_weak_control_overlay_row_count: `{s['nonbinder_weak_control_overlay_row_count']}`",
        f"- binder_direct_overlay_row_count: `{s['binder_direct_overlay_row_count']}`",
        "",
        "## Workbook",
        "",
        "| packet_step | ligand | binder | role | kcal | source | ready |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row.get('packet_step', '')}` | `{row.get('replacement_ligand_id', '')}` | "
            f"`{row.get('replacement_is_binder', '')}` | `{row.get('replacement_role', '')}` | "
            f"`{row.get('replacement_reference_binding_kcal_mol', '')}` | "
            f"`{row.get('replacement_source', '')}` | `{row.get('row_ready_for_apply', '')}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_receipt_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# PXR Direct-Binding Replacement Workbook Apply Receipt",
        "",
        f"- status: `{s['status']}`",
        f"- workbook_apply_ready: `{s['workbook_apply_ready']}`",
        f"- workbook_row_count: `{s['workbook_row_count']}`",
        f"- ready_row_count: `{s['ready_row_count']}`",
        f"- direct_binding_overlay_row_count: `{s['direct_binding_overlay_row_count']}`",
        f"- nonbinder_weak_control_overlay_row_count: `{s['nonbinder_weak_control_overlay_row_count']}`",
        f"- binder_direct_overlay_row_count: `{s['binder_direct_overlay_row_count']}`",
        f"- authoritative_replacement_fields_touched: `{s['authoritative_replacement_fields_touched']}`",
        "",
        "## Next Step",
        "",
        s["next_required_step"],
        "",
        "## Claim Boundary",
        "",
        s["claim_boundary"],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply the validated PXR direct-binding draft to the workbook.")
    parser.add_argument("--draft-json", default=DEFAULT_DRAFT_JSON.as_posix())
    parser.add_argument("--draft-csv", default=DEFAULT_DRAFT_CSV.as_posix())
    parser.add_argument("--workbook-json", default=DEFAULT_WORKBOOK_JSON.as_posix())
    parser.add_argument("--workbook-csv", default=DEFAULT_WORKBOOK_CSV.as_posix())
    parser.add_argument("--workbook-md", default=DEFAULT_WORKBOOK_MD.as_posix())
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON.as_posix())
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV.as_posix())
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD.as_posix())
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    draft_packet = _read_json(args.draft_json)
    fieldnames, draft_rows = _read_csv(args.draft_csv)
    payload = build_payload(
        draft_summary=_summary(draft_packet),
        draft_rows=draft_rows,
        workbook_csv_path=args.workbook_csv,
        workbook_json_path=args.workbook_json,
    )
    if not payload["summary"]["workbook_apply_ready"]:
        _write_json(args.out_json, payload)
        write_csv_rows(_resolve(args.out_csv), payload["applied_rows"])
        _write_receipt_md(args.out_md, payload)
        raise SystemExit("PXR direct-binding draft is not safe to apply to workbook")
    _write_csv(args.workbook_csv, fieldnames, payload["workbook_rows"])
    _write_json(args.workbook_json, {"summary": payload["summary"], "workbook_rows": payload["workbook_rows"]})
    _write_workbook_md(args.workbook_md, payload)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["applied_rows"])
    _write_receipt_md(args.out_md, payload)


if __name__ == "__main__":
    main()
