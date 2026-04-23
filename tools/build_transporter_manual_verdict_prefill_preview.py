#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AQP1_BINDER_SHEET_JSON = "runs/aqp1_binder_verdict_update_sheet_current.json"
DEFAULT_GLUT1_BINDER_SHEET_JSON = "runs/glut1_binder_verdict_update_sheet_current.json"
DEFAULT_OUT_JSON = "runs/transporter_manual_verdict_prefill_preview_current.json"
DEFAULT_OUT_CSV = "runs/transporter_manual_verdict_prefill_preview_current.csv"
DEFAULT_OUT_MD = "runs/transporter_manual_verdict_prefill_preview_current.md"
GLUT1_SOURCE_CONFIRMATION_PACKET_MD = "runs/glut1_second_wave_source_confirmation_packet_current.md"
GLUT1_SOURCE_CONFIRMATION_LEAD = "cytochalasin B"
GLUT1_SOURCE_CONFIRMATION_EXACT_TARGET_PAIR_FUNCTIONAL_LIGAND = "WZB117"
GLUT1_SOURCE_CONFIRMATION_STRUCTURED_PAIR_CAVEAT_LIGAND = "STF-31"


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


def _glut1_source_confirmation_handoff(target_id: str, packet_step: str) -> dict[str, str]:
    if target_id != "GLUT1":
        return {
            "source_confirmation_packet_artifact": "",
            "source_confirmation_handoff_lane": "",
            "source_confirmation_review_note": "",
        }
    lane_by_step = {
        "core_binder_01": (
            "lead",
            f"Keep {GLUT1_SOURCE_CONFIRMATION_LEAD} as the review-only GLUT1 second-wave source-confirmation lead.",
        ),
        "core_binder_02": (
            "exact-target-pair functional lane",
            "Keep WZB117 as the review-only exact-target-pair functional lane in the GLUT1 source-confirmation handoff.",
        ),
        "core_binder_03": (
            "structured-pair caveat",
            "Keep STF-31 as the review-only structured-pair caveat in the GLUT1 source-confirmation handoff.",
        ),
    }
    lane, review_note = lane_by_step.get(
        packet_step,
        (
            "review-only handoff context",
            "Keep this GLUT1 row inside the review-only source-confirmation handoff until a reviewer confirms stronger transporter-specific evidence.",
        ),
    )
    return {
        "source_confirmation_packet_artifact": GLUT1_SOURCE_CONFIRMATION_PACKET_MD,
        "source_confirmation_handoff_lane": lane,
        "source_confirmation_review_note": review_note,
    }


def _collect_rows(sheet_payload: dict[str, Any]) -> list[dict[str, Any]]:
    preview_rows: list[dict[str, Any]] = []
    for row in sheet_payload.get("sheet_rows", []) or []:
        target_id = str(row.get("target_id", "")).strip()
        packet_step = str(row.get("packet_step", "")).strip()
        source_confirmation = _glut1_source_confirmation_handoff(target_id, packet_step)
        preview_rows.append(
            {
                "target_id": target_id,
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": packet_step,
                "candidate_name": str(row.get("candidate_name", "")).strip(),
                "prefill_verdict": str(row.get("suggested_manual_verdict", "")).strip(),
                "prefill_confidence": str(row.get("suggested_manual_confidence_update", "")).strip(),
                "prefill_decision_note": str(row.get("suggested_manual_decision_note", "")).strip(),
                "requires_human_confirm": "yes",
                "source_anchor": str(row.get("source_anchor", "")).strip(),
                "update_status": str(row.get("update_status", "")).strip(),
                "source_confirmation_packet_artifact": source_confirmation["source_confirmation_packet_artifact"],
                "source_confirmation_handoff_lane": source_confirmation["source_confirmation_handoff_lane"],
                "source_confirmation_review_note": source_confirmation["source_confirmation_review_note"],
            }
        )
    return preview_rows


