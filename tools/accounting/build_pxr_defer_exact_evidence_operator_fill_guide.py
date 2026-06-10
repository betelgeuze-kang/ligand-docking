#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.accounting.build_pxr_exact_evidence_review_intake_template import ASSAY_PLACEHOLDER
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_COMMIT_JSON = RUNS / "pxr_pending_resolution_commit_packet_current.json"
DEFAULT_OUT_GUIDE_MD = RUNS / "pxr_defer_exact_evidence_operator_fill_guide_current.md"
DEFAULT_OUT_INTAKE_CSV = RUNS / "pxr_defer_exact_evidence_intake_supplement_current.csv"
DEFAULT_OUT_JSON = RUNS / "pxr_defer_exact_evidence_operator_fill_guide_current.json"

DEFER_OPERATOR_GUIDANCE: dict[str, dict[str, str]] = {
    "core_eval_non_binder_01": {
        "candidate_name": "acetaminophen",
        "required_evidence_mode": "resolve_activity_proxy_conflict_or_keep_deferred",
        "operator_note": (
            "Human NR1I2/PXR activity proxy conflicts with non-binder label. "
            "Only fill exact kcal if operator-verified direct human PXR binding disproves activation; "
            "otherwise KEEP_DEFERRED and leave kcal blank."
        ),
    },
    "core_eval_non_binder_02": {
        "candidate_name": "caffeine",
        "required_evidence_mode": "resolve_activity_proxy_conflict_or_keep_deferred",
        "operator_note": (
            "Target-specific human PXR activity exists; absence of contradiction is not enough. "
            "Provide orthogonal exact NR1I2/PXR evidence or KEEP_DEFERRED."
        ),
    },
    "ood_fit_binder_01": {
        "candidate_name": "bexarotene",
        "required_evidence_mode": "upgrade_supportive_binder_to_claim_safe_or_keep_deferred",
        "operator_note": (
            "Supportive qHTS activity (AID 1346982) is not claim-safe direct binding. "
            "Fill exact Kd/IC50-derived kcal with PMID/DOI only after manual confirmation; "
            "otherwise KEEP_DEFERRED."
        ),
    },
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_intake_rows(commit_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for commit in commit_rows:
        if str(commit.get("manual_commit_class", "")).strip() != "must_remain_deferred":
            continue
        packet_step = str(commit.get("packet_step", "")).strip()
        guidance = DEFER_OPERATOR_GUIDANCE.get(packet_step, {})
        rows.append(
            {
                "review_row_id": f"pxr_defer_review_{packet_step}",
                "packet_step": packet_step,
                "candidate_name": guidance.get("candidate_name", str(commit.get("ligand", "")).strip()),
                "current_label": "binder" if str(commit.get("binder", "")).strip() == "1" else "non_binder",
                "target_gene": "NR1I2",
                "target_alias": "PXR",
                "target_species": "Homo sapiens",
                "required_evidence_mode": guidance.get(
                    "required_evidence_mode", "resolve_activity_proxy_conflict_or_keep_deferred"
                ),
                "target_match_confirmed": "false",
                "replacement_reference_binding_kcal_mol": "KEEP_BLOCKED",
                "replacement_source_url_or_doi": "KEEP_BLOCKED",
                "assay_type_and_endpoint": ASSAY_PLACEHOLDER,
                "assay_is_direct_or_claim_safe": "false",
                "conflict_resolution_decision": "KEEP_DEFERRED",
                "review_decision": "KEEP_BLOCKED",
                "authoritative_apply_requested": "false",
                "reviewer_notes": guidance.get("operator_note", str(commit.get("manual_commit_note", "")).strip()),
                "manual_promotion_blocker": str(commit.get("manual_promotion_blocker", "")).strip(),
                "manual_commit_class": "must_remain_deferred",
            }
        )
    return rows


def build_payload(commit_packet: dict[str, Any]) -> dict[str, Any]:
    commit_rows = [dict(row) for row in commit_packet.get("rows", []) or [] if isinstance(row, dict)]
    intake_rows = build_intake_rows(commit_rows)
    summary = {
        "packet_type": "pxr_defer_exact_evidence_operator_fill_guide",
        "status": "pxr_defer_exact_evidence_operator_fill_guide_ready" if intake_rows else "blocked_pxr_defer_exact_evidence_operator_fill_guide",
        "defer_row_count": len(intake_rows),
        "operator_fill_policy": "KEEP_DEFERRED_or_exact_evidence_only",
        "kcal_policy": "never_fill_from_activity_proxy_without_direct_claim_safe_source",
        "next_required_step": (
            "Use the supplement CSV as the operator reference while filling exact-review intake; "
            "rerun PXR exact-review and scope breadth gates after any claim-safe upgrade."
            if intake_rows
            else "Regenerate PXR pending resolution commit packet before building defer operator fill guide."
        ),
    }
    return {"summary": summary, "rows": intake_rows}


def _write_guide_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# PXR Defer Exact Evidence Operator Fill Guide",
        "",
        f"- defer_row_count: `{payload['summary']['defer_row_count']}`",
        f"- operator_fill_policy: `{payload['summary']['operator_fill_policy']}`",
        "",
        "## How to fill",
        "",
        "1. Open `runs/pxr_exact_evidence_review_intake_template_current.csv` after regeneration.",
        "2. For each defer row below, either:",
        "   - **KEEP_DEFERRED / KEEP_BLOCKED**: leave kcal blank; document proxy conflict in reviewer_notes.",
        "   - **Resolve with exact evidence**: fill human NR1I2/PXR Kd/IC50-derived kcal, exact PMID/DOI, assay endpoint, and set `assay_is_direct_or_claim_safe=true` only when claim-safe.",
        "3. Never promote from PubChem qHTS potency alone.",
        "4. Rerun: `build_pxr_exact_evidence_review_intake_template` → blocked gate → reconciliation → scope contract.",
        "",
        "## Defer rows",
        "",
    ]
    for row in payload["rows"]:
        lines.extend(
            [
                f"### `{row['packet_step']}` — {row['candidate_name']}",
                "",
                f"- current_label: `{row['current_label']}`",
                f"- required_evidence_mode: `{row['required_evidence_mode']}`",
                f"- conflict_resolution_decision: `{row['conflict_resolution_decision']}`",
                f"- replacement_reference_binding_kcal_mol: `{row['replacement_reference_binding_kcal_mol']}`",
                f"- replacement_source_url_or_doi: `{row['replacement_source_url_or_doi']}`",
                f"- reviewer_notes: {row['reviewer_notes']}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PXR defer exact-evidence operator fill guide and supplement intake.")
    parser.add_argument("--commit-json", default=str(DEFAULT_COMMIT_JSON))
    parser.add_argument("--out-guide-md", default=str(DEFAULT_OUT_GUIDE_MD))
    parser.add_argument("--out-intake-csv", default=str(DEFAULT_OUT_INTAKE_CSV))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(_read_json(_resolve(args.commit_json)))
    out_json = _resolve(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(_resolve(args.out_intake_csv), payload["rows"])
    _write_guide_md(_resolve(args.out_guide_md), payload)


if __name__ == "__main__":
    main()
