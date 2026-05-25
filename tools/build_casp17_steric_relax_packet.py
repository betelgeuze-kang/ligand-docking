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

from tools import validate_casp17_confidence_calibration as confidence_validator
from tools import validate_casp17_geometry_sanity as geometry_validator
from tools import validate_casp17_ts_prediction as format_validator
from tools.build_casp17_all_atom_quality_packet import (
    MIN_HEAVY_ATOM_COMPLETION,
    _completion_metrics,
    _inter_residue_contact_counts,
    _parse_first_model,
)
from tools.build_casp17_sidechain_scaffold_packet import BACKBONE_ATOMS


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_SOURCE_DIR = "runs/casp17_predictions_sidechain_repacked_current"
DEFAULT_SEQUENCE_DIR = "runs/casp17_sequences_current"
DEFAULT_OUT_DIR = "runs/casp17_predictions_steric_relaxed_current"
DEFAULT_OUT_JSON = "runs/casp17_steric_relax_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_steric_relax_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_steric_relax_packet_current.md"

SOFT_DISTANCE_A = 1.10
SEVERE_DISTANCE_A = 0.80
TARGET_DISTANCE_A = 1.16
SPATIAL_CELL_SIZE_A = 1.20
DEFAULT_ITERATIONS = 12
MAX_STEP_A = 0.18
MAX_CUMULATIVE_SHIFT_A = 0.90


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
    root = _resolve(args.source_dir)
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


def _parse_source(path_like: str | Path) -> tuple[list[str], list[dict[str, Any]]]:
    path = _resolve(path_like)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    atoms: list[dict[str, Any]] = []
    seen_model = False
    in_first_model = False
    for line_index, line in enumerate(lines):
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
                "line_index": line_index,
                "chain_id": chain,
                "resseq": int(resseq),
                "insertion_code": insertion,
                "atom_name": atom_name,
                "resname": line[17:20].strip().upper() if len(line) >= 20 else "UNK",
                "coord": (float(x), float(y), float(z)),
            }
        )
    return lines, atoms


