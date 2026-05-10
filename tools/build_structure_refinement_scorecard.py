#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from tools.lib.artifacts import (
    artifact as _artifact,
    read_csv as _read_csv,
    read_json as _read_json,
    resolve as _resolve,
    summary as _summary,
    text as _text,
    write_csv as _write_csv,
    write_json as _write_json,
)

DEFAULT_NATIVE_MANIFEST_CSV = "runs/selected_allatom_native_structure_manifest_current.csv"
DEFAULT_TCRUZI_REVIEW_JSON = "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json"
DEFAULT_SARSCOV2_RUNNER_JSON = "runs/wetlab_sarscov2_mpro_allatom_refinement_runner_current.json"
DEFAULT_CATHEPSIN_RUNNER_JSON = "runs/wetlab_cathepsin_k_allatom_refinement_runner_current.json"
DEFAULT_METRIC_MATERIALIZATION_JSON = "runs/structure_refinement_metric_materialization_current.json"
DEFAULT_OUT_JSON = "runs/structure_refinement_scorecard_current.json"
DEFAULT_OUT_CSV = "runs/structure_refinement_scorecard_current.csv"
DEFAULT_OUT_MD = "runs/structure_refinement_scorecard_current.md"


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "pass", "ready"}:
        return True
    if text in {"false", "0", "no", "fail", "blocked"}:
        return False
    return None


def _metric_present(summary: dict[str, Any], names: tuple[str, ...]) -> bool:
    return any(_float(summary.get(name)) is not None for name in names)


