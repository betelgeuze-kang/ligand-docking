#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_EXACT_REVIEW_JSON = RUNS / "pxr_exact_evidence_review_intake_template_current.json"
DEFAULT_SOURCE_DIR = RUNS / "pxr_public_evidence_recheck_sources"
DEFAULT_OUT_JSON = RUNS / "pxr_public_evidence_recheck_packet_current.json"
DEFAULT_OUT_CSV = RUNS / "pxr_public_evidence_recheck_packet_current.csv"
DEFAULT_OUT_MD = RUNS / "pxr_public_evidence_recheck_packet_current.md"

TARGET_CHEMBL_ID = "CHEMBL3401"
TARGET_UNIPROT = "O75469"
CLAIM_SAFE_BINDING_TYPES = {"KI", "KD", "IC50"}

KNOWN_MOLECULES = {
    "acetaminophen": "CHEMBL112",
    "caffeine": "CHEMBL113",
    "nicotinamide": "CHEMBL1140",
    "ibuprofen": "CHEMBL521",
    "aspirin": "CHEMBL25",
    "bexarotene": "CHEMBL1023",
}

CLAIM_BOUNDARY = (
    "PXR public evidence recheck packet only; reads saved ChEMBL and BindingDB raw payloads for the current "
    "human NR1I2/PXR exact-review candidates and classifies whether public direct or claim-safe quantitative "
    "binding evidence is already present. It does not fetch network data, fill placeholders, promote scope, run "
    "docking, or mutate external state beyond writing this local audit artifact."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


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
    rows = packet.get("rows")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _source_path(source_dir: str | Path, pattern: str) -> Path:
    return _resolve(source_dir) / pattern


def _chembl_activity_payload(source_dir: str | Path, ligand: str, molecule_id: str) -> dict[str, Any]:
    return _read_json(
        _source_path(
            source_dir,
            f"chembl_activity_{ligand}_{molecule_id}_{TARGET_CHEMBL_ID}.json",
        )
    )


def _bindingdb_payload(source_dir: str | Path, ligand: str) -> dict[str, Any]:
    return _read_json(_source_path(source_dir, f"bindingdb_target_{ligand}.json"))


def _bindingdb_affinities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    root = payload.get("getLindsByUniprotResponse")
    if not isinstance(root, dict):
        root = payload.get("getLindsByUniprotsResponse")
    if not isinstance(root, dict):
        return []
    rows = root.get("bdb.affinities") or root.get("affinities") or []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _bindingdb_hit_count(payload: dict[str, Any]) -> int:
    root = payload.get("getLindsByUniprotResponse")
    if not isinstance(root, dict):
        root = payload.get("getLindsByUniprotsResponse")
    if not isinstance(root, dict):
        return 0
    try:
        return int(float(root.get("bdb.hit") or 0))
    except (TypeError, ValueError):
        return 0


def _pxr_like_bindingdb_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in _bindingdb_affinities(payload):
        text = json.dumps(row, sort_keys=True, ensure_ascii=False).lower()
        if any(marker in text for marker in ("o75469", "nr1i2", "pregnane", "nuclear receptor subfamily 1 group i member 2")):
            rows.append(row)
    return rows


def _activity_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in payload.get("activities", []) or [] if isinstance(row, dict)]


def _standard_type(row: dict[str, Any]) -> str:
    return _text(row.get("standard_type")).upper()


def _has_quantitative_value(row: dict[str, Any]) -> bool:
    return bool(_text(row.get("standard_value"))) and bool(_text(row.get("standard_units")))


def _direct_binding_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if _text(row.get("assay_type")).upper() == "B"
        and _standard_type(row) in CLAIM_SAFE_BINDING_TYPES
        and _has_quantitative_value(row)
    ]


def _functional_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _text(row.get("assay_type")).upper() == "F"]


