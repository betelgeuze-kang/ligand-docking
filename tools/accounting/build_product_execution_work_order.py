#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.htvs_command import build_htvs_command_from_profile_json
from betelgeuze_product.work_order import build_product_execution_work_order
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_READINESS_JSON = "runs/product_readiness_gate_current.json"
DEFAULT_OUT_JSON = "runs/product_execution_work_order_current.json"
DEFAULT_OUT_CSV = "runs/product_execution_work_order_current.csv"
DEFAULT_OUT_MD = "runs/product_execution_work_order_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Execution Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- family: `{s['family']}`",
        f"- ligand_count: `{s['ligand_count']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- docking_results_emitted: `{s['docking_results_emitted']}`",
        f"- bundle_assembled: `{s['bundle_assembled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Commands",
        "",
        "| step | command |",
        "| --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['step']}` | `{row['command']}` |")
    lines.extend(["", "## Blockers", ""])
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a product execution work order from a product readiness gate.")
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--run-command", default="")
    parser.add_argument("--profile-json", default="")
    parser.add_argument("--profile-out-prefix", default="")
    parser.add_argument("--config-path", action="append", dest="config_paths", default=[])
    parser.add_argument("--planned-artifact-path", action="append", dest="planned_artifact_paths", default=[])
    parser.add_argument("--bundle-tag", default="")
    parser.add_argument("--out-dir", default="runs/local_delivery")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    command_generation: dict[str, Any] = {}
    run_command = args.run_command
    config_paths = list(args.config_paths or [])
    if args.profile_json:
        profile_path = str(args.profile_json)
        command_generation = build_htvs_command_from_profile_json(
            _resolve(profile_path),
            out_prefix=str(args.profile_out_prefix or ""),
        )
        command_generation["profile_json"] = profile_path
        if not run_command:
            run_command = str(command_generation.get("command") or "")
        if profile_path not in config_paths:
            config_paths.append(profile_path)
    payload = build_product_execution_work_order(
        _read_json(args.readiness_json),
        run_command=run_command,
        config_paths=config_paths,
        planned_artifact_paths=args.planned_artifact_paths,
        command_generation=command_generation,
        bundle_tag=args.bundle_tag,
        out_dir=args.out_dir,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
