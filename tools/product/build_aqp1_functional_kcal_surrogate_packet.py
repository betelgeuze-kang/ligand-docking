#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CAPTURE_SHEET_JSON = "runs/aqp1_quantitative_binding_capture_sheet_current.json"
DEFAULT_PROVENANCE_JSON = "runs/aqp1_quantitative_provenance_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_functional_kcal_surrogate_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_functional_kcal_surrogate_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_functional_kcal_surrogate_packet_current.md"

R_KCAL_PER_MOL_K = 0.00198720425864083
DEFAULT_TEMPERATURE_K = 298.15


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalise_units_to_molar(value: float, units: str) -> float:
    unit = units.strip().lower().replace("µ", "u")
    if unit in {"m", "mol/l", "molar"}:
        return value
    if unit in {"mm", "mmol/l", "millimolar"}:
        return value * 1e-3
    if unit in {"um", "umol/l", "micromolar"}:
        return value * 1e-6
    if unit in {"nm", "nmol/l", "nanomolar"}:
        return value * 1e-9
    return 0.0


def _functional_delta_g_kcal(value: float, units: str, temperature_k: float) -> float:
    molar = _normalise_units_to_molar(value, units)
    if molar <= 0:
        return 0.0
    return R_KCAL_PER_MOL_K * temperature_k * math.log(molar)


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(row or {}) for row in payload.get("rows", []) or []]


