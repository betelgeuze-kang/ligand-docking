from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import types

import pytest

from betelgeuze_product import docking_cli, prepared_lifecycle_cli


@pytest.fixture
def facade(monkeypatch):
    from betelgeuze_product import prepared_lifecycle as lifecycle

    class FakeFacade:
        def __init__(self):
            self.calls = []

        def _record(self, action, *args, **kwargs):
            self.calls.append((action, args, kwargs))
            return {
                "execution_id": "a" * 32, "status": "queued",
                "cancel_state": "requested" if action == "cancel" else "none",
                "research_only": True, "qualified": False,
            }

        def submit(self, *args, **kwargs):
            return self._record("submit", *args, **kwargs)

        def status(self, *args, **kwargs):
            return self._record("status", *args, **kwargs)

        def cancel(self, *args, **kwargs):
            return self._record("cancel", *args, **kwargs)

        def resume(self, *args, **kwargs):
            return self._record("resume", *args, **kwargs)

        def artifacts(self, *args, **kwargs):
            return self._record("artifacts", *args, **kwargs)

        def artifact(self, *args, **kwargs):
            self._record("artifact", *args, **kwargs)
            return Path("/private/server/artifact.json"), {
                "artifact_id": "b" * 32, "sha256": "c" * 64, "bytes": 2,
                "media_type": "application/json", "role": "report", "schema": "test/1",
            }

    service = FakeFacade()
    constructed = []

    def configured_service(**kwargs):
        constructed.append(kwargs)
        return service

    monkeypatch.setattr(lifecycle, "configured_service", configured_service)
    return service, constructed


@pytest.mark.parametrize("arguments,expected", [
    (["submit", "admitted-input", "--idempotency-key", "client:key"],
     ("submit", ("admitted-input", "client:key"), {"budget_policy": "local_cpu_research_v1"})),
    (["status", "a" * 32], ("status", ("a" * 32,), {})),
    (["cancel", "a" * 32, "--reason", "operator request"],
     ("cancel", ("a" * 32,), {"reason": "operator request"})),
    (["resume", "a" * 32], ("resume", ("a" * 32,), {})),
    (["artifacts", "a" * 32], ("artifacts", ("a" * 32,), {})),
])
def test_product_command_delegates_only_declared_inputs(facade, capsys, arguments, expected):
    service, constructed = facade
    assert docking_cli.main(["prepared-jobs", *arguments]) == 0
    assert service.calls == [expected]
    assert constructed == [{}]
    payload = json.loads(capsys.readouterr().out)
    assert payload["qualified"] is False
    assert payload["research_only"] is True


@pytest.mark.parametrize("unsafe", [
    ["--protocol", "/private/protocol.json"], ["--run-dir", "/private/run"],
    ["--tenant-id", "other"], ["--argv", "other-program"],
    ["--env", "SECRET=value"], ["--profile", "unbounded"],
    ["--output", "/private/output"], ["--budget", "local_cpu_research_v1"],
])
def test_cli_rejects_path_environment_tenant_and_abbreviated_options(facade, capsys, unsafe):
    service, constructed = facade
    assert docking_cli.main([
        "prepared-jobs", "submit", "admitted", "--idempotency-key", "key", *unsafe,
    ]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.err)["error"]["code"] == "INVALID_ARGUMENT"
    assert "/private" not in captured.err
    assert "SECRET" not in captured.err
    assert service.calls == []
    assert constructed == []


def test_cli_artifact_is_opaque_metadata_without_internal_path(facade, capsys):
    service, _ = facade
    assert prepared_lifecycle_cli.main(["artifact", "a" * 32, "b" * 32]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["artifact"]["artifact_id"] == "b" * 32
    assert "/private" not in captured.out
    assert service.calls == [("artifact", ("a" * 32, "b" * 32), {})]


def test_cli_preserves_typed_unknown_resume_refusal(facade, monkeypatch, capsys):
    from betelgeuze_product.prepared_lifecycle import LifecycleError

    service, _ = facade

    def refused(execution_id):
        raise LifecycleError("UNKNOWN_WORK", "Unknown work cannot be resumed", http_status=409)

    monkeypatch.setattr(service, "resume", refused)
    assert prepared_lifecycle_cli.main(["resume", "a" * 32]) == 2
    error = json.loads(capsys.readouterr().err)["error"]
    assert error == {
        "code": "UNKNOWN_WORK", "message": "Unknown work cannot be resumed", "retry_allowed": False,
    }


def test_cli_unexpected_failure_is_sanitized(facade, monkeypatch, capsys):
    service, _ = facade

    def failed(execution_id):
        raise RuntimeError("private /secret/root token=credential")

    monkeypatch.setattr(service, "status", failed)
    assert prepared_lifecycle_cli.main(["status", "a" * 32]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.err)["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in captured.err
    assert "credential" not in captured.err


def test_cli_owner_once_uses_fixed_owner_and_reports_idle(facade, monkeypatch, capsys):
    service, _ = facade
    calls = []

    def run_one(actual):
        calls.append(actual)
        return None

    owner = types.ModuleType("betelgeuze_product.prepared_lifecycle_owner")
    owner.run_one = run_one
    monkeypatch.setitem(sys.modules, owner.__name__, owner)
    assert prepared_lifecycle_cli.main(["owner-once"]) == 0
    assert calls == [service]
    assert json.loads(capsys.readouterr().out) == {
        "status": "idle", "qualified": False, "research_only": True,
    }


def test_cli_owner_uses_only_trusted_configured_nonlocal_tenant(monkeypatch, tmp_path, capsys):
    inputs = tmp_path / "inputs"
    inputs.mkdir(mode=0o700)
    monkeypatch.setenv("BETELGEUZE_PREPARED_LIFECYCLE_ENABLED", "1")
    monkeypatch.setenv("BETELGEUZE_PREPARED_LIFECYCLE_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("BETELGEUZE_PREPARED_LIFECYCLE_INPUT_ROOT", str(inputs))
    monkeypatch.setenv("BETELGEUZE_PREPARED_LIFECYCLE_TENANT_ID", "trusted:nonlocal")
    seen = []
    owner = types.ModuleType("betelgeuze_product.prepared_lifecycle_owner")

    def run_one(service):
        seen.append(service.tenant_id)
        return None

    owner.run_one = run_one
    monkeypatch.setitem(sys.modules, owner.__name__, owner)
    assert docking_cli.main(["prepared-jobs", "owner-once"]) == 0
    assert seen == ["trusted:nonlocal"]
    assert json.loads(capsys.readouterr().out)["status"] == "idle"


def test_root_cli_runs_disabled_without_optional_http_dependencies():
    root = Path(__file__).resolve().parents[2]
    script = """
import builtins, sys
sys.path.insert(0, sys.argv[1])
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'fastapi', 'starlette', 'pydantic', 'api'}:
        raise AssertionError('optional HTTP dependency imported: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from betelgeuze_product.docking_cli import main
raise SystemExit(main(['prepared-jobs', 'status', 'a' * 32]))
"""
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith("BETELGEUZE_PREPARED_LIFECYCLE_")
    }
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(root)], env=environment,
        capture_output=True, text=True, check=False, timeout=20,
    )
    assert result.returncode == 2, result.stderr
    assert json.loads(result.stderr)["error"]["code"] == "LIFECYCLE_DISABLED"
    assert "Traceback" not in result.stderr
