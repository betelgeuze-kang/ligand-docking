#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np

try:  # pragma: no cover - optional in lightweight CI.
    from rdkit import Chem  # type: ignore
except Exception:  # pragma: no cover
    Chem = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_STAGE3_CSV = "runs/gpcr_drd2_pseudo_allatom_repair_rows_current.csv"
DEFAULT_RANKING_ROWS_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage5_ranking_rows.csv"
)
DEFAULT_ATOM_CACHE_CSV = "runs/gpcr_atom_window_anchor_feature_cache_drd2_pseudo_allatom_repair_current.csv"
DEFAULT_LOCAL_MINIMIZATION_JSON = "runs/gpcr_drd2_local_minimization_survival_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_drd2_atom_typed_backmapping_support_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_drd2_atom_typed_backmapping_support_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_drd2_atom_typed_backmapping_support_current.md"

DEFAULT_TARGET = "CHEMBL217_DRD2_HUMAN"
DEFAULT_POSITIVE_LIGAND = "CHEMBL301265"
DEFAULT_SCORE_COL = "binding_score_composite_v7_residual_active"

MIN_BACKMAPPING_COVERAGE = 0.50
FULL_ATOM_COVERAGE = 0.95
POSE_RMSD_MAX_A = 6.0
LOCAL_MINIMIZATION_SURVIVAL_MIN = 0.55

