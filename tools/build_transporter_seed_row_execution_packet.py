#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


RUNS = Path("runs")

DEFAULT_SEED_BOARD_JSON = RUNS / "transporter_seed_row_promotion_board_current.json"
DEFAULT_SEED_PACKET_JSON = RUNS / "aqp1_first_seed_row_packet_current.json"
DEFAULT_FILL_DRAFT_JSON = RUNS / "aqp1_seed_row_fill_draft_current.json"
DEFAULT_SYNC_PREVIEW_JSON = RUNS / "aqp1_seed_row_sync_apply_preview_current.json"
DEFAULT_WORKBOOK_JSON = RUNS / "aqp1_packet_replacement_workbook_current.json"
DEFAULT_FILL_QUEUE_JSON = RUNS / "aqp1_packet_fill_queue_current.json"
DEFAULT_LEDGER_JSON = RUNS / "aqp1_candidate_evidence_ledger_current.json"
DEFAULT_BLOCKER_JSON = RUNS / "transporter_authoritative_apply_blocker_decomposition_current.json"

DEFAULT_PACKET_STEP = "core_binder_01"
DEFAULT_OUT_JSON = RUNS / "transporter_seed_row_execution_packet_current.json"
DEFAULT_OUT_CSV = RUNS / "transporter_seed_row_execution_packet_current.csv"
DEFAULT_OUT_MD = RUNS / "transporter_seed_row_execution_packet_current.md"


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return json.load(fh)


def _index_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key, "")).strip(): dict(row) for row in rows}


def _find_packet_row(seed_board: dict[str, Any], packet_step: str, target_id: str) -> dict[str, Any]:
    target_norm = target_id.strip().lower()
    for row in list(seed_board.get("rows", []) or []):
        if str(row.get("packet_step", "")).strip() != packet_step:
            continue
        if str(row.get("target_id", "")).strip().lower() == target_norm:
            return dict(row)
    raise KeyError(f"packet_step/target_id not found in seed board: {packet_step} {target_id}")


def _find_ledger_row(ledger: dict[str, Any], packet_step: str) -> dict[str, Any]:
    row_map = _index_by(list(ledger.get("rows", []) or []), "proposed_packet_step")
    return row_map.get(packet_step, {})


def _find_workbook_row(workbook: dict[str, Any], packet_step: str, target_id: str) -> dict[str, Any]:
    target_norm = target_id.strip().lower()
    packet_matches: list[dict[str, Any]] = []
    for row in list(workbook.get("workbook_rows", []) or []):
        if str(row.get("packet_step", "")).strip() != packet_step:
            continue
        packet_matches.append(dict(row))
        target_value = str(row.get("target", "")).strip().lower()
        if target_value.startswith(target_norm):
            return dict(row)
    if len(packet_matches) == 1:
        return packet_matches[0]
    raise KeyError(f"packet_step/target_id not found in workbook: {packet_step} {target_id}")


