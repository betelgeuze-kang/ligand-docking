from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

import tools.verify_engine_v2_global_orientation_contaminated_development as verifier
from tools.verify_engine_v2_global_orientation_contaminated_development import (
    GlobalOrientationDevelopmentProtocolError,
    load_protocol,
    verify_historical_protocol,
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


def test_historical_global_orientation_protocol_verifies_against_snapshot_only() -> None:
    observed = verify_historical_protocol(_protocol())
    assert observed["protocol_sha256"] == (
        "7ecbb5fa10ce95b035cdc0c11b2c27469caa019aa994315831ad2631cca0fdc3"
    )
    assert observed["verification_mode"] == "historical_static_source_only"
    assert observed["source_snapshot_manifest_sha256"] == (
        verifier.HISTORICAL_SNAPSHOT_MANIFEST_SHA256
    )
    assert observed["execution_authorized"] is False
    assert observed["live_checkout_verified"] is False
    assert observed["current_source_matches"] is False


def test_default_verifier_rejects_old_protocol_against_current_execution_sources() -> None:
    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="pre-import ScorerV1 source manifest",
    ):
        verify_protocol(_protocol())


def test_default_verifier_cannot_inherit_historical_source_context() -> None:
    snapshot, _ = verifier._load_historical_source_snapshot()
    token = verifier._BOUND_SOURCE_BYTES.set(snapshot)
    try:
        with pytest.raises(
            GlobalOrientationDevelopmentProtocolError,
            match="pre-import ScorerV1 source manifest",
        ):
            verify_protocol(_protocol())
        assert verifier._BOUND_SOURCE_BYTES.get() is snapshot
    finally:
        verifier._BOUND_SOURCE_BYTES.reset(token)


def test_historical_verification_restores_live_source_context_after_failure() -> None:
    changed = _protocol()
    changed["authority"]["historical_development_execution_authorized"] = True
    with pytest.raises(GlobalOrientationDevelopmentProtocolError):
        verify_historical_protocol(_reseal(changed))
    assert verifier._BOUND_SOURCE_BYTES.get() is None
    scope = verifier.SCORER_PYTHON_SOURCE_SCOPE
    assert verifier._sha256(
        verifier._source_manifest(roots=tuple(scope["roots"]), files=tuple(scope["files"]))
    ) != "7db2a8ba4bdf4c70c941b106892e36aaccd253c6a88d31ac4ef78e73fd416aa7"


@pytest.fixture
def historical_snapshot_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    destination = tmp_path / "historical-snapshot"
    shutil.copytree(verifier._HISTORICAL_SNAPSHOT_ROOT, destination)
    monkeypatch.setattr(verifier, "_HISTORICAL_SNAPSHOT_ROOT", destination)
    return destination


@pytest.mark.parametrize(
    "filename",
    (
        "guided_placement.py.txt",
        "scorer_v1.py.txt",
        "torsion_contact_refinement.py.txt",
        "source_paired_clearance_one_shot_binding.py.txt",
        "run_engine_v2_public_redocking_300.py.txt",
    ),
)
@pytest.mark.parametrize("mutation", ("tamper", "remove"))
def test_historical_source_tamper_or_absence_fails_closed(
    historical_snapshot_copy: Path, filename: str, mutation: str
) -> None:
    path = historical_snapshot_copy / filename
    if mutation == "tamper":
        path.write_bytes(path.read_bytes() + b"\n# changed archived source\n")
    else:
        path.unlink()
    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="historical source.*(drifted|not readable)",
    ):
        verify_historical_protocol(_protocol())


def test_resealed_historical_manifest_cannot_accept_changed_archived_source(
    historical_snapshot_copy: Path,
) -> None:
    path = historical_snapshot_copy / "scorer_v1.py.txt"
    changed = path.read_bytes() + b"\n# replacement\n"
    path.write_bytes(changed)
    manifest_path = historical_snapshot_copy / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    row = next(
        row for row in manifest["files"]
        if row["path"] == "betelgeuze_engine_v2/docking/scorer_v1.py"
    )
    row["sha256"] = hashlib.sha256(changed).hexdigest()
    row["size_bytes"] = len(changed)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="snapshot manifest drifted",
    ):
        verify_historical_protocol(_protocol())


