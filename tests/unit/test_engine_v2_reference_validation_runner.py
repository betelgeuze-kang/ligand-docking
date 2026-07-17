from __future__ import annotations

import ast
from copy import copy
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from betelgeuze_engine_v2.physics.reference_validation_protocol import (
    frozen_cpu_reference_validation_protocol,
)
from betelgeuze_engine_v2.physics.reference_validation_runner import (
    FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256,
    REFERENCE_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID,
    REFERENCE_VALIDATION_RUNNER_MAX_CASES,
    REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS,
    REFERENCE_VALIDATION_RUNNER_START_SCHEMA_ID,
    ReferenceValidationRunnerAlreadyStartedError,
    ReferenceValidationRunnerError,
    reference_validation_runner_contract_decision,
    reference_validation_runner_contract_document,
    reference_validation_runner_source_sha256,
    require_reference_validation_runner_contract_document,
    run_bounded_cpu_reference_validation,
)
import betelgeuze_engine_v2.physics.reference_validation_runner as module


NOW = datetime(2026, 7, 17, 9, 0, 0, tzinfo=timezone.utc)
AUTHORIZATION_NONCE = "e" * 64
ENVIRONMENT_RECEIPT_SHA256 = "1" * 64
ENVIRONMENT_FINGERPRINT_SHA256 = "2" * 64
AUTHORIZATION_RECEIPT_SHA256 = "3" * 64
CODE_COMMIT_SHA = "4" * 40
DEPENDENCY_ROWS = {
    "numpy-1.26.4-wheel": "5" * 64,
    "python-3.11-runtime": "6" * 64,
    "torch-2.6.0-cpu-wheel": "7" * 64,
}


def _private_root(tmp_path: Path, name: str = "outputs") -> Path:
    root = tmp_path / name
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return root


