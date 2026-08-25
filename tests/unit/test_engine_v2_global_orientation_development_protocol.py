from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import tools.verify_engine_v2_global_orientation_contaminated_development as verifier
from tools.verify_engine_v2_global_orientation_contaminated_development import (
    GlobalOrientationDevelopmentProtocolError,
    load_protocol,
    verify_protocol,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROTOCOL_PATH = (
    _REPO_ROOT / "config/engine_v2_global_orientation_contaminated_development.json"
)
_PROTOCOL_DOC_PATH = (
    _REPO_ROOT
    / "docs/engine_v2_global_orientation_contaminated_development_protocol.md"
)


def _protocol() -> dict[str, object]:
    return load_protocol(_PROTOCOL_PATH)


def _reseal(payload: dict[str, object]) -> dict[str, object]:
    changed = copy.deepcopy(payload)
    changed.pop("protocol_sha256", None)
    changed["protocol_sha256"] = hashlib.sha256(
        json.dumps(
            changed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    return changed


def test_current_global_orientation_development_protocol_verifies() -> None:
    observed = verify_protocol(_protocol())
    assert observed == (
        "0e8591de97bd8313e748631f4e25222a62c017250b8fe64528eca2d1da0f4f68"
    )


def test_protocol_loader_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text(
        '{"authority":{"historical_development_execution_authorized":true,'
        '"historical_development_execution_authorized":false}}',
        encoding="utf-8",
    )

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="duplicate JSON key: historical_development_execution_authorized",
    ):
        load_protocol(path)


def test_live_generator_identity_cannot_move_with_resealed_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changed = _protocol()
    changed["arm_contract"]["experimental"]["proposal_authority"] = "other-profile"
    changed["arm_contract"]["experimental"]["profile_id"] = "other-profile"
    changed = _reseal(changed)
    monkeypatch.setattr(verifier, "GLOBAL_ORIENTATION_GENERATOR_ID", "other-profile")

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="live generator identity",
    ):
        verify_protocol(changed)


def test_protocol_document_tracks_schema_hash_and_execution_boundary() -> None:
    protocol = _protocol()
    document = _PROTOCOL_DOC_PATH.read_text(encoding="utf-8")

    assert protocol["schema_id"] in document
    assert protocol["protocol_sha256"] in document
    assert "historical_development_execution_authorized = false" in document
    assert "does not answer that question." in document


def test_verifier_runs_outside_checkout_without_pythonpath(tmp_path: Path) -> None:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [
            sys.executable,
            str(
                _REPO_ROOT / "tools/verify_engine_v2_global_orientation_"
                "contaminated_development.py"
            ),
        ],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == _protocol()["protocol_sha256"]


def test_resealed_execution_authority_escalation_fails_closed() -> None:
    changed = _protocol()
    changed["authority"]["historical_development_execution_authorized"] = True
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="authority",
    ):
        verify_protocol(changed)


def test_resealed_evaluator_or_go_receipt_escalation_fails_closed() -> None:
    for key in ("decision_evaluator_implemented", "go_receipt_emission_authorized"):
        changed = _protocol()
        changed["decision"][key] = True
        changed = _reseal(changed)

        with pytest.raises(
            GlobalOrientationDevelopmentProtocolError,
            match="decision evaluator|Go receipt",
        ):
            verify_protocol(changed)


def test_resealed_source_receipt_claim_fails_closed() -> None:
    changed = _protocol()
    changed["source_bindings"]["source_receipts_committed"] = True
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="source bindings",
    ):
        verify_protocol(changed)


def test_resealed_forbidden_input_drift_fails_closed() -> None:
    changed = _protocol()
    changed["information_boundary"]["generator_forbidden_inputs"].remove(
        "reference_pose"
    )
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="forbidden inputs",
    ):
        verify_protocol(changed)


def test_resealed_unknown_information_boundary_field_fails_closed() -> None:
    changed = _protocol()
    changed["information_boundary"]["reference_pose_input_allowed"] = True
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="information boundary key set",
    ):
        verify_protocol(changed)


def test_resealed_candidate_budget_drift_fails_closed() -> None:
    changed = _protocol()
    changed["arm_contract"]["experimental"]["generator_config"]["orientation_count"] = 7
    changed["arm_contract"]["experimental"]["candidate_slot_count"] = 56
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="experimental generator config",
    ):
        verify_protocol(changed)


def test_resealed_generator_configuration_drift_fails_closed() -> None:
    changed = _protocol()
    changed["arm_contract"]["experimental"]["generator_config"][
        "minimum_receptor_distance"
    ] = 1.2
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="experimental generator config",
    ):
        verify_protocol(changed)


def test_resealed_generator_profile_drift_fails_closed() -> None:
    changed = _protocol()
    changed["arm_contract"]["experimental"]["profile_id"] = "other-profile"
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="experimental profile identity",
    ):
        verify_protocol(changed)


def test_resealed_validity_contract_drift_fails_closed() -> None:
    changed = _protocol()
    changed["shared_execution_contract"]["posebusters_required_check_set_sha256"] = (
        "0" * 64
    )
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="shared execution contract",
    ):
        verify_protocol(changed)


def test_resealed_unknown_decision_authority_fails_closed() -> None:
    changed = _protocol()
    changed["decision"]["product_execution_authorized"] = True
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="decision key set",
    ):
        verify_protocol(changed)


def test_resealed_breadth_criterion_cannot_be_weakened() -> None:
    changed = _protocol()
    changed["decision"]["go_criteria_all"][0] = (
        "valid_proposal_oracle_recovery_in_at_least_1_of_7_previously_uncovered_cases"
    )
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="Go criteria",
    ):
        verify_protocol(changed)


def test_resealed_archive_identity_drift_fails_closed() -> None:
    changed = _protocol()
    changed["source_bindings"]["historical_archive_sha256"] = "0" * 64
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="source bindings",
    ):
        verify_protocol(changed)


def test_resealed_pr245_dependency_cannot_be_removed() -> None:
    changed = _protocol()
    changed["execution_gate"]["pr245_reviewed_terminal_state_required"] = False
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="execution gate",
    ):
        verify_protocol(changed)
