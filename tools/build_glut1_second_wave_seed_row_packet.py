#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SEED_BOARD_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_WORKBOOK_JSON = "runs/glut1_packet_replacement_workbook_current.json"
DEFAULT_APPLY_DRAFT_JSON = "runs/glut1_manual_verdict_apply_draft_current.json"
DEFAULT_SOURCE_CONFIRMATION_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
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


def _find_row(rows: list[dict[str, Any]], packet_step: str, *, target_id: str = "") -> dict[str, Any]:
    for row in rows:
        if str(row.get("packet_step", "")).strip() != packet_step:
            continue
        row_target_id = str(row.get("target_id", "")).strip()
        row_alias = str(row.get("canonical_target_alias", "")).strip()
        if target_id and row_target_id and row_target_id != target_id:
            continue
        if target_id and row_alias and row_alias != target_id:
            continue
        if target_id and not row_target_id and not row_alias:
            continue
        return dict(row)
    return {}


def _default_output(stem: str, packet_step: str, suffix: str) -> str:
    if packet_step == "core_binder_01":
        return f"runs/{stem}_current.{suffix}"
    return f"runs/{stem}_{packet_step}_current.{suffix}"


def _binding_note(source_row: dict[str, Any], current_value: str) -> str:
    if current_value:
        return "Quantitative binding field is already staged locally, but this row must remain non-authoritative."
    status = str(source_row.get("public_provenance_status", "")).strip()
    if status == "exact_human_glut1_direct_binding_present_no_kcal":
        return "Direct human GLUT1 binding support exists, but no claim-safe quantitative binding kcal/mol reference is curated."
    if status == "exact_human_glut1_activity_present_nonbinding":
        return "Exact human GLUT1 target-pair activity exists, but it is a functional inhibitor row rather than a claim-safe binding kcal/mol reference."
    return "Only review-only functional/direct-binding-claim support is available, not a claim-safe quantitative binding kcal/mol reference."


