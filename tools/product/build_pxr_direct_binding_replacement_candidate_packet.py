#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_EXACT_REVIEW_JSON = RUNS / "pxr_exact_evidence_review_intake_template_current.json"
DEFAULT_SOURCE_DIR = RUNS / "pxr_direct_binding_candidate_sources"
DEFAULT_OUT_JSON = RUNS / "pxr_direct_binding_replacement_candidate_packet_current.json"
DEFAULT_OUT_CSV = RUNS / "pxr_direct_binding_replacement_candidate_packet_current.csv"
DEFAULT_OUT_MD = RUNS / "pxr_direct_binding_replacement_candidate_packet_current.md"

TARGET_CHEMBL_ID = "CHEMBL3401"
TARGET_GENE = "NR1I2"
TARGET_ALIAS = "PXR"
TARGET_SPECIES = "human"
RT_KCAL_MOL_298K = 0.00198720425864083 * 298.15
TYPE_PRIORITY = {"Kd": 0, "Ki": 1, "IC50": 2}
WEAK_DIRECT_CONTROL_MIN_NM = 3000.0
STRONG_BINDER_MAX_NM = 100.0
DIRECT_ASSAY_MARKERS = (
    "displacement",
    "binding affinity",
    "competition binding",
    "dissociation constant",
)

