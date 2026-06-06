#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]

CHEMBL_ACTIVITY_API = "https://www.ebi.ac.uk/chembl/api/data/activity.json"
CA2_TARGET_CHEMBL_ID = "CHEMBL205"
DEFAULT_CAPTURE_SHEET_CSV = "runs/ca2_negative_evidence_capture_sheet_current.csv"
DEFAULT_OUT_JSON = "runs/ca2_public_negative_evidence_overlay_current.json"
DEFAULT_OUT_CSV = "runs/ca2_public_negative_evidence_overlay_current.csv"
DEFAULT_OUT_MD = "runs/ca2_public_negative_evidence_overlay_current.md"

LIGAND_CHEMBL_IDS = {
    "acetaminophen": "CHEMBL112",
    "aspirin": "CHEMBL25",
    "caffeine": "CHEMBL113",
    "ibuprofen": "CHEMBL521",
    "metformin": "CHEMBL1431",
}

NO_DIRECT_BLOCKERS = {
    "no_direct_ca2_negative_evidence_curated",
    "no_direct_ca2_negative_evidence_located_after_research",
}


def _resolve(path_like: str) -> Path:
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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _activity_query_url(molecule_chembl_id: str, *, limit: int = 20) -> str:
    return f"{CHEMBL_ACTIVITY_API}?{urlencode({'molecule_chembl_id': molecule_chembl_id, 'target_chembl_id': CA2_TARGET_CHEMBL_ID, 'limit': limit})}"


