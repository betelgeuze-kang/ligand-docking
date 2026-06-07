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
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_FREEZE_PACKET_JSON = "runs/gpcr_positive_coverage_freeze_packet_current.json"
DEFAULT_BASE_PROFILE_JSON = "config/ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k.json"
DEFAULT_CANDIDATES_CSV = "config/gpcr_non_adrb2_positive_candidates_v1.csv"
DEFAULT_OUT_DIR = "runs/gpcr_frozen_candidate_profile_support_current"
POCKET_VALIDATION_TOLERANCE_A = 0.25


def _resolve(path_like: str | Path | None) -> Path | None:
    if path_like is None or str(path_like).strip() == "":
        return None
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload if isinstance(payload, dict) else {}


def _read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _split_list(value: Any) -> set[str]:
    return {part.strip() for part in str(value or "").split(",") if part.strip()}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "pass", "passed"}


def _has_number(value: Any) -> bool:
    try:
        if _text(value) == "":
            return False
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _as_float(value: Any) -> float | None:
    try:
        if _text(value) == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _candidate_rows(freeze_packet: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = freeze_packet.get("accepted_candidate_rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raw_rows = freeze_packet.get("candidate_rows")
    if not isinstance(raw_rows, list):
        return []

    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        target = _text(row.get("target"))
        ligand_id = _text(row.get("ligand_id"))
        if not target or not ligand_id:
            continue
        if target.upper() == "ADRB2_GPCR_BLIND":
            continue
        if row.get("accepted_for_freeze") is not None and not _as_bool(row.get("accepted_for_freeze")):
            continue
        rows.append(dict(row))
    return rows


def _candidate_detail_index(candidate_rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    indexed: dict[tuple[str, str], dict[str, str]] = {}
    for row in candidate_rows:
        target = _text(row.get("target"))
        ligand_id = _text(row.get("ligand_id"))
        if target and ligand_id:
            indexed[(target, ligand_id)] = row
    return indexed


def _merge_candidate_detail(candidate: dict[str, Any], details: dict[tuple[str, str], dict[str, str]]) -> dict[str, Any]:
    target = _text(candidate.get("target"))
    ligand_id = _text(candidate.get("ligand_id"))
    merged = dict(details.get((target, ligand_id), {}))
    merged.update({key: value for key, value in candidate.items() if _text(value) != "" or key not in merged})
    return merged


def _rdkit_ligand_meta(smiles: str, scaffold: str = "") -> dict[str, str]:
    if not smiles:
        return {}
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, Lipinski
        from rdkit.Chem.Scaffolds import MurckoScaffold
    except Exception:
        return {}

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {}
    scaffold_smiles = scaffold
    if not scaffold_smiles:
        try:
            scaffold_mol = MurckoScaffold.GetScaffoldForMol(mol)
            scaffold_smiles = Chem.MolToSmiles(scaffold_mol, canonical=True) if scaffold_mol is not None else ""
        except Exception:
            scaffold_smiles = ""
    return {
        "molecular_weight": f"{Descriptors.MolWt(mol):.3f}",
        "logp": f"{Descriptors.MolLogP(mol):.3f}",
        "h_donors": str(Lipinski.NumHDonors(mol)),
        "h_acceptors": str(Lipinski.NumHAcceptors(mol)),
        "rot_bonds": str(Lipinski.NumRotatableBonds(mol)),
        "scaffold": scaffold_smiles,
    }


def _native_index(native_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in native_rows:
        target = _text(row.get("target"))
        if target:
            indexed[target] = row
    return indexed


def _native_status(row: dict[str, str] | None) -> tuple[bool, str, str]:
    if not row:
        return False, "blocked_missing_native_or_pocket", "native target row not found"
    missing: list[str] = []
    native_path = _resolve(row.get("native_pdb_path"))
    if not _text(row.get("native_pdb_path")):
        missing.append("native_pdb_path")
    elif native_path is None or not native_path.exists():
        missing.append("native_pdb_path_missing_on_disk")
    if not (_text(row.get("pocket_source")) or _text(row.get("pdb_id"))):
        missing.append("pocket_source")
    for coord in ("pocket_x", "pocket_y", "pocket_z"):
        if not _has_number(row.get(coord)):
            missing.append(coord)
    validation_status = _text(row.get("pocket_validation_status"))
    if validation_status and validation_status not in {"pass", "not_requested"}:
        missing.append(f"pocket_validation_{validation_status}")
    if _text(row.get("native_download_error")):
        missing.append("native_download_error")
    if missing:
        return False, "blocked_missing_native_or_pocket", "missing " + ",".join(missing)
    return True, "ready_native_pocket_sourced", ""


def _download_pdb(pdb_id: str, out_dir: Path) -> tuple[Path | None, str]:
    pdb = _text(pdb_id).upper()
    if not pdb:
        return None, "missing_pdb_id"
    out_path = out_dir / "native_pdb" / f"{pdb.lower()}.pdb"
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path, ""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://files.rcsb.org/download/{pdb}.pdb"
    try:
        with urlopen(url, timeout=30) as response:
            data = response.read()
    except (OSError, URLError) as exc:
        return None, f"download_failed:{exc}"
    if not data or len(data) < 100:
        return None, "download_failed:empty_or_too_small"
    out_path.write_bytes(data)
    return out_path, ""


def _ligand_centroid_from_pdb(
    pdb_path: Path,
    *,
    ligand_code: str,
    ligand_chain: str = "",
) -> tuple[tuple[float, float, float] | None, int]:
    code = _text(ligand_code).upper()
    chain = _text(ligand_chain)
    if not code or not pdb_path.exists():
        return None, 0
    coords: list[tuple[float, float, float]] = []
    with pdb_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith("HETATM"):
                continue
            if line[17:20].strip().upper() != code:
                continue
            if chain and line[21].strip() != chain:
                continue
            try:
                coords.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
            except ValueError:
                continue
    if not coords:
        return None, 0
    n = float(len(coords))
    return (
        sum(coord[0] for coord in coords) / n,
        sum(coord[1] for coord in coords) / n,
        sum(coord[2] for coord in coords) / n,
    ), len(coords)


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _prepare_native_source(row: dict[str, str] | None, out_dir: Path) -> dict[str, str] | None:
    if not row:
        return None
    prepared = dict(row)
    pdb_id = _text(prepared.get("pdb_id")).upper()
    if not _text(prepared.get("native_pdb_path")) and pdb_id:
        pdb_path, error = _download_pdb(pdb_id, out_dir)
        if pdb_path is not None:
            prepared["native_pdb_path"] = str(pdb_path)
        else:
            prepared["native_download_error"] = error

    native_path = _resolve(prepared.get("native_pdb_path"))
    ligand_code = _text(prepared.get("ligand_code"))
    ligand_chain = _text(prepared.get("ligand_chain"))
    if native_path is not None and native_path.exists() and ligand_code:
        centroid, atom_count = _ligand_centroid_from_pdb(
            native_path,
            ligand_code=ligand_code,
            ligand_chain=ligand_chain,
        )
        prepared["pocket_ligand_atom_count"] = str(atom_count)
        if centroid is None:
            prepared["pocket_validation_status"] = "ligand_not_found"
        else:
            for idx, coord in enumerate(("pocket_x", "pocket_y", "pocket_z")):
                if not _has_number(prepared.get(coord)):
                    prepared[coord] = f"{centroid[idx]:.3f}"
            observed = (
                _as_float(prepared.get("pocket_x")),
                _as_float(prepared.get("pocket_y")),
                _as_float(prepared.get("pocket_z")),
            )
            if all(value is not None for value in observed):
                dist = _distance(centroid, (observed[0], observed[1], observed[2]))  # type: ignore[arg-type]
                prepared["pocket_validation_distance_A"] = f"{dist:.4f}"
                prepared["pocket_validation_status"] = (
                    "pass" if dist <= POCKET_VALIDATION_TOLERANCE_A else "centroid_mismatch"
                )
        if not _text(prepared.get("pocket_source")):
            prepared["pocket_source"] = (
                f"RCSB_PDB:{pdb_id}:{ligand_code}:{ligand_chain or '*'}:ligand_centroid"
            )
    if not _text(prepared.get("pocket_fingerprint")):
        fingerprint_seed = "|".join(
            [
                pdb_id,
                ligand_code,
                ligand_chain,
                _text(prepared.get("pocket_x")),
                _text(prepared.get("pocket_y")),
                _text(prepared.get("pocket_z")),
            ]
        )
        digest = hashlib.sha256(fingerprint_seed.encode("utf-8")).hexdigest()[:16]
        prepared["pocket_fingerprint"] = f"rcsb_ligand_centroid:{digest}"
    return prepared


def _artifact_paths(out_dir: Path) -> dict[str, Path]:
    return {
        "candidate_reference_csv": out_dir / "candidate_reference.csv",
        "split_csv": out_dir / "candidate_splits.csv",
        "ligand_meta_csv": out_dir / "ligand_meta.csv",
        "target_meta_csv": out_dir / "target_meta.csv",
        "native_csv": out_dir / "native_targets.csv",
        "profile_json": out_dir / "profile.json",
        "set_spec_json": out_dir / "set_spec.json",
        "summary_json": out_dir / "summary.json",
        "summary_md": out_dir / "summary.md",
    }


def _append_base_reference_rows(rows: list[dict[str, Any]], source_rows: list[dict[str, str]]) -> set[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    for row in source_rows:
        target = _text(row.get("target"))
        ligand_id = _text(row.get("ligand_id"))
        if not target or not ligand_id:
            continue
        key = (target, ligand_id)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "target": target,
                "ligand_id": ligand_id,
                "reference_binding_kcal_mol": _text(row.get("reference_binding_kcal_mol")),
                "is_binder": _text(row.get("is_binder")),
                "source": _text(row.get("source")),
                "source_url": _text(row.get("source_url")),
                "row_classification": _text(row.get("row_classification")) or "base_profile_row",
            }
        )
    return seen


def _append_base_split_rows(rows: list[dict[str, Any]], source_rows: list[dict[str, str]]) -> set[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    for row in source_rows:
        target = _text(row.get("target"))
        ligand_id = _text(row.get("ligand_id"))
        if not target or not ligand_id:
            continue
        key = (target, ligand_id)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"target": target, "ligand_id": ligand_id, "role": _text(row.get("role"))})
    return seen


def _append_base_ligand_rows(rows: list[dict[str, Any]], source_rows: list[dict[str, str]]) -> set[str]:
    seen: set[str] = set()
    for row in source_rows:
        ligand_id = _text(row.get("ligand_id"))
        if not ligand_id or ligand_id in seen:
            continue
        seen.add(ligand_id)
        rows.append(
            {
                "ligand_id": ligand_id,
                "smiles": _text(row.get("smiles")),
                "molecular_weight": _text(row.get("molecular_weight")),
                "logp": _text(row.get("logp")),
                "h_donors": _text(row.get("h_donors")),
                "h_acceptors": _text(row.get("h_acceptors")),
                "rot_bonds": _text(row.get("rot_bonds")),
                "scaffold": _text(row.get("scaffold")),
                "source": _text(row.get("source")) or "base_profile_ligand_meta",
                "meta_status": _text(row.get("meta_status")) or "base_profile_row",
            }
        )
    return seen


def _append_base_target_rows(rows: list[dict[str, Any]], source_rows: list[dict[str, str]]) -> set[str]:
    seen: set[str] = set()
    for row in source_rows:
        target = _text(row.get("target"))
        if not target or target in seen:
            continue
        seen.add(target)
        rows.append(
            {
                "target": target,
                "target_family": _text(row.get("target_family")),
                "sequence": _text(row.get("sequence")),
                "pocket_fingerprint": _text(row.get("pocket_fingerprint")),
                "native_status": _text(row.get("native_status")) or "base_profile_target_meta",
                "blocker_reason": _text(row.get("blocker_reason")),
                "profile_ready": True,
            }
        )
    return seen


def _append_base_native_rows(rows: list[dict[str, Any]], source_rows: list[dict[str, str]]) -> set[str]:
    seen: set[str] = set()
    for row in source_rows:
        target = _text(row.get("target"))
        if not target or target in seen:
            continue
        seen.add(target)
        rows.append(
            {
                "target": target,
                "native_pdb_path": _text(row.get("native_pdb_path")),
                "pdb_id": _text(row.get("pdb_id")),
                "pocket_x": _text(row.get("pocket_x")),
                "pocket_y": _text(row.get("pocket_y")),
                "pocket_z": _text(row.get("pocket_z")),
                "pocket_source": _text(row.get("pocket_source") or row.get("pdb_id")),
                "ligand_code": _text(row.get("ligand_code")),
                "ligand_chain": _text(row.get("ligand_chain")),
                "pocket_validation_status": _text(row.get("pocket_validation_status")),
                "pocket_validation_distance_A": _text(row.get("pocket_validation_distance_A")),
                "pocket_ligand_atom_count": _text(row.get("pocket_ligand_atom_count")),
                "status": _text(row.get("status")) or "base_profile_native_row",
                "blocker_reason": _text(row.get("blocker_reason")),
            }
        )
    return seen


def _build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR Frozen Candidate Profile Support",
        "",
        f"- profile_ready: `{summary['profile_ready']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- blocked_target_count: `{summary['blocked_target_count']}`",
        f"- claim_promotion_allowed: `{summary['claim_promotion_allowed']}`",
        f"- router_claim_allowed: `{summary['router_claim_allowed']}`",
        f"- platform_claim_allowed: `{summary['platform_claim_allowed']}`",
        "",
        "## Target Native Status",
        "",
        "| target | status | blocker |",
        "| --- | --- | --- |",
    ]
    for row in payload["target_rows"]:
        lines.append(f"| `{row['target']}` | `{row['native_status']}` | {row['blocker_reason']} |")
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- This support packet is not claim authorization.",
            "- Native structures and pocket coordinates are only copied from explicit source rows; missing data remains blocked.",
            "",
        ]
    )
    return "\n".join(lines)


