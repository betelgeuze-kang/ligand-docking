#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shlex
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BURNDOWN_JSON = "runs/wetlab_selected_allatom_gate_burndown_packet_current.json"
DEFAULT_REVIEW_JSON = "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json"
DEFAULT_RESCUE_LANE_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.json"
DEFAULT_ALLATOM_RESCUE_RUNNER_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_selected_allatom_repair_packet_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_selected_allatom_repair_packet_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_selected_allatom_repair_packet_current.md"
DEFAULT_ACCURACY_EXTERNAL_CSV = "runs/accuracy_gate_local_delivery_preflight_current.csv"
ACCURACY_EXTERNAL_REQUIRED_COLUMNS = ("avg_rmsd_aligned", "avg_rmsd_vs_native_aligned")
HARD_GATE_REPAIR_COMMAND = (
    "python3 tools/run_wetlab_tcruzi_pde_allatom_rescue.py "
    "--top-k 8 --filter-mode strict_then_near_fill --execute"
)
BINDING_PROXY_REPAIR_COMMAND = (
    HARD_GATE_REPAIR_COMMAND
    + " --clash-relief-mode translate --clash-relief-target-min-distance-A 2.12"
)
CLAIM_INPUT_BUILD_COMMAND = (
    "python3 tools/build_claim_inputs_from_openmm_manifest.py "
    "--manifest-csv <openmm_manifest.csv> --targets \"T. cruzi PDE\""
)
CLAIM_READINESS_COMMAND = (
    "python3 tools/run_allatom_claim_readiness.py "
    "--strict-summary-json <strict_summary.json> "
    "--accuracy-external-csv <accuracy_external.csv> "
    "--kinetics-input-csv <kinetics.csv> "
    "--thermo-input-csv <thermo.csv> "
    "--experiment-input-csv <experiment.csv> "
    "--enforce-complete-claim "
    "--out-json <claim_summary.json> --gate-out-json <gate.json>"
)
CLAIM_ATTACHED_REVIEW_COMMAND = (
    "python3 tools/build_wetlab_tcruzi_pde_allatom_review_packet.py "
    "--claim-readiness-json <claim_summary.json> --equivalence-gate-json <gate.json>"
)


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


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary", {}) or {})


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _safe_float(value: Any) -> float | None:
    try:
        if value in {"", None, "missing"}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_float(value: Any, digits: int = 3) -> str:
    parsed = _safe_float(value)
    if parsed is None:
        return "-"
    return f"{parsed:.{digits}f}"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _path_exists(path_text: str) -> bool:
    text = _text(path_text)
    return bool(text and "<" not in text and _resolve(text).exists())


def _first_existing_path(*candidates: Any) -> str:
    for candidate in candidates:
        text = _text(candidate)
        if _path_exists(text):
            return text
    return ""


def _quote(value: str) -> str:
    text = _text(value)
    return shlex.quote(text) if text else text


