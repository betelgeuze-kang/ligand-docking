#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"

DEFAULT_CANDIDATE_VERDICT_JSON = "runs/aqp1_candidate_verdict_sheet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_negative_source_exclusion_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_negative_source_exclusion_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_negative_source_exclusion_packet_current.md"

AQP1_TARGET = {
    "target_chembl_id": "CHEMBL4523210",
    "target_pref_name": "Aquaporin-1",
    "organism": "Homo sapiens",
}

CANDIDATE_CONFIG = {
    "tetraethylammonium": {
        "molecule_chembl_id": "CHEMBL9324",
        "chembl_pref_name": "TETRYLAMMONIUM",
    },
    "acetazolamide": {
        "molecule_chembl_id": "CHEMBL20",
        "chembl_pref_name": "ACETAZOLAMIDE",
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


def _load_json(path_like: str | Path) -> dict[str, Any]:
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
    req = Request(url, headers={"User-Agent": "md-aqp1-negative-source-exclusion/1.0"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _activity_lookup(
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


def _caution_rows(candidate_verdict_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in candidate_verdict_payload.get("rows", []) or []:
        if str(row.get("proposed_packet_step", "")).strip() != "caution_only":
            continue
        candidate_name = str(row.get("candidate_name", "")).strip()
        if candidate_name.lower() not in CANDIDATE_CONFIG:
            continue
        rows.append(dict(row))
    return rows


def build_payload(
    candidate_verdict_payload: dict[str, Any],
    *,
    activity_lookup: Callable[[str, str], dict[str, Any]] | None = None,
    as_of_date: str | None = None,
    throttle_sec: float = 0.34,
) -> dict[str, Any]:
    today = as_of_date or date.today().isoformat()
    rows: list[dict[str, Any]] = []

    for rank, verdict_row in enumerate(_caution_rows(candidate_verdict_payload), start=1):
        candidate_name = str(verdict_row.get("candidate_name", "")).strip()
        config = dict(CANDIDATE_CONFIG.get(candidate_name.lower(), {}) or {})
        molecule_chembl_id = str(config.get("molecule_chembl_id", "")).strip()
        query_error = ""
        activity_result: dict[str, Any] = {}
        try:
            activity_result = (activity_lookup or _activity_lookup)(
                molecule_chembl_id,
                AQP1_TARGET["target_chembl_id"],
            )
            if throttle_sec > 0:
                time.sleep(throttle_sec)
        except Exception as exc:
            query_error = str(exc)

        exact_target_pair_activity_count = int(activity_result.get("activity_count", 0) or 0)
        if query_error:
            exclusion_status = "query_error_keep_excluded"
            provenance_signal = "query_error_keep_review_only"
        elif exact_target_pair_activity_count > 0:
            exclusion_status = "unexpected_exact_target_pair_activity_present_manual_review_required"
            provenance_signal = "manual_review_required_activity_present"
        else:
            exclusion_status = "exact_human_aqp1_target_pair_absent_keep_excluded"
            provenance_signal = "exact_target_pair_absent_exclusion_keep_review_only"

        rows.append(
            {
                "exclusion_rank": rank,
                "candidate_name": candidate_name,
                "review_bucket": str(verdict_row.get("review_bucket", "")).strip(),
                "recommended_verdict": str(verdict_row.get("recommended_verdict", "")).strip(),
                "source_anchor": str(verdict_row.get("source_anchor", "")).strip(),
                "caution": str(verdict_row.get("caution", "")).strip(),
                "molecule_chembl_id": molecule_chembl_id,
                "chembl_pref_name": str(config.get("chembl_pref_name", "")).strip(),
                "target_chembl_id": AQP1_TARGET["target_chembl_id"],
                "target_pref_name": AQP1_TARGET["target_pref_name"],
                "target_organism": AQP1_TARGET["organism"],
                "exact_target_pair_activity_count": exact_target_pair_activity_count,
                "activity_url": str(activity_result.get("activity_url", "")).strip(),
                "exclusion_status": exclusion_status,
                "public_provenance_signal": provenance_signal,
                "authoritative_apply_allowed": False,
                "next_required_action": "keep_out_of_negative_packet_rows_and_authoritative_apply",
                "state_change_potential": "low" if exact_target_pair_activity_count == 0 else "medium",
                "query_error": query_error,
            }
        )

    exact_pair_absent_count = sum(
        1 for row in rows if row["exclusion_status"] == "exact_human_aqp1_target_pair_absent_keep_excluded"
    )
    summary = {
        "family": "aqp1",
        "as_of_date": today,
        "target_chembl_id": AQP1_TARGET["target_chembl_id"],
        "target_pref_name": AQP1_TARGET["target_pref_name"],
        "row_count": len(rows),
        "exact_target_pair_absent_count": exact_pair_absent_count,
        "unexpected_exact_target_pair_activity_present_count": sum(
            1
            for row in rows
            if row["exclusion_status"] == "unexpected_exact_target_pair_activity_present_manual_review_required"
        ),
        "query_error_count": sum(1 for row in rows if row["query_error"]),
        "primary_focus_ligand": rows[0]["candidate_name"] if rows else "",
        "packet_artifact": "runs/aqp1_negative_source_exclusion_packet_current.md",
        "next_required_step": (
            "Keep tetraethylammonium and acetazolamide excluded from AQP1 negative-slot promotion. "
            "Current live ChEMBL exact-pair checks recover no human AQP1 activity rows for either caution reference, "
            "so core_non_binder_01 through core_non_binder_03 remain review-only until direct transporter-specific negative evidence is curated."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Source Exclusion Packet",
        "",
        f"- family: `{s['family']}`",
        f"- as_of_date: `{s['as_of_date']}`",
        f"- target_chembl_id: `{s['target_chembl_id']}`",
        f"- target_pref_name: `{s['target_pref_name']}`",
        f"- row_count: `{s['row_count']}`",
        f"- exact_target_pair_absent_count: `{s['exact_target_pair_absent_count']}`",
        f"- unexpected_exact_target_pair_activity_present_count: `{s['unexpected_exact_target_pair_activity_present_count']}`",
        f"- query_error_count: `{s['query_error_count']}`",
        f"- primary_focus_ligand: `{s['primary_focus_ligand']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Exclusion Rows",
        "",
        "| exclusion_rank | candidate_name | source_anchor | molecule_chembl_id | exact_target_pair_activity_count | exclusion_status | public_provenance_signal |",
        "| ---: | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['exclusion_rank']} | `{row['candidate_name']}` | `{row['source_anchor']}` | "
            f"`{row['molecule_chembl_id']}` | {row['exact_target_pair_activity_count']} | "
            f"`{row['exclusion_status']}` | `{row['public_provenance_signal']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AQP1 negative-source exclusion packet.")
    parser.add_argument("--candidate-verdict-json", default=DEFAULT_CANDIDATE_VERDICT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.candidate_verdict_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
