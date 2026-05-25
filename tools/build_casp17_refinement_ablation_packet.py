#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from build_casp17_historical_benchmark_packet import (
    _artifact,
    _read_manifest,
    _resolve,
    _score_one,
    _text,
)


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_current.csv"
DEFAULT_OUT_JSON = "runs/casp17_refinement_ablation_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_refinement_ablation_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_refinement_ablation_packet_current.md"

DEFAULT_LAYERS = [
    "recursive=runs/casp17_historical_ablation_predictions_current/recursive",
    "scored=runs/casp17_historical_ablation_predictions_current/scored",
    "sidechain_scaffold=runs/casp17_historical_ablation_predictions_current/sidechain_scaffold",
    "sidechain_repacked=runs/casp17_historical_ablation_predictions_current/sidechain_repacked",
    "sidechain_completed=runs/casp17_historical_ablation_predictions_current/sidechain_completed",
    "steric_relaxed=runs/casp17_historical_ablation_predictions_current/steric_relaxed",
    "rotamer_minimized=runs/casp17_historical_ablation_predictions_current/rotamer_minimized",
    "polar_refined=runs/casp17_historical_ablation_predictions_current/polar_refined",
    "forcefield_minimized=runs/casp17_historical_ablation_predictions_current/forcefield_minimized",
    "statistical_rotamer=runs/casp17_historical_ablation_predictions_current/statistical_rotamer",
]

