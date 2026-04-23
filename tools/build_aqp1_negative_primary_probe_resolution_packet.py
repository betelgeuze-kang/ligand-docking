#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_NEGATIVE_PRIMARY_PROBE_JSON = "runs/aqp1_negative_primary_probe_packet_current.json"
DEFAULT_NEGATIVE_FRONTIER_RESOLUTION_JSON = "runs/aqp1_negative_frontier_resolution_packet_current.json"
DEFAULT_NEGATIVE_CONFIRMATION_JSON = "runs/aqp1_negative_evidence_confirmation_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_negative_primary_probe_resolution_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_negative_primary_probe_resolution_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_negative_primary_probe_resolution_packet_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def build_payload(
    negative_primary_probe_payload: dict[str, Any],
    negative_frontier_resolution_payload: dict[str, Any],
    negative_confirmation_payload: dict[str, Any],
    *,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    probe_summary = dict((negative_primary_probe_payload or {}).get("summary", {}) or {})
    probe_rows = list((negative_primary_probe_payload or {}).get("rows", []) or [])
    frontier_rows = list((negative_frontier_resolution_payload or {}).get("rows", []) or [])
    confirmation_summary = dict((negative_confirmation_payload or {}).get("summary", {}) or {})
    today = as_of_date or date.today().isoformat()

    probe_row = dict(probe_rows[0]) if probe_rows else {}
    frontier_by_name = {
        _text(row.get("candidate_name")): dict(row)
        for row in frontier_rows
        if _text(row.get("candidate_name"))
    }
    fallback_row = frontier_by_name.get("dimethyl sulfoxide", {})
    resolution_decision = (
        _text(confirmation_summary.get("confirmation_decision"))
        or _text(probe_summary.get("probe_decision"))
        or "keep_review_only_no_authoritative_negative_promotion"
    )

    rows = [
        {
            "resolution_rank": 1,
            "candidate_name": _text(probe_row.get("candidate_name")) or "sodium nitroprusside",
            "molecule_chembl_id": _text(probe_row.get("molecule_chembl_id")),
            "probe_resolution_role": "primary_direct_negative_probe_followup_review_only",
            "current_probe_state": _text(probe_row.get("probe_role")) or "primary_review_only_negative_probe_candidate",
            "source_anchor_pmid": _text(probe_row.get("source_anchor_pmid")) or _text(probe_summary.get("source_anchor_pmid")),
            "source_anchor_title": _text(probe_row.get("source_anchor_title")),
            "source_anchor_url": _text(probe_row.get("source_anchor_url")),
            "indirect_context_pmid": _text(probe_row.get("indirect_context_pmid")) or _text(probe_summary.get("indirect_context_pmid")),
            "indirect_context_title": _text(probe_row.get("indirect_context_title")),
            "indirect_context_url": _text(probe_row.get("indirect_context_url")),
            "assay_context_pmid": _text(probe_row.get("assay_context_pmid")) or _text(probe_summary.get("assay_context_pmid")),
            "assay_context_title": _text(probe_row.get("assay_context_title")),
            "assay_context_url": _text(probe_row.get("assay_context_url")),
            "exact_target_pair_activity_count": _int(probe_row.get("exact_target_pair_activity_count")),
            "activity_url": _text(probe_row.get("activity_url")),
            "solvent_fallback_candidate": _text(fallback_row.get("candidate_name")) or "dimethyl sulfoxide",
            "solvent_fallback_role": _text(fallback_row.get("frontier_resolution_role")) or "solvent_context_fallback_frontier_candidate",
            "solvent_fallback_context_signal": _text(fallback_row.get("context_signal")),
            "solvent_fallback_exact_target_pair_activity_count": _int(fallback_row.get("exact_target_pair_activity_count")),
            "resolution_decision": resolution_decision,
            "blocker_reason": "no_direct_transporter_specific_quantitative_negative_row_with_claim_safe_provenance",
            "closure_gate": (
                "Promote only if a direct transporter-specific quantitative negative row with unambiguous ligand identity, human-relevant target context, and claim-safe provenance is curated."
            ),
            "park_gate": (
                "Keep sodium nitroprusside review-only when the exact-source outcome is almost unaffected, older permeability reports point in a conflicting direction, and exact target-pair activity is still absent."
            ),
            "fallback_instruction": (
                "Keep dimethyl sulfoxide as exact-source small-inhibitor solvent context from PMID 23123479; do not reuse it as a negative fallback or primary negative probe."
            ),
            "authoritative_apply_allowed": False,
        }
    ]

    summary = {
        "family": "aqp1",
        "as_of_date": today,
        "row_count": len(rows),
        "primary_probe_candidate": _text(rows[0].get("candidate_name")) if rows else "",
        "source_anchor_pmid": _text(rows[0].get("source_anchor_pmid")) if rows else "",
        "indirect_context_pmid": _text(rows[0].get("indirect_context_pmid")) if rows else "",
        "assay_context_pmid": _text(rows[0].get("assay_context_pmid")) if rows else "",
        "solvent_fallback_candidate": _text(rows[0].get("solvent_fallback_candidate")) if rows else "",
        "exact_target_pair_absent_count": sum(
            1 for row in rows if _int(row.get("exact_target_pair_activity_count")) == 0
        ),
        "direct_negative_quantitative_row_found_count": 0,
        "resolution_decision": resolution_decision,
        "packet_artifact": "runs/aqp1_negative_primary_probe_resolution_packet_current.md",
        "next_required_step": (
            "Open sodium nitroprusside as the first AQP1 primary-probe follow-up lane, keep it review-only while ChEMBL exact target-pair activity remains absent, and treat dimethyl sulfoxide only as exact-source small-inhibitor solvent context rather than a negative fallback. Do not promote any authoritative negative row until a direct transporter-specific quantitative negative measurement is curated."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Primary Probe Resolution Packet",
        "",
        f"- family: `{s['family']}`",
        f"- as_of_date: `{s['as_of_date']}`",
        f"- row_count: `{s['row_count']}`",
        f"- primary_probe_candidate: `{s['primary_probe_candidate']}`",
        f"- source_anchor_pmid: `{s['source_anchor_pmid']}`",
        f"- indirect_context_pmid: `{s['indirect_context_pmid']}`",
        f"- assay_context_pmid: `{s['assay_context_pmid']}`",
        f"- solvent_fallback_candidate: `{s['solvent_fallback_candidate']}`",
        f"- exact_target_pair_absent_count: `{s['exact_target_pair_absent_count']}`",
        f"- direct_negative_quantitative_row_found_count: `{s['direct_negative_quantitative_row_found_count']}`",
        f"- resolution_decision: `{s['resolution_decision']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Resolution Row",
        "",
        "| resolution_rank | candidate_name | probe_resolution_role | source_anchor_pmid | indirect_context_pmid | assay_context_pmid | solvent_fallback_candidate | exact_target_pair_activity_count |",
        "| ---: | --- | --- | --- | --- | --- | --- | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['resolution_rank']} | `{row['candidate_name']}` | `{row['probe_resolution_role']}` | "
            f"`{row['source_anchor_pmid']}` | `{row['indirect_context_pmid']}` | `{row['assay_context_pmid']}` | "
            f"`{row['solvent_fallback_candidate']}` | {row['exact_target_pair_activity_count']} |"
        )
    lines.extend(["", "## Gates", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['candidate_name']}` promote: {row['closure_gate']}")
        lines.append(f"- `{row['candidate_name']}` park: {row['park_gate']}")
        lines.append(f"- `{row['candidate_name']}` fallback: {row['fallback_instruction']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AQP1 negative primary probe resolution packet.")
    parser.add_argument("--negative-primary-probe-json", default=DEFAULT_NEGATIVE_PRIMARY_PROBE_JSON)
    parser.add_argument("--negative-frontier-resolution-json", default=DEFAULT_NEGATIVE_FRONTIER_RESOLUTION_JSON)
    parser.add_argument("--negative-confirmation-json", default=DEFAULT_NEGATIVE_CONFIRMATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.negative_primary_probe_json),
        _load_json(args.negative_frontier_resolution_json),
        _load_json(args.negative_confirmation_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
