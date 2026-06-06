#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_WORKBOOK_CSV = RUNS / "pxr_packet_replacement_workbook_current.csv"
DEFAULT_CANDIDATE_JSON = RUNS / "pxr_direct_binding_replacement_candidate_packet_current.json"
DEFAULT_MOLECULE_DIR = RUNS / "pxr_direct_binding_candidate_sources"
DEFAULT_OUT_JSON = RUNS / "pxr_direct_binding_replacement_apply_draft_current.json"
DEFAULT_OUT_CSV = RUNS / "pxr_direct_binding_replacement_apply_draft_current.csv"
DEFAULT_OUT_MD = RUNS / "pxr_direct_binding_replacement_apply_draft_current.md"

CLAIM_BOUNDARY = (
    "PXR direct-binding replacement apply draft only; overlays exact ChEMBL human NR1I2/PXR direct-binding "
    "candidate values onto a copy of the current replacement workbook. It does not overwrite authoritative "
    "workbook/config files, run docking, promote PXR scope, or mutate external state."
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


def _read_csv(path_like: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    path = _resolve(path_like)
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_csv(path_like: str | Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _molecule_payload(molecule_dir: str | Path, molecule_id: str) -> dict[str, Any]:
    return _read_json(_resolve(molecule_dir) / f"chembl_molecule_{molecule_id}.json")


def _props(molecule: dict[str, Any]) -> dict[str, Any]:
    props = molecule.get("molecule_properties") if isinstance(molecule.get("molecule_properties"), dict) else {}
    structures = molecule.get("molecule_structures") if isinstance(molecule.get("molecule_structures"), dict) else {}
    return {
        "replacement_smiles": _text(structures.get("canonical_smiles")),
        "replacement_molecular_weight": _text(props.get("full_mwt")),
        "replacement_logp": _text(props.get("alogp")),
        "replacement_h_donors": _text(props.get("hbd")),
        "replacement_h_acceptors": _text(props.get("hba")),
        "replacement_rot_bonds": _text(props.get("rtb")),
        "replacement_scaffold": _text(structures.get("standard_inchi_key")),
    }


def build_payload(
    *,
    workbook_rows: list[dict[str, str]],
    workbook_fieldnames: list[str],
    candidate_packet: dict[str, Any],
    molecule_dir: str | Path = DEFAULT_MOLECULE_DIR,
) -> dict[str, Any]:
    candidate_by_step = {
        _text(row.get("replacement_for_packet_step")): row
        for row in _rows(candidate_packet)
        if _text(row.get("replacement_for_packet_step"))
    }
    draft_rows: list[dict[str, Any]] = []
    overlay_count = 0
    blocked_before = 0
    ready_after = 0
    for row in workbook_rows:
        draft = dict(row)
        packet_step = _text(row.get("packet_step"))
        was_blocked = _text(row.get("row_ready_for_apply")).lower() != "yes"
        if was_blocked:
            blocked_before += 1
        candidate = candidate_by_step.get(packet_step)
        if candidate:
            molecule = _molecule_payload(molecule_dir, _text(candidate.get("molecule_chembl_id")))
            draft.update(_props(molecule))
            planned_is_binder = _text(candidate.get("planned_is_binder")) or "1"
            draft.update(
                {
                    "replacement_ligand_id": _text(candidate.get("replacement_ligand_id")),
                    "replacement_reference_binding_kcal_mol": _text(candidate.get("reference_binding_kcal_mol")),
                    "replacement_is_binder": planned_is_binder,
                    "replacement_source": _text(candidate.get("source")),
                    "replacement_role": _text(row.get("current_role")) or _text(candidate.get("planned_role")),
                    "row_ready_for_apply": "yes",
                    "required_missing_fields": "",
                    "resolved_query_name": _text(candidate.get("replacement_ligand_id")),
                    "replacement_pubchem_cid": "",
                    "replacement_structure_resolution_status": "chembl_molecule_resolved",
                    "replacement_structure_resolution_url": (
                        f"https://www.ebi.ac.uk/chembl/compound_report_card/{_text(candidate.get('molecule_chembl_id'))}/"
                    ),
                    "notes": (
                        _text(row.get("notes"))
                        + " Direct-binding apply draft overlay from "
                        + _text(candidate.get("source"))
                    ).strip(),
                }
            )
            overlay_count += 1
        if _text(draft.get("row_ready_for_apply")).lower() == "yes" and not _text(
            draft.get("required_missing_fields")
        ):
            ready_after += 1
        draft_rows.append(draft)

    fieldnames = list(workbook_fieldnames)
    for field in draft_rows[0].keys() if draft_rows else []:
        if field not in fieldnames:
            fieldnames.append(field)
    first_overlay = next((row for row in draft_rows if "chembl_direct_binding::" in _text(row.get("replacement_source"))), {})
    summary = {
        "packet_type": "pxr_direct_binding_replacement_apply_draft",
        "status": (
            "pxr_direct_binding_replacement_apply_draft_ready"
            if overlay_count >= 6 and ready_after == len(draft_rows)
            else "blocked_pxr_direct_binding_replacement_apply_draft"
        ),
        "draft_ready": bool(overlay_count >= 6 and ready_after == len(draft_rows)),
        "workbook_row_count": len(workbook_rows),
        "blocked_row_count_before_draft": blocked_before,
        "direct_binding_overlay_row_count": overlay_count,
        "ready_for_apply_row_count_after_draft": ready_after,
        "blocked_row_count_after_draft": len(draft_rows) - ready_after,
        "first_overlay_packet_step": _text(first_overlay.get("packet_step")),
        "first_overlay_replacement_ligand_id": _text(first_overlay.get("replacement_ligand_id")),
        "first_overlay_replacement_reference_binding_kcal_mol": _text(
            first_overlay.get("replacement_reference_binding_kcal_mol")
        ),
        "first_overlay_replacement_source": _text(first_overlay.get("replacement_source")),
        "draft_csv_artifact": DEFAULT_OUT_CSV.as_posix(),
        "next_required_step": (
            "Review this draft CSV, then copy approved rows into the authoritative PXR replacement workbook and "
            "rerun validate_pxr_packet_fill_readiness.py, build_pxr_blocked_row_promotion_gate.py, "
            "build_pxr_authoritative_reconciliation_packet.py, and build_product_scope_breadth_contract.py."
        ),
        "authoritative_replacement_fields_touched": False,
        "authoritative_apply_allowed": False,
        "scope_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "fieldnames": fieldnames,
    }
    return {"summary": summary, "draft_rows": draft_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# PXR Direct-Binding Replacement Apply Draft",
        "",
        f"- status: `{s['status']}`",
        f"- workbook_row_count: `{s['workbook_row_count']}`",
        f"- blocked_row_count_before_draft: `{s['blocked_row_count_before_draft']}`",
        f"- direct_binding_overlay_row_count: `{s['direct_binding_overlay_row_count']}`",
        f"- ready_for_apply_row_count_after_draft: `{s['ready_for_apply_row_count_after_draft']}`",
        f"- blocked_row_count_after_draft: `{s['blocked_row_count_after_draft']}`",
        f"- authoritative_replacement_fields_touched: `{s['authoritative_replacement_fields_touched']}`",
        "",
        "## Draft Rows",
        "",
        "| step | ligand | kcal | source | ready |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in payload["draft_rows"]:
        lines.append(
            f"| `{row.get('packet_step', '')}` | `{row.get('replacement_ligand_id', '')}` | "
            f"`{row.get('replacement_reference_binding_kcal_mol', '')}` | "
            f"`{row.get('replacement_source', '')}` | `{row.get('row_ready_for_apply', '')}` |"
        )
    lines.extend(["", "## Next Step", "", s["next_required_step"], "", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PXR direct-binding replacement apply draft.")
    parser.add_argument("--workbook-csv", default=DEFAULT_WORKBOOK_CSV.as_posix())
    parser.add_argument("--candidate-json", default=DEFAULT_CANDIDATE_JSON.as_posix())
    parser.add_argument("--molecule-dir", default=DEFAULT_MOLECULE_DIR.as_posix())
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON.as_posix())
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV.as_posix())
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD.as_posix())
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    fieldnames, workbook_rows = _read_csv(args.workbook_csv)
    payload = build_payload(
        workbook_rows=workbook_rows,
        workbook_fieldnames=fieldnames,
        candidate_packet=_read_json(args.candidate_json),
        molecule_dir=args.molecule_dir,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["summary"]["fieldnames"], payload["draft_rows"])
    write_csv_rows(_resolve(args.out_csv + ".summary.csv"), [payload["summary"]])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
