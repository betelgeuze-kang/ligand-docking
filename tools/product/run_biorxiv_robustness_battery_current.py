#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Execute prepared robustness-battery scenarios with the scenario runner.")
    ap.add_argument("--battery-json", default="runs/biorxiv_robustness_battery_current.json")
    ap.add_argument("--scenario-ids", default="")
    ap.add_argument("--sets", default="set3_operational_smoke,set1_core_blind,set2_expanded_ood")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out-json", default="runs/biorxiv_robustness_battery_execution_current.json")
    ap.add_argument("--out-md", default="runs/biorxiv_robustness_battery_execution_current.md")
    args = ap.parse_args(argv)

    battery = _read_json((ROOT / args.battery_json).resolve())
    selected = {x.strip() for x in str(args.scenario_ids).split(",") if x.strip()}
    rows: list[dict] = []

    for row in battery.get("rows", []):
        scenario_id = str(row.get("scenario_id") or "")
        if selected and scenario_id not in selected:
            continue
        tag = f"{dt.date.today().isoformat()}_{scenario_id}"
        cmd = [
            sys.executable,
            str((ROOT / "tools/run_biorxiv_robustness_scenario.py").resolve()),
            "--scenario",
            scenario_id,
            "--tag",
            tag,
            "--sets",
            str(args.sets),
            "--set-spec-json",
            str(row.get("spec_json") or ""),
        ]
        if args.dry_run:
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "status": "dry_run",
                    "tag": tag,
                    "set_spec_json": str(row.get("spec_json") or ""),
                    "command": cmd,
                }
            )
            continue
        rc = subprocess.run(cmd, cwd=str(ROOT)).returncode
        rows.append(
            {
                "scenario_id": scenario_id,
                "status": "completed" if rc == 0 else "failed",
                "tag": tag,
                "set_spec_json": str(row.get("spec_json") or ""),
                "returncode": rc,
            }
        )
        if rc != 0:
            break

    payload = {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "battery_json": str((ROOT / args.battery_json).resolve()),
        "dry_run": bool(args.dry_run),
        "row_count": len(rows),
        "rows": rows,
    }
    out_json = (ROOT / args.out_json).resolve()
    out_md = (ROOT / args.out_md).resolve()
    _write_json(out_json, payload)

    lines = [
        "# bioRxiv Robustness Battery Execution",
        "",
        f"- dry_run: `{payload['dry_run']}`",
        f"- row_count: `{payload['row_count']}`",
        "",
        "| scenario_id | status | tag | spec_json |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('scenario_id')} | {row.get('status')} | {row.get('tag')} | {row.get('set_spec_json')} |"
        )
    _write_text(out_md, "\n".join(lines) + "\n")

    print(json.dumps({"ok": True, "out_json": str(out_json), "row_count": len(rows)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