def build_payload(
    seed_board: dict[str, Any],
    workbook: dict[str, Any],
    apply_draft: dict[str, Any],
    source_confirmation: dict[str, Any],
    *,
    packet_step: str = DEFAULT_PACKET_STEP,
) -> dict[str, Any]:
    seed_row = _find_row(seed_board.get("rows", []) or [], packet_step, target_id="GLUT1")
    workbook_row = _find_row(workbook.get("workbook_rows", []) or [], packet_step)
    apply_row = _find_row(apply_draft.get("draft_rows", []) or [], packet_step)
    source_row = _find_row(source_confirmation.get("rows", []) or [], packet_step)

    replacement_ligand_id = str(workbook_row.get("replacement_ligand_id", "")).strip()
    replacement_binding = str(workbook_row.get("replacement_reference_binding_kcal_mol", "")).strip()
    replacement_source = str(workbook_row.get("replacement_source", "")).strip()
    replacement_smiles = str(workbook_row.get("replacement_smiles", "")).strip()
    replacement_scaffold = str(workbook_row.get("replacement_scaffold", "")).strip()
    candidate_name = (
        str(source_row.get("candidate_name", "")).strip()
        or str(seed_row.get("candidate_name", "")).strip()
        or str(apply_row.get("candidate_name", "")).strip()
    )

    field_rows = [
        {
            "field_name": "replacement_ligand_id",
            "current_value": replacement_ligand_id,
            "suggested_value": candidate_name,
            "status": "staged_review_identifier" if replacement_ligand_id else "needs_curated_identifier",
            "note": "Choose a stable local GLUT1 ligand identifier; the literature-facing candidate label is shown only as a reviewer hint.",
        },
        {
            "field_name": "replacement_reference_binding_kcal_mol",
            "current_value": replacement_binding,
            "suggested_value": "",
            "status": "staged_review_binding" if replacement_binding else "blocked_quantitative_binding_gap",
            "note": _binding_note(source_row, replacement_binding),
        },
        {
            "field_name": "replacement_source",
            "current_value": replacement_source,
            "suggested_value": str(source_row.get("source_url", "") or seed_row.get("source_url", "")).strip(),
            "status": "staged_review_source" if replacement_source else "ready_to_copy",
            "note": "Use the exact-source confirmation URL as the synchronized provenance pointer while the row remains second-wave and non-authoritative.",
        },
        {
            "field_name": "replacement_smiles",
            "current_value": replacement_smiles,
            "suggested_value": "",
            "status": "staged_review_structure" if replacement_smiles else "needs_curated_structure",
            "note": "The local GLUT1 packet still lacks a curated structure field for this candidate." if not replacement_smiles else "Structure field is already staged locally.",
        },
        {
            "field_name": "replacement_scaffold",
            "current_value": replacement_scaffold,
            "suggested_value": "",
            "status": "staged_review_structure" if replacement_scaffold else "needs_curated_structure",
            "note": "Scaffold should be derived only after the structure field is curated." if not replacement_scaffold else "Scaffold field is already staged locally.",
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
        "target_id": "GLUT1",
        "wave": "second",
        "packet_step": packet_step,
        "candidate_name": candidate_name,
        "promotion_class": str(seed_row.get("promotion_class", "")).strip(),
        "source_anchor": str(source_row.get("source_anchor", "") or seed_row.get("source_anchor", "")).strip(),
        "source_url": str(source_row.get("source_url", "") or seed_row.get("source_url", "")).strip(),
        "evidence_signal": str(source_row.get("evidence_signal", "") or seed_row.get("evidence_signal", "")).strip(),
        "source_confirmation_scope": str(source_row.get("confirmation_scope", "")).strip(),
        "public_provenance_status": str(source_row.get("public_provenance_status", "")).strip(),
        "public_provenance_signal": str(source_row.get("public_provenance_signal", "")).strip(),
        "promotion_blocker": str(source_row.get("promotion_blocker", "") or seed_row.get("promotion_blocker", "")).strip(),
        "required_seed_field_count": len(field_rows),
        "ready_to_copy_field_count": sum(1 for row in field_rows if row["status"] in safe_statuses),
        "blocked_field_count": len(unresolved_fields),
        "evidence_mode": "second_wave_non_authoritative_staged_review_only",
        "quantitative_binding_status": "quantitative_binding_absent_claim_safe_kcal_missing",
        "remaining_unresolved_fields": ",".join(unresolved_fields),
        "remaining_unresolved_field_count": len(unresolved_fields),
        "direct_quantitative_binding_count": int(source_confirmation.get("summary", {}).get("direct_quantitative_binding_count", 0) or 0),
        "exact_target_pair_activity_count": int(source_confirmation.get("summary", {}).get("exact_target_pair_activity_count", 0) or 0),
        "structured_pair_absent_count": int(source_confirmation.get("summary", {}).get("structured_pair_absent_count", 0) or 0),
        "authoritative_apply_allowed": False,
        "next_required_step": (
            f"Use this packet to stage the GLUT1 second-wave synchronized candidate row for {packet_step}. "
            f"Keep `{','.join(unresolved_fields)}` unresolved until curated, leave replacement_reference_binding_kcal_mol blank, "
            "and do not treat this row as authoritative apply."
            if unresolved_fields
            else f"All second-wave seed-row fields for {packet_step} are staged, but the row must remain non-authoritative and kcal-blank."
        ),
    }
    return {"summary": summary, "rows": field_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GLUT1 Second-Wave Seed Row Packet",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- wave: `{s['wave']}`",
        f"- packet_step: `{s['packet_step']}`",
        f"- candidate_name: `{s['candidate_name']}`",
        f"- promotion_class: `{s['promotion_class']}`",
        f"- source_anchor: `{s['source_anchor']}`",
        f"- source_url: `{s['source_url']}`",
        f"- evidence_signal: `{s['evidence_signal']}`",
        f"- source_confirmation_scope: `{s['source_confirmation_scope']}`",
        f"- public_provenance_status: `{s['public_provenance_status']}`",
        f"- public_provenance_signal: `{s['public_provenance_signal']}`",
        f"- promotion_blocker: `{s['promotion_blocker']}`",
        f"- required_seed_field_count: `{s['required_seed_field_count']}`",
        f"- ready_to_copy_field_count: `{s['ready_to_copy_field_count']}`",
        f"- blocked_field_count: `{s['blocked_field_count']}`",
        f"- evidence_mode: `{s['evidence_mode']}`",
        f"- quantitative_binding_status: `{s['quantitative_binding_status']}`",
        f"- remaining_unresolved_fields: `{s['remaining_unresolved_fields']}`",
        f"- direct_quantitative_binding_count: `{s['direct_quantitative_binding_count']}`",
        f"- exact_target_pair_activity_count: `{s['exact_target_pair_activity_count']}`",
        f"- structured_pair_absent_count: `{s['structured_pair_absent_count']}`",
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
    parser = argparse.ArgumentParser(description="Build a GLUT1 second-wave seed-row packet.")
    parser.add_argument("--seed-board-json", default=DEFAULT_SEED_BOARD_JSON)
    parser.add_argument("--workbook-json", default=DEFAULT_WORKBOOK_JSON)
    parser.add_argument("--apply-draft-json", default=DEFAULT_APPLY_DRAFT_JSON)
    parser.add_argument("--source-confirmation-json", default=DEFAULT_SOURCE_CONFIRMATION_JSON)
    parser.add_argument("--packet-step", default=DEFAULT_PACKET_STEP)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-csv", default="")
    parser.add_argument("--out-md", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    packet_step = args.packet_step
    payload = build_payload(
        _load_json(args.seed_board_json),
        _load_json(args.workbook_json),
        _load_json(args.apply_draft_json),
        _load_json(args.source_confirmation_json),
        packet_step=packet_step,
    )
    out_json = _resolve(args.out_json or _default_output("glut1_second_wave_seed_row_packet", packet_step, "json"))
    out_csv = _resolve(args.out_csv or _default_output("glut1_second_wave_seed_row_packet", packet_step, "csv"))
    out_md = _resolve(args.out_md or _default_output("glut1_second_wave_seed_row_packet", packet_step, "md"))
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
