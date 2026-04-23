#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from typing import Dict, List, Optional, Sequence


DEFAULT_TESTS: List[str] = [
    "tests/unit/test_speed_profile_defaults.py",
    "tests/unit/test_run_accuracy_revalidation.py",
    "tests/unit/test_run_preflight_gate.py",
    "tests/unit/test_run_initial_claim_triplet_gate.py",
    "tests/unit/test_run_nightly_screening_batch.py",
]


def _which_pytest() -> Optional[str]:
    spec = importlib.util.find_spec("pytest")
    if spec is None:
        return None
    return str(spec.origin or "pytest")


def _run_cmd(cmd: List[str]) -> Dict[str, object]:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    return {
        "cmd": list(cmd),
        "returncode": int(proc.returncode),
        "ok": bool(proc.returncode == 0),
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-80:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-80:]),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Run local unit-test CI for nightly speed/accuracy pipeline changes. "
            "Optionally installs pytest from requirements-dev.txt when missing."
        )
    )
    p.add_argument("--requirements-dev", type=str, default="requirements-dev.txt")
    p.add_argument("--install-missing", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--pytest-args", type=str, default="-q")
    p.add_argument("--out-json", type=str, default="runs/local_ci_tests_summary.json")
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--tests", nargs="*", default=list(DEFAULT_TESTS))
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    tests = [str(t).strip() for t in list(args.tests or []) if str(t).strip()]
    if not tests:
        tests = list(DEFAULT_TESTS)

    summary: Dict[str, object] = {
        "pytest_found": bool(_which_pytest() is not None),
        "install_attempted": False,
        "install_result": None,
        "tests": tests,
        "pytest_args": str(args.pytest_args),
        "dry_run": bool(args.dry_run),
    }

    install_result = None
    if (_which_pytest() is None) and bool(args.install_missing):
        summary["install_attempted"] = True
        install_cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(args.requirements_dev),
        ]
        if bool(args.dry_run):
            install_result = {"cmd": install_cmd, "returncode": 0, "ok": True, "stdout_tail": "", "stderr_tail": ""}
        else:
            install_result = _run_cmd(install_cmd)
        summary["install_result"] = install_result

    pytest_after = _which_pytest() is not None
    summary["pytest_found_after_install"] = bool(pytest_after)

    pytest_cmd = [sys.executable, "-m", "pytest"]
    pytest_args = [x for x in str(args.pytest_args).split(" ") if x]
    pytest_cmd.extend(pytest_args)
    pytest_cmd.extend(tests)
    if bool(args.dry_run):
        test_result = {"cmd": pytest_cmd, "returncode": 0, "ok": True, "stdout_tail": "", "stderr_tail": ""}
    elif not pytest_after:
        test_result = {
            "cmd": pytest_cmd,
            "returncode": 127,
            "ok": False,
            "stdout_tail": "",
            "stderr_tail": "pytest_not_found_after_install",
        }
    else:
        test_result = _run_cmd(pytest_cmd)
    summary["test_result"] = test_result
    summary["pass"] = bool(test_result.get("ok", False))

    out_json = str(args.out_json).strip()
    if out_json:
        os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

    print(
        json.dumps(
            {
                "pass": summary["pass"],
                "pytest_found_after_install": summary["pytest_found_after_install"],
                "out_json": out_json,
                "pytest_cmd": pytest_cmd,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    if not bool(summary["pass"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()

