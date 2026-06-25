from __future__ import annotations

import copy
from pathlib import Path

import pytest

from betelgeuze_product.capability_matrix import (
    BLOCKED_HIGH_RISK_CLAIM_IDS,
    build_product_capability_matrix_verification,
    load_product_capability_matrix,
)

ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "config/product_capability_matrix.yaml"


def test_product_capability_matrix_current_file_is_fail_closed() -> None:
    matrix = load_product_capability_matrix(MATRIX_PATH)

    payload = build_product_capability_matrix_verification(matrix)

    summary = payload["summary"]
    assert summary["status"] == "product_capability_matrix_verified"
    assert summary["capability_matrix_ready"] is True
    assert summary["blocker_count"] == 0
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False


@pytest.mark.parametrize("claim_id", sorted(BLOCKED_HIGH_RISK_CLAIM_IDS))
def test_product_capability_matrix_blocks_high_risk_overclaims(claim_id: str) -> None:
    matrix = load_product_capability_matrix(MATRIX_PATH)
    mutated = copy.deepcopy(matrix)
    for row in mutated["capabilities"]:
        if row["id"] == claim_id:
            row["claim_state"] = "allowed"
            row["scientific_validity_green"] = True
            row["row_level_evidence_count"] = 0

    payload = build_product_capability_matrix_verification(mutated)

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_capability_matrix"
    assert summary["capability_matrix_ready"] is False
    assert "high_risk_claims_blocked" in summary["blocked_checks"]
    assert "scientific_green_requires_row_evidence" in summary["blocked_checks"]


def test_product_capability_matrix_blocks_missing_backlog_metadata() -> None:
    matrix = load_product_capability_matrix(MATRIX_PATH)
    mutated = copy.deepcopy(matrix)
    mutated["capabilities"][0]["definition_of_done"] = []

    payload = build_product_capability_matrix_verification(mutated)

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_capability_matrix"
    assert "backlog_metadata_complete" in summary["blocked_checks"]


def test_product_capability_matrix_blocks_policy_header_drift() -> None:
    matrix = load_product_capability_matrix(MATRIX_PATH)
    mutated = copy.deepcopy(matrix)
    mutated["claim_policy"]["broad_platform_claim_allowed"] = True

    payload = build_product_capability_matrix_verification(mutated)

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_capability_matrix"
    assert "claim_policy_blocks_high_risk_claims" in summary["blocked_checks"]


def test_product_capability_matrix_blocks_execution_or_external_mutation_flags() -> None:
    matrix = load_product_capability_matrix(MATRIX_PATH)
    mutated = copy.deepcopy(matrix)
    mutated["capabilities"][0]["execution_enabled"] = True
    mutated["capabilities"][1]["external_state_mutated"] = True

    payload = build_product_capability_matrix_verification(mutated)

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_capability_matrix"
    assert "local_only_fail_closed_flags" in summary["blocked_checks"]


def test_product_capability_matrix_blocks_missing_high_risk_row() -> None:
    matrix = load_product_capability_matrix(MATRIX_PATH)
    mutated = copy.deepcopy(matrix)
    mutated["capabilities"] = [
        row for row in mutated["capabilities"] if row["id"] != "wetlab_hit_claim"
    ]

    payload = build_product_capability_matrix_verification(mutated)

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_capability_matrix"
    assert "high_risk_claim_ids_present" in summary["blocked_checks"]
