#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_SUPPLEMENT_CSV = RUNS / "aqp1_direct_binding_external_evidence_intake_supplement_current.csv"
DEFAULT_OUT_JSON = RUNS / "aqp1_direct_binding_external_evidence_intake_current.json"
DEFAULT_OUT_MD = RUNS / "aqp1_direct_binding_external_evidence_intake_current.md"
DEFAULT_OVERLAY_CSV = RUNS / "aqp1_direct_binding_external_evidence_workbook_overlay_current.csv"

KEEP_BLOCKED = "KEEP_BLOCKED"
OPERATOR_FILL = "OPERATOR_FILL"
APPROVE_DECISIONS = {"APPROVE_CLAIM_SAFE", "CLAIM_SAFE_APPROVED", "APPROVE"}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _is_truthy(value: Any) -> bool:
    return _text(value).lower() in {"true", "1", "yes"}


def _is_operator_placeholder(value: Any) -> bool:
    text = _text(value)
    return not text or text.startswith(OPERATOR_FILL) or text == KEEP_BLOCKED


def _is_numeric_kcal(value: Any) -> bool:
    text = _text(value)
    if not text or text == KEEP_BLOCKED:
        return False
    try:
        float(text)
    except ValueError:
        return False
    return True


def _row_validation_errors(row: dict[str, str]) -> list[str]:
    review_row_id = _text(row.get("review_row_id")) or _text(row.get("packet_step")) or "unknown_row"
    errors: list[str] = []
    if not _text(row.get("packet_step")):
        errors.append(f"{review_row_id}: blank packet_step")
    target_uniprot = _text(row.get("target_uniprot"))
    if target_uniprot and target_uniprot != "P29972":
        errors.append(f"{review_row_id}: target_uniprot must be P29972 for claim-safe AQP1 direct binding")
    return errors


def _row_is_claim_safe_approved(row: dict[str, str]) -> bool:
    if _text(row.get("review_decision")).upper() in {KEEP_BLOCKED, "REJECT", "DEFER"}:
        return False
    if _text(row.get("operator_claim_safe_decision")).upper() not in APPROVE_DECISIONS:
        return False
    if not _is_truthy(row.get("target_match_confirmed")):
        return False
    if not _is_truthy(row.get("assay_is_direct_binding")):
        return False
    if not _is_truthy(row.get("data_validity_accepted")):
        return False
    if _is_operator_placeholder(row.get("source_locator_or_raw_report")):
        return False
    if _is_operator_placeholder(row.get("standard_value_nM")):
        return False
    if not _is_numeric_kcal(row.get("replacement_reference_binding_kcal_mol")):
        return False
    if _is_operator_placeholder(row.get("replacement_ligand_id")):
        return False
    return True


def _row_is_operator_pending(row: dict[str, str]) -> bool:
    if _row_is_claim_safe_approved(row):
        return False
    critical_fields = [
        "replacement_reference_binding_kcal_mol",
        "source_locator_or_raw_report",
        "standard_value_nM",
        "operator_claim_safe_decision",
        "direct_binding_method",
    ]
    return any(_is_operator_placeholder(row.get(field)) for field in critical_fields)


def _workbook_overlay_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "packet_step": _text(row.get("packet_step")),
        "replacement_ligand_id": _text(row.get("replacement_ligand_id")),
        "replacement_reference_binding_kcal_mol": _text(row.get("replacement_reference_binding_kcal_mol")),
        "replacement_source": _text(row.get("source_locator_or_raw_report")),
        "notes": (
            "Claim-safe direct-binding kcal from operator external-evidence intake; "
            f"method={_text(row.get('direct_binding_method'))}; "
            f"standard_type={_text(row.get('standard_type'))}; "
            f"standard_value_nM={_text(row.get('standard_value_nM'))}."
        ),
    }