def _provenance_by_step(provenance_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_step: dict[str, dict[str, Any]] = {}
    for row in _rows(provenance_payload):
        step = _text(row.get("packet_step"))
        if step:
            by_step[step] = row
    return by_step


def _source_measure(row: dict[str, Any], provenance_row: dict[str, Any]) -> dict[str, str]:
    capture_kind = _text(row.get("quantitative_measure_kind"))
    capture_value = _float(row.get("quantitative_measure_value"))
    capture_units = _text(row.get("quantitative_measure_units"))
    chembl_kind = _text(provenance_row.get("chembl_best_activity_type"))
    chembl_value = _float(provenance_row.get("chembl_best_activity_value"))
    chembl_units = _text(provenance_row.get("chembl_best_activity_units"))
    if chembl_kind.upper() == "IC50" and chembl_value > 0 and chembl_units:
        return {
            "kind": chembl_kind,
            "value": f"{chembl_value:g}",
            "units": chembl_units,
            "basis": "chembl_exact_target_functional_ic50",
        }
    return {
        "kind": capture_kind,
        "value": f"{capture_value:g}" if capture_value else "",
        "units": capture_units,
        "basis": "source_reported_functional_potency",
    }


def build_payload(
    capture_sheet_payload: dict[str, Any],
    provenance_payload: dict[str, Any],
    *,
    as_of_date: str | None = None,
    temperature_k: float = DEFAULT_TEMPERATURE_K,
) -> dict[str, Any]:
    as_of_date = as_of_date or date.today().isoformat()
    provenance_by_step = _provenance_by_step(provenance_payload)
    rows: list[dict[str, Any]] = []
    for capture_row in _rows(capture_sheet_payload):
        packet_step = _text(capture_row.get("packet_step"))
        provenance_row = provenance_by_step.get(packet_step, {})
        measure = _source_measure(capture_row, provenance_row)
        measure_value = _float(measure["value"])
        measure_units = _text(measure["units"])
        kcal = _functional_delta_g_kcal(measure_value, measure_units, temperature_k)
        kind = _text(measure["kind"]).upper()
        functional_measure_ok = kind == "IC50" and kcal < 0
        source_url = _text(capture_row.get("source_url") or provenance_row.get("source_url"))
        pubchem_cid = _text(provenance_row.get("pubchem_cid"))
        pubchem_smiles = _text(provenance_row.get("pubchem_canonical_smiles"))
        row_ready = bool(functional_measure_ok and source_url and (pubchem_cid or pubchem_smiles))
        rows.append(
            {
                "as_of_date": as_of_date,
                "packet_step": packet_step,
                "candidate_name": _text(capture_row.get("candidate_name")),
                "replacement_ligand_id": _text(capture_row.get("replacement_ligand_id")),
                "source_anchor": _text(capture_row.get("source_anchor") or provenance_row.get("source_anchor")),
                "source_title": _text(capture_row.get("source_title") or provenance_row.get("source_title")),
                "source_url": source_url,
                "current_signal": _text(capture_row.get("current_signal") or provenance_row.get("current_signal")),
                "assay_type_honesty": "functional_ic50_derived_surrogate_not_direct_binding",
                "functional_measure_kind": measure["kind"],
                "functional_measure_value": measure["value"],
                "functional_measure_units": measure["units"],
                "functional_measure_basis": measure["basis"],
                "temperature_K": f"{temperature_k:g}",
                "functional_delta_g_surrogate_kcal_mol": f"{kcal:.2f}" if kcal else "",
                "direct_binding_claim_allowed": "no",
                "binding_kcal_claim_allowed": "no",
                "replacement_reference_binding_kcal_mol_must_remain_blank": "yes",
                "functional_kcal_surrogate_allowed": "yes" if row_ready else "no",
                "claim_safe_functional_kcal_ready": "yes" if row_ready else "no",
                "row_ready_for_apply": "yes" if row_ready else "no",
                "public_provenance_status": _text(provenance_row.get("public_provenance_status")),
                "chembl_molecule_chembl_id": _text(provenance_row.get("chembl_molecule_chembl_id")),
                "chembl_activity_record_count": _text(provenance_row.get("chembl_activity_record_count")),
                "target_chembl_id": _text(provenance_row.get("target_chembl_id")),
                "target_uniprot": _text(provenance_row.get("target_uniprot")),
                "pubchem_cid": pubchem_cid,
                "pubchem_canonical_smiles": pubchem_smiles,
                "next_required_action": (
                    "use_functional_kcal_surrogate_only; keep direct binding and replacement_reference_binding_kcal_mol claims blank"
                    if row_ready
                    else "keep_row_review_only_until_functional_ic50_identity_and_source_are_complete"
                ),
            }
        )
    ready_count = sum(1 for row in rows if row["row_ready_for_apply"] == "yes")
    direct_binding_claim_allowed_count = sum(
        1 for row in rows if row["direct_binding_claim_allowed"] == "yes"
    )
    summary = {
        "family": "aqp1",
        "as_of_date": as_of_date,
        "row_count": len(rows),
        "functional_kcal_surrogate_ready_count": ready_count,
        "claim_safe_functional_kcal_ready_count": ready_count,
        "direct_binding_claim_allowed_count": direct_binding_claim_allowed_count,
        "binding_kcal_claim_allowed_count": 0,
        "replacement_reference_binding_kcal_mol_blank_required_count": len(rows),
        "functional_kcal_surrogate_closure_allowed": ready_count == 3,
        "direct_binding_gap_still_open": True,
        "packet_artifact": "runs/aqp1_functional_kcal_surrogate_packet_current.md",
        "next_required_step": (
            "AQP1 binder kcal can be represented only as functional IC50-derived surrogate kcal for the current rows; "
            "do not promote these rows as direct binding kcal."
            if ready_count == 3
            else "Keep AQP1 kcal blocked until all three functional IC50 surrogate rows have source, identity, and concentration support."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Functional Kcal Surrogate Packet",
        "",
        f"- row_count: `{s['row_count']}`",
        f"- functional_kcal_surrogate_ready_count: `{s['functional_kcal_surrogate_ready_count']}`",
        f"- claim_safe_functional_kcal_ready_count: `{s['claim_safe_functional_kcal_ready_count']}`",
        f"- direct_binding_claim_allowed_count: `{s['direct_binding_claim_allowed_count']}`",
        f"- direct_binding_gap_still_open: `{s['direct_binding_gap_still_open']}`",
        f"- functional_kcal_surrogate_closure_allowed: `{s['functional_kcal_surrogate_closure_allowed']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Rows",
        "",
        "| packet_step | candidate_name | functional_measure | functional_delta_g_surrogate_kcal_mol | row_ready_for_apply | direct_binding_claim_allowed |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        measure = f"{row['functional_measure_kind']} {row['functional_measure_value']} {row['functional_measure_units']}"
        lines.append(
            f"| `{row['packet_step']}` | `{row['candidate_name']}` | `{measure.strip()}` | "
            f"`{row['functional_delta_g_surrogate_kcal_mol']}` | `{row['row_ready_for_apply']}` | "
            f"`{row['direct_binding_claim_allowed']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AQP1 functional IC50-derived kcal surrogate packet.")
    parser.add_argument("--capture-sheet-json", default=DEFAULT_CAPTURE_SHEET_JSON)
    parser.add_argument("--provenance-json", default=DEFAULT_PROVENANCE_JSON)
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--temperature-k", type=float, default=DEFAULT_TEMPERATURE_K)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.capture_sheet_json),
        _load_json(args.provenance_json),
        as_of_date=args.as_of_date or None,
        temperature_k=args.temperature_k,
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
