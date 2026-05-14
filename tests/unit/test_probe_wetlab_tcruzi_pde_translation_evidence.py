from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.probe_wetlab_tcruzi_pde_translation_evidence import build_probe, discover_candidate_files


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_probe_discovers_rescue_tree_and_related_current_artifacts(tmp_path: Path) -> None:
    rescue_state = (
        tmp_path
        / "runs"
        / "wetlab_tcruzi_pde_allatom_rescue"
        / "t_cruzi_pde"
        / "20_of_20"
        / "top_1"
        / "attempts"
        / "attempt_1"
        / "allatom_rescue_state.json"
    )
    current_review = tmp_path / "runs" / "wetlab_tcruzi_pde_allatom_review_packet_current.csv"
    unrelated = tmp_path / "runs" / "wetlab_cathepsin_k_allatom_review_packet_current.csv"

    _write_json(rescue_state, {"summary": {"pose_preservation_rmsd_A": 1.7}})
    _write_csv(current_review, [{"ligand_id": "lig_a", "binding_energy_proxy": -0.4}])
    _write_csv(unrelated, [{"ligand_id": "lig_b", "binding_energy_proxy": -0.1}])

    discovered = [path.relative_to(tmp_path).as_posix() for path in discover_candidate_files(tmp_path)]

    assert rescue_state.relative_to(tmp_path).as_posix() in discovered
    assert current_review.relative_to(tmp_path).as_posix() in discovered
    assert unrelated.relative_to(tmp_path).as_posix() not in discovered


def test_probe_reports_exact_and_alias_fields_with_non_null_counts(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "runs" / "wetlab_tcruzi_pde_allatom_rescue_current.json",
        {
            "summary": {
                "pose_preservation_rmsd_A": 1.2,
                "source_three_bead_backmapping_consistency_score": 0.82,
                "source_three_bead_local_minimization_survival_fraction": None,
                "source_three_bead_replicate_pass_fraction": 0.75,
            },
            "rows": [
                {
                    "ligand_id": "lig_a",
                    "binding_energy_proxy": -0.5,
                    "source_three_bead_binding_energy_proxy": -0.6,
                }
            ],
        },
    )
    _write_csv(
        tmp_path / "runs" / "wetlab_tcruzi_pde_allatom_rescue_lane_current.csv",
        [
            {
                "ligand_id": "lig_a",
                "pose_validation_pose_preservation_rmsd_A": 1.3,
                "source_three_bead_replicate_pass_fraction": "",
            }
        ],
    )

    payload = build_probe(tmp_path)
    metrics = payload["metrics"]

    assert metrics["pose_preservation_rmsd_A"]["exact_field_present"] is True
    assert metrics["pose_preservation_rmsd_A"]["exact_field_non_null_count"] == 1
    assert metrics["binding_energy_proxy"]["exact_field_present"] is True
    assert metrics["binding_energy_proxy"]["exact_field_non_null_count"] == 1
    assert metrics["backmapping_consistency_score"]["exact_field_present"] is False
    assert metrics["local_minimization_survival_fraction"]["exact_field_present"] is False

    pose_aliases = {
        item["field"]
        for item in metrics["pose_preservation_rmsd_A"]["observed_fields"]
        if not item["exact_requested_field"]
    }
    assert pose_aliases == {"pose_validation_pose_preservation_rmsd_A"}

    replicate_alias = next(
        item
        for item in metrics["replicate_pass_fraction"]["observed_fields"]
        if item["field"] == "source_three_bead_replicate_pass_fraction"
    )
    assert replicate_alias["occurrence_count"] == 2
    assert replicate_alias["non_null_count"] == 1


def test_probe_scores_tcruzi_pde_translation_candidate_pool(tmp_path: Path) -> None:
    _write_csv(
        tmp_path
        / "runs"
        / "archive"
        / "snapshot_current"
        / "wetlab_broad_screen_throughput"
        / "t_cruzi_pde"
        / "20_of_20"
        / "throughput_run_stage3_scores.csv",
        [
            {
                "ligand_id": "weak_core_like",
                "binding_energy_proxy": "-0.12",
                "mean_min_distance_A": "2.7",
                "stability_score": "0.5",
                "contact_fraction": "0.7",
                "trajectory_frames": "300",
            },
            {
                "ligand_id": "strong_core_pass",
                "binding_energy_proxy": "-0.65",
                "mean_min_distance_A": "2.8",
                "stability_score": "0.4",
                "contact_fraction": "0.8",
                "trajectory_frames": "220",
            },
        ],
    )

    payload = build_probe(tmp_path)
    summary = payload["summary"]

    assert summary["translation_score_candidate_file_count"] == 1
    assert summary["translation_score_candidate_row_count"] == 2
    assert summary["translation_energy_pass_count"] == 1
    assert summary["translation_energy_pass_unique_ligand_count"] == 1
    assert summary["translation_core_pass_count"] == 1
    assert summary["translation_core_pass_unique_ligand_count"] == 1
    assert summary["candidate_pool_supports_energy_closure"] is True
    assert summary["best_binding_energy_proxy"] == -0.65
    assert summary["best_binding_energy_proxy_row"]["ligand_id"] == "strong_core_pass"
    assert summary["candidate_pool_energy_gap_closed"] is True
    assert summary["candidate_pool_core_gate_closed"] is True


