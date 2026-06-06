#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_transporter_local_crosscheck_triage_packet import (
    DEFAULT_CROSSCHECK_DIR,
    _records_for_target,
)

ROOT = Path(__file__).resolve().parents[1]
RUNS = Path("runs")

DEFAULT_TRIAGE_JSON = RUNS / "transporter_local_crosscheck_triage_packet_current.json"
DEFAULT_OUT_JSON = RUNS / "transporter_slot_assignment_candidate_workbook_current.json"
DEFAULT_OUT_CSV = RUNS / "transporter_slot_assignment_candidate_workbook_current.csv"
DEFAULT_OUT_MD = RUNS / "transporter_slot_assignment_candidate_workbook_current.md"

RT_KCAL_MOL_298K = 0.00198720425864083 * 298.15
TARGET_REFERENCE_IDS = {
    "AQP1": "AQP1_TRANSPORT_BLIND",
    "GLUT1_4PYP": "GLUT1_TRANSPORT_BLIND",
}

CLAIM_BOUNDARY = (
    "Transporter slot assignment candidate workbook only; proposes local public-data candidate rows for unresolved "
    "AQP1/GLUT1 packet slots and records the remaining manual checks. It does not write config CSVs, assign final "
    "ligands, authoritatively apply rows, reopen donor policy, run docking, widen product scope, upload, submit, "
    "email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_json(path_like: str | Path) -> dict[str, Any]:
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


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dg_from_nm(value_nM: float | None) -> str:
    if value_nM is None or value_nM <= 0:
        return ""
    return f"{RT_KCAL_MOL_298K * math.log(value_nM * 1e-9):.4f}"


def _candidate_ligand_id(record: dict[str, Any]) -> str:
    molecule_id = _text(record.get("molecule_id")).lower()
    source_kind = _text(record.get("source_kind"))
    if molecule_id:
        prefix = "bindingdb" if source_kind == "bindingdb_affinity" else "chembl"
        return f"{prefix}_{molecule_id}"
    return ""


def _source(record: dict[str, Any]) -> str:
    source_kind = _text(record.get("source_kind"))
    activity_type = _text(record.get("activity_type"))
    value = _text(record.get("value"))
    units = _text(record.get("units"))
    doc = _text(record.get("document_id"))
    molecule_id = _text(record.get("molecule_id"))
    return f"{source_kind}::{molecule_id}::{activity_type}_{value}_{units}::source_{doc}".rstrip(":")


def _suggest_scaffold(smiles: str) -> str:
    text = _text(smiles)
    lowered = text.lower()
    if not text:
        return ""
    if "s(=o)(=o)" in lowered and "n" in lowered:
        return "heuristic::sulfonamide_heteroaryl"
    if lowered.count("cl") >= 2 and "c(=o)n" in lowered:
        return "heuristic::chlorinated_benzamide"
    if "[c@h]" in lowered and len(text) > 90:
        return "heuristic::polyoxygenated_macrocycle"
    if "o[c@h]" in lowered and "co)" in lowered and lowered.count("c") >= 12:
        return "heuristic::alkyl_glycoside"
    if "c1ccccc1" in lowered:
        return "heuristic::phenyl_aromatic"
    carbon_count = text.count("C")
    if set(text) <= {"C"} and carbon_count:
        return f"heuristic::acyclic_{carbon_count}c"
    if carbon_count and not any(marker in text for marker in ("1", "2", "@", "=", "#")):
        return "heuristic::acyclic_aliphatic"
    return "heuristic::unclassified_review_required"


def _is_direct(record: dict[str, Any]) -> bool:
    return record.get("direct_quantitative") is True


def _is_functional(record: dict[str, Any]) -> bool:
    return record.get("functional_quantitative") is True


def _is_inactive(record: dict[str, Any]) -> bool:
    return record.get("not_active_nonquantitative") is True


def _sort_value(record: dict[str, Any]) -> tuple[int, float, str]:
    value = _float(record.get("value"))
    value_sort = value if value is not None else 1e12
    return (0 if record.get("has_source_provenance") else 1, value_sort, _text(record.get("molecule_id")))


def _select_candidate(row: dict[str, Any], records: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    bucket = _text(row.get("slot_triage_bucket"))
    is_binder = _text(row.get("packet_step")).startswith("core_binder")
    if bucket == "keep_review_only_direct_binding_gap":
        candidates = sorted([record for record in records if _is_direct(record)], key=_sort_value)
        return (candidates[0], "reference_only_review_not_source_signal_assignment") if candidates else ({}, "no_direct_candidate")
    if bucket == "functional_quantitative_only_direct_gap_open":
        candidates = sorted([record for record in records if _is_functional(record)], key=_sort_value)
        return (candidates[0], "functional_quantitative_surrogate_review_only") if candidates else ({}, "no_functional_candidate")
    if is_binder:
        candidates = sorted([record for record in records if _is_direct(record)], key=_sort_value)
        if candidates:
            return candidates[0], "direct_quantitative_replacement_candidate"
        candidates = sorted([record for record in records if _is_functional(record)], key=_sort_value)
        return (candidates[0], "functional_quantitative_replacement_candidate") if candidates else ({}, "no_quantitative_candidate")
    candidates = sorted([record for record in records if _is_inactive(record)], key=_sort_value)
    if candidates:
        return candidates[0], "inactive_nonquantitative_replacement_candidate_requires_negative_value_review"
    candidates = sorted([record for record in records if _is_direct(record) or _is_functional(record)], key=_sort_value, reverse=True)
    return (candidates[0], "weak_quantitative_nonbinder_candidate_requires_threshold_review") if candidates else ({}, "no_negative_candidate")


def _missing_fields(candidate: dict[str, Any], candidate_mode: str, scaffold: str) -> str:
    required = {
        "replacement_ligand_id": _candidate_ligand_id(candidate),
        "replacement_source": _source(candidate),
        "replacement_smiles": _text(candidate.get("smiles")),
        "replacement_scaffold": scaffold,
    }
    if "inactive_nonquantitative" in candidate_mode:
        required["replacement_reference_binding_kcal_mol"] = ""
    else:
        required["replacement_reference_binding_kcal_mol"] = _dg_from_nm(_float(candidate.get("value")))
    return ",".join(name for name, value in required.items() if not _text(value))


def _candidate_ready(candidate: dict[str, Any], candidate_mode: str, bucket: str) -> bool:
    return False


def _manual_review_blockers(candidate_mode: str, bucket: str, missing: str) -> str:
    blockers: list[str] = []
    if bucket in {"keep_review_only_direct_binding_gap", "functional_quantitative_only_direct_gap_open"}:
        blockers.append("review_only_or_functional_surrogate")
    if "inactive_nonquantitative" in candidate_mode:
        blockers.append("negative_quantitative_value_required")
    if missing:
        blockers.append(f"missing_fields={missing}")
    blockers.append("manual_ligand_identity_and_scaffold_confirmation_required")
    return ";".join(blockers)


def _action(row: dict[str, Any], candidate_mode: str) -> str:
    bucket = _text(row.get("slot_triage_bucket"))
    if bucket == "functional_quantitative_only_direct_gap_open":
        return "Keep AQP1 binder row blocked for direct-binding/kcal; use functional record only as review evidence."
    if bucket == "keep_review_only_direct_binding_gap":
        return "Keep review-only unless source-signal ligand identity is reconciled to a direct-binding constant."
    if "inactive_nonquantitative" in candidate_mode:
        return "Manual reviewer must decide whether inactive/nonquantitative evidence is sufficient or acquire exact quantitative negative evidence."
    return "Manual reviewer must confirm ligand identity, scaffold, source provenance, and split/meta synchronization before apply."


def build_payload(
    *,
    triage_payload: dict[str, Any],
    crosscheck_dir: str | Path = DEFAULT_CROSSCHECK_DIR,
    triage_path: str = DEFAULT_TRIAGE_JSON.as_posix(),
) -> dict[str, Any]:
    records_by_target: dict[str, list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    for triage_row in _rows(triage_payload):
        target_id = _text(triage_row.get("target_id"))
        bucket = _text(triage_row.get("slot_triage_bucket"))
        if bucket not in {
            "candidate_assignment_required_from_local_pool",
            "functional_quantitative_only_direct_gap_open",
            "keep_review_only_direct_binding_gap",
        }:
            continue
        records = records_by_target.setdefault(target_id, _records_for_target(crosscheck_dir, target_id))
        candidate, candidate_mode = _select_candidate(triage_row, records)
        scaffold = _suggest_scaffold(_text(candidate.get("smiles"))) if candidate else ""
        missing = (
            _missing_fields(candidate, candidate_mode, scaffold)
            if candidate
            else "replacement_ligand_id,replacement_reference_binding_kcal_mol,replacement_source,replacement_smiles,replacement_scaffold"
        )
        rows.append(
            {
                "priority": _text(triage_row.get("priority")) or len(rows) + 1,
                "target_id": target_id,
                "target_reference_id": TARGET_REFERENCE_IDS.get(target_id, target_id),
                "item_id": _text(triage_row.get("item_id")),
                "packet_step": _text(triage_row.get("packet_step")),
                "current_candidate_or_check": _text(triage_row.get("candidate_or_check")),
                "slot_triage_bucket": bucket,
                "candidate_mode": candidate_mode,
                "replacement_ligand_id": _candidate_ligand_id(candidate),
                "replacement_reference_binding_kcal_mol": "" if "inactive_nonquantitative" in candidate_mode else _dg_from_nm(_float(candidate.get("value"))),
                "replacement_is_binder": "0" if "non_binder" in _text(triage_row.get("packet_step")) else "1",
                "replacement_source": _source(candidate) if candidate else "",
                "replacement_smiles": _text(candidate.get("smiles")),
                "replacement_scaffold": scaffold,
                "scaffold_suggestion_status": "heuristic_review_required" if scaffold else "missing",
                "candidate_activity_type": _text(candidate.get("activity_type")),
                "candidate_activity_value": _text(candidate.get("value")),
                "candidate_activity_units": _text(candidate.get("units")),
                "candidate_document_id": _text(candidate.get("document_id")),
                "candidate_source_file": _text(candidate.get("source_file")),
                "required_missing_fields": missing,
                "manual_review_blockers": _manual_review_blockers(candidate_mode, bucket, missing),
                "candidate_ready_for_manual_review": bool(candidate),
                "candidate_ready_for_apply": _candidate_ready(candidate, candidate_mode, bucket),
                "next_action": _action(triage_row, candidate_mode),
                "authoritative_apply_allowed": False,
                "scope_promotion_allowed": False,
                "external_state_mutated": False,
            }
        )

    ready_for_review = [row for row in rows if row["candidate_ready_for_manual_review"]]
    ready_for_apply = [row for row in rows if row["candidate_ready_for_apply"]]
    blocked_review_only = [
        row
        for row in rows
        if row["slot_triage_bucket"] in {"functional_quantitative_only_direct_gap_open", "keep_review_only_direct_binding_gap"}
    ]
    negative_value_review = [row for row in rows if "inactive_nonquantitative" in row["candidate_mode"]]
    scaffold_suggestions = [row for row in rows if row["replacement_scaffold"]]
    summary = {
        "packet_type": "transporter_slot_assignment_candidate_workbook",
        "candidate_workbook_ready": True,
        "candidate_row_count": len(rows),
        "candidate_ready_for_manual_review_count": len(ready_for_review),
        "candidate_ready_for_apply_count": len(ready_for_apply),
        "blocked_review_only_count": len(blocked_review_only),
        "scaffold_suggestion_count": len(scaffold_suggestions),
        "negative_value_review_required_count": len(negative_value_review),
        "authoritative_apply_allowed_count": 0,
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "external_state_mutated": False,
        "source_artifacts": [triage_path, str(crosscheck_dir)],
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Manually review candidate rows, fill scaffold and any missing negative quantitative values, then regenerate transporter P0 closure before any authoritative apply."
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
        "# Transporter Slot Assignment Candidate Workbook",
        "",
        f"- candidate_workbook_ready: `{s['candidate_workbook_ready']}`",
        f"- candidate_row_count: `{s['candidate_row_count']}`",
        f"- candidate_ready_for_manual_review_count: `{s['candidate_ready_for_manual_review_count']}`",
        f"- candidate_ready_for_apply_count: `{s['candidate_ready_for_apply_count']}`",
        f"- blocked_review_only_count: `{s['blocked_review_only_count']}`",
        f"- scaffold_suggestion_count: `{s['scaffold_suggestion_count']}`",
        f"- negative_value_review_required_count: `{s['negative_value_review_required_count']}`",
        f"- authoritative_apply_allowed: `{s['authoritative_apply_allowed']}`",
        f"- scope_promotion_allowed: `{s['scope_promotion_allowed']}`",
        "",
        "## Candidates",
        "",
        "| priority | target | item | mode | ligand | kcal | missing | ready apply |",
        "| ---: | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['target_id']}` | `{row['item_id']}` | `{row['candidate_mode']}` | "
            f"`{row['replacement_ligand_id'] or '-'}` | {row['replacement_reference_binding_kcal_mol'] or ''} | "
            f"`{row['required_missing_fields'] or '-'}` | `{row['candidate_ready_for_apply']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build transporter slot assignment candidate workbook.")
    parser.add_argument("--triage-json", default=str(DEFAULT_TRIAGE_JSON))
    parser.add_argument("--crosscheck-dir", default=str(DEFAULT_CROSSCHECK_DIR))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        triage_payload=_read_json(args.triage_json),
        crosscheck_dir=args.crosscheck_dir,
        triage_path=args.triage_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
