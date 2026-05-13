#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
RUNS = Path("runs")

DEFAULT_EXTERNAL_CROSSCHECK_JSON = RUNS / "transporter_external_evidence_crosscheck_current.json"
DEFAULT_NEGATIVE_DIRECT_AUDIT_JSON = RUNS / "aqp1_negative_direct_evidence_audit_packet_current.json"
DEFAULT_NEGATIVE_EXACT_SOURCE_JSON = RUNS / "aqp1_negative_exact_source_outcome_packet_current.json"
DEFAULT_NEGATIVE_CANDIDATE_HARVEST_JSON = RUNS / "transporter_negative_candidate_harvest_current.json"
DEFAULT_NEGATIVE_QUEUE_JSON = RUNS / "transporter_negative_evidence_closure_queue_current.json"
DEFAULT_OUT_JSON = RUNS / "aqp1_negative_evidence_gap_matrix_current.json"
DEFAULT_OUT_CSV = RUNS / "aqp1_negative_evidence_gap_matrix_current.csv"
DEFAULT_OUT_MD = RUNS / "aqp1_negative_evidence_gap_matrix_current.md"

TARGET_ID = "AQP1"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _external_aqp1_row(payload: dict[str, Any], evidence_role: str = "negative_candidate_probe") -> dict[str, Any]:
    for row in payload.get("rows", []) or []:
        if _text(row.get("target_id")) == TARGET_ID and _text(row.get("evidence_role")) == evidence_role:
            return dict(row)
    return {}


def _exact_source_row(payload: dict[str, Any], candidate_name: str) -> dict[str, Any]:
    for row in payload.get("rows", []) or []:
        if _text(row.get("candidate_name")).lower() == candidate_name.lower():
            return dict(row)
    return {}


def _gap_row(
    *,
    rank: int,
    route: str,
    source_artifact: str,
    observation: str,
    exact_target_pair_activity_count: int = 0,
    quantitative_negative_count: int = 0,
    review_context_count: int = 0,
    route_status: str,
    blocker_reason: str,
    closure_requirement: str,
) -> dict[str, Any]:
    evidence_ready = quantitative_negative_count > 0
    return {
        "gap_rank": rank,
        "target_id": TARGET_ID,
        "evidence_route": route,
        "source_artifact": source_artifact,
        "observation": observation,
        "exact_target_pair_activity_count": exact_target_pair_activity_count,
        "quantitative_negative_count": quantitative_negative_count,
        "review_context_count": review_context_count,
        "route_status": route_status,
        "blocker_reason": blocker_reason,
        "closure_requirement": closure_requirement,
        "direct_negative_quantitative_row_found": evidence_ready,
        "authoritative_negative_apply_allowed": False,
        "claim_promotion_allowed": False,
    }


