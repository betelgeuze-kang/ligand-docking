from __future__ import annotations

import pytest

from api.config import settings
from api.runner_profile_contract import EXECUTION_MODE_RESTRICTED_PRODUCTION


def test_restricted_dispatch_still_rejects_redacted_only_ligands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.docking_dispatch as dispatch

    execution = {
        "execution_mode": EXECUTION_MODE_RESTRICTED_PRODUCTION,
        "customer_submission_allowed": True,
        "synthetic_input_allowed": False,
        "production_claim_allowed": False,
        "customer_pose_emission_allowed": False,
    }
    monkeypatch.setattr(settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(
        dispatch,
        "_load_profile_contract",
        lambda _record: ({"approved": True}, execution, "backmapping_scoring.production"),
    )
    record = {
        "job_id": "redacted-only",
        "status": "accepted_fail_closed",
        "queue_status": "queued_fail_closed",
        "validation_status": "pass",
        "engine_dispatch_ready": True,
        "scope_claim_allowed_for_request": True,
        "worker_dispatch_enqueued": False,
        "source_host": "203.0.113.10",
        "ligand_count": 1,
        "materialization_ligands": [
            {
                "ligand_id": "LIG-001",
                "source_kind": "smiles",
                "source_value_sha256": "a" * 64,
                "source_redacted": True,
            }
        ],
        "engine_dispatch_manifest": {
            "runner_profile_id": "backmapping_scoring.production",
            "execution_mode": EXECUTION_MODE_RESTRICTED_PRODUCTION,
        },
    }

    eligible, reason = dispatch.is_dispatch_eligible(record)

    assert eligible is False
    assert reason == "runner_input_materialization_not_ready"