def _iter_path_values(value: Any, *, key_hint: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            out.extend(_iter_path_values(child, key_hint=str(key)))
    elif isinstance(value, list):
        for child in value:
            out.extend(_iter_path_values(child, key_hint=key_hint))
    else:
        text = _text(value)
        if text:
            out.append((key_hint, text))
    return out


def _strict_summary_candidate_paths(*summaries: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for summary in summaries:
        for key, text in _iter_path_values(summary):
            key_lower = key.lower()
            text_lower = text.lower()
            if "strict_summary_json" not in key_lower and "strict" not in text_lower:
                continue
            if not text_lower.endswith(".json"):
                continue
            if text in seen:
                continue
            seen.add(text)
            candidates.append(text)
    return candidates


def _is_rejected_strict_summary_path(path_text: str) -> str:
    path_lower = path_text.lower()
    if "final_result_summaries" in path_lower:
        return "final_result_summaries_candidate_not_auto_adopted"
    parts = {part.lower() for part in Path(path_text).parts}
    if parts.intersection({"archive", "archived", "archives"}):
        return "archived_candidate_not_auto_adopted"
    if "smoke" in parts or any("smoke" in part for part in parts):
        return "smoke_candidate_not_auto_adopted"
    return ""


def _load_json_if_exists(path_text: str) -> dict[str, Any]:
    if not _path_exists(path_text):
        return {}
    try:
        return _load_json(path_text)
    except (OSError, json.JSONDecodeError):
        return {}


def _same_existing_path(left: str, right: str) -> bool:
    if not left or not right:
        return False
    try:
        return _resolve(left) == _resolve(right)
    except OSError:
        return False


def _strict_summary_source_consistent(path_text: str, manifest_csv: str) -> bool:
    if "current" in Path(path_text).name.lower():
        return True
    payload = _load_json_if_exists(path_text)
    if not payload or not manifest_csv:
        return False
    for key, candidate in _iter_path_values(payload):
        key_lower = key.lower()
        if "manifest" not in key_lower or not candidate.lower().endswith(".csv"):
            continue
        if _same_existing_path(candidate, manifest_csv):
            return True
    return False


def _strict_release_summary_rejection_reason(path_text: str) -> str:
    payload = _load_json_if_exists(path_text)
    if not payload:
        return "invalid_or_unreadable_json"
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    gates = payload.get("gates", {}) if isinstance(payload.get("gates"), dict) else {}
    acc = gates.get("accuracy_gate", {}) if isinstance(gates.get("accuracy_gate"), dict) else {}
    speed = gates.get("speed", {}) if isinstance(gates.get("speed"), dict) else {}
    stability = gates.get("long_stability", {}) if isinstance(gates.get("long_stability"), dict) else {}

    if _safe_int(summary.get("targets"), default=0) <= 0:
        return "missing_strict_release_target_count"
    if _safe_float(acc.get("avg_neighbor_jaccard")) is None:
        return "missing_strict_release_accuracy_gate"
    if _safe_float(speed.get("avg_speedup_on_vs_off")) is None:
        return "missing_strict_release_speed_gate"
    if _safe_float(stability.get("passed_targets")) is None:
        return "missing_strict_release_long_stability_gate"
    return ""


def _csv_header_if_exists(path_text: str) -> list[str]:
    if not _path_exists(path_text):
        return []
    try:
        with _resolve(path_text).open("r", encoding="utf-8", newline="") as fh:
            return [str(col).strip() for col in next(csv.reader(fh), [])]
    except (OSError, StopIteration, csv.Error):
        return []


def _accuracy_external_candidate_paths(
    *,
    allatom_runner_summary: dict[str, Any],
    rescue_lane_summary: dict[str, Any],
) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for candidate in (
        allatom_runner_summary.get("accuracy_external_csv"),
        rescue_lane_summary.get("accuracy_external_csv"),
        DEFAULT_ACCURACY_EXTERNAL_CSV,
    ):
        text = _text(candidate)
        if not text or text in seen:
            continue
        seen.add(text)
        candidates.append(text)
    return candidates


def _accuracy_external_rejection_reason(path_text: str) -> str:
    if not _path_exists(path_text):
        return "candidate_not_found"
    header = set(_csv_header_if_exists(path_text))
    if not header:
        return "missing_or_unreadable_csv_header"
    missing = [col for col in ACCURACY_EXTERNAL_REQUIRED_COLUMNS if col not in header]
    if missing:
        return "missing_accuracy_external_columns:" + ",".join(missing)
    return ""


def _discover_accuracy_external_csv(
    *,
    rescue_lane_summary: dict[str, Any],
    allatom_runner_summary: dict[str, Any],
) -> dict[str, Any]:
    candidate_paths = _accuracy_external_candidate_paths(
        allatom_runner_summary=allatom_runner_summary,
        rescue_lane_summary=rescue_lane_summary,
    )
    rejected_candidates: list[dict[str, str]] = []
    for candidate in candidate_paths:
        rejected_reason = _accuracy_external_rejection_reason(candidate)
        if rejected_reason:
            if _path_exists(candidate):
                rejected_candidates.append({"path": candidate, "reason": rejected_reason})
            continue
        return {
            "path": candidate,
            "accuracy_external_candidate_paths": candidate_paths,
            "rejected_candidates": rejected_candidates,
        }
    return {
        "path": "",
        "accuracy_external_candidate_paths": candidate_paths,
        "rejected_candidates": rejected_candidates,
    }


def _discover_strict_summary_json(
    *,
    manifest_csv: str,
    rescue_lane_summary: dict[str, Any],
    allatom_runner_summary: dict[str, Any],
) -> dict[str, Any]:
    candidate_paths = _strict_summary_candidate_paths(allatom_runner_summary, rescue_lane_summary)
    rejected_candidates: list[dict[str, str]] = []
    for candidate in candidate_paths:
        if not _path_exists(candidate):
            continue
        rejected_reason = _is_rejected_strict_summary_path(candidate)
        if rejected_reason:
            rejected_candidates.append({"path": candidate, "reason": rejected_reason})
            continue
        rejected_reason = _strict_release_summary_rejection_reason(candidate)
        if rejected_reason:
            rejected_candidates.append({"path": candidate, "reason": rejected_reason})
            continue
        if _strict_summary_source_consistent(candidate, manifest_csv):
            return {
                "path": candidate,
                "strict_summary_candidate_paths": candidate_paths,
                "rejected_candidates": rejected_candidates,
            }
        rejected_candidates.append({"path": candidate, "reason": "not_current_or_source_consistent"})
    return {
        "path": "",
        "strict_summary_candidate_paths": candidate_paths,
        "rejected_candidates": rejected_candidates,
    }


def _claim_handoff_artifacts(
    *,
    rescue_lane_summary: dict[str, Any],
    allatom_runner_summary: dict[str, Any],
) -> dict[str, Any]:
    stamp = dt.date.today().isoformat()
    out_prefix = f"runs/allatom_claim_readiness_{stamp}"
    claim_input_summary_json = f"runs/claim_input_real_openmm_summary_{stamp}.json"
    kinetics_csv = f"runs/kinetics_equivalence_input_real_openmm_{stamp}.csv"
    thermo_csv = f"runs/thermo_equivalence_input_real_openmm_{stamp}.csv"
    experiment_csv = f"runs/experiment_consistency_input_real_openmm_{stamp}.csv"
    diagnostics_csv = f"runs/claim_input_diagnostics_{stamp}.csv"
    diagnostics_json = f"runs/claim_input_diagnostics_{stamp}.json"
    gate_json = f"{out_prefix}_gate.json"
    gate_csv = f"{out_prefix}_gate.csv"
    claim_summary_json = f"{out_prefix}_summary.json"
    claim_summary_csv = f"{out_prefix}_summary.csv"
    claim_summary_md = f"{out_prefix}_summary.md"

    manifest_csv = _first_existing_path(
        allatom_runner_summary.get("allatom_stage2_manifest_csv"),
        rescue_lane_summary.get("allatom_stage2_manifest_csv"),
        rescue_lane_summary.get("base_stage2_manifest_csv"),
    )
    strict_summary_discovery = _discover_strict_summary_json(
        manifest_csv=manifest_csv,
        rescue_lane_summary=rescue_lane_summary,
        allatom_runner_summary=allatom_runner_summary,
    )
    strict_summary_json = _text(strict_summary_discovery.get("path"))
    accuracy_external_discovery = _discover_accuracy_external_csv(
        rescue_lane_summary=rescue_lane_summary,
        allatom_runner_summary=allatom_runner_summary,
    )
    accuracy_external_csv = _text(accuracy_external_discovery.get("path"))

    available_inputs = {
        "openmm_manifest_csv": manifest_csv,
    }
    if accuracy_external_csv:
        available_inputs["accuracy_external_csv"] = accuracy_external_csv
    if strict_summary_json:
        available_inputs["strict_summary_json"] = strict_summary_json

    missing_inputs = []
    if not manifest_csv:
        missing_inputs.append("openmm_manifest_csv")
    if not strict_summary_json:
        missing_inputs.append("strict_summary_json")
    if not accuracy_external_csv:
        missing_inputs.append("accuracy_external_csv")

    claim_input_outputs = {
        "kinetics_csv": kinetics_csv,
        "thermo_csv": thermo_csv,
        "experiment_csv": experiment_csv,
        "diagnostics_csv": diagnostics_csv,
        "diagnostics_json": diagnostics_json,
        "claim_input_summary_json": claim_input_summary_json,
    }
    claim_readiness_outputs = {
        "claim_summary_json": claim_summary_json,
        "claim_summary_csv": claim_summary_csv,
        "claim_summary_md": claim_summary_md,
        "gate_json": gate_json,
        "gate_csv": gate_csv,
    }

    return {
        "input_status": "ready_to_build_claim_inputs" if manifest_csv else "missing_required_claim_inputs",
        "available_inputs": available_inputs,
        "missing_inputs": missing_inputs,
        "strict_summary_candidate_paths": strict_summary_discovery["strict_summary_candidate_paths"],
        "rejected_candidates": strict_summary_discovery["rejected_candidates"],
        "accuracy_external_candidate_paths": accuracy_external_discovery[
            "accuracy_external_candidate_paths"
        ],
        "accuracy_external_rejected_candidates": accuracy_external_discovery["rejected_candidates"],
        "claim_input_outputs": claim_input_outputs,
        "claim_readiness_outputs": claim_readiness_outputs,
        "build_command": (
            "python3 tools/build_claim_inputs_from_openmm_manifest.py "
            f"--manifest-csv {_quote(manifest_csv) if manifest_csv else '<openmm_manifest.csv>'} "
            "--targets \"T. cruzi PDE\" "
            f"--out-kinetics-csv {kinetics_csv} "
            f"--out-thermo-csv {thermo_csv} "
            f"--out-experiment-csv {experiment_csv} "
            f"--out-diagnostics-csv {diagnostics_csv} "
            f"--out-diagnostics-json {diagnostics_json} "
            f"--out-json {claim_input_summary_json}"
        ),
        "readiness_command": (
            "python3 tools/run_allatom_claim_readiness.py "
            f"--strict-summary-json {_quote(strict_summary_json) if strict_summary_json else '<strict_summary.json>'} "
            f"--accuracy-external-csv {_quote(accuracy_external_csv) if accuracy_external_csv else '<accuracy_external.csv>'} "
            f"--kinetics-input-csv {kinetics_csv} "
            f"--thermo-input-csv {thermo_csv} "
            f"--experiment-input-csv {experiment_csv} "
            "--enforce-complete-claim "
            f"--gate-out-json {gate_json} --gate-out-csv {gate_csv} "
            f"--out-json {claim_summary_json} --out-csv {claim_summary_csv} --out-md {claim_summary_md}"
        ),
        "review_command": (
            "python3 tools/build_wetlab_tcruzi_pde_allatom_review_packet.py "
            f"--claim-readiness-json {claim_summary_json} --equivalence-gate-json {gate_json}"
        ),
    }


def _burndown_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row or {}) for row in (payload.get("rows", []) or [])]


