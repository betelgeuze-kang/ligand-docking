#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem

from tools.wetlab_target_render_utils import load_json, write_artifact

TARGET_ID = "T. cruzi PDE"
DEFAULT_GAP_JSON = "runs/wetlab_tcruzi_pde_ligand_atomization_gap_packet_current.json"
DEFAULT_OUT_DIR = "runs/wetlab_tcruzi_pde_atomized_ligand_drafts_current"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_atomized_ligand_draft_packet_current.md"


def _text(value: Any) -> str:
    return "" if value in {"", None} else str(value).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_name(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return text.strip("_") or "ligand"


def _heavy_atom_count(mol: Chem.Mol) -> int:
    return sum(1 for atom in mol.GetAtoms() if atom.GetAtomicNum() > 1)


def _ligand_anchor_coords_from_pdb(path_text: str) -> list[np.ndarray]:
    if not path_text:
        return []
    path = Path(path_text)
    if not path.exists() or path.is_dir():
        return []
    coords: list[np.ndarray] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.startswith(("ATOM", "HETATM")):
                continue
            resname = line[17:20].strip()
            chain = line[21:22].strip()
            if resname != "LIG" and chain != "L":
                parts = line.split()
                if not (len(parts) >= 9 and ("LIG" in parts[3:5] or "L" in parts[4:6])):
                    continue
                try:
                    coords.append(np.array([float(parts[6]), float(parts[7]), float(parts[8])], dtype=float))
                except (IndexError, ValueError):
                    continue
                continue
            try:
                coords.append(
                    np.array(
                        [
                            float(line[30:38]),
                            float(line[38:46]),
                            float(line[46:54]),
                        ],
                        dtype=float,
                    )
                )
            except ValueError:
                continue
    return coords


def _rotation_between(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    source_norm = np.linalg.norm(source)
    target_norm = np.linalg.norm(target)
    if source_norm == 0 or target_norm == 0:
        return np.eye(3)
    a = source / source_norm
    b = target / target_norm
    cross = np.cross(a, b)
    dot = float(np.clip(np.dot(a, b), -1.0, 1.0))
    if np.linalg.norm(cross) < 1e-8:
        if dot > 0:
            return np.eye(3)
        axis = np.array([1.0, 0.0, 0.0])
        if abs(a[0]) > 0.9:
            axis = np.array([0.0, 1.0, 0.0])
        cross = np.cross(a, axis)
    skew = np.array(
        [
            [0.0, -cross[2], cross[1]],
            [cross[2], 0.0, -cross[0]],
            [-cross[1], cross[0], 0.0],
        ]
    )
    s = np.linalg.norm(cross)
    if s == 0:
        return np.eye(3)
    return np.eye(3) + skew + skew @ skew * ((1.0 - dot) / (s * s))


def _farthest_heavy_atom_pair(mol: Chem.Mol) -> tuple[int, int] | None:
    conf = mol.GetConformer()
    heavy = [atom.GetIdx() for atom in mol.GetAtoms() if atom.GetAtomicNum() > 1]
    if len(heavy) < 2:
        return None
    best_pair = (heavy[0], heavy[1])
    best_distance = -1.0
    for i, left in enumerate(heavy):
        left_pos = np.array(conf.GetAtomPosition(left), dtype=float)
        for right in heavy[i + 1 :]:
            right_pos = np.array(conf.GetAtomPosition(right), dtype=float)
            distance = float(np.linalg.norm(left_pos - right_pos))
            if distance > best_distance:
                best_distance = distance
                best_pair = (left, right)
    return best_pair


def _orient_to_pseudo_anchor(mol: Chem.Mol, anchors: list[np.ndarray]) -> dict[str, Any]:
    if len(anchors) < 2:
        return {
            "anchor_status": "no_two_point_pseudo_anchor",
            "pseudo_anchor_distance_A": None,
            "draft_anchor_pair_distance_A": None,
        }
    pair = _farthest_heavy_atom_pair(mol)
    if pair is None:
        return {
            "anchor_status": "insufficient_heavy_atoms",
            "pseudo_anchor_distance_A": None,
            "draft_anchor_pair_distance_A": None,
        }
    conf = mol.GetConformer()
    source_a = np.array(conf.GetAtomPosition(pair[0]), dtype=float)
    source_b = np.array(conf.GetAtomPosition(pair[1]), dtype=float)
    target_a, target_b = anchors[0], anchors[1]
    source_mid = (source_a + source_b) / 2.0
    target_mid = (target_a + target_b) / 2.0
    rotation = _rotation_between(source_b - source_a, target_b - target_a)
    for atom_idx in range(mol.GetNumAtoms()):
        pos = np.array(conf.GetAtomPosition(atom_idx), dtype=float)
        new_pos = rotation @ (pos - source_mid) + target_mid
        conf.SetAtomPosition(atom_idx, tuple(float(value) for value in new_pos))
    pseudo_distance = float(np.linalg.norm(target_b - target_a))
    draft_distance = float(np.linalg.norm(source_b - source_a))
    return {
        "anchor_status": "oriented_to_two_point_pseudo_anchor",
        "pseudo_anchor_distance_A": round(pseudo_distance, 6),
        "draft_anchor_pair_distance_A": round(draft_distance, 6),
        "anchor_distance_mismatch_A": round(abs(pseudo_distance - draft_distance), 6),
        "anchor_heavy_atom_pair": f"{pair[0]}:{pair[1]}",
    }


def _embed_atomized_ligand(smiles: str, *, seed: int) -> tuple[Chem.Mol | None, str, str]:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None, "invalid_smiles", "none"
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = seed
    status = AllChem.EmbedMolecule(mol, params)
    if status != 0:
        return None, f"rdkit_embed_failed_{status}", "none"
    if AllChem.MMFFHasAllMoleculeParams(mol):
        opt_status = AllChem.MMFFOptimizeMolecule(mol, maxIters=500)
        return mol, "embedded", f"mmff_status_{opt_status}"
    opt_status = AllChem.UFFOptimizeMolecule(mol, maxIters=500)
    return mol, "embedded", f"uff_status_{opt_status}"


def build_payload(
    gap_payload: dict[str, Any],
    *,
    source_gap_json: str = DEFAULT_GAP_JSON,
    out_dir: Path = Path(DEFAULT_OUT_DIR),
    seed_base: int = 20260514,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for rank, raw in enumerate(gap_payload.get("rows", []) or [], start=1):
        ligand_id = _text(raw.get("ligand_id"))
        smiles = _text(raw.get("ligand_smiles"))
        safe_id = _safe_name(ligand_id)
        mol, embed_status, optimization_status = _embed_atomized_ligand(smiles, seed=seed_base + rank)
        sdf_path = out_dir / f"{rank:02d}_{safe_id}.sdf"
        pdb_path = out_dir / f"{rank:02d}_{safe_id}.pdb"
        anchor_info: dict[str, Any] = {"anchor_status": "not_embedded"}
        heavy_count = 0
        total_atom_count = 0
        if mol is not None:
            anchor_info = _orient_to_pseudo_anchor(mol, _ligand_anchor_coords_from_pdb(_text(raw.get("backmapped_pdb"))))
            heavy_count = _heavy_atom_count(mol)
            total_atom_count = mol.GetNumAtoms()
            writer = Chem.SDWriter(str(sdf_path))
            writer.write(mol)
            writer.close()
            Chem.MolToPDBFile(mol, str(pdb_path))
        expected = int(raw.get("expected_ligand_heavy_atom_count_from_smiles") or 0)
        atomization_ready = bool(mol is not None and expected > 0 and heavy_count >= expected)
        rows.append(
            {
                "row_kind": "tcruzi_pde_atomized_ligand_draft_row",
                "priority_rank": rank,
                "target_id": TARGET_ID,
                "ligand_id": ligand_id,
                "source_pool_class": _text(raw.get("source_pool_class")),
                "binding_energy_proxy": _safe_float(raw.get("binding_energy_proxy")),
                "ligand_smiles": smiles,
                "expected_ligand_heavy_atom_count_from_smiles": expected,
                "atomized_ligand_heavy_atom_count": heavy_count,
                "atomized_ligand_total_atom_count_with_hydrogens": total_atom_count,
                "atomization_draft_ready": atomization_ready,
                "embed_status": embed_status,
                "optimization_status": optimization_status,
                **anchor_info,
                "atomized_ligand_sdf": sdf_path.as_posix() if mol is not None else "",
                "atomized_ligand_pdb": pdb_path.as_posix() if mol is not None else "",
                "source_pseudo_backmapped_pdb": _text(raw.get("backmapped_pdb")),
                "source_trajectory_npz": _text(raw.get("trajectory_npz")),
                "parameterization_status": "pending",
                "protein_local_minimization_status": "pending",
                "claim_promotion_allowed": False,
                "claim_policy": "atomized_ligand_draft_only_not_pose_preservation_or_local_min_survival_evidence",
                "next_action": (
                    "Parameterize the atomized ligand and run protein-ligand local minimization before treating this as pose-preservation evidence."
                ),
            }
        )

    ready_rows = [row for row in rows if row["atomization_draft_ready"]]
    anchor_rows = [row for row in rows if row.get("anchor_status") == "oriented_to_two_point_pseudo_anchor"]
    return {
        "summary": {
            "status": "wetlab_tcruzi_pde_atomized_ligand_draft_packet_ready",
            "target_id": TARGET_ID,
            "source_gap_json": source_gap_json,
            "out_dir": out_dir.as_posix(),
            "row_count": len(rows),
            "atomization_draft_ready_count": len(ready_rows),
            "two_point_anchor_oriented_count": len(anchor_rows),
            "parameterization_ready_count": 0,
            "protein_local_minimization_ready_count": 0,
            "claim_promotion_allowed": False,
            "commercial_gap_status": "blocked_parameterization_and_local_minimization",
            "next_required_step": (
                "Use the atomized ligand drafts as inputs for ligand parameterization and protein-ligand local minimization; do not use them as commercial pose-preservation evidence yet."
            ),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build atomized ligand drafts for T. cruzi PDE energy-hit seeds.")
    parser.add_argument("--gap-json", default=DEFAULT_GAP_JSON)
    parser.add_argument("--out-dir", type=Path, default=Path(DEFAULT_OUT_DIR))
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(load_json(args.gap_json), source_gap_json=args.gap_json, out_dir=args.out_dir)
    write_artifact(args.out_md, "Wetlab T. cruzi PDE Atomized Ligand Draft Packet", payload)
    print(args.out_md)


if __name__ == "__main__":
    main()
