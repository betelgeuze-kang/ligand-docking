#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BINDER_SHEET_JSON = "runs/aqp1_binder_verdict_update_sheet_current.json"
DEFAULT_EVIDENCE_JSON = "runs/aqp1_candidate_evidence_ledger_current.json"
DEFAULT_PROVENANCE_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_binder_review_brief_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_binder_review_brief_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_binder_review_brief_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _evidence_lookup(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("candidate_name", "")).strip(): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("candidate_name", "")).strip()
    }


def _provenance_focus(provenance_row: dict[str, Any]) -> str:
    status = str(provenance_row.get("public_provenance_status", "")).strip()
    if status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
        return (
            "Confirm the exact human AQP1 target-activity provenance is recorded correctly, "
            "but keep review-only and do not reinterpret it as claim-safe binding."
        )
    if status == "compound_publicly_resolved_target_activity_absent":
        return (
            "Confirm review-only hold. Public compound resolution exists, but the current exact human AQP1 target-activity lane is absent."
        )
    if status == "pubchem_resolved_chembl_target_pair_absent":
        return (
            "Confirm review-only hold. PubChem resolves the compound, but the exact ChEMBL AQP1 pair is still absent."
        )
    return "Confirm the evidence still supports keep_review_only and does not justify authoritative transporter apply."


def build_payload(
    binder_sheet: dict[str, Any],
    evidence_payload: dict[str, Any],
    provenance_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_by_name = _evidence_lookup(evidence_payload)
    provenance_by_name = _evidence_lookup(provenance_payload or {})
    rows: list[dict[str, Any]] = []
    for row in binder_sheet.get("sheet_rows", []) or []:
        candidate_name = str(row.get("candidate_name", "")).strip()
        evidence = evidence_by_name.get(candidate_name, {})
        provenance = provenance_by_name.get(candidate_name, {})
        rows.append(
            {
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "candidate_name": candidate_name,
                "source_anchor": str(row.get("source_anchor", "")).strip(),
                "source_url": str(row.get("source_url", "")).strip(),
                "mechanism_bucket": str(evidence.get("mechanism_bucket", "")).strip(),
                "assay_surface": str(evidence.get("assay_surface", "")).strip(),
                "review_focus": _provenance_focus(provenance),
                "confirm_fields": "manual_verdict_update, manual_confidence_update, manual_decision_note",
                "suggested_manual_verdict": str(row.get("suggested_manual_verdict", "")).strip(),
                "suggested_manual_confidence_update": str(row.get("suggested_manual_confidence_update", "")).strip(),
                "reviewer_copy_note": str(row.get("suggested_manual_decision_note", "")).strip(),
                "caution": str(row.get("caution", "")).strip(),
                "public_provenance_status": str(provenance.get("public_provenance_status", "")).strip(),
                "public_provenance_signal": str(provenance.get("public_provenance_signal", "")).strip(),
                "chembl_best_activity_type": str(provenance.get("chembl_best_activity_type", "")).strip(),
                "chembl_best_activity_value": str(provenance.get("chembl_best_activity_value", "")).strip(),
                "chembl_best_activity_units": str(provenance.get("chembl_best_activity_units", "")).strip(),
                "update_status": str(row.get("update_status", "")).strip(),
            }
        )

    summary = {
        "binder_slot_count": len(rows),
        "pending_manual_verdict_count": sum(1 for row in rows if row["update_status"] == "pending_manual_verdict"),
        "ready_for_reviewer_fill_count": len(rows),
        "exact_human_provenance_count": sum(
            1
            for row in rows
            if str(row.get("public_provenance_status", "")).strip()
            == "exact_human_aqp1_quantitative_activity_present_nonbinding"
        ),
        "next_required_step": "Use this brief to fill the three AQP1 binder manual verdict fields, but keep every row in review-only territory until transporter packet evidence and donor policy mature.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Binder Review Brief",
        "",
        f"- binder_slot_count: `{s['binder_slot_count']}`",
        f"- pending_manual_verdict_count: `{s['pending_manual_verdict_count']}`",
        f"- ready_for_reviewer_fill_count: `{s['ready_for_reviewer_fill_count']}`",
        f"- exact_human_provenance_count: `{s['exact_human_provenance_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## First-Wave Binder Slots",
        "",
        "| priority_rank | packet_step | candidate_name | source_anchor | suggested_manual_verdict | suggested_manual_confidence_update | confirm_fields |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | `{row['source_anchor']}` | "
            f"`{row['suggested_manual_verdict']}` | `{row['suggested_manual_confidence_update']}` | `{row['confirm_fields']}` |"
        )
        lines.append("")
        lines.append(f"- Reviewer note template for `{row['candidate_name']}`: {row['reviewer_copy_note']}")
        lines.append(f"- Caution: {row['caution']}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a reviewer-facing brief for AQP1 first-wave binder manual verdict work.")
    parser.add_argument("--binder-sheet-json", default=DEFAULT_BINDER_SHEET_JSON)
    parser.add_argument("--evidence-json", default=DEFAULT_EVIDENCE_JSON)
    parser.add_argument("--provenance-json", default=DEFAULT_PROVENANCE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.binder_sheet_json),
        _load_json(args.evidence_json),
        _load_json(args.provenance_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