def _first_row(rows: list[dict[str, Any]], code: str) -> dict[str, Any]:
    for row in rows:
        if _text(row.get("code")) == code:
            return dict(row)
    return {}


def _repair_phase(row: dict[str, Any]) -> str:
    code = _text(row.get("code"))
    severity = _text(row.get("severity"))
    category = _text(row.get("category"))
    if code == "defer_expensive_lane" or severity == "soft":
        return "deferred"
    if category == "claim_equivalence" or code in {"produce_claim_equivalence_packet", "resolve_claim_equivalence_gate"}:
        return "after_hard_gate"
    return "hard_gate_repair"


def _operator_action(row: dict[str, Any]) -> str:
    code = _text(row.get("code"))
    if code == "recompute_mean_min_distance_A":
        return "repair_pose_geometry_and_recompute_gate"
    if code == "recompute_binding_energy_proxy":
        return "relieve_pose_clash_and_recompute_binding_proxy"
    if code == "recompute_claim_gate_required_unavailable":
        return "materialize_missing_claim_gate_metric"
    if code == "produce_claim_equivalence_packet":
        return "produce_claim_equivalence_packet_after_hard_gate"
    if code == "resolve_claim_equivalence_gate":
        return "resolve_claim_equivalence_gate_after_hard_gate"
    if code == "defer_expensive_lane":
        return "keep_expensive_lane_deferred"
    return _text(row.get("action"), default=code or "repair_selected_allatom_gate")


