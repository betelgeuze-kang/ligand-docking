from __future__ import annotations

from pathlib import Path

import pytest

from api import simulation_scope
from core.claim_boundary import (
    CLAIM_SCOPE_RESTRICTED_LOCAL,
    GENERAL_MD_ACCURACY_CLAIM,
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    validate_manifest_claim_fields,
)


ROOT = Path(__file__).resolve().parents[2]
SUMMARY_MD = ROOT / "docs" / "commercialization_status_summary.md"


def test_commercialization_status_summary_is_navigation_index_only() -> None:
    text = SUMMARY_MD.read_text(encoding="utf-8")
    assert "Do not hand-edit green/closed claims" in text
    assert "runs/commercialization_readiness_current.json" in text
    assert "docs/p0_p1_closure_status.md" in text
    assert "api/simulation_scope.py" in text
    assert "core/claim_boundary.py" in text


def test_simulation_scope_enforces_runner_profile() -> None:
    with pytest.raises(simulation_scope.UnsupportedSimulationScopeError, match="runner_profile_id"):
        simulation_scope.validate_simulation_request_scope({"target_name": "x", "steps": 1})


def test_claim_boundary_blocks_general_md_for_placeholder() -> None:
    with pytest.raises(ValueError, match=GENERAL_MD_ACCURACY_CLAIM):
        validate_manifest_claim_fields(
            {
                "fidelity": TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
                "claim_scope": CLAIM_SCOPE_RESTRICTED_LOCAL,
                "accuracy_claim_grade": GENERAL_MD_ACCURACY_CLAIM,
            }
        )


def test_claim_boundary_allows_restricted_local_manifest() -> None:
    validate_manifest_claim_fields(
        {
            "fidelity": "sequence_mapped",
            "claim_scope": CLAIM_SCOPE_RESTRICTED_LOCAL,
            "accuracy_claim_grade": "restricted-local-delivery",
        }
    )
