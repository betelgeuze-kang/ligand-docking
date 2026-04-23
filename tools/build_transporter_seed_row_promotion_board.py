#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_AQP1_WORKBOOK_JSON = "runs/aqp1_packet_replacement_workbook_current.json"
DEFAULT_GLUT1_WORKBOOK_JSON = "runs/glut1_packet_replacement_workbook_current.json"
DEFAULT_AQP1_APPLY_DRAFT_JSON = "runs/aqp1_manual_verdict_apply_draft_current.json"
DEFAULT_GLUT1_APPLY_DRAFT_JSON = "runs/glut1_manual_verdict_apply_draft_current.json"
DEFAULT_AQP1_NEGATIVE_PACKET_JSON = "runs/aqp1_negative_review_handoff_packet_current.json"
DEFAULT_GLUT1_NEGATIVE_PACKET_JSON = "runs/glut1_negative_review_handoff_packet_current.json"
DEFAULT_WAVE_DECISION_JSON = "runs/transporter_wave_decision_current.json"
DEFAULT_BLOCKER_JSON = "runs/transporter_authoritative_apply_blocker_decomposition_current.json"
DEFAULT_APPLY_STATUS_JSON = "runs/transporter_apply_draft_status_current.json"
DEFAULT_OUT_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_OUT_CSV = "runs/transporter_seed_row_promotion_board_current.csv"
DEFAULT_OUT_MD = "runs/transporter_seed_row_promotion_board_current.md"


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