def _field_map(fill_draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return _index_by(list(fill_draft.get("rows", []) or []), "field_name")


def build_rows(
    *,
    seed_board: dict[str, Any],
    seed_packet: dict[str, Any],
    fill_draft: dict[str, Any],
    sync_preview: dict[str, Any],
    workbook: dict[str, Any],
    ledger: dict[str, Any],
    blocker: dict[str, Any],
    packet_step: str,
) -> list[dict[str, Any]]:
    seed_summary = dict(seed_packet.get("summary", {}) or {})
    target_id = str(seed_summary.get("target_id", "") or "").strip() or "AQP1"
    board_row = _find_packet_row(seed_board, packet_step, target_id)
    workbook_row = _find_workbook_row(workbook, packet_step, target_id)
    ledger_row = _find_ledger_row(ledger, packet_step)
    field_rows = _field_map(fill_draft)
    sync_summary = dict(sync_preview.get("summary", {}) or {})
    blocker_summary = dict(blocker.get("summary", {}) or {})
    blocker_rows = list(blocker.get("rows", []) or [])

    apply_contract = (
        f"reference={workbook_row.get('apply_reference_row', '')}; "
        f"split={workbook_row.get('apply_split_row', '')}; "
        f"meta={workbook_row.get('apply_meta_row', '')}"
    )
    blocker_signal = str(blocker_summary.get("top_blocker_signal", "")).strip() or "; ".join(
        str(x) for x in board_row.get("blocker_link", "").split("; ") if x
    )
    unresolved_fields = set(str(sync_preview.get("row", {}).get("unresolved_fields", "")).split(",")) if sync_preview.get("row") else set()

    rows: list[dict[str, Any]] = []
    for field_name in [
        "replacement_ligand_id",
        "replacement_reference_binding_kcal_mol",
        "replacement_source",
        "replacement_smiles",
        "replacement_scaffold",
    ]:
        field_row = field_rows.get(field_name, {})
        rows.append(
            {
                "packet_step": packet_step,
                "field_name": field_name,
                "candidate_name": seed_summary.get("candidate_name", ""),
                "current_workbook_value": workbook_row.get(field_name, ""),
                "suggested_value": field_row.get("suggested_value", ""),
                "staged_fill_value": field_row.get("staged_fill_value", ""),
                "stage_now": "yes" if field_row.get("reviewer_safe_now") == "yes" else "no",
                "sync_contract": apply_contract,
                "blocking_status": field_row.get("field_status", ""),
                "blocker_link": blocker_signal,
                "source_anchor": board_row.get("source_anchor", ""),
                "source_url": board_row.get("source_url", ""),
                "note": field_row.get("note", ""),
                "still_unresolved_after_sync_preview": "yes" if field_name in unresolved_fields else "no",
            }
        )

    for blocker_row in blocker_rows[:2]:
        rows.append(
            {
                "packet_step": packet_step,
                "field_name": f"blocker::{blocker_row.get('blocker_id', '')}",
                "candidate_name": seed_summary.get("candidate_name", ""),
                "current_workbook_value": "",
                "suggested_value": "",
                "staged_fill_value": "",
                "stage_now": "no",
                "sync_contract": apply_contract,
                "blocking_status": blocker_row.get("blocker_status", ""),
                "blocker_link": blocker_row.get("current_signal", "") or blocker_signal,
                "source_anchor": board_row.get("source_anchor", ""),
                "source_url": board_row.get("source_url", ""),
                "note": blocker_row.get("next_action", ""),
                "still_unresolved_after_sync_preview": "yes",
            }
        )

    if ledger_row:
        rows.append(
            {
                "packet_step": packet_step,
                "field_name": "evidence_anchor",
                "candidate_name": seed_summary.get("candidate_name", ""),
                "current_workbook_value": "",
                "suggested_value": ledger_row.get("potency_or_signal", ""),
                "staged_fill_value": "",
                "stage_now": "review_only",
                "sync_contract": apply_contract,
                "blocking_status": ledger_row.get("promotion_policy", ""),
                "blocker_link": ledger_row.get("caution", ""),
                "source_anchor": ledger_row.get("anchor", ""),
                "source_url": ledger_row.get("source_url", ""),
                "note": ledger_row.get("assay_surface", ""),
                "still_unresolved_after_sync_preview": "yes",
            }
        )

    return rows


def build_summary(
    *,
    seed_board: dict[str, Any],
    seed_packet: dict[str, Any],
    fill_draft: dict[str, Any],
    sync_preview: dict[str, Any],
    workbook: dict[str, Any],
    fill_queue: dict[str, Any],
    ledger: dict[str, Any],
    blocker: dict[str, Any],
    packet_step: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    seed_summary = dict(seed_packet.get("summary", {}) or {})
    target_id = str(seed_summary.get("target_id", "") or "").strip() or "AQP1"
    board_row = _find_packet_row(seed_board, packet_step, target_id)
    workbook_row = _find_workbook_row(workbook, packet_step, target_id)
    fill_summary = dict(fill_draft.get("summary", {}) or {})
    sync_summary = dict(sync_preview.get("summary", {}) or {})
    ledger_row = _find_ledger_row(ledger, packet_step)
    blocker_summary = dict(blocker.get("summary", {}) or {})
    queue_summary = dict(fill_queue.get("summary", {}) or {})

    return {
        "target_id": board_row.get("target_id", ""),
        "packet_step": packet_step,
        "candidate_name": seed_summary.get("candidate_name", ""),
        "wave": board_row.get("wave", ""),
        "promotion_class": board_row.get("promotion_class", ""),
        "source_anchor": board_row.get("source_anchor", ""),
        "source_url": board_row.get("source_url", ""),
        "triple_sync_required": board_row.get("triple_sync_required", ""),
        "apply_reference_row": workbook_row.get("apply_reference_row", ""),
        "apply_split_row": workbook_row.get("apply_split_row", ""),
        "apply_meta_row": workbook_row.get("apply_meta_row", ""),
        "required_seed_field_count": seed_summary.get("required_seed_field_count", 0),
        "safe_prefill_field_count": fill_summary.get("safe_prefill_field_count", 0),
        "safe_staged_field_count": sync_summary.get("safe_staged_field_count", 0),
        "unresolved_field_count": sync_summary.get("unresolved_field_count", 0),
        "functional_potency_staged": True,
        "evidence_mode": seed_summary.get("evidence_mode", "functional_potency_staged_review_only"),
        "quantitative_binding_status": seed_summary.get(
            "quantitative_binding_status",
            "quantitative_binding_absent_claim_safe_kcal_missing",
        ),
        "remaining_unresolved_fields": seed_summary.get("remaining_unresolved_fields", ""),
        "authoritative_apply_allowed": False,
        "donor_policy_reopen_allowed": False,
        "top_blocker_id": blocker_summary.get("top_blocker_id", ""),
        "top_blocker_signal": blocker_summary.get("top_blocker_signal", "") or str(board_row.get("blocker_link", "")).strip(),
        "queue_count": queue_summary.get("queue_count", 0),
        "ledger_confidence": ledger_row.get("confidence", ""),
        "next_required_step": (
            "Use this execution packet to stage the first non-authoritative AQP1 seed row. Current evidence is functional potency only, not claim-safe quantitative binding, so keep the reference/split/meta triple synchronized, copy only reviewer-safe fields now, and leave replacement_reference_binding_kcal_mol unresolved until curated."
        ),
        "row_count": len(rows),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Transporter Seed Row Execution Packet",
        "",
        f"- target_id: `{summary['target_id']}`",
        f"- packet_step: `{summary['packet_step']}`",
        f"- candidate_name: `{summary['candidate_name']}`",
        f"- wave: `{summary['wave']}`",
        f"- promotion_class: `{summary['promotion_class']}`",
        f"- source_anchor: `{summary['source_anchor']}`",
        f"- triple_sync_required: `{summary['triple_sync_required']}`",
        f"- apply_reference_row: `{summary['apply_reference_row']}`",
        f"- apply_split_row: `{summary['apply_split_row']}`",
        f"- apply_meta_row: `{summary['apply_meta_row']}`",
        f"- safe_prefill_field_count: `{summary['safe_prefill_field_count']}`",
        f"- safe_staged_field_count: `{summary['safe_staged_field_count']}`",
        f"- unresolved_field_count: `{summary['unresolved_field_count']}`",
        f"- evidence_mode: `{summary['evidence_mode']}`",
        f"- quantitative_binding_status: `{summary['quantitative_binding_status']}`",
        f"- remaining_unresolved_fields: `{summary['remaining_unresolved_fields']}`",
        f"- authoritative_apply_allowed: `{summary['authoritative_apply_allowed']}`",
        f"- donor_policy_reopen_allowed: `{summary['donor_policy_reopen_allowed']}`",
        f"- top_blocker_id: `{summary['top_blocker_id']}`",
        f"- top_blocker_signal: `{summary['top_blocker_signal']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Execution Table",
        "",
        "| field_name | suggested_value | staged_fill_value | stage_now | sync_contract | blocking_status | still_unresolved_after_sync_preview |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['field_name']}` | `{row['suggested_value']}` | `{row['staged_fill_value']}` | `{row['stage_now']}` | `{row['sync_contract']}` | `{row['blocking_status']}` | `{row['still_unresolved_after_sync_preview']}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This packet is execution-facing, not claim-bearing.",
            "- It is only for replacing the first transporter placeholder row with a synchronized non-authoritative seed-row draft.",
            "- Current AQP1 evidence is functional potency staged in review-only mode; it is not claim-safe quantitative binding.",
            "- Only `replacement_reference_binding_kcal_mol` should remain unresolved for the first staged row.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the transporter seed-row execution packet for the current AQP1 first-wave target.")
    parser.add_argument("--seed-board-json", default=str(DEFAULT_SEED_BOARD_JSON))
    parser.add_argument("--seed-packet-json", default=str(DEFAULT_SEED_PACKET_JSON))
    parser.add_argument("--fill-draft-json", default=str(DEFAULT_FILL_DRAFT_JSON))
    parser.add_argument("--sync-preview-json", default=str(DEFAULT_SYNC_PREVIEW_JSON))
    parser.add_argument("--workbook-json", default=str(DEFAULT_WORKBOOK_JSON))
    parser.add_argument("--fill-queue-json", default=str(DEFAULT_FILL_QUEUE_JSON))
    parser.add_argument("--ledger-json", default=str(DEFAULT_LEDGER_JSON))
    parser.add_argument("--blocker-json", default=str(DEFAULT_BLOCKER_JSON))
    parser.add_argument("--packet-step", default=DEFAULT_PACKET_STEP)
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seed_board = load_json(Path(args.seed_board_json))
    seed_packet = load_json(Path(args.seed_packet_json))
    fill_draft = load_json(Path(args.fill_draft_json))
    sync_preview = load_json(Path(args.sync_preview_json))
    workbook = load_json(Path(args.workbook_json))
    fill_queue = load_json(Path(args.fill_queue_json))
    ledger = load_json(Path(args.ledger_json))
    blocker = load_json(Path(args.blocker_json))

    rows = build_rows(
        seed_board=seed_board,
        seed_packet=seed_packet,
        fill_draft=fill_draft,
        sync_preview=sync_preview,
        workbook=workbook,
        ledger=ledger,
        blocker=blocker,
        packet_step=args.packet_step,
    )
    summary = build_summary(
        seed_board=seed_board,
        seed_packet=seed_packet,
        fill_draft=fill_draft,
        sync_preview=sync_preview,
        workbook=workbook,
        fill_queue=fill_queue,
        ledger=ledger,
        blocker=blocker,
        packet_step=args.packet_step,
        rows=rows,
    )
    payload = {"summary": summary, "rows": rows}

    write_json(Path(args.out_json), payload)
    write_csv(Path(args.out_csv), rows)
    write_md(Path(args.out_md), summary, rows)


if __name__ == "__main__":
    main()
