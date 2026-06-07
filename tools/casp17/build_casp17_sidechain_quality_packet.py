#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.build_casp17_sidechain_scaffold_packet import BACKBONE_ATOMS, SIDECHAIN_ATOMS


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_steric_relaxed_current"
DEFAULT_OUT_JSON = "runs/casp17_sidechain_quality_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_sidechain_quality_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_sidechain_quality_packet_current.md"

ROTAMER_FRAME_ANGLES_DEG = (-140.0, -80.0, -20.0, 40.0, 100.0, 160.0)
MAX_ROTAMER_ANGLE_DEVIATION_DEG = 50.0
MIN_ROTAMER_PROXY_PASS_FRACTION = 0.90
MAX_CB_RADIAL_OUTLIER_FRACTION = 0.08
MIN_COMPLETE_SIDECHAIN_FRACTION = 0.96
CB_RADIAL_RANGE_A = (0.75, 2.85)


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


def _record(line: str) -> str:
    return line[:6].strip().upper()


def _current_open_targets(watchlist: dict[str, Any]) -> list[str]:
    rows = watchlist.get("rows")
    if not isinstance(rows, list):
        return []
    targets: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        lane = _text(row.get("lane_recommendation"))
        target_id = _text(row.get("target_id")).upper()
        if target_id and row.get("human_open") is True and lane in {"organic_ligand_protein_complexes", "difficult_protein_complexes"}:
            targets.append(target_id)
    return targets


def _target_ids(args: argparse.Namespace) -> list[str]:
    explicit = [item.strip().upper() for item in _text(args.target_ids).split(",") if item.strip()]
    if explicit:
        return explicit
    current = _current_open_targets(_read_json(args.target_watchlist_json))
    if current:
        return current
    root = _resolve(args.prediction_dir)
    return sorted(path.name[:-6].upper() for path in root.glob("*TS.pdb"))


def _float_or_none(value: str) -> float | None:
    try:
        parsed = float(value.strip())
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _pdb_float(line: str, start: int, end: int, fallback_index: int) -> float | None:
    if len(line) >= end:
        parsed = _float_or_none(line[start:end])
        if parsed is not None:
            return parsed
    fields = line.split()
    if len(fields) > fallback_index:
        return _float_or_none(fields[fallback_index])
    return None


def _atom_key(line: str) -> tuple[str, int, str, str]:
    chain = line[21].strip() or "_" if len(line) > 21 else "_"
    try:
        resseq = int(line[22:26])
    except ValueError:
        fields = line.split()
        resseq = int(fields[5]) if len(fields) > 5 and fields[5].lstrip("-").isdigit() else 0
    insertion = line[26].strip() or "_" if len(line) > 26 else "_"
    atom = line[12:16].strip() if len(line) >= 16 else ""
    return chain, resseq, insertion, atom


def _parse_first_model(path_like: str | Path) -> dict[tuple[str, int, str], dict[str, Any]]:
    path = _resolve(path_like)
    residues: dict[tuple[str, int, str], dict[str, Any]] = {}
    seen_model = False
    in_first_model = False
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.rstrip("\r\n")
        rec = _record(line)
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            in_first_model = True
            continue
        if rec == "END" and in_first_model:
            break
        if rec != "ATOM" or (seen_model and not in_first_model):
            continue
        x = _pdb_float(line, 30, 38, 6)
        y = _pdb_float(line, 38, 46, 7)
        z = _pdb_float(line, 46, 54, 8)
        if x is None or y is None or z is None:
            continue
        chain, resseq, insertion, atom_name = _atom_key(line)
        key = (chain, int(resseq), insertion)
        residue = residues.setdefault(
            key,
            {
                "chain_id": chain,
                "resseq": int(resseq),
                "insertion_code": insertion,
                "resname": line[17:20].strip().upper() if len(line) >= 20 else "UNK",
                "atoms": {},
            },
        )
        residue["atoms"][atom_name] = (float(x), float(y), float(z))
    return residues


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _norm(a: tuple[float, float, float]) -> float:
    return math.sqrt(max(0.0, _dot(a, a)))