def _fetch_json(url: str) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": "md-family-expansion/1.0"})
    with urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _activity_rows_for_ligand(
    molecule_chembl_id: str,
    *,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    url = _activity_query_url(molecule_chembl_id)
    fetch = fetch_json or _fetch_json
    payload = fetch(url)
    return url, list(payload.get("activities", []) or [])


def _direct_negative_like(row: dict[str, Any]) -> bool:
    activity_comment = _text(row.get("activity_comment")).lower()
    standard_relation = _text(row.get("standard_relation")).strip()
    standard_value = _text(row.get("standard_value")).strip()
    if "inhibition < 50%" in activity_comment:
        return True
    if "no inhibition" in activity_comment or "inactive" in activity_comment or "not active" in activity_comment:
        return True
    return standard_relation == "<" and bool(standard_value)


def _activity_summary(activities: list[dict[str, Any]], *, limit: int = 2) -> tuple[str, str]:
    summary_parts: list[str] = []
    source_ids: list[str] = []
    for row in activities[:limit]:
        activity_comment = _text(row.get("activity_comment")) or "direct CA2 activity row"
        assay_id = _text(row.get("assay_chembl_id"))
        document_id = _text(row.get("document_chembl_id"))
        assay_doc = " / ".join(part for part in [assay_id, document_id] if part).strip()
        if assay_doc:
            source_ids.append(assay_doc)
            summary_parts.append(f"{activity_comment} in {assay_doc}")
        else:
            summary_parts.append(activity_comment)
    return "; ".join(summary_parts), " | ".join(source_ids)


def _candidate_rows(capture_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in capture_rows:
        blocker = _text(row.get("manual_promotion_blocker"))
        capture_status = _text(row.get("capture_status"))
        if blocker in NO_DIRECT_BLOCKERS or capture_status in {"", "pending_capture"}:
            rows.append(row)
    return rows


def _overlay_row(
    row: dict[str, Any],
    *,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
    today_local: str | None = None,
) -> dict[str, Any]:
    packet_step = _text(row.get("packet_step"))
    ligand_label = _text(row.get("ligand"))
    ligand = ligand_label.lower()
    molecule_chembl_id = LIGAND_CHEMBL_IDS.get(ligand, "")
    today_local = today_local or str(date.today())
    base = {
        "packet_step": packet_step,
        "ligand": ligand_label,
        "molecule_chembl_id": molecule_chembl_id,
        "target_chembl_id": CA2_TARGET_CHEMBL_ID,
    }
    if not molecule_chembl_id:
        return {
            **base,
            "overlay_status": "unsupported_ligand",
            "supports_direct_ca2_negative": "",
            "evidence_scope": "",
            "assay_context": "",
            "source_title": "",
            "source_id": "",
            "source_url": "",
            "weak_activity_conflict_present": "",
            "capture_status": "",
            "manual_review_bucket": "",
            "manual_assay_type_honesty": "",
            "manual_promotion_blocker": "",
            "manual_next_required_action": "",
            "manual_recommended_resolution": "",
            "manual_decision_note": "",
            "commit_status": "",
        }

    try:
        source_url, activities = _activity_rows_for_ligand(molecule_chembl_id, fetch_json=fetch_json)
    except Exception as exc:
        return {
            **base,
            "overlay_status": "query_error",
            "supports_direct_ca2_negative": "",
            "evidence_scope": "",
            "assay_context": "",
            "source_title": f"ChEMBL {CA2_TARGET_CHEMBL_ID} activity query for {ligand_label} failed.",
            "source_id": "",
            "source_url": _activity_query_url(molecule_chembl_id),
            "weak_activity_conflict_present": "",
            "capture_status": "pending_capture",
            "manual_review_bucket": "",
            "manual_assay_type_honesty": "",
            "manual_promotion_blocker": "",
            "manual_next_required_action": "",
            "manual_recommended_resolution": "",
            "manual_decision_note": f"Live query error while checking direct CA2-negative evidence for {ligand_label}: {exc}",
            "commit_status": "",
        }

    negative_like_rows = [activity for activity in activities if _direct_negative_like(activity)]
    if not negative_like_rows:
        return {
            **base,
            "overlay_status": "no_direct_negative_found",
            "supports_direct_ca2_negative": "",
            "evidence_scope": "",
            "assay_context": "",
            "source_title": "",
            "source_id": "",
            "source_url": "",
            "weak_activity_conflict_present": "",
            "capture_status": "",
            "manual_review_bucket": "",
            "manual_assay_type_honesty": "",
            "manual_promotion_blocker": "",
            "manual_next_required_action": "",
            "manual_recommended_resolution": "",
            "manual_decision_note": "",
            "commit_status": "",
        }

    summary, source_ids = _activity_summary(negative_like_rows)
    return {
        **base,
        "overlay_status": "captured_direct_negative_review_only",
        "supports_direct_ca2_negative": "yes",
        "evidence_scope": "target_specific_direct_negative_upper_bound",
        "assay_context": "direct_ca2_enzyme_inhibition_upper_bound",
        "source_title": f"ChEMBL {CA2_TARGET_CHEMBL_ID} activity query for {ligand_label} returned {len(negative_like_rows)} direct CA2-negative-like records.",
        "source_id": source_ids,
        "source_url": source_url,
        "weak_activity_conflict_present": "no",
        "capture_status": "captured_direct_negative_review_only",
        "manual_review_bucket": "standard_review",
        "manual_assay_type_honesty": "direct_ca2_negative_like_upper_bound_review_only",
        "manual_promotion_blocker": "direct_ca2_negative_evidence_curated_review_only",
        "manual_next_required_action": "apply_direct_negative_evidence_review_only",
        "manual_recommended_resolution": "keep_review_only_with_direct_ca2_negative_evidence",
        "manual_decision_note": (
            f"As of {today_local}, the live ChEMBL target query found direct human CA2 evidence for {ligand_label}: {summary}. "
            "This supports review-only direct negative-like closure without filling a quantitative non-binder kcal value."
        ),
        "commit_status": "confirmed_review_only",
    }


def build_payload(
    capture_rows: list[dict[str, Any]],
    *,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
    today_local: str | None = None,
) -> dict[str, Any]:
    overlay_rows = [
        _overlay_row(row, fetch_json=fetch_json, today_local=today_local)
        for row in _candidate_rows(capture_rows)
    ]
    overlay_rows = [row for row in overlay_rows if row.get("overlay_status") not in {"no_direct_negative_found", "unsupported_ligand"}]
    summary = {
        "family": "ca2",
        "row_count": len(overlay_rows),
        "direct_negative_row_count": sum(
            1 for row in overlay_rows if row.get("overlay_status") == "captured_direct_negative_review_only"
        ),
        "query_error_count": sum(1 for row in overlay_rows if row.get("overlay_status") == "query_error"),
        "source_linked_count": sum(1 for row in overlay_rows if _text(row.get("source_url")) or _text(row.get("source_title"))),
        "next_required_step": "Merge the overlay into the CA2 capture sheet, then rerun intake so direct CA2-negative evidence can clear no-direct-source blockers.",
    }
    return {"summary": summary, "rows": overlay_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# CA2 Public Negative-Evidence Overlay",
        "",
        f"- family: `{s['family']}`",
        f"- row_count: `{s['row_count']}`",
        f"- direct_negative_row_count: `{s['direct_negative_row_count']}`",
        f"- query_error_count: `{s['query_error_count']}`",
        f"- source_linked_count: `{s['source_linked_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Overlay Rows",
        "",
        "| packet_step | ligand | overlay_status | source_title |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['packet_step']}` | `{row['ligand']}` | `{row['overlay_status']}` | {row['source_title']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a live public-evidence overlay for CA2 rows still missing direct negative evidence.")
    parser.add_argument("--capture-sheet-csv", default=DEFAULT_CAPTURE_SHEET_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    capture_rows = _read_csv(_resolve(args.capture_sheet_csv))
    payload = build_payload(capture_rows)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
