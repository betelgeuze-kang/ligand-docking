#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools import build_aqp1_first_seed_row_packet as seed_packet_mod
from tools import build_aqp1_seed_row_fill_draft as fill_draft_mod
from tools import build_aqp1_seed_row_sync_apply_preview as sync_preview_mod

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SEED_BOARD_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_WORKBOOK_JSON = "runs/aqp1_packet_replacement_workbook_current.json"
DEFAULT_APPLY_DRAFT_JSON = "runs/aqp1_manual_verdict_apply_draft_current.json"
DEFAULT_EXTERNAL_SEED_JSON = "runs/aqp1_external_evidence_seed_current.json"
DEFAULT_MANUAL_QUEUE_JSON = "runs/aqp1_manual_review_queue_current.json"
DEFAULT_QUANTITATIVE_PROVENANCE_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_first_wave_follow_on_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_first_wave_follow_on_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_first_wave_follow_on_packet_current.md"

FOLLOW_ON_STEPS = ("core_binder_02", "core_binder_03")


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


def _artifact_path(kind: str, packet_step: str, suffix: str) -> Path:
    return _resolve(f"runs/aqp1_{kind}_{packet_step}_current.{suffix}")


def _rows_by_step(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("packet_step")): dict(row)
        for row in payload.get("rows", []) or []
        if _text(row.get("packet_step"))
    }


def _follow_on_focus_scope(public_provenance_status: str) -> str:
    if public_provenance_status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
        return "exact_human_activity_guardrail_follow_on"
    return "follow_on_exact_source_scope"


