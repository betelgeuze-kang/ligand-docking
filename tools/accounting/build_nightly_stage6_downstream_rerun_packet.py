#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import shlex
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_RESCORED_JSON = "runs/nightly_stage6_rescored_gate_packet_current.json"
DEFAULT_REALIZATION_JSON = "runs/nightly_stage6_realization_packet_current.json"
DEFAULT_BASE_PROFILE_JSON = "config/ligand_htvs_nightly_strict_v1.json"
DEFAULT_DRY_RUN_STATUS_JSON = "runs/nightly_stage6_downstream_rerun_current_status.json"
DEFAULT_PROFILE_JSON = "runs/nightly_stage6_downstream_rerun_profile_current.json"
DEFAULT_OVERRIDE_CSV = "runs/nightly_stage6_downstream_rerun_gate_override_current.csv"
DEFAULT_OUT_JSON = "runs/nightly_stage6_downstream_rerun_packet_current.json"
DEFAULT_OUT_CSV = "runs/nightly_stage6_downstream_rerun_packet_current.csv"
DEFAULT_OUT_MD = "runs/nightly_stage6_downstream_rerun_packet_current.md"
DEFAULT_OUT_PREFIX = "runs/nightly_stage6_downstream_rerun_current"


def _default_date_tag() -> str:
    return f"{dt.date.today().isoformat()}_stage6_downstream_rerun"


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


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _dry_run_status_artifacts(
    dry_run_status_payload: dict[str, Any],
    *,
    out_prefix: str,
) -> dict[str, str]:
    artifacts = dict(dry_run_status_payload.get("artifacts", {}) or {})
    return {
        "status_json_artifact": _text(artifacts.get("status_json")) or f"{out_prefix}_status.json",
        "status_md_artifact": _text(artifacts.get("status_md")) or f"{out_prefix}_status.md",
        "pipeline_summary_json_artifact": _text(artifacts.get("pipeline_summary_json")) or f"{out_prefix}_summary.json",
        "pipeline_summary_md_artifact": _text(artifacts.get("pipeline_summary_md")) or f"{out_prefix}_summary.md",
    }


def _extract_nested_stage(summary_payload: dict[str, Any], *path: str) -> dict[str, Any]:
    cursor: Any = summary_payload
    for key in path:
        if not isinstance(cursor, dict):
            return {}
        cursor = cursor.get(key)
    return dict(cursor or {}) if isinstance(cursor, dict) else {}


def _derived_profile(
    base_profile_payload: dict[str, Any],
    *,
    target_subset: str,
    rescored_summary: dict[str, Any],
    realization_summary: dict[str, Any],
    base_profile_json: str,
    gate_distance_override_csv_artifact: str,
) -> dict[str, Any]:
    base_version = _text(base_profile_payload.get("version")) or "ligand_htvs_nightly_profile"
    profile = dict(base_profile_payload)
    profile["version"] = f"{base_version}_stage6_downstream_rerun_v1"
    profile["description"] = (
        "Smoke-only downstream nightly rerun profile derived from the strict nightly base after stage6 canonical "
        "retry replacement and rescored-gate pass."
    )
    profile["targets"] = target_subset
    profile["run_scope"] = "smoke"
    profile["require_ood_eval"] = False
    profile["retry"] = {"max_attempts": 1, "sleep_sec": 0}
    profile["dry_run"] = False
    profile["gate_distance_override_csv"] = gate_distance_override_csv_artifact
    profile["stage6_downstream_rerun_metadata"] = {
        "base_profile_json": base_profile_json,
        "rescored_gate_packet_artifact": _text(rescored_summary.get("packet_artifact")),
        "realization_packet_artifact": _text(realization_summary.get("packet_artifact")),
        "gate_distance_override_csv_artifact": gate_distance_override_csv_artifact,
        "primary_applied_row_key": _text(rescored_summary.get("primary_applied_row_key")),
        "companion_applied_row_key": _text(rescored_summary.get("companion_applied_row_key")),
        "primary_anchor_row_key": _text(rescored_summary.get("primary_anchor_row_key")),
        "primary_canonical_retry_preset_id": _text(rescored_summary.get("primary_canonical_retry_preset_id")),
        "rescored_gate_mean_min_distance_A": _float(rescored_summary.get("rescored_gate_mean_min_distance_A")),
        "gate_threshold_A": _float(rescored_summary.get("gate_threshold_A")),
    }
    return profile


