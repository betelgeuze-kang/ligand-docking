#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from tools.wetlab.probe_wetlab_tcruzi_pde_translation_evidence import (
    TRANSLATION_DISTANCE_THRESHOLD_A,
    TRANSLATION_ENERGY_THRESHOLD,
    TRANSLATION_STABILITY_THRESHOLD,
)
from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

TARGET_ID = "T. cruzi PDE"
DEFAULT_TRANSLATION_EVIDENCE_JSON = "runs/wetlab_tcruzi_pde_translation_evidence_probe_current.json"
DEFAULT_METRIC_SCALE_JSON = "runs/wetlab_tcruzi_pde_metric_scale_gap_packet_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_pose_backmapping_closure_queue_current.md"

SOURCE_SPECS = [
    (
        "external_homolog_pdeb1_seed",
        "runs/wetlab_tcruzi_pde_external_pdeb1_seed_screen/stage3_scores.csv",
    ),
    (
        "external_homolog_pdeb1_geomstab_rescore",
        "runs/wetlab_tcruzi_pde_external_geomstab_rescore*/stage3_scores.csv",
    ),
    (
        "external_homolog_pdeb1_adress_rescue",
        "runs/wetlab_tcruzi_pde_external_geomstab_adress_rescue_scores*/stage3_scores.csv",
    ),
    (
        "external_homolog_pdeb1_contact_rescue",
        "runs/wetlab_tcruzi_pde_external_geomstab_contact_rescue_scores*/stage3_scores.csv",
    ),
    (
        "external_bindingdb_similarity_seed",
        "runs/wetlab_tcruzi_pde_bindingdb_similarity_seed_screen/stage*_stage3_scores.csv",
    ),
]


def _text(value: Any) -> str:
    return "" if value in {"", None} else str(value).strip()


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _paths_for_glob(root: Path, pattern: str) -> list[Path]:
    return [
        path
        for path in sorted(root.glob(pattern))
        if path.is_file() and path.name != "stage_stage3_scores.csv"
    ]


