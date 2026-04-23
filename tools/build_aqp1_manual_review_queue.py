#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKBOOK_CSV = "runs/aqp1_packet_replacement_workbook_current.csv"
DEFAULT_EXTERNAL_SEED_JSON = "runs/aqp1_external_evidence_seed_current.json"
DEFAULT_QUANTITATIVE_PROVENANCE_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_manual_review_queue_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_manual_review_queue_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_manual_review_queue_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


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


def _index_by_step(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in rows
        if str(row.get("packet_step", "")).strip()
    }


def _classify(row: dict[str, str], provenance_row: dict[str, Any] | None = None) -> dict[str, str]:
    provenance_row = provenance_row or {}
    is_binder = str(row.get("replacement_is_binder", "")).strip() == "1"
    if is_binder:
        provenance_status = str(provenance_row.get("public_provenance_status", "")).strip()
        if provenance_status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
            return {
                "review_bucket": "defer_exact_human_activity_nonbinding",
                "promotion_blocker": "no_claim_safe_aqp1_binding_kcal_curated",
                "next_required_action": "carry_exact_human_activity_provenance_keep_kcal_blank",
                "recommended_resolution": "keep_review_only_exact_human_activity_present_nonbinding",
                "notes": (
                    "Exact human AQP1 quantitative activity is publicly traceable for this candidate, "
                    "but it is still a nonbinding functional/activity lane rather than a claim-safe binding-kcal source."
                ),
            }
        return {
            "review_bucket": "defer_pending_target_specific_evidence",
            "promotion_blocker": "no_local_aqp1_binder_evidence_curated",
            "next_required_action": "manual_curated_search_or_defer",
            "recommended_resolution": "keep_draft_only_until_transporter_specific_binder_evidence_is_curated",
            "notes": "AQP1 binder slots remain draft-only until transporter-specific small-molecule evidence is locally curated.",
        }
    return {
        "review_bucket": "review_only_negative_evidence",
        "promotion_blocker": "no_quantitative_transporter_negative_evidence_curated",
        "next_required_action": "manual_negative_evidence_review",
        "recommended_resolution": "keep_review_only_until_negative_evidence_is_curated",
        "notes": "AQP1 negative-like slots should stay review-only; do not inject proxy non-binder values.",
        }


def build_payload(
    rows: list[dict[str, str]],
    external_seed: dict[str, Any] | None = None,
    quantitative_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    seed_lookup: dict[str, dict[str, Any]] = {}
    for seed_row in (external_seed or {}).get("rows", []) or []:
        key = str(seed_row.get("proposed_packet_step", "")).strip()
        if key:
            seed_lookup[key] = dict(seed_row)
    provenance_lookup = _index_by_step((quantitative_provenance or {}).get("rows", []) or [])
    queue_rows: list[dict[str, Any]] = []
    review_only_negative_count = 0
    defer_count = 0
    exact_human_activity_binder_count = 0
    for idx, row in enumerate(rows, start=1):
        packet_step = str(row.get("packet_step", "")).strip()
        provenance_row = provenance_lookup.get(packet_step, {})
        classification = _classify(row, provenance_row)
        seed_row = seed_lookup.get(str(row.get("packet_step", "")).strip(), {})
        if classification["review_bucket"] == "review_only_negative_evidence":
            review_only_negative_count += 1
        else:
            defer_count += 1
        if str(provenance_row.get("public_provenance_status", "")).strip() == "exact_human_aqp1_quantitative_activity_present_nonbinding":
            exact_human_activity_binder_count += 1
        queue_rows.append(
            {
                "priority_rank": idx,
                "packet": str(row.get("packet", "")).strip(),
                "packet_step": packet_step,
                "current_ligand_id": str(row.get("current_ligand_id", "")).strip(),
                "replacement_is_binder": str(row.get("replacement_is_binder", "")).strip(),
                "required_missing_fields": str(row.get("required_missing_fields", "")).strip(),
                "suggested_external_candidate": str(seed_row.get("candidate_name", "")).strip(),
                "suggested_external_review_bucket": str(seed_row.get("recommended_review_bucket", "")).strip(),
                "suggested_external_source_anchor": str(seed_row.get("source_anchor", "")).strip(),
                "public_provenance_status": str(provenance_row.get("public_provenance_status", "")).strip(),
                "public_provenance_signal": str(provenance_row.get("public_provenance_signal", "")).strip(),
                "state_change_potential": str(provenance_row.get("state_change_potential", "")).strip(),
                "chembl_activity_record_count": str(provenance_row.get("chembl_activity_record_count", "")).strip(),
                "chembl_best_activity_type": str(provenance_row.get("chembl_best_activity_type", "")).strip(),
                "chembl_best_activity_value": str(provenance_row.get("chembl_best_activity_value", "")).strip(),
                "chembl_best_activity_units": str(provenance_row.get("chembl_best_activity_units", "")).strip(),
                **classification,
            }
        )
    return {
        "summary": {
            "family": "aqp1",
            "row_count": len(queue_rows),
            "review_only_negative_count": review_only_negative_count,
            "defer_binder_count": defer_count,
            "exact_human_activity_binder_count": exact_human_activity_binder_count,
            "policy_fixed_pending_count": len(queue_rows),
            "next_required_step": (
                "Keep all AQP1 rows out of authoritative apply; carry AqB013 as exact human AQP1 target-activity provenance while still leaving replacement_reference_binding_kcal_mol blank, and keep the remaining binder slots plus all non-binder slots review-only."
                if exact_human_activity_binder_count > 0
                else "Keep all AQP1 rows out of authoritative apply; curate transporter-specific binder evidence for binder slots and review-only negative evidence for non-binder slots."
            ),
        },
        "rows": queue_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# AQP1 Manual Review Queue",
        "",
        f"- family: `{payload['summary']['family']}`",
        f"- row_count: `{payload['summary']['row_count']}`",
        f"- review_only_negative_count: `{payload['summary']['review_only_negative_count']}`",
        f"- defer_binder_count: `{payload['summary']['defer_binder_count']}`",
        f"- exact_human_activity_binder_count: `{payload['summary']['exact_human_activity_binder_count']}`",
        f"- policy_fixed_pending_count: `{payload['summary']['policy_fixed_pending_count']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Queue",
        "",
        "| priority_rank | packet_step | current_ligand_id | binder | review_bucket | public_provenance_status | suggested_external_candidate | next_required_action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | {row['packet_step']} | `{row['current_ligand_id']}` | {row['replacement_is_binder']} | `{row['review_bucket']}` | "
            f"`{row['public_provenance_status'] or '-'}` | `{row['suggested_external_candidate']}` | `{row['next_required_action']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1 draft/manual-review queue from the replacement workbook.")
    parser.add_argument("--workbook-csv", default=DEFAULT_WORKBOOK_CSV)
    parser.add_argument("--external-seed-json", default=DEFAULT_EXTERNAL_SEED_JSON)
    parser.add_argument("--quantitative-provenance-json", default=DEFAULT_QUANTITATIVE_PROVENANCE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = _read_csv(_resolve(args.workbook_csv))
    payload = build_payload(
        rows,
        _load_json(args.external_seed_json),
        _load_json(args.quantitative_provenance_json),
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
