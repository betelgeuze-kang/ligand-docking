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
        "256c7e80ef5a016edcca91d6d378f5896589feb206e3882eed2900001491b0a0"
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


def test_generator_identity_cannot_move_with_resealed_protocol() -> None:
    changed = _protocol()
    changed["arm_contract"]["experimental"]["proposal_authority"] = "other-profile"
    changed["arm_contract"]["experimental"]["profile_id"] = "other-profile"
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="experimental proposal authority",
    ):
        verify_protocol(changed)


def test_resealed_generator_source_identity_drift_fails_closed() -> None:
    changed = _protocol()
    changed["authority_bindings"]["experimental_global_orientation"][
        "generator_module_sha256"
    ] = "0" * 64
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="experimental authority binding",
    ):
        verify_protocol(changed)


def test_generator_signature_is_checked_without_importing_engine_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        verifier,
        "_generator_parameters",
        lambda: ("ligand_coordinates", "reference_pose"),
    )

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="generator signature",
    ):
        verify_protocol(_protocol())


def test_resealed_baseline_lineage_identity_drift_fails_closed() -> None:
    changed = _protocol()
    changed["authority_bindings"]["baseline_current_v7"][
        "candidate_lineage_sha256_by_case"
    ]["6T88_MWQ"] = "0" * 64
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="baseline authority binding",
    ):
        verify_protocol(changed)


def test_resealed_scorer_or_evaluator_authority_drift_fails_closed() -> None:
    for authority, field in (
        ("scorer_v1", "implementation_source_sha256"),
        ("internal_validity", "evaluator_implementation_sha256"),
        ("posebusters", "implementation_sha256"),
        ("rmsd", "symmetry_policy_sha256"),
    ):
        changed = _protocol()
        changed["authority_bindings"][authority][field] = "0" * 64
        changed = _reseal(changed)

        with pytest.raises(
            GlobalOrientationDevelopmentProtocolError,
            match="source identity|authority binding",
        ):
            verify_protocol(changed)


def test_resealed_transitive_evaluator_source_drift_fails_closed() -> None:
    for authority, field in (
        ("scorer_v1", "python_transitive_source_manifest_sha256"),
        ("posebusters", "evaluation_source_manifest_sha256"),
        ("internal_validity", "evaluator_source_manifest_sha256"),
    ):
        changed = _protocol()
        target = changed["authority_bindings"][authority]
        if authority == "scorer_v1":
            target = target["implementation_manifest"]
        target[field] = "0" * 64
        changed = _reseal(changed)

        with pytest.raises(
            GlobalOrientationDevelopmentProtocolError,
            match="source identity|authority binding",
        ):
            verify_protocol(changed)


@pytest.mark.parametrize(
    ("relative_path", "expected_error"),
    (
        (
            "betelgeuze_engine_v2/docking/contact_validity.py",
            "pre-import ScorerV1 source manifest",
        ),
        (
            "betelgeuze_engine_v2/stack_round3_integrity_compat.py",
            "pre-import ScorerV1 source manifest",
        ),
        (
            "betelgeuze_engine_v2/benchmark/public_redocking_benchmark.py",
            "pre-import ScorerV1 source manifest",
        ),
        (
            "betelgeuze_engine_v2/stack_round1_hardening.py",
            "pre-import ScorerV1 source manifest",
        ),
    ),
)
def test_live_transitive_evaluator_source_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
    expected_error: str,
) -> None:
    real_file_sha256 = verifier._file_sha256

    def changed_file_sha256(path: str) -> str:
        if path == relative_path:
            return "0" * 64
        return real_file_sha256(path)

    monkeypatch.setattr(verifier, "_file_sha256", changed_file_sha256)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match=expected_error,
    ):
        verify_protocol(_protocol())


def test_verifier_module_import_does_not_load_engine_or_native_package() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import tools.verify_engine_v2_global_orientation_"
                "contaminated_development; "
                "assert 'betelgeuze_engine_v2' not in sys.modules; "
                "assert 'betelgeuze_engine_v2_native' not in sys.modules"
            ),
        ],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_resealed_validity_configuration_contract_drift_fails_closed() -> None:
    changed = _protocol()
    changed["authority_bindings"]["internal_validity"]["config_contract"][
        "fixed_fields"
    ]["receptor_ligand_clash_angstrom"] = 0.9
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="internal validity authority binding",
    ):
        verify_protocol(changed)


def test_resealed_runtime_artifact_or_evaluation_pipeline_drift_fails_closed() -> None:
    changed = _protocol()
    changed["authority_bindings"]["posebusters"][
        "expected_evaluation_pipeline_sha256"
    ] = "0" * 64
    changed = _reseal(changed)
    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="PoseBusters authority binding",
    ):
        verify_protocol(changed)

    changed = _protocol()
    changed["authority_bindings"]["scorer_v1"]["native_runtime_artifact_contract"][
        "unbound_native_runtime_blocks_execution"
    ] = False
    changed = _reseal(changed)
    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="ScorerV1 authority binding",
    ):
        verify_protocol(changed)


def test_resealed_generator_runtime_binding_cannot_be_bypassed() -> None:
    changed = _protocol()
    changed["authority_bindings"]["experimental_global_orientation"][
        "runtime_artifact_contract"
    ]["unbound_generator_runtime_blocks_execution"] = False
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="experimental authority binding",
    ):
        verify_protocol(changed)


@pytest.mark.parametrize(
    ("section", "field", "integer_value"),
    (
        ("decision", "decision_evaluator_implemented", 0),
        ("execution_gate", "operator_reservation_required", 1),
    ),
)
def test_resealed_boolean_integer_substitution_fails_closed(
    section: str,
    field: str,
    integer_value: int,
) -> None:
    changed = _protocol()
    changed[section][field] = integer_value
    changed = _reseal(changed)

    with pytest.raises(GlobalOrientationDevelopmentProtocolError):
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