def _read_score_rows(path: Path, source_pool_class: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            row = dict(raw)
            row["source_path"] = path.as_posix()
            row["source_pool_class"] = source_pool_class
            rows.append(row)
    return rows


def _energy_hit_row(raw: dict[str, Any]) -> dict[str, Any] | None:
    ligand_id = _text(raw.get("ligand_id"))
    energy = _safe_float(raw.get("binding_energy_proxy"))
    distance = _safe_float(raw.get("mean_min_distance_A"))
    stability = _safe_float(raw.get("stability_score"))
    if not ligand_id or energy is None or energy > TRANSLATION_ENERGY_THRESHOLD:
        return None
    distance_pass = distance is not None and distance <= TRANSLATION_DISTANCE_THRESHOLD_A
    stability_pass = stability is not None and stability >= TRANSLATION_STABILITY_THRESHOLD
    source_pool_class = _text(raw.get("source_pool_class"))
    source_rank = {
        "external_homolog_pdeb1_geomstab_rescore": 0,
        "external_homolog_pdeb1_contact_rescue": 1,
        "external_homolog_pdeb1_adress_rescue": 2,
        "external_bindingdb_similarity_seed": 3,
        "external_homolog_pdeb1_seed": 4,
    }.get(source_pool_class, 9)
    return {
        "ligand_id": ligand_id,
        "ligand_smiles": _text(raw.get("ligand_smiles")),
        "target": _text(raw.get("target"),) or TARGET_ID,
        "source_path": _text(raw.get("source_path")),
        "source_pool_class": source_pool_class,
        "source_rank": source_rank,
        "queue_id": _text(raw.get("queue_id")),
        "binding_energy_proxy": energy,
        "mean_min_distance_A": distance,
        "stability_score": stability,
        "contact_fraction": _safe_float(raw.get("contact_fraction")),
        "binding_energy_mmpbsa_std": _safe_float(raw.get("binding_energy_mmpbsa_std")),
        "trajectory_npz": _text(raw.get("trajectory_npz")),
        "backmapped_pdb": _text(raw.get("backmapped_pdb")),
        "score_json": _text(raw.get("score_json")),
        "protein_structure_source_path": _text(raw.get("protein_structure_source_path")),
        "protein_structure_source_kind": _text(raw.get("protein_structure_source_kind")),
        "backmapped_contains_protein": _text(raw.get("backmapped_contains_protein")),
        "backmapped_protein_atoms": _safe_int(raw.get("backmapped_protein_atoms")),
        "backmapped_ligand_atoms": _safe_int(raw.get("backmapped_ligand_atoms")),
        "translation_energy_pass": True,
        "translation_distance_pass": distance_pass,
        "translation_stability_pass": stability_pass,
        "translation_core_pass": distance_pass and stability_pass,
        "distance_gap_A": max(0.0, (distance or 999.0) - TRANSLATION_DISTANCE_THRESHOLD_A),
        "stability_gap": max(0.0, TRANSLATION_STABILITY_THRESHOLD - (stability or 0.0)),
    }


def _priority_tuple(row: dict[str, Any]) -> tuple[float, float, int, float, str]:
    export_rank = (
        0
        if _text(row.get("backmapped_pdb")) and _text(row.get("score_json"))
        else 1
        if _text(row.get("trajectory_npz"))
        else 2
    )
    distance_gap = _safe_float(row.get("distance_gap_A"), 999.0) or 999.0
    stability_gap = _safe_float(row.get("stability_gap"), 999.0) or 999.0
    energy = _safe_float(row.get("binding_energy_proxy"), 999.0) or 999.0
    source_rank = _safe_int(row.get("source_rank"), 9)
    return (export_rank, energy, source_rank, distance_gap + stability_gap, _text(row.get("ligand_id")))


def _best_unique_energy_hits(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_ligand: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = _energy_hit_row(raw)
        if row is None:
            continue
        ligand_id = row["ligand_id"]
        previous = best_by_ligand.get(ligand_id)
        if previous is None or _priority_tuple(row) < _priority_tuple(previous):
            best_by_ligand[ligand_id] = row
    return sorted(best_by_ligand.values(), key=_priority_tuple)


def _closure_lane(row: dict[str, Any]) -> str:
    if _text(row.get("backmapped_pdb")) and _text(row.get("score_json")):
        return "measure_pose_backmapping_and_local_min_survival"
    if _text(row.get("trajectory_npz")):
        return "rebuild_backmapped_pose_then_measure_pose_backmapping"
    return "rerun_short_replicate_with_backmapping_exports"


def build_payload(
    *,
    root: Path = Path("."),
    translation_evidence_payload: dict[str, Any] | None = None,
    metric_scale_payload: dict[str, Any] | None = None,
    source_translation_evidence_json: str = DEFAULT_TRANSLATION_EVIDENCE_JSON,
    source_metric_scale_json: str = DEFAULT_METRIC_SCALE_JSON,
    max_rows: int = 8,
) -> dict[str, Any]:
    all_rows: list[dict[str, Any]] = []
    source_file_count = 0
    for source_pool_class, pattern in SOURCE_SPECS:
        paths = _paths_for_glob(root, pattern)
        source_file_count += len(paths)
        for path in paths:
            all_rows.extend(_read_score_rows(path, source_pool_class))

    unique_energy_hits = _best_unique_energy_hits(all_rows)
    selected_rows = unique_energy_hits[: max(1, max_rows)]
    queue_rows: list[dict[str, Any]] = []
    for rank, row in enumerate(selected_rows, start=1):
        closure_lane = _closure_lane(row)
        row.update(
            {
                "row_kind": "tcruzi_pde_pose_backmapping_closure_queue_row",
                "priority_rank": rank,
                "target_id": TARGET_ID,
                "closure_lane": closure_lane,
                "required_pose_preservation_rmsd_A_max": 2.50,
                "required_backmapping_consistency_score_min": 0.60,
                "required_local_minimization_survival_fraction_min": 0.60,
                "required_replicate_pass_fraction_min": 0.60,
                "required_measurements": (
                    "pose_preservation_rmsd_A;"
                    "backmapping_consistency_score;"
                    "local_minimization_survival_fraction;"
                    "replicate_pass_fraction"
                ),
                "claim_promotion_allowed": False,
                "threshold_policy": "do_not_relax_energy_distance_or_stability_thresholds",
                "next_action": (
                    "Run a short pose-preserving all-atom-style backmapping/local-minimization check for this energy-hit seed, "
                    "then rerun translation evidence and quality packets."
                ),
            }
        )
        queue_rows.append(row)

    evidence_summary = dict((translation_evidence_payload or {}).get("summary", {}) or {})
    metric_summary = dict((metric_scale_payload or {}).get("summary", {}) or {})
    status = "pose_backmapping_closure_queue_ready" if queue_rows else "blocked_no_energy_hit_seed_rows"
    return {
        "summary": {
            "status": status,
            "target_id": TARGET_ID,
            "source_translation_evidence_json": source_translation_evidence_json if evidence_summary else "",
            "source_metric_scale_json": source_metric_scale_json if metric_summary else "",
            "source_file_count": source_file_count,
            "raw_score_row_count": len(all_rows),
            "energy_hit_unique_ligand_count": len(unique_energy_hits),
            "queue_row_count": len(queue_rows),
            "top_queue_ligand_id": _text(queue_rows[0].get("ligand_id")) if queue_rows else "",
            "top_queue_binding_energy_proxy": queue_rows[0].get("binding_energy_proxy") if queue_rows else None,
            "top_queue_source_pool_class": _text(queue_rows[0].get("source_pool_class")) if queue_rows else "",
            "translation_score_candidate_row_count": evidence_summary.get("translation_score_candidate_row_count"),
            "translation_energy_pass_count": evidence_summary.get("translation_energy_pass_count"),
            "translation_core_pass_count": evidence_summary.get("translation_core_pass_count"),
            "metric_scale_gap_detected": bool(metric_summary.get("metric_scale_gap_detected", False)),
            "claim_promotion_allowed": False,
            "next_required_step": (
                "Execute the queued pose-preservation/backmapping/local-minimization measurements on unique energy-hit PDE seeds, then rerun the translation evidence probe."
                if queue_rows
                else "Source or generate energy-hit PDE seeds before pose/backmapping closure."
            ),
        },
        "rows": queue_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the T. cruzi PDE pose/backmapping closure queue.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--translation-evidence-json", default=DEFAULT_TRANSLATION_EVIDENCE_JSON)
    parser.add_argument("--metric-scale-json", default=DEFAULT_METRIC_SCALE_JSON)
    parser.add_argument("--max-rows", type=int, default=8)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(
        root=args.root,
        translation_evidence_payload=maybe_load_json(args.translation_evidence_json),
        metric_scale_payload=maybe_load_json(args.metric_scale_json),
        source_translation_evidence_json=args.translation_evidence_json,
        source_metric_scale_json=args.metric_scale_json,
        max_rows=args.max_rows,
    )
    write_artifact(args.out_md, "Wetlab T. cruzi PDE Pose/Backmapping Closure Queue", payload)
    print(args.out_md)


if __name__ == "__main__":
    main()
