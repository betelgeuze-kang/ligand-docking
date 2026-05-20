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


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OUT_JSON = "runs/casp17_geometry_sanity_current.json"
DEFAULT_OUT_CSV = "runs/casp17_geometry_sanity_current.csv"
DEFAULT_OUT_MD = "runs/casp17_geometry_sanity_current.md"

CLASH_DISTANCE_A = 0.80
CA_TOO_CLOSE_A = 2.00
CA_TOO_FAR_A = 8.00
COORD_ABS_MAX_A = 10000.0


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


def _float_slice(line: str, start: int, end: int, fallback_index: int) -> float | None:
    value = None
    if len(line) >= end:
        value = _float_or_none(line[start:end])
    if value is not None:
        return value
    fields = line.split()
    if len(fields) > fallback_index:
        return _float_or_none(fields[fallback_index])
    return None


def _float_or_none(value: str) -> float | None:
    try:
        parsed = float(value.strip())
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _int_or_none(value: str) -> int | None:
    try:
        return int(value.strip())
    except ValueError:
        return None


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _warning(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "warning", "reason": reason}


def _parse_atom(line: str) -> dict[str, Any] | None:
    if _record(line) != "ATOM":
        return None
    x = _float_slice(line, 30, 38, 6)
    y = _float_slice(line, 38, 46, 7)
    z = _float_slice(line, 46, 54, 8)
    if x is None or y is None or z is None:
        return {
            "valid_coord": False,
            "raw": line,
            "atom_name": "",
            "chain_id": "",
            "residue_number": None,
            "insertion_code": "",
            "coord": (math.nan, math.nan, math.nan),
        }
    atom_name = line[12:16].strip() if len(line) >= 16 else (line.split()[2] if len(line.split()) > 2 else "")
    chain_id = line[21].strip() if len(line) >= 22 else (line.split()[4] if len(line.split()) > 4 else "")
    residue_text = line[22:26].strip() if len(line) >= 26 else (line.split()[5] if len(line.split()) > 5 else "")
    insertion_code = line[26].strip() if len(line) >= 27 else ""
    return {
        "valid_coord": True,
        "raw": line,
        "atom_name": atom_name,
        "chain_id": chain_id or "_",
        "residue_number": _int_or_none(residue_text),
        "residue_text": residue_text,
        "insertion_code": insertion_code or "_",
        "coord": (x, y, z),
    }


def _read_first_model_atoms(path_like: str | Path) -> tuple[list[dict[str, Any]], int]:
    lines = _resolve(path_like).read_text(encoding="utf-8").splitlines()
    in_first_model = False
    seen_model = False
    model_index = 0
    atoms: list[dict[str, Any]] = []
    for line in lines:
        rec = _record(line)
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            in_first_model = True
            parts = line.split()
            if len(parts) > 1:
                model_index = _int_or_none(parts[1]) or 0
            continue
        if rec == "END" and in_first_model:
            break
        if rec == "ATOM" and (in_first_model or not seen_model):
            atom = _parse_atom(line)
            if atom is not None:
                atoms.append(atom)
    return atoms, model_index or 1


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _same_residue(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (
        a.get("chain_id") == b.get("chain_id")
        and a.get("residue_number") == b.get("residue_number")
        and a.get("insertion_code") == b.get("insertion_code")
    )


def _cell(coord: tuple[float, float, float], cell_size: float) -> tuple[int, int, int]:
    return tuple(math.floor(axis / cell_size) for axis in coord)


def _clash_count(atoms: list[dict[str, Any]], threshold: float) -> int:
    grid: dict[tuple[int, int, int], list[dict[str, Any]]] = defaultdict(list)
    clashes = 0
    threshold_sq = threshold * threshold
    for atom in atoms:
        if not atom.get("valid_coord"):
            continue
        coord = atom["coord"]
        cell = _cell(coord, threshold)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for other in grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), []):
                        if _same_residue(atom, other):
                            continue
                        other_coord = other["coord"]
                        dist_sq = (
                            (coord[0] - other_coord[0]) ** 2
                            + (coord[1] - other_coord[1]) ** 2
                            + (coord[2] - other_coord[2]) ** 2
                        )
                        if dist_sq < threshold_sq:
                            clashes += 1
        grid[cell].append(atom)
    return clashes


def _ca_continuity(atoms: list[dict[str, Any]]) -> dict[str, Any]:
    ca_by_chain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for atom in atoms:
        if atom.get("atom_name") == "CA" and atom.get("residue_number") is not None and atom.get("valid_coord"):
            ca_by_chain[str(atom["chain_id"])].append(atom)
    too_close = 0
    too_far = 0
    checked = 0
    for chain_atoms in ca_by_chain.values():
        chain_atoms.sort(key=lambda item: (int(item["residue_number"]), str(item["insertion_code"])))
        for left, right in zip(chain_atoms, chain_atoms[1:]):
            if int(right["residue_number"]) - int(left["residue_number"]) != 1:
                continue
            checked += 1
            dist = _distance(left["coord"], right["coord"])
            if dist < CA_TOO_CLOSE_A:
                too_close += 1
            if dist > CA_TOO_FAR_A:
                too_far += 1
    return {
        "chain_count_with_ca": len(ca_by_chain),
        "ca_pair_checked_count": checked,
        "ca_too_close_count": too_close,
        "ca_too_far_count": too_far,
    }


