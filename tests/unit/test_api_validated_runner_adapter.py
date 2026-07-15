from __future__ import annotations

from pathlib import Path

import asyncio
import datetime as dt
import hashlib
import json
import os
import sqlite3
import sys
import threading
import time

import pytest

from api.validated_runner_runtime_qualification import (
    RECEIPT_PATH_ENV,
    RECEIPT_SHA256_ENV,
    RECEIPT_SCHEMA_VERSION,
    validated_runner_namespace_runtime_receipt_template,
)


@pytest.fixture(autouse=True)
def _qualified_namespace_runtime_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    payload = validated_runner_namespace_runtime_receipt_template(
        issued_at=now - dt.timedelta(minutes=1),
        expires_at=now + dt.timedelta(hours=1),
    )
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    receipt = tmp_path / "validated-runner-namespace-runtime.json"
    receipt.write_bytes(raw)
    receipt.chmod(0o600)
    monkeypatch.setenv(RECEIPT_PATH_ENV, str(receipt))
    monkeypatch.setenv(RECEIPT_SHA256_ENV, hashlib.sha256(raw).hexdigest())


def test_validated_runner_child_environment_excludes_service_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    secret_names = [
        "PRODUCT_API_TOKEN",
        "PRODUCT_API_ADMIN_TOKEN",
        "API_RESULT_MANIFEST_SIGNING_KEY",
        "DOCKING_PRIVATE_PAYLOAD_KEYS",
        "AWS_SECRET_ACCESS_KEY",
        "UNRELATED_SERVICE_TOKEN",
        "LC_API_TOKEN",
    ]
    for name in secret_names:
        monkeypatch.setenv(name, f"secret-for-{name}")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    probe = (
        "import json,os; "
        f"names={secret_names!r}; "
        "print(json.dumps({'secret_presence': {name: name in os.environ for name in names}, "
        "'cuda_visible': os.environ.get('CUDA_VISIBLE_DEVICES', '')}, sort_keys=True))"
    )

    completed = validated_runner._run_profile_command(
        [sys.executable, "-c", probe],
        timeout_seconds=10,
    )

    assert completed["returncode"] == 0
    payload = json.loads(completed["stdout"])
    assert payload["secret_presence"] == {name: False for name in secret_names}
    assert payload["cuda_visible"] == "0"


