#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_model_selected_shape_guarded_coordinate_normalized_current"
DEFAULT_OUT_JSON = "runs/casp17_structure_shape_sanity_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_structure_shape_sanity_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_structure_shape_sanity_packet_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _record(line: str) -> str:
    return line[:6].strip().upper()


def _distance(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return math.sqrt((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2 + (left[2] - right[2]) ** 2)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _prediction_paths(prediction_dir: Path, target_ids: set[str]) -> list[Path]:
    if not prediction_dir.exists():
        return []
    paths = sorted(prediction_dir.glob("*TS.pdb"))
    if not target_ids:
        return paths
    return [path for path in paths if path.stem.replace("TS", "").upper() in target_ids]


def _parse_ca_trace(path: Path) -> dict[str, Any]:
    target_id = path.stem.replace("TS", "").upper()
    ca_coords: list[tuple[float, float, float]] = []
    by_chain: dict[str, list[tuple[int, tuple[float, float, float]]]] = {}
    atom_count = 0
    seen_model = False
    in_first_model = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        rec = _record(line)
        if rec == "TARGET":
            parts = line.split()
            if len(parts) >= 2:
                target_id = parts[1].upper()
            continue
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            in_first_model = True
            continue
        if rec in {"ENDMDL", "END"} and in_first_model:
            break
        if rec != "ATOM":
            continue
        if seen_model and not in_first_model:
            continue
        atom_count += 1
        atom_name = line[12:16].strip()
        if atom_name != "CA":
            continue
        try:
            chain_id = line[21].strip() or "_"
            resseq = int(line[22:26])
            coord = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
        except (IndexError, ValueError):
            continue
        ca_coords.append(coord)
        by_chain.setdefault(chain_id, []).append((resseq, coord))

    continuity_total = 0
    continuity_pass = 0
    max_ca_gap = 0.0
    max_chain_linearity = 0.0
    max_chain_end_to_end = 0.0
    total_contour_length = 0.0
    for values in by_chain.values():
        ordered = [coord for _resseq, coord in sorted(values)]
        if len(ordered) < 2:
            continue
        contour_length = 3.8 * float(len(ordered) - 1)
        total_contour_length += contour_length
        end_to_end = _distance(ordered[0], ordered[-1])
        max_chain_end_to_end = max(max_chain_end_to_end, end_to_end)
        if contour_length > 0:
            max_chain_linearity = max(max_chain_linearity, end_to_end / contour_length)
        for left, right in zip(ordered, ordered[1:]):
            gap = _distance(left, right)
            continuity_total += 1
            continuity_pass += int(2.0 <= gap <= 8.0)
            max_ca_gap = max(max_ca_gap, gap)

    ca_count = len(ca_coords)
    if ca_coords:
        center = tuple(sum(coord[index] for coord in ca_coords) / ca_count for index in range(3))
        radius_gyration = math.sqrt(sum(_distance(coord, center) ** 2 for coord in ca_coords) / ca_count)
        xs = [coord[0] for coord in ca_coords]
        ys = [coord[1] for coord in ca_coords]
        zs = [coord[2] for coord in ca_coords]
        max_axis_span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
        bbox_diagonal = math.sqrt((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2 + (max(zs) - min(zs)) ** 2)
    else:
        radius_gyration = 0.0
        max_axis_span = 0.0
        bbox_diagonal = 0.0
    return {
        "target_id": target_id,
        "prediction_file": _artifact(path),
        "atom_count": atom_count,
        "ca_count": ca_count,
        "chain_count": len(by_chain),
        "ca_radius_gyration_A": round(radius_gyration, 6),
        "ca_radius_gyration_per_residue": round(radius_gyration / max(1.0, float(ca_count)), 6),
        "ca_max_axis_span_A": round(max_axis_span, 6),
        "ca_max_axis_span_per_residue": round(max_axis_span / max(1.0, float(ca_count)), 6),
        "ca_bounding_box_diagonal_A": round(bbox_diagonal, 6),
        "ca_bounding_box_diagonal_per_residue": round(bbox_diagonal / max(1.0, float(ca_count)), 6),
        "max_chain_linearity": round(max_chain_linearity, 6),
        "max_chain_end_to_end_A": round(max_chain_end_to_end, 6),
        "total_chain_contour_length_A": round(total_contour_length, 6),
        "ca_continuity_fraction": round(continuity_pass / continuity_total if continuity_total else 0.0, 6),
        "max_ca_gap_A": round(max_ca_gap, 6),
    }


def _shape_penalty(row: dict[str, Any], args: argparse.Namespace) -> float:
    span_ratio = _float(row.get("ca_max_axis_span_per_residue")) / max(1e-6, float(args.max_span_per_residue))
    rg_ratio = _float(row.get("ca_radius_gyration_per_residue")) / max(1e-6, float(args.max_radius_gyration_per_residue))
    linearity_ratio = _float(row.get("max_chain_linearity")) / max(1e-6, float(args.max_chain_linearity))
    over_span = max(0.0, span_ratio - 1.0)
    over_rg = max(0.0, rg_ratio - 1.0)
    over_linearity = max(0.0, linearity_ratio - 1.0)
    return min(0.65, 0.30 * over_span + 0.20 * over_rg + 0.15 * over_linearity)


def _evaluate_row(row: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    if int(row.get("ca_count", 0)) <= 0:
        blockers.append("no_ca_atoms")
    if _float(row.get("ca_continuity_fraction")) < float(args.min_ca_continuity_fraction):
        blockers.append("ca_continuity_below_threshold")
    if _float(row.get("max_ca_gap_A")) > float(args.max_ca_gap):
        blockers.append("max_ca_gap_above_threshold")
    if _float(row.get("ca_max_axis_span_per_residue")) > float(args.max_span_per_residue):
        blockers.append("ca_span_per_residue_above_threshold")
    if _float(row.get("ca_radius_gyration_per_residue")) > float(args.max_radius_gyration_per_residue):
        blockers.append("ca_radius_gyration_per_residue_above_threshold")
    if _float(row.get("max_chain_linearity")) > float(args.max_chain_linearity):
        blockers.append("max_chain_linearity_above_threshold")
    penalty = _shape_penalty(row, args)
    if penalty > float(args.max_shape_penalty):
        blockers.append("shape_penalty_above_threshold")
    row["shape_penalty"] = round(penalty, 6)
    row["shape_plausibility_score"] = round(max(0.0, 1.0 - penalty), 6)
    row["shape_sanity_status"] = "pass" if not blockers else "blocked"
    row["blockers"] = ",".join(dict.fromkeys(blockers))
    return row


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    prediction_dir = _resolve(args.prediction_dir)
    target_ids = {item.strip().upper() for item in str(args.target_ids or "").split(",") if item.strip()}
    rows = [_evaluate_row(_parse_ca_trace(path), args) for path in _prediction_paths(prediction_dir, target_ids)]
    rows = sorted(rows, key=lambda row: str(row.get("target_id", "")))
    pass_count = sum(1 for row in rows if row["shape_sanity_status"] == "pass")
    blocked_rows = [row for row in rows if row["shape_sanity_status"] != "pass"]
    max_span_per_residue = max((_float(row.get("ca_max_axis_span_per_residue")) for row in rows), default=0.0)
    max_rg_per_residue = max((_float(row.get("ca_radius_gyration_per_residue")) for row in rows), default=0.0)
    max_linearity = max((_float(row.get("max_chain_linearity")) for row in rows), default=0.0)
    max_penalty = max((_float(row.get("shape_penalty")) for row in rows), default=0.0)
    summary = {
        "packet_type": "casp17_structure_shape_sanity_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "shape_sanity_status": "pass" if rows and pass_count == len(rows) else "blocked",
        "prediction_dir": _artifact(args.prediction_dir),
        "target_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": len(blocked_rows),
        "max_observed_span_per_residue": round(max_span_per_residue, 6),
        "max_observed_radius_gyration_per_residue": round(max_rg_per_residue, 6),
        "max_observed_chain_linearity": round(max_linearity, 6),
        "max_observed_shape_penalty": round(max_penalty, 6),
        "max_span_per_residue": float(args.max_span_per_residue),
        "max_radius_gyration_per_residue": float(args.max_radius_gyration_per_residue),
        "max_chain_linearity": float(args.max_chain_linearity),
        "max_shape_penalty": float(args.max_shape_penalty),
        "min_ca_continuity_fraction": float(args.min_ca_continuity_fraction),
        "max_ca_gap_A": float(args.max_ca_gap),
        "blocked_targets": ",".join(row["target_id"] for row in blocked_rows),
        "claim_boundary": (
            "Local CA-shape sanity gate only. It detects overextended or line-like generated coordinates before rendering/submission; "
            "it does not prove native accuracy, experimental correctness, or CASP assessment quality."
        ),
    }
    return {"summary": summary, "rows": rows}


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
        fieldnames = ["target_id", "shape_sanity_status", "blockers"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Structure Shape Sanity Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- shape_sanity_status: `{summary['shape_sanity_status']}`",
        f"- pass/target: `{summary['pass_count']}/{summary['target_count']}`",
        f"- blocked_targets: `{summary['blocked_targets'] or '-'}`",
        f"- max observed span/Rg/linearity/penalty: `{summary['max_observed_span_per_residue']}` / `{summary['max_observed_radius_gyration_per_residue']}` / `{summary['max_observed_chain_linearity']}` / `{summary['max_observed_shape_penalty']}`",
        "",
        "## Rows",
        "",
        "| target | status | CA | chains | span/res | Rg/res | linearity | max gap | penalty | blockers |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['shape_sanity_status']}` | {row['ca_count']} | {row['chain_count']} | "
            f"{row['ca_max_axis_span_per_residue']} | {row['ca_radius_gyration_per_residue']} | "
            f"{row['max_chain_linearity']} | {row['max_ca_gap_A']} | {row['shape_penalty']} | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA-shape sanity packet for CASP17 generated TS predictions.")
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--target-ids", default="")
    parser.add_argument("--max-span-per-residue", type=float, default=0.35)
    parser.add_argument("--max-radius-gyration-per-residue", type=float, default=0.18)
    parser.add_argument("--max-chain-linearity", type=float, default=0.24)
    parser.add_argument("--max-shape-penalty", type=float, default=0.05)
    parser.add_argument("--min-ca-continuity-fraction", type=float, default=0.98)
    parser.add_argument("--max-ca-gap", type=float, default=8.0)
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
    if payload["summary"]["shape_sanity_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
