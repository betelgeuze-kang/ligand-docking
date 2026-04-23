#!/usr/bin/env python3

from __future__ import annotations

import json

import pytest

from tools import run_preflight_gate as preflight


def test_build_gate_argv_includes_speed_mode():
    parser = preflight.build_parser()
    args = parser.parse_args(
        [
            "--targets",
            "Chignolin",
            "--speed-mode",
            "extreme",
            "--speed-mode-replicas",
            "128",
            "--label",
            "speed_probe",
        ]
    )
    argv = preflight._build_gate_argv(args)

    assert "--speed-mode" in argv
    assert argv[argv.index("--speed-mode") + 1] == "extreme"
    assert "--speed-mode-replicas" in argv
    assert argv[argv.index("--speed-mode-replicas") + 1] == "128"


def test_preflight_dry_run_skips_gate(monkeypatch):
    called = {"count": 0}

    def _fake_run_gate(_args):
        called["count"] += 1
        return {"summary": {"pass": True}}

    monkeypatch.setattr(preflight, "run_accuracy_gate", _fake_run_gate)

    preflight.main(
        [
            "--targets",
            "Chignolin",
            "--speed-mode",
            "turbo",
            "--speed-mode-replicas",
            "64",
            "--dry-run",
        ]
    )

    assert called["count"] == 0


def test_preflight_forwards_speed_mode_to_gate(monkeypatch):
    observed = {}

    def _fake_run_gate(args):
        observed["speed_mode"] = args.speed_mode
        observed["speed_mode_replicas"] = args.speed_mode_replicas
        return {"summary": {"pass": True}}

    monkeypatch.setattr(preflight, "run_accuracy_gate", _fake_run_gate)

    preflight.main(
        [
            "--targets",
            "Chignolin",
            "--speed-mode",
            "extreme",
            "--speed-mode-replicas",
            "256",
        ]
    )

    assert observed["speed_mode"] == "extreme"
    assert observed["speed_mode_replicas"] == 256


def test_preflight_fails_on_gate_fail(monkeypatch):
    def _fake_run_gate(_args):
        return {"summary": {"pass": False}}

    monkeypatch.setattr(preflight, "run_accuracy_gate", _fake_run_gate)

    with pytest.raises(SystemExit) as exc_info:
        preflight.main(["--targets", "Chignolin"])
    assert exc_info.value.code == 2


def test_preflight_uses_speed_defaults_json(tmp_path):
    defaults = tmp_path / "speed_defaults.json"
    defaults.write_text(
        json.dumps(
            {
                "sections": {
                    "preflight": {
                        "speed_mode": "turbo",
                        "speed_mode_replicas": 64,
                        "speed_profile_max_replicas": 256,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    parser = preflight.build_parser()
    args = parser.parse_args(
        [
            "--targets",
            "Chignolin",
            "--speed-profile-defaults-json",
            str(defaults),
            "--speed-profile-defaults-section",
            "preflight",
        ]
    )
    argv = preflight._build_gate_argv(args)
    assert argv[argv.index("--speed-mode") + 1] == "turbo"
    assert argv[argv.index("--speed-mode-replicas") + 1] == "64"
    assert argv[argv.index("--speed-profile-max-replicas") + 1] == "256"
