#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bundle_name(run_root: Path) -> str:
    name = run_root.name
    prefix = "external_validation_blind_runs_"
    return name[len(prefix):] if name.startswith(prefix) else name


def _proc_lines(tag: str) -> list[str]:
    if not tag.strip():
        return []
    try:
        out = subprocess.check_output(["pgrep", "-af", tag], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []
    rows: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if "pgrep -af" in line:
            continue
        if "monitor_biorxiv_external_validation.py" in line:
            continue
        if "recover_biorxiv_external_validation.py" in line:
            continue
        rows.append(line)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# bioRxiv External Validation Recovery Plan",
        "",
        f"- run_root: `{payload['run_root']}`",
        f"- tag: `{payload['tag']}`",
        f"- status_before: `{payload['status_before']}`",
        f"- effective_status: `{payload['effective_status']}`",
        f"- phase_before: `{payload['phase_before']}`",
        f"- summary_exists: `{payload['summary_exists']}`",
        f"- package_exists: `{payload['package_exists']}`",
        "",
        "## Suggested Actions",
        "",
    ]
    for action in payload.get("suggested_actions", []):
        lines.append(f"- `{action}`")
    for key in ["resume_cmd", "partial_package_cmd", "final_package_cmd", "audit_cmd"]:
        cmd = payload.get(key)
        if isinstance(cmd, list) and cmd:
            lines.extend(["", f"## {key}", "", "```bash", " ".join(str(x) for x in cmd), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _derive_plan(run_root: Path) -> dict[str, Any]:
    status_json = run_root / "oneshot_status.json"
    status = _read_json(status_json) if status_json.exists() else {}
    tag = str(status.get("tag") or _bundle_name(run_root)).strip()
    status_before = str(status.get("status", "missing_status")).strip() or "missing_status"
    phase_before = str(status.get("phase", "")).strip()
    summary_exists = (run_root / "summary.json").exists()
    package_root = ROOT / "runs" / f"biorxiv_external_validation_package_{tag}"
    package_exists = package_root.exists()
    proc_lines = _proc_lines(tag)
    effective_status = status_before
    if effective_status == "running" and not proc_lines:
        effective_status = "stale"
    elif summary_exists and effective_status == "running":
        effective_status = "completed_unfinalized"

    resume_cmd = [
        sys.executable,
        str(ROOT / "tools/resume_biorxiv_external_validation.py"),
        "--run-root",
        str(run_root),
    ]
    partial_package_cmd = [
        sys.executable,
        str(ROOT / "tools/build_biorxiv_external_validation_package.py"),
        "--run-root",
        str(run_root),
        "--allow-partial",
    ]
    final_package_cmd = [
        sys.executable,
        str(ROOT / "tools/build_biorxiv_external_validation_package.py"),
        "--run-root",
        str(run_root),
    ]
    audit_cmd = [
        sys.executable,
        str(ROOT / "tools/audit_biorxiv_external_validation_package.py"),
        "--package-root",
        str(package_root),
    ]

    suggested: list[str] = []
    if effective_status in {"stale", "failed"} and not summary_exists:
        if package_exists:
            suggested.append("audit_existing_partial_package")
        else:
            suggested.append("build_partial_package")
        suggested.append("resume_validation")
    elif effective_status == "failed_validation_packaged":
        suggested.extend(["audit_existing_partial_package", "resume_validation"])
    elif summary_exists and not package_exists:
        suggested.append("build_final_package")
    elif summary_exists and package_exists:
        suggested.append("audit_existing_package")
    elif effective_status == "running":
        suggested.append("wait_for_validation")
    else:
        suggested.append("inspect_run_root")

    return {
        "run_root": str(run_root.resolve()),
        "tag": tag,
        "status_before": status_before,
        "effective_status": effective_status,
        "phase_before": phase_before,
        "summary_exists": summary_exists,
        "package_exists": package_exists,
        "matching_processes": proc_lines,
        "suggested_actions": suggested,
        "resume_cmd": resume_cmd,
        "partial_package_cmd": partial_package_cmd,
        "final_package_cmd": final_package_cmd,
        "audit_cmd": audit_cmd,
        "package_root": str(package_root.resolve()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Plan or execute recovery steps for a stale/failed bioRxiv external validation run.")
    ap.add_argument("--run-root", required=True)
    ap.add_argument("--build-partial", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--resume", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--audit", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--out-json", default="")
    ap.add_argument("--out-md", default="")
    args = ap.parse_args()

    run_root = Path(args.run_root).resolve() if Path(args.run_root).is_absolute() else (ROOT / args.run_root).resolve()
    plan = _derive_plan(run_root)
    out_json = Path(args.out_json).resolve() if args.out_json else run_root / "recovery_plan.json"
    out_md = Path(args.out_md).resolve() if args.out_md else run_root / "recovery_plan.md"
    _write_json(out_json, plan)
    _write_md(out_md, plan)

    returncodes: dict[str, int] = {}
    if args.build_partial:
        p = subprocess.run(plan["partial_package_cmd"], cwd=str(ROOT))
        returncodes["build_partial"] = int(p.returncode)
    if args.resume:
        p = subprocess.run(plan["resume_cmd"], cwd=str(ROOT))
        returncodes["resume"] = int(p.returncode)
    if args.audit:
        p = subprocess.run(plan["audit_cmd"], cwd=str(ROOT))
        returncodes["audit"] = int(p.returncode)

    if returncodes:
        plan["executed_returncodes"] = returncodes
        _write_json(out_json, plan)
        _write_md(out_md, plan)
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return max(returncodes.values())

    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
