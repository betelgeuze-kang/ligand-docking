#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_cameo.capability_preflight import build_cameo_capability_preflight
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VALIDATION_JSON = "runs/cameo_validation_readiness_gate_current.json"
DEFAULT_REPAIR_PREFLIGHT_JSON = "runs/cameo_repair_execution_preflight_current.json"
DEFAULT_RECEIVER_SMOKE_JSON = "runs/cameo_receiver_smoke_contract_current.json"
DEFAULT_OUT_JSON = "runs/cameo_capability_preflight_current.json"
DEFAULT_OUT_CSV = "runs/cameo_capability_preflight_current.csv"
DEFAULT_OUT_MD = "runs/cameo_capability_preflight_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


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


def _receiver_scaffold_present() -> bool:
    return (ROOT / "api" / "cameo.py").exists() and (ROOT / "betelgeuze_cameo" / "intake.py").exists()


def _api_route_registered() -> bool:
    main = ROOT / "api" / "main.py"
    cameo = ROOT / "api" / "cameo.py"
    if not main.exists() or not cameo.exists():
        return False
    try:
        main_text = main.read_text(encoding="utf-8")
        cameo_text = cameo.read_text(encoding="utf-8")
    except OSError:
        return False
    return "cameo" in main_text and 'prefix="/cameo"' in cameo_text and '"/targets"' in cameo_text


def _api_operations_route_registered() -> bool:
    main = ROOT / "api" / "main.py"
    cameo = ROOT / "api" / "cameo.py"
    if not main.exists() or not cameo.exists():
        return False
    try:
        main_text = main.read_text(encoding="utf-8")
        cameo_text = cameo.read_text(encoding="utf-8")
    except OSError:
        return False
    return (
        "cameo" in main_text
        and 'prefix="/cameo"' in cameo_text
        and '"/operations"' in cameo_text
        and '"/architecture-validation"' in cameo_text
        and '"/official-results"' in cameo_text
        and '"/registration-approval"' in cameo_text
        and '"/api-contract"' in cameo_text
        and '"/service-boundary"' in cameo_text
    )


def _local_status_cli_present() -> bool:
    return (ROOT / "betelgeuze_cameo" / "cli.py").exists()


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Capability Preflight",
        "",
        f"- status: `{s['status']}`",
        f"- capability_lane: `{s['capability_lane']}`",
        f"- receiver_scaffold_present: `{s['receiver_scaffold_present']}`",
        f"- api_route_registered: `{s['api_route_registered']}`",
        f"- api_operations_route_registered: `{s['api_operations_route_registered']}`",
        f"- local_status_cli_present: `{s['local_status_cli_present']}`",
        f"- source_validation_status: `{s['source_validation_status']}`",
        f"- source_repair_execution_preflight_status: `{s['source_repair_execution_preflight_status']}`",
        f"- source_receiver_smoke_status: `{s['source_receiver_smoke_status']}`",
        f"- source_api_dependency_status: `{s['source_api_dependency_status']}`",
        f"- api_dependency_ready: `{s['api_dependency_ready']}`",
        f"- api_dependency_blocker_count: `{s['api_dependency_blocker_count']}`",
        f"- receiver_smoke_post_200_ok: `{s['receiver_smoke_post_200_ok']}`",
        f"- receiver_smoke_blocker_count: `{s['receiver_smoke_blocker_count']}`",
        f"- public_registration_requested: `{s['public_registration_requested']}`",
        f"- public_registration_allowed: `{s['public_registration_allowed']}`",
        f"- public_registration_blocker_count: `{s['public_registration_blocker_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- warning_count: `{s['warning_count']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- prediction_generation_enabled: `{s['prediction_generation_enabled']}`",
        f"- server_registration_mutated: `{s['server_registration_mutated']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` |")

    lines.extend(["", "## Registration Blockers", ""])
    registration_blockers = payload.get("registration_blockers") or []
    if registration_blockers:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in registration_blockers)
    else:
        lines.append("- none")

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
    parser = argparse.ArgumentParser(description="Build a CAMEO capability preflight without registering or sending email.")
    parser.add_argument("--validation-json", default=DEFAULT_VALIDATION_JSON)
    parser.add_argument("--repair-preflight-json", default=DEFAULT_REPAIR_PREFLIGHT_JSON)
    parser.add_argument("--receiver-smoke-json", default=DEFAULT_RECEIVER_SMOKE_JSON)
    parser.add_argument("--capability-lane", default="polymer_complex_receiver_dry_run")
    parser.add_argument("--public-registration-requested", action="store_true")
    parser.add_argument("--registration-approval-token", default="")
    parser.add_argument("--outbound-email-requested", action="store_true")
    parser.add_argument("--outbound-email-approval-token", default="")
    parser.add_argument("--prediction-generation-requested", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cameo_capability_preflight(
        validation_readiness_packet=_read_json(args.validation_json),
        repair_execution_preflight_packet=_read_json(args.repair_preflight_json),
        receiver_smoke_packet=_read_json_if_present(args.receiver_smoke_json),
        receiver_scaffold_present=_receiver_scaffold_present(),
        api_route_registered=_api_route_registered(),
        api_operations_route_registered=_api_operations_route_registered(),
        local_status_cli_present=_local_status_cli_present(),
        capability_lane=args.capability_lane,
        public_registration_requested=args.public_registration_requested,
        registration_approval_token=args.registration_approval_token,
        outbound_email_requested=args.outbound_email_requested,
        outbound_email_approval_token=args.outbound_email_approval_token,
        prediction_generation_requested=args.prediction_generation_requested,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
