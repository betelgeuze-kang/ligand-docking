#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_STATUS_JSON = "runs/nightly_stage6_downstream_execute_current_status.json"
DEFAULT_SUMMARY_JSON = "runs/nightly_stage6_downstream_execute_current_summary.json"
DEFAULT_DOWNSTREAM_RERUN_JSON = "runs/nightly_stage6_downstream_rerun_packet_current.json"
DEFAULT_OUT_JSON = "runs/nightly_stage6_execute_result_packet_current.json"
DEFAULT_OUT_CSV = "runs/nightly_stage6_execute_result_packet_current.csv"
DEFAULT_OUT_MD = "runs/nightly_stage6_execute_result_packet_current.md"
DEFAULT_GATE_THRESHOLD_A = 2.5


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _fmt_float(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def _replace_json_suffix(path_like: str, suffix: str) -> str:
    text = _text(path_like)
    if text.endswith(".json"):
        return f"{text[:-5]}{suffix}"
    return text


def _joined_text(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(_text(item) for item in value if _text(item))
    return _text(value)


def _extract_nested_stage(summary_payload: dict[str, Any], *path: str) -> dict[str, Any]:
    cursor: Any = summary_payload
    for key in path:
        if not isinstance(cursor, dict):
            return {}
        cursor = cursor.get(key)
    return dict(cursor or {}) if isinstance(cursor, dict) else {}


def _command_tokens(status_payload: dict[str, Any]) -> list[str]:
    attempts = list(status_payload.get("attempts", []) or [])
    command_payloads = [dict(status_payload.get("command", {}) or {})]
    command_payloads.extend(dict((attempt or {}).get("command", {}) or {}) for attempt in reversed(attempts))
    for command_payload in command_payloads:
        cmd = command_payload.get("cmd")
        if isinstance(cmd, list) and cmd:
            return [_text(token) for token in cmd if _text(token)]
        cmd_str = _text(command_payload.get("cmd_str"))
        if cmd_str:
            try:
                return shlex.split(cmd_str)
            except ValueError:
                return cmd_str.split()
    return []


def _command_flag_value(tokens: list[str], flag: str) -> str:
    for index, token in enumerate(tokens):
        if token == flag and index + 1 < len(tokens):
            return _text(tokens[index + 1])
        if token.startswith(f"{flag}="):
            return _text(token.split("=", 1)[1])
    return ""


def _status_artifacts(
    status_payload: dict[str, Any],
    *,
    status_json_artifact: str,
    summary_json_artifact: str,
) -> dict[str, str]:
    artifacts = dict(status_payload.get("artifacts", {}) or {})
    attempts = list(status_payload.get("attempts", []) or [])
    latest_attempt = dict(attempts[-1] or {}) if attempts else {}
    attempt_artifacts = dict(latest_attempt.get("artifacts", {}) or {})
    resolved_status_json = _text(artifacts.get("status_json")) or _text(status_json_artifact)
    resolved_summary_json = _text(artifacts.get("pipeline_summary_json")) or _text(summary_json_artifact)
    return {
        "status_json_artifact": resolved_status_json,
        "status_md_artifact": _text(artifacts.get("status_md")) or _replace_json_suffix(resolved_status_json, ".md"),
        "pipeline_summary_json_artifact": resolved_summary_json,
        "pipeline_summary_md_artifact": _text(artifacts.get("pipeline_summary_md"))
        or _replace_json_suffix(resolved_summary_json, ".md"),
        "attempt_summary_json_artifact": _text(attempt_artifacts.get("attempt_summary_json")),
        "attempt_summary_md_artifact": _text(attempt_artifacts.get("attempt_summary_md")),
    }


def _payload_pass(status_payload: dict[str, Any], summary_payload: dict[str, Any]) -> bool:
    if "pass" in status_payload:
        return bool(status_payload.get("pass"))
    if "pass" in summary_payload:
        return bool(summary_payload.get("pass"))
    return False


def build_payload(
    status_payload: dict[str, Any] | None = None,
    summary_payload: dict[str, Any] | None = None,
    *,
    downstream_rerun_payload: dict[str, Any] | None = None,
    execute_status_payload: dict[str, Any] | None = None,
    execute_pipeline_summary_payload: dict[str, Any] | None = None,
    status_json_artifact: str = DEFAULT_STATUS_JSON,
    summary_json_artifact: str = DEFAULT_SUMMARY_JSON,
    packet_json_artifact: str = DEFAULT_OUT_JSON,
    packet_csv_artifact: str = DEFAULT_OUT_CSV,
    packet_md_artifact: str = DEFAULT_OUT_MD,
) -> dict[str, Any]:
    status_payload = dict(execute_status_payload or status_payload or {})
    summary_payload = dict(execute_pipeline_summary_payload or summary_payload or {})
    downstream_rerun_payload = dict(downstream_rerun_payload or {})
    downstream_summary = dict(downstream_rerun_payload.get("summary", {}) or {})
    downstream_rows = [dict(row or {}) for row in (downstream_rerun_payload.get("rows", []) or [])]
    artifacts = _status_artifacts(
        status_payload,
        status_json_artifact=status_json_artifact,
        summary_json_artifact=summary_json_artifact,
    )
    execute_pass = _payload_pass(status_payload, summary_payload)
    command_payload = dict(status_payload.get("command", {}) or {})
    command_tokens = _command_tokens(status_payload)
    runner_command = _text(command_payload.get("cmd_str")) or _text(downstream_summary.get("runner_execute_command")) or " ".join(
        shlex.quote(token) for token in command_tokens if _text(token)
    )
    gate_threshold = _float(_command_flag_value(command_tokens, "--gate-max-mean-min-distance-A")) or DEFAULT_GATE_THRESHOLD_A
    run_scope = _text(status_payload.get("run_scope")) or _text(summary_payload.get("run_scope"))
    targets = _text(downstream_summary.get("target_subset")) or _text(status_payload.get("targets")) or _text(summary_payload.get("targets"))
    date_tag = _text(status_payload.get("date_tag")) or _text(summary_payload.get("date_tag"))
    gate_enforcement_mode = _text(summary_payload.get("gate_enforcement_mode")) or "operational"
    service_result = dict(summary_payload.get("service_result", {}) or {})
    service_status = _text(service_result.get("status"))
    error_code = _text(service_result.get("error_code"))
    failed_stage = _text(summary_payload.get("failed_stage")) or _text(service_result.get("failed_stage"))
    gate_override_csv_artifact = _text((status_payload.get("effective_inputs", {}) or {}).get("gate_distance_override_csv"))

    gate_stage_payloads = [
        ("stage6_operational_gate", _extract_nested_stage(summary_payload, "stages", "stage6_operational_gate")),
        ("stage6_strict_gate", _extract_nested_stage(summary_payload, "stages", "stage6_strict_gate")),
    ]
    preferred_gate_name = "stage6_strict_gate" if gate_enforcement_mode == "strict" else "stage6_operational_gate"
    available_gate_names = [name for name, payload in gate_stage_payloads if payload]
    if preferred_gate_name not in available_gate_names:
        preferred_gate_name = available_gate_names[0] if available_gate_names else ""

    rows: list[dict[str, Any]] = []
    for gate_name, gate_stage in gate_stage_payloads:
        if not gate_stage:
            continue
        gate_mean_present = gate_stage.get("mean_min_distance_A") is not None
        gate_mean = _float(gate_stage.get("mean_min_distance_A"))
        rows.append(
            {
                "gate_name": gate_name,
                "is_primary_gate": gate_name == preferred_gate_name,
                "enabled": bool(gate_stage.get("enabled", False)),
                "pass": bool(gate_stage.get("pass", False)),
                "min_frames_observed": _int(gate_stage.get("min_frames_observed")),
                "mean_min_distance_A": gate_mean,
                "mean_min_distance_A_all": _float(gate_stage.get("mean_min_distance_A_all")),
                "gate_threshold_A": gate_threshold,
                "gate_margin_A": gate_threshold - gate_mean if gate_mean_present else 0.0,
                "mean_min_distance_A_source": _text(gate_stage.get("mean_min_distance_A_source")),
                "mean_min_distance_A_topk_k": _int(gate_stage.get("mean_min_distance_A_topk_k")),
                "failed_metrics": _joined_text(gate_stage.get("failed_metrics")),
                "warnings": _joined_text(gate_stage.get("warnings")),
                "ranking_auc": _float(gate_stage.get("ranking_auc")),
                "ranking_unique_auc": _float(gate_stage.get("ranking_unique_auc")),
                "ranking_pr_auc": _float(gate_stage.get("ranking_pr_auc")),
                "ranking_ef1": _float(gate_stage.get("ranking_ef1")),
                "ranking_topk_hit_rate": _float(gate_stage.get("ranking_topk_hit_rate")),
                "override_csv_artifact": _text(gate_stage.get("mean_min_distance_A_override_csv")) or gate_override_csv_artifact,
                "override_row_count": _int(gate_stage.get("mean_min_distance_A_override_row_count")),
                "override_valid_row_count": _int(gate_stage.get("mean_min_distance_A_override_valid_row_count")),
                "override_applied_count": _int(gate_stage.get("mean_min_distance_A_override_applied_count")),
                "override_missing_count": _int(gate_stage.get("mean_min_distance_A_override_missing_count")),
                "gate_enforcement_mode": gate_enforcement_mode,
                "run_scope": run_scope,
                "targets": targets,
                "date_tag": date_tag,
                "overall_execute_pass": execute_pass,
                "service_status": service_status,
                "error_code": error_code,
                "failed_stage": failed_stage,
            }
        )
    rows.sort(key=lambda row: (not bool(row.get("is_primary_gate", False)), _text(row.get("gate_name")).lower()))

    primary_row = dict(rows[0] or {}) if rows else {}
    primary_gate_name = _text(primary_row.get("gate_name"))
    primary_gate_mean = _float(primary_row.get("mean_min_distance_A"))
    primary_gate_pass = bool(primary_row.get("pass", False))
    primary_gate_margin = _float(primary_row.get("gate_margin_A"))
    primary_override_csv_artifact = _text(primary_row.get("override_csv_artifact")) or gate_override_csv_artifact
    primary_override_row_count = _int(primary_row.get("override_row_count"))
    primary_override_valid_row_count = _int(primary_row.get("override_valid_row_count"))
    primary_override_applied_count = _int(primary_row.get("override_applied_count"))
    primary_override_missing_count = _int(primary_row.get("override_missing_count"))

    gate_snapshot = (
        f"`{primary_gate_name}` mean `{_fmt_float(primary_gate_mean)}` vs threshold `{_fmt_float(gate_threshold)}`"
        if primary_gate_name
        else "stage6 gate metrics are unavailable in the pipeline summary"
    )
    status_line = (
        f"Downstream execute passed with {gate_snapshot}, override_applied_count=`{primary_override_applied_count}`, "
        f"and service_result=`{service_status or '-'}/{error_code or '-'}`."
        if execute_pass
        else f"Downstream execute failed with {gate_snapshot}, failed_stage=`{failed_stage or '-'}`, "
        f"and service_result=`{service_status or '-'}/{error_code or '-'}`."
    )
    rescored_gate_mean = _float(downstream_summary.get("rescored_gate_mean_min_distance_A"))
    execute_matches_rescored_gate = abs(primary_gate_mean - rescored_gate_mean) <= 0.05 if rescored_gate_mean else False
    next_required_step = (
        f"Promote `{packet_md_artifact}` as the operator-facing execute handoff and keep "
        f"`{artifacts['status_json_artifact']}` plus `{artifacts['pipeline_summary_json_artifact']}` as the canonical "
        f"proof set. No rerun is required while {gate_snapshot}."
        if execute_pass
        else f"Inspect `{failed_stage or primary_gate_name or 'downstream_execute'}` using "
        f"`{artifacts['status_json_artifact']}` and `{artifacts['pipeline_summary_json_artifact']}`, repair the gate "
        f"inputs or override CSV `{primary_override_csv_artifact or '-'}`, then rerun downstream execute until the "
        f"primary stage6 gate passes."
    )

    summary = {
        "packet_ready": bool(status_payload or summary_payload),
        "packet_artifact": packet_md_artifact,
        "packet_json_artifact": packet_json_artifact,
        "packet_csv_artifact": packet_csv_artifact,
        "packet_md_artifact": packet_md_artifact,
        "status": (
            "nightly_stage6_execute_result_packet_ready"
            if execute_pass
            else "nightly_stage6_execute_result_packet_failed"
        )
        if (status_payload or summary_payload)
        else "nightly_stage6_execute_result_packet_missing",
        "execute_pass": execute_pass,
        "run_scope": run_scope,
        "targets": targets,
        "date_tag": date_tag,
        "retry_max": _int(status_payload.get("retry_max")),
        "attempt_count": _int(status_payload.get("attempt_count")),
        "passed_attempt": _int(status_payload.get("passed_attempt")),
        "command_ok": bool(command_payload.get("ok", False)),
        "command_returncode": command_payload.get("returncode", ""),
        "runner_command": runner_command,
        "target_subset": targets,
        "row_count": len(downstream_rows) or len(rows),
        "primary_focus_row_key": _text(downstream_summary.get("primary_focus_row_key")),
        "primary_canonical_retry_preset_id": _text(downstream_summary.get("primary_canonical_retry_preset_id")),
        "rescored_gate_mean_min_distance_A": rescored_gate_mean,
        "gate_enforcement_mode": gate_enforcement_mode,
        "status_json_artifact": artifacts["status_json_artifact"],
        "status_md_artifact": artifacts["status_md_artifact"],
        "pipeline_summary_json_artifact": artifacts["pipeline_summary_json_artifact"],
        "pipeline_summary_md_artifact": artifacts["pipeline_summary_md_artifact"],
        "execute_status_json_artifact": artifacts["status_json_artifact"],
        "execute_status_md_artifact": artifacts["status_md_artifact"],
        "execute_pipeline_summary_json_artifact": artifacts["pipeline_summary_json_artifact"],
        "execute_pipeline_summary_md_artifact": artifacts["pipeline_summary_md_artifact"],
        "attempt_summary_json_artifact": artifacts["attempt_summary_json_artifact"],
        "attempt_summary_md_artifact": artifacts["attempt_summary_md_artifact"],
        "service_status": service_status,
        "error_code": error_code,
        "failed_stage": failed_stage,
        "stage6_primary_gate_name": primary_gate_name,
        "stage6_gate_mean_min_distance_A": primary_gate_mean,
        "stage6_gate_mean_min_distance_A_all": _float(primary_row.get("mean_min_distance_A_all")),
        "gate_threshold_A": gate_threshold,
        "stage6_gate_margin_A": primary_gate_margin,
        "stage6_gate_pass": primary_gate_pass,
        "stage6_gate_source": _text(primary_row.get("mean_min_distance_A_source")),
        "stage6_gate_topk_k": _int(primary_row.get("mean_min_distance_A_topk_k")),
        "stage6_override_csv_artifact": primary_override_csv_artifact,
        "stage6_override_row_count": primary_override_row_count,
        "stage6_override_valid_row_count": primary_override_valid_row_count,
        "stage6_override_applied_count": primary_override_applied_count,
        "stage6_override_missing_count": primary_override_missing_count,
        "execute_gate_mean_min_distance_A": primary_gate_mean,
        "execute_gate_pass": primary_gate_pass,
        "execute_gate_source": _text(primary_row.get("mean_min_distance_A_source")),
        "execute_override_applied_count": primary_override_applied_count,
        "execute_payload_pass": execute_pass,
        "execute_matches_rescored_gate": execute_matches_rescored_gate,
        "gate_row_count": len(rows),
        "status_line": status_line,
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _markdown(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary", {}) or {})
    rows = list(payload.get("rows", []) or [])
    lines = [
        "# Nightly Stage6 Execute Result Packet",
        "",
        f"- packet_ready: `{summary.get('packet_ready', False)}`",
        f"- status: `{summary.get('status') or '-'}`",
        f"- packet_json_artifact: `{summary.get('packet_json_artifact') or '-'}`",
        f"- packet_csv_artifact: `{summary.get('packet_csv_artifact') or '-'}`",
        f"- packet_md_artifact: `{summary.get('packet_md_artifact') or '-'}`",
        f"- execute_pass: `{summary.get('execute_pass', False)}`",
        f"- run_scope: `{summary.get('run_scope') or '-'}`",
        f"- targets: `{summary.get('targets') or '-'}`",
        f"- date_tag: `{summary.get('date_tag') or '-'}`",
        f"- attempt_count: `{summary.get('attempt_count')}`",
        f"- passed_attempt: `{summary.get('passed_attempt')}`",
        f"- retry_max: `{summary.get('retry_max')}`",
        f"- command_ok: `{summary.get('command_ok', False)}`",
        f"- command_returncode: `{summary.get('command_returncode')}`",
        f"- status_json_artifact: `{summary.get('status_json_artifact') or '-'}`",
        f"- pipeline_summary_json_artifact: `{summary.get('pipeline_summary_json_artifact') or '-'}`",
        f"- service_status: `{summary.get('service_status') or '-'}`",
        f"- error_code: `{summary.get('error_code') or '-'}`",
        f"- failed_stage: `{summary.get('failed_stage') or '-'}`",
        f"- stage6_primary_gate_name: `{summary.get('stage6_primary_gate_name') or '-'}`",
        f"- stage6_gate_mean_min_distance_A: `{_fmt_float(summary.get('stage6_gate_mean_min_distance_A'))}`",
        f"- gate_threshold_A: `{_fmt_float(summary.get('gate_threshold_A'))}`",
        f"- stage6_gate_margin_A: `{_fmt_float(summary.get('stage6_gate_margin_A'))}`",
        f"- stage6_gate_pass: `{summary.get('stage6_gate_pass', False)}`",
        f"- stage6_gate_source: `{summary.get('stage6_gate_source') or '-'}`",
        f"- stage6_override_csv_artifact: `{summary.get('stage6_override_csv_artifact') or '-'}`",
        f"- stage6_override_applied_count: `{summary.get('stage6_override_applied_count')}`",
        f"- status_line: `{summary.get('status_line') or '-'}`",
        "",
        "## Command",
        "",
        f"- `{summary.get('runner_command') or '-'}`",
        "",
        "## Next Step",
        "",
        f"- {summary.get('next_required_step') or '-'}",
        "",
        "## Gate Rows",
        "",
        "| gate_name | primary | enabled | pass | mean | threshold | margin | source | override_applied | failed_metrics | warnings |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['gate_name']}` | `{row['is_primary_gate']}` | `{row['enabled']}` | `{row['pass']}` | "
            f"{_fmt_float(row['mean_min_distance_A'])} | {_fmt_float(row['gate_threshold_A'])} | "
            f"{_fmt_float(row['gate_margin_A'])} | `{row['mean_min_distance_A_source'] or '-'}` | "
            f"{row['override_applied_count']} | `{row['failed_metrics'] or '-'}` | `{row['warnings'] or '-'}` |"
        )
    if not rows:
        lines.append("| `-` | `-` | `-` | `-` | - | - | - | `-` | 0 | `-` | `-` |")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the nightly stage6 execute result packet.")
    parser.add_argument("--downstream-rerun-json", default=DEFAULT_DOWNSTREAM_RERUN_JSON)
    parser.add_argument("--status-json", default=DEFAULT_STATUS_JSON)
    parser.add_argument("--summary-json", default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        status_payload=_load_json(args.status_json),
        summary_payload=_load_json(args.summary_json),
        downstream_rerun_payload=_load_json(args.downstream_rerun_json),
        status_json_artifact=args.status_json,
        summary_json_artifact=args.summary_json,
        packet_json_artifact=args.out_json,
        packet_csv_artifact=args.out_csv,
        packet_md_artifact=args.out_md,
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload.get("rows", []))
    out_md.write_text(_markdown(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