def _operator_instruction(row: dict[str, Any], *, target_id: str, recommended_lane_reason: str) -> str:
    code = _text(row.get("code"))
    if code == "recompute_mean_min_distance_A":
        return (
            f"Repair `{target_id}` selected all-atom pose geometry, rerun the pseudo-all-atom rescue scoring, "
            "and recompute `mean_min_distance_A` against the unchanged 2.500A strict gate."
        )
    if code == "recompute_binding_energy_proxy":
        return (
            f"Run `{target_id}` selected all-atom rescue with opt-in clash relief, preserve the unchanged scoring proxy, "
            "and require `binding_energy_proxy <= -0.050` while keeping `mean_min_distance_A <= 2.500`."
        )
    if code == "recompute_claim_gate_required_unavailable":
        return (
            "Build the claim/equivalence inputs from real all-atom evidence, attach the resulting gate JSON to the "
            "selected all-atom review packet, then rerun the commercial/final wetlab gate without changing pass state by hand."
        )
    if code == "produce_claim_equivalence_packet":
        return "Only after the hard gate clears, produce and attach the neglected-disease claim/equivalence packet."
    if code == "resolve_claim_equivalence_gate":
        return "Only after the claim/equivalence packet exists, rerun that gate and require explicit resolution before final wetlab readiness."
    if code == "defer_expensive_lane":
        return recommended_lane_reason or "Keep explicit-water rescoring and other expensive lanes deferred until hard gate repair succeeds."
    return _text(row.get("next_required_action"), default="Complete this repair row without pass override or threshold relaxation.")


def _repair_row(
    row: dict[str, Any],
    *,
    rank: int,
    target_id: str,
    recommended_lane_reason: str,
) -> dict[str, Any]:
    value = _text(row.get("value"))
    threshold = _text(row.get("threshold"))
    delta = _text(row.get("delta"))
    if not delta or delta == "-":
        value_num = _safe_float(value)
        threshold_num = _safe_float(threshold)
        if value_num is not None and threshold_num is not None:
            delta = _fmt_float(value_num - threshold_num)
        else:
            delta = "-"
    return {
        "repair_rank": rank,
        "execution_phase": _repair_phase(row),
        "severity": _text(row.get("severity")),
        "category": _text(row.get("category")),
        "repair_code": _text(row.get("code")),
        "operator_action": _operator_action(row),
        "source_status": _text(row.get("status")),
        "metric": _text(row.get("metric")),
        "value": value,
        "threshold": threshold,
        "delta": delta,
        "threshold_change_allowed": False,
        "manual_pass_promotion_allowed": False,
        "selected_allatom_pass_override_allowed": False,
        "delivery_ready_override_allowed": False,
        "reason": _text(row.get("reason")),
        "operator_instruction": _operator_instruction(
            row,
            target_id=target_id,
            recommended_lane_reason=recommended_lane_reason,
        ),
    }


def _command_plan(*, target_id: str, focus_artifact: str, primary_code: str = "", primary_metric: str = "") -> list[dict[str, str]]:
    return _command_plan_with_claim_handoff(
        target_id=target_id,
        focus_artifact=focus_artifact,
        primary_code=primary_code,
        primary_metric=primary_metric,
        claim_handoff=_claim_handoff_artifacts(rescue_lane_summary={}, allatom_runner_summary={}),
    )


