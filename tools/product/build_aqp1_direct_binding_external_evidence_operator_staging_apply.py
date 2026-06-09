#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_aqp1_direct_binding_external_evidence_intake import (
    APPROVE_DECISIONS,
    KEEP_BLOCKED,
    OPERATOR_FILL,
    build_payload as build_intake_payload,
)
from tools.product.build_aqp1_direct_binding_external_evidence_operator_worksheet import (
    build_payload as build_worksheet_payload,
)
from tools.product.build_aqp1_direct_binding_external_evidence_supplement_example import (
    EXAMPLE_NOTE_PREFIX,
)

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_PROCUREMENT_JSON = RUNS / "aqp1_direct_binding_procurement_packet_current.json"
DEFAULT_OPERATOR_CANDIDATE_JSON = RUNS / "aqp1_operator_validation_candidate_packet_current.json"
DEFAULT_FUNCTIONAL_JSON = RUNS / "aqp1_functional_kcal_surrogate_packet_current.json"
DEFAULT_LIVE_SUPPLEMENT_CSV = RUNS / "aqp1_direct_binding_external_evidence_intake_supplement_current.csv"
DEFAULT_STAGING_SUPPLEMENT_CSV = RUNS / "aqp1_direct_binding_external_evidence_intake_supplement_example_current.csv"
DEFAULT_OUT_JSON = RUNS / "aqp1_direct_binding_external_evidence_operator_staging_apply_current.json"
DEFAULT_OUT_CSV = RUNS / "aqp1_direct_binding_external_evidence_operator_staging_apply_current.csv"
DEFAULT_OUT_MD = RUNS / "aqp1_direct_binding_external_evidence_operator_staging_apply_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    import csv

    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _live_apply_rows(staging_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in staging_rows
        if not _contains_example_marker(row)
        and _text(row.get("operator_claim_safe_decision")).upper() in APPROVE_DECISIONS
    ]


