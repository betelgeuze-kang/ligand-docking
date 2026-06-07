#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SEED_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_seed_current.csv"
DEFAULT_CALIBRATION_LEDGER_JSON = "casp17/casp17_historical_seed_calibration_candidate_ledgers_current.json"
DEFAULT_METRIC_DIR = "casp17/historical_seed_native_oracle_metric_candidates"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_native_oracle_metric_candidates_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_native_oracle_metric_candidates_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_NATIVE_ORACLE_METRIC_CANDIDATES.md"

ROW_COLUMNS = [
    "row_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "metric_status",
    "metric_candidate_csv",
    "native_pdb",
    "native_exists",
    "candidate_count",
    "metric_candidate_count",
    "selected_native_metric_candidate",
    "best_native_metric_candidate",
    "best_model_rank_candidate",
    "next_action",
    "blockers",
]

CANDIDATE_COLUMNS = [
    "target_id",
    "benchmark_id",
    "scope",
    "candidate_rank",
    "role",
    "path",
    "native_pdb",
    "exists",
    "coordinate_valid",
    "native_exists",
    "native_coordinate_valid",
    "sha256_16",
    "native_metric_candidate",
    "gdt_ts_proxy",
    "gdt_ha_proxy",
    "ca_lddt_proxy",
    "tm_score_proxy",
    "ca_rmsd_angstrom",
    "ca_match_count",
    "ca_match_basis",
    "interface_contact_recall_proxy",
    "interface_contact_precision_proxy",
    "dockq_proxy",
    "ligand_rmsd_proxy",
    "lddt_pli_proxy",
    "bisyrmsd_proxy",
    "metric_status",
    "blockers",
    "notes",
]

CLAIM_BOUNDARY = (
    "Local CASP17 historical seed native metric candidates only. Metrics are deterministic CA-aligned proxy "
    "surfaces computed against already-local historical native files. They are not official CASP assessment "
    "metrics, do not clear leakage provenance, do not prove current-CASP eligibility, do not fetch structures, "
    "do not mutate operator CSVs, and do not submit to CASP."
)

