from __future__ import annotations

import ast
from copy import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import inspect
import json
import os
from pathlib import Path
import py_compile
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Mapping

import pytest

from betelgeuze_engine_v2.physics.reference_validation_authorization import (
    AuthorizationOperatorTrustAnchor,
    build_signed_reference_validation_authorization_receipt,
)
from betelgeuze_engine_v2.physics.reference_validation_nonce_reservation import (
    reserve_reference_validation_authorization_nonce,
)
from betelgeuze_engine_v2.physics.reference_validation_protocol import (
    frozen_cpu_reference_validation_protocol,
)
from betelgeuze_engine_v2.physics.reference_validation_receipts import (
    FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256,
    FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
)
from betelgeuze_engine_v2.physics.reference_validation_review import (
    ScientificReviewerTrustAnchor,
    build_signed_reference_validation_review_attestation,
)
from betelgeuze_engine_v2.physics.reference_validation_run_start import (
    build_signed_reference_validation_network_isolation_attestation,
    reference_validation_artifact_output_root_identity_sha256,
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
    reference_validation_checked_out_code_commit_sha,
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
    monkeypatch.setattr(
        module,
        "reference_validation_checked_out_code_commit_sha",
        lambda: receipt.code_commit_sha,
    )
    monkeypatch.setattr(
        module,
        "_require_clean_checked_out_code_commit",
        lambda _expected_commit: None,
    )
    monkeypatch.setattr(
        module,
        "_require_isolated_python_bootstrap_runtime",
        lambda: (),
    )
    monkeypatch.setattr(module, "_require_source_only_python_runtime", lambda: None)

    def run_in_process(
        protocol: object,
        manifest_cases: object,
        **kwargs: object,
    ):
        return module._run_case_matrix_in_process(
            protocol,
            manifest_cases,
            deadline=kwargs["deadline"],
        )

    monkeypatch.setattr(module, "_run_supervised_case_matrix", run_in_process)
    monkeypatch.setattr(
        module,
        "_run_supervised_frozen_case_matrix",
        lambda **_kwargs: module._load_frozen_case_matrix(),
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

    runner_source = Path(inspect.getsourcefile(module) or "")
    bootstrap_source = Path(module.reference_validation_bootstrap_path())
    assert runner_source.is_file()
    assert bootstrap_source.is_file()
    expected_source_identity = {
        "schema_id": (
            "betelgeuze.engine_v2_reference_validation_execution_sources/1.0.0"
        ),
        "sources": [
            {
                "path": (
                    "betelgeuze_engine_v2/physics/"
                    "reference_validation_bootstrap.py"
                ),
                "sha256": hashlib.sha256(bootstrap_source.read_bytes()).hexdigest(),
            },
            {
                "path": (
                    "betelgeuze_engine_v2/physics/reference_validation_runner.py"
                ),
                "sha256": hashlib.sha256(runner_source.read_bytes()).hexdigest(),
            },
        ],
    }
    assert reference_validation_runner_source_sha256() == hashlib.sha256(
        module._canonical_bytes(expected_source_identity)
    ).hexdigest()
    assert reference_validation_checked_out_code_commit_sha() == subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True,
    ).strip()


def test_clean_checkout_preflight_uses_only_the_root_owned_absolute_git(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = reference_validation_checked_out_code_commit_sha()
    seen: dict[str, object] = {}

    def clean_run(command: object, **kwargs: object) -> SimpleNamespace:
        seen["command"] = command
        seen["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout=b"")

    monkeypatch.setattr(subprocess, "run", clean_run)
    module._require_clean_checked_out_code_commit(commit)
    command = seen["command"]
    kwargs = seen["kwargs"]
    assert isinstance(command, list)
    assert command[0] == "/usr/bin/git"
    assert command[-3:] == ["status", "--porcelain=v1", "--untracked-files=all"]
    assert isinstance(kwargs, dict)
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL
    assert kwargs["timeout"] == 10
    assert kwargs["env"]["GIT_NO_REPLACE_OBJECTS"] == "1"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=b" M betelgeuze_engine_v2/physics/reference_forcefield.py\n",
        ),
    )
    with pytest.raises(ReferenceValidationRunnerError, match="not exactly clean"):
        module._require_clean_checked_out_code_commit(commit)


def test_git_replacement_refs_are_rejected_loose_or_packed(tmp_path: Path) -> None:
    git_dir = tmp_path / "git"
    common_dir = tmp_path / "common"
    git_dir.mkdir()
    common_dir.mkdir()
    module._require_no_git_replacement_refs(git_dir, common_dir)

    loose = common_dir / "refs" / "replace"
    loose.mkdir(parents=True)
    with pytest.raises(ReferenceValidationRunnerError, match="replacement refs"):
        module._require_no_git_replacement_refs(git_dir, common_dir)
    loose.rmdir()

    (common_dir / "packed-refs").write_text(
        f"{'a' * 40} refs/replace/{'b' * 40}\n",
        encoding="ascii",
    )
    with pytest.raises(ReferenceValidationRunnerError, match="replacement refs"):
        module._require_no_git_replacement_refs(git_dir, common_dir)


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


def test_runner_rejects_checkout_or_frozen_evaluator_source_drift_before_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from betelgeuze_engine_v2.physics import reference_validation_artifact_binding

    checkout_root = _private_root(tmp_path, "checkout")
    _install_verified_receipt(monkeypatch, _receipt())
    monkeypatch.setattr(
        module,
        "reference_validation_checked_out_code_commit_sha",
        lambda: "0" * 40,
    )
    with pytest.raises(ReferenceValidationRunnerError, match="checked-out code commit"):
        _run(checkout_root)
    assert list(checkout_root.iterdir()) == []

    dirty_root = _private_root(tmp_path, "dirty")
    monkeypatch.setattr(
        module,
        "reference_validation_checked_out_code_commit_sha",
        lambda: CODE_COMMIT_SHA,
    )

    def reject_dirty_checkout(_expected_commit: str) -> None:
        raise ReferenceValidationRunnerError(
            "validation checkout is not exactly clean at the authorized commit"
        )

    monkeypatch.setattr(
        module,
        "_require_clean_checked_out_code_commit",
        reject_dirty_checkout,
    )
    with pytest.raises(ReferenceValidationRunnerError, match="not exactly clean"):
        _run(dirty_root)
    assert list(dirty_root.iterdir()) == []

    evaluator_root = _private_root(tmp_path, "evaluator")
    monkeypatch.setattr(
        module,
        "_require_clean_checked_out_code_commit",
        lambda _expected_commit: None,
    )
    monkeypatch.setattr(
        reference_validation_artifact_binding,
        "reference_forcefield_source_sha256",
        lambda: "0" * 64,
    )
    with pytest.raises(ReferenceValidationRunnerError, match="artifact source drifted"):
        _run(evaluator_root)
    assert list(evaluator_root.iterdir()) == []


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


def test_evaluator_is_interrupted_at_the_frozen_wall_clock_deadline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from betelgeuze_engine_v2.physics import reference_forcefield

    root = _private_root(tmp_path)
    _install_verified_receipt(monkeypatch, _receipt())
    protocol, manifest_cases = module._load_frozen_case_matrix()
    monkeypatch.setattr(
        module,
        "_run_supervised_frozen_case_matrix",
        lambda **_kwargs: (protocol, manifest_cases),
    )
    monkeypatch.setattr(module, "REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS", 0.05)

    def _slow(*args: object, **kwargs: object):
        time.sleep(5.0)
        return None

    monkeypatch.setattr(reference_forcefield, "evaluate_reference_force_field", _slow)
    started = time.monotonic()
    observation = _run(root)
    elapsed = time.monotonic() - started

    variants = [
        variant
        for case in observation.case_results
        for variant in case.variant_results
    ]
    assert elapsed < 1.0
    assert len(variants) == REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
    assert all(
        variant.observed_status == "time_budget_exhausted"
        for variant in variants
    )


def test_case_materialization_is_interrupted_and_all_variants_are_retained(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from betelgeuze_engine_v2.physics import reference_validation_artifact_binding
    from betelgeuze_engine_v2.physics import reference_validation_materializer

    root = _private_root(tmp_path)
    _install_verified_receipt(monkeypatch, _receipt())
    protocol, manifest_cases = module._load_frozen_case_matrix()
    monkeypatch.setattr(
        module,
        "_run_supervised_frozen_case_matrix",
        lambda **_kwargs: (protocol, manifest_cases),
    )
    binding = reference_validation_artifact_binding.frozen_reference_validation_artifact_binding()
    manifest = reference_validation_materializer.reference_validation_materialization_manifest_document()
    monkeypatch.setattr(module, "REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS", 0.05)
    monkeypatch.setattr(
        reference_validation_artifact_binding,
        "frozen_reference_validation_artifact_binding",
        lambda: binding,
    )
    monkeypatch.setattr(
        reference_validation_materializer,
        "reference_validation_materialization_manifest_document",
        lambda: manifest,
    )

    def slow_materialization(*args: object, **kwargs: object):
        time.sleep(5.0)
        raise AssertionError("deadline did not interrupt materialization")

    monkeypatch.setattr(
        reference_validation_materializer,
        "materialize_frozen_reference_validation_case",
        slow_materialization,
    )
    started = time.monotonic()
    observation = _run(root)
    elapsed = time.monotonic() - started

    variants = [
        variant
        for case in observation.case_results
        for variant in case.variant_results
    ]
    assert elapsed < 1.0
    assert len(variants) == REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
    assert all(
        variant.observed_status == "time_budget_exhausted"
        for variant in variants
    )


def test_expired_manifest_preflight_budget_does_not_consume_runner_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _private_root(tmp_path)
    _install_verified_receipt(monkeypatch, _receipt())
    monkeypatch.setattr(module, "REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS", -1.0)

    with pytest.raises(
        ReferenceValidationRunnerError,
        match="time budget expired before runner start",
    ):
        _run(root)

    assert list(root.iterdir()) == []


def test_supervisor_hard_kills_a_case_worker_at_the_wall_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol, manifest_cases = module._load_frozen_case_matrix()
    seen: dict[str, object] = {}

    class StalledProcess:
        args = [sys.executable, "--case-worker"]
        returncode: int | None = None

        def __init__(self) -> None:
            self.communicate_calls = 0

        def communicate(self, **kwargs: object):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise subprocess.TimeoutExpired(self.args, kwargs["timeout"])
            self.returncode = -9
            return b"", None

        def kill(self) -> None:
            seen["killed"] = True

    stalled = StalledProcess()

    def popen(command: object, **kwargs: object) -> StalledProcess:
        seen["command"] = command
        seen["kwargs"] = kwargs
        return stalled

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(
        module,
        "_case_worker_environment",
        lambda: {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": "/dev/null"},
    )
    rows = module._run_supervised_case_matrix(
        protocol,
        manifest_cases,
        expected_code_commit_sha=reference_validation_checked_out_code_commit_sha(),
        expected_runner_source_sha256=reference_validation_runner_source_sha256(),
        deadline=time.monotonic() + 0.01,
    )

    assert seen["killed"] is True
    assert seen["command"][-1] == "--case-worker"
    assert seen["kwargs"]["stderr"] is subprocess.DEVNULL
    assert len(rows) == REFERENCE_VALIDATION_RUNNER_MAX_CASES
    assert all(row.observed_status == "time_budget_exhausted" for row in rows)
    assert all(
        variant.observed_status == "time_budget_exhausted"
        for row in rows
        for variant in row.variant_results
    )


def test_supervisor_hard_kills_manifest_materialization_before_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    class StalledProcess:
        args = [sys.executable, "--manifest-worker"]
        returncode: int | None = None

        def __init__(self) -> None:
            self.communicate_calls = 0

        def communicate(self, **kwargs: object):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise subprocess.TimeoutExpired(self.args, kwargs["timeout"])
            self.returncode = -9
            return b"", None

        def kill(self) -> None:
            seen["killed"] = True

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: StalledProcess())
    monkeypatch.setattr(
        module,
        "_case_worker_environment",
        lambda: {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": "/dev/null"},
    )
    with pytest.raises(
        ReferenceValidationRunnerError,
        match="materialization preflight did not complete",
    ):
        module._run_supervised_frozen_case_matrix(
            expected_code_commit_sha=reference_validation_checked_out_code_commit_sha(),
            expected_runner_source_sha256=reference_validation_runner_source_sha256(),
            deadline=time.monotonic() + 0.01,
        )
    assert seen["killed"] is True


def test_source_only_import_runtime_requires_redirected_disabled_bytecode() -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": "/dev/null",
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from betelgeuze_engine_v2.physics import "
                "reference_validation_runner as runner; "
                "runner._require_source_only_python_runtime()"
            ),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")


def test_isolated_bootstrap_ignores_pythonpath_user_site_and_sitecustomize(
    tmp_path: Path,
) -> None:
    shadow_root = tmp_path / "shadow"
    shadow_torch = shadow_root / "torch"
    shadow_torch.mkdir(parents=True)
    import_marker = tmp_path / "shadow-imported"
    site_marker = tmp_path / "sitecustomize-imported"
    shadow_torch.joinpath("__init__.py").write_text(
        f"from pathlib import Path\nPath({str(import_marker)!r}).touch()\n",
        encoding="ascii",
    )
    shadow_root.joinpath("sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(site_marker)!r}).touch()\n",
        encoding="ascii",
    )
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONPATH": os.fspath(shadow_root),
            "PYTHONUSERBASE": os.fspath(shadow_root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": "/dev/null",
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-X",
            "pycache_prefix=/dev/null",
            module.reference_validation_bootstrap_path(),
        ],
        cwd=tmp_path,
        env=environment,
        input=b"{}\n",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )

    assert completed.returncode == 2
    assert completed.stdout == b""
    assert completed.stderr == b""
    assert not import_marker.exists()
    assert not site_marker.exists()


def test_runner_rejects_execution_without_isolated_bootstrap() -> None:
    with pytest.raises(
        ReferenceValidationRunnerError,
        match="isolated dependency bootstrap",
    ):
        module._require_isolated_python_bootstrap_runtime()


def test_source_only_import_runtime_ignores_a_valid_timestamp_cache(
    tmp_path: Path,
) -> None:
    source = tmp_path / "cached_target.py"
    source.write_text("VALUE='cache!'\n", encoding="ascii")
    original_stat = source.stat()
    py_compile.compile(source, doraise=True)
    source.write_text("VALUE='source'\n", encoding="ascii")
    os.utime(
        source,
        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
    )
    command = [
        sys.executable,
        "-c",
        "import cached_target; print(cached_target.VALUE)",
    ]
    vulnerable_environment = os.environ.copy()
    vulnerable_environment["PYTHONPATH"] = os.fspath(tmp_path)
    vulnerable_environment.pop("PYTHONDONTWRITEBYTECODE", None)
    vulnerable_environment.pop("PYTHONPYCACHEPREFIX", None)
    vulnerable = subprocess.run(
        command,
        env=vulnerable_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    assert vulnerable.returncode == 0
    assert vulnerable.stdout == b"cache!\n"

    source_only_environment = dict(vulnerable_environment)
    source_only_environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": "/dev/null",
        }
    )
    source_only = subprocess.run(
        command,
        env=source_only_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    assert source_only.returncode == 0
    assert source_only.stdout == b"source\n"


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


def test_exact_module_entrypoint_dispatches_canonical_stdin_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = {
        "schema_id": module.REFERENCE_VALIDATION_RUNNER_REQUEST_SCHEMA_ID,
        "reservation_root": "/private/reservations",
        "artifact_output_root": "/private/results",
        "authorization_nonce_sha256": AUTHORIZATION_NONCE,
        "authorization_receipt": {"signed": "authorization"},
        "review_attestation": {"signed": "review"},
        "expected_implementation_author_identity_sha256": "9" * 64,
        "network_isolation_attestation": {"signed": "network"},
        "expected_code_commit_sha": CODE_COMMIT_SHA,
        "expected_runner_source_sha256": "b" * 64,
        "expected_dependency_artifact_sha256_rows": DEPENDENCY_ROWS,
        "revoked_authorization_receipt_sha256s": [],
        "revoked_review_attestation_sha256s": [],
        "externally_conflicting_nonce_sha256s": [],
        "revoked_network_attestation_sha256s": [],
    }
    response = {
        "schema_id": module.REFERENCE_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID,
        "claim_safe": False,
    }
    encoded_request = module._canonical_bytes(request) + b"\n"
    output = io.BytesIO()
    monkeypatch.setattr(
        module.sys,
        "stdin",
        SimpleNamespace(buffer=io.BytesIO(encoded_request)),
    )
    monkeypatch.setattr(
        module.sys,
        "stdout",
        SimpleNamespace(buffer=output),
    )
    seen: dict[str, object] = {}

    def execute(parsed: Mapping[str, object]) -> dict[str, object]:
        seen["request"] = parsed
        return response

    monkeypatch.setattr(module, "_execute_runner_request", execute)

    assert module.main() == 0
    assert seen["request"] == request
    assert output.getvalue() == module._canonical_bytes(response) + b"\n"


def test_preconfigured_trust_store_parses_keys_and_enforces_root_owned_stats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "schema_id": module.REFERENCE_VALIDATION_TRUST_STORE_SCHEMA_ID,
        "reviewer_keys": [
            {
                "key_id": "reviewer",
                "reviewer_identity_sha256": "8" * 64,
                "verification_key_hex": "aa" * 32,
            }
        ],
        "operator_keys": [
            {
                "key_id": "operator",
                "operator_identity_sha256": "9" * 64,
                "verification_key_hex": "bb" * 32,
            }
        ],
    }
    store_path = tmp_path / "trust-store.json"
    store_path.write_bytes(module._canonical_bytes(payload) + b"\n")
    store_path.chmod(0o600)
    validate_file = module._validate_preconfigured_trust_file
    monkeypatch.setattr(
        module,
        "_open_preconfigured_trust_store",
        lambda: os.open(store_path, os.O_RDONLY | os.O_CLOEXEC),
    )
    monkeypatch.setattr(
        module,
        "_validate_preconfigured_trust_file",
        lambda _file_stat: None,
    )

    reviewer_keys, operator_keys = module._load_preconfigured_trust_anchors()

    assert set(reviewer_keys) == {"reviewer"}
    assert set(operator_keys) == {"operator"}
    assert reviewer_keys["reviewer"].verification_key == b"\xaa" * 32
    assert operator_keys["operator"].verification_key == b"\xbb" * 32

    module._validate_preconfigured_trust_directory(
        SimpleNamespace(st_mode=module.stat.S_IFDIR | 0o755, st_uid=0)
    )
    with pytest.raises(ReferenceValidationRunnerError, match="directory policy"):
        module._validate_preconfigured_trust_directory(
            SimpleNamespace(st_mode=module.stat.S_IFDIR | 0o777, st_uid=0)
        )
    validate_file(
        SimpleNamespace(
            st_mode=module.stat.S_IFREG | 0o600,
            st_uid=0,
            st_nlink=1,
            st_size=store_path.stat().st_size,
        )
    )
    with pytest.raises(ReferenceValidationRunnerError, match="file policy"):
        validate_file(
            SimpleNamespace(
                st_mode=module.stat.S_IFREG | 0o600,
                st_uid=1,
                st_nlink=1,
                st_size=store_path.stat().st_size,
            )
        )


