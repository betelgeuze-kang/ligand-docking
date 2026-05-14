#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path
from typing import Any

from tools.probe_wetlab_tcruzi_pde_translation_evidence import (
    TRANSLATION_DISTANCE_THRESHOLD_A,
    TRANSLATION_ENERGY_THRESHOLD,
    TRANSLATION_STABILITY_THRESHOLD,
)
from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

TARGET_ID = "T. cruzi PDE"
DEFAULT_REVIEW_JSON = "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json"
DEFAULT_TRANSLATION_EVIDENCE_JSON = "runs/wetlab_tcruzi_pde_translation_evidence_probe_current.json"
DEFAULT_QUALITY_JSON = "runs/wetlab_tcruzi_pde_translation_quality_packet_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_metric_scale_gap_packet_current.md"

COHORT_SPECS = [
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


def _safe_float(value: Any) -> float | None:
    try:
        if value in {"", None}:
            return None
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _min_or_none(values: list[float]) -> float | None:
    return min(values) if values else None


def _max_or_none(values: list[float]) -> float | None:
    return max(values) if values else None


def _metric_rows_from_dicts(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in source_rows:
        energy = _safe_float(raw.get("binding_energy_proxy"))
        distance = _safe_float(raw.get("mean_min_distance_A"))
        stability = _safe_float(raw.get("stability_score"))
        contact = _safe_float(raw.get("contact_fraction"))
        if energy is None and distance is None and stability is None and contact is None:
            continue
        rows.append(
            {
                "ligand_id": str(raw.get("ligand_id", "")).strip(),
                "binding_energy_proxy": energy,
                "mean_min_distance_A": distance,
                "stability_score": stability,
                "contact_fraction": contact,
                "energy_pass": energy is not None and energy <= TRANSLATION_ENERGY_THRESHOLD,
                "distance_pass": distance is not None and distance <= TRANSLATION_DISTANCE_THRESHOLD_A,
                "stability_pass": stability is not None and stability >= TRANSLATION_STABILITY_THRESHOLD,
            }
        )
    for row in rows:
        row["core_pass"] = row["energy_pass"] and row["distance_pass"] and row["stability_pass"]
        row["geometry_stability_pass"] = row["distance_pass"] and row["stability_pass"]
    return rows


def _read_csv_metric_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows.extend(dict(row) for row in reader)
    return _metric_rows_from_dicts(rows)


def _summarize_cohort(
    *,
    cohort_id: str,
    source_kind: str,
    source_paths: list[Path],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    energies = [value for row in rows if (value := row.get("binding_energy_proxy")) is not None]
    distances = [value for row in rows if (value := row.get("mean_min_distance_A")) is not None]
    stabilities = [value for row in rows if (value := row.get("stability_score")) is not None]
    contacts = [value for row in rows if (value := row.get("contact_fraction")) is not None]
    energy_pass_count = sum(1 for row in rows if row.get("energy_pass"))
    geometry_stability_pass_count = sum(1 for row in rows if row.get("geometry_stability_pass"))
    core_pass_count = sum(1 for row in rows if row.get("core_pass"))
    best_energy_row = min(
        (row for row in rows if row.get("binding_energy_proxy") is not None),
        key=lambda row: row["binding_energy_proxy"],
        default={},
    )
    best_geometry_row = min(
        (row for row in rows if row.get("geometry_stability_pass") and row.get("binding_energy_proxy") is not None),
        key=lambda row: row["binding_energy_proxy"],
        default={},
    )
    if core_pass_count:
        tradeoff_class = "core_gate_closed"
    elif energy_pass_count and not geometry_stability_pass_count:
        tradeoff_class = "energy_strong_geometry_stability_collapsed"
    elif geometry_stability_pass_count and not energy_pass_count:
        tradeoff_class = "geometry_stability_preserved_energy_weak"
    elif energy_pass_count:
        tradeoff_class = "partial_energy_hit_without_core"
    else:
        tradeoff_class = "no_translation_gate_progress"
    return {
        "row_kind": "tcruzi_pde_metric_scale_gap_cohort",
        "cohort_id": cohort_id,
        "source_kind": source_kind,
        "source_file_count": len(source_paths),
        "source_paths": ";".join(path.as_posix() for path in source_paths),
        "row_count": len(rows),
        "unique_ligand_count": len({row["ligand_id"] for row in rows if row.get("ligand_id")}),
        "energy_pass_count": energy_pass_count,
        "distance_pass_count": sum(1 for row in rows if row.get("distance_pass")),
        "stability_pass_count": sum(1 for row in rows if row.get("stability_pass")),
        "geometry_stability_pass_count": geometry_stability_pass_count,
        "core_pass_count": core_pass_count,
        "best_binding_energy_proxy": _min_or_none(energies),
        "median_binding_energy_proxy": _median(energies),
        "best_mean_min_distance_A": _min_or_none(distances),
        "median_mean_min_distance_A": _median(distances),
        "best_stability_score": _max_or_none(stabilities),
        "median_stability_score": _median(stabilities),
        "best_contact_fraction": _max_or_none(contacts),
        "median_contact_fraction": _median(contacts),
        "best_energy_ligand_id": best_energy_row.get("ligand_id", ""),
        "best_energy_row_mean_min_distance_A": best_energy_row.get("mean_min_distance_A"),
        "best_energy_row_stability_score": best_energy_row.get("stability_score"),
        "best_geometry_ligand_id": best_geometry_row.get("ligand_id", ""),
        "best_geometry_row_binding_energy_proxy": best_geometry_row.get("binding_energy_proxy"),
        "metric_tradeoff_class": tradeoff_class,
        "claim_policy": "do_not_promote_until_core_pass_and_pose_backmapping_axes_close",
    }


def _paths_for_glob(root: Path, pattern: str) -> list[Path]:
    paths = sorted(path for path in root.glob(pattern) if path.is_file())
    return [
        path
        for path in paths
        if path.name != "stage_stage3_scores.csv"
    ]


def build_payload(
    review_payload: dict[str, Any],
    *,
    translation_evidence_payload: dict[str, Any] | None = None,
    quality_payload: dict[str, Any] | None = None,
    root: Path = Path("."),
    source_review_json: str = DEFAULT_REVIEW_JSON,
    source_translation_evidence_json: str = DEFAULT_TRANSLATION_EVIDENCE_JSON,
    source_quality_json: str = DEFAULT_QUALITY_JSON,
) -> dict[str, Any]:
    review_rows = _metric_rows_from_dicts([dict(row or {}) for row in (review_payload.get("rows", []) or [])])
    rows: list[dict[str, Any]] = [
        _summarize_cohort(
            cohort_id="selected_allatom_review_top4",
            source_kind="pseudo_allatom_review",
            source_paths=[Path(source_review_json)],
            rows=review_rows,
        )
    ]
    for cohort_id, pattern in COHORT_SPECS:
        source_paths = _paths_for_glob(root, pattern)
        rows.append(
            _summarize_cohort(
                cohort_id=cohort_id,
                source_kind="external_candidate_pool_expansion",
                source_paths=source_paths,
                rows=_read_csv_metric_rows(source_paths),
            )
        )

    selected = rows[0]
    external_rows = rows[1:]
    external_energy_pass_count = sum(_safe_int(row.get("energy_pass_count")) for row in external_rows)
    external_core_pass_count = sum(_safe_int(row.get("core_pass_count")) for row in external_rows)
    external_geometry_stability_pass_count = sum(
        _safe_int(row.get("geometry_stability_pass_count")) for row in external_rows
    )
    selected_geometry_stability_pass_count = _safe_int(selected.get("geometry_stability_pass_count"))
    selected_energy_pass_count = _safe_int(selected.get("energy_pass_count"))
    metric_scale_gap_detected = (
        selected_geometry_stability_pass_count > 0
        and selected_energy_pass_count == 0
        and external_energy_pass_count > 0
        and external_core_pass_count == 0
    )
    translation_summary = dict((translation_evidence_payload or {}).get("summary", {}) or {})
    quality_summary = dict((quality_payload or {}).get("summary", {}) or {})
    next_required_step = (
        "Normalize the metric scale with all-atom-style pose preservation/backmapping and local-minimization survival on energy-hit PDE seeds before any further claim review."
        if metric_scale_gap_detected
        else "Continue translation-quality closure until energy, geometry, stability, pose preservation, backmapping, local minimization, and replicate axes close together."
    )
    return {
        "summary": {
            "status": "wetlab_tcruzi_pde_metric_scale_gap_packet_ready",
            "target_id": TARGET_ID,
            "source_review_json": source_review_json,
            "source_translation_evidence_json": source_translation_evidence_json if translation_summary else "",
            "source_quality_json": source_quality_json if quality_summary else "",
            "cohort_count": len(rows),
            "metric_scale_gap_detected": metric_scale_gap_detected,
            "commercial_gap_status": "blocked_metric_scale_split" if metric_scale_gap_detected else "review_required",
            "claim_promotion_allowed": False,
            "selected_allatom_review_row_count": _safe_int(selected.get("row_count")),
            "selected_allatom_energy_pass_count": selected_energy_pass_count,
            "selected_allatom_geometry_stability_pass_count": selected_geometry_stability_pass_count,
            "external_energy_pass_count": external_energy_pass_count,
            "external_geometry_stability_pass_count": external_geometry_stability_pass_count,
            "external_core_pass_count": external_core_pass_count,
            "translation_score_candidate_row_count": translation_summary.get("translation_score_candidate_row_count"),
            "translation_energy_pass_count": translation_summary.get("translation_energy_pass_count"),
            "translation_core_pass_count": translation_summary.get("translation_core_pass_count"),
            "quality_next_required_step": quality_summary.get("next_required_step", ""),
            "next_required_step": next_required_step,
        },
        "structured": {
            "hard_thresholds": {
                "binding_energy_proxy_max": TRANSLATION_ENERGY_THRESHOLD,
                "mean_min_distance_A_max": TRANSLATION_DISTANCE_THRESHOLD_A,
                "stability_score_min": TRANSLATION_STABILITY_THRESHOLD,
            },
            "interpretation": (
                "Selected review rows preserve geometry/stability but are energy-weak, while external homolog/similarity rows add energy hits without geometry/stability. Treat this as a metric-scale/pose-preservation gap, not as a wetlab-ready hit signal."
                if metric_scale_gap_detected
                else "No decisive metric-scale split detected from the currently materialized cohorts."
            ),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--review-json", default=DEFAULT_REVIEW_JSON)
    parser.add_argument("--translation-evidence-json", default=DEFAULT_TRANSLATION_EVIDENCE_JSON)
    parser.add_argument("--quality-json", default=DEFAULT_QUALITY_JSON)
    parser.add_argument("--out", default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    payload = build_payload(
        load_json(args.review_json),
        translation_evidence_payload=maybe_load_json(args.translation_evidence_json),
        quality_payload=maybe_load_json(args.quality_json),
        root=args.root,
        source_review_json=args.review_json,
        source_translation_evidence_json=args.translation_evidence_json,
        source_quality_json=args.quality_json,
    )
    write_artifact(args.out, "Wetlab T. cruzi PDE Metric Scale Gap Packet", payload)
    print(args.out)


if __name__ == "__main__":
    main()