def test_missing_historical_manifest_fails_closed(historical_snapshot_copy: Path) -> None:
    (historical_snapshot_copy / "manifest.json").unlink()
    with pytest.raises(GlobalOrientationDevelopmentProtocolError, match="not readable"):
        verify_historical_protocol(_protocol())


def test_historical_source_symlink_is_rejected(historical_snapshot_copy: Path) -> None:
    path = historical_snapshot_copy / "scorer_v1.py.txt"
    target = historical_snapshot_copy / "source-copy.txt"
    path.rename(target)
    path.symlink_to(target)
    with pytest.raises(GlobalOrientationDevelopmentProtocolError, match="symlink"):
        verify_historical_protocol(_protocol())


@pytest.mark.parametrize("missing", (False, True))
def test_shared_historical_source_is_still_bound_to_original_bytes(
    monkeypatch: pytest.MonkeyPatch, missing: bool
) -> None:
    target = _REPO_ROOT / "betelgeuze_engine_v2/docking/contact_validity.py"
    original_read = Path.read_bytes

    def changed_read(path: Path) -> bytes:
        if path == target:
            if missing:
                raise FileNotFoundError("simulated missing shared source")
            return original_read(path) + b"\n# unexpected shared source change\n"
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", changed_read)
    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="historical source.*(drifted|not readable)",
    ):
        verify_historical_protocol(_protocol())


def test_historical_verification_does_not_import_or_execute_engine_sources() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from pathlib import Path; "
            "from tools.verify_engine_v2_global_orientation_contaminated_development "
            "import verify_historical_protocol, load_protocol; "
            "receipt = verify_historical_protocol(load_protocol(Path("
            "'config/engine_v2_global_orientation_contaminated_development.json'))); "
            "assert receipt['execution_authorized'] is False; "
            "assert not any(name.startswith('betelgeuze_engine_v2') for name in sys.modules)",
        ],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr


def test_cli_requires_explicit_historical_mode() -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(verifier.__file__))],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode != 0
    assert "pre-import ScorerV1 source manifest drifted" in completed.stderr
    assert "historical_snapshot_verified" not in completed.stdout


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
        verify_historical_protocol(changed)


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
        verify_historical_protocol(changed)


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
        verify_historical_protocol(_protocol())


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
        verify_historical_protocol(changed)


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
            verify_historical_protocol(changed)


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
            verify_historical_protocol(changed)


def test_resealed_or_live_arm_metrics_source_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changed = _protocol()
    changed["metrics"]["arm_metrics_module_sha256"] = "0" * 64
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="arm metrics module identity",
    ):
        verify_historical_protocol(changed)

    real_file_sha256 = verifier._file_sha256

    def changed_file_sha256(path: str) -> str:
        if path == (
            "betelgeuze_engine_v2/benchmark/global_orientation_development_metrics.py"
        ):
            return "0" * 64
        return real_file_sha256(path)

    monkeypatch.setattr(verifier, "_file_sha256", changed_file_sha256)
    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="pre-import ScorerV1 source manifest|live arm metrics source",
    ):
        verify_historical_protocol(_protocol())


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
        verify_historical_protocol(_protocol())


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
        verify_historical_protocol(changed)


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
        verify_historical_protocol(changed)

    changed = _protocol()
    changed["authority_bindings"]["scorer_v1"]["native_runtime_artifact_contract"][
        "unbound_native_runtime_blocks_execution"
    ] = False
    changed = _reseal(changed)
    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="ScorerV1 authority binding",
    ):
        verify_historical_protocol(changed)


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
        verify_historical_protocol(changed)