def test_exact_module_invocation_cannot_self_authorize_with_request_keys(
    tmp_path: Path,
) -> None:
    reservation_root = _private_root(tmp_path, "reservations")
    artifact_root = _private_root(tmp_path, "artifacts")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    reviewed_at = now - timedelta(minutes=1)
    review_expires_at = now + timedelta(minutes=10)
    authorization_expires_at = now + timedelta(minutes=5)
    network_expires_at = now + timedelta(minutes=2)
    author_identity = "1" * 64
    reviewer_identity = "2" * 64
    operator_identity = "3" * 64
    review_key_id = "entrypoint-reviewer"
    operator_key_id = "entrypoint-operator"
    review_key = b"entrypoint-review-key-material-32-bytes-minimum"
    operator_key = b"entrypoint-operator-key-material-32-bytes-minimum"
    nonce = hashlib.sha256(os.fspath(tmp_path).encode("utf-8")).hexdigest()
    review_nonce = hashlib.sha256(f"review:{tmp_path}".encode("utf-8")).hexdigest()
    code_commit = reference_validation_checked_out_code_commit_sha()
    runner_source = reference_validation_runner_source_sha256()
    dependencies = {
        "numpy-1.26.4-wheel": "4" * 64,
        "python-runtime": "5" * 64,
        "torch-2.6.0-cpu-wheel": "6" * 64,
    }
    review = build_signed_reference_validation_review_attestation(
        implementation_author_identity_sha256=author_identity,
        independent_reviewer_identity_sha256=reviewer_identity,
        reviewer_key_id=review_key_id,
        signing_key=review_key,
        reviewed_at=reviewed_at,
        expires_at=review_expires_at,
        nonce_sha256=review_nonce,
    )
    reviewer_keys = {
        review_key_id: ScientificReviewerTrustAnchor(
            reviewer_identity,
            review_key,
        )
    }
    authorization = build_signed_reference_validation_authorization_receipt(
        review_attestation=review,
        trusted_reviewer_keys=reviewer_keys,
        expected_implementation_author_identity_sha256=author_identity,
        authorization_operator_identity_sha256=operator_identity,
        authorization_key_id=operator_key_id,
        signing_key=operator_key,
        issued_at=now,
        expires_at=authorization_expires_at,
        authorization_nonce_sha256=nonce,
        code_commit_sha=code_commit,
        runner_source_sha256=runner_source,
        execution_environment_contract_sha256=(
            FROZEN_REFERENCE_VALIDATION_EXECUTION_ENVIRONMENT_CONTRACT_SHA256
        ),
        result_receipt_contract_sha256=(
            FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
        ),
        dependency_artifact_sha256_rows=dependencies,
    )
    operator_keys = {
        operator_key_id: AuthorizationOperatorTrustAnchor(
            operator_identity,
            operator_key,
        )
    }
    reserve_reference_validation_authorization_nonce(
        reservation_root,
        authorization_receipt=authorization,
        review_attestation=review,
        trusted_reviewer_keys=reviewer_keys,
        expected_implementation_author_identity_sha256=author_identity,
        trusted_operator_keys=operator_keys,
        reserved_at=now,
        expected_code_commit_sha=code_commit,
        expected_runner_source_sha256=runner_source,
        expected_dependency_artifact_sha256_rows=dependencies,
    )
    namespace_identity = hashlib.sha256(
        os.readlink("/proc/self/ns/net").encode("utf-8")
    ).hexdigest()
    network = build_signed_reference_validation_network_isolation_attestation(
        authorization_receipt_sha256=authorization["receipt_sha256"],
        authorization_nonce_sha256=nonce,
        authorization_operator_identity_sha256=operator_identity,
        authorization_key_id=operator_key_id,
        signing_key=operator_key,
        code_commit_sha=code_commit,
        runner_source_sha256=runner_source,
        artifact_output_root_identity_sha256=(
            reference_validation_artifact_output_root_identity_sha256(
                artifact_root
            )
        ),
        network_namespace_identity_sha256=namespace_identity,
        observed_at=now,
        expires_at=network_expires_at,
    )
    request = {
        "schema_id": module.REFERENCE_VALIDATION_RUNNER_REQUEST_SCHEMA_ID,
        "reservation_root": os.fspath(reservation_root),
        "artifact_output_root": os.fspath(artifact_root),
        "authorization_nonce_sha256": nonce,
        "authorization_receipt": authorization,
        "review_attestation": review,
        "expected_implementation_author_identity_sha256": author_identity,
        "network_isolation_attestation": network,
        "expected_code_commit_sha": code_commit,
        "expected_runner_source_sha256": runner_source,
        "expected_dependency_artifact_sha256_rows": dependencies,
        "revoked_authorization_receipt_sha256s": [],
        "revoked_review_attestation_sha256s": [],
        "externally_conflicting_nonce_sha256s": [],
        "revoked_network_attestation_sha256s": [],
    }
    environment = os.environ.copy()
    environment.update(
        {
            "CUDA_VISIBLE_DEVICES": "",
            "HIP_VISIBLE_DEVICES": "",
            "ROCR_VISIBLE_DEVICES": "",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "MKL_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": "/dev/null",
            "TZ": "UTC",
            "PYTHONHASHSEED": "123",
            "BETELGEUZE_REFERENCE_VALIDATION_SEED": "456",
        }
    )
    self_authorized_request = dict(request)
    self_authorized_request["trusted_reviewer_keys"] = [
        {
            "key_id": review_key_id,
            "reviewer_identity_sha256": reviewer_identity,
            "verification_key_hex": review_key.hex(),
        }
    ]
    self_authorized_request["trusted_operator_keys"] = [
        {
            "key_id": operator_key_id,
            "operator_identity_sha256": operator_identity,
            "verification_key_hex": operator_key.hex(),
        }
    ]
    for candidate in (self_authorized_request, request):
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-X",
                "pycache_prefix=/dev/null",
                module.reference_validation_bootstrap_path(),
            ],
            cwd=Path(__file__).resolve().parents[2],
            env=environment,
            input=module._canonical_bytes(candidate) + b"\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
        assert completed.returncode == 2
        assert completed.stdout == b""
        assert operator_key.hex().encode("ascii") not in completed.stderr

    assert list(artifact_root.iterdir()) == []
    secret_hex = operator_key.hex().encode("ascii")
    assert secret_hex not in completed.stdout
    assert secret_hex not in completed.stderr
