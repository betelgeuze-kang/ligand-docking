#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_AQP1_COMMIT_JSON = "runs/aqp1_manual_verdict_commit_packet_current.json"
DEFAULT_GLUT1_COMMIT_JSON = "runs/glut1_manual_verdict_commit_packet_current.json"
DEFAULT_LAUNCHBOARD_JSON = "runs/transporter_manual_review_launchboard_current.json"
DEFAULT_OUT_JSON = "runs/transporter_manual_verdict_confirmation_console_current.json"
DEFAULT_OUT_CSV = "runs/transporter_manual_verdict_confirmation_console_current.csv"
DEFAULT_OUT_MD = "runs/transporter_manual_verdict_confirmation_console_current.md"
GLUT1_SOURCE_CONFIRMATION_PACKET_MD = "runs/glut1_second_wave_source_confirmation_packet_current.md"


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
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _glut1_source_confirmation_handoff(launchboard_summary: dict[str, Any]) -> dict[str, Any]:
    packet_artifact = str(launchboard_summary.get("glut1_open_source_confirmation", "") or "").strip()
    ready = bool(launchboard_summary.get("glut1_second_wave_source_confirmation_ready", False))
    quickstart_rule = str(launchboard_summary.get("quickstart_rule", "") or "").strip()
    day2_rule = str(launchboard_summary.get("day2_rule", "") or "").strip()
    handoff_rule = quickstart_rule or day2_rule
    if not packet_artifact and ready:
        packet_artifact = GLUT1_SOURCE_CONFIRMATION_PACKET_MD
    if not handoff_rule and (ready or packet_artifact):
        handoff_rule = (
            f"When GLUT1 opens, keep {packet_artifact or GLUT1_SOURCE_CONFIRMATION_PACKET_MD} open, start with "
            f"{str(launchboard_summary.get('glut1_second_wave_source_confirmation_primary_focus_ligand', '') or 'cytochalasin B').strip() or 'cytochalasin B'}, "
            "keep WZB117 on the exact-target-pair functional lane, and keep STF-31 review-only with structured-pair caveats."
        )
    return {
        "open_source_confirmation": packet_artifact,
        "packet_artifact": packet_artifact,
        "second_wave_source_confirmation_ready": ready or bool(packet_artifact),
        "primary_focus_ligand": str(
            launchboard_summary.get("glut1_second_wave_source_confirmation_primary_focus_ligand", "") or ""
        ).strip(),
        "handoff_rule": handoff_rule,
        "direct_quantitative_binding_count": int(
            launchboard_summary.get("glut1_direct_quantitative_binding_count", 0) or 0
        ),
        "exact_target_pair_activity_count": int(
            launchboard_summary.get("glut1_exact_target_pair_activity_count", 0) or 0
        ),
        "structured_pair_absent_count": int(
            launchboard_summary.get("glut1_structured_pair_absent_count", 0) or 0
        ),
    }


