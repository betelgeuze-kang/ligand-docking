#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
RUNS = Path("runs")

DEFAULT_QUEUE_JSON = RUNS / "product_scope_breadth_evidence_acquisition_queue_current.json"
DEFAULT_CROSSCHECK_DIR = RUNS / "life_science_skill_crosscheck"
TRANSPORTER_REVIEW_TEMPLATE = RUNS / "transporter_manual_review_intake_template_current.json"
TRANSPORTER_APPLY_GATE = RUNS / "transporter_binder_promotion_gate_current.json"
PXR_REVIEW_TEMPLATE = RUNS / "pxr_exact_evidence_review_intake_template_current.json"
PXR_APPLY_GATE = RUNS / "pxr_blocked_row_promotion_gate_current.json"
GENERAL_REVIEW_TEMPLATE = RUNS / "general_protein_ligand_claim_blocker_packet_current.json"
GENERAL_APPLY_GATE = RUNS / "product_scope_breadth_contract_current.json"
DEFAULT_OUT_JSON = RUNS / "product_scope_breadth_evidence_priority_packet_current.json"
DEFAULT_OUT_CSV = RUNS / "product_scope_breadth_evidence_priority_packet_current.csv"
DEFAULT_OUT_MD = RUNS / "product_scope_breadth_evidence_priority_packet_current.md"

