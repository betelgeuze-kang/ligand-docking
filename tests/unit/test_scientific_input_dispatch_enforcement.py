from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from api.config import settings
from api.runner_profile_contract import EXECUTION_MODE_RESTRICTED_PRODUCTION
from betelgeuze_product.scientific_input_provenance import build_scientific_input_provenance


PDB_TEXT = "ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 10.00           C\n"


def _manifest() -> dict:
    return {
        "job_id": "dispatch-science-input",
        "target_id": "ADRB2",
        "family": "gpcr",
        "runner_profile_id": "backmapping_scoring.production",
        "execution_mode": EXECUTION_MODE_RESTRICTED_PRODUCTION,
        "customer_submission_allowed": True,
        "synthetic_input_allowed": False,
        "production_claim_allowed": False,
        "customer_pose_emission_allowed": False,
    }


def _execution_contract() -> dict:
    return {
        "execution_mode": EXECUTION_MODE_RESTRICTED_PRODUCTION,
        "customer_submission_allowed": True,
        "synthetic_input_allowed": False,
        "production_claim_allowed": False,
        "customer_pose_emission_allowed": False,
    }


def _request_sha(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _raw_payload() -> dict:
    return {
        "family": "gpcr",
        "target_id": "ADRB2",
        "pdb_content": PDB_TEXT,
        "ligands": [{"ligand_id": "lig-1", "smiles": "CCO"}],
        "pocket_center": [1.0, 2.0, 3.0],
        "pocket_box_size": [20.0, 20.0, 20.0],
    }


def _record(tmp_path: Path) -> dict:
    raw = _raw_payload()
    request_sha256 = _request_sha(raw)
    receipt = build_scientific_input_provenance(
        raw,
        request_sha256=request_sha256,
        dispatch_manifest=_manifest(),
        root=tmp_path,
    )
    return {
        "job_id": "dispatch-science-input",
        "status": "accepted_fail_closed",
        "queue_status": "queued_fail_closed",
        "validation_status": "pass",
        "engine_dispatch_ready": True,
        "scope_claim_allowed_for_request": True,
        "worker_dispatch_enqueued": False,
        "source_host": "203.0.113.10",
        "customer_id": "tenant-a",
        "user_id": "user-a",
        "family": "gpcr",
        "target_id": "ADRB2",
        "ligand_count": 1,
        "request_sha256": request_sha256,
        "materialization_ligands": [
            {
                "ligand_id": "lig-1",
                "source_kind": "smiles",
                "source_value_sha256": hashlib.sha256(b"CCO").hexdigest(),
                "source_redacted": True,
            }
        ],
        "intake_payload": {
            "family": "gpcr",
            "target_id": "ADRB2",
            "ligands": [
                {
                    "ligand_id": "lig-1",
                    "source_kind": "smiles",
                    "source_value_sha256": hashlib.sha256(b"CCO").hexdigest(),
                    "source_redacted": True,
                }
            ],
        },
        "engine_dispatch_manifest": _manifest(),
        "scientific_input_provenance": receipt,
        "scientific_input_provenance_sha256": receipt["receipt_sha256"],
        "private_payload_stored": True,
    }


def _patch_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.docking_dispatch as dispatch

    monkeypatch.setattr(settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(
        dispatch,
        "_load_profile_contract",
        lambda _record: ({"approved": True}, _execution_contract(), "backmapping_scoring.production"),
    )


def test_restricted_dispatch_accepts_bound_receipt_and_encrypted_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.docking_dispatch as dispatch

    _patch_profile(monkeypatch)
    eligible, reason = dispatch.is_dispatch_eligible(_record(tmp_path))

    assert eligible is True
    assert reason == "eligible"


def test_restricted_dispatch_rejects_tampered_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.docking_dispatch as dispatch

    _patch_profile(monkeypatch)
    record = _record(tmp_path)
    record["scientific_input_provenance"]["pocket"]["definition_kind"] = "tampered"

    eligible, reason = dispatch.is_dispatch_eligible(record)

    assert eligible is False
    assert reason == "scientific_input_provenance_digest_mismatch"


def test_restricted_dispatch_rejects_missing_private_payload_after_raw_materialization_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.docking_dispatch as dispatch

    _patch_profile(monkeypatch)
    record = _record(tmp_path)
    record["private_payload_stored"] = False
    record["materialization_ligands"] = [{"ligand_id": "lig-1", "smiles": "CCO"}]

    eligible, reason = dispatch.is_dispatch_eligible(record)

    assert eligible is False
    assert reason == "scientific_input_private_payload_not_stored"


def test_restricted_dispatch_rejects_receipt_bound_to_another_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.docking_dispatch as dispatch

    _patch_profile(monkeypatch)
    record = _record(tmp_path)
    record["engine_dispatch_manifest"] = {
        **record["engine_dispatch_manifest"],
        "runner_profile_id": "another.production",
    }

    eligible, reason = dispatch.is_dispatch_eligible(record)

    assert eligible is False
    assert reason == "scientific_input_provenance_dispatch_mismatch"


def test_simulate_request_carries_only_redacted_receipt_and_enforcement_flags(tmp_path: Path) -> None:
    import api.docking_dispatch as dispatch

    record = _record(tmp_path)
    request = dispatch.build_simulate_request(
        record,
        execution_contract=_execution_contract(),
    )
    params = request["runner_profile_params"]

    assert params["scientific_input_provenance_required"] is True
    assert params["private_payload_stored"] is True
    assert params["scientific_input_provenance_sha256"] == record["scientific_input_provenance_sha256"]
    assert params["scientific_input_provenance"] == record["scientific_input_provenance"]
    serialized = json.dumps(request, sort_keys=True)
    assert PDB_TEXT.strip() not in serialized
    assert "CCO" not in serialized