def _first_activity_signature(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    row = rows[0]
    return "::".join(
        item
        for item in [
            _text(row.get("assay_chembl_id")),
            _text(row.get("standard_type")),
            _text(row.get("standard_relation")),
            _text(row.get("standard_value")),
            _text(row.get("standard_units")),
            _text(row.get("document_chembl_id")),
        ]
        if item
    )


def _decision(*, direct_count: int, pxr_like_bindingdb_count: int, functional_count: int) -> tuple[str, str]:
    if direct_count > 0 or pxr_like_bindingdb_count > 0:
        return "operator_verify_direct_binding_before_fill", "public_direct_binding_candidate_present"
    if functional_count > 0:
        return "keep_blocked_functional_activity_not_binding_kcal_claim_safe", "functional_activity_proxy_only"
    return "keep_blocked_no_public_direct_or_claim_safe_pxr_binding_evidence", "no_public_target_pair_quantitative_binding_evidence"


def _row(review_row: dict[str, Any], source_dir: str | Path) -> dict[str, Any]:
    ligand = _text(review_row.get("candidate_name")).lower()
    molecule_id = KNOWN_MOLECULES.get(ligand, "")
    chembl_payload = _chembl_activity_payload(source_dir, ligand, molecule_id) if molecule_id else {}
    bindingdb_payload = _bindingdb_payload(source_dir, ligand)
    activities = _activity_rows(chembl_payload)
    direct = _direct_binding_rows(activities)
    functional = _functional_rows(activities)
    bindingdb_pxr = _pxr_like_bindingdb_rows(bindingdb_payload)
    decision, blocker = _decision(
        direct_count=len(direct),
        pxr_like_bindingdb_count=len(bindingdb_pxr),
        functional_count=len(functional),
    )
    return {
        "review_row_id": _text(review_row.get("review_row_id")),
        "candidate_name": ligand,
        "packet_step": _text(review_row.get("packet_step")),
        "target_gene": _text(review_row.get("target_gene")) or "NR1I2",
        "target_alias": _text(review_row.get("target_alias")) or "PXR",
        "target_species": _text(review_row.get("target_species")) or "human",
        "target_chembl_id": TARGET_CHEMBL_ID,
        "target_uniprot_accession": TARGET_UNIPROT,
        "molecule_chembl_id": molecule_id,
        "chembl_activity_raw_artifact": (
            f"{DEFAULT_SOURCE_DIR.as_posix()}/chembl_activity_{ligand}_{molecule_id}_{TARGET_CHEMBL_ID}.json"
            if molecule_id
            else ""
        ),
        "chembl_activity_record_count": len(activities),
        "chembl_direct_binding_record_count": len(direct),
        "chembl_functional_activity_record_count": len(functional),
        "chembl_first_activity_signature": _first_activity_signature(activities),
        "bindingdb_raw_artifact": f"{DEFAULT_SOURCE_DIR.as_posix()}/bindingdb_target_{ligand}.json",
        "bindingdb_compound_target_hit_count": _bindingdb_hit_count(bindingdb_payload),
        "bindingdb_pxr_like_record_count": len(bindingdb_pxr),
        "public_direct_or_claim_safe_binding_kcal_ready": bool(len(direct) > 0 or len(bindingdb_pxr) > 0),
        "public_recheck_decision": decision,
        "public_recheck_blocker": blocker,
        "scope_promotion_allowed": False,
        "authoritative_apply_allowed": False,
        "external_state_mutated": False,
    }


def build_payload(
    *,
    exact_review_packet: dict[str, Any],
    source_dir: str | Path = DEFAULT_SOURCE_DIR,
    exact_review_path: str = DEFAULT_EXACT_REVIEW_JSON.as_posix(),
) -> dict[str, Any]:
    rows = [_row(row, source_dir) for row in _rows(exact_review_packet)]
    direct_ready = [row for row in rows if row["public_direct_or_claim_safe_binding_kcal_ready"] is True]
    functional_proxy = [
        row for row in rows if row["public_recheck_blocker"] == "functional_activity_proxy_only"
    ]
    no_public = [
        row
        for row in rows
        if row["public_recheck_blocker"] == "no_public_target_pair_quantitative_binding_evidence"
    ]
    first_blocked = next((row for row in rows if row["public_direct_or_claim_safe_binding_kcal_ready"] is False), {})
    summary = {
        "packet_type": "pxr_public_evidence_recheck_packet",
        "status": (
            "pxr_public_evidence_recheck_has_direct_candidates"
            if direct_ready
            else "blocked_pxr_public_evidence_recheck_no_direct_candidates"
        ),
        "public_evidence_recheck_ready": bool(rows),
        "exact_review_artifact": exact_review_path,
        "public_recheck_artifact": DEFAULT_OUT_JSON.as_posix(),
        "source_dir": str(source_dir),
        "target_chembl_id": TARGET_CHEMBL_ID,
        "target_uniprot_accession": TARGET_UNIPROT,
        "target_gene": "NR1I2",
        "target_alias": "PXR",
        "target_species": "human",
        "candidate_count": len(rows),
        "chembl_activity_total_record_count": sum(int(row["chembl_activity_record_count"]) for row in rows),
        "chembl_direct_binding_total_record_count": sum(int(row["chembl_direct_binding_record_count"]) for row in rows),
        "chembl_functional_activity_total_record_count": sum(int(row["chembl_functional_activity_record_count"]) for row in rows),
        "bindingdb_compound_target_total_hit_count": sum(int(row["bindingdb_compound_target_hit_count"]) for row in rows),
        "bindingdb_pxr_like_total_record_count": sum(int(row["bindingdb_pxr_like_record_count"]) for row in rows),
        "public_direct_or_claim_safe_binding_kcal_ready_count": len(direct_ready),
        "functional_activity_proxy_only_count": len(functional_proxy),
        "no_public_target_pair_quantitative_binding_evidence_count": len(no_public),
        "all_candidates_remain_blocked": bool(rows) and not direct_ready,
        "first_blocked_candidate_name": _text(first_blocked.get("candidate_name")),
        "first_blocked_review_row_id": _text(first_blocked.get("review_row_id")),
        "first_blocked_reason": _text(first_blocked.get("public_recheck_blocker")),
        "triage_decision": (
            "keep_pxr_exact_review_rows_blocked_until_direct_or_claim_safe_public_binding_evidence_is_curated"
        ),
        "next_required_step": (
            "Do not fill PXR kcal placeholders from the current public recheck. The saved ChEMBL/BindingDB payloads "
            "contain no direct or claim-safe human NR1I2/PXR binding-kcal evidence for the six current candidates; "
            "either curate a stronger primary source or replace candidates with claim-safe evidence-backed rows."
        ),
        "scope_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
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
        "# PXR Public Evidence Recheck Packet",
        "",
        f"- status: `{s['status']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- chembl_direct_binding_total_record_count: `{s['chembl_direct_binding_total_record_count']}`",
        f"- chembl_functional_activity_total_record_count: `{s['chembl_functional_activity_total_record_count']}`",
        f"- bindingdb_pxr_like_total_record_count: `{s['bindingdb_pxr_like_total_record_count']}`",
        f"- public_direct_or_claim_safe_binding_kcal_ready_count: `{s['public_direct_or_claim_safe_binding_kcal_ready_count']}`",
        f"- triage_decision: `{s['triage_decision']}`",
        "",
        "## Rows",
        "",
        "| candidate | ChEMBL activity | ChEMBL binding | ChEMBL functional | BindingDB PXR-like | decision |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['candidate_name']}` | {row['chembl_activity_record_count']} | "
            f"{row['chembl_direct_binding_record_count']} | {row['chembl_functional_activity_record_count']} | "
            f"{row['bindingdb_pxr_like_record_count']} | `{row['public_recheck_decision']}` |"
        )
    lines.extend(["", "## Next Step", "", s["next_required_step"], "", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PXR public evidence recheck packet from saved raw payloads.")
    parser.add_argument("--exact-review-json", default=DEFAULT_EXACT_REVIEW_JSON.as_posix())
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR.as_posix())
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON.as_posix())
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV.as_posix())
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD.as_posix())
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        exact_review_packet=_read_json(args.exact_review_json),
        source_dir=args.source_dir,
        exact_review_path=args.exact_review_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