def _normalize_rows(
    target_id: str,
    commit_packet_path: str,
    confirmation_card_path: str,
    rows: list[dict[str, Any]],
    glut1_source_confirmation: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        source_confirmation_packet = ""
        source_confirmation_primary_focus_ligand = ""
        source_confirmation_direct_quantitative_binding_count = 0
        source_confirmation_exact_target_pair_activity_count = 0
        source_confirmation_structured_pair_absent_count = 0
        if target_id == "GLUT1" and glut1_source_confirmation:
            source_confirmation_packet = str(glut1_source_confirmation.get("open_source_confirmation", "")).strip()
            source_confirmation_primary_focus_ligand = str(
                glut1_source_confirmation.get("primary_focus_ligand", "")
            ).strip()
            source_confirmation_direct_quantitative_binding_count = int(
                glut1_source_confirmation.get("direct_quantitative_binding_count", 0) or 0
            )
            source_confirmation_exact_target_pair_activity_count = int(
                glut1_source_confirmation.get("exact_target_pair_activity_count", 0) or 0
            )
            source_confirmation_structured_pair_absent_count = int(
                glut1_source_confirmation.get("structured_pair_absent_count", 0) or 0
            )
        out.append(
            {
                "target_id": target_id,
                "priority_rank": str(row.get("priority_rank", "")).strip(),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "candidate_name": str(row.get("candidate_name", "")).strip(),
                "commit_packet": commit_packet_path,
                "confirmation_card": confirmation_card_path,
                "open_source_confirmation": source_confirmation_packet,
                "source_confirmation_primary_focus_ligand": source_confirmation_primary_focus_ligand,
                "source_confirmation_direct_quantitative_binding_count": source_confirmation_direct_quantitative_binding_count,
                "source_confirmation_exact_target_pair_activity_count": source_confirmation_exact_target_pair_activity_count,
                "source_confirmation_structured_pair_absent_count": source_confirmation_structured_pair_absent_count,
                "staged_verdict": str(row.get("commit_value_verdict", row.get("staged_manual_verdict", ""))).strip(),
                "staged_confidence": str(row.get("commit_value_confidence", row.get("staged_manual_confidence_update", ""))).strip(),
                "promotion_blocker": str(row.get("stop_condition", row.get("promotion_blocker", ""))).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "note_preview": str(row.get("commit_value_note", row.get("staged_manual_decision_note", ""))).strip(),
                "manual_verdict_update": str(row.get("manual_verdict_update", "")).strip(),
                "manual_confidence_update": str(row.get("manual_confidence_update", "")).strip(),
                "manual_decision_note": str(row.get("manual_decision_note", "")).strip(),
                "update_status": str(row.get("update_status", "pending_manual_verdict")).strip(),
            }
        )
    return out


def build_payload(
    aqp1_commit_packet: dict[str, Any],
    glut1_commit_packet: dict[str, Any],
    launchboard: dict[str, Any],
) -> dict[str, Any]:
    launchboard_summary = dict(launchboard.get("summary", {}) or {})
    glut1_source_confirmation = _glut1_source_confirmation_handoff(launchboard_summary)
    aqp1_rows = _normalize_rows(
        "AQP1",
        "runs/aqp1_manual_verdict_commit_packet_current.md",
        "runs/aqp1_binder_confirmation_card_current.md",
        list(aqp1_commit_packet.get("rows", []) or []),
    )
    glut1_rows = _normalize_rows(
        "GLUT1",
        "runs/glut1_manual_verdict_commit_packet_current.md",
        "runs/glut1_binder_confirmation_card_current.md",
        list(glut1_commit_packet.get("rows", []) or []),
        glut1_source_confirmation,
    )
    rows = aqp1_rows + glut1_rows

    summary = {
        "target_count": 2,
        "row_count": len(rows),
        "pending_manual_verdict_count": sum(1 for row in rows if row["update_status"] == "pending_manual_verdict"),
        "completed_manual_verdict_count": sum(1 for row in rows if row["update_status"] != "pending_manual_verdict"),
        "aqp1_commit_ready_count": int(aqp1_commit_packet.get("summary", {}).get("commit_ready_count", 0) or 0),
        "glut1_commit_ready_count": int(glut1_commit_packet.get("summary", {}).get("staged_confirmation_count", 0) or 0),
        "today_open_now": "runs/aqp1_manual_verdict_commit_packet_current.md",
        "today_open_card": "runs/aqp1_binder_confirmation_card_current.md",
        "today_open_now_label": launchboard_summary.get("today_open_now_label", ""),
        "next_wave_packet": "runs/glut1_manual_verdict_commit_packet_current.md",
        "next_wave_card": "runs/glut1_binder_confirmation_card_current.md",
        "glut1_open_source_confirmation": glut1_source_confirmation["open_source_confirmation"],
        "glut1_second_wave_source_confirmation_packet_artifact": glut1_source_confirmation["packet_artifact"],
        "glut1_second_wave_source_confirmation_ready": glut1_source_confirmation["second_wave_source_confirmation_ready"],
        "glut1_second_wave_source_confirmation_primary_focus_ligand": glut1_source_confirmation["primary_focus_ligand"],
        "glut1_second_wave_source_confirmation_handoff_rule": glut1_source_confirmation["handoff_rule"],
        "glut1_direct_quantitative_binding_count": glut1_source_confirmation["direct_quantitative_binding_count"],
        "glut1_exact_target_pair_activity_count": glut1_source_confirmation["exact_target_pair_activity_count"],
        "glut1_structured_pair_absent_count": glut1_source_confirmation["structured_pair_absent_count"],
        "next_required_step": (
            "Confirm AQP1 commit rows first, then move to GLUT1 commit rows only after the AQP1 first-wave binder and negative packet path is exhausted."
            + (
                f" {glut1_source_confirmation['handoff_rule']}"
                if glut1_source_confirmation["second_wave_source_confirmation_ready"]
                else ""
            )
            if any(row["update_status"] == "pending_manual_verdict" for row in rows)
            else "Treat this console as an audit surface only; AQP1 and GLUT1 reviewer-side commit rows are already filled, but transporter authoritative apply remains blocked."
            + (
                f" Keep {glut1_source_confirmation['packet_artifact'] or GLUT1_SOURCE_CONFIRMATION_PACKET_MD} attached to the GLUT1 handoff with {glut1_source_confirmation['primary_focus_ligand'] or 'cytochalasin B'} as the lead reference, WZB117 on the exact-target-pair lane, and STF-31 as the structured-pair caveat."
                if glut1_source_confirmation["second_wave_source_confirmation_ready"]
                else ""
            )
        ),
    }
    checklist = [
        "Open the AQP1 commit packet first.",
        "Confirm only manual_verdict_update, manual_confidence_update, and manual_decision_note fields.",
        "Keep all transporter rows non-authoritative even after manual confirmation.",
        (
            f"Move to the GLUT1 commit packet only after the AQP1 first-wave path is exhausted, and keep {glut1_source_confirmation['packet_artifact'] or GLUT1_SOURCE_CONFIRMATION_PACKET_MD} open with {glut1_source_confirmation['primary_focus_ligand'] or 'cytochalasin B'} as the second-wave source-confirmation lead, WZB117 on the exact-target-pair lane, and STF-31 review-only with structured-pair caveats."
            if glut1_source_confirmation["second_wave_source_confirmation_ready"]
            else "Move to the GLUT1 commit packet only after the AQP1 first-wave path is exhausted."
        ),
    ]
    return {"summary": summary, "checklist": checklist, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Manual Verdict Confirmation Console",
        "",
        f"- target_count: `{s['target_count']}`",
        f"- row_count: `{s['row_count']}`",
        f"- pending_manual_verdict_count: `{s['pending_manual_verdict_count']}`",
        f"- completed_manual_verdict_count: `{s['completed_manual_verdict_count']}`",
        f"- aqp1_commit_ready_count: `{s['aqp1_commit_ready_count']}`",
        f"- glut1_commit_ready_count: `{s['glut1_commit_ready_count']}`",
        f"- glut1_open_source_confirmation: `{s['glut1_open_source_confirmation']}`",
        f"- glut1_second_wave_source_confirmation_ready: `{s['glut1_second_wave_source_confirmation_ready']}`",
        f"- glut1_second_wave_source_confirmation_primary_focus_ligand: `{s['glut1_second_wave_source_confirmation_primary_focus_ligand']}`",
        f"- glut1_direct_quantitative_binding_count: `{s['glut1_direct_quantitative_binding_count']}`",
        f"- glut1_exact_target_pair_activity_count: `{s['glut1_exact_target_pair_activity_count']}`",
        f"- glut1_structured_pair_absent_count: `{s['glut1_structured_pair_absent_count']}`",
        "",
        "## Open Now",
        "",
        f"- Packet: `{s['today_open_now']}`",
        f"- Confirmation card: `{s['today_open_card']}`",
        f"- Start label: `{s['today_open_now_label']}`",
        f"- Next wave packet: `{s['next_wave_packet']}`",
        f"- Next wave card: `{s['next_wave_card']}`",
        f"- GLUT1 source confirmation: `{s['glut1_open_source_confirmation']}`",
        "",
        "## Checklist",
        "",
    ]
    for item in payload["checklist"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Confirmation Rows",
            "",
            "| target_id | priority_rank | candidate_name | staged_verdict | staged_confidence | promotion_blocker | update_status | confirmation_card | open_source_confirmation | commit_packet |",
            "| --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | {row['priority_rank']} | `{row['candidate_name']}` | "
            f"`{row['staged_verdict']}` | `{row['staged_confidence']}` | `{row['promotion_blocker']}` | "
            f"`{row['update_status']}` | `{row['confirmation_card']}` | `{row['open_source_confirmation']}` | `{row['commit_packet']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a single confirmation console across AQP1/GLUT1 transporter commit packets.")
    parser.add_argument("--aqp1-commit-json", default=DEFAULT_AQP1_COMMIT_JSON)
    parser.add_argument("--glut1-commit-json", default=DEFAULT_GLUT1_COMMIT_JSON)
    parser.add_argument("--launchboard-json", default=DEFAULT_LAUNCHBOARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_commit_json),
        _load_json(args.glut1_commit_json),
        _load_json(args.launchboard_json),
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