def _binder_lookup(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows") or payload.get("draft_rows") or []
    return {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in rows
        if str(row.get("packet_step", "")).strip()
    }


def _negative_lookup(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows") or payload.get("negative_rows") or []
    return {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in rows
        if str(row.get("packet_step", "")).strip()
    }


def _aqp1_seed_artifact(kind: str, packet_step: str) -> str:
    if packet_step == "core_binder_01":
        return f"runs/aqp1_{kind}_current.md"
    return f"runs/aqp1_{kind}_{packet_step}_current.md"


def _glut1_seed_artifact(kind: str, packet_step: str) -> str:
    if packet_step == "core_binder_01":
        return f"runs/glut1_second_wave_{kind}_current.md"
    return f"runs/glut1_second_wave_{kind}_{packet_step}_current.md"


def _build_rows_for_target(
    *,
    target_id: str,
    wave: str,
    workbook: dict[str, Any],
    binder_apply_draft: dict[str, Any],
    negative_packet: dict[str, Any],
    binder_priority_prefix: str,
    blocker_signal: str,
) -> list[dict[str, Any]]:
    binder_lookup = _binder_lookup(binder_apply_draft)
    negative_lookup = _negative_lookup(negative_packet)
    rows: list[dict[str, Any]] = []
    for workbook_row in workbook.get("workbook_rows", []) or []:
        packet_step = str(workbook_row.get("packet_step", "")).strip()
        is_binder = str(workbook_row.get("current_binder_label", "")).strip() == "binder"
        lookup_row = binder_lookup.get(packet_step, {}) if is_binder else negative_lookup.get(packet_step, {})
        if is_binder:
            promotion_class = "seed_now" if wave == "first" else "seed_after_aqp1"
            candidate_name = str(
                lookup_row.get("candidate_name")
                or lookup_row.get("current_ligand_id")
                or workbook_row.get("current_ligand_id", "")
            ).strip()
            source_anchor = str(lookup_row.get("source_anchor", "")).strip()
            source_url = str(lookup_row.get("source_url", "")).strip()
            review_bucket = str(
                lookup_row.get("current_review_bucket")
                or lookup_row.get("suggested_manual_verdict")
                or "keep_review_only"
            ).strip()
            promotion_blocker = str(lookup_row.get("promotion_blocker", "")).strip()
            next_required_action = str(
                lookup_row.get("next_required_action")
                or "manual_curated_search_or_defer"
            ).strip()
            evidence_signal = str(
                lookup_row.get("potency_or_signal")
                or lookup_row.get("suggested_manual_decision_note")
                or ""
            ).strip()
            blocker_link = blocker_signal or "placeholder_packet_rows; workbook_seed_rows_empty"
            priority_rank = int(f"{binder_priority_prefix}{packet_step.split('_')[-1]}")
            seed_packet_artifact = _aqp1_seed_artifact("first_seed_row_packet", packet_step) if target_id == "AQP1" else ""
            fill_draft_artifact = _aqp1_seed_artifact("seed_row_fill_draft", packet_step) if target_id == "AQP1" else ""
            sync_preview_artifact = _aqp1_seed_artifact("seed_row_sync_apply_preview", packet_step) if target_id == "AQP1" else ""
            if target_id == "GLUT1":
                seed_packet_artifact = _glut1_seed_artifact("seed_row_packet", packet_step)
                fill_draft_artifact = _glut1_seed_artifact("seed_row_fill_draft", packet_step)
                sync_preview_artifact = _glut1_seed_artifact("seed_row_sync_apply_preview", packet_step)
        else:
            promotion_class = "review_only_hold"
            candidate_name = str(lookup_row.get("label") or workbook_row.get("current_ligand_id", "")).strip()
            source_anchor = ""
            source_url = ""
            review_bucket = str(
                lookup_row.get("review_bucket")
                or lookup_row.get("recommended_resolution")
                or "review_only_negative_evidence"
            ).strip()
            promotion_blocker = str(
                lookup_row.get("promotion_blocker")
                or "no_quantitative_transporter_negative_evidence_curated"
            ).strip()
            next_required_action = str(
                lookup_row.get("next_action")
                or lookup_row.get("next_required_action")
                or "manual_negative_evidence_review"
            ).strip()
            evidence_signal = str(lookup_row.get("notes", "")).strip()
            blocker_link = "placeholder_packet_rows"
            priority_rank = 300 + int(packet_step.split("_")[-1]) + (0 if target_id == "AQP1" else 10)
            seed_packet_artifact = ""
            fill_draft_artifact = ""
            sync_preview_artifact = ""

        rows.append(
            {
                "priority_rank": priority_rank,
                "target_id": target_id,
                "wave": wave,
                "packet_step": packet_step,
                "row_kind": "binder" if is_binder else "negative",
                "promotion_class": promotion_class,
                "candidate_name": candidate_name,
                "source_anchor": source_anchor,
                "source_url": source_url,
                "review_bucket": review_bucket,
                "evidence_signal": evidence_signal,
                "promotion_blocker": promotion_blocker,
                "next_required_action": next_required_action,
                "required_seed_fields": str(workbook_row.get("required_missing_fields", "")).strip(),
                "triple_sync_required": "reference+split+meta",
                "blocker_link": blocker_link,
                "seed_packet_artifact": seed_packet_artifact,
                "fill_draft_artifact": fill_draft_artifact,
                "sync_preview_artifact": sync_preview_artifact,
                "authoritative_apply_allowed": "no",
            }
        )
    return rows


def build_payload(
    aqp1_workbook: dict[str, Any],
    glut1_workbook: dict[str, Any],
    aqp1_apply_draft: dict[str, Any],
    glut1_apply_draft: dict[str, Any],
    aqp1_negative_packet: dict[str, Any],
    glut1_negative_packet: dict[str, Any],
    wave_decision: dict[str, Any],
    blocker_payload: dict[str, Any],
    apply_status_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocker_summary = dict(blocker_payload.get("summary", {}) or {})
    apply_status_summary = dict((apply_status_payload or {}).get("summary", {}) or {})
    wave_summary = dict(wave_decision.get("summary", {}) or {})
    blocker_signal = (
        f"placeholder_driven_rows={apply_status_summary.get('placeholder_driven_rows', 0)}; "
        f"staged_non_authoritative_rows={apply_status_summary.get('staged_non_authoritative_rows', 0)}; "
        f"ready_for_apply_rows={apply_status_summary.get('ready_for_apply_rows', 0)}"
        if apply_status_summary
        else str(blocker_summary.get("top_blocker_signal", "")).strip()
    )

    aqp1_rows = _build_rows_for_target(
        target_id="AQP1",
        wave="first",
        workbook=aqp1_workbook,
        binder_apply_draft=aqp1_apply_draft,
        negative_packet=aqp1_negative_packet,
        binder_priority_prefix="1",
        blocker_signal=blocker_signal,
    )
    glut1_rows = _build_rows_for_target(
        target_id="GLUT1",
        wave="second",
        workbook=glut1_workbook,
        binder_apply_draft=glut1_apply_draft,
        negative_packet=glut1_negative_packet,
        binder_priority_prefix="2",
        blocker_signal=blocker_signal,
    )
    rows = sorted(aqp1_rows + glut1_rows, key=lambda row: (int(row["priority_rank"]), row["target_id"], row["packet_step"]))
    summary = {
        "row_count": len(rows),
        "binder_row_count": sum(1 for row in rows if row["row_kind"] == "binder"),
        "negative_row_count": sum(1 for row in rows if row["row_kind"] == "negative"),
        "seed_now_count": sum(1 for row in rows if row["promotion_class"] == "seed_now"),
        "seed_after_aqp1_count": sum(1 for row in rows if row["promotion_class"] == "seed_after_aqp1"),
        "review_only_hold_count": sum(1 for row in rows if row["promotion_class"] == "review_only_hold"),
        "top_blocker_id": blocker_summary.get("top_blocker_id", ""),
        "top_blocker_signal": blocker_signal,
        "first_wave_target": wave_summary.get("first_wave_target", "AQP1"),
        "second_wave_target": wave_summary.get("second_wave_target", "GLUT1"),
        "today_seed_target": "AQP1 core_binder_01",
        "aqp1_seed_surface_count": sum(1 for row in rows if row["target_id"] == "AQP1" and row["row_kind"] == "binder"),
        "glut1_seed_surface_count": sum(1 for row in rows if row["target_id"] == "GLUT1" and row["row_kind"] == "binder"),
        "next_required_step": "Use AQP1 core_binder_01 as the first non-placeholder synchronized candidate-row target, keep the remaining AQP1 binders in the same first-wave board, keep GLUT1 binders second-wave, and leave all transporter negative rows review-only until quantitative negative evidence is curated.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Seed Row Promotion Board",
        "",
        f"- row_count: `{s['row_count']}`",
        f"- binder_row_count: `{s['binder_row_count']}`",
        f"- negative_row_count: `{s['negative_row_count']}`",
        f"- seed_now_count: `{s['seed_now_count']}`",
        f"- seed_after_aqp1_count: `{s['seed_after_aqp1_count']}`",
        f"- review_only_hold_count: `{s['review_only_hold_count']}`",
        f"- top_blocker_id: `{s['top_blocker_id']}`",
        f"- top_blocker_signal: `{s['top_blocker_signal']}`",
        f"- first_wave_target: `{s['first_wave_target']}`",
        f"- second_wave_target: `{s['second_wave_target']}`",
        f"- today_seed_target: `{s['today_seed_target']}`",
        f"- aqp1_seed_surface_count: `{s['aqp1_seed_surface_count']}`",
        f"- glut1_seed_surface_count: `{s['glut1_seed_surface_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Rows",
        "",
        "| priority_rank | target_id | wave | packet_step | row_kind | promotion_class | candidate_name | source_anchor | review_bucket | promotion_blocker | next_required_action | required_seed_fields | seed_packet_artifact | fill_draft_artifact | sync_preview_artifact | blocker_link |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['target_id']}` | `{row['wave']}` | `{row['packet_step']}` | `{row['row_kind']}` | "
            f"`{row['promotion_class']}` | `{row['candidate_name']}` | `{row['source_anchor']}` | `{row['review_bucket']}` | "
            f"`{row['promotion_blocker']}` | `{row['next_required_action']}` | `{row['required_seed_fields']}` | "
            f"`{row['seed_packet_artifact']}` | `{row['fill_draft_artifact']}` | `{row['sync_preview_artifact']}` | `{row['blocker_link']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a row-level board for transporter seed-row promotion after manual-verdict closure.")
    parser.add_argument("--aqp1-workbook-json", default=DEFAULT_AQP1_WORKBOOK_JSON)
    parser.add_argument("--glut1-workbook-json", default=DEFAULT_GLUT1_WORKBOOK_JSON)
    parser.add_argument("--aqp1-apply-draft-json", default=DEFAULT_AQP1_APPLY_DRAFT_JSON)
    parser.add_argument("--glut1-apply-draft-json", default=DEFAULT_GLUT1_APPLY_DRAFT_JSON)
    parser.add_argument("--aqp1-negative-packet-json", default=DEFAULT_AQP1_NEGATIVE_PACKET_JSON)
    parser.add_argument("--glut1-negative-packet-json", default=DEFAULT_GLUT1_NEGATIVE_PACKET_JSON)
    parser.add_argument("--wave-decision-json", default=DEFAULT_WAVE_DECISION_JSON)
    parser.add_argument("--blocker-json", default=DEFAULT_BLOCKER_JSON)
    parser.add_argument("--apply-status-json", default=DEFAULT_APPLY_STATUS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_workbook_json),
        _load_json(args.glut1_workbook_json),
        _load_json(args.aqp1_apply_draft_json),
        _load_json(args.glut1_apply_draft_json),
        _load_json(args.aqp1_negative_packet_json),
        _load_json(args.glut1_negative_packet_json),
        _load_json(args.wave_decision_json),
        _load_json(args.blocker_json),
        _load_json(args.apply_status_json),
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
