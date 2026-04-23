#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TUNING_JSON = "runs/nightly_stage6_tuning_packet_current.json"
DEFAULT_REALIZATION_JSON = "runs/nightly_stage6_realization_packet_current.json"
DEFAULT_OUT_JSON = "runs/nightly_stage6_rescored_gate_packet_current.json"
DEFAULT_OUT_CSV = "runs/nightly_stage6_rescored_gate_packet_current.csv"
DEFAULT_OUT_MD = "runs/nightly_stage6_rescored_gate_packet_current.md"


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


def build_payload(tuning_payload: dict[str, Any], realization_payload: dict[str, Any]) -> dict[str, Any]:
    tuning_summary = dict(tuning_payload.get("summary", {}) or {})
    tuning_rows = [dict(row or {}) for row in (tuning_payload.get("rows", []) or [])]
    realization_summary = dict(realization_payload.get("summary", {}) or {})
    realization_rows = {
        _text(row.get("row_key")): dict(row or {})
        for row in (realization_payload.get("rows", []) or [])
        if _text(row.get("row_key"))
    }

    threshold = _float(tuning_summary.get("primary_gate_threshold")) or _float(realization_summary.get("gate_threshold_A")) or 2.5
    current_gate_mean = _float(tuning_summary.get("primary_gate_value")) or _float(
        realization_summary.get("current_gate_mean_min_distance_A")
    )
    realization_ready = bool(realization_summary.get("realization_ready", False))

    rows: list[dict[str, Any]] = []
    rescored_values: list[float] = []
    for tuning_row in tuning_rows:
        row_key = _text(tuning_row.get("row_key"))
        if not row_key:
            continue
        realization_row = dict(realization_rows.get(row_key, {}) or {})
        original_mean = _float(tuning_row.get("mean_min_distance_A"))
        replaced = bool(realization_row)
        rescored_mean = (
            _float(realization_row.get("realized_mean_min_distance_A"))
            if replaced
            else original_mean
        )
        rescored_values.append(rescored_mean)
        lane_status = (
            "canonical_retry_replacement"
            if replaced
            else "kept_anchor_row"
            if original_mean <= threshold
            else "kept_original_above_threshold_row"
        )
        rows.append(
            {
                "topk_rank": _int(tuning_row.get("tuning_priority_rank")) or len(rows) + 1,
                "row_key": row_key,
                "target": _text(tuning_row.get("target")),
                "ligand_id": _text(tuning_row.get("ligand_id")),
                "lane_status": lane_status,
                "is_replaced": replaced,
                "canonical_retry_preset_id": _text(realization_row.get("canonical_retry_preset_id")),
                "original_mean_min_distance_A": original_mean,
                "rescored_mean_min_distance_A": rescored_mean,
                "rescore_delta_A": rescored_mean - original_mean,
                "gate_margin_A": threshold - rescored_mean,
                "original_distance_over_threshold_A": _float(tuning_row.get("distance_over_threshold")),
                "realization_manifest_artifact": _text(realization_row.get("realization_manifest_artifact")),
                "realization_manifest_present": bool(realization_row.get("realization_manifest_present", False)),
                "canonical_retry_command_str": _text(realization_row.get("canonical_retry_command_str")),
                "source_packet_artifact": (
                    _text(realization_summary.get("packet_artifact"))
                    if replaced
                    else _text(tuning_summary.get("packet_artifact")) or DEFAULT_TUNING_JSON.replace(".json", ".md")
                ),
            }
        )

    rows.sort(key=lambda row: (int(row.get("topk_rank", 9999)), _text(row.get("row_key")).lower()))
    rescored_gate_mean = sum(rescored_values) / len(rescored_values) if rescored_values else current_gate_mean
    rescored_gate_delta = rescored_gate_mean - threshold
    replaced_rows = [row for row in rows if bool(row.get("is_replaced"))]
    untouched_rows = [row for row in rows if not bool(row.get("is_replaced"))]
    rows_by_key = {_text(row.get("row_key")): row for row in rows if _text(row.get("row_key"))}
    preferred_primary_row_key = _text(realization_summary.get("primary_realization_row_key"))
    primary_applied_row = rows_by_key.get(preferred_primary_row_key, replaced_rows[0] if replaced_rows else {})
    companion_applied_row = next(
        (
            row
            for row in replaced_rows
            if _text(row.get("row_key")) and _text(row.get("row_key")) != _text(primary_applied_row.get("row_key"))
        ),
        {},
    )
    primary_anchor_row = next(
        (row for row in untouched_rows if _text(row.get("lane_status")) == "kept_anchor_row"),
        untouched_rows[0] if untouched_rows else {},
    )

    summary = {
        "packet_ready": bool(rows),
        "packet_artifact": DEFAULT_OUT_MD,
        "status": "nightly_stage6_rescored_gate_packet_ready" if rows else "nightly_stage6_rescored_gate_packet_missing",
        "tuning_packet_artifact": _text(tuning_summary.get("packet_artifact")) or DEFAULT_TUNING_JSON.replace(".json", ".md"),
        "realization_packet_artifact": _text(realization_summary.get("packet_artifact")) or DEFAULT_REALIZATION_JSON.replace(".json", ".md"),
        "promotion_apply_preview_csv_artifact": _text(realization_summary.get("apply_preview_csv_artifact")),
        "topk_row_count": len(rows),
        "replaced_row_count": len(replaced_rows),
        "untouched_row_count": len(untouched_rows),
        "primary_applied_row_key": _text(primary_applied_row.get("row_key")),
        "companion_applied_row_key": _text(companion_applied_row.get("row_key")),
        "primary_anchor_row_key": _text(primary_anchor_row.get("row_key")),
        "primary_canonical_retry_preset_id": _text(primary_applied_row.get("canonical_retry_preset_id")),
        "current_gate_mean_min_distance_A": current_gate_mean,
        "rescored_gate_mean_min_distance_A": rescored_gate_mean,
        "gate_threshold_A": threshold,
        "rescored_gate_delta_A": rescored_gate_delta,
        "rescored_gate_pass": rescored_gate_delta <= 0.0,
        "apply_ready": realization_ready and bool(replaced_rows),
        "downstream_rerun_ready": realization_ready and bool(replaced_rows) and rescored_gate_delta <= 0.0,
        "status_line": (
            f"Applying `{len(replaced_rows)}` measured canonical rows drops the stage6 gate mean from "
            f"`{_fmt_float(current_gate_mean)}` to `{_fmt_float(rescored_gate_mean)}` against threshold "
            f"`{_fmt_float(threshold)}`."
            if rows
            else "Build the realization packet first so the top-k gate can be rescored."
        ),
        "next_required_step": (
            f"Use `{DEFAULT_OUT_MD}` as the post-apply stage6 snapshot: lock `{_text(primary_applied_row.get('row_key'))}`"
            + (
                f" and `{_text(companion_applied_row.get('row_key'))}`" if companion_applied_row else ""
            )
            + f" into the canonical retry lane, keep `{_text(primary_anchor_row.get('row_key')) or '-'}` as the untouched anchor row, and rerun downstream nightly scoring with rescored gate mean `{_fmt_float(rescored_gate_mean)}`."
            if rows
            else "Build the stage6 realization packet first, then rescore the gate from the measured replacement rows."
        ),
    }
    return {"summary": summary, "rows": rows}


