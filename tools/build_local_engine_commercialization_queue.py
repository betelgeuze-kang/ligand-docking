#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from tools import build_nightly_gate_burndown_packet as nightly_gate_burndown_mod
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"

DEFAULT_VIEWER_JSON = "runs/viewer_smoke_refresh_current.json"
DEFAULT_WETLAB_DASHBOARD_JSON = "runs/wetlab_master_handoff_dashboard_current.json"
DEFAULT_WETLAB_FINAL_JSON = "runs/wetlab_final_campaign_summary_current.json"
DEFAULT_WETLAB_READINESS_JSON = "runs/wetlab_execution_readiness_queue_current.json"
DEFAULT_WETLAB_SELECTED_ALLATOM_JSON = "runs/wetlab_selected_allatom_gate_burndown_packet_current.json"
DEFAULT_REFRESH_JSON = "runs/family_expansion_refresh_current.json"
DEFAULT_NEGATIVE_QUEUE_JSON = "runs/transporter_negative_evidence_closure_queue_current.json"
DEFAULT_GAP_JSON = "runs/commercialization_gap_burndown_current.json"
DEFAULT_NIGHTLY_GATE_JSON = "runs/nightly_gate_burndown_packet_current.json"
DEFAULT_NIGHTLY_TUNING_JSON = "runs/nightly_stage6_tuning_packet_current.json"
DEFAULT_NIGHTLY_FOLLOWUP_JSON = "runs/nightly_stage6_followup_retry_packet_current.json"
DEFAULT_NIGHTLY_SWEEP_JSON = "runs/nightly_stage6_tuning_sweep_packet_current.json"
DEFAULT_NIGHTLY_PROBE_JSON = "runs/nightly_stage6_probe_result_packet_current.json"
DEFAULT_NIGHTLY_PROMOTION_JSON = "runs/nightly_stage6_probe_promotion_packet_current.json"
DEFAULT_NIGHTLY_REALIZATION_JSON = "runs/nightly_stage6_realization_packet_current.json"
DEFAULT_NIGHTLY_RESCORED_JSON = "runs/nightly_stage6_rescored_gate_packet_current.json"
DEFAULT_NIGHTLY_DOWNSTREAM_RERUN_JSON = "runs/nightly_stage6_downstream_rerun_packet_current.json"
DEFAULT_NIGHTLY_DOWNSTREAM_RERUN_STATUS_JSON = "runs/nightly_stage6_downstream_rerun_current_status.json"
DEFAULT_NIGHTLY_EXECUTE_JSON = "runs/nightly_stage6_execute_result_packet_current.json"
DEFAULT_OUT_JSON = "runs/local_engine_commercialization_queue_current.json"
DEFAULT_OUT_CSV = "runs/local_engine_commercialization_queue_current.csv"
DEFAULT_OUT_MD = "runs/local_engine_commercialization_queue_current.md"

