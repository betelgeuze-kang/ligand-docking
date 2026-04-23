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

ROOT = Path(__file__).resolve().parents[1]

CHEMBL_ACTIVITY_API = "https://www.ebi.ac.uk/chembl/api/data/activity.json"
PUBCHEM_PUG_API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PXR_TARGET_CHEMBL_ID = "CHEMBL3401"
DEFAULT_CAPTURE_SHEET_CSV = "runs/pxr_unresolved_evidence_capture_sheet_current.csv"
DEFAULT_OUT_JSON = "runs/pxr_public_evidence_overlay_current.json"
DEFAULT_OUT_CSV = "runs/pxr_public_evidence_overlay_current.csv"
DEFAULT_OUT_MD = "runs/pxr_public_evidence_overlay_current.md"

LIGAND_CHEMBL_IDS = {
    "acetaminophen": "CHEMBL112",
    "aspirin": "CHEMBL25",
    "bexarotene": "CHEMBL1023",
    "caffeine": "CHEMBL113",
    "ibuprofen": "CHEMBL521",
    "nicotinamide": "CHEMBL1140",
}

LIGAND_PUBCHEM_CIDS = {
    "aspirin": "2244",
    "caffeine": "2519",
    "bexarotene": "82146",
    "nicotinamide": "936",
}

LITERATURE_OVERRIDES = {
    "bexarotene": {
        "source_title": "PMID 18544536: Rexinoids modulate steroid and xenobiotic receptor activity by increasing its protein turnover in a calpain-dependent manner.",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/18544536/",
        "source_note_template": (
            "As of {today_local}, manual review accepted PMID 18544536 as target-specific human SXR/PXR literature support for bexarotene. "
            "Keep this row deferred because claim-safe quantitative human PXR activity/binding provenance is still missing, even though binder/modulator support is now confirmed."
        ),
        "manual_assay_type_honesty": "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing",
        "manual_promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
        "manual_next_required_action": "curate_quantitative_binding_value",
        "manual_commit_class_override": "Manual review confirmed human PXR/SXR binder-modulator support for bexarotene from PMID 18544536; claim-safe quantitative provenance is still missing, so keep deferred and leave binder fields blank.",
        "manual_commit_note": "confirmed_defer",
        "commit_status": "confirmed_defer",
    }
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
    return f"{CHEMBL_ACTIVITY_API}?{urlencode({'molecule_chembl_id': molecule_chembl_id, 'target_chembl_id': PXR_TARGET_CHEMBL_ID, 'limit': limit})}"


def _fetch_json(url: str) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": "md-family-expansion/1.0"})
    with urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _activity_rows_for_ligand(
    molecule_chembl_id: str,
    *,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, Any]], str]:
    url = _activity_query_url(molecule_chembl_id)
    fetch = fetch_json or _fetch_json
    payload = fetch(url)
    return url, list(payload.get("activities", []) or []), ""


def _activity_summary(activities: list[dict[str, Any]], *, limit: int = 2) -> str:
    summary_parts: list[str] = []
    for row in activities[:limit]:
        standard_type = _text(row.get("standard_type")) or "activity"
        relation = _text(row.get("standard_relation"))
        value = _text(row.get("standard_value"))
        units = _text(row.get("standard_units"))
        assay_id = _text(row.get("assay_chembl_id"))
        document_id = _text(row.get("document_chembl_id"))
        assay_description = _text(row.get("assay_description"))
        measurement = " ".join(part for part in [standard_type, f"{relation}{value}".strip(), units] if part).strip()
        assay_doc = " / ".join(part for part in [assay_id, document_id] if part).strip()
        if assay_description and assay_doc:
            summary_parts.append(f"{assay_description} ({measurement}; {assay_doc})".strip())
        elif assay_description:
            summary_parts.append(f"{assay_description} ({measurement})".strip())
        elif assay_doc:
            summary_parts.append(f"{measurement} in {assay_doc}".strip())
        else:
            summary_parts.append(measurement)
    return "; ".join(part for part in summary_parts if part)


def _pubchem_assaysummary_url(cid: str) -> str:
    return f"{PUBCHEM_PUG_API}/compound/cid/{cid}/assaysummary/JSON"