def validate_geometry(*, target_id: str, prediction_file: str | Path) -> dict[str, Any]:
    path = _resolve(prediction_file)
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not path.exists():
        blockers.append(_blocker("prediction_file_missing", f"Prediction file `{_artifact(path)}` is missing."))
        return _payload(target_id, path, blockers, warnings, {})

    atoms, model_index = _read_first_model_atoms(path)
    if not atoms:
        blockers.append(_blocker("atom_records_missing", "No ATOM records found in model 1."))
        return _payload(target_id, path, blockers, warnings, {"model_index": model_index, "atom_count": 0})

    invalid_coord_count = sum(1 for atom in atoms if not atom.get("valid_coord"))
    finite_atoms = [atom for atom in atoms if atom.get("valid_coord")]
    if invalid_coord_count:
        blockers.append(_blocker("invalid_atom_coordinates", "One or more ATOM records have missing or non-finite coordinates."))
    out_of_bounds_count = sum(
        1 for atom in finite_atoms for axis in atom["coord"] if abs(axis) > COORD_ABS_MAX_A
    )
    if out_of_bounds_count:
        blockers.append(_blocker("coordinate_out_of_bounds", "One or more coordinates exceed the configured absolute coordinate bound."))

    clash_count = _clash_count(finite_atoms, CLASH_DISTANCE_A)
    if clash_count:
        blockers.append(_blocker("severe_inter_residue_atom_clashes", f"Detected {clash_count} inter-residue atom pairs below {CLASH_DISTANCE_A:.2f} A."))

    continuity = _ca_continuity(finite_atoms)
    if continuity["ca_too_close_count"]:
        blockers.append(_blocker("ca_continuity_too_close", "Consecutive CA atoms include distances below the configured lower bound."))
    if continuity["ca_too_far_count"]:
        blockers.append(_blocker("ca_continuity_too_far", "Consecutive CA atoms include distances above the configured upper bound."))
    if continuity["ca_pair_checked_count"] == 0:
        warnings.append(_warning("no_ca_continuity_pairs_checked", "No consecutive CA pairs were available for continuity checks."))

    xs = [atom["coord"][0] for atom in finite_atoms]
    ys = [atom["coord"][1] for atom in finite_atoms]
    zs = [atom["coord"][2] for atom in finite_atoms]
    spans = {
        "x_span_A": max(xs) - min(xs) if xs else 0.0,
        "y_span_A": max(ys) - min(ys) if ys else 0.0,
        "z_span_A": max(zs) - min(zs) if zs else 0.0,
    }
    if finite_atoms and max(spans.values()) < 0.5:
        blockers.append(_blocker("near_zero_coordinate_span", "All atom coordinates occupy a near-zero spatial span."))

    metrics = {
        "target_id": target_id,
        "model_index": model_index,
        "atom_count": len(atoms),
        "finite_atom_count": len(finite_atoms),
        "invalid_coord_count": invalid_coord_count,
        "out_of_bounds_coordinate_count": out_of_bounds_count,
        "severe_clash_count": clash_count,
        **continuity,
        **{key: round(value, 3) for key, value in spans.items()},
    }
    return _payload(target_id, path, blockers, warnings, metrics)


def _payload(
    target_id: str,
    prediction_path: Path,
    blockers: list[dict[str, str]],
    warnings: list[dict[str, str]],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    summary = {
        "packet_type": "casp17_geometry_sanity",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_id": target_id,
        "prediction_file_path": _artifact(prediction_path),
        "geometry_sanity_status": "fail" if blockers else "pass",
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "atom_count": metrics.get("atom_count", 0),
        "finite_atom_count": metrics.get("finite_atom_count", 0),
        "severe_clash_count": metrics.get("severe_clash_count", 0),
        "ca_pair_checked_count": metrics.get("ca_pair_checked_count", 0),
        "ca_too_close_count": metrics.get("ca_too_close_count", 0),
        "ca_too_far_count": metrics.get("ca_too_far_count", 0),
        "claim_boundary": "CASP17 geometry sanity only; not structure accuracy, interface correctness, or accepted submission evidence.",
    }
    return {"summary": summary, "blockers": blockers, "warnings": warnings, "metrics": metrics}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "geometry_sanity_status",
        "blocker_count",
        "warning_count",
        "atom_count",
        "finite_atom_count",
        "severe_clash_count",
        "ca_pair_checked_count",
        "ca_too_close_count",
        "ca_too_far_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Geometry Sanity",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target: `{summary['target_id']}`",
        f"- prediction file: `{summary['prediction_file_path']}`",
        f"- geometry sanity: `{summary['geometry_sanity_status']}`",
        f"- atoms: `{summary['atom_count']}`",
        f"- severe clashes: `{summary['severe_clash_count']}`",
        f"- CA pairs checked: `{summary['ca_pair_checked_count']}`",
        f"- blocker/warning count: `{summary['blocker_count']}/{summary['warning_count']}`",
        "",
        "## Blockers",
        "",
    ]
    if payload["blockers"]:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    if payload["warnings"]:
        lines.extend(f"- `{warning['code']}`: {warning['reason']}" for warning in payload["warnings"])
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate basic CASP17 TS prediction geometry sanity.")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--prediction-file", required=True)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = validate_geometry(target_id=args.target_id, prediction_file=args.prediction_file)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, [payload["summary"]])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
