#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import write_artifact

DEFAULT_STAGE1_QUEUE_CSV = "runs/wetlab_tcruzi_pde_external_pdeb1_seed_screen/stage1_queue.csv"
DEFAULT_STAGE3_SCORES_CSV = "runs/wetlab_tcruzi_pde_external_pdeb1_seed_screen/stage3_scores.csv"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_external_geometry_stability_rescue_queue_current.md"

TRANSLATION_ENERGY_THRESHOLD = -0.55
TRANSLATION_DISTANCE_THRESHOLD_A = 3.10
TRANSLATION_STABILITY_THRESHOLD = 0.32


def _text(value: Any) -> str:
    return "" if value in {"", None} else str(value).strip()


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _read_csv(path_like: str) -> list[dict[str, Any]]:
    path = Path(path_like)
    if not path.exists() or path.is_dir():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _score_rows_by_ligand(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        ligand_id = _text(row.get("ligand_id"))
        if not ligand_id:
            continue
        energy = _safe_float(row.get("binding_energy_proxy"))
        distance = _safe_float(row.get("mean_min_distance_A"))
        stability = _safe_float(row.get("stability_score"))
        if energy is None or distance is None or stability is None:
            continue
        if energy > TRANSLATION_ENERGY_THRESHOLD:
            continue
        indexed[ligand_id] = dict(row)
    return indexed


def _blocker(distance: float, stability: float) -> str:
    distance_pass = distance <= TRANSLATION_DISTANCE_THRESHOLD_A
    stability_pass = stability >= TRANSLATION_STABILITY_THRESHOLD
    if distance_pass and not stability_pass:
        return "stability_only"
    if stability_pass and not distance_pass:
        return "distance_only"
    if distance_pass and stability_pass:
        return "core_gate_closed"
    return "distance_and_stability"


def _rescue_mode(blocker: str) -> str:
    if blocker == "stability_only":
        return "replicate_stability_rescue"
    if blocker == "distance_only":
        return "pocket_recenter_rescue"
    if blocker == "core_gate_closed":
        return "no_rescue_required"
    return "pocket_recenter_then_replicate_stability_rescue"


def _priority_tuple(row: dict[str, Any]) -> tuple[int, float, float, float, str]:
    blocker = _text(row.get("core_gate_blocker"))
    blocker_rank = {
        "stability_only": 0,
        "distance_only": 1,
        "distance_and_stability": 2,
        "core_gate_closed": 9,
    }.get(blocker, 8)
    distance_gap = _safe_float(row.get("distance_gap_A"), 999.0) or 999.0
    stability_gap = _safe_float(row.get("stability_gap"), 999.0) or 999.0
    energy = _safe_float(row.get("binding_energy_proxy"), 999.0) or 999.0
    return (blocker_rank, distance_gap, stability_gap, energy, _text(row.get("ligand_id")))


def build_payload(
    *,
    stage1_queue_csv: str = DEFAULT_STAGE1_QUEUE_CSV,
    stage3_scores_csv: str = DEFAULT_STAGE3_SCORES_CSV,
    max_rows: int = 6,
) -> dict[str, Any]:
    queue_rows = _read_csv(stage1_queue_csv)
    score_rows = _score_rows_by_ligand(_read_csv(stage3_scores_csv))
    rescue_rows: list[dict[str, Any]] = []
    original_queue_by_ligand = {_text(row.get("ligand_id")): dict(row) for row in queue_rows if _text(row.get("ligand_id"))}

    for ligand_id, score in score_rows.items():
        base = dict(original_queue_by_ligand.get(ligand_id, {}))
        if not base:
            continue
        energy = _safe_float(score.get("binding_energy_proxy"), 0.0) or 0.0
        distance = _safe_float(score.get("mean_min_distance_A"), 999.0) or 999.0
        stability = _safe_float(score.get("stability_score"), 0.0) or 0.0
        contact = _safe_float(score.get("contact_fraction"), 0.0) or 0.0
        blocker = _blocker(distance, stability)
        distance_gap = max(0.0, distance - TRANSLATION_DISTANCE_THRESHOLD_A)
        stability_gap = max(0.0, TRANSLATION_STABILITY_THRESHOLD - stability)
        row = {
            **base,
            "source_stage3_scores_csv": stage3_scores_csv,
            "source_stage1_queue_csv": stage1_queue_csv,
            "rescue_source_scope": "chembl_homolog_pdeb1_seed_candidate_pool_only",
            "direct_tcruzi_pde_claim_evidence": False,
            "claim_promotion_allowed": False,
            "binding_energy_proxy": energy,
            "mean_min_distance_A": distance,
            "stability_score": stability,
            "contact_fraction": contact,
            "translation_energy_threshold": TRANSLATION_ENERGY_THRESHOLD,
            "translation_distance_threshold_A": TRANSLATION_DISTANCE_THRESHOLD_A,
            "translation_stability_threshold": TRANSLATION_STABILITY_THRESHOLD,
            "translation_energy_pass": True,
            "translation_distance_pass": distance <= TRANSLATION_DISTANCE_THRESHOLD_A,
            "translation_stability_pass": stability >= TRANSLATION_STABILITY_THRESHOLD,
            "translation_core_pass": blocker == "core_gate_closed",
            "distance_gap_A": round(distance_gap, 6),
            "stability_gap": round(stability_gap, 6),
            "core_gate_blocker": blocker,
            "recommended_rescue_mode": _rescue_mode(blocker),
            "recommended_rescore_model": "3bead_implicit_hbond",
            "recommended_next_stage": "geometry_stability_rescore_then_translation_evidence_probe",
        }
        rescue_rows.append(row)

    rescue_rows = sorted(rescue_rows, key=_priority_tuple)[: max(1, int(max_rows))]
    for idx, row in enumerate(rescue_rows, start=1):
        row["priority_rank"] = idx
        row["rescue_queue_id"] = f"{_text(row.get('queue_id'))}__geomstab_rescue_r{idx:02d}"

    focus = rescue_rows[0] if rescue_rows else {}
    status = (
        "external_geometry_stability_rescue_queue_ready"
        if rescue_rows
        else "blocked_no_external_energy_pass_candidates"
    )
    return {
        "summary": {
            "status": status,
            "target_id": "T. cruzi PDE",
            "source_stage3_scores_csv": stage3_scores_csv,
            "source_stage1_queue_csv": stage1_queue_csv,
            "energy_pass_candidate_count": len(score_rows),
            "rescue_row_count": len(rescue_rows),
            "core_pass_count": sum(1 for row in rescue_rows if row.get("translation_core_pass") is True),
            "stability_only_count": sum(1 for row in rescue_rows if row.get("core_gate_blocker") == "stability_only"),
            "distance_and_stability_count": sum(
                1 for row in rescue_rows if row.get("core_gate_blocker") == "distance_and_stability"
            ),
            "top_rescue_ligand_id": _text(focus.get("ligand_id")),
            "top_rescue_binding_energy_proxy": focus.get("binding_energy_proxy"),
            "top_rescue_mean_min_distance_A": focus.get("mean_min_distance_A"),
            "top_rescue_stability_score": focus.get("stability_score"),
            "top_rescue_mode": _text(focus.get("recommended_rescue_mode")),
            "claim_promotion_allowed": False,
            "claim_policy": "homolog_seed_rescue_queue_only_not_direct_tcruzi_pde_claim",
            "next_required_step": (
                "Run the rescue queue with 3-bead implicit hbond scoring and rerun the translation evidence probe; do not relax energy, distance, or stability thresholds."
                if rescue_rows
                else "Generate or source additional PDEB1-like candidates before geometry/stability rescue."
            ),
        },
        "rows": rescue_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the T. cruzi PDE external PDEB1 geometry/stability rescue queue.")
    parser.add_argument("--stage1-queue-csv", default=DEFAULT_STAGE1_QUEUE_CSV)
    parser.add_argument("--stage3-scores-csv", default=DEFAULT_STAGE3_SCORES_CSV)
    parser.add_argument("--max-rows", type=int, default=6)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(
        stage1_queue_csv=args.stage1_queue_csv,
        stage3_scores_csv=args.stage3_scores_csv,
        max_rows=args.max_rows,
    )
    write_artifact(args.out_md, "Wet-Lab T. cruzi PDE External Geometry/Stability Rescue Queue", payload)
    print(args.out_md)


if __name__ == "__main__":
    main()