def _write_fake_runner(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json",
                "from pathlib import Path",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--request-json', required=True)",
                "p.add_argument('--out-json', required=True)",
                "p.add_argument('--evidence-bundle', required=False, default='')",
                "args = p.parse_args()",
                "request = json.loads(Path(args.request_json).read_text(encoding='utf-8'))",
                "Path(args.out_json).write_text(json.dumps({",
                "    'ok': True,",
                "    'runner_kind': 'fake_validated_runner',",
                "    'target_name': request.get('target_name'),",
                "    'runner_profile_id': request.get('runner_profile_id'),",
                "    'evidence_bundle_path': args.evidence_bundle,",
                "}, sort_keys=True) + '\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_self_cancel_runner(path: Path) -> None:
    _write_fake_runner(path)
    payload = path.read_text(encoding="utf-8")
    path.write_text(
        payload
        + "import os, signal\n"
        + "os.kill(os.getppid(), signal.SIGTERM)\n"
        + "os._exit(0)\n",
        encoding="utf-8",
    )


def _write_slow_runner(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json, time",
                "from pathlib import Path",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--request-json', required=True)",
                "p.add_argument('--out-json', required=True)",
                "args = p.parse_args()",
                "time.sleep(10)",
                "Path(args.out_json).write_text(json.dumps({'ok': True}) + '\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_process_group_runner(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json, subprocess, sys, time",
                "from pathlib import Path",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--request-json', required=True)",
                "p.add_argument('--out-json', required=True)",
                "p.add_argument('--pid-file', required=True)",
                "p.add_argument('--late-marker', required=True)",
                "args = p.parse_args()",
                "child_code = (\"import time; from pathlib import Path; \"",
                "              \"time.sleep(3); Path(sys.argv[1]).write_text('LATE', encoding='utf-8')\")",
                "child = subprocess.Popen([sys.executable, '-c', 'import sys; ' + child_code, args.late_marker])",
                "Path(args.pid_file).write_text(json.dumps({'parent': __import__('os').getpid(), 'child': child.pid}), encoding='utf-8')",
                "time.sleep(20)",
                "Path(args.out_json).write_text(json.dumps({'ok': True}) + '\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_detached_double_fork_runner(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json, os, time",
                "from pathlib import Path",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--pid-file', required=True)",
                "p.add_argument('--late-marker', required=True)",
                "p.add_argument('--marker-delay', type=float, default=1.0)",
                "args = p.parse_args()",
                "runner_pid = os.getpid()",
                "first = os.fork()",
                "if first == 0:",
                "    os.setsid()",
                "    second = os.fork()",
                "    if second == 0:",
                "        Path(args.pid_file).write_text(json.dumps({'runner': runner_pid, 'detached': os.getpid()}), encoding='utf-8')",
                "        time.sleep(args.marker_delay)",
                "        Path(args.late_marker).write_text('LATE', encoding='utf-8')",
                "        os._exit(0)",
                "    os._exit(0)",
                "os.waitpid(first, 0)",
                "time.sleep(20)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _running_pids_with_command_token(token: str) -> list[int]:
    matches: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", errors="replace"
            )
        except OSError:
            continue
        if token in command:
            matches.append(int(entry.name))
    return matches


@pytest.mark.skipif(sys.platform != "linux", reason="Linux process containment regression")
def test_validated_runner_cancellation_contains_detached_double_fork(
    tmp_path: Path,
) -> None:
    import api.validated_runner as validated_runner

    runner = tmp_path / "detached_double_fork_runner.py"
    _write_detached_double_fork_runner(runner)
    pid_file = tmp_path / "detached-pids.json"
    late_marker = tmp_path / "detached-late-marker.txt"
    cancellation_event = threading.Event()
    outcome: dict[str, object] = {}

    def _run() -> None:
        outcome.update(
            validated_runner._run_profile_command(
                [
                    sys.executable,
                    str(runner),
                    "--pid-file",
                    str(pid_file),
                    "--late-marker",
                    str(late_marker),
                ],
                timeout_seconds=30,
                cancellation_event=cancellation_event,
            )
        )

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 2
    while not pid_file.exists():
        if time.monotonic() >= deadline:
            raise AssertionError("detached double-fork runner did not start")
        time.sleep(0.01)
    json.loads(pid_file.read_text(encoding="utf-8"))
    cancellation_event.set()
    thread.join(timeout=3)

    assert not thread.is_alive()
    assert outcome["cancelled"] is True
    deadline = time.monotonic() + 2
    while _running_pids_with_command_token(str(late_marker)) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not _running_pids_with_command_token(str(late_marker))
    time.sleep(1.1)
    assert not late_marker.exists()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux process containment regression")
def test_validated_runner_timeout_contains_detached_double_fork(
    tmp_path: Path,
) -> None:
    import api.validated_runner as validated_runner

    runner = tmp_path / "timeout_double_fork_runner.py"
    _write_detached_double_fork_runner(runner)
    pid_file = tmp_path / "timeout-detached-pids.json"
    late_marker = tmp_path / "timeout-detached-late-marker.txt"

    started = time.monotonic()
    outcome = validated_runner._run_profile_command(
        [
            sys.executable,
            str(runner),
            "--pid-file",
            str(pid_file),
            "--late-marker",
            str(late_marker),
            "--marker-delay",
            "1.4",
        ],
        timeout_seconds=1,
    )
    elapsed = time.monotonic() - started

    assert outcome["timed_out"] is True
    assert outcome["cancelled"] is False
    assert outcome["returncode"] != 0
    assert outcome["containment_error"] == ""
    assert elapsed < 5
    json.loads(pid_file.read_text(encoding="utf-8"))
    assert not _running_pids_with_command_token(str(late_marker))
    time.sleep(0.6)
    assert not late_marker.exists()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux process containment regression")
def test_validated_runner_namespace_init_cannot_be_killed_by_runner(
    tmp_path: Path,
) -> None:
    import api.validated_runner as validated_runner

    started_file = tmp_path / "namespace-kill-started.txt"
    late_marker = tmp_path / "namespace-kill-late.txt"
    probe = (
        "import os,signal,sys,time; from pathlib import Path; "
        "Path(sys.argv[1]).write_text('STARTED', encoding='utf-8'); "
        "os.kill(os.getppid(), signal.SIGSTOP); "
        "os.kill(os.getppid(), signal.SIGKILL); "
        "time.sleep(1.5); "
        "Path(sys.argv[2]).write_text('SURVIVED', encoding='utf-8')"
    )

    outcome = validated_runner._run_profile_command(
        [
            sys.executable,
            "-c",
            probe,
            str(started_file),
            str(late_marker),
        ],
        timeout_seconds=1,
    )

    assert started_file.read_text(encoding="utf-8") == "STARTED"
    assert outcome["timed_out"] is True
    assert outcome["returncode"] != 0
    assert outcome["containment_error"] == ""
    assert outcome["supervisor"] == "linux_pid_namespace_v1"
    assert not _running_pids_with_command_token(str(late_marker))
    time.sleep(0.7)
    assert not late_marker.exists()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux process containment regression")
def test_validated_runner_cannot_ptrace_or_open_supervisor_protocol() -> None:
    import api.validated_runner as validated_runner

    probe = "\n".join(
        [
            "import ctypes, json, os",
            "from pathlib import Path",
            "status = {}",
            "for line in Path('/proc/self/status').read_text(encoding='utf-8').splitlines():",
            "    key, separator, value = line.partition(':')",
            "    if separator:",
            "        status[key] = value.strip()",
            "libc = ctypes.CDLL(None, use_errno=True)",
            "ptrace_rc = libc.ptrace(0x4206, 1, None, None)",
            "ptrace_errno = ctypes.get_errno()",
            "protocol_fd_opened = False",
            "try:",
            "    protocol_fd = os.open('/proc/1/fd/1', os.O_WRONLY | os.O_NONBLOCK)",
            "except OSError:",
            "    pass",
            "else:",
            "    protocol_fd_opened = True",
            "    os.close(protocol_fd)",
            "print(json.dumps({",
            "    'cap_eff': status.get('CapEff', ''),",
            "    'no_new_privs': status.get('NoNewPrivs', ''),",
            "    'ptrace_rc': ptrace_rc,",
            "    'ptrace_errno': ptrace_errno,",
            "    'protocol_fd_opened': protocol_fd_opened,",
            "}, sort_keys=True))",
        ]
    )

    outcome = validated_runner._run_profile_command(
        [sys.executable, "-c", probe],
        timeout_seconds=5,
    )

    assert outcome["returncode"] == 0
    payload = json.loads(outcome["stdout"])
    assert int(payload["cap_eff"], 16) == 0
    assert payload["no_new_privs"] == "1"
    assert payload["ptrace_rc"] == -1
    assert payload["ptrace_errno"] in {1, 13}
    assert payload["protocol_fd_opened"] is False


@pytest.mark.skipif(sys.platform != "linux", reason="Linux process containment regression")
def test_validated_runner_self_sigterm_is_always_failure() -> None:
    import api.validated_runner as validated_runner

    probe = (
        "import os,signal; "
        "os.kill(os.getppid(), signal.SIGTERM); "
        "os._exit(0)"
    )
    outcomes = [
        validated_runner._run_profile_command(
            [sys.executable, "-c", probe],
            timeout_seconds=5,
        )
        for _ in range(5)
    ]

    assert all(outcome["cancelled"] is True for outcome in outcomes)
    assert all(outcome["returncode"] != 0 for outcome in outcomes)
    assert all(outcome["containment_error"] == "" for outcome in outcomes)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux process containment regression")
def test_validated_runner_post_reap_descendant_sigterm_is_failure() -> None:
    import api.validated_runner as validated_runner

    signal_sent_marker = "post_reap_sigterm_sent"
    probe = "\n".join(
        [
            "import os, signal",
            "runner_pid = os.getpid()",
            "if os.fork():",
            "    os._exit(0)",
            "while os.path.exists(f'/proc/{runner_pid}'):",
            "    pass",
            "os.kill(1, signal.SIGTERM)",
            f"os.write(1, b'{signal_sent_marker}\\n')",
            "os._exit(0)",
        ]
    )
    outcomes = [
        validated_runner._run_profile_command(
            [sys.executable, "-c", probe],
            timeout_seconds=5,
        )
        for _ in range(20)
    ]
    signal_sent_outcomes = [
        outcome
        for outcome in outcomes
        if signal_sent_marker in outcome["stdout"]
    ]

    assert signal_sent_outcomes
    assert all(outcome["cancelled"] is True for outcome in signal_sent_outcomes)
    assert all(outcome["returncode"] != 0 for outcome in signal_sent_outcomes)
    assert all(outcome["containment_error"] == "" for outcome in outcomes)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux process containment regression")
def test_concurrent_validated_runner_supervisors_do_not_cross_kill(
    tmp_path: Path,
) -> None:
    import api.validated_runner as validated_runner

    detached_runner = tmp_path / "concurrent_double_fork_runner.py"
    _write_detached_double_fork_runner(detached_runner)
    detached_pid_file = tmp_path / "concurrent-detached-pids.json"
    detached_marker = tmp_path / "concurrent-detached-late.txt"
    survivor_ready = tmp_path / "concurrent-survivor-ready.txt"
    survivor_marker = tmp_path / "concurrent-survivor-finished.txt"
    cancel_first = threading.Event()
    first_outcome: dict[str, object] = {}
    second_outcome: dict[str, object] = {}

    def _run_first() -> None:
        first_outcome.update(
            validated_runner._run_profile_command(
                [
                    sys.executable,
                    str(detached_runner),
                    "--pid-file",
                    str(detached_pid_file),
                    "--late-marker",
                    str(detached_marker),
                ],
                timeout_seconds=30,
                cancellation_event=cancel_first,
            )
        )

    survivor_probe = (
        "import sys,time; from pathlib import Path; "
        "Path(sys.argv[1]).write_text('READY', encoding='utf-8'); "
        "time.sleep(0.5); "
        "Path(sys.argv[2]).write_text('FINISHED', encoding='utf-8')"
    )

    def _run_second() -> None:
        second_outcome.update(
            validated_runner._run_profile_command(
                [
                    sys.executable,
                    "-c",
                    survivor_probe,
                    str(survivor_ready),
                    str(survivor_marker),
                ],
                timeout_seconds=5,
            )
        )

    first_thread = threading.Thread(target=_run_first, daemon=True)
    second_thread = threading.Thread(target=_run_second, daemon=True)
    first_thread.start()
    deadline = time.monotonic() + 2
    while not detached_pid_file.exists():
        if time.monotonic() >= deadline:
            raise AssertionError("first concurrent runner did not start")
        time.sleep(0.01)
    second_thread.start()
    deadline = time.monotonic() + 2
    while not survivor_ready.exists():
        if time.monotonic() >= deadline:
            raise AssertionError("second concurrent runner did not start")
        time.sleep(0.01)

    cancel_first.set()
    first_thread.join(timeout=3)
    second_thread.join(timeout=3)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert first_outcome["cancelled"] is True
    assert first_outcome["containment_error"] == ""
    assert second_outcome["returncode"] == 0
    assert second_outcome["containment_error"] == ""
    assert survivor_marker.read_text(encoding="utf-8") == "FINISHED"
    time.sleep(1.1)
    assert not detached_marker.exists()


def test_validated_runner_fails_before_spawn_without_linux_containment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    from api.linux_runner_supervisor import LinuxRunnerContainmentUnavailable

    spawned = False

    def _unsupported() -> None:
        raise LinuxRunnerContainmentUnavailable("test containment unavailable")

    def _must_not_spawn(*args, **kwargs):
        nonlocal spawned
        spawned = True
        raise AssertionError("runner supervisor must not spawn")

    monkeypatch.setattr(
        validated_runner,
        "require_linux_runner_supervisor_support",
        _unsupported,
    )
    monkeypatch.setattr(validated_runner.subprocess, "Popen", _must_not_spawn)

    with pytest.raises(
        LinuxRunnerContainmentUnavailable,
        match="test containment unavailable",
    ):
        validated_runner._run_profile_command(
            [sys.executable, "-c", "print('must not execute')"],
            timeout_seconds=1,
        )
    assert spawned is False


def _write_native_bundle_runner(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json",
                "from pathlib import Path",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--request-json', required=True)",
                "p.add_argument('--out-json', required=True)",
                "p.add_argument('--evidence-bundle', required=True)",
                "args = p.parse_args()",
                "request = json.loads(Path(args.request_json).read_text(encoding='utf-8'))",
                "Path(args.out_json).write_text(json.dumps({",
                "    'ok': True,",
                "    'runner_kind': 'fake_native_bundle_runner',",
                "    'target_name': request.get('target_name'),",
                "}, sort_keys=True) + '\\n', encoding='utf-8')",
                "bundle = {",
                "    'bundle_id': 'native_' + request.get('target_name', 'job'),",
                "    'project_id': request.get('target_name', 'job'),",
                "    'ranked_shortlist': [],",
                "    'trajectory_summary': {'frame_count': 0},",
                "    'backmapped_poses': [],",
                "    'interaction_report': {},",
                "    'topology_report': {",
                "        'status': 'not_assessed',",
                "        'topology_fidelity': 'placeholder_alanine',",
                "        'claim_blockers': ['topology_validity_not_assessed'],",
                "    },",
                "    'ai_residual_report': {'residual_mode': 'disabled', 'uncertainty': 1.0, 'abstained': True},",
                "    'failure_flags': ['delivery_bundle_validation_not_attached'],",
                "    'source_hashes': {",
                "        'input_hash': 'i' * 64,",
                "        'config_hash': 'c' * 64,",
                "        'model_hash': 'm' * 64,",
                "        'executable_hash': 'e' * 64,",
                "    },",
                "    'viewer_assets': [],",
                "    'wetlab_handoff_table': [],",
                "    'verdict': {",
                "        'claim_safe': False,",
                "        'verdict_label': 'native_runner_review_only',",
                "        'claim_scope': 'restricted_local_delivery_proxy_refinement_only',",
                "        'topology_fidelity': 'placeholder_alanine',",
                "        'accuracy_claim_grade': 'restricted-local-delivery',",
                "        'failure_flags': ['delivery_bundle_validation_not_attached'],",
                "    },",
                "}",
                "Path(args.evidence_bundle).write_text(json.dumps(bundle, sort_keys=True) + '\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _native_bundle_payload(project_id: str = "native-audit") -> dict:
    return {
        "bundle_id": f"native_{project_id}",
        "project_id": project_id,
        "ranked_shortlist": [],
        "trajectory_summary": {"frame_count": 0},
        "backmapped_poses": [],
        "interaction_report": {},
        "topology_report": {
            "status": "not_assessed",
            "topology_fidelity": "placeholder_alanine",
            "claim_blockers": ["topology_validity_not_assessed"],
        },
        "ai_residual_report": {
            "residual_mode": "disabled",
            "uncertainty": 1.0,
            "abstained": True,
        },
        "failure_flags": ["delivery_bundle_validation_not_attached"],
        "source_hashes": {
            "input_hash": "i" * 64,
            "config_hash": "c" * 64,
            "model_hash": "m" * 64,
            "executable_hash": "e" * 64,
        },
        "viewer_assets": [],
        "wetlab_handoff_table": [],
        "verdict": {
            "claim_safe": False,
            "verdict_label": "native_runner_review_only",
            "claim_scope": "restricted_local_delivery_proxy_refinement_only",
            "topology_fidelity": "placeholder_alanine",
            "accuracy_claim_grade": "restricted-local-delivery",
            "failure_flags": ["delivery_bundle_validation_not_attached"],
        },
    }


def _write_invalid_bundle_runner(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json",
                "from pathlib import Path",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--request-json', required=True)",
                "p.add_argument('--out-json', required=True)",
                "p.add_argument('--evidence-bundle', required=True)",
                "args = p.parse_args()",
                "request = json.loads(Path(args.request_json).read_text(encoding='utf-8'))",
                "Path(args.out_json).write_text(json.dumps({",
                "    'ok': True,",
                "    'runner_kind': 'fake_invalid_bundle_runner',",
                "    'target_name': request.get('target_name'),",
                "}, sort_keys=True) + '\\n', encoding='utf-8')",
                "Path(args.evidence_bundle).write_text(json.dumps({'bundle_id': 'x'}) + '\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_no_bundle_runner(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json",
                "from pathlib import Path",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--request-json', required=True)",
                "p.add_argument('--out-json', required=True)",
                "p.add_argument('--evidence-bundle', required=True)",
                "args = p.parse_args()",
                "request = json.loads(Path(args.request_json).read_text(encoding='utf-8'))",
                "Path(args.out_json).write_text(json.dumps({",
                "    'ok': True,",
                "    'runner_kind': 'fake_no_bundle_runner',",
                "    'target_name': request.get('target_name'),",
                "}, sort_keys=True) + '\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_evidence(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "input_contract_reviewed": True,
                "output_contract_reviewed": True,
                "claim_boundary_reviewed": True,
                "gate_policy_reviewed": True,
                "fake_result_emission_forbidden": True,
                "gate_policy_artifact": "runs/fake_gate_policy_current.json",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _profile_payload(profile_id: str, fake_runner: Path, evidence: Path) -> dict:
    return {
        "profile_id": profile_id,
        "enabled": True,
        "execution_mode": "restricted-production",
        "customer_submission_allowed": True,
        "synthetic_input_allowed": False,
        "production_claim_allowed": False,
        "customer_pose_emission_allowed": False,
        "runner_script": str(fake_runner.resolve()),
        "arguments": [
            "--request-json",
            "{request_json_path}",
            "--out-json",
            "{result_file}",
        ],
        "result_file_template": "{job_results_dir}/runner_result.json",
        "production_readiness": {
            "approved_by": "unit-test-operator",
            "approved_at_utc": "2026-06-06T00:00:00+00:00",
            "claim_scope": "unit-test-profile-only",
            "evidence_artifact": str(evidence),
            "runner_script_sha256": _sha256(fake_runner),
        },
    }


def _profile_payload_with_evidence_bundle(
    profile_id: str, fake_runner: Path, evidence: Path
) -> dict:
    payload = _profile_payload(profile_id, fake_runner, evidence)
    payload["evidence_bundle_template"] = "{job_results_dir}/evidence_bundle.json"
    payload["arguments"] = [
        "--request-json",
        "{request_json_path}",
        "--out-json",
        "{result_file}",
        "--evidence-bundle",
        "{evidence_bundle}",
    ]
    return payload


def test_api_task_executes_operator_approved_runner_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    from api.tasks import run_simulation_async

    fake_runner = tmp_path / "fake_validated_runner.py"
    _write_fake_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "smoke.json").write_text(
        json.dumps(_profile_payload("smoke", fake_runner, evidence), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    asyncio.run(
        run_simulation_async(
            "job_profile",
            {
                "target_name": "Chignolin",
                "runner_profile_id": "smoke",
                "runner_profile_params": {"ignored_by_adapter": True},
            },
        )
    )

    status = json.loads((tmp_path / "results" / "job_profile" / "status.json").read_text(encoding="utf-8"))
    result_file = Path(status["result_file"])
    execution_record = Path(status["runner_execution"])
    result = json.loads(result_file.read_text(encoding="utf-8"))

    assert status["status"] == "completed"
    assert status["runner_profile_id"] == "smoke"
    assert status["runner_profile_claim_scope"] == "unit-test-profile-only"
    assert status["result_file_sha256"]
    assert result["runner_kind"] == "fake_validated_runner"
    assert result["target_name"] == "Chignolin"
    assert execution_record.exists()
    assert "shell" not in json.loads(execution_record.read_text(encoding="utf-8"))


def test_api_rejects_runner_that_self_cancels_after_writing_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    from api.tasks import run_simulation_async

    runner = tmp_path / "self_cancel_runner.py"
    _write_self_cancel_runner(runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "self_cancel.json").write_text(
        json.dumps(
            _profile_payload("self_cancel", runner, evidence), sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    results_root = tmp_path / "results"
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(
        validated_runner.settings,
        "api_validated_runner_profiles_path",
        str(profiles_dir),
    )
    monkeypatch.setattr(
        validated_runner.settings,
        "api_validated_runner_timeout_seconds",
        5,
    )
    monkeypatch.setattr(
        validated_runner.settings,
        "results_storage_path",
        str(results_root),
    )

    with pytest.raises(RuntimeError, match="validated runner failed"):
        asyncio.run(
            run_simulation_async(
                "job_self_cancel",
                {
                    "target_name": "Chignolin",
                    "runner_profile_id": "self_cancel",
                },
            )
        )

    execution = json.loads(
        (results_root / "job_self_cancel" / "runner_execution.json").read_text(
            encoding="utf-8"
        )
    )
    assert execution["ok"] is False
    assert execution["cancelled"] is True
    assert execution["returncode"] != 0


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_validated_runner_execution_record_replaces_link_without_touching_victim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    link_kind: str,
) -> None:
    import api.validated_runner as validated_runner
    import api.worker as worker
    from api.job_store import SQLiteJobStore
    from api.tasks import run_simulation_async

    runner = tmp_path / "linked_execution_record_runner.py"
    runner.write_text(
        "\n".join(
            [
                "import argparse, json, os",
                "from pathlib import Path",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--request-json', required=True)",
                "p.add_argument('--out-json', required=True)",
                "p.add_argument('--victim', required=True)",
                "p.add_argument('--link-kind', required=True)",
                "args = p.parse_args()",
                "out = Path(args.out_json)",
                "out.write_text(json.dumps({'ok': True}) + '\\n', encoding='utf-8')",
                "reserved = out.parent / 'runner_execution.json'",
                "reserved.symlink_to(args.victim) if args.link_kind == 'symlink' else os.link(args.victim, reserved)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    victim = tmp_path / f"{link_kind}-execution-record-victim.json"
    original = b'{"external":"victim"}\n'
    victim.write_bytes(original)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    profile = _profile_payload("linked_record", runner, evidence)
    profile["arguments"].extend(
        ["--victim", str(victim), "--link-kind", link_kind]
    )
    (profiles_dir / "linked_record.json").write_text(
        json.dumps(profile, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    results_root = tmp_path / "results"
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(
        validated_runner.settings,
        "api_validated_runner_profiles_path",
        str(profiles_dir),
    )
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(results_root))

    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    request = {"target_name": "Chignolin", "runner_profile_id": "linked_record"}
    store.create_job("job_linked_record", request)
    worker.write_status_file(
        worker.job_status_path("job_linked_record"),
        {"job_id": "job_linked_record", "status": "submitted"},
    )
    completed = asyncio.run(
        worker.process_next_job_once(
            store,
            worker_id="worker-linked-record",
            runner=run_simulation_async,
            lease_seconds=60,
        )
    )

    assert completed is not None
    assert completed["status"] == "completed"
    assert victim.read_bytes() == original
    status = json.loads(Path(completed["published_status_path"]).read_text())
    execution_record = Path(status["runner_execution"])
    assert execution_record.is_file()
    assert not os.path.samefile(victim, execution_record)


@pytest.mark.parametrize("attempt_bound", [False, True], ids=["direct", "attempt"])
@pytest.mark.parametrize("artifact_kind", ["symlink", "hardlink", "fifo"])
def test_validated_runner_rejects_unsafe_result_artifacts_without_blocking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact_kind: str,
    attempt_bound: bool,
) -> None:
    import api.validated_runner as validated_runner
    from api.job_artifacts import (
        create_and_activate_attempt_results_dir,
        reset_attempt_results_dir,
    )
    from api.tasks import run_simulation_async

    runner = tmp_path / "unsafe_result_runner.py"
    runner.write_text("# execution is replaced by the deterministic test callback\n", encoding="utf-8")
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "unsafe_result.json").write_text(
        json.dumps(
            _profile_payload("unsafe_result", runner, evidence),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    results_root = tmp_path / "results"
    victim = tmp_path / f"outside-{artifact_kind}.json"
    original = b'{"outside":"victim"}\n'
    victim.write_bytes(original)

    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(
        validated_runner.settings,
        "api_validated_runner_profiles_path",
        str(profiles_dir),
    )
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(results_root))

    def _unsafe_result_callback(command, *, timeout_seconds, cancellation_event):
        del timeout_seconds, cancellation_event
        result_path = Path(command[command.index("--out-json") + 1])
        if artifact_kind == "symlink":
            result_path.symlink_to(victim)
        elif artifact_kind == "hardlink":
            os.link(victim, result_path)
        else:
            os.mkfifo(result_path, 0o600)
        return {
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "cancelled": False,
            "containment_error": "",
            "supervisor": "linux_pid_namespace_v1",
        }

    monkeypatch.setattr(validated_runner, "_run_profile_command", _unsafe_result_callback)
    binding_token = None
    job_id = f"job-{artifact_kind}-{'attempt' if attempt_bound else 'direct'}"
    if attempt_bound:
        _, binding_token = create_and_activate_attempt_results_dir(
            storage_root=results_root,
            job_id=job_id,
            worker_id="unsafe-result-worker",
            attempt_token="unsafe-result-attempt-token",
            attempt_count=1,
        )

    try:
        with pytest.raises(PermissionError, match="confined regular single-link"):
            asyncio.run(
                run_simulation_async(
                    job_id,
                    {
                        "target_name": "Chignolin",
                        "runner_profile_id": "unsafe_result",
                    },
                )
            )
        status_path = Path(validated_runner._status_path(job_id))
        status = json.loads(status_path.read_text(encoding="utf-8"))
        assert status["status"] == "failed"
        assert "result_file_sha256" not in status
        assert victim.read_bytes() == original
    finally:
        if binding_token is not None:
            reset_attempt_results_dir(binding_token)


def test_validated_runner_timeout_records_fail_closed_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    slow_runner = tmp_path / "slow_validated_runner.py"
    _write_slow_runner(slow_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "slow.json").write_text(
        json.dumps(_profile_payload("slow", slow_runner, evidence), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(slow_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 1)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    with pytest.raises(RuntimeError, match="validated runner failed"):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job_slow",
                {"target_name": "Chignolin", "runner_profile_id": "slow"},
            )
        )

    status = json.loads((tmp_path / "results" / "job_slow" / "status.json").read_text(encoding="utf-8"))
    execution_record = json.loads(Path(status["runner_execution"]).read_text(encoding="utf-8"))

    assert status["status"] == "failed"
    assert status["error"] == "validated_runner_timeout:1s"
    assert execution_record["timed_out"] is True
    assert execution_record["timeout_seconds"] == 1
    assert execution_record["process_group_killed_on_timeout"] is True
    assert execution_record["descendant_tree_contained"] is True
    assert execution_record["descendant_containment_error"] == ""
    assert execution_record["runner_supervisor"] == "linux_pid_namespace_v1"
    assert execution_record["returncode"] != 0


def test_validated_runner_cancellation_kills_process_group_and_waits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    slow_runner = tmp_path / "process_group_runner.py"
    _write_process_group_runner(slow_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    pid_file = tmp_path / "runner_pids.json"
    late_marker = tmp_path / "late-marker.txt"
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    profile = _profile_payload("cancel_group", slow_runner, evidence)
    profile["arguments"].extend(
        [
            "--pid-file",
            str(pid_file),
            "--late-marker",
            str(late_marker),
        ]
    )
    (profiles_dir / "cancel_group.json").write_text(
        json.dumps(profile, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        validated_runner,
        "ALLOWED_RUNNER_SCRIPTS",
        {str(slow_runner.resolve())},
    )
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(
        validated_runner.settings,
        "api_validated_runner_profiles_path",
        str(profiles_dir),
    )
    monkeypatch.setattr(
        validated_runner.settings,
        "api_validated_runner_timeout_seconds",
        30,
    )
    monkeypatch.setattr(
        validated_runner.settings,
        "results_storage_path",
        str(tmp_path / "results"),
    )

    async def _scenario() -> float:
        task = asyncio.create_task(
            validated_runner.execute_validated_runner_profile(
                "job_cancel_group",
                {"target_name": "Chignolin", "runner_profile_id": "cancel_group"},
            )
        )
        deadline = asyncio.get_running_loop().time() + 2
        while not pid_file.exists():
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError("validated runner did not start")
            await asyncio.sleep(0.01)
        json.loads(pid_file.read_text(encoding="utf-8"))
        started = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        return time.monotonic() - started

    cancellation_duration = asyncio.run(_scenario())
    assert cancellation_duration < 2
    deadline = time.monotonic() + 2
    while _running_pids_with_command_token(str(late_marker)) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not _running_pids_with_command_token(str(late_marker))
    time.sleep(0.2)
    assert not late_marker.exists()
    assert not (tmp_path / "results" / "job_cancel_group" / "runner_result.json").exists()


def test_repeated_cancellation_waits_for_validated_runner_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    runner = tmp_path / "repeated_cancel_runner.py"
    _write_fake_runner(runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "repeated_cancel.json").write_text(
        json.dumps(
            _profile_payload("repeated_cancel", runner, evidence), sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    command_started = threading.Event()
    cleanup_started = threading.Event()
    cleanup_finished = threading.Event()

    def _controlled_command(
        _command: list[str],
        *,
        timeout_seconds: int,
        cancellation_event: threading.Event | None = None,
    ) -> dict[str, object]:
        assert timeout_seconds > 0
        assert cancellation_event is not None
        command_started.set()
        assert cancellation_event.wait(timeout=2)
        cleanup_started.set()
        time.sleep(0.3)
        cleanup_finished.set()
        return {
            "returncode": 125,
            "timed_out": False,
            "cancelled": True,
            "stdout": "",
            "stderr": "cancelled",
            "containment_error": "",
            "supervisor": "linux_pid_namespace_v1",
        }

    monkeypatch.setattr(validated_runner, "_run_profile_command", _controlled_command)
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(
        validated_runner.settings,
        "api_validated_runner_profiles_path",
        str(profiles_dir),
    )
    monkeypatch.setattr(
        validated_runner.settings,
        "results_storage_path",
        str(tmp_path / "results"),
    )

    async def _scenario() -> float:
        task = asyncio.create_task(
            validated_runner.execute_validated_runner_profile(
                "job_repeated_cancel",
                {
                    "target_name": "Chignolin",
                    "runner_profile_id": "repeated_cancel",
                },
            )
        )
        deadline = asyncio.get_running_loop().time() + 2
        while not command_started.is_set():
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError("controlled runner did not start")
            await asyncio.sleep(0.01)
        task.cancel()
        while not cleanup_started.is_set():
            await asyncio.sleep(0.005)
        started = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        return time.monotonic() - started

    cancellation_duration = asyncio.run(_scenario())
    assert cleanup_finished.is_set()
    assert cancellation_duration >= 0.2


def test_api_task_remains_fail_closed_when_validated_runner_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    from api.tasks import run_simulation_async

    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", False)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    with pytest.raises(NotImplementedError, match="validated runner execution is disabled"):
        asyncio.run(
            run_simulation_async(
                "job_disabled",
                {"target_name": "Chignolin", "runner_profile_id": "smoke"},
            )
        )

    status = json.loads((tmp_path / "results" / "job_disabled" / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"
    assert "validated runner execution is disabled" in status["error"]


def test_validated_runner_rejects_profile_path_traversal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(tmp_path / "profiles"))
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    with pytest.raises(ValueError, match="runner_profile_id"):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job_bad",
                {"target_name": "Chignolin", "runner_profile_id": "../bad"},
            )
        )


def test_validated_runner_rejects_output_outside_job_results_before_spawn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    fake_runner = tmp_path / "fake_validated_runner.py"
    _write_fake_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    profile = _profile_payload("escaped_output", fake_runner, evidence)
    profile["result_file_template"] = "{job_results_dir}/../escaped.json"
    (profiles_dir / "escaped_output.json").write_text(
        json.dumps(profile, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        validated_runner,
        "ALLOWED_RUNNER_SCRIPTS",
        {str(fake_runner.resolve())},
    )
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(
        validated_runner.settings,
        "api_validated_runner_profiles_path",
        str(profiles_dir),
    )
    monkeypatch.setattr(
        validated_runner.settings,
        "results_storage_path",
        str(tmp_path / "results"),
    )
    spawned = False

    def _must_not_spawn(*args, **kwargs):
        nonlocal spawned
        spawned = True
        raise AssertionError("runner must not spawn")

    monkeypatch.setattr(validated_runner, "_run_profile_command", _must_not_spawn)
    with pytest.raises(PermissionError, match="escapes the job attempt"):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job_escaped_output",
                {"target_name": "Chignolin", "runner_profile_id": "escaped_output"},
            )
        )
    assert spawned is False
    assert not (tmp_path / "results" / "escaped.json").exists()


def test_validated_runner_rejects_enabled_profile_without_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    fake_runner = tmp_path / "fake_validated_runner.py"
    _write_fake_runner(fake_runner)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "missing_evidence.json").write_text(
        json.dumps(
                {
                    "profile_id": "missing_evidence",
                    "enabled": True,
                    "execution_mode": "smoke",
                    "customer_submission_allowed": False,
                    "synthetic_input_allowed": True,
                    "production_claim_allowed": False,
                    "customer_pose_emission_allowed": False,
                    "runner_script": str(fake_runner.resolve()),
                "arguments": ["--request-json", "{request_json_path}", "--out-json", "{result_file}"],
                "result_file_template": "{job_results_dir}/runner_result.json",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    profile_path = profiles_dir / "missing_evidence.json"
    explicit_profile = json.loads(profile_path.read_text(encoding="utf-8"))
    legacy_profile = dict(explicit_profile)
    for field in (
        "execution_mode",
        "customer_submission_allowed",
        "synthetic_input_allowed",
        "production_claim_allowed",
        "customer_pose_emission_allowed",
    ):
        legacy_profile.pop(field)
    profile_path.write_text(
        json.dumps(legacy_profile, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(PermissionError, match="execution_mode is required"):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job_missing_contract",
                {"target_name": "Chignolin", "runner_profile_id": "missing_evidence"},
                require_customer_submission_allowed=False,
            )
        )

    profile_path.write_text(
        json.dumps(explicit_profile, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(PermissionError, match="production_readiness"):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job_missing_evidence",
                {"target_name": "Chignolin", "runner_profile_id": "missing_evidence"},
                require_customer_submission_allowed=False,
            )
        )


def test_worker_queue_executes_validated_runner_profile_and_signs_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.artifact_access import verify_completed_result_artifacts
    import api.validated_runner as validated_runner
    import api.worker as worker
    from api.job_store import SQLiteJobStore
    from api.result_manifest import verify_result_manifest
    from api.tasks import run_simulation_async
    from api.validated_runner_execution_evidence import (
        EXECUTION_EVIDENCE_PROVENANCE_KEY,
        validate_validated_runner_execution_evidence,
    )

    fake_runner = tmp_path / "fake_validated_runner.py"
    _write_fake_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "worker_smoke.json").write_text(
        json.dumps(_profile_payload("worker_smoke", fake_runner, evidence), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    request = {
        "target_name": "Chignolin",
        "runner_profile_id": "worker_smoke",
        "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
        "runner_profile_params": {
            "ligands": ["CCO"],
            "metadata": {"ligand_smiles": "CCN"},
        },
    }
    store.create_job("job_worker_profile", request, status="submitted")
    worker.write_status_file(
        worker.job_status_path("job_worker_profile"),
        {"job_id": "job_worker_profile", "status": "submitted"},
    )

    completed = asyncio.run(
        worker.process_next_job_once(
            store,
            worker_id="worker_profile",
            runner=run_simulation_async,
            heartbeat_interval_seconds=0.05,
        )
    )

    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["result_file"]
    assert completed["result_manifest_path"]
    assert completed["evidence_bundle_path"]
    assert completed["evidence_bundle_sha256"]
    assert len(completed["evidence_bundle_sha256"]) == 64

    manifest = json.loads(Path(completed["result_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["result_file"] == completed["result_file"]
    assert verify_result_manifest(manifest, signing_key=validated_runner.settings.api_result_manifest_signing_key)
    status = json.loads((tmp_path / "results" / "job_worker_profile" / "status.json").read_text(encoding="utf-8"))
    runtime_qualification_keys = {
        "validated_runner_namespace_runtime_qualified",
        "validated_runner_namespace_runtime_receipt_schema_version",
        "validated_runner_namespace_runtime_receipt_sha256",
        "validated_runner_namespace_runtime_receipt_issued_at_utc",
        "validated_runner_namespace_runtime_receipt_expires_at_utc",
    }
    signed_runtime_qualification = manifest["worker_provenance"][
        "validated_runner_runtime_qualification"
    ]
    assert signed_runtime_qualification == {
        key: status[key] for key in runtime_qualification_keys
    }
    assert signed_runtime_qualification[
        "validated_runner_namespace_runtime_qualified"
    ] is True
    assert signed_runtime_qualification[
        "validated_runner_namespace_runtime_receipt_schema_version"
    ] == RECEIPT_SCHEMA_VERSION
    assert signed_runtime_qualification[
        "validated_runner_namespace_runtime_receipt_sha256"
    ] == os.environ[RECEIPT_SHA256_ENV]
    signed_execution_evidence = manifest["worker_provenance"][
        EXECUTION_EVIDENCE_PROVENANCE_KEY
    ]
    assert signed_execution_evidence == status[EXECUTION_EVIDENCE_PROVENANCE_KEY]
    assert validate_validated_runner_execution_evidence(
        signed_execution_evidence
    ) == signed_execution_evidence
    assert signed_execution_evidence["runner_profile_id"] == "worker_smoke"
    assert signed_execution_evidence["customer_submission_allowed"] is True
    evidence_bundle = Path(status["evidence_bundle"])
    assert evidence_bundle.exists()
    assert len(status["evidence_bundle_sha256"]) == 64
    bundle = json.loads(evidence_bundle.read_text(encoding="utf-8"))
    assert bundle["verdict"]["claim_safe"] is False
    assert bundle["source_hashes"]["executable_hash"] == _sha256(fake_runner)
    assert "delivery_bundle_validation_not_attached" in bundle["failure_flags"]
    runner_request = (Path(completed["result_file"]).parent / "request.json").read_text(
        encoding="utf-8"
    )
    assert "ATOM      1" not in runner_request
    assert "CCO" not in runner_request
    assert "CCN" not in runner_request
    assert "sha256" in runner_request

    verified = verify_completed_result_artifacts(
        job_id="job_worker_profile",
        record=completed,
        status_data=status,
        result_root=tmp_path / "results" / "job_worker_profile",
        signing_key=validated_runner.settings.api_result_manifest_signing_key,
        expected_key_id=validated_runner.settings.api_result_manifest_key_id,
    )
    try:
        assert verified.manifest["worker_provenance"] == manifest[
            "worker_provenance"
        ]
    finally:
        verified.close()


@pytest.mark.parametrize(
    "status_data",
    [
        {"validated_runner_namespace_runtime_qualified": True},
        {
            "validated_runner_namespace_runtime_qualified": 1,
            "validated_runner_namespace_runtime_receipt_schema_version": RECEIPT_SCHEMA_VERSION,
            "validated_runner_namespace_runtime_receipt_sha256": "a" * 64,
            "validated_runner_namespace_runtime_receipt_issued_at_utc": "2026-07-16T00:00:00Z",
            "validated_runner_namespace_runtime_receipt_expires_at_utc": "2026-07-16T01:00:00Z",
        },
        {
            "validated_runner_namespace_runtime_qualified": True,
            "validated_runner_namespace_runtime_receipt_schema_version": RECEIPT_SCHEMA_VERSION,
            "validated_runner_namespace_runtime_receipt_sha256": "A" * 64,
            "validated_runner_namespace_runtime_receipt_issued_at_utc": "2026-07-16T00:00:00Z",
            "validated_runner_namespace_runtime_receipt_expires_at_utc": "2026-07-16T01:00:00Z",
        },
        {
            "validated_runner_namespace_runtime_qualified": True,
            "validated_runner_namespace_runtime_receipt_schema_version": RECEIPT_SCHEMA_VERSION,
            "validated_runner_namespace_runtime_receipt_sha256": "a" * 64,
            "validated_runner_namespace_runtime_receipt_issued_at_utc": "2026-07-16T00:00:00+00:00",
            "validated_runner_namespace_runtime_receipt_expires_at_utc": "2026-07-16T01:00:00Z",
        },
    ],
)
def test_worker_rejects_partial_or_malformed_runtime_qualification_status(
    status_data: dict[str, object],
) -> None:
    import api.worker as worker

    with pytest.raises(worker.JobIntegrityError, match="runtime qualification"):
        worker._bind_validated_runner_runtime_qualification(
            {"worker_id": "worker"},
            status_data,
        )


def test_artifact_reader_rejects_boolean_alias_in_signed_worker_provenance() -> None:
    from fastapi import HTTPException

    from api.artifact_access import _require_published_worker_provenance

    expected = {
        "worker_id": "worker",
        "attempt_count": 1,
        "attempt_token_sha256": "a" * 64,
    }
    status_data = {"worker_provenance": dict(expected)}
    manifest = {
        "worker_provenance": {
            **expected,
            "attempt_count": True,
        }
    }

    with pytest.raises(HTTPException, match="provenance disagree"):
        _require_published_worker_provenance(
            status_data=status_data,
            manifest=manifest,
            expected=expected,
        )


def test_artifact_reader_rejects_unsigned_runtime_qualification_status() -> None:
    from fastapi import HTTPException

    from api.artifact_access import _require_published_worker_provenance

    expected = {
        "worker_id": "worker",
        "attempt_count": 1,
        "attempt_token_sha256": "a" * 64,
    }
    status_data = {
        "worker_provenance": dict(expected),
        "validated_runner_namespace_runtime_qualified": True,
    }
    manifest = {"worker_provenance": dict(expected)}

    with pytest.raises(HTTPException, match="not signed"):
        _require_published_worker_provenance(
            status_data=status_data,
            manifest=manifest,
            expected=expected,
        )


def test_artifact_reader_rejects_unsigned_execution_evidence_status() -> None:
    from fastapi import HTTPException

    from api.artifact_access import _require_published_worker_provenance
    from api.validated_runner_execution_evidence import (
        EXECUTION_EVIDENCE_PROVENANCE_KEY,
        tier_alpha_adrb2_execution_evidence,
    )

    expected = {
        "worker_id": "worker",
        "attempt_count": 1,
        "attempt_token_sha256": "a" * 64,
    }
    status_data = {
        "worker_provenance": dict(expected),
        EXECUTION_EVIDENCE_PROVENANCE_KEY: (
            tier_alpha_adrb2_execution_evidence("tier_alpha_job")
        ),
    }
    manifest = {"worker_provenance": dict(expected)}

    with pytest.raises(HTTPException, match="execution evidence is not signed"):
        _require_published_worker_provenance(
            status_data=status_data,
            manifest=manifest,
            expected=expected,
        )


def test_worker_lease_loss_kills_validated_runner_process_group(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    import api.worker as worker
    from api.job_store import SQLiteJobStore
    from api.tasks import run_simulation_async

    slow_runner = tmp_path / "lease_loss_runner.py"
    _write_process_group_runner(slow_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    pid_file = tmp_path / "lease_loss_pids.json"
    late_marker = tmp_path / "lease-loss-late.txt"
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    profile = _profile_payload("lease_loss", slow_runner, evidence)
    profile["arguments"].extend(
        ["--pid-file", str(pid_file), "--late-marker", str(late_marker)]
    )
    (profiles_dir / "lease_loss.json").write_text(
        json.dumps(profile, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        validated_runner,
        "ALLOWED_RUNNER_SCRIPTS",
        {str(slow_runner.resolve())},
    )
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(
        validated_runner.settings,
        "api_validated_runner_profiles_path",
        str(profiles_dir),
    )
    monkeypatch.setattr(
        validated_runner.settings,
        "api_validated_runner_timeout_seconds",
        30,
    )
    monkeypatch.setattr(
        validated_runner.settings,
        "results_storage_path",
        str(tmp_path / "results"),
    )

    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    request = {"target_name": "Chignolin", "runner_profile_id": "lease_loss"}
    store.create_job("job_lease_loss", request, max_attempts=2)
    first = store.acquire_next_job("stable-worker", lease_seconds=60)
    assert first is not None
    worker.write_status_file(
        worker.job_status_path("job_lease_loss"),
        {"job_id": "job_lease_loss", "status": "submitted"},
    )

    async def _scenario() -> dict:
        task = asyncio.create_task(
            worker.run_job_once(
                store,
                job_id="job_lease_loss",
                request_data=dict(first["request"]),
                runner=run_simulation_async,
                worker_id="stable-worker",
                attempt_token=first["attempt_token"],
                lease_seconds=60,
                heartbeat_interval_seconds=0.05,
            )
        )
        deadline = asyncio.get_running_loop().time() + 2
        while not pid_file.exists():
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError("validated runner did not start")
            await asyncio.sleep(0.01)
        json.loads(pid_file.read_text(encoding="utf-8"))
        with sqlite3.connect(store.path) as conn:
            conn.execute(
                "UPDATE simulation_jobs SET lease_expires_at_utc='2000-01-01T00:00:00+00:00' "
                "WHERE job_id='job_lease_loss'"
            )
        replacement = store.acquire_next_job("stable-worker", lease_seconds=60)
        assert replacement is not None
        assert replacement["attempt_token"] != first["attempt_token"]
        with pytest.raises(worker.JobLeaseLostError):
            await asyncio.wait_for(task, timeout=2)
        return replacement

    replacement = asyncio.run(_scenario())
    assert store.get_job("job_lease_loss")["attempt_token"] == replacement["attempt_token"]
    deadline = time.monotonic() + 2
    while _running_pids_with_command_token(str(late_marker)) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not _running_pids_with_command_token(str(late_marker))
    time.sleep(0.2)
    assert not late_marker.exists()
    assert not list((tmp_path / "results" / "job_lease_loss").rglob("runner_result.json"))


def test_validate_api_runner_profiles_cli_reports_ready_enabled_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    from tools.product.validate_api_runner_profiles import validate_profiles

    fake_runner = tmp_path / "fake_validated_runner.py"
    _write_fake_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "ready_profile.json").write_text(
        json.dumps(_profile_payload("ready_profile", fake_runner, evidence), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})

    payload = validate_profiles(profiles_dir)

    assert payload["status"] == "pass"
    assert payload["enabled_profile_count"] == 1
    assert payload["failed_profile_count"] == 0
    assert payload["enabled_native_evidence_bundle_missing_count"] == 1
    assert payload["first_enabled_native_evidence_bundle_missing_profile_id"] == "ready_profile"
    assert payload["rows"][0]["status"] == "ready"
    assert payload["rows"][0]["evidence_bundle_template_declared"] is False
    assert payload["rows"][0]["evidence_bundle_template"] == ""


def test_validate_api_runner_profiles_reports_native_evidence_bundle_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    from tools.product.validate_api_runner_profiles import validate_profiles

    fake_runner = tmp_path / "native_bundle_runner.py"
    _write_native_bundle_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "native_profile.json").write_text(
        json.dumps(_profile_payload_with_evidence_bundle("native_profile", fake_runner, evidence), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (profiles_dir / "disabled.json").write_text(
        json.dumps({"profile_id": "disabled", "enabled": False}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})

    payload = validate_profiles(profiles_dir)
    rows = {row["profile_id"]: row for row in payload["rows"]}

    assert payload["status"] == "pass"
    assert payload["enabled_native_evidence_bundle_missing_count"] == 0
    assert payload["first_enabled_native_evidence_bundle_missing_profile_id"] == ""
    assert rows["native_profile"]["status"] == "ready"
    assert rows["native_profile"]["evidence_bundle_template_declared"] is True
    assert "{job_results_dir}/evidence_bundle.json" == rows["native_profile"]["evidence_bundle_template"]
    assert rows["disabled"]["status"] == "disabled_skip"
    assert rows["disabled"]["evidence_bundle_template_declared"] is False
    assert rows["disabled"]["evidence_bundle_template"] == ""


def test_validated_runner_validates_native_evidence_bundle_and_records_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    from betelgeuze_ai_md.contracts import EvidenceBundle

    fake_runner = tmp_path / "native_bundle_runner.py"
    _write_native_bundle_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "native_profile.json").write_text(
        json.dumps(_profile_payload_with_evidence_bundle("native_profile", fake_runner, evidence), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    status_payload = asyncio.run(
        validated_runner.execute_validated_runner_profile(
            "job_native_bundle",
            {"target_name": "Chignolin", "runner_profile_id": "native_profile"},
        )
    )

    assert status_payload["status"] == "completed"
    native_bundle_path = Path(status_payload["evidence_bundle"])
    assert native_bundle_path.exists()
    assert status_payload["evidence_bundle_source"] == "validated_runner_native"
    raw_payload = json.loads(native_bundle_path.read_text(encoding="utf-8"))
    expected_fingerprint = EvidenceBundle(**raw_payload).fingerprint()
    assert status_payload["evidence_bundle_sha256"] == expected_fingerprint
    assert len(status_payload["evidence_bundle_sha256"]) == 64

    execution_record = json.loads(
        (tmp_path / "results" / "job_native_bundle" / "runner_execution.json").read_text(encoding="utf-8")
    )
    assert execution_record["evidence_bundle_template"] == "{job_results_dir}/evidence_bundle.json"
    assert execution_record["native_evidence_bundle"] == str(native_bundle_path)
    assert execution_record["native_evidence_bundle_sha256"] == expected_fingerprint


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_direct_validated_runner_rejects_linked_native_evidence_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    link_kind: str,
) -> None:
    import api.validated_runner as validated_runner
    from api.tasks import run_simulation_async

    runner = tmp_path / "linked_native_bundle_runner.py"
    runner.write_text("# execution is replaced by the deterministic test callback\n", encoding="utf-8")
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "linked_native.json").write_text(
        json.dumps(
            _profile_payload_with_evidence_bundle(
                "linked_native",
                runner,
                evidence,
            ),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    victim = tmp_path / f"outside-native-{link_kind}.json"
    original = (
        json.dumps(_native_bundle_payload(), sort_keys=True) + "\n"
    ).encode("utf-8")
    victim.write_bytes(original)
    results_root = tmp_path / "results"

    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(
        validated_runner.settings,
        "api_validated_runner_profiles_path",
        str(profiles_dir),
    )
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(results_root))

    def _linked_native_callback(command, *, timeout_seconds, cancellation_event):
        del timeout_seconds, cancellation_event
        result_path = Path(command[command.index("--out-json") + 1])
        result_path.write_text('{"ok":true}\n', encoding="utf-8")
        bundle_path = Path(command[command.index("--evidence-bundle") + 1])
        if link_kind == "symlink":
            bundle_path.symlink_to(victim)
        else:
            os.link(victim, bundle_path)
        return {
            "returncode": 0,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "cancelled": False,
            "containment_error": "",
            "supervisor": "linux_pid_namespace_v1",
        }

    monkeypatch.setattr(validated_runner, "_run_profile_command", _linked_native_callback)

    with pytest.raises(PermissionError, match="native evidence bundle is not valid JSON"):
        asyncio.run(
            run_simulation_async(
                f"job-native-{link_kind}",
                {
                    "target_name": "Chignolin",
                    "runner_profile_id": "linked_native",
                },
            )
        )

    status = json.loads(
        (results_root / f"job-native-{link_kind}" / "status.json").read_text(
            encoding="utf-8"
        )
    )
    assert status["status"] == "failed"
    assert victim.read_bytes() == original


def test_validated_runner_fail_closed_when_native_bundle_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    fake_runner = tmp_path / "no_bundle_runner.py"
    _write_no_bundle_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "no_bundle.json").write_text(
        json.dumps(_profile_payload_with_evidence_bundle("no_bundle", fake_runner, evidence), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    with pytest.raises(FileNotFoundError, match="native evidence bundle"):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job_no_bundle",
                {"target_name": "Chignolin", "runner_profile_id": "no_bundle"},
            )
        )

    status = json.loads((tmp_path / "results" / "job_no_bundle" / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"


def test_validated_runner_fail_closed_when_native_bundle_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    fake_runner = tmp_path / "invalid_bundle_runner.py"
    _write_invalid_bundle_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "invalid_bundle.json").write_text(
        json.dumps(
            _profile_payload_with_evidence_bundle("invalid_bundle", fake_runner, evidence), sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    with pytest.raises(PermissionError, match="EvidenceBundle validation"):
        asyncio.run(
            validated_runner.execute_validated_runner_profile(
                "job_invalid_bundle",
                {"target_name": "Chignolin", "runner_profile_id": "invalid_bundle"},
            )
        )

    status = json.loads((tmp_path / "results" / "job_invalid_bundle" / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"


def test_worker_adopts_validated_native_evidence_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    import api.worker as worker
    from api.job_store import SQLiteJobStore
    from betelgeuze_ai_md.contracts import EvidenceBundle
    from api.tasks import run_simulation_async

    fake_runner = tmp_path / "native_bundle_runner.py"
    _write_native_bundle_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "worker_native.json").write_text(
        json.dumps(
            _profile_payload_with_evidence_bundle("worker_native", fake_runner, evidence), sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    request = {
        "target_name": "Chignolin",
        "runner_profile_id": "worker_native",
    }
    store.create_job("job_worker_native", request, status="submitted")
    worker.write_status_file(
        worker.job_status_path("job_worker_native"),
        {"job_id": "job_worker_native", "status": "submitted"},
    )

    completed = asyncio.run(
        worker.process_next_job_once(
            store,
            worker_id="worker_native",
            runner=run_simulation_async,
            heartbeat_interval_seconds=0.05,
        )
    )

    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["evidence_bundle_path"]
    assert completed["evidence_bundle_sha256"]
    assert len(completed["evidence_bundle_sha256"]) == 64

    status = json.loads(
        (tmp_path / "results" / "job_worker_native" / "status.json").read_text(encoding="utf-8")
    )
    native_bundle_path = Path(status["evidence_bundle"])
    assert native_bundle_path.exists()
    assert native_bundle_path.name == "evidence_bundle.json"
    raw_payload = json.loads(native_bundle_path.read_text(encoding="utf-8"))
    expected_fingerprint = EvidenceBundle(**raw_payload).fingerprint()
    assert completed["evidence_bundle_sha256"] == expected_fingerprint
    assert status["evidence_bundle_sha256"] == expected_fingerprint
    assert status["evidence_bundle_source"] == "validated_runner_native"
    assert "delivery_bundle_validation_not_attached" in raw_payload["failure_flags"]


def test_validated_runner_without_template_keeps_fallback_no_native_bundle_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner

    fake_runner = tmp_path / "fake_validated_runner.py"
    _write_fake_runner(fake_runner)
    evidence = tmp_path / "profile_evidence.json"
    _write_evidence(evidence)
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "fallback.json").write_text(
        json.dumps(_profile_payload("fallback", fake_runner, evidence), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(validated_runner.settings, "api_validated_runner_timeout_seconds", 5)
    monkeypatch.setattr(validated_runner.settings, "results_storage_path", str(tmp_path / "results"))

    status_payload = asyncio.run(
        validated_runner.execute_validated_runner_profile(
            "job_fallback",
            {"target_name": "Chignolin", "runner_profile_id": "fallback"},
        )
    )

    assert status_payload["status"] == "completed"
    assert "evidence_bundle" not in status_payload
    assert "evidence_bundle_sha256" not in status_payload

    execution_record = json.loads(
        (tmp_path / "results" / "job_fallback" / "runner_execution.json").read_text(encoding="utf-8")
    )
    assert execution_record["evidence_bundle_template"] == ""
    assert execution_record["native_evidence_bundle"] == ""
    assert execution_record["native_evidence_bundle_sha256"] == ""
