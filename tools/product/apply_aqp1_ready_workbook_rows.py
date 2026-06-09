#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
RUNS = ROOT / "runs"

TARGET = "AQP1_TRANSPORT_BLIND"
DEFAULT_WORKBOOK_JSON = RUNS / "aqp1_packet_replacement_workbook_current.json"
DEFAULT_INTAKE_JSON = RUNS / "aqp1_direct_binding_external_evidence_intake_current.json"
DEFAULT_REFERENCE_CSV = CONFIG / "ligand_binding_reference_blind_aqp1_v1.csv"
DEFAULT_SPLIT_CSV = CONFIG / "ligand_eval_splits_blind_aqp1_v1.csv"
DEFAULT_META_CSV = CONFIG / "ligand_meta_blind_aqp1_v1.csv"
DEFAULT_OUT_JSON = RUNS / "aqp1_ready_workbook_apply_current.json"
DEFAULT_OUT_CSV = RUNS / "aqp1_ready_workbook_apply_current.csv"
DEFAULT_OUT_MD = RUNS / "aqp1_ready_workbook_apply_current.md"

REFERENCE_FIELDS = ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"]
SPLIT_FIELDS = ["target", "ligand_id", "role"]
META_FIELDS = ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"]

BLOCKED_SOURCE_MARKERS = (
    "functional_ic50_derived_surrogate",
    "not_direct_binding",
    "template_placeholder",
    "keep_blocked",
)


def _resolve(path_like: str | Path) -> Path:
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


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _is_placeholder(value: Any) -> bool:
    return "placeholder" in _text(value).lower()


def _is_numeric_kcal(value: Any) -> bool:
    text = _text(value)
    if not text or text.upper() == "KEEP_BLOCKED":
        return False
    try:
        float(text)
    except ValueError:
        return False
    return True


def _is_claim_safe_direct_binding_row(row: dict[str, Any]) -> bool:
    source = _text(row.get("replacement_source")).lower()
    if not _is_numeric_kcal(row.get("replacement_reference_binding_kcal_mol")):
        return False
    return not any(marker in source for marker in BLOCKED_SOURCE_MARKERS)


def _approved_packet_steps(intake_payload: dict[str, Any] | None) -> set[str]:
    if not intake_payload:
        return set()
    approved: set[str] = set()
    for row in intake_payload.get("rows", []) or []:
        if not isinstance(row, dict):
            continue
        if row.get("intake_status") != "claim_safe_approved":
            continue
        step = _text(row.get("packet_step"))
        if step:
            approved.add(step)
    return approved


