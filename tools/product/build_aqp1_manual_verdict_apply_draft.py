#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BINDER_SHEET_JSON = "runs/aqp1_binder_verdict_update_sheet_current.json"
DEFAULT_EVIDENCE_LEDGER_JSON = "runs/aqp1_candidate_evidence_ledger_current.json"
DEFAULT_PROVENANCE_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_manual_verdict_apply_draft_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_manual_verdict_apply_draft_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_manual_verdict_apply_draft_current.md"


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


def _ledger_index(ledger_payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for row in ledger_payload.get("rows", []) or ledger_payload.get("ledger_rows", []) or []:
        candidate_name = str(row.get("candidate_name", "")).strip()
        if not candidate_name:
            continue
        index[candidate_name] = {
            "mechanism_bucket": str(row.get("mechanism_bucket", "")).strip(),
            "assay_surface": str(row.get("assay_surface", "")).strip(),
            "review_bucket": str(row.get("review_bucket", "")).strip(),
            "ledger_confidence": str(row.get("confidence", "")).strip(),
        }
    return index


def _provenance_index(provenance_payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for row in provenance_payload.get("rows", []) or []:
        candidate_name = str(row.get("candidate_name", "")).strip()
        if not candidate_name:
            continue
        index[candidate_name] = {
            "public_provenance_status": str(row.get("public_provenance_status", "")).strip(),
            "public_provenance_signal": str(row.get("public_provenance_signal", "")).strip(),
            "state_change_potential": str(row.get("state_change_potential", "")).strip(),
            "chembl_best_activity_type": str(row.get("chembl_best_activity_type", "")).strip(),
            "chembl_best_activity_value": str(row.get("chembl_best_activity_value", "")).strip(),
            "chembl_best_activity_units": str(row.get("chembl_best_activity_units", "")).strip(),
        }
    return index


def _reviewer_checklist(provenance: dict[str, str]) -> str:
    status = provenance.get("public_provenance_status", "")
    if status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
        return "confirm_anchor_scope;confirm_exact_human_activity_nonbinding;keep_kcal_blank;record_manual_note"
    if status == "compound_publicly_resolved_target_activity_absent":
        return "confirm_anchor_scope;confirm_public_target_activity_absent;confirm_review_only_hold;record_manual_note"
    if status == "pubchem_resolved_chembl_target_pair_absent":
        return "confirm_anchor_scope;confirm_pubchem_resolution_only;confirm_review_only_hold;record_manual_note"
    return "confirm_anchor_scope;confirm_review_only_hold;record_manual_note"


def _decision_note(base_note: str, provenance: dict[str, str]) -> str:
    status = provenance.get("public_provenance_status", "")
    activity = " ".join(
        part
        for part in (
            provenance.get("chembl_best_activity_type", ""),
            provenance.get("chembl_best_activity_value", ""),
            provenance.get("chembl_best_activity_units", ""),
        )
        if part
    ).strip()
    if status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
        suffix = (
            " Public exact-human AQP1 target-activity provenance exists"
            + (f" (`{activity}`)." if activity else ".")
            + " Keep replacement_reference_binding_kcal_mol blank because this is not a claim-safe binding-kcal source."
        )
        return (base_note + suffix).strip()
    if status == "compound_publicly_resolved_target_activity_absent":
        return (
            base_note
            + " Public compound resolution exists, but the current exact human AQP1 target-activity lane is absent; keep review-only."
        ).strip()
    if status == "pubchem_resolved_chembl_target_pair_absent":
        return (
            base_note
            + " PubChem resolves the compound, but the exact ChEMBL AQP1 pair is still absent; keep review-only."
        ).strip()
    return base_note


def build_payload(
    binder_sheet: dict[str, Any],
    evidence_ledger: dict[str, Any],
    provenance_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ledger_by_name = _ledger_index(evidence_ledger)
    provenance_by_name = _provenance_index(provenance_payload or {})
    rows: list[dict[str, Any]] = []
    for row in binder_sheet.get("sheet_rows", []) or []:
        candidate_name = str(row.get("candidate_name", "")).strip()
        ledger = ledger_by_name.get(candidate_name, {})
        provenance = provenance_by_name.get(candidate_name, {})
        rows.append(
            {
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "candidate_name": candidate_name,
                "source_anchor": str(row.get("source_anchor", "")).strip(),
                "source_url": str(row.get("source_url", "")).strip(),
                "evidence_class": str(row.get("evidence_class", "")).strip(),
                "evidence_strength": str(row.get("evidence_strength", "")).strip(),
                "potency_or_signal": str(row.get("potency_or_signal", "")).strip(),
                "mechanism_bucket": ledger.get("mechanism_bucket", ""),
                "assay_surface": ledger.get("assay_surface", ""),
                "current_review_bucket": str(row.get("current_review_bucket", "")).strip(),
                "draft_manual_verdict_update": str(row.get("suggested_manual_verdict", "")).strip(),
                "draft_manual_confidence_update": str(row.get("suggested_manual_confidence_update", "")).strip(),
                "draft_manual_decision_note": _decision_note(
                    str(row.get("suggested_manual_decision_note", "")).strip(),
                    provenance,
                ),
                "reviewer_confirm_fields": "manual_verdict_update,manual_confidence_update,manual_decision_note",
                "reviewer_checklist": _reviewer_checklist(provenance),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
                "caution": str(row.get("caution", "")).strip(),
                "public_provenance_status": provenance.get("public_provenance_status", ""),
                "public_provenance_signal": provenance.get("public_provenance_signal", ""),
                "state_change_potential": provenance.get("state_change_potential", ""),
                "authoritative_apply_allowed": "no",
                "manual_verdict_update": str(row.get("manual_verdict_update", "")).strip(),
                "manual_confidence_update": str(row.get("manual_confidence_update", "")).strip(),
                "manual_decision_note": str(row.get("manual_decision_note", "")).strip(),
                "update_status": str(row.get("update_status", "")).strip(),
            }
        )

    summary = {
        "target_id": "AQP1",
        "row_count": len(rows),
        "draft_prefill_count": sum(1 for row in rows if row["draft_manual_verdict_update"]),
        "pending_manual_verdict_count": sum(1 for row in rows if row["update_status"] == "pending_manual_verdict"),
        "exact_human_provenance_count": sum(
            1
            for row in rows
            if str(row.get("public_provenance_status", "")).strip()
            == "exact_human_aqp1_quantitative_activity_present_nonbinding"
        ),
        "authoritative_apply_allowed": False,
        "next_required_step": "Use this AQP1-only draft packet to prefill reviewer judgment, but keep manual_verdict_update explicit and do not promote any row to authoritative apply.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# AQP1 Manual Verdict Apply Draft",
        "",
        f"- target_id: `{summary['target_id']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- draft_prefill_count: `{summary['draft_prefill_count']}`",
        f"- pending_manual_verdict_count: `{summary['pending_manual_verdict_count']}`",
        f"- exact_human_provenance_count: `{summary['exact_human_provenance_count']}`",
        f"- authoritative_apply_allowed: `{summary['authoritative_apply_allowed']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Draft Rows",
        "",
        "| priority_rank | packet_step | candidate_name | draft_manual_verdict_update | draft_manual_confidence_update | reviewer_checklist | promotion_blocker |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['draft_manual_verdict_update']}` | `{row['draft_manual_confidence_update']}` | "
            f"`{row['reviewer_checklist']}` | `{row['promotion_blocker']}` |"
        )
        lines.extend(
            [
                "",
                f"- Draft note for `{row['candidate_name']}`: {row['draft_manual_decision_note']}",
                f"- Assay surface: `{row['assay_surface']}`",
                f"- Caution: {row['caution']}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1-only reviewer draft packet for manual verdict application without touching authoritative apply fields.")
    parser.add_argument("--binder-sheet-json", default=DEFAULT_BINDER_SHEET_JSON)
    parser.add_argument("--evidence-ledger-json", default=DEFAULT_EVIDENCE_LEDGER_JSON)
    parser.add_argument("--provenance-json", default=DEFAULT_PROVENANCE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.binder_sheet_json),
        _load_json(args.evidence_ledger_json),
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
