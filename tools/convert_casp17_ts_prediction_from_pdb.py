#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/casp17_ts_prediction_conversion_current.json"
DEFAULT_OUT_CSV = "runs/casp17_ts_prediction_conversion_current.csv"
DEFAULT_OUT_MD = "runs/casp17_ts_prediction_conversion_current.md"


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


def _atom_lines(path: Path) -> tuple[list[str], int]:
    raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    atoms: list[str] = []
    hetatm_count = 0
    for line in raw_lines:
        rec = _record(line)
        if rec == "ATOM":
            atoms.append(line.rstrip("\r\n"))
        elif rec == "HETATM":
            hetatm_count += 1
    return atoms, hetatm_count


def _atom_chain_id(line: str) -> str:
    if len(line) > 21:
        return line[21].strip() or "_"
    fields = line.split()
    return fields[4] if len(fields) > 4 else "_"


def _ts_coordinate_lines(atoms: list[str], parent: str) -> tuple[list[str], int, int]:
    lines: list[str] = []
    current_chain = ""
    parent_count = 0
    ter_count = 0
    for atom in atoms:
        chain_id = _atom_chain_id(atom)
        if chain_id != current_chain:
            if current_chain:
                lines.append("TER")
                ter_count += 1
            lines.append(f"PARENT {parent}")
            parent_count += 1
            current_chain = chain_id
        lines.append(atom)
    if current_chain:
        lines.append("TER")
        ter_count += 1
    return lines, parent_count, ter_count


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
        "# CASP17 TS Prediction Conversion",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target: `{summary['target_id']}`",
        f"- input PDB: `{summary['input_pdb']}`",
        f"- output TS PDB: `{summary['out_pdb']}`",
        f"- conversion status: `{summary['conversion_status']}`",
        f"- atom count: `{summary['atom_count']}`",
        f"- blockers: `{summary['blocker_count']}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = payload.get("blockers", [])
    if blockers:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def convert_prediction(args: argparse.Namespace) -> dict[str, Any]:
    target_id = _text(args.target_id).upper()
    input_pdb = _resolve(args.input_pdb)
    sequence_path = _resolve(args.sequence_path)
    out_pdb = _resolve(args.out_pdb or f"runs/casp17_predictions_current/{target_id}TS.pdb")
    blockers: list[dict[str, str]] = []

    if not target_id:
        blockers.append(_blocker("missing_target_id", "Target id is required."))
    if not _text(args.author_code):
        blockers.append(_blocker("missing_author_code", "CASP author code is required; do not generate submission-shaped files without it."))
    if not input_pdb.exists():
        blockers.append(_blocker("input_pdb_missing", "Input PDB does not exist."))
    if not sequence_path.exists():
        blockers.append(_blocker("sequence_file_missing", "Sequence FASTA does not exist."))

    atom_count = 0
    hetatm_count = 0
    parent_record_count = 0
    ter_record_count = 0
    if not blockers:
        atoms, hetatm_count = _atom_lines(input_pdb)
        atom_count = len(atoms)
        if atom_count == 0:
            blockers.append(_blocker("atom_records_missing", "Input PDB has no ATOM records to convert."))
        if not blockers:
            method = _text(args.method) or "Internal CASP17 target-specific structure prediction; source PDB converted to TS format."
            parent = _text(args.parent) or "N/A"
            coordinate_lines, parent_record_count, ter_record_count = _ts_coordinate_lines(atoms, parent)
            lines = [
                "PFRMAT TS",
                f"TARGET {target_id}",
                f"AUTHOR {_text(args.author_code)}",
                f"METHOD {method}",
                "MODEL 1",
                *coordinate_lines,
                "END",
                "",
            ]
            out_pdb.parent.mkdir(parents=True, exist_ok=True)
            out_pdb.write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "packet_type": "casp17_ts_prediction_conversion",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_id": target_id,
        "input_pdb": _artifact(input_pdb),
        "sequence_path": _artifact(sequence_path),
        "out_pdb": _artifact(out_pdb),
        "conversion_status": "pass" if not blockers else "blocked",
        "atom_count": atom_count,
        "hetatm_count_ignored": hetatm_count,
        "parent_record_count": parent_record_count,
        "ter_record_count": ter_record_count,
        "blocker_count": len(blockers),
        "claim_boundary": "PDB-to-CASP17 TS wrapper only; not validation, official submission, or accuracy evidence.",
    }
    return {"summary": summary, "blockers": blockers}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a target-specific PDB prediction into a CASP17 TS-formatted PDB.")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--input-pdb", required=True)
    parser.add_argument("--sequence-path", required=True)
    parser.add_argument("--author-code", required=True)
    parser.add_argument("--method", default="")
    parser.add_argument("--parent", default="N/A")
    parser.add_argument("--out-pdb", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = convert_prediction(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, [payload["summary"]])
    _write_md(args.out_md, payload)
    if payload["blockers"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
