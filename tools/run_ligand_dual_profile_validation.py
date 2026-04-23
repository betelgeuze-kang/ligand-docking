#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _run(cmd: List[str], env: Dict[str, str]) -> Dict[str, Any]:
    p = subprocess.run(cmd, text=True, capture_output=True, env=env)
    return {
        "ok": bool(p.returncode == 0),
        "returncode": int(p.returncode),
        "cmd": cmd,
        "cmd_str": " ".join(cmd),
        "stdout_tail": "\n".join((p.stdout or "").splitlines()[-80:]),
        "stderr_tail": "\n".join((p.stderr or "").splitlines()[-80:]),
    }


def _read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    return obj if isinstance(obj, dict) else {}


def _run_profile(
    profile_json: str,
    name: str,
    ligand_sizes: str,
    repeats: int,
    date_tag: str,
    out_prefix: str,
    fail_fast: bool,
    env: Dict[str, str],
) -> Dict[str, Any]:
    run_prefix = f"{out_prefix}_{name}"
    run_tag = f"{date_tag}_{name}"
    cmd = [
        sys.executable,
        "tools/run_ligand_stress_validation.py",
        "--profile-json",
        profile_json,
        "--ligand-sizes",
        str(ligand_sizes),
        "--repeats",
        str(int(max(repeats, 1))),
        "--date-tag",
        run_tag,
        "--out-prefix",
        run_prefix,
        "--fail-fast" if bool(fail_fast) else "--no-fail-fast",
    ]
    rec = _run(cmd, env=env)
    summary_json = f"{run_prefix}_summary.json"
    summary = _read_json(summary_json)
    return {
        "name": name,
        "profile_json": profile_json,
        "command": rec,
        "summary_json": summary_json,
        "pass": bool(summary.get("pass", False)),
        "summary": summary,
    }


def run_dual(args: argparse.Namespace) -> Dict[str, Any]:
    strict_profile = str(args.strict_profile_json).strip()
    operational_profile = str(args.operational_profile_json).strip()
    for p in [strict_profile, operational_profile]:
        if (not p) or (not os.path.exists(p)):
            raise FileNotFoundError(f"profile json not found: {p}")

    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    out_prefix = str(args.out_prefix).strip() or f"runs/ligand_dual_profile_validation_{date_tag}"
    _ensure_parent(f"{out_prefix}_summary.json")

    env = dict(os.environ)
    env.setdefault("FORCE_RUST_HIP", "1")
    env.setdefault("RUST_HIP_USE_GPU_NBLIST_BUILDER", "1")

    strict = _run_profile(
        profile_json=strict_profile,
        name="strict",
        ligand_sizes=str(args.ligand_sizes),
        repeats=int(args.repeats),
        date_tag=date_tag,
        out_prefix=out_prefix,
        fail_fast=bool(args.fail_fast),
        env=env,
    )
    operational = _run_profile(
        profile_json=operational_profile,
        name="operational",
        ligand_sizes=str(args.ligand_sizes),
        repeats=int(args.repeats),
        date_tag=date_tag,
        out_prefix=out_prefix,
        fail_fast=bool(args.fail_fast),
        env=env,
    )

    passed = bool(strict.get("pass", False) and operational.get("pass", False))
    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "pass": passed,
        "ligand_sizes": str(args.ligand_sizes),
        "repeats": int(args.repeats),
        "profiles": {
            "strict": strict,
            "operational": operational,
        },
        "artifacts": {
            "summary_json": f"{out_prefix}_summary.json",
            "summary_md": f"{out_prefix}_summary.md",
            "strict_summary_json": strict.get("summary_json"),
            "operational_summary_json": operational.get("summary_json"),
        },
    }

    out_json = f"{out_prefix}_summary.json"
    out_md = f"{out_prefix}_summary.md"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    lines = [
        "# Ligand Dual-Profile Validation",
        "",
        f"- generated_at_local: {payload['generated_at_local']}",
        f"- pass: {payload['pass']}",
        f"- ligand_sizes: {payload['ligand_sizes']}",
        f"- repeats: {payload['repeats']}",
        f"- strict_profile: `{strict_profile}`",
        f"- strict_pass: {bool(strict.get('pass', False))}",
        f"- strict_summary_json: `{strict.get('summary_json', '')}`",
        f"- operational_profile: `{operational_profile}`",
        f"- operational_pass: {bool(operational.get('pass', False))}",
        f"- operational_summary_json: `{operational.get('summary_json', '')}`",
        "",
        "## Failures",
        f"- strict_rc: {int((strict.get('command') or {}).get('returncode', -1))}",
        f"- operational_rc: {int((operational.get('command') or {}).get('returncode', -1))}",
    ]
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(description="Run strict + operational ligand stress validation profiles sequentially.")
    p.add_argument(
        "--strict-profile-json",
        type=str,
        default="config/ligand_htvs_commercial_validation_disjoint_strict_v1.json",
    )
    p.add_argument(
        "--operational-profile-json",
        type=str,
        default="config/ligand_htvs_commercial_validation_operational_relaxed_v1.json",
    )
    p.add_argument("--ligand-sizes", type=str, default="64,1000,5000,10000")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--date-tag", type=str, default=stamp)
    p.add_argument("--out-prefix", type=str, default=f"runs/ligand_dual_profile_validation_{stamp}")
    p.add_argument("--fail-fast", action=argparse.BooleanOptionalAction, default=False)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_dual(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not bool(payload.get("pass", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
