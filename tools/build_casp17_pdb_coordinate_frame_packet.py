#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_model_selected_statistical_rotamer_current"
DEFAULT_OUT_DIR = "runs/casp17_predictions_model_selected_coordinate_normalized_current"
DEFAULT_OUT_JSON = "runs/casp17_pdb_coordinate_frame_packet_model_selected_current.json"
DEFAULT_OUT_CSV = "runs/casp17_pdb_coordinate_frame_packet_model_selected_current.csv"
DEFAULT_OUT_MD = "runs/casp17_pdb_coordinate_frame_packet_model_selected_current.md"

PDB_COORD_MIN = -999.0
PDB_COORD_MAX = 9999.0
PDB_COORD_MARGIN = 1.0


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


def _field_int(text: str, default: int) -> int:
    try:
        return int(text.strip())
    except ValueError:
        return default


def _field_float(text: str, default: float) -> float:
    try:
        return float(text.strip())
    except ValueError:
        return default


def _element_from_atom_name(atom_name: str) -> str:
    stripped = "".join(char for char in atom_name.strip() if char.isalpha())
    if not stripped:
        return ""
    if len(stripped) >= 2 and stripped[:2].title() in {"Cl", "Br", "Na", "Mg", "Ca", "Fe", "Zn", "Mn", "Cu", "Co", "Ni"}:
        return stripped[:2].title()
    return stripped[0].upper()


def _parse_atom_line(line: str) -> dict[str, Any] | None:
    parts = line.split()
    record = _record(line) or (parts[0].upper() if parts else "ATOM")
    serial = _field_int(line[6:11], -1)
    atom_name = line[12:16].strip()
    resname = line[17:20].strip()
    chain_id = line[21:22].strip() or "_"
    resseq = _field_int(line[22:26], -1)
    fixed_ok = False
    try:
        x = float(line[30:38])
        y = float(line[38:46])
        z = float(line[46:54])
        fixed_ok = serial >= 0 and bool(atom_name and resname) and resseq >= 0
    except ValueError:
        fixed_ok = False
    if not fixed_ok:
        if len(parts) < 9:
            return None
        try:
            serial = int(parts[1])
            atom_name = parts[2]
            resname = parts[3]
            chain_id = parts[4][:1] or "_"
            resseq = int(parts[5])
            x = float(parts[6])
            y = float(parts[7])
            z = float(parts[8])
        except (ValueError, IndexError):
            return None
    try:
        occupancy = float(line[54:60])
    except ValueError:
        occupancy = _field_float(parts[9], 1.0) if len(parts) > 9 else 1.0
    try:
        b_factor = float(line[60:66])
    except ValueError:
        b_factor = _field_float(parts[10], 0.0) if len(parts) > 10 else 0.0
    try:
        element = parts[11] if len(parts) > 11 else line[76:78].strip()
    except (ValueError, IndexError):
        element = line[76:78].strip()
    element = element.strip() or _element_from_atom_name(atom_name)
    alt_loc = line[16:17] if len(line) >= 17 and line[16:17].strip() else " "
    insertion = line[26:27] if len(line) >= 27 and line[26:27].strip() else " "
    charge = line[78:80].strip() if len(line) >= 80 else ""
    return {
        "record": record if record in {"ATOM", "HETATM"} else "ATOM",
        "serial": serial,
        "atom_name": atom_name,
        "alt_loc": alt_loc,
        "resname": resname,
        "chain_id": chain_id,
        "resseq": resseq,
        "insertion": insertion,
        "x": x,
        "y": y,
        "z": z,
        "occupancy": occupancy,
        "b_factor": b_factor,
        "element": element,
        "charge": charge,
    }


def _format_atom_name(atom_name: str, element: str) -> str:
    atom = atom_name.strip()[:4]
    elem = element.strip()
    if len(atom) < 4 and len(elem) == 1 and not atom[0].isdigit():
        return f" {atom:<3}"
    return f"{atom:<4}"


def _format_atom_line(atom: dict[str, Any]) -> str:
    atom_name = _format_atom_name(_text(atom["atom_name"]), _text(atom["element"]))
    return (
        f"{_text(atom['record']):<6}{int(atom['serial']):5d} "
        f"{atom_name}{_text(atom['alt_loc'])[:1] or ' '}"
        f"{_text(atom['resname'])[:3]:>3} {_text(atom['chain_id'])[:1] or '_'}"
        f"{int(atom['resseq']):4d}{_text(atom['insertion'])[:1] or ' '}   "
        f"{float(atom['x']):8.3f}{float(atom['y']):8.3f}{float(atom['z']):8.3f}"
        f"{float(atom['occupancy']):6.2f}{float(atom['b_factor']):6.2f}"
        f"          {_text(atom['element'])[:2]:>2}{_text(atom['charge'])[:2]:>2}"
    )


def _axis_shift(values: list[float]) -> tuple[float, str]:
    if not values:
        return 0.0, "no_atoms"
    low = min(values)
    high = max(values)
    if low >= PDB_COORD_MIN and high <= PDB_COORD_MAX:
        return 0.0, "already_in_frame"
    span = high - low
    allowed_span = (PDB_COORD_MAX - PDB_COORD_MARGIN) - (PDB_COORD_MIN + PDB_COORD_MARGIN)
    if span > allowed_span:
        return 0.0, "span_exceeds_pdb_field"
    desired_low = PDB_COORD_MIN + PDB_COORD_MARGIN
    shift = desired_low - low
    if high + shift > PDB_COORD_MAX - PDB_COORD_MARGIN:
        shift = (PDB_COORD_MAX - PDB_COORD_MARGIN) - high
    return shift, "shifted"


