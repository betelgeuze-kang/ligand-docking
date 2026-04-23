#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"

OUT_JSON = RUNS / "family_expansion_refresh_current.json"
OUT_MD = RUNS / "family_expansion_refresh_current.md"
ROLLUP_JSON = RUNS / "family_expansion_status_rollup_current.json"

# These follow-on steps are allowed to be absent until their builders land.
OPTIONAL_STEP_LABELS = {
    "aqp1_follow_on_source_confirmation_packet",
    "glut1_second_wave_source_confirmation_packet",
    "transporter_placeholder_burndown_queue",
}


def _script(name: str) -> str:
    return str(ROOT / "tools" / name)


def _run(label: str, cmd: list[str]) -> dict[str, object]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "label": label,
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
        "ok": proc.returncode == 0,
    }


def _safe_load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _family_signal(label: str, signal: str, blocker: str, source_artifact: str) -> dict[str, str]:
    return {
        "family": label,
        "completion_signal": signal,
        "blocker": blocker,
        "source_artifact": source_artifact,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Family Expansion Refresh",
        "",
        f"- overall_ok: `{s['overall_ok']}`",
        f"- step_count: `{s['step_count']}`",
        f"- ok_count: `{s['ok_count']}`",
        f"- failed_count: `{s['failed_count']}`",
        f"- first_failed_step: `{s['first_failed_step'] or '-'}`",
        f"- top_blocker_family: `{s['top_blocker_family']}`",
        f"- next_required_step: {s['next_required_step']}",
        "",
        "## Completion Signals",
        "",
        "| family | completion_signal | blocker | source_artifact |",
        "| --- | --- | --- | --- |",
    ]
    for row in s["family_signals"]:
        lines.append(
            f"| `{row['family']}` | `{row['completion_signal']}` | `{row['blocker']}` | `{row['source_artifact']}` |"
        )
    lines.extend(
        [
            "",
            "## Step Results",
            "",
            "| label | ok | returncode |",
            "| --- | --- | ---: |",
        ]
    )
    for step in payload["steps"]:
        lines.append(f"| `{step['label']}` | `{step['ok']}` | {step['returncode']} |")
    lines.extend(
        [
            "",
            "## Rollup Snapshot",
            "",
            f"- artifact: `{payload['summary']['rollup_artifact']}`",
            "",
            "| family | phase | current_scope | blocking_signal | next_required_step |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rollup"].get("rows", []):
        lines.append(
            f"| `{row['family']}` | `{row['phase']}` | `{row.get('current_scope', '')}` | `{row['blocking_signal']}` | {row['next_required_step']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    steps = [
        ("ca2_capture_sheet_seed", [sys.executable, _script("build_ca2_negative_evidence_capture_sheet.py")]),
        ("ca2_public_negative_overlay", [sys.executable, _script("build_ca2_public_negative_evidence_overlay.py")]),
        ("ca2_capture_sheet", [sys.executable, _script("build_ca2_negative_evidence_capture_sheet.py")]),
        ("ca2_capture_intake", [sys.executable, _script("build_ca2_negative_evidence_capture_intake.py")]),
        ("pxr_capture_sheet_seed", [sys.executable, _script("build_pxr_unresolved_evidence_capture_sheet.py")]),
        ("pxr_public_overlay", [sys.executable, _script("build_pxr_public_evidence_overlay.py")]),
        ("pxr_capture_sheet", [sys.executable, _script("build_pxr_unresolved_evidence_capture_sheet.py")]),
        ("pxr_capture_intake", [sys.executable, _script("build_pxr_unresolved_evidence_capture_intake.py")]),
        ("aqp1_external_seed", [sys.executable, _script("build_aqp1_external_evidence_seed.py")]),
        ("aqp1_fill_queue", [sys.executable, _script("build_aqp1_packet_fill_queue.py")]),
        ("aqp1_workbook", [sys.executable, _script("build_aqp1_packet_replacement_workbook.py")]),
        ("aqp1_quant_sheet", [sys.executable, _script("build_aqp1_quantitative_binding_capture_sheet.py")]),
        ("aqp1_quant_intake", [sys.executable, _script("build_aqp1_quantitative_binding_capture_intake.py")]),
        ("aqp1_quantitative_provenance_packet", [sys.executable, _script("build_aqp1_quantitative_provenance_packet.py")]),
        ("aqp1_first_wave_source_confirmation_packet", [sys.executable, _script("build_aqp1_first_wave_source_confirmation_packet.py")]),
        ("aqp1_candidate_ledger", [sys.executable, _script("build_aqp1_candidate_evidence_ledger.py")]),
        ("aqp1_local_note", [sys.executable, _script("build_aqp1_local_evidence_note.py")]),
        ("aqp1_manual_queue", [sys.executable, _script("build_aqp1_manual_review_queue.py")]),
        ("aqp1_next_slice", [sys.executable, _script("build_aqp1_next_verification_slice.py")]),
        ("aqp1_candidate_verdict_sheet", [sys.executable, _script("build_transporter_candidate_verdict_sheet.py"), "--family", "aqp1"]),
        ("aqp1_binder_verdict_update_sheet", [sys.executable, _script("build_transporter_binder_verdict_update_sheet.py"), "--family", "aqp1"]),
        ("aqp1_binder_brief", [sys.executable, _script("build_aqp1_binder_review_brief.py")]),
        ("aqp1_apply_draft", [sys.executable, _script("build_aqp1_manual_verdict_apply_draft.py")]),
        ("aqp1_negative_handoff", [sys.executable, _script("build_aqp1_negative_review_handoff_packet.py")]),
        ("aqp1_negative_source_exclusion", [sys.executable, _script("build_aqp1_negative_source_exclusion_packet.py")]),
        ("aqp1_negative_slot_closure", [sys.executable, _script("build_aqp1_negative_slot_closure_packet.py")]),
        ("aqp1_negative_acquisition", [sys.executable, _script("build_aqp1_negative_evidence_acquisition_packet.py")]),
        ("aqp1_negative_confirmation", [sys.executable, _script("build_aqp1_negative_evidence_confirmation_packet.py")]),
        ("aqp1_negative_slot_resolution", [sys.executable, _script("build_aqp1_negative_slot_resolution_packet.py")]),
        ("aqp1_negative_candidate_frontier", [sys.executable, _script("build_aqp1_negative_candidate_frontier_packet.py")]),
        ("aqp1_negative_frontier_resolution", [sys.executable, _script("build_aqp1_negative_frontier_resolution_packet.py")]),
        ("aqp1_negative_primary_probe", [sys.executable, _script("build_aqp1_negative_primary_probe_packet.py")]),
        ("aqp1_negative_exact_source_outcome", [sys.executable, _script("build_aqp1_negative_exact_source_outcome_packet.py")]),
        ("aqp1_negative_primary_probe_resolution", [sys.executable, _script("build_aqp1_negative_primary_probe_resolution_packet.py")]),
        ("aqp1_manual_handoff", [sys.executable, _script("build_aqp1_manual_verdict_handoff_packet.py")]),
        ("aqp1_reviewer_workbench", [sys.executable, _script("build_aqp1_reviewer_workbench.py")]),
        ("aqp1_p0_plan", [sys.executable, _script("build_aqp1_p0_packet_plan.py")]),
        ("transporter_wave_notes", [sys.executable, _script("build_transporter_wave_verdict_notes.py")]),
        ("transporter_wave_decision", [sys.executable, _script("build_transporter_wave_decision.py")]),
        ("transporter_apply_status", [sys.executable, _script("build_transporter_apply_draft_status.py")]),
        ("transporter_donor_blocker", [sys.executable, _script("build_transporter_donor_policy_blocker_packet.py")]),
        ("transporter_membrane_readiness", [sys.executable, _script("build_transporter_membrane_readiness.py")]),
        ("transporter_fit_donor_policy", [sys.executable, _script("build_transporter_fit_donor_policy_decision.py")]),
        ("transporter_donor_reopen", [sys.executable, _script("build_transporter_donor_policy_reopen_checklist.py")]),
        ("transporter_blocker_decomposition", [sys.executable, _script("build_transporter_authoritative_apply_blocker_decomposition.py")]),
        ("transporter_binder_slot_ledger", [sys.executable, _script("build_transporter_binder_slot_ledger.py")]),
        ("glut1_negative_handoff", [sys.executable, _script("build_glut1_negative_review_handoff_packet.py")]),
        ("transporter_negative_day_plan", [sys.executable, _script("build_transporter_negative_reviewer_day_plan.py")]),
        ("transporter_negative_target_packets", [sys.executable, _script("build_transporter_negative_evidence_target_packets.py")]),
        ("transporter_reviewer_day_plan", [sys.executable, _script("build_transporter_reviewer_day_plan.py")]),
        ("transporter_reviewer_day2_console", [sys.executable, _script("build_transporter_reviewer_day2_console.py")]),
        ("transporter_verdict_summary", [sys.executable, _script("build_transporter_verdict_summary.py")]),
        ("transporter_verdict_packets", [sys.executable, _script("build_transporter_manual_verdict_packets.py")]),
        ("transporter_blocker_sheet", [sys.executable, _script("build_transporter_blocker_capture_sheet.py")]),
        ("transporter_blocker_intake", [sys.executable, _script("build_transporter_blocker_capture_intake.py")]),
        ("aqp1_first_seed_packet", [sys.executable, _script("build_aqp1_first_seed_row_packet.py")]),
        ("aqp1_seed_fill_draft", [sys.executable, _script("build_aqp1_seed_row_fill_draft.py")]),
        ("aqp1_seed_sync_preview", [sys.executable, _script("build_aqp1_seed_row_sync_apply_preview.py")]),
        ("aqp1_first_wave_follow_on_packet", [sys.executable, _script("build_aqp1_first_wave_follow_on_packet.py")]),
        ("aqp1_follow_on_source_confirmation_packet", [sys.executable, _script("build_aqp1_follow_on_source_confirmation_packet.py")]),
        ("aqp1_follow_on_blocker_decomposition", [sys.executable, _script("build_aqp1_follow_on_blocker_decomposition.py")]),
        ("glut1_second_wave_source_confirmation_packet", [sys.executable, _script("build_glut1_second_wave_source_confirmation_packet.py")]),
        ("glut1_second_wave_seed_packet", [sys.executable, _script("build_glut1_second_wave_seed_row_packet.py")]),
        ("glut1_second_wave_seed_fill_draft", [sys.executable, _script("build_glut1_second_wave_seed_row_fill_draft.py")]),
        ("glut1_second_wave_seed_sync_preview", [sys.executable, _script("build_glut1_second_wave_seed_row_sync_apply_preview.py")]),
        (
            "glut1_second_wave_seed_packet_core_binder_02",
            [
                sys.executable,
                _script("build_glut1_second_wave_seed_row_packet.py"),
                "--packet-step",
                "core_binder_02",
            ],
        ),
        (
            "glut1_second_wave_seed_fill_draft_core_binder_02",
            [
                sys.executable,
                _script("build_glut1_second_wave_seed_row_fill_draft.py"),
                "--packet-step",
                "core_binder_02",
                "--seed-packet-json",
                "runs/glut1_second_wave_seed_row_packet_core_binder_02_current.json",
            ],
        ),
        (
            "glut1_second_wave_seed_sync_preview_core_binder_02",
            [
                sys.executable,
                _script("build_glut1_second_wave_seed_row_sync_apply_preview.py"),
                "--packet-step",
                "core_binder_02",
                "--seed-fill-draft-json",
                "runs/glut1_second_wave_seed_row_fill_draft_core_binder_02_current.json",
                "--seed-packet-json",
                "runs/glut1_second_wave_seed_row_packet_core_binder_02_current.json",
            ],
        ),
        (
            "glut1_second_wave_seed_packet_core_binder_03",
            [
                sys.executable,
                _script("build_glut1_second_wave_seed_row_packet.py"),
                "--packet-step",
                "core_binder_03",
            ],
        ),
        (
            "glut1_second_wave_seed_fill_draft_core_binder_03",
            [
                sys.executable,
                _script("build_glut1_second_wave_seed_row_fill_draft.py"),
                "--packet-step",
                "core_binder_03",
                "--seed-packet-json",
                "runs/glut1_second_wave_seed_row_packet_core_binder_03_current.json",
            ],
        ),
        (
            "glut1_second_wave_seed_sync_preview_core_binder_03",
            [
                sys.executable,
                _script("build_glut1_second_wave_seed_row_sync_apply_preview.py"),
                "--packet-step",
                "core_binder_03",
                "--seed-fill-draft-json",
                "runs/glut1_second_wave_seed_row_fill_draft_core_binder_03_current.json",
                "--seed-packet-json",
                "runs/glut1_second_wave_seed_row_packet_core_binder_03_current.json",
            ],
        ),
        ("transporter_apply_status_post_stage", [sys.executable, _script("build_transporter_apply_draft_status.py")]),
        ("transporter_seed_row_promotion_board_post_stage", [sys.executable, _script("build_transporter_seed_row_promotion_board.py")]),
        ("transporter_seed_execution", [sys.executable, _script("build_transporter_seed_row_execution_packet.py")]),
        ("transporter_operator_console", [sys.executable, _script("build_transporter_operator_console.py")]),
        ("family_manual_burndown", [sys.executable, _script("build_family_manual_review_burndown.py")]),
        ("family_manual_priority_queue", [sys.executable, _script("build_family_manual_review_priority_queue.py")]),
        ("family_negative_policy", [sys.executable, _script("build_family_negative_policy_summary.py")]),
        ("family_policy_freeze_notes", [sys.executable, _script("build_family_policy_freeze_notes.py")]),
        ("partial_authoritative_family_handoff", [sys.executable, _script("build_partial_authoritative_family_handoff.py")]),
        ("partial_authoritative_operator_console", [sys.executable, _script("build_partial_authoritative_operator_console.py")]),
        ("partial_authoritative_commit_launchboard", [sys.executable, _script("build_partial_authoritative_commit_launchboard.py")]),
        ("partial_authoritative_launchboard", [sys.executable, _script("build_partial_authoritative_launchboard.py")]),
        ("family_evidence_acquisition_queue", [sys.executable, _script("build_family_evidence_acquisition_queue.py")]),
        ("pxr_literature_candidate_overlay", [sys.executable, _script("build_pxr_literature_candidate_overlay.py")]),
        ("family_evidence_investigator_packet", [sys.executable, _script("build_family_evidence_investigator_packet.py")]),
        ("pxr_exact_source_confirmation_packet", [sys.executable, _script("build_pxr_exact_source_confirmation_packet.py")]),
        ("pxr_conflict_resolver_packet", [sys.executable, _script("build_pxr_conflict_resolver_packet.py")]),
        ("pxr_quantitative_provenance_packet", [sys.executable, _script("build_pxr_quantitative_provenance_packet.py")]),
        ("partial_authoritative_quickstart_packet", [sys.executable, _script("build_partial_authoritative_quickstart_packet.py")]),
        ("partial_authoritative_reviewer_console", [sys.executable, _script("build_partial_authoritative_reviewer_console.py")]),
        ("transporter_commercialization_closure_queue", [sys.executable, _script("build_transporter_commercialization_closure_queue.py")]),
        ("transporter_placeholder_burndown_queue", [sys.executable, _script("build_transporter_placeholder_burndown_queue.py")]),
        ("transporter_negative_evidence_closure_queue", [sys.executable, _script("build_transporter_negative_evidence_closure_queue.py")]),
        ("nightly_gate_burndown_packet", [sys.executable, _script("build_nightly_gate_burndown_packet.py")]),
        ("nightly_stage6_tuning_packet", [sys.executable, _script("build_nightly_stage6_tuning_packet.py")]),
        ("nightly_stage6_followup_retry_packet", [sys.executable, _script("build_nightly_stage6_followup_retry_packet.py")]),
        ("nightly_stage6_tuning_sweep_packet", [sys.executable, _script("build_nightly_stage6_tuning_sweep_packet.py")]),
        ("nightly_stage6_probe_result_packet", [sys.executable, _script("build_nightly_stage6_probe_result_packet.py")]),
        ("nightly_stage6_probe_promotion_packet", [sys.executable, _script("build_nightly_stage6_probe_promotion_packet.py")]),
        ("nightly_stage6_realization_packet", [sys.executable, _script("build_nightly_stage6_realization_packet.py")]),
        ("nightly_stage6_rescored_gate_packet", [sys.executable, _script("build_nightly_stage6_rescored_gate_packet.py")]),
        ("nightly_stage6_downstream_rerun_packet", [sys.executable, _script("build_nightly_stage6_downstream_rerun_packet.py")]),
        ("nightly_stage6_execute_result_packet", [sys.executable, _script("build_nightly_stage6_execute_result_packet.py")]),
        ("wetlab_execution_readiness_queue", [sys.executable, _script("build_wetlab_execution_readiness_queue.py")]),
        ("wetlab_selected_allatom_gate_burndown_packet", [sys.executable, _script("build_wetlab_selected_allatom_gate_burndown_packet.py")]),
        ("local_engine_commercialization_queue", [sys.executable, _script("build_local_engine_commercialization_queue.py")]),
        ("execution_handoff_dashboard", [sys.executable, _script("build_execution_handoff_dashboard.py")]),
        ("family_packet_catalog", [sys.executable, _script("build_family_packet_catalog.py")]),
        ("family_operator_quicklink_board", [sys.executable, _script("build_family_operator_quicklink_board.py")]),
        ("domain_completion_status", [sys.executable, _script("build_domain_completion_status.py")]),
        ("commercialization_readiness", [sys.executable, _script("build_commercialization_readiness_report.py")]),
        ("cross_family_shadow", [sys.executable, _script("build_cross_family_residual_shadow_layer.py")]),
        ("commercialization_gap_burndown", [sys.executable, _script("build_commercialization_gap_burndown.py")]),
        ("commercialization_status_report", [sys.executable, _script("build_commercialization_status_report.py")]),
        ("family_expansion_rollup", [sys.executable, _script("build_family_expansion_status_rollup.py")]),
    ]

    results: list[dict[str, object]] = []
    first_failed_step = ""
    for label, cmd in steps:
        if label in OPTIONAL_STEP_LABELS and not Path(cmd[1]).exists():
            continue
        result = _run(label, cmd)
        results.append(result)
        if not result["ok"]:
            first_failed_step = label
            break

    rollup = _safe_load_json(ROLLUP_JSON)
    rollup_summary = dict(rollup.get("summary", {}) or {})

    ca2_intake = _safe_load_json(RUNS / "ca2_negative_evidence_capture_intake_current.json")
    ca2_commit = _safe_load_json(RUNS / "ca2_evidence_closure_commit_packet_current.json")
    pxr_intake = _safe_load_json(RUNS / "pxr_unresolved_evidence_capture_intake_current.json")
    pxr_commit = _safe_load_json(RUNS / "pxr_pending_resolution_commit_packet_current.json")
    transporter_apply_status = _safe_load_json(RUNS / "transporter_apply_draft_status_current.json")
    transporter_capture_intake = _safe_load_json(RUNS / "transporter_blocker_capture_intake_current.json")
    transporter_seed_execution = _safe_load_json(RUNS / "transporter_seed_row_execution_packet_current.json")
    aqp1_quant_intake = _safe_load_json(RUNS / "aqp1_quantitative_binding_capture_intake_current.json")
    aqp1_quant_provenance = _safe_load_json(RUNS / "aqp1_quantitative_provenance_packet_current.json")
    aqp1_first_seed = _safe_load_json(RUNS / "aqp1_first_seed_row_packet_current.json")
    aqp1_fill_draft = _safe_load_json(RUNS / "aqp1_seed_row_fill_draft_current.json")
    aqp1_sync_preview = _safe_load_json(RUNS / "aqp1_seed_row_sync_apply_preview_current.json")

    family_signals = [
        _family_signal(
            "CA2",
            f"source_linked={ca2_intake.get('summary', {}).get('source_linked_count', 0)}; "
            f"pending_capture={ca2_intake.get('summary', {}).get('pending_capture_count', 0)}; "
            f"confirmed_commit={ca2_intake.get('summary', {}).get('confirmed_commit_count', 0)}",
            str(ca2_commit.get("summary", {}).get("next_required_step", "")).strip(),
            "runs/ca2_negative_evidence_capture_intake_current.json",
        ),
        _family_signal(
            "PXR",
            f"source_linked={pxr_intake.get('summary', {}).get('source_linked_count', 0)}; "
            f"supportive={pxr_intake.get('summary', {}).get('supportive_target_specific_human_count', 0)}; "
            f"ready_like={pxr_commit.get('summary', {}).get('ready_for_apply_row_count', 0)}",
            str(pxr_commit.get("summary", {}).get("next_required_step", "")).strip(),
            "runs/pxr_unresolved_evidence_capture_intake_current.json",
        ),
        _family_signal(
            "transporter",
            f"placeholder_driven_rows={transporter_apply_status.get('summary', {}).get('placeholder_driven_rows', 0)}; "
            f"staged_non_authoritative_rows={transporter_apply_status.get('summary', {}).get('staged_non_authoritative_rows', 0)}; "
            f"ready_for_apply_rows={transporter_apply_status.get('summary', {}).get('ready_for_apply_rows', 0)}",
            str(transporter_apply_status.get("summary", {}).get("next_required_step", "")).strip(),
            "runs/transporter_apply_draft_status_current.json",
        ),
        _family_signal(
            "AQP1",
            f"safe_prefill_field_count={aqp1_fill_draft.get('summary', {}).get('safe_prefill_field_count', 0)}; "
            f"safe_staged_field_count={aqp1_sync_preview.get('summary', {}).get('safe_staged_field_count', 0)}; "
            f"blocked_field_count={aqp1_first_seed.get('summary', {}).get('blocked_field_count', 0)}; "
            f"exact_human_activity_count={aqp1_quant_provenance.get('summary', {}).get('exact_human_aqp1_activity_count', 0)}",
            str(aqp1_first_seed.get("summary", {}).get("next_required_step", "")).strip(),
            "runs/aqp1_first_seed_row_packet_current.json",
        ),
    ]

    ok_count = sum(1 for r in results if r["ok"])
    failed_count = sum(1 for r in results if not r["ok"])
    overall_ok = failed_count == 0
    summary = {
        "overall_ok": overall_ok,
        "step_count": len(results),
        "ok_count": ok_count,
        "failed_count": failed_count,
        "first_failed_step": first_failed_step,
        "rollup_artifact": str(ROLLUP_JSON.relative_to(ROOT)),
        "top_blocker_family": str(rollup_summary.get("highest_gap_family", "")).strip() or "transporter",
        "next_required_step": (
            str(rollup_summary.get("next_required_step", "")).strip()
            if overall_ok
            else f"Inspect failed step `{first_failed_step}` in family_expansion_refresh_current.json and rerun after fixing the first error."
        ),
        "family_signals": family_signals,
        "refresh_artifacts": [
            "runs/family_expansion_refresh_current.json",
            "runs/family_expansion_refresh_current.md",
            "runs/family_expansion_status_rollup_current.json",
            "runs/family_expansion_status_rollup_current.md",
            "runs/nightly_gate_burndown_packet_current.md",
            "runs/nightly_stage6_tuning_packet_current.md",
            "runs/nightly_stage6_followup_retry_packet_current.md",
            "runs/nightly_stage6_tuning_sweep_packet_current.md",
            "runs/nightly_stage6_probe_result_packet_current.md",
            "runs/nightly_stage6_probe_promotion_packet_current.md",
            "runs/nightly_stage6_realization_packet_current.md",
            "runs/nightly_stage6_rescored_gate_packet_current.md",
            "runs/nightly_stage6_downstream_rerun_packet_current.md",
            "runs/nightly_stage6_execute_result_packet_current.md",
            "runs/wetlab_execution_readiness_queue_current.md",
            "runs/wetlab_selected_allatom_gate_burndown_packet_current.md",
            "runs/local_engine_commercialization_queue_current.md",
            "commercialization_status_report.md",
        ],
    }

    payload = {"summary": summary, "steps": results, "rollup": rollup}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(OUT_MD, payload)
    if not overall_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