def build_payload(rows: list[dict[str, str]]) -> dict[str, Any]:
    validation_errors: list[str] = []
    reviewed_rows: list[dict[str, Any]] = []
    overlay_rows: list[dict[str, str]] = []

    for row in rows:
        validation_errors.extend(_row_validation_errors(row))
        approved = _row_is_claim_safe_approved(row)
        pending = _row_is_operator_pending(row)
        reviewed = {
            **row,
            "intake_status": (
                "claim_safe_approved" if approved else "operator_fill_pending" if pending else "keep_blocked"
            ),
            "authoritative_apply_allowed": approved,
            "functional_surrogate_promoted_to_kcal": False,
        }
        reviewed_rows.append(reviewed)
        if approved:
            overlay_rows.append(_workbook_overlay_row(row))

    duplicate_steps = [
        step
        for step, count in (
            (step, sum(1 for row in overlay_rows if row["packet_step"] == step))
            for step in {row["packet_step"] for row in overlay_rows}
        )
        if count > 1
    ]
    for step in duplicate_steps:
        validation_errors.append(f"duplicate claim-safe approved overlay for packet_step: {step}")

    approved_count = sum(1 for row in reviewed_rows if row["intake_status"] == "claim_safe_approved")
    pending_count = sum(1 for row in reviewed_rows if row["intake_status"] == "operator_fill_pending")
    keep_blocked_count = len(reviewed_rows) - approved_count - pending_count

    summary = {
        "packet_type": "aqp1_direct_binding_external_evidence_intake",
        "status": (
            "aqp1_direct_binding_external_evidence_intake_ready"
            if rows and not validation_errors
            else "blocked_aqp1_direct_binding_external_evidence_intake"
        ),
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "row_count": len(rows),
        "claim_safe_approved_count": approved_count,
        "operator_fill_pending_count": pending_count,
        "keep_blocked_count": keep_blocked_count,
        "workbook_overlay_row_count": len(overlay_rows),
        "direct_binding_gap_open": approved_count == 0,
        "kcal_policy": "never_promote_functional_surrogate_to_replacement_reference_binding_kcal_mol",
        "validation_error_count": len(validation_errors),
        "intake_applied": bool(rows) and not validation_errors,
        "next_required_step": (
            "No supplement rows found. Regenerate the operator fill guide CSV first."
            if not rows
            else (
                "Fix validation errors in the supplement CSV, then rerun intake."
                if validation_errors
                else (
                    "Claim-safe direct-binding rows are ready. Merge workbook overlay, rebuild AQP1 workbook, "
                    "run external-evidence intake, then apply with apply_aqp1_ready_workbook_rows.py and rerun "
                    "transporter P0 / scope gates."
                    if approved_count
                    else "Operator supplement rows remain KEEP_BLOCKED or pending. Fill exact human AQP1 direct "
                    "Kd/Ki with primary source and set operator_claim_safe_decision=APPROVE_CLAIM_SAFE, or keep "
                    "replacement_reference_binding_kcal_mol blank."
                )
            )
        ),
    }
    return {
        "summary": summary,
        "validation_errors": validation_errors,
        "rows": reviewed_rows,
        "workbook_overlay_rows": overlay_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# AQP1 Direct Binding External Evidence Intake",
        "",
        f"- status: `{summary['status']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- claim_safe_approved_count: `{summary['claim_safe_approved_count']}`",
        f"- operator_fill_pending_count: `{summary['operator_fill_pending_count']}`",
        f"- keep_blocked_count: `{summary['keep_blocked_count']}`",
        f"- workbook_overlay_row_count: `{summary['workbook_overlay_row_count']}`",
        f"- direct_binding_gap_open: `{summary['direct_binding_gap_open']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
    ]
    if payload["validation_errors"]:
        lines.extend(["", "## Validation Errors", ""])
        for err in payload["validation_errors"]:
            lines.append(f"- {err}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate AQP1 external direct-binding operator supplement CSV and emit workbook overlay rows."
    )
    parser.add_argument("--supplement-csv", default=str(DEFAULT_SUPPLEMENT_CSV))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    parser.add_argument("--overlay-csv", default=str(DEFAULT_OVERLAY_CSV))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = _read_csv(args.supplement_csv)
    payload = build_payload(rows)
    overlay_fieldnames = [
        "packet_step",
        "replacement_ligand_id",
        "replacement_reference_binding_kcal_mol",
        "replacement_source",
        "notes",
    ]
    _write_json(args.out_json, payload)
    _write_csv(args.overlay_csv, payload["workbook_overlay_rows"], overlay_fieldnames)
    _write_markdown(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
