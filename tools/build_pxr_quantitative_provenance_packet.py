#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"
BINDINGDB_BASE = "https://bindingdb.org"

DEFAULT_CAPTURE_SHEET_JSON = "runs/pxr_unresolved_evidence_capture_sheet_current.json"
DEFAULT_INVESTIGATOR_PACKET_JSON = "runs/family_evidence_investigator_packet_current.json"
DEFAULT_COMMIT_PACKET_JSON = "runs/pxr_pending_resolution_commit_packet_current.json"
DEFAULT_OUT_JSON = "runs/pxr_quantitative_provenance_packet_current.json"
DEFAULT_OUT_CSV = "runs/pxr_quantitative_provenance_packet_current.csv"
DEFAULT_OUT_MD = "runs/pxr_quantitative_provenance_packet_current.md"

TRACE_CONFIG = {
    "bexarotene": {
        "pubmed_target_query": '(LGD1069 OR bexarotene OR Targretin) AND (PXR OR SXR OR "pregnane X receptor")',
        "qualitative_support_pmid": "18544536",
        "qualitative_support_title": "Rexinoids modulate steroid and xenobiotic receptor activity by increasing its protein turnover in a calpain-dependent manner.",
        "qualitative_support_url": "https://pubmed.ncbi.nlm.nih.gov/18544536/",
        "qualitative_support_strength": "primary_abstract_human_target_support_nonquantitative",
        "qualitative_support_note": (
            "The accessible PMID 18544536 abstract directly states that rexinoids are weak activators of human SXR/PXR, "
            "names bexarotene among the rexinoids studied, and cites competition for binding to SXR. "
            "This supports a human target-specific interaction lane, but it still does not expose a bexarotene numeric human PXR value."
        ),
        "primary_trace_pmid": "10628745",
        "primary_trace_title": "The pregnane X receptor: a promiscuous xenobiotic receptor that has diverged during evolution.",
        "primary_trace_url": "https://pubmed.ncbi.nlm.nih.gov/10628745/",
        "primary_trace_note": (
            "PMID 18544536 cites PMID 10628745 as reference 8 for the SXR competition-binding sentence. "
            "The accessible PMID 10628745 abstract confirms a direct human PXR binding-assay context via a novel scintillation proximity binding assay, "
            "but it still does not expose a bexarotene-specific numeric value in the abstract."
        ),
        "review_trace_pmid": "14996618",
        "review_trace_title": "Orphan nuclear receptors, PXR and LXR: new ligands and therapeutic potential.",
        "review_trace_url": "https://pubmed.ncbi.nlm.nih.gov/14996618/",
        "review_trace_note": (
            "Review-like context mentions bexarotene as an RXR-targeting drug while discussing PXR/LXR therapeutic potential. "
            "This is not claim-safe quantitative human PXR evidence."
        ),
        "chembl_molecule_chembl_id": "CHEMBL1023",
        "chembl_target_chembl_id": "CHEMBL3401",
        "bindingdb_uniprot": "O75469",
        "canonical_smiles": "C=C(c1ccc(C(=O)O)cc1)c1cc2c(cc1C)C(C)(C)CCC2(C)C",
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


def _rows_by_step(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    payload = payload or {}
    return {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }


def _capture_name(row: dict[str, Any]) -> str:
    return str(row.get("ligand", "")).strip() or str(row.get("replacement_ligand_id", "")).strip()


def _fetch_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": "md-family-expansion/1.0"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _fetch_json(url: str) -> dict[str, Any]:
    return json.loads(_fetch_text(url))


def _pubmed_esearch_ids(query: str, *, retmax: int = 20, fetch_json: Callable[[str], dict[str, Any]] | None = None) -> list[str]:
    url = f"{PUBMED_BASE}/esearch.fcgi?{urlencode({'db': 'pubmed', 'term': query, 'retmode': 'json', 'retmax': retmax})}"
    payload = (fetch_json or _fetch_json)(url)
    return list(payload.get("esearchresult", {}).get("idlist", []) or [])


def _chembl_activity_record_count(
    molecule_chembl_id: str,
    target_chembl_id: str,
    *,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
) -> int:
    url = (
        f"{CHEMBL_BASE}/activity.json?"
        f"{urlencode({'molecule_chembl_id': molecule_chembl_id, 'target_chembl_id': target_chembl_id, 'limit': 20})}"
    )
    payload = (fetch_json or _fetch_json)(url)
    page_meta = dict(payload.get("page_meta", {}) or {})
    total_count = page_meta.get("total_count")
    if total_count is not None:
        return int(total_count or 0)
    return len(payload.get("activities", []) or [])


def _normalize_smiles(smiles: str) -> str:
    base = smiles.split("|", 1)[0]
    return re.sub(r"\s+", "", base).strip()


def _bindingdb_exact_smiles_match_count(
    uniprot: str,
    canonical_smiles: str,
    *,
    fetch_json: Callable[[str], dict[str, Any]] | None = None,
) -> int:
    url = f"{BINDINGDB_BASE}/rest/getLigandsByUniprots?{urlencode({'uniprot': uniprot, 'response': 'application/json'})}"
    payload: dict[str, Any] = {}
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            payload = (fetch_json or _fetch_json)(url)
            break
        except json.JSONDecodeError as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(0.5)
                continue
            return 0
    if not payload and last_error is not None:
        return 0
    rows = list(payload.get("getLindsByUniprotsResponse", {}).get("affinities", []) or [])
    wanted = _normalize_smiles(canonical_smiles)
    return sum(1 for row in rows if _normalize_smiles(str(row.get("smile", ""))) == wanted)


def _acceptance_gate() -> str:
    return (
        "Accept only exact human NR1I2/PXR/SXR target-specific evidence with an explicit quantitative output "
        "(for example Kd, Ki, IC50, EC50, or a claim-safe target-specific activity proxy plus assay context)."
    )


def _rejection_gate() -> str:
    return (
        "Reject RXR-only affinity, indirect CYP3A induction, review-only summaries, non-human-only evidence, and qualitative rexinoid "
        "context that still leaves the human PXR quantitative field blank."
    )


def _next_required_step(*, quantitative_value_found: bool, primary_trace_pmid: str) -> str:
    if quantitative_value_found:
        return (
            "Attach the exact quantitative human PXR source to the capture sheet, rerun intake/commit refresh, and only then fill "
            "binder-facing quantitative fields."
        )
    return (
        f"Keep the row deferred on the quantitative-gap lane. Manual follow-up should target the primary-source trail around PMID {primary_trace_pmid} "
        "or an equivalent authoritative assay table that exposes a numeric human PXR value."
    )


def _should_include_row(capture_row: dict[str, Any]) -> bool:
    blocker = str(capture_row.get("manual_promotion_blocker", "")).strip()
    honesty = str(capture_row.get("manual_assay_type_honesty", "")).strip()
    capture_status = str(capture_row.get("capture_status", "")).strip()
    evidence_need_class = str(capture_row.get("evidence_need_class", "")).strip()
    if blocker == "quantitative_binding_value_or_activity_proxy_missing" or "quantitative_value_missing" in honesty:
        return True
    return (
        blocker == "activity_present_manual_confirmation_required"
        and capture_status == "captured_supportive"
        and evidence_need_class == "target_specific_human_pxr_binder_evidence"
    )


def build_payload(
    capture_sheet_payload: dict[str, Any],
    investigator_packet_payload: dict[str, Any],
    commit_packet_payload: dict[str, Any],
    *,
    pubmed_search_ids: Callable[[str], list[str]] | None = None,
    chembl_activity_count: Callable[[str, str], int] | None = None,
    bindingdb_exact_match_count: Callable[[str, str], int] | None = None,
    as_of_date: str | None = None,
    throttle_sec: float = 0.34,
) -> dict[str, Any]:
    investigator_by_step = _rows_by_step(investigator_packet_payload)
    commit_by_step = _rows_by_step(commit_packet_payload)
    rows: list[dict[str, Any]] = []
    today = as_of_date or date.today().isoformat()

    for capture_row in capture_sheet_payload.get("rows", []) or []:
        if not _should_include_row(capture_row):
            continue
        blocker = str(capture_row.get("manual_promotion_blocker", "")).strip()
        honesty = str(capture_row.get("manual_assay_type_honesty", "")).strip()

        ligand = _capture_name(capture_row)
        if not ligand:
            continue
        config = TRACE_CONFIG.get(ligand.lower(), {})
        step = str(capture_row.get("packet_step", "")).strip()
        investigator_row = investigator_by_step.get(step, {})
        commit_row = commit_by_step.get(step, {})

        pubmed_query = str(
            config.get("pubmed_target_query", investigator_row.get("search_query", ""))
        ).strip()
        pubmed_ids: list[str] = []
        chembl_count: int | None = None
        bindingdb_count: int | None = None
        query_error = ""

        try:
            if pubmed_query:
                if throttle_sec > 0:
                    time.sleep(throttle_sec)
                pubmed_ids = list((pubmed_search_ids or _pubmed_esearch_ids)(pubmed_query) or [])
            molecule_id = str(config.get("chembl_molecule_chembl_id", "")).strip()
            target_id = str(config.get("chembl_target_chembl_id", "")).strip()
            if molecule_id and target_id:
                if throttle_sec > 0:
                    time.sleep(throttle_sec)
                chembl_count = int((chembl_activity_count or _chembl_activity_record_count)(molecule_id, target_id))
            uniprot = str(config.get("bindingdb_uniprot", "")).strip()
            canonical_smiles = str(config.get("canonical_smiles", "")).strip()
            if uniprot and canonical_smiles:
                if throttle_sec > 0:
                    time.sleep(throttle_sec)
                bindingdb_count = int(
                    (bindingdb_exact_match_count or _bindingdb_exact_smiles_match_count)(uniprot, canonical_smiles)
                )
        except Exception as exc:
            query_error = str(exc)

        quantitative_value_found = bool((chembl_count or 0) > 0 or (bindingdb_count or 0) > 0)
        qualitative_support_pmid = str(config.get("qualitative_support_pmid", "")).strip()
        primary_trace_pmid = str(config.get("primary_trace_pmid", "")).strip()
        review_trace_pmid = str(config.get("review_trace_pmid", "")).strip()

        rows.append(
            {
                "trace_rank": 0,
                "as_of_date": today,
                "packet_step": step,
                "ligand": ligand,
                "provenance_scope": (
                    "supportive_manual_confirmation_quantitative_gap"
                    if blocker == "activity_present_manual_confirmation_required"
                    else "explicit_quantitative_gap"
                ),
                "capture_status": str(capture_row.get("capture_status", "")).strip(),
                "policy_bucket": str(capture_row.get("policy_bucket", "")).strip(),
                "manual_assay_type_honesty": honesty,
                "manual_promotion_blocker": blocker,
                "next_required_action": str(capture_row.get("manual_next_required_action", "")).strip()
                or str(capture_row.get("next_required_action", "")).strip(),
                "qualitative_support_pmid": qualitative_support_pmid,
                "qualitative_support_title": str(config.get("qualitative_support_title", "")).strip()
                or str(capture_row.get("source_title", "")).strip(),
                "qualitative_support_url": str(config.get("qualitative_support_url", "")).strip()
                or str(capture_row.get("source_url", "")).strip(),
                "qualitative_support_strength": str(config.get("qualitative_support_strength", "")).strip()
                or "supportive_source_present_strength_unspecified",
                "qualitative_support_note": str(config.get("qualitative_support_note", "")).strip()
                or str(capture_row.get("source_note", "")).strip(),
                "pubmed_exact_target_query": pubmed_query,
                "pubmed_exact_target_query_url": (
                    f"https://pubmed.ncbi.nlm.nih.gov/?term={quote_plus(pubmed_query)}" if pubmed_query else ""
                ),
                "pubmed_exact_target_hit_count": len(pubmed_ids),
                "pubmed_exact_target_pmids": ",".join(pubmed_ids),
                "primary_trace_pmid": primary_trace_pmid,
                "primary_trace_title": str(config.get("primary_trace_title", "")).strip(),
                "primary_trace_url": str(config.get("primary_trace_url", "")).strip(),
                "primary_trace_note": str(config.get("primary_trace_note", "")).strip(),
                "review_trace_pmid": review_trace_pmid,
                "review_trace_title": str(config.get("review_trace_title", "")).strip(),
                "review_trace_url": str(config.get("review_trace_url", "")).strip(),
                "review_trace_note": str(config.get("review_trace_note", "")).strip(),
                "chembl_molecule_chembl_id": str(config.get("chembl_molecule_chembl_id", "")).strip(),
                "chembl_target_chembl_id": str(config.get("chembl_target_chembl_id", "")).strip(),
                "chembl_target_activity_record_count": "" if chembl_count is None else int(chembl_count),
                "bindingdb_uniprot": str(config.get("bindingdb_uniprot", "")).strip(),
                "bindingdb_exact_smiles_match_count": "" if bindingdb_count is None else int(bindingdb_count),
                "quantitative_value_found": "yes" if quantitative_value_found else "no",
                "investigator_search_query": str(investigator_row.get("search_query", "")).strip(),
                "investigator_stop_condition": str(investigator_row.get("stop_condition", "")).strip(),
                "current_commit_note": str(commit_row.get("commit_note", "")).strip(),
                "acceptance_gate": _acceptance_gate(),
                "rejection_gate": _rejection_gate(),
                "query_error": query_error,
                "next_required_step": _next_required_step(
                    quantitative_value_found=quantitative_value_found,
                    primary_trace_pmid=primary_trace_pmid or qualitative_support_pmid,
                ),
            }
        )

    rows.sort(key=lambda row: str(row.get("packet_step", "")))
    for idx, row in enumerate(rows, start=1):
        row["trace_rank"] = idx

    summary = {
        "as_of_date": today,
        "row_count": len(rows),
        "supportive_manual_confirmation_gap_count": sum(
            1 for row in rows if row["provenance_scope"] == "supportive_manual_confirmation_quantitative_gap"
        ),
        "quantitative_value_found_count": sum(1 for row in rows if row["quantitative_value_found"] == "yes"),
        "chembl_zero_activity_count": sum(
            1 for row in rows if row["chembl_target_activity_record_count"] in {0, "0"}
        ),
        "bindingdb_exact_gap_count": sum(
            1 for row in rows if row["bindingdb_exact_smiles_match_count"] in {0, "0"}
        ),
        "pubmed_trace_ready_count": sum(1 for row in rows if int(row["pubmed_exact_target_hit_count"] or 0) > 0),
        "primary_focus_ligand": str(rows[0].get("ligand", "")).strip() if rows else "",
        "next_required_step": (
            "Treat the quantitative-provenance packet as the blocker ledger for literature-confirmed or supportive-manual-confirmation binder rows. "
            "Do not fill quantitative binder fields until an explicit human PXR value/proxy is attached."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# PXR Quantitative Provenance Packet",
        "",
        f"- as_of_date: `{s['as_of_date']}`",
        f"- row_count: `{s['row_count']}`",
        f"- supportive_manual_confirmation_gap_count: `{s['supportive_manual_confirmation_gap_count']}`",
        f"- quantitative_value_found_count: `{s['quantitative_value_found_count']}`",
        f"- chembl_zero_activity_count: `{s['chembl_zero_activity_count']}`",
        f"- bindingdb_exact_gap_count: `{s['bindingdb_exact_gap_count']}`",
        f"- pubmed_trace_ready_count: `{s['pubmed_trace_ready_count']}`",
        f"- primary_focus_ligand: `{s['primary_focus_ligand']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Rows",
        "",
        "| trace_rank | ligand | packet_step | provenance_scope | pubmed_exact_target_hit_count | chembl_target_activity_record_count | bindingdb_exact_smiles_match_count | quantitative_value_found |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['trace_rank']} | `{row['ligand']}` | `{row['packet_step']}` | `{row['provenance_scope']}` | "
            f"{row['pubmed_exact_target_hit_count']} | {row['chembl_target_activity_record_count']} | "
            f"{row['bindingdb_exact_smiles_match_count']} | `{row['quantitative_value_found']}` |"
        )
    lines.extend(["", "## Trace Notes", ""])
    for row in payload["rows"]:
        lines.append(
            f"- `{row['ligand']}` qualitative support: `{row['qualitative_support_pmid']}` {row['qualitative_support_title']} "
            f"(`{row['qualitative_support_strength']}`)"
        )
        lines.append(f"- `{row['ligand']}` primary trace: `{row['primary_trace_pmid']}` {row['primary_trace_note']}")
        if row["review_trace_pmid"]:
            lines.append(f"- `{row['ligand']}` review trace: `{row['review_trace_pmid']}` {row['review_trace_note']}")
        lines.append(f"- `{row['ligand']}` accept: {row['acceptance_gate']}")
        lines.append(f"- `{row['ligand']}` reject: {row['rejection_gate']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a reviewer-facing packet for PXR rows blocked on quantitative provenance.")
    parser.add_argument("--capture-sheet-json", default=DEFAULT_CAPTURE_SHEET_JSON)
    parser.add_argument("--investigator-packet-json", default=DEFAULT_INVESTIGATOR_PACKET_JSON)
    parser.add_argument("--commit-packet-json", default=DEFAULT_COMMIT_PACKET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.capture_sheet_json),
        _load_json(args.investigator_packet_json),
        _load_json(args.commit_packet_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
