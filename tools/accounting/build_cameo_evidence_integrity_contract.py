#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.evidence_integrity import build_cameo_evidence_integrity_contract
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OFFICIAL_RESULTS_JSON = "runs/cameo_official_results_intake_gate_current.json"
DEFAULT_ARCHITECTURE_VALIDATION_JSON = "runs/cameo_architecture_validation_contract_current.json"
DEFAULT_OPERATIONS_JSON = "runs/cameo_validation_operations_dossier_current.json"
DEFAULT_REGISTRATION_JSON = "runs/cameo_public_registration_approval_gate_current.json"
DEFAULT_OUT_JSON = "runs/cameo_evidence_integrity_contract_current.json"
DEFAULT_OUT_CSV = "runs/cameo_evidence_integrity_contract_current.csv"
DEFAULT_OUT_MD = "runs/cameo_evidence_integrity_contract_current.md"


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
        "# CAMEO Evidence Integrity Contract",
        "",
        f"- status: `{s['status']}`",
        f"- evidence_integrity_ready: `{s['evidence_integrity_ready']}`",
        f"- check_count: `{s['check_count']}`",
        f"- pass_count: `{s['pass_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- official_result_provenance_honest: `{s['official_result_provenance_honest']}`",
        f"- official_result_schema_visible: `{s['official_result_schema_visible']}`",
        f"- official_results_ready: `{s['official_results_ready']}`",
        f"- official_results_pending_honest: `{s['official_results_pending_honest']}`",
        f"- no_local_native_accuracy_substitution: `{s['no_local_native_accuracy_substitution']}`",
        f"- external_mutation_flags_clear: `{s['external_mutation_flags_clear']}`",
        f"- registration_and_email_gated: `{s['registration_and_email_gated']}`",
        f"- local_protocol_connected: `{s['local_protocol_connected']}`",
        f"- operator_intake_csv: `{s['operator_intake_csv']}`",
        f"- missing_required_columns: `{';'.join(s['missing_required_columns'])}`",
        f"- official_results_fetched: `{s['official_results_fetched']}`",
        f"- native_local_accuracy_used: `{s['native_local_accuracy_used']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | artifact | reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | "
            f"`{row['artifact_path']}` | {row['reason']} |"
        )
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the read-only CAMEO evidence integrity contract.")
    parser.add_argument("--official-results-json", default=DEFAULT_OFFICIAL_RESULTS_JSON)
    parser.add_argument("--architecture-validation-json", default=DEFAULT_ARCHITECTURE_VALIDATION_JSON)
    parser.add_argument("--operations-json", default=DEFAULT_OPERATIONS_JSON)
    parser.add_argument("--registration-json", default=DEFAULT_REGISTRATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cameo_evidence_integrity_contract(
        official_results_packet=_read_json_if_present(args.official_results_json),
        architecture_validation_packet=_read_json_if_present(args.architecture_validation_json),
        operations_packet=_read_json_if_present(args.operations_json),
        registration_packet=_read_json_if_present(args.registration_json),
        official_results_path=args.official_results_json,
        architecture_validation_path=args.architecture_validation_json,
        operations_path=args.operations_json,
        registration_path=args.registration_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
