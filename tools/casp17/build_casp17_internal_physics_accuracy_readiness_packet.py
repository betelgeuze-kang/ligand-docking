#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_RAW_GATE_JSON = "runs/casp17_internal_physics_raw_gate_packet_quality_current.json"
DEFAULT_TS_GATE_JSON = "runs/casp17_internal_physics_ts_gate_batch_quality_current.json"
DEFAULT_SUBMISSION_GATE_JSON = "runs/casp17_submission_gate_packet_quality_current.json"
DEFAULT_JOB_DIR = "runs/casp17_prediction_jobs_quality_current"
DEFAULT_OUT_JSON = "runs/casp17_internal_physics_accuracy_readiness_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_internal_physics_accuracy_readiness_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_internal_physics_accuracy_readiness_packet_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _rows(payload: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


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
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Internal Physics Accuracy Readiness Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target count: `{summary['target_count']}`",
        f"- pass/fail: `{summary['pass_count']}/{summary['fail_count']}`",
        f"- require backbone atoms: `{summary['require_backbone_atoms']}`",
        f"- packet status: `{summary['accuracy_readiness_status']}`",
        "",
        "## Rows",
        "",
        "| target | status | chains | residues | ensemble/steps | rg max ratio | contacts | min inter-CA | inter clashes | atom/residue | blockers |",
        "| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['accuracy_readiness_status']}` | {row['chain_count']} | {row['residue_count']} | "
            f"`{row['ensemble_size']}/{row['steps']}` | {row['max_chain_rg_ratio']} | {row['interchain_ca_contact_count_12A']} | "
            f"{row['min_interchain_ca_distance_A']} | {row['interchain_ca_clash_count_3A']} | {row['atom_to_residue_ratio']} | "
            f"{row['blockers'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | `no_rows` | 0 | 0 | `0/0` | 0 | 0 | 0 | 0 | 0 | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _index(rows: list[dict[str, Any]], key: str = "target_id") -> dict[str, dict[str, Any]]:
    return {_text(row.get(key)).upper(): row for row in rows if _text(row.get(key))}