@pytest.mark.parametrize(
    ("section", "field", "integer_value"),
    (
        ("decision", "decision_evaluator_implemented", 0),
        ("decision", "decision_requires_exact_case_comparison_receipts", 1),
        ("decision", "go_receipt_emission_authorized", 0),
        ("execution_gate", "operator_reservation_required", 1),
        ("metrics", "arm_metrics_evaluator_implemented", 1),
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
        verify_historical_protocol(changed)


def test_protocol_document_tracks_schema_hash_and_execution_boundary() -> None:
    protocol = _protocol()
    document = _PROTOCOL_DOC_PATH.read_text(encoding="utf-8")

    assert protocol["schema_id"] in document
    assert protocol["protocol_sha256"] in document
    assert "historical_development_execution_authorized = false" in document
    assert "does not answer that question." in document


def test_historical_verifier_runs_outside_checkout_without_pythonpath(tmp_path: Path) -> None:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [
            sys.executable,
            str(
                _REPO_ROOT / "tools/verify_engine_v2_global_orientation_"
                "contaminated_development.py"
            ),
            "--historical-snapshot",
        ],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    receipt = json.loads(completed.stdout)
    assert receipt["protocol_sha256"] == _protocol()["protocol_sha256"]
    assert receipt["verification_mode"] == "historical_static_source_only"
    assert receipt["execution_authorized"] is False
    assert receipt["live_checkout_verified"] is False


def test_resealed_execution_authority_escalation_fails_closed() -> None:
    changed = _protocol()
    changed["authority"]["historical_development_execution_authorized"] = True
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="authority",
    ):
        verify_historical_protocol(changed)


def test_resealed_evaluator_disable_or_go_receipt_escalation_fails_closed() -> None:
    changed = _protocol()
    changed["decision"]["decision_evaluator_implemented"] = False
    changed = _reseal(changed)
    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="decision evaluator",
    ):
        verify_historical_protocol(changed)

    changed = _protocol()
    changed["decision"]["go_receipt_emission_authorized"] = True
    changed = _reseal(changed)
    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="Go receipt",
    ):
        verify_historical_protocol(changed)


def test_resealed_or_live_decision_evaluator_source_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changed = _protocol()
    changed["decision"]["decision_evaluator_module_sha256"] = "0" * 64
    changed = _reseal(changed)
    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="decision evaluator module identity",
    ):
        verify_historical_protocol(changed)

    real_file_sha256 = verifier._file_sha256

    def changed_file_sha256(path: str) -> str:
        if path == (
            "betelgeuze_engine_v2/benchmark/"
            "global_orientation_development_decision.py"
        ):
            return "0" * 64
        return real_file_sha256(path)

    monkeypatch.setattr(verifier, "_file_sha256", changed_file_sha256)
    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="pre-import ScorerV1 source manifest|live decision evaluator source",
    ):
        verify_historical_protocol(_protocol())


def test_resealed_source_receipt_claim_fails_closed() -> None:
    changed = _protocol()
    changed["source_bindings"]["source_receipts_committed"] = True
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="source bindings",
    ):
        verify_historical_protocol(changed)


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
        verify_historical_protocol(changed)


def test_resealed_unknown_information_boundary_field_fails_closed() -> None:
    changed = _protocol()
    changed["information_boundary"]["reference_pose_input_allowed"] = True
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="information boundary key set",
    ):
        verify_historical_protocol(changed)


def test_resealed_candidate_budget_drift_fails_closed() -> None:
    changed = _protocol()
    changed["arm_contract"]["experimental"]["generator_config"]["orientation_count"] = 7
    changed["arm_contract"]["experimental"]["candidate_slot_count"] = 56
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="experimental generator config",
    ):
        verify_historical_protocol(changed)


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
        verify_historical_protocol(changed)


def test_resealed_generator_profile_drift_fails_closed() -> None:
    changed = _protocol()
    changed["arm_contract"]["experimental"]["profile_id"] = "other-profile"
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="experimental profile identity",
    ):
        verify_historical_protocol(changed)


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
        verify_historical_protocol(changed)


def test_resealed_unknown_decision_authority_fails_closed() -> None:
    changed = _protocol()
    changed["decision"]["product_execution_authorized"] = True
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="decision key set",
    ):
        verify_historical_protocol(changed)


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
        verify_historical_protocol(changed)


def test_resealed_archive_identity_drift_fails_closed() -> None:
    changed = _protocol()
    changed["source_bindings"]["historical_archive_sha256"] = "0" * 64
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="source bindings",
    ):
        verify_historical_protocol(changed)


def test_resealed_pr245_dependency_cannot_be_removed() -> None:
    changed = _protocol()
    changed["execution_gate"]["pr245_reviewed_terminal_state_required"] = False
    changed = _reseal(changed)

    with pytest.raises(
        GlobalOrientationDevelopmentProtocolError,
        match="execution gate",
    ):
        verify_historical_protocol(changed)
