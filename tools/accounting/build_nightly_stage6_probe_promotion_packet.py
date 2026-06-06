#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PROBE_JSON = "runs/nightly_stage6_probe_result_packet_current.json"
DEFAULT_FOLLOWUP_JSON = "runs/nightly_stage6_followup_retry_packet_current.json"
DEFAULT_SWEEP_JSON = "runs/nightly_stage6_tuning_sweep_packet_current.json"
DEFAULT_OUT_JSON = "runs/nightly_stage6_probe_promotion_packet_current.json"
DEFAULT_OUT_CSV = "runs/nightly_stage6_probe_promotion_packet_current.csv"
DEFAULT_OUT_MD = "runs/nightly_stage6_probe_promotion_packet_current.md"
DEFAULT_APPLY_PREVIEW_CSV = "runs/nightly_stage6_probe_promotion_apply_preview_current.csv"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _fmt_float(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _maybe_load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _source_summary_artifact_from_manifest(manifest_artifact: str) -> str:
    text = _text(manifest_artifact)
    if not text.endswith("_manifest.csv"):
        return ""
    return text.replace("_manifest.csv", "_summary.json")


def _source_summary_md_artifact_from_manifest(manifest_artifact: str) -> str:
    text = _text(manifest_artifact)
    if not text.endswith("_manifest.csv"):
        return ""
    return text.replace("_manifest.csv", "_summary.md")


def _source_run_label_from_manifest(manifest_artifact: str) -> str:
    text = _text(manifest_artifact)
    name = Path(text).name
    if not name.endswith("_manifest.csv"):
        return ""
    return name[: -len("_manifest.csv")]


def _manifest_artifact_from_summary_artifact(summary_artifact: str) -> str:
    text = _text(summary_artifact)
    if text.endswith("_summary.json"):
        return text.replace("_summary.json", "_manifest.csv")
    if text.endswith("_summary.md"):
        return text.replace("_summary.md", "_manifest.csv")
    return ""


def _preferred_preset_ids(culprit_kind: str, retry_lane_role: str) -> list[str]:
    kind = _text(culprit_kind)
    role = _text(retry_lane_role)
    if kind == "binder_recovery" or role == "retry_from_best_replica":
        return [
            "target_forced_adress_uncapped_probe",
            "target_forced_adress_replay",
            "anchor_replay_baseline",
            "target_forced_adress_geometry_bias",
        ]
    if kind == "decoy_cleanup" or role == "retry_cleanup_from_best_replica":
        return [
            "target_forced_adress_uncapped_probe",
            "target_forced_adress_consistency_probe",
            "anchor_replay_baseline",
            "adress_only_boundary_probe",
        ]
    return ["anchor_replay_baseline"]


def _select_fallback_sweep_row(
    sweep_rows: list[dict[str, Any]],
    *,
    culprit_kind: str,
    retry_lane_role: str,
) -> dict[str, Any]:
    ordered = sorted(
        [dict(row or {}) for row in sweep_rows],
        key=lambda row: (
            int(_float(row.get("preset_rank")) or 9999),
            _text(row.get("preset_id")).lower(),
        ),
    )
    if not ordered:
        return {}
    by_preset = {
        _text(row.get("preset_id")): row
        for row in ordered
        if _text(row.get("preset_id"))
    }
    for preset_id in _preferred_preset_ids(culprit_kind, retry_lane_role):
        selected = by_preset.get(preset_id)
        if selected:
            return selected
    return ordered[0]


def build_payload(
    probe_payload: dict[str, Any],
    followup_payload: dict[str, Any],
    sweep_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    probe_summary = dict(probe_payload.get("summary", {}) or {})
    probe_rows = list(probe_payload.get("rows", []) or [])
    followup_rows = {
        _text(row.get("row_key")): dict(row)
        for row in followup_payload.get("rows", []) or []
        if _text(row.get("row_key"))
    }
    sweep_rows_by_key: dict[str, list[dict[str, Any]]] = {}
    for row in (sweep_payload or {}).get("rows", []) or []:
        candidate = dict(row or {})
        row_key = _text(candidate.get("row_key"))
        if not row_key:
            continue
        sweep_rows_by_key.setdefault(row_key, []).append(candidate)
    projected_gate_pass = bool(probe_summary.get("projected_gate_pass", False))
    gate_threshold = _float(probe_summary.get("gate_threshold_A"))

    rows: list[dict[str, Any]] = []
    for probe_row in probe_rows:
        row_key = _text(probe_row.get("row_key"))
        followup_row = dict(followup_rows.get(row_key, {}) or {})
        retry_lane_role = _text(followup_row.get("recommended_action"))
        culprit_kind = _text(followup_row.get("culprit_kind"))
        fallback_sweep_row = _select_fallback_sweep_row(
            sweep_rows_by_key.get(row_key, []),
            culprit_kind=culprit_kind,
            retry_lane_role=retry_lane_role,
        )
        fallback_preset = _text(fallback_sweep_row.get("preset_id"))
        fallback_summary_json_artifact = _text(fallback_sweep_row.get("retry_summary_json_artifact"))
        fallback_summary_md_artifact = _text(fallback_sweep_row.get("retry_summary_md_artifact"))
        promoted_mean = _float(probe_row.get("probe_mean_min_distance_A"))
        promoted_inside_gate = promoted_mean <= gate_threshold if gate_threshold > 0 else projected_gate_pass
        promotion_decision = (
            "promote_probe_as_retry_replacement"
            if projected_gate_pass and promoted_inside_gate
            else "hold_probe_for_additional_tuning"
        )
        gate_margin = gate_threshold - promoted_mean if gate_threshold > 0 else 0.0
        promoted_row = {
            "promotion_rank": 0,
            "row_key": row_key,
            "promotion_decision": promotion_decision,
            "probe_manifest_artifact": _text(probe_row.get("probe_manifest_artifact")),
            "probe_summary_artifact": _source_summary_artifact_from_manifest(_text(probe_row.get("probe_manifest_artifact"))),
            "probe_summary_md_artifact": _source_summary_md_artifact_from_manifest(
                _text(probe_row.get("probe_manifest_artifact"))
            ),
            "canonical_source_run_label": _source_run_label_from_manifest(_text(probe_row.get("probe_manifest_artifact"))),
            "original_mean_min_distance_A": _float(probe_row.get("original_mean_min_distance_A")),
            "promoted_mean_min_distance_A": promoted_mean,
            "gate_threshold_A": gate_threshold,
            "promoted_inside_gate": promoted_inside_gate,
            "measured_gate_margin_A": gate_margin,
            "distance_delta_A": _float(probe_row.get("distance_delta_A")),
            "strategy_reason": _text(probe_row.get("strategy_reason")),
            "promoted_seed": _text(probe_row.get("seed")),
            "retry_lane_role": retry_lane_role,
            "culprit_kind": culprit_kind,
            "original_retry_anchor_queue_id": _text(followup_row.get("retry_anchor_queue_id")),
            "original_retry_anchor_seed": _text(followup_row.get("retry_anchor_seed")),
            "original_retry_anchor_trajectory_npz": _text(followup_row.get("retry_anchor_trajectory_npz")),
            "canonical_fallback_preset_id": fallback_preset,
            "canonical_fallback_subset_queue_csv_artifact": _text(
                fallback_sweep_row.get("subset_queue_csv_artifact")
            ),
            "canonical_fallback_retry_manifest_artifact": _manifest_artifact_from_summary_artifact(
                fallback_summary_json_artifact or fallback_summary_md_artifact
            ),
            "canonical_fallback_retry_summary_json_artifact": fallback_summary_json_artifact,
            "canonical_fallback_retry_summary_md_artifact": fallback_summary_md_artifact,
            "canonical_fallback_retry_command_str": _text(fallback_sweep_row.get("retry_command_str")),
        }
        rows.append(promoted_row)

    rows.sort(key=lambda row: _float(row.get("distance_delta_A")))
    for idx, row in enumerate(rows, start=1):
        row["promotion_rank"] = idx
        fallback_preset = _text(row.get("canonical_fallback_preset_id"))
        fallback_matches_source = fallback_preset and fallback_preset == _text(row.get("canonical_source_run_label"))
        row["operator_action_line"] = (
            f"Promote `{_text(row.get('row_key'))}` from `{_text(row.get('canonical_source_run_label')) or 'probe'}` "
            f"at `{_fmt_float(row.get('promoted_mean_min_distance_A'))}` A against `{_fmt_float(row.get('gate_threshold_A'))}` A"
            + (
                " and keep that same preset as the canonical retry lane."
                if fallback_matches_source
                else f" and keep fallback preset `{fallback_preset}` ready."
                if fallback_preset
                else "."
            )
        )
    promoted_rows = [
        row for row in rows if _text(row.get("promotion_decision")) == "promote_probe_as_retry_replacement"
    ]
    hold_rows = [
        row for row in rows if _text(row.get("promotion_decision")) != "promote_probe_as_retry_replacement"
    ]
    apply_preview_rows: list[dict[str, Any]] = [
        {
            "promotion_rank": row["promotion_rank"],
            "row_key": row["row_key"],
            "projected_mean_min_distance_A": row["promoted_mean_min_distance_A"],
            "promoted_seed": row["promoted_seed"],
            "retry_lane_role": row["retry_lane_role"],
            "canonical_fallback_preset_id": row["canonical_fallback_preset_id"],
            "source": "probe_promotion",
            "source_manifest_artifact": row["probe_manifest_artifact"],
            "promotion_decision": row["promotion_decision"],
        }
        for row in promoted_rows
    ]
    priority_line = " -> ".join(
        f"{_text(row.get('row_key'))} [{_text(row.get('canonical_fallback_preset_id')) or _text(row.get('promotion_decision'))}]"
        for row in promoted_rows
    )
    primary_row = promoted_rows[0] if promoted_rows else {}
    companion_row = promoted_rows[1] if len(promoted_rows) > 1 else {}
    summary = {
        "packet_ready": bool(rows),
        "packet_artifact": DEFAULT_OUT_MD,
        "status": "nightly_stage6_probe_promotion_packet_ready" if rows else "nightly_stage6_probe_promotion_packet_missing",
        "probe_result_artifact": _text(probe_summary.get("packet_artifact")) or DEFAULT_PROBE_JSON.replace(".json", ".md"),
        "followup_artifact": _text(dict(followup_payload.get("summary", {}) or {}).get("packet_artifact")) or DEFAULT_FOLLOWUP_JSON.replace(".json", ".md"),
        "sweep_artifact": _text(dict((sweep_payload or {}).get("summary", {}) or {}).get("packet_artifact"))
        or DEFAULT_SWEEP_JSON.replace(".json", ".md"),
        "apply_preview_csv_artifact": DEFAULT_APPLY_PREVIEW_CSV,
        "canonical_retry_lane_ready": bool(promoted_rows) and projected_gate_pass,
        "promoted_row_count": len(promoted_rows),
        "hold_row_count": len(hold_rows),
        "primary_promoted_row_key": _text(primary_row.get("row_key")),
        "primary_companion_row_key": _text(companion_row.get("row_key")),
        "primary_canonical_fallback_preset_id": _text(primary_row.get("canonical_fallback_preset_id")),
        "priority_line": priority_line,
        "gate_threshold_A": gate_threshold,
        "projected_gate_mean_min_distance_A": _float(probe_summary.get("projected_gate_mean_min_distance_A")),
        "projected_gate_pass": projected_gate_pass,
        "next_required_step": (
            (
                f"Use `{DEFAULT_APPLY_PREVIEW_CSV}` as the canonical replacement preview, promote `{_text(primary_row.get('row_key'))}` first"
                + (
                    ", keep that same uncapped preset as the canonical retry lane"
                    if _text(primary_row.get("canonical_fallback_preset_id"))
                    and _text(primary_row.get("canonical_fallback_preset_id"))
                    == _text(primary_row.get("canonical_source_run_label"))
                    else f", keep `{_text(primary_row.get('canonical_fallback_preset_id'))}` ready as the capped fallback preset"
                    if _text(primary_row.get("canonical_fallback_preset_id"))
                    else ""
                )
                + (
                    f", then carry `{_text(companion_row.get('row_key'))}` as the companion canonical row"
                    if companion_row
                    else ""
                )
                + " before re-scoring the nightly gate."
            )
            if promoted_rows
            else "Hold the probe rows in review; the projected gate still does not justify canonical retry-lane promotion."
            if rows
            else "Build the probe result packet first so there are measured rows to promote."
        ),
    }
    return {"summary": summary, "rows": rows, "apply_preview_rows": apply_preview_rows}


def _markdown(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary", {}) or {})
    rows = list(payload.get("rows", []) or [])
    lines = [
        "# Nightly Stage6 Probe Promotion Packet",
        "",
        f"- packet_ready: `{summary.get('packet_ready', False)}`",
        f"- status: `{summary.get('status') or '-'}`",
        f"- probe_result_artifact: `{summary.get('probe_result_artifact') or '-'}`",
        f"- followup_artifact: `{summary.get('followup_artifact') or '-'}`",
        f"- sweep_artifact: `{summary.get('sweep_artifact') or '-'}`",
        f"- apply_preview_csv_artifact: `{summary.get('apply_preview_csv_artifact') or '-'}`",
        f"- promoted_row_count: `{summary.get('promoted_row_count')}`",
        f"- hold_row_count: `{summary.get('hold_row_count')}`",
        f"- primary_promoted_row_key: `{summary.get('primary_promoted_row_key') or '-'}`",
        f"- primary_companion_row_key: `{summary.get('primary_companion_row_key') or '-'}`",
        f"- primary_canonical_fallback_preset_id: `{summary.get('primary_canonical_fallback_preset_id') or '-'}`",
        f"- canonical_retry_lane_ready: `{summary.get('canonical_retry_lane_ready', False)}`",
        f"- priority_line: `{summary.get('priority_line') or '-'}`",
        f"- gate_threshold_A: `{_fmt_float(summary.get('gate_threshold_A'))}`",
        f"- projected_gate_mean_min_distance_A: `{_fmt_float(summary.get('projected_gate_mean_min_distance_A'))}`",
        f"- projected_gate_pass: `{summary.get('projected_gate_pass', False)}`",
        "",
        "## Next Step",
        "",
        f"- {summary.get('next_required_step') or '-'}",
        "",
        "## Promotion Rows",
        "",
        "| rank | row_key | decision | promoted_mean | gate_margin | fallback_preset | retry_lane_role | probe_manifest |",
        "| ---: | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['promotion_rank']} | `{row['row_key']}` | `{row['promotion_decision']}` | "
            f"{_fmt_float(row['promoted_mean_min_distance_A'])} | {_fmt_float(row['measured_gate_margin_A'])} | "
            f"`{row['canonical_fallback_preset_id'] or '-'}` | `{row['retry_lane_role'] or '-'}` | "
            f"`{row['probe_manifest_artifact']}` |"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the nightly stage6 probe promotion packet.")
    parser.add_argument("--probe-json", default=DEFAULT_PROBE_JSON)
    parser.add_argument("--followup-json", default=DEFAULT_FOLLOWUP_JSON)
    parser.add_argument("--sweep-json", default=DEFAULT_SWEEP_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--apply-preview-csv", default=DEFAULT_APPLY_PREVIEW_CSV)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        probe_payload=_load_json(args.probe_json),
        followup_payload=_load_json(args.followup_json),
        sweep_payload=_maybe_load_json(args.sweep_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    apply_preview_csv = _resolve(args.apply_preview_csv)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    write_csv_rows(apply_preview_csv, payload["apply_preview_rows"])
    out_md.write_text(_markdown(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