CLAIM_BOUNDARY = (
    "Product scope breadth evidence priority packet only; classifies existing acquisition queue rows against local "
    "crosscheck-file presence and fail-closed claim gates. It does not acquire evidence, authoritatively apply rows, "
    "widen API scope, run docking, promote claims, upload, submit, email, delete, or mutate external state."
)


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
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _tokenize(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", value.lower()) if len(token) >= 3]


def _crosscheck_files(crosscheck_dir: str | Path) -> list[Path]:
    path = _resolve(crosscheck_dir)
    if not path.exists() or not path.is_dir():
        return []
    return sorted(item for item in path.rglob("*") if item.is_file())


def _domain_tokens(row: dict[str, Any]) -> list[str]:
    item_id = _text(row.get("item_id")).lower()
    domain = _text(row.get("domain")).lower()
    if "aqp1" in item_id:
        return ["aqp1", "p29972"]
    if "glut1" in item_id:
        return ["glut1", "p11166", "4pyp"]
    if domain == "pxr":
        return ["pxr", "nr1i2"]
    return []


def _candidate_tokens(row: dict[str, Any]) -> list[str]:
    candidate = _text(row.get("candidate_or_check"))
    tokens = _tokenize(candidate)
    return [token for token in tokens if token not in {"placeholder", "current", "required", "ready", "domain"}]


def _matching_crosscheck_paths(row: dict[str, Any], crosscheck_paths: list[Path], *, limit: int = 6) -> list[str]:
    tokens = _domain_tokens(row) + _candidate_tokens(row)
    if not tokens:
        return []
    matched: list[str] = []
    for path in crosscheck_paths:
        haystack = path.name.lower()
        if any(token in haystack for token in tokens):
            matched.append(path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix())
        if len(matched) >= limit:
            break
    return matched


def _priority_bucket(row: dict[str, Any], local_paths: list[str]) -> str:
    if _text(row.get("item_type")) != "scientific_evidence_request":
        return "claim_gate_waits_on_domain_evidence"
    request_mode = _text(row.get("request_mode"))
    if "review_only" in request_mode or "functional_review_only" in request_mode:
        return "review_only_keep_blocked_until_direct_binding"
    if not local_paths:
        return "external_primary_exact_evidence_required"
    if "negative" in request_mode or "non_binder" in _text(row.get("item_id")):
        return "local_crosscheck_review_present_but_exact_negative_required"
    return "local_crosscheck_review_present_but_exact_quant_required"


def _action_lane(row: dict[str, Any], bucket: str) -> str:
    if bucket == "claim_gate_waits_on_domain_evidence":
        return "defer_until_transporter_and_pxr_green"
    if bucket == "external_primary_exact_evidence_required":
        return "external_scientific_evidence_acquisition"
    if bucket == "review_only_keep_blocked_until_direct_binding":
        return "review_only_guardrail"
    if _text(row.get("domain")) == "transporter":
        return "local_crosscheck_triage_then_exact_source_capture"
    return "local_crosscheck_triage_then_authoritative_reconciliation"


def _acceptance_criteria(row: dict[str, Any], bucket: str) -> str:
    domain = _text(row.get("domain"))
    if bucket == "claim_gate_waits_on_domain_evidence":
        return "Do not alter product/API claim gates until transporter and PXR domain gates are green."
    if domain == "pxr":
        return "Accept only exact human NR1I2/PXR target-pair quantitative evidence strong enough to pass fill-readiness and authoritative reconciliation."
    if "negative" in bucket:
        return "Accept only exact target-pair quantitative negative/non-binder evidence with ligand identity, source, SMILES, scaffold, and claim-safe kcal or explicit inactive value."
    if bucket == "review_only_keep_blocked_until_direct_binding":
        return "Keep review-only unless an exact direct-binding kcal source is curated for the GLUT1 target pair."
    return "Accept only exact target-pair quantitative binder evidence with claim-safe kcal provenance and synchronized reference/split/meta rows."


def _rejection_criteria(row: dict[str, Any], bucket: str) -> str:
    if bucket == "claim_gate_waits_on_domain_evidence":
        return "Reject wording-only broad platform changes while any prerequisite domain is blocked."
    if bucket == "review_only_keep_blocked_until_direct_binding":
        return "Reject functional-only GLUT1 inhibition evidence as an authoritative direct-binding value."
    if _text(row.get("domain")) == "pxr":
        return "Reject generic CYP induction, non-human-only evidence, proxy-only activity, or qualitative mentions that do not resolve exact human PXR quantitative readiness."
    return "Reject docking-only, target-ambiguous, qualitative-only, or replacement rows missing ligand/source/SMILES/scaffold synchronization."


def _next_step(bucket: str) -> str:
    if bucket == "claim_gate_waits_on_domain_evidence":
        return "Wait for domain gates, then rerun the capability surface and general claim blocker packet."
    if bucket == "external_primary_exact_evidence_required":
        return "Acquire or curate a primary exact source before any authoritative apply attempt."
    if bucket == "review_only_keep_blocked_until_direct_binding":
        return "Keep blocked as review-only and search only for exact direct-binding evidence."
    return "Review local crosscheck files, capture exact evidence if present, then rerun the domain-specific intake and reconciliation gates."


def _required_evidence_type(row: dict[str, Any], bucket: str) -> str:
    domain = _text(row.get("domain"))
    request_mode = _text(row.get("request_mode"))
    if bucket == "claim_gate_waits_on_domain_evidence":
        return "domain_gate_green_and_explicit_claim_surface_update"
    if bucket == "review_only_keep_blocked_until_direct_binding":
        return "exact_direct_binding_kcal_or_keep_review_only_guardrail"
    if domain == "pxr":
        return "exact_human_nr1i2_pxr_quantitative_value_with_source_and_target_match"
    if "negative" in request_mode or "non_binder" in _text(row.get("item_id")):
        return "exact_transporter_target_pair_negative_or_inactive_quantitative_value"
    return "exact_transporter_target_pair_quantitative_binder_kcal"


def _review_template_artifact(row: dict[str, Any], bucket: str) -> str:
    domain = _text(row.get("domain"))
    if domain == "transporter":
        return TRANSPORTER_REVIEW_TEMPLATE.as_posix()
    if domain == "pxr":
        return PXR_REVIEW_TEMPLATE.as_posix()
    if bucket == "claim_gate_waits_on_domain_evidence":
        return GENERAL_REVIEW_TEMPLATE.as_posix()
    return ""


def _apply_gate_artifact(row: dict[str, Any], bucket: str) -> str:
    domain = _text(row.get("domain"))
    if domain == "transporter":
        return TRANSPORTER_APPLY_GATE.as_posix()
    if domain == "pxr":
        return PXR_APPLY_GATE.as_posix()
    if bucket == "claim_gate_waits_on_domain_evidence":
        return GENERAL_APPLY_GATE.as_posix()
    return ""


def _regeneration_commands(row: dict[str, Any], bucket: str) -> str:
    domain = _text(row.get("domain"))
    if domain == "transporter":
        return "; ".join(
            [
                "python3 tools/build_transporter_manual_review_intake_template.py",
                "python3 tools/build_transporter_binder_promotion_gate.py",
                "python3 tools/build_transporter_p0_closure_packet.py",
                "python3 tools/build_product_scope_breadth_evidence_acquisition_queue.py",
                "python3 tools/build_product_scope_breadth_evidence_priority_packet.py",
                "python3 tools/build_product_scope_breadth_evidence_intake_readiness.py",
                "python3 tools/build_product_scope_breadth_closure_checklist.py",
            ]
        )
    if domain == "pxr":
        return "; ".join(
            [
                "python3 tools/build_pxr_exact_evidence_review_intake_template.py",
                "python3 tools/build_pxr_blocked_row_promotion_gate.py",
                "python3 tools/build_pxr_authoritative_reconciliation_packet.py",
                "python3 tools/build_product_scope_breadth_evidence_acquisition_queue.py",
                "python3 tools/build_product_scope_breadth_evidence_priority_packet.py",
                "python3 tools/build_product_scope_breadth_evidence_intake_readiness.py",
                "python3 tools/build_product_scope_breadth_closure_checklist.py",
            ]
        )
    if bucket == "claim_gate_waits_on_domain_evidence":
        return "; ".join(
            [
                "python3 tools/build_product_capability_surface_contract.py",
                "python3 tools/build_product_scope_breadth_contract.py",
                "python3 tools/build_general_protein_ligand_claim_blocker_packet.py",
                "python3 tools/build_product_scope_breadth_closure_checklist.py",
            ]
        )
    return ""


def _operator_packet_binding_ready(row: dict[str, Any], bucket: str) -> bool:
    return bool(
        _text(row.get("item_id"))
        and _text(row.get("domain"))
        and _required_evidence_type(row, bucket)
        and _review_template_artifact(row, bucket)
        and _apply_gate_artifact(row, bucket)
        and _regeneration_commands(row, bucket)
    )


def build_payload(
    *,
    queue_payload: dict[str, Any],
    crosscheck_dir: str | Path = DEFAULT_CROSSCHECK_DIR,
    queue_path: str = DEFAULT_QUEUE_JSON.as_posix(),
) -> dict[str, Any]:
    crosscheck_paths = _crosscheck_files(crosscheck_dir)
    rows: list[dict[str, Any]] = []
    for row in _rows(queue_payload):
        local_paths = _matching_crosscheck_paths(row, crosscheck_paths)
        bucket = _priority_bucket(row, local_paths)
        rows.append(
            {
                "priority": _int(row.get("priority")),
                "domain": _text(row.get("domain")),
                "item_id": _text(row.get("item_id")),
                "item_type": _text(row.get("item_type")),
                "candidate_or_check": _text(row.get("candidate_or_check")),
                "evidence_priority_bucket": bucket,
                "action_lane": _action_lane(row, bucket),
                "local_crosscheck_present": bool(local_paths),
                "local_crosscheck_path_count": len(local_paths),
                "local_crosscheck_paths": ";".join(local_paths),
                "request_mode": _text(row.get("request_mode")),
                "acceptance_criteria": _acceptance_criteria(row, bucket),
                "rejection_criteria": _rejection_criteria(row, bucket),
                "next_step": _next_step(bucket),
                "required_evidence_type": _required_evidence_type(row, bucket),
                "review_template_artifact": _review_template_artifact(row, bucket),
                "apply_gate_artifact": _apply_gate_artifact(row, bucket),
                "regeneration_commands": _regeneration_commands(row, bucket),
                "operator_packet_binding_key": f"{_text(row.get('domain'))}:{_text(row.get('item_id'))}",
                "operator_packet_binding_ready": _operator_packet_binding_ready(row, bucket),
                "source_artifact": _text(row.get("source_artifact")) or queue_path,
                "authoritative_apply_allowed": False,
                "scope_promotion_allowed": False,
                "external_state_mutated": False,
            }
        )

    queue_summary = _summary(queue_payload)
    scientific_rows = [row for row in rows if row["item_type"] == "scientific_evidence_request"]
    claim_gate_rows = [row for row in rows if row["evidence_priority_bucket"] == "claim_gate_waits_on_domain_evidence"]
    local_rows = [row for row in scientific_rows if row["local_crosscheck_present"]]
    external_rows = [
        row for row in scientific_rows if row["evidence_priority_bucket"] == "external_primary_exact_evidence_required"
    ]
    review_only_rows = [
        row for row in scientific_rows if row["evidence_priority_bucket"] == "review_only_keep_blocked_until_direct_binding"
    ]
    binding_ready_rows = [row for row in rows if row["operator_packet_binding_ready"]]
    top_row = rows[0] if rows else {}
    summary = {
        "packet_type": "product_scope_breadth_evidence_priority_packet",
        "priority_packet_ready": True,
        "queue_item_count": len(rows),
        "source_queue_item_count": _int(queue_summary.get("queue_item_count")),
        "scientific_evidence_request_count": len(scientific_rows),
        "claim_gate_prerequisite_count": len(claim_gate_rows),
        "local_crosscheck_candidate_count": len(local_rows),
        "external_primary_exact_evidence_required_count": len(external_rows),
        "review_only_keep_blocked_count": len(review_only_rows),
        "operator_packet_binding_ready_count": len(binding_ready_rows),
        "operator_packet_binding_missing_count": len(rows) - len(binding_ready_rows),
        "all_operator_packet_bindings_ready": bool(rows) and len(binding_ready_rows) == len(rows),
        "top_item_id": top_row.get("item_id", ""),
        "top_domain": top_row.get("domain", ""),
        "top_bucket": top_row.get("evidence_priority_bucket", ""),
        "top_required_evidence_type": top_row.get("required_evidence_type", ""),
        "top_review_template_artifact": top_row.get("review_template_artifact", ""),
        "top_apply_gate_artifact": top_row.get("apply_gate_artifact", ""),
        "top_next_step": top_row.get("next_step", ""),
        "open_item_count": len(rows),
        "authoritative_apply_allowed_count": 0,
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
        "source_artifacts": [queue_path, str(crosscheck_dir)],
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Triage local AQP1/GLUT1 crosscheck candidates first, keep review-only rows blocked, and acquire exact primary evidence for PXR and any unmatched transporter rows."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Scope Breadth Evidence Priority Packet",
        "",
        f"- priority_packet_ready: `{s['priority_packet_ready']}`",
        f"- queue_item_count: `{s['queue_item_count']}`",
        f"- scientific_evidence_request_count: `{s['scientific_evidence_request_count']}`",
        f"- claim_gate_prerequisite_count: `{s['claim_gate_prerequisite_count']}`",
        f"- local_crosscheck_candidate_count: `{s['local_crosscheck_candidate_count']}`",
        f"- external_primary_exact_evidence_required_count: `{s['external_primary_exact_evidence_required_count']}`",
        f"- review_only_keep_blocked_count: `{s['review_only_keep_blocked_count']}`",
        f"- all_operator_packet_bindings_ready: `{s['all_operator_packet_bindings_ready']}`",
        f"- operator_packet_binding_missing_count: `{s['operator_packet_binding_missing_count']}`",
        f"- top_item_id: `{s['top_item_id']}`",
        f"- top_required_evidence_type: `{s['top_required_evidence_type']}`",
        f"- top_review_template_artifact: `{s['top_review_template_artifact']}`",
        f"- top_apply_gate_artifact: `{s['top_apply_gate_artifact']}`",
        f"- scope_promotion_allowed: `{s['scope_promotion_allowed']}`",
        "",
        "## Priority Rows",
        "",
        "| priority | domain | item | candidate/check | bucket | evidence type | review template | apply gate | local files | next step |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['domain']}` | `{row['item_id']}` | `{row['candidate_or_check'] or '-'}` | "
            f"`{row['evidence_priority_bucket']}` | `{row['required_evidence_type']}` | "
            f"`{row['review_template_artifact']}` | `{row['apply_gate_artifact']}` | "
            f"{row['local_crosscheck_path_count']} | {row['next_step']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product scope breadth evidence priority packet.")
    parser.add_argument("--queue-json", default=str(DEFAULT_QUEUE_JSON))
    parser.add_argument("--crosscheck-dir", default=str(DEFAULT_CROSSCHECK_DIR))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        queue_payload=_load_json(args.queue_json),
        crosscheck_dir=args.crosscheck_dir,
        queue_path=args.queue_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
