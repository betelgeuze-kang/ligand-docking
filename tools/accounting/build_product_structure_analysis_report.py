#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.structure_report import build_product_structure_analysis_report
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TARGET_NATIVE_CSV = "config/real_drug_targets_blind_gpcr_adrb2_v1.csv"
DEFAULT_TARGET_KEY = "ADRB2_GPCR_BLIND"
DEFAULT_TARGET_ID = "ADRB2"
DEFAULT_FAMILY = "gpcr"
DEFAULT_OUT_JSON = "runs/product_structure_analysis_report_current.json"
DEFAULT_OUT_CSV = "runs/product_structure_analysis_report_current.csv"
DEFAULT_OUT_MD = "runs/product_structure_analysis_report_current.md"


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
        "# Product Structure Analysis Report",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- target_key: `{s['target_key']}`",
        f"- family: `{s['family']}`",
        f"- target_native_csv: `{s['target_native_csv']}`",
        f"- structure_path: `{s['structure_path']}`",
        f"- pdb_id: `{s['pdb_id']}`",
        f"- atom_count: `{s['atom_count']}`",
        f"- chain_count: `{s['chain_count']}`",
        f"- residue_count: `{s['residue_count']}`",
        f"- ligand_like_residue_count: `{s['ligand_like_residue_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- docking_results_emitted: `{s['docking_results_emitted']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | artifact |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | "
            f"`{row['required']}` | `{row['artifact_path']}` |"
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
    parser = argparse.ArgumentParser(description="Build a local product structure-analysis report from target-native evidence.")
    parser.add_argument("--target-native-csv", default=DEFAULT_TARGET_NATIVE_CSV)
    parser.add_argument("--target-key", default=DEFAULT_TARGET_KEY)
    parser.add_argument("--target-id", default=DEFAULT_TARGET_ID)
    parser.add_argument("--family", default=DEFAULT_FAMILY)
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_structure_analysis_report(
        target_native_csv=args.target_native_csv,
        target_key=args.target_key,
        target_id=args.target_id,
        family=args.family,
        root=args.root,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
