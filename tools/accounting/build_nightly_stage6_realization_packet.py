#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TUNING_JSON = "runs/nightly_stage6_tuning_packet_current.json"
DEFAULT_PROMOTION_JSON = "runs/nightly_stage6_probe_promotion_packet_current.json"
DEFAULT_OUT_JSON = "runs/nightly_stage6_realization_packet_current.json"
DEFAULT_OUT_CSV = "runs/nightly_stage6_realization_packet_current.csv"
DEFAULT_OUT_MD = "runs/nightly_stage6_realization_packet_current.md"


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


def _fmt_float(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def _manifest_exists(path_like: str) -> bool:
    text = _text(path_like)
    return bool(text) and _resolve(text).exists()


def build_payload(tuning_payload: dict[str, Any], promotion_payload: dict[str, Any]) -> dict[str, Any]:
    tuning_summary = dict(tuning_payload.get("summary", {}) or {})
    tuning_rows = {
        _text(row.get("row_key")): dict(row)
        for row in (tuning_payload.get("rows", []) or [])
        if _text(row.get("row_key"))
    }
    promotion_summary = dict(promotion_payload.get("summary", {}) or {})
    threshold = _float(tuning_summary.get("primary_gate_threshold")) or _float(promotion_summary.get("gate_threshold_A")) or 2.5
    current_mean = _float(tuning_summary.get("primary_gate_value"))
    replaced_values = {
        row_key: _float(row.get("mean_min_distance_A"))
        for row_key, row in tuning_rows.items()
    }
    rows: list[dict[str, Any]] = []
    for promotion_row in promotion_payload.get("rows", []) or []:
        row = dict(promotion_row or {})
        if _text(row.get("promotion_decision")) != "promote_probe_as_retry_replacement":
            continue
        row_key = _text(row.get("row_key"))
        if not row_key:
            continue
        manifest_artifact = _text(row.get("canonical_fallback_retry_manifest_artifact")) or _text(row.get("probe_manifest_artifact"))
        realized_mean = _float(row.get("promoted_mean_min_distance_A"))
        replaced_values[row_key] = realized_mean
        rows.append(
            {
                "realization_rank": 0,
                "row_key": row_key,
                "canonical_retry_preset_id": _text(row.get("canonical_fallback_preset_id")) or _text(row.get("canonical_source_run_label")),
                "realization_manifest_artifact": manifest_artifact,
                "realization_manifest_present": _manifest_exists(manifest_artifact),
                "realization_summary_json_artifact": _text(row.get("canonical_fallback_retry_summary_json_artifact")) or _text(row.get("probe_summary_artifact")),
                "realization_summary_md_artifact": _text(row.get("canonical_fallback_retry_summary_md_artifact")) or _text(row.get("probe_summary_md_artifact")),
                "canonical_retry_command_str": _text(row.get("canonical_fallback_retry_command_str")),
                "original_mean_min_distance_A": _float(row.get("original_mean_min_distance_A")),
                "realized_mean_min_distance_A": realized_mean,
                "distance_delta_A": _float(row.get("distance_delta_A")),
                "measured_gate_margin_A": threshold - realized_mean if threshold > 0 else 0.0,
                "strategy_reason": _text(row.get("strategy_reason")),
                "realized_seed": _text(row.get("promoted_seed")),
                "retry_lane_role": _text(row.get("retry_lane_role")),
            }
        )
    rows.sort(key=lambda row: _float(row.get("distance_delta_A")))
    for idx, row in enumerate(rows, start=1):
        row["realization_rank"] = idx

    realized_mean = sum(replaced_values.values()) / len(replaced_values) if replaced_values else current_mean
    realized_delta = realized_mean - threshold
    realization_ready = bool(rows) and all(bool(row.get("realization_manifest_present")) for row in rows)
    primary_row = rows[0] if rows else {}
    companion_row = rows[1] if len(rows) > 1 else {}
    summary = {
        "packet_ready": bool(rows),
        "packet_artifact": DEFAULT_OUT_MD,
        "status": "nightly_stage6_realization_packet_ready" if rows else "nightly_stage6_realization_packet_missing",
        "tuning_packet_artifact": _text(tuning_summary.get("packet_artifact")) or DEFAULT_TUNING_JSON.replace(".json", ".md"),
        "promotion_packet_artifact": _text(promotion_summary.get("packet_artifact")) or DEFAULT_PROMOTION_JSON.replace(".json", ".md"),
        "apply_preview_csv_artifact": _text(promotion_summary.get("apply_preview_csv_artifact")),
        "realization_row_count": len(rows),
        "primary_realization_row_key": _text(primary_row.get("row_key")),
        "primary_canonical_retry_preset_id": _text(primary_row.get("canonical_retry_preset_id")),
        "companion_realization_row_key": _text(companion_row.get("row_key")),
        "current_gate_mean_min_distance_A": current_mean,
        "realized_gate_mean_min_distance_A": realized_mean,
        "gate_threshold_A": threshold,
        "realized_gate_delta_A": realized_delta,
        "realized_gate_pass": realized_delta <= 0.0,
        "canonical_retry_lane_ready": bool(
            promotion_summary.get("canonical_retry_lane_ready", promotion_summary.get("projected_gate_pass", False))
        ),
        "realization_ready": realization_ready,
        "next_required_step": (
            f"Treat the measured canonical replacement rows as the stage6 realization lane: `{_text(primary_row.get('row_key'))}` first"
            + (f", then `{_text(companion_row.get('row_key'))}`" if companion_row else "")
            + f", with realized gate mean `{_fmt_float(realized_mean)}` against threshold `{_fmt_float(threshold)}`."
            if rows
            else "Build the probe promotion packet first so the realization lane has measured rows."
        ),
    }
    return {"summary": summary, "rows": rows}


def _markdown(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary", {}) or {})
    rows = list(payload.get("rows", []) or [])
    lines = [
        "# Nightly Stage6 Realization Packet",
        "",
        f"- packet_ready: `{summary.get('packet_ready', False)}`",
        f"- status: `{summary.get('status') or '-'}`",
        f"- tuning_packet_artifact: `{summary.get('tuning_packet_artifact') or '-'}`",
        f"- promotion_packet_artifact: `{summary.get('promotion_packet_artifact') or '-'}`",
        f"- apply_preview_csv_artifact: `{summary.get('apply_preview_csv_artifact') or '-'}`",
        f"- realization_row_count: `{summary.get('realization_row_count')}`",
        f"- primary_realization_row_key: `{summary.get('primary_realization_row_key') or '-'}`",
        f"- primary_canonical_retry_preset_id: `{summary.get('primary_canonical_retry_preset_id') or '-'}`",
        f"- companion_realization_row_key: `{summary.get('companion_realization_row_key') or '-'}`",
        f"- current_gate_mean_min_distance_A: `{_fmt_float(summary.get('current_gate_mean_min_distance_A'))}`",
        f"- realized_gate_mean_min_distance_A: `{_fmt_float(summary.get('realized_gate_mean_min_distance_A'))}`",
        f"- gate_threshold_A: `{_fmt_float(summary.get('gate_threshold_A'))}`",
        f"- realized_gate_delta_A: `{_fmt_float(summary.get('realized_gate_delta_A'))}`",
        f"- realized_gate_pass: `{summary.get('realized_gate_pass', False)}`",
        f"- canonical_retry_lane_ready: `{summary.get('canonical_retry_lane_ready', False)}`",
        f"- realization_ready: `{summary.get('realization_ready', False)}`",
        "",
        "## Next Step",
        "",
        f"- {summary.get('next_required_step') or '-'}",
        "",
        "## Realization Rows",
        "",
        "| rank | row_key | preset | realized_mean | gate_margin | manifest_present | manifest |",
        "| ---: | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['realization_rank']} | `{row['row_key']}` | `{row['canonical_retry_preset_id'] or '-'}` | "
            f"{_fmt_float(row['realized_mean_min_distance_A'])} | {_fmt_float(row['measured_gate_margin_A'])} | "
            f"`{row['realization_manifest_present']}` | `{row['realization_manifest_artifact']}` |"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the nightly stage6 realization packet.")
    parser.add_argument("--tuning-json", default=DEFAULT_TUNING_JSON)
    parser.add_argument("--promotion-json", default=DEFAULT_PROMOTION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        tuning_payload=_load_json(args.tuning_json),
        promotion_payload=_load_json(args.promotion_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    out_md.write_text(_markdown(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
