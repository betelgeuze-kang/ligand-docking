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

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ROWS_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage5_ranking_rows.csv"
)
DEFAULT_STAGE3_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_CI_JSON = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage5_ranking_summary.json"
)
DEFAULT_READINESS_JSON = ""
DEFAULT_OUT_JSON = "runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json"
DEFAULT_OUT_MD = "runs/gpcr_guarded_100k_rank_failure_diagnostics_current.md"
DEFAULT_V4_REPLAY_EVAL_JSON = "runs/gpcr_acidic_anchor_v4_shadow_replay_eval_current.json"
DEFAULT_V4_REPLAY_SUMMARY_JSON = "runs/gpcr_acidic_anchor_v4_shadow_replay_summary_current.json"

SCORE_COL = "binding_score_composite_v7"
SCORE_COL_CANDIDATES = (
    "binding_score_composite_v7_residual_active",
    "binding_score_composite_v7",
)
TOP20_THRESHOLD = 0.20
CI_LOW_THRESHOLD = 0.45
NON_ADRB2_MARKERS = ("DRD", "HTR", "OPRM", "OPRD", "OPRK", "CHEMBL217", "CHEMBL224", "CHEMBL233")
DRD2_MARKERS = ("DRD2", "CHEMBL217")
FEATURE_COLUMNS = [
    "ligand_affinity_hint",
    "ligand_onsps_norm",
    "ligand_mw",
    "ligand_logp",
    "ligand_rot_bonds",
    "ligand_h_donors",
    "ligand_h_acceptors",
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "mean_min_distance_A",
    "contact_fraction",
    "stability_score",
]
ANCHOR_PROXY_SOURCE_COLUMNS = [
    "contact_fraction",
    "mean_min_distance_A",
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "stability_score",
    "ligand_affinity_hint",
    "ligand_onsps_norm",
    "residual_shadow_prior_pressure",
]
EXCLUDED_NATIVE_LIGAND_RESN = {
    "HOH",
    "WAT",
    "DOD",
    "PEG",
    "OLA",
    "OLC",
    "CLR",
    "CHL",
    "NA",
    "CL",
    "K",
    "MG",
    "CA",
    "ZN",
}
ACID_SIDECHAIN_ATOMS = {"ASP": {"OD1", "OD2"}, "GLU": {"OE1", "OE2"}}


def _resolve(path_like: str | Path | None) -> Path | None:
    if path_like is None or str(path_like).strip() == "":
        return None
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _is_positive(row: dict[str, Any]) -> bool:
    return _text(row.get("is_binder")).lower() in {"1", "true", "t", "yes", "y"}


def _is_non_adrb2(target: str) -> bool:
    upper = target.upper()
    return "ADRB2" not in upper and any(marker in upper for marker in NON_ADRB2_MARKERS)


def _is_drd2_target(target: str) -> bool:
    upper = target.upper()
    return any(marker in upper for marker in DRD2_MARKERS)


def _score_col(rows: list[dict[str, Any]]) -> str:
    observed = {key for row in rows for key in row}
    for col in SCORE_COL_CANDIDATES:
        if col in observed and any(_float(row.get(col)) is not None for row in rows):
            return col
    return SCORE_COL


def _rank_maps(rows: list[dict[str, Any]], score_col: str) -> tuple[dict[tuple[str, str], int], dict[tuple[str, str], int]]:
    scored = [
        (idx, row, _float(row.get(score_col)))
        for idx, row in enumerate(rows)
        if _float(row.get(score_col)) is not None
    ]
    scored.sort(key=lambda item: (item[2], _text(item[1].get("target")), _text(item[1].get("ligand_id"))))
    global_ranks = {
        (_text(row.get("target")), _text(row.get("ligand_id"))): rank
        for rank, (_idx, row, _score) in enumerate(scored, start=1)
    }
    within_ranks: dict[tuple[str, str], int] = {}
    by_target: dict[str, list[tuple[int, dict[str, Any], float | None]]] = {}
    for item in scored:
        by_target.setdefault(_text(item[1].get("target")), []).append(item)
    for target, target_rows in by_target.items():
        for rank, (_idx, row, _score) in enumerate(target_rows, start=1):
            within_ranks[(target, _text(row.get("ligand_id")))] = rank
    return global_ranks, within_ranks


def _stage3_feature_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        if key not in lookup:
            lookup[key] = row
    return lookup


def _feature_snapshot(row: dict[str, Any]) -> dict[str, float | None]:
    return {col: _float(row.get(col)) for col in FEATURE_COLUMNS if col in row}


def _clamp01(value: float | None) -> float | None:
    if value is None:
        return None
    return float(max(0.0, min(1.0, value)))


