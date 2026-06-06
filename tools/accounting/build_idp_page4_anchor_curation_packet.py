#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_QUEUE_JSON = "runs/idp_anchor_curation_queue_current.json"
DEFAULT_ANCHORS_JSON = "config/idp_observable_anchors_expanded_v5.json"
DEFAULT_FAILURE_JSON = "runs/idp_fold19_page4_failure_analysis_current.json"
DEFAULT_SHADOW_JSON = "runs/idp_page4_feature_state_v1_shadow_current_summary.json"
DEFAULT_EVIDENCE_SEED_JSON = "runs/idp_page4_anchor_evidence_seed_current.json"
DEFAULT_CITATION_CONFIRMED_JSON = "runs/idp_page4_anchor_citation_confirmed_packet_current.json"
DEFAULT_PHOSPHO_FOLLOWUP_JSON = "runs/idp_page4_phosphorylation_followup_packet_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_anchor_curation_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_anchor_curation_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_anchor_curation_packet_current.md"


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


def _maybe_load_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(
    queue_payload: dict[str, Any],
    anchors_payload: dict[str, Any],
    failure_payload: dict[str, Any],
    shadow_payload: dict[str, Any],
    evidence_seed_payload: dict[str, Any] | None = None,
    citation_confirmed_payload: dict[str, Any] | None = None,
    phosphorylation_followup_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    queue_rows = [dict(row) for row in queue_payload.get("rows", []) or []]
    queue_row = next((row for row in queue_rows if str(row.get("target_name", "")).strip() == "page4"), {})
    page4_meta = dict((((anchors_payload.get("targets") or {}) if isinstance(anchors_payload.get("targets"), dict) else {}) or {}).get("page4", {}) or {})
    provenance = dict((page4_meta.get("provenance") if isinstance(page4_meta.get("provenance"), dict) else {}) or {})
    failure_s = dict((failure_payload.get("summary") if isinstance(failure_payload.get("summary"), dict) else {}) or {})
    kalman_s = dict((shadow_payload.get("kalman_shadow") if isinstance(shadow_payload.get("kalman_shadow"), dict) else {}) or {})
    evidence_seed_s = dict((((evidence_seed_payload or {}).get("summary")) if isinstance((evidence_seed_payload or {}).get("summary"), dict) else {}) or {})
    citation_s = dict((((citation_confirmed_payload or {}).get("summary")) if isinstance((citation_confirmed_payload or {}).get("summary"), dict) else {}) or {})
    followup_s = dict((((phosphorylation_followup_payload or {}).get("summary")) if isinstance((phosphorylation_followup_payload or {}).get("summary"), dict) else {}) or {})
    provenance_fill_value = ""
    provenance_fill_risk = "candidate_anchor_citation_missing"
    provenance_fill_action = "fill candidate_anchor_citation, construct_mapping, and condition_mapping before any promotion decision"
    if citation_s:
        provenance_fill_value = (
            f"confirmed citation={str(citation_s.get('confirmed_anchor_citation', '')).strip()}; "
            f"confirmed construct_mapping={str(citation_s.get('construct_mapping', '')).strip()}; "
            f"followup={str(citation_s.get('followup_source_anchors', '')).strip()}"
        )
        provenance_fill_risk = "construct_citation_confirmed_state_specific_followup_required"
        provenance_fill_action = "use the phosphorylation-state follow-up sources to separate ph_low/ph_high before any anchor replacement"
    elif evidence_seed_s:
        residue_count = int(evidence_seed_s.get("residue_count", 0) or 0)
        provenance_fill_value = (
            f"draft citation={str(evidence_seed_s.get('first_open_source_anchor', '')).strip()}; "
            f"draft construct_mapping=synthetic page4 -> PAGE4 full_length_{residue_count}aa candidate; "
            "draft condition_mapping=baseline_disorder_identity primary; phosphorylation-state follow-up required for ph_low/ph_high"
        )
        provenance_fill_risk = "draft_not_frozen_state_specific_followup_required"
        provenance_fill_action = "validate the PAGE4 construct alias first, then use the phosphorylation-state follow-up sources before any anchor replacement"

    rows = [
        {
            "evidence_item": "replacement_anchor_provenance",
            "current_value": provenance_fill_value,
            "risk_signal": provenance_fill_risk,
            "next_action": provenance_fill_action,
        },
        {
            "evidence_item": "current_anchor_source",
            "current_value": str(page4_meta.get("source", "")).strip(),
            "risk_signal": "provisional_only_branch_prior",
            "next_action": "replace with construct-matched literature or experimental anchor provenance",
        },
        {
            "evidence_item": "provenance_kind",
            "current_value": str(provenance.get("kind", "")).strip(),
            "risk_signal": "not_construct_matched",
            "next_action": "capture explicit citation, construct mapping, and condition relevance",
        },
        {
            "evidence_item": "rg_mean_range",
            "current_value": str(page4_meta.get("rg_mean_range", "")),
            "risk_signal": f"current_rg_anchor_error={failure_s.get('current_rg_anchor_error', '')}",
            "next_action": "seek condition-aware compactness/rg anchor from literature-grade source",
        },
        {
            "evidence_item": "sasa_proxy_range",
            "current_value": str(page4_meta.get("sasa_proxy_mean_range", "")),
            "risk_signal": "provisional_sasa_proxy_range",
            "next_action": "seek construct-matched exposure/compaction signal if available",
        },
        {
            "evidence_item": "branch_state_pattern",
            "current_value": "helix_enriched / helix_tad across current provisional rows",
            "risk_signal": f"regressed_conditions={failure_s.get('regressed_conditions', [])}",
            "next_action": "verify whether branch/state prior is actually supported by external anchor evidence",
        },
        {
            "evidence_item": "shadow_behavior",
            "current_value": (
                f"target_count={shadow_payload.get('target_count', 0)}; provisional_anchor_row_count={kalman_s.get('provisional_anchor_row_count', 0)}; "
                f"smoothed_feature_count={kalman_s.get('smoothed_feature_count', 0)}; would_change_state_count={kalman_s.get('would_change_state_count', 0)}"
            ),
            "risk_signal": "provisional_anchor_abstain_only",
            "next_action": "keep shadow abstain behavior until page4 graduates from provisional-only to anchor-backed",
        },
    ]

    summary = {
        "status": "page4_anchor_curation_packet_ready",
        "target_name": "page4",
        "priority_band": str(queue_row.get("priority_band", "")).strip(),
        "artifact_reference_count": int(queue_row.get("artifact_reference_count", 0) or 0),
        "source_class": str(page4_meta.get("source", "")).strip(),
        "provenance_kind": str(provenance.get("kind", "")).strip(),
        "provenance_citation": str(provenance.get("citation", "")).strip(),
        "provisional_condition_count": int(shadow_payload.get("target_count", 0) or 0),
        "shadow_abstain_expected": int(kalman_s.get("smoothed_feature_count", 0) or 0) == 0,
        "failure_mechanism": str(failure_s.get("likely_failure_mechanism", "")).strip(),
        "current_wrong_conditions": list(failure_s.get("current_wrong_conditions", []) or []),
        "evidence_search_target": "page4 construct-matched literature or experimental anchor evidence for compactness, aggregation, and branch-state interpretation",
        "evidence_seed_ready": bool(evidence_seed_s),
        "evidence_seed_artifact": "runs/idp_page4_anchor_evidence_seed_current.md" if evidence_seed_s else "",
        "provenance_fill_draft_artifact": "runs/idp_page4_anchor_provenance_fill_draft_current.md" if evidence_seed_s else "",
        "citation_confirmed_packet_artifact": "runs/idp_page4_anchor_citation_confirmed_packet_current.md" if citation_s else "",
        "phosphorylation_followup_packet_artifact": "runs/idp_page4_phosphorylation_followup_packet_current.md" if followup_s else "",
        "first_open_source_anchor": str(evidence_seed_s.get("first_open_source_anchor", "")).strip(),
        "first_open_source_url": str(evidence_seed_s.get("first_open_source_url", "")).strip(),
        "next_required_step": (
            "Use page4 as the first anchor-curation target, open the page4 phosphorylation-state follow-up packet first, then use the state-specific follow-up sources before any anchor replacement, "
            "and keep page4 out of any true broader roster until provenance is explicit and anchor-backed."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Anchor Curation Packet",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- priority_band: `{s['priority_band']}`",
        f"- artifact_reference_count: `{s['artifact_reference_count']}`",
        f"- source_class: `{s['source_class']}`",
        f"- provenance_kind: `{s['provenance_kind']}`",
        f"- provisional_condition_count: `{s['provisional_condition_count']}`",
        f"- shadow_abstain_expected: `{s['shadow_abstain_expected']}`",
        f"- evidence_search_target: `{s['evidence_search_target']}`",
        f"- evidence_seed_ready: `{s['evidence_seed_ready']}`",
        f"- evidence_seed_artifact: `{s['evidence_seed_artifact']}`",
        f"- provenance_fill_draft_artifact: `{s['provenance_fill_draft_artifact']}`",
        f"- citation_confirmed_packet_artifact: `{s['citation_confirmed_packet_artifact']}`",
        f"- phosphorylation_followup_packet_artifact: `{s['phosphorylation_followup_packet_artifact']}`",
        f"- first_open_source_anchor: `{s['first_open_source_anchor']}`",
        "",
        "## Current Risk",
        "",
        f"- {s['failure_mechanism']}",
        f"- provenance_citation: `{s['provenance_citation']}`",
        f"- current_wrong_conditions: `{', '.join(s['current_wrong_conditions'])}`",
        f"- first_open_source_url: `{s['first_open_source_url']}`",
        "",
        "## Evidence Checklist",
        "",
        "| evidence_item | current_value | risk_signal | next_action |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['evidence_item']}` | `{row['current_value']}` | `{row['risk_signal']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the first-wave page4 anchor curation packet for IDP.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--anchors-json", default=DEFAULT_ANCHORS_JSON)
    parser.add_argument("--failure-json", default=DEFAULT_FAILURE_JSON)
    parser.add_argument("--shadow-json", default=DEFAULT_SHADOW_JSON)
    parser.add_argument("--evidence-seed-json", default=DEFAULT_EVIDENCE_SEED_JSON)
    parser.add_argument("--citation-confirmed-json", default=DEFAULT_CITATION_CONFIRMED_JSON)
    parser.add_argument("--phosphorylation-followup-json", default=DEFAULT_PHOSPHO_FOLLOWUP_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.queue_json),
        _load_json(args.anchors_json),
        _load_json(args.failure_json),
        _load_json(args.shadow_json),
        _maybe_load_json(args.evidence_seed_json),
        _maybe_load_json(args.citation_confirmed_json),
        _maybe_load_json(args.phosphorylation_followup_json),
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
