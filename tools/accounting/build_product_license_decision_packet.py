#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.license_options import build_product_license_decision_packet
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMMERCIAL_INDEPENDENCE_JSON = "runs/product_commercial_independence_gate_current.json"
DEFAULT_LICENSE_DECISION_JSON = "runs/product_license_decision_gate_current.json"
DEFAULT_OPERATOR_TEMPLATE_CSV = "runs/product_license_decision_operator_template_current.csv"
DEFAULT_OPERATOR_INTAKE_CSV = "runs/product_license_decision_operator_intake.csv"
DEFAULT_OUT_JSON = "runs/product_license_decision_packet_current.json"
DEFAULT_OUT_CSV = "runs/product_license_decision_packet_current.csv"
DEFAULT_OUT_MD = "runs/product_license_decision_packet_current.md"


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
        "# Product License Decision Packet",
        "",
        f"- status: `{s['status']}`",
        f"- option_count: `{s['option_count']}`",
        f"- ready_local_license_text_source_candidate_count: `{s['ready_local_license_text_source_candidate_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- hard_blocker_count: `{s['hard_blocker_count']}`",
        f"- review_item_count: `{s['review_item_count']}`",
        f"- commercial_gate_only_license_blocked: `{s['commercial_gate_only_license_blocked']}`",
        f"- commercial_independence_ready: `{s['commercial_independence_ready']}`",
        f"- license_decision_gate_status: `{s['license_decision_gate_status']}`",
        f"- license_decision_gate_ready: `{s['license_decision_gate_ready']}`",
        f"- license_decision_authorized_for_file_creation_review: `{s['license_decision_authorized_for_file_creation_review']}`",
        f"- operator_intake_csv_present: `{s['operator_intake_csv_present']}`",
        f"- operator_template_csv: `{s['operator_template_csv']}`",
        f"- operator_intake_csv: `{s['operator_intake_csv']}`",
        f"- operator_intake_fill_command_template: `{s['operator_intake_fill_command_template']}`",
        f"- required_decision: `{s['required_decision']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- license_present: `{s['license_present']}`",
        f"- license_file_written: `{s['license_file_written']}`",
        f"- legal_advice_provided: `{s['legal_advice_provided']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Options",
        "",
        "| rank | SPDX id | family | commercial fit | operator review focus | text source hint | local source candidate | local source ready |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['option_rank']}` | `{row['spdx_license_id']}` | `{row['license_family']}` | "
            f"{row['commercial_distribution_fit']} | {row['operator_review_focus']} | {row['license_text_source_hint']} | "
            f"`{row['local_license_text_source_candidate'] or 'operator-provided'}` | "
            f"`{row['local_license_text_source_present'] and row['local_license_text_source_non_empty']}` |"
        )
    local_examples = [row for row in payload["rows"] if row.get("operator_intake_fill_command_local_source_example")]
    lines.extend(["", "## Local Source Command Examples", ""])
    if local_examples:
        lines.extend(
            f"- `{row['spdx_license_id']}`: `{row['operator_intake_fill_command_local_source_example']}`"
            for row in local_examples
        )
    else:
        lines.append("- none")
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only product license decision packet.")
    parser.add_argument("--commercial-independence-json", default=DEFAULT_COMMERCIAL_INDEPENDENCE_JSON)
    parser.add_argument("--license-decision-json", default=DEFAULT_LICENSE_DECISION_JSON)
    parser.add_argument("--operator-template-csv", default=DEFAULT_OPERATOR_TEMPLATE_CSV)
    parser.add_argument("--operator-intake-csv", default=DEFAULT_OPERATOR_INTAKE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_license_decision_packet(
        commercial_independence_gate_packet=_read_json_if_present(args.commercial_independence_json),
        license_decision_gate_packet=_read_json_if_present(args.license_decision_json),
        operator_template_csv=args.operator_template_csv,
        operator_intake_csv=args.operator_intake_csv,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
