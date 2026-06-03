#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.readiness import build_product_readiness_gate

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VERDICT_JSON = "runs/local_delivery_verdict_gate_current.json"
DEFAULT_OUT_JSON = "runs/product_readiness_gate_current.json"
DEFAULT_OUT_MD = "runs/product_readiness_gate_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Readiness Gate",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- family: `{s['family']}`",
        f"- ligand_count: `{s['ligand_count']}`",
        f"- request_contract_status: `{s['request_contract_status']}`",
        f"- local_delivery_delivery_ready: `{s['local_delivery_delivery_ready']}`",
        f"- local_delivery_verdict: `{s['local_delivery_verdict']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- docking_results_emitted: `{s['docking_results_emitted']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        f"- execution_approval_token_required: `{s['execution_approval_token_required']}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a product readiness gate from a docking request JSON and local-delivery verdict.")
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--verdict-json", default=DEFAULT_VERDICT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_readiness_gate(
        _read_json(args.request_json),
        _read_json(args.verdict_json),
        local_delivery_verdict_path=str(args.verdict_json),
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