def build_payload(
    rescored_payload: dict[str, Any],
    realization_payload: dict[str, Any],
    base_profile_payload: dict[str, Any],
    dry_run_status_payload: dict[str, Any] | None = None,
    *,
    base_profile_json_artifact: str = DEFAULT_BASE_PROFILE_JSON,
    downstream_profile_json_artifact: str = DEFAULT_PROFILE_JSON,
    gate_distance_override_csv_artifact: str = DEFAULT_OVERRIDE_CSV,
    downstream_out_prefix: str = DEFAULT_OUT_PREFIX,
    downstream_date_tag: str | None = None,
) -> dict[str, Any]:
    rescored_summary = dict(rescored_payload.get("summary", {}) or {})
    realization_summary = dict(realization_payload.get("summary", {}) or {})
    dry_run_status_payload = dict(dry_run_status_payload or {})
    downstream_date_tag = _text(downstream_date_tag) or _default_date_tag()

    rescored_rows = [dict(row or {}) for row in (rescored_payload.get("rows", []) or [])]
    target_subset_list = _ordered_unique([_text(row.get("target")) for row in rescored_rows])
    target_subset = ",".join(target_subset_list)
    threshold = _float(rescored_summary.get("gate_threshold_A")) or 2.5
    rescored_gate_mean = _float(rescored_summary.get("rescored_gate_mean_min_distance_A"))
    rescored_gate_pass = bool(rescored_summary.get("rescored_gate_pass", False))
    downstream_rerun_ready = bool(rescored_summary.get("downstream_rerun_ready", False)) and bool(target_subset_list)

    profile_payload = _derived_profile(
        base_profile_payload=base_profile_payload,
        target_subset=target_subset,
        rescored_summary=rescored_summary,
        realization_summary=realization_summary,
        base_profile_json=base_profile_json_artifact,
        gate_distance_override_csv_artifact=gate_distance_override_csv_artifact,
    )

    dry_run_command_tokens = [
        "python3",
        "tools/run_ligand_htvs_nightly.py",
        "--profile-json",
        downstream_profile_json_artifact,
        "--date-tag",
        downstream_date_tag,
        "--run-scope",
        "smoke",
        "--targets",
        target_subset,
        "--out-prefix",
        downstream_out_prefix,
        "--dry-run",
        "--retry-max",
        "1",
        "--retry-sleep-sec",
        "0",
    ]
    execute_command_tokens = [
        "python3",
        "tools/run_ligand_htvs_nightly.py",
        "--profile-json",
        downstream_profile_json_artifact,
        "--date-tag",
        downstream_date_tag,
        "--run-scope",
        "smoke",
        "--targets",
        target_subset,
        "--out-prefix",
        downstream_out_prefix,
        "--no-dry-run",
        "--retry-max",
        "1",
        "--retry-sleep-sec",
        "0",
    ]
    dry_run_command = " ".join(shlex.quote(token) for token in dry_run_command_tokens if _text(token))
    execute_command = " ".join(shlex.quote(token) for token in execute_command_tokens if _text(token))

    rows: list[dict[str, Any]] = []
    gate_distance_override_rows: list[dict[str, Any]] = []
    for row in rescored_rows:
        row_key = _text(row.get("row_key"))
        if not row_key:
            continue
        lane_status = _text(row.get("lane_status"))
        rerun_rationale = (
            "carry the measured canonical retry replacement into the downstream smoke rerun"
            if lane_status == "canonical_retry_replacement"
            else "keep the untouched anchor row in scope while validating the rerun"
            if lane_status == "kept_anchor_row"
            else "keep the affected target in scope for the downstream rerun snapshot"
        )
        rows.append(
            {
                "rerun_rank": _int(row.get("topk_rank")) or len(rows) + 1,
                "row_key": row_key,
                "target": _text(row.get("target")),
                "ligand_id": _text(row.get("ligand_id")),
                "lane_status": lane_status,
                "selected_for_downstream_rerun": _text(row.get("target")) in target_subset_list,
                "canonical_retry_preset_id": _text(row.get("canonical_retry_preset_id")),
                "rescored_mean_min_distance_A": _float(row.get("rescored_mean_min_distance_A")),
                "gate_margin_A": _float(row.get("gate_margin_A")),
                "source_packet_artifact": _text(row.get("source_packet_artifact")),
                "rerun_scope": "smoke",
                "rerun_rationale": rerun_rationale,
            }
        )
        if lane_status == "canonical_retry_replacement":
            gate_distance_override_rows.append(
                {
                    "row_key": row_key,
                    "target": _text(row.get("target")),
                    "ligand_id": _text(row.get("ligand_id")),
                    "override_mean_min_distance_A": _float(row.get("rescored_mean_min_distance_A")),
                    "source_packet_artifact": _text(row.get("source_packet_artifact")),
                    "canonical_retry_preset_id": _text(row.get("canonical_retry_preset_id")),
                    "lane_status": lane_status,
                }
            )
    rows.sort(key=lambda row: (int(row.get("rerun_rank", 9999)), _text(row.get("row_key")).lower()))
    gate_distance_override_rows.sort(
        key=lambda row: (_text(row.get("target")).lower(), _text(row.get("ligand_id")).lower())
    )

    dry_run_artifacts = _dry_run_status_artifacts(dry_run_status_payload, out_prefix=downstream_out_prefix)
    dry_run_pipeline_summary = _maybe_load_json(dry_run_artifacts["pipeline_summary_json_artifact"])
    dry_run_stage6 = _extract_nested_stage(dry_run_pipeline_summary, "stages", "stage6_operational_gate")
    dry_run_service_result = dict(dry_run_pipeline_summary.get("service_result", {}) or {})
    dry_run_status_present = bool(dry_run_status_payload)
    dry_run_payload_pass = bool(dry_run_status_payload.get("pass", False))
    dry_run_attempt_count = _int(dry_run_status_payload.get("attempt_count"))
    dry_run_returncode = (dry_run_status_payload.get("command", {}) or {}).get("returncode")
    dry_run_failed_stage = _text(dry_run_service_result.get("failed_stage"))
    dry_run_error_code = _text(dry_run_service_result.get("error_code"))
    dry_run_gate_mean = _float(dry_run_stage6.get("mean_min_distance_A"))
    dry_run_gate_pass = bool(dry_run_stage6.get("pass", False))
    dry_run_vs_rescored_delta = dry_run_gate_mean - rescored_gate_mean if dry_run_gate_mean else 0.0
    dry_run_matches_rescored_gate = abs(dry_run_vs_rescored_delta) <= 0.05 if dry_run_gate_mean else False
    dry_run_status_line = (
        f"dry-run status artifact `{dry_run_artifacts['status_json_artifact']}` is present with "
        f"`attempt_count={dry_run_attempt_count}` and `payload_pass={dry_run_payload_pass}`."
        + (
            f" Pipeline summary failed at `{dry_run_failed_stage or '-'}` with `{dry_run_error_code or '-'}` and "
            f"stage6 mean `{_fmt_float(dry_run_gate_mean)}`."
            if dry_run_pipeline_summary
            else ""
        )
        if dry_run_status_present
        else "dry-run has not been invoked yet; use the generated runner command to validate the downstream rerun seam."
    )

    summary = {
        "packet_ready": bool(rows),
        "packet_artifact": DEFAULT_OUT_MD,
        "status": (
            "nightly_stage6_downstream_rerun_packet_ready"
            if rows and downstream_rerun_ready
            else "nightly_stage6_downstream_rerun_packet_pending"
        ),
        "rescored_gate_packet_artifact": _text(rescored_summary.get("packet_artifact")) or DEFAULT_RESCORED_JSON.replace(".json", ".md"),
        "realization_packet_artifact": _text(realization_summary.get("packet_artifact")) or DEFAULT_REALIZATION_JSON.replace(".json", ".md"),
        "base_profile_json_artifact": base_profile_json_artifact,
        "downstream_profile_json_artifact": downstream_profile_json_artifact,
        "gate_distance_override_csv_artifact": gate_distance_override_csv_artifact,
        "downstream_profile_version": _text(profile_payload.get("version")),
        "downstream_out_prefix": downstream_out_prefix,
        "downstream_date_tag": downstream_date_tag,
        "target_subset": target_subset,
        "target_count": len(target_subset_list),
        "row_count": len(rows),
        "gate_distance_override_row_count": len(gate_distance_override_rows),
        "primary_focus_row_key": _text(rescored_summary.get("primary_applied_row_key")),
        "companion_focus_row_key": _text(rescored_summary.get("companion_applied_row_key")),
        "anchor_row_key": _text(rescored_summary.get("primary_anchor_row_key")),
        "primary_canonical_retry_preset_id": _text(rescored_summary.get("primary_canonical_retry_preset_id")),
        "rescored_gate_mean_min_distance_A": rescored_gate_mean,
        "gate_threshold_A": threshold,
        "rescored_gate_pass": rescored_gate_pass,
        "downstream_rerun_ready": downstream_rerun_ready,
        "runner_dry_run_command": dry_run_command,
        "runner_execute_command": execute_command,
        "dry_run_status_json_artifact": dry_run_artifacts["status_json_artifact"],
        "dry_run_status_md_artifact": dry_run_artifacts["status_md_artifact"],
        "dry_run_pipeline_summary_json_artifact": dry_run_artifacts["pipeline_summary_json_artifact"],
        "dry_run_pipeline_summary_md_artifact": dry_run_artifacts["pipeline_summary_md_artifact"],
        "dry_run_pipeline_summary_present": bool(dry_run_pipeline_summary),
        "dry_run_status_present": dry_run_status_present,
        "dry_run_attempt_count": dry_run_attempt_count,
        "dry_run_payload_pass": dry_run_payload_pass,
        "dry_run_command_returncode": dry_run_returncode if dry_run_returncode is not None else "",
        "dry_run_command_validated": dry_run_status_present and dry_run_attempt_count > 0,
        "dry_run_failed_stage": dry_run_failed_stage,
        "dry_run_error_code": dry_run_error_code,
        "dry_run_gate_mean_min_distance_A": dry_run_gate_mean,
        "dry_run_gate_pass": dry_run_gate_pass,
        "dry_run_rescored_gate_delta_A": dry_run_vs_rescored_delta,
        "dry_run_matches_rescored_gate": dry_run_matches_rescored_gate,
        "dry_run_status_line": dry_run_status_line,
        "status_line": (
            f"The downstream nightly rerun seam is ready for targets `{target_subset}`: the rescored stage6 gate is "
            f"`{_fmt_float(rescored_gate_mean)}` against threshold `{_fmt_float(threshold)}` and the next move is a smoke rerun."
            if rows and downstream_rerun_ready
            else "Build the stage6 rescored gate packet first so the downstream rerun seam has a concrete target subset."
        ),
        "next_required_step": (
            f"Use `{DEFAULT_OUT_MD}` as the exact downstream nightly rerun handoff: validate `{target_subset}` with "
            f"`{dry_run_command}` first, then run `{execute_command}` once the dry-run seam is confirmed. "
            f"The profile already carries gate override CSV `{gate_distance_override_csv_artifact}`."
            if rows and downstream_rerun_ready
            else "Build the rescored gate packet and measured realization lane before attempting a downstream nightly rerun."
        ),
    }
    return {
        "summary": summary,
        "rows": rows,
        "gate_distance_override_rows": gate_distance_override_rows,
        "downstream_profile": profile_payload,
    }


