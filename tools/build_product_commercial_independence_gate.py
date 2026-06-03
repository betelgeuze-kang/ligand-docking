#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.commercial_independence import build_product_commercial_independence_gate
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/product_commercial_independence_gate_current.json"
DEFAULT_OUT_CSV = "runs/product_commercial_independence_gate_current.csv"
DEFAULT_OUT_MD = "runs/product_commercial_independence_gate_current.md"


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
        "# Product Commercial Independence Gate",
        "",
        f"- status: `{s['status']}`",
        f"- commercial_independent_product_claim_allowed: `{s['commercial_independent_product_claim_allowed']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- check_count: `{s['check_count']}`",
        f"- license_present: `{s['license_present']}`",
        f"- runtime_requirements_present: `{s['runtime_requirements_present']}`",
        f"- loose_runtime_dependency_count: `{s['loose_runtime_dependency_count']}`",
        f"- dependency_provenance_manifest_present: `{s['dependency_provenance_manifest_present']}`",
        f"- dependency_provenance_git_short_commit: `{s['dependency_provenance_git_short_commit']}`",
        f"- dependency_provenance_requirements_lock_txt_sha256: `{s['dependency_provenance_requirements_lock_txt_sha256']}`",
        f"- requirements_lock_artifacts_present: `{s['requirements_lock_artifacts_present']}`",
        f"- requirements_lock_complete: `{s['requirements_lock_complete']}`",
        f"- reproducible_install_manifest_ready: `{s['reproducible_install_manifest_ready']}`",
        f"- external_api_runtime_dependency_count: `{s['external_api_runtime_dependency_count']}`",
        f"- optional_profiles_separated: `{s['optional_profiles_separated']}`",
        f"- deployment_manifest_present: `{s['deployment_manifest_present']}`",
        f"- pyproject_packaging_metadata_present: `{s['pyproject_packaging_metadata_present']}`",
        f"- package_discovery_present: `{s['package_discovery_present']}`",
        f"- console_entrypoint_targets_present: `{s['console_entrypoint_targets_present']}`",
        f"- core_product_surface_present: `{s['core_product_surface_present']}`",
        f"- product_cli_surface_present: `{s['product_cli_surface_present']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- docking_results_emitted: `{s['docking_results_emitted']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | artifact | reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | "
            f"`{row['required']}` | `{row['artifact_path']}` | {row['reason']} |"
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
    parser = argparse.ArgumentParser(description="Build a commercial independent-product packaging gate without installing packages.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--environment-manifest-json", default="runs/local_delivery_environment_manifest_current.json")
    parser.add_argument("--requirements-lock-json", default="runs/local_delivery_requirements_lock_current.json")
    parser.add_argument("--requirements-lock-md", default="runs/local_delivery_requirements_lock_current.md")
    parser.add_argument("--requirements-lock-txt", default="runs/local_delivery_requirements_lock_current.txt")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_commercial_independence_gate(
        root=args.root,
        environment_manifest_json=args.environment_manifest_json,
        requirements_lock_json=args.requirements_lock_json,
        requirements_lock_md=args.requirements_lock_md,
        requirements_lock_txt=args.requirements_lock_txt,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