def build_support_packet(
    *,
    freeze_packet_json: str | Path = DEFAULT_FREEZE_PACKET_JSON,
    base_profile_json: str | Path = DEFAULT_BASE_PROFILE_JSON,
    candidates_csv: str | Path | None = DEFAULT_CANDIDATES_CSV,
    native_source_csv: str | Path | None = None,
    out_dir: str | Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    freeze_path = _resolve(freeze_packet_json)
    base_profile_path = _resolve(base_profile_json)
    output_dir = _resolve(out_dir)
    if freeze_path is None or base_profile_path is None or output_dir is None:
        raise ValueError("freeze_packet_json, base_profile_json, and out_dir are required")

    freeze_packet = _read_json(freeze_path)
    base_profile = _read_json(base_profile_path)
    candidate_details_path = _resolve(candidates_csv) if candidates_csv is not None else None
    candidate_details = _candidate_detail_index(_read_csv(candidate_details_path))
    native_path = _resolve(native_source_csv) if native_source_csv is not None else _resolve(base_profile.get("target_native_csv"))
    source_native_rows = _read_csv(native_path)
    native_by_target = _native_index(source_native_rows)
    candidates = _candidate_rows(freeze_packet)
    paths = _artifact_paths(output_dir)

    base_reference_rows = _read_csv(_resolve(base_profile.get("ligand_csv")))
    base_split_rows = _read_csv(_resolve(base_profile.get("eval_split_csv")))
    base_ligand_rows = _read_csv(_resolve(base_profile.get("leakage_ligand_meta_csv")))
    base_target_rows = _read_csv(_resolve(base_profile.get("leakage_target_meta_csv")))
    base_native_rows = _read_csv(_resolve(base_profile.get("target_native_csv")))

    reference_rows: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []
    ligand_rows: list[dict[str, Any]] = []
    native_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    seen_reference_keys = _append_base_reference_rows(reference_rows, base_reference_rows)
    seen_split_keys = _append_base_split_rows(split_rows, base_split_rows)
    seen_ligands = _append_base_ligand_rows(ligand_rows, base_ligand_rows)
    seen_targets = _append_base_target_rows(target_rows, base_target_rows)
    seen_native_targets = _append_base_native_rows(native_rows, base_native_rows)
    candidate_targets: set[str] = set()

    for candidate in candidates:
        candidate = _merge_candidate_detail(candidate, candidate_details)
        target = _text(candidate.get("target"))
        ligand_id = _text(candidate.get("ligand_id"))
        role = _text(candidate.get("role")) or "far_ood_eval"
        candidate_targets.add(target)
        reference_key = (target, ligand_id)
        if reference_key not in seen_reference_keys:
            seen_reference_keys.add(reference_key)
            reference_rows.append(
                {
                    "target": target,
                    "ligand_id": ligand_id,
                    "reference_binding_kcal_mol": candidate.get("reference_binding_kcal_mol", ""),
                    "is_binder": 1 if _as_bool(candidate.get("is_binder", True)) else 0,
                    "source": _text(candidate.get("source")),
                    "source_url": _text(candidate.get("source_url")),
                    "row_classification": _text(candidate.get("row_classification")) or "frozen_non_adrb2_gpcr_candidate",
                }
            )
        if reference_key not in seen_split_keys:
            seen_split_keys.add(reference_key)
            split_rows.append({"target": target, "ligand_id": ligand_id, "role": role})
        if ligand_id not in seen_ligands:
            seen_ligands.add(ligand_id)
            smiles = _text(candidate.get("smiles"))
            rdkit_meta = _rdkit_ligand_meta(smiles, _text(candidate.get("scaffold")))
            ligand_rows.append(
                {
                    "ligand_id": ligand_id,
                    "smiles": smiles,
                    "molecular_weight": _text(candidate.get("molecular_weight")) or rdkit_meta.get("molecular_weight", ""),
                    "logp": _text(candidate.get("logp")) or rdkit_meta.get("logp", ""),
                    "h_donors": _text(candidate.get("h_donors")) or rdkit_meta.get("h_donors", ""),
                    "h_acceptors": _text(candidate.get("h_acceptors")) or rdkit_meta.get("h_acceptors", ""),
                    "rot_bonds": _text(candidate.get("rot_bonds")) or rdkit_meta.get("rot_bonds", ""),
                    "scaffold": _text(candidate.get("scaffold")) or rdkit_meta.get("scaffold", ""),
                    "source": _text(candidate.get("source")),
                    "meta_status": "transparent_review_row",
                }
            )
        if target in seen_native_targets:
            continue
        seen_native_targets.add(target)
        native_source = _prepare_native_source(native_by_target.get(target), output_dir)
        ready, status, reason = _native_status(native_source)
        native_source = native_source or {}
        native_rows.append(
            {
                "target": target,
                "native_pdb_path": _text(native_source.get("native_pdb_path")) if ready else "",
                "pdb_id": _text(native_source.get("pdb_id")) if ready else "",
                "pocket_x": _text(native_source.get("pocket_x")) if ready else "",
                "pocket_y": _text(native_source.get("pocket_y")) if ready else "",
                "pocket_z": _text(native_source.get("pocket_z")) if ready else "",
                "pocket_source": _text(native_source.get("pocket_source") or native_source.get("pdb_id")) if ready else "",
                "ligand_code": _text(native_source.get("ligand_code")) if ready else "",
                "ligand_chain": _text(native_source.get("ligand_chain")) if ready else "",
                "pocket_validation_status": _text(native_source.get("pocket_validation_status")) if ready else "",
                "pocket_validation_distance_A": _text(native_source.get("pocket_validation_distance_A")) if ready else "",
                "pocket_ligand_atom_count": _text(native_source.get("pocket_ligand_atom_count")) if ready else "",
                "status": status,
                "blocker_reason": reason,
            }
        )
        if target in seen_targets:
            continue
        seen_targets.add(target)
        target_rows.append(
            {
                "target": target,
                "target_family": _text(candidate.get("target_family")) or "gpcr",
                "sequence": _text(native_source.get("sequence")),
                "pocket_fingerprint": _text(native_source.get("pocket_fingerprint")),
                "native_status": status,
                "blocker_reason": reason,
                "profile_ready": ready,
            }
        )

    candidate_profile_rows = [row for row in target_rows if row["target"] in candidate_targets]
    profile_ready = bool(candidates) and all(row["profile_ready"] is True for row in candidate_profile_rows)
    target_list = sorted(_split_list(base_profile.get("targets")) | candidate_targets)
    hard_decoy_target_list = sorted(_split_list(base_profile.get("hard_decoy_targets")) | candidate_targets)
    profile = dict(base_profile)
    profile.update(
        {
            "version": f"{_text(base_profile.get('version')) or 'gpcr'}_frozen_candidate_support",
            "description": "Guarded base+frozen non-ADRB2 GPCR support profile; not claim-authorizing.",
            "targets": ",".join(target_list),
            "ligand_csv": str(paths["candidate_reference_csv"]),
            "ranking_labels_csv": str(paths["candidate_reference_csv"]),
            "calibration_reference_csv": str(paths["candidate_reference_csv"]),
            "eval_split_csv": str(paths["split_csv"]),
            "target_native_csv": str(paths["native_csv"]),
            "native_path_col": "native_pdb_path",
            "leakage_ligand_meta_csv": str(paths["ligand_meta_csv"]),
            "leakage_target_meta_csv": str(paths["target_meta_csv"]),
            "hard_decoy_reference_csv": str(paths["candidate_reference_csv"]),
            "hard_decoy_ligand_meta_csv": str(paths["ligand_meta_csv"]),
            "hard_decoy_target_meta_csv": str(paths["target_meta_csv"]),
            "hard_decoy_targets": ",".join(hard_decoy_target_list),
            "profile_ready": profile_ready,
            "guarded_profile_status": "ready_native_pocket_sourced" if profile_ready else "blocked_missing_native_or_pocket",
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
        }
    )
    set_spec = {
        "set_id": "gpcr_frozen_non_adrb2_candidate_support_current",
        "source_freeze_packet_json": str(freeze_path),
        "base_profile_json": str(base_profile_path),
        "candidate_details_csv": str(candidate_details_path) if candidate_details_path else None,
        "native_source_csv": str(native_path) if native_path else None,
        "candidate_count": len(candidates),
        "base_reference_row_count": len(base_reference_rows),
        "combined_reference_row_count": len(reference_rows),
        "target_count": len(target_list),
        "profile_ready": profile_ready,
        "claim_authorization": False,
        "claim_promotion_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "freeze_packet_is_not_claim_authorization": True,
        "native_coordinates_fabricated": False,
        "native_structure_fabricated": False,
        "required_before_run": "resolve every blocked native_pdb_path and pocket source row before treating profile as runnable",
    }
    summary = {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "profile_ready": profile_ready,
        "candidate_count": len(candidates),
        "target_count": len(target_list),
        "blocked_target_count": sum(1 for row in candidate_profile_rows if row["profile_ready"] is False),
        "combined_reference_row_count": len(reference_rows),
        "combined_split_row_count": len(split_rows),
        "claim_promotion_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "next_required_step": (
            "Resolve blocked native structure and pocket-source rows before any guarded profile run."
            if not profile_ready
            else "Profile support inputs are complete for review; set-spec still does not authorize claims."
        ),
    }
    payload = {
        "packet_type": "gpcr_frozen_candidate_profile_support",
        "summary": summary,
        "artifacts": {key: str(path) for key, path in paths.items()},
        "source_artifacts": {
            "freeze_packet_json": str(freeze_path),
            "base_profile_json": str(base_profile_path),
            "candidate_details_csv": str(candidate_details_path) if candidate_details_path else None,
            "native_source_csv": str(native_path) if native_path else None,
        },
        "candidate_rows": reference_rows,
        "target_rows": target_rows,
        "set_spec": set_spec,
    }

    _write_csv(
        paths["candidate_reference_csv"],
        reference_rows,
        [
            "target",
            "ligand_id",
            "reference_binding_kcal_mol",
            "is_binder",
            "source",
            "source_url",
            "row_classification",
        ],
    )
    _write_csv(paths["split_csv"], split_rows, ["target", "ligand_id", "role"])
    _write_csv(
        paths["ligand_meta_csv"],
        ligand_rows,
        [
            "ligand_id",
            "smiles",
            "molecular_weight",
            "logp",
            "h_donors",
            "h_acceptors",
            "rot_bonds",
            "scaffold",
            "source",
            "meta_status",
        ],
    )
    _write_csv(
        paths["target_meta_csv"],
        target_rows,
        [
            "target",
            "target_family",
            "sequence",
            "pocket_fingerprint",
            "native_status",
            "blocker_reason",
            "profile_ready",
        ],
    )
    _write_csv(
        paths["native_csv"],
        native_rows,
        [
            "target",
            "native_pdb_path",
            "pdb_id",
            "pocket_x",
            "pocket_y",
            "pocket_z",
            "pocket_source",
            "ligand_code",
            "ligand_chain",
            "pocket_validation_status",
            "pocket_validation_distance_A",
            "pocket_ligand_atom_count",
            "status",
            "blocker_reason",
        ],
    )
    _write_json(paths["profile_json"], profile)
    _write_json(paths["set_spec_json"], set_spec)
    _write_json(paths["summary_json"], payload)
    paths["summary_md"].write_text(_build_markdown(payload) + "\n", encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build guarded support artifacts for frozen non-ADRB2 GPCR candidate profile review."
    )
    parser.add_argument("--freeze-packet-json", default=DEFAULT_FREEZE_PACKET_JSON)
    parser.add_argument("--base-profile-json", default=DEFAULT_BASE_PROFILE_JSON)
    parser.add_argument("--candidates-csv", default=DEFAULT_CANDIDATES_CSV)
    parser.add_argument("--native-source-csv", default=None)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_support_packet(
        freeze_packet_json=args.freeze_packet_json,
        base_profile_json=args.base_profile_json,
        candidates_csv=args.candidates_csv,
        native_source_csv=args.native_source_csv,
        out_dir=args.out_dir,
    )


if __name__ == "__main__":
    main()