def build_payload(
    external_crosscheck_payload: dict[str, Any],
    negative_direct_audit_payload: dict[str, Any],
    negative_exact_source_payload: dict[str, Any],
    negative_candidate_harvest_payload: dict[str, Any],
    negative_queue_payload: dict[str, Any],
) -> dict[str, Any]:
    external_summary = dict(external_crosscheck_payload.get("summary", {}) or {})
    audit_summary = dict(negative_direct_audit_payload.get("summary", {}) or {})
    exact_source_summary = dict(negative_exact_source_payload.get("summary", {}) or {})
    harvest_summary = dict(negative_candidate_harvest_payload.get("summary", {}) or {})
    queue_summary = dict(negative_queue_payload.get("summary", {}) or {})
    external_probe = _external_aqp1_row(external_crosscheck_payload)
    exact_probe = _exact_source_row(
        negative_exact_source_payload,
        _text(audit_summary.get("primary_candidate")) or "sodium nitroprusside",
    )

    target_chembl_id = _text(external_summary.get("aqp1_chembl_target_id")) or _text(
        audit_summary.get("target_chembl_id")
    )
    target_accession = _text(external_summary.get("aqp1_uniprot_accession")) or _text(
        external_probe.get("target_accession")
    )
    slot_count = _int(queue_summary.get("aqp1_negative_slot_count"))
    if not slot_count:
        slot_count = 3

    rows = [
        _gap_row(
            rank=1,
            route="chembl_exact_target_pair_primary_probe",
            source_artifact="runs/aqp1_negative_direct_evidence_audit_packet_current.md",
            observation=(
                f"{_text(audit_summary.get('primary_candidate')) or 'sodium nitroprusside'} has "
                f"{_int(audit_summary.get('chembl_exact_target_pair_activity_count'))} structured human AQP1 ChEMBL rows."
            ),
            exact_target_pair_activity_count=_int(audit_summary.get("chembl_exact_target_pair_activity_count")),
            quantitative_negative_count=0,
            route_status="exhausted_no_structured_exact_pair_row",
            blocker_reason="no_human_aqp1_exact_target_pair_activity_row",
            closure_requirement="exact human AQP1 target-pair quantitative weak/no-binding row with units and primary source",
        ),
        _gap_row(
            rank=2,
            route="bindingdb_target_affinity_aqp1",
            source_artifact="runs/transporter_external_evidence_crosscheck_current.md",
            observation=(
                f"BindingDB target affinity count for {target_accession or 'AQP1'} is "
                f"{_int(external_summary.get('aqp1_bindingdb_affinity_count'))}."
            ),
            review_context_count=_int(external_summary.get("aqp1_bindingdb_affinity_count")),
            route_status="exhausted_no_bindingdb_target_affinity",
            blocker_reason="no_bindingdb_affinity_rows_for_aqp1_target",
            closure_requirement="BindingDB or equivalent exact AQP1 inactive/weak quantitative affinity row",
        ),
        _gap_row(
            rank=3,
            route="pubmed_exact_ligand_target_context",
            source_artifact="runs/aqp1_negative_direct_evidence_audit_packet_current.md",
            observation=(
                f"PubMed exact ligand/target hits={_int(audit_summary.get('pubmed_exact_ligand_target_hit_count'))}, "
                f"but direct negative quantitative rows={_int(audit_summary.get('direct_negative_quantitative_row_found_count'))}."
            ),
            review_context_count=_int(audit_summary.get("pubmed_exact_ligand_target_hit_count")),
            quantitative_negative_count=_int(audit_summary.get("direct_negative_quantitative_row_found_count")),
            route_status="review_context_only",
            blocker_reason="literature_hits_do_not_contain_curated_direct_quantitative_negative_row",
            closure_requirement="primary literature row with exact molecule, human AQP1 context, quantitative inactive/no-effect threshold",
        ),
        _gap_row(
            rank=4,
            route="pressure_hemolysis_exact_source_anchor",
            source_artifact="runs/aqp1_negative_exact_source_outcome_packet_current.md",
            observation=(
                f"Exact-source endpoint={_text(exact_source_summary.get('source_endpoint'))}; "
                f"primary probe outcome={_text(exact_probe.get('hemolysis_outcome')) or '-'}."
            ),
            review_context_count=_int(exact_source_summary.get("row_count")),
            quantitative_negative_count=_int(exact_source_summary.get("direct_negative_quantitative_row_found_count")),
            route_status="indirect_endpoint_not_authoritative_negative",
            blocker_reason=_text(exact_source_summary.get("promotion_gate_failed_reason"))
            or "not_a_direct_transporter_specific_quantitative_negative_binding_or_flux_row",
            closure_requirement="direct transporter-specific binding, permeability, flux, or channel assay row with negative semantics",
        ),
        _gap_row(
            rank=5,
            route="chembl_target_level_candidate_harvest",
            source_artifact="runs/transporter_negative_candidate_harvest_current.md",
            observation=(
                f"AQP1 target-level review rows={_int(harvest_summary.get('aqp1_candidate_review_row_count'))}, "
                f"quantitative lower-bound candidates={_int(harvest_summary.get('aqp1_quantitative_lower_bound_candidate_count'))}."
            ),
            review_context_count=_int(harvest_summary.get("aqp1_candidate_review_row_count")),
            quantitative_negative_count=_int(harvest_summary.get("aqp1_quantitative_lower_bound_candidate_count")),
            route_status="review_rows_available_no_quantitative_lower_bound",
            blocker_reason="target_level_rows_are_nonquantitative_or_outlier_review_only",
            closure_requirement="curated AQP1 lower-bound Kd/Ki/IC50/functional no-effect row, not just Not Active/comment/outlier context",
        ),
    ]

    direct_negative_count = sum(_int(row["quantitative_negative_count"]) for row in rows)
    apply_count = sum(1 for row in rows if _bool(row["authoritative_negative_apply_allowed"]))
    summary = {
        "gap_matrix_ready": True,
        "packet_artifact": "runs/aqp1_negative_evidence_gap_matrix_current.md",
        "target_id": TARGET_ID,
        "target_uniprot_accession": target_accession,
        "target_chembl_id": target_chembl_id,
        "negative_slot_count": slot_count,
        "evidence_route_count": len(rows),
        "blocked_route_count": sum(1 for row in rows if not _bool(row["direct_negative_quantitative_row_found"])),
        "review_context_route_count": sum(1 for row in rows if _int(row["review_context_count"]) > 0),
        "direct_negative_quantitative_row_found_count": direct_negative_count,
        "authoritative_negative_apply_allowed_count": apply_count,
        "negative_slot_cover_ready_count": min(slot_count, direct_negative_count),
        "negative_slot_cover_missing_count": max(0, slot_count - direct_negative_count),
        "claim_promotion_allowed": False,
        "gap_status": "aqp1_direct_negative_quantitative_evidence_absent",
        "commercialization_blocker": "hard_blocker_for_broad_transporter_claim",
        "next_required_step": (
            "AQP1 negative closure now needs new exact target-pair quantitative evidence, not more reinterpretation of existing "
            "review-only context. Acceptable closure is a public or internal primary-source row with exact human AQP1 target, exact molecule, "
            "negative/weak/no-effect quantitative semantics, assay context, units, and split/reference metadata."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Evidence Gap Matrix",
        "",
        f"- gap_matrix_ready: `{s['gap_matrix_ready']}`",
        f"- target_id: `{s['target_id']}`",
        f"- target_uniprot_accession: `{s['target_uniprot_accession']}`",
        f"- target_chembl_id: `{s['target_chembl_id']}`",
        f"- negative_slot_count: `{s['negative_slot_count']}`",
        f"- evidence_route_count: `{s['evidence_route_count']}`",
        f"- blocked_route_count: `{s['blocked_route_count']}`",
        f"- review_context_route_count: `{s['review_context_route_count']}`",
        f"- direct_negative_quantitative_row_found_count: `{s['direct_negative_quantitative_row_found_count']}`",
        f"- authoritative_negative_apply_allowed_count: `{s['authoritative_negative_apply_allowed_count']}`",
        f"- negative_slot_cover: `{s['negative_slot_cover_ready_count']}/{s['negative_slot_count']}`",
        f"- negative_slot_cover_missing_count: `{s['negative_slot_cover_missing_count']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        f"- gap_status: `{s['gap_status']}`",
        f"- commercialization_blocker: `{s['commercialization_blocker']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Evidence Routes",
        "",
        "| rank | route | status | quantitative_negative_count | review_context_count | blocker_reason | closure_requirement |",
        "| ---: | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['gap_rank']} | `{row['evidence_route']}` | `{row['route_status']}` | "
            f"{row['quantitative_negative_count']} | {row['review_context_count']} | "
            f"`{row['blocker_reason']}` | `{row['closure_requirement']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1 negative-evidence gap matrix.")
    parser.add_argument("--external-crosscheck-json", default=str(DEFAULT_EXTERNAL_CROSSCHECK_JSON))
    parser.add_argument("--negative-direct-audit-json", default=str(DEFAULT_NEGATIVE_DIRECT_AUDIT_JSON))
    parser.add_argument("--negative-exact-source-json", default=str(DEFAULT_NEGATIVE_EXACT_SOURCE_JSON))
    parser.add_argument("--negative-candidate-harvest-json", default=str(DEFAULT_NEGATIVE_CANDIDATE_HARVEST_JSON))
    parser.add_argument("--negative-queue-json", default=str(DEFAULT_NEGATIVE_QUEUE_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.external_crosscheck_json),
        _load_json(args.negative_direct_audit_json),
        _load_json(args.negative_exact_source_json),
        _load_json(args.negative_candidate_harvest_json),
        _load_json(args.negative_queue_json),
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
