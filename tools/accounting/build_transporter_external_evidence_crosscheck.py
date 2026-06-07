#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")
SKILL_RUNS = RUNS / "life_science_skill_crosscheck"

DEFAULT_AQP1_CHEMBL_ACTIVITY_JSON = SKILL_RUNS / "chembl_activity_aqp1_sodium_nitroprusside.json"
DEFAULT_AQP1_CHEMBL_TARGET_ACTIVITY_JSON = SKILL_RUNS / "chembl_activity_aqp1_target_latest.json"
DEFAULT_GLUT1_CYTO_CHB_ACTIVITY_JSON = SKILL_RUNS / "chembl_activity_glut1_cytochalasin_b.json"
DEFAULT_GLUT1_WZB117_ACTIVITY_JSON = SKILL_RUNS / "chembl_activity_glut1_wzb117.json"
DEFAULT_GLUT1_STF31_ACTIVITY_JSON = SKILL_RUNS / "chembl_activity_glut1_stf31.json"
DEFAULT_BINDINGDB_AQP1_JSON = SKILL_RUNS / "bindingdb_aqp1_p29972.json"
DEFAULT_BINDINGDB_GLUT1_JSON = SKILL_RUNS / "bindingdb_glut1_p11166.json"
DEFAULT_PUBMED_AQP1_SNP_JSON = SKILL_RUNS / "pubmed_aqp1_sodium_nitroprusside.json"
DEFAULT_PUBMED_AQP1_TEA_JSON = SKILL_RUNS / "pubmed_aqp1_tetraethylammonium.json"
DEFAULT_PUBMED_AQP1_DMSO_JSON = SKILL_RUNS / "pubmed_aqp1_dmso.json"
DEFAULT_PUBMED_GLUT1_JSON = SKILL_RUNS / "pubmed_glut1_binders.json"
DEFAULT_PUBMED_KEY_SUMMARIES_JSON = SKILL_RUNS / "pubmed_key_summaries.json"
DEFAULT_RCSB_4PYP_JSON = SKILL_RUNS / "rcsb_entry_4pyp.json"
DEFAULT_OUT_JSON = RUNS / "transporter_external_evidence_crosscheck_current.json"
DEFAULT_OUT_CSV = RUNS / "transporter_external_evidence_crosscheck_current.csv"
DEFAULT_OUT_MD = RUNS / "transporter_external_evidence_crosscheck_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _activities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    activities = payload.get("activities", [])
    return [dict(row) for row in activities if isinstance(row, dict)]


def _activity_count(payload: dict[str, Any]) -> int:
    return len(_activities(payload))


def _quantitative_activity_count(payload: dict[str, Any]) -> int:
    return sum(1 for row in _activities(payload) if _text(row.get("standard_type")) and _text(row.get("standard_value")))


def _target_functional_quantitative_activity_count(payload: dict[str, Any]) -> int:
    return sum(
        1
        for row in _activities(payload)
        if _text(row.get("standard_type")).upper() in {"IC50", "EC50"}
        and _text(row.get("standard_value"))
        and _text(row.get("target_organism")).lower() == "homo sapiens"
    )


def _target_direct_binding_activity_count(payload: dict[str, Any]) -> int:
    return sum(
        1
        for row in _activities(payload)
        if _text(row.get("standard_type")).upper() in {"KD", "KI"}
        and _text(row.get("standard_value"))
        and _text(row.get("target_organism")).lower() == "homo sapiens"
    )


def _target_unquantified_not_active_count(payload: dict[str, Any]) -> int:
    return sum(
        1
        for row in _activities(payload)
        if _text(row.get("activity_comment")).lower() == "not active" and not _text(row.get("standard_value"))
    )


def _pchembl_values(payload: dict[str, Any]) -> str:
    values = [_text(row.get("pchembl_value")) for row in _activities(payload) if _text(row.get("pchembl_value"))]
    return ",".join(values)


def _best_ic50_nm(payload: dict[str, Any]) -> str:
    values: list[float] = []
    for row in _activities(payload):
        if _text(row.get("standard_type")).upper() != "IC50":
            continue
        if _text(row.get("standard_units")).lower() != "nm":
            continue
        try:
            values.append(float(row.get("standard_value")))
        except (TypeError, ValueError):
            continue
    if not values:
        return ""
    best = min(values)
    return str(int(best)) if best.is_integer() else str(best)