def test_probe_scores_external_homolog_seed_screen_without_promoting_claims(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "runs" / "wetlab_tcruzi_pde_external_pdeb1_seed_screen" / "stage3_scores.csv",
        [
            {
                "ligand_id": "external_energy_hit",
                "binding_energy_proxy": "-0.82",
                "mean_min_distance_A": "3.7",
                "stability_score": "0.001",
                "contact_fraction": "0.01",
                "trajectory_frames": "100",
            },
            {
                "ligand_id": "external_geometry_hit",
                "binding_energy_proxy": "-0.2",
                "mean_min_distance_A": "2.9",
                "stability_score": "0.5",
                "contact_fraction": "0.7",
                "trajectory_frames": "100",
            },
        ],
    )

    payload = build_probe(tmp_path)
    summary = payload["summary"]

    assert summary["translation_score_candidate_file_count"] == 1
    assert summary["external_homolog_seed_candidate_file_count"] == 1
    assert summary["external_homolog_seed_candidate_row_count"] == 2
    assert summary["translation_energy_pass_count"] == 1
    assert summary["translation_energy_pass_unique_ligand_count"] == 1
    assert summary["translation_core_pass_count"] == 0
    assert summary["translation_core_pass_unique_ligand_count"] == 0
    assert summary["external_homolog_seed_energy_pass_count"] == 1
    assert summary["external_homolog_seed_core_pass_count"] == 0
    assert summary["candidate_pool_energy_gap_closed"] is True
    assert summary["candidate_pool_core_gate_closed"] is False
    assert summary["candidate_pool_supports_energy_closure"] is False
    assert summary["external_homolog_seed_best_binding_energy_proxy"] == -0.82
    assert (
        summary["candidate_pool_claim_scope_note"]
        == "external_homolog_seed_rows_are_candidate_pool_expansion_only_not_direct_tcruzi_pde_claim"
    )
    assert summary["best_binding_energy_proxy_row"]["source_pool_class"] == "external_homolog_pdeb1_seed"


def test_probe_scores_external_geometry_stability_rescore_as_separate_evidence(tmp_path: Path) -> None:
    rows = [
        {
            "ligand_id": "same_energy_hit",
            "binding_energy_proxy": "-0.82",
            "mean_min_distance_A": "3.7",
            "stability_score": "0.001",
            "contact_fraction": "0.01",
            "trajectory_frames": "100",
        }
    ]
    _write_csv(
        tmp_path / "runs" / "wetlab_tcruzi_pde_external_pdeb1_seed_screen" / "stage3_scores.csv",
        rows,
    )
    _write_csv(
        tmp_path / "runs" / "wetlab_tcruzi_pde_external_geomstab_rescore_3bead_current" / "stage3_scores.csv",
        rows,
    )

    payload = build_probe(tmp_path)
    summary = payload["summary"]

    assert summary["translation_score_candidate_file_count"] == 2
    assert summary["translation_score_candidate_row_count"] == 2
    assert summary["translation_score_candidate_unique_ligand_count"] == 1
    assert summary["translation_energy_pass_count"] == 2
    assert summary["translation_energy_pass_unique_ligand_count"] == 1
    assert summary["translation_core_pass_count"] == 0
    assert summary["translation_core_pass_unique_ligand_count"] == 0
    assert summary["external_homolog_geomstab_rescore_candidate_file_count"] == 1
    assert summary["external_homolog_geomstab_rescore_candidate_row_count"] == 1
    assert summary["external_homolog_geomstab_rescore_energy_pass_count"] == 1
    assert summary["external_homolog_geomstab_rescore_core_pass_count"] == 0
    assert summary["external_homolog_geomstab_rescore_best_binding_energy_proxy"] == -0.82


