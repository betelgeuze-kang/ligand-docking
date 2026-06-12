#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _run_live(
    cmd: list[str],
    log_path: Path,
    heartbeat_interval_sec: float,
    on_heartbeat: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n[{dt.datetime.now().isoformat(timespec='seconds')}] CMD: {' '.join(cmd)}\n")
        log.flush()
        p = subprocess.Popen(cmd, cwd=str(ROOT), stdout=log, stderr=log, text=True)
        try:
            while True:
                rc = p.poll()
                heartbeat = {
                    "child_pid": p.pid,
                    "last_heartbeat_local": dt.datetime.now().isoformat(timespec="seconds"),
                    "stage_log": str(log_path.resolve()),
                }
                if on_heartbeat is not None:
                    on_heartbeat(heartbeat)
                if rc is not None:
                    break
                time.sleep(max(0.2, float(heartbeat_interval_sec)))
        finally:
            log.flush()
    return {"ok": rc == 0, "returncode": int(rc), "cmd": cmd, "log": str(log_path.resolve()), "pid": int(p.pid)}


def _resume_hint(run_root: Path) -> list[str]:
    return [
        sys.executable,
        str(ROOT / "tools/resume_biorxiv_external_validation.py"),
        "--run-root",
        str(run_root),
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the preregistered bioRxiv external validation sets and build the top-level submission package.")
    ap.add_argument("--tag", default=f"{dt.date.today().isoformat()}_biorxiv_current")
    ap.add_argument("--sets", default="set3_operational_smoke,set1_core_blind,set2_expanded_ood")
    ap.add_argument("--set-spec-json", default="config/external_validation_biorxiv_blind_sets_v1.json")
    ap.add_argument("--out-root", default="runs/external_validation_blind_runs")
    ap.add_argument("--package-out-root", default="runs")
    ap.add_argument("--heartbeat-interval-sec", type=float, default=5.0)
    args = ap.parse_args()
    run_root = ROOT / args.out_root / f"external_validation_blind_runs_{args.tag}"
    run_root.mkdir(parents=True, exist_ok=True)
    status_json = run_root / "oneshot_status.json"
    status_md = run_root / "oneshot_status.md"
    validation_log = run_root / "validation_stage.log"
    package_log = run_root / "package_stage.log"
    resume_cmd = _resume_hint(run_root)

    def write_status(status: str, phase: str, extra: dict | None = None) -> None:
        payload = {
            "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
            "tag": args.tag,
            "status": status,
            "phase": phase,
            "run_root": str(run_root),
            "set_spec_json": str((ROOT / args.set_spec_json).resolve()),
            "sets": [x.strip() for x in str(args.sets).split(",") if x.strip()],
            "resume_cmd": resume_cmd,
        }
        if extra:
            payload.update(extra)
        _write_json(status_json, payload)
        md_lines = [
            "# bioRxiv One-Shot Runner Status",
            "",
            f"- tag: `{args.tag}`",
            f"- status: `{status}`",
            f"- phase: `{phase}`",
            f"- run_root: `{run_root}`",
        ]
        if extra:
            for key in [
                "last_heartbeat_local",
                "child_pid",
                "validation_log",
                "package_log",
                "stage_log",
                "returncode",
                "package_root",
            ]:
                if key in extra:
                    md_lines.append(f"- {key}: `{extra[key]}`")
        md_lines.append("")
        md_lines.append("## Resume")
        md_lines.append("")
        md_lines.append("```bash")
        md_lines.append(" ".join(resume_cmd))
        md_lines.append("```")
        status_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    run_cmd = [
        sys.executable,
        str(ROOT / "tools/run_external_validation_blind_sets.py"),
        "--set-spec-json", str(args.set_spec_json),
        "--tag", str(args.tag),
        "--sets", str(args.sets),
        "--out-root", str(args.out_root),
    ]
    write_status("running", "validation", {"run_cmd": run_cmd, "validation_log": str(validation_log.resolve())})
    run_meta = _run_live(
        run_cmd,
        validation_log,
        args.heartbeat_interval_sec,
        on_heartbeat=lambda hb: write_status(
            "running",
            "validation",
            {"run_cmd": run_cmd, "validation_log": str(validation_log.resolve()), **hb},
        ),
    )
    if not run_meta["ok"]:
        pkg_cmd = [
            sys.executable,
            str(ROOT / "tools/build_biorxiv_external_validation_package.py"),
            "--run-root", str(run_root),
            "--out-root", str(args.package_out_root),
            "--set-spec-json", str(args.set_spec_json),
            "--allow-partial",
        ]
        write_status(
            "running",
            "partial_package_build",
            {
                "returncode": int(run_meta["returncode"]),
                "package_cmd": pkg_cmd,
                "package_log": str(package_log.resolve()),
                "validation_log": str(validation_log.resolve()),
            },
        )
        pkg_meta = _run_live(
            pkg_cmd,
            package_log,
            args.heartbeat_interval_sec,
            on_heartbeat=lambda hb: write_status(
                "running",
                "partial_package_build",
                {
                    "returncode": int(run_meta["returncode"]),
                    "package_cmd": pkg_cmd,
                    "package_log": str(package_log.resolve()),
                    "validation_log": str(validation_log.resolve()),
                    **hb,
                },
            ),
        )
        if pkg_meta["ok"]:
            write_status(
                "failed_validation_packaged",
                "partial_package_built",
                {
                    "returncode": int(run_meta["returncode"]),
                    "package_root": str((ROOT / args.package_out_root / f"biorxiv_external_validation_package_{args.tag}").resolve()),
                    "validation_log": str(validation_log.resolve()),
                    "package_log": str(package_log.resolve()),
                },
            )
        else:
            write_status(
                "failed",
                "validation",
                {
                    "returncode": int(run_meta["returncode"]),
                    "validation_log": str(validation_log.resolve()),
                    "package_log": str(package_log.resolve()),
                    "package_returncode": int(pkg_meta["returncode"]),
                },
            )
        raise SystemExit(int(run_meta["returncode"]))

    pkg_cmd = [
        sys.executable,
        str(ROOT / "tools/build_biorxiv_external_validation_package.py"),
        "--run-root", str(run_root),
        "--out-root", str(args.package_out_root),
        "--set-spec-json", str(args.set_spec_json),
    ]
    write_status(
        "running",
        "package_build",
        {"package_cmd": pkg_cmd, "validation_log": str(validation_log.resolve()), "package_log": str(package_log.resolve())},
    )
    pkg_meta = _run_live(
        pkg_cmd,
        package_log,
        args.heartbeat_interval_sec,
        on_heartbeat=lambda hb: write_status(
            "running",
            "package_build",
            {
                "package_cmd": pkg_cmd,
                "validation_log": str(validation_log.resolve()),
                "package_log": str(package_log.resolve()),
                **hb,
            },
        ),
    )
    if not pkg_meta["ok"]:
        write_status(
            "failed",
            "package_build",
            {
                "returncode": int(pkg_meta["returncode"]),
                "validation_log": str(validation_log.resolve()),
                "package_log": str(package_log.resolve()),
            },
        )
        raise SystemExit(int(pkg_meta["returncode"]))

    result = {
        "tag": args.tag,
        "run_root": str(run_root.resolve()),
        "package_root": str((ROOT / args.package_out_root / f"biorxiv_external_validation_package_{args.tag}").resolve()),
        "set_spec_json": str((ROOT / args.set_spec_json).resolve()),
        "validation_log": str(validation_log.resolve()),
        "package_log": str(package_log.resolve()),
    }
    write_status("completed", "done", result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
