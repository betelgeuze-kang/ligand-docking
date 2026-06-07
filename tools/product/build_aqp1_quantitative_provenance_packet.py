#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"

DEFAULT_CAPTURE_SHEET_JSON = "runs/aqp1_quantitative_binding_capture_sheet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_quantitative_provenance_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_quantitative_provenance_packet_current.md"

AQP1_TARGET = {
    "target_chembl_id": "CHEMBL4523210",
    "target_pref_name": "Aquaporin-1",
    "uniprot": "P29972",
}

CANDIDATE_CONFIG = {
    "bacopaside ii": {
        "pubchem_query_name": "bacopaside II",
        "chembl_query_name": "bacopaside II",
        "chembl_molecule_chembl_id": "CHEMBL390758",
    },
    "aqb013": {
        "pubchem_query_name": "AqB013",
        "chembl_query_name": "AqB013",
        "chembl_molecule_chembl_id": "CHEMBL5280895",
    },
    "aqb011": {
        "pubchem_query_name": "AqB011",
        "chembl_query_name": "3-(Butylamino)-4-phenoxy-N-(pyridin-3-ylmethyl)-5-sulfamoylbenzamide",
        "chembl_molecule_chembl_id": "",
    },
}


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _fetch_json(url: str) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": "md-family-expansion/1.0"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _pubchem_name_resolution(query_name: str, fetch_json: Callable[[str], dict[str, Any]] | None = None) -> dict[str, Any]:
    path = f"compound/name/{quote(query_name)}/property/CanonicalSMILES/JSON"
    url = f"{PUBCHEM_BASE}/{path}"
    payload = (fetch_json or _fetch_json)(url)
    records = list(payload.get("PropertyTable", {}).get("Properties", []) or [])
    if not records:
        return {
            "query_name": query_name,
            "resolved": False,
            "pubchem_cid": "",
            "canonical_smiles": "",
            "resolution_url": url,
        }
    record = dict(records[0])
    return {
        "query_name": query_name,
        "resolved": True,
        "pubchem_cid": str(record.get("CID", "")).strip(),
        "canonical_smiles": str(
            record.get("ConnectivitySMILES", "") or record.get("CanonicalSMILES", "")
        ).strip(),
        "resolution_url": url,
    }


