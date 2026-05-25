#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from tools.build_casp17_historical_benchmark_packet import LEAKAGE_CLEAR_VALUES
from tools.build_casp17_sidechain_scaffold_packet import BACKBONE_ATOMS


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_current.csv"
DEFAULT_OUT_JSON = "runs/casp17_sidechain_native_benchmark_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_sidechain_native_benchmark_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_sidechain_native_benchmark_packet_current.md"


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


def _read_manifest(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], ["manifest_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return [], ["manifest_empty"]
    return rows, []


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
        fieldnames = ["benchmark_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _atom_key(atom: dict[str, Any]) -> tuple[str, int, str, str]:
    return str(atom["chain_id"]), int(atom["resseq"]), str(atom["insertion_code"]), str(atom["atom_name"])


def _residue_key(atom: dict[str, Any]) -> tuple[str, int, str]:
    return str(atom["chain_id"]), int(atom["resseq"]), str(atom["insertion_code"])


def _parse_atoms(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    atoms: list[dict[str, Any]] = []
    seen_model = False
    in_first_model = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
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
        atom_name = line[12:16].strip() if len(line) >= 16 else ""
        resname = line[17:20].strip().upper() if len(line) >= 20 else "UNK"
        chain = line[21].strip() or "_" if len(line) > 21 else "_"
        try:
            resseq = int(line[22:26])
        except ValueError:
            fields = line.split()
            resseq = int(fields[5]) if len(fields) > 5 and fields[5].lstrip("-").isdigit() else 0
        insertion = line[26].strip() or "_" if len(line) > 26 else "_"
        coord = (
            _pdb_float(line, 30, 38, 6),
            _pdb_float(line, 38, 46, 7),
            _pdb_float(line, 46, 54, 8),
        )
        if any(value is None for value in coord):
            continue
        atoms.append(
            {
                "atom_name": atom_name,
                "resname": resname or "UNK",
                "chain_id": chain,
                "resseq": int(resseq),
                "insertion_code": insertion,
                "coord": (float(coord[0]), float(coord[1]), float(coord[2])),
            }
        )
    return atoms


def _ca_entries(atoms: list[dict[str, Any]]) -> dict[tuple[str, int, str], dict[str, Any]]:
    return {_residue_key(atom): atom for atom in atoms if atom["atom_name"] == "CA"}


def _chain_ids(entries: dict[tuple[str, int, str], dict[str, Any]]) -> list[str]:
    return sorted({key[0] for key in entries})


def _identity_match_fraction(
    keys: list[tuple[str, int, str]],
    prediction_entries: dict[tuple[str, int, str], dict[str, Any]],
    native_entries: dict[tuple[str, int, str], dict[str, Any]],
) -> float:
    comparable = [key for key in keys if key in prediction_entries and key in native_entries]
    if not comparable:
        return 0.0
    matched = sum(1 for key in comparable if prediction_entries[key]["resname"] == native_entries[key]["resname"])
    return float(matched / len(comparable))


def _sidechain_entries(atoms: list[dict[str, Any]]) -> dict[tuple[str, int, str, str], dict[str, Any]]:
    entries: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    for atom in atoms:
        atom_name = str(atom["atom_name"]).strip()
        if atom_name in BACKBONE_ATOMS:
            continue
        if atom_name.startswith(("H", "D")):
            continue
        entries[_atom_key(atom)] = atom
    return entries


def _superpose_transform(prediction: np.ndarray, native: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pred_center = prediction.mean(axis=0)
    native_center = native.mean(axis=0)
    pred_centered = prediction - pred_center
    native_centered = native - native_center
    covariance = pred_centered.T @ native_centered
    u, _s, vt = np.linalg.svd(covariance)
    determinant = np.linalg.det(vt.T @ u.T)
    correction = np.diag([1.0, 1.0, -1.0 if determinant < 0 else 1.0])
    rotation = vt.T @ correction @ u.T
    return pred_center, native_center, rotation


def _apply_transform(coords: np.ndarray, pred_center: np.ndarray, native_center: np.ndarray, rotation: np.ndarray) -> np.ndarray:
    return (coords - pred_center) @ rotation + native_center


def _lddt_from_distances(distances: np.ndarray) -> float:
    if len(distances) == 0:
        return 0.0
    return float(np.mean([np.mean(distances <= threshold) for threshold in (0.5, 1.0, 2.0, 4.0)]))


def _score_one(row: dict[str, str], args: argparse.Namespace) -> dict[str, Any]:
    benchmark_id = _text(row.get("benchmark_id")) or _text(row.get("target_id")) or "unknown"
    target_id = _text(row.get("target_id")) or benchmark_id
    scope = (_text(row.get("scope")) or "monomer").lower()
    prediction_path = _resolve(_text(row.get("prediction_pdb")) or _text(row.get("prediction_file")))
    native_path = _resolve(_text(row.get("native_pdb")) or _text(row.get("native_file")))
    leakage = _text(row.get("leakage_clearance") or row.get("no_leak_status")).lower()
    blockers: list[str] = []
    if leakage not in LEAKAGE_CLEAR_VALUES:
        blockers.append("leakage_clearance_missing_or_not_clear")
    if not prediction_path.exists():
        blockers.append("prediction_pdb_missing")
    if not native_path.exists():
        blockers.append("native_pdb_missing")

    metrics: dict[str, Any] = {
        "prediction_ca_count": 0,
        "native_ca_count": 0,
        "matched_ca_count": 0,
        "prediction_ca_coverage": 0.0,
        "native_ca_coverage": 0.0,
        "prediction_chain_count": 0,
        "native_chain_count": 0,
        "sequence_identity_match_fraction": 0.0,
        "sequence_exact_match": False,
        "chain_exact_match": False,
        "prediction_sidechain_atom_count": 0,
        "native_sidechain_atom_count": 0,
        "matched_sidechain_atom_count": 0,
        "native_sidechain_atom_coverage": 0.0,
        "prediction_sidechain_atom_coverage": 0.0,
        "sidechain_rmsd_A": 0.0,
        "sidechain_lddt_proxy": 0.0,
    }
    if not blockers:
        prediction_atoms = _parse_atoms(prediction_path)
        native_atoms = _parse_atoms(native_path)
        prediction_ca = _ca_entries(prediction_atoms)
        native_ca = _ca_entries(native_atoms)
        ca_keys = sorted(set(prediction_ca) & set(native_ca), key=lambda item: (item[0], item[1], item[2]))
        prediction_chains = _chain_ids(prediction_ca)
        native_chains = _chain_ids(native_ca)
        identity_fraction = _identity_match_fraction(ca_keys, prediction_ca, native_ca)
        chain_exact_match = bool(prediction_chains and prediction_chains == native_chains)
        prediction_ca_coverage = len(ca_keys) / len(prediction_ca) if prediction_ca else 0.0
        native_ca_coverage = len(ca_keys) / len(native_ca) if native_ca else 0.0
        prediction_sidechain = _sidechain_entries(prediction_atoms)
        native_sidechain = _sidechain_entries(native_atoms)
        sidechain_keys = sorted(set(prediction_sidechain) & set(native_sidechain), key=lambda item: (item[0], item[1], item[2], item[3]))
        metrics.update(
            {
                "prediction_ca_count": int(len(prediction_ca)),
                "native_ca_count": int(len(native_ca)),
                "matched_ca_count": int(len(ca_keys)),
                "prediction_ca_coverage": round(prediction_ca_coverage, 6),
                "native_ca_coverage": round(native_ca_coverage, 6),
                "prediction_chain_count": int(len(prediction_chains)),
                "native_chain_count": int(len(native_chains)),
                "sequence_identity_match_fraction": round(identity_fraction, 6),
                "sequence_exact_match": bool(identity_fraction >= float(args.min_sequence_match_fraction)),
                "chain_exact_match": chain_exact_match,
                "prediction_sidechain_atom_count": int(len(prediction_sidechain)),
                "native_sidechain_atom_count": int(len(native_sidechain)),
                "matched_sidechain_atom_count": int(len(sidechain_keys)),
                "native_sidechain_atom_coverage": round(len(sidechain_keys) / len(native_sidechain), 6)
                if native_sidechain
                else 0.0,
                "prediction_sidechain_atom_coverage": round(len(sidechain_keys) / len(prediction_sidechain), 6)
                if prediction_sidechain
                else 0.0,
            }
        )
        if len(ca_keys) < int(args.min_ca_count):
            blockers.append("matched_ca_count_below_threshold")
        if prediction_ca_coverage < float(args.min_ca_coverage):
            blockers.append("prediction_ca_coverage_below_threshold")
        if native_ca_coverage < float(args.min_ca_coverage):
            blockers.append("native_ca_coverage_below_threshold")
        if not chain_exact_match:
            blockers.append("prediction_native_chain_ids_mismatch")
        if scope == "complex" and (len(prediction_chains) < 2 or len(native_chains) < 2):
            blockers.append("complex_scope_requires_multichain")
        if scope != "complex" and (len(prediction_chains) != 1 or len(native_chains) != 1):
            blockers.append("monomer_scope_requires_single_chain")
        if identity_fraction < float(args.min_sequence_match_fraction):
            blockers.append("prediction_native_residue_identity_mismatch")
        if len(sidechain_keys) < int(args.min_sidechain_atom_count):
            blockers.append("matched_sidechain_atom_count_below_threshold")
        if metrics["native_sidechain_atom_coverage"] < float(args.min_native_sidechain_coverage):
            blockers.append("native_sidechain_coverage_below_threshold")
        if not blockers:
            pred_ca_coords = np.asarray([prediction_ca[key]["coord"] for key in ca_keys], dtype=float)
            native_ca_coords = np.asarray([native_ca[key]["coord"] for key in ca_keys], dtype=float)
            pred_center, native_center, rotation = _superpose_transform(pred_ca_coords, native_ca_coords)
            pred_sidechain_coords = np.asarray([prediction_sidechain[key]["coord"] for key in sidechain_keys], dtype=float)
            native_sidechain_coords = np.asarray([native_sidechain[key]["coord"] for key in sidechain_keys], dtype=float)
            aligned_sidechain = _apply_transform(pred_sidechain_coords, pred_center, native_center, rotation)
            distances = np.linalg.norm(aligned_sidechain - native_sidechain_coords, axis=1)
            metrics.update(
                {
                    "sidechain_rmsd_A": round(float(math.sqrt(np.mean(distances**2))), 4),
                    "sidechain_lddt_proxy": round(_lddt_from_distances(distances), 6),
                }
            )
            if metrics["sidechain_rmsd_A"] > float(args.max_sidechain_rmsd_A):
                blockers.append("sidechain_rmsd_above_threshold")
            if metrics["sidechain_lddt_proxy"] < float(args.min_sidechain_lddt_proxy):
                blockers.append("sidechain_lddt_below_threshold")
    return {
        "benchmark_id": benchmark_id,
        "target_id": target_id,
        "scope": scope,
        "split": _text(row.get("split")) or "historical",
        "leakage_clearance": leakage or "missing",
        "prediction_pdb": _artifact(prediction_path),
        "native_pdb": _artifact(native_path),
        "sidechain_native_status": "pass" if not blockers else "blocked",
        **metrics,
        "blockers": ",".join(sorted(set(blockers))),
    }


def _mean(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row.get(key, 0.0) or 0.0) for row in rows if row.get("sidechain_native_status") == "pass"]
    return round(sum(values) / len(values), 6) if values else 0.0


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    manifest_rows, manifest_blockers = _read_manifest(args.manifest_csv)
    rows = [_score_one(row, args) for row in manifest_rows]
    pass_count = sum(1 for row in rows if row["sidechain_native_status"] == "pass")
    blocked_count = len(rows) - pass_count
    if manifest_blockers:
        blocked_count = max(blocked_count, 1)
    summary = {
        "packet_type": "casp17_sidechain_native_benchmark_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "manifest_csv": _artifact(args.manifest_csv),
        "benchmark_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": blocked_count,
        "sidechain_native_benchmark_status": "pass" if rows and blocked_count == 0 else "blocked",
        "mean_sidechain_rmsd_A": _mean(rows, "sidechain_rmsd_A"),
        "mean_sidechain_lddt_proxy": _mean(rows, "sidechain_lddt_proxy"),
        "mean_native_sidechain_atom_coverage": _mean(rows, "native_sidechain_atom_coverage"),
        "manifest_blockers": ",".join(manifest_blockers),
        "thresholds": {
            "min_ca_count": int(args.min_ca_count),
            "min_ca_coverage": float(args.min_ca_coverage),
            "min_sidechain_atom_count": int(args.min_sidechain_atom_count),
            "min_sequence_match_fraction": float(args.min_sequence_match_fraction),
            "min_native_sidechain_coverage": float(args.min_native_sidechain_coverage),
            "max_sidechain_rmsd_A": float(args.max_sidechain_rmsd_A),
            "min_sidechain_lddt_proxy": float(args.min_sidechain_lddt_proxy),
        },
        "claim_boundary": "Local no-leak historical sidechain/native benchmark proxy only; not official MolProbity, not current-target native accuracy evidence, and not portal submission.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Sidechain Native Benchmark Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- manifest_csv: `{summary['manifest_csv']}`",
        f"- status: `{summary['sidechain_native_benchmark_status']}`",
        f"- benchmark_count: `{summary['benchmark_count']}`",
        f"- pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- mean sidechain RMSD/lddt/coverage: `{summary['mean_sidechain_rmsd_A']}/{summary['mean_sidechain_lddt_proxy']}/{summary['mean_native_sidechain_atom_coverage']}`",
        "",
        "| benchmark | target | scope | status | matched CA | CA coverage | matched sidechain atoms | native coverage | sidechain RMSD A | sidechain lDDT proxy | blockers |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['benchmark_id']}` | `{row['target_id']}` | `{row['scope']}` | `{row['sidechain_native_status']}` | "
            f"{row['matched_ca_count']} | {row['prediction_ca_coverage']}/{row['native_ca_coverage']} | "
            f"{row['matched_sidechain_atom_count']} | {row['native_sidechain_atom_coverage']} | "
            f"{row['sidechain_rmsd_A']} | {row['sidechain_lddt_proxy']} | {row['blockers'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked` | 0 | 0/0 | 0 | 0 | 0 | 0 | manifest missing or empty |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a no-leak historical sidechain/native benchmark proxy packet for CASP17 internal predictions.")
    parser.add_argument("--manifest-csv", default=DEFAULT_MANIFEST_CSV)
    parser.add_argument("--min-ca-count", type=int, default=20)
    parser.add_argument("--min-ca-coverage", type=float, default=1.0)
    parser.add_argument("--min-sidechain-atom-count", type=int, default=40)
    parser.add_argument("--min-sequence-match-fraction", type=float, default=1.0)
    parser.add_argument("--min-native-sidechain-coverage", type=float, default=0.85)
    parser.add_argument("--max-sidechain-rmsd-A", type=float, default=2.5)
    parser.add_argument("--min-sidechain-lddt-proxy", type=float, default=0.55)
    parser.add_argument("--fail-on-blocked", action="store_true")
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
    if args.fail_on_blocked and payload["summary"]["blocked_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
