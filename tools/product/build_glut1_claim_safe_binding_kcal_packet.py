#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RT_KCAL_MOL_298K = 0.00198720425864083 * 298.15

DEFAULT_SOURCE_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_PUBCHEM_JSON = "runs/life_science_skill_crosscheck/pubchem_cytochalasin_b.json"
DEFAULT_CHEMBL_ACTIVITY_JSON = "runs/life_science_skill_crosscheck/chembl_activity_glut1_cytochalasin_b.json"
DEFAULT_OUT_JSON = "runs/glut1_claim_safe_binding_kcal_packet_current.json"
DEFAULT_OUT_CSV = "runs/glut1_claim_safe_binding_kcal_packet_current.csv"
DEFAULT_OUT_MD = "runs/glut1_claim_safe_binding_kcal_packet_current.md"

TARGET_ID = "GLUT1"
PACKET_STEP = "core_binder_01"
REPLACEMENT_LIGAND_ID = "cytochalasin_b"
REPLACEMENT_ROLE = "far_ood_eval"
REPLACEMENT_SCAFFOLD = "cytochalasin_macrocycle"


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
    return json.loads(path.read_text(encoding="utf-8"))


def _text(value: Any) -> str:
    return str(value or "").strip()


def _dg_from_nm(value_nM: float) -> str:
    return f"{RT_KCAL_MOL_298K * math.log(value_nM * 1e-9):.4f}"


def _direct_binding_nm(measure: str) -> float | None:
    match = re.search(r"\bK[di]\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*nM\b", measure, flags=re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    return value if value > 0 else None


def _source_row(source_payload: dict[str, Any]) -> dict[str, Any]:
    for row in source_payload.get("rows", []) or []:
        if _text(row.get("packet_step")) == PACKET_STEP and _text(row.get("candidate_name")).lower() == "cytochalasin b":
            return dict(row)
    return {}


def _pubchem_props(pubchem_payload: dict[str, Any]) -> dict[str, Any]:
    props = ((pubchem_payload.get("PropertyTable") or {}).get("Properties") or [])
    return dict(props[0]) if props else {}


def _chembl_activity(chembl_payload: dict[str, Any]) -> dict[str, Any]:
    activities = chembl_payload.get("activities") or []
    return dict(activities[0]) if activities else {}


def build_payload(
    *,
    source_payload: dict[str, Any],
    pubchem_payload: dict[str, Any],
    chembl_activity_payload: dict[str, Any],
) -> dict[str, Any]:
    source = _source_row(source_payload)
    direct_binding_nM = _direct_binding_nm(_text(source.get("direct_binding_measure")))
    pubchem = _pubchem_props(pubchem_payload)
    chembl = _chembl_activity(chembl_activity_payload)

    smiles = _text(chembl.get("canonical_smiles")) or _text(pubchem.get("ConnectivitySMILES"))
    molecular_weight = _text(pubchem.get("MolecularWeight"))
    source_anchor = _text(source.get("source_anchor")) or "PMID 1716731"
    source_url = _text(source.get("source_url"))
    chembl_activity_url = _text(source.get("chembl_activity_url"))
    source_ready = bool(source and direct_binding_nM and smiles and molecular_weight)

    rows: list[dict[str, Any]] = []
    if source_ready and direct_binding_nM is not None:
        kcal = _dg_from_nm(direct_binding_nM)
        rows.append(
            {
                "target_id": TARGET_ID,
                "packet_step": PACKET_STEP,
                "candidate_name": "cytochalasin B",
                "replacement_ligand_id": REPLACEMENT_LIGAND_ID,
                "replacement_reference_binding_kcal_mol": kcal,
                "replacement_is_binder": "1",
                "replacement_source": (
                    f"pubmed_direct_binding::{source_anchor.replace(' ', '')}::CHEMBL2535::CHEMBL411729::"
                    f"Kd_{direct_binding_nM:g}_nM::deltaG_298K_{kcal}"
                ),
                "replacement_role": REPLACEMENT_ROLE,
                "replacement_smiles": smiles,
                "replacement_molecular_weight": molecular_weight,
                "replacement_logp": "",
                "replacement_h_donors": "",
                "replacement_h_acceptors": "",
                "replacement_rot_bonds": "",
                "replacement_scaffold": REPLACEMENT_SCAFFOLD,
                "direct_binding_measure": _text(source.get("direct_binding_measure")),
                "direct_binding_value_nM": f"{direct_binding_nM:g}",
                "delta_g_method": "RTln(Kd_M) at 298.15 K",
                "claim_safe_binding_kcal_ready": "yes",
                "manual_verdict": "promote_authoritative_apply",
                "source_url": source_url,
                "chembl_activity_url": chembl_activity_url,
                "source_artifacts": (
                    f"{DEFAULT_SOURCE_JSON};{DEFAULT_PUBCHEM_JSON};{DEFAULT_CHEMBL_ACTIVITY_JSON}"
                ),
                "row_ready_for_apply": "yes",
                "claim_boundary": (
                    "Direct human GLUT1 Kd-derived deltaG proxy for this binder row only; does not promote "
                    "WZB117, STF-31, non-binders, donor policy, runnable profiles, or broad transporter scope."
                ),
            }
        )

    summary = {
        "status": "glut1_claim_safe_binding_kcal_packet_ready" if rows else "blocked_glut1_claim_safe_binding_kcal_packet",
        "target_id": TARGET_ID,
        "packet_step": PACKET_STEP,
        "claim_safe_row_count": len(rows),
        "claim_safe_binding_kcal_ready_count": sum(1 for row in rows if row["claim_safe_binding_kcal_ready"] == "yes"),
        "source_direct_binding_measure": _text(source.get("direct_binding_measure")),
        "source_smiles_ready": bool(smiles),
        "source_molecular_weight_ready": bool(molecular_weight),
        "external_state_mutated": False,
        "next_required_step": (
            "Use this row to fill the GLUT1 core_binder_01 workbook slot, then rerun transporter binder promotion and donor-policy gates."
            if rows
            else "Keep GLUT1 binder promotion blocked until direct binding measure, SMILES, and molecular weight are all available."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# GLUT1 Claim-Safe Binding Kcal Packet",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- packet_step: `{s['packet_step']}`",
        f"- claim_safe_row_count: `{s['claim_safe_row_count']}`",
        f"- claim_safe_binding_kcal_ready_count: `{s['claim_safe_binding_kcal_ready_count']}`",
        f"- source_direct_binding_measure: `{s['source_direct_binding_measure']}`",
        "",
        "## Rows",
        "",
        "| target | packet_step | ligand | kcal | measure | method | ready |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['packet_step']}` | `{row['replacement_ligand_id']}` | "
            f"{row['replacement_reference_binding_kcal_mol']} | `{row['direct_binding_measure']}` | "
            f"`{row['delta_g_method']}` | `{row['row_ready_for_apply']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a claim-safe GLUT1 cytochalasin B binding kcal packet.")
    parser.add_argument("--source-json", default=DEFAULT_SOURCE_JSON)
    parser.add_argument("--pubchem-json", default=DEFAULT_PUBCHEM_JSON)
    parser.add_argument("--chembl-activity-json", default=DEFAULT_CHEMBL_ACTIVITY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        source_payload=_load_json(args.source_json),
        pubchem_payload=_load_json(args.pubchem_json),
        chembl_activity_payload=_load_json(args.chembl_activity_json),
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
