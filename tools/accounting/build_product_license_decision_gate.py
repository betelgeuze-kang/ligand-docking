#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.license_decision import APPROVAL_TOKEN, DECISION_CREATE_LICENSE, build_product_license_decision_gate
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMMERCIAL_INDEPENDENCE_JSON = "runs/product_commercial_independence_gate_current.json"
DEFAULT_OPERATOR_INTAKE_CSV = "runs/product_license_decision_operator_intake.csv"
DEFAULT_TEMPLATE_CSV = "runs/product_license_decision_operator_template_current.csv"
DEFAULT_OUT_JSON = "runs/product_license_decision_gate_current.json"
DEFAULT_OUT_CSV = "runs/product_license_decision_gate_current.csv"
DEFAULT_OUT_MD = "runs/product_license_decision_gate_current.md"


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


def _write_template(path_like: str | Path) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "decision,approval_token_required,approval_token,spdx_license_id,license_text_source,copyright_holder,effective_year,notes",
        (
            f"{DECISION_CREATE_LICENSE},{APPROVAL_TOKEN},,"
            "OPERATOR_FILL_SPDX,OPERATOR_FILL_LICENSE_TEXT_SOURCE,OPERATOR_FILL_HOLDER,OPERATOR_FILL_YEAR,"
            "operator must paste exact approval_token before creating LICENSE"
        ),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product License Decision Gate",
        "",
        f"- status: `{s['status']}`",
        f"- authorized_for_license_file_creation_review: `{s['authorized_for_license_file_creation_review']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- operator_intake_csv_present: `{s['operator_intake_csv_present']}`",
        f"- operator_decision: `{s['operator_decision']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- approval_token_valid: `{s['approval_token_valid']}`",
        f"- spdx_license_id: `{s['spdx_license_id']}`",
        f"- missing_required_field_count: `{s['missing_required_field_count']}`",
        f"- license_present: `{s['license_present']}`",
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
    parser = argparse.ArgumentParser(description="Build a product license decision gate without writing a LICENSE file.")
    parser.add_argument("--commercial-independence-json", default=DEFAULT_COMMERCIAL_INDEPENDENCE_JSON)
    parser.add_argument("--operator-intake-csv", default=DEFAULT_OPERATOR_INTAKE_CSV)
    parser.add_argument("--template-csv", default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_license_decision_gate(
        commercial_independence_gate_packet=_read_json_if_present(args.commercial_independence_json),
        operator_intake_csv=_resolve(args.operator_intake_csv),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)
    _write_template(args.template_csv)


if __name__ == "__main__":
    main()
