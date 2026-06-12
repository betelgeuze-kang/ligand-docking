#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _short_path(path_str: str) -> str:
    p = Path(path_str).resolve()
    try:
        return str(p.relative_to(ROOT))
    except Exception:
        return str(p)


def _bundle_name(run_root: Path) -> str:
    name = run_root.name
    prefix = "external_validation_blind_runs_"
    return name[len(prefix):] if name.startswith(prefix) else name


def _derive_resume_payload(run_root: Path) -> dict[str, Any]:
    status_json = run_root / "oneshot_status.json"
    provenance_json = run_root / "provenance.json"
    state_json = run_root / "state.json"
    if not status_json.exists():
        raise FileNotFoundError(status_json)

    status = _read_json(status_json)
    provenance = _read_json(provenance_json) if provenance_json.exists() else {}
    state = _read_json(state_json) if state_json.exists() else {}

    tag = str(status.get("tag") or _bundle_name(run_root)).strip()
    if not tag:
        raise ValueError(f"could not derive tag from {run_root}")

    sets = status.get("sets") or provenance.get("selected_sets") or []
    if not isinstance(sets, list) or not sets:
        raise ValueError(f"could not derive sets from {status_json}")

    set_spec_json = str(status.get("set_spec_json") or provenance.get("spec_json") or "").strip()
    if not set_spec_json:
        raise ValueError(f"could not derive set_spec_json from {status_json}")

    out_root = str(run_root.parent.resolve())
    try:
        out_root = str(run_root.parent.resolve().relative_to(ROOT))
    except Exception:
        pass

    package_out_root = "runs"
    if state.get("out_root"):
        try:
            out_path = Path(str(state.get("out_root"))).resolve()
            if out_path.parent == ROOT:
                package_out_root = out_path.name
        except Exception:
            pass

    cmd = [
        sys.executable,
        str(ROOT / "tools/run_biorxiv_external_validation_current.py"),
        "--tag",
        tag,
        "--sets",
        ",".join(str(x).strip() for x in sets if str(x).strip()),
        "--set-spec-json",
        _short_path(set_spec_json),
        "--out-root",
        out_root,
        "--package-out-root",
        package_out_root,
    ]
    return {
        "run_root": str(run_root.resolve()),
        "tag": tag,
        "status_before": str(status.get("status", "")),
        "phase_before": str(status.get("phase", "")),
        "sets": [str(x) for x in sets],
        "set_spec_json": _short_path(set_spec_json),
        "out_root": out_root,
        "package_out_root": package_out_root,
        "resume_cmd": cmd,
        "resume_reason": "resume stale/failed bioRxiv external validation run using frozen tag/spec/sets",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Resume a stale or failed bioRxiv external validation one-shot run.")
    ap.add_argument("--run-root", required=True)
    ap.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--force", action=argparse.BooleanOptionalAction, default=False)
    args = ap.parse_args()

    run_root = Path(args.run_root).resolve() if Path(args.run_root).is_absolute() else (ROOT / args.run_root).resolve()
    payload = _derive_resume_payload(run_root)
    status_before = payload["status_before"]
    if status_before == "completed" and not args.force:
        payload["launched"] = False
        payload["note"] = "run already completed; pass --force to rerun wrapper"
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if args.dry_run:
        payload["launched"] = False
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    p = subprocess.run(payload["resume_cmd"], cwd=str(ROOT))
    payload["launched"] = True
    payload["returncode"] = int(p.returncode)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return int(p.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
