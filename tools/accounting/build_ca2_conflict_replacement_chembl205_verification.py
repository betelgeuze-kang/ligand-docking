#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

from tools.product.build_ca2_public_negative_evidence_overlay import (
    CA2_TARGET_CHEMBL_ID,
    _activity_query_url,
    _activity_rows_for_ligand,
    _activity_summary,
    _direct_negative_like,
    _text,
)
from tools.accounting.build_ca2_conflict_replacement_shortlist import REPLACEMENTS

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_SHORTLIST_JSON = RUNS / "ca2_conflict_replacement_shortlist_current.json"
DEFAULT_VERIFICATION_CSV = RUNS / "ca2_binding_verification_sheet_current.csv"
DEFAULT_WORKBOOK_CSV = RUNS / "ca2_packet_replacement_workbook_current.csv"
DEFAULT_OUT_JSON = RUNS / "ca2_conflict_replacement_chembl205_verification_current.json"
DEFAULT_OUT_MD = RUNS / "ca2_conflict_replacement_chembl205_verification_current.md"

REPLACEMENT_LIGAND_CHEMBL_IDS: dict[str, str] = {
    "mannitol": "CHEMBL866",
    "glycerol": "CHEMBL689",
    "sucrose": "CHEMBL853",
    "benzoic_acid": "CHEMBL542",
    "D_glucose": "CHEMBL822",
    "nicotinamide": "CHEMBL886",
}


def _alternate_candidate_ids(shortlist_row: dict[str, Any]) -> list[str]:
    primary = _text(shortlist_row.get("primary_replacement_ligand_id"))
    candidates: list[str] = []
    for ligand_id in [
        _text(shortlist_row.get("alternate_replacement_ligand_id")),
        *[
            _text(value)
            for value in (REPLACEMENTS.get(_text(shortlist_row.get("packet_step")), {}) or {}).get(
                "fallback_alternate_ligand_ids", []
            )
        ],
    ]:
        if ligand_id and ligand_id != primary and ligand_id not in candidates:
            candidates.append(ligand_id)
    return candidates


def _ligand_workbook_fields(ligand_id: str) -> dict[str, str]:
    for spec in REPLACEMENTS.values():
        if str(spec.get("primary_ligand_id", "")).strip() == ligand_id:
            return {
                "replacement_smiles": str(spec.get("primary_smiles", "")),
                "replacement_scaffold": str(spec.get("primary_scaffold", "")),
                "replacement_source": str(spec.get("primary_source", "")),
            }
    return {"replacement_smiles": "", "replacement_scaffold": "", "replacement_source": ""}


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


def _positive_binding_like(row: dict[str, Any]) -> bool:
    standard_type = _text(row.get("standard_type"))
    standard_value = _text(row.get("standard_value"))
    if standard_type not in {"Ki", "IC50", "Kd", "EC50"} or not standard_value:
        return False
    try:
        return float(standard_value) > 0
    except ValueError:
        return False


