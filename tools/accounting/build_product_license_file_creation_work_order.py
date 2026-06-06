#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.license_file_creation import build_product_license_file_creation_work_order
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LICENSE_DECISION_JSON = "runs/product_license_decision_gate_current.json"
DEFAULT_COMMERCIAL_INDEPENDENCE_JSON = "runs/product_commercial_independence_gate_current.json"
DEFAULT_OUT_JSON = "runs/product_license_file_creation_work_order_current.json"
DEFAULT_OUT_CSV = "runs/product_license_file_creation_work_order_current.csv"
DEFAULT_OUT_MD = "runs/product_license_file_creation_work_order_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product License File Creation Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- license_file_creation_review_ready: `{s['license_file_creation_review_ready']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- target_license_path: `{s['target_license_path']}`",
        f"- spdx_license_id: `{s['spdx_license_id']}`",
        f"- license_text_source: `{s['license_text_source']}`",
        f"- license_text_source_present: `{s['license_text_source_present']}`",
        f"- license_text_source_size_bytes: `{s['license_text_source_size_bytes']}`",
        f"- license_text_source_sha256: `{s['license_text_source_sha256']}`",
        f"- license_review_manifest_ready: `{s['license_review_manifest_ready']}`",
        f"- license_review_manifest_fingerprint_sha256: `{s['license_review_manifest_fingerprint_sha256']}`",
        f"- license_file_write_command_template: `{s['license_file_write_command_template']}`",
        f"- authorized_for_license_file_creation_review: `{s['authorized_for_license_file_creation_review']}`",
        f"- commercial_gate_only_license_blocked: `{s['commercial_gate_only_license_blocked']}`",
        f"- license_file_written: `{s['license_file_written']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | {row['reason']} |")
    lines.extend(["", "## Work Items", "", "| step | status | approval | command/source |", "| --- | --- | --- | --- |"])
    for row in payload.get("work_items", []):
        lines.append(
            f"| `{row['step']}` | `{row['status']}` | `{row.get('approval_token_required', '')}` | "
            f"`{row.get('command') or row.get('license_text_source') or ''}` |"
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
    parser = argparse.ArgumentParser(description="Build a read-only product LICENSE file creation work order.")
    parser.add_argument("--license-decision-json", default=DEFAULT_LICENSE_DECISION_JSON)
    parser.add_argument("--commercial-independence-json", default=DEFAULT_COMMERCIAL_INDEPENDENCE_JSON)
    parser.add_argument("--target-license-path", default="LICENSE")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_license_file_creation_work_order(
        license_decision_gate_packet=_read_json_if_present(args.license_decision_json),
        commercial_independence_gate_packet=_read_json_if_present(args.commercial_independence_json),
        target_license_path=args.target_license_path,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
