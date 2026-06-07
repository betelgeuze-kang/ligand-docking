#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_SCOPE_JSON = RUNS / "product_scope_breadth_contract_current.json"
DEFAULT_CAPABILITY_JSON = RUNS / "product_capability_surface_contract_current.json"
DEFAULT_OUT_JSON = RUNS / "general_protein_ligand_claim_blocker_packet_current.json"
DEFAULT_OUT_CSV = RUNS / "general_protein_ligand_claim_blocker_packet_current.csv"
DEFAULT_OUT_MD = RUNS / "general_protein_ligand_claim_blocker_packet_current.md"

REQUIRED_DOMAIN_PREREQUISITES = ["transporter", "ca2", "pxr", "idp_broad", "all_atom"]
MIN_ALLOWED_SCOPE_FAMILY_COUNT = 6
CLAIM_BOUNDARY = (
    "General protein-ligand claim blocker packet only; reconciles current breadth domains, capability surface, and "
    "explicit platform flags before any broad protein-ligand platform wording. It does not widen API scope, run docking, "
    "promote claims, upload, submit, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


def _scope_rows_by_domain(scope_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("domain")): dict(row)
        for row in scope_payload.get("rows", []) or []
        if isinstance(row, dict) and _text(row.get("domain"))
    }


def build_payload(*, scope_payload: dict[str, Any], capability_payload: dict[str, Any]) -> dict[str, Any]:
    scope = _summary(scope_payload)
    capability = _summary(capability_payload)
    rows_by_domain = _scope_rows_by_domain(scope_payload)
    allowed_families = [str(item) for item in capability.get("allowed_scope_families") or scope.get("allowed_scope_families") or []]

    rows: list[dict[str, Any]] = []
    for domain in REQUIRED_DOMAIN_PREREQUISITES:
        scope_row = rows_by_domain.get(domain, {})
        ready = _text(scope_row.get("status")) == "ready"
        rows.append(
            {
                "check_id": f"domain_ready.{domain}",
                "check_type": "breadth_domain",
                "status": "ready" if ready else "blocked",
                "current_value": _text(scope_row.get("status")) or "missing",
                "required_value": "ready",
                "artifact": _text(scope_row.get("artifact")) or DEFAULT_SCOPE_JSON.as_posix(),
                "release_blocker": not ready,
                "observed": _text(scope_row.get("observed")),
                "next_action": _text(scope_row.get("next_action")) or "Make the domain ready in product scope breadth contract.",
            }
        )

    allowed_family_ready = len(allowed_families) >= MIN_ALLOWED_SCOPE_FAMILY_COUNT
    rows.append(
        {
            "check_id": "allowed_scope_family_count",
            "check_type": "api_scope",
            "status": "ready" if allowed_family_ready else "blocked",
            "current_value": str(len(allowed_families)),
            "required_value": f">={MIN_ALLOWED_SCOPE_FAMILY_COUNT}",
            "artifact": DEFAULT_CAPABILITY_JSON.as_posix(),
            "release_blocker": not allowed_family_ready,
            "observed": ",".join(allowed_families),
            "next_action": "Keep API scope restricted until the breadth domains are ready, then explicitly widen allowed scope families.",
        }
    )

    explicit_platform_flag = _bool(scope.get("general_protein_ligand_platform_ready")) or _bool(
        capability.get("general_protein_ligand_platform_ready")
    )
    rows.append(
        {
            "check_id": "explicit_general_platform_flag",
            "check_type": "product_claim_flag",
            "status": "ready" if explicit_platform_flag else "blocked",
            "current_value": str(explicit_platform_flag),
            "required_value": "True",
            "artifact": DEFAULT_SCOPE_JSON.as_posix(),
            "release_blocker": not explicit_platform_flag,
            "observed": f"scope_flag={scope.get('general_protein_ligand_platform_ready')};capability_flag={capability.get('general_protein_ligand_platform_ready')}",
            "next_action": "Add an explicit general-protein-ligand platform flag only after domain evidence and API scope are widened.",
        }
    )

    api_surface_ready = _bool(capability.get("api_surface_ready"))
    rows.append(
        {
            "check_id": "api_surface_ready",
            "check_type": "product_surface",
            "status": "ready" if api_surface_ready else "blocked",
            "current_value": str(api_surface_ready),
            "required_value": "True",
            "artifact": DEFAULT_CAPABILITY_JSON.as_posix(),
            "release_blocker": not api_surface_ready,
            "observed": f"api_surface_ready={capability.get('api_surface_ready')}",
            "next_action": "Keep product API surface contract green before any platform wording.",
        }
    )

    blocker_rows = [row for row in rows if row["release_blocker"]]
    ready_domains = [
        domain
        for domain in REQUIRED_DOMAIN_PREREQUISITES
        if _text(rows_by_domain.get(domain, {}).get("status")) == "ready"
    ]
    missing_domains = [domain for domain in REQUIRED_DOMAIN_PREREQUISITES if domain not in ready_domains]
    general_claim_allowed = not blocker_rows
    summary = {
        "packet_type": "general_protein_ligand_claim_blocker_packet",
        "claim_blocker_packet_ready": True,
        "general_protein_ligand_claim_allowed": general_claim_allowed,
        "scope_breadth_ready": scope.get("scope_breadth_ready") is True,
        "ready_domain_count": len(ready_domains),
        "required_domain_count": len(REQUIRED_DOMAIN_PREREQUISITES),
        "ready_domains": ready_domains,
        "missing_domains": missing_domains,
        "allowed_scope_family_count": len(allowed_families),
        "allowed_scope_families": allowed_families,
        "min_allowed_scope_family_count": MIN_ALLOWED_SCOPE_FAMILY_COUNT,
        "explicit_general_platform_flag": explicit_platform_flag,
        "api_surface_ready": api_surface_ready,
        "blocker_count": len(blocker_rows),
        "blockers": [row["check_id"] for row in blocker_rows],
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Keep general protein-ligand wording blocked until transporter and PXR are ready, allowed scope families reach at least six, and an explicit platform flag is set."
            if blocker_rows
            else "General protein-ligand claim prerequisites are green; explicit product/API widening remains a separate approval."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# General Protein-Ligand Claim Blocker Packet",
        "",
        f"- claim_blocker_packet_ready: `{s['claim_blocker_packet_ready']}`",
        f"- general_protein_ligand_claim_allowed: `{s['general_protein_ligand_claim_allowed']}`",
        f"- scope_breadth_ready: `{s['scope_breadth_ready']}`",
        f"- ready_domains: `{','.join(s['ready_domains'])}`",
        f"- missing_domains: `{','.join(s['missing_domains'])}`",
        f"- allowed_scope_family_count: `{s['allowed_scope_family_count']}`",
        f"- min_allowed_scope_family_count: `{s['min_allowed_scope_family_count']}`",
        f"- explicit_general_platform_flag: `{s['explicit_general_platform_flag']}`",
        f"- api_surface_ready: `{s['api_surface_ready']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- blockers: `{','.join(s['blockers'])}`",
        "",
        "## Checks",
        "",
        "| check | type | status | current | required | blocker | next action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['check_type']}` | `{row['status']}` | "
            f"`{row['current_value']}` | `{row['required_value']}` | `{row['release_blocker']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build general protein-ligand claim blocker packet.")
    parser.add_argument("--scope-json", default=str(DEFAULT_SCOPE_JSON))
    parser.add_argument("--capability-json", default=str(DEFAULT_CAPABILITY_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(scope_payload=_load_json(args.scope_json), capability_payload=_load_json(args.capability_json))
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