def _markdown(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary", {}) or {})
    rows = list(payload.get("rows", []) or [])
    lines = [
        "# Nightly Stage6 Rescored Gate Packet",
        "",
        f"- packet_ready: `{summary.get('packet_ready', False)}`",
        f"- status: `{summary.get('status') or '-'}`",
        f"- tuning_packet_artifact: `{summary.get('tuning_packet_artifact') or '-'}`",
        f"- realization_packet_artifact: `{summary.get('realization_packet_artifact') or '-'}`",
        f"- promotion_apply_preview_csv_artifact: `{summary.get('promotion_apply_preview_csv_artifact') or '-'}`",
        f"- topk_row_count: `{summary.get('topk_row_count')}`",
        f"- replaced_row_count: `{summary.get('replaced_row_count')}`",
        f"- untouched_row_count: `{summary.get('untouched_row_count')}`",
        f"- primary_applied_row_key: `{summary.get('primary_applied_row_key') or '-'}`",
        f"- companion_applied_row_key: `{summary.get('companion_applied_row_key') or '-'}`",
        f"- primary_anchor_row_key: `{summary.get('primary_anchor_row_key') or '-'}`",
        f"- primary_canonical_retry_preset_id: `{summary.get('primary_canonical_retry_preset_id') or '-'}`",
        f"- current_gate_mean_min_distance_A: `{_fmt_float(summary.get('current_gate_mean_min_distance_A'))}`",
        f"- rescored_gate_mean_min_distance_A: `{_fmt_float(summary.get('rescored_gate_mean_min_distance_A'))}`",
        f"- gate_threshold_A: `{_fmt_float(summary.get('gate_threshold_A'))}`",
        f"- rescored_gate_delta_A: `{_fmt_float(summary.get('rescored_gate_delta_A'))}`",
        f"- rescored_gate_pass: `{summary.get('rescored_gate_pass', False)}`",
        f"- apply_ready: `{summary.get('apply_ready', False)}`",
        f"- downstream_rerun_ready: `{summary.get('downstream_rerun_ready', False)}`",
        f"- status_line: `{summary.get('status_line') or '-'}`",
        "",
        "## Next Step",
        "",
        f"- {summary.get('next_required_step') or '-'}",
        "",
        "## Rescored Rows",
        "",
        "| topk_rank | row_key | lane_status | original_mean | rescored_mean | delta | gate_margin | manifest_present | source_packet |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['topk_rank']} | `{row['row_key']}` | `{row['lane_status']}` | "
            f"{_fmt_float(row['original_mean_min_distance_A'])} | {_fmt_float(row['rescored_mean_min_distance_A'])} | "
            f"{_fmt_float(row['rescore_delta_A'])} | {_fmt_float(row['gate_margin_A'])} | "
            f"`{row['realization_manifest_present']}` | `{row['source_packet_artifact']}` |"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the nightly stage6 rescored gate packet.")
    parser.add_argument("--tuning-json", default=DEFAULT_TUNING_JSON)
    parser.add_argument("--realization-json", default=DEFAULT_REALIZATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        tuning_payload=_load_json(args.tuning_json),
        realization_payload=_load_json(args.realization_json),
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