def _write_supplement_csv(path_like: str | Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    import csv

    path = _resolve(path_like)
    fieldnames = list(rows[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _contains_example_marker(row: dict[str, str]) -> bool:
    notes = _text(row.get("reviewer_notes"))
    source = _text(row.get("source_locator_or_raw_report"))
    return EXAMPLE_NOTE_PREFIX in notes or "EXAMPLE_" in source.upper()


def _staging_validation_errors(
    rows: list[dict[str, str]],
    *,
    allow_example_markers: bool,
    validate_pending_rows: bool,
) -> list[str]:
    errors: list[str] = []
    for row in rows:
        review_row_id = _text(row.get("review_row_id")) or _text(row.get("packet_step")) or "unknown_row"
        decision = _text(row.get("operator_claim_safe_decision")).upper()
        if decision not in APPROVE_DECISIONS and not validate_pending_rows:
            continue
        if not allow_example_markers and _contains_example_marker(row):
            errors.append(f"{review_row_id}: illustrative example markers must not be copied into live supplement")
        if (
            not allow_example_markers
            and decision in APPROVE_DECISIONS
            and _contains_example_marker(row)
        ):
            errors.append(f"{review_row_id}: APPROVE_CLAIM_SAFE blocked while EXAMPLE markers remain")
        if validate_pending_rows and decision.startswith(OPERATOR_FILL):
            errors.append(f"{review_row_id}: operator decision still pending")
        if _text(row.get("replacement_reference_binding_kcal_mol")) == KEEP_BLOCKED and decision in APPROVE_DECISIONS:
            errors.append(f"{review_row_id}: APPROVE_CLAIM_SAFE requires numeric direct-binding kcal")
    return errors


def build_payload(
    *,
    staging_rows: list[dict[str, str]],
    live_supplement_rows: list[dict[str, str]],
    procurement_packet: dict[str, Any],
    operator_candidate_packet: dict[str, Any],
    functional_packet: dict[str, Any],
    staging_csv: str | Path,
    live_supplement_csv: str | Path,
    mode: str = "preview",
) -> dict[str, Any]:
    allow_example_markers = mode == "rehearsal"
    validate_pending_rows = mode in {"preview", "live_apply"}
    validation_errors = _staging_validation_errors(
        staging_rows,
        allow_example_markers=allow_example_markers,
        validate_pending_rows=validate_pending_rows,
    )
    intake_payload = build_intake_payload(staging_rows)
    worksheet_payload = build_worksheet_payload(
        procurement_packet=procurement_packet,
        operator_candidate_packet=operator_candidate_packet,
        functional_packet=functional_packet,
        supplement_rows=staging_rows,
    )
    approved_count = int(intake_payload["summary"].get("claim_safe_approved_count") or 0)
    live_approved_count = sum(
        1 for row in build_intake_payload(live_supplement_rows)["rows"] if row.get("intake_status") == "claim_safe_approved"
    )
    live_apply_allowed = (
        mode == "live_apply"
        and not validation_errors
        and approved_count > 0
        and not any(_contains_example_marker(row) for row in staging_rows)
    )
    rehearsal_green = mode == "rehearsal" and not validation_errors and approved_count > 0
    summary = {
        "packet_type": "aqp1_direct_binding_external_evidence_operator_staging_apply",
        "status": (
            "aqp1_operator_staging_apply_ready_for_live_copy"
            if live_apply_allowed
            else "aqp1_operator_staging_rehearsal_green"
            if rehearsal_green
            else "blocked_aqp1_operator_staging_apply"
        ),
        "mode": mode,
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "staging_csv": str(_resolve(staging_csv)),
        "live_supplement_csv": str(_resolve(live_supplement_csv)),
        "staging_row_count": len(staging_rows),
        "live_supplement_row_count": len(live_supplement_rows),
        "staging_claim_safe_approved_count": approved_count,
        "live_claim_safe_approved_count": live_approved_count,
        "validation_error_count": len(validation_errors),
        "live_apply_allowed": live_apply_allowed,
        "live_copy_executed": False,
        "authoritative_apply_allowed": False,
        "next_required_step": (
            "Copy verified primary-source rows from staging into the live supplement CSV without EXAMPLE markers, "
            "then rerun intake, worksheet, and apply_aqp1_ready_workbook_rows.py."
            if rehearsal_green
            else (
                "Fix staging validation errors or replace illustrative placeholders with verified PMID/DOI and direct "
                "Kd/Ki before any live APPROVE_CLAIM_SAFE apply."
                if validation_errors or approved_count == 0
                else "Live apply preview is green. Operator may copy approved rows into the live supplement CSV and rerun intake."
            )
        ),
    }
    detail_rows = [
        {
            "review_row_id": _text(row.get("review_row_id")),
            "packet_step": _text(row.get("packet_step")),
            "operator_claim_safe_decision": _text(row.get("operator_claim_safe_decision")),
            "replacement_reference_binding_kcal_mol": _text(row.get("replacement_reference_binding_kcal_mol")),
            "source_locator_or_raw_report": _text(row.get("source_locator_or_raw_report")),
            "contains_example_marker": _contains_example_marker(row),
            "intake_status": next(
                (
                    reviewed.get("intake_status")
                    for reviewed in intake_payload.get("rows", [])
                    if _text(reviewed.get("review_row_id")) == _text(row.get("review_row_id"))
                ),
                "unknown",
            ),
        }
        for row in staging_rows
    ]
    return {
        "summary": summary,
        "validation_errors": validation_errors,
        "intake_summary": intake_payload["summary"],
        "worksheet_summary": worksheet_payload["summary"],
        "rows": detail_rows,
        "claim_boundary": {
            "authoritative_apply_allowed": False,
            "functional_surrogate_promoted_to_kcal": False,
            "illustrative_example_must_not_become_live_claim_safe": True,
        },
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# AQP1 Direct Binding External Evidence Operator Staging Apply",
        "",
        f"- status: `{summary['status']}`",
        f"- mode: `{summary['mode']}`",
        f"- staging_claim_safe_approved_count: `{summary['staging_claim_safe_approved_count']}`",
        f"- live_claim_safe_approved_count: `{summary['live_claim_safe_approved_count']}`",
        f"- live_apply_allowed: `{str(summary['live_apply_allowed']).lower()}`",
        "",
        "## Paths",
        "",
        f"- staging_csv: `{summary['staging_csv']}`",
        f"- live_supplement_csv: `{summary['live_supplement_csv']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
    ]
    if payload.get("validation_errors"):
        lines.extend(["## Validation Errors", ""])
        for err in payload["validation_errors"]:
            lines.append(f"- {err}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview operator supplement staging intake/worksheet apply without touching live claim-safe rows."
    )
    parser.add_argument(
        "--apply-live-copy",
        action="store_true",
        help="When live_apply is allowed, copy validated staging rows into the live supplement CSV.",
    )
    parser.add_argument("--mode", choices=("preview", "rehearsal", "live_apply"), default="rehearsal")
    parser.add_argument("--staging-csv", default=str(DEFAULT_STAGING_SUPPLEMENT_CSV))
    parser.add_argument("--live-supplement-csv", default=str(DEFAULT_LIVE_SUPPLEMENT_CSV))
    parser.add_argument("--procurement-json", default=str(DEFAULT_PROCUREMENT_JSON))
    parser.add_argument("--operator-candidate-json", default=str(DEFAULT_OPERATOR_CANDIDATE_JSON))
    parser.add_argument("--functional-json", default=str(DEFAULT_FUNCTIONAL_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        staging_rows=_read_csv(args.staging_csv),
        live_supplement_rows=_read_csv(args.live_supplement_csv),
        procurement_packet=_read_json(args.procurement_json),
        operator_candidate_packet=_read_json(args.operator_candidate_json),
        functional_packet=_read_json(args.functional_json),
        staging_csv=args.staging_csv,
        live_supplement_csv=args.live_supplement_csv,
        mode=args.mode,
    )
    summary = payload["summary"]
    if args.apply_live_copy and summary.get("live_apply_allowed"):
        live_rows = _live_apply_rows(_read_csv(args.staging_csv))
        _write_supplement_csv(args.live_supplement_csv, live_rows)
        summary["live_copy_executed"] = True
        summary["live_supplement_row_count"] = len(live_rows)
        summary["next_required_step"] = (
            "Live supplement CSV updated from validated staging rows. Rerun intake, workbook apply, and transporter scope gates."
        )
        payload["summary"] = summary
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(_resolve(args.out_md), payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