THRESHOLD_BLOCKERS = {
    "monomer_tm_below_threshold",
    "monomer_gdt_ts_below_threshold",
    "monomer_lddt_below_threshold",
    "complex_tm_below_threshold",
    "complex_interface_f1_below_threshold",
}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["benchmark_id", "layer_name"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _parse_layer_specs(specs: list[str]) -> list[tuple[str, str]]:
    layers: list[tuple[str, str]] = []
    seen: set[str] = set()
    for spec in specs:
        if "=" not in spec:
            raise SystemExit(f"invalid layer spec {spec!r}; expected name=prediction_dir")
        name, path = spec.split("=", 1)
        name = _text(name)
        path = _text(path)
        if not name or not path:
            raise SystemExit(f"invalid layer spec {spec!r}; expected nonempty name and path")
        if name in seen:
            raise SystemExit(f"duplicate layer name {name!r}")
        seen.add(name)
        layers.append((name, path))
    return layers


def _prediction_path_for_layer(manifest_row: dict[str, str], layer_name: str, layer_dir: str | Path) -> Path:
    explicit = _text(manifest_row.get(f"{layer_name}_prediction_pdb")) or _text(manifest_row.get(f"prediction_pdb_{layer_name}"))
    if explicit:
        return _resolve(explicit)
    target_id = _text(manifest_row.get("target_id")) or _text(manifest_row.get("benchmark_id"))
    candidate = _resolve(layer_dir) / f"{target_id}TS.pdb"
    if candidate.exists():
        return candidate
    return _resolve(layer_dir) / f"{target_id}.pdb"


def _hard_blockers(blockers: str) -> list[str]:
    return [blocker for blocker in blockers.split(",") if blocker and blocker not in THRESHOLD_BLOCKERS]


def _score_layer(
    manifest_row: dict[str, str],
    *,
    layer_name: str,
    layer_dir: str,
    layer_index: int,
    args: argparse.Namespace,
) -> dict[str, Any]:
    prediction_path = _prediction_path_for_layer(manifest_row, layer_name, layer_dir)
    scoring_row = dict(manifest_row)
    scoring_row["prediction_pdb"] = str(prediction_path)
    scored = _score_one(scoring_row, args)
    hard_blockers = _hard_blockers(str(scored.get("blockers") or ""))
    return {
        **scored,
        "layer_index": layer_index,
        "layer_name": layer_name,
        "layer_prediction_dir": _artifact(layer_dir),
        "layer_prediction_pdb": _artifact(prediction_path),
        "layer_score_usable": not hard_blockers,
        "layer_hard_blockers": ",".join(hard_blockers),
    }


def _layer_row(rows: list[dict[str, Any]], benchmark_id: str, layer_name: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("benchmark_id") == benchmark_id and row.get("layer_name") == layer_name:
            return row
    return None


def _metric_delta(final: dict[str, Any], baseline: dict[str, Any], key: str) -> float:
    return round(float(final.get(key, 0.0) or 0.0) - float(baseline.get(key, 0.0) or 0.0), 6)


def _rmsd_delta(final: dict[str, Any], baseline: dict[str, Any]) -> float:
    return round(float(baseline.get("ca_rmsd_A", 0.0) or 0.0) - float(final.get("ca_rmsd_A", 0.0) or 0.0), 6)


def _build_group_rows(rows: list[dict[str, Any]], manifest_rows: list[dict[str, str]], args: argparse.Namespace) -> list[dict[str, Any]]:
    group_rows: list[dict[str, Any]] = []
    for manifest_row in manifest_rows:
        benchmark_id = _text(manifest_row.get("benchmark_id")) or _text(manifest_row.get("target_id")) or "unknown"
        baseline = _layer_row(rows, benchmark_id, args.baseline_layer)
        final = _layer_row(rows, benchmark_id, args.final_layer)
        blockers: list[str] = []
        if baseline is None:
            blockers.append("baseline_layer_missing")
        if final is None:
            blockers.append("final_layer_missing")
        if baseline is not None and not bool(baseline.get("layer_score_usable")):
            blockers.append("baseline_layer_unusable")
        if final is not None and not bool(final.get("layer_score_usable")):
            blockers.append("final_layer_unusable")
        tm_delta = _metric_delta(final or {}, baseline or {}, "tm_score_proxy")
        gdt_delta = _metric_delta(final or {}, baseline or {}, "gdt_ts_proxy")
        lddt_delta = _metric_delta(final or {}, baseline or {}, "ca_lddt_proxy")
        interface_delta = _metric_delta(final or {}, baseline or {}, "interface_contact_f1_proxy")
        rmsd_improvement = _rmsd_delta(final or {}, baseline or {})
        not_worse = (
            tm_delta >= -float(args.not_worse_tolerance)
            and gdt_delta >= -float(args.not_worse_tolerance)
            and lddt_delta >= -float(args.not_worse_tolerance)
            and rmsd_improvement >= -float(args.rmsd_not_worse_tolerance)
        )
        improved = (
            tm_delta > float(args.improvement_epsilon)
            or gdt_delta > float(args.improvement_epsilon)
            or lddt_delta > float(args.improvement_epsilon)
            or rmsd_improvement > float(args.rmsd_improvement_epsilon)
            or interface_delta > float(args.improvement_epsilon)
        )
        if baseline is not None and final is not None and bool(baseline.get("layer_score_usable")) and bool(final.get("layer_score_usable")):
            if not not_worse:
                blockers.append("final_layer_worse_than_baseline")
            if not improved:
                blockers.append("final_layer_not_improved")
        group_rows.append(
            {
                "benchmark_id": benchmark_id,
                "target_id": _text(manifest_row.get("target_id")) or benchmark_id,
                "scope": _text(manifest_row.get("scope")) or "monomer",
                "baseline_layer": args.baseline_layer,
                "final_layer": args.final_layer,
                "baseline_tm_score_proxy": baseline.get("tm_score_proxy", 0.0) if baseline else 0.0,
                "final_tm_score_proxy": final.get("tm_score_proxy", 0.0) if final else 0.0,
                "delta_tm_score_proxy": tm_delta,
                "baseline_gdt_ts_proxy": baseline.get("gdt_ts_proxy", 0.0) if baseline else 0.0,
                "final_gdt_ts_proxy": final.get("gdt_ts_proxy", 0.0) if final else 0.0,
                "delta_gdt_ts_proxy": gdt_delta,
                "baseline_ca_lddt_proxy": baseline.get("ca_lddt_proxy", 0.0) if baseline else 0.0,
                "final_ca_lddt_proxy": final.get("ca_lddt_proxy", 0.0) if final else 0.0,
                "delta_ca_lddt_proxy": lddt_delta,
                "baseline_ca_rmsd_A": baseline.get("ca_rmsd_A", 0.0) if baseline else 0.0,
                "final_ca_rmsd_A": final.get("ca_rmsd_A", 0.0) if final else 0.0,
                "rmsd_improvement_A": rmsd_improvement,
                "delta_interface_contact_f1_proxy": interface_delta,
                "final_layer_not_worse": not_worse and not blockers,
                "final_layer_improved": improved and not blockers,
                "ablation_group_status": "pass" if not blockers else "blocked",
                "blockers": ",".join(sorted(set(blockers))),
            }
        )
    return group_rows


def _mean(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row.get(key, 0.0) or 0.0) for row in rows if row.get("ablation_group_status") == "pass"]
    return round(sum(values) / len(values), 6) if values else 0.0


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    layers = _parse_layer_specs(args.layer or DEFAULT_LAYERS)
    layer_names = [name for name, _path in layers]
    config_blockers: list[str] = []
    if args.baseline_layer not in layer_names:
        config_blockers.append("baseline_layer_not_in_layer_specs")
    if args.final_layer not in layer_names:
        config_blockers.append("final_layer_not_in_layer_specs")
    manifest_rows, manifest_blockers = _read_manifest(args.manifest_csv)
    rows: list[dict[str, Any]] = []
    if not config_blockers:
        for manifest_row in manifest_rows:
            for layer_index, (layer_name, layer_dir) in enumerate(layers, start=1):
                rows.append(_score_layer(manifest_row, layer_name=layer_name, layer_dir=layer_dir, layer_index=layer_index, args=args))
    group_rows = [] if config_blockers else _build_group_rows(rows, manifest_rows, args)
    layer_count = len(layers)
    expected_layer_rows = len(manifest_rows) * layer_count
    usable_layer_count = sum(1 for row in rows if row.get("layer_score_usable") is True)
    blocked_layer_count = len(rows) - usable_layer_count
    pass_group_count = sum(1 for row in group_rows if row.get("ablation_group_status") == "pass")
    improved_group_count = sum(1 for row in group_rows if row.get("final_layer_improved") is True)
    not_worse_group_count = sum(1 for row in group_rows if row.get("final_layer_not_worse") is True)
    required_improved_count = int(round(len(group_rows) * float(args.min_improved_fraction) + 0.499999)) if group_rows else 0
    blocked_count = blocked_layer_count + (len(group_rows) - pass_group_count) + len(manifest_blockers) + len(config_blockers)
    status = (
        "pass"
        if rows
        and not manifest_blockers
        and not config_blockers
        and len(rows) == expected_layer_rows
        and blocked_layer_count == 0
        and pass_group_count == len(group_rows)
        and not_worse_group_count == len(group_rows)
        and improved_group_count >= required_improved_count
        else "blocked"
    )
    summary = {
        "packet_type": "casp17_refinement_ablation_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "manifest_csv": _artifact(args.manifest_csv),
        "layer_count": layer_count,
        "layers": [{"name": name, "prediction_dir": _artifact(path)} for name, path in layers],
        "baseline_layer": args.baseline_layer,
        "final_layer": args.final_layer,
        "benchmark_count": len(manifest_rows),
        "layer_row_count": len(rows),
        "expected_layer_row_count": expected_layer_rows,
        "usable_layer_count": usable_layer_count,
        "blocked_layer_count": blocked_layer_count,
        "ablation_group_count": len(group_rows),
        "ablation_group_pass_count": pass_group_count,
        "final_not_worse_count": not_worse_group_count,
        "final_improved_count": improved_group_count,
        "required_improved_count": required_improved_count,
        "min_improved_fraction": float(args.min_improved_fraction),
        "mean_delta_tm_score_proxy": _mean(group_rows, "delta_tm_score_proxy"),
        "mean_delta_gdt_ts_proxy": _mean(group_rows, "delta_gdt_ts_proxy"),
        "mean_delta_ca_lddt_proxy": _mean(group_rows, "delta_ca_lddt_proxy"),
        "mean_rmsd_improvement_A": _mean(group_rows, "rmsd_improvement_A"),
        "refinement_ablation_status": status,
        "manifest_blockers": ",".join(manifest_blockers),
        "config_blockers": ",".join(config_blockers),
        "blocked_count": blocked_count,
        "claim_boundary": "No-leak historical refinement ablation proxy only; not official CASP scoring and not current-target native evidence.",
    }
    return {"summary": summary, "rows": rows, "group_rows": group_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Refinement Ablation Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- manifest_csv: `{summary['manifest_csv']}`",
        f"- status: `{summary['refinement_ablation_status']}`",
        f"- benchmark_count: `{summary['benchmark_count']}`",
        f"- layers: `{summary['layer_count']}`",
        f"- usable/blocked layer rows: `{summary['usable_layer_count']}/{summary['blocked_layer_count']}`",
        f"- baseline/final: `{summary['baseline_layer']}/{summary['final_layer']}`",
        f"- final not-worse/improved: `{summary['final_not_worse_count']}/{summary['final_improved_count']}`",
        f"- mean delta TM/GDT_TS/lDDT/RMSD-improvement: `{summary['mean_delta_tm_score_proxy']}/{summary['mean_delta_gdt_ts_proxy']}/{summary['mean_delta_ca_lddt_proxy']}/{summary['mean_rmsd_improvement_A']}`",
        f"- manifest_blockers: `{summary['manifest_blockers'] or '-'}`",
        f"- config_blockers: `{summary['config_blockers'] or '-'}`",
        "",
        "## Group Deltas",
        "",
        "| benchmark | target | scope | status | baseline | final | dTM | dGDT_TS | dlDDT | RMSD improvement A | blockers |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["group_rows"]:
        lines.append(
            f"| `{row['benchmark_id']}` | `{row['target_id']}` | `{row['scope']}` | `{row['ablation_group_status']}` | "
            f"`{row['baseline_layer']}` | `{row['final_layer']}` | {row['delta_tm_score_proxy']} | "
            f"{row['delta_gdt_ts_proxy']} | {row['delta_ca_lddt_proxy']} | {row['rmsd_improvement_A']} | {row['blockers'] or '-'} |"
        )
    if not payload["group_rows"]:
        lines.append("| - | - | - | `blocked` | - | - | 0 | 0 | 0 | 0 | manifest missing or empty |")
    lines.extend(
        [
            "",
            "## Layer Rows",
            "",
            "| benchmark | layer | status | usable | CA | TM | GDT_TS | lDDT | RMSD A | interface F1 | blockers |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['benchmark_id']}` | `{row['layer_name']}` | `{row['benchmark_status']}` | {row['layer_score_usable']} | "
            f"{row['matched_ca_count']} | {row['tm_score_proxy']} | {row['gdt_ts_proxy']} | "
            f"{row['ca_lddt_proxy']} | {row['ca_rmsd_A']} | {row['interface_contact_f1_proxy']} | {row['blockers'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `blocked` | False | 0 | 0 | 0 | 0 | 0 | 0 | manifest missing or empty |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build no-leak historical ablation evidence across CASP17 internal refinement layers.")
    parser.add_argument("--manifest-csv", default=DEFAULT_MANIFEST_CSV)
    parser.add_argument("--layer", action="append", help="Layer spec as name=prediction_dir. Defaults to historical ablation layer dirs.")
    parser.add_argument("--baseline-layer", default="recursive")
    parser.add_argument("--final-layer", default="statistical_rotamer")
    parser.add_argument("--min-ca-count", type=int, default=20)
    parser.add_argument("--monomer-tm-threshold", type=float, default=0.90)
    parser.add_argument("--monomer-gdt-ts-threshold", type=float, default=0.80)
    parser.add_argument("--monomer-lddt-threshold", type=float, default=0.75)
    parser.add_argument("--complex-tm-threshold", type=float, default=0.75)
    parser.add_argument("--complex-interface-f1-threshold", type=float, default=0.50)
    parser.add_argument("--min-sequence-match-fraction", type=float, default=1.0)
    parser.add_argument("--min-ca-coverage", type=float, default=1.0)
    parser.add_argument("--allow-order-fallback", action="store_true")
    parser.add_argument("--not-worse-tolerance", type=float, default=0.001)
    parser.add_argument("--rmsd-not-worse-tolerance", type=float, default=0.01)
    parser.add_argument("--improvement-epsilon", type=float, default=0.001)
    parser.add_argument("--rmsd-improvement-epsilon", type=float, default=0.01)
    parser.add_argument("--min-improved-fraction", type=float, default=0.50)
    parser.add_argument("--fail-on-blocked", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if args.fail_on_blocked and payload["summary"]["blocked_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
