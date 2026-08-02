"""Contract tests for the retired proxy-energy field names (P0-5)."""

from __future__ import annotations

import numpy as np

from betelgeuze_engine.physics.mm_gbsa import (
    GB_SA_PROXY_ENERGY_FIELD,
    gb_sa_proxy_energy,
    mm_gbsa_binding_energy,
)
from betelgeuze_product.proxy_energy_schema import (
    CANDIDATE_REFINE_PROXY_SCORE_FIELD,
    INTERNAL_REFINE_PROXY_SCORE_FIELD,
    REFINE_PROXY_SCORE_FIELD,
    RETIRED_PROXY_ENERGY_FIELDS,
    field_with_aliases,
    read_proxy_energy,
    rename_retired_fields,
)

RETIRED_ENGINE_FIELDS = ("deltaG_mm_gbsa_kcal_mol", "deltaG_mmpbsa_proxy_kcal_mol")


def _protein() -> np.ndarray:
    return np.asarray(
        [[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0]],
        dtype=np.float32,
    )


def _ligand() -> np.ndarray:
    return np.asarray([[1.0, 1.0, 1.0], [1.5, 1.0, 1.0]], dtype=np.float32)


def test_mm_gbsa_result_uses_active_proxy_field_only() -> None:
    out = mm_gbsa_binding_energy(_protein(), _ligand())

    assert GB_SA_PROXY_ENERGY_FIELD in out
    for retired in RETIRED_ENGINE_FIELDS:
        assert retired not in out


def test_mm_gbsa_empty_input_result_uses_active_proxy_field_only() -> None:
    out = mm_gbsa_binding_energy(
        np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.float32)
    )

    assert GB_SA_PROXY_ENERGY_FIELD in out
    for retired in RETIRED_ENGINE_FIELDS:
        assert retired not in out


def test_gb_sa_proxy_energy_reads_retired_names_for_historical_artifacts() -> None:
    assert gb_sa_proxy_energy({GB_SA_PROXY_ENERGY_FIELD: -2.0}) == -2.0
    assert gb_sa_proxy_energy({"deltaG_mm_gbsa_kcal_mol": -3.0}) == -3.0
    assert gb_sa_proxy_energy({"deltaG_mmpbsa_proxy_kcal_mol": -4.0}) == -4.0
    assert gb_sa_proxy_energy({}, 1.5) == 1.5
    assert gb_sa_proxy_energy(None, 1.5) == 1.5


def test_gb_sa_proxy_energy_prefers_active_field_over_retired() -> None:
    row = {GB_SA_PROXY_ENERGY_FIELD: -1.0, "deltaG_mm_gbsa_kcal_mol": -9.0}

    assert gb_sa_proxy_energy(row) == -1.0


def test_retired_benchmark_field_names_are_declared() -> None:
    assert RETIRED_PROXY_ENERGY_FIELDS == (
        "deltaG_mm_gbsa_kcal_mol",
        "deltaG_candidate_kcal_mol",
        "deltaG_proxy_kcal_mol",
    )


def test_active_benchmark_field_names_do_not_claim_kcal_mol() -> None:
    for field in (
        INTERNAL_REFINE_PROXY_SCORE_FIELD,
        CANDIDATE_REFINE_PROXY_SCORE_FIELD,
        REFINE_PROXY_SCORE_FIELD,
    ):
        assert "deltaG" not in field
        assert "kcal_mol" not in field


def test_field_with_aliases_orders_active_first() -> None:
    assert field_with_aliases(INTERNAL_REFINE_PROXY_SCORE_FIELD) == (
        "internal_refine_proxy_score",
        "deltaG_mm_gbsa_kcal_mol",
    )
    assert field_with_aliases("pose_rmsd_A") == ("pose_rmsd_A",)


def test_read_proxy_energy_falls_back_to_retired_column() -> None:
    assert (
        read_proxy_energy(
            {"deltaG_candidate_kcal_mol": "-5.5"}, CANDIDATE_REFINE_PROXY_SCORE_FIELD
        )
        == "-5.5"
    )
    assert (
        read_proxy_energy(
            {CANDIDATE_REFINE_PROXY_SCORE_FIELD: ""},
            CANDIDATE_REFINE_PROXY_SCORE_FIELD,
            "fallback",
        )
        == "fallback"
    )


def test_rename_retired_fields_upgrades_historical_rows() -> None:
    upgraded = rename_retired_fields(
        {
            "deltaG_mm_gbsa_kcal_mol": "-3.0",
            "deltaG_proxy_kcal_mol": "-2.0",
            "deltaG_experimental_kcal_mol": "-7.0",
            "pose_rmsd_A": "1.2",
        }
    )

    assert upgraded[INTERNAL_REFINE_PROXY_SCORE_FIELD] == "-3.0"
    assert upgraded[REFINE_PROXY_SCORE_FIELD] == "-2.0"
    assert upgraded["deltaG_experimental_kcal_mol"] == "-7.0"
    assert upgraded["pose_rmsd_A"] == "1.2"


def test_active_benchmark_work_order_columns_have_no_retired_names() -> None:
    from tools.product.build_refine_tier_public_benchmark_readiness import (
        WORK_ORDER_COLUMNS,
        WORK_ORDER_OPERATOR_FIELDS,
    )

    for columns in (WORK_ORDER_COLUMNS, WORK_ORDER_OPERATOR_FIELDS):
        for retired in RETIRED_PROXY_ENERGY_FIELDS:
            assert retired not in columns
        assert INTERNAL_REFINE_PROXY_SCORE_FIELD in columns
