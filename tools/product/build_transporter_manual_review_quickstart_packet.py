#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DASHBOARD_JSON = "runs/transporter_manual_review_dashboard_current.json"
DEFAULT_BINDER_LEDGER_JSON = "runs/transporter_binder_slot_ledger_current.json"
DEFAULT_NEGATIVE_DAY_PLAN_JSON = "runs/transporter_negative_reviewer_day_plan_current.json"
DEFAULT_DONOR_CHECKLIST_JSON = "runs/transporter_donor_policy_reopen_checklist_current.json"
DEFAULT_VERDICT_PACKETS_JSON = "runs/transporter_manual_verdict_packets_current.json"
DEFAULT_SOURCE_CONFIRMATION_JSON = "runs/aqp1_first_wave_source_confirmation_packet_current.json"
DEFAULT_GLUT1_SOURCE_CONFIRMATION_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_OUT_JSON = "runs/transporter_manual_review_quickstart_packet_current.json"
DEFAULT_OUT_CSV = "runs/transporter_manual_review_quickstart_packet_current.csv"
DEFAULT_OUT_MD = "runs/transporter_manual_review_quickstart_packet_current.md"


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


def _aqp1_primary_probe_resolution_handoff(summary: dict[str, Any]) -> str:
    artifact = str(summary.get("aqp1_negative_primary_probe_resolution_artifact", "") or "").strip()
    if not artifact:
        return ""
    candidate = (
        str(summary.get("aqp1_negative_primary_probe_resolution_candidate", "") or "").strip()
        or "sodium nitroprusside"
    )
    fallback = (
        str(summary.get("aqp1_negative_primary_probe_resolution_solvent_fallback_candidate", "") or "").strip()
        or "dimethyl sulfoxide"
    )
    decision = (
        str(summary.get("aqp1_negative_primary_probe_resolution_decision", "") or "").strip()
        or "keep_review_only_no_authoritative_negative_promotion"
    )
    return (
        f" Keep `{artifact}` ready as the AQP1 primary-probe resolution handoff: leave `{candidate}` review-only, "
        f"keep `{fallback}` solvent-only, and preserve decision `{decision}`."
    )