def _command_plan_with_claim_handoff(
    *,
    target_id: str,
    focus_artifact: str,
    claim_handoff: dict[str, Any],
    primary_code: str = "",
    primary_metric: str = "",
) -> list[dict[str, str]]:
    target_slug = "tcruzi_pde" if "cruzi" in target_id.lower() and "pde" in target_id.lower() else "selected_allatom"
    binding_proxy_repair = primary_code == "recompute_binding_energy_proxy" or primary_metric == "binding_energy_proxy"
    claim_gate_repair = primary_code == "recompute_claim_gate_required_unavailable"
    hard_gate_command = BINDING_PROXY_REPAIR_COMMAND if binding_proxy_repair else HARD_GATE_REPAIR_COMMAND
    hard_gate_purpose = (
        "execute strict-then-near pseudo-all-atom rescue with opt-in clash relief and recompute the unchanged binding proxy gate"
        if binding_proxy_repair
        else "execute strict-then-near pseudo-all-atom rescue and recompute the unchanged hard gate"
    )
    downstream_refresh_plan = [
        {
            "phase": "current_results_index_refresh",
            "command": "python3 tools/build_wetlab_current_results_index.py",
            "purpose": "refresh the selected all-atom source-of-truth index from the rebuilt claim-attached review packet",
            "manual_pass_promotion_allowed": "false",
        },
        {
            "phase": "partnering_stack_refresh",
            "command": "python3 tools/build_wetlab_partnering_stack.py",
            "purpose": "refresh the partnering stack from the current results index before final/dashboard surfaces",
            "manual_pass_promotion_allowed": "false",
        },
        {
            "phase": "final_campaign_refresh",
            "command": "python3 tools/build_wetlab_final_campaign_summary.py",
            "purpose": "refresh the final campaign summary from the rebuilt selected all-atom state and partnering stack",
            "manual_pass_promotion_allowed": "false",
        },
        {
            "phase": "dashboard_refresh",
            "command": "python3 tools/build_wetlab_master_handoff_dashboard.py",
            "purpose": "refresh the master wetlab dashboard after final campaign summary rebuild",
            "manual_pass_promotion_allowed": "false",
        },
        {
            "phase": "burndown_refresh",
            "command": "python3 tools/build_wetlab_selected_allatom_gate_burndown_packet.py",
            "purpose": "refresh hard_block_count, missing_metric_count, and primary_burndown_code",
            "manual_pass_promotion_allowed": "false",
        },
        {
            "phase": "commercialization_queue_refresh",
            "command": "python3 tools/build_local_engine_commercialization_queue.py",
            "purpose": "refresh commercialization queue state from the repaired wetlab selected-allatom artifacts",
            "manual_pass_promotion_allowed": "false",
        },
        {
            "phase": "commercialization_status_refresh",
            "command": "python3 tools/build_commercialization_status_report.py",
            "purpose": "refresh commercialization status report without overriding any wetlab gate result",
            "manual_pass_promotion_allowed": "false",
        },
        {
            "phase": "delivery_verdict_refresh",
            "command": "python3 tools/build_local_delivery_verdict_gate.py",
            "purpose": "refresh the conservative local-delivery verdict gate after queue/status rebuilds",
            "manual_pass_promotion_allowed": "false",
        },
        {
            "phase": "closure_acceptance_check",
            "command": "confirm delivery_ready=true only from regenerated verdict outputs",
            "purpose": "accept closure only when regenerated verdict artifacts report no P0 blockers; do not infer pass from this repair packet",
            "manual_pass_promotion_allowed": "false",
        },
    ]
    claim_plan = [
        {
            "phase": "claim_inputs_build_after_hard_gate",
            "command": _text(claim_handoff.get("build_command"), default=CLAIM_INPUT_BUILD_COMMAND),
            "purpose": (
                "after hard-gate closure, derive kinetics/thermo/experiment claim inputs from real OpenMM outputs; "
                "placeholder or missing inputs remain blocked"
            ),
            "required_inputs": _text(
                (claim_handoff.get("available_inputs") or {}).get("openmm_manifest_csv"),
                default="<openmm_manifest.csv>",
            ),
            "blocked_if_missing": "true",
            "manual_pass_promotion_allowed": "false",
        },
        {
            "phase": "claim_readiness_after_hard_gate",
            "command": _text(claim_handoff.get("readiness_command"), default=CLAIM_READINESS_COMMAND),
            "purpose": (
                "after claim inputs exist, evaluate all-atom claim readiness and write both claim summary and gate JSON; "
                "incomplete claim data remains blocked"
            ),
            "required_inputs": ", ".join(
                [
                    _text((claim_handoff.get("available_inputs") or {}).get("strict_summary_json"), default="<strict_summary.json>"),
                    _text((claim_handoff.get("available_inputs") or {}).get("accuracy_external_csv"), default="<accuracy_external.csv>"),
                    _text((claim_handoff.get("claim_input_outputs") or {}).get("kinetics_csv"), default="<kinetics.csv>"),
                    _text((claim_handoff.get("claim_input_outputs") or {}).get("thermo_csv"), default="<thermo.csv>"),
                    _text((claim_handoff.get("claim_input_outputs") or {}).get("experiment_csv"), default="<experiment.csv>"),
                ]
            ),
            "blocked_if_missing": "true",
            "manual_pass_promotion_allowed": "false",
        },
        {
            "phase": "claim_attached_review_refresh",
            "command": _text(claim_handoff.get("review_command"), default=CLAIM_ATTACHED_REVIEW_COMMAND),
            "purpose": (
                "rebuild the selected all-atom review with explicit claim/equivalence evidence attached "
                "before downstream final/queue/verdict refresh"
            ),
            "required_inputs": ", ".join(
                [
                    _text((claim_handoff.get("claim_readiness_outputs") or {}).get("claim_summary_json"), default="<claim_summary.json>"),
                    _text((claim_handoff.get("claim_readiness_outputs") or {}).get("gate_json"), default="<gate.json>"),
                ]
            ),
            "blocked_if_missing": "true",
            "manual_pass_promotion_allowed": "false",
        },
    ]
    if target_slug == "tcruzi_pde":
        if claim_gate_repair:
            return claim_plan + downstream_refresh_plan
        return [
            {
                "phase": "rescue_only_branch_build",
                "command": "python3 tools/run_wetlab_tcruzi_pde_rescue_only_branch.py",
                "purpose": "materialize the dedicated T. cruzi PDE rescue-only branch before selected all-atom repair",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "rescue_only_branch_summary",
                "command": "python3 tools/build_wetlab_tcruzi_pde_rescue_only_branch_summary.py",
                "purpose": "refresh rescue-only branch summary inputs for the all-atom rescue lane",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "allatom_rescue_lane_build",
                "command": "python3 tools/build_wetlab_tcruzi_pde_allatom_rescue_lane.py",
                "purpose": "build the pseudo-all-atom rescue lane from rescue-only branch inputs",
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "hard_gate_repair",
                "command": hard_gate_command,
                "purpose": hard_gate_purpose,
                "manual_pass_promotion_allowed": "false",
            },
            {
                "phase": "hard_gate_review_refresh",
                "command": "python3 tools/build_wetlab_tcruzi_pde_allatom_review_packet.py",
                "purpose": f"rebuild selected all-atom review artifact `{focus_artifact}` from the hard-gate repair run",
                "manual_pass_promotion_allowed": "false",
            },
            *claim_plan,
            *downstream_refresh_plan,
        ]
    return [
        {
            "phase": "hard_gate_repair",
            "command": hard_gate_command if binding_proxy_repair else "rerun selected all-atom pose repair and scoring lane",
            "purpose": (
                "refresh binding_energy_proxy with opt-in clash relief without relaxing the energy threshold"
                if binding_proxy_repair
                else "refresh mean_min_distance_A without relaxing the strict gate"
            ),
            "manual_pass_promotion_allowed": "false",
        }
    ]