def _query_ligand(
    ligand_id: str,
    *,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    molecule_chembl_id = REPLACEMENT_LIGAND_CHEMBL_IDS.get(ligand_id, "")
    base = {
        "ligand_id": ligand_id,
        "molecule_chembl_id": molecule_chembl_id,
        "target_chembl_id": CA2_TARGET_CHEMBL_ID,
    }
    if not molecule_chembl_id:
        return {**base, "query_status": "unsupported_ligand", "activity_count": 0}

    try:
        source_url, activities = _activity_rows_for_ligand(molecule_chembl_id, fetch_json=fetch_json)
    except Exception as exc:
        return {
            **base,
            "query_status": "query_error",
            "activity_count": 0,
            "source_url": _activity_query_url(molecule_chembl_id),
            "error": str(exc),
        }

    negative_like = [row for row in activities if _direct_negative_like(row)]
    positive_like = [row for row in activities if _positive_binding_like(row)]
    if positive_like:
        summary, source_ids = _activity_summary(positive_like)
        return {
            **base,
            "query_status": "positive_activity_conflict",
            "activity_count": len(activities),
            "source_url": source_url,
            "activity_summary": summary,
            "source_id": source_ids,
        }
    if negative_like:
        summary, source_ids = _activity_summary(negative_like)
        return {
            **base,
            "query_status": "direct_negative_like",
            "activity_count": len(activities),
            "negative_like_count": len(negative_like),
            "source_url": source_url,
            "activity_summary": summary,
            "source_id": source_ids,
        }
    return {
        **base,
        "query_status": "no_chembl205_target_activity",
        "activity_count": len(activities),
        "source_url": source_url,
    }


def _verification_update_from_query(
    packet_step: str,
    *,
    selected_ligand_id: str,
    query: dict[str, Any],
    superseded_ligand: str,
    used_alternate_for: str = "",
    rejected_primary: str = "",
    today_local: str,
) -> dict[str, str]:
    status = query["query_status"]
    if status == "direct_negative_like":
        source_id = _text(query.get("source_id")) or "manual_source"
        provenance = "::".join(
            [
                "ca2_direct_negative_evidence",
                source_id,
                "target_specific_direct_negative_upper_bound",
                "direct_ca2_enzyme_inhibition_upper_bound",
            ]
        )
        alternate_note = ""
        if used_alternate_for:
            alternate_note = (
                f" Primary replacement `{rejected_primary or used_alternate_for}` failed CHEMBL205 verification;"
                f" promoted alternate `{selected_ligand_id}`."
            )
        evidence_note = (
            f"ChEMBL {CA2_TARGET_CHEMBL_ID} query for {selected_ligand_id} returned direct CA2-negative-like evidence "
            f"({query.get('activity_summary', '')}). Supersedes conflict ligand {superseded_ligand}.{alternate_note} "
            f"Keep replacement_reference_binding_kcal_mol blank (review-only negative closure as of {today_local})."
        )
        return {
            "packet_step": packet_step,
            "replacement_ligand_id": selected_ligand_id,
            "verify_reference_binding_kcal_mol": "",
            "verify_provenance_source": provenance,
            "verify_source_url": _text(query.get("source_url")),
            "verification_status": "verified_direct_negative_evidence_review_only",
            "evidence_note": evidence_note.strip(),
            "replacement_status": "verified_direct_negative_review_only",
        }

    if status == "no_chembl205_target_activity":
        return {
            "packet_step": packet_step,
            "replacement_ligand_id": selected_ligand_id,
            "verify_reference_binding_kcal_mol": "",
            "verify_provenance_source": (
                f"ca2_conflict_replacement_chembl205::{selected_ligand_id}::no_target_activity_found"
            ),
            "verify_source_url": _text(query.get("source_url")),
            "verification_status": "verified_no_chembl205_target_activity",
            "evidence_note": (
                f"No CHEMBL {CA2_TARGET_CHEMBL_ID} activity rows for {selected_ligand_id}; this is not claim-safe direct "
                f"negative evidence. Supersedes conflict ligand {superseded_ligand}. Keep kcal blank and keep row blocked."
            ),
            "replacement_status": "blocked_no_chembl205_activity",
        }

    if status == "positive_activity_conflict":
        return {
            "packet_step": packet_step,
            "replacement_ligand_id": selected_ligand_id,
            "verify_reference_binding_kcal_mol": "",
            "verify_provenance_source": (
                f"ca2_conflict_replacement_chembl205::{selected_ligand_id}::positive_activity_conflict"
            ),
            "verify_source_url": _text(query.get("source_url")),
            "verification_status": "chembl205_positive_activity_blocks_replacement",
            "evidence_note": (
                f"CHEMBL {CA2_TARGET_CHEMBL_ID} returned positive binding-like activity for {selected_ligand_id} "
                f"({query.get('activity_summary', '')}); replacement blocked."
            ),
            "replacement_status": "blocked_positive_activity_conflict",
        }

    return {
        "packet_step": packet_step,
        "replacement_ligand_id": selected_ligand_id,
        "verify_reference_binding_kcal_mol": "",
        "verify_provenance_source": f"ca2_conflict_replacement_chembl205::{selected_ligand_id}::{status}",
        "verify_source_url": _text(query.get("source_url")),
        "verification_status": "pending_chembl205_negative_verification",
        "evidence_note": _text(query.get("error")) or f"CHEMBL205 verification incomplete for {selected_ligand_id}.",
        "replacement_status": "proposed_pending_verification",
    }


def verify_shortlist_row(
    shortlist_row: dict[str, Any],
    *,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
    today_local: str | None = None,
) -> dict[str, Any]:
    today_local = today_local or str(date.today())
    packet_step = _text(shortlist_row.get("packet_step"))
    primary = _text(shortlist_row.get("primary_replacement_ligand_id"))
    alternate = _text(shortlist_row.get("alternate_replacement_ligand_id"))
    superseded = _text(shortlist_row.get("superseded_ligand"))

    primary_query = _query_ligand(primary, fetch_json=fetch_json)
    selected_ligand = primary
    used_alternate_for = ""
    rejected_primary = ""
    selected_query = primary_query

    if primary_query["query_status"] in {"no_chembl205_target_activity", "positive_activity_conflict"}:
        for alternate_id in _alternate_candidate_ids(shortlist_row):
            alternate_query = _query_ligand(alternate_id, fetch_json=fetch_json)
            if alternate_query["query_status"] == "direct_negative_like":
                selected_ligand = alternate_id
                used_alternate_for = alternate_id
                rejected_primary = primary
                selected_query = alternate_query
                break

    update = _verification_update_from_query(
        packet_step,
        selected_ligand_id=selected_ligand,
        query=selected_query,
        superseded_ligand=superseded,
        used_alternate_for=used_alternate_for,
        rejected_primary=rejected_primary,
        today_local=today_local,
    )
    return {
        "packet_step": packet_step,
        "superseded_ligand": superseded,
        "primary_replacement_ligand_id": primary,
        "alternate_replacement_ligand_id": alternate,
        "selected_replacement_ligand_id": selected_ligand,
        "used_alternate_for": used_alternate_for,
        "rejected_primary": rejected_primary,
        "primary_query": primary_query,
        "selected_query": selected_query,
        **update,
    }


def _synthetic_shortlist_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for packet_step, spec in REPLACEMENTS.items():
        rows.append(
            {
                "packet_step": packet_step,
                "superseded_ligand": spec["superseded_ligand"],
                "primary_replacement_ligand_id": spec["primary_ligand_id"],
                "alternate_replacement_ligand_id": spec["alternate_ligand_id"],
            }
        )
    return rows


def build_payload(
    shortlist_payload: dict[str, Any],
    *,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
    today_local: str | None = None,
) -> dict[str, Any]:
    shortlist_rows = [
        dict(row)
        for row in shortlist_payload.get("rows", []) or []
        if isinstance(row, dict) and _text(row.get("packet_step"))
    ]
    if not shortlist_rows:
        shortlist_rows = _synthetic_shortlist_rows()
    rows = [
        verify_shortlist_row(row, fetch_json=fetch_json, today_local=today_local)
        for row in shortlist_rows
    ]
    direct_negative_count = sum(
        1 for row in rows if row.get("verification_status") == "verified_direct_negative_evidence_review_only"
    )
    blocked_count = sum(
        1
        for row in rows
        if str(row.get("verification_status", "")).startswith(
            ("verified_no_chembl205", "chembl205_positive", "pending_chembl205")
        )
        or row.get("replacement_status", "").startswith("blocked_")
    )
    summary = {
        "packet_type": "ca2_conflict_replacement_chembl205_verification",
        "status": "ca2_conflict_replacement_chembl205_verification_ready" if rows else "blocked_ca2_conflict_replacement_chembl205_verification",
        "row_count": len(rows),
        "direct_negative_review_only_count": direct_negative_count,
        "blocked_or_pending_count": blocked_count,
        "alternate_promoted_count": sum(1 for row in rows if _text(row.get("used_alternate_for"))),
        "next_required_step": (
            "Apply verification updates, regenerate CA2 capture sheet/intake/commit/readiness, then rerun rollups."
            if rows
            else "Regenerate CA2 conflict replacement shortlist before running CHEMBL205 verification."
        ),
    }
    return {"summary": summary, "rows": rows}


def apply_verification_sheet_patch(
    verification_rows: list[dict[str, str]], verification_results: list[dict[str, Any]]
) -> list[dict[str, str]]:
    by_step = {str(row["packet_step"]): row for row in verification_results}
    patched: list[dict[str, str]] = []
    for row in verification_rows:
        next_row = dict(row)
        result = by_step.get(str(row.get("packet_step", "")).strip())
        if not result:
            patched.append(next_row)
            continue
        selected = str(result["selected_replacement_ligand_id"])
        next_row["replacement_ligand_id"] = selected
        fields = _ligand_workbook_fields(selected)
        if fields["replacement_smiles"]:
            next_row["replacement_smiles"] = fields["replacement_smiles"]
        if fields["replacement_scaffold"]:
            next_row["replacement_scaffold"] = fields["replacement_scaffold"]
        next_row["verify_reference_binding_kcal_mol"] = ""
        next_row["verify_provenance_source"] = str(result["verify_provenance_source"])
        next_row["verify_source_url"] = str(result.get("verify_source_url", ""))
        next_row["verification_status"] = str(result["verification_status"])
        note = str(next_row.get("notes", "")).strip()
        evidence_note = str(result.get("evidence_note", "")).strip()
        if evidence_note and evidence_note not in note:
            next_row["notes"] = f"{note} {evidence_note}".strip()
        patched.append(next_row)
    return patched


def apply_workbook_patch(
    workbook_rows: list[dict[str, str]],
    shortlist_rows: list[dict[str, Any]],
    verification_results: list[dict[str, Any]],
) -> list[dict[str, str]]:
    shortlist_by_step = {str(row["packet_step"]): row for row in shortlist_rows}
    result_by_step = {str(row["packet_step"]): row for row in verification_results}
    patched: list[dict[str, str]] = []
    for row in workbook_rows:
        next_row = dict(row)
        packet_step = str(row.get("packet_step", "")).strip()
        result = result_by_step.get(packet_step)
        shortlist = shortlist_by_step.get(packet_step, {})
        if not result:
            patched.append(next_row)
            continue
        selected = str(result.get("selected_replacement_ligand_id", "")).strip()
        if selected and selected != str(row.get("replacement_ligand_id", "")).strip():
            fields = _ligand_workbook_fields(selected)
            next_row["replacement_ligand_id"] = selected
            if fields["replacement_smiles"]:
                next_row["replacement_smiles"] = fields["replacement_smiles"]
            if fields["replacement_scaffold"]:
                next_row["replacement_scaffold"] = fields["replacement_scaffold"]
            if selected == str(shortlist.get("primary_replacement_ligand_id", "")).strip():
                next_row["replacement_source"] = str(shortlist.get("primary_replacement_source", ""))
            else:
                next_row["replacement_source"] = (
                    fields["replacement_source"]
                    or f"ca2_conflict_replacement_alternate::{selected}::promoted_after_primary_no_chembl205_activity"
                )
                next_row["notes"] = (
                    f"{str(row.get('notes', '')).strip()} Alternate {selected} promoted after primary "
                    f"{shortlist.get('primary_replacement_ligand_id', '')} had no CHEMBL205 target activity."
                ).strip()
        next_row["replacement_reference_binding_kcal_mol"] = ""
        next_row["required_missing_fields"] = "replacement_reference_binding_kcal_mol"
        next_row["row_ready_for_apply"] = (
            "yes"
            if result.get("verification_status") == "verified_direct_negative_evidence_review_only"
            else "no"
        )
        patched.append(next_row)
    return patched


def apply_shortlist_status_patch(
    shortlist_payload: dict[str, Any], verification_results: list[dict[str, Any]]
) -> dict[str, Any]:
    result_by_step = {str(row["packet_step"]): row for row in verification_results}
    next_payload = dict(shortlist_payload)
    next_rows: list[dict[str, Any]] = []
    for row in shortlist_payload.get("rows", []) or []:
        next_row = dict(row)
        result = result_by_step.get(str(row.get("packet_step", "")).strip())
        if result:
            next_row["replacement_status"] = str(result.get("replacement_status", row.get("replacement_status", "")))
            next_row["selected_replacement_ligand_id"] = str(result.get("selected_replacement_ligand_id", ""))
            if result.get("used_alternate_for"):
                next_row["promoted_alternate_after_primary"] = str(result.get("used_alternate_for"))
        next_rows.append(next_row)
    next_payload["rows"] = next_rows
    verified_count = sum(
        1 for row in next_rows if row.get("replacement_status") == "verified_direct_negative_review_only"
    )
    next_payload["summary"] = dict(shortlist_payload.get("summary", {}) or {})
    next_payload["summary"]["chembl205_verified_direct_negative_count"] = verified_count
    next_payload["summary"]["chembl205_blocked_count"] = sum(
        1 for row in next_rows if str(row.get("replacement_status", "")).startswith("blocked_")
    )
    return next_payload


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# CA2 Conflict Replacement CHEMBL205 Verification",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        f"- direct_negative_review_only_count: `{s['direct_negative_review_only_count']}`",
        f"- blocked_or_pending_count: `{s['blocked_or_pending_count']}`",
        f"- alternate_promoted_count: `{s['alternate_promoted_count']}`",
        "",
        "## Rows",
        "",
        "| packet_step | selected | status | query |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['packet_step']}` | `{row['selected_replacement_ligand_id']}` | "
            f"`{row['verification_status']}` | `{row['selected_query']['query_status']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify CA2 conflict replacement candidates against CHEMBL205.")
    parser.add_argument("--shortlist-json", default=str(DEFAULT_SHORTLIST_JSON))
    parser.add_argument("--verification-csv", default=str(DEFAULT_VERIFICATION_CSV))
    parser.add_argument("--workbook-csv", default=str(DEFAULT_WORKBOOK_CSV))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    parser.add_argument("--apply", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    shortlist_payload = _read_json(_resolve(args.shortlist_json))
    payload = build_payload(shortlist_payload)
    out_json = _resolve(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_md(_resolve(args.out_md), payload)

    if args.apply:
        verification_rows = _read_csv(_resolve(args.verification_csv))
        patched_verification = apply_verification_sheet_patch(verification_rows, payload["rows"])
        _write_csv(_resolve(args.verification_csv), patched_verification)
        verified_count = sum(
            1
            for row in patched_verification
            if str(row.get("verification_status", "")).strip().startswith("verified_")
        )
        verification_payload = {
            "summary": {
                "family": "ca2",
                "row_count": len(patched_verification),
                "verified_row_count": verified_count,
                "next_required_step": payload["summary"]["next_required_step"],
            },
            "sheet_rows": patched_verification,
        }
        verification_json = _resolve(args.verification_csv).with_name("ca2_binding_verification_sheet_current.json")
        verification_json.write_text(json.dumps(verification_payload, indent=2) + "\n", encoding="utf-8")
        workbook_path = _resolve(args.workbook_csv)
        if workbook_path.exists():
            patched_workbook = apply_workbook_patch(
                _read_csv(workbook_path),
                list(shortlist_payload.get("rows", []) or []),
                payload["rows"],
            )
            _write_csv(workbook_path, patched_workbook)
        patched_shortlist = apply_shortlist_status_patch(
            shortlist_payload if shortlist_payload.get("rows") else {"rows": _synthetic_shortlist_rows(), "summary": {}},
            payload["rows"],
        )
        _resolve(args.shortlist_json).write_text(
            json.dumps(patched_shortlist, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
