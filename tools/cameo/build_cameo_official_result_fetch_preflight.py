#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.official_result_fetch_preflight import build_official_result_fetch_preflight
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPERATIONS_DOSSIER_JSON = "runs/cameo_validation_operations_dossier_current.json"
DEFAULT_OPERATOR_FETCH_CSV = "runs/cameo_official_result_fetch_operator_approval_intake.csv"
DEFAULT_TEMPLATE_CSV = "runs/cameo_official_result_fetch_operator_approval_template_current.csv"
DEFAULT_OUT_JSON = "runs/cameo_official_result_fetch_preflight_current.json"
DEFAULT_OUT_CSV = "runs/cameo_official_result_fetch_preflight_current.csv"
DEFAULT_OUT_MD = "runs/cameo_official_result_fetch_preflight_current.md"


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


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_template(path_like: str | Path, target_id: str = "") -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "operator_decision",
        "fetch_approval_token",
        "result_source_url",
        "result_record_id",
        "expected_candidate_id",
        "expected_cameo_model_rank",
        "operator_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "target_id": target_id,
                "operator_decision": "",
                "fetch_approval_token": "",
                "result_source_url": "",
                "result_record_id": "",
                "expected_candidate_id": "",
                "expected_cameo_model_rank": "1",
                "operator_note": "",
            }
        )


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Official Result Fetch Preflight",
        "",
        f"- status: `{s['status']}`",
        f"- operations_surface_ready: `{s['operations_surface_ready']}`",
        f"- receiver_smoke_ready: `{s['receiver_smoke_ready']}`",
        f"- operator_fetch_csv_present: `{s['operator_fetch_csv_present']}`",
        f"- authorized_for_separate_operator_fetch: `{s['authorized_for_separate_operator_fetch']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- blockers: `{';'.join(s['blockers'])}`",
        f"- network_request_opened: `{s['network_request_opened']}`",
        f"- official_results_fetched: `{s['official_results_fetched']}`",
        f"- native_local_accuracy_used: `{s['native_local_accuracy_used']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| gate_status | decision | url | record | candidate | rank | blockers |",
        "| --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['fetch_preflight_status']}` | `{row['operator_decision']}` | `{row['result_source_url_present']}` | "
            f"`{row['result_record_id_present']}` | `{row['expected_candidate_id_present']}` | "
            f"`{row['expected_cameo_model_rank']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate CAMEO official-result fetch readiness without network access.")
    parser.add_argument("--operations-dossier-json", default=DEFAULT_OPERATIONS_DOSSIER_JSON)
    parser.add_argument("--operator-fetch-csv", default=DEFAULT_OPERATOR_FETCH_CSV)
    parser.add_argument("--template-csv", default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    operations = _read_json_if_present(args.operations_dossier_json)
    operator_path = _resolve(args.operator_fetch_csv)
    payload = build_official_result_fetch_preflight(
        operations_dossier_packet=operations,
        operator_fetch_rows=_read_csv_rows(args.operator_fetch_csv),
        operator_fetch_csv_present=operator_path.exists(),
        operator_fetch_csv=args.operator_fetch_csv,
        template_csv=args.template_csv,
    )
    _write_template(args.template_csv, _text(_summary(operations).get("target_id")))
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
