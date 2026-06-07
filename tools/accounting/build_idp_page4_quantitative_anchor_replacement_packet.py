#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PROMOTION_REVIEW_JSON = "runs/idp_page4_anchor_backed_promotion_review_current.json"
DEFAULT_CONFIRMATION_JSON = "runs/idp_page4_anchor_backed_candidate_confirmation_sheet_current.json"
DEFAULT_CITATION_CONFIRMED_JSON = "runs/idp_page4_anchor_citation_confirmed_packet_current.json"
DEFAULT_ANCHOR_CONFIG_JSON = "config/idp_observable_anchors_expanded_v5.json"
DEFAULT_OUT_JSON = "runs/idp_page4_quantitative_anchor_replacement_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_quantitative_anchor_replacement_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_quantitative_anchor_replacement_packet_current.md"


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


def build_payload(
    promotion_review_payload: dict[str, Any],
    confirmation_payload: dict[str, Any],
    citation_confirmed_payload: dict[str, Any],
    anchor_config_payload: dict[str, Any],
) -> dict[str, Any]:
    promotion_s = dict((promotion_review_payload.get("summary") if isinstance(promotion_review_payload.get("summary"), dict) else {}) or {})
    confirmation_s = dict((confirmation_payload.get("summary") if isinstance(confirmation_payload.get("summary"), dict) else {}) or {})
    citation_s = dict((citation_confirmed_payload.get("summary") if isinstance(citation_confirmed_payload.get("summary"), dict) else {}) or {})
    page4_anchor = dict((((anchor_config_payload.get("targets") or {}).get("page4")) if isinstance(anchor_config_payload.get("targets"), dict) else {}) or {})
    provenance = dict((page4_anchor.get("provenance") if isinstance(page4_anchor.get("provenance"), dict) else {}) or {})

    candidate_ready_now = bool(promotion_s.get("anchor_backed_candidate_ready_now", False))
    pending_confirmation_count = int(confirmation_s.get("pending_manual_confirmation_count", 0) or 0)
    current_source = str(page4_anchor.get("source", "")).strip() or "branch_family_provisional"
    current_provenance_kind = str(provenance.get("kind", "")).strip() or "branch_family_prior"
    replacement_completed = (
        candidate_ready_now
        and pending_confirmation_count == 0
        and current_source != "branch_family_provisional"
        and current_provenance_kind != "branch_family_prior"
    )

    quantitative_fields = [
        "rg_mean_range",
        "sasa_proxy_mean_range",
        "contact_persistence_range",
        "transient_helicity_range",
        "ensemble_diversity_range",
    ]
    rows = []
    for field in quantitative_fields:
        if field == "rg_mean_range":
            replacement_status = (
                "direct_literature_range_applied"
                if replacement_completed
                else "direct_literature_range_pending"
            )
            supporting_measurement = "WT-PAGE4 SAXS <Rg> = 36 +/- 1.1 A from Table 1 of the 2018 PAGE4 conformational switching paper."
        elif field == "sasa_proxy_mean_range":
            replacement_status = (
                "proxy_assisted_range_carried_forward_under_literature_partial_anchor"
                if replacement_completed
                else "proxy_assisted_range_pending"
            )
            supporting_measurement = "No construct-matched direct SASA value is frozen yet; keep proxy-assisted baseline range under the literature-curated partial anchor."
        elif field == "contact_persistence_range":
            replacement_status = (
                "proxy_assisted_range_carried_forward_under_literature_partial_anchor"
                if replacement_completed
                else "proxy_assisted_range_pending"
            )
            supporting_measurement = "WT-PAGE4 Table 1 smFRET distances support compact N-terminal loop behavior, but contact persistence remains proxy-assisted until a direct PAGE4 contact anchor is frozen."
        elif field == "transient_helicity_range":
            replacement_status = (
                "proxy_assisted_range_carried_forward_under_literature_partial_anchor"
                if replacement_completed
                else "proxy_assisted_range_pending"
            )
            supporting_measurement = "PAGE4 transient-helix interpretation is literature-backed, but a direct construct-matched helicity percentage is not yet frozen for the baseline anchor."
        else:
            replacement_status = (
                "proxy_assisted_range_carried_forward_under_literature_partial_anchor"
                if replacement_completed
                else "proxy_assisted_range_pending"
            )
            supporting_measurement = "Conformational heterogeneity is literature-backed, but baseline ensemble-diversity remains proxy-assisted until a direct PAGE4 range is frozen."
        rows.append(
            {
                "anchor_field": field,
                "current_value": json.dumps(page4_anchor.get(field, []), ensure_ascii=False),
                "current_source": current_source,
                "replacement_requirement": "construct_matched_quantitative_range_required",
                "supporting_construct_anchor": str(citation_s.get("confirmed_anchor_citation", "PMC3077599 (2011)")).strip() or "PMC3077599 (2011)",
                "replacement_status": replacement_status,
                "supporting_measurement": supporting_measurement,
                "guardrail": "keep ph_low/ph_high literature notes separate from baseline quantitative anchor replacement",
            }
        )

    summary = {
        "status": "page4_quantitative_anchor_replacement_completed_partial_literature_anchor"
        if replacement_completed
        else "page4_quantitative_anchor_replacement_packet_ready"
        if candidate_ready_now and pending_confirmation_count == 0
        else "page4_quantitative_anchor_replacement_packet_pending_candidate_confirmation",
        "target_name": "page4",
        "candidate_ready_now": candidate_ready_now and pending_confirmation_count == 0,
        "pending_manual_confirmation_count": pending_confirmation_count,
        "replacement_completed": replacement_completed,
        "current_anchor_source": current_source,
        "current_anchor_provenance_kind": current_provenance_kind,
        "current_anchor_config_path": DEFAULT_ANCHOR_CONFIG_JSON,
        "quantitative_replacement_row_count": len(rows),
        "direct_literature_field_count": 1 if replacement_completed else 0,
        "proxy_assisted_field_count": 4 if replacement_completed else 0,
        "anchor_backed_target_count_after_replacement": 1 if replacement_completed else 0,
        "broader_rerun_ready": False,
        "next_required_step": (
            "Treat page4 as the first additional anchor-backed target in roster viability, reopen broader shadow review with the same no-override guardrails, and keep broader promotion blocked until one true broader rerun is explicitly reviewed."
            if replacement_completed
            else
            "Replace the provisional page4 anchor ranges in config/idp_observable_anchors_expanded_v5.json with construct-matched quantitative values before counting page4 as an additional anchor-backed target or considering any true broader rerun."
            if candidate_ready_now and pending_confirmation_count == 0
            else "Do not start quantitative anchor replacement until the ph_low and ph_high confirmations are explicit."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Quantitative Anchor Replacement Packet",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- candidate_ready_now: `{s['candidate_ready_now']}`",
        f"- pending_manual_confirmation_count: `{s['pending_manual_confirmation_count']}`",
        f"- replacement_completed: `{s['replacement_completed']}`",
        f"- current_anchor_source: `{s['current_anchor_source']}`",
        f"- current_anchor_provenance_kind: `{s['current_anchor_provenance_kind']}`",
        f"- current_anchor_config_path: `{s['current_anchor_config_path']}`",
        f"- quantitative_replacement_row_count: `{s['quantitative_replacement_row_count']}`",
        f"- direct_literature_field_count: `{s['direct_literature_field_count']}`",
        f"- proxy_assisted_field_count: `{s['proxy_assisted_field_count']}`",
        f"- anchor_backed_target_count_after_replacement: `{s['anchor_backed_target_count_after_replacement']}`",
        f"- broader_rerun_ready: `{s['broader_rerun_ready']}`",
        "",
        "## Quantitative Fields",
        "",
        "| anchor_field | current_source | replacement_requirement | replacement_status | supporting_construct_anchor |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['anchor_field']}` | `{row['current_source']}` | `{row['replacement_requirement']}` | `{row['replacement_status']}` | `{row['supporting_construct_anchor']}` |"
        )
        lines.append("")
        lines.append(f"- Current value: `{row['current_value']}`")
        lines.append(f"- Supporting measurement: {row['supporting_measurement']}")
        lines.append(f"- Guardrail: {row['guardrail']}")
        lines.append("")
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the page4 quantitative anchor replacement packet.")
    parser.add_argument("--promotion-review-json", default=DEFAULT_PROMOTION_REVIEW_JSON)
    parser.add_argument("--confirmation-json", default=DEFAULT_CONFIRMATION_JSON)
    parser.add_argument("--citation-confirmed-json", default=DEFAULT_CITATION_CONFIRMED_JSON)
    parser.add_argument("--anchor-config-json", default=DEFAULT_ANCHOR_CONFIG_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.promotion_review_json),
        _load_json(args.confirmation_json),
        _load_json(args.citation_confirmed_json),
        _load_json(args.anchor_config_json),
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
