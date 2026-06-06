#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_NEGATIVE_CONFIRMATION_JSON = "runs/aqp1_negative_evidence_confirmation_packet_current.json"
DEFAULT_NEGATIVE_SOURCE_EXCLUSION_JSON = "runs/aqp1_negative_source_exclusion_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_negative_candidate_frontier_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_negative_candidate_frontier_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_negative_candidate_frontier_packet_current.md"

PRIMARY_ANCHOR_PMID = "23123479"
PRIMARY_ANCHOR_TITLE = "Reinvestigation of drugs and chemicals as aquaporin-1 inhibitors using pressure-induced hemolysis in human erythrocytes."
PRIMARY_ANCHOR_URL = "https://pubmed.ncbi.nlm.nih.gov/23123479/"

FRONTIER_ROWS = [
    {
        "frontier_rank": 1,
        "candidate_name": "acetazolamide",
        "molecule_chembl_id": "CHEMBL20",
        "source_role": "positive_boundary_context_keep_excluded",
        "source_anchor": "PMID 40359885",
        "exact_target_pair_activity_count": 0,
        "frontier_status": "exact_human_aqp1_target_pair_absent_boundary_only",
        "state_change_potential": "low",
    },
    {
        "frontier_rank": 2,
        "candidate_name": "tetraethylammonium",
        "molecule_chembl_id": "CHEMBL9324",
        "source_role": "tool_reference_context_keep_excluded",
        "source_anchor": "PMID 23123479",
        "exact_target_pair_activity_count": 0,
        "frontier_status": "exact_human_aqp1_target_pair_absent_tool_reference_only",
        "state_change_potential": "low",
    },
    {
        "frontier_rank": 3,
        "candidate_name": "sodium nitroprusside",
        "molecule_chembl_id": "CHEMBL136478",
        "source_role": "exact_source_tested_frontier_candidate",
        "source_anchor": "PMID 23123479",
        "exact_target_pair_activity_count": 0,
        "frontier_status": "exact_source_tested_exact_pair_absent_review_only_frontier",
        "state_change_potential": "medium",
    },
    {
        "frontier_rank": 4,
        "candidate_name": "dimethyl sulfoxide",
        "molecule_chembl_id": "CHEMBL504",
        "source_role": "exact_source_tested_frontier_candidate",
        "source_anchor": "PMID 23123479",
        "exact_target_pair_activity_count": 0,
        "frontier_status": "exact_source_tested_exact_pair_absent_review_only_frontier",
        "state_change_potential": "medium",
    },
]


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
    negative_confirmation_payload: dict[str, Any],
    negative_source_exclusion_payload: dict[str, Any],
    *,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    confirmation_summary = dict((negative_confirmation_payload or {}).get("summary", {}) or {})
    exclusion_rows = list((negative_source_exclusion_payload or {}).get("rows", []) or [])
    exclusion_by_name = {_text(row.get("candidate_name")): dict(row) for row in exclusion_rows if _text(row.get("candidate_name"))}
    today = as_of_date or date.today().isoformat()

    rows: list[dict[str, Any]] = []
    for row in FRONTIER_ROWS:
        candidate_name = _text(row["candidate_name"])
        exclusion_row = exclusion_by_name.get(candidate_name, {})
        exact_target_pair_activity_count = row["exact_target_pair_activity_count"]
        activity_url = _text(exclusion_row.get("activity_url"))
        if not activity_url and candidate_name == "sodium nitroprusside":
            activity_url = "https://www.ebi.ac.uk/chembl/api/data/activity.json?molecule_chembl_id=CHEMBL136478&target_chembl_id=CHEMBL4523210&limit=10"
        if not activity_url and candidate_name == "dimethyl sulfoxide":
            activity_url = "https://www.ebi.ac.uk/chembl/api/data/activity.json?molecule_chembl_id=CHEMBL504&target_chembl_id=CHEMBL4523210&limit=10"

        rows.append(
            {
                "frontier_rank": row["frontier_rank"],
                "candidate_name": candidate_name,
                "molecule_chembl_id": _text(row["molecule_chembl_id"]),
                "source_role": _text(row["source_role"]),
                "source_anchor": _text(row["source_anchor"]),
                "primary_anchor_pmid": PRIMARY_ANCHOR_PMID,
                "primary_anchor_title": PRIMARY_ANCHOR_TITLE,
                "primary_anchor_url": PRIMARY_ANCHOR_URL,
                "exact_target_pair_activity_count": exact_target_pair_activity_count,
                "activity_url": activity_url,
                "frontier_status": _text(row["frontier_status"]),
                "state_change_potential": _text(row["state_change_potential"]),
                "confirmation_decision": _text(confirmation_summary.get("confirmation_decision"))
                or "keep_review_only_no_authoritative_negative_promotion",
                "authoritative_apply_allowed": False,
            }
        )

    summary = {
        "family": "aqp1",
        "as_of_date": today,
        "row_count": len(rows),
        "exact_source_tested_row_count": len(rows),
        "exact_target_pair_absent_count": sum(1 for row in rows if _int(row.get("exact_target_pair_activity_count")) == 0),
        "frontier_candidate_count": sum(1 for row in rows if _text(row.get("source_role")) == "exact_source_tested_frontier_candidate"),
        "claim_safe_negative_candidate_count": 0,
        "primary_frontier_candidate": "sodium nitroprusside",
        "primary_anchor_pmid": PRIMARY_ANCHOR_PMID,
        "packet_artifact": "runs/aqp1_negative_candidate_frontier_packet_current.md",
        "next_required_step": (
            "Use PMID 23123479 as the exact-source tested frontier. Keep acetazolamide and tetraethylammonium excluded, and treat sodium nitroprusside plus DMSO as review-only frontier candidates until a direct transporter-specific quantitative negative row is curated."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Candidate Frontier Packet",
        "",
        f"- family: `{s['family']}`",
        f"- as_of_date: `{s['as_of_date']}`",
        f"- row_count: `{s['row_count']}`",
        f"- exact_source_tested_row_count: `{s['exact_source_tested_row_count']}`",
        f"- exact_target_pair_absent_count: `{s['exact_target_pair_absent_count']}`",
        f"- frontier_candidate_count: `{s['frontier_candidate_count']}`",
        f"- claim_safe_negative_candidate_count: `{s['claim_safe_negative_candidate_count']}`",
        f"- primary_frontier_candidate: `{s['primary_frontier_candidate']}`",
        f"- primary_anchor_pmid: `{s['primary_anchor_pmid']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Frontier Rows",
        "",
        "| frontier_rank | candidate_name | molecule_chembl_id | source_role | exact_target_pair_activity_count | frontier_status |",
        "| ---: | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['frontier_rank']} | `{row['candidate_name']}` | `{row['molecule_chembl_id']}` | `{row['source_role']}` | "
            f"{row['exact_target_pair_activity_count']} | `{row['frontier_status']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AQP1 negative candidate frontier packet.")
    parser.add_argument("--negative-confirmation-json", default=DEFAULT_NEGATIVE_CONFIRMATION_JSON)
    parser.add_argument("--negative-source-exclusion-json", default=DEFAULT_NEGATIVE_SOURCE_EXCLUSION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.negative_confirmation_json),
        _load_json(args.negative_source_exclusion_json),
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
