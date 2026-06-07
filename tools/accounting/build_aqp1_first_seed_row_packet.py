#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SEED_BOARD_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_WORKBOOK_JSON = "runs/aqp1_packet_replacement_workbook_current.json"
DEFAULT_APPLY_DRAFT_JSON = "runs/aqp1_manual_verdict_apply_draft_current.json"
DEFAULT_EXTERNAL_SEED_JSON = "runs/aqp1_external_evidence_seed_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_first_seed_row_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_first_seed_row_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_first_seed_row_packet_current.md"
DEFAULT_PACKET_STEP = "core_binder_01"


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


def _find_row(rows: list[dict[str, Any]], packet_step: str) -> dict[str, Any]:
    for row in rows:
        if str(row.get("packet_step", "")).strip() == packet_step:
            return dict(row)
    return {}


def build_payload(
    seed_board: dict[str, Any],
    workbook: dict[str, Any],
    apply_draft: dict[str, Any],
    external_seed: dict[str, Any],
    *,
    packet_step: str = DEFAULT_PACKET_STEP,
) -> dict[str, Any]:
    seed_row = _find_row(seed_board.get("rows", []) or [], packet_step)
    workbook_row = _find_row(workbook.get("workbook_rows", []) or [], packet_step)
    apply_row = _find_row(apply_draft.get("rows", []) or [], packet_step)
    external_row = _find_row(external_seed.get("rows", []) or [], packet_step)

    replacement_ligand_id = str(workbook_row.get("replacement_ligand_id", "")).strip()
    replacement_binding = str(workbook_row.get("replacement_reference_binding_kcal_mol", "")).strip()
    replacement_source = str(workbook_row.get("replacement_source", "")).strip()
    replacement_smiles = str(workbook_row.get("replacement_smiles", "")).strip()
    replacement_scaffold = str(workbook_row.get("replacement_scaffold", "")).strip()
    field_rows = [
        {
            "field_name": "replacement_ligand_id",
            "current_value": replacement_ligand_id,
            "suggested_value": str(apply_row.get("candidate_name", "")).strip(),
            "status": "staged_review_identifier" if replacement_ligand_id else "needs_curated_identifier",
            "note": "Choose a stable local ligand identifier for the first AQP1 non-placeholder row.",
        },
        {
            "field_name": "replacement_reference_binding_kcal_mol",
            "current_value": replacement_binding,
            "suggested_value": "",
            "status": "staged_review_binding" if replacement_binding else "blocked_quantitative_binding_gap",
            "note": (
                "Claim-safe quantitative binding is staged."
                if replacement_binding
                else "Current evidence is functional IC50, not a claim-safe binding kcal/mol reference."
            ),
        },
        {
            "field_name": "replacement_source",
            "current_value": replacement_source,
            "suggested_value": str(seed_row.get("source_url", "") or external_row.get("source_url", "")).strip(),
            "status": "staged_review_source" if replacement_source else "ready_to_copy",
            "note": "The PubMed anchor can be used as the first synchronized source pointer while the row stays non-authoritative.",
        },
        {
            "field_name": "replacement_smiles",
            "current_value": replacement_smiles,
            "suggested_value": "",
            "status": "staged_review_structure" if replacement_smiles else "needs_curated_structure",
            "note": "Local transporter packet still lacks a curated structure field for this candidate." if not replacement_smiles else "Structure field is staged from the local packet replacement workbook.",
        },
        {
            "field_name": "replacement_scaffold",
            "current_value": replacement_scaffold,
            "suggested_value": "",
            "status": "staged_review_structure" if replacement_scaffold else "needs_curated_structure",
            "note": "Scaffold should be derived only after the structure field is curated." if not replacement_scaffold else "Scaffold field is staged from the local packet replacement workbook.",
        },
    ]
    safe_statuses = {
        "ready_to_copy",
        "staged_review_identifier",
        "staged_review_source",
        "staged_review_structure",
        "staged_review_binding",
    }
    unresolved_fields = [row["field_name"] for row in field_rows if row["status"] not in safe_statuses]

    summary = {
        "target_id": "AQP1",
        "packet_step": packet_step,
        "candidate_name": str(seed_row.get("candidate_name", "") or apply_row.get("candidate_name", "")).strip(),
        "promotion_class": str(seed_row.get("promotion_class", "")).strip(),
        "source_anchor": str(seed_row.get("source_anchor", "") or external_row.get("source_anchor", "")).strip(),
        "source_url": str(seed_row.get("source_url", "") or external_row.get("source_url", "")).strip(),
        "evidence_signal": str(seed_row.get("evidence_signal", "") or external_row.get("potency_or_signal", "")).strip(),
        "promotion_blocker": str(seed_row.get("promotion_blocker", "")).strip(),
        "required_seed_field_count": len(field_rows),
        "ready_to_copy_field_count": sum(1 for row in field_rows if row["status"] in safe_statuses),
        "blocked_field_count": len(unresolved_fields),
        "functional_potency_staged": True,
        "evidence_mode": "functional_potency_staged_review_only",
        "quantitative_binding_status": "quantitative_binding_absent_claim_safe_kcal_missing",
        "remaining_unresolved_fields": ",".join(unresolved_fields),
        "remaining_unresolved_field_count": len(unresolved_fields),
        "direct_quantitative_binding_candidate_count": int(
            external_seed.get("summary", {}).get("direct_quantitative_binding_candidate_count", 0) or 0
        ),
        "external_endpoint_status": str(external_seed.get("summary", {}).get("endpoint_status", "")).strip(),
        "authoritative_apply_allowed": False,
        "next_required_step": (
            f"Use this packet to stage the AQP1 synchronized candidate row for {packet_step}. "
            f"Current evidence is functional potency only, not claim-safe quantitative binding, so keep only `{','.join(unresolved_fields)}` unresolved until curated and do not treat this packet as authoritative apply."
            if unresolved_fields
            else f"All seed-row fields for {packet_step} are staged, but the row must remain non-authoritative until quantitative binding/provenance review is complete."
        ),
    }
    return {"summary": summary, "rows": field_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Seed Row Packet",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- packet_step: `{s['packet_step']}`",
        f"- candidate_name: `{s['candidate_name']}`",
        f"- promotion_class: `{s['promotion_class']}`",
        f"- source_anchor: `{s['source_anchor']}`",
        f"- source_url: `{s['source_url']}`",
        f"- evidence_signal: `{s['evidence_signal']}`",
        f"- promotion_blocker: `{s['promotion_blocker']}`",
        f"- required_seed_field_count: `{s['required_seed_field_count']}`",
        f"- ready_to_copy_field_count: `{s['ready_to_copy_field_count']}`",
        f"- blocked_field_count: `{s['blocked_field_count']}`",
        f"- evidence_mode: `{s['evidence_mode']}`",
        f"- quantitative_binding_status: `{s['quantitative_binding_status']}`",
        f"- remaining_unresolved_fields: `{s['remaining_unresolved_fields']}`",
        f"- direct_quantitative_binding_candidate_count: `{s['direct_quantitative_binding_candidate_count']}`",
        f"- external_endpoint_status: `{s['external_endpoint_status']}`",
        f"- authoritative_apply_allowed: `{s['authoritative_apply_allowed']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Required Fields",
        "",
        "| field_name | current_value | suggested_value | status | note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['field_name']}` | `{row['current_value']}` | `{row['suggested_value']}` | `{row['status']}` | {row['note']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1 seed-row promotion packet.")
    parser.add_argument("--seed-board-json", default=DEFAULT_SEED_BOARD_JSON)
    parser.add_argument("--workbook-json", default=DEFAULT_WORKBOOK_JSON)
    parser.add_argument("--apply-draft-json", default=DEFAULT_APPLY_DRAFT_JSON)
    parser.add_argument("--external-seed-json", default=DEFAULT_EXTERNAL_SEED_JSON)
    parser.add_argument("--packet-step", default=DEFAULT_PACKET_STEP)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.seed_board_json),
        _load_json(args.workbook_json),
        _load_json(args.apply_draft_json),
        _load_json(args.external_seed_json),
        packet_step=args.packet_step,
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