def test_probe_scores_external_adress_rescue_as_failed_rescue_evidence(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "runs" / "wetlab_tcruzi_pde_external_geomstab_adress_rescue_scores_current" / "stage3_scores.csv",
        [
            {
                "ligand_id": "adress_energy_hit",
                "binding_energy_proxy": "-0.70",
                "mean_min_distance_A": "4.1",
                "stability_score": "0.001",
                "contact_fraction": "0.01",
                "trajectory_frames": "300",
            }
        ],
    )

    payload = build_probe(tmp_path)
    summary = payload["summary"]

    assert summary["translation_score_candidate_file_count"] == 1
    assert summary["translation_energy_pass_count"] == 1
    assert summary["translation_energy_pass_unique_ligand_count"] == 1
    assert summary["translation_core_pass_count"] == 0
    assert summary["external_homolog_adress_rescue_candidate_file_count"] == 1
    assert summary["external_homolog_adress_rescue_candidate_row_count"] == 1
    assert summary["external_homolog_adress_rescue_energy_pass_count"] == 1
    assert summary["external_homolog_adress_rescue_core_pass_count"] == 0
    assert summary["external_homolog_adress_rescue_best_binding_energy_proxy"] == -0.70
    assert summary["best_binding_energy_proxy_row"]["source_pool_class"] == "external_homolog_pdeb1_adress_rescue"


def test_probe_scores_external_contact_rescue_as_failed_rescue_evidence(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "runs" / "wetlab_tcruzi_pde_external_geomstab_contact_rescue_scores_current" / "stage3_scores.csv",
        [
            {
                "ligand_id": "contact_energy_hit",
                "binding_energy_proxy": "-0.64",
                "mean_min_distance_A": "4.3",
                "stability_score": "0.001",
                "contact_fraction": "0.01",
                "trajectory_frames": "300",
            }
        ],
    )

    payload = build_probe(tmp_path)
    summary = payload["summary"]

    assert summary["translation_score_candidate_file_count"] == 1
    assert summary["translation_energy_pass_count"] == 1
    assert summary["translation_energy_pass_unique_ligand_count"] == 1
    assert summary["translation_core_pass_count"] == 0
    assert summary["external_homolog_contact_rescue_candidate_file_count"] == 1
    assert summary["external_homolog_contact_rescue_candidate_row_count"] == 1
    assert summary["external_homolog_contact_rescue_energy_pass_count"] == 1
    assert summary["external_homolog_contact_rescue_core_pass_count"] == 0
    assert summary["external_homolog_contact_rescue_best_binding_energy_proxy"] == -0.64
    assert summary["best_binding_energy_proxy_row"]["source_pool_class"] == "external_homolog_pdeb1_contact_rescue"


def test_probe_scores_bindingdb_similarity_seed_screen_as_claim_safe_evidence(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "runs" / "wetlab_tcruzi_pde_bindingdb_similarity_seed_screen" / "stage9_stage3_scores.csv",
        [
            {
                "ligand_id": "bindingdb_energy_hit",
                "binding_energy_proxy": "-0.60",
                "mean_min_distance_A": "4.35",
                "stability_score": "0.001",
                "contact_fraction": "0.01",
                "trajectory_frames": "300",
            },
            {
                "ligand_id": "bindingdb_geometry_hit",
                "binding_energy_proxy": "-0.20",
                "mean_min_distance_A": "2.80",
                "stability_score": "0.40",
                "contact_fraction": "0.70",
                "trajectory_frames": "300",
            },
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
                "trajectory_frames": "300",
            }
        ],
    )

    payload = build_probe(tmp_path)
    summary = payload["summary"]

    assert summary["translation_score_candidate_file_count"] == 1
    assert summary["translation_score_candidate_row_count"] == 2
    assert summary["translation_energy_pass_count"] == 1
    assert summary["translation_core_pass_count"] == 0
    assert summary["external_bindingdb_similarity_candidate_file_count"] == 1
    assert summary["external_bindingdb_similarity_candidate_row_count"] == 2
    assert summary["external_bindingdb_similarity_energy_pass_count"] == 1
    assert summary["external_bindingdb_similarity_core_pass_count"] == 0
    assert summary["external_bindingdb_similarity_best_binding_energy_proxy"] == -0.60
    assert summary["best_binding_energy_proxy_row"]["source_pool_class"] == "external_bindingdb_similarity_seed"
    assert (
        summary["candidate_pool_claim_scope_note"]
        == "external_homolog_seed_rows_are_candidate_pool_expansion_only_not_direct_tcruzi_pde_claim"
    )
