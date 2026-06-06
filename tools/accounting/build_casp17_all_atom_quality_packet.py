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
DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_sidechain_scaffold_current"
DEFAULT_SIDECHAIN_SCAFFOLD_JSON = "runs/casp17_sidechain_scaffold_packet_current.json"
DEFAULT_OUT_JSON = "runs/casp17_all_atom_quality_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_all_atom_quality_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_all_atom_quality_packet_current.md"

SOFT_CLASH_DISTANCE_A = 1.10
SEVERE_CLASH_DISTANCE_A = 0.80
MAX_SOFT_CLASHSCORE_PER_1000 = 45.0
MIN_HEAVY_ATOM_COMPLETION = 0.98


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


def _record(line: str) -> str:
    return line[:6].strip().upper()


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


def _parse_first_model(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    atoms: list[dict[str, Any]] = []
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
        atoms.append(
            {
                "chain_id": chain,
                "resseq": resseq,
                "insertion_code": insertion,
                "atom_name": atom_name,
                "resname": line[17:20].strip().upper() if len(line) >= 20 else "UNK",
                "coord": (float(x), float(y), float(z)),
            }
        )
    return atoms


def _cell(coord: tuple[float, float, float], cell_size: float) -> tuple[int, int, int]:
    return tuple(math.floor(axis / cell_size) for axis in coord)


def _same_residue(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left["chain_id"] == right["chain_id"]
        and int(left["resseq"]) == int(right["resseq"])
        and left["insertion_code"] == right["insertion_code"]
    )


def _distance_sq(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return (left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2 + (left[2] - right[2]) ** 2


def _inter_residue_contact_counts(atoms: list[dict[str, Any]]) -> dict[str, Any]:
    grid: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    severe_sq = SEVERE_CLASH_DISTANCE_A * SEVERE_CLASH_DISTANCE_A
    soft_sq = SOFT_CLASH_DISTANCE_A * SOFT_CLASH_DISTANCE_A
    severe_count = 0
    soft_count = 0
    closest = None
    for atom_index, atom in enumerate(atoms):
        coord = atom["coord"]
        cell = _cell(coord, SOFT_CLASH_DISTANCE_A)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for other_index in grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), []):
                        other = atoms[other_index]
                        if _same_residue(atom, other):
                            continue
                        dist_sq = _distance_sq(coord, other["coord"])
                        if closest is None or dist_sq < closest:
                            closest = dist_sq
                        if dist_sq < soft_sq:
                            soft_count += 1
                        if dist_sq < severe_sq:
                            severe_count += 1
        grid[cell].append(atom_index)
    atom_count = len(atoms)
    return {
        "soft_clash_count": soft_count,
        "severe_clash_count": severe_count,
        "soft_clashscore_per_1000_atoms": round((soft_count * 1000.0 / atom_count) if atom_count else 0.0, 3),
        "closest_inter_residue_atom_distance_A": round(math.sqrt(closest), 3) if closest is not None else 0.0,
    }


def _completion_metrics(atoms: list[dict[str, Any]]) -> dict[str, Any]:
    by_residue: dict[tuple[str, int, str], dict[str, Any]] = {}
    for atom in atoms:
        key = (str(atom["chain_id"]), int(atom["resseq"]), str(atom["insertion_code"]))
        residue = by_residue.setdefault(key, {"resname": atom["resname"], "atoms": set()})
        residue["atoms"].add(str(atom["atom_name"]))
    expected_heavy_atom_count = 0
    observed_expected_heavy_atom_count = 0
    missing_sidechain_atom_count = 0
    unknown_residue_count = 0
    sidechain_residue_count = 0
    complete_sidechain_residue_count = 0
    standard_atom_sets = {resname: set(BACKBONE_ATOMS) | set(sidechain) for resname, sidechain in SIDECHAIN_ATOMS.items()}
    for residue in by_residue.values():
        resname = str(residue["resname"])
        atom_names = set(residue["atoms"])
        expected = standard_atom_sets.get(resname)
        if expected is None:
            unknown_residue_count += 1
            continue
        sidechain_expected = set(SIDECHAIN_ATOMS.get(resname, ()))
        expected_heavy_atom_count += len(expected)
        observed_expected_heavy_atom_count += len(expected & atom_names)
        missing_sidechain_atom_count += len(sidechain_expected - atom_names)
        if sidechain_expected:
            sidechain_residue_count += 1
            complete_sidechain_residue_count += int(sidechain_expected.issubset(atom_names))
    return {
        "residue_count": len(by_residue),
        "unknown_residue_count": unknown_residue_count,
        "expected_heavy_atom_count": expected_heavy_atom_count,
        "observed_expected_heavy_atom_count": observed_expected_heavy_atom_count,
        "heavy_atom_completion_fraction": round(
            observed_expected_heavy_atom_count / expected_heavy_atom_count if expected_heavy_atom_count else 0.0,
            6,
        ),
        "missing_sidechain_atom_count": missing_sidechain_atom_count,
        "sidechain_residue_count": sidechain_residue_count,
        "complete_sidechain_residue_count": complete_sidechain_residue_count,
        "complete_sidechain_residue_fraction": round(
            complete_sidechain_residue_count / sidechain_residue_count if sidechain_residue_count else 1.0,
            6,
        ),
    }


def _build_one(target_id: str, args: argparse.Namespace) -> dict[str, Any]:
    prediction = _resolve(args.prediction_dir) / f"{target_id}TS.pdb"
    blockers: list[str] = []
    if not prediction.exists():
        blockers.append("prediction_file_missing")
        return {
            "target_id": target_id,
            "all_atom_quality_status": "blocked",
            "prediction_file": _artifact(prediction),
            "atom_count": 0,
            "residue_count": 0,
            "heavy_atom_completion_fraction": 0.0,
            "complete_sidechain_residue_fraction": 0.0,
            "soft_clash_count": 0,
            "severe_clash_count": 0,
            "soft_clashscore_per_1000_atoms": 0.0,
            "closest_inter_residue_atom_distance_A": 0.0,
            "blockers": ",".join(blockers),
        }
    atoms = _parse_first_model(prediction)
    if not atoms:
        blockers.append("atom_records_missing")
    completion = _completion_metrics(atoms)
    clashes = _inter_residue_contact_counts(atoms)
    if completion["heavy_atom_completion_fraction"] < float(args.min_heavy_atom_completion):
        blockers.append("heavy_atom_completion_below_threshold")
    if clashes["severe_clash_count"]:
        blockers.append("severe_inter_residue_clashes")
    if clashes["soft_clashscore_per_1000_atoms"] > float(args.max_soft_clashscore_per_1000):
        blockers.append("soft_clashscore_above_threshold")
    if completion["unknown_residue_count"]:
        blockers.append("unknown_residue_types")
    status = "pass" if not blockers else "blocked"
    return {
        "target_id": target_id,
        "all_atom_quality_status": status,
        "prediction_file": _artifact(prediction),
        "atom_count": len(atoms),
        **completion,
        **clashes,
        "blockers": ",".join(sorted(set(blockers))),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = [_build_one(target_id, args) for target_id in _target_ids(args)]
    pass_count = sum(1 for row in rows if row["all_atom_quality_status"] == "pass")
    completion_values = [float(row.get("heavy_atom_completion_fraction", 0.0) or 0.0) for row in rows if int(row.get("expected_heavy_atom_count", 0) or 0) > 0]
    clashscores = [float(row.get("soft_clashscore_per_1000_atoms", 0.0) or 0.0) for row in rows if int(row.get("atom_count", 0) or 0) > 0]
    severe_clash_count = sum(int(row.get("severe_clash_count", 0) or 0) for row in rows)
    soft_clash_count = sum(int(row.get("soft_clash_count", 0) or 0) for row in rows)
    scaffold_summary = (_read_json(args.sidechain_scaffold_json).get("summary") or {})
    summary = {
        "packet_type": "casp17_all_atom_quality_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": len(rows) - pass_count,
        "all_atom_quality_status": "pass" if rows and pass_count == len(rows) else "blocked",
        "prediction_dir": _artifact(args.prediction_dir),
        "sidechain_scaffold_json": _artifact(args.sidechain_scaffold_json),
        "min_heavy_atom_completion_fraction": round(min(completion_values), 6) if completion_values else 0.0,
        "mean_heavy_atom_completion_fraction": round(sum(completion_values) / len(completion_values), 6) if completion_values else 0.0,
        "max_soft_clashscore_per_1000_atoms": round(max(clashscores), 3) if clashscores else 0.0,
        "mean_soft_clashscore_per_1000_atoms": round(sum(clashscores) / len(clashscores), 3) if clashscores else 0.0,
        "total_soft_clash_count": soft_clash_count,
        "total_severe_clash_count": severe_clash_count,
        "threshold_max_soft_clashscore_per_1000": float(args.max_soft_clashscore_per_1000),
        "threshold_min_heavy_atom_completion": float(args.min_heavy_atom_completion),
        "scaffold_pass_count": int(scaffold_summary.get("pass_count", 0) or 0),
        "scaffold_validation_pass_count": int(scaffold_summary.get("validation_pass_count", 0) or 0),
        "claim_boundary": "Internal MolProbity-style steric/completion QC for generated CASP17 coordinates only; not official MolProbity, not native accuracy evidence, not energy-minimized all-atom refinement, and not portal submission.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 All-Atom Quality Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- prediction_dir: `{summary['prediction_dir']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- status: `{summary['all_atom_quality_status']}`",
        f"- pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- min heavy-atom completion: `{summary['min_heavy_atom_completion_fraction']}`",
        f"- max soft clashscore per 1000 atoms: `{summary['max_soft_clashscore_per_1000_atoms']}`",
        f"- total severe clashes: `{summary['total_severe_clash_count']}`",
        "",
        "| target | status | atoms | residues | completion | complete sidechains | soft clashscore | severe clashes | closest contact A | blockers |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['all_atom_quality_status']}` | {row['atom_count']} | {row['residue_count']} | "
            f"{row['heavy_atom_completion_fraction']} | {row['complete_sidechain_residue_fraction']} | "
            f"{row['soft_clashscore_per_1000_atoms']} | {row['severe_clash_count']} | "
            f"{row['closest_inter_residue_atom_distance_A']} | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build internal MolProbity-style all-atom quality packet for CASP17 sidechain scaffold predictions.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--target-ids", default="")
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--sidechain-scaffold-json", default=DEFAULT_SIDECHAIN_SCAFFOLD_JSON)
    parser.add_argument("--min-heavy-atom-completion", type=float, default=MIN_HEAVY_ATOM_COMPLETION)
    parser.add_argument("--max-soft-clashscore-per-1000", type=float, default=MAX_SOFT_CLASHSCORE_PER_1000)
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