_TOP_NIGHTLY_RE = re.compile(r"ligand_htvs_nightly_(\d{4}-\d{2}-\d{2})_summary\.json$")
_SMOKE_NIGHTLY_RE = re.compile(r"ligand_htvs_nightly_(\d{4}-\d{2}-\d{2})_smoke_summary\.json$")


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _maybe_load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_text(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def _summaryish(payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(payload.get("summary", {}) or {})
    if summary:
        merged = dict(payload)
        merged.update(summary)
        return merged
    return dict(payload or {})


def _discover_latest_top_nightly() -> Path | None:
    candidates: list[tuple[str, Path]] = []
    for path in RUNS.glob("ligand_htvs_nightly_*_summary.json"):
        match = _TOP_NIGHTLY_RE.fullmatch(path.name)
        if match:
            candidates.append((match.group(1), path))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def _discover_nightly_scan_paths() -> list[Path]:
    candidates: list[tuple[str, Path]] = []
    for path in RUNS.glob("ligand_htvs_nightly_*summary.json"):
        top = _TOP_NIGHTLY_RE.fullmatch(path.name)
        smoke = _SMOKE_NIGHTLY_RE.fullmatch(path.name)
        if top:
            candidates.append((top.group(1) + "_top", path))
        elif smoke:
            candidates.append((smoke.group(1) + "_smoke", path))
    return [path for _, path in sorted(candidates, key=lambda item: item[0])]


def _recent_top_nightly_paths(limit: int = 3) -> list[Path]:
    candidates: list[tuple[str, Path]] = []
    for path in RUNS.glob("ligand_htvs_nightly_*_summary.json"):
        match = _TOP_NIGHTLY_RE.fullmatch(path.name)
        if match:
            candidates.append((match.group(1), path))
    return [path for _, path in sorted(candidates, key=lambda item: item[0])[-limit:]]


def _extract_generated_at(payload: dict[str, Any]) -> str:
    return _text(payload.get("generated_at_local"))


def _extract_failed_stage(payload: dict[str, Any]) -> str:
    return _text(payload.get("failed_stage"))


def _extract_service_error(payload: dict[str, Any]) -> str:
    return _text(dict(payload.get("service_result", {}) or {}).get("error_code"))


def _extract_nested_stage(payload: dict[str, Any], *path: str) -> dict[str, Any]:
    cursor: Any = payload
    for key in path:
        if not isinstance(cursor, dict):
            return {}
        cursor = cursor.get(key)
    return dict(cursor or {}) if isinstance(cursor, dict) else {}


def _primary_failed_stage(payload: dict[str, Any]) -> str:
    top = _extract_failed_stage(payload)
    if top and top != "smoke":
        return top
    smoke = _extract_nested_stage(payload, "stages", "smoke")
    smoke_stage = _extract_failed_stage(smoke)
    return smoke_stage or top


def _find_import_error_anchor(paths: list[Path]) -> dict[str, str]:
    latest: dict[str, str] = {}
    for path in paths:
        payload = _load_json(path)
        stage = _extract_nested_stage(payload, "stages", "stage1_ligand_mapping")
        if not stage:
            stage = _extract_nested_stage(payload, "stages", "smoke", "stages", "stage1_ligand_mapping")
        stderr_tail = _text(stage.get("stderr_tail"))
        if "ModuleNotFoundError" in stderr_tail and "No module named 'core'" in stderr_tail:
            latest = {
                "artifact": str(path.relative_to(ROOT)),
                "generated_at_local": _extract_generated_at(payload) or path.name,
                "failed_stage": "stage1_ligand_mapping",
                "stderr_tail": stderr_tail,
            }
    return latest


def _derive_nightly_companion_artifact(latest_nightly_artifact: str, suffix: str) -> str:
    if latest_nightly_artifact.endswith("_summary.json"):
        return latest_nightly_artifact.replace("_summary.json", suffix)
    return ""


def _latest_nightly_signal(
    latest_payload: dict[str, Any],
    latest_artifact: str,
    import_anchor: dict[str, str],
    recent_payloads: list[dict[str, Any]],
    nightly_gate_payload: dict[str, Any] | None = None,
    nightly_tuning_payload: dict[str, Any] | None = None,
    nightly_followup_payload: dict[str, Any] | None = None,
    nightly_sweep_payload: dict[str, Any] | None = None,
    nightly_probe_payload: dict[str, Any] | None = None,
    nightly_promotion_payload: dict[str, Any] | None = None,
    nightly_realization_payload: dict[str, Any] | None = None,
    nightly_rescored_payload: dict[str, Any] | None = None,
    nightly_downstream_rerun_payload: dict[str, Any] | None = None,
    nightly_execute_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    latest_pass = bool(latest_payload.get("pass", False))
    recent_fail_count = sum(1 for payload in recent_payloads if bool(payload) and not bool(payload.get("pass", False)))
    recent_stage_labels = [_primary_failed_stage(payload) for payload in recent_payloads]
    latest_smoke = _extract_nested_stage(latest_payload, "stages", "smoke")
    latest_failed_stage = _primary_failed_stage(latest_payload)
    latest_error_code = _extract_service_error(latest_payload)
    if not latest_error_code and latest_smoke:
        latest_error_code = _extract_service_error(latest_smoke)
    latest_stage2 = _extract_nested_stage(latest_smoke or latest_payload, "stages", "stage2_trajectory_generation")
    latest_stage6 = _extract_nested_stage(latest_smoke or latest_payload, "stages", "stage6_operational_gate")
    stage2_ok = bool(latest_stage2.get("ok", False) or latest_stage2.get("pass", False))
    stage2_returncode = latest_stage2.get("returncode")
    gate_failed_metrics = list(latest_stage6.get("failed_metrics") or [])
    first_gate_metric = dict(gate_failed_metrics[0] or {}) if gate_failed_metrics else {}
    gate_metric_name = _text(first_gate_metric.get("metric"))
    gate_metric_value = _float_text(first_gate_metric.get("value"))
    gate_metric_threshold = _float_text(first_gate_metric.get("threshold"))
    import_anchor_date = _text(import_anchor.get("generated_at_local"))
    import_anchor_artifact = _text(import_anchor.get("artifact"))
    nightly_gate_summary = dict((nightly_gate_payload or {}).get("summary", {}) or {})
    nightly_tuning_summary = dict((nightly_tuning_payload or {}).get("summary", {}) or {})
    gate_packet_artifact = _text(nightly_gate_summary.get("packet_artifact"))
    gate_packet_metric = _text(nightly_gate_summary.get("primary_gate_metric")) or gate_metric_name
    gate_packet_value = _text(nightly_gate_summary.get("primary_gate_value")) or gate_metric_value
    gate_packet_threshold = _text(nightly_gate_summary.get("primary_gate_threshold")) or gate_metric_threshold
    gate_packet_delta = _text(nightly_gate_summary.get("primary_gate_delta"))
    gate_packet_status_line = _text(nightly_gate_summary.get("status_line"))
    gate_packet_next_required_step = _text(nightly_gate_summary.get("next_required_step"))
    gate_packet_recent_transition_line = _text(nightly_gate_summary.get("recent_transition_line"))
    tuning_packet_artifact = _text(nightly_tuning_summary.get("packet_artifact"))
    tuning_full_band = bool(nightly_tuning_summary.get("topk_equals_full_unique_band", False))
    tuning_rows_above_threshold = _int(nightly_tuning_summary.get("rows_above_threshold_count"))
    tuning_min_rows_to_touch = _int(nightly_tuning_summary.get("minimum_rows_to_touch_if_clamped_to_threshold"))
    tuning_primary_focus = _text(nightly_tuning_summary.get("primary_focus_row_key"))
    nightly_followup_summary = dict((nightly_followup_payload or {}).get("summary", {}) or {})
    followup_packet_artifact = _text(nightly_followup_summary.get("packet_artifact"))
    followup_primary_focus = _text(nightly_followup_summary.get("primary_execution_focus_row_key"))
    followup_retry_rows = _int(nightly_followup_summary.get("retry_row_count"))
    followup_closure_rows = _int(nightly_followup_summary.get("closure_row_count"))
    nightly_sweep_summary = dict((nightly_sweep_payload or {}).get("summary", {}) or {})
    sweep_packet_artifact = _text(nightly_sweep_summary.get("packet_artifact"))
    sweep_primary_focus = _text(nightly_sweep_summary.get("primary_focus_row_key"))
    sweep_primary_preset = _text(nightly_sweep_summary.get("primary_preset_id"))
    sweep_preset_rows = _int(nightly_sweep_summary.get("sweep_preset_row_count"))
    sweep_retry_subset_queue_count = _int(nightly_sweep_summary.get("retry_subset_queue_count"))
    nightly_probe_summary = dict((nightly_probe_payload or {}).get("summary", {}) or {})
    probe_packet_artifact = _text(nightly_probe_summary.get("packet_artifact"))
    probe_primary_focus = _text(nightly_probe_summary.get("primary_probe_row_key"))
    probe_projected_gate_mean = _text(nightly_probe_summary.get("projected_gate_mean_min_distance_A"))
    probe_projected_gate_pass = bool(nightly_probe_summary.get("projected_gate_pass", False))
    nightly_promotion_summary = dict((nightly_promotion_payload or {}).get("summary", {}) or {})
    promotion_packet_artifact = _text(nightly_promotion_summary.get("packet_artifact"))
    promotion_primary_focus = _text(nightly_promotion_summary.get("primary_promoted_row_key"))
    promotion_primary_preset = _text(nightly_promotion_summary.get("primary_canonical_fallback_preset_id"))
    promotion_projected_gate_pass = bool(nightly_promotion_summary.get("projected_gate_pass", False))
    promotion_lane_ready = bool(
        nightly_promotion_summary.get(
            "canonical_retry_lane_ready",
            nightly_promotion_summary.get("projected_gate_pass", False),
        )
    )
    nightly_realization_summary = dict((nightly_realization_payload or {}).get("summary", {}) or {})
    realization_packet_artifact = _text(nightly_realization_summary.get("packet_artifact"))
    realization_primary_focus = _text(nightly_realization_summary.get("primary_realization_row_key"))
    realization_primary_preset = _text(nightly_realization_summary.get("primary_canonical_retry_preset_id"))
    realization_gate_mean = _text(nightly_realization_summary.get("realized_gate_mean_min_distance_A"))
    realization_gate_pass = bool(nightly_realization_summary.get("realized_gate_pass", False))
    realization_ready = bool(nightly_realization_summary.get("realization_ready", False))
    nightly_rescored_summary = dict((nightly_rescored_payload or {}).get("summary", {}) or {})
    rescored_packet_artifact = _text(nightly_rescored_summary.get("packet_artifact"))
    rescored_primary_focus = _text(nightly_rescored_summary.get("primary_applied_row_key"))
    rescored_primary_preset = _text(nightly_rescored_summary.get("primary_canonical_retry_preset_id"))
    rescored_gate_mean = _text(nightly_rescored_summary.get("rescored_gate_mean_min_distance_A"))
    rescored_gate_pass = bool(nightly_rescored_summary.get("rescored_gate_pass", False))
    rescored_rerun_ready = bool(nightly_rescored_summary.get("downstream_rerun_ready", False))
    nightly_downstream_rerun_summary = dict((nightly_downstream_rerun_payload or {}).get("summary", {}) or {})
    downstream_rerun_packet_artifact = _text(nightly_downstream_rerun_summary.get("packet_artifact"))
    downstream_rerun_primary_focus = _text(nightly_downstream_rerun_summary.get("primary_focus_row_key"))
    downstream_rerun_primary_preset = _text(nightly_downstream_rerun_summary.get("primary_canonical_retry_preset_id"))
    downstream_rerun_target_subset = _text(nightly_downstream_rerun_summary.get("target_subset"))
    downstream_rerun_profile_artifact = _text(
        nightly_downstream_rerun_summary.get("downstream_profile_json_artifact")
    )
    downstream_rerun_status_artifact = _text(
        nightly_downstream_rerun_summary.get("dry_run_status_json_artifact")
    )
    downstream_rerun_ready = bool(nightly_downstream_rerun_summary.get("downstream_rerun_ready", False))
    downstream_rerun_dry_run_status_present = bool(
        nightly_downstream_rerun_summary.get("dry_run_status_present", False)
    )
    downstream_rerun_dry_run_validated = bool(
        nightly_downstream_rerun_summary.get("dry_run_command_validated", False)
    )
    downstream_rerun_dry_run_payload_pass = bool(
        nightly_downstream_rerun_summary.get("dry_run_payload_pass", False)
    )
    nightly_execute_summary = dict((nightly_execute_payload or {}).get("summary", {}) or {})
    execute_packet_artifact = _text(nightly_execute_summary.get("packet_artifact"))
    execute_primary_focus = _text(nightly_execute_summary.get("primary_focus_row_key"))
    execute_primary_preset = _text(nightly_execute_summary.get("primary_canonical_retry_preset_id"))
    execute_target_subset = _text(nightly_execute_summary.get("target_subset"))
    execute_status_artifact = _text(nightly_execute_summary.get("execute_status_json_artifact"))
    execute_summary_artifact = _text(nightly_execute_summary.get("execute_pipeline_summary_json_artifact"))
    execute_gate_mean = _text(nightly_execute_summary.get("execute_gate_mean_min_distance_A"))
    execute_gate_pass = bool(nightly_execute_summary.get("execute_gate_pass", False))
    execute_payload_pass = bool(nightly_execute_summary.get("execute_payload_pass", False))
    execute_matches_rescored_gate = bool(nightly_execute_summary.get("execute_matches_rescored_gate", False))
    downstream_rerun_execute_status_artifact = execute_status_artifact or downstream_rerun_status_artifact
    downstream_rerun_execute_status_payload = (
        _maybe_load_json(downstream_rerun_execute_status_artifact) if downstream_rerun_execute_status_artifact else {}
    )
    downstream_rerun_execute_pass = (
        execute_payload_pass if execute_status_artifact else bool(downstream_rerun_execute_status_payload.get("pass", False))
    )
    source_signal = (
        f"latest_failed_stage={latest_failed_stage or '-'}; "
        f"latest_error_code={latest_error_code or '-'}; "
        f"recent_fail_count={recent_fail_count}/{max(len(recent_payloads), 1)}; "
        f"recent_failed_stages={', '.join(label or '-' for label in recent_stage_labels) or '-'}; "
        f"stage2_ok={stage2_ok}; "
        f"stage2_returncode={stage2_returncode if stage2_returncode is not None else '-'}; "
        f"stage6_gate_metric={gate_metric_name or '-'}; "
        f"stage6_gate_value={gate_metric_value}; "
        f"stage6_gate_threshold={gate_metric_threshold}; "
        f"stage6_gate_burndown_artifact={gate_packet_artifact or '-'}; "
        f"stage6_gate_burndown_delta={_float_text(gate_packet_delta)}; "
        f"stage6_gate_recent_transition={gate_packet_recent_transition_line or '-'}; "
        f"stage6_tuning_artifact={tuning_packet_artifact or '-'}; "
        f"stage6_tuning_full_band={tuning_full_band}; "
        f"stage6_tuning_rows_above_threshold={tuning_rows_above_threshold}; "
        f"stage6_tuning_min_rows_to_touch={tuning_min_rows_to_touch}; "
        f"stage6_tuning_primary_focus={tuning_primary_focus or '-'}; "
        f"stage6_followup_artifact={followup_packet_artifact or '-'}; "
        f"stage6_followup_retry_rows={followup_retry_rows}; "
        f"stage6_followup_closure_rows={followup_closure_rows}; "
        f"stage6_followup_primary_focus={followup_primary_focus or '-'}; "
        f"stage6_sweep_artifact={sweep_packet_artifact or '-'}; "
        f"stage6_sweep_preset_rows={sweep_preset_rows}; "
        f"stage6_sweep_subset_queue_count={sweep_retry_subset_queue_count}; "
        f"stage6_sweep_primary_focus={sweep_primary_focus or '-'}; "
        f"stage6_sweep_primary_preset={sweep_primary_preset or '-'}; "
        f"stage6_probe_artifact={probe_packet_artifact or '-'}; "
        f"stage6_probe_primary_focus={probe_primary_focus or '-'}; "
        f"stage6_probe_projected_gate_mean={probe_projected_gate_mean or '-'}; "
        f"stage6_probe_projected_gate_pass={probe_projected_gate_pass}; "
        f"stage6_promotion_artifact={promotion_packet_artifact or '-'}; "
        f"stage6_promotion_primary_focus={promotion_primary_focus or '-'}; "
        f"stage6_promotion_primary_preset={promotion_primary_preset or '-'}; "
        f"stage6_promotion_projected_gate_pass={promotion_projected_gate_pass}; "
        f"stage6_promotion_lane_ready={promotion_lane_ready}; "
        f"stage6_realization_artifact={realization_packet_artifact or '-'}; "
        f"stage6_realization_primary_focus={realization_primary_focus or '-'}; "
        f"stage6_realization_primary_preset={realization_primary_preset or '-'}; "
        f"stage6_realization_gate_mean={realization_gate_mean or '-'}; "
        f"stage6_realization_gate_pass={realization_gate_pass}; "
        f"stage6_realization_ready={realization_ready}; "
        f"stage6_rescored_artifact={rescored_packet_artifact or '-'}; "
        f"stage6_rescored_primary_focus={rescored_primary_focus or '-'}; "
        f"stage6_rescored_primary_preset={rescored_primary_preset or '-'}; "
        f"stage6_rescored_gate_mean={rescored_gate_mean or '-'}; "
        f"stage6_rescored_gate_pass={rescored_gate_pass}; "
        f"stage6_rescored_rerun_ready={rescored_rerun_ready}; "
        f"stage6_downstream_rerun_artifact={downstream_rerun_packet_artifact or '-'}; "
        f"stage6_downstream_rerun_primary_focus={downstream_rerun_primary_focus or '-'}; "
        f"stage6_downstream_rerun_primary_preset={downstream_rerun_primary_preset or '-'}; "
        f"stage6_downstream_rerun_target_subset={downstream_rerun_target_subset or '-'}; "
        f"stage6_downstream_rerun_ready={downstream_rerun_ready}; "
        f"stage6_downstream_rerun_profile_artifact={downstream_rerun_profile_artifact or '-'}; "
        f"stage6_downstream_rerun_dry_run_status_artifact={downstream_rerun_status_artifact or '-'}; "
        f"stage6_downstream_rerun_dry_run_status_present={downstream_rerun_dry_run_status_present}; "
        f"stage6_downstream_rerun_dry_run_validated={downstream_rerun_dry_run_validated}; "
        f"stage6_downstream_rerun_dry_run_payload_pass={downstream_rerun_dry_run_payload_pass}; "
        f"stage6_downstream_rerun_execute_status_artifact={downstream_rerun_execute_status_artifact or '-'}; "
        f"stage6_downstream_rerun_execute_pass={downstream_rerun_execute_pass}; "
        f"stage6_execute_artifact={execute_packet_artifact or '-'}; "
        f"stage6_execute_primary_focus={execute_primary_focus or '-'}; "
        f"stage6_execute_primary_preset={execute_primary_preset or '-'}; "
        f"stage6_execute_target_subset={execute_target_subset or '-'}; "
        f"stage6_execute_status_artifact={execute_status_artifact or '-'}; "
        f"stage6_execute_summary_artifact={execute_summary_artifact or '-'}; "
        f"stage6_execute_gate_mean={execute_gate_mean or '-'}; "
        f"stage6_execute_gate_pass={execute_gate_pass}; "
        f"stage6_execute_payload_pass={execute_payload_pass}; "
        f"stage6_execute_matches_rescored_gate={execute_matches_rescored_gate}; "
        f"import_anchor={import_anchor_date or '-'}"
    )
    if latest_pass:
        status = "keep_green"
        impact = "critical"
        status_line = "latest nightly pass is green; keep the recovered writer/import path stable while burning down viewer and wetlab blockers."
        next_required_action = (
            "Keep nightly green. Preserve the writer/import regression fix path and avoid reopening the old "
            "`ModuleNotFoundError: core` or writer-process failure lanes while downstream commercialization blockers are being burned down."
        )
    elif latest_failed_stage == "stage6_operational_gate" or latest_error_code == "HTVS_GATE_FAILED":
        status = "partial"
        impact = "critical"
        status_line = gate_packet_status_line or (
            "stage2 trajectory-generation now completes; the nightly lane is currently blocked by the operational gate at "
            f"{gate_metric_name or 'stage6_metric'}={gate_metric_value} versus threshold {gate_metric_threshold}."
        )
        next_required_action = (
            "Hold the recovered stage2 writer/import path green, then use "
            f"`{gate_packet_artifact or nightly_gate_burndown_mod.DEFAULT_OUT_MD}` as the nightly stage6 burndown surface so "
            f"`{gate_packet_metric or gate_metric_name or 'mean_min_distance_A'}` moves from "
            f"`{_float_text(gate_packet_value)}` to within the `{_float_text(gate_packet_threshold)}` threshold "
            "before treating nightly as commercial-grade. "
            + (
                gate_packet_next_required_step
                if gate_packet_next_required_step
                else "Burn down the current stage6 operational gate without reopening the recovered nightly writer/import path."
            )
            + (
                " "
                + (
                    f"Then open `{tuning_packet_artifact}` because the current `eval_unique_topk` band is fully enumerated there; "
                    f"`{tuning_rows_above_threshold}` rows are still above threshold and "
                    f"`{tuning_min_rows_to_touch}` rows need touch, starting from `{tuning_primary_focus}`."
                    if tuning_packet_artifact
                    else ""
                )
                + (
                    " "
                    + (
                        f"Then open `{followup_packet_artifact}` for row-level execution: "
                        f"`{followup_retry_rows}` retry rows and `{followup_closure_rows}` closure rows, led by `{followup_primary_focus}`."
                    )
                    if followup_packet_artifact
                    else ""
                )
                + (
                    " "
                    + (
                        f"Then open `{sweep_packet_artifact}` for executable subset reruns: "
                        f"`{sweep_preset_rows}` presets across `{sweep_retry_subset_queue_count}` subset queues, starting from "
                        f"`{sweep_primary_focus}` with `{sweep_primary_preset}`."
                    )
                    if sweep_packet_artifact
                    else ""
                )
                + (
                    " "
                    + (
                        f"Measured probes now project the gate to `{_float_text(probe_projected_gate_mean)}`; "
                        f"open `{probe_packet_artifact}` and promote `{probe_primary_focus}` plus its companion retry row into the canonical retry lane."
                    )
                    if probe_packet_artifact and probe_projected_gate_pass
                    else ""
                )
                + (
                    " "
                    + (
                        f"Use `{promotion_packet_artifact}` as the apply-ready promotion packet; "
                        f"`{promotion_primary_focus}` is the first canonical replacement row"
                        + (
                            f" and `{promotion_primary_preset}` stays attached as the capped fallback preset."
                            if promotion_primary_preset
                            else "."
                        )
                    )
                    if promotion_packet_artifact and promotion_lane_ready
                    else ""
                )
                + (
                    " "
                    + (
                        f"Use `{realization_packet_artifact}` as the measured canonical replacement packet; "
                        f"`{realization_primary_focus}` leads the realized lane and the gate already lands at "
                        f"`{_float_text(realization_gate_mean)}`."
                    )
                    if realization_packet_artifact and realization_ready and realization_gate_pass
                    else ""
                )
                + (
                    " "
                    + (
                        f"Use `{rescored_packet_artifact}` as the post-apply stage6 snapshot; "
                        f"`{rescored_primary_focus}` is the first locked replacement row and the rescored gate already lands at "
                        f"`{_float_text(rescored_gate_mean)}`, so the next move is an end-to-end nightly rerun rather than more stage6 tuning."
                    )
                    if rescored_packet_artifact and rescored_rerun_ready and rescored_gate_pass
                    else ""
                )
                + (
                    " "
                    + (
                        f"Then open `{downstream_rerun_packet_artifact}` as the exact downstream nightly rerun handoff for target subset "
                        f"`{downstream_rerun_target_subset or '-'}`: "
                        + (
                            (
                                f"`{downstream_rerun_execute_status_artifact}` already reports `pass=true` and the dry-run payload is also green, so the smoke handoff is confirmed."
                            )
                            if downstream_rerun_execute_pass and downstream_rerun_dry_run_payload_pass
                            else (
                                f"`{downstream_rerun_execute_status_artifact}` already reports `pass=true`, so the smoke handoff is confirmed."
                                if downstream_rerun_execute_pass
                                else (
                                    "the downstream dry-run seam is already validated and the next move is the non-dry-run smoke rerun."
                                    if downstream_rerun_dry_run_validated
                                    else "run the generated dry-run seam first before executing the rerun."
                                )
                            )
                        )
                    )
                    if downstream_rerun_packet_artifact and downstream_rerun_ready
                    else ""
                )
                + (
                    " "
                    + (
                        f"Use `{execute_packet_artifact}` as the measured non-dry-run smoke proof: target subset "
                        f"`{execute_target_subset or '-'}` already passes at `{_float_text(execute_gate_mean)}` and "
                        + (
                            "matches the rescored gate closely."
                            if execute_matches_rescored_gate
                            else "still needs a small execute-vs-rescored reconciliation check."
                        )
                    )
                    if execute_packet_artifact and execute_payload_pass and execute_gate_pass
                    else ""
                )
            )
        )
    else:
        status = "blocked"
        impact = "critical"
        status_line = (
            "nightly still crashes before the gate layer; preserve the old import fix path and keep the stage2 writer path reproducible "
            "until the smoke run reaches downstream gates."
        )
        next_required_action = (
            "Stabilize nightly in two passes: first, preserve the stage1 import/bootstrap fix path so the old "
            "`ModuleNotFoundError: core` regression stays dead; second, turn the current stage2 trajectory-generation "
            "failure into a reproducible targeted retry surface with a claim-safe pass condition before treating nightly as commercial-grade."
            + (
                " "
                + (
                    f"Keep `{probe_packet_artifact}` parked as the measured re-entry target because it still projects the gate to "
                    f"`{_float_text(probe_projected_gate_mean)}` once nightly reaches stage6 again."
                )
                if probe_packet_artifact and probe_projected_gate_pass
                else ""
            )
            + (
                " "
                + (
                    f"Keep `{promotion_packet_artifact}` parked as the canonical retry-lane promotion packet; "
                    f"`{promotion_primary_focus}` is already the first replacement row"
                    + (
                        f" with `{promotion_primary_preset}` attached as the capped fallback preset."
                        if promotion_primary_preset
                        else "."
                    )
                )
                if promotion_packet_artifact and promotion_lane_ready
                else ""
            )
        )
    return {
        "priority_rank": 1,
        "blocker_id": "nightly_reliability",
        "blocker_domain": "engine",
        "blocker_kind": "reliability",
        "status": status,
        "commercialization_impact": impact,
        "source_artifact": latest_artifact,
        "secondary_artifact": gate_packet_artifact or import_anchor_artifact,
        "source_signal": source_signal,
        "status_line": status_line,
        "next_required_action": next_required_action,
    }


def _viewer_signal(viewer_payload: dict[str, Any]) -> dict[str, Any]:
    viewer_data = _summaryish(viewer_payload)
    geometry_access = dict(viewer_data.get("geometry_access", {}) or {})
    if "compare_writeback" in geometry_access and isinstance(geometry_access.get("compare_writeback"), dict):
        geometry_access = dict(geometry_access.get("compare_writeback") or {})
    if not geometry_access:
        geometry_access = dict(((viewer_payload.get("geometry_access") or {}).get("compare_writeback") or {}) or {})
    compact = dict(viewer_data.get("geometry_probe_compact", {}) or {})
    if "compare_writeback" in compact and isinstance(compact.get("compare_writeback"), dict):
        compact = dict(compact.get("compare_writeback") or {})
    if not compact:
        compact = dict(((viewer_payload.get("geometry_probe") or {}).get("compare_writeback") or {}) or {})
    single = dict(compact.get("single", {}) or {})
    compare_a = dict(compact.get("compareA", {}) or {})
    compare_b = dict(compact.get("compareB", {}) or {})
    compare_pane_state_rep_count = _int(viewer_data.get("compare_writeback_compare_pane_state_rep_count"))
    wrapper_gap_count = _int(viewer_data.get("compare_writeback_wrapper_gap_count"))
    mesh_probe_unavailable_count = _int(viewer_data.get("compare_writeback_mesh_probe_unavailable_count"))
    geometry_burndown_status_line = _text(viewer_data.get("compare_writeback_geometry_burndown_status_line"))
    geometry_burndown_next_required_step = _text(viewer_data.get("compare_writeback_geometry_burndown_next_required_step"))
    keep_green_ready = bool(viewer_payload.get("overall_ok", False)) and (
        compare_pane_state_rep_count >= 2
        and wrapper_gap_count == 0
        and mesh_probe_unavailable_count == 0
        and bool(geometry_access.get("compareA_canvas_probe_ready"))
        and bool(geometry_access.get("compareB_canvas_probe_ready"))
    )
    source_signal = (
        f"overall_ok={viewer_payload.get('overall_ok', False)}; "
        f"single_canvas_probe_ready={geometry_access.get('single_canvas_probe_ready', False)}; "
        f"compareA_canvas_probe_ready={geometry_access.get('compareA_canvas_probe_ready', False)}; "
        f"compareB_canvas_probe_ready={geometry_access.get('compareB_canvas_probe_ready', False)}; "
        f"single_wrapper_gap={geometry_access.get('single_wrapper_gap', False)}; "
        f"compareA_wrapper_gap={geometry_access.get('compareA_wrapper_gap', False)}; "
        f"compareB_wrapper_gap={geometry_access.get('compareB_wrapper_gap', False)}; "
        f"single_renderables={single.get('renderable_count', 0)}; "
        f"compareA_renderables={compare_a.get('renderable_count', 0)}; "
        f"compareB_renderables={compare_b.get('renderable_count', 0)}; "
        f"compare_pane_state_rep_count={compare_pane_state_rep_count}; "
        f"wrapper_gap_count={wrapper_gap_count}; "
        f"mesh_probe_unavailable_count={mesh_probe_unavailable_count}; "
        f"geometry_status_line={_text(viewer_data.get('compare_writeback_geometry_status_line')) or '-'}"
    )
    next_required_action = (
        "Keep compare-writeback smoke green and treat the mesh-backed compare-pane proof as a regression guardrail while nightly "
        "and wetlab blockers burn down."
        if keep_green_ready
        else geometry_burndown_next_required_step
        or (
            "Keep the smoke suite green, but upgrade the viewer lane from 'viewer_ready_mesh_probe_unavailable' to a "
            "commercial-grade visual surface by closing the canvas/mesh probe gap and making at least one compare surface "
            "report real renderables instead of wrapper-only readiness."
        )
    )
    status_line = geometry_burndown_status_line or _text(viewer_data.get("compare_writeback_geometry_status_line")) or "viewer geometry status unavailable"
    return {
        "priority_rank": 2,
        "blocker_id": "viewer_usability",
        "blocker_domain": "engine",
        "blocker_kind": "ui",
        "status": "keep_green" if keep_green_ready else "partial",
        "commercialization_impact": "high",
        "source_artifact": DEFAULT_VIEWER_JSON,
        "secondary_artifact": "runs/viewer_smoke_refresh_current.md",
        "source_signal": source_signal,
        "status_line": status_line,
        "next_required_action": next_required_action,
    }


def _wetlab_signal(
    wetlab_dashboard: dict[str, Any],
    wetlab_final: dict[str, Any],
    wetlab_readiness: dict[str, Any] | None = None,
    wetlab_selected_allatom: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dashboard = _summaryish(wetlab_dashboard)
    final_summary = _summaryish(wetlab_final)
    readiness_summary = _summaryish(wetlab_readiness or {})
    selected_allatom_summary = _summaryish(wetlab_selected_allatom or {})
    primary_watch_liveness = _text(dashboard.get("broad_screen_primary_watch_liveness"))
    antitarget_watch_liveness = _text(dashboard.get("broad_screen_antitarget_watch_liveness"))
    watch_gap_count = sum(
        1
        for value in (primary_watch_liveness, antitarget_watch_liveness)
        if value and value not in {"attached", "healthy"}
    )
    source_signal = (
        f"ready_to_send_track_count={final_summary.get('ready_to_send_track_count', 0)}; "
        f"execution_ready_now_row_count={final_summary.get('broad_screen_execution_ready_now_row_count', 0)}; "
        f"primary_watch_liveness={primary_watch_liveness or '-'}; "
        f"antitarget_watch_liveness={antitarget_watch_liveness or '-'}; "
        f"watch_gap_count={watch_gap_count}; "
        f"selected_allatom_wetlab_gate_pass={dashboard.get('selected_allatom_wetlab_gate_pass', False)}"
    )
    if readiness_summary:
        source_signal = (
            f"{_text(readiness_summary.get('status_line')) or source_signal}; "
            f"blocked_row_count={readiness_summary.get('blocked_count', readiness_summary.get('blocked_row_count', 0))}; "
            f"partial_row_count={readiness_summary.get('partial_count', readiness_summary.get('partial_row_count', 0))}; "
            f"ready_row_count={readiness_summary.get('ready_count', readiness_summary.get('ready_row_count', 0))}"
        )
    if selected_allatom_summary:
        source_signal = (
            f"{source_signal}; "
            f"selected_allatom_target_id={_text(selected_allatom_summary.get('selected_allatom_target_id')) or '-'}; "
            f"selected_allatom_primary_burndown_code={_text(selected_allatom_summary.get('primary_burndown_code')) or '-'}; "
            f"selected_allatom_primary_burndown_metric={_text(selected_allatom_summary.get('primary_burndown_metric')) or '-'}; "
            f"selected_allatom_primary_burndown_value={_text(selected_allatom_summary.get('primary_burndown_value')) or '-'}; "
            f"selected_allatom_primary_burndown_threshold={_text(selected_allatom_summary.get('primary_burndown_threshold')) or '-'}; "
            f"selected_allatom_primary_burndown_delta={_text(selected_allatom_summary.get('primary_burndown_delta')) or '-'}; "
            f"selected_allatom_hard_block_count={selected_allatom_summary.get('hard_block_count', 0)}; "
            f"selected_allatom_semi_hard_block_count={selected_allatom_summary.get('semi_hard_block_count', 0)}; "
            f"selected_allatom_missing_metric_count={selected_allatom_summary.get('missing_metric_count', 0)}"
        )
    next_required_action = _text(readiness_summary.get("next_required_step")) or (
        "Treat wetlab as an engine commercialization blocker, not just a science appendix: recover the stale/detached "
        "watch loops, create at least one execution-ready row, and stop calling the lane commercially mature while the "
        "selected all-atom wetlab gate is still failed."
    )
    if selected_allatom_summary:
        next_required_action = (
            f"{next_required_action} Use "
            f"`{_text(selected_allatom_summary.get('packet_artifact')) or 'runs/wetlab_selected_allatom_gate_burndown_packet_current.md'}` "
            f"as the exact hard-block surface: start from "
            f"`{_text(selected_allatom_summary.get('primary_burndown_code')) or 'recompute_mean_min_distance_A'}`, "
            "then clear the missing claim-gate field, and only after the hard block lifts move on to claim/equivalence work."
        )
    status_line = _text(readiness_summary.get("status_line")) or (
        f"ready_now={final_summary.get('broad_screen_execution_ready_now_row_count', 0)}; "
        f"primary_watch={primary_watch_liveness or '-'}; "
        f"antitarget_watch={antitarget_watch_liveness or '-'}; "
        f"selected_allatom_gate={dashboard.get('selected_allatom_wetlab_gate_pass', False)}"
    )
    blocked_readiness = int(
        readiness_summary.get("blocked_count", readiness_summary.get("blocked_row_count", 0)) or 0
    )
    partial_readiness = int(
        readiness_summary.get("partial_count", readiness_summary.get("partial_row_count", 0)) or 0
    )
    ready_readiness = int(
        readiness_summary.get("ready_count", readiness_summary.get("ready_row_count", 0)) or 0
    )
    return {
        "priority_rank": 3,
        "blocker_id": "wetlab_execution_readiness",
        "blocker_domain": "engine",
        "blocker_kind": "ops_validation",
        "status": (
            "blocked"
            if blocked_readiness > 0
            else "partial"
            if partial_readiness > 0
            else "keep_green"
            if readiness_summary and ready_readiness > 0
            else "blocked"
        ),
        "commercialization_impact": "high",
        "source_artifact": _text(selected_allatom_summary.get("packet_artifact"))
        or (DEFAULT_WETLAB_READINESS_JSON if readiness_summary else DEFAULT_WETLAB_DASHBOARD_JSON),
        "secondary_artifact": DEFAULT_WETLAB_READINESS_JSON if selected_allatom_summary else DEFAULT_WETLAB_DASHBOARD_JSON,
        "source_signal": source_signal,
        "status_line": status_line,
        "next_required_action": next_required_action,
    }


def _reproducibility_signal(refresh_payload: dict[str, Any]) -> dict[str, Any]:
    refresh = _summaryish(refresh_payload)
    overall_ok = bool(refresh.get("overall_ok", False))
    step_count = _int(refresh.get("step_count"))
    ok_count = _int(refresh.get("ok_count"))
    source_signal = (
        f"overall_ok={overall_ok}; "
        f"ok_count={ok_count}; "
        f"step_count={step_count}; "
        f"first_failed_step={_text(refresh.get('first_failed_step')) or '-'}"
    )
    next_required_action = (
        "Keep this lane green. Use the 103/103 refresh pass as the reproducibility guardrail while nightly, viewer, "
        "and wetlab blockers are being burned down."
    )
    return {
        "priority_rank": 4,
        "blocker_id": "local_reproducibility_guardrail",
        "blocker_domain": "engine",
        "blocker_kind": "reproducibility",
        "status": "keep_green" if overall_ok else "blocked",
        "commercialization_impact": "medium",
        "source_artifact": DEFAULT_REFRESH_JSON,
        "secondary_artifact": "runs/family_expansion_refresh_current.md",
        "source_signal": source_signal,
        "next_required_action": next_required_action,
    }


def _transporter_signal(negative_queue_payload: dict[str, Any], gap_payload: dict[str, Any]) -> dict[str, Any]:
    negative_summary = dict(negative_queue_payload.get("summary", {}) or {})
    gap_summary = dict(gap_payload.get("summary", {}) or {})
    source_signal = (
        f"highest_gap_family={_text(gap_summary.get('highest_gap_family')) or '-'}; "
        f"queue_row_count={negative_summary.get('row_count', 0)}; "
        f"top_target_id={_text(negative_summary.get('top_target_id')) or '-'}; "
        f"top_packet_step={_text(negative_summary.get('top_packet_step')) or '-'}; "
        f"placeholder_driven_rows_remaining={negative_summary.get('placeholder_driven_rows_remaining', 0)}"
    )
    next_required_action = (
        "Park transporter as the science-blocker lane behind the engine blockers. Keep AQP1/GLUT1 negative evidence "
        "review-only, and only reopen this queue after nightly reliability, viewer usability, and wetlab execution "
        "surfaces are promoted to a safer local commercial baseline."
    )
    return {
        "priority_rank": 5,
        "blocker_id": "transporter_science_blocker",
        "blocker_domain": "science",
        "blocker_kind": "evidence",
        "status": "parked",
        "commercialization_impact": "medium",
        "source_artifact": DEFAULT_NEGATIVE_QUEUE_JSON,
        "secondary_artifact": "runs/commercialization_gap_burndown_current.md",
        "source_signal": source_signal,
        "next_required_action": next_required_action,
    }


def build_payload(
    latest_nightly_payload: dict[str, Any],
    latest_nightly_artifact: str,
    import_anchor: dict[str, str],
    recent_nightly_payloads: list[dict[str, Any]],
    nightly_gate_payload: dict[str, Any] | None,
    nightly_tuning_payload: dict[str, Any] | None,
    nightly_followup_payload: dict[str, Any] | None,
    viewer_payload: dict[str, Any],
    wetlab_dashboard_payload: dict[str, Any],
    wetlab_final_payload: dict[str, Any],
    wetlab_readiness_payload: dict[str, Any] | None,
    refresh_payload: dict[str, Any],
    negative_queue_payload: dict[str, Any],
    gap_payload: dict[str, Any],
    wetlab_selected_allatom_payload: dict[str, Any] | None = None,
    recent_nightly_artifacts: list[str] | None = None,
    nightly_sweep_payload: dict[str, Any] | None = None,
    nightly_probe_payload: dict[str, Any] | None = None,
    nightly_promotion_payload: dict[str, Any] | None = None,
    nightly_realization_payload: dict[str, Any] | None = None,
    nightly_rescored_payload: dict[str, Any] | None = None,
    nightly_downstream_rerun_payload: dict[str, Any] | None = None,
    nightly_execute_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    recent_nightly_artifacts = list(recent_nightly_artifacts or [])
    if not recent_nightly_artifacts:
        recent_nightly_artifacts = [latest_nightly_artifact for _ in recent_nightly_payloads]
    nightly_gate_payload = dict(nightly_gate_payload or {})
    nightly_gate_summary = dict(nightly_gate_payload.get("summary", {}) or {})
    nightly_tuning_payload = dict(nightly_tuning_payload or {})
    nightly_tuning_summary = dict(nightly_tuning_payload.get("summary", {}) or {})
    nightly_followup_payload = dict(nightly_followup_payload or {})
    nightly_followup_summary = dict(nightly_followup_payload.get("summary", {}) or {})
    nightly_sweep_supplied = nightly_sweep_payload is not None
    nightly_sweep_payload = dict(nightly_sweep_payload or {})
    nightly_sweep_summary = dict(nightly_sweep_payload.get("summary", {}) or {})
    nightly_probe_supplied = nightly_probe_payload is not None
    nightly_probe_payload = dict(nightly_probe_payload or {})
    nightly_probe_summary = dict(nightly_probe_payload.get("summary", {}) or {})
    nightly_promotion_supplied = nightly_promotion_payload is not None
    nightly_promotion_payload = dict(nightly_promotion_payload or {})
    nightly_promotion_summary = dict(nightly_promotion_payload.get("summary", {}) or {})
    nightly_realization_supplied = nightly_realization_payload is not None
    nightly_realization_payload = dict(nightly_realization_payload or {})
    nightly_realization_summary = dict(nightly_realization_payload.get("summary", {}) or {})
    nightly_rescored_supplied = nightly_rescored_payload is not None
    nightly_rescored_payload = dict(nightly_rescored_payload or {})
    nightly_rescored_summary = dict(nightly_rescored_payload.get("summary", {}) or {})
    nightly_downstream_rerun_supplied = nightly_downstream_rerun_payload is not None
    nightly_downstream_rerun_payload = dict(nightly_downstream_rerun_payload or {})
    nightly_downstream_rerun_summary = dict(nightly_downstream_rerun_payload.get("summary", {}) or {})
    nightly_execute_supplied = nightly_execute_payload is not None
    nightly_execute_payload = dict(nightly_execute_payload or {})
    nightly_execute_summary = dict(nightly_execute_payload.get("summary", {}) or {})
    wetlab_selected_allatom_payload = dict(wetlab_selected_allatom_payload or {})
    wetlab_selected_allatom_summary = dict(wetlab_selected_allatom_payload.get("summary", {}) or {})
    if not nightly_gate_summary:
        stage2_artifact = _derive_nightly_companion_artifact(latest_nightly_artifact, "_stage2_traj_summary.json")
        stage5_artifact = _derive_nightly_companion_artifact(latest_nightly_artifact, "_stage5_ranking_summary.json")
        nightly_gate_payload = nightly_gate_burndown_mod.build_payload(
            latest_nightly_payload=latest_nightly_payload,
            latest_nightly_artifact=latest_nightly_artifact,
            stage2_payload=_maybe_load_json(stage2_artifact) if stage2_artifact else {},
            stage2_artifact=stage2_artifact,
            stage5_payload=_maybe_load_json(stage5_artifact) if stage5_artifact else {},
            stage5_artifact=stage5_artifact,
            recent_nightly_payloads=recent_nightly_payloads,
            recent_nightly_artifacts=recent_nightly_artifacts,
        )
        nightly_gate_summary = dict(nightly_gate_payload.get("summary", {}) or {})
    if not nightly_tuning_summary:
        nightly_tuning_payload = _maybe_load_json(DEFAULT_NIGHTLY_TUNING_JSON)
        nightly_tuning_summary = dict(nightly_tuning_payload.get("summary", {}) or {})
    if not nightly_followup_summary:
        nightly_followup_payload = _maybe_load_json(DEFAULT_NIGHTLY_FOLLOWUP_JSON)
        nightly_followup_summary = dict(nightly_followup_payload.get("summary", {}) or {})
    if nightly_sweep_supplied and not nightly_sweep_summary:
        nightly_sweep_payload = _maybe_load_json(DEFAULT_NIGHTLY_SWEEP_JSON)
        nightly_sweep_summary = dict(nightly_sweep_payload.get("summary", {}) or {})
    if nightly_probe_supplied and not nightly_probe_summary:
        nightly_probe_payload = _maybe_load_json(DEFAULT_NIGHTLY_PROBE_JSON)
        nightly_probe_summary = dict(nightly_probe_payload.get("summary", {}) or {})
    if nightly_promotion_supplied and not nightly_promotion_summary:
        nightly_promotion_payload = _maybe_load_json(DEFAULT_NIGHTLY_PROMOTION_JSON)
        nightly_promotion_summary = dict(nightly_promotion_payload.get("summary", {}) or {})
    if nightly_realization_supplied and not nightly_realization_summary:
        nightly_realization_payload = _maybe_load_json(DEFAULT_NIGHTLY_REALIZATION_JSON)
        nightly_realization_summary = dict(nightly_realization_payload.get("summary", {}) or {})
    if nightly_rescored_supplied and not nightly_rescored_summary:
        nightly_rescored_payload = _maybe_load_json(DEFAULT_NIGHTLY_RESCORED_JSON)
        nightly_rescored_summary = dict(nightly_rescored_payload.get("summary", {}) or {})
    if nightly_downstream_rerun_supplied and not nightly_downstream_rerun_summary:
        nightly_downstream_rerun_payload = _maybe_load_json(DEFAULT_NIGHTLY_DOWNSTREAM_RERUN_JSON)
        nightly_downstream_rerun_summary = dict(nightly_downstream_rerun_payload.get("summary", {}) or {})
    if nightly_execute_supplied and not nightly_execute_summary:
        nightly_execute_payload = _maybe_load_json(DEFAULT_NIGHTLY_EXECUTE_JSON)
        nightly_execute_summary = dict(nightly_execute_payload.get("summary", {}) or {})
    downstream_rerun_execute_status_artifact = _text(
        nightly_execute_summary.get("execute_status_json_artifact")
    ) or _text(nightly_downstream_rerun_summary.get("dry_run_status_json_artifact"))
    downstream_rerun_execute_status_payload = (
        _maybe_load_json(downstream_rerun_execute_status_artifact) if downstream_rerun_execute_status_artifact else {}
    )
    downstream_rerun_execute_pass = bool(
        nightly_execute_summary.get(
            "execute_payload_pass",
            downstream_rerun_execute_status_payload.get("pass", False),
        )
    )
    rows = [
        _latest_nightly_signal(
            latest_nightly_payload,
            latest_nightly_artifact,
            import_anchor,
            recent_nightly_payloads,
            nightly_gate_payload,
            nightly_tuning_payload,
            nightly_followup_payload,
            nightly_sweep_payload,
            nightly_probe_payload,
            nightly_promotion_payload,
            nightly_realization_payload,
            nightly_rescored_payload,
            nightly_downstream_rerun_payload,
            nightly_execute_payload,
        ),
        _viewer_signal(viewer_payload),
        _wetlab_signal(
            wetlab_dashboard_payload,
            wetlab_final_payload,
            wetlab_readiness_payload,
            wetlab_selected_allatom_payload,
        ),
        _reproducibility_signal(refresh_payload),
        _transporter_signal(negative_queue_payload, gap_payload),
    ]
    rows.sort(key=lambda row: int(row["priority_rank"]))
    top_row = rows[0] if rows else {}
    rows_by_id = {row["blocker_id"]: row for row in rows}
    blocked_count = sum(1 for row in rows if row["status"] == "blocked")
    partial_count = sum(1 for row in rows if row["status"] == "partial")
    keep_green_count = sum(1 for row in rows if row["status"] == "keep_green")
    parked_count = sum(1 for row in rows if row["status"] == "parked")
    nightly_status_line = _text(rows_by_id.get("nightly_reliability", {}).get("status_line"))
    viewer_status_line = _text(rows_by_id.get("viewer_usability", {}).get("status_line"))
    wetlab_status_line = _text(rows_by_id.get("wetlab_execution_readiness", {}).get("status_line"))
    viewer_row = dict(rows_by_id.get("viewer_usability", {}) or {})
    viewer_keep_green = _text(viewer_row.get("status")) == "keep_green"
    wetlab_row = dict(rows_by_id.get("wetlab_execution_readiness", {}) or {})
    nightly_gate_artifact = (
        _text(nightly_gate_summary.get("packet_artifact")) or nightly_gate_burndown_mod.DEFAULT_OUT_MD
    ) if nightly_gate_summary else ""
    nightly_tuning_artifact = _text(nightly_tuning_summary.get("packet_artifact"))
    nightly_followup_artifact = _text(nightly_followup_summary.get("packet_artifact"))
    nightly_sweep_artifact = _text(nightly_sweep_summary.get("packet_artifact"))
    nightly_probe_artifact = _text(nightly_probe_summary.get("packet_artifact"))
    nightly_promotion_artifact = _text(nightly_promotion_summary.get("packet_artifact"))
    nightly_realization_artifact = _text(nightly_realization_summary.get("packet_artifact"))
    nightly_rescored_artifact = _text(nightly_rescored_summary.get("packet_artifact"))
    nightly_downstream_rerun_artifact = _text(nightly_downstream_rerun_summary.get("packet_artifact"))
    nightly_execute_artifact = _text(nightly_execute_summary.get("packet_artifact"))
    nightly_promotion_projected_gate_pass = bool(nightly_promotion_summary.get("projected_gate_pass", False))
    nightly_gate_metric = _text(nightly_gate_summary.get("primary_gate_metric"))
    nightly_gate_delta = _text(nightly_gate_summary.get("primary_gate_delta"))
    viewer_phrase = (
        "keep the viewer mesh-backed compare-pane proof green, recover "
        if viewer_keep_green
        else "close the viewer mesh/canvas gap, recover "
    )
    next_required_step = (
        (
            "Raise engine commercialization first: keep the recovered nightly writer/import path green, use "
            f"{nightly_gate_artifact or nightly_gate_burndown_mod.DEFAULT_OUT_MD} to burn down the stage6 gate for "
            f"{nightly_gate_metric or 'mean_min_distance_A'} (+{_float_text(nightly_gate_delta)} over threshold), "
            + (
                f"keep `{nightly_tuning_artifact}` open as the exact culprit-band packet, "
                if nightly_tuning_artifact
                else ""
            )
            + (
                f"keep `{nightly_followup_artifact}` open as the row-level retry/closure packet, "
                if nightly_followup_artifact
                else ""
            )
            + (
                f"keep `{nightly_sweep_artifact}` open as the executable subset-rerun packet, "
                if nightly_sweep_artifact
                else ""
            )
            + (
                f"keep `{nightly_probe_artifact}` open as the measured probe-result packet, "
                if nightly_probe_artifact
                else ""
            )
            + (
                f"keep `{nightly_promotion_artifact}` open as the canonical promotion packet, "
                if nightly_promotion_artifact
                else ""
            )
            + (
                f"keep `{nightly_realization_artifact}` open as the measured realization packet, "
                if nightly_realization_artifact
                else ""
            )
            + (
                f"keep `{nightly_rescored_artifact}` open as the post-apply rescored gate packet, "
                if nightly_rescored_artifact
                else ""
            )
            + (
                f"keep `{nightly_downstream_rerun_artifact}` open as the exact downstream nightly rerun packet, "
                if nightly_downstream_rerun_artifact
                else ""
            )
            + (
                f"keep `{nightly_execute_artifact}` open as the measured non-dry-run smoke execute packet, "
                if nightly_execute_artifact
                else ""
            )
            + viewer_phrase
            + "wetlab execution readiness, keep refresh reproducibility green, and leave transporter negative-evidence "
            "mining parked as a science blocker until the local engine surfaces are more trustworthy."
        )
        if _text(top_row.get("blocker_id")) == "nightly_reliability" and _text(top_row.get("status")) == "partial"
        else (
            "Raise engine commercialization first: fix nightly reliability, "
            + viewer_phrase
            + "wetlab execution readiness, keep refresh reproducibility green, and leave transporter negative-evidence "
            "mining parked as a science blocker until the local engine surfaces are more trustworthy."
        )
    )
    summary = {
        "local_only_mode": True,
        "row_count": len(rows),
        "blocked_count": blocked_count,
        "partial_count": partial_count,
        "keep_green_count": keep_green_count,
        "parked_science_blocker_count": parked_count,
        "top_priority_id": _text(top_row.get("blocker_id")),
        "top_priority_status": _text(top_row.get("status")),
        "engine_blocker_count": sum(1 for row in rows if row["blocker_domain"] == "engine"),
        "science_blocker_count": sum(1 for row in rows if row["blocker_domain"] == "science"),
        "nightly_blocker_artifact": _text(rows[0]["source_artifact"]) if rows else "",
        "viewer_artifact": DEFAULT_VIEWER_JSON,
        "wetlab_artifact": DEFAULT_WETLAB_DASHBOARD_JSON,
        "wetlab_readiness_artifact": DEFAULT_WETLAB_READINESS_JSON,
        "refresh_guardrail_artifact": DEFAULT_REFRESH_JSON,
        "transporter_artifact": DEFAULT_NEGATIVE_QUEUE_JSON,
        "nightly_status_line": nightly_status_line,
        "nightly_gate_burndown_ready": bool(nightly_gate_summary),
        "nightly_gate_burndown_artifact": nightly_gate_artifact,
        "nightly_gate_status": _text(nightly_gate_summary.get("status")),
        "nightly_gate_status_line": _text(nightly_gate_summary.get("status_line")),
        "nightly_gate_primary_metric": _text(nightly_gate_summary.get("primary_gate_metric")),
        "nightly_gate_primary_value": _text(nightly_gate_summary.get("primary_gate_value")),
        "nightly_gate_primary_threshold": _text(nightly_gate_summary.get("primary_gate_threshold")),
        "nightly_gate_primary_delta": _text(nightly_gate_summary.get("primary_gate_delta")),
        "nightly_gate_recent_transition_line": _text(nightly_gate_summary.get("recent_transition_line")),
        "nightly_gate_recent_stage6_fail_count": _int(nightly_gate_summary.get("recent_stage6_fail_count")),
        "nightly_gate_next_required_step": _text(nightly_gate_summary.get("next_required_step")),
        "nightly_stage6_tuning_ready": bool(nightly_tuning_summary),
        "nightly_stage6_tuning_artifact": nightly_tuning_artifact,
        "nightly_stage6_tuning_primary_focus_row_key": _text(nightly_tuning_summary.get("primary_focus_row_key")),
        "nightly_stage6_tuning_rows_above_threshold_count": _int(nightly_tuning_summary.get("rows_above_threshold_count")),
        "nightly_stage6_tuning_minimum_rows_to_touch": _int(
            nightly_tuning_summary.get("minimum_rows_to_touch_if_clamped_to_threshold")
        ),
        "nightly_stage6_tuning_topk_equals_full_unique_band": bool(
            nightly_tuning_summary.get("topk_equals_full_unique_band", False)
        ),
        "nightly_stage6_followup_ready": bool(nightly_followup_summary),
        "nightly_stage6_followup_artifact": nightly_followup_artifact,
        "nightly_stage6_followup_primary_focus_row_key": _text(
            nightly_followup_summary.get("primary_execution_focus_row_key")
        ),
        "nightly_stage6_followup_retry_row_count": _int(nightly_followup_summary.get("retry_row_count")),
        "nightly_stage6_followup_closure_row_count": _int(nightly_followup_summary.get("closure_row_count")),
        "nightly_stage6_sweep_ready": bool(nightly_sweep_summary),
        "nightly_stage6_sweep_artifact": nightly_sweep_artifact,
        "nightly_stage6_sweep_primary_focus_row_key": _text(nightly_sweep_summary.get("primary_focus_row_key")),
        "nightly_stage6_sweep_primary_preset_id": _text(nightly_sweep_summary.get("primary_preset_id")),
        "nightly_stage6_sweep_preset_row_count": _int(nightly_sweep_summary.get("sweep_preset_row_count")),
        "nightly_stage6_sweep_retry_subset_queue_count": _int(
            nightly_sweep_summary.get("retry_subset_queue_count")
        ),
        "nightly_stage6_probe_ready": bool(nightly_probe_summary),
        "nightly_stage6_probe_artifact": nightly_probe_artifact,
        "nightly_stage6_probe_primary_focus_row_key": _text(nightly_probe_summary.get("primary_probe_row_key")),
        "nightly_stage6_probe_projected_gate_mean_min_distance_A": _text(
            nightly_probe_summary.get("projected_gate_mean_min_distance_A")
        ),
        "nightly_stage6_probe_projected_gate_pass": bool(nightly_probe_summary.get("projected_gate_pass", False)),
        "nightly_stage6_promotion_ready": bool(nightly_promotion_summary),
        "nightly_stage6_promotion_artifact": nightly_promotion_artifact,
        "nightly_stage6_promotion_primary_focus_row_key": _text(
            nightly_promotion_summary.get("primary_promoted_row_key")
        ),
        "nightly_stage6_promotion_primary_preset_id": _text(
            nightly_promotion_summary.get("primary_canonical_fallback_preset_id")
        ),
        "nightly_stage6_promotion_projected_gate_pass": nightly_promotion_projected_gate_pass,
        "nightly_stage6_promotion_canonical_retry_lane_ready": bool(
            nightly_promotion_summary.get(
                "canonical_retry_lane_ready",
                nightly_promotion_summary.get("projected_gate_pass", False),
            )
        ),
        "nightly_stage6_realization_ready": bool(nightly_realization_summary),
        "nightly_stage6_realization_artifact": nightly_realization_artifact,
        "nightly_stage6_realization_primary_focus_row_key": _text(
            nightly_realization_summary.get("primary_realization_row_key")
        ),
        "nightly_stage6_realization_primary_preset_id": _text(
            nightly_realization_summary.get("primary_canonical_retry_preset_id")
        ),
        "nightly_stage6_realization_gate_mean_min_distance_A": _text(
            nightly_realization_summary.get("realized_gate_mean_min_distance_A")
        ),
        "nightly_stage6_realization_gate_pass": bool(
            nightly_realization_summary.get("realized_gate_pass", False)
        ),
        "nightly_stage6_realization_packet_ready": bool(
            nightly_realization_summary.get("realization_ready", False)
        ),
        "nightly_stage6_rescored_gate_ready": bool(nightly_rescored_summary),
        "nightly_stage6_rescored_gate_artifact": nightly_rescored_artifact,
        "nightly_stage6_rescored_gate_primary_focus_row_key": _text(
            nightly_rescored_summary.get("primary_applied_row_key")
        ),
        "nightly_stage6_rescored_gate_primary_preset_id": _text(
            nightly_rescored_summary.get("primary_canonical_retry_preset_id")
        ),
        "nightly_stage6_rescored_gate_mean_min_distance_A": _text(
            nightly_rescored_summary.get("rescored_gate_mean_min_distance_A")
        ),
        "nightly_stage6_rescored_gate_pass": bool(
            nightly_rescored_summary.get("rescored_gate_pass", False)
        ),
        "nightly_stage6_rescored_gate_packet_ready": bool(
            nightly_rescored_summary
        ),
        "nightly_stage6_downstream_rerun_ready": bool(nightly_downstream_rerun_summary),
        "nightly_stage6_downstream_rerun_artifact": nightly_downstream_rerun_artifact,
        "nightly_stage6_downstream_rerun_primary_focus_row_key": _text(
            nightly_downstream_rerun_summary.get("primary_focus_row_key")
        ),
        "nightly_stage6_downstream_rerun_primary_preset_id": _text(
            nightly_downstream_rerun_summary.get("primary_canonical_retry_preset_id")
        ),
        "nightly_stage6_downstream_rerun_target_subset": _text(
            nightly_downstream_rerun_summary.get("target_subset")
        ),
        "nightly_stage6_downstream_rerun_profile_json_artifact": _text(
            nightly_downstream_rerun_summary.get("downstream_profile_json_artifact")
        ),
        "nightly_stage6_downstream_rerun_execute_status_artifact": downstream_rerun_execute_status_artifact,
        "nightly_stage6_downstream_rerun_execute_pass": downstream_rerun_execute_pass,
        "nightly_stage6_downstream_rerun_dry_run_status_artifact": _text(
            nightly_downstream_rerun_summary.get("dry_run_status_json_artifact")
        ),
        "nightly_stage6_downstream_rerun_dry_run_validated": bool(
            nightly_downstream_rerun_summary.get("dry_run_command_validated", False)
        ),
        "nightly_stage6_downstream_rerun_payload_pass": bool(
            nightly_downstream_rerun_summary.get("dry_run_payload_pass", False)
        ),
        "nightly_stage6_execute_ready": bool(nightly_execute_summary),
        "nightly_stage6_execute_artifact": nightly_execute_artifact,
        "nightly_stage6_execute_primary_focus_row_key": _text(
            nightly_execute_summary.get("primary_focus_row_key")
        ),
        "nightly_stage6_execute_primary_preset_id": _text(
            nightly_execute_summary.get("primary_canonical_retry_preset_id")
        ),
        "nightly_stage6_execute_target_subset": _text(
            nightly_execute_summary.get("target_subset")
        ),
        "nightly_stage6_execute_status_json_artifact": _text(
            nightly_execute_summary.get("execute_status_json_artifact")
        ),
        "nightly_stage6_execute_pipeline_summary_json_artifact": _text(
            nightly_execute_summary.get("execute_pipeline_summary_json_artifact")
        ),
        "nightly_stage6_execute_gate_mean_min_distance_A": _text(
            nightly_execute_summary.get("execute_gate_mean_min_distance_A")
        ),
        "nightly_stage6_execute_gate_pass": bool(
            nightly_execute_summary.get("execute_gate_pass", False)
        ),
        "nightly_stage6_execute_payload_pass": bool(
            nightly_execute_summary.get("execute_payload_pass", False)
        ),
        "nightly_stage6_execute_matches_rescored_gate": bool(
            nightly_execute_summary.get("execute_matches_rescored_gate", False)
        ),
        "viewer_status": _text(viewer_row.get("status")),
        "viewer_status_line": viewer_status_line,
        "wetlab_status": _text(wetlab_row.get("status")),
        "wetlab_status_line": wetlab_status_line,
        "wetlab_selected_allatom_gate_burndown_artifact": _text(
            wetlab_selected_allatom_summary.get("packet_artifact")
        ),
        "wetlab_selected_allatom_target_id": _text(
            wetlab_selected_allatom_summary.get("selected_allatom_target_id")
        ),
        "wetlab_selected_allatom_focus_artifact": _text(
            wetlab_selected_allatom_summary.get("selected_allatom_focus_artifact")
        ),
        "wetlab_selected_allatom_primary_burndown_code": _text(
            wetlab_selected_allatom_summary.get("primary_burndown_code")
        ),
        "wetlab_selected_allatom_primary_burndown_metric": _text(
            wetlab_selected_allatom_summary.get("primary_burndown_metric")
        ),
        "wetlab_selected_allatom_primary_burndown_value": _text(
            wetlab_selected_allatom_summary.get("primary_burndown_value")
        ),
        "wetlab_selected_allatom_primary_burndown_threshold": _text(
            wetlab_selected_allatom_summary.get("primary_burndown_threshold")
        ),
        "wetlab_selected_allatom_primary_burndown_delta": _text(
            wetlab_selected_allatom_summary.get("primary_burndown_delta")
        ),
        "wetlab_selected_allatom_hard_block_count": _int(
            wetlab_selected_allatom_summary.get("hard_block_count")
        ),
        "wetlab_selected_allatom_semi_hard_block_count": _int(
            wetlab_selected_allatom_summary.get("semi_hard_block_count")
        ),
        "wetlab_selected_allatom_soft_deferred_count": _int(
            wetlab_selected_allatom_summary.get("soft_deferred_count")
        ),
        "wetlab_selected_allatom_missing_metric_count": _int(
            wetlab_selected_allatom_summary.get("missing_metric_count")
        ),
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Local Engine Commercialization Queue",
        "",
        f"- local_only_mode: `{summary['local_only_mode']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- blocked_count: `{summary['blocked_count']}`",
        f"- partial_count: `{summary['partial_count']}`",
        f"- keep_green_count: `{summary['keep_green_count']}`",
        f"- parked_science_blocker_count: `{summary['parked_science_blocker_count']}`",
        f"- top_priority_id: `{summary['top_priority_id']}`",
        f"- top_priority_status: `{summary['top_priority_status']}`",
        f"- nightly_status_line: `{summary['nightly_status_line'] or '-'}`",
        f"- nightly_gate_burndown_artifact: `{summary['nightly_gate_burndown_artifact'] or '-'}`",
        f"- nightly_gate_primary_metric: `{summary['nightly_gate_primary_metric'] or '-'}`",
        f"- nightly_gate_primary_delta: `{summary['nightly_gate_primary_delta'] or '-'}`",
        f"- nightly_stage6_tuning_artifact: `{summary['nightly_stage6_tuning_artifact'] or '-'}`",
        f"- nightly_stage6_tuning_primary_focus_row_key: `{summary['nightly_stage6_tuning_primary_focus_row_key'] or '-'}`",
        f"- nightly_stage6_followup_artifact: `{summary['nightly_stage6_followup_artifact'] or '-'}`",
        f"- nightly_stage6_followup_primary_focus_row_key: `{summary['nightly_stage6_followup_primary_focus_row_key'] or '-'}`",
        f"- nightly_stage6_sweep_artifact: `{summary['nightly_stage6_sweep_artifact'] or '-'}`",
        f"- nightly_stage6_sweep_primary_focus_row_key: `{summary['nightly_stage6_sweep_primary_focus_row_key'] or '-'}`",
        f"- nightly_stage6_sweep_primary_preset_id: `{summary['nightly_stage6_sweep_primary_preset_id'] or '-'}`",
        f"- nightly_stage6_probe_artifact: `{summary['nightly_stage6_probe_artifact'] or '-'}`",
        f"- nightly_stage6_probe_primary_focus_row_key: `{summary['nightly_stage6_probe_primary_focus_row_key'] or '-'}`",
        f"- nightly_stage6_probe_projected_gate_pass: `{summary['nightly_stage6_probe_projected_gate_pass']}`",
        f"- nightly_stage6_promotion_artifact: `{summary['nightly_stage6_promotion_artifact'] or '-'}`",
        f"- nightly_stage6_promotion_primary_focus_row_key: `{summary['nightly_stage6_promotion_primary_focus_row_key'] or '-'}`",
        f"- nightly_stage6_promotion_primary_preset_id: `{summary['nightly_stage6_promotion_primary_preset_id'] or '-'}`",
        f"- nightly_stage6_promotion_projected_gate_pass: `{summary['nightly_stage6_promotion_projected_gate_pass']}`",
        f"- nightly_stage6_promotion_canonical_retry_lane_ready: `{summary['nightly_stage6_promotion_canonical_retry_lane_ready']}`",
        f"- nightly_stage6_realization_artifact: `{summary['nightly_stage6_realization_artifact'] or '-'}`",
        f"- nightly_stage6_realization_primary_focus_row_key: `{summary['nightly_stage6_realization_primary_focus_row_key'] or '-'}`",
        f"- nightly_stage6_realization_primary_preset_id: `{summary['nightly_stage6_realization_primary_preset_id'] or '-'}`",
        f"- nightly_stage6_realization_gate_mean_min_distance_A: `{summary['nightly_stage6_realization_gate_mean_min_distance_A'] or '-'}`",
        f"- nightly_stage6_realization_gate_pass: `{summary['nightly_stage6_realization_gate_pass']}`",
        f"- nightly_stage6_realization_packet_ready: `{summary['nightly_stage6_realization_packet_ready']}`",
        f"- nightly_stage6_rescored_gate_artifact: `{summary['nightly_stage6_rescored_gate_artifact'] or '-'}`",
        f"- nightly_stage6_rescored_gate_primary_focus_row_key: `{summary['nightly_stage6_rescored_gate_primary_focus_row_key'] or '-'}`",
        f"- nightly_stage6_rescored_gate_primary_preset_id: `{summary['nightly_stage6_rescored_gate_primary_preset_id'] or '-'}`",
        f"- nightly_stage6_rescored_gate_mean_min_distance_A: `{summary['nightly_stage6_rescored_gate_mean_min_distance_A'] or '-'}`",
        f"- nightly_stage6_rescored_gate_pass: `{summary['nightly_stage6_rescored_gate_pass']}`",
        f"- nightly_stage6_rescored_gate_packet_ready: `{summary['nightly_stage6_rescored_gate_packet_ready']}`",
        f"- nightly_stage6_downstream_rerun_artifact: `{summary['nightly_stage6_downstream_rerun_artifact'] or '-'}`",
        f"- nightly_stage6_downstream_rerun_primary_focus_row_key: `{summary['nightly_stage6_downstream_rerun_primary_focus_row_key'] or '-'}`",
        f"- nightly_stage6_downstream_rerun_primary_preset_id: `{summary['nightly_stage6_downstream_rerun_primary_preset_id'] or '-'}`",
        f"- nightly_stage6_downstream_rerun_target_subset: `{summary['nightly_stage6_downstream_rerun_target_subset'] or '-'}`",
        f"- nightly_stage6_downstream_rerun_profile_json_artifact: `{summary['nightly_stage6_downstream_rerun_profile_json_artifact'] or '-'}`",
        f"- nightly_stage6_downstream_rerun_dry_run_status_artifact: `{summary['nightly_stage6_downstream_rerun_dry_run_status_artifact'] or '-'}`",
        f"- nightly_stage6_downstream_rerun_dry_run_validated: `{summary['nightly_stage6_downstream_rerun_dry_run_validated']}`",
        f"- nightly_stage6_downstream_rerun_payload_pass: `{summary['nightly_stage6_downstream_rerun_payload_pass']}`",
        f"- nightly_stage6_downstream_rerun_execute_status_artifact: `{summary['nightly_stage6_downstream_rerun_execute_status_artifact'] or '-'}`",
        f"- nightly_stage6_downstream_rerun_execute_pass: `{summary['nightly_stage6_downstream_rerun_execute_pass']}`",
        f"- nightly_stage6_execute_artifact: `{summary['nightly_stage6_execute_artifact'] or '-'}`",
        f"- nightly_stage6_execute_primary_focus_row_key: `{summary['nightly_stage6_execute_primary_focus_row_key'] or '-'}`",
        f"- nightly_stage6_execute_primary_preset_id: `{summary['nightly_stage6_execute_primary_preset_id'] or '-'}`",
        f"- nightly_stage6_execute_target_subset: `{summary['nightly_stage6_execute_target_subset'] or '-'}`",
        f"- nightly_stage6_execute_status_json_artifact: `{summary['nightly_stage6_execute_status_json_artifact'] or '-'}`",
        f"- nightly_stage6_execute_pipeline_summary_json_artifact: `{summary['nightly_stage6_execute_pipeline_summary_json_artifact'] or '-'}`",
        f"- nightly_stage6_execute_gate_mean_min_distance_A: `{summary['nightly_stage6_execute_gate_mean_min_distance_A'] or '-'}`",
        f"- nightly_stage6_execute_gate_pass: `{summary['nightly_stage6_execute_gate_pass']}`",
        f"- nightly_stage6_execute_payload_pass: `{summary['nightly_stage6_execute_payload_pass']}`",
        f"- nightly_stage6_execute_matches_rescored_gate: `{summary['nightly_stage6_execute_matches_rescored_gate']}`",
        f"- viewer_status_line: `{summary['viewer_status_line'] or '-'}`",
        f"- wetlab_status_line: `{summary['wetlab_status_line'] or '-'}`",
        f"- wetlab_selected_allatom_gate_burndown_artifact: `{summary['wetlab_selected_allatom_gate_burndown_artifact'] or '-'}`",
        f"- wetlab_selected_allatom_target_id: `{summary['wetlab_selected_allatom_target_id'] or '-'}`",
        f"- wetlab_selected_allatom_focus_artifact: `{summary['wetlab_selected_allatom_focus_artifact'] or '-'}`",
        f"- wetlab_selected_allatom_primary_burndown_code: `{summary['wetlab_selected_allatom_primary_burndown_code'] or '-'}`",
        f"- wetlab_selected_allatom_primary_burndown_metric: `{summary['wetlab_selected_allatom_primary_burndown_metric'] or '-'}`",
        f"- wetlab_selected_allatom_primary_burndown_delta: `{summary['wetlab_selected_allatom_primary_burndown_delta'] or '-'}`",
        f"- wetlab_selected_allatom_hard_block_count: `{summary['wetlab_selected_allatom_hard_block_count']}`",
        f"- wetlab_selected_allatom_semi_hard_block_count: `{summary['wetlab_selected_allatom_semi_hard_block_count']}`",
        f"- wetlab_selected_allatom_soft_deferred_count: `{summary['wetlab_selected_allatom_soft_deferred_count']}`",
        f"- wetlab_selected_allatom_missing_metric_count: `{summary['wetlab_selected_allatom_missing_metric_count']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Queue",
        "",
        "| priority | blocker_id | domain | kind | status | impact | source_artifact | source_signal | next_required_action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['blocker_id']}` | `{row['blocker_domain']}` | "
            f"`{row['blocker_kind']}` | `{row['status']}` | `{row['commercialization_impact']}` | "
            f"`{row['source_artifact']}` | `{row['source_signal']}` | `{row['next_required_action']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the local-engine commercialization queue.")
    parser.add_argument("--viewer-json", default=DEFAULT_VIEWER_JSON)
    parser.add_argument("--nightly-gate-json", default=DEFAULT_NIGHTLY_GATE_JSON)
    parser.add_argument("--nightly-tuning-json", default=DEFAULT_NIGHTLY_TUNING_JSON)
    parser.add_argument("--nightly-followup-json", default=DEFAULT_NIGHTLY_FOLLOWUP_JSON)
    parser.add_argument("--nightly-sweep-json", default=DEFAULT_NIGHTLY_SWEEP_JSON)
    parser.add_argument("--nightly-probe-json", default=DEFAULT_NIGHTLY_PROBE_JSON)
    parser.add_argument("--nightly-promotion-json", default=DEFAULT_NIGHTLY_PROMOTION_JSON)
    parser.add_argument("--nightly-realization-json", default=DEFAULT_NIGHTLY_REALIZATION_JSON)
    parser.add_argument("--nightly-rescored-json", default=DEFAULT_NIGHTLY_RESCORED_JSON)
    parser.add_argument("--nightly-downstream-rerun-json", default=DEFAULT_NIGHTLY_DOWNSTREAM_RERUN_JSON)
    parser.add_argument("--nightly-execute-json", default=DEFAULT_NIGHTLY_EXECUTE_JSON)
    parser.add_argument("--wetlab-dashboard-json", default=DEFAULT_WETLAB_DASHBOARD_JSON)
    parser.add_argument("--wetlab-final-json", default=DEFAULT_WETLAB_FINAL_JSON)
    parser.add_argument("--wetlab-readiness-json", default=DEFAULT_WETLAB_READINESS_JSON)
    parser.add_argument("--wetlab-selected-allatom-json", default=DEFAULT_WETLAB_SELECTED_ALLATOM_JSON)
    parser.add_argument("--refresh-json", default=DEFAULT_REFRESH_JSON)
    parser.add_argument("--negative-queue-json", default=DEFAULT_NEGATIVE_QUEUE_JSON)
    parser.add_argument("--gap-json", default=DEFAULT_GAP_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    latest_nightly_path = _discover_latest_top_nightly()
    latest_nightly_payload = _load_json(latest_nightly_path) if latest_nightly_path else {}
    latest_nightly_artifact = (
        str(latest_nightly_path.relative_to(ROOT)) if latest_nightly_path else "runs/ligand_htvs_nightly_latest_summary.json"
    )
    recent_nightly_payloads = [_load_json(path) for path in _recent_top_nightly_paths(limit=3)]
    import_anchor = _find_import_error_anchor(_discover_nightly_scan_paths())
    payload = build_payload(
        latest_nightly_payload=latest_nightly_payload,
        latest_nightly_artifact=latest_nightly_artifact,
        import_anchor=import_anchor,
        recent_nightly_payloads=recent_nightly_payloads,
        nightly_gate_payload=_maybe_load_json(args.nightly_gate_json),
        nightly_tuning_payload=_maybe_load_json(args.nightly_tuning_json),
        nightly_followup_payload=_maybe_load_json(args.nightly_followup_json),
        nightly_sweep_payload=_maybe_load_json(args.nightly_sweep_json),
        nightly_probe_payload=_maybe_load_json(args.nightly_probe_json),
        nightly_promotion_payload=_maybe_load_json(args.nightly_promotion_json),
        nightly_realization_payload=_maybe_load_json(args.nightly_realization_json),
        nightly_rescored_payload=_maybe_load_json(args.nightly_rescored_json),
        nightly_downstream_rerun_payload=_maybe_load_json(args.nightly_downstream_rerun_json),
        nightly_execute_payload=_maybe_load_json(args.nightly_execute_json),
        viewer_payload=_load_json(args.viewer_json),
        wetlab_dashboard_payload=_load_json(args.wetlab_dashboard_json),
        wetlab_final_payload=_load_json(args.wetlab_final_json),
        wetlab_readiness_payload=_maybe_load_json(args.wetlab_readiness_json),
        wetlab_selected_allatom_payload=_maybe_load_json(args.wetlab_selected_allatom_json),
        refresh_payload=_load_json(args.refresh_json),
        negative_queue_payload=_load_json(args.negative_queue_json),
        gap_payload=_load_json(args.gap_json),
        recent_nightly_artifacts=[str(path.relative_to(ROOT)) for path in _recent_top_nightly_paths(limit=3)],
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