def _materialized_by_target(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("metric_status") != "metrics_computed":
            continue
        out.setdefault(_text(row.get("target")), []).append(row)
    return out


def _native_by_target(native_manifest_csv: str | Path) -> dict[str, dict[str, str]]:
    return {row.get("target", "").strip(): row for row in _read_csv(native_manifest_csv)}


def _row(
    *,
    target_id: str,
    native_row: dict[str, str],
    source_artifact: str,
    source_summary: dict[str, Any],
    materialized_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    native_path = _text(native_row.get("path")) or _text(source_summary.get("target_native_pdb_path"))
    native_reference_available = bool(native_path and Path(native_path).exists())
    scores_csv = _text(source_summary.get("allatom_scores_csv"))
    allatom_scores_available = bool(scores_csv and Path(scores_csv).exists())
    pseudo_lane_ready = _text(source_summary.get("status")).endswith("_ready") or bool(
        source_summary.get("packet_ready_for_operator_review")
    )
    materialized_rmsd_available = any(_float(row.get("ca_aligned_rmsd_A")) is not None for row in materialized_rows)
    materialized_gdt_proxy_available = any(_float(row.get("gdt_ts_proxy")) is not None for row in materialized_rows)
    materialized_tm_proxy_available = any(_float(row.get("tm_score_ca_proxy")) is not None for row in materialized_rows)
    materialized_lddt_proxy_available = any(_float(row.get("lddt_ca_proxy")) is not None for row in materialized_rows)
    rmsd_available = (
        _metric_present(source_summary, ("rmsd", "avg_rmsd", "avg_rmsd_aligned", "structure_rmsd_A"))
        or materialized_rmsd_available
    )
    tm_score_available = _metric_present(source_summary, ("tm_score", "tm_score_mean"))
    gdt_available = _metric_present(source_summary, ("gdt_ts", "gdt_ha", "gdt_ts_mean"))
    lddt_available = _metric_present(source_summary, ("lddt", "lddt_mean", "molprobity_score"))
    dockq_available = _metric_present(source_summary, ("dockq", "dockq_mean", "interface_rmsd_A"))

    blockers: list[str] = []
    if not native_reference_available:
        blockers.append("native_reference_missing")
    if not pseudo_lane_ready:
        blockers.append("pseudo_allatom_lane_not_ready")
    if not rmsd_available:
        blockers.append("rmsd_missing")
    if not tm_score_available:
        blockers.append("tm_score_missing")
    if not gdt_available:
        blockers.append("gdt_missing")
    if not lddt_available:
        blockers.append("lddt_or_molprobity_missing")
    if not dockq_available:
        blockers.append("dockq_or_interface_metric_missing")

    return {
        "target_id": target_id,
        "source_artifact": source_artifact,
        "native_reference_available": native_reference_available,
        "native_pdb_id": _text(native_row.get("pdb_id")) or _text(source_summary.get("target_native_pdb_id")),
        "native_pdb_path": native_path,
        "pseudo_allatom_lane_ready": pseudo_lane_ready,
        "selected_command_kind": _text(source_summary.get("selected_command_kind")),
        "slice_candidate_count": _float(source_summary.get("slice_candidate_count")),
        "allatom_scores_available": allatom_scores_available,
        "rmsd_available": rmsd_available,
        "tm_score_available": tm_score_available,
        "gdt_available": gdt_available,
        "gdt_ts_proxy_available": materialized_gdt_proxy_available,
        "tm_score_ca_proxy_available": materialized_tm_proxy_available,
        "lddt_ca_proxy_available": materialized_lddt_proxy_available,
        "materialized_metric_candidate_count": len(materialized_rows),
        "best_ca_aligned_rmsd_A": min(
            (_float(row.get("ca_aligned_rmsd_A")) for row in materialized_rows if _float(row.get("ca_aligned_rmsd_A")) is not None),
            default=None,
        ),
        "best_gdt_ts_proxy": max(
            (_float(row.get("gdt_ts_proxy")) for row in materialized_rows if _float(row.get("gdt_ts_proxy")) is not None),
            default=None,
        ),
        "best_tm_score_ca_proxy": max(
            (_float(row.get("tm_score_ca_proxy")) for row in materialized_rows if _float(row.get("tm_score_ca_proxy")) is not None),
            default=None,
        ),
        "best_lddt_ca_proxy": max(
            (_float(row.get("lddt_ca_proxy")) for row in materialized_rows if _float(row.get("lddt_ca_proxy")) is not None),
            default=None,
        ),
        "lddt_or_molprobity_available": lddt_available,
        "dockq_or_interface_metric_available": dockq_available,
        "wetlab_gate_pass": _bool(source_summary.get("wetlab_gate_pass")),
        "commercial_hard_gate_pass": _bool(
            source_summary.get("commercial_hard_gate_pass")
            if "commercial_hard_gate_pass" in source_summary
            else source_summary.get("commercial_hard_gate_pass_v2")
        ),
        "claim_promotion_allowed": False,
        "blockers": blockers,
    }


def build_scorecard(
    *,
    native_manifest_csv: str | Path = DEFAULT_NATIVE_MANIFEST_CSV,
    tcruzi_review_json: str | Path = DEFAULT_TCRUZI_REVIEW_JSON,
    sarscov2_runner_json: str | Path = DEFAULT_SARSCOV2_RUNNER_JSON,
    cathepsin_runner_json: str | Path = DEFAULT_CATHEPSIN_RUNNER_JSON,
    metric_materialization_json: str | Path = DEFAULT_METRIC_MATERIALIZATION_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    native_rows = _native_by_target(native_manifest_csv)
    materialized = _materialized_by_target(_read_json(metric_materialization_json))
    source_specs = [
        ("T. cruzi PDE", tcruzi_review_json),
        ("SARS-CoV-2 Mpro", sarscov2_runner_json),
        ("Cathepsin K", cathepsin_runner_json),
    ]
    rows = [
        _row(
            target_id=target,
            native_row=native_rows.get(target, {}),
            source_artifact=_artifact(path),
            source_summary=_summary(_read_json(path)),
            materialized_rows=materialized.get(target, []),
        )
        for target, path in source_specs
    ]
    blocker_counts: dict[str, int] = {}
    for row in rows:
        for blocker in row["blockers"]:
            blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
    target_count = len(rows)
    native_count = sum(1 for row in rows if row["native_reference_available"])
    pseudo_ready_count = sum(1 for row in rows if row["pseudo_allatom_lane_ready"])
    rmsd_count = sum(1 for row in rows if row["rmsd_available"])
    tm_count = sum(1 for row in rows if row["tm_score_available"])
    gdt_count = sum(1 for row in rows if row["gdt_available"])
    gdt_proxy_count = sum(1 for row in rows if row["gdt_ts_proxy_available"])
    tm_proxy_count = sum(1 for row in rows if row["tm_score_ca_proxy_available"])
    lddt_proxy_count = sum(1 for row in rows if row["lddt_ca_proxy_available"])
    lddt_count = sum(1 for row in rows if row["lddt_or_molprobity_available"])
    dockq_count = sum(1 for row in rows if row["dockq_or_interface_metric_available"])
    claim_allowed = (
        target_count > 0
        and native_count == target_count
        and rmsd_count == target_count
        and tm_count == target_count
        and gdt_count == target_count
        and lddt_count == target_count
        and dockq_count == target_count
    )
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "structure_refinement_scorecard_pass" if claim_allowed else "blocked_structure_refinement_metrics_missing",
        "target_count": target_count,
        "native_reference_target_count": native_count,
        "pseudo_allatom_lane_ready_count": pseudo_ready_count,
        "rmsd_available_count": rmsd_count,
        "tm_score_available_count": tm_count,
        "gdt_available_count": gdt_count,
        "gdt_ts_proxy_available_count": gdt_proxy_count,
        "tm_score_ca_proxy_available_count": tm_proxy_count,
        "lddt_ca_proxy_available_count": lddt_proxy_count,
        "lddt_or_molprobity_available_count": lddt_count,
        "dockq_or_interface_metric_available_count": dockq_count,
        "rmsd_pass": rmsd_count == target_count and target_count > 0,
        "tm_score_pass": tm_count == target_count and target_count > 0,
        "gdt_pass": gdt_count == target_count and target_count > 0,
        "lddt_pass": lddt_count == target_count and target_count > 0,
        "dockq_pass": dockq_count == target_count and target_count > 0,
        "claim_promotion_allowed": claim_allowed,
        "galaxy_class_claim_allowed": claim_allowed,
        "blockers": sorted(blocker_counts),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "source_artifacts": {
            "native_manifest_csv": _artifact(native_manifest_csv),
            "tcruzi_review_json": _artifact(tcruzi_review_json),
            "sarscov2_runner_json": _artifact(sarscov2_runner_json),
            "cathepsin_runner_json": _artifact(cathepsin_runner_json),
            "metric_materialization_json": _artifact(metric_materialization_json),
        },
        "next_required_step": (
            "Compute frozen structure/refinement metrics for each native-backed target: RMSD, TM-score, "
            "GDT-TS/GDT-HA, lDDT or MolProbity, and DockQ/interface RMSD where applicable."
        ),
    }
    return {
        "packet_type": "structure_refinement_scorecard",
        "summary": summary,
        "rows": rows,
        "claim_boundary": {
            "claim_promotion_allowed": claim_allowed,
            "galaxy_class_claim_allowed": claim_allowed,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "pseudo_allatom_lane_alone_is_not_structure_parity": True,
            "ca_proxy_metrics_do_not_unlock_galaxy_class_claim": True,
        },
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Structure Refinement Scorecard",
        "",
        "## Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- native_reference_target_count: `{summary['native_reference_target_count']}`",
        f"- pseudo_allatom_lane_ready_count: `{summary['pseudo_allatom_lane_ready_count']}`",
        f"- rmsd/tm/gdt/lddt/dockq available counts: `{summary['rmsd_available_count']}` / `{summary['tm_score_available_count']}` / `{summary['gdt_available_count']}` / `{summary['lddt_or_molprobity_available_count']}` / `{summary['dockq_or_interface_metric_available_count']}`",
        f"- gdt_ts_proxy_available_count: `{summary['gdt_ts_proxy_available_count']}`",
        f"- tm_score_ca_proxy_available_count: `{summary['tm_score_ca_proxy_available_count']}`",
        f"- lddt_ca_proxy_available_count: `{summary['lddt_ca_proxy_available_count']}`",
        f"- galaxy_class_claim_allowed: `{str(summary['galaxy_class_claim_allowed']).lower()}`",
        "",
        "## Rows",
        "",
        "| Target | Native | Pseudo Lane | RMSD | TM | GDT | GDT proxy | TM CA proxy | lDDT CA proxy | lDDT/MolProbity | DockQ/Interface | Blockers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["rows"]:
        blockers = ", ".join(f"`{blocker}`" for blocker in row["blockers"][:5]) or "none"
        lines.append(
            f"| `{row['target_id']}` | `{str(row['native_reference_available']).lower()}` | "
            f"`{str(row['pseudo_allatom_lane_ready']).lower()}` | `{str(row['rmsd_available']).lower()}` | "
            f"`{str(row['tm_score_available']).lower()}` | `{str(row['gdt_available']).lower()}` | "
            f"`{str(row['gdt_ts_proxy_available']).lower()}` | "
            f"`{str(row['tm_score_ca_proxy_available']).lower()}` | "
            f"`{str(row['lddt_ca_proxy_available']).lower()}` | "
            f"`{str(row['lddt_or_molprobity_available']).lower()}` | "
            f"`{str(row['dockq_or_interface_metric_available']).lower()}` | {blockers} |"
        )
    lines.extend(["", "## Next Required Step", "", f"- {summary['next_required_step']}", ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a GALAXY-style structure/refinement scorecard shell.")
    parser.add_argument("--native-manifest-csv", default=DEFAULT_NATIVE_MANIFEST_CSV)
    parser.add_argument("--tcruzi-review-json", default=DEFAULT_TCRUZI_REVIEW_JSON)
    parser.add_argument("--sarscov2-runner-json", default=DEFAULT_SARSCOV2_RUNNER_JSON)
    parser.add_argument("--cathepsin-runner-json", default=DEFAULT_CATHEPSIN_RUNNER_JSON)
    parser.add_argument("--metric-materialization-json", default=DEFAULT_METRIC_MATERIALIZATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_scorecard(
        native_manifest_csv=args.native_manifest_csv,
        tcruzi_review_json=args.tcruzi_review_json,
        sarscov2_runner_json=args.sarscov2_runner_json,
        cathepsin_runner_json=args.cathepsin_runner_json,
        metric_materialization_json=args.metric_materialization_json,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