def _pubchem_assaysummary_rows(
    cid: str,
    *,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    url = _pubchem_assaysummary_url(cid)
    payload = (fetch_json or _fetch_json)(url)
    table = dict(payload.get("Table", {}) or {})
    column_nodes = list(((table.get("Columns", {}) or {}).get("Column", []) or []))
    column_names: list[str] = []
    for node in column_nodes:
        if isinstance(node, dict):
            column_names.append(_text(node.get("Name")))
        else:
            column_names.append(_text(node))
    rows: list[dict[str, str]] = []
    for row in list(table.get("Row", []) or []):
        cells = list((row or {}).get("Cell", []) or []) if isinstance(row, dict) else list(row or [])
        mapped: dict[str, str] = {}
        for idx, name in enumerate(column_names):
            mapped[name] = _text(cells[idx]) if idx < len(cells) else ""
        rows.append(mapped)
    return url, rows


def _pubchem_human_pxr_proxy_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    filtered: list[dict[str, str]] = []
    for row in rows:
        assay_name = _text(row.get("Assay Name")).lower()
        target_gene_id = _text(row.get("Target GeneID"))
        target_accession = _text(row.get("Target Accession"))
        if "human pregnane x receptor" not in assay_name and target_gene_id != "8856" and target_accession != "ADZ17384":
            continue
        if "counter screen" in assay_name:
            continue
        if "summary" in assay_name:
            continue
        filtered.append(row)
    return filtered


def _pubchem_row_rank(row: dict[str, str]) -> tuple[int, int, float]:
    outcome = _text(row.get("Activity Outcome")).lower()
    assay_name = _text(row.get("Assay Name")).lower()
    value = _text(row.get("Activity Value [uM]"))
    outcome_rank = 3 if outcome == "active" else 2 if outcome == "inconclusive" else 1 if outcome == "inactive" else 0
    direct_rank = 1 if "activation by small molecules" in assay_name or "small molecule agonists" in assay_name else 0
    try:
        numeric = float(value)
    except ValueError:
        numeric = 1e9
    return (outcome_rank, direct_rank, -numeric)


def _pubchem_activity_override(
    ligand: str,
    ligand_label: str,
    *,
    is_binder: bool,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
    today_local: str,
) -> dict[str, Any] | None:
    cid = LIGAND_PUBCHEM_CIDS.get(ligand, "")
    if not cid:
        return None
    try:
        source_url, rows = _pubchem_assaysummary_rows(cid, fetch_json=fetch_json)
    except Exception:
        return None

    proxy_rows = _pubchem_human_pxr_proxy_rows(rows)
    inactive_rows = [row for row in proxy_rows if _text(row.get("Activity Outcome")).lower() == "inactive"]
    positive_rows = [
        row
        for row in proxy_rows
        if _text(row.get("Activity Outcome")).lower() in {"active", "inconclusive"}
        or (
            _text(row.get("Activity Value [uM]"))
            and _text(row.get("Activity Outcome")).lower() not in {"inactive"}
        )
    ]
    if not positive_rows:
        if not is_binder and inactive_rows:
            best = sorted(inactive_rows, key=_pubchem_row_rank, reverse=True)[0]
            best_aid = _text(best.get("AID"))
            best_name = _text(best.get("Assay Name"))
            aid_list = ",".join(dict.fromkeys(_text(row.get("AID")) for row in inactive_rows if _text(row.get("AID"))))
            best_url = f"https://pubchem.ncbi.nlm.nih.gov/bioassay/{best_aid}" if best_aid else source_url
            return {
                "overlay_status": "captured_review_only",
                "supports_local_target_specific_human_pxr": "yes",
                "source_title": f"PubChem CID {cid} inactive-only human PXR qHTS summary for {ligand_label}.",
                "source_url": best_url,
                "source_note": (
                    f"As of {today_local}, PubChem CID {cid} reports direct human PXR qHTS rows for {ligand_label}, "
                    f"and the currently surfaced target-specific rows are inactive-only ({aid_list or 'inactive replicate rows'}; "
                    f"lead assay: AID {best_aid or 'n/a'} {best_name}). Treat this as a review-only inactive-evidence lane, "
                    "not as a count-improving negative claim."
                ),
                "capture_status": "captured_review_only",
                "manual_assay_type_honesty": "inactive_only_human_pxr_qhts_review_only",
                "manual_promotion_blocker": "inactive_only_human_pxr_qhts_review_only",
                "manual_next_required_action": "manual_negative_evidence_review",
                "manual_commit_class_override": (
                    f"Direct human PXR qHTS rows for {ligand_label} are inactive-only in PubChem; keep this row "
                    "review-only and do not inject a quantitative non-binder value."
                ),
                "manual_commit_note": "confirmed_review_only",
                "commit_status": "confirmed_review_only",
            }
        return None

    best = sorted(positive_rows, key=_pubchem_row_rank, reverse=True)[0]
    conflicting = inactive_rows
    best_aid = _text(best.get("AID"))
    best_value = _text(best.get("Activity Value [uM]"))
    best_outcome = _text(best.get("Activity Outcome")) or "Unspecified"
    best_name = _text(best.get("Assay Name"))
    best_activity_name = _text(best.get("Activity Name")) or "Potency"
    best_url = f"https://pubchem.ncbi.nlm.nih.gov/bioassay/{best_aid}" if best_aid else source_url
    value_fragment = (
        f"{best_activity_name} {best_value} uM with outcome {best_outcome}"
        if best_value
        else f"outcome {best_outcome}"
    )
    note = (
        f"As of {today_local}, PubChem CID {cid} reports direct human PXR assay evidence for {ligand_label}: "
        f"AID {best_aid} ({best_name}) gives {value_fragment}."
    )
    if conflicting:
        conflict_aids = ",".join(dict.fromkeys(_text(row.get("AID")) for row in conflicting if _text(row.get("AID"))))
        note += f" Conflicting human PXR qHTS inactive rows also remain present ({conflict_aids or 'inactive replicate rows'})."
    if not is_binder:
        return {
            "overlay_status": "captured_conflict",
            "supports_local_target_specific_human_pxr": "yes",
            "source_title": f"PubChem CID {cid} human PXR qHTS summary for {ligand_label}.",
            "source_url": best_url,
            "source_note": note + " Treat this as a human-PXR conflict lane, not a clean non-binder.",
            "capture_status": "captured_conflict",
            "manual_assay_type_honesty": "activity_proxy_conflicts_with_non_binder",
            "manual_promotion_blocker": "activity_proxy_conflicts_with_non_binder",
            "manual_next_required_action": "manual_curated_search_or_defer",
            "manual_commit_class_override": _activity_override(ligand_label, is_binder=False),
            "manual_commit_note": "confirmed_defer",
            "commit_status": "confirmed_defer",
        }
    note += " Keep this on the manual-confirmation lane."
    return {
        "overlay_status": "captured_supportive",
        "supports_local_target_specific_human_pxr": "yes",
        "source_title": f"PubChem CID {cid} human PXR qHTS summary for {ligand_label}.",
        "source_url": best_url,
        "source_note": note,
        "capture_status": "captured_supportive",
        "manual_assay_type_honesty": "activity_present_manual_confirmation_required",
        "manual_promotion_blocker": "activity_present_manual_confirmation_required",
        "manual_next_required_action": "manual_curated_search_or_defer",
        "manual_commit_class_override": (
            f"PubChem human PXR qHTS activity proxy exists for {ligand_label} (AID {best_aid}, {best_activity_name} {best_value} uM), "
            "but conflicting or inconclusive assay outcomes remain; keep deferred until manual confirmation upgrades it to claim-safe binder evidence."
        ),
        "manual_commit_note": "confirmed_defer",
        "commit_status": "confirmed_defer",
    }


def _gap_note(ligand: str, *, is_binder: bool, today_local: str) -> str:
    if is_binder:
        return (
            f"As of {today_local}, the live ChEMBL target query found no human NR1I2/PXR activity rows for {ligand}. "
            "This remains a binder-evidence gap, not a claim-safe binder confirmation."
        )
    return (
        f"As of {today_local}, the live ChEMBL target query found no human NR1I2/PXR activity rows for {ligand}. "
        "This remains an evidence gap, not a validated negative."
    )


def _gap_override(ligand: str, *, is_binder: bool) -> str:
    if is_binder:
        return f"Keep deferred until direct local human PXR binder evidence is curated for {ligand}."
    return f"Keep deferred until direct local human PXR evidence exists for {ligand}; absence of evidence is not enough to relabel."


def _activity_override(ligand: str, *, is_binder: bool) -> str:
    if is_binder:
        return (
            f"Human PXR target activity was found for {ligand}, but this still needs manual confirmation before "
            "filling authoritative binder fields."
        )
    return (
        f"Target-specific human PXR activity was found for {ligand}, so do not force a non-binder label without manual review."
    )


def _overlay_row(
    row: dict[str, Any],
    *,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
    today_local: str | None = None,
) -> dict[str, Any]:
    packet_step = _text(row.get("packet_step"))
    ligand = _text(row.get("replacement_ligand_id")).lower()
    ligand_label = _text(row.get("replacement_ligand_id"))
    is_binder = _text(row.get("replacement_is_binder")) == "1"
    molecule_chembl_id = LIGAND_CHEMBL_IDS.get(ligand, "")
    today_local = today_local or str(date.today())
    base = {
        "packet_step": packet_step,
        "replacement_ligand_id": ligand_label,
        "replacement_is_binder": _text(row.get("replacement_is_binder")),
        "molecule_chembl_id": molecule_chembl_id,
        "target_chembl_id": PXR_TARGET_CHEMBL_ID,
    }
    if not molecule_chembl_id:
        return {
            **base,
            "overlay_status": "unsupported_ligand",
            "supports_local_target_specific_human_pxr": "",
            "source_title": "",
            "source_url": "",
            "source_note": "",
            "capture_status": "",
            "manual_assay_type_honesty": "",
            "manual_promotion_blocker": "",
            "manual_next_required_action": "",
            "manual_commit_class_override": "",
            "manual_commit_note": "",
            "commit_status": "",
        }

    try:
        source_url, activities, _ = _activity_rows_for_ligand(molecule_chembl_id, fetch_json=fetch_json)
    except Exception as exc:
        return {
            **base,
            "overlay_status": "query_error",
            "supports_local_target_specific_human_pxr": "",
            "source_title": f"ChEMBL {PXR_TARGET_CHEMBL_ID} activity query for {ligand_label} failed.",
            "source_url": _activity_query_url(molecule_chembl_id),
            "source_note": f"Live query error: {exc}",
            "capture_status": "pending_capture",
            "manual_assay_type_honesty": "",
            "manual_promotion_blocker": "",
            "manual_next_required_action": "",
            "manual_commit_class_override": "",
            "manual_commit_note": "",
            "commit_status": "",
        }

    if not activities:
        pubchem_override = _pubchem_activity_override(
            ligand,
            ligand_label,
            is_binder=is_binder,
            fetch_json=fetch_json,
            today_local=today_local,
        )
        if pubchem_override:
            return {
                **base,
                **pubchem_override,
            }
        literature_override = LITERATURE_OVERRIDES.get(ligand)
        if literature_override:
            return {
                **base,
                "overlay_status": "captured_supportive",
                "supports_local_target_specific_human_pxr": "yes",
                "source_title": literature_override["source_title"],
                "source_url": literature_override["source_url"],
                "source_note": literature_override["source_note_template"].format(today_local=today_local),
                "capture_status": "captured_supportive",
                "manual_assay_type_honesty": literature_override["manual_assay_type_honesty"],
                "manual_promotion_blocker": literature_override["manual_promotion_blocker"],
                "manual_next_required_action": literature_override["manual_next_required_action"],
                "manual_commit_class_override": literature_override["manual_commit_class_override"],
                "manual_commit_note": literature_override["manual_commit_note"],
                "commit_status": literature_override["commit_status"],
            }
        return {
            **base,
            "overlay_status": "captured_gap",
            "supports_local_target_specific_human_pxr": "no",
            "source_title": f"ChEMBL {PXR_TARGET_CHEMBL_ID} activity query for {ligand_label} returned 0 records.",
            "source_url": source_url,
            "source_note": _gap_note(ligand_label, is_binder=is_binder, today_local=today_local),
            "capture_status": "captured_gap",
            "manual_assay_type_honesty": "no_local_target_activity_curated",
            "manual_promotion_blocker": "no_local_target_activity_curated",
            "manual_next_required_action": "manual_curated_search_or_defer",
            "manual_commit_class_override": _gap_override(ligand_label, is_binder=is_binder),
            "manual_commit_note": "confirmed_defer",
            "commit_status": "confirmed_defer",
        }

    summary = _activity_summary(activities)
    capture_status = "captured_supportive" if is_binder else "captured_conflict"
    assay_honesty = "activity_present_manual_confirmation_required" if is_binder else "activity_proxy_conflicts_with_non_binder"
    blocker = "activity_present_manual_confirmation_required" if is_binder else "activity_proxy_conflicts_with_non_binder"
    next_action = "manual_curated_search_or_defer"
    return {
        **base,
        "overlay_status": capture_status,
        "supports_local_target_specific_human_pxr": "yes",
        "source_title": f"ChEMBL {PXR_TARGET_CHEMBL_ID} activity query for {ligand_label} returned {len(activities)} records.",
        "source_url": source_url,
        "source_note": (
            f"As of {today_local}, the live ChEMBL target query found human NR1I2/PXR activity rows for {ligand_label}: {summary}."
        ),
        "capture_status": capture_status,
        "manual_assay_type_honesty": assay_honesty,
        "manual_promotion_blocker": blocker,
        "manual_next_required_action": next_action,
        "manual_commit_class_override": _activity_override(ligand_label, is_binder=is_binder),
        "manual_commit_note": "confirmed_defer",
        "commit_status": "confirmed_defer",
    }


def build_payload(
    capture_rows: list[dict[str, Any]],
    *,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
    today_local: str | None = None,
) -> dict[str, Any]:
    overlay_rows: list[dict[str, Any]] = []
    for row in capture_rows:
        capture_status = _text(row.get("capture_status"))
        manual_blocker = _text(row.get("manual_promotion_blocker"))
        if capture_status and capture_status not in {"pending_capture", "captured_gap", "captured_review_only", "captured_conflict"}:
            if not (
                capture_status == "captured_supportive"
                and manual_blocker == "quantitative_binding_value_or_activity_proxy_missing"
            ):
                continue
        overlay_rows.append(_overlay_row(row, fetch_json=fetch_json, today_local=today_local))

    summary = {
        "family": "pxr",
        "row_count": len(overlay_rows),
        "gap_row_count": sum(1 for row in overlay_rows if row.get("overlay_status") == "captured_gap"),
        "review_only_row_count": sum(1 for row in overlay_rows if row.get("overlay_status") == "captured_review_only"),
        "supportive_row_count": sum(1 for row in overlay_rows if row.get("overlay_status") == "captured_supportive"),
        "conflict_row_count": sum(1 for row in overlay_rows if row.get("overlay_status") == "captured_conflict"),
        "query_error_count": sum(1 for row in overlay_rows if row.get("overlay_status") == "query_error"),
        "unsupported_ligand_count": sum(1 for row in overlay_rows if row.get("overlay_status") == "unsupported_ligand"),
        "pending_row_count": sum(1 for row in overlay_rows if row.get("capture_status") == "pending_capture"),
        "source_linked_count": sum(1 for row in overlay_rows if _text(row.get("source_title")) or _text(row.get("source_url"))),
        "next_required_step": (
            "Merge the overlay into the PXR capture sheet, then rerun intake so deferred rows carry explicit public-evidence gap or conflict notes."
        ),
    }
    return {"summary": summary, "rows": overlay_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# PXR Public Evidence Overlay",
        "",
        f"- family: `{summary['family']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- gap_row_count: `{summary['gap_row_count']}`",
        f"- review_only_row_count: `{summary['review_only_row_count']}`",
        f"- supportive_row_count: `{summary['supportive_row_count']}`",
        f"- conflict_row_count: `{summary['conflict_row_count']}`",
        f"- query_error_count: `{summary['query_error_count']}`",
        f"- unsupported_ligand_count: `{summary['unsupported_ligand_count']}`",
        f"- pending_row_count: `{summary['pending_row_count']}`",
        f"- source_linked_count: `{summary['source_linked_count']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Overlay Rows",
        "",
        "| packet_step | ligand | overlay_status | capture_status | source_title |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['packet_step']}` | `{row['replacement_ligand_id']}` | `{row['overlay_status']}` | "
            f"`{row['capture_status']}` | {row['source_title']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a live public-evidence overlay for pending PXR unresolved capture rows.")
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
