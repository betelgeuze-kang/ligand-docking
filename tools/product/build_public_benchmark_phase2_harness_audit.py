#!/usr/bin/env python3
"""Build the Phase 2 public benchmark harness audit.

Read-only: this audit re-materializes the product-doc Phase 2 benchmark
requirements from current public benchmark artifacts. It distinguishes the
required Vina/GNINA comparison adapter contract from optional comparator score
evidence, so the beta-readiness surface does not silently overclaim.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONTRACT_JSON = "runs/product_public_benchmark_contract_current.json"
DEFAULT_OUT_JSON = "runs/public_benchmark_phase2_harness_audit_current.json"
DEFAULT_OUT_MD = "runs/public_benchmark_phase2_harness_audit_current.md"
DEFAULT_OUT_CSV = "runs/public_benchmark_phase2_harness_audit_current.csv"

PACKET_TYPE = "public_benchmark_phase2_harness_audit"
SCHEMA_VERSION = "public_benchmark_phase2_harness_audit_v1"

REQUIREMENT_ORDER = (
    "casf_pdbbind_pose_success_harness",
    "symmetry_aware_ligand_rmsd",
    "posebusters_style_validity_checks",
    "vina_gnina_comparison_adapter",
    "dude_or_lit_pcba_enrichment",
)

CLAIM_BOUNDARY = (
    "Public benchmark Phase 2 harness audit only; it reads current local benchmark contract and execution "
    "summaries to verify the product-doc Phase 2 harness requirements. It does not download datasets, run "
    "docking, run Vina/GNINA, compute new metrics, submit predictions, deploy, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "docking_results_emitted": False,
    "claim_promotion_allowed": False,
}

_CSV_COLUMNS = [
    "requirement_id",
    "status",
    "ready",
    "evidence",
    "blocker",
    "requirement_kind",
    "source_contract_status",
    "source_contract_phase2_ready",
    "source_contract_json",
    "notes",
    "execution_enabled",
    "external_state_mutated",
    "docking_results_emitted",
    "claim_promotion_allowed",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    text = _text(path_like)
    if not text:
        return ""
    if ";" in text:
        return ";".join(_display(part) for part in text.split(";"))
    path = Path(text)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return text


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "ready"}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _requirements_by_id(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = contract.get("phase2_requirements")
    if not isinstance(rows, list):
        return {}
    return {
        _text(row.get("requirement_id")): row
        for row in rows
        if isinstance(row, dict) and _text(row.get("requirement_id"))
    }


def _row(
    requirement_id: str,
    requirement: dict[str, Any],
    *,
    summary: dict[str, Any],
    contract_json: Path,
) -> dict[str, Any]:
    ready = bool(requirement.get("ready") is True)
    blocker = _text(requirement.get("blocker"))
    evidence = _text(requirement.get("evidence"))
    notes = ""
    requirement_kind = "phase2_required"
    if requirement_id == "vina_gnina_comparison_adapter":
        score_evidence_ready = bool(summary.get("vina_gnina_comparison_adapter_score_evidence_ready") is True)
        adapter_status = _text(summary.get("vina_gnina_comparison_adapter_status"))
        notes = (
            f"adapter_contract_status={adapter_status or 'missing'};"
            f"comparison_score_evidence_ready={str(score_evidence_ready).lower()};"
            "score_evidence_required_for_phase2=false"
        )
        requirement_kind = "phase2_required_adapter_contract"
    elif requirement_id == "dude_or_lit_pcba_enrichment":
        notes = f"ready_sources={_text(summary.get('phase2_enrichment_ready_sources')) or 'missing'}"
    elif requirement_id == "casf_pdbbind_pose_success_harness":
        notes = (
            f"pose_success_rate={summary.get('pdbbind_pose_success_rate')};"
            f"threshold={summary.get('pdbbind_pose_success_threshold')}"
        )
    elif requirement_id == "symmetry_aware_ligand_rmsd":
        notes = f"coverage={summary.get('pdbbind_symmetry_aware_ligand_rmsd_coverage')}"
    elif requirement_id == "posebusters_style_validity_checks":
        notes = f"posebusters_valid_rate={summary.get('pdbbind_posebusters_valid_rate')}"
    if not requirement:
        ready = False
        blocker = "phase2_requirement_row_missing"
    return {
        "requirement_id": requirement_id,
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "evidence": _display(evidence),
        "blocker": blocker,
        "requirement_kind": requirement_kind,
        "source_contract_status": _text(summary.get("status")),
        "source_contract_phase2_ready": bool(summary.get("phase2_public_benchmark_harness_ready") is True),
        "source_contract_json": _display(contract_json),
        "notes": notes,
        **_READ_ONLY_FLAGS,
    }


def build_public_benchmark_phase2_harness_audit(
    *,
    contract_json: str | Path = DEFAULT_CONTRACT_JSON,
) -> dict[str, Any]:
    contract_path = _resolve(contract_json)
    contract = _read_json(contract_path)
    summary = contract.get("summary") if isinstance(contract.get("summary"), dict) else {}
    reqs = _requirements_by_id(contract)
    rows = [
        _row(requirement_id, reqs.get(requirement_id, {}), summary=summary, contract_json=contract_path)
        for requirement_id in REQUIREMENT_ORDER
    ]
    ready_rows = [row for row in rows if row["ready"]]
    blockers = [
        f"{row['requirement_id']}:{row['blocker'] or 'not_ready'}"
        for row in rows
        if not row["ready"]
    ]
    adapter_row = next(row for row in rows if row["requirement_id"] == "vina_gnina_comparison_adapter")
    enrichment_row = next(row for row in rows if row["requirement_id"] == "dude_or_lit_pcba_enrichment")
    audit_ready = (
        contract_path.exists()
        and _text(summary.get("status")) == "product_public_benchmark_contract_ready"
        and bool(summary.get("phase2_public_benchmark_harness_ready") is True)
        and len(ready_rows) == len(rows)
        and _int(summary.get("phase2_ready_requirement_count")) == len(rows)
    )
    audit_blockers = list(blockers)
    if not contract_path.exists():
        audit_blockers.append("contract_json_missing")
    if _text(summary.get("status")) != "product_public_benchmark_contract_ready":
        audit_blockers.append("source_contract_not_ready")
    if summary.get("phase2_public_benchmark_harness_ready") is not True:
        audit_blockers.append("source_contract_phase2_not_ready")
    summary_out = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "public_benchmark_phase2_harness_audit_ready" if audit_ready else "blocked_public_benchmark_phase2_harness_audit",
        "phase2_harness_audit_ready": audit_ready,
        "contract_json": _display(contract_path),
        "source_contract_status": _text(summary.get("status")),
        "source_contract_phase2_ready": bool(summary.get("phase2_public_benchmark_harness_ready") is True),
        "requirement_count": len(rows),
        "ready_requirement_count": len(ready_rows),
        "blocker_count": len(audit_blockers),
        "blockers": audit_blockers,
        "pdbbind_execution_summary_json": _display(summary.get("pdbbind_execution_summary_json")),
        "pdbbind_pose_success_rate": summary.get("pdbbind_pose_success_rate"),
        "pdbbind_symmetry_aware_ligand_rmsd_coverage": summary.get(
            "pdbbind_symmetry_aware_ligand_rmsd_coverage"
        ),
        "pdbbind_posebusters_valid_rate": summary.get("pdbbind_posebusters_valid_rate"),
        "vina_gnina_comparison_adapter_ready": bool(adapter_row["ready"]),
        "vina_gnina_comparison_adapter_status": _text(summary.get("vina_gnina_comparison_adapter_status")),
        "vina_gnina_comparison_adapter_score_evidence_ready": bool(
            summary.get("vina_gnina_comparison_adapter_score_evidence_ready") is True
        ),
        "vina_gnina_comparison_score_evidence_required_for_phase2": False,
        "enrichment_requirement_ready": bool(enrichment_row["ready"]),
        "phase2_enrichment_ready_sources": _text(summary.get("phase2_enrichment_ready_sources")),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Phase 2 public benchmark harness is ready; optional Vina/GNINA comparator scores may be added later."
            if audit_ready
            else "Repair blocked Phase 2 requirement rows in the public benchmark contract, then rebuild this audit."
        ),
        **_READ_ONLY_FLAGS,
    }
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary_out,
        "rows": rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _fmt(row.get(column)) for column in _CSV_COLUMNS})


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Public Benchmark Phase 2 Harness Audit",
        "",
        f"- status: `{summary['status']}`",
        f"- phase2_harness_audit_ready: `{str(summary['phase2_harness_audit_ready']).lower()}`",
        f"- ready_requirement_count: `{summary['ready_requirement_count']}` / `{summary['requirement_count']}`",
        f"- vina_gnina_comparison_adapter_ready: `{str(summary['vina_gnina_comparison_adapter_ready']).lower()}`",
        f"- vina_gnina_comparison_adapter_score_evidence_ready: `{str(summary['vina_gnina_comparison_adapter_score_evidence_ready']).lower()}`",
        f"- vina_gnina_comparison_score_evidence_required_for_phase2: `{str(summary['vina_gnina_comparison_score_evidence_required_for_phase2']).lower()}`",
        f"- phase2_enrichment_ready_sources: `{summary['phase2_enrichment_ready_sources'] or '(none)'}`",
        "",
        "| requirement | status | evidence | notes | blocker |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{req}` | `{status}` | `{evidence}` | `{notes}` | `{blocker}` |".format(
                req=row["requirement_id"],
                status=row["status"],
                evidence=row["evidence"] or "",
                notes=row["notes"],
                blocker=row["blocker"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the public benchmark Phase 2 harness audit.")
    parser.add_argument("--contract-json", default=DEFAULT_CONTRACT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    payload = build_public_benchmark_phase2_harness_audit(contract_json=args.contract_json)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_csv = _resolve(args.out_csv)
    _write_json(out_json, payload)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    return 0 if payload["summary"]["phase2_harness_audit_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
