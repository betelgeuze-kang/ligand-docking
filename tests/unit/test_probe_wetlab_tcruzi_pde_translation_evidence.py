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