CLAIM_BOUNDARY = (
    "PXR direct-binding replacement candidate packet only; reads saved ChEMBL human NR1I2/PXR binding-assay "
    "payloads, ranks exact direct binding rows, computes RT ln(K) kcal/mol at 298.15 K, and stages replacement "
    "candidates for operator review. It does not edit authoritative PXR config, fill placeholders, run docking, "
    "promote scope, or mutate external state beyond writing this local audit artifact."
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


def _activity_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("activities")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _source_files(source_dir: str | Path) -> list[Path]:
    root = _resolve(source_dir)
    return sorted(root.glob("chembl_activity_CHEMBL3401_assayB_*.json"))


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _delta_g_from_nm(value_nm: float) -> float:
    return RT_KCAL_MOL_298K * math.log(value_nm * 1e-9)


def _ligand_id(row: dict[str, Any]) -> str:
    name = _text(row.get("molecule_pref_name")).lower().replace(" ", "_").replace("-", "_")
    return name or _text(row.get("molecule_chembl_id")).lower()


def _source_string(row: dict[str, Any]) -> str:
    return (
        "chembl_direct_binding::"
        f"{_text(row.get('target_chembl_id'))}::"
        f"{_text(row.get('molecule_chembl_id'))}::"
        f"activity_{_text(row.get('activity_id'))}::"
        f"assay_{_text(row.get('assay_chembl_id'))}::"
        f"{_text(row.get('standard_type'))}_{_text(row.get('standard_value'))}_nM::"
        f"doc_{_text(row.get('document_chembl_id'))}"
    )


def _is_direct_binding_assay(row: dict[str, Any]) -> bool:
    description = _text(row.get("assay_description")).lower()
    return any(marker in description for marker in DIRECT_ASSAY_MARKERS)


def _candidate_rows(source_dir: str | Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for path in _source_files(source_dir):
        for row in _activity_rows(_read_json(path)):
            value_nm = _float(row.get("standard_value"))
            standard_type = _text(row.get("standard_type"))
            if (
                _text(row.get("target_chembl_id")) != TARGET_CHEMBL_ID
                or _text(row.get("target_organism")) != "Homo sapiens"
                or _text(row.get("assay_type")) != "B"
                or _text(row.get("standard_relation")) != "="
                or _text(row.get("standard_units")) != "nM"
                or standard_type not in TYPE_PRIORITY
                or value_nm is None
                or value_nm <= 0
            ):
                continue
            item = dict(row)
            item["_source_artifact"] = _display_path(path)
            item["_standard_value_nM"] = value_nm
            item["_delta_g"] = _delta_g_from_nm(value_nm)
            candidates.append(item)
    candidates.sort(
        key=lambda row: (
            float(row["_standard_value_nM"]),
            TYPE_PRIORITY.get(_text(row.get("standard_type")), 99),
            _text(row.get("molecule_chembl_id")),
            _text(row.get("activity_id")),
        )
    )
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in candidates:
        molecule_id = _text(row.get("molecule_chembl_id"))
        if not molecule_id or molecule_id in seen:
            continue
        seen.add(molecule_id)
        deduped.append(row)
    return deduped


def _planned_is_binder(review_row: dict[str, Any]) -> str:
    label = _text(review_row.get("current_label")).lower()
    mode = _text(review_row.get("required_evidence_mode") or review_row.get("request_mode")).lower()
    if label == "non_binder" or "negative" in mode or "non_binder" in mode:
        return "0"
    return "1"


def _select_for_review_rows(
    review_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    top_n: int,
) -> list[tuple[dict[str, Any], dict[str, Any], str]]:
    direct_candidates = [row for row in candidates if _is_direct_binding_assay(row)]
    weak_controls = [
        row
        for row in direct_candidates
        if _text(row.get("standard_type")) == "IC50"
        and float(row["_standard_value_nM"]) >= WEAK_DIRECT_CONTROL_MIN_NM
    ]
    weak_controls.sort(
        key=lambda row: (
            -float(row["_standard_value_nM"]),
            _text(row.get("molecule_chembl_id")),
            _text(row.get("activity_id")),
        )
    )
    strong_binders = [
        row
        for row in direct_candidates
        if float(row["_standard_value_nM"]) <= STRONG_BINDER_MAX_NM
    ]
    strong_binders.sort(
        key=lambda row: (
            float(row["_standard_value_nM"]),
            TYPE_PRIORITY.get(_text(row.get("standard_type")), 99),
            _text(row.get("molecule_chembl_id")),
            _text(row.get("activity_id")),
        )
    )

    selected: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    used_molecules: set[str] = set()
    review_slice = review_rows[:top_n]
    for index in range(top_n):
        review_row = review_slice[index] if index < len(review_slice) else {}
        planned_is_binder = _planned_is_binder(review_row)
        pool = strong_binders if planned_is_binder == "1" else weak_controls
        candidate = next(
            (
                row
                for row in pool
                if _text(row.get("molecule_chembl_id"))
                and _text(row.get("molecule_chembl_id")) not in used_molecules
            ),
            {},
        )
        if not candidate:
            continue
        used_molecules.add(_text(candidate.get("molecule_chembl_id")))
        selected.append((review_row, candidate, planned_is_binder))
    return selected


def build_payload(
    *,
    exact_review_packet: dict[str, Any],
    source_dir: str | Path = DEFAULT_SOURCE_DIR,
    top_n: int = 6,
) -> dict[str, Any]:
    review_rows = _rows(exact_review_packet)
    candidates = _candidate_rows(source_dir)
    selected = _select_for_review_rows(review_rows, candidates, top_n=top_n)
    rows: list[dict[str, Any]] = []
    for rank, (review_row, row, planned_is_binder) in enumerate(selected, start=1):
        value_nm = float(row["_standard_value_nM"])
        delta_g = float(row["_delta_g"])
        selection_bucket = "strong_direct_binder" if planned_is_binder == "1" else "weak_direct_nonbinder_control"
        rows.append(
            {
                "rank": rank,
                "replacement_for_review_row_id": _text(review_row.get("review_row_id")),
                "replacement_for_packet_step": _text(review_row.get("packet_step")),
                "replacement_for_current_candidate_name": _text(review_row.get("candidate_name")),
                "planned_role": _text(review_row.get("current_role")) or (
                    "fit" if planned_is_binder == "1" else "far_ood_eval"
                ),
                "planned_is_binder": planned_is_binder,
                "selection_bucket": selection_bucket,
                "weak_direct_control_min_nM": WEAK_DIRECT_CONTROL_MIN_NM,
                "strong_binder_max_nM": STRONG_BINDER_MAX_NM,
                "target_gene": TARGET_GENE,
                "target_alias": TARGET_ALIAS,
                "target_species": TARGET_SPECIES,
                "target_chembl_id": TARGET_CHEMBL_ID,
                "molecule_chembl_id": _text(row.get("molecule_chembl_id")),
                "replacement_ligand_id": _ligand_id(row),
                "molecule_pref_name": _text(row.get("molecule_pref_name")),
                "canonical_smiles": _text(row.get("canonical_smiles")),
                "reference_binding_kcal_mol": f"{delta_g:.4f}",
                "standard_type": _text(row.get("standard_type")),
                "standard_relation": _text(row.get("standard_relation")),
                "standard_value_nM": value_nm,
                "pchembl_value": _text(row.get("pchembl_value")),
                "activity_id": _text(row.get("activity_id")),
                "assay_chembl_id": _text(row.get("assay_chembl_id")),
                "document_chembl_id": _text(row.get("document_chembl_id")),
                "document_journal": _text(row.get("document_journal")),
                "document_year": _text(row.get("document_year")),
                "assay_description": _text(row.get("assay_description")),
                "source": _source_string(row),
                "source_raw_artifact": _text(row.get("_source_artifact")),
                "target_match_confirmed": True,
                "assay_is_direct_or_claim_safe": True,
                "direct_binding_assay_confirmed": True,
                "replacement_candidate_ready_for_operator_review": True,
                "authoritative_apply_allowed": False,
                "scope_promotion_allowed": False,
                "external_state_mutated": False,
            }
        )
    ready_count = sum(1 for row in rows if row["replacement_candidate_ready_for_operator_review"] is True)
    first = rows[0] if rows else {}
    summary = {
        "packet_type": "pxr_direct_binding_replacement_candidate_packet",
        "status": (
            "pxr_direct_binding_replacement_candidates_ready"
            if ready_count >= top_n
            else "blocked_pxr_direct_binding_replacement_candidates_insufficient"
        ),
        "replacement_candidate_packet_ready": ready_count >= top_n,
        "target_gene": TARGET_GENE,
        "target_alias": TARGET_ALIAS,
        "target_species": TARGET_SPECIES,
        "target_chembl_id": TARGET_CHEMBL_ID,
        "requested_top_n": top_n,
        "review_placeholder_row_count": len(review_rows),
        "direct_binding_candidate_count": len(candidates),
        "direct_assay_candidate_count": len([row for row in candidates if _is_direct_binding_assay(row)]),
        "weak_direct_control_candidate_count": len(
            [
                row
                for row in candidates
                if _is_direct_binding_assay(row)
                and _text(row.get("standard_type")) == "IC50"
                and float(row["_standard_value_nM"]) >= WEAK_DIRECT_CONTROL_MIN_NM
            ]
        ),
        "strong_direct_binder_candidate_count": len(
            [
                row
                for row in candidates
                if _is_direct_binding_assay(row)
                and float(row["_standard_value_nM"]) <= STRONG_BINDER_MAX_NM
            ]
        ),
        "selected_replacement_candidate_count": len(rows),
        "selected_claim_safe_candidate_count": ready_count,
        "selected_nonbinder_weak_control_count": sum(1 for row in rows if row["planned_is_binder"] == "0"),
        "selected_binder_direct_count": sum(1 for row in rows if row["planned_is_binder"] == "1"),
        "first_replacement_ligand_id": _text(first.get("replacement_ligand_id")),
        "first_replacement_molecule_chembl_id": _text(first.get("molecule_chembl_id")),
        "first_replacement_reference_binding_kcal_mol": _text(first.get("reference_binding_kcal_mol")),
        "first_replacement_source": _text(first.get("source")),
        "replacement_candidate_artifact": DEFAULT_OUT_JSON.as_posix(),
        "source_dir": str(source_dir),
        "next_required_step": (
            "Operator can use these six exact ChEMBL human NR1I2/PXR direct-binding rows as a replacement route "
            "for the current blocked PXR placeholders. Non-binder slots use weak direct-displacement controls "
            f"(IC50 >= {WEAK_DIRECT_CONTROL_MIN_NM:g} nM), binder slots use strong direct binders "
            f"(<= {STRONG_BINDER_MAX_NM:g} nM). Then rerun PXR packet-fill, blocked-row promotion, "
            "authoritative reconciliation, and scope breadth gates."
            if ready_count >= top_n
            else "Curate additional exact human NR1I2/PXR direct-binding rows before replacing the blocked PXR placeholders."
        ),
        "authoritative_apply_allowed": False,
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
        "# PXR Direct-Binding Replacement Candidate Packet",
        "",
        f"- status: `{s['status']}`",
        f"- direct_binding_candidate_count: `{s['direct_binding_candidate_count']}`",
        f"- selected_replacement_candidate_count: `{s['selected_replacement_candidate_count']}`",
        f"- selected_claim_safe_candidate_count: `{s['selected_claim_safe_candidate_count']}`",
        f"- selected_nonbinder_weak_control_count: `{s['selected_nonbinder_weak_control_count']}`",
        f"- selected_binder_direct_count: `{s['selected_binder_direct_count']}`",
        f"- first_replacement_ligand_id: `{s['first_replacement_ligand_id']}`",
        "",
        "## Candidates",
        "",
        "| rank | replaces | label | ligand | type | nM | kcal/mol | source |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['rank']} | `{row['replacement_for_current_candidate_name']}` | "
            f"`{row['planned_is_binder']}` | "
            f"`{row['replacement_ligand_id']}` | `{row['standard_type']}` | "
            f"{row['standard_value_nM']} | {row['reference_binding_kcal_mol']} | `{row['source']}` |"
        )
    lines.extend(["", "## Next Step", "", s["next_required_step"], "", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PXR direct-binding replacement candidate packet.")
    parser.add_argument("--exact-review-json", default=DEFAULT_EXACT_REVIEW_JSON.as_posix())
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR.as_posix())
    parser.add_argument("--top-n", type=int, default=6)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON.as_posix())
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV.as_posix())
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD.as_posix())
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        exact_review_packet=_read_json(args.exact_review_json),
        source_dir=args.source_dir,
        top_n=args.top_n,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
