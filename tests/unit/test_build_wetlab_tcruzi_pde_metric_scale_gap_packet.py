from __future__ import annotations

import csv
from pathlib import Path

from tools.build_wetlab_tcruzi_pde_metric_scale_gap_packet import build_payload


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_metric_scale_gap_packet_detects_energy_geometry_split(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "runs" / "wetlab_tcruzi_pde_external_pdeb1_seed_screen" / "stage3_scores.csv",
        [
            {
                "ligand_id": "external_energy_hit",
                "binding_energy_proxy": "-0.72",
                "mean_min_distance_A": "4.2",
                "stability_score": "0.001",
                "contact_fraction": "0.01",
            }
        ],
    )
    _write_csv(
        tmp_path / "runs" / "wetlab_tcruzi_pde_bindingdb_similarity_seed_screen" / "stage9_stage3_scores.csv",
        [
            {
                "ligand_id": "bindingdb_energy_hit",
                "binding_energy_proxy": "-0.60",
                "mean_min_distance_A": "4.35",
                "stability_score": "0.001",
                "contact_fraction": "0.01",
            }
        ],
    )
    _write_csv(
        tmp_path / "runs" / "wetlab_tcruzi_pde_bindingdb_similarity_seed_screen" / "stage_stage3_scores.csv",
        [
            {
                "ligand_id": "single_seed_pilot_not_main_screen",
                "binding_energy_proxy": "-0.10",
                "mean_min_distance_A": "4.80",
                "stability_score": "0.001",
                "contact_fraction": "0.01",
            }
        ],
    )
    review_payload = {
        "rows": [
            {
                "ligand_id": "review_geometry_hit_1",
                "binding_energy_proxy": "-0.19",
                "mean_min_distance_A": "2.8",
                "stability_score": "0.39",
                "contact_fraction": "0.63",
            },
            {
                "ligand_id": "review_geometry_hit_2",
                "binding_energy_proxy": "-0.18",
                "mean_min_distance_A": "3.0",
                "stability_score": "0.37",
                "contact_fraction": "0.61",
            },
        ]
    }

    payload = build_payload(
        review_payload,
        root=tmp_path,
        translation_evidence_payload={
            "summary": {
                "translation_score_candidate_row_count": 4,
                "translation_energy_pass_count": 2,
                "translation_core_pass_count": 0,
            }
        },
        quality_payload={"summary": {"next_required_step": "blocked"}},
    )

    summary = payload["summary"]
    assert summary["metric_scale_gap_detected"] is True
    assert summary["commercial_gap_status"] == "blocked_metric_scale_split"
    assert summary["claim_promotion_allowed"] is False
    assert summary["selected_allatom_geometry_stability_pass_count"] == 2
    assert summary["selected_allatom_energy_pass_count"] == 0
    assert summary["external_energy_pass_count"] == 2
    assert summary["external_core_pass_count"] == 0
    assert summary["next_required_step"].startswith("Normalize the metric scale")

    rows_by_cohort = {row["cohort_id"]: row for row in payload["rows"]}
    assert (
        rows_by_cohort["selected_allatom_review_top4"]["metric_tradeoff_class"]
        == "geometry_stability_preserved_energy_weak"
    )
    assert rows_by_cohort["external_homolog_pdeb1_seed"]["metric_tradeoff_class"] == (
        "energy_strong_geometry_stability_collapsed"
    )
    assert rows_by_cohort["external_bindingdb_similarity_seed"]["row_count"] == 1
    assert rows_by_cohort["external_bindingdb_similarity_seed"]["energy_pass_count"] == 1
