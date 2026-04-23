from __future__ import annotations

import pandas as pd

from tools import build_trpv1_matched_negative_panel as mod


def test_build_trpv1_matched_negative_panel_selects_three_diverse_rows() -> None:
    ranking = pd.DataFrame(
        [
            {"target": "TRPV1_ION_CHANNEL_BLIND", "ligand_id": "POS1", "is_binder": 1, "reference_binding_kcal_mol": -10.0, "binding_score_composite_v5": -9.0, "mean_min_distance_A": 3.0, "role": "far_ood_eval"},
            {"target": "TRPV1_ION_CHANNEL_BLIND", "ligand_id": "POS2", "is_binder": 1, "reference_binding_kcal_mol": -10.0, "binding_score_composite_v5": -8.0, "mean_min_distance_A": 3.2, "role": "far_ood_eval"},
            {"target": "TRPV1_ION_CHANNEL_BLIND", "ligand_id": "POS3", "is_binder": 1, "reference_binding_kcal_mol": -10.0, "binding_score_composite_v5": -7.0, "mean_min_distance_A": 3.4, "role": "far_ood_eval"},
            {"target": "TRPV1_ION_CHANNEL_BLIND", "ligand_id": "NEG_A", "is_binder": 0, "reference_binding_kcal_mol": -2.95, "binding_score_composite_v5": -0.2, "mean_min_distance_A": 3.21, "role": "far_ood_eval"},
            {"target": "TRPV1_ION_CHANNEL_BLIND", "ligand_id": "NEG_B", "is_binder": 0, "reference_binding_kcal_mol": -2.95, "binding_score_composite_v5": -0.3, "mean_min_distance_A": 3.22, "role": "far_ood_eval"},
            {"target": "TRPV1_ION_CHANNEL_BLIND", "ligand_id": "NEG_C", "is_binder": 0, "reference_binding_kcal_mol": -2.95, "binding_score_composite_v5": -0.4, "mean_min_distance_A": 3.23, "role": "far_ood_eval"},
        ]
    )
    labels = pd.DataFrame(
        [
            {"ligand_id": "NEG_A", "smiles": "CC", "scaffold": "aryl", "molecular_weight": 100.0, "logp": 1.0, "h_donors": 0, "h_acceptors": 0, "rot_bonds": 1, "decoy_match_distance": 1.0, "decoy_hardness_score": -1.0},
            {"ligand_id": "NEG_B", "smiles": "CCC", "scaffold": "heteroaryl", "molecular_weight": 110.0, "logp": 1.1, "h_donors": 0, "h_acceptors": 1, "rot_bonds": 1, "decoy_match_distance": 1.1, "decoy_hardness_score": -1.1},
            {"ligand_id": "NEG_C", "smiles": "CCCC", "scaffold": "cyclohexyl", "molecular_weight": 120.0, "logp": 1.2, "h_donors": 0, "h_acceptors": 1, "rot_bonds": 1, "decoy_match_distance": 1.2, "decoy_hardness_score": -1.2},
        ]
    )

    payload = mod.build_payload(ranking, labels)

    assert payload["summary"]["matched_negative_panel_locked"] is True
    assert payload["summary"]["matched_negative_slot_count_locked"] == 3
    assert payload["rows"][0]["negative_control_locked"] is True
    assert payload["rows"][0]["external_send_ready"] is False
    assert {row["compound_id"] for row in payload["rows"]} == {"NEG_A", "NEG_B", "NEG_C"}