def _line_parseable_fixed_width(line: str) -> bool:
    try:
        float(line[30:38])
        float(line[38:46])
        float(line[46:54])
        float(line[54:60])
        float(line[60:66])
    except ValueError:
        return False
    return True


def _normalize_file(source: Path, out_dir: Path) -> dict[str, Any]:
    target_id = source.stem.replace("TS", "").upper()
    out_path = out_dir / source.name
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    atoms: list[dict[str, Any]] = []
    atom_indexes: list[int] = []
    pre_bad = 0
    parse_errors = 0
    for index, line in enumerate(lines):
        if _record(line) not in {"ATOM", "HETATM"}:
            continue
        if not _line_parseable_fixed_width(line):
            pre_bad += 1
        atom = _parse_atom_line(line)
        if atom is None:
            parse_errors += 1
            continue
        atom_indexes.append(index)
        atoms.append(atom)

    x_shift, x_status = _axis_shift([float(atom["x"]) for atom in atoms])
    y_shift, y_status = _axis_shift([float(atom["y"]) for atom in atoms])
    z_shift, z_status = _axis_shift([float(atom["z"]) for atom in atoms])
    axis_statuses = [x_status, y_status, z_status]
    blocked = parse_errors > 0 or any(status == "span_exceeds_pdb_field" for status in axis_statuses)
    post_bad = 0

    if blocked:
        shutil.copyfile(source, out_path)
    else:
        updated_lines = list(lines)
        for index, atom in zip(atom_indexes, atoms):
            atom["x"] = float(atom["x"]) + x_shift
            atom["y"] = float(atom["y"]) + y_shift
            atom["z"] = float(atom["z"]) + z_shift
            updated = _format_atom_line(atom)
            if not _line_parseable_fixed_width(updated):
                post_bad += 1
            updated_lines[index] = updated
        out_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

    return {
        "target_id": target_id,
        "source_pdb": _artifact(source),
        "normalized_pdb": _artifact(out_path),
        "coordinate_frame_status": "blocked" if blocked or post_bad else "pass",
        "atom_count": len(atoms),
        "pre_fixed_width_parse_error_count": pre_bad,
        "post_fixed_width_parse_error_count": post_bad if not blocked else pre_bad,
        "atom_parse_error_count": parse_errors,
        "x_shift": round(x_shift, 3),
        "y_shift": round(y_shift, 3),
        "z_shift": round(z_shift, 3),
        "x_status": x_status,
        "y_status": y_status,
        "z_status": z_status,
        "blockers": ",".join(
            blocker
            for blocker, condition in [
                ("atom_parse_errors", parse_errors > 0),
                ("coordinate_span_exceeds_pdb_field", any(status == "span_exceeds_pdb_field" for status in axis_statuses)),
                ("post_fixed_width_parse_errors", post_bad > 0),
            ]
            if condition
        ),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_dir = _resolve(args.prediction_dir)
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [_normalize_file(path, out_dir) for path in sorted(source_dir.glob("*TS.pdb"))]
    pass_count = sum(1 for row in rows if row["coordinate_frame_status"] == "pass")
    shifted_count = sum(1 for row in rows if row["x_shift"] or row["y_shift"] or row["z_shift"])
    pre_errors = sum(int(row["pre_fixed_width_parse_error_count"]) for row in rows)
    post_errors = sum(int(row["post_fixed_width_parse_error_count"]) for row in rows)
    summary = {
        "packet_type": "casp17_pdb_coordinate_frame_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "coordinate_frame_status": "pass" if rows and pass_count == len(rows) and post_errors == 0 else "blocked",
        "prediction_dir": _artifact(source_dir),
        "normalized_prediction_dir": _artifact(out_dir),
        "target_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": len(rows) - pass_count,
        "shifted_target_count": shifted_count,
        "pre_fixed_width_parse_error_count": pre_errors,
        "post_fixed_width_parse_error_count": post_errors,
        "claim_boundary": "Coordinate-frame normalization only. It applies rigid translations to generated CASP17 coordinates so PDB fixed-width coordinate fields remain parseable; it does not change geometry, prove native accuracy, use external predictors, or submit to CASP.",
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
        fieldnames = ["target_id", "coordinate_frame_status", "blockers"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 PDB Coordinate Frame Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- coordinate_frame_status: `{summary['coordinate_frame_status']}`",
        f"- targets pass/total: `{summary['pass_count']}/{summary['target_count']}`",
        f"- shifted targets: `{summary['shifted_target_count']}`",
        f"- fixed-width parse errors before/after: `{summary['pre_fixed_width_parse_error_count']}/{summary['post_fixed_width_parse_error_count']}`",
        f"- normalized_prediction_dir: `{summary['normalized_prediction_dir']}`",
        "",
        "## Targets",
        "",
        "| target | status | pre errors | post errors | shifts xyz | blockers |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['coordinate_frame_status']}` | "
            f"{row['pre_fixed_width_parse_error_count']} | {row['post_fixed_width_parse_error_count']} | "
            f"`{row['x_shift']},{row['y_shift']},{row['z_shift']}` | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize CASP17 PDB coordinate frames into fixed-width parseable fields.")
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
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
    if payload["summary"]["coordinate_frame_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
