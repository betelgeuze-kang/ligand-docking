#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_WORKBENCH_JSON = RUNS / "ca2_reviewer_workbench_current.json"
DEFAULT_WORKBOOK_CSV = RUNS / "ca2_packet_replacement_workbook_current.csv"
DEFAULT_VERIFICATION_CSV = RUNS / "ca2_binding_verification_sheet_current.csv"
DEFAULT_OUT_JSON = RUNS / "ca2_conflict_replacement_shortlist_current.json"
DEFAULT_OUT_CSV = RUNS / "ca2_conflict_replacement_shortlist_current.csv"
DEFAULT_OUT_MD = RUNS / "ca2_conflict_replacement_shortlist_current.md"
DEFAULT_CHEMBL205_VERIFICATION_JSON = RUNS / "ca2_conflict_replacement_chembl205_verification_current.json"

REPLACEMENTS: dict[str, dict[str, Any]] = {
    "core_non_binder_01": {
        "superseded_ligand": "acetaminophen",
        "primary_ligand_id": "mannitol",
        "primary_smiles": "OC[C@H](O)[C@H](O)[C@H](O)[C@H](O)CO",
        "primary_scaffold": "polyol",
        "primary_source": "ca2_conflict_replacement_proposed::CHEMBL205_verify_required::mannitol::Inhibition_lt_50pct_at_10uM_required",
        "alternate_ligand_id": "glycerol",
        "conflict_pmid": "PMID:18579385",
    },
    "core_non_binder_03": {
        "superseded_ligand": "caffeine",
        "primary_ligand_id": "glycerol",
        "primary_smiles": "OCC(O)CO",
        "primary_scaffold": "triol",
        "primary_source": "ca2_conflict_replacement_proposed::CHEMBL205_verify_required::glycerol::Inhibition_lt_50pct_at_10uM_required",
        "alternate_ligand_id": "sucrose",
        "conflict_pmid": "PMID:21612376",
    },
    "ood_non_binder_01": {
        "superseded_ligand": "aspirin",
        "primary_ligand_id": "sucrose",
        "primary_smiles": "OC[C@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O",
        "primary_scaffold": "disaccharide",
        "primary_source": "ca2_conflict_replacement_proposed::CHEMBL205_verify_required::sucrose::Inhibition_lt_50pct_at_10uM_required",
        "alternate_ligand_id": "mannitol",
        "conflict_pmid": "PMCID:PMC7226357",
    },
    "ood_non_binder_02": {
        "superseded_ligand": "ibuprofen",
        "primary_ligand_id": "benzoic_acid",
        "primary_smiles": "OC(=O)c1ccccc1",
        "primary_scaffold": "benzoic_acid",
        "primary_source": "ca2_conflict_replacement_proposed::CHEMBL205_verify_required::benzoic_acid::Inhibition_lt_50pct_at_10uM_required",
        "alternate_ligand_id": "nicotinamide",
        "fallback_alternate_ligand_ids": ["mannitol", "glycerol"],
        "conflict_pmid": "PMID:36322425",
    },
    "ood_non_binder_03": {
        "superseded_ligand": "caffeine",
        "primary_ligand_id": "D_glucose",
        "primary_smiles": "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
        "primary_scaffold": "pyranose",
        "primary_source": "ca2_conflict_replacement_proposed::CHEMBL205_verify_required::D_glucose::Inhibition_lt_50pct_at_10uM_required",
        "alternate_ligand_id": "glycerol",
        "conflict_pmid": "PMID:21612376",
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _shortlist_rows_from_chembl205_verification(verification_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in verification_payload.get("rows", []) or []:
        if not isinstance(result, dict):
            continue
        packet_step = str(result.get("packet_step", "")).strip()
        spec = REPLACEMENTS.get(packet_step, {})
        rows.append(
            {
                "packet_step": packet_step,
                "packet": "core" if packet_step.startswith("core_") else "ood",
                "superseded_ligand": str(result.get("superseded_ligand", spec.get("superseded_ligand", ""))).strip(),
                "superseded_conflict_pmid": spec.get("conflict_pmid", ""),
                "primary_replacement_ligand_id": str(result.get("primary_replacement_ligand_id", "")).strip(),
                "primary_replacement_smiles": spec.get("primary_smiles", ""),
                "primary_replacement_scaffold": spec.get("primary_scaffold", ""),
                "primary_replacement_source": spec.get("primary_source", ""),
                "alternate_replacement_ligand_id": str(result.get("alternate_replacement_ligand_id", "")).strip(),
                "selected_replacement_ligand_id": str(result.get("selected_replacement_ligand_id", "")).strip(),
                "replacement_status": str(result.get("replacement_status", "")).strip(),
                "quantitative_kcal_policy": "keep_blank_until_chembl205_upper_bound_or_direct_negative_verified",
                "verification_requirement": "CHEMBL205 verification complete; see ca2_conflict_replacement_chembl205_verification_current.json",
                "next_required_action": "Rerun CA2 capture/commit/readiness builders after verification apply.",
            }
        )
    return rows


def build_shortlist_rows(
    workbench_rows: list[dict[str, Any]],
    *,
    chembl205_verification: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for workbench in workbench_rows:
        if workbench.get("operator_review_bucket") != "conflict_review":
            continue
        packet_step = str(workbench.get("packet_step", "")).strip()
        spec = REPLACEMENTS.get(packet_step)
        if not spec:
            continue
        rows.append(
            {
                "packet_step": packet_step,
                "packet": str(workbench.get("packet", "")).strip(),
                "superseded_ligand": spec["superseded_ligand"],
                "superseded_conflict_pmid": spec["conflict_pmid"],
                "primary_replacement_ligand_id": spec["primary_ligand_id"],
                "primary_replacement_smiles": spec["primary_smiles"],
                "primary_replacement_scaffold": spec["primary_scaffold"],
                "primary_replacement_source": spec["primary_source"],
                "alternate_replacement_ligand_id": spec["alternate_ligand_id"],
                "replacement_status": "proposed_pending_verification",
                "quantitative_kcal_policy": "keep_blank_until_chembl205_upper_bound_or_direct_negative_verified",
                "verification_requirement": "Confirm human CA2 (CHEMBL205) Inhibition <50% @10 uM or equivalent direct negative upper bound before any non-binder kcal assignment.",
                "next_required_action": "Run ChEMBL205 activity query for primary candidate; if clean, sync workbook and rerun capture/commit builders.",
            }
        )
    if rows:
        return rows
    if chembl205_verification:
        return _shortlist_rows_from_chembl205_verification(chembl205_verification)
    return rows


def apply_workbook_patch(workbook_rows: list[dict[str, str]], shortlist_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    by_step = {str(row["packet_step"]): row for row in shortlist_rows}
    patched: list[dict[str, str]] = []
    for row in workbook_rows:
        next_row = dict(row)
        shortlist = by_step.get(str(row.get("packet_step", "")).strip())
        if not shortlist:
            patched.append(next_row)
            continue
        next_row["replacement_ligand_id"] = str(shortlist["primary_replacement_ligand_id"])
        next_row["replacement_smiles"] = str(shortlist["primary_replacement_smiles"])
        next_row["replacement_scaffold"] = str(shortlist["primary_replacement_scaffold"])
        next_row["replacement_source"] = str(shortlist["primary_replacement_source"])
        next_row["replacement_reference_binding_kcal_mol"] = ""
        next_row["required_missing_fields"] = "replacement_reference_binding_kcal_mol"
        next_row["row_ready_for_apply"] = "no"
        note_suffix = (
            f" Conflict replacement proposed: superseded {shortlist['superseded_ligand']} "
            f"({shortlist['superseded_conflict_pmid']}) -> {shortlist['primary_replacement_ligand_id']} "
            f"pending CHEMBL205 negative verification; kcal remains blank."
        )
        next_row["notes"] = f"{str(row.get('notes', '')).strip()}{note_suffix}".strip()
        patched.append(next_row)
    return patched


def apply_verification_patch(
    verification_rows: list[dict[str, str]], shortlist_rows: list[dict[str, Any]]
) -> list[dict[str, str]]:
    by_step = {str(row["packet_step"]): row for row in shortlist_rows}
    patched: list[dict[str, str]] = []
    for row in verification_rows:
        next_row = dict(row)
        shortlist = by_step.get(str(row.get("packet_step", "")).strip())
        if not shortlist:
            patched.append(next_row)
            continue
        next_row["replacement_ligand_id"] = str(shortlist["primary_replacement_ligand_id"])
        next_row["replacement_smiles"] = str(shortlist["primary_replacement_smiles"])
        next_row["replacement_scaffold"] = str(shortlist["primary_replacement_scaffold"])
        next_row["replacement_source"] = str(shortlist["primary_replacement_source"])
        next_row["verify_reference_binding_kcal_mol"] = ""
        next_row["verify_provenance_source"] = str(shortlist["primary_replacement_source"])
        next_row["verification_status"] = "pending_chembl205_negative_verification"
        next_row["notes"] = (
            f"Conflict replacement candidate pending CHEMBL205 verification; "
            f"superseded {shortlist['superseded_ligand']} ({shortlist['superseded_conflict_pmid']})."
        )
        patched.append(next_row)
    return patched


def build_payload(
    workbench_packet: dict[str, Any],
    *,
    apply_patch: bool,
    workbook_rows: list[dict[str, str]] | None = None,
    verification_rows: list[dict[str, str]] | None = None,
    chembl205_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    workbench_rows = list(workbench_packet.get("rows", []) or [])
    shortlist_rows = build_shortlist_rows(workbench_rows, chembl205_verification=chembl205_verification)
    workbook_patch_count = 0
    verification_patch_count = 0
    if apply_patch and workbook_rows is not None:
        before = {str(row.get("packet_step", "")): row.get("replacement_ligand_id", "") for row in workbook_rows}
        workbook_rows = apply_workbook_patch(workbook_rows, shortlist_rows)
        workbook_patch_count = sum(
            1
            for row in workbook_rows
            if before.get(str(row.get("packet_step", ""))) != row.get("replacement_ligand_id")
        )
    if apply_patch and verification_rows is not None:
        verification_rows = apply_verification_patch(verification_rows, shortlist_rows)
        verification_patch_count = len(shortlist_rows)
    summary = {
        "packet_type": "ca2_conflict_replacement_shortlist",
        "status": "ca2_conflict_replacement_shortlist_ready" if shortlist_rows else "blocked_ca2_conflict_replacement_shortlist",
        "conflict_row_count": len(shortlist_rows),
        "workbook_patch_applied": apply_patch and workbook_patch_count > 0,
        "workbook_patched_row_count": workbook_patch_count,
        "verification_patched_row_count": verification_patch_count if apply_patch else 0,
        "next_required_step": (
            "Verify each primary replacement against CHEMBL205, then rerun CA2 capture/commit/readiness builders."
            if shortlist_rows
            else "Regenerate CA2 reviewer workbench before building conflict replacement shortlist."
        ),
    }
    payload: dict[str, Any] = {"summary": summary, "rows": shortlist_rows}
    if workbook_rows is not None:
        payload["workbook_rows"] = workbook_rows
    if verification_rows is not None:
        payload["verification_rows"] = verification_rows
    return payload


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# CA2 Conflict Replacement Shortlist",
        "",
        f"- status: `{s['status']}`",
        f"- conflict_row_count: `{s['conflict_row_count']}`",
        f"- workbook_patch_applied: `{s['workbook_patch_applied']}`",
        f"- workbook_patched_row_count: `{s['workbook_patched_row_count']}`",
        "",
        "## Rows",
        "",
        "| packet_step | superseded | primary | alternate | status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['packet_step']}` | `{row['superseded_ligand']}` | `{row['primary_replacement_ligand_id']}` | "
            f"`{row['alternate_replacement_ligand_id']}` | `{row['replacement_status']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CA2 conflict replacement shortlist and optionally patch workbook.")
    parser.add_argument("--workbench-json", default=str(DEFAULT_WORKBENCH_JSON))
    parser.add_argument("--chembl205-verification-json", default=str(DEFAULT_CHEMBL205_VERIFICATION_JSON))
    parser.add_argument("--workbook-csv", default=str(DEFAULT_WORKBOOK_CSV))
    parser.add_argument("--verification-csv", default=str(DEFAULT_VERIFICATION_CSV))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    parser.add_argument("--apply-workbook-patch", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    workbench = _read_json(_resolve(args.workbench_json))
    chembl205 = _read_json(_resolve(args.chembl205_verification_json))
    workbook_rows = _read_csv(_resolve(args.workbook_csv)) if _resolve(args.workbook_csv).exists() else None
    verification_rows = _read_csv(_resolve(args.verification_csv)) if _resolve(args.verification_csv).exists() else None
    payload = build_payload(
        workbench,
        apply_patch=bool(args.apply_workbook_patch),
        workbook_rows=workbook_rows,
        verification_rows=verification_rows,
        chembl205_verification=chembl205 if chembl205.get("rows") else None,
    )
    out_json = _resolve(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(_resolve(args.out_md), payload)
    if args.apply_workbook_patch and workbook_rows is not None:
        _write_csv(_resolve(args.workbook_csv), payload["workbook_rows"])
    if args.apply_workbook_patch and verification_rows is not None:
        _write_csv(_resolve(args.verification_csv), payload["verification_rows"])


if __name__ == "__main__":
    main()
