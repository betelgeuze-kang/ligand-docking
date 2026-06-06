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

try:  # pragma: no cover - optional dependency in some CI slices.
    from rdkit import Chem  # type: ignore
except Exception:  # pragma: no cover
    Chem = None  # type: ignore

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ROWS_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage5_ranking_rows.csv"
)
DEFAULT_STAGE3_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_ATOM_CACHE_CSV = "runs/gpcr_atom_window_anchor_feature_cache_drd2_top64_current.csv"
DEFAULT_DIAGNOSTICS_JSON = "runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_drd2_pose_generation_repair_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_drd2_pose_generation_repair_packet_current.md"
DEFAULT_OUT_CSV = "runs/gpcr_drd2_pose_generation_repair_packet_rows_current.csv"

DEFAULT_TARGET = "CHEMBL217_DRD2_HUMAN"
DEFAULT_POSITIVE_LIGAND = "CHEMBL301265"
SCORE_COL_CANDIDATES = (
    "binding_score_composite_v7_residual_active",
    "binding_score_composite_v7",
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


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
    f = _float(value)
    return int(f) if f is not None else None


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _is_positive(row: dict[str, Any]) -> bool:
    return _text(row.get("is_binder")).lower() in {"1", "true", "t", "yes", "y"}


def _score_col(rows: list[dict[str, Any]]) -> str:
    observed = {key for row in rows for key in row}
    for col in SCORE_COL_CANDIDATES:
        if col in observed and any(_float(row.get(col)) is not None for row in rows):
            return col
    return SCORE_COL_CANDIDATES[-1]


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
    # Fallback is intentionally simple: enough for packet-level coverage telemetry.
    tokens = re.findall(r"Cl|Br|[BCNOFPSI][a-z]?|[cnops]", s)
    return len(tokens) if tokens else None


def _basic_amine_proxy(smiles: str) -> int:
    s = _text(smiles)
    if not s:
        return 0
    if Chem is not None:
        try:
            mol = Chem.MolFromSmiles(s)
            if mol is not None:
                for atom in mol.GetAtoms():
                    if atom.GetAtomicNum() != 7:
                        continue
                    if atom.GetIsAromatic():
                        continue
                    if atom.GetFormalCharge() > 0 or atom.GetTotalNumHs() > 0 or atom.GetDegree() >= 2:
                        return 1
        except Exception:
            pass
    return 1 if re.search(r"(?<![A-Za-z])N|[CN]N|NCC|CN\(|\[NH", s) else 0


def _npz_shape_summary(path_text: str) -> dict[str, Any]:
    path = _resolve(path_text) if path_text else None
    if path is None or not path.exists():
        return {
            "trajectory_npz": str(path) if path else "",
            "trajectory_available": False,
            "trajectory_reason": "missing",
        }
    try:
        with np.load(str(path), allow_pickle=False) as npz:
            ligand_frames = np.asarray(npz["ligand_frames"])
            protein_atom_frames = np.asarray(npz["protein_atom_frames"]) if "protein_atom_frames" in npz else None
            frame_indices = np.asarray(npz["frame_indices"]) if "frame_indices" in npz else None
    except Exception as exc:
        return {
            "trajectory_npz": str(path),
            "trajectory_available": False,
            "trajectory_reason": f"unreadable:{type(exc).__name__}",
        }
    ligand_frame_atom_count = int(ligand_frames.shape[1]) if ligand_frames.ndim >= 3 else None
    protein_atom_count = int(protein_atom_frames.shape[1]) if protein_atom_frames is not None and protein_atom_frames.ndim >= 3 else None
    return {
        "trajectory_npz": str(path),
        "trajectory_available": True,
        "trajectory_reason": "ok",
        "trajectory_frame_count": int(ligand_frames.shape[0]) if ligand_frames.ndim >= 1 else 0,
        "ligand_frame_atom_count": ligand_frame_atom_count,
        "protein_atom_count": protein_atom_count,
        "frame_indices_count": int(frame_indices.shape[0]) if frame_indices is not None and frame_indices.ndim >= 1 else None,
    }


def _lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        if key not in out:
            out[key] = row
    return out


def _failure_tags(row: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    if row.get("is_positive"):
        if (row.get("within_target_rank") or 0) > 100:
            tags.append("positive_tail_rank")
        if row.get("backmapping_atom_coverage_ratio") is not None and row["backmapping_atom_coverage_ratio"] < 0.5:
            tags.append("positive_backmapping_atom_coverage_low")
        if row.get("contact_fraction") is not None and row["contact_fraction"] < 0.005:
            tags.append("positive_contact_fraction_weak")
        if row.get("binding_energy_mmpbsa_kcal_mol_proxy") is not None and row[
            "binding_energy_mmpbsa_kcal_mol_proxy"
        ] > -0.05:
            tags.append("positive_binding_proxy_weak")
    else:
        if row.get("atom_contact_fraction_le_2p8A") is not None and row["atom_contact_fraction_le_2p8A"] >= 0.5:
            tags.append("decoy_overanchor_too_close")
        if row.get("atom_contact_fraction_2p8_4p2A") is not None and row["atom_contact_fraction_2p8_4p2A"] >= 0.75:
            tags.append("decoy_anchor_window_like")
        if row.get("basic_amine_proxy") and (row.get("ligand_h_donors") or 0) >= 3 and (row.get("ligand_h_acceptors") or 0) >= 5:
            tags.append("multipolar_basic_decoy")
        if row.get("score") is not None and row.get("positive_score") is not None and row["score"] < row["positive_score"]:
            tags.append("decoy_above_positive")
    return tags


def _row_packet(
    *,
    rank_row: dict[str, Any],
    stage3_row: dict[str, Any],
    cache_row: dict[str, Any],
    global_rank: int | None,
    within_rank: int | None,
    score_col: str,
    positive_score: float | None,
) -> dict[str, Any]:
    target = _text(rank_row.get("target") or stage3_row.get("target") or cache_row.get("target"))
    ligand_id = _text(rank_row.get("ligand_id") or stage3_row.get("ligand_id") or cache_row.get("ligand_id"))
    smiles = _text(stage3_row.get("ligand_smiles") or stage3_row.get("smiles"))
    heavy_atoms = _heavy_atom_count(smiles)
    traj = _npz_shape_summary(_text(stage3_row.get("trajectory_npz") or cache_row.get("class_a_atom_anchor_trajectory_npz")))
    ligand_frame_atoms = traj.get("ligand_frame_atom_count")
    coverage = None
    if heavy_atoms and ligand_frame_atoms is not None:
        coverage = float(ligand_frame_atoms / max(heavy_atoms, 1))
    row: dict[str, Any] = {
        "target": target,
        "ligand_id": ligand_id,
        "queue_id": _text(stage3_row.get("queue_id") or rank_row.get("queue_id")),
        "is_positive": _is_positive(rank_row),
        "global_rank": global_rank,
        "within_target_rank": within_rank,
        "score": _float(rank_row.get(score_col)),
        "positive_score": positive_score,
        "ligand_smiles": smiles,
        "trajectory_npz": _text(stage3_row.get("trajectory_npz") or cache_row.get("class_a_atom_anchor_trajectory_npz")),
        "protein_structure_source_path": _text(
            stage3_row.get("protein_structure_source_path") or cache_row.get("class_a_atom_anchor_native_pdb")
        ),
        "smiles_heavy_atom_count": heavy_atoms,
        "ligand_frame_atom_count": ligand_frame_atoms,
        "backmapping_atom_coverage_ratio": coverage,
        "trajectory_frame_count": traj.get("trajectory_frame_count"),
        "trajectory_available": bool(traj.get("trajectory_available")),
        "atom_anchor_available": _int(cache_row.get("class_a_atom_anchor_available")),
        "atom_anchor_min_distance_A": _float(cache_row.get("class_a_atom_anchor_min_distance_A")),
        "atom_anchor_p10_distance_A": _float(cache_row.get("class_a_atom_anchor_p10_distance_A")),
        "atom_anchor_mean_distance_A": _float(cache_row.get("class_a_atom_anchor_mean_distance_A")),
        "atom_contact_fraction_le_2p8A": _float(cache_row.get("class_a_atom_anchor_contact_fraction_le_2p8A")),
        "atom_contact_fraction_2p8_4p2A": _float(cache_row.get("class_a_atom_anchor_contact_fraction_2p8_4p2A")),
        "binding_energy_mmpbsa_kcal_mol_proxy": _float(stage3_row.get("binding_energy_mmpbsa_kcal_mol_proxy")),
        "contact_fraction": _float(stage3_row.get("contact_fraction")),
        "stability_score": _float(stage3_row.get("stability_score")),
        "mean_min_distance_A": _float(rank_row.get("mean_min_distance_A") or stage3_row.get("mean_min_distance_A")),
        "ligand_h_donors": _float(stage3_row.get("ligand_h_donors")),
        "ligand_h_acceptors": _float(stage3_row.get("ligand_h_acceptors")),
        "ligand_rot_bonds": _float(stage3_row.get("ligand_rot_bonds")),
        "ligand_logp": _float(stage3_row.get("ligand_logp")),
        "basic_amine_proxy": _basic_amine_proxy(smiles),
    }
    row["failure_tags"] = _failure_tags(row)
    row["failure_tag_text"] = ",".join(row["failure_tags"])
    return row


def build_packet(
    *,
    rows_csv: str | Path = DEFAULT_ROWS_CSV,
    stage3_csv: str | Path = DEFAULT_STAGE3_CSV,
    atom_cache_csv: str | Path = DEFAULT_ATOM_CACHE_CSV,
    diagnostics_json: str | Path = DEFAULT_DIAGNOSTICS_JSON,
    target: str = DEFAULT_TARGET,
    positive_ligand: str = DEFAULT_POSITIVE_LIGAND,
    top_decoys: int = 64,
    generated_at_local: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rank_rows = [row for row in _read_csv(rows_csv) if _text(row.get("target")) == target]
    stage3 = _lookup(_read_csv(stage3_csv))
    cache = _lookup(_read_csv(atom_cache_csv))
    diagnostics = _read_json(diagnostics_json)
    score_col = _score_col(rank_rows)
    ranked = sorted(
        [row for row in rank_rows if _float(row.get(score_col)) is not None],
        key=lambda row: (_float(row.get(score_col)) or float("inf"), _text(row.get("ligand_id"))),
    )
    global_rank_by_key: dict[tuple[str, str], int] = {}
    for all_rank, row in enumerate(
        sorted(
            [row for row in _read_csv(rows_csv) if _float(row.get(score_col)) is not None],
            key=lambda row: (_float(row.get(score_col)) or float("inf"), _text(row.get("target")), _text(row.get("ligand_id"))),
        ),
        start=1,
    ):
        global_rank_by_key[(_text(row.get("target")), _text(row.get("ligand_id")))] = all_rank
    within_rank_by_key = {(_text(row.get("target")), _text(row.get("ligand_id"))): idx for idx, row in enumerate(ranked, start=1)}
    positive_key = (target, positive_ligand)
    positive_rank_row = next((row for row in ranked if _text(row.get("ligand_id")) == positive_ligand), {})
    positive_score = _float(positive_rank_row.get(score_col))
    decoys_above = [
        row
        for row in ranked
        if not _is_positive(row)
        and positive_score is not None
        and (_float(row.get(score_col)) is not None)
        and (_float(row.get(score_col)) or 0.0) < positive_score
    ]
    selected_rank_rows = decoys_above[: max(0, int(top_decoys))]
    if positive_rank_row:
        selected_rank_rows.append(positive_rank_row)
    rows: list[dict[str, Any]] = []
    for row in selected_rank_rows:
        key = (_text(row.get("target")), _text(row.get("ligand_id")))
        rows.append(
            _row_packet(
                rank_row=row,
                stage3_row=stage3.get(key, {}),
                cache_row=cache.get(key, {}),
                global_rank=global_rank_by_key.get(key),
                within_rank=within_rank_by_key.get(key),
                score_col=score_col,
                positive_score=positive_score,
            )
        )
    positive_packet = next((row for row in rows if row.get("is_positive")), {})
    decoy_packets = [row for row in rows if not row.get("is_positive")]
    overanchor_count = sum(1 for row in decoy_packets if "decoy_overanchor_too_close" in row.get("failure_tags", []))
    window_like_count = sum(1 for row in decoy_packets if "decoy_anchor_window_like" in row.get("failure_tags", []))
    multipolar_count = sum(1 for row in decoy_packets if "multipolar_basic_decoy" in row.get("failure_tags", []))
    coverage_low = bool(
        positive_packet.get("backmapping_atom_coverage_ratio") is not None
        and positive_packet["backmapping_atom_coverage_ratio"] < 0.5
    )
    missing_pose_rmsd = "drd2_pose_physics_diagnostics" in diagnostics and diagnostics.get(
        "drd2_pose_physics_diagnostics", {}
    ).get("positive_pose_preservation_rmsd_A") in {None, "None", ""}
    missing_local_min = "drd2_pose_physics_diagnostics" in diagnostics and diagnostics.get(
        "drd2_pose_physics_diagnostics", {}
    ).get("positive_local_minimization_survival_support") in {None, "None", ""}

    blockers = []
    if positive_packet.get("within_target_rank", 0) and positive_packet.get("within_target_rank", 0) > 100:
        blockers.append("drd2_positive_tail_rank")
    if coverage_low:
        blockers.append("positive_backmapping_atom_coverage_low")
    if missing_pose_rmsd:
        blockers.append("pose_preservation_rmsd_missing")
    if missing_local_min:
        blockers.append("local_minimization_survival_missing")
    if overanchor_count > 0:
        blockers.append("overanchored_decoy_cluster_present")
    if multipolar_count > 0:
        blockers.append("multipolar_basic_decoy_intrusion_present")

    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "blocked_pose_generation_repair_required",
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "target": target,
        "positive_ligand_id": positive_ligand,
        "score_col": score_col,
        "positive_global_rank": positive_packet.get("global_rank"),
        "positive_within_target_rank": positive_packet.get("within_target_rank"),
        "decoys_above_positive_count": len(decoys_above),
        "inspected_decoy_count": len(decoy_packets),
        "overanchored_decoy_count": overanchor_count,
        "atom_window_like_decoy_count": window_like_count,
        "multipolar_basic_decoy_count": multipolar_count,
        "positive_ligand_frame_atom_count": positive_packet.get("ligand_frame_atom_count"),
        "positive_smiles_heavy_atom_count": positive_packet.get("smiles_heavy_atom_count"),
        "positive_backmapping_atom_coverage_ratio": positive_packet.get("backmapping_atom_coverage_ratio"),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "next_action": "repair_drd2_pose_generation_backmapping_then_rebuild_hard_decoys",
        "next_required_step": (
            "Do not relaunch v8/v9 or run a full 100k claim review. First rebuild DRD2 pose/backmapping so "
            "the ligand trajectory carries atom-typed cationic-center evidence, add pose-preservation RMSD and "
            "local-minimization survival checks, then rebuild the hard-decoy set into overanchor, multipolar-basic, "
            "and valid-anchor challenge slices."
        ),
    }
    payload = {
        "packet_type": "gpcr_drd2_pose_generation_repair_packet",
        "summary": summary,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "full_100k_claim_review_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
        "input_artifacts": {
            "rows_csv": str(_resolve(rows_csv)),
            "stage3_csv": str(_resolve(stage3_csv)),
            "atom_cache_csv": str(_resolve(atom_cache_csv)),
            "diagnostics_json": str(_resolve(diagnostics_json)),
        },
        "positive_row": positive_packet,
        "decoy_cluster_summary": {
            "decoys_above_positive_count": len(decoys_above),
            "inspected_decoy_count": len(decoy_packets),
            "overanchored_decoy_count": overanchor_count,
            "atom_window_like_decoy_count": window_like_count,
            "multipolar_basic_decoy_count": multipolar_count,
        },
        "repair_requirements": [
            "full_ligand_atom_typed_backmapping_for_drd2_positive_and_top_decoys",
            "cationic_center_to_asp114_distance_not_ligand_any_atom_min_distance",
            "pose_preservation_rmsd_A_for_positive_and_top_decoy_slices",
            "local_minimization_survival_fraction_for_positive_and_top_decoy_slices",
            "hard_decoy_slice_labels_overanchor_multipolar_basic_valid_anchor",
            "non_leaky_drd2_htr2a_oprm1_positive_expansion_before_claim_review",
        ],
        "rows": rows[: max(0, int(top_decoys)) + 1],
    }
    return payload, rows


def _render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# GPCR DRD2 Pose Generation Repair Packet",
        "",
        "## Summary",
        "",
        f"- status: `{s['status']}`",
        f"- claim_promotion_allowed: `{str(s['claim_promotion_allowed']).lower()}`",
        f"- scorer_apply_allowed: `{str(s['scorer_apply_allowed']).lower()}`",
        f"- target: `{s['target']}`",
        f"- positive_ligand_id: `{s['positive_ligand_id']}`",
        f"- positive_global_rank: `{s['positive_global_rank']}`",
        f"- positive_within_target_rank: `{s['positive_within_target_rank']}`",
        f"- decoys_above_positive_count: `{s['decoys_above_positive_count']}`",
        f"- inspected_decoy_count: `{s['inspected_decoy_count']}`",
        f"- overanchored_decoy_count: `{s['overanchored_decoy_count']}`",
        f"- atom_window_like_decoy_count: `{s['atom_window_like_decoy_count']}`",
        f"- multipolar_basic_decoy_count: `{s['multipolar_basic_decoy_count']}`",
        f"- positive_ligand_frame_atom_count: `{s['positive_ligand_frame_atom_count']}`",
        f"- positive_smiles_heavy_atom_count: `{s['positive_smiles_heavy_atom_count']}`",
        f"- positive_backmapping_atom_coverage_ratio: `{s['positive_backmapping_atom_coverage_ratio']}`",
        f"- blockers: `{', '.join(s['blockers'])}`",
        f"- next_action: `{s['next_action']}`",
        "",
        "## Next Required Step",
        "",
        s["next_required_step"],
        "",
        "## Repair Requirements",
        "",
    ]
    for item in payload.get("repair_requirements", []):
        lines.append(f"- `{item}`")
    lines.extend(["", "This packet is diagnostic-only and cannot widen GPCR/router/platform claim wording.", ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a DRD2 pose/backmapping repair packet for GPCR recovery.")
    parser.add_argument("--rows-csv", default=DEFAULT_ROWS_CSV)
    parser.add_argument("--stage3-csv", default=DEFAULT_STAGE3_CSV)
    parser.add_argument("--atom-cache-csv", default=DEFAULT_ATOM_CACHE_CSV)
    parser.add_argument("--diagnostics-json", default=DEFAULT_DIAGNOSTICS_JSON)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--positive-ligand", default=DEFAULT_POSITIVE_LIGAND)
    parser.add_argument("--top-decoys", type=int, default=64)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload, rows = build_packet(
        rows_csv=args.rows_csv,
        stage3_csv=args.stage3_csv,
        atom_cache_csv=args.atom_cache_csv,
        diagnostics_json=args.diagnostics_json,
        target=args.target,
        positive_ligand=args.positive_ligand,
        top_decoys=int(args.top_decoys),
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, rows)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