def _materialize_step(
    packet_step: str,
    seed_board: dict[str, Any],
    workbook: dict[str, Any],
    apply_draft: dict[str, Any],
    external_seed: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    seed_payload = seed_packet_mod.build_payload(
        seed_board,
        workbook,
        apply_draft,
        external_seed,
        packet_step=packet_step,
    )
    seed_json = _artifact_path("first_seed_row_packet", packet_step, "json")
    seed_csv = _artifact_path("first_seed_row_packet", packet_step, "csv")
    seed_md = _artifact_path("first_seed_row_packet", packet_step, "md")
    seed_json.write_text(json.dumps(seed_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    seed_packet_mod._write_csv(seed_csv, seed_payload["rows"])
    seed_packet_mod._write_markdown(seed_md, seed_payload)

    fill_rows = fill_draft_mod.build_rows(seed_payload, workbook, apply_draft, packet_step)
    fill_summary = fill_draft_mod.build_summary(seed_payload, fill_rows, packet_step)
    fill_payload = {"summary": fill_summary, "rows": fill_rows}
    fill_json = _artifact_path("seed_row_fill_draft", packet_step, "json")
    fill_csv = _artifact_path("seed_row_fill_draft", packet_step, "csv")
    fill_md = _artifact_path("seed_row_fill_draft", packet_step, "md")
    fill_draft_mod.write_json(fill_json, fill_payload)
    fill_draft_mod.write_csv(fill_csv, fill_rows)
    fill_draft_mod.write_md(fill_md, fill_summary, fill_rows)

    sync_row = sync_preview_mod.build_row(fill_payload, workbook, seed_payload, packet_step)
    sync_summary = sync_preview_mod.build_summary(fill_payload, sync_row)
    sync_payload = {"summary": sync_summary, "row": sync_row}
    sync_json = _artifact_path("seed_row_sync_apply_preview", packet_step, "json")
    sync_csv = _artifact_path("seed_row_sync_apply_preview", packet_step, "csv")
    sync_md = _artifact_path("seed_row_sync_apply_preview", packet_step, "md")
    sync_preview_mod.write_json(sync_json, sync_payload)
    sync_preview_mod.write_csv(sync_csv, sync_row)
    sync_preview_mod.write_md(sync_md, sync_summary, sync_row)

    return seed_payload, fill_payload, sync_payload


def build_payload(
    seed_board: dict[str, Any],
    workbook: dict[str, Any],
    apply_draft: dict[str, Any],
    external_seed: dict[str, Any],
    manual_queue: dict[str, Any],
    quantitative_provenance: dict[str, Any],
) -> dict[str, Any]:
    manual_by_step = _rows_by_step(manual_queue)
    provenance_by_step = _rows_by_step(quantitative_provenance)
    rows: list[dict[str, Any]] = []

    for rank, packet_step in enumerate(FOLLOW_ON_STEPS, start=1):
        seed_payload, fill_payload, sync_payload = _materialize_step(
            packet_step,
            seed_board,
            workbook,
            apply_draft,
            external_seed,
        )
        manual_row = manual_by_step.get(packet_step, {})
        provenance_row = provenance_by_step.get(packet_step, {})
        public_provenance_status = _text(provenance_row.get("public_provenance_status")) or _text(
            manual_row.get("public_provenance_status")
        )
        rows.append(
            {
                "follow_on_rank": rank,
                "priority_rank": rank,
                "packet_step": packet_step,
                "candidate_name": _text(seed_payload["summary"].get("candidate_name")),
                "focus_scope": _follow_on_focus_scope(public_provenance_status),
                "source_anchor": _text(seed_payload["summary"].get("source_anchor")) or _text(manual_row.get("suggested_external_source_anchor")),
                "source_url": _text(seed_payload["summary"].get("source_url")),
                "evidence_signal": _text(seed_payload["summary"].get("evidence_signal")) or _text(provenance_row.get("current_signal")),
                "public_provenance_status": public_provenance_status,
                "public_provenance_signal": _text(provenance_row.get("public_provenance_signal")) or _text(
                    manual_row.get("public_provenance_signal")
                ),
                "state_change_potential": _text(provenance_row.get("state_change_potential")) or _text(
                    manual_row.get("state_change_potential")
                ),
                "review_bucket": _text(manual_row.get("review_bucket")),
                "promotion_blocker": _text(manual_row.get("promotion_blocker")) or _text(
                    seed_payload["summary"].get("promotion_blocker")
                ),
                "next_required_action": _text(manual_row.get("next_required_action")) or _text(
                    provenance_row.get("next_required_step")
                ),
                "seed_packet_artifact": f"runs/aqp1_first_seed_row_packet_{packet_step}_current.md",
                "fill_draft_artifact": f"runs/aqp1_seed_row_fill_draft_{packet_step}_current.md",
                "sync_preview_artifact": f"runs/aqp1_seed_row_sync_apply_preview_{packet_step}_current.md",
                "seed_packet_next_required_step": _text(seed_payload["summary"].get("next_required_step")),
                "fill_draft_next_required_step": _text(fill_payload["summary"].get("next_required_step")),
                "sync_preview_next_required_step": _text(sync_payload["summary"].get("next_required_step")),
                "seed_ready_to_copy_field_count": seed_payload["summary"].get("ready_to_copy_field_count", 0),
                "seed_blocked_field_count": seed_payload["summary"].get("blocked_field_count", 0),
                "seed_remaining_unresolved_fields": _text(seed_payload["summary"].get("remaining_unresolved_fields")),
                "fill_safe_prefill_field_count": fill_payload["summary"].get("safe_prefill_field_count", 0),
                "fill_blocked_field_count": fill_payload["summary"].get("blocked_field_count", 0),
                "sync_safe_staged_field_count": sync_payload["summary"].get("safe_staged_field_count", 0),
                "sync_unresolved_field_count": sync_payload["summary"].get("unresolved_field_count", 0),
                "authoritative_apply_allowed": "no",
            }
        )

    follow_on_targets = ", ".join(row["packet_step"] for row in rows)
    summary = {
        "status": "aqp1_first_wave_follow_on_packet_ready",
        "row_count": len(rows),
        "follow_on_targets": follow_on_targets,
        "primary_follow_on_target": rows[0]["packet_step"] if rows else "",
        "primary_focus_ligand": rows[0]["candidate_name"] if rows else "",
        "candidate_names": ", ".join(row["candidate_name"] for row in rows),
        "source_anchors": ", ".join(row["source_anchor"] for row in rows),
        "seed_packet_artifacts": ", ".join(row["seed_packet_artifact"] for row in rows),
        "fill_draft_artifacts": ", ".join(row["fill_draft_artifact"] for row in rows),
        "sync_preview_artifacts": ", ".join(row["sync_preview_artifact"] for row in rows),
        "exact_human_guardrail_ligand": next(
            (
                row["candidate_name"]
                for row in rows
                if row["public_provenance_status"] == "exact_human_aqp1_quantitative_activity_present_nonbinding"
            ),
            "",
        ),
        "review_only_follow_on_count": sum(1 for row in rows if row["review_bucket"]),
        "blocking_signal": (
            f"follow_on_targets={follow_on_targets}; "
            f"exact_human_guardrail={next((row['candidate_name'] for row in rows if row['public_provenance_status'] == 'exact_human_aqp1_quantitative_activity_present_nonbinding'), '')}; "
            "authoritative_apply_allowed=False"
        ),
        "next_required_step": (
            f"After core_binder_01, use {rows[0]['packet_step']} ({rows[0]['candidate_name']}) as the first AQP1 follow-on lane, keep replacement_reference_binding_kcal_mol blank, "
            f"then continue {rows[1]['packet_step']} ({rows[1]['candidate_name']}) before widening to GLUT1."
            if len(rows) == 2
            else "No AQP1 follow-on rows are available."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# AQP1 First-Wave Follow-On Packet",
        "",
        f"- row_count: `{summary['row_count']}`",
        f"- status: `{summary['status']}`",
        f"- follow_on_targets: `{summary['follow_on_targets']}`",
        f"- primary_follow_on_target: `{summary['primary_follow_on_target']}`",
        f"- primary_focus_ligand: `{summary['primary_focus_ligand']}`",
        f"- candidate_names: `{summary['candidate_names']}`",
        f"- source_anchors: `{summary['source_anchors']}`",
        f"- exact_human_guardrail_ligand: `{summary['exact_human_guardrail_ligand']}`",
        f"- review_only_follow_on_count: `{summary['review_only_follow_on_count']}`",
        f"- blocking_signal: `{summary['blocking_signal']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Follow-On Rows",
        "",
        "| follow_on_rank | packet_step | candidate_name | focus_scope | public_provenance_status | seed_packet_artifact | fill_draft_artifact | sync_preview_artifact |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['follow_on_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | `{row['focus_scope']}` | `{row['public_provenance_status']}` | "
            f"`{row['seed_packet_artifact']}` | `{row['fill_draft_artifact']}` | `{row['sync_preview_artifact']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AQP1 first-wave follow-on packet and materialize core_binder_02/core_binder_03 artifacts.")
    parser.add_argument("--seed-board-json", default=DEFAULT_SEED_BOARD_JSON)
    parser.add_argument("--workbook-json", default=DEFAULT_WORKBOOK_JSON)
    parser.add_argument("--apply-draft-json", default=DEFAULT_APPLY_DRAFT_JSON)
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
        _load_json(args.seed_board_json),
        _load_json(args.workbook_json),
        _load_json(args.apply_draft_json),
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