def build_payload(aqp1_sheet: dict[str, Any], glut1_sheet: dict[str, Any]) -> dict[str, Any]:
    rows = _collect_rows(aqp1_sheet) + _collect_rows(glut1_sheet)
    has_glut1_rows = any(row["target_id"] == "GLUT1" for row in rows)
    summary = {
        "preview_row_count": len(rows),
        "aqp1_preview_count": sum(1 for row in rows if row["target_id"] == "AQP1"),
        "glut1_preview_count": sum(1 for row in rows if row["target_id"] == "GLUT1"),
        "requires_human_confirm_count": sum(1 for row in rows if row["requires_human_confirm"] == "yes"),
        "glut1_second_wave_source_confirmation_packet_artifact": GLUT1_SOURCE_CONFIRMATION_PACKET_MD if has_glut1_rows else "",
        "glut1_second_wave_source_confirmation_primary_focus_ligand": GLUT1_SOURCE_CONFIRMATION_LEAD if has_glut1_rows else "",
        "glut1_second_wave_source_confirmation_exact_target_pair_functional_ligand": (
            GLUT1_SOURCE_CONFIRMATION_EXACT_TARGET_PAIR_FUNCTIONAL_LIGAND if has_glut1_rows else ""
        ),
        "glut1_second_wave_source_confirmation_structured_pair_caveat_ligand": (
            GLUT1_SOURCE_CONFIRMATION_STRUCTURED_PAIR_CAVEAT_LIGAND if has_glut1_rows else ""
        ),
        "next_required_step": (
            "Use this preview as a reviewer convenience layer only. Manual_verdict_update and manual_decision_note still need explicit human confirmation in the source sheets. "
            f"For GLUT1, keep `{GLUT1_SOURCE_CONFIRMATION_PACKET_MD}` open with "
            f"{GLUT1_SOURCE_CONFIRMATION_LEAD} as the lead, "
            f"{GLUT1_SOURCE_CONFIRMATION_EXACT_TARGET_PAIR_FUNCTIONAL_LIGAND} as the exact-target-pair functional lane, "
            f"and {GLUT1_SOURCE_CONFIRMATION_STRUCTURED_PAIR_CAVEAT_LIGAND} as the structured-pair caveat."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Manual Verdict Prefill Preview",
        "",
        f"- preview_row_count: `{s['preview_row_count']}`",
        f"- aqp1_preview_count: `{s['aqp1_preview_count']}`",
        f"- glut1_preview_count: `{s['glut1_preview_count']}`",
        f"- requires_human_confirm_count: `{s['requires_human_confirm_count']}`",
    ]
    if s.get("glut1_second_wave_source_confirmation_packet_artifact"):
        lines.extend(
            [
                f"- glut1_second_wave_source_confirmation_packet_artifact: `{s['glut1_second_wave_source_confirmation_packet_artifact']}`",
                f"- glut1_second_wave_source_confirmation_primary_focus_ligand: `{s['glut1_second_wave_source_confirmation_primary_focus_ligand']}`",
                f"- glut1_second_wave_source_confirmation_exact_target_pair_functional_ligand: `{s['glut1_second_wave_source_confirmation_exact_target_pair_functional_ligand']}`",
                f"- glut1_second_wave_source_confirmation_structured_pair_caveat_ligand: `{s['glut1_second_wave_source_confirmation_structured_pair_caveat_ligand']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            f"- {s['next_required_step']}",
            "",
            "## Preview Rows",
            "",
            "| target_id | priority_rank | packet_step | candidate_name | prefill_verdict | prefill_confidence | source_confirmation_handoff_lane | requires_human_confirm |",
            "| --- | ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| {row['target_id']} | {row['priority_rank']} | `{row['packet_step']}` | "
            f"`{row['candidate_name']}` | `{row['prefill_verdict']}` | `{row['prefill_confidence']}` | "
            f"`{row['source_confirmation_handoff_lane'] or '-'}` | `{row['requires_human_confirm']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a combined transporter manual verdict prefill preview.")
    parser.add_argument("--aqp1-binder-sheet-json", default=DEFAULT_AQP1_BINDER_SHEET_JSON)
    parser.add_argument("--glut1-binder-sheet-json", default=DEFAULT_GLUT1_BINDER_SHEET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_binder_sheet_json),
        _load_json(args.glut1_binder_sheet_json),
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