def _unit(a: tuple[float, float, float], fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    value = _norm(a)
    if value < 1e-6:
        return fallback
    return a[0] / value, a[1] / value, a[2] / value


def _angle_delta(left: float, right: float) -> float:
    delta = abs((left - right + 180.0) % 360.0 - 180.0)
    return min(delta, 360.0 - delta)


def _frame(trace: list[dict[str, Any]], index: int) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    ca = trace[index]["atoms"]["CA"]
    if len(trace) == 1:
        tangent = (1.0, 0.0, 0.0)
    elif index == 0:
        tangent = _unit(_sub(trace[1]["atoms"]["CA"], ca), (1.0, 0.0, 0.0))
    elif index == len(trace) - 1:
        tangent = _unit(_sub(ca, trace[index - 1]["atoms"]["CA"]), (1.0, 0.0, 0.0))
    else:
        tangent = _unit(_sub(trace[index + 1]["atoms"]["CA"], trace[index - 1]["atoms"]["CA"]), (1.0, 0.0, 0.0))
    ref = (0.0, 0.0, 1.0)
    if _norm(_cross(tangent, ref)) < 1e-4:
        ref = (0.0, 1.0, 0.0)
    normal = _unit(_cross(ref, tangent), (0.0, 1.0, 0.0))
    binormal = _unit(_cross(tangent, normal), (0.0, 0.0, 1.0))
    return tangent, normal, binormal


def _build_one(target_id: str, args: argparse.Namespace) -> dict[str, Any]:
    prediction = _resolve(args.prediction_dir) / f"{target_id}TS.pdb"
    blockers: list[str] = []
    if not prediction.exists():
        return {
            "target_id": target_id,
            "sidechain_quality_status": "blocked",
            "prediction_file": _artifact(prediction),
            "residue_count": 0,
            "sidechain_residue_count": 0,
            "complete_sidechain_residue_fraction": 0.0,
            "rotamer_proxy_pass_fraction": 0.0,
            "cb_radial_outlier_fraction": 0.0,
            "mean_rotamer_angle_deviation_deg": 0.0,
            "max_rotamer_angle_deviation_deg": 0.0,
            "blockers": "prediction_file_missing",
        }
    residues = _parse_first_model(prediction)
    by_chain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for residue in residues.values():
        if "CA" in residue["atoms"]:
            by_chain[str(residue["chain_id"])].append(residue)
    for trace in by_chain.values():
        trace.sort(key=lambda row: (int(row["resseq"]), str(row["insertion_code"])))

    residue_count = len(residues)
    sidechain_residue_count = 0
    complete_sidechain_residue_count = 0
    rotamer_proxy_count = 0
    rotamer_proxy_pass_count = 0
    cb_radial_count = 0
    cb_radial_outlier_count = 0
    angle_deviations: list[float] = []
    unknown_residue_count = 0

    for trace in by_chain.values():
        for index, residue in enumerate(trace):
            resname = str(residue["resname"])
            sidechain = SIDECHAIN_ATOMS.get(resname)
            if sidechain is None:
                unknown_residue_count += 1
                continue
            if not sidechain:
                continue
            sidechain_residue_count += 1
            atom_names = set(residue["atoms"])
            if set(sidechain).issubset(atom_names):
                complete_sidechain_residue_count += 1
            if "CB" not in residue["atoms"] or "CA" not in residue["atoms"]:
                continue
            _tangent, normal, binormal = _frame(trace, index)
            cb_vector = _sub(residue["atoms"]["CB"], residue["atoms"]["CA"])
            radial_normal = _dot(cb_vector, normal)
            radial_binormal = _dot(cb_vector, binormal)
            radial = math.sqrt(radial_normal * radial_normal + radial_binormal * radial_binormal)
            cb_radial_count += 1
            if radial < CB_RADIAL_RANGE_A[0] or radial > CB_RADIAL_RANGE_A[1]:
                cb_radial_outlier_count += 1
            if radial < 1e-6:
                continue
            angle = math.degrees(math.atan2(radial_binormal, radial_normal))
            deviation = min(_angle_delta(angle, candidate) for candidate in ROTAMER_FRAME_ANGLES_DEG)
            angle_deviations.append(deviation)
            rotamer_proxy_count += 1
            if deviation <= float(args.max_rotamer_angle_deviation_deg):
                rotamer_proxy_pass_count += 1

    complete_fraction = complete_sidechain_residue_count / sidechain_residue_count if sidechain_residue_count else 1.0
    rotamer_fraction = rotamer_proxy_pass_count / rotamer_proxy_count if rotamer_proxy_count else 1.0
    cb_outlier_fraction = cb_radial_outlier_count / cb_radial_count if cb_radial_count else 0.0
    if unknown_residue_count:
        blockers.append("unknown_residue_types")
    if complete_fraction < float(args.min_complete_sidechain_fraction):
        blockers.append("sidechain_completion_below_threshold")
    if rotamer_fraction < float(args.min_rotamer_proxy_pass_fraction):
        blockers.append("rotamer_proxy_pass_fraction_below_threshold")
    if cb_outlier_fraction > float(args.max_cb_radial_outlier_fraction):
        blockers.append("cb_radial_outlier_fraction_above_threshold")
    status = "pass" if not blockers else "blocked"
    return {
        "target_id": target_id,
        "sidechain_quality_status": status,
        "prediction_file": _artifact(prediction),
        "residue_count": residue_count,
        "sidechain_residue_count": sidechain_residue_count,
        "complete_sidechain_residue_count": complete_sidechain_residue_count,
        "complete_sidechain_residue_fraction": round(complete_fraction, 6),
        "rotamer_proxy_count": rotamer_proxy_count,
        "rotamer_proxy_pass_count": rotamer_proxy_pass_count,
        "rotamer_proxy_pass_fraction": round(rotamer_fraction, 6),
        "cb_radial_count": cb_radial_count,
        "cb_radial_outlier_count": cb_radial_outlier_count,
        "cb_radial_outlier_fraction": round(cb_outlier_fraction, 6),
        "mean_rotamer_angle_deviation_deg": round(sum(angle_deviations) / len(angle_deviations), 3) if angle_deviations else 0.0,
        "max_rotamer_angle_deviation_deg": round(max(angle_deviations), 3) if angle_deviations else 0.0,
        "unknown_residue_count": unknown_residue_count,
        "blockers": ",".join(sorted(set(blockers))),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = [_build_one(target_id, args) for target_id in _target_ids(args)]
    pass_count = sum(1 for row in rows if row["sidechain_quality_status"] == "pass")
    complete_fractions = [float(row.get("complete_sidechain_residue_fraction", 0.0) or 0.0) for row in rows]
    rotamer_fractions = [float(row.get("rotamer_proxy_pass_fraction", 0.0) or 0.0) for row in rows]
    cb_outlier_fractions = [float(row.get("cb_radial_outlier_fraction", 0.0) or 0.0) for row in rows]
    angle_means = [float(row.get("mean_rotamer_angle_deviation_deg", 0.0) or 0.0) for row in rows]
    summary = {
        "packet_type": "casp17_sidechain_quality_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": len(rows) - pass_count,
        "sidechain_quality_status": "pass" if rows and pass_count == len(rows) else "blocked",
        "prediction_dir": _artifact(args.prediction_dir),
        "min_complete_sidechain_residue_fraction": round(min(complete_fractions), 6) if complete_fractions else 0.0,
        "mean_complete_sidechain_residue_fraction": round(sum(complete_fractions) / len(complete_fractions), 6) if complete_fractions else 0.0,
        "min_rotamer_proxy_pass_fraction": round(min(rotamer_fractions), 6) if rotamer_fractions else 0.0,
        "mean_rotamer_proxy_pass_fraction": round(sum(rotamer_fractions) / len(rotamer_fractions), 6) if rotamer_fractions else 0.0,
        "max_cb_radial_outlier_fraction": round(max(cb_outlier_fractions), 6) if cb_outlier_fractions else 0.0,
        "mean_rotamer_angle_deviation_deg": round(sum(angle_means) / len(angle_means), 3) if angle_means else 0.0,
        "threshold_min_complete_sidechain_fraction": float(args.min_complete_sidechain_fraction),
        "threshold_min_rotamer_proxy_pass_fraction": float(args.min_rotamer_proxy_pass_fraction),
        "threshold_max_cb_radial_outlier_fraction": float(args.max_cb_radial_outlier_fraction),
        "threshold_max_rotamer_angle_deviation_deg": float(args.max_rotamer_angle_deviation_deg),
        "claim_boundary": "Internal sidechain completeness and rotamer-frame proxy QC only; not a statistical rotamer-library validation, not official MolProbity, and not native sidechain accuracy evidence.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Sidechain Quality Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- prediction_dir: `{summary['prediction_dir']}`",
        f"- status: `{summary['sidechain_quality_status']}`",
        f"- pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- min complete sidechain fraction: `{summary['min_complete_sidechain_residue_fraction']}`",
        f"- min rotamer proxy pass fraction: `{summary['min_rotamer_proxy_pass_fraction']}`",
        f"- max CB radial outlier fraction: `{summary['max_cb_radial_outlier_fraction']}`",
        "",
        "| target | status | residues | sidechain residues | complete fraction | rotamer proxy pass | CB radial outliers | mean angle dev | max angle dev | blockers |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['sidechain_quality_status']}` | {row['residue_count']} | "
            f"{row['sidechain_residue_count']} | {row['complete_sidechain_residue_fraction']} | "
            f"{row['rotamer_proxy_pass_fraction']} | {row['cb_radial_outlier_fraction']} | "
            f"{row['mean_rotamer_angle_deviation_deg']} | {row['max_rotamer_angle_deviation_deg']} | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build internal CASP17 sidechain completeness and rotamer-frame proxy QC packet.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--target-ids", default="")
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--min-complete-sidechain-fraction", type=float, default=MIN_COMPLETE_SIDECHAIN_FRACTION)
    parser.add_argument("--min-rotamer-proxy-pass-fraction", type=float, default=MIN_ROTAMER_PROXY_PASS_FRACTION)
    parser.add_argument("--max-cb-radial-outlier-fraction", type=float, default=MAX_CB_RADIAL_OUTLIER_FRACTION)
    parser.add_argument("--max-rotamer-angle-deviation-deg", type=float, default=MAX_ROTAMER_ANGLE_DEVIATION_DEG)
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
    if payload["summary"]["blocked_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