def _chembl_molecule_lookup(
    query_name: str,
    preferred_molecule_chembl_id: str = "",
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    url = f"{CHEMBL_BASE}/molecule/search.json?{urlencode({'q': query_name, 'limit': 10})}"
    payload = (fetch_json or _fetch_json)(url)
    molecules = list(payload.get("molecules", []) or [])
    page_meta = dict(payload.get("page_meta", {}) or {})
    exact = None
    if preferred_molecule_chembl_id:
        for molecule in molecules:
            if str(molecule.get("molecule_chembl_id", "")).strip() == preferred_molecule_chembl_id:
                exact = molecule
                break
    if exact is None:
        query_lower = query_name.strip().lower()
        for molecule in molecules:
            pref_name = str(molecule.get("pref_name", "")).strip().lower()
            synonyms = [
                str(row.get("molecule_synonym", "")).strip().lower()
                for row in molecule.get("molecule_synonyms", []) or []
            ]
            if pref_name == query_lower or query_lower in synonyms:
                exact = molecule
                break
    structures = dict((exact or {}).get("molecule_structures", {}) or {})
    return {
        "query_name": query_name,
        "search_result_count": int(page_meta.get("total_count", len(molecules)) or 0),
        "exact_match_count": 1 if exact else 0,
        "molecule_chembl_id": str((exact or {}).get("molecule_chembl_id", "")).strip(),
        "canonical_smiles": str(structures.get("canonical_smiles", "")).strip(),
        "match_url": url,
    }


def _chembl_activity_lookup(
    molecule_chembl_id: str,
    target_chembl_id: str,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    url = (
        f"{CHEMBL_BASE}/activity.json?"
        f"{urlencode({'molecule_chembl_id': molecule_chembl_id, 'target_chembl_id': target_chembl_id, 'limit': 10})}"
    )
    payload = (fetch_json or _fetch_json)(url)
    activities = list(payload.get("activities", []) or [])
    page_meta = dict(payload.get("page_meta", {}) or {})
    return {
        "activity_url": url,
        "activity_count": int(page_meta.get("total_count", len(activities)) or 0),
        "activities": activities,
    }


def _best_activity_row(activities: list[dict[str, Any]]) -> dict[str, Any]:
    if not activities:
        return {}
    def sort_key(row: dict[str, Any]) -> tuple[int, float]:
        value = str(row.get("standard_value", "")).strip()
        try:
            numeric = float(value)
        except ValueError:
            numeric = float("inf")
        return (0 if value else 1, numeric)
    return min((dict(row) for row in activities), key=sort_key)


def _row_next_step(status: str, candidate_name: str) -> str:
    if status == "exact_human_aqp1_quantitative_activity_present_nonbinding":
        return (
            f"Carry `{candidate_name}` forward as exact human AQP1 quantitative-activity provenance, "
            "but keep replacement_reference_binding_kcal_mol blank until direct binding or a claim-safe kcal reference is curated."
        )
    if status == "compound_publicly_resolved_target_activity_absent":
        return (
            f"Keep `{candidate_name}` review-only. The compound is publicly resolved, but exact human AQP1 target activity "
            "is not present in the current ChEMBL pair lane."
        )
    if status == "pubchem_resolved_chembl_target_pair_absent":
        return (
            f"Keep `{candidate_name}` review-only. PubChem resolves the compound, but an exact ChEMBL molecule/target pair "
            "was not recovered from the current public lane."
        )
    return f"Keep `{candidate_name}` on the functional-only literature lane until stronger public target provenance appears."


def build_payload(
    capture_sheet_payload: dict[str, Any],
    *,
    pubchem_lookup: Callable[[str], dict[str, Any]] | None = None,
    chembl_molecule_lookup: Callable[[str, str], dict[str, Any]] | None = None,
    chembl_activity_lookup: Callable[[str, str], dict[str, Any]] | None = None,
    as_of_date: str | None = None,
    throttle_sec: float = 0.34,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    today = as_of_date or date.today().isoformat()

    for capture_row in capture_sheet_payload.get("rows", []) or []:
        packet_step = str(capture_row.get("packet_step", "")).strip()
        if not packet_step.startswith("core_binder_"):
            continue

        candidate_name = str(capture_row.get("candidate_name", "")).strip()
        if not candidate_name:
            continue

        config = CANDIDATE_CONFIG.get(candidate_name.lower(), {})
        pubchem_query_name = str(config.get("pubchem_query_name", "")).strip() or candidate_name
        chembl_query_name = str(config.get("chembl_query_name", "")).strip() or candidate_name
        preferred_molecule_chembl_id = str(config.get("chembl_molecule_chembl_id", "")).strip()

        query_error = ""
        pubchem_result: dict[str, Any] = {}
        chembl_result: dict[str, Any] = {}
        activity_result: dict[str, Any] = {}

        try:
            pubchem_result = (pubchem_lookup or _pubchem_name_resolution)(pubchem_query_name)
            if throttle_sec > 0:
                time.sleep(throttle_sec)
            chembl_result = (chembl_molecule_lookup or _chembl_molecule_lookup)(
                chembl_query_name, preferred_molecule_chembl_id
            )
            molecule_chembl_id = str(chembl_result.get("molecule_chembl_id", "")).strip()
            if molecule_chembl_id:
                if throttle_sec > 0:
                    time.sleep(throttle_sec)
                activity_result = (chembl_activity_lookup or _chembl_activity_lookup)(
                    molecule_chembl_id,
                    AQP1_TARGET["target_chembl_id"],
                )
        except Exception as exc:
            query_error = str(exc)

        best_activity = _best_activity_row(list(activity_result.get("activities", []) or []))
        activity_count = int(activity_result.get("activity_count", 0) or 0)
        pubchem_resolved = bool(pubchem_result.get("resolved", False))
        chembl_exact_match = int(chembl_result.get("exact_match_count", 0) or 0)

        if activity_count > 0:
            provenance_status = "exact_human_aqp1_quantitative_activity_present_nonbinding"
            signal = "exact_human_activity_present_leave_kcal_blank"
            state_change_potential = "medium"
        elif chembl_exact_match > 0:
            provenance_status = "compound_publicly_resolved_target_activity_absent"
            signal = "compound_resolved_target_activity_absent"
            state_change_potential = "low"
        elif pubchem_resolved:
            provenance_status = "pubchem_resolved_chembl_target_pair_absent"
            signal = "pubchem_resolved_target_pair_absent"
            state_change_potential = "low"
        else:
            provenance_status = "public_compound_resolution_gap"
            signal = "public_resolution_gap"
            state_change_potential = "low"

        rows.append(
            {
                "trace_rank": int(capture_row.get("priority_rank", 0) or 0),
                "as_of_date": today,
                "packet_step": packet_step,
                "candidate_name": candidate_name,
                "source_anchor": str(capture_row.get("source_anchor", "")).strip(),
                "source_title": str(capture_row.get("source_title", "")).strip(),
                "source_url": str(capture_row.get("source_url", "")).strip(),
                "current_signal": str(capture_row.get("current_signal", "")).strip(),
                "capture_status": str(capture_row.get("capture_status", "")).strip(),
                "assay_type_honesty": str(capture_row.get("assay_type_honesty", "")).strip(),
                "public_provenance_status": provenance_status,
                "public_provenance_signal": signal,
                "state_change_potential": state_change_potential,
                "pubchem_query_name": pubchem_query_name,
                "pubchem_resolved": "yes" if pubchem_resolved else "no",
                "pubchem_cid": str(pubchem_result.get("pubchem_cid", "")).strip(),
                "pubchem_canonical_smiles": str(pubchem_result.get("canonical_smiles", "")).strip(),
                "pubchem_resolution_url": str(pubchem_result.get("resolution_url", "")).strip(),
                "chembl_query_name": chembl_query_name,
                "chembl_search_result_count": int(chembl_result.get("search_result_count", 0) or 0),
                "chembl_exact_match_count": chembl_exact_match,
                "chembl_molecule_chembl_id": str(chembl_result.get("molecule_chembl_id", "")).strip(),
                "chembl_exact_match_url": str(chembl_result.get("match_url", "")).strip(),
                "chembl_activity_record_count": activity_count,
                "chembl_best_activity_type": str(best_activity.get("standard_type", "")).strip(),
                "chembl_best_activity_relation": str(best_activity.get("standard_relation", "")).strip(),
                "chembl_best_activity_value": str(best_activity.get("standard_value", "")).strip(),
                "chembl_best_activity_units": str(best_activity.get("standard_units", "")).strip(),
                "chembl_best_activity_assay_type": str(best_activity.get("assay_type", "")).strip(),
                "chembl_best_activity_assay_description": str(best_activity.get("assay_description", "")).strip(),
                "chembl_activity_url": str(activity_result.get("activity_url", "")).strip(),
                "target_chembl_id": AQP1_TARGET["target_chembl_id"],
                "target_uniprot": AQP1_TARGET["uniprot"],
                "claim_safe_binding_kcal_ready": "no",
                "next_required_step": _row_next_step(provenance_status, candidate_name),
                "query_error": query_error,
            }
        )

    rows.sort(key=lambda item: (int(item.get("trace_rank", 999) or 999), str(item.get("packet_step", ""))))
    exact_human_activity_count = sum(1 for row in rows if int(row.get("chembl_activity_record_count", 0) or 0) > 0)
    pubchem_resolved_count = sum(1 for row in rows if str(row.get("pubchem_resolved", "")).strip() == "yes")
    chembl_exact_match_count = sum(1 for row in rows if int(row.get("chembl_exact_match_count", 0) or 0) > 0)
    query_error_count = sum(1 for row in rows if str(row.get("query_error", "")).strip())
    signal = (
        "exact_human_activity_present_leave_kcal_blank"
        if exact_human_activity_count > 0
        else "quantitative_binding_absent_leave_kcal_blank"
    )
    primary_focus_ligand = ""
    for row in rows:
        if int(row.get("chembl_activity_record_count", 0) or 0) > 0:
            primary_focus_ligand = str(row.get("candidate_name", "")).strip()
            break
    if not primary_focus_ligand and rows:
        primary_focus_ligand = str(rows[0].get("candidate_name", "")).strip()

    summary = {
        "family": "aqp1",
        "as_of_date": today,
        "row_count": len(rows),
        "pubchem_resolved_count": pubchem_resolved_count,
        "chembl_exact_match_count": chembl_exact_match_count,
        "exact_human_aqp1_activity_count": exact_human_activity_count,
        "claim_safe_kcal_ready_count": 0,
        "query_error_count": query_error_count,
        "primary_focus_ligand": primary_focus_ligand,
        "signal": signal,
        "next_required_step": (
            "Carry exact human AQP1 quantitative-activity provenance forward where available, but keep replacement_reference_binding_kcal_mol blank until direct binding or a claim-safe kcal anchor is curated."
            if exact_human_activity_count > 0
            else "Keep all first-wave AQP1 binders review-only and leave replacement_reference_binding_kcal_mol blank until stronger public target provenance appears."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# AQP1 Quantitative Provenance Packet",
        "",
        f"- family: `{summary['family']}`",
        f"- as_of_date: `{summary['as_of_date']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- pubchem_resolved_count: `{summary['pubchem_resolved_count']}`",
        f"- chembl_exact_match_count: `{summary['chembl_exact_match_count']}`",
        f"- exact_human_aqp1_activity_count: `{summary['exact_human_aqp1_activity_count']}`",
        f"- claim_safe_kcal_ready_count: `{summary['claim_safe_kcal_ready_count']}`",
        f"- primary_focus_ligand: `{summary['primary_focus_ligand']}`",
        f"- signal: `{summary['signal']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Rows",
        "",
        "| rank | packet_step | candidate_name | provenance_status | pubchem_resolved | chembl_exact_match_count | chembl_activity_record_count | best_activity |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        best_activity = " ".join(
            part
            for part in (
                str(row.get("chembl_best_activity_type", "")).strip(),
                str(row.get("chembl_best_activity_relation", "")).strip(),
                str(row.get("chembl_best_activity_value", "")).strip(),
                str(row.get("chembl_best_activity_units", "")).strip(),
            )
            if part
        ) or "-"
        lines.append(
            f"| {row['trace_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['public_provenance_status']}` | `{row['pubchem_resolved']}` | "
            f"{row['chembl_exact_match_count']} | {row['chembl_activity_record_count']} | `{best_activity}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1 public quantitative-provenance packet for the first-wave binder rows.")
    parser.add_argument("--capture-sheet-json", default=DEFAULT_CAPTURE_SHEET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.capture_sheet_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
