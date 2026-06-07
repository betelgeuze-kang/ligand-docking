#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_FIRST_SEED_ROW_PACKET_JSON = "runs/aqp1_first_seed_row_packet_current.json"
DEFAULT_EXTERNAL_SEED_JSON = "runs/aqp1_external_evidence_seed_current.json"
DEFAULT_MANUAL_QUEUE_JSON = "runs/aqp1_manual_review_queue_current.json"
DEFAULT_QUANTITATIVE_PROVENANCE_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_first_wave_source_confirmation_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_first_wave_source_confirmation_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_first_wave_source_confirmation_packet_current.md"


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _rows_by_step(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    payload = payload or {}
    return {
        _text(row.get("packet_step")): dict(row)
        for row in payload.get("rows", []) or []
        if _text(row.get("packet_step"))
    }


def _focus_scope(packet_step: str, provenance_status: str) -> str:
    if packet_step == "core_binder_01":
        return "first_wave_primary_exact_source_scope"
    if provenance_status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
        return "exact_human_activity_reference_guardrail"
    return "follow_on_exact_source_scope"


def _acceptance_gate(packet_step: str, provenance_status: str) -> str:
    if packet_step == "core_binder_01":
        return (
            "Accept only if the cited source is still consistent with AQP1-focused functional evidence and does not get over-interpreted as exact human target activity or binding."
        )
    if provenance_status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
        return (
            "Accept only if the row stays exact human AQP1 target-activity provenance and replacement_reference_binding_kcal_mol remains blank."
        )
    return "Accept only exact source identity, packet-step mapping, and current review-only bucket continuity."


def _rejection_gate(packet_step: str, provenance_status: str) -> str:
    if packet_step == "core_binder_01":
        return (
            "Reject any wording that upgrades Xenopus functional potency into exact human target activity, direct binding, or claim-safe kcal provenance."
        )
    if provenance_status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
        return "Reject any wording that reinterprets human target activity as claim-safe binding-kcal support."
    return "Reject non-exact identity matches, source drift, and any premature promotion out of review-only."


def _review_action(packet_step: str, provenance_status: str, next_required_action: str) -> str:
    if packet_step == "core_binder_01":
        return "confirm_exact_source_scope_and_keep_review_only"
    if provenance_status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
        return "confirm_exact_human_activity_reference_keep_kcal_blank"
    return next_required_action or "confirm_follow_on_source_scope_and_keep_review_only"


def build_payload(
    first_seed_row_packet_payload: dict[str, Any],
    external_seed_payload: dict[str, Any],
    manual_queue_payload: dict[str, Any],
    quantitative_provenance_payload: dict[str, Any],
) -> dict[str, Any]:
    first_seed_summary = dict(first_seed_row_packet_payload.get("summary", {}) or {})
    external_by_step = _rows_by_step(external_seed_payload)
    manual_by_step = _rows_by_step(manual_queue_payload)
    provenance_by_step = _rows_by_step(quantitative_provenance_payload)
    provenance_summary = dict(quantitative_provenance_payload.get("summary", {}) or {})

    packet_steps = ["core_binder_01", "core_binder_02", "core_binder_03"]
    rows: list[dict[str, Any]] = []
    for rank, packet_step in enumerate(packet_steps, start=1):
        external_row = external_by_step.get(packet_step, {})
        manual_row = manual_by_step.get(packet_step, {})
        provenance_row = provenance_by_step.get(packet_step, {})
        candidate_name = (
            _text(provenance_row.get("candidate_name"))
            or _text(external_row.get("candidate_name"))
            or _text(manual_row.get("suggested_external_candidate"))
        )
        provenance_status = _text(provenance_row.get("public_provenance_status")) or _text(
            manual_row.get("public_provenance_status")
        )
        provenance_signal = _text(provenance_row.get("public_provenance_signal")) or _text(
            manual_row.get("public_provenance_signal")
        )
        rows.append(
            {
                "confirmation_rank": rank,
                "packet_step": packet_step,
                "candidate_name": candidate_name,
                "focus_scope": _focus_scope(packet_step, provenance_status),
                "source_anchor": _text(provenance_row.get("source_anchor")) or _text(external_row.get("source_anchor")),
                "source_title": _text(provenance_row.get("source_title")) or _text(external_row.get("source_title")),
                "source_url": _text(provenance_row.get("source_url")) or _text(external_row.get("source_url")),
                "current_signal": _text(provenance_row.get("current_signal")) or _text(external_row.get("evidence_signal")),
                "assay_type_honesty": _text(provenance_row.get("assay_type_honesty")) or "functional_not_direct_binding",
                "public_provenance_status": provenance_status,
                "public_provenance_signal": provenance_signal,
                "pubchem_resolved": _text(provenance_row.get("pubchem_resolved")),
                "pubchem_cid": _text(provenance_row.get("pubchem_cid")),
                "chembl_molecule_chembl_id": _text(provenance_row.get("chembl_molecule_chembl_id")),
                "chembl_activity_record_count": _int(provenance_row.get("chembl_activity_record_count")),
                "chembl_activity_url": _text(provenance_row.get("chembl_activity_url")),
                "claim_safe_binding_kcal_ready": _text(provenance_row.get("claim_safe_binding_kcal_ready")),
                "review_bucket": _text(manual_row.get("review_bucket")) or _text(external_row.get("review_bucket")),
                "promotion_blocker": _text(manual_row.get("promotion_blocker")) or _text(first_seed_summary.get("promotion_blocker")),
                "acceptance_gate": _acceptance_gate(packet_step, provenance_status),
                "rejection_gate": _rejection_gate(packet_step, provenance_status),
                "review_action": _review_action(
                    packet_step,
                    provenance_status,
                    _text(manual_row.get("next_required_action")),
                ),
                "review_note": (
                    "Confirm bacopaside II as functional AQP1 first-wave scope only. Keep review-only because the current public lane has no exact human AQP1 pair activity or claim-safe binding support."
                    if packet_step == "core_binder_01"
                    else "Keep AqB013 as the exact human AQP1 target-activity reference row, but do not convert it into a claim-safe binding-kcal row."
                    if provenance_status == "exact_human_aqp1_quantitative_activity_present_nonbinding"
                    else "Keep follow-on AQP1 source scope aligned to the current review-only first-wave policy."
                ),
            }
        )

    exact_pair_absent_count = sum(1 for row in rows if int(row["chembl_activity_record_count"]) == 0)
    exact_human_reference_count = sum(
        1
        for row in rows
        if row["public_provenance_status"] == "exact_human_aqp1_quantitative_activity_present_nonbinding"
    )
    exact_human_reference_ligand = next(
        (row["candidate_name"] for row in rows if row["public_provenance_status"] == "exact_human_aqp1_quantitative_activity_present_nonbinding"),
        "",
    )

    summary = {
        "row_count": len(rows),
        "primary_focus_ligand": _text(rows[0]["candidate_name"]) if rows else "",
        "exact_human_reference_ligand": exact_human_reference_ligand,
        "pubchem_resolved_count": provenance_summary.get("pubchem_resolved_count", 0),
        "exact_pair_absent_count": exact_pair_absent_count,
        "exact_human_activity_reference_count": exact_human_reference_count,
        "claim_safe_kcal_ready_count": provenance_summary.get("claim_safe_kcal_ready_count", 0),
        "next_required_step": (
            f"Review {rows[0]['candidate_name']} first as the AQP1 core_binder_01 exact-source scope packet, keep {exact_human_reference_ligand or 'AqB013'} as the exact-human-activity reference row, and leave replacement_reference_binding_kcal_mol blank."
            if rows
            else "No first-wave source confirmation rows are available."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 First-Wave Source Confirmation Packet",
        "",
        f"- row_count: `{s['row_count']}`",
        f"- primary_focus_ligand: `{s['primary_focus_ligand']}`",
        f"- exact_human_reference_ligand: `{s['exact_human_reference_ligand']}`",
        f"- pubchem_resolved_count: `{s['pubchem_resolved_count']}`",
        f"- exact_pair_absent_count: `{s['exact_pair_absent_count']}`",
        f"- exact_human_activity_reference_count: `{s['exact_human_activity_reference_count']}`",
        f"- claim_safe_kcal_ready_count: `{s['claim_safe_kcal_ready_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Rows",
        "",
        "| confirmation_rank | packet_step | candidate_name | focus_scope | public_provenance_status | chembl_activity_record_count |",
        "| ---: | --- | --- | --- | --- | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['confirmation_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | `{row['focus_scope']}` | `{row['public_provenance_status'] or '-'}` | {row['chembl_activity_record_count']} |"
        )
    lines.extend(["", "## Reviewer Gates", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['candidate_name']}` accept: {row['acceptance_gate']}")
        lines.append(f"- `{row['candidate_name']}` reject: {row['rejection_gate']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1 first-wave source confirmation packet for the current first-wave transporter binder rows.")
    parser.add_argument("--first-seed-row-packet-json", default=DEFAULT_FIRST_SEED_ROW_PACKET_JSON)
    parser.add_argument("--external-seed-json", default=DEFAULT_EXTERNAL_SEED_JSON)
    parser.add_argument("--manual-queue-json", default=DEFAULT_MANUAL_QUEUE_JSON)
    parser.add_argument("--quantitative-provenance-json", default=DEFAULT_QUANTITATIVE_PROVENANCE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.first_seed_row_packet_json),
        _load_json(args.external_seed_json),
        _load_json(args.manual_queue_json),
        _load_json(args.quantitative_provenance_json),
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
