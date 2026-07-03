#!/usr/bin/env python3
"""Build a PocketMD Lite canonical report review packet.

Read-only: this compares the blocked canonical PocketMD Lite report with the
claim-grade metric fill preview report. It prepares operator review rows for a
future, explicitly approved canonical candidate CSV update, but never mutates
the canonical CSV or promotes PocketMD Lite claims.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CANONICAL_REPORT_JSON = "runs/pocketmd_lite_report_current.json"
DEFAULT_PREVIEW_REPORT_JSON = "runs/pocketmd_lite_candidate_metric_fill_preview_report_current.json"
DEFAULT_CANDIDATE_FILL_PREVIEW_JSON = "runs/pocketmd_lite_candidate_metric_fill_preview_current.json"
DEFAULT_METRIC_SOURCE_AUDIT_JSON = "runs/pocketmd_lite_claim_grade_metric_source_audit_current.json"
DEFAULT_CANONICAL_CANDIDATE_CSV = "config/pocketmd_lite_candidates_current.csv"
DEFAULT_PREVIEW_CANDIDATE_CSV = "runs/pocketmd_lite_candidate_metric_fill_preview_current.candidates.csv"
DEFAULT_OUT_JSON = "runs/pocketmd_lite_canonical_report_review_packet_current.json"
DEFAULT_OUT_MD = "runs/pocketmd_lite_canonical_report_review_packet_current.md"
DEFAULT_OUT_CSV = "runs/pocketmd_lite_canonical_report_review_packet_current.csv"

PACKET_TYPE = "pocketmd_lite_canonical_report_review_packet"
SCHEMA_VERSION = "pocketmd_lite_canonical_report_review_packet_v1"
APPROVAL_TOKEN_REQUIRED = "APPROVE_POCKETMD_LITE_CANONICAL_METRIC_FILL"

CLAIM_BOUNDARY = (
    "PocketMD Lite canonical report review packet only. It compares the canonical report with the "
    "claim-grade metric fill preview report and prepares operator review rows for a separate, explicitly "
    "approved canonical candidate CSV update. It does not write the canonical candidate CSV, does not run "
    "local-min or micro-MD, does not promote claims, and does not mutate external state."
)

READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "refinement_execution_enabled": False,
    "candidate_csv_update_allowed": False,
    "canonical_candidate_csv_mutated": False,
    "claim_promotion_allowed": False,
}

CSV_COLUMNS = [
    "entry_id",
    "canonical_band",
    "preview_band",
    "canonical_claim_safe",
    "preview_claim_safe",
    "canonical_missing_metric_names",
    "preview_missing_metric_names",
    "metric_fill_status",
    "metric_source_npz",
    "canonical_local_min_ligand_rmsd_a",
    "preview_local_min_ligand_rmsd_a",
    "canonical_hbond_persistence",
    "preview_hbond_persistence",
    "canonical_contact_persistence",
    "preview_contact_persistence",
    "canonical_initial_clash_count",
    "preview_initial_clash_count",
    "canonical_clash_count",
    "preview_clash_count",
    "canonical_clash_relief_count",
    "preview_clash_relief_count",
    "canonical_update_candidate",
    "review_ready",
    "review_action",
    "blockers",
    "candidate_csv_update_allowed",
    "canonical_candidate_csv_mutated",
    "claim_promotion_allowed",
    "execution_enabled",
    "external_state_mutated",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return str(path)


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv_rows(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _preview_candidate_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("preview_candidate_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "on"}


def _num(value: Any) -> float | None:
    try:
        if value is None or _text(value) == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.8g}"
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def _list_field(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if _text(item)]
    text = _text(value)
    if not text:
        return []
    separator = ";" if ";" in text else ","
    return [item.strip() for item in text.split(separator) if item.strip()]


def _entry_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("entry_id")): row for row in rows if _text(row.get("entry_id"))}


def _selected_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [row for row in rows if _bool(row.get("selected_for_refine"))]
    return selected if selected else rows


def _report_ready(summary: dict[str, Any]) -> bool:
    return bool(
        summary.get("status") == "pocketmd_lite_report_ready"
        and summary.get("pocketmd_lite_claim_safe") is True
        and summary.get("top_k_refinement_evidence_ready") is True
        and int(summary.get("refinement_blocker_count", 0) or 0) == 0
    )


def _candidate_fill_preview_ready(summary: dict[str, Any]) -> bool:
    return bool(
        summary.get("status") == "pocketmd_lite_candidate_metric_fill_preview_ready"
        and summary.get("canonical_candidate_csv_mutated") is False
        and summary.get("candidate_csv_update_allowed") is False
        and int(summary.get("blocked_fill_row_count", 0) or 0) == 0
        and int(summary.get("fill_ready_row_count", 0) or 0) > 0
    )


def _metric_source_ready(summary: dict[str, Any]) -> bool:
    candidate_count = int(summary.get("candidate_count", 0) or 0)
    exact_ready_count = int(summary.get("exact_metric_source_ready_count", 0) or 0)
    missing_exact_count = int(summary.get("missing_exact_metric_source_count", 0) or 0)
    return bool(
        summary.get("status") == "pocketmd_lite_claim_grade_metric_source_audit_ready"
        and candidate_count > 0
        and exact_ready_count >= candidate_count
        and missing_exact_count == 0
        and summary.get("candidate_csv_update_allowed") is False
    )


def _metric_fill_status(preview_candidate_row: dict[str, Any], fill_row: dict[str, Any]) -> str:
    return _text(
        preview_candidate_row.get("pocketmd_lite_metric_fill_status")
        or fill_row.get("pocketmd_lite_metric_fill_status")
    )


def _metric_source_npz(preview_candidate_row: dict[str, Any], fill_row: dict[str, Any]) -> str:
    return _text(
        preview_candidate_row.get("pocketmd_lite_metric_fill_source_npz")
        or fill_row.get("pocketmd_lite_metric_fill_source_npz")
    )


def _review_row(
    *,
    preview_row: dict[str, Any],
    canonical_row: dict[str, Any],
    preview_candidate_row: dict[str, Any],
    fill_row: dict[str, Any],
    canonical_report_ready: bool,
) -> dict[str, Any]:
    entry_id = _text(preview_row.get("entry_id") or canonical_row.get("entry_id"))
    canonical_missing = _list_field(canonical_row.get("missing_evidence_fields"))
    preview_missing = _list_field(preview_row.get("missing_evidence_fields"))
    fill_status = _metric_fill_status(preview_candidate_row, fill_row)
    source_npz = _metric_source_npz(preview_candidate_row, fill_row)
    canonical_claim_safe = _bool(canonical_row.get("claim_safe"))
    preview_claim_safe = _bool(preview_row.get("claim_safe"))
    preview_green = _text(preview_row.get("band")) == "green"
    canonical_update_candidate = bool(
        not canonical_report_ready
        and preview_claim_safe
        and (canonical_missing or not canonical_claim_safe or _text(canonical_row.get("band")) != _text(preview_row.get("band")))
    )

    blockers: list[str] = []
    if not canonical_row:
        blockers.append("canonical_report_row_missing")
    if not preview_green:
        blockers.append("preview_band_not_green")
    if not preview_claim_safe:
        blockers.append("preview_claim_safe_false")
    if preview_missing:
        blockers.append("preview_missing_metrics:" + ",".join(preview_missing))
    if fill_status != "filled_from_claim_grade_probe":
        blockers.append("metric_fill_status_not_claim_grade_probe")
    if not source_npz:
        blockers.append("metric_source_npz_missing")

    review_ready = bool(canonical_update_candidate and not blockers)
    if canonical_report_ready:
        review_action = "no_action_required_canonical_report_already_ready"
    elif review_ready:
        review_action = "operator_review_preview_metrics_before_canonical_candidate_csv_update"
    else:
        review_action = "restore_claim_grade_preview_evidence_before_canonical_review"

    return {
        "entry_id": entry_id,
        "canonical_band": _text(canonical_row.get("band")),
        "preview_band": _text(preview_row.get("band")),
        "canonical_claim_safe": canonical_claim_safe,
        "preview_claim_safe": preview_claim_safe,
        "canonical_missing_metric_names": canonical_missing,
        "preview_missing_metric_names": preview_missing,
        "metric_fill_status": fill_status,
        "metric_source_npz": source_npz,
        "canonical_local_min_ligand_rmsd_a": _num(canonical_row.get("local_min_ligand_rmsd_a")),
        "preview_local_min_ligand_rmsd_a": _num(preview_row.get("local_min_ligand_rmsd_a")),
        "canonical_hbond_persistence": _num(canonical_row.get("hbond_persistence")),
        "preview_hbond_persistence": _num(preview_row.get("hbond_persistence")),
        "canonical_contact_persistence": _num(canonical_row.get("contact_persistence")),
        "preview_contact_persistence": _num(preview_row.get("contact_persistence")),
        "canonical_initial_clash_count": _num(canonical_row.get("initial_clash_count")),
        "preview_initial_clash_count": _num(preview_row.get("initial_clash_count")),
        "canonical_clash_count": _num(canonical_row.get("clash_count")),
        "preview_clash_count": _num(preview_row.get("clash_count")),
        "canonical_clash_relief_count": _num(canonical_row.get("clash_relief_count")),
        "preview_clash_relief_count": _num(preview_row.get("clash_relief_count")),
        "canonical_update_candidate": canonical_update_candidate,
        "review_ready": review_ready,
        "review_action": review_action,
        "blockers": blockers,
        **READ_ONLY_FLAGS,
    }


def build_pocketmd_lite_canonical_report_review_packet(
    *,
    canonical_report_json: str | Path = DEFAULT_CANONICAL_REPORT_JSON,
    preview_report_json: str | Path = DEFAULT_PREVIEW_REPORT_JSON,
    candidate_fill_preview_json: str | Path = DEFAULT_CANDIDATE_FILL_PREVIEW_JSON,
    metric_source_audit_json: str | Path = DEFAULT_METRIC_SOURCE_AUDIT_JSON,
    canonical_candidate_csv: str | Path = DEFAULT_CANONICAL_CANDIDATE_CSV,
    preview_candidate_csv: str | Path = DEFAULT_PREVIEW_CANDIDATE_CSV,
) -> dict[str, Any]:
    canonical_report = _read_json(canonical_report_json)
    preview_report = _read_json(preview_report_json)
    fill_preview = _read_json(candidate_fill_preview_json)
    source_audit = _read_json(metric_source_audit_json)

    canonical_summary = _summary(canonical_report)
    preview_summary = _summary(preview_report)
    fill_preview_summary = _summary(fill_preview)
    source_audit_summary = _summary(source_audit)

    canonical_ready = _report_ready(canonical_summary)
    preview_ready = _report_ready(preview_summary)
    fill_ready = _candidate_fill_preview_ready(fill_preview_summary)
    source_ready = _metric_source_ready(source_audit_summary)

    canonical_by_entry = _entry_map(_rows(canonical_report))
    preview_candidates_by_entry = _entry_map(_read_csv_rows(preview_candidate_csv))
    if not preview_candidates_by_entry:
        preview_candidates_by_entry = _entry_map(_preview_candidate_rows(fill_preview))
    fill_rows_by_entry = _entry_map(_preview_candidate_rows(fill_preview))

    rows = [
        _review_row(
            preview_row=preview_row,
            canonical_row=canonical_by_entry.get(_text(preview_row.get("entry_id")), {}),
            preview_candidate_row=preview_candidates_by_entry.get(_text(preview_row.get("entry_id")), {}),
            fill_row=fill_rows_by_entry.get(_text(preview_row.get("entry_id")), {}),
            canonical_report_ready=canonical_ready,
        )
        for preview_row in _selected_rows(_rows(preview_report))
    ]

    canonical_update_candidates = [row for row in rows if row["canonical_update_candidate"]]
    review_ready_rows = [row for row in rows if row["review_ready"]]
    blocked_rows = [row for row in rows if row["blockers"]]
    canonical_missing_metric_names = sorted(
        {
            metric
            for row in rows
            for metric in row["canonical_missing_metric_names"]
        }
    )

    if canonical_ready:
        status = "pocketmd_lite_canonical_report_review_closed"
    elif (
        rows
        and preview_ready
        and fill_ready
        and source_ready
        and canonical_update_candidates
        and len(review_ready_rows) == len(canonical_update_candidates)
        and not blocked_rows
    ):
        status = "pocketmd_lite_canonical_report_review_packet_ready"
    else:
        status = "blocked_pocketmd_lite_canonical_report_review_packet"

    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "canonical_report_json": _display(canonical_report_json),
        "preview_report_json": _display(preview_report_json),
        "candidate_fill_preview_json": _display(candidate_fill_preview_json),
        "metric_source_audit_json": _display(metric_source_audit_json),
        "canonical_candidate_csv": _display(canonical_candidate_csv),
        "preview_candidate_csv": _display(preview_candidate_csv),
        "canonical_report_status": canonical_summary.get("status", "missing"),
        "preview_report_status": preview_summary.get("status", "missing"),
        "candidate_fill_preview_status": fill_preview_summary.get("status", "missing"),
        "metric_source_audit_status": source_audit_summary.get("status", "missing"),
        "canonical_report_ready": canonical_ready,
        "preview_report_ready": preview_ready,
        "candidate_fill_preview_ready": fill_ready,
        "metric_source_audit_ready": source_ready,
        "canonical_claim_safe": bool(canonical_summary.get("pocketmd_lite_claim_safe") is True),
        "preview_claim_safe": bool(preview_summary.get("pocketmd_lite_claim_safe") is True),
        "canonical_top_k_refinement_evidence_ready": bool(
            canonical_summary.get("top_k_refinement_evidence_ready") is True
        ),
        "preview_top_k_refinement_evidence_ready": bool(
            preview_summary.get("top_k_refinement_evidence_ready") is True
        ),
        "selected_top_k_count": int(preview_summary.get("selected_top_k_count", len(rows)) or 0),
        "review_row_count": len(rows),
        "ready_review_row_count": len(review_ready_rows),
        "blocked_review_row_count": len(blocked_rows),
        "canonical_update_candidate_row_count": len(canonical_update_candidates),
        "canonical_green_row_count": int(canonical_summary.get("green_row_count", 0) or 0),
        "preview_green_row_count": int(preview_summary.get("green_row_count", 0) or 0),
        "canonical_abstain_row_count": int(canonical_summary.get("abstain_row_count", 0) or 0),
        "preview_abstain_row_count": int(preview_summary.get("abstain_row_count", 0) or 0),
        "canonical_missing_refinement_metric_names": canonical_missing_metric_names,
        "operator_approval_required": bool(not canonical_ready and status == "pocketmd_lite_canonical_report_review_packet_ready"),
        "approval_token_required": APPROVAL_TOKEN_REQUIRED,
        "next_required_step": (
            "Canonical PocketMD Lite report is already claim-safe; no canonical review packet action is required."
            if canonical_ready
            else "Operator review required: compare preview metrics against exact NPZ sources, then provide explicit approval before any separate canonical candidate CSV update."
            if status == "pocketmd_lite_canonical_report_review_packet_ready"
            else "Restore the claim-grade fill preview report, metric source audit, and source NPZ links before canonical review."
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        **READ_ONLY_FLAGS,
    }
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "rows": rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PocketMD Lite Canonical Report Review Packet",
        "",
        f"- status: `{summary['status']}`",
        f"- canonical_report_status: `{summary['canonical_report_status']}`",
        f"- preview_report_status: `{summary['preview_report_status']}`",
        f"- metric_source_audit_status: `{summary['metric_source_audit_status']}`",
        f"- canonical_update_candidate_row_count: `{summary['canonical_update_candidate_row_count']}`",
        f"- ready_review_row_count: `{summary['ready_review_row_count']}`",
        f"- operator_approval_required: `{str(summary['operator_approval_required']).lower()}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        f"- canonical_candidate_csv_mutated: `{str(summary['canonical_candidate_csv_mutated']).lower()}`",
        "",
        "## Rows",
        "",
        "| entry | canonical band | preview band | source | action | blockers |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{entry}` | `{canonical}` | `{preview}` | `{source}` | `{action}` | `{blockers}` |".format(
                entry=row["entry_id"],
                canonical=row["canonical_band"] or "(none)",
                preview=row["preview_band"] or "(none)",
                source=row["metric_source_npz"] or "(none)",
                action=row["review_action"],
                blockers=", ".join(row["blockers"]) or "(none)",
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any], *, out_json: str | Path, out_md: str | Path, out_csv: str | Path) -> None:
    json_path = _resolve(out_json)
    md_path = _resolve(out_md)
    csv_path = _resolve(out_csv)
    for path in (json_path, md_path, csv_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in payload["rows"]:
            writer.writerow({column: _fmt(row.get(column)) for column in CSV_COLUMNS})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-report-json", default=DEFAULT_CANONICAL_REPORT_JSON)
    parser.add_argument("--preview-report-json", default=DEFAULT_PREVIEW_REPORT_JSON)
    parser.add_argument("--candidate-fill-preview-json", default=DEFAULT_CANDIDATE_FILL_PREVIEW_JSON)
    parser.add_argument("--metric-source-audit-json", default=DEFAULT_METRIC_SOURCE_AUDIT_JSON)
    parser.add_argument("--canonical-candidate-csv", default=DEFAULT_CANONICAL_CANDIDATE_CSV)
    parser.add_argument("--preview-candidate-csv", default=DEFAULT_PREVIEW_CANDIDATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_pocketmd_lite_canonical_report_review_packet(
        canonical_report_json=args.canonical_report_json,
        preview_report_json=args.preview_report_json,
        candidate_fill_preview_json=args.candidate_fill_preview_json,
        metric_source_audit_json=args.metric_source_audit_json,
        canonical_candidate_csv=args.canonical_candidate_csv,
        preview_candidate_csv=args.preview_candidate_csv,
    )
    write_outputs(payload, out_json=args.out_json, out_md=args.out_md, out_csv=args.out_csv)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