def _bindingdb_affinity_count(payload: dict[str, Any]) -> int:
    response = payload.get("getLindsByUniprotsResponse", {}) if isinstance(payload, dict) else {}
    affinities = response.get("affinities", []) if isinstance(response, dict) else []
    return len(affinities if isinstance(affinities, list) else [])


def _pubmed_count(payload: dict[str, Any]) -> int:
    esearch = payload.get("esearchresult", {}) if isinstance(payload, dict) else {}
    if isinstance(esearch, dict):
        return _int(esearch.get("count") or len(esearch.get("idlist", []) or []))
    return 0


def _summary_title(payload: dict[str, Any], pmid: str) -> str:
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    row = result.get(pmid, {}) if isinstance(result, dict) else {}
    return _text(row.get("title"))


def _rcsb_title(payload: dict[str, Any]) -> str:
    citation = payload.get("citation", []) if isinstance(payload, dict) else []
    if citation and isinstance(citation[0], dict):
        return _text(citation[0].get("title"))
    struct = payload.get("struct", {}) if isinstance(payload, dict) else {}
    return _text(struct.get("title"))


def build_payload(
    aqp1_chembl_activity: dict[str, Any],
    aqp1_chembl_target_activity: dict[str, Any],
    glut1_cyto_activity: dict[str, Any],
    glut1_wzb117_activity: dict[str, Any],
    glut1_stf31_activity: dict[str, Any],
    bindingdb_aqp1: dict[str, Any],
    bindingdb_glut1: dict[str, Any],
    pubmed_aqp1_snp: dict[str, Any],
    pubmed_aqp1_tea: dict[str, Any],
    pubmed_aqp1_dmso: dict[str, Any],
    pubmed_glut1: dict[str, Any],
    pubmed_key_summaries: dict[str, Any],
    rcsb_4pyp: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        {
            "target_id": "AQP1",
            "target_accession": "P29972",
            "target_chembl_id": "CHEMBL4523210",
            "candidate": "AQP1 target-wide ChEMBL functional inventory",
            "candidate_chembl_id": "",
            "evidence_role": "target_wide_functional_activity_inventory",
            "chembl_exact_activity_count": _activity_count(aqp1_chembl_target_activity),
            "chembl_quantitative_activity_count": _quantitative_activity_count(aqp1_chembl_target_activity),
            "chembl_functional_quantitative_activity_count": _target_functional_quantitative_activity_count(
                aqp1_chembl_target_activity
            ),
            "chembl_direct_binding_activity_count": _target_direct_binding_activity_count(aqp1_chembl_target_activity),
            "chembl_unquantified_not_active_count": _target_unquantified_not_active_count(aqp1_chembl_target_activity),
            "best_ic50_nm": _best_ic50_nm(aqp1_chembl_target_activity),
            "pubmed_query_hit_count": _pubmed_count(pubmed_aqp1_snp),
            "bindingdb_target_affinity_count": _bindingdb_affinity_count(bindingdb_aqp1),
            "direct_negative_quantitative_row_found": False,
            "authoritative_negative_apply_allowed": False,
            "interpretation": "exact_human_functional_activity_present_no_direct_binding_kcal",
            "source_artifacts": "runs/life_science_skill_crosscheck/chembl_activity_aqp1_target_latest.json;runs/life_science_skill_crosscheck/bindingdb_aqp1_p29972.json",
        },
        {
            "target_id": "AQP1",
            "target_accession": "P29972",
            "target_chembl_id": "CHEMBL4523210",
            "candidate": "sodium nitroprusside",
            "candidate_chembl_id": "CHEMBL136478",
            "evidence_role": "negative_candidate_probe",
            "chembl_exact_activity_count": _activity_count(aqp1_chembl_activity),
            "chembl_quantitative_activity_count": _quantitative_activity_count(aqp1_chembl_activity),
            "best_ic50_nm": _best_ic50_nm(aqp1_chembl_activity),
            "pubmed_query_hit_count": _pubmed_count(pubmed_aqp1_snp),
            "bindingdb_target_affinity_count": _bindingdb_affinity_count(bindingdb_aqp1),
            "direct_negative_quantitative_row_found": False,
            "authoritative_negative_apply_allowed": False,
            "interpretation": "review_only_literature_context_no_exact_quantitative_target_pair",
            "source_artifacts": "runs/life_science_skill_crosscheck/chembl_activity_aqp1_sodium_nitroprusside.json;runs/life_science_skill_crosscheck/pubmed_aqp1_sodium_nitroprusside.json;runs/life_science_skill_crosscheck/bindingdb_aqp1_p29972.json",
        },
        {
            "target_id": "AQP1",
            "target_accession": "P29972",
            "target_chembl_id": "CHEMBL4523210",
            "candidate": "tetraethylammonium / dimethyl sulfoxide",
            "candidate_chembl_id": "",
            "evidence_role": "caution_or_solvent_context",
            "chembl_exact_activity_count": 0,
            "chembl_quantitative_activity_count": 0,
            "best_ic50_nm": "",
            "pubmed_query_hit_count": _pubmed_count(pubmed_aqp1_tea) + _pubmed_count(pubmed_aqp1_dmso),
            "bindingdb_target_affinity_count": _bindingdb_affinity_count(bindingdb_aqp1),
            "direct_negative_quantitative_row_found": False,
            "authoritative_negative_apply_allowed": False,
            "interpretation": "exclude_as_authoritative_negative_replacement",
            "source_artifacts": "runs/life_science_skill_crosscheck/pubmed_aqp1_tetraethylammonium.json;runs/life_science_skill_crosscheck/pubmed_aqp1_dmso.json",
        },
        {
            "target_id": "GLUT1",
            "target_accession": "P11166",
            "target_chembl_id": "CHEMBL2535",
            "candidate": "cytochalasin B",
            "candidate_chembl_id": "CHEMBL411729",
            "evidence_role": "positive_inhibitor_context",
            "chembl_exact_activity_count": _activity_count(glut1_cyto_activity),
            "chembl_quantitative_activity_count": _quantitative_activity_count(glut1_cyto_activity),
            "best_ic50_nm": _best_ic50_nm(glut1_cyto_activity),
            "pchembl_values": _pchembl_values(glut1_cyto_activity),
            "pubmed_query_hit_count": _pubmed_count(pubmed_glut1),
            "bindingdb_target_affinity_count": _bindingdb_affinity_count(bindingdb_glut1),
            "direct_negative_quantitative_row_found": False,
            "authoritative_negative_apply_allowed": False,
            "interpretation": "positive_inhibitor_not_negative_replacement",
            "source_artifacts": "runs/life_science_skill_crosscheck/chembl_activity_glut1_cytochalasin_b.json;runs/life_science_skill_crosscheck/pubmed_glut1_binders.json;runs/life_science_skill_crosscheck/rcsb_entry_4pyp.json",
        },
        {
            "target_id": "GLUT1",
            "target_accession": "P11166",
            "target_chembl_id": "CHEMBL2535",
            "candidate": "WZB117",
            "candidate_chembl_id": "CHEMBL3092944",
            "evidence_role": "positive_inhibitor_context",
            "chembl_exact_activity_count": _activity_count(glut1_wzb117_activity),
            "chembl_quantitative_activity_count": _quantitative_activity_count(glut1_wzb117_activity),
            "best_ic50_nm": _best_ic50_nm(glut1_wzb117_activity),
            "pchembl_values": _pchembl_values(glut1_wzb117_activity),
            "pubmed_query_hit_count": _pubmed_count(pubmed_glut1),
            "bindingdb_target_affinity_count": _bindingdb_affinity_count(bindingdb_glut1),
            "direct_negative_quantitative_row_found": False,
            "authoritative_negative_apply_allowed": False,
            "interpretation": "positive_inhibitor_not_negative_replacement",
            "source_artifacts": "runs/life_science_skill_crosscheck/chembl_activity_glut1_wzb117.json;runs/life_science_skill_crosscheck/pubmed_glut1_binders.json",
        },
        {
            "target_id": "GLUT1",
            "target_accession": "P11166",
            "target_chembl_id": "CHEMBL2535",
            "candidate": "STF-31",
            "candidate_chembl_id": "CHEMBL3105156",
            "evidence_role": "literature_functional_context",
            "chembl_exact_activity_count": _activity_count(glut1_stf31_activity),
            "chembl_quantitative_activity_count": _quantitative_activity_count(glut1_stf31_activity),
            "best_ic50_nm": _best_ic50_nm(glut1_stf31_activity),
            "pchembl_values": _pchembl_values(glut1_stf31_activity),
            "pubmed_query_hit_count": _pubmed_count(pubmed_glut1),
            "bindingdb_target_affinity_count": _bindingdb_affinity_count(bindingdb_glut1),
            "direct_negative_quantitative_row_found": False,
            "authoritative_negative_apply_allowed": False,
            "interpretation": "literature_context_not_negative_replacement",
            "source_artifacts": "runs/life_science_skill_crosscheck/chembl_activity_glut1_stf31.json;runs/life_science_skill_crosscheck/pubmed_glut1_binders.json",
        },
    ]

    direct_negative_rows = sum(1 for row in rows if row["direct_negative_quantitative_row_found"])
    authoritative_negative_rows = sum(1 for row in rows if row["authoritative_negative_apply_allowed"])
    glut1_positive_exact_activity_count = sum(
        _int(row.get("chembl_exact_activity_count"))
        for row in rows
        if row["target_id"] == "GLUT1" and row["evidence_role"] == "positive_inhibitor_context"
    )
    summary = {
        "crosscheck_ready": True,
        "skill_family": "life_science_research",
        "skill_source_count": 6,
        "target_count": 2,
        "row_count": len(rows),
        "aqp1_uniprot_accession": "P29972",
        "glut1_uniprot_accession": "P11166",
        "aqp1_chembl_target_id": "CHEMBL4523210",
        "glut1_chembl_target_id": "CHEMBL2535",
        "rcsb_glut1_entry": "4PYP",
        "rcsb_glut1_title": _rcsb_title(rcsb_4pyp),
        "aqp1_pubmed_anchor_title": _summary_title(pubmed_key_summaries, "23123479"),
        "glut1_cytochalasin_b_pubmed_title": _summary_title(pubmed_key_summaries, "27078104"),
        "aqp1_bindingdb_affinity_count": _bindingdb_affinity_count(bindingdb_aqp1),
        "aqp1_target_chembl_exact_activity_count": _activity_count(aqp1_chembl_target_activity),
        "aqp1_target_chembl_quantitative_activity_count": _quantitative_activity_count(aqp1_chembl_target_activity),
        "aqp1_target_chembl_functional_quantitative_count": _target_functional_quantitative_activity_count(
            aqp1_chembl_target_activity
        ),
        "aqp1_target_chembl_direct_binding_count": _target_direct_binding_activity_count(aqp1_chembl_target_activity),
        "aqp1_target_chembl_unquantified_not_active_count": _target_unquantified_not_active_count(
            aqp1_chembl_target_activity
        ),
        "glut1_bindingdb_affinity_count": _bindingdb_affinity_count(bindingdb_glut1),
        "glut1_positive_exact_activity_count": glut1_positive_exact_activity_count,
        "direct_negative_quantitative_row_found_count": direct_negative_rows,
        "authoritative_negative_apply_allowed_count": authoritative_negative_rows,
        "negative_evidence_closure_allowed": direct_negative_rows >= 6 and authoritative_negative_rows >= 6,
        "current_decision": "keep_transporter_negative_slots_review_only",
        "next_required_step": (
            "Do not promote AQP1/GLUT1 negative rows. AQP1 has exact human functional ChEMBL IC50/EC50 rows, "
            "but AQP1 BindingDB affinity/direct-binding rows remain absent and sodium nitroprusside has no exact "
            "AQP1 activity row; keep AQP1 kcal as functional surrogate only and keep replacement_reference_binding_kcal_mol blank. "
            "GLUT1 has positive inhibitor evidence for cytochalasin B/WZB117 but no negative replacement evidence. Continue exact target-pair negative evidence acquisition."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter External Evidence Crosscheck",
        "",
        f"- crosscheck_ready: `{s['crosscheck_ready']}`",
        f"- skill_family: `{s['skill_family']}`",
        f"- skill_source_count: `{s['skill_source_count']}`",
        f"- target_count: `{s['target_count']}`",
        f"- row_count: `{s['row_count']}`",
        f"- aqp1_uniprot_accession: `{s['aqp1_uniprot_accession']}`",
        f"- glut1_uniprot_accession: `{s['glut1_uniprot_accession']}`",
        f"- aqp1_chembl_target_id: `{s['aqp1_chembl_target_id']}`",
        f"- glut1_chembl_target_id: `{s['glut1_chembl_target_id']}`",
        f"- rcsb_glut1_entry: `{s['rcsb_glut1_entry']}`",
        f"- aqp1_bindingdb_affinity_count: `{s['aqp1_bindingdb_affinity_count']}`",
        f"- aqp1_target_chembl_exact_activity_count: `{s['aqp1_target_chembl_exact_activity_count']}`",
        f"- aqp1_target_chembl_functional_quantitative_count: `{s['aqp1_target_chembl_functional_quantitative_count']}`",
        f"- aqp1_target_chembl_direct_binding_count: `{s['aqp1_target_chembl_direct_binding_count']}`",
        f"- aqp1_target_chembl_unquantified_not_active_count: `{s['aqp1_target_chembl_unquantified_not_active_count']}`",
        f"- glut1_bindingdb_affinity_count: `{s['glut1_bindingdb_affinity_count']}`",
        f"- glut1_positive_exact_activity_count: `{s['glut1_positive_exact_activity_count']}`",
        f"- direct_negative_quantitative_row_found_count: `{s['direct_negative_quantitative_row_found_count']}`",
        f"- authoritative_negative_apply_allowed_count: `{s['authoritative_negative_apply_allowed_count']}`",
        f"- negative_evidence_closure_allowed: `{s['negative_evidence_closure_allowed']}`",
        f"- current_decision: `{s['current_decision']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Crosscheck Rows",
        "",
        "| target | candidate | role | ChEMBL exact | ChEMBL quantitative | direct binding | best IC50 nM | PubMed hits | BindingDB target affinities | interpretation |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['candidate']}` | `{row['evidence_role']}` | "
            f"{row['chembl_exact_activity_count']} | {row['chembl_quantitative_activity_count']} | "
            f"{row.get('chembl_direct_binding_activity_count', 0)} | "
            f"`{row.get('best_ic50_nm', '')}` | {row['pubmed_query_hit_count']} | "
            f"{row['bindingdb_target_affinity_count']} | `{row['interpretation']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a transporter external evidence crosscheck from skill query snapshots.")
    parser.add_argument("--aqp1-chembl-activity-json", default=str(DEFAULT_AQP1_CHEMBL_ACTIVITY_JSON))
    parser.add_argument("--aqp1-chembl-target-activity-json", default=str(DEFAULT_AQP1_CHEMBL_TARGET_ACTIVITY_JSON))
    parser.add_argument("--glut1-cyto-activity-json", default=str(DEFAULT_GLUT1_CYTO_CHB_ACTIVITY_JSON))
    parser.add_argument("--glut1-wzb117-activity-json", default=str(DEFAULT_GLUT1_WZB117_ACTIVITY_JSON))
    parser.add_argument("--glut1-stf31-activity-json", default=str(DEFAULT_GLUT1_STF31_ACTIVITY_JSON))
    parser.add_argument("--bindingdb-aqp1-json", default=str(DEFAULT_BINDINGDB_AQP1_JSON))
    parser.add_argument("--bindingdb-glut1-json", default=str(DEFAULT_BINDINGDB_GLUT1_JSON))
    parser.add_argument("--pubmed-aqp1-snp-json", default=str(DEFAULT_PUBMED_AQP1_SNP_JSON))
    parser.add_argument("--pubmed-aqp1-tea-json", default=str(DEFAULT_PUBMED_AQP1_TEA_JSON))
    parser.add_argument("--pubmed-aqp1-dmso-json", default=str(DEFAULT_PUBMED_AQP1_DMSO_JSON))
    parser.add_argument("--pubmed-glut1-json", default=str(DEFAULT_PUBMED_GLUT1_JSON))
    parser.add_argument("--pubmed-key-summaries-json", default=str(DEFAULT_PUBMED_KEY_SUMMARIES_JSON))
    parser.add_argument("--rcsb-4pyp-json", default=str(DEFAULT_RCSB_4PYP_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_chembl_activity_json),
        _load_json(args.aqp1_chembl_target_activity_json),
        _load_json(args.glut1_cyto_activity_json),
        _load_json(args.glut1_wzb117_activity_json),
        _load_json(args.glut1_stf31_activity_json),
        _load_json(args.bindingdb_aqp1_json),
        _load_json(args.bindingdb_glut1_json),
        _load_json(args.pubmed_aqp1_snp_json),
        _load_json(args.pubmed_aqp1_tea_json),
        _load_json(args.pubmed_aqp1_dmso_json),
        _load_json(args.pubmed_glut1_json),
        _load_json(args.pubmed_key_summaries_json),
        _load_json(args.rcsb_4pyp_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
