from __future__ import annotations

import ast
from copy import copy
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import stat
import subprocess
import time
from types import SimpleNamespace

import pytest

import betelgeuze_engine_v2.physics.reference_minimization_validation_bootstrap as bootstrap
import betelgeuze_engine_v2.physics.reference_minimization_validation_runner as module
from betelgeuze_engine_v2.physics.reference_minimization_validation_protocol import (
    cpu_minimization_validation_protocol_document,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_runner import (
    FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256,
    REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES,
    ReferenceMinimizationValidationRunnerAlreadyStartedError,
    ReferenceMinimizationValidationRunnerError,
    reference_minimization_validation_runner_contract_decision,
    reference_minimization_validation_runner_contract_document,
    reference_minimization_validation_runner_source_sha256,
    require_reference_minimization_validation_runner_contract_document,
    run_bounded_cpu_reference_minimization_validation,
)


NOW = datetime(2026, 7, 18, 5, 0, 0, tzinfo=timezone.utc)
NONCE = "a" * 64
RECEIPT_SHA256 = "b" * 64
FINGERPRINT_SHA256 = "c" * 64
COMMIT_SHA = "d" * 40
DEPENDENCIES = (("numpy-wheel", "e" * 64), ("torch-cpu-wheel", "f" * 64))


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "artifacts"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return root


def _receipt() -> SimpleNamespace:
    return SimpleNamespace(
        started_at_utc="2026-07-18T05:00:00Z",
        receipt_sha256=RECEIPT_SHA256,
        environment_fingerprint_sha256=FINGERPRINT_SHA256,
        code_commit_sha=COMMIT_SHA,
        runner_source_sha256=reference_minimization_validation_runner_source_sha256(),
        dependency_artifact_sha256_rows=DEPENDENCIES,
        command_argv=module.REFERENCE_MINIMIZATION_VALIDATION_LOGICAL_RUNNER_ARGV,
        application_seed=456,
    )


def _install_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    receipt = _receipt()
    monkeypatch.setattr(module, "_utc_now", lambda: NOW)
    monkeypatch.setattr(
        module,
        "require_reference_minimization_validation_execution_environment_receipt_for_runner",
        lambda *args, **kwargs: receipt,
    )
    monkeypatch.setattr(
        module, "_require_clean_checked_out_code_commit", lambda expected: None
    )
    monkeypatch.setattr(module, "_require_isolated_python_bootstrap_runtime", lambda: ())
    monkeypatch.setattr(module, "_require_source_only_python_runtime", lambda: None)


def _run(root: Path):
    return run_bounded_cpu_reference_minimization_validation(
        root,
        NONCE,
        expected_environment_receipt_sha256=RECEIPT_SHA256,
        expected_code_commit_sha=COMMIT_SHA,
        expected_dependency_artifact_sha256_rows=dict(DEPENDENCIES),
    )


def _stall_worker(connection: object) -> None:
    del connection
    time.sleep(10)


def test_contract_is_frozen_and_all_claims_remain_closed() -> None:
    document = reference_minimization_validation_runner_contract_document()
    decision = reference_minimization_validation_runner_contract_decision()
    assert document["contract_sha256"] == (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_RUNNER_CONTRACT_SHA256
    )
    assert document["bounds"]["case_count"] == 14
    assert REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES == 14
    assert document["observation"]["failure_inclusive"] is True
    assert document["observation"]["result_receipt_written"] is False
    assert all(value is False for value in document["claim_policy"].values())
    assert require_reference_minimization_validation_runner_contract_document(
        document
    ) == document
    assert decision["bounded_validation_runner_implemented"] is True
    assert decision["result_receipt_writer_implemented"] is False
    assert decision["claim_safe"] is False


def test_contract_rejects_tamper_and_source_binds_bootstrap_and_runner() -> None:
    tampered = copy(reference_minimization_validation_runner_contract_document())
    tampered["claim_policy"] = dict(tampered["claim_policy"])
    tampered["claim_policy"]["claim_safe"] = True
    with pytest.raises(ReferenceMinimizationValidationRunnerError, match="frozen"):
        require_reference_minimization_validation_runner_contract_document(tampered)

    runner_path = Path(inspect.getsourcefile(module) or "")
    bootstrap_path = Path(bootstrap.reference_minimization_validation_bootstrap_path())
    source_identity = {
        "schema_id": (
            "betelgeuze.engine_v2_reference_minimization_validation_execution_sources/"
            "1.0.0"
        ),
        "sources": [
            {
                "path": "betelgeuze_engine_v2/physics/reference_minimization_validation_bootstrap.py",
                "sha256": hashlib.sha256(bootstrap_path.read_bytes()).hexdigest(),
            },
            {
                "path": "betelgeuze_engine_v2/physics/reference_minimization_validation_runner.py",
                "sha256": hashlib.sha256(runner_path.read_bytes()).hexdigest(),
            },
        ],
    }
    assert reference_minimization_validation_runner_source_sha256() == hashlib.sha256(
        module._canonical_bytes(source_identity)
    ).hexdigest()


def test_stdlib_bootstrap_has_no_package_or_third_party_imports() -> None:
    tree = ast.parse(Path(bootstrap.__file__).read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    assert imports == {
        "__future__",
        "hashlib",
        "hmac",
        "json",
        "os",
        "betelgeuze_engine_v2.physics",
        "stat",
        "subprocess",
        "sys",
        "sysconfig",
    }
    assert "torch" not in imports
    assert "numpy" not in imports
    assert bootstrap.REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_TRUST_STORE_PATH == (
        "/etc/betelgeuze/engine-v2/"
        "reference-minimization-validation-trust-anchors.json"
    )


def test_runner_defers_numpy_and_torch_imports_until_bootstrap_verification() -> None:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    top_level_imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level_imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            top_level_imports.add(node.module or "")
    assert "numpy" not in top_level_imports
    assert "torch" not in top_level_imports


def test_exact_matrix_retains_all_success_and_fail_closed_rows() -> None:
    rows = module._run_case_matrix_in_process()
    protocol = cpu_minimization_validation_protocol_document()
    expected_ids = [row["case_id"] for row in protocol["case_manifest"]["cases"]]
    assert [row.case_id for row in rows] == expected_ids
    assert [row.ordinal for row in rows] == list(range(1, 15))
    assert len(rows) == 14
    assert all(row.case_passed for row in rows)
    assert sum(row.expected_outcome == "pass" for row in rows) == 8
    assert sum(row.expected_outcome == "fail_closed" for row in rows) == 6
    assert all(
        row.observed_error_code == row.expected_error_code
        for row in rows[8:]
    )
    checkpoint_rows = {row.case_id: dict(row.metric_values) for row in rows}
    for case_id in (
        "v1_checkpoint_restart_exact",
        "v2_constrained_checkpoint_restart_exact",
        "v2_fixed_born_checkpoint_restart_exact",
    ):
        assert checkpoint_rows[case_id]["checkpoint_resume_bitwise_equal"] == 1.0


def test_deadline_retains_every_pending_case_as_failure() -> None:
    rows = module._run_case_matrix_in_process(deadline=0.0)
    assert len(rows) == 14
    assert all(row.observed_error_code == "runner_wall_time_exhausted" for row in rows)
    assert all(row.case_passed is False for row in rows)


def test_supervisor_hard_stops_a_stalled_child_and_retains_all_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_matrix_worker_main", _stall_worker)
    rows = module._run_supervised_case_matrix(deadline=time.monotonic() + 0.05)
    assert len(rows) == 14
    assert all(row.observed_error_code == "runner_wall_time_exhausted" for row in rows)
    assert all(row.case_passed is False for row in rows)


def test_run_persists_one_canonical_mode_0600_marker_and_no_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_preflight(monkeypatch)
    root = _root(tmp_path)
    observation = _run(root)
    marker = root / f"{module.REFERENCE_MINIMIZATION_VALIDATION_RUNNER_START_PREFIX}{NONCE}.json"
    payload = marker.read_bytes()
    assert stat.S_IMODE(marker.stat().st_mode) == 0o600
    assert marker.stat().st_nlink == 1
    assert payload == module._canonical_bytes(json.loads(payload))
    assert observation.all_cases_observed is True
    assert observation.all_cases_passed is True
    assert observation.to_dict()["result_receipt_written"] is False
    assert list(root.iterdir()) == [marker]
    with pytest.raises(ReferenceMinimizationValidationRunnerAlreadyStartedError):
        _run(root)
    assert marker.exists()


def test_manifest_failure_does_not_consume_start_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_preflight(monkeypatch)
    root = _root(tmp_path)
    monkeypatch.setattr(
        module,
        "_validate_manifest_before_start",
        lambda: (_ for _ in ()).throw(
            ReferenceMinimizationValidationRunnerError("manifest tamper")
        ),
    )
    with pytest.raises(ReferenceMinimizationValidationRunnerError, match="tamper"):
        _run(root)
    assert list(root.iterdir()) == []


def test_marker_reader_rejects_hardlink_and_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_preflight(monkeypatch)
    root = _root(tmp_path)
    observation = _run(root)
    marker = root / f"{module.REFERENCE_MINIMIZATION_VALIDATION_RUNNER_START_PREFIX}{NONCE}.json"
    document = module.read_reference_minimization_validation_runner_start_record(
        root,
        NONCE,
        expected_record_sha256=observation.runner_start_record_sha256,
        expected_environment_receipt_sha256=RECEIPT_SHA256,
        expected_runner_source_sha256=observation.runner_source_sha256,
    )
    assert document["runner_start_record_sha256"] == (
        observation.runner_start_record_sha256
    )
    alias = tmp_path / "marker-alias"
    os.link(marker, alias)
    with pytest.raises(ReferenceMinimizationValidationRunnerError, match="securely"):
        module.read_reference_minimization_validation_runner_start_record(
            root,
            NONCE,
            expected_record_sha256=observation.runner_start_record_sha256,
            expected_environment_receipt_sha256=RECEIPT_SHA256,
            expected_runner_source_sha256=observation.runner_source_sha256,
        )
    alias.unlink()
    payload = json.loads(marker.read_text(encoding="ascii"))
    payload["claim_safe"] = True
    marker.write_bytes(module._canonical_bytes(payload))
    with pytest.raises(ReferenceMinimizationValidationRunnerError, match="identity"):
        module.read_reference_minimization_validation_runner_start_record(
            root,
            NONCE,
            expected_record_sha256=observation.runner_start_record_sha256,
            expected_environment_receipt_sha256=RECEIPT_SHA256,
            expected_runner_source_sha256=observation.runner_source_sha256,
        )


def test_preflight_rejects_receipt_crosswire_before_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_preflight(monkeypatch)
    root = _root(tmp_path)
    receipt = _receipt()
    receipt.runner_source_sha256 = "0" * 64
    monkeypatch.setattr(
        module,
        "require_reference_minimization_validation_execution_environment_receipt_for_runner",
        lambda *args, **kwargs: receipt,
    )
    with pytest.raises(ReferenceMinimizationValidationRunnerError, match="source"):
        _run(root)
    assert list(root.iterdir()) == []


def test_direct_entrypoint_remains_closed_until_result_writer_exists() -> None:
    with pytest.raises(ReferenceMinimizationValidationRunnerError, match="writer"):
        module._main_from_canonical_request(b"{}")
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "reference_minimization_validation_result_writer" not in source
    assert "validation_receipt\": True" not in source


def test_direct_library_run_requires_external_trust_bootstrap(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ReferenceMinimizationValidationRunnerError,
        match="isolated trust bootstrap",
    ):
        _run(_root(tmp_path))


def test_real_isolated_bootstrap_fails_closed_without_production_request() -> None:
    bootstrap_path = Path(bootstrap.__file__).resolve()
    result = subprocess.run(
        [
            os.fspath(Path(os.sys.executable).resolve()),
            "-I",
            "-S",
            "-B",
            "-X",
            "pycache_prefix=/dev/null",
            os.fspath(bootstrap_path),
        ],
        input=b"{}",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == b""