def _hard_gate_command(command_plan: list[dict[str, str]]) -> str:
    for item in command_plan:
        if item.get("phase") == "hard_gate_repair":
            return _text(item.get("command"))
    return command_plan[0]["command"] if command_plan else ""


def build_payload(
    burndown_payload: dict[str, Any],
    review_payload: dict[str, Any],
    rescue_lane_payload: dict[str, Any],
    allatom_runner_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    burndown_summary = _summary(burndown_payload)
    review_summary = _summary(review_payload)
    rescue_summary = _summary(rescue_lane_payload)
    allatom_runner_summary = _summary(allatom_runner_payload or {})
    burndown_rows = _burndown_rows(burndown_payload)

    target_id = _text(burndown_summary.get("selected_allatom_target_id")) or _text(review_summary.get("target_id"))
    focus_artifact = _text(
        burndown_summary.get("selected_allatom_focus_artifact"),
        default="runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
    )
    primary_code = _text(burndown_summary.get("primary_burndown_code"), default="recompute_mean_min_distance_A")
    primary_row = _first_row(burndown_rows, primary_code) or (burndown_rows[0] if burndown_rows else {})
    primary_metric = _text(burndown_summary.get("primary_burndown_metric")) or _text(primary_row.get("metric"))
    primary_value = _text(burndown_summary.get("primary_burndown_value")) or _text(primary_row.get("value"))
    primary_threshold = _text(burndown_summary.get("primary_burndown_threshold")) or _text(primary_row.get("threshold"))
    primary_delta = _text(burndown_summary.get("primary_burndown_delta")) or _text(primary_row.get("delta"))
    if not primary_delta or primary_delta == "-":
        value_num = _safe_float(primary_value)
        threshold_num = _safe_float(primary_threshold)
        primary_delta = _fmt_float(value_num - threshold_num) if value_num is not None and threshold_num is not None else "-"

    recommended_lane = _text(review_summary.get("recommended_next_expensive_lane")) or _text(
        rescue_summary.get("recommended_next_expensive_lane")
    )
    recommended_lane_reason = _text(review_summary.get("recommended_next_expensive_lane_reason")) or _text(
        rescue_summary.get("recommended_next_expensive_lane_reason")
    )
    rows = [
        _repair_row(
            row,
            rank=idx,
            target_id=target_id or "selected all-atom focus",
            recommended_lane_reason=recommended_lane_reason,
        )
        for idx, row in enumerate(burndown_rows, start=1)
    ]
    hard_block_count = _safe_int(
        burndown_summary.get("hard_block_count"),
        sum(1 for row in rows if row["severity"] == "hard"),
    )
    missing_metric_count = _safe_int(
        burndown_summary.get("missing_metric_count"),
        sum(1 for row in rows if row["source_status"] == "missing"),
    )
    claim_handoff = _claim_handoff_artifacts(
        rescue_lane_summary=rescue_summary,
        allatom_runner_summary=allatom_runner_summary,
    )
    command_plan = _command_plan_with_claim_handoff(
        target_id=target_id,
        focus_artifact=focus_artifact,
        claim_handoff=claim_handoff,
        primary_code=primary_code,
        primary_metric=primary_metric,
    )
    recommended_command = _hard_gate_command(command_plan)
    hard_codes = [row["repair_code"] for row in rows if row["execution_phase"] == "hard_gate_repair"]
    after_hard_codes = [row["repair_code"] for row in rows if row["execution_phase"] == "after_hard_gate"]
    deferred_codes = [row["repair_code"] for row in rows if row["execution_phase"] == "deferred"]

    summary = {
        "repair_ready": bool(rows),
        "packet_artifact": DEFAULT_OUT_MD,
        "target_id": target_id,
        "selected_allatom_focus_artifact": focus_artifact,
        "supporting_packet_only": True,
        "repair_only_packet": True,
        "threshold_relaxation_allowed": False,
        "manual_pass_promotion_allowed": False,
        "delivery_ready_override_allowed": False,
        "selected_allatom_pass_override_allowed": False,
        "selected_allatom_wetlab_gate_pass": bool(burndown_summary.get("selected_allatom_wetlab_gate_pass", False)),
        "selected_allatom_final_gate_pass": bool(burndown_summary.get("selected_allatom_final_gate_pass", False)),
        "review_packet_wetlab_gate_pass": bool(review_summary.get("wetlab_gate_pass", False)),
        "review_packet_wetlab_final_gate_pass": bool(review_summary.get("wetlab_final_gate_pass", False)),
        "hard_block_count": hard_block_count,
        "missing_metric_count": missing_metric_count,
        "primary_repair_code": primary_code,
        "primary_metric": primary_metric,
        "primary_value": primary_value,
        "primary_threshold": primary_threshold,
        "primary_delta": primary_delta,
        "recommended_command": recommended_command,
        "command_plan": command_plan,
        "closure_plan": command_plan,
        "claim_equivalence_required_inputs": ["<claim_summary.json>", "<gate.json>"],
        "claim_equivalence_missing_inputs_pass": False,
        "claim_equivalence_input_status": claim_handoff["input_status"],
        "claim_equivalence_available_inputs": claim_handoff["available_inputs"],
        "claim_equivalence_missing_inputs": claim_handoff["missing_inputs"],
        "claim_equivalence_strict_summary_candidate_paths": claim_handoff["strict_summary_candidate_paths"],
        "claim_equivalence_rejected_candidates": claim_handoff["rejected_candidates"],
        "claim_equivalence_accuracy_external_candidate_paths": claim_handoff[
            "accuracy_external_candidate_paths"
        ],
        "claim_equivalence_accuracy_external_rejected_candidates": claim_handoff[
            "accuracy_external_rejected_candidates"
        ],
        "claim_equivalence_claim_input_outputs": claim_handoff["claim_input_outputs"],
        "claim_equivalence_readiness_outputs": claim_handoff["claim_readiness_outputs"],
        "claim_equivalence_plan_phases": [
            "claim_inputs_build_after_hard_gate",
            "claim_readiness_after_hard_gate",
            "claim_attached_review_refresh",
        ],
        "hard_gate_acceptance_metric": primary_metric or "mean_min_distance_A",
        "hard_gate_acceptance_operator": "<=",
        "hard_gate_acceptance_threshold": primary_threshold or "2.500",
        "hard_gate_acceptance_scope": "promoted selected all-atom review rows",
        "hard_gate_acceptance_manual_override_allowed": False,
        "closure_acceptance_requires": [
            "selected_allatom_wetlab_gate_pass=true",
            "selected_allatom_final_gate_pass=true",
            "hard_block_count=0",
            "semi_hard_block_count=0",
            "missing_metric_count=0",
            "commercialization_queue_clear=true",
            "delivery_ready=true",
            "p0_blocker_count=0",
        ],
        "hard_gate_repair_codes": hard_codes,
        "after_hard_gate_codes": after_hard_codes,
        "deferred_codes": deferred_codes,
        "recommended_next_expensive_lane": recommended_lane,
        "recommended_next_expensive_lane_reason": recommended_lane_reason,
        "claim_equivalence_after_hard_gate": bool(after_hard_codes),
        "expensive_lane_deferred": recommended_lane == "defer_expensive_lane" or "defer_expensive_lane" in deferred_codes,
        "source_burndown_packet": DEFAULT_BURNDOWN_JSON,
        "source_review_packet": DEFAULT_REVIEW_JSON,
        "source_rescue_lane_packet": DEFAULT_RESCUE_LANE_JSON,
        "next_required_step": (
            f"Execute repair `{primary_code}` for `{target_id or 'selected_allatom'}` with `{primary_metric}` currently "
            f"`{primary_value or '-'}` versus unchanged threshold `{primary_threshold or '-'}` (delta `{primary_delta or '-'}`); "
            "then recompute `claim_gate_required_unavailable`. Run claim/equivalence only after hard gate closure with "
            f"`{(claim_handoff['claim_readiness_outputs']).get('claim_summary_json')}` and "
            f"`{(claim_handoff['claim_readiness_outputs']).get('gate_json')}`; missing inputs "
            f"`{', '.join(claim_handoff['missing_inputs']) or 'none'}` stay blocked, not pass. Keep the expensive lane deferred."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Wetlab Selected All-Atom Repair Packet",
        "",
        f"- repair_ready: `{summary['repair_ready']}`",
        f"- supporting_packet_only: `{summary['supporting_packet_only']}`",
        f"- repair_only_packet: `{summary['repair_only_packet']}`",
        f"- delivery_ready_override_allowed: `{summary['delivery_ready_override_allowed']}`",
        f"- selected_allatom_pass_override_allowed: `{summary['selected_allatom_pass_override_allowed']}`",
        f"- threshold_relaxation_allowed: `{summary['threshold_relaxation_allowed']}`",
        f"- target_id: `{summary['target_id']}`",
        f"- selected_allatom_focus_artifact: `{summary['selected_allatom_focus_artifact']}`",
        f"- hard_block_count: `{summary['hard_block_count']}`",
        f"- missing_metric_count: `{summary['missing_metric_count']}`",
        f"- primary_repair_code: `{summary['primary_repair_code']}`",
        f"- primary_metric: `{summary['primary_metric']}`",
        f"- primary_value: `{summary['primary_value']}`",
        f"- primary_threshold: `{summary['primary_threshold']}`",
        f"- primary_delta: `{summary['primary_delta']}`",
        f"- recommended_command: `{summary['recommended_command']}`",
        f"- hard_gate_acceptance: `{summary['hard_gate_acceptance_metric']} {summary['hard_gate_acceptance_operator']} {summary['hard_gate_acceptance_threshold']}`",
        f"- hard_gate_acceptance_scope: `{summary['hard_gate_acceptance_scope']}`",
        f"- claim_equivalence_required_inputs: `{', '.join(summary['claim_equivalence_required_inputs'])}`",
        f"- claim_equivalence_missing_inputs_pass: `{summary['claim_equivalence_missing_inputs_pass']}`",
        f"- claim_equivalence_input_status: `{summary['claim_equivalence_input_status']}`",
        f"- claim_equivalence_available_inputs: `{json.dumps(summary['claim_equivalence_available_inputs'], ensure_ascii=False)}`",
        f"- claim_equivalence_missing_inputs: `{', '.join(summary['claim_equivalence_missing_inputs']) or 'none'}`",
        f"- claim_equivalence_strict_summary_candidate_paths: `{json.dumps(summary['claim_equivalence_strict_summary_candidate_paths'], ensure_ascii=False)}`",
        f"- claim_equivalence_rejected_candidates: `{json.dumps(summary['claim_equivalence_rejected_candidates'], ensure_ascii=False)}`",
        f"- claim_equivalence_accuracy_external_candidate_paths: `{json.dumps(summary['claim_equivalence_accuracy_external_candidate_paths'], ensure_ascii=False)}`",
        f"- claim_equivalence_accuracy_external_rejected_candidates: `{json.dumps(summary['claim_equivalence_accuracy_external_rejected_candidates'], ensure_ascii=False)}`",
        "",
        "## Next Required Step",
        "",
        summary["next_required_step"],
        "",
        "## Command Plan",
        "",
    ]
    for item in summary["command_plan"]:
        suffix = ""
        if item.get("required_inputs"):
            suffix = f" Required inputs: `{item['required_inputs']}`."
        if item.get("blocked_if_missing") == "true":
            suffix += " Missing inputs remain blocked, not pass."
        lines.append(f"- `{item['phase']}`: `{item['command']}` - {item['purpose']}{suffix}")
    lines.extend(
        [
            "",
            "## Repair Rows",
            "",
            "| rank | phase | severity | repair_code | action | status | metric | value | threshold | delta |",
            "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| {row['repair_rank']} | `{row['execution_phase']}` | `{row['severity']}` | `{row['repair_code']}` | "
            f"`{row['operator_action']}` | `{row['source_status']}` | `{row['metric'] or '-'}` | "
            f"`{row['value'] or '-'}` | `{row['threshold'] or '-'}` | `{row['delta']}` |"
        )
    lines.extend(["", "## Operator Instructions", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['repair_code']}`: {row['operator_instruction']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wetlab selected all-atom repair packet.")
    parser.add_argument("--burndown-json", default=DEFAULT_BURNDOWN_JSON)
    parser.add_argument("--review-json", default=DEFAULT_REVIEW_JSON)
    parser.add_argument("--rescue-lane-json", default=DEFAULT_RESCUE_LANE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runner_payload = _load_json(DEFAULT_ALLATOM_RESCUE_RUNNER_JSON) if _path_exists(DEFAULT_ALLATOM_RESCUE_RUNNER_JSON) else {}
    payload = build_payload(
        burndown_payload=_load_json(args.burndown_json),
        review_payload=_load_json(args.review_json),
        rescue_lane_payload=_load_json(args.rescue_lane_json),
        allatom_runner_payload=runner_payload,
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
