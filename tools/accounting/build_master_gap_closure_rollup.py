#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/master_gap_closure_rollup_current.json"
DEFAULT_OUT_CSV = "runs/master_gap_closure_rollup_current.csv"
DEFAULT_OUT_MD = "runs/master_gap_closure_rollup_current.md"

CLAIM_BOUNDARY = (
    "Master gap closure rollup only; it aggregates local accounting closure status across commercial, product AI, "
    "data/science, infrastructure, deploy/ops/legal, storage/tools, science-claim-boundary, and API runner profile "
    "readiness packets. It does not run docking, promote claims, enable execution, delete files, or mutate external state."
)

ROLLUP_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("COMMERCIAL", "Commercial productization gaps", "runs/commercial_gap_closure_status_current.json", "commercial_gap_closure_complete"),
    (
        "PRODUCT-AI",
        "Product AI architecture gaps",
        "runs/product_ai_architecture_gap_closure_current.json",
        "product_ai_architecture_gap_closure_complete",
    ),
    (
        "DATA-SCIENCE",
        "Data/science expansion gaps",
        "runs/data_science_expansion_gap_closure_current.json",
        "data_science_expansion_gap_closure_complete",
    ),
    (
        "INFRA",
        "Product infrastructure gaps",
        "runs/product_infrastructure_gap_closure_current.json",
        "product_infrastructure_gap_closure_complete",
    ),
    (
        "SCI-CLAIM",
        "Science claim promotion boundaries",
        "runs/science_claim_promotion_gap_closure_current.json",
        "science_claim_promotion_gap_closure_complete",
    ),
    (
        "DEPLOY-OPS",
        "Deploy/ops/legal boundaries",
        "runs/deploy_ops_legal_gap_closure_current.json",
        "deploy_ops_legal_gap_closure_complete",
    ),
    (
        "STORAGE",
        "Storage cleanup boundaries",
        "runs/storage_cleanup_gap_closure_current.json",
        "storage_cleanup_gap_closure_complete",
    ),
    (
        "TOOLS",
        "Tools refactor planning boundaries",
        "runs/tools_refactor_gap_closure_current.json",
        "tools_refactor_gap_closure_complete",
    ),
    (
        "API-RUNNER",
        "API runner profile promotion readiness",
        "runs/api_runner_profile_promotion_readiness_current.json",
        "api_runner_profile_promotion_ready",
    ),
)


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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _row(
    gap_id: str,
    area: str,
    status: str,
    evidence: str,
    observed: str,
    next_action: str,
    *,
    rollup_status: str = "",
) -> dict[str, Any]:
    return {
        "gap_id": gap_id,
        "area": area,
        "status": status,
        "evidence": evidence,
        "observed": observed,
        "next_action": next_action,
        "rollup_status": rollup_status,
        "release_blocker": status != "closed",
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_master_gap_closure_rollup(
    *,
    commercial_packet: dict[str, Any] | None = None,
    product_ai_packet: dict[str, Any] | None = None,
    data_science_packet: dict[str, Any] | None = None,
    infrastructure_packet: dict[str, Any] | None = None,
    science_claim_packet: dict[str, Any] | None = None,
    deploy_ops_packet: dict[str, Any] | None = None,
    storage_packet: dict[str, Any] | None = None,
    tools_packet: dict[str, Any] | None = None,
    api_runner_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet_overrides = {
        "COMMERCIAL": commercial_packet,
        "PRODUCT-AI": product_ai_packet,
        "DATA-SCIENCE": data_science_packet,
        "INFRA": infrastructure_packet,
        "SCI-CLAIM": science_claim_packet,
        "DEPLOY-OPS": deploy_ops_packet,
        "STORAGE": storage_packet,
        "TOOLS": tools_packet,
        "API-RUNNER": api_runner_packet,
    }
    rows: list[dict[str, Any]] = []
    for gap_id, area, artifact, complete_status in ROLLUP_SPECS:
        packet = packet_overrides.get(gap_id)
        if packet is None:
            packet = _read_json_if_present(artifact)
        summary = _summary(packet)
        rollup_status = _text(summary.get("status"))
        closed = bool(summary.get("all_gaps_closed") is True or rollup_status == complete_status)
        rows.append(
            _row(
                gap_id,
                area,
                "closed" if closed else "open",
                artifact,
                f"rollup_status={rollup_status or 'missing'}; all_gaps_closed={summary.get('all_gaps_closed')}",
                _text(summary.get("current_next_action") or summary.get("next_required_step"))
                or f"Rebuild {artifact} until status={complete_status}.",
                rollup_status=rollup_status,
            )
        )
    closed_rows = [row for row in rows if row["status"] == "closed"]
    open_rows = [row for row in rows if row["status"] != "closed"]
    first_open = open_rows[0] if open_rows else None
    summary = {
        "packet_type": "master_gap_closure_rollup",
        "status": "master_gap_closure_rollup_complete" if not open_rows else "blocked_master_gap_closure_rollup",
        "all_gaps_closed": not open_rows,
        "gap_count": len(rows),
        "closed_gap_count": len(closed_rows),
        "open_gap_count": len(open_rows),
        "closed_gap_ids": [row["gap_id"] for row in closed_rows],
        "open_gap_ids": [row["gap_id"] for row in open_rows],
        "current_primary_open_gap_id": first_open["gap_id"] if first_open else "none",
        "current_next_action": first_open["next_action"] if first_open else "All tracked master gap closure rollups are complete.",
        "execution_enabled": False,
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Master Gap Closure Rollup",
        "",
        f"- status: `{s['status']}`",
        f"- all_gaps_closed: `{s['all_gaps_closed']}`",
        f"- closed_gap_count: `{s['closed_gap_count']}` / `{s['gap_count']}`",
        "",
        "## Rollups",
        "",
        "| gap_id | status | area | rollup_status |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['gap_id']}` | `{row['status']}` | {row['area']} | `{row['rollup_status']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build master gap closure rollup.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_master_gap_closure_rollup()
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