def _workbook_candidate_rows(workbook_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in workbook_payload.get("workbook_rows", []) or []:
        if _text(row.get("target")) != TARGET:
            continue
        if _text(row.get("apply_reference_row")).lower() != "yes":
            continue
        if _text(row.get("apply_split_row")).lower() != "yes":
            continue
        if _text(row.get("apply_meta_row")).lower() != "yes":
            continue
        rows.append(dict(row))
    return rows


def _ready_rows(
    workbook_payload: dict[str, Any],
    *,
    intake_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    approved_steps = _approved_packet_steps(intake_payload)
    rows: list[dict[str, Any]] = []
    for row in _workbook_candidate_rows(workbook_payload):
        if _text(row.get("row_ready_for_apply")).lower() != "yes":
            continue
        if _text(row.get("required_missing_fields")):
            continue
        if not _is_claim_safe_direct_binding_row(row):
            continue
        packet_step = _text(row.get("packet_step"))
        if intake_payload and packet_step not in approved_steps:
            continue
        rows.append(row)
    return rows


def _reference_replacement(row: dict[str, Any]) -> dict[str, str]:
    return {
        "target": TARGET,
        "ligand_id": _text(row.get("replacement_ligand_id")),
        "reference_binding_kcal_mol": _text(row.get("replacement_reference_binding_kcal_mol")),
        "is_binder": _text(row.get("replacement_is_binder")),
        "source": _text(row.get("replacement_source")),
    }


def _split_replacement(row: dict[str, Any]) -> dict[str, str]:
    return {
        "target": TARGET,
        "ligand_id": _text(row.get("replacement_ligand_id")),
        "role": _text(row.get("replacement_role")),
    }


def _meta_replacement(row: dict[str, Any]) -> dict[str, str]:
    return {
        "ligand_id": _text(row.get("replacement_ligand_id")),
        "smiles": _text(row.get("replacement_smiles")),
        "molecular_weight": _text(row.get("replacement_molecular_weight")),
        "logp": _text(row.get("replacement_logp")),
        "h_donors": _text(row.get("replacement_h_donors")),
        "h_acceptors": _text(row.get("replacement_h_acceptors")),
        "rot_bonds": _text(row.get("replacement_rot_bonds")),
        "scaffold": _text(row.get("replacement_scaffold")),
    }


def _replace_by_ligand_id(
    rows: list[dict[str, str]],
    *,
    current_ligand_id: str,
    replacement: dict[str, str],
    target_scoped: bool,
) -> tuple[list[dict[str, str]], int]:
    updated: list[dict[str, str]] = []
    replaced = 0
    for row in rows:
        row_ligand = _text(row.get("ligand_id"))
        row_target = _text(row.get("target"))
        target_matches = row_target == TARGET if target_scoped else True
        if row_ligand == current_ligand_id and target_matches:
            updated.append(dict(replacement))
            replaced += 1
        else:
            updated.append(dict(row))
    return updated, replaced


def _aqp1_binder_ligand_ids(reference_rows: list[dict[str, str]]) -> set[str]:
    return {
        _text(row.get("ligand_id"))
        for row in reference_rows
        if _text(row.get("target")) == TARGET and _text(row.get("is_binder")) == "1"
    }


def _placeholder_count(rows: list[dict[str, str]], *, target_scoped: bool) -> int:
    count = 0
    for row in rows:
        if target_scoped and _text(row.get("target")) != TARGET:
            continue
        if any(_is_placeholder(value) for value in row.values()):
            count += 1
        elif target_scoped and _text(row.get("is_binder")) == "1" and not _text(row.get("reference_binding_kcal_mol")):
            count += 1
        elif any(marker in _text(row.get("source")).lower() for marker in BLOCKED_SOURCE_MARKERS):
            count += 1
    return count


def _has_row(rows: list[dict[str, str]], expected: dict[str, str], *, target_scoped: bool) -> bool:
    expected_items = {key: _text(value) for key, value in expected.items()}
    for row in rows:
        if target_scoped and _text(row.get("target")) != TARGET:
            continue
        if all(_text(row.get(key)) == value for key, value in expected_items.items()):
            return True
    return False


def _claim_safe_blocker(row: dict[str, Any], *, intake_payload: dict[str, Any] | None) -> str:
    if _text(row.get("row_ready_for_apply")).lower() != "yes":
        return ""
    if _text(row.get("required_missing_fields")):
        return "required_missing_fields"
    if not _is_claim_safe_direct_binding_row(row):
        return "claim_safe_direct_binding_kcal_required"
    packet_step = _text(row.get("packet_step"))
    if intake_payload and packet_step not in _approved_packet_steps(intake_payload):
        return "external_evidence_intake_not_claim_safe_approved"
    return ""


def build_payload(
    *,
    reference_rows: list[dict[str, str]],
    split_rows: list[dict[str, str]],
    meta_rows: list[dict[str, str]],
    workbook_payload: dict[str, Any],
    intake_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ready_rows = _ready_rows(workbook_payload, intake_payload=intake_payload)
    updated_reference = [dict(row) for row in reference_rows]
    updated_split = [dict(row) for row in split_rows]
    updated_meta = [dict(row) for row in meta_rows]
    applied_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    seen_replacements: set[str] = set()
    binder_ids = _aqp1_binder_ligand_ids(reference_rows)

    for row in _workbook_candidate_rows(workbook_payload):
        blocker = _claim_safe_blocker(row, intake_payload=intake_payload)
        if blocker and _text(row.get("row_ready_for_apply")).lower() == "yes":
            blocked_rows.append(
                {
                    "packet_step": _text(row.get("packet_step")),
                    "current_ligand_id": _text(row.get("current_ligand_id")),
                    "replacement_ligand_id": _text(row.get("replacement_ligand_id")),
                    "blocker": blocker,
                }
            )

    for row in ready_rows:
        current_ligand_id = _text(row.get("current_ligand_id"))
        replacement_ligand_id = _text(row.get("replacement_ligand_id"))
        if not current_ligand_id or not replacement_ligand_id:
            blocked_rows.append(
                {
                    "packet_step": _text(row.get("packet_step")),
                    "current_ligand_id": current_ligand_id,
                    "replacement_ligand_id": replacement_ligand_id,
                    "blocker": "missing_current_or_replacement_ligand_id",
                }
            )
            continue
        if replacement_ligand_id in seen_replacements:
            blocked_rows.append(
                {
                    "packet_step": _text(row.get("packet_step")),
                    "current_ligand_id": current_ligand_id,
                    "replacement_ligand_id": replacement_ligand_id,
                    "blocker": "duplicate_replacement_ligand_id",
                }
            )
            continue
        seen_replacements.add(replacement_ligand_id)

        reference_replacement = _reference_replacement(row)
        split_replacement = _split_replacement(row)
        meta_replacement = _meta_replacement(row)
        updated_reference, ref_replaced = _replace_by_ligand_id(
            updated_reference,
            current_ligand_id=current_ligand_id,
            replacement=reference_replacement,
            target_scoped=True,
        )
        updated_split, split_replaced = _replace_by_ligand_id(
            updated_split,
            current_ligand_id=current_ligand_id,
            replacement=split_replacement,
            target_scoped=True,
        )
        updated_meta, meta_replaced = _replace_by_ligand_id(
            updated_meta,
            current_ligand_id=current_ligand_id,
            replacement=meta_replacement,
            target_scoped=False,
        )
        already_applied = (
            ref_replaced == 0
            and split_replaced == 0
            and meta_replaced == 0
            and _has_row(updated_reference, reference_replacement, target_scoped=True)
            and _has_row(updated_split, split_replacement, target_scoped=True)
            and _has_row(updated_meta, meta_replacement, target_scoped=False)
        )
        if ref_replaced == 0 and split_replaced == 0 and meta_replaced == 0 and not already_applied:
            blocked_rows.append(
                {
                    "packet_step": _text(row.get("packet_step")),
                    "current_ligand_id": current_ligand_id,
                    "replacement_ligand_id": replacement_ligand_id,
                    "blocker": "no_matching_current_row_and_replacement_not_present",
                }
            )
            continue
        applied_rows.append(
            {
                "packet_step": _text(row.get("packet_step")),
                "current_ligand_id": current_ligand_id,
                "replacement_ligand_id": replacement_ligand_id,
                "apply_status": "already_applied" if already_applied else "newly_applied",
                "reference_rows_replaced": ref_replaced,
                "split_rows_replaced": split_replaced,
                "meta_rows_replaced": meta_replaced,
                "reference_binding_kcal_mol": _text(row.get("replacement_reference_binding_kcal_mol")),
                "source": _text(row.get("replacement_source")),
            }
        )

    scoped_meta = [row for row in meta_rows if _text(row.get("ligand_id")) in binder_ids]
    updated_scoped_meta = [row for row in updated_meta if _text(row.get("ligand_id")) in binder_ids]
    before = {
        "reference_placeholder_rows": _placeholder_count(reference_rows, target_scoped=True),
        "split_placeholder_rows": _placeholder_count(split_rows, target_scoped=True),
        "meta_placeholder_rows": _placeholder_count(scoped_meta, target_scoped=False),
    }
    after = {
        "reference_placeholder_rows": _placeholder_count(updated_reference, target_scoped=True),
        "split_placeholder_rows": _placeholder_count(updated_split, target_scoped=True),
        "meta_placeholder_rows": _placeholder_count(updated_scoped_meta, target_scoped=False),
    }
    full_packet_ready = all(value == 0 for value in after.values())
    newly_applied_count = sum(1 for row in applied_rows if row["apply_status"] == "newly_applied")
    already_applied_count = sum(1 for row in applied_rows if row["apply_status"] == "already_applied")
    summary = {
        "target": TARGET,
        "ready_workbook_row_count": len(ready_rows),
        "applied_row_count": len(applied_rows),
        "newly_applied_row_count": newly_applied_count,
        "already_applied_row_count": already_applied_count,
        "blocked_ready_row_count": len(blocked_rows),
        "before_reference_placeholder_rows": before["reference_placeholder_rows"],
        "before_split_placeholder_rows": before["split_placeholder_rows"],
        "before_meta_placeholder_rows": before["meta_placeholder_rows"],
        "after_reference_placeholder_rows": after["reference_placeholder_rows"],
        "after_split_placeholder_rows": after["split_placeholder_rows"],
        "after_meta_placeholder_rows": after["meta_placeholder_rows"],
        "full_packet_ready_after_apply": full_packet_ready,
        "claim_safe_direct_binding_required": True,
        "external_evidence_intake_required": intake_payload is not None,
        "next_required_step": (
            "Regenerate AQP1 and transporter scope gates; the synchronized AQP1 binder packet is now claim-safe and placeholder-free."
            if full_packet_ready
            else "Keep curating remaining AQP1 binder rows with claim-safe direct-binding kcal before treating reference/split/meta artifacts as ready."
        ),
    }
    return {
        "summary": summary,
        "applied_rows": applied_rows,
        "blocked_rows": blocked_rows,
        "updated_reference_rows": updated_reference,
        "updated_split_rows": updated_split,
        "updated_meta_rows": updated_meta,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Ready Workbook Apply",
        "",
        f"- target: `{s['target']}`",
        f"- ready_workbook_row_count: `{s['ready_workbook_row_count']}`",
        f"- applied_row_count: `{s['applied_row_count']}`",
        f"- newly_applied_row_count: `{s['newly_applied_row_count']}`",
        f"- already_applied_row_count: `{s['already_applied_row_count']}`",
        f"- blocked_ready_row_count: `{s['blocked_ready_row_count']}`",
        f"- before_placeholders: `reference={s['before_reference_placeholder_rows']};split={s['before_split_placeholder_rows']};meta={s['before_meta_placeholder_rows']}`",
        f"- after_placeholders: `reference={s['after_reference_placeholder_rows']};split={s['after_split_placeholder_rows']};meta={s['after_meta_placeholder_rows']}`",
        f"- full_packet_ready_after_apply: `{s['full_packet_ready_after_apply']}`",
        "",
        "## Applied Rows",
        "",
        "| packet_step | current_ligand_id | replacement_ligand_id | status | ref | split | meta | source |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["applied_rows"]:
        lines.append(
            f"| `{row['packet_step']}` | `{row['current_ligand_id']}` | `{row['replacement_ligand_id']}` | `{row['apply_status']}` | "
            f"{row['reference_rows_replaced']} | {row['split_rows_replaced']} | {row['meta_rows_replaced']} | `{row['source']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply ready AQP1 workbook rows as synchronized reference/split/meta edits with claim-safe direct-binding kcal only."
    )
    parser.add_argument("--workbook-json", default=str(DEFAULT_WORKBOOK_JSON))
    parser.add_argument("--intake-json", default=str(DEFAULT_INTAKE_JSON))
    parser.add_argument("--reference-csv", default=str(DEFAULT_REFERENCE_CSV))
    parser.add_argument("--split-csv", default=str(DEFAULT_SPLIT_CSV))
    parser.add_argument("--meta-csv", default=str(DEFAULT_META_CSV))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    parser.add_argument("--no-write-config", action="store_true")
    parser.add_argument("--skip-intake-gate", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reference_csv = _resolve(args.reference_csv)
    split_csv = _resolve(args.split_csv)
    meta_csv = _resolve(args.meta_csv)
    intake_payload = None if args.skip_intake_gate else _load_json(_resolve(args.intake_json))
    payload = build_payload(
        reference_rows=_read_csv(reference_csv),
        split_rows=_read_csv(split_csv),
        meta_rows=_read_csv(meta_csv),
        workbook_payload=_load_json(_resolve(args.workbook_json)),
        intake_payload=intake_payload,
    )
    if not args.no_write_config and payload["summary"]["applied_row_count"] > 0:
        _write_csv(reference_csv, payload["updated_reference_rows"], REFERENCE_FIELDS)
        _write_csv(split_csv, payload["updated_split_rows"], SPLIT_FIELDS)
        _write_csv(meta_csv, payload["updated_meta_rows"], META_FIELDS)

    out_payload = {
        "summary": payload["summary"],
        "applied_rows": payload["applied_rows"],
        "blocked_rows": payload["blocked_rows"],
    }
    out_json = _resolve(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(out_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(
        _resolve(args.out_csv),
        payload["applied_rows"],
        [
            "packet_step",
            "current_ligand_id",
            "replacement_ligand_id",
            "apply_status",
            "reference_rows_replaced",
            "split_rows_replaced",
            "meta_rows_replaced",
            "reference_binding_kcal_mol",
            "source",
        ],
    )
    _write_markdown(_resolve(args.out_md), out_payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
