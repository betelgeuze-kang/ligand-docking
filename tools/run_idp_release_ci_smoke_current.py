#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ROOT = "/home/betelgeuze/분자동역학"
DEFAULT_PYTEST_TARGETS = [
    "tests/unit/test_idp_3bead_holdout_pipeline.py",
    "tests/unit/test_run_idp_3bead_release_smoke.py",
    "tests/unit/test_run_idp_3bead_release_smoke_current.py",
    "tests/unit/test_idp_branch_gate.py",
]


def _run(cmd: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "cmd": cmd,
        "rc": int(proc.returncode),
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-40:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-40:]),
    }


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _split_extra(raw: str) -> List[str]:
    return [x for x in str(raw).split() if x]


def run_ci_smoke(args: argparse.Namespace) -> Dict[str, Any]:
    out_json = str(args.out_json).strip() or f"runs/idp_3bead_release_ci_smoke_current_{dt.date.today().isoformat()}.json"
    out_md = str(args.out_md).strip() or (
        out_json[:-5] + ".md" if out_json.endswith(".json") else out_json + ".md"
    )
    smoke_tag = str(args.smoke_tag).strip() or "ci"
    smoke_out_prefix = str(args.smoke_out_prefix).strip()
    if not smoke_out_prefix:
        smoke_out_prefix = f"runs/idp_3bead_release_smoke_current_{dt.date.today().isoformat()}_{smoke_tag}"

    payload: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "pytest_targets": list(DEFAULT_PYTEST_TARGETS),
        "smoke_out_prefix": smoke_out_prefix,
        "pass": False,
    }

    if not bool(args.skip_pytest):
        pytest_cmd = [sys.executable, "-m", "pytest", "-q", *DEFAULT_PYTEST_TARGETS, *_split_extra(args.pytest_extra_args)]
        payload["pytest"] = _run(pytest_cmd)
        if payload["pytest"]["rc"] != 0 and not bool(args.allow_smoke_after_pytest_failure):
            payload["pass"] = False
            _write_json(out_json, payload)
            Path(out_md).write_text(
                "\n".join(
                    [
                        "# IDP Release CI Smoke",
                        "",
                        f"- pass: {payload['pass']}",
                        f"- pytest_rc: {payload['pytest']['rc']}",
                        f"- smoke_out_prefix: `{smoke_out_prefix}`",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            return payload

    if not bool(args.skip_smoke):
        smoke_cmd = [
            sys.executable,
            "tools/run_idp_3bead_release_smoke_current.py",
            "--release-manifest-current-json",
            str(args.release_manifest_current_json),
            "--smoke-current-json",
            str(args.smoke_current_json),
            "--config-json",
            str(args.config_json),
            "--device",
            str(args.device),
            "--out-prefix",
            smoke_out_prefix,
            "--tag",
            smoke_tag,
        ]
        if str(args.holdouts).strip():
            smoke_cmd.extend(["--holdouts", str(args.holdouts).strip()])
        payload["smoke"] = _run(smoke_cmd)
        runner_json = f"{smoke_out_prefix}_runner.json"
        if Path(runner_json).exists():
            payload["smoke_runner_json"] = runner_json
            payload["smoke_runner"] = _load_json(runner_json)

    pytest_ok = True
    if "pytest" in payload:
        pytest_ok = payload["pytest"]["rc"] == 0
    smoke_ok = True
    if "smoke" in payload:
        smoke_ok = payload["smoke"]["rc"] == 0 and bool((payload.get("smoke_runner") or {}).get("pass", False))

    payload["pass"] = bool(pytest_ok and smoke_ok)
    _write_json(out_json, payload)
    Path(out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(out_md).write_text(
        "\n".join(
            [
                "# IDP Release CI Smoke",
                "",
                f"- pass: {payload['pass']}",
                f"- smoke_out_prefix: `{smoke_out_prefix}`",
                f"- pytest_rc: `{payload.get('pytest', {}).get('rc', 'skipped')}`",
                f"- smoke_rc: `{payload.get('smoke', {}).get('rc', 'skipped')}`",
                f"- smoke_runner_json: `{payload.get('smoke_runner_json', '')}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run local IDP release safety checks: current unit tests plus current smoke regression.")
    p.add_argument("--release-manifest-current-json", type=str, default="runs/idp_3bead_release_manifest_current.json")
    p.add_argument("--smoke-current-json", type=str, default="runs/idp_3bead_release_smoke_current.json")
    p.add_argument("--config-json", type=str, default="config/idp_3bead_benchmark_v7.json")
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--holdouts", type=str, default="")
    p.add_argument("--smoke-tag", type=str, default="ci")
    p.add_argument("--smoke-out-prefix", type=str, default="")
    p.add_argument("--pytest-extra-args", type=str, default="")
    p.add_argument("--allow-smoke-after-pytest-failure", action="store_true")
    p.add_argument("--skip-pytest", action="store_true")
    p.add_argument("--skip-smoke", action="store_true")
    p.add_argument("--out-json", type=str, default="")
    p.add_argument("--out-md", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_ci_smoke(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
