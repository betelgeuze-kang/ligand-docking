#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_NEGATIVE_CANDIDATE_FRONTIER_JSON = "runs/aqp1_negative_candidate_frontier_packet_current.json"
DEFAULT_NEGATIVE_CONFIRMATION_JSON = "runs/aqp1_negative_evidence_confirmation_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_negative_frontier_resolution_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_negative_frontier_resolution_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_negative_frontier_resolution_packet_current.md"

PRIMARY_ANCHOR_PMID = "23123479"
PRIMARY_ANCHOR_TITLE = "Reinvestigation of drugs and chemicals as aquaporin-1 inhibitors using pressure-induced hemolysis in human erythrocytes."
PRIMARY_ANCHOR_URL = "https://pubmed.ncbi.nlm.nih.gov/23123479/"

INDIRECT_CONTEXT_PMID = "27261598"
INDIRECT_CONTEXT_TITLE = "Effects of nitric oxide system and osmotic stress on Aquaporin-1 in the postnatal heart."
INDIRECT_CONTEXT_URL = "https://pubmed.ncbi.nlm.nih.gov/27261598/"


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
    negative_candidate_frontier_payload: dict[str, Any],
    negative_confirmation_payload: dict[str, Any],
    *,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    frontier_rows = list((negative_candidate_frontier_payload or {}).get("rows", []) or [])
    confirmation_summary = dict((negative_confirmation_payload or {}).get("summary", {}) or {})
    today = as_of_date or date.today().isoformat()

    frontier_by_name = {
        _text(row.get("candidate_name")): dict(row)
        for row in frontier_rows
        if _text(row.get("candidate_name"))
    }

    ordered_candidates = [
        (
            "sodium nitroprusside",
            {
                "frontier_resolution_role": "primary_indirect_aqp1_context_frontier_candidate",
                "supporting_context_pmid": INDIRECT_CONTEXT_PMID,
                "supporting_context_title": INDIRECT_CONTEXT_TITLE,
                "supporting_context_url": INDIRECT_CONTEXT_URL,
                "context_signal": "indirect_aqp1_no_system_context_present",
                "state_change_potential": "medium",
            },
        ),
        (
            "dimethyl sulfoxide",
            {
                "frontier_resolution_role": "solvent_context_fallback_frontier_candidate",
                "supporting_context_pmid": "",
                "supporting_context_title": "",
                "supporting_context_url": "",
                "context_signal": "no_clean_aqp1_specific_support_beyond_exact_source_keep_solvent_fallback_only",
                "state_change_potential": "low",
            },
        ),
    ]

    rows: list[dict[str, Any]] = []
    for resolution_rank, (candidate_name, meta) in enumerate(ordered_candidates, start=1):
        frontier_row = frontier_by_name.get(candidate_name, {})
        rows.append(
            {
                "resolution_rank": resolution_rank,
                "candidate_name": candidate_name,
                "molecule_chembl_id": _text(frontier_row.get("molecule_chembl_id")),
                "frontier_resolution_role": _text(meta.get("frontier_resolution_role")),
                "source_anchor_pmid": PRIMARY_ANCHOR_PMID,
                "source_anchor_title": PRIMARY_ANCHOR_TITLE,
                "source_anchor_url": PRIMARY_ANCHOR_URL,
                "supporting_context_pmid": _text(meta.get("supporting_context_pmid")),
                "supporting_context_title": _text(meta.get("supporting_context_title")),
                "supporting_context_url": _text(meta.get("supporting_context_url")),
                "exact_target_pair_activity_count": _int(frontier_row.get("exact_target_pair_activity_count")),
                "activity_url": _text(frontier_row.get("activity_url")),
                "context_signal": _text(meta.get("context_signal")),
                "state_change_potential": _text(meta.get("state_change_potential")),
                "confirmation_decision": _text(confirmation_summary.get("confirmation_decision"))
                or "keep_review_only_no_authoritative_negative_promotion",
                "authoritative_apply_allowed": False,
            }
        )

    summary = {
        "family": "aqp1",
        "as_of_date": today,
        "row_count": len(rows),
        "primary_frontier_candidate": "sodium nitroprusside",
        "solvent_fallback_candidate": "dimethyl sulfoxide",
        "indirect_context_row_count": sum(1 for row in rows if _text(row.get("supporting_context_pmid"))),
        "solvent_context_row_count": sum(
            1
            for row in rows
            if _text(row.get("frontier_resolution_role")) == "solvent_context_fallback_frontier_candidate"
        ),
        "exact_target_pair_absent_count": sum(
            1 for row in rows if _int(row.get("exact_target_pair_activity_count")) == 0
        ),
        "authoritative_negative_promotion_candidate_count": 0,
        "packet_artifact": "runs/aqp1_negative_frontier_resolution_packet_current.md",
        "next_required_step": (
            "Use sodium nitroprusside first as the primary frontier resolution lane because it is exact-source tested and has indirect AQP1 context (PMID 27261598), but keep it review-only until a direct transporter-specific quantitative negative row is curated. Keep DMSO only as a solvent-context fallback from PMID 23123479."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Frontier Resolution Packet",
        "",
        f"- family: `{s['family']}`",
        f"- as_of_date: `{s['as_of_date']}`",
        f"- row_count: `{s['row_count']}`",
        f"- primary_frontier_candidate: `{s['primary_frontier_candidate']}`",
        f"- solvent_fallback_candidate: `{s['solvent_fallback_candidate']}`",
        f"- indirect_context_row_count: `{s['indirect_context_row_count']}`",
        f"- solvent_context_row_count: `{s['solvent_context_row_count']}`",
        f"- exact_target_pair_absent_count: `{s['exact_target_pair_absent_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Resolution Rows",
        "",
        "| resolution_rank | candidate_name | frontier_resolution_role | supporting_context_pmid | exact_target_pair_activity_count | context_signal |",
        "| ---: | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['resolution_rank']} | `{row['candidate_name']}` | `{row['frontier_resolution_role']}` | "
            f"`{row['supporting_context_pmid'] or '-'}` | {row['exact_target_pair_activity_count']} | `{row['context_signal']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AQP1 negative frontier resolution packet.")
    parser.add_argument("--negative-candidate-frontier-json", default=DEFAULT_NEGATIVE_CANDIDATE_FRONTIER_JSON)
    parser.add_argument("--negative-confirmation-json", default=DEFAULT_NEGATIVE_CONFIRMATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.negative_candidate_frontier_json),
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
