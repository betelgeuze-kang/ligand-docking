#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_NEGATIVE_FRONTIER_RESOLUTION_JSON = "runs/aqp1_negative_frontier_resolution_packet_current.json"
DEFAULT_NEGATIVE_CONFIRMATION_JSON = "runs/aqp1_negative_evidence_confirmation_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_negative_primary_probe_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_negative_primary_probe_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_negative_primary_probe_packet_current.md"

SOURCE_ANCHOR_PMID = "23123479"
SOURCE_ANCHOR_TITLE = "Reinvestigation of drugs and chemicals as aquaporin-1 inhibitors using pressure-induced hemolysis in human erythrocytes."
SOURCE_ANCHOR_URL = "https://pubmed.ncbi.nlm.nih.gov/23123479/"
INDIRECT_CONTEXT_PMID = "27261598"
INDIRECT_CONTEXT_TITLE = "Effects of nitric oxide system and osmotic stress on Aquaporin-1 in the postnatal heart."
INDIRECT_CONTEXT_URL = "https://pubmed.ncbi.nlm.nih.gov/27261598/"
ASSAY_CONTEXT_PMID = "26685080"
ASSAY_CONTEXT_TITLE = "Rapid Identification of Novel Inhibitors of the Human Aquaporin-1 Water Channel."
ASSAY_CONTEXT_URL = "https://pubmed.ncbi.nlm.nih.gov/26685080/"


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
    negative_frontier_resolution_payload: dict[str, Any],
    negative_confirmation_payload: dict[str, Any],
    *,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    frontier_rows = list((negative_frontier_resolution_payload or {}).get("rows", []) or [])
    frontier_by_name = {
        _text(row.get("candidate_name")): dict(row)
        for row in frontier_rows
        if _text(row.get("candidate_name"))
    }
    probe_row = frontier_by_name.get("sodium nitroprusside", {})
    confirmation_summary = dict((negative_confirmation_payload or {}).get("summary", {}) or {})
    today = as_of_date or date.today().isoformat()

    rows = [
        {
            "probe_rank": 1,
            "candidate_name": "sodium nitroprusside",
            "molecule_chembl_id": _text(probe_row.get("molecule_chembl_id")),
            "probe_role": "primary_review_only_negative_probe_candidate",
            "source_anchor_pmid": SOURCE_ANCHOR_PMID,
            "source_anchor_title": SOURCE_ANCHOR_TITLE,
            "source_anchor_url": SOURCE_ANCHOR_URL,
            "indirect_context_pmid": INDIRECT_CONTEXT_PMID,
            "indirect_context_title": INDIRECT_CONTEXT_TITLE,
            "indirect_context_url": INDIRECT_CONTEXT_URL,
            "assay_context_pmid": ASSAY_CONTEXT_PMID,
            "assay_context_title": ASSAY_CONTEXT_TITLE,
            "assay_context_url": ASSAY_CONTEXT_URL,
            "exact_target_pair_activity_count": _int(probe_row.get("exact_target_pair_activity_count")),
            "activity_url": _text(probe_row.get("activity_url")),
            "probe_state_change_potential": "medium",
            "probe_decision": _text(confirmation_summary.get("confirmation_decision"))
            or "keep_review_only_no_authoritative_negative_promotion",
            "authoritative_apply_allowed": False,
        }
    ]

    summary = {
        "family": "aqp1",
        "as_of_date": today,
        "row_count": 1,
        "primary_probe_candidate": "sodium nitroprusside",
        "source_anchor_pmid": SOURCE_ANCHOR_PMID,
        "indirect_context_pmid": INDIRECT_CONTEXT_PMID,
        "assay_context_pmid": ASSAY_CONTEXT_PMID,
        "exact_target_pair_absent_count": rows[0]["exact_target_pair_activity_count"] == 0 and 1 or 0,
        "probe_decision": rows[0]["probe_decision"],
        "packet_artifact": "runs/aqp1_negative_primary_probe_packet_current.md",
        "next_required_step": (
            "Use sodium nitroprusside as the first AQP1 negative probe candidate because it is exact-source tested in PMID 23123479, has indirect AQP1/NO-system context in PMID 27261598, and can be interpreted against a human AQP1 inhibitor-assay context from PMID 26685080. Keep it review-only until a direct transporter-specific quantitative negative row is curated."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Primary Probe Packet",
        "",
        f"- family: `{s['family']}`",
        f"- as_of_date: `{s['as_of_date']}`",
        f"- row_count: `{s['row_count']}`",
        f"- primary_probe_candidate: `{s['primary_probe_candidate']}`",
        f"- source_anchor_pmid: `{s['source_anchor_pmid']}`",
        f"- indirect_context_pmid: `{s['indirect_context_pmid']}`",
        f"- assay_context_pmid: `{s['assay_context_pmid']}`",
        f"- exact_target_pair_absent_count: `{s['exact_target_pair_absent_count']}`",
        f"- probe_decision: `{s['probe_decision']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Probe Row",
        "",
        "| probe_rank | candidate_name | probe_role | source_anchor_pmid | indirect_context_pmid | assay_context_pmid | exact_target_pair_activity_count |",
        "| ---: | --- | --- | --- | --- | --- | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['probe_rank']} | `{row['candidate_name']}` | `{row['probe_role']}` | "
            f"`{row['source_anchor_pmid']}` | `{row['indirect_context_pmid']}` | `{row['assay_context_pmid']}` | "
            f"{row['exact_target_pair_activity_count']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AQP1 negative primary probe packet.")
    parser.add_argument("--negative-frontier-resolution-json", default=DEFAULT_NEGATIVE_FRONTIER_RESOLUTION_JSON)
    parser.add_argument("--negative-confirmation-json", default=DEFAULT_NEGATIVE_CONFIRMATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
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
