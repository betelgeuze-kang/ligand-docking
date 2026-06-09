from __future__ import annotations

from betelgeuze_product.residual_mode_policy import customer_ligand_ranking_snapshot
from tools.product.build_docking_ranking_mutation_e2e_smoke import run_smoke


def test_customer_ligand_ranking_snapshot_mutates_only_when_guard_unlocked() -> None:
    rows = [
        {"ligand_id": "lig_a", "binding_score_composite_v7": 1.0, "binding_score_composite_v7_residual_active": -5.0},
        {"ligand_id": "lig_b", "binding_score_composite_v7": -5.0, "binding_score_composite_v7_residual_active": 1.0},
    ]
    locked = customer_ligand_ranking_snapshot(rows, ranking_mutation_allowed=False)
    unlocked = customer_ligand_ranking_snapshot(rows, ranking_mutation_allowed=True)

    assert locked["customer_score_column"] == "binding_score_composite_v7"
    assert locked["ranking_mutated"] is False
    assert locked["base_ranking_ligand_ids"] == locked["customer_ranking_ligand_ids"]
    assert unlocked["customer_score_column"] == "binding_score_composite_v7_residual_active"
    assert unlocked["ranking_mutated"] is True
    assert unlocked["base_ranking_ligand_ids"] == ["lig_b", "lig_a"]
    assert unlocked["customer_ranking_ligand_ids"] == ["lig_a", "lig_b"]


def test_docking_ranking_mutation_e2e_smoke_passes_locked_and_unlocked_scenarios() -> None:
    payload = run_smoke()
    summary = payload["summary"]
    assert summary["status"] == "docking_ranking_mutation_e2e_smoke_ready"
    assert summary["pass_scenario_count"] == 2
    by_scenario = {row["scenario"]: row for row in payload["rows"]}
    assert by_scenario["shadow_locked"]["ranking_mutated"] is False
    assert by_scenario["shadow_unlocked"]["ranking_mutated"] is True
    assert by_scenario["shadow_unlocked"]["customer_ranking_ligand_ids"] == ["lig_a", "lig_b"]
