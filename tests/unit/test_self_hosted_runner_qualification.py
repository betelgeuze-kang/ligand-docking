from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat

import pytest

from tools.product.self_hosted_runner_qualification import (
    NODE24_MINIMUM_RUNNER_VERSION,
    RunnerQualificationError,
    build_qualification_receipt,
    discover_runner_listener,
    parse_runner_version,
    qualify_runner,
    version_at_least,
    write_receipt,
)


ROOT = Path(__file__).resolve().parents[2]
TRUSTED_WORKFLOW = ROOT / ".github" / "workflows" / "product-api-worker-trusted.yml"


def test_semantic_runner_version_parser_and_minimum() -> None:
    assert parse_runner_version("2.327.1") == (2, 327, 1)
    assert parse_runner_version("v2.335.1") == (2, 335, 1)
    assert parse_runner_version("2.335.1+local") == (2, 335, 1)
    assert version_at_least((2, 327, 1), NODE24_MINIMUM_RUNNER_VERSION) is True
    assert version_at_least((2, 327, 0), NODE24_MINIMUM_RUNNER_VERSION) is False
    with pytest.raises(ValueError, match="semantic"):
        parse_runner_version("2.327")
    with pytest.raises(ValueError, match="semantic"):
        parse_runner_version("latest")


def test_explicit_version_receipt_is_redacted_and_deterministic() -> None:
    environment = {
        "RUNNER_NAME": "private-rocm-host-01",
        "RUNNER_OS": "Linux",
        "RUNNER_ARCH": "X64",
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "2",
        "GITHUB_SHA": "a" * 40,
    }
    receipt = qualify_runner(
        observed_version="2.335.1",
        environment=environment,
        observed_at_utc="2026-07-16T00:00:00Z",
    )
    repeated = qualify_runner(
        observed_version="2.335.1",
        environment=environment,
        observed_at_utc="2026-07-16T00:00:00Z",
    )

    assert receipt == repeated
    assert receipt["qualified"] is True
    assert receipt["setup_python_v6_qualified"] is True
    assert receipt["minimum_runner_version"] == "2.327.1"
    assert receipt["observed_runner_version"] == "2.335.1"
    assert receipt["version_source"] == "explicit_argument"
    assert receipt["runner_name_sha256"] == hashlib.sha256(
        environment["RUNNER_NAME"].encode("utf-8")
    ).hexdigest()
    assert environment["RUNNER_NAME"] not in json.dumps(receipt, sort_keys=True)
    assert receipt["receipt_sha256"]


def test_old_runner_receipt_is_fail_closed() -> None:
    receipt = build_qualification_receipt(
        observed_version="2.326.0",
        version_source="fixture",
        environment={},
        observed_at_utc="2026-07-16T00:00:00Z",
    )
    assert receipt["qualified"] is False
    assert receipt["setup_python_v6_qualified"] is False
    assert receipt["status"] == "blocked_node24_actions_runtime_runner_too_old"


def test_runner_listener_is_discovered_versioned_and_hashed(tmp_path: Path) -> None:
    runner_root = tmp_path / "actions-runner"
    listener = runner_root / "bin" / "Runner.Listener"
    listener.parent.mkdir(parents=True)
    listener.write_text("#!/bin/sh\nprintf '2.335.1\\n'\n", encoding="utf-8")
    listener.chmod(0o700)

    discovered = discover_runner_listener(
        runner_root=runner_root,
        environment={},
        parent_pid=1,
    )
    assert discovered == listener

    receipt = qualify_runner(
        runner_root=runner_root,
        environment={"RUNNER_OS": "Linux", "RUNNER_ARCH": "X64"},
        parent_pid=1,
        observed_at_utc="2026-07-16T00:00:00Z",
    )
    assert receipt["qualified"] is True
    assert receipt["version_source"] == "Runner.Listener"
    assert receipt["runner_listener_sha256"] == hashlib.sha256(listener.read_bytes()).hexdigest()
    assert receipt["runner_listener_size_bytes"] == listener.stat().st_size


def test_non_executable_or_symlink_listener_is_rejected(tmp_path: Path) -> None:
    runner_root = tmp_path / "runner"
    listener = runner_root / "bin" / "Runner.Listener"
    listener.parent.mkdir(parents=True)
    listener.write_text("2.335.1", encoding="utf-8")
    listener.chmod(0o600)
    with pytest.raises(RunnerQualificationError, match="could not be discovered"):
        discover_runner_listener(runner_root=runner_root, environment={}, parent_pid=1)

    target = tmp_path / "real-listener"
    target.write_text("#!/bin/sh\necho 2.335.1\n", encoding="utf-8")
    target.chmod(0o700)
    listener.unlink()
    try:
        listener.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(RunnerQualificationError, match="could not be discovered"):
        discover_runner_listener(runner_root=runner_root, environment={}, parent_pid=1)


def test_receipt_is_written_atomically_with_private_mode(tmp_path: Path) -> None:
    receipt = build_qualification_receipt(
        observed_version="2.335.1",
        version_source="fixture",
        environment={},
        observed_at_utc="2026-07-16T00:00:00Z",
    )
    path = write_receipt(tmp_path / "receipt.json", receipt)

    assert json.loads(path.read_text(encoding="utf-8")) == receipt
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".receipt.json.*.tmp"))


def test_trusted_workflow_qualifies_before_setup_python_and_uploads_receipt() -> None:
    source = TRUSTED_WORKFLOW.read_text(encoding="utf-8")
    qualification = "Qualify self-hosted runner for Node 24 Actions"
    setup = "Set up Python"
    assert qualification in source
    assert source.index(qualification) < source.index(setup)
    assert "self_hosted_runner_qualification.py" in source
    assert "self-hosted-runner-qualification.json" in source
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in source
    # The actual setup-python upgrade remains separate until a real receipt exists.
    assert "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065" in source
    assert "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1" not in source
