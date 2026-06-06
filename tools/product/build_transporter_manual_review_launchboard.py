#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.product.transporter_phase_helpers import aqp1_follow_on_seed_steps

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_QUICKSTART_JSON = "runs/transporter_manual_review_quickstart_packet_current.json"
DEFAULT_OPERATOR_CONSOLE_JSON = "runs/transporter_operator_console_current.json"
DEFAULT_REVIEWER_DAY2_CONSOLE_JSON = "runs/transporter_reviewer_day2_console_current.json"
DEFAULT_MANUAL_REVIEW_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_MANUAL_VERDICT_PACKETS_JSON = "runs/transporter_manual_verdict_packets_current.json"
DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_OUT_JSON = "runs/transporter_manual_review_launchboard_current.json"
DEFAULT_OUT_CSV = "runs/transporter_manual_review_launchboard_current.csv"
DEFAULT_OUT_MD = "runs/transporter_manual_review_launchboard_current.md"


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


def _aqp1_packet(manual_verdict_packets: dict[str, Any]) -> dict[str, Any]:
    for packet in manual_verdict_packets.get("target_packets", []) or []:
        if str(packet.get("target_id", "")).strip() == "AQP1":
            return dict(packet)
    return {}


def _follow_on_blocker_decomposition_artifact(summary: dict[str, Any]) -> str:
    return str(
        summary.get("aqp1_open_follow_on_blocker_decomposition")
        or summary.get("aqp1_follow_on_blocker_decomposition_artifact")
        or summary.get("today_open_follow_on_blocker_decomposition")
        or summary.get("follow_on_blocker_decomposition_artifact")
        or ""
    ).strip()


