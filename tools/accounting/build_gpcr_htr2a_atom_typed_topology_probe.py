#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Any

from tools.lib.artifacts import (
    artifact as _artifact,
    read_csv as _read_csv,
    resolve as _resolve,
    write_csv as _write_csv,
    write_json as _write_json,
)

try:  # pragma: no cover - fallback path is covered by pure-Python token parsing.
    from rdkit import Chem  # type: ignore
except Exception:  # pragma: no cover
    Chem = None  # type: ignore

DEFAULT_REPAIR_ROWS_CSV = "runs/gpcr_htr2a_anchor_support_repair_packet_rows_current.csv"
DEFAULT_STAGE3_SCORES_CSV = (
    "runs/archive/runs_artifact_inventory_root_archive_current/"
    "external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_OUT_JSON = "runs/gpcr_htr2a_atom_typed_topology_probe_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_htr2a_atom_typed_topology_probe_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_htr2a_atom_typed_topology_probe_current.md"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _int(value: Any) -> int | None:
    value_float = _float(value)
    return int(value_float) if value_float is not None else None


def _token_topology(smiles: str) -> dict[str, Any]:
    tokens = re.findall(r"Cl|Br|[BCNOFPSI][a-z]?|[cnops]", _text(smiles))
    heavy_atom_count = len(tokens)
    aromatic_atom_count = sum(1 for token in tokens if token and token[0].islower())
    aromatic_ring_count = int(aromatic_atom_count // 6) if aromatic_atom_count >= 6 else 0
    nitrogen_count = sum(1 for token in tokens if token.upper().startswith("N"))
    basic_amine_count = sum(1 for token in tokens if token == "N")
    hetero_atom_count = sum(1 for token in tokens if token[:1].upper() != "C")
    sulfone_like_count = 1 if re.search(r"S(?:\d)?\(?=O\)?", smiles) and smiles.count("=O") >= 2 else 0
    return {
        "topology_method": "token_fallback",
        "heavy_atom_count": heavy_atom_count,
        "aromatic_atom_count": aromatic_atom_count,
        "aromatic_ring_count": aromatic_ring_count,
        "nitrogen_count": nitrogen_count,
        "basic_amine_count": basic_amine_count,
        "hetero_atom_count": hetero_atom_count,
        "sulfone_like_count": sulfone_like_count,
    }


def _rdkit_topology(smiles: str) -> dict[str, Any]:
    src = _text(smiles)
    if not src or Chem is None:
        return _token_topology(src)
    mol = Chem.MolFromSmiles(src)
    if mol is None:
        return _token_topology(src)
    ring_info = mol.GetRingInfo()
    aromatic_atom_count = sum(1 for atom in mol.GetAtoms() if atom.GetIsAromatic())
    aromatic_ring_count = sum(
        1 for ring in ring_info.AtomRings() if all(mol.GetAtomWithIdx(idx).GetIsAromatic() for idx in ring)
    )
    basic_amine_count = 0
    sulfone_like_count = 0
    for atom in mol.GetAtoms():
        if (
            atom.GetAtomicNum() == 7
            and not atom.GetIsAromatic()
            and (atom.GetFormalCharge() > 0 or atom.GetTotalNumHs() > 0 or atom.GetDegree() >= 2)
        ):
            basic_amine_count += 1
        if atom.GetAtomicNum() == 16:
            oxygen_neighbors = sum(1 for neighbor in atom.GetNeighbors() if neighbor.GetAtomicNum() == 8)
            if oxygen_neighbors >= 2:
                sulfone_like_count += 1
    return {
        "topology_method": "rdkit",
        "heavy_atom_count": int(mol.GetNumHeavyAtoms()),
        "aromatic_atom_count": int(aromatic_atom_count),
        "aromatic_ring_count": int(aromatic_ring_count),
        "nitrogen_count": int(sum(1 for atom in mol.GetAtoms() if atom.GetAtomicNum() == 7)),
        "basic_amine_count": int(basic_amine_count),
        "hetero_atom_count": int(sum(1 for atom in mol.GetAtoms() if atom.GetAtomicNum() not in (1, 6))),
        "sulfone_like_count": int(sulfone_like_count),
    }


def _topology_support(features: dict[str, Any]) -> float:
    heavy_gate = 1.0 if int(features.get("heavy_atom_count") or 0) >= 24 else 0.0
    aromatic_gate = 1.0 if int(features.get("aromatic_ring_count") or 0) >= 2 else 0.0
    basic_gate = 1.0 if int(features.get("basic_amine_count") or 0) >= 2 else 0.0
    sulfone_gate = 1.0 if int(features.get("sulfone_like_count") or 0) >= 1 else 0.0
    return float(heavy_gate * aromatic_gate * basic_gate * sulfone_gate)


def _stage3_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        target = _text(row.get("target"))
        ligand_id = _text(row.get("ligand_id"))
        if target and ligand_id:
            out[(target, ligand_id)] = row
    return out


def build_probe(
    *,
    repair_rows_csv: str | Path = DEFAULT_REPAIR_ROWS_CSV,
    stage3_scores_csv: str | Path = DEFAULT_STAGE3_SCORES_CSV,
    generated_at_local: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    repair_rows = _read_csv(repair_rows_csv)
    stage3_rows = _stage3_lookup(_read_csv(stage3_scores_csv))
    out_rows: list[dict[str, Any]] = []
    for row in repair_rows:
        target = _text(row.get("target"))
        ligand_id = _text(row.get("ligand_id"))
        stage3 = stage3_rows.get((target, ligand_id), {})
        smiles = _text(stage3.get("ligand_smiles") or stage3.get("smiles") or stage3.get("canonical_smiles"))
        topology = _rdkit_topology(smiles)
        support = _topology_support(topology)
        out_rows.append(
            {
                "target_rank": _int(row.get("target_rank")),
                "row_role": _text(row.get("row_role")),
                "target": target,
                "ligand_id": ligand_id,
                "smiles_present": bool(smiles),
                "topology_probe_support": support,
                "topology_probe_pressure": 0.0 if support > 0.0 else 1.0,
                "exact_anchor_signature_matches_positive": _text(row.get("exact_anchor_signature_matches_positive")),
                "generic_anchor_signature_matches_positive": _text(row.get("generic_anchor_signature_matches_positive")),
                **topology,
            }
        )
    positive = next((row for row in out_rows if row.get("row_role") == "positive"), {})
    decoys = [row for row in out_rows if row.get("row_role") != "positive"]
    positive_support = _float(positive.get("topology_probe_support")) if positive else None
    max_decoy_support = max((_float(row.get("topology_probe_support")) or 0.0 for row in decoys), default=0.0)
    decoy_support_positive_or_higher = sum(
        1
        for row in decoys
        if positive_support is not None and (_float(row.get("topology_probe_support")) or 0.0) >= positive_support
    )
    missing_smiles_count = sum(1 for row in out_rows if not row.get("smiles_present"))
    if missing_smiles_count:
        status = "blocked_htr2a_topology_probe_smiles_missing"
        next_action = "restore_htr2a_stage3_smiles_before_probe_replay"
    elif positive_support == 1.0 and decoy_support_positive_or_higher == 0:
        status = "htr2a_atom_typed_topology_probe_separates_current_slice_diagnostic_only"
        next_action = "prototype_claim_locked_htr2a_topology_support_shadow_replay"
    else:
        status = "blocked_htr2a_topology_probe_does_not_separate_current_slice"
        next_action = "add_structure_contact_probe_before_shadow_replay"
    next_required_step = (
        "Promote this only as a claim-locked diagnostic feature contract: replay the atom-typed topology support "
        "on the frozen GPCR rows and require HTR2A target-rank 1 without DRD2/OPRM1 regression. Do not apply it "
        "to the active scorer or guarded 100k claim review until the replay, leakage checks, and OPRM1 repair pass."
    )
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "guarded_100k_rerun_allowed": False,
        "repair_rows_csv": _artifact(repair_rows_csv),
        "stage3_scores_csv": _artifact(stage3_scores_csv),
        "row_count": len(out_rows),
        "decoy_row_count": len(decoys),
        "missing_smiles_count": missing_smiles_count,
        "positive_ligand_id": positive.get("ligand_id"),
        "positive_topology_probe_support": positive_support,
        "positive_heavy_atom_count": positive.get("heavy_atom_count"),
        "positive_aromatic_ring_count": positive.get("aromatic_ring_count"),
        "positive_basic_amine_count": positive.get("basic_amine_count"),
        "positive_sulfone_like_count": positive.get("sulfone_like_count"),
        "max_decoy_topology_probe_support": max_decoy_support,
        "decoy_support_positive_or_higher_count": decoy_support_positive_or_higher,
        "next_action": next_action,
        "next_required_step": next_required_step,
    }
    payload = {
        "packet_type": "gpcr_htr2a_atom_typed_topology_probe",
        "summary": summary,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "guarded_100k_rerun_allowed": False,
            "threshold_relaxation_allowed": False,
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "fake_pass_allowed": False,
        },
        "feature_contract": {
            "feature_name": "htr2a_atom_typed_topology_support_probe",
            "diagnostic_formula": (
                "heavy_atom_count>=24 and aromatic_ring_count>=2 and basic_amine_count>=2 and "
                "sulfone_like_count>=1"
            ),
            "diagnostic_only": True,
            "requires_replay_before_apply": True,
        },
        "rows": out_rows,
    }
    return payload, out_rows


def _render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    return "\n".join(
        [
            "# GPCR HTR2A Atom-Typed Topology Probe",
            "",
            f"- status: `{s['status']}`",
            f"- claim_promotion_allowed: `{str(s['claim_promotion_allowed']).lower()}`",
            f"- scorer_apply_allowed: `{str(s['scorer_apply_allowed']).lower()}`",
            f"- guarded_100k_rerun_allowed: `{str(s['guarded_100k_rerun_allowed']).lower()}`",
            f"- row_count: `{s['row_count']}`",
            f"- missing_smiles_count: `{s['missing_smiles_count']}`",
            f"- positive_ligand_id: `{s['positive_ligand_id']}`",
            f"- positive_topology_probe_support: `{s['positive_topology_probe_support']}`",
            f"- positive_heavy_atom_count: `{s['positive_heavy_atom_count']}`",
            f"- positive_aromatic_ring_count: `{s['positive_aromatic_ring_count']}`",
            f"- positive_basic_amine_count: `{s['positive_basic_amine_count']}`",
            f"- positive_sulfone_like_count: `{s['positive_sulfone_like_count']}`",
            f"- max_decoy_topology_probe_support: `{s['max_decoy_topology_probe_support']}`",
            f"- decoy_support_positive_or_higher_count: `{s['decoy_support_positive_or_higher_count']}`",
            f"- next_action: `{s['next_action']}`",
            "",
            "## Next Required Step",
            "",
            s["next_required_step"],
            "",
            "## Diagnostic Formula",
            "",
            f"`{payload['feature_contract']['diagnostic_formula']}`",
            "",
        ]
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an HTR2A atom-typed topology diagnostic probe.")
    parser.add_argument("--repair-rows-csv", default=DEFAULT_REPAIR_ROWS_CSV)
    parser.add_argument("--stage3-scores-csv", default=DEFAULT_STAGE3_SCORES_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload, rows = build_probe(repair_rows_csv=args.repair_rows_csv, stage3_scores_csv=args.stage3_scores_csv)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, rows)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