def _mean_present(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return float(sum(present) / len(present))


def _proxy_diagnostics(row: dict[str, Any]) -> dict[str, float | None]:
    contact = _float(row.get("contact_fraction"))
    distance = _float(row.get("mean_min_distance_A"))
    energy = _float(row.get("binding_energy_mmpbsa_kcal_mol_proxy"))
    stability = _float(row.get("stability_score"))
    affinity_hint = _float(row.get("ligand_affinity_hint"))
    prior_pressure = _float(row.get("residual_shadow_prior_pressure"))

    contact_support = _clamp01((contact or 0.0) / 0.006) if contact is not None else None
    distance_support = _clamp01((6.0 - distance) / 2.0) if distance is not None else None
    conserved_anchor_proxy = _mean_present([contact_support, distance_support])

    energy_support = _clamp01((-(energy or 0.0)) / 0.55) if energy is not None else None
    stability_support = _clamp01((stability or 0.0) / 0.006) if stability is not None else None
    pose_physics_support = _mean_present([conserved_anchor_proxy, energy_support, stability_support])

    prior_signal = prior_pressure if prior_pressure is not None else affinity_hint
    prior_overreward_without_anchor = None
    if prior_signal is not None and conserved_anchor_proxy is not None:
        prior_overreward_without_anchor = _clamp01(prior_signal * (1.0 - conserved_anchor_proxy))

    return {
        "conserved_anchor_proxy": conserved_anchor_proxy,
        "pose_physics_support": pose_physics_support,
        "prior_overreward_without_anchor": prior_overreward_without_anchor,
    }


def _compact_drd2_row(
    row: dict[str, Any],
    stage3: dict[str, Any],
    *,
    rank: int | None,
    within_target_rank: int | None,
    score_col: str,
) -> dict[str, Any]:
    merged = {**row, **stage3}
    return {
        "target": _text(row.get("target")),
        "ligand_id": _text(row.get("ligand_id")),
        "is_binder": _is_positive(row),
        "rank": rank,
        "within_target_rank": within_target_rank,
        "score": _float(row.get(score_col)),
        "diagnostics": _proxy_diagnostics(merged),
        "source_features": {col: _float(merged.get(col)) for col in ANCHOR_PROXY_SOURCE_COLUMNS if col in merged},
    }


def _mean_diagnostics(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    diagnostics = [row.get("diagnostics") for row in rows if isinstance(row.get("diagnostics"), dict)]
    return {
        key: _mean_present([diag.get(key) for diag in diagnostics])
        for key in ("conserved_anchor_proxy", "pose_physics_support", "prior_overreward_without_anchor")
    }


def _mean_atom_anchor_diagnostics(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    diagnostics = [
        row.get("atom_anchor_diagnostics")
        for row in rows
        if isinstance(row.get("atom_anchor_diagnostics"), dict) and row.get("atom_anchor_diagnostics", {}).get("available")
    ]
    return {
        key: _mean_present([diag.get(key) for diag in diagnostics])
        for key in (
            "anchor_mean_distance_A",
            "anchor_min_distance_A",
            "anchor_p10_distance_A",
            "anchor_contact_fraction_le_4A",
            "anchor_contact_fraction_le_6A",
        )
    }


def _decoy_margin_summary(
    decoys: list[dict[str, Any]],
    positive_score: float | None,
    score_col: str,
    limit: int,
) -> dict[str, Any]:
    selected = decoys[:limit]
    margins = [
        (_float(row.get(score_col)) or 0.0) - positive_score
        for row in selected
        if positive_score is not None and _float(row.get(score_col)) is not None
    ]
    best_decoy = selected[0] if selected else {}
    return {
        "selection": f"top{limit}_lowest_score_drd2_decoys",
        "decoy_count": len(selected),
        "best_decoy_ligand_id": _text(best_decoy.get("ligand_id")),
        "best_decoy_score": _float(best_decoy.get(score_col)),
        "best_margin": margins[0] if margins else None,
        "mean_margin": _mean_present(margins),
    }


def _top_decoy_cluster_anchor_overanchoring_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    overanchored_rows = [
        row
        for row in rows
        if (
            isinstance(row.get("diagnostics"), dict)
            and (row.get("diagnostics", {}).get("conserved_anchor_proxy") or 0.0) >= 0.75
        )
        or (
            isinstance(row.get("atom_anchor_diagnostics"), dict)
            and row.get("atom_anchor_diagnostics", {}).get("available")
            and (row.get("atom_anchor_diagnostics", {}).get("anchor_contact_fraction_le_4A") or 0.0) >= 0.5
        )
    ]
    return {
        "cluster_size": len(rows),
        "overanchored_decoy_count": len(overanchored_rows),
        "overanchoring_rule": (
            "conserved_anchor_proxy >= 0.75 or atom_anchor_contact_fraction_le_4A >= 0.5"
        ),
        "overanchored_ligand_ids": [row.get("ligand_id") for row in overanchored_rows],
        "atom_anchor_available_count": sum(
            1
            for row in rows
            if isinstance(row.get("atom_anchor_diagnostics"), dict)
            and row.get("atom_anchor_diagnostics", {}).get("available")
        ),
        "mean_atom_anchor_diagnostics": _mean_atom_anchor_diagnostics(rows),
        "mean_conserved_anchor_proxy": _mean_present(
            [
                row.get("diagnostics", {}).get("conserved_anchor_proxy")
                for row in rows
                if isinstance(row.get("diagnostics"), dict)
            ]
        ),
        "mean_prior_overreward_without_anchor": _mean_present(
            [
                row.get("diagnostics", {}).get("prior_overreward_without_anchor")
                for row in rows
                if isinstance(row.get("diagnostics"), dict)
            ]
        ),
    }


def _acidic_anchor_overcontact_probe(
    decoys: list[dict[str, Any]],
    stage3_lookup: dict[tuple[str, str], dict[str, Any]],
    *,
    limit: int = 50,
) -> dict[str, Any]:
    selected = decoys[:limit]
    diagnostics: list[dict[str, Any]] = []
    for row in selected:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        atom_diag = _atom_anchor_diagnostics({**row, **stage3_lookup.get(key, {})})
        if isinstance(atom_diag, dict) and atom_diag.get("available"):
            diagnostics.append(atom_diag)
    min_lt_3 = [
        diag
        for diag in diagnostics
        if (_float(diag.get("anchor_min_distance_A")) is not None)
        and (_float(diag.get("anchor_min_distance_A")) or 999.0) < 3.0
    ]
    p10_lt_3 = [
        diag
        for diag in diagnostics
        if (_float(diag.get("anchor_p10_distance_A")) is not None)
        and (_float(diag.get("anchor_p10_distance_A")) or 999.0) < 3.0
    ]
    mean_contact_le_4 = _mean_present(
        [_float(diag.get("anchor_contact_fraction_le_4A")) for diag in diagnostics]
    )
    return {
        "diagnostic_only": True,
        "probe_name": "acidic_anchor_overcontact_pressure_probe",
        "selection": f"top{limit}_lowest_score_drd2_decoys",
        "selected_decoy_count": len(selected),
        "atom_anchor_available_count": len(diagnostics),
        "anchor_min_distance_lt_3A_count": len(min_lt_3),
        "anchor_p10_distance_lt_3A_count": len(p10_lt_3),
        "anchor_min_distance_lt_3A_fraction": (len(min_lt_3) / len(diagnostics)) if diagnostics else None,
        "anchor_p10_distance_lt_3A_fraction": (len(p10_lt_3) / len(diagnostics)) if diagnostics else None,
        "mean_anchor_contact_fraction_le_4A": mean_contact_le_4,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "interpretation": (
            "Use only as a target-agnostic acidic-anchor overcontact diagnostic. A future scorer term must be "
            "shadow/replay reviewed and must not use target identity, labels, ranks, ligand IDs, or reference values."
        ),
    }


def _parse_pdb_anchor_template(path: str | Path | None) -> dict[str, Any]:
    pdb_path = _resolve(path)
    if pdb_path is None or not pdb_path.exists():
        return {"available": False, "reason": "native_pdb_missing", "anchor_atom_indices": []}
    protein_atoms: list[dict[str, Any]] = []
    acid_atoms: list[dict[str, Any]] = []
    het_groups: dict[tuple[str, str, str], list[list[float]]] = {}
    with pdb_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if line.startswith("ATOM"):
                atom_index = len(protein_atoms)
                atom_name = _text(line[12:16]).upper()
                resn = _text(line[17:20]).upper()
                chain = _text(line[21:22])
                resi = _text(line[22:26])
                try:
                    xyz = [float(line[30:38]), float(line[38:46]), float(line[46:54])]
                except Exception:
                    continue
                atom = {
                    "atom_index": atom_index,
                    "atom_name": atom_name,
                    "resn": resn,
                    "chain": chain,
                    "resi": resi,
                    "xyz": xyz,
                }
                protein_atoms.append(atom)
                if atom_name in ACID_SIDECHAIN_ATOMS.get(resn, set()):
                    acid_atoms.append(atom)
            elif line.startswith("HETATM"):
                resn = _text(line[17:20]).upper()
                if resn in EXCLUDED_NATIVE_LIGAND_RESN:
                    continue
                chain = _text(line[21:22])
                resi = _text(line[22:26])
                try:
                    xyz = [float(line[30:38]), float(line[38:46]), float(line[46:54])]
                except Exception:
                    continue
                het_groups.setdefault((resn, chain, resi), []).append(xyz)
    if not acid_atoms or not het_groups:
        return {"available": False, "reason": "acid_or_native_ligand_missing", "anchor_atom_indices": []}
    acid_xyz = np.asarray([atom["xyz"] for atom in acid_atoms], dtype=float)
    best: tuple[float, tuple[str, str, str], list[list[float]]] | None = None
    for group_key, coords in het_groups.items():
        if len(coords) < 5:
            continue
        lig_xyz = np.asarray(coords, dtype=float)
        min_dist = float(np.linalg.norm(acid_xyz[:, None, :] - lig_xyz[None, :, :], axis=2).min())
        if best is None or min_dist < best[0]:
            best = (min_dist, group_key, coords)
    if best is None:
        return {"available": False, "reason": "native_ligand_group_not_selected", "anchor_atom_indices": []}
    native_min_dist, native_ligand_key, native_ligand_coords = best
    native_ligand_xyz = np.asarray(native_ligand_coords, dtype=float)
    ranked_acids = sorted(
        [
            (
                float(np.linalg.norm(native_ligand_xyz - np.asarray(atom["xyz"], dtype=float), axis=1).min()),
                atom,
            )
            for atom in acid_atoms
        ],
        key=lambda item: (
            item[0],
            item[1]["resn"],
            item[1]["chain"],
            item[1]["resi"],
            item[1]["atom_name"],
        ),
    )
    anchor_residue = ranked_acids[0][1]
    anchor_atoms = [
        atom
        for atom in acid_atoms
        if atom["resn"] == anchor_residue["resn"]
        and atom["chain"] == anchor_residue["chain"]
        and atom["resi"] == anchor_residue["resi"]
    ]
    return {
        "available": True,
        "native_pdb": str(pdb_path),
        "native_ligand_resn": native_ligand_key[0],
        "native_ligand_chain": native_ligand_key[1],
        "native_ligand_resi": native_ligand_key[2],
        "native_ligand_min_acid_distance_A": native_min_dist,
        "anchor_resn": anchor_residue["resn"],
        "anchor_chain": anchor_residue["chain"],
        "anchor_resi": anchor_residue["resi"],
        "anchor_atom_names": [atom["atom_name"] for atom in anchor_atoms],
        "anchor_atom_indices": [int(atom["atom_index"]) for atom in anchor_atoms],
    }


def _atom_anchor_diagnostics(row: dict[str, Any]) -> dict[str, Any]:
    trajectory_npz = _text(row.get("trajectory_npz"))
    native_pdb = _text(row.get("protein_structure_source_path"))
    template = _parse_pdb_anchor_template(native_pdb)
    if not template.get("available"):
        return {
            "available": False,
            "reason": template.get("reason", "anchor_template_unavailable"),
            "native_pdb": native_pdb,
            "trajectory_npz": trajectory_npz,
        }
    npz_path = _resolve(trajectory_npz)
    if npz_path is None or not npz_path.exists():
        return {
            "available": False,
            "reason": "trajectory_npz_missing",
            "native_pdb": native_pdb,
            "trajectory_npz": trajectory_npz,
            "anchor_template": template,
        }
    try:
        with np.load(str(npz_path), allow_pickle=False) as npz:
            ligand_frames = np.asarray(npz["ligand_frames"], dtype=float)
            protein_atom_frames = np.asarray(npz["protein_atom_frames"], dtype=float)
    except Exception as exc:
        return {
            "available": False,
            "reason": f"trajectory_npz_unreadable:{type(exc).__name__}",
            "native_pdb": native_pdb,
            "trajectory_npz": trajectory_npz,
            "anchor_template": template,
        }
    anchor_indices = [idx for idx in template.get("anchor_atom_indices", []) if 0 <= int(idx) < protein_atom_frames.shape[1]]
    if ligand_frames.size == 0 or protein_atom_frames.size == 0 or not anchor_indices:
        return {
            "available": False,
            "reason": "ligand_or_anchor_frames_missing",
            "native_pdb": native_pdb,
            "trajectory_npz": trajectory_npz,
            "anchor_template": template,
        }
    anchor_frames = protein_atom_frames[:, anchor_indices, :]
    distances = np.linalg.norm(
        ligand_frames[:, :, None, :] - anchor_frames[:, None, :, :],
        axis=3,
    ).min(axis=(1, 2))
    return {
        "available": True,
        "basis": "native_pdb_acidic_anchor_plus_trajectory_npz",
        "native_pdb": native_pdb,
        "trajectory_npz": trajectory_npz,
        "anchor_template": template,
        "frame_count": int(len(distances)),
        "anchor_min_distance_A": float(np.min(distances)),
        "anchor_mean_distance_A": float(np.mean(distances)),
        "anchor_p10_distance_A": float(np.percentile(distances, 10)),
        "anchor_contact_fraction_le_4A": float(np.mean(distances <= 4.0)),
        "anchor_contact_fraction_le_6A": float(np.mean(distances <= 6.0)),
    }


def _drd2_pose_physics_diagnostics(
    rows: list[dict[str, Any]],
    stage3_lookup: dict[tuple[str, str], dict[str, Any]],
    global_ranks: dict[tuple[str, str], int],
    within_ranks: dict[tuple[str, str], int],
    score_col: str,
) -> dict[str, Any]:
    drd2_rows = [row for row in rows if _is_drd2_target(_text(row.get("target")))]
    positives = [row for row in drd2_rows if _is_positive(row)]
    decoys = [row for row in drd2_rows if not _is_positive(row) and _float(row.get(score_col)) is not None]
    positives.sort(
        key=lambda row: (
            global_ranks.get((_text(row.get("target")), _text(row.get("ligand_id"))), 10**12),
            _text(row.get("ligand_id")),
        )
    )
    decoys.sort(key=lambda row: (_float(row.get(score_col)) or 0.0, _text(row.get("ligand_id"))))

    positive = positives[0] if positives else {}
    positive_key = (_text(positive.get("target")), _text(positive.get("ligand_id"))) if positive else ("", "")
    cluster_rows = []
    for row in decoys[:12]:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        cluster_rows.append(
            _compact_drd2_row(
                row,
                stage3_lookup.get(key, {}),
                rank=global_ranks.get(key),
                within_target_rank=within_ranks.get(key),
                score_col=score_col,
            )
        )

    positive_payload = (
        _compact_drd2_row(
            positive,
            stage3_lookup.get(positive_key, {}),
            rank=global_ranks.get(positive_key),
            within_target_rank=within_ranks.get(positive_key),
            score_col=score_col,
        )
        if positive
        else {}
    )
    if positive_payload:
        positive_payload["atom_anchor_diagnostics"] = _atom_anchor_diagnostics(
            {**positive, **stage3_lookup.get(positive_key, {})}
        )
    for row in cluster_rows:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        row["atom_anchor_diagnostics"] = _atom_anchor_diagnostics(
            {**row, **stage3_lookup.get(key, {})}
        )

    return {
        "slice": "DRD2_pose_physics_conserved_anchor_proxy",
        "metadata": {
            "diagnostic_only": True,
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "feature_basis": "stage3_csv_proxy_not_atom_anchor",
            "proxy_note": (
                "No atom-resolved conserved GPCR anchor annotations are available in this packet; "
                "conserved_anchor_proxy, pose_physics_support, and prior_overreward_without_anchor are "
                "computed only from shared stage3 CSV pose/physics/prior columns."
            ),
            "proxy_source_columns": ANCHOR_PROXY_SOURCE_COLUMNS,
            "score_column": score_col,
        },
        "positive": positive_payload,
        "top_decoy_cluster": {
            "selection": "lowest_score_drd2_decoys_from_latest_ranking_rows",
            "size": len(cluster_rows),
            "rows": cluster_rows,
            "mean_diagnostics": _mean_diagnostics(cluster_rows),
            "mean_atom_anchor_diagnostics": _mean_atom_anchor_diagnostics(cluster_rows),
        },
    }


def _drd2_target_internal_pairwise_diagnostic(
    rows: list[dict[str, Any]],
    stage3_lookup: dict[tuple[str, str], dict[str, Any]],
    global_ranks: dict[tuple[str, str], int],
    within_ranks: dict[tuple[str, str], int],
    score_col: str,
) -> dict[str, Any]:
    drd2_rows = [row for row in rows if _is_drd2_target(_text(row.get("target")))]
    positives = [row for row in drd2_rows if _is_positive(row) and _float(row.get(score_col)) is not None]
    decoys = [row for row in drd2_rows if not _is_positive(row) and _float(row.get(score_col)) is not None]
    positives.sort(
        key=lambda row: (
            within_ranks.get((_text(row.get("target")), _text(row.get("ligand_id"))), 10**12),
            _text(row.get("ligand_id")),
        )
    )
    decoys.sort(key=lambda row: (_float(row.get(score_col)) or 0.0, _text(row.get("ligand_id"))))

    positive = positives[0] if positives else {}
    positive_key = (_text(positive.get("target")), _text(positive.get("ligand_id"))) if positive else ("", "")
    positive_score = _float(positive.get(score_col)) if positive else None
    decoys_above_positive = [
        row
        for row in decoys
        if positive_score is not None and (_float(row.get(score_col)) or 0.0) < positive_score
    ]
    pairwise_wins = [
        row
        for row in decoys
        if positive_score is not None and (_float(row.get(score_col)) or 0.0) > positive_score
    ]

    cluster_rows: list[dict[str, Any]] = []
    for row in decoys[:12]:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        cluster_row = _compact_drd2_row(
            row,
            stage3_lookup.get(key, {}),
            rank=global_ranks.get(key),
            within_target_rank=within_ranks.get(key),
            score_col=score_col,
        )
        cluster_row["atom_anchor_diagnostics"] = _atom_anchor_diagnostics({**row, **stage3_lookup.get(key, {})})
        cluster_rows.append(cluster_row)

    positive_payload = (
        _compact_drd2_row(
            positive,
            stage3_lookup.get(positive_key, {}),
            rank=global_ranks.get(positive_key),
            within_target_rank=within_ranks.get(positive_key),
            score_col=score_col,
        )
        if positive
        else {}
    )

    return {
        "slice": "DRD2_target_internal_pairwise_rank_failure",
        "metadata": {
            "diagnostic_only": True,
            "replay_only": True,
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "score_column": score_col,
            "score_order": "lower_score_ranks_higher",
            "forbidden_live_features": [
                "target",
                "is_binder",
                "rank",
                "within_target_rank",
                "reference_binding_kcal_mol",
            ],
        },
        "positive": positive_payload,
        "decoy_count": len(decoys),
        "decoys_above_positive_count": len(decoys_above_positive),
        "decoys_above_positive_fraction": (len(decoys_above_positive) / len(decoys)) if decoys else None,
        "decoys_above_positive_ligand_ids": [_text(row.get("ligand_id")) for row in decoys_above_positive],
        "top12_decoy_margin_vs_positive": _decoy_margin_summary(decoys, positive_score, score_col, 12),
        "top50_decoy_margin_vs_positive": _decoy_margin_summary(decoys, positive_score, score_col, 50),
        "pairwise_win_rate": (len(pairwise_wins) / len(decoys)) if decoys else None,
        "pairwise_win_count": len(pairwise_wins),
        "top_decoy_cluster_anchor_overanchoring_summary": _top_decoy_cluster_anchor_overanchoring_summary(
            cluster_rows
        ),
        "acidic_anchor_overcontact_probe": _acidic_anchor_overcontact_probe(
            decoys,
            stage3_lookup,
            limit=50,
        ),
        "shadow_replay_snapshot": {
            "not_claim_evidence": True,
            "ci_low_computed": True,
            "base_r2_pr_auc": 0.5186945103743427,
            "base_r2_pr_auc_ci_low": 0.1485815545422209,
            "base_r2_top20_hit_rate": 0.25,
            "family_anchor_v2_shadow_pr_auc": 0.5767474245351905,
            "family_anchor_v2_shadow_pr_auc_ci_low": 0.21066694653866244,
            "family_anchor_v2_shadow_pr_auc_ci_low_threshold": 0.45,
            "family_anchor_v2_shadow_top20_hit_rate": 0.25,
            "family_anchor_v2_shadow_drd2_global_rank": 8562,
            "family_anchor_v2_shadow_drd2_target_rank": 2435,
            "family_anchor_v2_shadow_drd2_decoys_above_positive_count": 2434,
            "family_anchor_v2_shadow_drd2_pairwise_win_rate": 0.7565756575657565,
            "family_anchor_v2_shadow_mean_mismatch_pressure_positive": 0.0,
            "family_anchor_v2_shadow_mean_mismatch_pressure_decoy": 0.8541410783206624,
            "family_anchor_v2_shadow_claim_review_status": "blocked_ci_low_below_threshold",
        },
        "guarded_validation_prep": {
            "ready_for_guarded_apply": False,
            "blockers": [
                "diagnostic_only_replay_packet",
                "shadow_replay_pr_auc_ci_low_below_threshold",
                "full_guarded_validation_missing",
            ],
            "required_next_evidence": [
                "target_internal_pairwise_replay_review",
                "guarded_apply_candidate_review",
                "full_100k_ci_low_top20_claim_review_green",
            ],
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "full_100k_rerun_allowed_in_this_task": False,
        },
    }


def _ci_summary(ci_payload: dict[str, Any]) -> dict[str, Any]:
    summary = ci_payload.get("summary") if isinstance(ci_payload.get("summary"), dict) else {}
    stage6 = (
        ci_payload.get("stages", {}).get("stage6_operational_gate", {})
        if isinstance(ci_payload.get("stages"), dict)
        else {}
    )
    metrics_unique = ci_payload.get("metrics_unique") if isinstance(ci_payload.get("metrics_unique"), dict) else {}
    metrics_ci_unique = ci_payload.get("metrics_ci_unique") if isinstance(ci_payload.get("metrics_ci_unique"), dict) else {}
    topk_unique = ci_payload.get("topk_unique") if isinstance(ci_payload.get("topk_unique"), list) else []
    top20_hit_rate = None
    for row in topk_unique:
        if isinstance(row, dict) and int(_float(row.get("k")) or 0) == 20:
            top20_hit_rate = _float(row.get("hit_rate"))
            break
    ci_low_from_stage5 = None
    if isinstance(metrics_ci_unique.get("pr_auc"), dict):
        ci_low_from_stage5 = _float(metrics_ci_unique.get("pr_auc", {}).get("low"))
    return {
        "ranking_pr_auc": (
            _float(summary.get("ranking_pr_auc"))
            if _float(summary.get("ranking_pr_auc")) is not None
            else _float(stage6.get("ranking_pr_auc"))
            if _float(stage6.get("ranking_pr_auc")) is not None
            else _float(metrics_unique.get("pr_auc"))
        ),
        "ranking_pr_auc_ci_low": (
            _float(summary.get("ranking_pr_auc_ci_low"))
            if _float(summary.get("ranking_pr_auc_ci_low")) is not None
            else _float(stage6.get("ranking_pr_auc_ci_low"))
            if _float(stage6.get("ranking_pr_auc_ci_low")) is not None
            else ci_low_from_stage5
        ),
        "ranking_topk_hit_rate": (
            _float(summary.get("ranking_topk_hit_rate"))
            if _float(summary.get("ranking_topk_hit_rate")) is not None
            else _float(stage6.get("ranking_topk_hit_rate"))
            if _float(stage6.get("ranking_topk_hit_rate")) is not None
            else top20_hit_rate
        ),
        "ranking_positive_count": (
            _float(summary.get("ranking_positive_count"))
            if _float(summary.get("ranking_positive_count")) is not None
            else _float(stage6.get("ranking_positive_count"))
            if _float(stage6.get("ranking_positive_count")) is not None
            else _float(metrics_unique.get("positive_count"))
        ),
        "ci_low_threshold": _float(summary.get("threshold")) or CI_LOW_THRESHOLD,
        "top20_threshold": TOP20_THRESHOLD,
    }


def _ci_low_stability_metadata(ci: dict[str, Any]) -> dict[str, Any]:
    base_pr_auc = _float(ci.get("ranking_pr_auc"))
    base_ci_low = _float(ci.get("ranking_pr_auc_ci_low"))
    threshold = _float(ci.get("ci_low_threshold")) or CI_LOW_THRESHOLD
    v2_shadow_pr_auc = 0.5767474245351905
    v2_shadow_ci_low = 0.21066694653866244
    v2_shadow_top20_hit_rate = 0.25
    v2_shadow_drd2_decoys_above_positive_count = 2434
    v2_shadow_drd2_pairwise_win_rate = 0.7565756575657565
    ci_low_computed = base_ci_low is not None
    base_gap = (threshold - base_ci_low) if ci_low_computed else None
    v2_shadow_gap = threshold - v2_shadow_ci_low
    blocked = (not ci_low_computed) or (base_ci_low < threshold) or (v2_shadow_ci_low < threshold)
    blockers: list[str] = []
    if not ci_low_computed:
        blockers.append("bootstrap_pr_auc_ci_low_missing")
    if base_ci_low is None or base_ci_low < threshold:
        blockers.append("base_bootstrap_pr_auc_ci_low_below_threshold")
    if v2_shadow_ci_low < threshold:
        blockers.append("v2_shadow_bootstrap_pr_auc_ci_low_below_threshold")
    if blockers:
        blockers.append("do_not_promote_from_point_pr_auc")
    return {
        "diagnostic_only": True,
        "ci_low_computed": ci_low_computed,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "threshold_relaxation_allowed": False,
        "base_pr_auc": base_pr_auc,
        "base_pr_auc_ci_low": base_ci_low,
        "base_ci_low_gap_to_threshold": base_gap if base_ci_low is None or base_ci_low < threshold else 0.0,
        "v2_shadow_pr_auc": v2_shadow_pr_auc,
        "v2_shadow_pr_auc_ci_low": v2_shadow_ci_low,
        "v2_shadow_top20_hit_rate": v2_shadow_top20_hit_rate,
        "v2_shadow_ci_low_gap_to_threshold": v2_shadow_gap,
        "v2_shadow_drd2_decoys_above_positive_count": v2_shadow_drd2_decoys_above_positive_count,
        "v2_shadow_drd2_pairwise_win_rate": v2_shadow_drd2_pairwise_win_rate,
        "ci_low_threshold": threshold,
        "ci_low_gap_to_threshold": max(
            value
            for value in [
                base_gap if base_gap is not None else threshold,
                v2_shadow_gap,
                0.0,
            ]
        )
        if blocked
        else 0.0,
        "ci_low_status": "blocked_below_threshold" if blocked else "green",
        "recommended_next_action": "gpcr_core_family_anchor_ci_stability_v3_diagnostic_only",
        "blockers": sorted(set(blockers)),
        "stability_hypotheses": [
            "bootstrap_positive_support_instability",
            "point_pr_auc_improvement_not_enough_for_claim",
            "target_agnostic_v2_terms_need_ci_low_replay_review",
        ],
    }


def _latest_v4_replay_review() -> dict[str, Any]:
    eval_path = _resolve(DEFAULT_V4_REPLAY_EVAL_JSON)
    summary_path = _resolve(DEFAULT_V4_REPLAY_SUMMARY_JSON)
    if eval_path is None or not eval_path.exists():
        return {"available": False}
    eval_payload = _read_json(eval_path)
    summary_payload = _read_json(summary_path) if summary_path and summary_path.exists() else {}
    metrics = eval_payload.get("metrics_unique") if isinstance(eval_payload.get("metrics_unique"), dict) else {}
    ci = eval_payload.get("metrics_ci_unique") if isinstance(eval_payload.get("metrics_ci_unique"), dict) else {}
    pr_auc_ci = ci.get("pr_auc") if isinstance(ci.get("pr_auc"), dict) else {}
    top20 = None
    for row in eval_payload.get("topk_unique", []):
        if isinstance(row, dict) and int(row.get("k") or 0) == 20:
            top20 = _float(row.get("hit_rate"))
            break
    residual = (
        summary_payload.get("residual_prototype")
        if isinstance(summary_payload.get("residual_prototype"), dict)
        else {}
    )
    pr_auc = _float(metrics.get("pr_auc"))
    pr_auc_ci_low = _float(pr_auc_ci.get("low"))
    status = "reject_evidence"
    if (
        pr_auc is not None
        and pr_auc > 0.5767474245351905
        and pr_auc_ci_low is not None
        and pr_auc_ci_low > 0.21066694653866244
        and top20 is not None
        and top20 >= 0.25
    ):
        status = "shadow_replay_improved_needs_guarded_review"
    return {
        "available": True,
        "status": status,
        "eval_json": str(eval_path),
        "summary_json": str(summary_path) if summary_path else "",
        "pr_auc": pr_auc,
        "pr_auc_ci_low": pr_auc_ci_low,
        "top20_hit_rate": top20,
        "gate_activation_count": int(residual.get("positive_delta_count") or 0),
        "shadow_only_active_locked": bool(residual.get("shadow_only_active_locked", False)),
        "score_scaling_mode": summary_payload.get("score_reference_scaling", {}).get("mode")
        if isinstance(summary_payload.get("score_reference_scaling"), dict)
        else "",
        "score_reference_stats_hash": summary_payload.get("score_reference_scaling", {}).get("stats_hash")
        if isinstance(summary_payload.get("score_reference_scaling"), dict)
        else "",
    }


def _post_v3_acidic_anchor_review(
    pairwise: dict[str, Any],
    ci: dict[str, Any],
) -> dict[str, Any]:
    acidic_probe = (
        pairwise.get("acidic_anchor_overcontact_probe")
        if isinstance(pairwise.get("acidic_anchor_overcontact_probe"), dict)
        else {}
    )
    selected_count = int(acidic_probe.get("selected_decoy_count") or 0)
    available_count = int(acidic_probe.get("atom_anchor_available_count") or 0)
    min_lt_3_count = int(acidic_probe.get("anchor_min_distance_lt_3A_count") or 0)
    p10_lt_3_count = int(acidic_probe.get("anchor_p10_distance_lt_3A_count") or 0)
    v4_replay = _latest_v4_replay_review()
    return {
        "diagnostic_only": True,
        "candidate_variant": "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
        "candidate_role": "shadow_only_guarded_comparison_direction",
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "threshold_relaxation_allowed": False,
        "target_identity_feature_allowed": False,
        "label_rank_ligand_id_or_reference_binding_feature_allowed": False,
        "required_scaling_mode": "fixed_family_reference",
        "source_probe": "drd2_target_internal_pairwise_diagnostic.acidic_anchor_overcontact_probe",
        "selected_decoy_count": selected_count,
        "atom_anchor_available_count": available_count,
        "anchor_min_distance_lt_3A_count": min_lt_3_count,
        "anchor_p10_distance_lt_3A_count": p10_lt_3_count,
        "anchor_min_distance_lt_3A_fraction": (
            min_lt_3_count / available_count if available_count else None
        ),
        "anchor_p10_distance_lt_3A_fraction": (
            p10_lt_3_count / available_count if available_count else None
        ),
        "overcontact_signal_present": bool(available_count and min_lt_3_count > 0),
        "current_ci_low": ci.get("ranking_pr_auc_ci_low"),
        "ci_low_threshold": ci.get("ci_low_threshold"),
        "short_replay_acceptance": {
            "pr_auc_must_exceed": 0.5767474245351905,
            "pr_auc_ci_low_must_exceed": 0.21066694653866244,
            "top20_hit_rate_min": 0.25,
            "drd2_decoys_above_positive_must_be_below": 2434,
            "drd2_pairwise_win_rate_must_exceed": 0.7565756575657565,
        },
        "blocked_until": [
            "shadow_replay_beats_v2_without_metric_regression",
            "leakage_review_no_target_label_rank_ligand_id_reference_inputs",
            "full_100k_ci_low_top20_claim_review_green",
        ],
        "latest_v4_replay": v4_replay,
        "interpretation": (
            "Post-v3 evidence supports a shadow-only proxy gate for overcontact/prior-overreward review. "
            "It is not atom-resolved scorer evidence and cannot authorize delivery, router, or platform claims."
        ),
    }


def build_packet(
    *,
    rows_csv: str | Path | None = DEFAULT_ROWS_CSV,
    stage3_csv: str | Path | None = DEFAULT_STAGE3_CSV,
    ci_json: str | Path | None = DEFAULT_CI_JSON,
    readiness_json: str | Path | None = DEFAULT_READINESS_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    rows_path = _resolve(rows_csv)
    stage3_path = _resolve(stage3_csv)
    ci_path = _resolve(ci_json)
    readiness_path = _resolve(readiness_json)
    rows = _read_csv(rows_path)
    stage3_rows = _read_csv(stage3_path)
    ci_payload = _read_json(ci_path)
    readiness_payload = _read_json(readiness_path)
    stage3_lookup = _stage3_feature_lookup(stage3_rows)
    score_col = _score_col(rows)
    global_ranks, within_ranks = _rank_maps(rows, score_col)

    positives: list[dict[str, Any]] = []
    for row in rows:
        if not _is_positive(row):
            continue
        target = _text(row.get("target"))
        ligand_id = _text(row.get("ligand_id"))
        key = (target, ligand_id)
        stage3 = stage3_lookup.get(key, {})
        positives.append(
            {
                "target": target,
                "ligand_id": ligand_id,
                "non_adrb2": _is_non_adrb2(target),
                "global_rank": global_ranks.get(key),
                "within_target_rank": within_ranks.get(key),
                "score": _float(row.get(score_col)),
                "mean_min_distance_A": _float(row.get("mean_min_distance_A")),
                "reference_binding_kcal_mol": _float(row.get("reference_binding_kcal_mol")),
                "features": _feature_snapshot(stage3),
            }
        )
    positives.sort(key=lambda row: (row.get("global_rank") or 10**12, row["target"], row["ligand_id"]))

    top_intrusions: list[dict[str, Any]] = []
    sorted_rows = sorted(
        [row for row in rows if _float(row.get(score_col)) is not None],
        key=lambda row: (_float(row.get(score_col)) or 0.0, _text(row.get("target")), _text(row.get("ligand_id"))),
    )
    for rank, row in enumerate(sorted_rows, start=1):
        if _is_positive(row):
            continue
        top_intrusions.append(
            {
                "rank": rank,
                "target": _text(row.get("target")),
                "ligand_id": _text(row.get("ligand_id")),
                "score": _float(row.get(score_col)),
                "mean_min_distance_A": _float(row.get("mean_min_distance_A")),
                "reference_binding_kcal_mol": _float(row.get("reference_binding_kcal_mol")),
            }
        )
        if len(top_intrusions) >= 12:
            break

    ci = _ci_summary(ci_payload)
    readiness_summary = readiness_payload.get("summary") if isinstance(readiness_payload.get("summary"), dict) else {}
    non_adrb2_tail = [
        row
        for row in positives
        if row["non_adrb2"] and ((row.get("global_rank") or 10**12) > 20 or (row.get("within_target_rank") or 10**12) > 20)
    ]
    blockers: list[str] = []
    if not rows:
        blockers.append("ranking_rows_missing")
    if ci["ranking_pr_auc_ci_low"] is None or ci["ranking_pr_auc_ci_low"] < ci["ci_low_threshold"]:
        blockers.append("ci_low_below_threshold")
    if ci["ranking_topk_hit_rate"] is None or ci["ranking_topk_hit_rate"] < ci["top20_threshold"]:
        blockers.append("top20_stability_not_green")
    if non_adrb2_tail:
        blockers.append("non_adrb2_positive_tail_rank")
    if top_intrusions:
        blockers.append("target_internal_decoy_intrusion")

    v4_replay = _latest_v4_replay_review()
    next_action = "shadow_replay_acidic_anchor_overcontact_prior_gate_v4"
    next_required_step = (
        "Do not relaunch the same packet as claim evidence. "
        "Use the post-v3 acidic-anchor overcontact review to run a fixed-family-reference, shadow-only "
        "v4 shadow replay before any guarded apply or fresh full 100k claim review."
    )
    if v4_replay.get("available") and v4_replay.get("status") == "reject_evidence":
        next_action = "redesign_fixed_reference_live_gpcr_shadow_gate_after_v4_reject"
        next_required_step = (
            "Do not relaunch v4 unchanged as claim evidence. The fixed-family-reference v4 shadow replay is reject "
            "evidence, so redesign a fixed-reference-live shadow gate before any guarded apply or fresh full 100k "
            "claim review."
        )

    drd2_pose_physics = _drd2_pose_physics_diagnostics(
        rows,
        stage3_lookup,
        global_ranks,
        within_ranks,
        score_col,
    )
    drd2_pairwise = _drd2_target_internal_pairwise_diagnostic(
        rows,
        stage3_lookup,
        global_ranks,
        within_ranks,
        score_col,
    )

    return {
        "packet_type": "gpcr_guarded_100k_rank_failure_diagnostics",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "input_artifacts": {
            "rows_csv": str(rows_path) if rows_path else None,
            "stage3_csv": str(stage3_path) if stage3_path else None,
            "ci_json": str(ci_path) if ci_path else None,
            "readiness_json": str(readiness_path) if readiness_path else None,
        },
        "summary": {
            "status": "blocked_ranking_quality" if blockers else "diagnostic_green",
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "next_action": next_action,
            "positive_count": len(positives),
            "non_adrb2_positive_count": sum(1 for row in positives if row["non_adrb2"]),
            "non_adrb2_tail_positive_count": len(non_adrb2_tail),
            "worst_positive_global_rank": max((row.get("global_rank") or 0 for row in positives), default=None),
            "worst_positive_within_target_rank": max((row.get("within_target_rank") or 0 for row in positives), default=None),
            "ranking_pr_auc": ci["ranking_pr_auc"],
            "ranking_pr_auc_ci_low": ci["ranking_pr_auc_ci_low"],
            "ranking_topk_hit_rate": ci["ranking_topk_hit_rate"],
            "blocker_count": len(blockers),
            "blockers": blockers,
            "readiness_blockers": readiness_summary.get("blockers", []),
            "next_action": next_action,
            "next_required_step": next_required_step,
        },
        "positive_rank_diagnostics": positives,
        "top_decoy_intrusions": top_intrusions,
        "ci_low_stability_metadata": _ci_low_stability_metadata(ci),
        "drd2_pose_physics_diagnostics": drd2_pose_physics,
        "drd2_target_internal_pairwise_diagnostic": drd2_pairwise,
        "post_v3_acidic_anchor_review": _post_v3_acidic_anchor_review(drd2_pairwise, ci),
        "claim_boundary": {
            "diagnostic_only_not_claim_authorizing": True,
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR Guarded 100k Rank Failure Diagnostics",
        "",
        "## Summary",
        f"- status: `{summary['status']}`",
        f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
        f"- scorer_apply_allowed: `{str(summary['scorer_apply_allowed']).lower()}`",
        f"- next_action: `{summary['next_action']}`",
        f"- positive_count: `{summary['positive_count']}`",
        f"- non_adrb2_positive_count: `{summary['non_adrb2_positive_count']}`",
        f"- non_adrb2_tail_positive_count: `{summary['non_adrb2_tail_positive_count']}`",
        f"- ranking_pr_auc_ci_low: `{summary['ranking_pr_auc_ci_low']}`",
        f"- ranking_topk_hit_rate: `{summary['ranking_topk_hit_rate']}`",
        f"- blockers: `{', '.join(summary['blockers'])}`",
        "",
        "## Positive Ranks",
        "",
        "| global_rank | within_target_rank | target | ligand_id | score | mean_min_distance_A |",
        "| ---: | ---: | --- | --- | ---: | ---: |",
    ]
    for row in payload.get("positive_rank_diagnostics", []):
        lines.append(
            "| {global_rank} | {within_target_rank} | `{target}` | `{ligand_id}` | {score} | {distance} |".format(
                global_rank=row.get("global_rank"),
                within_target_rank=row.get("within_target_rank"),
                target=row.get("target"),
                ligand_id=row.get("ligand_id"),
                score=row.get("score"),
                distance=row.get("mean_min_distance_A"),
            )
        )
    lines.extend(
        [
            "",
            "## Top Decoy Intrusions",
            "",
            "| rank | target | ligand_id | score | mean_min_distance_A |",
            "| ---: | --- | --- | ---: | ---: |",
        ]
    )
    for row in payload.get("top_decoy_intrusions", []):
        lines.append(
            "| {rank} | `{target}` | `{ligand_id}` | {score} | {distance} |".format(
                rank=row.get("rank"),
                target=row.get("target"),
                ligand_id=row.get("ligand_id"),
                score=row.get("score"),
                distance=row.get("mean_min_distance_A"),
            )
        )
    ci_meta = (
        payload.get("ci_low_stability_metadata")
        if isinstance(payload.get("ci_low_stability_metadata"), dict)
        else {}
    )
    lines.extend(
        [
            "",
            "## CI-Low Stability Metadata",
            "",
            f"- diagnostic_only: `{str(ci_meta.get('diagnostic_only', False)).lower()}`",
            f"- ci_low_computed: `{str(ci_meta.get('ci_low_computed', False)).lower()}`",
            f"- base_pr_auc: `{ci_meta.get('base_pr_auc', '')}`",
            f"- base_pr_auc_ci_low: `{ci_meta.get('base_pr_auc_ci_low', '')}`",
            f"- v2_shadow_pr_auc: `{ci_meta.get('v2_shadow_pr_auc', '')}`",
            f"- v2_shadow_pr_auc_ci_low: `{ci_meta.get('v2_shadow_pr_auc_ci_low', '')}`",
            f"- v2_shadow_top20_hit_rate: `{ci_meta.get('v2_shadow_top20_hit_rate', '')}`",
            f"- v2_shadow_drd2_decoys_above_positive_count: `{ci_meta.get('v2_shadow_drd2_decoys_above_positive_count', '')}`",
            f"- v2_shadow_drd2_pairwise_win_rate: `{ci_meta.get('v2_shadow_drd2_pairwise_win_rate', '')}`",
            f"- ci_low_threshold: `{ci_meta.get('ci_low_threshold', '')}`",
            f"- ci_low_gap_to_threshold: `{ci_meta.get('ci_low_gap_to_threshold', '')}`",
            f"- ci_low_status: `{ci_meta.get('ci_low_status', '')}`",
            f"- recommended_next_action: `{ci_meta.get('recommended_next_action', '')}`",
        ]
    )
    drd2 = payload.get("drd2_pose_physics_diagnostics") if isinstance(payload.get("drd2_pose_physics_diagnostics"), dict) else {}
    drd2_meta = drd2.get("metadata") if isinstance(drd2.get("metadata"), dict) else {}
    drd2_positive = drd2.get("positive") if isinstance(drd2.get("positive"), dict) else {}
    drd2_cluster = drd2.get("top_decoy_cluster") if isinstance(drd2.get("top_decoy_cluster"), dict) else {}
    positive_atom_anchor = (
        drd2_positive.get("atom_anchor_diagnostics")
        if isinstance(drd2_positive.get("atom_anchor_diagnostics"), dict)
        else {}
    )
    cluster_atom_anchor = (
        drd2_cluster.get("mean_atom_anchor_diagnostics")
        if isinstance(drd2_cluster.get("mean_atom_anchor_diagnostics"), dict)
        else {}
    )
    lines.extend(
        [
            "",
            "## DRD2 Pose/Physics Anchor Proxy",
            "",
            f"- feature_basis: `{drd2_meta.get('feature_basis', '')}`",
            f"- proxy_source_columns: `{', '.join(drd2_meta.get('proxy_source_columns', []))}`",
            f"- positive_ligand_id: `{drd2_positive.get('ligand_id', '')}`",
            f"- top_decoy_cluster_size: `{drd2_cluster.get('size', 0)}`",
            f"- positive_atom_anchor_mean_distance_A: `{positive_atom_anchor.get('anchor_mean_distance_A', '')}`",
            f"- decoy_cluster_atom_anchor_mean_distance_A: `{cluster_atom_anchor.get('anchor_mean_distance_A', '')}`",
        ]
    )
    pairwise = (
        payload.get("drd2_target_internal_pairwise_diagnostic")
        if isinstance(payload.get("drd2_target_internal_pairwise_diagnostic"), dict)
        else {}
    )
    pairwise_positive = pairwise.get("positive") if isinstance(pairwise.get("positive"), dict) else {}
    overanchor = (
        pairwise.get("top_decoy_cluster_anchor_overanchoring_summary")
        if isinstance(pairwise.get("top_decoy_cluster_anchor_overanchoring_summary"), dict)
        else {}
    )
    acidic_probe = (
        pairwise.get("acidic_anchor_overcontact_probe")
        if isinstance(pairwise.get("acidic_anchor_overcontact_probe"), dict)
        else {}
    )
    post_v3_review = (
        payload.get("post_v3_acidic_anchor_review")
        if isinstance(payload.get("post_v3_acidic_anchor_review"), dict)
        else {}
    )
    shadow = pairwise.get("shadow_replay_snapshot") if isinstance(pairwise.get("shadow_replay_snapshot"), dict) else {}
    guarded = pairwise.get("guarded_validation_prep") if isinstance(pairwise.get("guarded_validation_prep"), dict) else {}
    lines.extend(
        [
            "",
            "## DRD2 Target-Internal Pairwise Diagnostic",
            "",
            f"- diagnostic_only: `{str(pairwise.get('metadata', {}).get('diagnostic_only', False)).lower()}`",
            f"- replay_only: `{str(pairwise.get('metadata', {}).get('replay_only', False)).lower()}`",
            f"- positive_ligand_id: `{pairwise_positive.get('ligand_id', '')}`",
            f"- positive_within_target_rank: `{pairwise_positive.get('within_target_rank', '')}`",
            f"- decoys_above_positive_count: `{pairwise.get('decoys_above_positive_count', '')}`",
            f"- decoys_above_positive_fraction: `{pairwise.get('decoys_above_positive_fraction', '')}`",
            f"- pairwise_win_rate: `{pairwise.get('pairwise_win_rate', '')}`",
            f"- pairwise_win_count: `{pairwise.get('pairwise_win_count', '')}`",
            f"- top12_best_margin_vs_positive: `{pairwise.get('top12_decoy_margin_vs_positive', {}).get('best_margin', '')}`",
            f"- top50_mean_margin_vs_positive: `{pairwise.get('top50_decoy_margin_vs_positive', {}).get('mean_margin', '')}`",
            f"- overanchored_decoy_count: `{overanchor.get('overanchored_decoy_count', '')}`",
            f"- acidic_anchor_probe_available_count: `{acidic_probe.get('atom_anchor_available_count', '')}`",
            f"- acidic_anchor_min_lt_3A_count: `{acidic_probe.get('anchor_min_distance_lt_3A_count', '')}`",
            f"- acidic_anchor_p10_lt_3A_count: `{acidic_probe.get('anchor_p10_distance_lt_3A_count', '')}`",
            f"- post_v3_candidate_variant: `{post_v3_review.get('candidate_variant', '')}`",
            f"- post_v3_required_scaling_mode: `{post_v3_review.get('required_scaling_mode', '')}`",
            f"- post_v3_overcontact_signal_present: `{str(post_v3_review.get('overcontact_signal_present', False)).lower()}`",
            f"- shadow_replay_pr_auc: `{shadow.get('family_anchor_v2_shadow_pr_auc', '')}`",
            f"- shadow_replay_pr_auc_ci_low: `{shadow.get('family_anchor_v2_shadow_pr_auc_ci_low', '')}`",
            f"- shadow_replay_drd2_global_rank: `{shadow.get('family_anchor_v2_shadow_drd2_global_rank', '')}`",
            f"- shadow_replay_drd2_decoys_above_positive_count: `{shadow.get('family_anchor_v2_shadow_drd2_decoys_above_positive_count', '')}`",
            f"- shadow_replay_drd2_pairwise_win_rate: `{shadow.get('family_anchor_v2_shadow_drd2_pairwise_win_rate', '')}`",
            f"- shadow_replay_ci_low_computed: `{str(shadow.get('ci_low_computed', False)).lower()}`",
            f"- shadow_replay_claim_review_status: `{shadow.get('family_anchor_v2_shadow_claim_review_status', '')}`",
            f"- ready_for_guarded_apply: `{str(guarded.get('ready_for_guarded_apply', False)).lower()}`",
        ]
    )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    return "\n".join(lines)


def write_outputs(
    *,
    rows_csv: str | Path | None,
    stage3_csv: str | Path | None,
    ci_json: str | Path | None,
    readiness_json: str | Path | None,
    out_json: str | Path,
    out_md: str | Path,
) -> dict[str, Any]:
    payload = build_packet(
        rows_csv=rows_csv,
        stage3_csv=stage3_csv,
        ci_json=ci_json,
        readiness_json=readiness_json,
    )
    out_json_path = _resolve(out_json)
    out_md_path = _resolve(out_md)
    assert out_json_path is not None
    assert out_md_path is not None
    _write_json(out_json_path, payload)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build diagnostic packet for GPCR guarded 100k rank failure.")
    parser.add_argument("--rows-csv", default=DEFAULT_ROWS_CSV)
    parser.add_argument("--stage3-csv", default=DEFAULT_STAGE3_CSV)
    parser.add_argument("--ci-json", default=DEFAULT_CI_JSON)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_outputs(
        rows_csv=args.rows_csv,
        stage3_csv=args.stage3_csv,
        ci_json=args.ci_json,
        readiness_json=args.readiness_json,
        out_json=args.out_json,
        out_md=args.out_md,
    )


if __name__ == "__main__":
    main()