COMMON_NON_LIGAND_HET = {
    "HOH",
    "WAT",
    "DOD",
    "SO4",
    "PO4",
    "GOL",
    "EDO",
    "DMS",
    "PEG",
    "PGE",
    "MPD",
    "ACT",
    "ACY",
    "FMT",
    "EOH",
    "IPA",
    "MES",
    "TRS",
    "CL",
    "NA",
    "K",
    "CA",
    "MG",
    "ZN",
    "MN",
    "FE",
    "CU",
    "NI",
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _int(value: Any) -> int | None:
    out = _float(value)
    return int(out) if out is not None else None


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _is_positive(row: dict[str, Any], positive_ligand: str) -> bool:
    if _text(row.get("ligand_id")) == positive_ligand:
        return True
    return _text(row.get("is_binder")).lower() in {"1", "true", "t", "yes", "y"}


def _heavy_atom_count(smiles: str) -> int | None:
    s = _text(smiles)
    if not s:
        return None
    if Chem is not None:
        try:
            mol = Chem.MolFromSmiles(s)
            if mol is not None:
                return int(sum(1 for atom in mol.GetAtoms() if atom.GetAtomicNum() > 1))
        except Exception:
            pass
    tokens = re.findall(r"Cl|Br|[BCNOFPSI][a-z]?|[cnops]", s)
    return len(tokens) if tokens else None


def _cationic_center_count(smiles: str) -> int | None:
    s = _text(smiles)
    if not s:
        return None
    if Chem is not None:
        try:
            mol = Chem.MolFromSmiles(s)
            if mol is not None:
                count = 0
                for atom in mol.GetAtoms():
                    if atom.GetAtomicNum() != 7 or atom.GetIsAromatic():
                        continue
                    if atom.GetFormalCharge() > 0 or atom.GetTotalNumHs() > 0 or atom.GetDegree() >= 2:
                        count += 1
                return count
        except Exception:
            pass
    return len(re.findall(r"\[NH\d?\+?\]|(?<![A-Za-z])N|NCC|CN", s))


def _load_npz_metrics(path_text: str) -> dict[str, Any]:
    path = _resolve(path_text) if path_text else None
    if path is None or not path.exists():
        return {
            "trajectory_npz_available": False,
            "trajectory_npz_reason": "missing",
            "trajectory_npz": str(path) if path else "",
        }
    try:
        with np.load(str(path), allow_pickle=False) as npz:
            ligand_frames = np.asarray(npz["ligand_frames"], dtype=float)
    except Exception as exc:
        return {
            "trajectory_npz_available": False,
            "trajectory_npz_reason": f"unreadable:{type(exc).__name__}",
            "trajectory_npz": str(path),
        }
    if ligand_frames.ndim != 3 or ligand_frames.shape[0] <= 0 or ligand_frames.shape[1] <= 0:
        return {
            "trajectory_npz_available": False,
            "trajectory_npz_reason": "ligand_frames_invalid",
            "trajectory_npz": str(path),
        }
    finite_frames = np.isfinite(ligand_frames).all(axis=(1, 2))
    valid = ligand_frames[finite_frames]
    if valid.shape[0] <= 0:
        return {
            "trajectory_npz_available": False,
            "trajectory_npz_reason": "ligand_frames_nonfinite",
            "trajectory_npz": str(path),
            "trajectory_frame_count": int(ligand_frames.shape[0]),
            "ligand_frame_atom_count": int(ligand_frames.shape[1]),
        }
    ref = valid[0] - valid[0].mean(axis=0, keepdims=True)
    centered = valid - valid.mean(axis=1, keepdims=True)
    rmsd_by_frame = np.sqrt(np.mean(np.sum((centered - ref[None, :, :]) ** 2, axis=2), axis=1))
    centroid = valid.mean(axis=1)
    centroid_drift = np.linalg.norm(centroid - centroid[0], axis=1)
    return {
        "trajectory_npz_available": True,
        "trajectory_npz_reason": "ok",
        "trajectory_npz": str(path),
        "trajectory_frame_count": int(ligand_frames.shape[0]),
        "trajectory_finite_frame_fraction": float(finite_frames.mean()),
        "ligand_frame_atom_count": int(ligand_frames.shape[1]),
        "pose_preservation_rmsd_A_median": float(np.median(rmsd_by_frame)),
        "pose_preservation_rmsd_A_p90": float(np.percentile(rmsd_by_frame, 90)),
        "centroid_drift_A_p90": float(np.percentile(centroid_drift, 90)),
        "local_stability_survival_proxy_fraction": float(np.mean(rmsd_by_frame <= POSE_RMSD_MAX_A)),
    }


def _pdb_element(line: str) -> str:
    element = _text(line[76:78]).upper()
    if element:
        return element
    atom_name = _text(line[12:16]).upper()
    letters = re.sub(r"[^A-Z]", "", atom_name)
    if not letters:
        return ""
    if len(letters) >= 2 and letters[:2] in {"CL", "BR", "NA", "MG", "ZN", "FE", "CU", "MN", "CA", "NI"}:
        return letters[:2]
    return letters[:1]


def _pdb_ligand_group_key(line: str) -> tuple[str, str, str]:
    return (_text(line[17:20]).upper(), _text(line[21:22]).upper(), _text(line[22:27]).upper())


def _load_backmapped_pdb_ligand_metrics(path_text: str) -> dict[str, Any]:
    path = _resolve(path_text) if path_text else None
    if path is None:
        return {
            "backmapped_pdb_available": False,
            "backmapped_pdb_reason": "missing",
            "backmapped_pdb": "",
        }
    if not path.exists():
        return {
            "backmapped_pdb_available": False,
            "backmapped_pdb_reason": "missing",
            "backmapped_pdb": str(path),
        }
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception as exc:
        return {
            "backmapped_pdb_available": False,
            "backmapped_pdb_reason": f"unreadable:{type(exc).__name__}",
            "backmapped_pdb": str(path),
        }

    explicit_ligand_lines: list[str] = []
    het_groups: dict[tuple[str, str, str], list[str]] = {}
    for line in lines:
        if not line.startswith(("ATOM", "HETATM")):
            continue
        resn = _text(line[17:20]).upper()
        chain = _text(line[21:22]).upper()
        if resn == "LIG" or chain == "L":
            explicit_ligand_lines.append(line)
        if line.startswith("HETATM") and resn not in COMMON_NON_LIGAND_HET:
            het_groups.setdefault(_pdb_ligand_group_key(line), []).append(line)

    selected_lines = explicit_ligand_lines
    selected_key = "explicit_lig_or_chain_l"
    if not selected_lines and het_groups:
        selected_group_key, selected_lines = max(
            het_groups.items(),
            key=lambda item: (len(item[1]), item[0][0], item[0][1], item[0][2]),
        )
        selected_key = ":".join(selected_group_key)

    heavy_atom_count = sum(1 for line in selected_lines if _pdb_element(line) != "H")
    return {
        "backmapped_pdb_available": True,
        "backmapped_pdb_reason": "ok" if heavy_atom_count > 0 else "ligand_atoms_missing",
        "backmapped_pdb": str(path),
        "backmapped_pdb_ligand_group": selected_key if selected_lines else "",
        "backmapped_pdb_ligand_atom_count": int(len(selected_lines)),
        "backmapped_pdb_ligand_heavy_atom_count": int(heavy_atom_count),
    }


def _select_coverage_count(
    *,
    pdb_metrics: dict[str, Any],
    ligand_frame_atoms: int | None,
) -> tuple[int | None, str, str]:
    pdb_count = _int(pdb_metrics.get("backmapped_pdb_ligand_heavy_atom_count"))
    if pdb_metrics.get("backmapped_pdb_available") and pdb_count is not None and pdb_count > 0:
        return pdb_count, "backmapped_pdb_ligand_heavy_atom_count", "backmapped_pdb"
    if ligand_frame_atoms is not None:
        return ligand_frame_atoms, "ligand_frame_atom_count", "trajectory_npz"
    return None, "missing", "none"


def _select_local_minimization_survival(stage3_row: dict[str, str]) -> tuple[float | None, str]:
    for column in ("local_minimization_survival_fraction", "source_three_bead_local_minimization_survival_fraction"):
        value = _float(stage3_row.get(column))
        if value is not None:
            return value, column
    return None, "missing"


def _local_minimization_rows(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return {}
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        if all(key):
            out[key] = row
    return out


def _ranking_selection(
    ranking_rows: list[dict[str, str]],
    *,
    target: str,
    positive_ligand: str,
    score_col: str,
    top_decoys: int,
) -> list[tuple[str, str, str, int]]:
    target_rows = [row for row in ranking_rows if _text(row.get("target")) == target]
    ranked = sorted(
        target_rows,
        key=lambda row: (
            _float(row.get(score_col)) if _float(row.get(score_col)) is not None else float("inf"),
            _text(row.get("ligand_id")),
        ),
    )
    selected: list[tuple[str, str, str, int]] = []
    positive_rank = None
    for rank, row in enumerate(ranked, start=1):
        if _text(row.get("ligand_id")) == positive_ligand:
            positive_rank = rank
            break
    for rank, row in enumerate(ranked, start=1):
        ligand_id = _text(row.get("ligand_id"))
        if ligand_id == positive_ligand:
            selected.append((target, ligand_id, "positive", rank))
            continue
        if positive_rank is not None and rank > positive_rank:
            continue
        if len([item for item in selected if item[2] == "decoy_above_positive"]) >= top_decoys:
            continue
        selected.append((target, ligand_id, "decoy_above_positive", rank))
    if not any(item[1] == positive_ligand for item in selected):
        selected.append((target, positive_ligand, "positive", positive_rank or 0))
    return selected


def _row_metrics(
    *,
    stage3_row: dict[str, str] | None,
    atom_cache_row: dict[str, str] | None,
    local_min_row: dict[str, Any] | None,
    local_min_summary: dict[str, Any],
    target: str,
    ligand_id: str,
    role: str,
    target_rank: int,
    positive_ligand: str,
) -> dict[str, Any]:
    stage3_row = stage3_row or {}
    atom_cache_row = atom_cache_row or {}
    smiles = _text(stage3_row.get("ligand_smiles"))
    npz_metrics = _load_npz_metrics(_text(stage3_row.get("trajectory_npz")))
    pdb_metrics = _load_backmapped_pdb_ligand_metrics(_text(stage3_row.get("backmapped_pdb")))
    heavy_atoms = _heavy_atom_count(smiles)
    cationic_centers = _cationic_center_count(smiles)
    ligand_frame_atoms = _int(npz_metrics.get("ligand_frame_atom_count"))
    coverage_atom_count, coverage_atom_count_source, coverage_coordinate_source = _select_coverage_count(
        pdb_metrics=pdb_metrics,
        ligand_frame_atoms=ligand_frame_atoms,
    )
    coverage = None
    if heavy_atoms and coverage_atom_count is not None:
        coverage = coverage_atom_count / heavy_atoms
    local_min_survival, local_min_survival_source = _select_local_minimization_survival(stage3_row)
    local_min_claim_scope = ""
    local_min_engine_kind = ""
    local_min_evidence_allowed = True
    local_min_row_blockers: list[str] = []
    if local_min_survival is None and local_min_row:
        local_min_survival = _float(local_min_row.get("survival_fraction"))
        local_min_survival_source = "gpcr_drd2_local_minimization_survival_packet"
        local_min_claim_scope = _text(local_min_row.get("survival_claim_scope"))
        local_min_engine_kind = _text(local_min_row.get("engine_kind"))
        local_min_evidence_allowed = bool(local_min_summary.get("hard_decoy_rebuild_evidence_allowed"))
        local_min_row_blockers = [str(item) for item in local_min_row.get("blockers") or []]

    blockers: list[str] = []
    if not stage3_row:
        blockers.append("stage3_row_missing")
    if not npz_metrics.get("trajectory_npz_available"):
        blockers.append(str(npz_metrics.get("trajectory_npz_reason") or "trajectory_npz_missing"))
    if coverage is None:
        blockers.append("backmapping_atom_coverage_unmeasured")
    elif coverage < MIN_BACKMAPPING_COVERAGE:
        blockers.append("backmapping_atom_coverage_below_min")
    if coverage is None or coverage < FULL_ATOM_COVERAGE:
        blockers.append("full_atom_typed_backmapping_missing")
    pose_rmsd = _float(npz_metrics.get("pose_preservation_rmsd_A_p90"))
    if pose_rmsd is None:
        blockers.append("pose_preservation_rmsd_missing")
    elif pose_rmsd > POSE_RMSD_MAX_A:
        blockers.append("pose_preservation_rmsd_above_max")
    if local_min_survival is None:
        blockers.append("local_minimization_survival_missing")
    elif local_min_survival < LOCAL_MINIMIZATION_SURVIVAL_MIN:
        blockers.append("local_minimization_survival_below_min")
    elif local_min_evidence_allowed is not True:
        blockers.append("local_minimization_survival_not_claim_grade")
    if not _text(stage3_row.get("backmapped_pdb")):
        blockers.append("backmapped_pdb_missing")
    elif not pdb_metrics.get("backmapped_pdb_available"):
        blockers.append(str(pdb_metrics.get("backmapped_pdb_reason") or "backmapped_pdb_unavailable"))
    elif not _int(pdb_metrics.get("backmapped_pdb_ligand_heavy_atom_count")):
        blockers.append(str(pdb_metrics.get("backmapped_pdb_reason") or "backmapped_pdb_ligand_atoms_missing"))
    if cationic_centers and (coverage is None or coverage < FULL_ATOM_COVERAGE):
        blockers.append("cationic_center_anchor_not_atom_typed")

    source_metric_provenance = {
        "backmapping_atom_coverage_ratio": {
            "coordinate_source": coverage_coordinate_source,
            "atom_count_source": coverage_atom_count_source,
            "atom_count": coverage_atom_count,
            "denominator_source": "ligand_smiles_heavy_atom_count",
            "denominator_count": heavy_atoms,
        },
        "pose_preservation_rmsd_A_p90": {
            "source": "trajectory_npz_ligand_frames",
            "available": pose_rmsd is not None,
        },
        "local_minimization_survival_fraction": {
            "source_column": local_min_survival_source,
            "threshold_min": LOCAL_MINIMIZATION_SURVIVAL_MIN,
            "engine_kind": local_min_engine_kind,
            "claim_scope": local_min_claim_scope,
            "hard_decoy_rebuild_evidence_allowed": local_min_evidence_allowed,
            "source_blockers": local_min_row_blockers,
        },
    }

    return {
        "target": target,
        "ligand_id": ligand_id,
        "role": role,
        "target_rank": target_rank,
        "is_positive": ligand_id == positive_ligand,
        "ligand_smiles": smiles,
        "smiles_heavy_atom_count": heavy_atoms,
        "cationic_center_count": cationic_centers,
        "ligand_frame_atom_count": ligand_frame_atoms,
        "backmapped_pdb_ligand_atom_count": pdb_metrics.get("backmapped_pdb_ligand_atom_count"),
        "backmapped_pdb_ligand_heavy_atom_count": pdb_metrics.get("backmapped_pdb_ligand_heavy_atom_count"),
        "backmapped_pdb_ligand_group": pdb_metrics.get("backmapped_pdb_ligand_group"),
        "backmapped_pdb_reason": pdb_metrics.get("backmapped_pdb_reason"),
        "backmapping_atom_count_for_coverage": coverage_atom_count,
        "backmapping_atom_count_source": coverage_atom_count_source,
        "backmapping_coordinate_source": coverage_coordinate_source,
        "backmapping_atom_coverage_ratio": coverage,
        "minimum_backmapping_coverage_gate_pass": bool(coverage is not None and coverage >= MIN_BACKMAPPING_COVERAGE),
        "full_atom_typed_backmapping_ready": bool(coverage is not None and coverage >= FULL_ATOM_COVERAGE),
        "trajectory_npz_available": npz_metrics.get("trajectory_npz_available"),
        "trajectory_frame_count": npz_metrics.get("trajectory_frame_count"),
        "trajectory_finite_frame_fraction": npz_metrics.get("trajectory_finite_frame_fraction"),
        "pose_preservation_rmsd_A_median": npz_metrics.get("pose_preservation_rmsd_A_median"),
        "pose_preservation_rmsd_A_p90": npz_metrics.get("pose_preservation_rmsd_A_p90"),
        "centroid_drift_A_p90": npz_metrics.get("centroid_drift_A_p90"),
        "local_stability_survival_proxy_fraction": npz_metrics.get("local_stability_survival_proxy_fraction"),
        "local_minimization_survival_fraction": local_min_survival,
        "local_minimization_survival_source_column": local_min_survival_source,
        "local_minimization_survival_engine_kind": local_min_engine_kind,
        "local_minimization_survival_claim_scope": local_min_claim_scope,
        "local_minimization_survival_hard_decoy_evidence_allowed": local_min_evidence_allowed,
        "local_minimization_survival_source_blockers": local_min_row_blockers,
        "local_minimization_survival_gate_pass": bool(
            local_min_survival is not None
            and local_min_survival >= LOCAL_MINIMIZATION_SURVIVAL_MIN
            and local_min_evidence_allowed is True
        ),
        "class_a_atom_anchor_available": _int(atom_cache_row.get("class_a_atom_anchor_available")),
        "class_a_atom_anchor_template_residue": _text(atom_cache_row.get("class_a_atom_anchor_template_residue")),
        "class_a_atom_anchor_min_distance_A": _float(atom_cache_row.get("class_a_atom_anchor_min_distance_A")),
        "class_a_atom_anchor_mean_distance_A": _float(atom_cache_row.get("class_a_atom_anchor_mean_distance_A")),
        "class_a_atom_anchor_contact_fraction_le_2p8A": _float(
            atom_cache_row.get("class_a_atom_anchor_contact_fraction_le_2p8A")
        ),
        "class_a_atom_anchor_contact_fraction_2p8_4p2A": _float(
            atom_cache_row.get("class_a_atom_anchor_contact_fraction_2p8_4p2A")
        ),
        "backmapped_pdb": _text(stage3_row.get("backmapped_pdb")),
        "trajectory_npz": _text(stage3_row.get("trajectory_npz")),
        "source_metric_provenance": source_metric_provenance,
        "blockers": sorted(set(blockers)),
    }


def build_support(
    *,
    stage3_csv: str | Path = DEFAULT_STAGE3_CSV,
    ranking_rows_csv: str | Path = DEFAULT_RANKING_ROWS_CSV,
    atom_cache_csv: str | Path = DEFAULT_ATOM_CACHE_CSV,
    local_minimization_json: str | Path = DEFAULT_LOCAL_MINIMIZATION_JSON,
    target: str = DEFAULT_TARGET,
    positive_ligand: str = DEFAULT_POSITIVE_LIGAND,
    score_col: str = DEFAULT_SCORE_COL,
    top_decoys: int = 16,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    stage3_rows = _read_csv(stage3_csv)
    ranking_rows = _read_csv(ranking_rows_csv)
    atom_cache_rows = _read_csv(atom_cache_csv)
    local_min_payload = _read_json(local_minimization_json)
    local_min_summary = local_min_payload.get("summary", {})
    local_min_summary = local_min_summary if isinstance(local_min_summary, dict) else {}
    local_min_by_key = _local_minimization_rows(local_min_payload)
    stage3_by_key = {(_text(row.get("target")), _text(row.get("ligand_id"))): row for row in stage3_rows}
    atom_cache_by_key = {(_text(row.get("target")), _text(row.get("ligand_id"))): row for row in atom_cache_rows}
    selected = _ranking_selection(
        ranking_rows,
        target=target,
        positive_ligand=positive_ligand,
        score_col=score_col,
        top_decoys=top_decoys,
    )
    rows = [
        _row_metrics(
            stage3_row=stage3_by_key.get((t, ligand_id)),
            atom_cache_row=atom_cache_by_key.get((t, ligand_id)),
            local_min_row=local_min_by_key.get((t, ligand_id)),
            local_min_summary=local_min_summary,
            target=t,
            ligand_id=ligand_id,
            role=role,
            target_rank=rank,
            positive_ligand=positive_ligand,
        )
        for t, ligand_id, role, rank in selected
    ]
    positive_rows = [row for row in rows if row["is_positive"]]
    positive = positive_rows[0] if positive_rows else {}
    blocked_rows = [row for row in rows if row["blockers"]]
    positive_blockers = list(positive.get("blockers") or [])
    full_atom_ready = bool(positive.get("full_atom_typed_backmapping_ready"))
    minimum_coverage_pass = bool(positive.get("minimum_backmapping_coverage_gate_pass"))
    pose_rmsd_measured = positive.get("pose_preservation_rmsd_A_p90") is not None
    local_min_measured = positive.get("local_minimization_survival_fraction") is not None
    local_min_gate_pass = bool(positive.get("local_minimization_survival_gate_pass"))
    gate_pass = full_atom_ready and minimum_coverage_pass and pose_rmsd_measured and local_min_measured and local_min_gate_pass
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "drd2_atom_typed_backmapping_blocked" if not gate_pass else "drd2_atom_typed_backmapping_ready",
        "target": target,
        "positive_ligand_id": positive_ligand,
        "selected_row_count": len(rows),
        "blocked_row_count": len(blocked_rows),
        "positive_backmapping_atom_coverage_ratio": positive.get("backmapping_atom_coverage_ratio"),
        "positive_full_atom_typed_backmapping_ready": full_atom_ready,
        "positive_minimum_coverage_gate_pass": minimum_coverage_pass,
        "positive_pose_preservation_rmsd_A_p90": positive.get("pose_preservation_rmsd_A_p90"),
        "positive_local_minimization_survival_fraction": positive.get("local_minimization_survival_fraction"),
        "positive_local_minimization_survival_source_column": positive.get(
            "local_minimization_survival_source_column"
        ),
        "positive_local_minimization_survival_engine_kind": positive.get("local_minimization_survival_engine_kind"),
        "positive_local_minimization_survival_claim_scope": positive.get("local_minimization_survival_claim_scope"),
        "positive_local_minimization_survival_hard_decoy_evidence_allowed": positive.get(
            "local_minimization_survival_hard_decoy_evidence_allowed"
        ),
        "positive_local_minimization_survival_source_blockers": positive.get(
            "local_minimization_survival_source_blockers"
        ),
        "positive_local_minimization_survival_gate_pass": local_min_gate_pass,
        "local_minimization_survival_min": LOCAL_MINIMIZATION_SURVIVAL_MIN,
        "positive_backmapping_atom_count_source": positive.get("backmapping_atom_count_source"),
        "positive_backmapping_coordinate_source": positive.get("backmapping_coordinate_source"),
        "positive_source_metric_provenance": positive.get("source_metric_provenance"),
        "positive_blockers": positive_blockers,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "hard_decoy_rebuild_allowed": gate_pass,
        "guarded_100k_rerun_allowed": False,
        "next_required_step": (
            "Rebuild DRD2 hard-decoy challenge slices now that claim-grade full-forcefield local-minimization "
            "survival evidence is available; keep guarded 100k claim review locked."
            if gate_pass
            else "Generate claim-grade full-forcefield DRD2 local-minimization survival evidence "
            "before hard-decoy rebuild or guarded 100k claim review."
        ),
        "source_artifacts": {
            "stage3_csv": _artifact(stage3_csv),
            "ranking_rows_csv": _artifact(ranking_rows_csv),
            "atom_cache_csv": _artifact(atom_cache_csv),
            "local_minimization_json": _artifact(local_minimization_json),
        },
    }
    return {
        "packet_type": "gpcr_drd2_atom_typed_backmapping_support",
        "summary": summary,
        "rows": rows,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "guarded_100k_rerun_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "local_stability_survival_proxy_is_not_local_minimization": True,
        },
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR DRD2 Atom-Typed Backmapping Support",
        "",
        "## Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- target: `{summary['target']}`",
        f"- positive_ligand_id: `{summary['positive_ligand_id']}`",
        f"- positive_backmapping_atom_coverage_ratio: `{summary['positive_backmapping_atom_coverage_ratio']}`",
        f"- positive_full_atom_typed_backmapping_ready: `{str(summary['positive_full_atom_typed_backmapping_ready']).lower()}`",
        f"- positive_pose_preservation_rmsd_A_p90: `{summary['positive_pose_preservation_rmsd_A_p90']}`",
        f"- positive_local_minimization_survival_fraction: `{summary['positive_local_minimization_survival_fraction']}`",
        f"- hard_decoy_rebuild_allowed: `{str(summary['hard_decoy_rebuild_allowed']).lower()}`",
        f"- guarded_100k_rerun_allowed: `{str(summary['guarded_100k_rerun_allowed']).lower()}`",
        "",
        "## Positive Blockers",
        "",
    ]
    blockers = summary.get("positive_blockers") or []
    lines.extend([f"- `{blocker}`" for blocker in blockers] or ["- none"])
    lines.extend(["", "## Rows", ""])
    lines.append("| Role | Ligand | Rank | Coverage | Full atom ready | Pose p90 A | Local min survival | Blockers |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|")
    for row in payload["rows"]:
        blockers_text = ", ".join(f"`{item}`" for item in row["blockers"][:4]) or "none"
        lines.append(
            f"| `{row['role']}` | `{row['ligand_id']}` | `{row['target_rank']}` | "
            f"`{row['backmapping_atom_coverage_ratio']}` | `{str(row['full_atom_typed_backmapping_ready']).lower()}` | "
            f"`{row['pose_preservation_rmsd_A_p90']}` | `{row['local_minimization_survival_fraction']}` | {blockers_text} |"
        )
    lines.extend(["", "## Next Required Step", "", f"- {summary['next_required_step']}", ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build DRD2 atom-typed backmapping support evidence.")
    parser.add_argument("--stage3-csv", default=DEFAULT_STAGE3_CSV)
    parser.add_argument("--ranking-rows-csv", default=DEFAULT_RANKING_ROWS_CSV)
    parser.add_argument("--atom-cache-csv", default=DEFAULT_ATOM_CACHE_CSV)
    parser.add_argument("--local-minimization-json", default=DEFAULT_LOCAL_MINIMIZATION_JSON)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--positive-ligand", default=DEFAULT_POSITIVE_LIGAND)
    parser.add_argument("--score-col", default=DEFAULT_SCORE_COL)
    parser.add_argument("--top-decoys", type=int, default=16)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_support(
        stage3_csv=args.stage3_csv,
        ranking_rows_csv=args.ranking_rows_csv,
        atom_cache_csv=args.atom_cache_csv,
        local_minimization_json=args.local_minimization_json,
        target=args.target,
        positive_ligand=args.positive_ligand,
        score_col=args.score_col,
        top_decoys=args.top_decoys,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
