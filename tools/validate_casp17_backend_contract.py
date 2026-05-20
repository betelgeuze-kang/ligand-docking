#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/casp17_backend_contract_validation_current.json"
DEFAULT_OUT_CSV = "runs/casp17_backend_contract_validation_current.csv"
DEFAULT_OUT_MD = "runs/casp17_backend_contract_validation_current.md"

AA3_TO_1 = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLN": "Q",
    "GLU": "E",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
    "ASX": "B",
    "GLX": "Z",
    "UNK": "X",
}


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


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _fasta_residue_count(path_like: str | Path) -> tuple[int, int]:
    path = _resolve(path_like)
    if not path.exists():
        return 0, 0
    entries = 0
    residues = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            entries += 1
        else:
            residues += len(re.sub(r"[^A-Za-z*.-]", "", stripped))
    return entries, residues


def _fasta_sequences(path_like: str | Path) -> list[str]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    sequences: list[str] = []
    current: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            if current:
                sequences.append("".join(current))
            current = []
            continue
        current.append(re.sub(r"[^A-Za-z]", "", stripped).upper())
    if current:
        sequences.append("".join(current))
    return ["".join(char if char.isalpha() else "X" for char in sequence) for sequence in sequences if sequence]


def _pdb_atom_stats(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    stats = {"atom_count": 0, "hetatm_count": 0, "ca_count": 0, "residue_count": 0}
    if not path.exists():
        return stats
    residues: set[tuple[str, str, str]] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        rec = _record(line)
        if rec == "HETATM":
            stats["hetatm_count"] += 1
            continue
        if rec != "ATOM":
            continue
        stats["atom_count"] += 1
        atom_name = line[12:16].strip() if len(line) >= 16 else ""
        if atom_name == "CA":
            stats["ca_count"] += 1
        chain_id = line[21].strip() if len(line) >= 22 else "_"
        residue_number = line[22:26].strip() if len(line) >= 26 else ""
        insertion_code = line[26].strip() if len(line) >= 27 else "_"
        residues.add((chain_id or "_", residue_number, insertion_code or "_"))
    stats["residue_count"] = len(residues)
    return stats


def _pdb_ca_sequences(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    chains: list[dict[str, Any]] = []
    by_chain: dict[str, dict[str, Any]] = {}
    seen_residues: set[tuple[str, str, str]] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if _record(line) != "ATOM":
            continue
        atom_name = line[12:16].strip() if len(line) >= 16 else ""
        if atom_name != "CA":
            continue
        chain_id = line[21].strip() if len(line) >= 22 else "_"
        chain_id = chain_id or "_"
        residue_number = line[22:26].strip() if len(line) >= 26 else ""
        insertion_code = line[26].strip() if len(line) >= 27 else "_"
        key = (chain_id, residue_number, insertion_code or "_")
        if key in seen_residues:
            continue
        seen_residues.add(key)
        resname = line[17:20].strip().upper() if len(line) >= 20 else "UNK"
        entry = by_chain.get(chain_id)
        if entry is None:
            entry = {"chain_id": chain_id, "sequence": [], "residue_numbers": []}
            by_chain[chain_id] = entry
            chains.append(entry)
        entry["sequence"].append(AA3_TO_1.get(resname, "X"))
        entry["residue_numbers"].append(residue_number)
    return [
        {
            "chain_id": entry["chain_id"],
            "sequence": "".join(entry["sequence"]),
            "residue_count": len(entry["sequence"]),
            "residue_numbers": entry["residue_numbers"],
        }
        for entry in chains
    ]


def _runtime_gpu_evidence(payload: dict[str, Any]) -> tuple[bool, str]:
    candidates = [payload]
    summary = payload.get("summary")
    if isinstance(summary, dict):
        candidates.append(summary)
    runtime = payload.get("runtime")
    if isinstance(runtime, dict):
        candidates.append(runtime)
    for item in candidates:
        if item.get("gpu_detected") is True or item.get("cuda_available") is True:
            names = item.get("gpu_names") or item.get("device_names") or item.get("devices") or []
            if isinstance(names, list):
                return True, ",".join(str(name) for name in names if _text(name))
            return True, _text(names)
        torch_cuda = item.get("torch_cuda")
        if isinstance(torch_cuda, dict) and torch_cuda.get("cuda_available") is True:
            names = torch_cuda.get("device_names") or []
            return True, ",".join(str(name) for name in names if _text(name))
    return False, ""


def validate_contract(args: argparse.Namespace) -> dict[str, Any]:
    target_id = _text(args.target_id).upper()
    backend_kind = _text(args.backend_kind).lower() or "custom"
    sequence_path = _resolve(args.sequence_path)
    raw_pdb = _resolve(args.raw_pdb)
    runtime_json = _resolve(args.runtime_json) if _text(args.runtime_json) else Path("")
    blockers: list[dict[str, str]] = []

    if not target_id:
        blockers.append(_blocker("missing_target_id", "Target id is required."))
    if not sequence_path.exists():
        blockers.append(_blocker("sequence_file_missing", "Target FASTA file is missing."))
    if not raw_pdb.exists():
        blockers.append(_blocker("raw_prediction_pdb_missing", "Raw prediction PDB is missing."))

    fasta_entries, fasta_residues = _fasta_residue_count(sequence_path)
    stats = _pdb_atom_stats(raw_pdb)
    if sequence_path.exists() and (fasta_entries == 0 or fasta_residues == 0):
        blockers.append(_blocker("sequence_not_valid_fasta", "Target FASTA has no entries or residues."))
    if raw_pdb.exists() and stats["atom_count"] == 0:
        blockers.append(_blocker("raw_prediction_atom_records_missing", "Raw prediction PDB has no ATOM records."))
    if raw_pdb.exists() and stats["ca_count"] == 0:
        blockers.append(_blocker("raw_prediction_ca_records_missing", "Raw prediction PDB has no CA atoms."))
    if fasta_residues and stats["residue_count"] > fasta_residues * 1.30:
        blockers.append(_blocker("raw_prediction_residue_count_exceeds_fasta", "Raw prediction residue count substantially exceeds FASTA residue count."))

    runtime_payload = _read_json(runtime_json) if _text(args.runtime_json) else {}
    gpu_ok, gpu_name = _runtime_gpu_evidence(runtime_payload)
    if args.require_gpu and not gpu_ok:
        blockers.append(_blocker("backend_runtime_gpu_evidence_missing", "GPU execution evidence is required; do not treat CPU fallback as CASP17 generation evidence."))
    if backend_kind == "internal_physics":
        summary = runtime_payload.get("summary") if isinstance(runtime_payload.get("summary"), dict) else {}
        runtime_kind = _text(summary.get("backend_kind") or runtime_payload.get("backend_kind")).lower()
        if runtime_payload and runtime_kind != "internal_physics":
            blockers.append(_blocker("internal_physics_runtime_kind_mismatch", "Runtime evidence is not marked as backend_kind=internal_physics."))
        fasta_sequences = _fasta_sequences(sequence_path)
        pdb_chains = _pdb_ca_sequences(raw_pdb)
        if fasta_sequences and pdb_chains and len(fasta_sequences) != len(pdb_chains):
            blockers.append(_blocker("internal_physics_chain_count_mismatch", "Raw PDB CA chain count must match FASTA entry count for internal physics predictions."))
        if fasta_sequences and pdb_chains:
            for index, fasta_sequence in enumerate(fasta_sequences):
                if index >= len(pdb_chains):
                    continue
                pdb_sequence = _text(pdb_chains[index].get("sequence"))
                if len(pdb_sequence) != len(fasta_sequence):
                    blockers.append(_blocker("internal_physics_residue_count_mismatch", "Raw PDB CA residue count must exactly match each FASTA chain length."))
                    continue
                if pdb_sequence != fasta_sequence:
                    blockers.append(_blocker("internal_physics_sequence_mismatch", "Raw PDB CA residue names must exactly match the target FASTA sequence."))
                    break

    summary = {
        "packet_type": "casp17_backend_contract_validation",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_id": target_id,
        "backend_kind": backend_kind,
        "sequence_path": _artifact(sequence_path),
        "raw_pdb": _artifact(raw_pdb),
        "runtime_json": _artifact(runtime_json) if _text(args.runtime_json) else "",
        "contract_status": "pass" if not blockers else "blocked",
        "require_gpu": bool(args.require_gpu),
        "gpu_evidence_detected": gpu_ok,
        "gpu_evidence_name": gpu_name,
        "fasta_entry_count": fasta_entries,
        "fasta_residue_count": fasta_residues,
        "pdb_ca_chain_count": len(_pdb_ca_sequences(raw_pdb)) if raw_pdb.exists() else 0,
        **stats,
        "blocker_count": len(blockers),
        "claim_boundary": "Backend output contract validation only; not CASP17 format validation, structure accuracy evidence, or public submission authorization.",
    }
    return {"summary": summary, "blockers": blockers}


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
        "# CASP17 Backend Contract Validation",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target: `{summary['target_id']}`",
        f"- contract status: `{summary['contract_status']}`",
        f"- backend kind: `{summary['backend_kind']}`",
        f"- require GPU: `{summary['require_gpu']}`",
        f"- GPU evidence: `{summary['gpu_evidence_detected']}` `{summary['gpu_evidence_name'] or '-'}`",
        f"- raw atoms / CA / residues: `{summary['atom_count']}/{summary['ca_count']}/{summary['residue_count']}`",
        f"- FASTA entries / residues: `{summary['fasta_entry_count']}/{summary['fasta_residue_count']}`",
        f"- blockers: `{summary['blocker_count']}`",
        "",
        "## Blockers",
        "",
    ]
    if payload["blockers"]:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a CASP17 custom/backend raw prediction output contract before TS conversion.")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--sequence-path", required=True)
    parser.add_argument("--raw-pdb", required=True)
    parser.add_argument("--runtime-json", default="")
    parser.add_argument("--backend-kind", choices=["custom", "internal_physics", "external_adapter"], default="custom")
    parser.add_argument("--require-gpu", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = validate_contract(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, [payload["summary"]])
    _write_md(args.out_md, payload)
    if payload["blockers"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