def _add(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:
    return left[0] + right[0], left[1] + right[1], left[2] + right[2]


def _sub(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:
    return left[0] - right[0], left[1] - right[1], left[2] - right[2]


def _scale(vec: tuple[float, float, float], scalar: float) -> tuple[float, float, float]:
    return vec[0] * scalar, vec[1] * scalar, vec[2] * scalar


def _norm(vec: tuple[float, float, float]) -> float:
    return math.sqrt(max(0.0, vec[0] * vec[0] + vec[1] * vec[1] + vec[2] * vec[2]))


def _unit(vec: tuple[float, float, float], fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    value = _norm(vec)
    if value < 1e-8:
        return fallback
    return vec[0] / value, vec[1] / value, vec[2] / value


def _distance_sq(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return (left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2 + (left[2] - right[2]) ** 2


def _same_residue(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left["chain_id"] == right["chain_id"]
        and int(left["resseq"]) == int(right["resseq"])
        and str(left["insertion_code"]) == str(right["insertion_code"])
    )


def _cell(coord: tuple[float, float, float]) -> tuple[int, int, int]:
    return tuple(math.floor(axis / SPATIAL_CELL_SIZE_A) for axis in coord)


def _movable(atom: dict[str, Any]) -> bool:
    return str(atom.get("atom_name") or "") not in BACKBONE_ATOMS


def _fallback_direction(left: dict[str, Any], right: dict[str, Any]) -> tuple[float, float, float]:
    seed = (
        (int(left["resseq"]) * 17 + int(right["resseq"]) * 31) % 11 - 5,
        (ord(str(left["chain_id"] or "_")[0]) + ord(str(right["chain_id"] or "_")[0])) % 13 - 6,
        (int(left["line_index"]) - int(right["line_index"])) % 17 - 8,
    )
    return _unit((float(seed[0]), float(seed[1]), float(seed[2])), (1.0, 0.0, 0.0))


def _contact_pairs(
    atoms: list[dict[str, Any]],
    coords: dict[int, tuple[float, float, float]],
    *,
    cutoff: float,
) -> list[tuple[int, int, float]]:
    grid: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    cutoff_sq = cutoff * cutoff
    pairs: list[tuple[int, int, float]] = []
    for atom_index, atom in enumerate(atoms):
        coord = coords[int(atom["line_index"])]
        cell = _cell(coord)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for other_index in grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), []):
                        other = atoms[other_index]
                        if _same_residue(atom, other):
                            continue
                        dist_sq = _distance_sq(coord, coords[int(other["line_index"])])
                        if dist_sq < cutoff_sq:
                            pairs.append((atom_index, other_index, math.sqrt(max(dist_sq, 0.0))))
        grid[cell].append(atom_index)
    return pairs


def _quality_metrics(path_like: str | Path) -> dict[str, Any]:
    atoms = _parse_first_model(path_like)
    completion = _completion_metrics(atoms)
    contacts = _inter_residue_contact_counts(atoms)
    return {"atom_count": len(atoms), **completion, **contacts}


def _relax_atoms(
    atoms: list[dict[str, Any]],
    *,
    iterations: int,
    max_step: float,
    max_cumulative_shift: float,
) -> tuple[dict[int, tuple[float, float, float]], dict[str, Any]]:
    original = {int(atom["line_index"]): atom["coord"] for atom in atoms}
    coords = dict(original)
    total_soft_pairs_seen = 0
    moved_atom_ids: set[int] = set()
    applied_iterations = 0

    for iteration in range(max(0, int(iterations))):
        pairs = _contact_pairs(atoms, coords, cutoff=SOFT_DISTANCE_A)
        if not pairs:
            break
        shifts: dict[int, tuple[float, float, float]] = defaultdict(lambda: (0.0, 0.0, 0.0))
        for left_index, right_index, distance in pairs:
            left = atoms[left_index]
            right = atoms[right_index]
            left_movable = _movable(left)
            right_movable = _movable(right)
            if not left_movable and not right_movable:
                continue
            left_id = int(left["line_index"])
            right_id = int(right["line_index"])
            direction = _sub(coords[left_id], coords[right_id])
            direction = _unit(direction, _fallback_direction(left, right))
            deficit = max(0.0, TARGET_DISTANCE_A - distance)
            magnitude = min(float(max_step), deficit * (0.42 if left_movable and right_movable else 0.68))
            if magnitude <= 1e-8:
                continue
            if left_movable and right_movable:
                left_shift = _scale(direction, magnitude * 0.5)
                right_shift = _scale(direction, -magnitude * 0.5)
                shifts[left_id] = _add(shifts[left_id], left_shift)
                shifts[right_id] = _add(shifts[right_id], right_shift)
            elif left_movable:
                shifts[left_id] = _add(shifts[left_id], _scale(direction, magnitude))
            else:
                shifts[right_id] = _add(shifts[right_id], _scale(direction, -magnitude))
        if not shifts:
            break
        for line_index, shift in shifts.items():
            shift_norm = _norm(shift)
            if shift_norm > max_step:
                shift = _scale(shift, max_step / shift_norm)
            candidate = _add(coords[line_index], shift)
            from_original = _sub(candidate, original[line_index])
            cumulative = _norm(from_original)
            if cumulative > max_cumulative_shift:
                candidate = _add(original[line_index], _scale(from_original, max_cumulative_shift / cumulative))
            coords[line_index] = candidate
            moved_atom_ids.add(line_index)
        total_soft_pairs_seen += len(pairs)
        applied_iterations = iteration + 1

    updates = {line_index: coord for line_index, coord in coords.items() if _distance_sq(coord, original[line_index]) > 1e-8}
    final_pairs = _contact_pairs(atoms, coords, cutoff=SOFT_DISTANCE_A)
    return updates, {
        "relax_iteration_count": applied_iterations,
        "moved_atom_count": len(moved_atom_ids),
        "coordinate_update_count": len(updates),
        "soft_pair_observation_count": total_soft_pairs_seen,
        "remaining_soft_pair_count_after_relax": len(final_pairs),
    }


def _update_atom_line(line: str, coord: tuple[float, float, float]) -> str:
    padded = line.rstrip("\n")
    if len(padded) < 54:
        padded = padded.ljust(54)
    x, y, z = coord
    return f"{padded[:30]}{x:8.3f}{y:8.3f}{z:8.3f}{padded[54:]}"


def _insert_remark(lines: list[str]) -> list[str]:
    remark = "REMARK CASP17 STERIC_RELAX local internal sidechain steric relaxation; backbone fixed; not native-calibrated all-atom refinement"
    if any(line.startswith("REMARK CASP17 STERIC_RELAX") for line in lines):
        return lines
    out = lines[:]
    insert_index = next((index + 1 for index, line in enumerate(out) if _record(line) in {"SCORE", "QSCORE", "STOICH"}), None)
    if insert_index is None:
        insert_index = next((index + 1 for index, line in enumerate(out) if _record(line) == "MODEL"), 0)
    out.insert(insert_index, remark)
    return out


def _write_relaxed_source(source: Path, out_pdb: Path, updates: dict[int, tuple[float, float, float]]) -> None:
    lines, _atoms = _parse_source(source)
    for line_index, coord in updates.items():
        if 0 <= line_index < len(lines) and _record(lines[line_index]) == "ATOM":
            lines[line_index] = _update_atom_line(lines[line_index], coord)
    lines = _insert_remark(lines)
    out_pdb.parent.mkdir(parents=True, exist_ok=True)
    out_pdb.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_one(target_id: str, args: argparse.Namespace) -> dict[str, Any]:
    source = _resolve(args.source_dir) / f"{target_id}TS.pdb"
    sequence_path = _resolve(args.sequence_dir) / f"{target_id}.fasta"
    out_pdb = _resolve(args.out_dir) / f"{target_id}TS.pdb"
    blockers: list[str] = []
    if not source.exists():
        blockers.append("source_prediction_missing")
    if not sequence_path.exists():
        blockers.append("sequence_file_missing")
    metrics: dict[str, Any] = {
        "atom_count": 0,
        "relax_iteration_count": 0,
        "moved_atom_count": 0,
        "coordinate_update_count": 0,
        "soft_pair_observation_count": 0,
        "soft_clash_count_before": 0,
        "soft_clash_count_after": 0,
        "soft_clash_delta": 0,
        "soft_clashscore_before": 0.0,
        "soft_clashscore_after": 0.0,
        "severe_clash_count_before": 0,
        "severe_clash_count_after": 0,
        "heavy_atom_completion_fraction_after": 0.0,
        "revert_guard_triggered": False,
    }
    validation = {
        "format_check_status": "not_run",
        "geometry_sanity_status": "not_run",
        "confidence_calibration_status": "not_run",
    }
    if not blockers:
        _lines, atoms = _parse_source(source)
        if not atoms:
            blockers.append("atom_records_missing")
        else:
            before = _quality_metrics(source)
            updates, relax_metrics = _relax_atoms(
                atoms,
                iterations=int(args.iterations),
                max_step=float(args.max_step),
                max_cumulative_shift=float(args.max_cumulative_shift),
            )
            _write_relaxed_source(source, out_pdb, updates)
            after = _quality_metrics(out_pdb)
            if (
                int(after["soft_clash_count"]) > int(before["soft_clash_count"])
                or int(after["severe_clash_count"]) > int(before["severe_clash_count"])
            ):
                _write_relaxed_source(source, out_pdb, {})
                after = before
                updates = {}
                relax_metrics = {**relax_metrics, "reverted_not_worse_guard": True}
            validation_format = format_validator.validate_prediction(
                target_id=target_id,
                prediction_file=out_pdb,
                sequence_path=sequence_path,
            )
            validation_geometry = geometry_validator.validate_geometry(target_id=target_id, prediction_file=out_pdb)
            validation_confidence = confidence_validator.validate_confidence(
                target_id=target_id,
                prediction_file=out_pdb,
                sequence_path=sequence_path,
            )
            validation = {
                "format_check_status": validation_format["summary"]["format_check_status"],
                "geometry_sanity_status": validation_geometry["summary"]["geometry_sanity_status"],
                "confidence_calibration_status": validation_confidence["summary"]["confidence_calibration_status"],
            }
            if validation["format_check_status"] != "pass":
                blockers.append("format_check_failed")
            if validation["geometry_sanity_status"] != "pass":
                blockers.append("geometry_sanity_failed")
            if validation["confidence_calibration_status"] != "pass":
                blockers.append("confidence_calibration_failed")
            if float(after["heavy_atom_completion_fraction"]) < MIN_HEAVY_ATOM_COMPLETION:
                blockers.append("heavy_atom_completion_below_threshold")
            if int(after["severe_clash_count"]):
                blockers.append("severe_clash_after_relax")
            if int(after["soft_clash_count"]) > int(before["soft_clash_count"]):
                blockers.append("soft_clash_regression")
            metrics = {
                "atom_count": int(after["atom_count"]),
                **relax_metrics,
                "coordinate_update_count": len(updates),
                "soft_clash_count_before": int(before["soft_clash_count"]),
                "soft_clash_count_after": int(after["soft_clash_count"]),
                "soft_clash_delta": int(before["soft_clash_count"]) - int(after["soft_clash_count"]),
                "soft_clashscore_before": float(before["soft_clashscore_per_1000_atoms"]),
                "soft_clashscore_after": float(after["soft_clashscore_per_1000_atoms"]),
                "severe_clash_count_before": int(before["severe_clash_count"]),
                "severe_clash_count_after": int(after["severe_clash_count"]),
                "heavy_atom_completion_fraction_after": float(after["heavy_atom_completion_fraction"]),
                "revert_guard_triggered": bool(relax_metrics.get("reverted_not_worse_guard")),
            }
    status = "pass" if not blockers else "blocked"
    return {
        "target_id": target_id,
        "steric_relax_status": status,
        "source_pdb": _artifact(source),
        "out_pdb": _artifact(out_pdb),
        **metrics,
        **validation,
        "blockers": ",".join(sorted(set(blockers))),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = [_build_one(target_id, args) for target_id in _target_ids(args)]
    pass_count = sum(1 for row in rows if row["steric_relax_status"] == "pass")
    total_before = sum(int(row.get("soft_clash_count_before", 0) or 0) for row in rows)
    total_after = sum(int(row.get("soft_clash_count_after", 0) or 0) for row in rows)
    summary = {
        "packet_type": "casp17_steric_relax_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": len(rows) - pass_count,
        "steric_relax_status": "pass" if rows and pass_count == len(rows) else "blocked",
        "source_dir": _artifact(args.source_dir),
        "out_dir": _artifact(args.out_dir),
        "iterations": int(args.iterations),
        "max_step_A": float(args.max_step),
        "max_cumulative_shift_A": float(args.max_cumulative_shift),
        "total_soft_clash_count_before": total_before,
        "total_soft_clash_count_after": total_after,
        "total_soft_clash_delta": total_before - total_after,
        "total_coordinate_update_count": sum(int(row.get("coordinate_update_count", 0) or 0) for row in rows),
        "total_moved_atom_count": sum(int(row.get("moved_atom_count", 0) or 0) for row in rows),
        "revert_guard_count": sum(int(bool(row.get("revert_guard_triggered"))) for row in rows),
        "claim_boundary": "Local internal sidechain-only steric relaxation over generated CASP17 coordinates; backbone fixed; not a statistical rotamer-library packer, not energy-minimized all-atom refinement, not native accuracy evidence, and not portal submission.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Steric Relax Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- source_dir: `{summary['source_dir']}`",
        f"- out_dir: `{summary['out_dir']}`",
        f"- status: `{summary['steric_relax_status']}`",
        f"- pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- soft clashes before/after/delta: `{summary['total_soft_clash_count_before']}/{summary['total_soft_clash_count_after']}/{summary['total_soft_clash_delta']}`",
        f"- moved atoms / coordinate updates: `{summary['total_moved_atom_count']}/{summary['total_coordinate_update_count']}`",
        f"- revert_guard_count: `{summary['revert_guard_count']}`",
        "",
        "| target | status | atoms | iterations | moved atoms | coord updates | guard | soft before | soft after | delta | completion | format | geometry | confidence | blockers |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['steric_relax_status']}` | {row['atom_count']} | "
            f"{row['relax_iteration_count']} | {row['moved_atom_count']} | {row['coordinate_update_count']} | "
            f"`{row.get('revert_guard_triggered', False)}` | "
            f"{row['soft_clash_count_before']} | {row['soft_clash_count_after']} | {row['soft_clash_delta']} | "
            f"{row['heavy_atom_completion_fraction_after']} | `{row['format_check_status']}` | "
            f"`{row['geometry_sanity_status']}` | `{row['confidence_calibration_status']}` | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local internal sidechain-only steric relaxation TS copies for CASP17 predictions.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--target-ids", default="")
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--sequence-dir", default=DEFAULT_SEQUENCE_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--max-step", type=float, default=MAX_STEP_A)
    parser.add_argument("--max-cumulative-shift", type=float, default=MAX_CUMULATIVE_SHIFT_A)
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