def build_payload(
    quickstart: dict[str, Any],
    operator_console: dict[str, Any],
    reviewer_day2_console: dict[str, Any],
    manual_review_dashboard: dict[str, Any],
    manual_verdict_packets: dict[str, Any],
    transporter_seed_row_board: dict[str, Any],
) -> dict[str, Any]:
    aqp1_packet = _aqp1_packet(manual_verdict_packets)
    aqp1_follow_on_steps = aqp1_follow_on_seed_steps(transporter_seed_row_board)
    day2_rows = list(reviewer_day2_console.get("rows", []) or [])
    operator_summary = dict(operator_console.get("summary", {}) or {})
    aqp1_follow_on_blocker_decomposition_artifact = _follow_on_blocker_decomposition_artifact(operator_summary)
    aqp1_follow_on_blocker_decomposition_ready = bool(aqp1_follow_on_blocker_decomposition_artifact)
    aqp1_follow_on_blocker_decomposition_next_required_step = str(
        operator_summary.get("aqp1_follow_on_blocker_decomposition_next_required_step", "") or ""
    ).strip()
    aqp1_follow_on_blocker_decomposition_row_count = int(
        operator_summary.get("aqp1_follow_on_blocker_decomposition_row_count", 0) or 0
    )
    aqp1_follow_on_blocker_decomposition_follow_on_targets = str(
        operator_summary.get("aqp1_follow_on_blocker_decomposition_follow_on_targets", "") or ""
    ).strip()
    aqp1_follow_on_blocker_decomposition_primary_focus_ligand = str(
        operator_summary.get("aqp1_follow_on_blocker_decomposition_primary_focus_ligand", "") or ""
    ).strip()
    aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand = str(
        operator_summary.get("aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand", "") or ""
    ).strip()
    aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count = int(
        operator_summary.get("aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count", 0) or 0
    )
    aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count = int(
        operator_summary.get("aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count", 0) or 0
    )
    aqp1_primary_probe_resolution_artifact = str(
        operator_summary.get("aqp1_negative_primary_probe_resolution_artifact", "") or ""
    ).strip()
    aqp1_primary_probe_resolution_candidate = str(
        operator_summary.get("aqp1_negative_primary_probe_resolution_candidate", "") or ""
    ).strip()
    aqp1_primary_probe_resolution_decision = str(
        operator_summary.get("aqp1_negative_primary_probe_resolution_decision", "") or ""
    ).strip()
    aqp1_primary_probe_resolution_solvent_fallback_candidate = str(
        operator_summary.get("aqp1_negative_primary_probe_resolution_solvent_fallback_candidate", "") or ""
    ).strip()
    aqp1_primary_probe_resolution_handoff = (
        f" Keep `{aqp1_primary_probe_resolution_artifact}` ready so "
        f"`{aqp1_primary_probe_resolution_candidate or 'sodium nitroprusside'}` stays review-only while "
        f"`{aqp1_primary_probe_resolution_solvent_fallback_candidate or 'dimethyl sulfoxide'}` stays solvent-only at decision "
        f"`{aqp1_primary_probe_resolution_decision or 'keep_review_only_no_authoritative_negative_promotion'}`."
        if aqp1_primary_probe_resolution_artifact
        else ""
    )
    binder_pending_manual_verdict_count = int(
        operator_summary.get("binder_pending_manual_verdict_count", 0) or 0
    )
    stage_rows: list[dict[str, Any]] = []
    for row in day2_rows:
        review_mode = str(row.get("review_mode", "")).strip()
        if binder_pending_manual_verdict_count == 0:
            if review_mode == "binder_review" or review_mode == "seed_row_packet":
                review_mode = "seed_row_promotion"
            elif review_mode == "seed_row_sync_preview":
                review_mode = "sync_stage_preview"
            elif review_mode == "negative_review":
                review_mode = "negative_blocker_closure"
        stage_rows.append(
            {
                "stage_order": int(row.get("stage_order", 0) or 0),
                "target_id": str(row.get("target_id", "")).strip(),
                "review_mode": review_mode,
                "open_packet": str(row.get("open_packet", "")).strip(),
                "pending_count": int(row.get("pending_count", 0) or 0),
                "start_label": str(row.get("start_label", "")).strip(),
                "open_after_exhausted": str(row.get("open_after_exhausted", "")).strip(),
            }
        )

    summary = {
        "target_count": int(quickstart.get("summary", {}).get("target_count", 0) or 0),
        "first_wave_target": str(quickstart.get("summary", {}).get("first_wave_target", "")).strip(),
        "second_wave_target": str(quickstart.get("summary", {}).get("second_wave_target", "")).strip(),
        "current_phase": (
            "manual_verdict_burndown"
            if binder_pending_manual_verdict_count > 0
            else "blocker_closure_seed_row_promotion"
        ),
        "binder_pending_manual_verdict_count": binder_pending_manual_verdict_count,
        "negative_slot_count_total": int(manual_review_dashboard.get("summary", {}).get("negative_slot_count_total", 0) or 0),
        "today_open_now": str(day2_rows[0].get("open_packet", "")).strip() if day2_rows else "",
        "today_open_now_label": str(day2_rows[0].get("start_label", "")).strip() if day2_rows else "",
        "today_open_source_confirmation": str(
            operator_summary.get("aqp1_open_source_confirmation", "")
        ).strip(),
        "today_open_provenance": str(
            operator_summary.get("aqp1_open_provenance", "")
        ).strip(),
        "today_open_follow_on": str(
            operator_summary.get("aqp1_open_follow_on", "")
        ).strip(),
        "glut1_open_source_confirmation": str(
            operator_summary.get("glut1_open_source_confirmation", "")
        ).strip(),
        "glut1_second_wave_source_confirmation_ready": bool(
            operator_summary.get("glut1_second_wave_source_confirmation_ready", False)
        ),
        "glut1_second_wave_source_confirmation_primary_focus_ligand": str(
            operator_summary.get("glut1_second_wave_source_confirmation_primary_focus_ligand", "") or ""
        ).strip(),
        "glut1_direct_quantitative_binding_count": int(
            operator_summary.get("glut1_direct_quantitative_binding_count", 0) or 0
        ),
        "glut1_exact_target_pair_activity_count": int(
            operator_summary.get("glut1_exact_target_pair_activity_count", 0) or 0
        ),
        "glut1_structured_pair_absent_count": int(
            operator_summary.get("glut1_structured_pair_absent_count", 0) or 0
        ),
        "today_open_follow_on_blocker_decomposition": aqp1_follow_on_blocker_decomposition_artifact,
        "today_open_follow_on_blocker_decomposition_ready": aqp1_follow_on_blocker_decomposition_ready,
        "aqp1_follow_on_blocker_decomposition_artifact": aqp1_follow_on_blocker_decomposition_artifact,
        "aqp1_follow_on_blocker_decomposition_ready": aqp1_follow_on_blocker_decomposition_ready,
        "aqp1_follow_on_blocker_decomposition_row_count": aqp1_follow_on_blocker_decomposition_row_count,
        "aqp1_follow_on_blocker_decomposition_follow_on_targets": aqp1_follow_on_blocker_decomposition_follow_on_targets,
        "aqp1_follow_on_blocker_decomposition_primary_focus_ligand": aqp1_follow_on_blocker_decomposition_primary_focus_ligand,
        "aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand": aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand,
        "aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count": aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count,
        "aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count": aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count,
        "aqp1_follow_on_blocker_decomposition_next_required_step": aqp1_follow_on_blocker_decomposition_next_required_step,
        "aqp1_negative_primary_probe_resolution_ready": bool(aqp1_primary_probe_resolution_artifact),
        "aqp1_negative_primary_probe_resolution_artifact": aqp1_primary_probe_resolution_artifact,
        "aqp1_negative_primary_probe_resolution_candidate": aqp1_primary_probe_resolution_candidate,
        "aqp1_negative_primary_probe_resolution_decision": aqp1_primary_probe_resolution_decision,
        "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": aqp1_primary_probe_resolution_solvent_fallback_candidate,
        "today_finish_line": (
            f"Finish the {int(aqp1_packet.get('pending_manual_verdict_count', 0) or 0)} AQP1 binder manual verdict rows, "
            "then advance into the AQP1 negative review packet only if those binder rows are exhausted."
            if binder_pending_manual_verdict_count > 0
            else (
                "Manual-verdict backlog is cleared. Use AQP1 first to stage the first non-authoritative seed-row blocker-closure path and keep AqB013 provenance visible."
                + (
                    f" Keep `{aqp1_follow_on_blocker_decomposition_artifact}` open as the AQP1 follow-on blocker decomposition surface."
                    if aqp1_follow_on_blocker_decomposition_artifact
                    else ""
                )
                + (
                    f" Follow its next step: {aqp1_follow_on_blocker_decomposition_next_required_step}."
                    if aqp1_follow_on_blocker_decomposition_next_required_step
                    else ""
                )
                + (
                    f" Then use `{operator_summary.get('aqp1_open_follow_on', '').strip()}` to continue {', '.join(aqp1_follow_on_steps)} before touching GLUT1."
                    if aqp1_follow_on_steps and str(operator_summary.get("aqp1_open_follow_on", "")).strip()
                    else f" Then continue {', '.join(aqp1_follow_on_steps)} before touching GLUT1."
                    if aqp1_follow_on_steps
                    else " Then continue to GLUT1 only after the AQP1 first-wave lane is exhausted."
                )
                + aqp1_primary_probe_resolution_handoff
                + (
                    f" When GLUT1 opens, keep `{operator_summary.get('glut1_open_source_confirmation', 'runs/glut1_second_wave_source_confirmation_packet_current.md')}` open and start with "
                    f"{operator_summary.get('glut1_second_wave_source_confirmation_primary_focus_ligand', 'cytochalasin B')}."
                    if operator_summary.get("glut1_second_wave_source_confirmation_ready")
                    else ""
                )
            )
        ).strip(),
        "aqp1_follow_on_seed_targets": ", ".join(aqp1_follow_on_steps),
        "console_rule": str(operator_summary.get("console_rule", "")).strip(),
        "quickstart_rule": str(quickstart.get("summary", {}).get("next_required_step", "")).strip(),
        "day2_rule": str(reviewer_day2_console.get("summary", {}).get("next_required_step", "")).strip(),
    }
    if binder_pending_manual_verdict_count > 0:
        checklist = [
            f"Open `{summary['today_open_now']}` first.",
            f"Start at `{summary['today_open_now_label']}`.",
            "Do not skip ahead to GLUT1 before the AQP1 binder packet is exhausted.",
            "Do not reopen donor policy or authoritative apply from this launchboard.",
            "Only move to the next packet when the current packet's exhaustion rule is satisfied.",
        ]
    else:
        checklist = [
            f"Open `{summary['today_open_now']}` first.",
            f"Start at `{summary['today_open_now_label']}`.",
            "Treat AQP1 as the first transporter seed-row blocker-closure target and keep GLUT1 as second-wave blocker-closure follow-up.",
            (
                f"Keep `{summary['today_open_source_confirmation']}` open as the bacopaside II exact-source scope packet."
                if summary["today_open_source_confirmation"]
                else "Keep the bacopaside II exact-source scope packet open while working the first-wave seed row."
            ),
            (
                f"Keep `{summary['today_open_provenance']}` open as the AqB013 exact-human-activity guardrail."
                if summary["today_open_provenance"]
                else "Keep the AqB013 exact-human-activity provenance lane open as a guardrail."
            ),
            (
                f"Keep `{summary['today_open_follow_on']}` open as the AQP1 follow-on packet for `{', '.join(aqp1_follow_on_steps)}`."
                if summary["today_open_follow_on"] and aqp1_follow_on_steps
                else "Keep the AQP1 follow-on packet ready for core_binder_02/core_binder_03 after core_binder_01 is exhausted."
            ),
            (
                f"Keep `{summary['today_open_follow_on_blocker_decomposition']}` open as the AQP1 follow-on blocker decomposition surface."
                if summary["today_open_follow_on_blocker_decomposition"]
                else "Keep the AQP1 follow-on blocker decomposition surface open if it is available."
            ),
            (
                f"Keep `{summary['aqp1_negative_primary_probe_resolution_artifact']}` ready so `{summary['aqp1_negative_primary_probe_resolution_candidate'] or 'sodium nitroprusside'}` stays review-only while `{summary['aqp1_negative_primary_probe_resolution_solvent_fallback_candidate'] or 'dimethyl sulfoxide'}` stays solvent-only at decision `{summary['aqp1_negative_primary_probe_resolution_decision'] or 'keep_review_only_no_authoritative_negative_promotion'}`."
                if summary["aqp1_negative_primary_probe_resolution_artifact"]
                else "Keep the AQP1 primary-probe resolution handoff ready if the negative-evidence packet surface is available."
            ),
            (
                f"After core_binder_01, continue `{', '.join(aqp1_follow_on_steps)}` through the transporter seed-row blocker-closure board."
                if aqp1_follow_on_steps
                else "After core_binder_01, keep any follow-on AQP1 seed rows inside the transporter seed-row blocker-closure board."
            ),
            (
                f"When GLUT1 opens, keep `{summary['glut1_open_source_confirmation']}` open and start with `{summary['glut1_second_wave_source_confirmation_primary_focus_ligand'] or 'cytochalasin B'}`."
                if summary["glut1_second_wave_source_confirmation_ready"]
                else "When GLUT1 opens, keep the second-wave source-confirmation packet open and start with cytochalasin B."
            ),
            "Do not skip ahead to GLUT1 before the AQP1 first-wave blocker-closure work is exhausted.",
            "Use this launchboard for seed-row blocker closure, not for new manual-verdict wording work.",
            "Do not reopen donor policy or authoritative apply from this launchboard.",
        ]
    return {"summary": summary, "checklist": checklist, "rows": stage_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Manual-Review Launchboard",
        "",
        f"- target_count: `{s['target_count']}`",
        f"- first_wave_target: `{s['first_wave_target']}`",
        f"- second_wave_target: `{s['second_wave_target']}`",
        f"- current_phase: `{s['current_phase']}`",
        f"- binder_pending_manual_verdict_count: `{s['binder_pending_manual_verdict_count']}`",
        f"- negative_slot_count_total: `{s['negative_slot_count_total']}`",
        f"- aqp1_follow_on_seed_targets: `{s['aqp1_follow_on_seed_targets']}`",
        f"- today_open_source_confirmation: `{s['today_open_source_confirmation']}`",
        f"- today_open_provenance: `{s['today_open_provenance']}`",
        f"- today_open_follow_on: `{s['today_open_follow_on']}`",
        f"- glut1_open_source_confirmation: `{s['glut1_open_source_confirmation']}`",
        f"- glut1_second_wave_source_confirmation_ready: `{s['glut1_second_wave_source_confirmation_ready']}`",
        f"- glut1_second_wave_source_confirmation_primary_focus_ligand: `{s['glut1_second_wave_source_confirmation_primary_focus_ligand']}`",
        f"- glut1_direct_quantitative_binding_count: `{s['glut1_direct_quantitative_binding_count']}`",
        f"- glut1_exact_target_pair_activity_count: `{s['glut1_exact_target_pair_activity_count']}`",
        f"- glut1_structured_pair_absent_count: `{s['glut1_structured_pair_absent_count']}`",
        f"- today_open_follow_on_blocker_decomposition: `{s['today_open_follow_on_blocker_decomposition']}`",
        f"- aqp1_negative_primary_probe_resolution_ready: `{s['aqp1_negative_primary_probe_resolution_ready']}`",
        f"- aqp1_negative_primary_probe_resolution_artifact: `{s['aqp1_negative_primary_probe_resolution_artifact']}`",
        f"- aqp1_negative_primary_probe_resolution_candidate: `{s['aqp1_negative_primary_probe_resolution_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_decision: `{s['aqp1_negative_primary_probe_resolution_decision']}`",
        f"- aqp1_negative_primary_probe_resolution_solvent_fallback_candidate: `{s['aqp1_negative_primary_probe_resolution_solvent_fallback_candidate']}`",
        "",
        "## Open Now",
        "",
        f"- Packet: `{s['today_open_now']}`",
        f"- Start label: `{s['today_open_now_label']}`",
        f"- Source confirmation: `{s['today_open_source_confirmation']}`",
        f"- Provenance guardrail: `{s['today_open_provenance']}`",
        f"- Follow-on packet: `{s['today_open_follow_on']}`",
        f"- GLUT1 source confirmation: `{s['glut1_open_source_confirmation']}`",
        f"- Follow-on blocker decomposition: `{s['today_open_follow_on_blocker_decomposition']}`",
        f"- Primary-probe resolution: `{s['aqp1_negative_primary_probe_resolution_artifact']}`",
        "",
        "## Today's Finish Line",
        "",
        f"- {s['today_finish_line']}",
        "",
        "## Rules",
        "",
        f"- Console rule: {s['console_rule']}",
        f"- Quickstart rule: {s['quickstart_rule']}",
        f"- Day-2 rule: {s['day2_rule']}",
        "",
        "## Checklist",
        "",
    ]
    for item in payload["checklist"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Strict Opening Order",
            "",
            "| stage_order | target_id | review_mode | open_packet | pending_count | start_label | open_after_exhausted |",
            "| ---: | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| {row['stage_order']} | `{row['target_id']}` | `{row['review_mode']}` | `{row['open_packet']}` | "
            f"{row['pending_count']} | `{row['start_label']}` | `{row['open_after_exhausted']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a top-level transporter manual-review launchboard.")
    parser.add_argument("--quickstart-json", default=DEFAULT_QUICKSTART_JSON)
    parser.add_argument("--operator-console-json", default=DEFAULT_OPERATOR_CONSOLE_JSON)
    parser.add_argument("--reviewer-day2-console-json", default=DEFAULT_REVIEWER_DAY2_CONSOLE_JSON)
    parser.add_argument("--manual-review-dashboard-json", default=DEFAULT_MANUAL_REVIEW_DASHBOARD_JSON)
    parser.add_argument("--manual-verdict-packets-json", default=DEFAULT_MANUAL_VERDICT_PACKETS_JSON)
    parser.add_argument("--transporter-seed-row-board-json", default=DEFAULT_TRANSPORTER_SEED_ROW_BOARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.quickstart_json),
        _load_json(args.operator_console_json),
        _load_json(args.reviewer_day2_console_json),
        _load_json(args.manual_review_dashboard_json),
        _load_json(args.manual_verdict_packets_json),
        _load_json(args.transporter_seed_row_board_json),
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
