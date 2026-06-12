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

from tools.casp17 import validate_casp17_confidence_calibration as confidence_validator
from tools.casp17 import validate_casp17_geometry_sanity as geometry_validator
from tools import validate_casp17_ts_prediction as format_validator
from tools.build_casp17_sidechain_scaffold_packet import BACKBONE_ATOMS, SIDECHAIN_ATOMS


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WATCHLIST_JSON = "runs/casp17_target_watchlist_current.json"
DEFAULT_SOURCE_DIR = "runs/casp17_predictions_steric_relaxed_current"
DEFAULT_SEQUENCE_DIR = "runs/casp17_sequences_current"
DEFAULT_OUT_DIR = "runs/casp17_predictions_sidechain_completed_current"
DEFAULT_OUT_JSON = "runs/casp17_sidechain_completion_repair_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_sidechain_completion_repair_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_sidechain_completion_repair_packet_current.md"


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
    return chain, int(resseq), insertion, atom


def _parse_source(path_like: str | Path) -> tuple[list[str], dict[tuple[str, int, str], dict[str, Any]]]:
    path = _resolve(path_like)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    residues: dict[tuple[str, int, str], dict[str, Any]] = {}
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
        key = (chain, resseq, insertion)
        residue = residues.setdefault(
            key,
            {
                "chain_id": chain,
                "resseq": resseq,
                "insertion_code": insertion,
                "resname": line[17:20].strip().upper() if len(line) >= 20 else "UNK",
                "atoms": {},
                "last_line_index": line_index,
                "b_factor": _pdb_float(line, 60, 66, 10) or 50.0,
            },
        )
        residue["atoms"][atom_name] = (float(x), float(y), float(z))
        residue["last_line_index"] = max(int(residue["last_line_index"]), line_index)
        if atom_name == "CA":
            residue["b_factor"] = _pdb_float(line, 60, 66, 10) or residue["b_factor"]
    return lines, residues


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _add(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def _scale(a: tuple[float, float, float], scalar: float) -> tuple[float, float, float]:
    return a[0] * scalar, a[1] * scalar, a[2] * scalar


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


def _coord(
    ca: tuple[float, float, float],
    tangent: tuple[float, float, float],
    normal: tuple[float, float, float],
    binormal: tuple[float, float, float],
    t: float,
    n: float,
    b: float,
) -> tuple[float, float, float]:
    return _add(_add(_add(ca, _scale(tangent, t)), _scale(normal, n)), _scale(binormal, b))


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


def _missing_atom_coord(
    atom_name: str,
    ordinal: int,
    ca: tuple[float, float, float],
    tangent: tuple[float, float, float],
    normal: tuple[float, float, float],
    binormal: tuple[float, float, float],
) -> tuple[float, float, float]:
    if atom_name == "CB":
        return _coord(ca, tangent, normal, binormal, -0.22, 1.46, -0.48)
    level = 1 + max(0, ordinal - 1) // 2
    branch = -0.72 if ordinal % 2 else 0.72
    if atom_name[-1:].isdigit():
        branch *= 1.18 if int(atom_name[-1]) % 2 else -1.18
    if atom_name.startswith(("O", "N", "S")):
        branch *= 0.82
    if atom_name in {"CZ", "CE", "NE", "NZ", "OH", "SG", "SD", "CH2"}:
        level += 1
    return _coord(ca, tangent, normal, binormal, 0.24 * ((ordinal % 3) - 1), 1.45 + 1.02 * level, branch)


def _element(atom_name: str) -> str:
    stripped = atom_name.strip()
    if not stripped:
        return "C"
    if stripped[0].isdigit() and len(stripped) > 1:
        stripped = stripped[1:]
    return stripped[0].upper()


def _atom_line(
    atom_name: str,
    resname: str,
    chain_id: str,
    resseq: int,
    coord: tuple[float, float, float],
    b_factor: float,
) -> str:
    x, y, z = coord
    return (
        f"ATOM  {0:5d} {atom_name:<4} {resname:>3} {chain_id:1}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{float(b_factor):6.2f}          {_element(atom_name):>2}  "
    )


def _renumber_atom_lines(lines: list[str]) -> list[str]:
    serial = 1
    out: list[str] = []
    for line in lines:
        if _record(line) == "ATOM":
            padded = line.ljust(80)
            out.append(f"{padded[:6]}{serial:5d}{padded[11:]}")
            serial += 1
        else:
            out.append(line)
    return out


def _insert_remark(lines: list[str]) -> list[str]:
    remark = "REMARK CASP17 SIDECHAIN_COMPLETION_REPAIR local internal missing sidechain atom repair; not native-calibrated sidechain refinement"
    if any(line.startswith("REMARK CASP17 SIDECHAIN_COMPLETION_REPAIR") for line in lines):
        return lines
    out = lines[:]
    insert_index = next((index + 1 for index, line in enumerate(out) if _record(line) in {"SCORE", "QSCORE", "STOICH"}), None)
    if insert_index is None:
        insert_index = next((index + 1 for index, line in enumerate(out) if _record(line) == "MODEL"), 0)
    out.insert(insert_index, remark)
    return out


def _build_insertions(residues: dict[tuple[str, int, str], dict[str, Any]]) -> tuple[dict[int, list[str]], dict[str, int]]:
    by_chain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for residue in residues.values():
        if "CA" in residue["atoms"]:
            by_chain[str(residue["chain_id"])].append(residue)
    for trace in by_chain.values():
        trace.sort(key=lambda item: (int(item["resseq"]), str(item["insertion_code"])))
    insertions: dict[int, list[str]] = defaultdict(list)
    missing_before = 0
    inserted = 0
    repaired_residues = 0
    for chain_id, trace in by_chain.items():
        for index, residue in enumerate(trace):
            sidechain = SIDECHAIN_ATOMS.get(str(residue["resname"]))
            if not sidechain:
                continue
            missing = [atom_name for atom_name in sidechain if atom_name not in residue["atoms"]]
            if not missing:
                continue
            missing_before += len(missing)
            repaired_residues += 1
            tangent, normal, binormal = _frame(trace, index)
            ca = residue["atoms"]["CA"]
            for atom_name in missing:
                ordinal = sidechain.index(atom_name)
                coord = _missing_atom_coord(atom_name, ordinal, ca, tangent, normal, binormal)
                insertions[int(residue["last_line_index"])].append(
                    _atom_line(
                        atom_name,
                        str(residue["resname"]),
                        chain_id,
                        int(residue["resseq"]),
                        coord,
                        float(residue.get("b_factor", 50.0)),
                    )
                )
                inserted += 1
    return insertions, {
        "missing_sidechain_atom_count_before": missing_before,
        "inserted_sidechain_atom_count": inserted,
        "repaired_residue_count": repaired_residues,
    }


def _missing_sidechain_count(residues: dict[tuple[str, int, str], dict[str, Any]]) -> int:
    missing = 0
    for residue in residues.values():
        sidechain = SIDECHAIN_ATOMS.get(str(residue["resname"]))
        if not sidechain:
            continue
        atom_names = set(residue["atoms"])
        missing += len(set(sidechain) - atom_names)
    return missing


def _write_repaired(source: Path, out_pdb: Path) -> dict[str, int]:
    lines, residues = _parse_source(source)
    insertions, metrics = _build_insertions(residues)
    out_lines: list[str] = []
    for line_index, line in enumerate(lines):
        out_lines.append(line)
        out_lines.extend(insertions.get(line_index, []))
    out_lines = _renumber_atom_lines(_insert_remark(out_lines))
    out_pdb.parent.mkdir(parents=True, exist_ok=True)
    out_pdb.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    _lines_after, residues_after = _parse_source(out_pdb)
    metrics["missing_sidechain_atom_count_after"] = _missing_sidechain_count(residues_after)
    return metrics


def _build_one(target_id: str, args: argparse.Namespace) -> dict[str, Any]:
    source = _resolve(args.source_dir) / f"{target_id}TS.pdb"
    sequence_path = _resolve(args.sequence_dir) / f"{target_id}.fasta"
    out_pdb = _resolve(args.out_dir) / f"{target_id}TS.pdb"
    blockers: list[str] = []
    metrics = {
        "missing_sidechain_atom_count_before": 0,
        "inserted_sidechain_atom_count": 0,
        "repaired_residue_count": 0,
        "missing_sidechain_atom_count_after": 0,
    }
    validation = {
        "format_check_status": "not_run",
        "geometry_sanity_status": "not_run",
        "confidence_calibration_status": "not_run",
    }
    if not source.exists():
        blockers.append("source_prediction_missing")
    if not sequence_path.exists():
        blockers.append("sequence_file_missing")
    if not blockers:
        metrics = _write_repaired(source, out_pdb)
        validation_format = format_validator.validate_prediction(target_id=target_id, prediction_file=out_pdb, sequence_path=sequence_path)
        validation_geometry = geometry_validator.validate_geometry(target_id=target_id, prediction_file=out_pdb)
        validation_confidence = confidence_validator.validate_confidence(target_id=target_id, prediction_file=out_pdb, sequence_path=sequence_path)
        geometry_blocker_codes = {
            str(blocker.get("code", ""))
            for blocker in validation_geometry.get("blockers", [])
            if isinstance(blocker, dict)
        }
        relax_only_geometry = bool(geometry_blocker_codes) and geometry_blocker_codes <= {"severe_inter_residue_atom_clashes"}
        validation = {
            "format_check_status": validation_format["summary"]["format_check_status"],
            "geometry_sanity_status": validation_geometry["summary"]["geometry_sanity_status"],
            "confidence_calibration_status": validation_confidence["summary"]["confidence_calibration_status"],
        }
        if (
            validation["geometry_sanity_status"] != "pass"
            and bool(getattr(args, "allow_severe_clash_pre_relax", False))
            and relax_only_geometry
        ):
            validation["geometry_sanity_status"] = "needs_steric_relax"
        if validation["format_check_status"] != "pass":
            blockers.append("format_check_failed")
        if validation["geometry_sanity_status"] not in {"pass", "needs_steric_relax"}:
            blockers.append("geometry_sanity_failed")
        if validation["confidence_calibration_status"] != "pass":
            blockers.append("confidence_calibration_failed")
        if int(metrics["missing_sidechain_atom_count_after"]):
            blockers.append("missing_sidechain_atoms_after_repair")
    return {
        "target_id": target_id,
        "sidechain_completion_repair_status": "pass" if not blockers else "blocked",
        "source_pdb": _artifact(source),
        "out_pdb": _artifact(out_pdb),
        **metrics,
        **validation,
        "blockers": ",".join(sorted(set(blockers))),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rows = [_build_one(target_id, args) for target_id in _target_ids(args)]
    pass_count = sum(1 for row in rows if row["sidechain_completion_repair_status"] == "pass")
    summary = {
        "packet_type": "casp17_sidechain_completion_repair_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": len(rows) - pass_count,
        "sidechain_completion_repair_status": "pass" if rows and pass_count == len(rows) else "blocked",
        "source_dir": _artifact(args.source_dir),
        "out_dir": _artifact(args.out_dir),
        "total_missing_sidechain_atom_count_before": sum(int(row.get("missing_sidechain_atom_count_before", 0) or 0) for row in rows),
        "total_inserted_sidechain_atom_count": sum(int(row.get("inserted_sidechain_atom_count", 0) or 0) for row in rows),
        "total_missing_sidechain_atom_count_after": sum(int(row.get("missing_sidechain_atom_count_after", 0) or 0) for row in rows),
        "post_repair_needs_steric_relax_count": sum(1 for row in rows if row.get("geometry_sanity_status") == "needs_steric_relax"),
        "claim_boundary": "Local internal repair of missing sidechain atoms using CA-frame templates; severe close contacts may be allowed only as a pre-relax intermediate when explicitly requested; not statistical rotamer-library packing, not energy-minimized refinement, and not native sidechain accuracy evidence.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Sidechain Completion Repair Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- source_dir: `{summary['source_dir']}`",
        f"- out_dir: `{summary['out_dir']}`",
        f"- status: `{summary['sidechain_completion_repair_status']}`",
        f"- pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- missing sidechain atoms before/inserted/after: `{summary['total_missing_sidechain_atom_count_before']}/{summary['total_inserted_sidechain_atom_count']}/{summary['total_missing_sidechain_atom_count_after']}`",
        f"- post-repair needs steric relax: `{summary['post_repair_needs_steric_relax_count']}`",
        "",
        "| target | status | missing before | inserted | missing after | repaired residues | format | geometry | confidence | blockers |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['sidechain_completion_repair_status']}` | "
            f"{row['missing_sidechain_atom_count_before']} | {row['inserted_sidechain_atom_count']} | "
            f"{row['missing_sidechain_atom_count_after']} | {row['repaired_residue_count']} | "
            f"`{row['format_check_status']}` | `{row['geometry_sanity_status']}` | `{row['confidence_calibration_status']}` | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair missing sidechain atoms in CASP17 generated TS coordinates using local CA-frame templates.")
    parser.add_argument("--target-watchlist-json", default=DEFAULT_WATCHLIST_JSON)
    parser.add_argument("--target-ids", default="")
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--sequence-dir", default=DEFAULT_SEQUENCE_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument(
        "--allow-severe-clash-pre-relax",
        action="store_true",
        help="Treat severe inter-residue clashes introduced by missing-atom repair as an explicit intermediate that must be followed by steric relaxation.",
    )
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