def _receipt(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "started_at_utc": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "receipt_sha256": ENVIRONMENT_RECEIPT_SHA256,
        "environment_fingerprint_sha256": ENVIRONMENT_FINGERPRINT_SHA256,
        "authorization_receipt_sha256": AUTHORIZATION_RECEIPT_SHA256,
        "authorization_nonce_sha256": AUTHORIZATION_NONCE,
        "code_commit_sha": CODE_COMMIT_SHA,
        "runner_source_sha256": reference_validation_runner_source_sha256(),
        "dependency_artifact_sha256_rows": tuple(sorted(DEPENDENCY_ROWS.items())),
        "application_seed": 456,
        "command_argv": module.REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _install_verified_receipt(
    monkeypatch: pytest.MonkeyPatch,
    receipt: SimpleNamespace,
    *,
    now: datetime = NOW,
) -> None:
    monkeypatch.setattr(module, "_utc_now", lambda: now)
    monkeypatch.setattr(
        module,
        "require_reference_validation_execution_environment_receipt_for_runner",
        lambda *args, **kwargs: receipt,
    )


def _run(root: Path):
    return run_bounded_cpu_reference_validation(
        root,
        AUTHORIZATION_NONCE,
        expected_environment_receipt_sha256=ENVIRONMENT_RECEIPT_SHA256,
        expected_code_commit_sha=CODE_COMMIT_SHA,
        expected_dependency_artifact_sha256_rows=DEPENDENCY_ROWS,
    )


def test_runner_contract_is_frozen_and_current_decision_remains_closed() -> None:
    first = reference_validation_runner_contract_document()
    second = reference_validation_runner_contract_document()
    decision = reference_validation_runner_contract_decision()

    assert first == second
    assert first["schema_id"] == REFERENCE_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID
    assert first["contract_sha256"] == (
        FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256
    )
    assert first["bounds"]["case_count"] == REFERENCE_VALIDATION_RUNNER_MAX_CASES
    assert first["bounds"]["variant_count"] == (
        REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
    )
    assert first["observation"]["in_memory_only"] is True
    assert first["observation"]["failed_metrics_and_cases_retained"] is True
    assert first["claim_policy"]["claim_safe"] is False
    assert require_reference_validation_runner_contract_document(first) == first

    assert decision["bounded_validation_runner_implemented"] is True
    assert decision["production_runner_start_consumed"] is False
    assert decision["production_validation_execution_authorized"] is False
    assert decision["production_validation_results_collected"] is False
    assert decision["result_receipt_writer_implemented"] is False


def test_runner_contract_rejects_tamper_and_source_identity_is_exact() -> None:
    tampered = copy(reference_validation_runner_contract_document())
    tampered["claim_policy"] = dict(tampered["claim_policy"])
    tampered["claim_policy"]["claim_safe"] = True
    with pytest.raises(
        ReferenceValidationRunnerError,
        match="does not match the frozen record",
    ):
        require_reference_validation_runner_contract_document(tampered)

    source = Path(inspect.getsourcefile(module) or "")
    assert source.is_file()
    assert reference_validation_runner_source_sha256() == hashlib.sha256(
        source.read_bytes()
    ).hexdigest()


def test_bounded_runner_retains_exact_matrix_and_consumes_start_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    _install_verified_receipt(monkeypatch, _receipt())

    observation = _run(root)
    protocol = frozen_cpu_reference_validation_protocol()
    payload = observation.to_dict()

    assert [row.case_id for row in observation.case_results] == [
        row.case_id for row in protocol.cases
    ]
    assert len(observation.case_results) == REFERENCE_VALIDATION_RUNNER_MAX_CASES
    assert sum(len(row.variant_results) for row in observation.case_results) == (
        REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
    )
    fail_closed = [
        row for row in observation.case_results if row.expected_outcome == "fail_closed"
    ]
    assert len(fail_closed) == 12
    assert all(row.observed_status == "fail_closed_as_expected" for row in fail_closed)
    assert all(
        row.metric_values
        for row in observation.case_results
        if row.expected_outcome == "pass"
    )
    assert any(
        not metric.passed
        for row in observation.case_results
        for metric in row.metric_values
    )
    assert all(
        not variant.component_energies_kcal_per_mol
        and variant.total_energy_kcal_per_mol is None
        and not variant.forces_kcal_per_mol_angstrom
        for row in fail_closed
        for variant in row.variant_results
    )
    assert payload["coverage_summary"] == {
        "case_count": 27,
        "variant_count": 59,
        "case_pass_count": sum(row.case_passed for row in observation.case_results),
        "case_failure_count": sum(
            not row.case_passed for row in observation.case_results
        ),
        "all_cases_retained": True,
        "all_variants_retained": True,
        "skipped_cases": 0,
    }
    assert payload["production_validation_results_collected"] is False
    assert payload["result_receipt_written"] is False
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False

    paths = list(root.iterdir())
    assert [path.name for path in paths] == [
        f"{AUTHORIZATION_NONCE}.runner-start.json"
    ]
    assert paths[0].stat().st_nlink == 1
    assert paths[0].stat().st_mode & 0o777 == 0o600
    start = json.loads(paths[0].read_text(encoding="ascii"))
    assert start["schema_id"] == REFERENCE_VALIDATION_RUNNER_START_SCHEMA_ID
    assert start["result_values_present"] is False
    assert start["result_receipt_written"] is False

    with pytest.raises(
        ReferenceValidationRunnerAlreadyStartedError,
        match="already started",
    ):
        _run(root)


@pytest.mark.parametrize(
    ("receipt_overrides", "now", "message"),
    [
        ({"started_at_utc": "2026-07-17T08:54:59Z"}, NOW, "not fresh"),
        ({"code_commit_sha": "8" * 40}, NOW, "code commit"),
        ({"runner_source_sha256": "9" * 64}, NOW, "runner source"),
        (
            {"dependency_artifact_sha256_rows": (("other-wheel", "a" * 64),)},
            NOW,
            "dependency artifact rows",
        ),
    ],
)
def test_runner_preflight_rejects_stale_or_crosswired_receipt_before_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    receipt_overrides: dict[str, object],
    now: datetime,
    message: str,
) -> None:
    root = _private_root(tmp_path)
    _install_verified_receipt(
        monkeypatch,
        _receipt(**receipt_overrides),
        now=now,
    )

    with pytest.raises(ReferenceValidationRunnerError, match=message):
        _run(root)
    assert list(root.iterdir()) == []


def test_unexpected_evaluator_failures_are_sanitized_and_fully_retained(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from betelgeuze_engine_v2.physics import reference_forcefield

    root = _private_root(tmp_path)
    _install_verified_receipt(monkeypatch, _receipt())

    def _unexpected(*args: object, **kwargs: object):
        raise ValueError("sensitive-internal-diagnostic-must-not-escape")

    monkeypatch.setattr(
        reference_forcefield,
        "evaluate_reference_force_field",
        _unexpected,
    )
    observation = _run(root)
    variants = [
        variant
        for case in observation.case_results
        for variant in case.variant_results
    ]

    assert len(variants) == REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
    assert all(variant.observed_status == "unexpected_error" for variant in variants)
    assert all(
        variant.observed_error_code == "unexpected_reference_evaluator_error"
        for variant in variants
    )
    assert "sensitive-internal-diagnostic" not in json.dumps(observation.to_dict())


def test_runner_public_surface_has_no_unsafe_clock_writer_or_evaluator() -> None:
    signature = inspect.signature(run_bounded_cpu_reference_validation)
    assert "checked_at" not in signature.parameters
    assert module.main() == 2
    public = set(module.__all__)
    assert not any(name.startswith("delete_") for name in public)
    assert not any(name.startswith("release_") for name in public)
    assert not any(name.startswith("write_result") for name in public)

    source = inspect.getsource(module)
    tree = ast.parse(source)
    top_level_imports = [
        node
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module == "reference_forcefield"
        for node in top_level_imports
    )
    imported_modules = {
        alias.name.split(".", 1)[0]
        for node in top_level_imports
        for alias in node.names
        if isinstance(node, ast.Import)
    }
    assert "subprocess" not in imported_modules
    assert "socket" not in imported_modules
