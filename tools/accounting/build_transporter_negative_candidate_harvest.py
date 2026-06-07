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

DEFAULT_AQP1_TARGET_ACTIVITY_JSON = SKILL_RUNS / "chembl_activity_aqp1_target_all_limit50.json"
DEFAULT_GLUT1_TARGET_ACTIVITY_JSON = SKILL_RUNS / "chembl_activity_glut1_target_all_limit50.json"
DEFAULT_OUT_JSON = RUNS / "transporter_negative_candidate_harvest_current.json"
DEFAULT_OUT_CSV = RUNS / "transporter_negative_candidate_harvest_current.csv"
DEFAULT_OUT_MD = RUNS / "transporter_negative_candidate_harvest_current.md"

TARGETS = {
    "AQP1": "CHEMBL4523210",
    "GLUT1": "CHEMBL2535",
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
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _activities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("activities", []) if isinstance(payload, dict) else []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _candidate_class(row: dict[str, Any]) -> str:
    comment = _text(row.get("activity_comment")).lower()
    relation = _text(row.get("standard_relation"))
    standard_type = _text(row.get("standard_type")).upper()
    units = _text(row.get("standard_units")).lower()
    standard_value = _float(row.get("standard_value"))
    data_validity = _text(row.get("data_validity_comment")).lower()

    if relation in {">", ">="} and units == "nm" and standard_value is not None and standard_value >= 100000:
        if standard_type in {"KD", "KI", "IC50", "EC50", "INHIBITION", "ACTIVITY"}:
            return "chembl_quantitative_weak_or_no_binding_lower_bound"
    if comment == "not active":
        return "chembl_not_active_nonquantitative"
    if (
        standard_type in {"IC50", "EC50", "KD", "KI"}
        and units == "nm"
        and standard_value is not None
        and standard_value >= 1_000_000
    ):
        if "outside typical range" in data_validity:
            return "chembl_ultra_weak_outlier_review_only"
        return "chembl_ultra_weak_activity_review_only"
    return ""


def _priority(evidence_class: str) -> int:
    if evidence_class == "chembl_quantitative_weak_or_no_binding_lower_bound":
        return 1
    if evidence_class == "chembl_not_active_nonquantitative":
        return 2
    if evidence_class.startswith("chembl_ultra_weak"):
        return 3
    return 99


def _collect_target_rows(target_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    target_chembl_id = TARGETS[target_id]
    by_molecule: dict[str, dict[str, Any]] = {}
    for activity in _activities(payload):
        if _text(activity.get("target_chembl_id")) != target_chembl_id:
            continue
        evidence_class = _candidate_class(activity)
        if not evidence_class:
            continue
        molecule_id = _text(activity.get("molecule_chembl_id"))
        if not molecule_id:
            continue
        row = {
            "target_id": target_id,
            "target_chembl_id": target_chembl_id,
            "molecule_chembl_id": molecule_id,
            "molecule_pref_name": _text(activity.get("molecule_pref_name")),
            "canonical_smiles": _text(activity.get("canonical_smiles")),
            "document_chembl_id": _text(activity.get("document_chembl_id")),
            "document_year": _text(activity.get("document_year")),
            "assay_chembl_id": _text(activity.get("assay_chembl_id")),
            "assay_description": _text(activity.get("assay_description")),
            "activity_comment": _text(activity.get("activity_comment")),
            "standard_type": _text(activity.get("standard_type")),
            "standard_relation": _text(activity.get("standard_relation")),
            "standard_value": _text(activity.get("standard_value")),
            "standard_units": _text(activity.get("standard_units")),
            "data_validity_comment": _text(activity.get("data_validity_comment")),
            "evidence_class": evidence_class,
            "curation_priority": _priority(evidence_class),
            "candidate_review_ready": True,
            "authoritative_negative_apply_allowed": False,
            "promotion_blocker": "manual_ligand_identity_source_and_split_curation_required",
        }
        previous = by_molecule.get(molecule_id)
        if previous is None or row["curation_priority"] < previous["curation_priority"]:
            by_molecule[molecule_id] = row
    rows = sorted(
        by_molecule.values(),
        key=lambda row: (
            int(row["curation_priority"]),
            row["target_id"],
            row["molecule_chembl_id"],
        ),
    )
    for rank, row in enumerate(rows, start=1):
        row["target_candidate_rank"] = rank
    return rows


def build_payload(
    aqp1_target_activity_payload: dict[str, Any],
    glut1_target_activity_payload: dict[str, Any],
) -> dict[str, Any]:
    rows = _collect_target_rows("AQP1", aqp1_target_activity_payload)
    rows.extend(_collect_target_rows("GLUT1", glut1_target_activity_payload))

    for global_rank, row in enumerate(rows, start=1):
        row["global_candidate_rank"] = global_rank

    aqp1_rows = [row for row in rows if row["target_id"] == "AQP1"]
    glut1_rows = [row for row in rows if row["target_id"] == "GLUT1"]
    aqp1_quant_rows = [
        row for row in aqp1_rows if row["evidence_class"] == "chembl_quantitative_weak_or_no_binding_lower_bound"
    ]
    glut1_quant_rows = [
        row for row in glut1_rows if row["evidence_class"] == "chembl_quantitative_weak_or_no_binding_lower_bound"
    ]
    summary = {
        "candidate_harvest_ready": True,
        "skill_family": "life_science_research",
        "source_database": "ChEMBL",
        "target_count": 2,
        "row_count": len(rows),
        "aqp1_candidate_review_row_count": len(aqp1_rows),
        "glut1_candidate_review_row_count": len(glut1_rows),
        "aqp1_quantitative_lower_bound_candidate_count": len(aqp1_quant_rows),
        "glut1_quantitative_lower_bound_candidate_count": len(glut1_quant_rows),
        "potential_aqp1_negative_slot_cover_count": min(3, len(aqp1_quant_rows)),
        "potential_glut1_negative_slot_cover_count": min(3, len(glut1_quant_rows)),
        "unreviewed_direct_negative_quantitative_candidate_count": len(aqp1_quant_rows) + len(glut1_quant_rows),
        "authoritative_negative_apply_allowed_count": 0,
        "negative_evidence_closure_allowed": False,
        "candidate_harvest_status": (
            "glut1_quantitative_candidate_review_available_aqp1_still_blocked"
            if glut1_quant_rows and not aqp1_quant_rows
            else "candidate_review_available"
            if rows
            else "no_candidate_rows_found"
        ),
        "packet_artifact": "runs/transporter_negative_candidate_harvest_current.md",
        "next_required_step": (
            "Curate the GLUT1 ChEMBL lower-bound Kd rows first as candidate replacements for the three GLUT1 negative slots, "
            "but do not apply them until molecule identity, source provenance, split/reference/meta updates, and reviewer approval are complete. "
            "AQP1 still lacks quantitative lower-bound negative candidates and remains the first blocker."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Negative Candidate Harvest",
        "",
        f"- candidate_harvest_ready: `{s['candidate_harvest_ready']}`",
        f"- skill_family: `{s['skill_family']}`",
        f"- source_database: `{s['source_database']}`",
        f"- row_count: `{s['row_count']}`",
        f"- aqp1_candidate_review_row_count: `{s['aqp1_candidate_review_row_count']}`",
        f"- glut1_candidate_review_row_count: `{s['glut1_candidate_review_row_count']}`",
        f"- aqp1_quantitative_lower_bound_candidate_count: `{s['aqp1_quantitative_lower_bound_candidate_count']}`",
        f"- glut1_quantitative_lower_bound_candidate_count: `{s['glut1_quantitative_lower_bound_candidate_count']}`",
        f"- potential_aqp1_negative_slot_cover_count: `{s['potential_aqp1_negative_slot_cover_count']}`",
        f"- potential_glut1_negative_slot_cover_count: `{s['potential_glut1_negative_slot_cover_count']}`",
        f"- unreviewed_direct_negative_quantitative_candidate_count: `{s['unreviewed_direct_negative_quantitative_candidate_count']}`",
        f"- authoritative_negative_apply_allowed_count: `{s['authoritative_negative_apply_allowed_count']}`",
        f"- negative_evidence_closure_allowed: `{s['negative_evidence_closure_allowed']}`",
        f"- candidate_harvest_status: `{s['candidate_harvest_status']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Candidate Rows",
        "",
        "| rank | target | molecule | class | standard | document | curation_priority |",
        "| ---: | --- | --- | --- | --- | --- | ---: |",
    ]
    for row in payload["rows"]:
        standard = " ".join(
            part
            for part in [
                row.get("standard_type", ""),
                row.get("standard_relation", ""),
                row.get("standard_value", ""),
                row.get("standard_units", ""),
            ]
            if _text(part)
        )
        lines.append(
            f"| {row['global_candidate_rank']} | `{row['target_id']}` | `{row['molecule_chembl_id']}` | "
            f"`{row['evidence_class']}` | `{standard or row.get('activity_comment') or '-'}` | "
            f"`{row.get('document_chembl_id') or '-'}` | {row['curation_priority']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a ChEMBL target-level candidate harvest for transporter negative slots.")
    parser.add_argument("--aqp1-target-activity-json", default=str(DEFAULT_AQP1_TARGET_ACTIVITY_JSON))
    parser.add_argument("--glut1-target-activity-json", default=str(DEFAULT_GLUT1_TARGET_ACTIVITY_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_target_activity_json),
        _load_json(args.glut1_target_activity_json),
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
