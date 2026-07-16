from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat

import pytest
import yaml

from tools.product.self_hosted_runner_qualification import (
    NODE24_MINIMUM_RUNNER_VERSION,
    RunnerQualificationError,
    build_qualification_receipt,
    discover_runner_listener,
    parse_runner_version,
    qualify_runner,
    verify_qualification_receipt,
    version_at_least,
    write_receipt,
)


ROOT = Path(__file__).resolve().parents[2]
HOSTED_WORKFLOW = ROOT / ".github" / "workflows" / "ci-self-hosted-runner-qualification.yml"
TRUSTED_WORKFLOW = (
    ROOT / ".github" / "workflows" / "self-hosted-runner-node24-qualification-trusted.yml"
)
CHECKOUT_V4_SHA = "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5"
CHECKOUT_V7_SHA = "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
UPLOAD_V7_SHA = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
SETUP_PYTHON_V6_SHA = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"


def _workflow(path: Path) -> dict:
    payload = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(payload, dict)
    return payload


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


def test_explicit_version_receipt_is_redacted_deterministic_and_verifiable() -> None:
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
    assert verify_qualification_receipt(receipt, require_qualified=True) == (
        True,
        "verified",
    )


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
    assert verify_qualification_receipt(receipt, require_qualified=False) == (
        True,
        "verified",
    )
    assert verify_qualification_receipt(receipt, require_qualified=True) == (
        False,
        "qualification_receipt_runner_too_old",
    )


def test_runner_listener_is_discovered_versioned_hashed_and_cross_checked(tmp_path: Path) -> None:
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
        environment={
            "RUNNER_OS": "Linux",
            "RUNNER_ARCH": "X64",
            "ACTIONS_RUNNER_VERSION": "2.335.1",
        },
        parent_pid=1,
        observed_at_utc="2026-07-16T00:00:00Z",
    )
    assert receipt["qualified"] is True
    assert receipt["version_source"] == "Runner.Listener"
    assert receipt["declared_runner_version"] == "2.335.1"
    assert receipt["declared_version_matches_listener"] is True
    assert receipt["runner_listener_sha256"] == hashlib.sha256(listener.read_bytes()).hexdigest()
    assert receipt["runner_listener_size_bytes"] == listener.stat().st_size
    assert verify_qualification_receipt(receipt, require_qualified=True) == (
        True,
        "verified",
    )


def test_declared_runner_version_cannot_override_listener(tmp_path: Path) -> None:
    runner_root = tmp_path / "actions-runner"
    listener = runner_root / "bin" / "Runner.Listener"
    listener.parent.mkdir(parents=True)
    listener.write_text("#!/bin/sh\nprintf '2.335.1\\n'\n", encoding="utf-8")
    listener.chmod(0o700)

    with pytest.raises(RunnerQualificationError, match="disagrees"):
        qualify_runner(
            runner_root=runner_root,
            environment={"ACTIONS_RUNNER_VERSION": "2.327.1"},
            parent_pid=1,
        )


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


def test_receipt_tampering_is_rejected() -> None:
    receipt = build_qualification_receipt(
        observed_version="2.335.1",
        version_source="fixture",
        environment={},
        observed_at_utc="2026-07-16T00:00:00Z",
    )
    tampered = dict(receipt)
    tampered["observed_runner_version"] = "2.326.0"
    assert verify_qualification_receipt(tampered) == (
        False,
        "qualification_receipt_digest_mismatch",
    )


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


def test_trusted_qualification_workflow_uses_node20_checkout_before_node24_upload() -> None:
    source = TRUSTED_WORKFLOW.read_text(encoding="utf-8")
    workflow = _workflow(TRUSTED_WORKFLOW)
    assert set(workflow["on"]) == {"push", "workflow_dispatch"}
    job = workflow["jobs"]["node24-runner-qualification"]
    assert job["runs-on"] == ["self-hosted", "linux"]
    assert CHECKOUT_V4_SHA in source
    assert CHECKOUT_V7_SHA not in source
    assert "actions/setup-python@" not in source

    qualification = "Qualify Runner.Listener for Node 24 Actions"
    assert qualification in source
    assert source.index(CHECKOUT_V4_SHA) < source.index(qualification) < source.index(UPLOAD_V7_SHA)
    assert "self-hosted-runner-qualification-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}.json" in source
    assert "self_hosted_runner_qualification.py" in source
    assert "retention-days: 30" in source


def test_hosted_contract_workflow_is_ephemeral_and_uses_setup_python_v6() -> None:
    source = HOSTED_WORKFLOW.read_text(encoding="utf-8")
    workflow = _workflow(HOSTED_WORKFLOW)
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["qualification-contract"]
    assert job["runs-on"] == "ubuntu-latest"
    assert SETUP_PYTHON_V6_SHA in source
    assert "self-hosted" not in str(job["runs-on"]).lower()