def _current_open_targets(watchlist: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for row in _rows(watchlist):
        lane = _text(row.get("lane_recommendation"))
        if row.get("human_open") is True and lane in {"organic_ligand_protein_complexes", "difficult_protein_complexes"}:
            out.add(_text(row.get("target_id")).upper())
    return out


def _blocker(code: str) -> str:
    return code


def _float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _target_rg(residue_count: int) -> float:
    return max(7.5, 2.10 * (float(max(residue_count, 1)) ** 0.38))


def _ts_counts(path_like: str | Path) -> dict[str, Any]:
    if not _text(path_like):
        return {"exists": False, "atom_count": 0, "parent_count": 0, "ter_count": 0, "chain_segment_count": 0}
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return {"exists": False, "atom_count": 0, "parent_count": 0, "ter_count": 0, "chain_segment_count": 0}
    parent_count = 0
    ter_count = 0
    atom_count = 0
    chain_segments = 0
    previous_chain = None
    in_model = False
    seen_model = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        rec = line[:6].strip().upper()
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            in_model = True
            continue
        if rec == "END" and in_model:
            break
        if not in_model and seen_model:
            continue
        if rec == "PARENT":
            parent_count += 1
        elif rec == "TER":
            ter_count += 1
        elif rec == "ATOM":
            atom_count += 1
            chain_id = line[21].strip() if len(line) > 21 else "_"
            if chain_id != previous_chain:
                chain_segments += 1
                previous_chain = chain_id
    return {
        "exists": True,
        "atom_count": atom_count,
        "parent_count": parent_count,
        "ter_count": ter_count,
        "chain_segment_count": chain_segments,
    }


def _row_for_target(
    target_id: str,
    *,
    current_open: set[str],
    raw_by_target: dict[str, dict[str, Any]],
    ts_by_target: dict[str, dict[str, Any]],
    submission_by_target: dict[str, dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    blockers: list[str] = []
    raw = raw_by_target.get(target_id, {})
    ts = ts_by_target.get(target_id, {})
    submission = submission_by_target.get(target_id, {})
    metrics_path = _resolve(args.job_dir) / target_id / "internal_physics_metrics.json"
    metrics = _read_json(metrics_path)
    metrics_summary = metrics.get("summary") if isinstance(metrics.get("summary"), dict) else {}
    assembly = metrics.get("assembly") if isinstance(metrics.get("assembly"), dict) else {}
    chains = metrics.get("chains") if isinstance(metrics.get("chains"), list) else []

    if target_id not in current_open:
        blockers.append(_blocker("not_current_open_selected_protein_target"))
    if _text(raw.get("raw_gate_status")) != "pass":
        blockers.append(_blocker("raw_gate_not_pass"))
    if _text(ts.get("ts_conversion_status")) != "converted":
        blockers.append(_blocker("ts_conversion_not_converted"))
    if _text(submission.get("submission_decision")) != "submission_go":
        blockers.append(_blocker("submission_gate_not_go"))
    if not metrics:
        blockers.append(_blocker("internal_physics_metrics_missing"))

    chain_count = _int(metrics_summary.get("chain_count") or assembly.get("chain_count"))
    residue_count = _int(metrics_summary.get("residue_count"))
    ensemble_size = _int(metrics_summary.get("ensemble_size"))
    steps = _int(metrics_summary.get("steps"))
    if ensemble_size < int(args.min_ensemble_size):
        blockers.append(_blocker("ensemble_size_below_quality_floor"))
    if steps < int(args.min_steps):
        blockers.append(_blocker("annealing_steps_below_quality_floor"))

    max_rg_ratio = 0.0
    confidence_mean_min = 100.0
    confidence_mean_max = 0.0
    for chain in chains:
        if not isinstance(chain, dict):
            continue
        length = _int(chain.get("sequence_length") or chain.get("residue_count"))
        rg = _float(chain.get("rg_A"))
        ratio = _float(chain.get("rg_ratio"))
        if ratio <= 0.0:
            ratio = rg / _target_rg(length) if length else 0.0
        max_rg_ratio = max(max_rg_ratio, ratio)
        confidence_mean = _float(chain.get("confidence_mean"))
        confidence_mean_min = min(confidence_mean_min, confidence_mean)
        confidence_mean_max = max(confidence_mean_max, confidence_mean)
        if not math.isfinite(_float(chain.get("energy"), float("nan"))):
            blockers.append(_blocker("nonfinite_chain_energy"))
        if ratio < float(args.min_rg_ratio) or ratio > float(args.max_rg_ratio):
            blockers.append(_blocker("chain_rg_ratio_outside_proxy_band"))
        if _float(chain.get("ca_distance_min_A")) < 3.0 or _float(chain.get("ca_distance_max_A")) > 4.8:
            blockers.append(_blocker("ca_continuity_outside_tight_proxy_band"))
        if confidence_mean < float(args.min_confidence_mean) or confidence_mean > float(args.max_confidence_mean):
            blockers.append(_blocker("confidence_mean_outside_proxy_band"))

    contacts = _int(assembly.get("interchain_ca_contact_count_12A"))
    pair_contacts = _int(assembly.get("chain_pairs_with_contacts_12A"))
    min_inter = _float(assembly.get("min_interchain_ca_distance_A"))
    inter_clashes = _int(assembly.get("interchain_ca_clash_count_3A"))
    if chain_count > 1:
        if contacts < int(args.min_interchain_contacts):
            blockers.append(_blocker("interchain_contact_count_below_proxy_floor"))
        if pair_contacts < max(1, min(chain_count - 1, _int(assembly.get("chain_pair_count"), 1))):
            blockers.append(_blocker("too_few_chain_pairs_with_contacts"))
        if min_inter < float(args.min_interchain_distance):
            blockers.append(_blocker("interchain_ca_distance_below_proxy_floor"))
        if inter_clashes > int(args.max_interchain_clashes):
            blockers.append(_blocker("interchain_ca_clashes_above_proxy_floor"))

    ts_path = _text(submission.get("prediction_file_path") or ts.get("ts_pdb"))
    ts_counts = _ts_counts(ts_path)
    if not ts_counts["exists"]:
        blockers.append(_blocker("ts_prediction_file_missing"))
    if chain_count and ts_counts["chain_segment_count"] < chain_count:
        blockers.append(_blocker("ts_chain_segment_count_below_fasta_chain_count"))
    if chain_count and ts_counts["parent_count"] < chain_count:
        blockers.append(_blocker("ts_parent_record_count_below_chain_count"))
    if chain_count and ts_counts["ter_count"] < chain_count:
        blockers.append(_blocker("ts_ter_record_count_below_chain_count"))
    atom_to_residue_ratio = ts_counts["atom_count"] / residue_count if residue_count else 0.0
    if args.require_backbone_atoms and atom_to_residue_ratio < 3.0:
        blockers.append(_blocker("backbone_atom_density_below_proxy_floor"))

    unique_blockers = sorted(set(blockers))
    return {
        "target_id": target_id,
        "accuracy_readiness_status": "pass" if not unique_blockers else "fail",
        "chain_count": chain_count,
        "residue_count": residue_count,
        "ensemble_size": ensemble_size,
        "steps": steps,
        "max_chain_rg_ratio": round(max_rg_ratio, 3),
        "confidence_mean_min": round(confidence_mean_min if confidence_mean_min < 100.0 else 0.0, 3),
        "confidence_mean_max": round(confidence_mean_max, 3),
        "interchain_ca_contact_count_12A": contacts,
        "chain_pairs_with_contacts_12A": pair_contacts,
        "min_interchain_ca_distance_A": round(min_inter, 3),
        "interchain_ca_clash_count_3A": inter_clashes,
        "ts_parent_count": ts_counts["parent_count"],
        "ts_ter_count": ts_counts["ter_count"],
        "ts_atom_count": ts_counts["atom_count"],
        "atom_to_residue_ratio": round(atom_to_residue_ratio, 3),
        "metrics_json": _artifact(metrics_path),
        "prediction_file_path": _artifact(ts_path) if ts_path else "",
        "blockers": ";".join(unique_blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    watchlist = _read_json(args.target_watchlist_json)
    raw_gate = _read_json(args.raw_gate_json)
    ts_gate = _read_json(args.ts_gate_json)
    submission_gate = _read_json(args.submission_gate_json)
    current_open = _current_open_targets(watchlist)
    raw_by_target = _index(_rows(raw_gate))
    ts_by_target = _index(_rows(ts_gate))
    submission_by_target = _index(_rows(submission_gate, key="target_rows"))
    target_ids = sorted(current_open | set(submission_by_target))
    rows = [
        _row_for_target(
            target_id,
            current_open=current_open,
            raw_by_target=raw_by_target,
            ts_by_target=ts_by_target,
            submission_by_target=submission_by_target,
            args=args,
        )
        for target_id in target_ids
    ]
    pass_count = sum(1 for row in rows if row["accuracy_readiness_status"] == "pass")
    fail_count = sum(1 for row in rows if row["accuracy_readiness_status"] == "fail")
    summary = {
        "packet_type": "casp17_internal_physics_accuracy_readiness_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_watchlist_json": _artifact(args.target_watchlist_json),
        "raw_gate_json": _artifact(args.raw_gate_json),
        "ts_gate_json": _artifact(args.ts_gate_json),
        "submission_gate_json": _artifact(args.submission_gate_json),
        "job_dir": _artifact(args.job_dir),
        "target_count": len(rows),
        "current_open_selected_target_count": len(current_open),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "require_backbone_atoms": bool(args.require_backbone_atoms),
        "accuracy_readiness_status": "pass" if rows and fail_count == 0 else "fail",
        "claim_boundary": "Internal physics accuracy-readiness proxy only; blind CASP17 native accuracy cannot be proven before official assessment.",
    }
    return {"summary": summary, "rows": rows}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a stronger CASP17 internal-physics accuracy-readiness proxy packet.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--raw-gate-json", default=DEFAULT_RAW_GATE_JSON)
    parser.add_argument("--ts-gate-json", default=DEFAULT_TS_GATE_JSON)
    parser.add_argument("--submission-gate-json", default=DEFAULT_SUBMISSION_GATE_JSON)
    parser.add_argument("--job-dir", default=DEFAULT_JOB_DIR)
    parser.add_argument("--min-ensemble-size", type=int, default=16)
    parser.add_argument("--min-steps", type=int, default=1000)
    parser.add_argument("--min-rg-ratio", type=float, default=0.45)
    parser.add_argument("--max-rg-ratio", type=float, default=1.85)
    parser.add_argument("--min-confidence-mean", type=float, default=35.0)
    parser.add_argument("--max-confidence-mean", type=float, default=88.0)
    parser.add_argument("--min-interchain-contacts", type=int, default=1)
    parser.add_argument("--min-interchain-distance", type=float, default=3.0)
    parser.add_argument("--max-interchain-clashes", type=int, default=0)
    parser.add_argument("--require-backbone-atoms", action="store_true")
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
    if payload["summary"]["accuracy_readiness_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
