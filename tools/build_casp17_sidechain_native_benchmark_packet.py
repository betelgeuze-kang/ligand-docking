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

DEFAULT_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_draft_from_operator_current.csv"
DEFAULT_OUT_JSON = "runs/casp17_sidechain_native_benchmark_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_sidechain_native_benchmark_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_sidechain_native_benchmark_packet_current.md"
DEFAULT_OUT_WORKORDER_JSON = "runs/casp17_sidechain_native_input_workorder_current.json"
DEFAULT_OUT_WORKORDER_CSV = "runs/casp17_sidechain_native_input_workorder_current.csv"
DEFAULT_OUT_WORKORDER_MD = "runs/casp17_sidechain_native_input_workorder_current.md"


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


def _row_blockers(row: dict[str, Any]) -> set[str]:
    return {item for item in str(row.get("blockers", "")).split(",") if item}


def _blocker_histogram(rows: list[dict[str, Any]], manifest_blockers: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for blocker in manifest_blockers:
        counts[blocker] = counts.get(blocker, 0) + 1
    for row in rows:
        for blocker in _row_blockers(row):
            counts[blocker] = counts.get(blocker, 0) + 1
    return dict(sorted(counts.items()))


def _first_next_action(first_blocked: dict[str, Any], manifest_blockers: list[str]) -> str:
    if manifest_blockers:
        return "Create or populate the no-leak historical benchmark manifest, then rerun this packet."
    blockers = _row_blockers(first_blocked)
    if not blockers:
        return "No sidechain-native benchmark action is open."
    actions: list[str] = []
    if "leakage_clearance_missing_or_not_clear" in blockers:
        actions.append("replace placeholder leakage_clearance with operator-confirmed no_leak provenance")
    if {"prediction_pdb_missing", "native_pdb_missing"} & blockers:
        actions.append("place the cleared prediction/native PDB files for this benchmark row")
    if {
        "matched_ca_count_below_threshold",
        "prediction_ca_coverage_below_threshold",
        "native_ca_coverage_below_threshold",
        "prediction_native_chain_ids_mismatch",
        "complex_scope_requires_multichain",
        "monomer_scope_requires_single_chain",
        "prediction_native_residue_identity_mismatch",
        "matched_sidechain_atom_count_below_threshold",
        "native_sidechain_coverage_below_threshold",
    } & blockers:
        actions.append("repair chain, residue, atom, and sidechain exactness before native scoring")
    if {"sidechain_rmsd_above_threshold", "sidechain_lddt_below_threshold"} & blockers:
        actions.append("tune sidechain placement against RMSD/lDDT thresholds")
    return "; ".join(actions) + "." if actions else "Resolve the first blocked sidechain-native benchmark row."


def _workorder_action(
    *,
    action_rank: int,
    row: dict[str, Any],
    evidence_class: str,
    evidence_item: str,
    source_column: str,
    required_value: str,
    current_value: str,
    destination_path: str,
    blocker: str,
    next_action: str,
) -> dict[str, Any]:
    benchmark_id = _text(row.get("benchmark_id")) or "manifest"
    return {
        "action_rank": action_rank,
        "action_id": f"{benchmark_id}:{evidence_item}",
        "benchmark_id": benchmark_id,
        "target_id": _text(row.get("target_id")),
        "scope": _text(row.get("scope")) or "historical",
        "evidence_class": evidence_class,
        "evidence_item": evidence_item,
        "source_column": source_column,
        "required_value": required_value,
        "current_value": current_value,
        "destination_path": destination_path,
        "action_status": "open" if blocker else "closed",
        "blocker": blocker,
        "next_action": next_action,
    }


def _workorder_rows(
    rows: list[dict[str, Any]],
    manifest_blockers: list[str],
    *,
    max_sidechain_rmsd_A: float,
    min_sidechain_lddt_proxy: float,
) -> list[dict[str, Any]]:
    if manifest_blockers:
        return [
            _workorder_action(
                action_rank=1,
                row={"benchmark_id": "manifest", "target_id": "", "scope": "historical"},
                evidence_class="manifest",
                evidence_item="manifest_csv",
                source_column="manifest_csv",
                required_value="populated no-leak historical benchmark manifest CSV",
                current_value=",".join(manifest_blockers),
                destination_path=DEFAULT_MANIFEST_CSV,
                blocker=",".join(manifest_blockers),
                next_action="Create or populate the no-leak historical benchmark manifest, then rerun this packet.",
            )
        ]

    actions: list[dict[str, Any]] = []
    exactness_blockers = {
        "matched_ca_count_below_threshold",
        "prediction_ca_coverage_below_threshold",
        "native_ca_coverage_below_threshold",
        "prediction_native_chain_ids_mismatch",
        "complex_scope_requires_multichain",
        "monomer_scope_requires_single_chain",
        "prediction_native_residue_identity_mismatch",
        "matched_sidechain_atom_count_below_threshold",
        "native_sidechain_coverage_below_threshold",
    }
    metric_blockers = {"sidechain_rmsd_above_threshold", "sidechain_lddt_below_threshold"}
    for row in rows:
        blockers = _row_blockers(row)
        if "leakage_clearance_missing_or_not_clear" in blockers:
            actions.append(
                _workorder_action(
                    action_rank=len(actions) + 1,
                    row=row,
                    evidence_class="provenance",
                    evidence_item="leakage_clearance",
                    source_column="leakage_clearance",
                    required_value="operator-confirmed no_leak provenance",
                    current_value=_text(row.get("leakage_clearance")),
                    destination_path="manifest row leakage_clearance",
                    blocker="leakage_clearance_missing_or_not_clear",
                    next_action="Replace placeholder leakage_clearance with operator-confirmed no_leak provenance.",
                )
            )
        if "prediction_pdb_missing" in blockers:
            actions.append(
                _workorder_action(
                    action_rank=len(actions) + 1,
                    row=row,
                    evidence_class="core_file",
                    evidence_item="prediction_pdb",
                    source_column="prediction_pdb",
                    required_value="internal prediction PDB generated before native release",
                    current_value=_text(row.get("prediction_pdb")),
                    destination_path=_text(row.get("prediction_pdb")),
                    blocker="prediction_pdb_missing",
                    next_action="Place the internal prediction PDB at the manifest prediction_pdb path.",
                )
            )
        if "native_pdb_missing" in blockers:
            actions.append(
                _workorder_action(
                    action_rank=len(actions) + 1,
                    row=row,
                    evidence_class="core_file",
                    evidence_item="native_pdb",
                    source_column="native_pdb",
                    required_value="operator-cleared historical native PDB",
                    current_value=_text(row.get("native_pdb")),
                    destination_path=_text(row.get("native_pdb")),
                    blocker="native_pdb_missing",
                    next_action="Place the operator-cleared historical native PDB at the manifest native_pdb path.",
                )
            )
        exactness_open = sorted(exactness_blockers & blockers)
        if exactness_open:
            actions.append(
                _workorder_action(
                    action_rank=len(actions) + 1,
                    row=row,
                    evidence_class="exactness_gate",
                    evidence_item="chain_residue_sidechain_exactness",
                    source_column="prediction_pdb/native_pdb",
                    required_value="matching chain IDs, residue identity, CA coverage, and sidechain atom overlap",
                    current_value=(
                        f"matched_ca={row.get('matched_ca_count', 0)};"
                        f"matched_sidechain={row.get('matched_sidechain_atom_count', 0)}"
                    ),
                    destination_path="repair prediction/native PDB pair",
                    blocker=",".join(exactness_open),
                    next_action="Repair chain, residue, atom, and sidechain exactness before native scoring.",
                )
            )
        metric_open = sorted(metric_blockers & blockers)
        if metric_open:
            actions.append(
                _workorder_action(
                    action_rank=len(actions) + 1,
                    row=row,
                    evidence_class="metric_gate",
                    evidence_item="sidechain_rmsd_lddt",
                    source_column="sidechain_rmsd_A/sidechain_lddt_proxy",
                    required_value=(
                        f"RMSD <= {max_sidechain_rmsd_A}; "
                        f"lDDT >= {min_sidechain_lddt_proxy}"
                    ),
                    current_value=(
                        f"RMSD={row.get('sidechain_rmsd_A', 0.0)};"
                        f"lDDT={row.get('sidechain_lddt_proxy', 0.0)}"
                    ),
                    destination_path="sidechain refinement/tuning",
                    blocker=",".join(metric_open),
                    next_action="Tune sidechain placement against RMSD and lDDT thresholds.",
                )
            )
    return actions


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    manifest_rows, manifest_blockers = _read_manifest(args.manifest_csv)
    rows = [_score_one(row, args) for row in manifest_rows]
    pass_count = sum(1 for row in rows if row["sidechain_native_status"] == "pass")
    blocked_count = len(rows) - pass_count
    if manifest_blockers:
        blocked_count = max(blocked_count, 1)
    first_blocked = next((row for row in rows if row["sidechain_native_status"] != "pass"), {})
    blocker_histogram = _blocker_histogram(rows, manifest_blockers)
    leakage_blocked = sum(
        1 for row in rows if "leakage_clearance_missing_or_not_clear" in _row_blockers(row)
    )
    prediction_missing = sum(1 for row in rows if "prediction_pdb_missing" in _row_blockers(row))
    native_missing = sum(1 for row in rows if "native_pdb_missing" in _row_blockers(row))
    core_input_blocked = sum(
        1
        for row in rows
        if {"leakage_clearance_missing_or_not_clear", "prediction_pdb_missing", "native_pdb_missing"}
        & _row_blockers(row)
    )
    exactness_blockers = {
        "matched_ca_count_below_threshold",
        "prediction_ca_coverage_below_threshold",
        "native_ca_coverage_below_threshold",
        "prediction_native_chain_ids_mismatch",
        "complex_scope_requires_multichain",
        "monomer_scope_requires_single_chain",
        "prediction_native_residue_identity_mismatch",
        "matched_sidechain_atom_count_below_threshold",
        "native_sidechain_coverage_below_threshold",
    }
    exactness_blocked = sum(1 for row in rows if exactness_blockers & _row_blockers(row))
    metric_blocked = sum(
        1
        for row in rows
        if {"sidechain_rmsd_above_threshold", "sidechain_lddt_below_threshold"} & _row_blockers(row)
    )
    workorder_rows = _workorder_rows(
        rows,
        manifest_blockers,
        max_sidechain_rmsd_A=float(args.max_sidechain_rmsd_A),
        min_sidechain_lddt_proxy=float(args.min_sidechain_lddt_proxy),
    )
    open_workorder_rows = [row for row in workorder_rows if row["action_status"] != "closed"]
    workorder_counts: dict[str, int] = {}
    for row in open_workorder_rows:
        klass = str(row.get("evidence_class", ""))
        workorder_counts[klass] = workorder_counts.get(klass, 0) + 1
    summary = {
        "packet_type": "casp17_sidechain_native_benchmark_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "manifest_csv": _artifact(args.manifest_csv),
        "benchmark_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": blocked_count,
        "core_input_blocked_count": core_input_blocked,
        "leakage_clearance_blocked_count": leakage_blocked,
        "prediction_pdb_missing_count": prediction_missing,
        "native_pdb_missing_count": native_missing,
        "missing_core_file_count": prediction_missing + native_missing,
        "exactness_blocked_count": exactness_blocked,
        "metric_threshold_blocked_count": metric_blocked,
        "first_blocked_benchmark_id": str(first_blocked.get("benchmark_id", "")),
        "first_blocked_target_id": str(first_blocked.get("target_id", "")),
        "first_blocked_blockers": str(first_blocked.get("blockers", "")),
        "first_open_next_action": _first_next_action(first_blocked, manifest_blockers),
        "blocker_histogram": blocker_histogram,
        "workorder_json": _artifact(args.out_workorder_json),
        "workorder_csv": _artifact(args.out_workorder_csv),
        "workorder_md": _artifact(args.out_workorder_md),
        "workorder_action_count": len(workorder_rows),
        "open_workorder_action_count": len(open_workorder_rows),
        "workorder_action_counts_by_class": dict(sorted(workorder_counts.items())),
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
    return {"summary": summary, "rows": rows, "workorder_rows": workorder_rows}


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
        f"- core input blocked/leakage/prediction/native/missing files: `{summary['core_input_blocked_count']}/{summary['leakage_clearance_blocked_count']}/{summary['prediction_pdb_missing_count']}/{summary['native_pdb_missing_count']}/{summary['missing_core_file_count']}`",
        f"- exactness/metric blocked: `{summary['exactness_blocked_count']}/{summary['metric_threshold_blocked_count']}`",
        f"- first_blocked: `{summary['first_blocked_benchmark_id'] or '-'}` / `{summary['first_blocked_target_id'] or '-'}`",
        f"- first_blockers: `{summary['first_blocked_blockers'] or summary['manifest_blockers'] or '-'}`",
        f"- first_next_action: {summary['first_open_next_action']}",
        f"- blocker_histogram: `{summary['blocker_histogram']}`",
        f"- workorder actions/open: `{summary['workorder_action_count']}/{summary['open_workorder_action_count']}`",
        f"- workorder by class: `{summary['workorder_action_counts_by_class']}`",
        f"- workorder files: `{summary['workorder_json']}` `{summary['workorder_csv']}` `{summary['workorder_md']}`",
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


def _write_workorder_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    rows = payload["workorder_rows"]
    lines = [
        "# CASP17 Sidechain Native Input Workorder",
        "",
        "This local workorder separates no-leak sidechain/native benchmark gaps into provenance, core-file, exactness, and metric actions.",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- manifest_csv: `{summary['manifest_csv']}`",
        f"- benchmark status: `{summary['sidechain_native_benchmark_status']}`",
        f"- benchmark rows pass/blocked/total: `{summary['pass_count']}/{summary['blocked_count']}/{summary['benchmark_count']}`",
        f"- workorder actions/open: `{summary['workorder_action_count']}/{summary['open_workorder_action_count']}`",
        f"- action counts by class: `{summary['workorder_action_counts_by_class']}`",
        f"- first action: `{summary['first_blocked_benchmark_id'] or '-'}` `{summary['first_open_next_action']}`",
        "",
        "| rank | benchmark | target | class | item | destination | blocker | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows[:120]:
        lines.append(
            f"| {row['action_rank']} | `{row['benchmark_id']}` | `{row['target_id']}` | "
            f"`{row['evidence_class']}` | `{row['evidence_item']}` | `{row['destination_path'] or '-'}` | "
            f"`{row['blocker'] or '-'}` | {row['next_action'] or '-'} |"
        )
    if not rows:
        lines.append("| 0 | - | - | - | - | - | - | No open sidechain-native workorder actions. |")
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
    parser.add_argument("--out-workorder-json", default=DEFAULT_OUT_WORKORDER_JSON)
    parser.add_argument("--out-workorder-csv", default=DEFAULT_OUT_WORKORDER_CSV)
    parser.add_argument("--out-workorder-md", default=DEFAULT_OUT_WORKORDER_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    _write_json(args.out_workorder_json, {"summary": payload["summary"], "rows": payload["workorder_rows"]})
    _write_csv(args.out_workorder_csv, payload["workorder_rows"])
    _write_workorder_md(args.out_workorder_md, payload)
    if args.fail_on_blocked and payload["summary"]["blocked_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