WATER_NAMES = {"HOH", "WAT", "DOD"}


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


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() == "true"


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [f"{_artifact(path)}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    blockers: list[str] = []
    if not fields:
        blockers.append(f"{_artifact(path)}_header_missing")
    return rows, blockers


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


def _pdb_stats(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    stats: dict[str, Any] = {
        "exists": path.is_file(),
        "atom_count": 0,
        "coordinate_valid": False,
        "sha256_16": "",
    }
    if not path.is_file():
        return stats
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    atom_count = 0
    coordinate_valid = True
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            atom_count += 1
            try:
                float(line[30:38])
                float(line[38:46])
                float(line[46:54])
            except ValueError:
                coordinate_valid = False
    stats["atom_count"] = atom_count
    stats["coordinate_valid"] = coordinate_valid and atom_count > 0
    stats["sha256_16"] = digest.hexdigest()[:16]
    return stats


def _record(line: str) -> str:
    return line[:6].strip().upper()


def _first_model_atom_lines(path_like: str | Path) -> list[str]:
    path = _resolve(path_like)
    lines: list[str] = []
    in_first_model = False
    seen_model = False
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            rec = _record(line)
            if rec == "MODEL":
                if seen_model:
                    break
                seen_model = True
                in_first_model = True
                continue
            if rec == "END" and in_first_model:
                break
            if rec in {"ATOM", "HETATM"} and (in_first_model or not seen_model):
                lines.append(line.rstrip("\n"))
    return lines


def _float_slice(line: str, start: int, end: int, fallback_index: int) -> float | None:
    try:
        value = float(line[start:end].strip())
    except ValueError:
        fields = line.split()
        if len(fields) <= fallback_index:
            return None
        try:
            value = float(fields[fallback_index])
        except ValueError:
            return None
    return value if math.isfinite(value) else None


def _atom_from_line(line: str, serial_index: int) -> dict[str, Any] | None:
    x = _float_slice(line, 30, 38, 6)
    y = _float_slice(line, 38, 46, 7)
    z = _float_slice(line, 46, 54, 8)
    if x is None or y is None or z is None:
        return None
    record = _record(line)
    atom_name = line[12:16].strip() if len(line) >= 16 else ""
    res_name = line[17:20].strip() if len(line) >= 20 else ""
    chain = (line[21].strip() if len(line) > 21 else "") or "_"
    resseq = line[22:26].strip() if len(line) >= 26 else str(serial_index)
    icode = line[26].strip() if len(line) > 26 else ""
    return {
        "record": record,
        "atom_name": atom_name,
        "res_name": res_name,
        "chain": chain,
        "resseq": resseq,
        "icode": icode,
        "coord": np.array([x, y, z], dtype=float),
        "serial_index": serial_index,
    }


def _parse_atoms(path_like: str | Path) -> list[dict[str, Any]]:
    atoms: list[dict[str, Any]] = []
    for index, line in enumerate(_first_model_atom_lines(path_like), start=1):
        atom = _atom_from_line(line, index)
        if atom is not None:
            atoms.append(atom)
    return atoms


def _ca_atoms(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [atom for atom in atoms if atom["record"] == "ATOM" and atom["atom_name"] == "CA"]


def _ligand_atoms(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [atom for atom in atoms if atom["record"] == "HETATM" and atom["res_name"].upper() not in WATER_NAMES]


def _ca_key(atom: dict[str, Any]) -> tuple[str, str, str, str]:
    return (atom["chain"], atom["resseq"], atom["icode"], atom["atom_name"])


def _ligand_key(atom: dict[str, Any]) -> tuple[str, str, str, str, int]:
    return (atom["chain"], atom["resseq"], atom["res_name"], atom["atom_name"], atom["serial_index"])


def _protein_key(atom: dict[str, Any]) -> tuple[str, str, str, str]:
    return (atom["chain"], atom["resseq"], atom["icode"], atom["atom_name"])


def _matched_ca(pred_atoms: list[dict[str, Any]], native_atoms: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    pred_ca = _ca_atoms(pred_atoms)
    native_ca = _ca_atoms(native_atoms)
    pred_by_key = {_ca_key(atom): atom for atom in pred_ca}
    native_by_key = {_ca_key(atom): atom for atom in native_ca}
    keys = [key for key in native_by_key if key in pred_by_key]
    if len(keys) >= min(3, min(len(pred_ca), len(native_ca))):
        return [pred_by_key[key] for key in keys], [native_by_key[key] for key in keys], "chain_residue_ca_key"
    count = min(len(pred_ca), len(native_ca))
    return pred_ca[:count], native_ca[:count], "ordered_ca_fallback"


def _kabsch(pred: np.ndarray, native: np.ndarray) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    pred_centroid = pred.mean(axis=0)
    native_centroid = native.mean(axis=0)
    pred_centered = pred - pred_centroid
    native_centered = native - native_centroid
    cov = pred_centered.T @ native_centered
    left, _, right_t = np.linalg.svd(cov)
    rotation = right_t.T @ left.T
    if np.linalg.det(rotation) < 0:
        right_t[-1, :] *= -1
        rotation = right_t.T @ left.T
    aligned = pred_centered @ rotation + native_centroid
    diff = aligned - native
    rmsd = math.sqrt(float(np.mean(np.sum(diff * diff, axis=1))))
    return aligned, rmsd, rotation, pred_centroid


def _apply_transform(coord: np.ndarray, rotation: np.ndarray, pred_centroid: np.ndarray, native_centroid: np.ndarray) -> np.ndarray:
    return (coord - pred_centroid) @ rotation + native_centroid


def _gdt(distances: np.ndarray, thresholds: list[float]) -> float:
    if distances.size == 0:
        return 0.0
    return float(np.mean([np.mean(distances <= threshold) for threshold in thresholds]) * 100.0)


def _tm_score_proxy(rmsd: float, count: int) -> float:
    d0 = max(0.5, 1.24 * max(count - 15, 1) ** (1.0 / 3.0) - 1.8)
    return float(1.0 / (1.0 + (rmsd / d0) ** 2))


def _contact_set(ca_by_key: dict[tuple[str, str, str, str], np.ndarray], cutoff: float = 12.0) -> set[tuple[tuple[str, str, str, str], tuple[str, str, str, str]]]:
    keys = sorted(ca_by_key)
    contacts: set[tuple[tuple[str, str, str, str], tuple[str, str, str, str]]] = set()
    for left_index, left_key in enumerate(keys):
        for right_key in keys[left_index + 1 :]:
            if left_key[0] == right_key[0]:
                continue
            distance = float(np.linalg.norm(ca_by_key[left_key] - ca_by_key[right_key]))
            if distance <= cutoff:
                contacts.add((left_key, right_key))
    return contacts


def _ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return ""
    return f"{numerator / denominator:.3f}"


def _ligand_rmsd(
    pred_atoms: list[dict[str, Any]],
    native_atoms: list[dict[str, Any]],
    rotation: np.ndarray,
    pred_centroid: np.ndarray,
    native_centroid: np.ndarray,
) -> tuple[str, str, str]:
    pred_ligands = _ligand_atoms(pred_atoms)
    native_ligands = _ligand_atoms(native_atoms)
    if not pred_ligands or not native_ligands:
        return "", "", ""
    pred_by_name = {(atom["chain"], atom["resseq"], atom["res_name"], atom["atom_name"]): atom for atom in pred_ligands}
    native_by_name = {(atom["chain"], atom["resseq"], atom["res_name"], atom["atom_name"]): atom for atom in native_ligands}
    keys = [key for key in native_by_name if key in pred_by_name]
    if not keys:
        count = min(len(pred_ligands), len(native_ligands))
        matched_pred = pred_ligands[:count]
        matched_native = native_ligands[:count]
    else:
        matched_pred = [pred_by_name[key] for key in keys]
        matched_native = [native_by_name[key] for key in keys]
    if not matched_pred:
        return "", "", ""
    pred_coords = np.stack([
        _apply_transform(atom["coord"], rotation, pred_centroid, native_centroid) for atom in matched_pred
    ])
    native_coords = np.stack([atom["coord"] for atom in matched_native])
    diff = pred_coords - native_coords
    rmsd = math.sqrt(float(np.mean(np.sum(diff * diff, axis=1))))
    score = 1.0 / (1.0 + (rmsd / 2.0) ** 2)
    return f"{rmsd:.3f}", f"{score:.3f}", f"{rmsd:.3f}"


def _pli_proxy(
    pred_atoms: list[dict[str, Any]],
    native_atoms: list[dict[str, Any]],
    rotation: np.ndarray,
    pred_centroid: np.ndarray,
    native_centroid: np.ndarray,
    cutoff: float = 6.0,
) -> str:
    pred_ligands = _ligand_atoms(pred_atoms)
    native_ligands = _ligand_atoms(native_atoms)
    pred_protein = [atom for atom in pred_atoms if atom["record"] == "ATOM" and atom["atom_name"] == "CA"]
    native_protein = [atom for atom in native_atoms if atom["record"] == "ATOM" and atom["atom_name"] == "CA"]
    if not pred_ligands or not native_ligands or not pred_protein or not native_protein:
        return ""
    pred_contacts: set[tuple[tuple[str, str, str, str, int], tuple[str, str, str, str]]] = set()
    native_contacts: set[tuple[tuple[str, str, str, str, int], tuple[str, str, str, str]]] = set()
    for ligand in pred_ligands:
        ligand_coord = _apply_transform(ligand["coord"], rotation, pred_centroid, native_centroid)
        for protein in pred_protein:
            protein_coord = _apply_transform(protein["coord"], rotation, pred_centroid, native_centroid)
            if float(np.linalg.norm(ligand_coord - protein_coord)) <= cutoff:
                pred_contacts.add((_ligand_key(ligand), _protein_key(protein)))
    for ligand in native_ligands:
        for protein in native_protein:
            if float(np.linalg.norm(ligand["coord"] - protein["coord"])) <= cutoff:
                native_contacts.add((_ligand_key(ligand), _protein_key(protein)))
    if not pred_contacts and not native_contacts:
        return ""
    shared = len(pred_contacts & native_contacts)
    precision = shared / len(pred_contacts) if pred_contacts else 0.0
    recall = shared / len(native_contacts) if native_contacts else 0.0
    return f"{(precision + recall) / 2.0:.3f}"


def _metric_input_required(raw: dict[str, Any]) -> bool:
    role = _text(raw.get("role"))
    if role != "same_run_step_candidate":
        return True
    if _bool(raw.get("exists")) and _bool(raw.get("coordinate_valid")):
        return True
    path = _text(raw.get("path"))
    if not path:
        return False
    stats = _pdb_stats(path)
    return bool(stats["exists"] and stats["coordinate_valid"])


def _score_candidate(raw: dict[str, Any], native_pdb: str, fallback_rank: int) -> dict[str, Any]:
    target_id = _text(raw.get("target_id")).upper()
    candidate_path = _text(raw.get("path"))
    candidate_stats = _pdb_stats(candidate_path) if candidate_path else {"exists": False, "coordinate_valid": False, "sha256_16": "", "atom_count": 0}
    native_stats = _pdb_stats(native_pdb) if native_pdb else {"exists": False, "coordinate_valid": False, "sha256_16": "", "atom_count": 0}
    blockers: list[str] = []
    metrics = {
        "native_metric_candidate": "",
        "gdt_ts_proxy": "",
        "gdt_ha_proxy": "",
        "ca_lddt_proxy": "",
        "tm_score_proxy": "",
        "ca_rmsd_angstrom": "",
        "ca_match_count": 0,
        "ca_match_basis": "",
        "interface_contact_recall_proxy": "",
        "interface_contact_precision_proxy": "",
        "dockq_proxy": "",
        "ligand_rmsd_proxy": "",
        "lddt_pli_proxy": "",
        "bisyrmsd_proxy": "",
    }
    if not candidate_path:
        blockers.append("candidate_path_missing")
    if not candidate_stats["exists"]:
        blockers.append("candidate_pdb_missing")
    if candidate_stats["exists"] and not candidate_stats["coordinate_valid"]:
        blockers.append("candidate_coordinates_invalid")
    if not native_pdb:
        blockers.append("native_pdb_missing")
    if not native_stats["exists"]:
        blockers.append("native_pdb_missing")
    if native_stats["exists"] and not native_stats["coordinate_valid"]:
        blockers.append("native_coordinates_invalid")
    if not blockers:
        pred_atoms = _parse_atoms(candidate_path)
        native_atoms = _parse_atoms(native_pdb)
        pred_ca, native_ca, match_basis = _matched_ca(pred_atoms, native_atoms)
        if len(pred_ca) < 3:
            blockers.append("ca_match_count_below_minimum")
        else:
            pred_coords = np.stack([atom["coord"] for atom in pred_ca])
            native_coords = np.stack([atom["coord"] for atom in native_ca])
            aligned_pred, rmsd, rotation, pred_centroid = _kabsch(pred_coords, native_coords)
            native_centroid = native_coords.mean(axis=0)
            distances = np.linalg.norm(aligned_pred - native_coords, axis=1)
            gdt_ts = _gdt(distances, [1.0, 2.0, 4.0, 8.0])
            gdt_ha = _gdt(distances, [0.5, 1.0, 2.0, 4.0])
            ca_lddt = _gdt(distances, [0.5, 1.0, 2.0, 4.0]) / 100.0
            tm_score = _tm_score_proxy(rmsd, len(pred_ca))
            pred_ca_by_key = {
                _ca_key(atom): aligned_pred[index]
                for index, atom in enumerate(pred_ca)
            }
            native_ca_by_key = {
                _ca_key(atom): native_ca[index]["coord"]
                for index, atom in enumerate(native_ca)
            }
            pred_contacts = _contact_set(pred_ca_by_key)
            native_contacts = _contact_set(native_ca_by_key)
            shared_contacts = len(pred_contacts & native_contacts)
            interface_recall = _ratio(shared_contacts, len(native_contacts))
            interface_precision = _ratio(shared_contacts, len(pred_contacts))
            dockq = ""
            if native_contacts or pred_contacts:
                fnat = shared_contacts / len(native_contacts) if native_contacts else 0.0
                irms_term = 1.0 / (1.0 + (rmsd / 1.5) ** 2)
                lrms_term = 1.0 / (1.0 + (rmsd / 8.5) ** 2)
                dockq = f"{((fnat + irms_term + lrms_term) / 3.0):.3f}"
            ligand_rmsd, lddt_pli, bisyrmsd = _ligand_rmsd(
                pred_atoms, native_atoms, rotation, pred_centroid, native_centroid
            )
            pli_contact = _pli_proxy(pred_atoms, native_atoms, rotation, pred_centroid, native_centroid)
            if pli_contact:
                lddt_pli = pli_contact
            metrics.update(
                {
                    "native_metric_candidate": f"{gdt_ts:.3f}",
                    "gdt_ts_proxy": f"{gdt_ts:.3f}",
                    "gdt_ha_proxy": f"{gdt_ha:.3f}",
                    "ca_lddt_proxy": f"{ca_lddt:.3f}",
                    "tm_score_proxy": f"{tm_score:.3f}",
                    "ca_rmsd_angstrom": f"{rmsd:.3f}",
                    "ca_match_count": len(pred_ca),
                    "ca_match_basis": match_basis,
                    "interface_contact_recall_proxy": interface_recall,
                    "interface_contact_precision_proxy": interface_precision,
                    "dockq_proxy": dockq,
                    "ligand_rmsd_proxy": ligand_rmsd,
                    "lddt_pli_proxy": lddt_pli,
                    "bisyrmsd_proxy": bisyrmsd,
                }
            )
    status = "metric_ready" if _text(metrics["native_metric_candidate"]) and not blockers else "blocked"
    notes = _text(raw.get("notes")) or "local native metric candidate for model-selection review"
    if _text(metrics.get("ca_match_basis")):
        notes = f"{notes}; ca_match_basis={metrics['ca_match_basis']}"
    return {
        "target_id": target_id,
        "benchmark_id": _text(raw.get("benchmark_id")),
        "scope": _text(raw.get("scope")),
        "candidate_rank": _int(raw.get("candidate_rank")) or fallback_rank,
        "role": _text(raw.get("role")),
        "path": _artifact(candidate_path) if candidate_path else "",
        "native_pdb": _artifact(native_pdb) if native_pdb else "",
        "exists": bool(candidate_stats["exists"]),
        "coordinate_valid": bool(candidate_stats["coordinate_valid"]),
        "native_exists": bool(native_stats["exists"]),
        "native_coordinate_valid": bool(native_stats["coordinate_valid"]),
        "sha256_16": _text(candidate_stats.get("sha256_16")) or _text(raw.get("sha256_16")),
        **metrics,
        "metric_status": status,
        "blockers": ",".join(dict.fromkeys(blockers)),
        "notes": notes,
    }


def _candidate_rows_by_target(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped = payload.get("candidate_rows_by_target")
    if not isinstance(grouped, dict):
        return {}
    return {
        _text(target).upper(): [row for row in rows if isinstance(row, dict)]
        for target, rows in grouped.items()
        if isinstance(rows, list)
    }


def _native_by_target(seed_rows: list[dict[str, str]]) -> dict[str, str]:
    return {_text(row.get("target_id")).upper(): _text(row.get("native_pdb")) for row in seed_rows}


def _build_target_metrics(
    target_id: str,
    raw_rows: list[dict[str, Any]],
    native_pdb: str,
    row_rank: int,
    metric_dir: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metric_inputs = [raw for raw in raw_rows if _metric_input_required(raw)]
    metric_rows = [_score_candidate(raw, native_pdb, index) for index, raw in enumerate(metric_inputs, start=1)]
    ready_rows = [row for row in metric_rows if row["metric_status"] == "metric_ready"]
    selected_rows = [
        row
        for row in ready_rows
        if _text(row.get("role")) in {"selected_prediction", "selected_prediction_copy"}
    ]
    selected_metric = _text(selected_rows[0].get("native_metric_candidate")) if selected_rows else ""
    best_row = max(ready_rows, key=lambda row: float(row["native_metric_candidate"]), default={})
    best_metric = _text(best_row.get("native_metric_candidate"))
    best_rank = _text(best_row.get("candidate_rank"))
    native_stats = _pdb_stats(native_pdb) if native_pdb else {"exists": False}
    blockers: list[str] = []
    if not raw_rows:
        blockers.append("candidate_rows_missing")
    if not native_pdb or not native_stats["exists"]:
        blockers.append("native_pdb_missing")
    if len(ready_rows) < len(metric_rows):
        blockers.append("native_metric_inputs_blocked")
    if len(ready_rows) < 5:
        blockers.append("top5_native_metric_candidates_missing")
    if not selected_metric:
        blockers.append("selected_native_metric_candidate_missing")
    if not best_metric:
        blockers.append("best_native_metric_candidate_missing")
    status = "native_oracle_metric_candidates_ready_for_review" if not blockers else "blocked_native_metric_inputs"
    metric_csv = _resolve(metric_dir) / f"{row_rank:02d}_{_safe_name(target_id)}" / "native_metric_candidates.csv"
    _write_csv(metric_csv, metric_rows, CANDIDATE_COLUMNS)
    first = metric_rows[0] if metric_rows else {}
    summary_row = {
        "row_rank": row_rank,
        "target_id": target_id,
        "benchmark_id": _text(first.get("benchmark_id")),
        "scope": _text(first.get("scope")),
        "metric_status": status,
        "metric_candidate_csv": _artifact(metric_csv),
        "native_pdb": _artifact(native_pdb) if native_pdb else "",
        "native_exists": bool(native_stats["exists"]),
        "candidate_count": len(metric_rows),
        "metric_candidate_count": len(ready_rows),
        "selected_native_metric_candidate": selected_metric or "REQUIRES_NATIVE_ORACLE",
        "best_native_metric_candidate": best_metric or "REQUIRES_NATIVE_ORACLE",
        "best_model_rank_candidate": best_rank or "REQUIRES_NATIVE_ORACLE",
        "next_action": (
            "feed native metrics into calibration ledger, then keep no-leak provenance and operator fill separate"
            if status == "native_oracle_metric_candidates_ready_for_review"
            else "repair native/candidate PDB inputs before native metric review"
        ),
        "blockers": ",".join(dict.fromkeys(blockers)),
    }
    return summary_row, metric_rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    seed_rows, seed_blockers = _read_csv(args.seed_manifest_csv)
    ledger_payload = _read_json(args.calibration_ledger_json)
    grouped = _candidate_rows_by_target(ledger_payload)
    native_by_target = _native_by_target(seed_rows)
    rows: list[dict[str, Any]] = []
    candidate_rows_by_target: dict[str, list[dict[str, Any]]] = {}
    for index, (target_id, raw_rows) in enumerate(grouped.items(), start=1):
        summary_row, metric_rows = _build_target_metrics(
            target_id, raw_rows, native_by_target.get(target_id, ""), index, args.metric_dir
        )
        rows.append(summary_row)
        candidate_rows_by_target[target_id] = metric_rows
    blocked_count = sum(1 for row in rows if row["metric_status"] != "native_oracle_metric_candidates_ready_for_review")
    if seed_blockers:
        status = "blocked_missing_seed_manifest"
    elif not _resolve(args.calibration_ledger_json).exists():
        status = "blocked_missing_calibration_ledger"
    elif not rows:
        status = "blocked_missing_candidate_rows"
    elif blocked_count:
        status = "blocked_native_metric_inputs"
    else:
        status = "native_oracle_metric_candidates_ready_for_review"
    first_open = next(
        (row for row in rows if row["metric_status"] != "native_oracle_metric_candidates_ready_for_review"),
        rows[0] if rows else {},
    )
    summary = {
        "packet_type": "casp17_historical_seed_native_oracle_metric_candidates",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "native_metric_candidate_status": status,
        "seed_manifest_csv": _artifact(args.seed_manifest_csv),
        "calibration_ledger_json": _artifact(args.calibration_ledger_json),
        "metric_dir": _artifact(args.metric_dir),
        "seed_row_count": len(rows),
        "candidate_count": sum(_int(row.get("candidate_count")) for row in rows),
        "metric_candidate_count": sum(_int(row.get("metric_candidate_count")) for row in rows),
        "top5_native_metric_ready_count": sum(1 for row in rows if _int(row.get("metric_candidate_count")) >= 5),
        "selected_native_metric_candidate_count": sum(
            1 for row in rows if not _text(row.get("selected_native_metric_candidate")).startswith("REQUIRES")
        ),
        "best_native_metric_candidate_count": sum(
            1 for row in rows if not _text(row.get("best_native_metric_candidate")).startswith("REQUIRES")
        ),
        "blocked_candidate_input_count": blocked_count,
        "first_open_target_id": _text(first_open.get("target_id")),
        "first_next_action": _text(first_open.get("next_action")) or "provide seed manifest and calibration candidate rows",
        "input_blockers": ",".join(seed_blockers),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "candidate_rows_by_target": candidate_rows_by_target}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Native Oracle Metric Candidates",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- native_metric_candidate_status: `{summary['native_metric_candidate_status']}`",
        f"- seed rows/candidates/metric-ready: `{summary['seed_row_count']}/{summary['candidate_count']}/{summary['metric_candidate_count']}`",
        f"- top5 native-ready/selected/best/blocked: `{summary['top5_native_metric_ready_count']}/{summary['selected_native_metric_candidate_count']}/{summary['best_native_metric_candidate_count']}/{summary['blocked_candidate_input_count']}`",
        f"- first open: `{summary['first_open_target_id'] or '-'}`",
        f"- next action: {summary['first_next_action'] or '-'}",
        "",
        "## Seed Rows",
        "",
        "| rank | target | scope | status | candidates | metric-ready | selected native | best native | best rank | blockers |",
        "| ---: | --- | --- | --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['target_id']}` | `{row['scope']}` | `{row['metric_status']}` | "
            f"{row['candidate_count']} | {row['metric_candidate_count']} | "
            f"`{row['selected_native_metric_candidate']}` | `{row['best_native_metric_candidate']}` | "
            f"`{row['best_model_rank_candidate']}` | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked_missing_candidate_rows` | 0 | 0 | - | - | - | provide inputs |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed native oracle metric candidates.")
    parser.add_argument("--seed-manifest-csv", default=DEFAULT_SEED_MANIFEST_CSV)
    parser.add_argument("--calibration-ledger-json", default=DEFAULT_CALIBRATION_LEDGER_JSON)
    parser.add_argument("--metric-dir", default=DEFAULT_METRIC_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
