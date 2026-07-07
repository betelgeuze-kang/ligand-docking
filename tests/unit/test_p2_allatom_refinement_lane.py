from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.product.build_allatom_refinement_lane import build_allatom_refinement_lane


def test_refinement_lane_builds_work_order(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    pd.DataFrame([
        {"target": "T1", "ligand_id": "L1", "binding_energy_proxy": -2.0},
        {"target": "T1", "ligand_id": "L2", "binding_energy_proxy": -1.0},
    ]).to_csv(scores_csv, index=False)
    payload = build_allatom_refinement_lane(str(scores_csv), out_json=str(tmp_path / "lane.json"), topk=1)
    assert payload["summary"]["status"] == "allatom_refinement_work_order_ready"
    assert payload["summary"]["row_count"] == 1
    assert payload["summary"]["score_col_used"] == "binding_energy_proxy"
    assert payload["evidence"]["complete"] is False
    assert payload["work_order_rows"][0]["row_id"] == "T1::L1"


def test_refinement_lane_accepts_complete_evidence(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    pd.DataFrame([
        {
            "target": "T1",
            "ligand_id": "L1",
            "binding_energy_proxy": -2.0,
            "allatom_backend": "openmm",
            "allatom_refined_energy_kcal_mol": -5.1,
            "allatom_minimized_rmsd_A": 1.2,
            "allatom_parameterization_status": "pass",
        }
    ]).to_csv(scores_csv, index=False)
    payload = build_allatom_refinement_lane(str(scores_csv), out_json=str(tmp_path / "lane.json"))
    assert payload["summary"]["status"] == "allatom_refinement_evidence_ready"
    assert payload["evidence"]["complete_rows"] == 1
