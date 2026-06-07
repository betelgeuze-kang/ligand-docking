#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, write_artifact

try:
    from rdkit import Chem
except Exception:  # pragma: no cover - exercised only when RDKit is absent.
    Chem = None  # type: ignore[assignment]

TARGET_ID = "T. cruzi PDE"
DEFAULT_QUEUE_JSON = "runs/wetlab_tcruzi_pde_pose_backmapping_closure_queue_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_ligand_atomization_gap_packet_current.md"
MIN_ATOM_COVERAGE_RATIO = 0.80


def _text(value: Any) -> str:
    return "" if value in {"", None} else str(value).strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _heavy_atom_count(smiles: str) -> int:
    if not smiles or Chem is None:
        return 0
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return 0
    return int(mol.GetNumHeavyAtoms())


def _atomization_status(expected_heavy_atoms: int, observed_ligand_atoms: int) -> tuple[str, float]:
    if expected_heavy_atoms <= 0:
        return "blocked_expected_heavy_atom_count_unavailable", 0.0
    ratio = observed_ligand_atoms / expected_heavy_atoms
    if ratio >= MIN_ATOM_COVERAGE_RATIO:
        return "atomization_ready_for_pose_metric_preflight", ratio
    return "blocked_ligand_atomization_gap", ratio


def build_payload(
    queue_payload: dict[str, Any],
    *,
    source_queue_json: str = DEFAULT_QUEUE_JSON,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for rank, raw in enumerate(queue_payload.get("rows", []) or [], start=1):
        row = dict(raw or {})
        smiles = _text(row.get("ligand_smiles"))
        expected_heavy_atoms = _heavy_atom_count(smiles)
        observed_ligand_atoms = _safe_int(row.get("backmapped_ligand_atoms"))
        status, coverage_ratio = _atomization_status(expected_heavy_atoms, observed_ligand_atoms)
        atom_gap = max(0, expected_heavy_atoms - observed_ligand_atoms)
        rows.append(
            {
                "row_kind": "tcruzi_pde_ligand_atomization_gap_row",
                "priority_rank": rank,
                "target_id": TARGET_ID,
                "ligand_id": _text(row.get("ligand_id")),
                "source_pool_class": _text(row.get("source_pool_class")),
                "binding_energy_proxy": _safe_float(row.get("binding_energy_proxy")),
                "mean_min_distance_A": _safe_float(row.get("mean_min_distance_A")),
                "stability_score": _safe_float(row.get("stability_score")),
                "ligand_smiles": smiles,
                "expected_ligand_heavy_atom_count_from_smiles": expected_heavy_atoms,
                "observed_backmapped_ligand_atom_count": observed_ligand_atoms,
                "ligand_atom_coverage_ratio": round(coverage_ratio, 6),
                "missing_ligand_atom_count": atom_gap,
                "atomization_status": status,
                "backmapped_pdb": _text(row.get("backmapped_pdb")),
                "score_json": _text(row.get("score_json")),
                "trajectory_npz": _text(row.get("trajectory_npz")),
                "claim_promotion_allowed": False,
                "metric_policy": "do_not_treat_two_bead_ligand_backmaps_as_all_atom_pose_preservation",
                "next_action": (
                    "Generate chemically faithful all-atom ligand coordinates/parameters, then rerun pose-preservation, "
                    "backmapping, and local-minimization survival measurements."
                ),
            }
        )

    blocked_rows = [row for row in rows if row["atomization_status"] == "blocked_ligand_atomization_gap"]
    ready_rows = [row for row in rows if row["atomization_status"] == "atomization_ready_for_pose_metric_preflight"]
    worst = max(rows, key=lambda row: row["missing_ligand_atom_count"], default={})
    return {
        "summary": {
            "status": "wetlab_tcruzi_pde_ligand_atomization_gap_packet_ready",
            "target_id": TARGET_ID,
            "source_queue_json": source_queue_json,
            "queue_row_count": len(rows),
            "atomization_ready_count": len(ready_rows),
            "atomization_blocked_count": len(blocked_rows),
            "min_atom_coverage_ratio_required": MIN_ATOM_COVERAGE_RATIO,
            "worst_gap_ligand_id": _text(worst.get("ligand_id")),
            "worst_gap_missing_ligand_atom_count": worst.get("missing_ligand_atom_count"),
            "claim_promotion_allowed": False,
            "commercial_gap_status": "blocked_ligand_atomization_gap" if blocked_rows else "atomization_ready_for_review",
            "next_required_step": (
                "Build chemically faithful all-atom ligand coordinates/parameters for queued PDE energy hits before using pose-preservation or local-minimization metrics for commercial promotion."
                if blocked_rows
                else "Run pose-preservation/backmapping/local-minimization preflight on atomization-ready queued PDE seeds."
            ),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the T. cruzi PDE ligand atomization gap packet.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(load_json(args.queue_json), source_queue_json=args.queue_json)
    write_artifact(args.out_md, "Wetlab T. cruzi PDE Ligand Atomization Gap Packet", payload)
    print(args.out_md)


if __name__ == "__main__":
    main()
