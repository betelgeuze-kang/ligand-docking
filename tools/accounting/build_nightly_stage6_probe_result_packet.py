#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TUNING_JSON = "runs/nightly_stage6_tuning_packet_current.json"
DEFAULT_SWEEP_JSON = "runs/nightly_stage6_tuning_sweep_packet_current.json"
DEFAULT_OUT_JSON = "runs/nightly_stage6_probe_result_packet_current.json"
DEFAULT_OUT_CSV = "runs/nightly_stage6_probe_result_packet_current.csv"
DEFAULT_OUT_MD = "runs/nightly_stage6_probe_result_packet_current.md"

DEFAULT_PROBE_MANIFESTS = {
    "HIV1_PROTEASE::imatinib": "runs/nightly_stage6_retry_runs/hiv1_protease_imatinib/target_forced_adress_uncapped_probe_manifest.csv",
    "HIV1_PROTEASE::aspirin": "runs/nightly_stage6_retry_runs/hiv1_protease_aspirin/target_forced_adress_uncapped_probe_manifest.csv",
}


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


def _load_manifest_row(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return dict(rows[0] or {}) if rows else {}


def build_payload(
    tuning_payload: dict[str, Any],
    sweep_payload: dict[str, Any],
    probe_manifest_artifacts: dict[str, str],
) -> dict[str, Any]:
    tuning_summary = dict(tuning_payload.get("summary", {}) or {})
    tuning_rows = list(tuning_payload.get("rows", []) or [])
    threshold = _float(tuning_summary.get("primary_gate_threshold")) or 2.5
    current_rows = {
        _text(row.get("row_key")): dict(row)
        for row in tuning_rows
        if _text(row.get("row_key"))
    }
    rows: list[dict[str, Any]] = []
    replaced_values: dict[str, float] = {
        row_key: _float(row.get("mean_min_distance_A"))
        for row_key, row in current_rows.items()
    }
    for row_key, manifest_artifact in probe_manifest_artifacts.items():
        manifest_row = _load_manifest_row(manifest_artifact)
        if not manifest_row:
            continue
        original = current_rows.get(row_key, {})
        original_mean = _float(original.get("mean_min_distance_A"))
        probe_mean = _float(manifest_row.get("mean_min_distance_A"))
        replaced_values[row_key] = probe_mean
        rows.append(
            {
                "row_key": row_key,
                "probe_manifest_artifact": manifest_artifact,
                "original_mean_min_distance_A": original_mean,
                "probe_mean_min_distance_A": probe_mean,
                "distance_delta_A": probe_mean - original_mean,
                "strategy_reason": _text(manifest_row.get("strategy_reason")),
                "final_min_distance_A": _float(manifest_row.get("final_min_distance_A")),
                "binding_energy_mmpbsa_kcal_mol_proxy": _float(manifest_row.get("binding_energy_mmpbsa_kcal_mol_proxy")),
                "seed": _text(manifest_row.get("seed")),
            }
        )
    current_mean = _float(tuning_summary.get("primary_gate_value"))
    projected_mean = sum(replaced_values.values()) / len(replaced_values) if replaced_values else current_mean
    projected_delta = projected_mean - threshold
    rows.sort(key=lambda row: _float(row.get("distance_delta_A")))
    primary_probe_row_key = _text(rows[0].get("row_key")) if rows else ""
    summary = {
        "packet_ready": bool(rows),
        "packet_artifact": DEFAULT_OUT_MD,
        "status": "nightly_stage6_probe_result_packet_ready" if rows else "nightly_stage6_probe_result_packet_missing",
        "tuning_packet_artifact": _text(tuning_summary.get("packet_artifact")) or DEFAULT_TUNING_JSON.replace(".json", ".md"),
        "sweep_packet_artifact": _text(dict(sweep_payload.get("summary", {}) or {}).get("packet_artifact")) or DEFAULT_SWEEP_JSON.replace(".json", ".md"),
        "probe_row_count": len(rows),
        "primary_probe_row_key": primary_probe_row_key,
        "current_gate_mean_min_distance_A": current_mean,
        "projected_gate_mean_min_distance_A": projected_mean,
        "gate_threshold_A": threshold,
        "projected_gate_delta_A": projected_delta,
        "projected_gate_pass": projected_delta <= 0.0,
        "next_required_step": (
            f"Promote the uncapped ADReSS probe rows into the canonical retry lane and re-score the nightly gate; projected mean moves from "
            f"`{_fmt_float(current_mean)}` to `{_fmt_float(projected_mean)}` against threshold `{_fmt_float(threshold)}`."
            if rows
            else "Run the uncapped ADReSS probes first so the packet has measured replacement rows."
        ),
    }
    return {"summary": summary, "rows": rows}


def _markdown(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary", {}) or {})
    rows = list(payload.get("rows", []) or [])
    lines = [
        "# Nightly Stage6 Probe Result Packet",
        "",
        f"- packet_ready: `{summary.get('packet_ready', False)}`",
        f"- status: `{summary.get('status') or '-'}`",
        f"- tuning_packet_artifact: `{summary.get('tuning_packet_artifact') or '-'}`",
        f"- sweep_packet_artifact: `{summary.get('sweep_packet_artifact') or '-'}`",
        f"- probe_row_count: `{summary.get('probe_row_count')}`",
        f"- primary_probe_row_key: `{summary.get('primary_probe_row_key') or '-'}`",
        f"- current_gate_mean_min_distance_A: `{_fmt_float(summary.get('current_gate_mean_min_distance_A'))}`",
        f"- projected_gate_mean_min_distance_A: `{_fmt_float(summary.get('projected_gate_mean_min_distance_A'))}`",
        f"- gate_threshold_A: `{_fmt_float(summary.get('gate_threshold_A'))}`",
        f"- projected_gate_delta_A: `{_fmt_float(summary.get('projected_gate_delta_A'))}`",
        f"- projected_gate_pass: `{summary.get('projected_gate_pass', False)}`",
        "",
        "## Next Step",
        "",
        f"- {summary.get('next_required_step') or '-'}",
        "",
        "## Probe Rows",
        "",
        "| row_key | original_mean | probe_mean | delta | strategy_reason | manifest |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['row_key']}` | {_fmt_float(row['original_mean_min_distance_A'])} | {_fmt_float(row['probe_mean_min_distance_A'])} | "
            f"{_fmt_float(row['distance_delta_A'])} | `{row['strategy_reason']}` | `{row['probe_manifest_artifact']}` |"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the nightly stage6 probe result packet.")
    parser.add_argument("--tuning-json", default=DEFAULT_TUNING_JSON)
    parser.add_argument("--sweep-json", default=DEFAULT_SWEEP_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        tuning_payload=_load_json(args.tuning_json),
        sweep_payload=_load_json(args.sweep_json),
        probe_manifest_artifacts=DEFAULT_PROBE_MANIFESTS,
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