def _build_target_rows(
    dashboard_payload: dict[str, Any],
    verdict_packets_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    targets = {str(row.get("target_id", "")).strip().lower(): dict(row) for row in dashboard_payload.get("target_rows", []) or []}
    packet_lookup = {
        str(packet.get("target_id", "")).strip().lower(): dict(packet)
        for packet in verdict_packets_payload.get("target_packets", []) or []
    }
    rows: list[dict[str, Any]] = []
    for idx, key in enumerate(("aqp1", "glut1"), start=1):
        target = targets[key]
        packet = packet_lookup[key]
        wave = "first-wave" if key == "aqp1" else "second-wave"
        rows.append(
            {
                "target_rank": idx,
                "target_id": key.upper(),
                "wave": wave,
                "lane_status": str(target.get("local_evidence_status", "")).strip(),
                "exact_human_activity_count": int(target.get("exact_human_activity_count", 0) or 0),
                "quantitative_provenance_focus_ligand": str(
                    target.get("quantitative_provenance_primary_focus_ligand", "")
                ).strip(),
                "quantitative_provenance_signal": str(
                    target.get("quantitative_provenance_signal", "")
                ).strip(),
                "binder_lane_count": int(packet.get("row_count", 0) or 0),
                "negative_lane_count": int(target.get("negative_slot_count", 0) or 0),
                "binder_pending_manual_verdict_count": int(packet.get("pending_manual_verdict_count", 0) or 0),
                "placeholder_rows": int(target.get("placeholder_rows", 0) or 0),
                "aqp1_negative_primary_probe_resolution_ready": bool(
                    target.get("aqp1_negative_primary_probe_resolution_artifact", "")
                )
                if key == "aqp1"
                else False,
                "aqp1_negative_primary_probe_resolution_artifact": str(
                    target.get("aqp1_negative_primary_probe_resolution_artifact", "")
                ).strip()
                if key == "aqp1"
                else "",
                "aqp1_negative_primary_probe_resolution_candidate": str(
                    target.get("aqp1_negative_primary_probe_resolution_candidate", "")
                ).strip()
                if key == "aqp1"
                else "",
                "aqp1_negative_primary_probe_resolution_decision": str(
                    target.get("aqp1_negative_primary_probe_resolution_decision", "")
                ).strip()
                if key == "aqp1"
                else "",
                "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": str(
                    target.get("aqp1_negative_primary_probe_resolution_solvent_fallback_candidate", "")
                ).strip()
                if key == "aqp1"
                else "",
                "next_required_step": str(target.get("next_required_step", "")).strip(),
            }
        )
    return rows


def _build_lane_rows(
    binder_ledger_payload: dict[str, Any],
    negative_day_plan_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for row in binder_ledger_payload.get("rows", []) or []:
        rows.append(
            {
                "lane_rank": 0,
                "target_id": str(row.get("target_id", "")).strip(),
                "wave": "first-wave" if str(row.get("target_id", "")).strip().upper() == "AQP1" else "second-wave",
                "lane": "binder",
                "priority_rank": 0,
                "packet_step": str(row.get("packet_step", "")).strip(),
                "candidate_or_label": str(row.get("candidate_name", "")).strip(),
                "review_bucket": str(row.get("review_bucket", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "promotion_blocker": str(row.get("promotion_blocker", "")).strip(),
            }
        )

    for row in negative_day_plan_payload.get("review_rows", []) or []:
        if str(row.get("review_phase", "")).strip() != "negative_slots_first":
            continue
        rows.append(
            {
                "lane_rank": 0,
                "target_id": str(row.get("target_id", "")).strip(),
                "wave": "first-wave" if str(row.get("target_id", "")).strip().upper() == "AQP1" else "second-wave",
                "lane": "negative",
                "priority_rank": int(str(row.get("priority_rank", "999")).strip() or 999),
                "packet_step": str(row.get("packet_step", "")).strip(),
                "candidate_or_label": str(row.get("candidate_or_label", "")).strip(),
                "review_bucket": str(row.get("review_bucket", "")).strip(),
                "next_required_action": str(row.get("next_required_action", "")).strip(),
                "promotion_blocker": "do_not_inject_proxy_negative_values",
            }
        )

    wave_order = {"first-wave": 0, "second-wave": 1}
    lane_order = {"binder": 0, "negative": 1}
    rows.sort(
        key=lambda row: (
            wave_order.get(str(row["wave"]), 9),
            lane_order.get(str(row["lane"]), 9),
            str(row["target_id"]),
            int(row["priority_rank"]) if row["lane"] == "negative" else 0,
            str(row["packet_step"]),
        )
    )
    for idx, row in enumerate(rows, start=1):
        row["lane_rank"] = idx
    return rows


def build_payload(
    dashboard_payload: dict[str, Any],
    binder_ledger_payload: dict[str, Any],
    negative_day_plan_payload: dict[str, Any],
    donor_checklist_payload: dict[str, Any],
    verdict_packets_payload: dict[str, Any],
    source_confirmation_payload: dict[str, Any],
    glut1_source_confirmation_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dashboard_s = dict(dashboard_payload.get("summary", {}) or {})
    donor_s = dict(donor_checklist_payload.get("summary", {}) or {})
    source_confirmation_s = dict(source_confirmation_payload.get("summary", {}) or {})
    glut1_source_confirmation_s = dict((glut1_source_confirmation_payload or {}).get("summary", {}) or {})
    target_rows = _build_target_rows(dashboard_payload, verdict_packets_payload)
    lane_rows = _build_lane_rows(binder_ledger_payload, negative_day_plan_payload)
    binder_pending_manual_verdict_count = int(dashboard_s.get("binder_pending_manual_verdict_count", 0) or 0)
    placeholder_row_count_total = sum(int(row.get("placeholder_rows", 0) or 0) for row in target_rows)
    aqp1_source_confirmation_row_count = int(source_confirmation_s.get("row_count", 0) or 0)
    aqp1_source_confirmation_primary_focus_ligand = str(source_confirmation_s.get("primary_focus_ligand", "")).strip()
    aqp1_source_confirmation_exact_human_reference_ligand = str(
        source_confirmation_s.get("exact_human_reference_ligand", "")
    ).strip()
    glut1_source_confirmation_row_count = int(glut1_source_confirmation_s.get("row_count", 0) or 0)
    glut1_source_confirmation_primary_focus_ligand = str(
        glut1_source_confirmation_s.get("primary_focus_ligand", "")
    ).strip()
    glut1_source_confirmation_primary_confirmation_target = str(
        glut1_source_confirmation_s.get("primary_confirmation_target", "")
    ).strip()
    glut1_direct_quantitative_binding_count = int(
        glut1_source_confirmation_s.get("direct_quantitative_binding_count", 0) or 0
    )
    glut1_exact_target_pair_activity_count = int(
        glut1_source_confirmation_s.get("exact_target_pair_activity_count", 0) or 0
    )
    glut1_structured_pair_absent_count = int(
        glut1_source_confirmation_s.get("structured_pair_absent_count", 0) or 0
    )
    aqp1_primary_probe_resolution_handoff = _aqp1_primary_probe_resolution_handoff(dashboard_s)

    for row in target_rows:
        target_id = str(row.get("target_id", "")).strip().upper()
        if target_id == "AQP1":
            row["source_confirmation_row_count"] = aqp1_source_confirmation_row_count
            row["source_confirmation_primary_focus_ligand"] = aqp1_source_confirmation_primary_focus_ligand
            row["source_confirmation_exact_human_reference_ligand"] = aqp1_source_confirmation_exact_human_reference_ligand
            row["source_confirmation_primary_confirmation_target"] = ""
            row["source_confirmation_direct_quantitative_binding_count"] = 0
            row["source_confirmation_exact_target_pair_activity_count"] = 0
            row["source_confirmation_structured_pair_absent_count"] = 0
            row["open_source_confirmation"] = "runs/aqp1_first_wave_source_confirmation_packet_current.md"
            continue
        row["source_confirmation_row_count"] = glut1_source_confirmation_row_count
        row["source_confirmation_primary_focus_ligand"] = glut1_source_confirmation_primary_focus_ligand
        row["source_confirmation_exact_human_reference_ligand"] = ""
        row["source_confirmation_primary_confirmation_target"] = glut1_source_confirmation_primary_confirmation_target
        row["source_confirmation_direct_quantitative_binding_count"] = glut1_direct_quantitative_binding_count
        row["source_confirmation_exact_target_pair_activity_count"] = glut1_exact_target_pair_activity_count
        row["source_confirmation_structured_pair_absent_count"] = glut1_structured_pair_absent_count
        row["open_source_confirmation"] = (
            "runs/glut1_second_wave_source_confirmation_packet_current.md" if glut1_source_confirmation_s else ""
        )

    summary = {
        "target_count": len(target_rows),
        "first_wave_target": "AQP1",
        "second_wave_target": "GLUT1",
        "current_phase": (
            "manual_verdict_burndown"
            if binder_pending_manual_verdict_count > 0
            else "blocker_closure_seed_row_promotion"
        ),
        "binder_lane_count": sum(1 for row in lane_rows if row["lane"] == "binder"),
        "negative_lane_count": sum(1 for row in lane_rows if row["lane"] == "negative"),
        "binder_pending_manual_verdict_count": binder_pending_manual_verdict_count,
        "placeholder_row_count_total": placeholder_row_count_total,
        "donor_policy_status": str(donor_s.get("decision_status", "")).strip(),
        "donor_policy_reopen_ready": bool(donor_s.get("reopen_ready", False)),
        "donor_policy_blocked_check_count": int(donor_s.get("blocked_check_count", 0) or 0),
        "scaffold_fit_donor_target": str(donor_s.get("scaffold_fit_donor_target", "")).strip(),
        "aqp1_seed_fill_ready": bool(dashboard_s.get("seed_row_fill_drafts_ready", False)),
        "aqp1_sync_preview_ready": bool(dashboard_s.get("seed_row_sync_preview_ready", False)),
        "aqp1_exact_human_activity_count": int(dashboard_s.get("aqp1_exact_human_activity_count", 0) or 0),
        "aqp1_quantitative_provenance_focus_ligand": str(
            dashboard_s.get("aqp1_quantitative_provenance_primary_focus_ligand", "")
        ).strip(),
        "aqp1_quantitative_provenance_signal": str(
            dashboard_s.get("aqp1_quantitative_provenance_signal", "")
        ).strip(),
        "aqp1_source_confirmation_row_count": aqp1_source_confirmation_row_count,
        "aqp1_source_confirmation_primary_focus_ligand": aqp1_source_confirmation_primary_focus_ligand,
        "aqp1_source_confirmation_exact_human_reference_ligand": aqp1_source_confirmation_exact_human_reference_ligand,
        "aqp1_open_source_confirmation": "runs/aqp1_first_wave_source_confirmation_packet_current.md",
        "aqp1_negative_primary_probe_resolution_ready": bool(
            dashboard_s.get("aqp1_negative_primary_probe_resolution_artifact", "")
        ),
        "aqp1_negative_primary_probe_resolution_artifact": str(
            dashboard_s.get("aqp1_negative_primary_probe_resolution_artifact", "")
        ).strip(),
        "aqp1_negative_primary_probe_resolution_candidate": str(
            dashboard_s.get("aqp1_negative_primary_probe_resolution_candidate", "")
        ).strip(),
        "aqp1_negative_primary_probe_resolution_decision": str(
            dashboard_s.get("aqp1_negative_primary_probe_resolution_decision", "")
        ).strip(),
        "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate": str(
            dashboard_s.get("aqp1_negative_primary_probe_resolution_solvent_fallback_candidate", "")
        ).strip(),
        "glut1_source_confirmation_row_count": glut1_source_confirmation_row_count,
        "glut1_source_confirmation_primary_focus_ligand": glut1_source_confirmation_primary_focus_ligand,
        "glut1_source_confirmation_primary_confirmation_target": glut1_source_confirmation_primary_confirmation_target,
        "glut1_direct_quantitative_binding_count": glut1_direct_quantitative_binding_count,
        "glut1_exact_target_pair_activity_count": glut1_exact_target_pair_activity_count,
        "glut1_structured_pair_absent_count": glut1_structured_pair_absent_count,
        "glut1_open_source_confirmation": (
            "runs/glut1_second_wave_source_confirmation_packet_current.md" if glut1_source_confirmation_s else ""
        ),
        "aqp1_operator_provenance_note": (
            "Carry AqB013 as the exact-human-activity provenance lane, but keep replacement_reference_binding_kcal_mol blank because claim-safe quantitative binding is still absent."
            if int(dashboard_s.get("aqp1_exact_human_activity_count", 0) or 0) > 0
            else "Keep replacement_reference_binding_kcal_mol blank until exact human target activity or claim-safe quantitative binding is curated."
        ),
        "next_required_step": (
            "Work AQP1 first-wave binder and negative lanes before GLUT1 second-wave lanes, and do not reopen donor policy until blocker checks clear."
            if binder_pending_manual_verdict_count > 0
            else (
                "Use the AQP1 first-wave source-confirmation packet first, review bacopaside II exact-source scope before negative review, keep AqB013 as the exact-human-activity provenance lane, keep GLUT1 second-wave behind AQP1, and do not reopen donor policy until placeholder rows and blocker checks are reduced."
                + aqp1_primary_probe_resolution_handoff
                + (
                    f" When GLUT1 opens, use {glut1_source_confirmation_primary_focus_ligand or 'cytochalasin B'} as the source-confirmation lead from runs/glut1_second_wave_source_confirmation_packet_current.md, keep WZB117 on the exact-target-pair functional lane, and keep STF-31 review-only with structured-pair caveats."
                    if glut1_source_confirmation_s
                    else ""
                )
            )
        ),
    }
    return {"summary": summary, "target_rows": target_rows, "lane_rows": lane_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Manual Review Quickstart Packet",
        "",
        f"- target_count: `{s['target_count']}`",
        f"- first_wave_target: `{s['first_wave_target']}`",
        f"- second_wave_target: `{s['second_wave_target']}`",
        f"- current_phase: `{s['current_phase']}`",
        f"- binder_lane_count: `{s['binder_lane_count']}`",
        f"- negative_lane_count: `{s['negative_lane_count']}`",
        f"- binder_pending_manual_verdict_count: `{s['binder_pending_manual_verdict_count']}`",
        f"- placeholder_row_count_total: `{s['placeholder_row_count_total']}`",
        f"- donor_policy_status: `{s['donor_policy_status']}`",
        f"- donor_policy_reopen_ready: `{s['donor_policy_reopen_ready']}`",
        f"- donor_policy_blocked_check_count: `{s['donor_policy_blocked_check_count']}`",
        f"- scaffold_fit_donor_target: `{s['scaffold_fit_donor_target']}`",
        f"- aqp1_seed_fill_ready: `{s['aqp1_seed_fill_ready']}`",
        f"- aqp1_sync_preview_ready: `{s['aqp1_sync_preview_ready']}`",
        f"- aqp1_exact_human_activity_count: `{s['aqp1_exact_human_activity_count']}`",
        f"- aqp1_quantitative_provenance_focus_ligand: `{s['aqp1_quantitative_provenance_focus_ligand']}`",
        f"- aqp1_quantitative_provenance_signal: `{s['aqp1_quantitative_provenance_signal']}`",
        f"- aqp1_source_confirmation_row_count: `{s['aqp1_source_confirmation_row_count']}`",
        f"- aqp1_source_confirmation_primary_focus_ligand: `{s['aqp1_source_confirmation_primary_focus_ligand']}`",
        f"- aqp1_source_confirmation_exact_human_reference_ligand: `{s['aqp1_source_confirmation_exact_human_reference_ligand']}`",
        f"- aqp1_open_source_confirmation: `{s['aqp1_open_source_confirmation']}`",
        f"- aqp1_negative_primary_probe_resolution_ready: `{s['aqp1_negative_primary_probe_resolution_ready']}`",
        f"- aqp1_negative_primary_probe_resolution_artifact: `{s['aqp1_negative_primary_probe_resolution_artifact']}`",
        f"- aqp1_negative_primary_probe_resolution_candidate: `{s['aqp1_negative_primary_probe_resolution_candidate']}`",
        f"- aqp1_negative_primary_probe_resolution_decision: `{s['aqp1_negative_primary_probe_resolution_decision']}`",
        f"- aqp1_negative_primary_probe_resolution_solvent_fallback_candidate: `{s['aqp1_negative_primary_probe_resolution_solvent_fallback_candidate']}`",
        f"- glut1_source_confirmation_row_count: `{s['glut1_source_confirmation_row_count']}`",
        f"- glut1_source_confirmation_primary_focus_ligand: `{s['glut1_source_confirmation_primary_focus_ligand']}`",
        f"- glut1_source_confirmation_primary_confirmation_target: `{s['glut1_source_confirmation_primary_confirmation_target']}`",
        f"- glut1_direct_quantitative_binding_count: `{s['glut1_direct_quantitative_binding_count']}`",
        f"- glut1_exact_target_pair_activity_count: `{s['glut1_exact_target_pair_activity_count']}`",
        f"- glut1_structured_pair_absent_count: `{s['glut1_structured_pair_absent_count']}`",
        f"- glut1_open_source_confirmation: `{s['glut1_open_source_confirmation']}`",
        "",
        "## Quickstart",
        "",
        f"- {s['next_required_step']}",
        f"- {s['aqp1_operator_provenance_note']}",
        "",
        "## Wave Order",
        "",
        "| target_id | wave | lane_status | exact_human_activity_count | quantitative_provenance_focus_ligand | source_confirmation_primary_focus_ligand | source_confirmation_primary_confirmation_target | source_confirmation_direct_quantitative_binding_count | source_confirmation_exact_target_pair_activity_count | source_confirmation_structured_pair_absent_count | binder_lane_count | negative_lane_count | binder_pending_manual_verdict_count | placeholder_rows |",
        "| --- | --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["target_rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['wave']}` | `{row['lane_status']}` | {row['exact_human_activity_count']} | `{row['quantitative_provenance_focus_ligand']}` | `{row['source_confirmation_primary_focus_ligand']}` | "
            f"`{row['source_confirmation_primary_confirmation_target']}` | {row['source_confirmation_direct_quantitative_binding_count']} | {row['source_confirmation_exact_target_pair_activity_count']} | "
            f"{row['source_confirmation_structured_pair_absent_count']} | {row['binder_lane_count']} | {row['negative_lane_count']} | {row['binder_pending_manual_verdict_count']} | {row['placeholder_rows']} |"
        )
    lines.extend(
        [
            "",
            "## Seed-Row vs Negative Lanes",
            "",
            "| lane_rank | target_id | wave | lane | priority_rank | packet_step | candidate_or_label | review_bucket | next_required_action | promotion_blocker |",
            "| ---: | --- | --- | --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["lane_rows"]:
        lines.append(
            f"| {row['lane_rank']} | `{row['target_id']}` | `{row['wave']}` | `{row['lane']}` | {row['priority_rank']} | "
            f"`{row['packet_step']}` | `{row['candidate_or_label']}` | `{row['review_bucket']}` | "
            f"`{row['next_required_action']}` | `{row['promotion_blocker']}` |"
        )
    lines.extend(
        [
            "",
            "## Donor Policy Blockers",
            "",
            f"- Keep transporter donor policy frozen at scaffold default `{s['scaffold_fit_donor_target']}`.",
            f"- Reopen is blocked now: `{s['donor_policy_reopen_ready']}` with `{s['donor_policy_blocked_check_count']}` blocked checks.",
            "- Do not promote any transporter row to authoritative apply until donor-policy blockers and local-evidence blockers are both reduced.",
            "",
            "## Detailed Follow-ups",
            "",
            "- Use the AQP1/GLUT1 detailed packets only after this quickstart packet is exhausted; treat them as seed-row/blocker-closure surfaces when manual-verdict backlog is already zero.",
            f"- Keep `AQP1` source confirmation open at `{s['aqp1_open_source_confirmation']}`.",
            (
                f"- Keep `AQP1` primary-probe resolution open at `{s['aqp1_negative_primary_probe_resolution_artifact']}` and leave `{s['aqp1_negative_primary_probe_resolution_candidate'] or 'sodium nitroprusside'}` review-only with `{s['aqp1_negative_primary_probe_resolution_solvent_fallback_candidate'] or 'dimethyl sulfoxide'}` parked as solvent fallback."
                if s["aqp1_negative_primary_probe_resolution_artifact"]
                else "- Keep the AQP1 primary-probe resolution handoff ready if the negative-evidence packet surface is available."
            ),
            f"- Keep `GLUT1` source confirmation open at `{s['glut1_open_source_confirmation']}` and start with `{s['glut1_source_confirmation_primary_focus_ligand'] or 'cytochalasin B'}` when the second wave opens.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an operator-friendly transporter manual-review quickstart packet.")
    parser.add_argument("--dashboard-json", default=DEFAULT_DASHBOARD_JSON)
    parser.add_argument("--binder-ledger-json", default=DEFAULT_BINDER_LEDGER_JSON)
    parser.add_argument("--negative-day-plan-json", default=DEFAULT_NEGATIVE_DAY_PLAN_JSON)
    parser.add_argument("--donor-checklist-json", default=DEFAULT_DONOR_CHECKLIST_JSON)
    parser.add_argument("--verdict-packets-json", default=DEFAULT_VERDICT_PACKETS_JSON)
    parser.add_argument("--source-confirmation-json", default=DEFAULT_SOURCE_CONFIRMATION_JSON)
    parser.add_argument("--glut1-source-confirmation-json", default=DEFAULT_GLUT1_SOURCE_CONFIRMATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.dashboard_json),
        _load_json(args.binder_ledger_json),
        _load_json(args.negative_day_plan_json),
        _load_json(args.donor_checklist_json),
        _load_json(args.verdict_packets_json),
        _load_json(args.source_confirmation_json),
        _load_json(args.glut1_source_confirmation_json),
    )

    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["lane_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