def _markdown(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary", {}) or {})
    rows = list(payload.get("rows", []) or [])
    lines = [
        "# Nightly Stage6 Downstream Rerun Packet",
        "",
        f"- packet_ready: `{summary.get('packet_ready', False)}`",
        f"- status: `{summary.get('status') or '-'}`",
        f"- rescored_gate_packet_artifact: `{summary.get('rescored_gate_packet_artifact') or '-'}`",
        f"- realization_packet_artifact: `{summary.get('realization_packet_artifact') or '-'}`",
        f"- downstream_profile_json_artifact: `{summary.get('downstream_profile_json_artifact') or '-'}`",
        f"- gate_distance_override_csv_artifact: `{summary.get('gate_distance_override_csv_artifact') or '-'}`",
        f"- downstream_profile_version: `{summary.get('downstream_profile_version') or '-'}`",
        f"- downstream_out_prefix: `{summary.get('downstream_out_prefix') or '-'}`",
        f"- downstream_date_tag: `{summary.get('downstream_date_tag') or '-'}`",
        f"- target_subset: `{summary.get('target_subset') or '-'}`",
        f"- target_count: `{summary.get('target_count')}`",
        f"- row_count: `{summary.get('row_count')}`",
        f"- gate_distance_override_row_count: `{summary.get('gate_distance_override_row_count')}`",
        f"- primary_focus_row_key: `{summary.get('primary_focus_row_key') or '-'}`",
        f"- companion_focus_row_key: `{summary.get('companion_focus_row_key') or '-'}`",
        f"- anchor_row_key: `{summary.get('anchor_row_key') or '-'}`",
        f"- primary_canonical_retry_preset_id: `{summary.get('primary_canonical_retry_preset_id') or '-'}`",
        f"- rescored_gate_mean_min_distance_A: `{_fmt_float(summary.get('rescored_gate_mean_min_distance_A'))}`",
        f"- gate_threshold_A: `{_fmt_float(summary.get('gate_threshold_A'))}`",
        f"- rescored_gate_pass: `{summary.get('rescored_gate_pass', False)}`",
        f"- downstream_rerun_ready: `{summary.get('downstream_rerun_ready', False)}`",
        f"- dry_run_status_present: `{summary.get('dry_run_status_present', False)}`",
        f"- dry_run_payload_pass: `{summary.get('dry_run_payload_pass', False)}`",
        f"- dry_run_command_validated: `{summary.get('dry_run_command_validated', False)}`",
        f"- dry_run_failed_stage: `{summary.get('dry_run_failed_stage') or '-'}`",
        f"- dry_run_error_code: `{summary.get('dry_run_error_code') or '-'}`",
        f"- dry_run_gate_mean_min_distance_A: `{_fmt_float(summary.get('dry_run_gate_mean_min_distance_A'))}`",
        f"- dry_run_gate_pass: `{summary.get('dry_run_gate_pass', False)}`",
        f"- dry_run_rescored_gate_delta_A: `{_fmt_float(summary.get('dry_run_rescored_gate_delta_A'))}`",
        f"- dry_run_matches_rescored_gate: `{summary.get('dry_run_matches_rescored_gate', False)}`",
        f"- dry_run_status_line: `{summary.get('dry_run_status_line') or '-'}`",
        "",
        "## Commands",
        "",
        f"- dry-run: `{summary.get('runner_dry_run_command') or '-'}`",
        f"- execute: `{summary.get('runner_execute_command') or '-'}`",
        "",
        "## Next Step",
        "",
        f"- {summary.get('next_required_step') or '-'}",
        "",
        "## Rerun Rows",
        "",
        "| rank | row_key | target | lane_status | preset | rescored_mean | gate_margin | rationale |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['rerun_rank']} | `{row['row_key']}` | `{row['target'] or '-'}` | `{row['lane_status'] or '-'}` | "
            f"`{row['canonical_retry_preset_id'] or '-'}` | {_fmt_float(row['rescored_mean_min_distance_A'])} | "
            f"{_fmt_float(row['gate_margin_A'])} | `{row['rerun_rationale']}` |"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the nightly stage6 downstream rerun packet.")
    parser.add_argument("--rescored-json", default=DEFAULT_RESCORED_JSON)
    parser.add_argument("--realization-json", default=DEFAULT_REALIZATION_JSON)
    parser.add_argument("--base-profile-json", default=DEFAULT_BASE_PROFILE_JSON)
    parser.add_argument("--dry-run-status-json", default=DEFAULT_DRY_RUN_STATUS_JSON)
    parser.add_argument("--profile-out-json", default=DEFAULT_PROFILE_JSON)
    parser.add_argument("--override-out-csv", default=DEFAULT_OVERRIDE_CSV)
    parser.add_argument("--out-prefix", default=DEFAULT_OUT_PREFIX)
    parser.add_argument("--date-tag", default=_default_date_tag())
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        rescored_payload=_load_json(args.rescored_json),
        realization_payload=_load_json(args.realization_json),
        base_profile_payload=_load_json(args.base_profile_json),
        dry_run_status_payload=_maybe_load_json(args.dry_run_status_json),
        base_profile_json_artifact=args.base_profile_json,
        downstream_profile_json_artifact=args.profile_out_json,
        gate_distance_override_csv_artifact=args.override_out_csv,
        downstream_out_prefix=args.out_prefix,
        downstream_date_tag=args.date_tag,
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    profile_out = _resolve(args.profile_out_json)
    override_out = _resolve(args.override_out_csv)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    profile_out.parent.mkdir(parents=True, exist_ok=True)
    override_out.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    profile_out.write_text(
        json.dumps(payload.get("downstream_profile", {}), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_csv_rows(out_csv, payload.get("rows", []))
    write_csv_rows(override_out, payload.get("gate_distance_override_rows", []))
    out_md.write_text(_markdown(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
