#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT_BUNDLE_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_MASTER_QUEUE_JSON = "runs/wetlab_master_execution_queue_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_outbound_execution_priority_board_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_outbound_execution_priority_board_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_outbound_execution_priority_board_current.md"

TRACK_PRIORITY: dict[str, dict[str, str | int]] = {
    "DNDi_IPK": {
        "priority_rank": 1,
        "campaign_bucket": "neglected_disease_now",
        "priority_reason": "Neglected-disease outbound is already packaged around cheap recombinant assays and explicit counterscreens.",
    },
    "READDI_Korea": {
        "priority_rank": 2,
        "campaign_bucket": "viral_protease_now",
        "priority_reason": "Paired Mpro and PLpro antiviral packet has vendor-checked controls and a clear fast micro-validation story.",
    },
    "M4K_open_science": {
        "priority_rank": 3,
        "campaign_bucket": "rare_disease_kinase_now",
        "priority_reason": "ALK2 is already framed for a mutant-aware open-science kinase validation pass.",
    },
    "oncology_condition_aware": {
        "priority_rank": 4,
        "campaign_bucket": "condition_aware_oncology_now",
        "priority_reason": "CA IX is ready for outbound under acidic-buffer conditions with same-packet deselection controls.",
    },
    "SGC_dark_kinase": {
        "priority_rank": 5,
        "campaign_bucket": "dark_kinase_benchmark_now",
        "priority_reason": "STK17B is sendable now but is lower direct disease urgency than neglected-disease and viral rails.",
    },
}


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _split_targets(text: str) -> list[str]:
    return [part.strip() for part in str(text).split(";") if part.strip()]


def _all_chains_resolved(master_queue: dict[str, Any]) -> bool:
    summary = dict(master_queue.get("summary", {}) or {})
    gate_states = dict(summary.get("stack_gate_states", {}) or {})
    if not gate_states:
        return False
    return all(bool(dict(row or {}).get("all_rows_resolved", False)) for row in gate_states.values())


