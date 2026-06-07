#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXTERNAL_SEED_JSON = "runs/aqp1_external_evidence_seed_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_candidate_evidence_ledger_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_candidate_evidence_ledger_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_candidate_evidence_ledger_current.md"


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _assay_surface(source_anchor: str, evidence_class: str) -> str:
    if source_anchor == "PMID 27474162":
        return "Xenopus oocyte swelling plus AQP1-high/low migration phenotype"
    if source_anchor == "PMID 22427546":
        return "human RPE fluid-flux assay with AQP1 antagonist intervention"
    if source_anchor == "PMID 26467039":
        return "AQP1 ion-conductance assay plus HT29 migration phenotype"
    if "BMC Physiol" in source_anchor:
        return "MDCK/native renal tissue water-flux functional assay"
    if "PLOS One" in source_anchor:
        return "kidney/HK-2 system modulation and degradation phenotype"
    return evidence_class


def _confidence_bucket(promotion_policy: str, evidence_strength: str) -> str:
    if promotion_policy == "draft_first_wave_manual_review" and "moderate" in evidence_strength:
        return "medium"
    if promotion_policy == "caution_only_not_for_authoritative_apply":
        return "low"
    return "low"


def build_payload(external_seed: dict[str, Any]) -> dict[str, Any]:
    source_rows = [dict(row) for row in (external_seed.get("rows", []) or [])]
    ledger_rows: list[dict[str, Any]] = []
    for row in source_rows:
        ledger_rows.append(
            {
                "candidate_name": str(row.get("candidate_name", "")).strip(),
                "proposed_packet_step": str(row.get("proposed_packet_step", "")).strip(),
                "mechanism_bucket": str(row.get("evidence_class", "")).strip(),
                "assay_surface": _assay_surface(str(row.get("source_anchor", "")).strip(), str(row.get("evidence_class", "")).strip()),
                "confidence": _confidence_bucket(str(row.get("promotion_policy", "")).strip(), str(row.get("evidence_strength", "")).strip()),
                "promotion_policy": str(row.get("promotion_policy", "")).strip(),
                "review_bucket": str(row.get("recommended_review_bucket", "")).strip(),
                "anchor": str(row.get("source_anchor", "")).strip(),
                "source_url": str(row.get("source_url", "")).strip(),
                "potency_or_signal": str(row.get("potency_or_signal", "")).strip(),
                "caution": str(row.get("caution", "")).strip(),
            }
        )
    summary = {
        "target_id": "AQP1_TRANSPORT_BLIND",
        "row_count": len(ledger_rows),
        "first_wave_row_count": sum(1 for row in ledger_rows if row["promotion_policy"] == "draft_first_wave_manual_review"),
        "caution_only_row_count": sum(1 for row in ledger_rows if row["promotion_policy"] == "caution_only_not_for_authoritative_apply"),
        "next_required_step": "Use this ledger for manual review only. First-wave rows can inform draft transporter packet discussion, but authoritative apply stays blocked until direct target-specific packet evidence exists.",
    }
    return {"summary": summary, "rows": ledger_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Candidate Evidence Ledger",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- row_count: `{s['row_count']}`",
        f"- first_wave_row_count: `{s['first_wave_row_count']}`",
        f"- caution_only_row_count: `{s['caution_only_row_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Ledger",
        "",
        "| candidate_name | proposed_packet_step | mechanism_bucket | assay_surface | confidence | review_bucket | anchor |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['candidate_name']}` | `{row['proposed_packet_step']}` | {row['mechanism_bucket']} | {row['assay_surface']} | "
            f"`{row['confidence']}` | `{row['review_bucket']}` | `{row['anchor']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a readable AQP1 candidate evidence ledger from external seed rows.")
    parser.add_argument("--external-seed-json", default=DEFAULT_EXTERNAL_SEED_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.external_seed_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
