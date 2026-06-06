#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.api_dependency import build_cameo_api_dependency_readiness
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REQUIREMENTS = "requirements-api.txt"
DEFAULT_OUT_JSON = "runs/cameo_api_dependency_readiness_current.json"
DEFAULT_OUT_CSV = "runs/cameo_api_dependency_readiness_current.csv"
DEFAULT_OUT_MD = "runs/cameo_api_dependency_readiness_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO API Dependency Readiness",
        "",
        f"- status: `{s['status']}`",
        f"- declared_dependency_count: `{s['declared_dependency_count']}`",
        f"- runtime_extra_count: `{s['runtime_extra_count']}`",
        f"- pass_count: `{s['pass_count']}`",
        f"- missing_or_unimportable_count: `{s['missing_or_unimportable_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- package_install_executed: `{s['package_install_executed']}`",
        f"- server_started: `{s['server_started']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Dependencies",
        "",
        "| requirement | import | status | installed_version | hint |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['display_name']}` | `{row['import_name']}` | `{row['status']}` | "
            f"`{row['installed_version']}` | {row['install_or_activate_hint']} |"
        )
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
    parser = argparse.ArgumentParser(description="Build CAMEO API dependency readiness without installing packages.")
    parser.add_argument("--requirements-api", default=DEFAULT_REQUIREMENTS)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cameo_api_dependency_readiness(requirements_path=args.requirements_api, root=args.root)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