def build_payload(
    export_bundle: dict[str, Any],
    portfolio: dict[str, Any],
    master_queue: dict[str, Any],
) -> dict[str, Any]:
    export_summary = dict(export_bundle.get("summary", {}) or {})
    portfolio_rows = list(portfolio.get("rows", []) or [])
    master_summary = dict(master_queue.get("summary", {}) or {})
    portfolio_by_target = {
        str(row.get("target_id", "")).strip(): dict(row)
        for row in portfolio_rows
        if str(row.get("target_id", "")).strip()
    }

    all_resolved = _all_chains_resolved(master_queue)
    rows: list[dict[str, Any]] = []
    for row in list(export_bundle.get("rows", []) or []):
        track_id = str(row.get("track_id", "")).strip()
        priority_meta = TRACK_PRIORITY.get(
            track_id,
            {
                "priority_rank": 99,
                "campaign_bucket": "unmapped_track",
                "priority_reason": "Track is not yet ranked in the bounded outbound execution board.",
            },
        )
        lead_targets = _split_targets(str(row.get("lead_targets", "")))
        lead_target_rows = [portfolio_by_target[target] for target in lead_targets if target in portfolio_by_target]
        disease_areas = list(dict.fromkeys(str(target_row.get("disease_area", "")).strip() for target_row in lead_target_rows if str(target_row.get("disease_area", "")).strip()))
        partner_rails = list(dict.fromkeys(str(target_row.get("partner_rail", "")).strip() for target_row in lead_target_rows if str(target_row.get("partner_rail", "")).strip()))
        total_priority_score = sum(int(target_row.get("total_priority_score", 0) or 0) for target_row in lead_target_rows)
        execution_now = bool(all_resolved and str(row.get("status", "")).strip() == "ready_to_send")
        rows.append(
            {
                "priority_rank": int(priority_meta["priority_rank"]),
                "track_id": track_id,
                "track_label": str(row.get("track_label", "")).strip(),
                "track_status": str(row.get("status", "")).strip(),
                "execution_now": execution_now,
                "campaign_bucket": str(priority_meta["campaign_bucket"]),
                "lead_targets": "; ".join(lead_targets),
                "lead_target_count": len(lead_targets),
                "lead_disease_areas": "; ".join(disease_areas),
                "partner_rails": "; ".join(partner_rails),
                "combined_total_priority_score": total_priority_score,
                "proposal_title": str(row.get("proposal_title", "")).strip(),
                "attachment_artifacts": str(row.get("attachment_artifacts", "")).strip(),
                "priority_reason": str(priority_meta["priority_reason"]),
            }
        )

    rows.sort(key=lambda item: (int(item["priority_rank"]), str(item["track_id"])))
    top_row = rows[0] if rows else {}
    ready_to_send_count = sum(1 for row in rows if bool(row.get("execution_now")))
    disease_virus_priority_count = sum(
        1
        for row in rows
        if str(row.get("campaign_bucket", "")) in {"neglected_disease_now", "viral_protease_now"}
    )
    summary = {
        "status": "wetlab_outbound_execution_priority_board_ready",
        "board_scope": "real_disease_virus_outbound_execution_packets",
        "all_chains_resolved": all_resolved,
        "chain_count": int(master_summary.get("chain_count", 0) or 0),
        "resolved_target_count": int(master_summary.get("resolved_target_count", 0) or 0),
        "ready_to_send_count": ready_to_send_count,
        "ready_to_send_target_count": ready_to_send_count,
        "priority_track_count": len(rows),
        "disease_virus_priority_count": disease_virus_priority_count,
        "top_priority_track_id": str(top_row.get("track_id", "")).strip(),
        "top_priority_track_label": str(top_row.get("track_label", "")).strip(),
        "top_priority_lead_targets": str(top_row.get("lead_targets", "")).strip(),
        "top_priority_disease_areas": str(top_row.get("lead_disease_areas", "")).strip(),
        "first_priority_target": str(top_row.get("lead_targets", "")).strip(),
        "follow_on_target_count": max(len(rows) - 1, 0),
        "export_bundle_sender_name": str(export_summary.get("sender_name", "")).strip(),
        "next_required_step": (
            "Send DNDi/IPK first, then READDI_Korea, then M4K_open_science, oncology_condition_aware, and SGC_dark_kinase."
            if rows and all_resolved
            else "Finish resolving all serialized chains before using this outbound execution priority board."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Wet-Lab Outbound Execution Priority Board",
        "",
        f"- status: `{summary['status']}`",
        f"- board_scope: `{summary['board_scope']}`",
        f"- all_chains_resolved: `{summary['all_chains_resolved']}`",
        f"- chain_count: `{summary['chain_count']}`",
        f"- resolved_target_count: `{summary['resolved_target_count']}`",
        f"- ready_to_send_count: `{summary['ready_to_send_count']}`",
        f"- priority_track_count: `{summary['priority_track_count']}`",
        f"- disease_virus_priority_count: `{summary['disease_virus_priority_count']}`",
        f"- top_priority_track_id: `{summary['top_priority_track_id']}`",
        f"- top_priority_track_label: `{summary['top_priority_track_label']}`",
        f"- top_priority_lead_targets: `{summary['top_priority_lead_targets']}`",
        f"- top_priority_disease_areas: `{summary['top_priority_disease_areas']}`",
        f"- export_bundle_sender_name: `{summary['export_bundle_sender_name']}`",
        "",
        "| Rank | Track | Lead Targets | Disease Areas | Send Now | Bucket |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | {row['track_id']} | {row['lead_targets']} | {row['lead_disease_areas']} | {row['execution_now']} | {row['campaign_bucket']} |"
        )
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            f"- {summary['next_required_step']}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wet-lab outbound execution priority board.")
    parser.add_argument("--export-bundle-json", default=DEFAULT_EXPORT_BUNDLE_JSON)
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--master-queue-json", default=DEFAULT_MASTER_QUEUE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.export_bundle_json),
        _load_json(args.portfolio_json),
        _load_json(args.master_queue_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
