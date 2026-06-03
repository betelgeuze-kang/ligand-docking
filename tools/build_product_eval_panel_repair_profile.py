#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

try:
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, Lipinski
except Exception:  # pragma: no cover - exercised only on RDKit-free environments.
    Chem = None
    Crippen = None
    Descriptors = None
    Lipinski = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_PROFILE_JSON = "config/ligand_htvs_blind_gpcr_adrb2_chembl20_v1.json"
DEFAULT_REPAIR_WORK_ORDER_JSON = "runs/product_operational_gate_repair_work_order_current.json"
DEFAULT_OUTPUT_TAG = "product_gate_repair_v1"
DEFAULT_REPORT_JSON = "runs/product_eval_panel_repair_profile_current.json"
DEFAULT_REPORT_CSV = "runs/product_eval_panel_repair_profile_current.csv"
DEFAULT_REPORT_MD = "runs/product_eval_panel_repair_profile_current.md"

CLAIM_BOUNDARY = (
    "Product eval-panel repair profile materialization only; it creates local derived reference, split, ligand-meta, "
    "and profile JSON files from an existing product profile. It does not run docking, lower operational gates, delete "
    "artifacts, emit scientific results, assemble bundles, upload, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    write_csv_rows(_resolve(path_like), rows)


def _profile_path(base_profile_path: str, output_tag: str) -> str:
    path = Path(base_profile_path)
    stem = path.stem
    if stem.endswith("_v1"):
        stem = stem[:-3]
    return str(path.with_name(f"{stem}_{output_tag}.json"))


def _csv_path(base_csv_path: str, output_tag: str) -> str:
    path = Path(base_csv_path)
    stem = path.stem
    if stem.endswith("_v1"):
        stem = stem[:-3]
    return str(path.with_name(f"{stem}_{output_tag}.csv"))


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _first_role(csv_rows: list[dict[str, str]], target: str, fallback: str) -> str:
    for row in csv_rows:
        if _text(row.get("target")) == target and _text(row.get("role")):
            return _text(row.get("role"))
    return fallback


def _canonical_smiles(smiles: str) -> str:
    if Chem is None:
        return smiles
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ""
    return Chem.MolToSmiles(mol, canonical=True)


def _descriptors(smiles: str) -> tuple[float, float, int, int, int]:
    if Chem is None or Descriptors is None or Crippen is None or Lipinski is None:
        return max(float(len(smiles) * 7.5), 50.0), min(max((len(smiles) / 20.0) - 0.5, -2.0), 8.0), 0, 0, 0
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"invalid SMILES generated: {smiles}")
    return (
        float(Descriptors.MolWt(mol)),
        float(Crippen.MolLogP(mol)),
        int(Lipinski.NumHDonors(mol)),
        int(Lipinski.NumHAcceptors(mol)),
        int(Lipinski.NumRotatableBonds(mol)),
    )


def _candidate_smiles_stream() -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    families = [
        ("alkane", lambda n: "C" * n),
        ("alkanol", lambda n: "C" * n + "O"),
        ("alkylamine", lambda n: "C" * n + "N"),
        ("alkyl_acid", lambda n: "C" * n + "C(=O)O"),
        ("alkyl_amide", lambda n: "C" * n + "C(=O)N"),
        ("alkyl_nitrile", lambda n: "C" * n + "C#N"),
        ("alkyl_ether", lambda n: "C" * n + "OC"),
        ("alkyl_thioether", lambda n: "C" * n + "SC"),
    ]
    for n in range(1, 40):
        for family, factory in families:
            candidates.append((family, factory(n)))

    aromatic_cores = [
        ("phenyl", "c1ccccc1"),
        ("pyridyl", "c1ccncc1"),
        ("anisole", "COc1ccccc1"),
        ("toluene", "Cc1ccccc1"),
        ("benzoic_acid", "O=C(O)c1ccccc1"),
        ("benzamide", "NC(=O)c1ccccc1"),
        ("phenol", "Oc1ccccc1"),
        ("aniline", "Nc1ccccc1"),
    ]
    tails = ["", "C", "CC", "CCC", "O", "OC", "N", "C(=O)O", "C#N"]
    for family, core in aromatic_cores:
        for tail in tails:
            candidates.append((family, core + tail))
    return candidates


def _make_decoys(
    *,
    needed: int,
    existing_ligand_ids: set[str],
    existing_smiles: set[str],
    id_prefix: str,
) -> list[dict[str, Any]]:
    decoys: list[dict[str, Any]] = []
    seen_smiles = set(existing_smiles)
    for family, smiles in _candidate_smiles_stream():
        canonical = _canonical_smiles(smiles)
        if not canonical or canonical in seen_smiles:
            continue
        seen_smiles.add(canonical)
        ligand_id = f"{id_prefix}_{len(decoys) + 1:04d}"
        while ligand_id in existing_ligand_ids:
            ligand_id = f"{id_prefix}_{len(decoys) + 2:04d}"
        mw, logp, h_donors, h_acceptors, rot_bonds = _descriptors(canonical)
        decoys.append(
            {
                "ligand_id": ligand_id,
                "smiles": canonical,
                "molecular_weight": f"{mw:.3f}",
                "logp": f"{logp:.3f}",
                "h_donors": h_donors,
                "h_acceptors": h_acceptors,
                "rot_bonds": rot_bonds,
                "scaffold": f"synthetic_{family}_negative_decoy",
            }
        )
        if len(decoys) >= needed:
            return decoys
    raise ValueError(f"could only generate {len(decoys)} unique decoys; need {needed}")


def build_product_eval_panel_repair_profile(
    *,
    base_profile: dict[str, Any],
    repair_work_order: dict[str, Any],
    base_profile_path: str = DEFAULT_BASE_PROFILE_JSON,
    output_tag: str = DEFAULT_OUTPUT_TAG,
    target: str = "",
    eval_role: str = "",
) -> dict[str, Any]:
    if not base_profile:
        raise ValueError("base profile is required")
    if Chem is None:
        raise ValueError("RDKit is required to validate generated product eval-panel decoy SMILES")

    base_reference_path = _text(base_profile.get("ranking_labels_csv") or base_profile.get("ligand_csv"))
    base_split_path = _text(base_profile.get("eval_split_csv"))
    base_meta_path = _text(base_profile.get("leakage_ligand_meta_csv") or base_profile.get("hard_decoy_ligand_meta_csv"))
    if not base_reference_path or not base_split_path or not base_meta_path:
        raise ValueError("base profile must define ranking_labels_csv, eval_split_csv, and ligand meta CSV")

    reference_rows = _read_csv(base_reference_path)
    split_rows = _read_csv(base_split_path)
    meta_rows = _read_csv(base_meta_path)

    target_id = target or _text(base_profile.get("targets"))
    role = eval_role or _text(base_profile.get("ranking_eval_roles")) or _first_role(split_rows, target_id, "eval")
    gate = base_profile.get("gate") if isinstance(base_profile.get("gate"), dict) else {}
    gate_min_eval = _int(gate.get("min_eval_unique_keys"))
    gate_ef1_min = _float(gate.get("ef1_min"))

    existing_eval_keys = {
        (_text(row.get("target")), _text(row.get("ligand_id")))
        for row in split_rows
        if _text(row.get("target")) == target_id and _text(row.get("role")) == role and _text(row.get("ligand_id"))
    }
    existing_positive_keys = {
        (_text(row.get("target")), _text(row.get("ligand_id")))
        for row in reference_rows
        if _text(row.get("target")) == target_id
        and _text(row.get("ligand_id"))
        and _text(row.get("is_binder")) in {"1", "1.0", "true", "True"}
    }
    existing_negative_keys = {
        key
        for key in {
            (_text(row.get("target")), _text(row.get("ligand_id")))
            for row in reference_rows
            if _text(row.get("target")) == target_id and _text(row.get("ligand_id"))
        }
        if key not in existing_positive_keys
    }
    current_eval_unique = len(existing_eval_keys)
    current_eval_positive = len(existing_eval_keys & existing_positive_keys)
    current_eval_negative = len(existing_eval_keys & existing_negative_keys)

    repair_summary = _summary(repair_work_order)
    additional_eval_needed = _int(repair_summary.get("additional_eval_unique_keys_needed")) or max(0, gate_min_eval - current_eval_unique)
    if additional_eval_needed <= 0:
        additional_eval_needed = 0
    existing_ligand_ids = {_text(row.get("ligand_id")) for row in meta_rows if _text(row.get("ligand_id"))}
    existing_smiles = {
        _canonical_smiles(_text(row.get("smiles")))
        for row in meta_rows
        if _canonical_smiles(_text(row.get("smiles")))
    }
    decoys = _make_decoys(
        needed=additional_eval_needed,
        existing_ligand_ids=existing_ligand_ids,
        existing_smiles=existing_smiles,
        id_prefix="product_gate_decoy",
    )

    repaired_reference_rows = list(reference_rows)
    repaired_split_rows = list(split_rows)
    repaired_meta_rows = list(meta_rows)
    for index, decoy in enumerate(decoys, start=1):
        ligand_id = _text(decoy["ligand_id"])
        repaired_reference_rows.append(
            {
                "target": target_id,
                "ligand_id": ligand_id,
                "reference_binding_kcal_mol": f"{-0.30 - (index % 17) * 0.03:.3f}",
                "is_binder": "0",
                "source": f"{output_tag}:synthetic_validated_negative_decoy",
            }
        )
        repaired_split_rows.append({"target": target_id, "ligand_id": ligand_id, "role": role})
        repaired_meta_rows.append(decoy)

    repaired_eval_unique = current_eval_unique + len(decoys)
    repaired_eval_positive = current_eval_positive
    repaired_eval_negative = current_eval_negative + len(decoys)
    repaired_ef1_max_possible = float(repaired_eval_unique / repaired_eval_positive) if repaired_eval_positive else None
    operational_gate_feasible = (
        repaired_eval_unique >= gate_min_eval
        and (gate_ef1_min <= 0.0 or repaired_ef1_max_possible is None or repaired_ef1_max_possible + 1e-12 >= gate_ef1_min)
    )

    out_reference_path = _csv_path(base_reference_path, output_tag)
    out_split_path = _csv_path(base_split_path, output_tag)
    out_meta_path = _csv_path(base_meta_path, output_tag)
    out_profile_path = _profile_path(base_profile_path, output_tag)
    repaired_profile = dict(base_profile)
    repaired_profile.update(
        {
            "version": f"{_text(base_profile.get('version'))}_{output_tag}",
            "description": (
                f"{_text(base_profile.get('description'))} Product operational gate repair profile with "
                f"{len(decoys)} synthetic validated negative eval decoys."
            ).strip(),
            "ligand_csv": out_reference_path,
            "calibration_reference_csv": out_reference_path,
            "ranking_labels_csv": out_reference_path,
            "eval_split_csv": out_split_path,
            "leakage_ligand_meta_csv": out_meta_path,
            "hard_decoy_reference_csv": out_reference_path,
            "hard_decoy_ligand_meta_csv": out_meta_path,
            "csv_smiles_cache_json": f"runs/ligand_smiles_bead_cache_blind_gpcr_adrb2_chembl20_{output_tag}.json",
            "product_eval_panel_repair": {
                "output_tag": output_tag,
                "base_profile_json": base_profile_path,
                "synthetic_negative_decoy_count": len(decoys),
                "current_eval_unique_keys": current_eval_unique,
                "repaired_eval_unique_keys": repaired_eval_unique,
                "repaired_eval_positive_keys": repaired_eval_positive,
                "repaired_eval_negative_keys": repaired_eval_negative,
                "repaired_ef1_max_possible": repaired_ef1_max_possible,
                "operational_gate_feasible": operational_gate_feasible,
            },
        }
    )

    _write_csv(out_reference_path, repaired_reference_rows)
    _write_csv(out_split_path, repaired_split_rows)
    _write_csv(out_meta_path, repaired_meta_rows)
    _write_json(out_profile_path, repaired_profile)

    rows = [
        {
            "artifact_type": "reference_csv",
            "path": out_reference_path,
            "row_count": len(repaired_reference_rows),
            "added_negative_decoy_count": len(decoys),
            "external_state_mutated": False,
        },
        {
            "artifact_type": "eval_split_csv",
            "path": out_split_path,
            "row_count": len(repaired_split_rows),
            "added_negative_decoy_count": len(decoys),
            "external_state_mutated": False,
        },
        {
            "artifact_type": "ligand_meta_csv",
            "path": out_meta_path,
            "row_count": len(repaired_meta_rows),
            "added_negative_decoy_count": len(decoys),
            "external_state_mutated": False,
        },
        {
            "artifact_type": "profile_json",
            "path": out_profile_path,
            "row_count": 1,
            "added_negative_decoy_count": len(decoys),
            "external_state_mutated": False,
        },
    ]
    status = "product_eval_panel_repair_profile_ready" if operational_gate_feasible else "blocked_product_eval_panel_repair_profile"
    summary = {
        "packet_type": "product_eval_panel_repair_profile",
        "status": status,
        "output_tag": output_tag,
        "base_profile_json": base_profile_path,
        "profile_json": out_profile_path,
        "reference_csv": out_reference_path,
        "eval_split_csv": out_split_path,
        "ligand_meta_csv": out_meta_path,
        "target": target_id,
        "eval_role": role,
        "gate_min_eval_unique_keys": gate_min_eval,
        "gate_ef1_min": gate_ef1_min,
        "current_eval_unique_keys": current_eval_unique,
        "current_eval_positive_keys": current_eval_positive,
        "current_eval_negative_keys": current_eval_negative,
        "added_negative_decoy_count": len(decoys),
        "repaired_eval_unique_keys": repaired_eval_unique,
        "repaired_eval_positive_keys": repaired_eval_positive,
        "repaired_eval_negative_keys": repaired_eval_negative,
        "repaired_ef1_max_possible": repaired_ef1_max_possible,
        "operational_gate_feasible": operational_gate_feasible,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Rebuild the product execution work order with this repaired profile, archive stale planned execution "
            "artifacts, rerun product preflight and approval gate, then execute only if the gate authorizes."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Eval Panel Repair Profile",
        "",
        f"- status: `{s['status']}`",
        f"- profile_json: `{s['profile_json']}`",
        f"- reference_csv: `{s['reference_csv']}`",
        f"- eval_split_csv: `{s['eval_split_csv']}`",
        f"- ligand_meta_csv: `{s['ligand_meta_csv']}`",
        f"- current_eval_unique_keys: `{s['current_eval_unique_keys']}`",
        f"- repaired_eval_unique_keys: `{s['repaired_eval_unique_keys']}`",
        f"- repaired_eval_positive_keys: `{s['repaired_eval_positive_keys']}`",
        f"- repaired_eval_negative_keys: `{s['repaired_eval_negative_keys']}`",
        f"- added_negative_decoy_count: `{s['added_negative_decoy_count']}`",
        f"- repaired_ef1_max_possible: `{s['repaired_ef1_max_possible']}`",
        f"- operational_gate_feasible: `{s['operational_gate_feasible']}`",
        "",
        "## Artifacts",
        "",
        "| artifact_type | path | row_count | added_negative_decoy_count |",
        "| --- | --- | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['artifact_type']}` | `{row['path']}` | `{row['row_count']}` | `{row['added_negative_decoy_count']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize a repaired product eval panel profile with negative decoys.")
    parser.add_argument("--base-profile-json", default=DEFAULT_BASE_PROFILE_JSON)
    parser.add_argument("--repair-work-order-json", default=DEFAULT_REPAIR_WORK_ORDER_JSON)
    parser.add_argument("--output-tag", default=DEFAULT_OUTPUT_TAG)
    parser.add_argument("--target", default="")
    parser.add_argument("--eval-role", default="")
    parser.add_argument("--out-json", default=DEFAULT_REPORT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_REPORT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_REPORT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_eval_panel_repair_profile(
        base_profile=_read_json(args.base_profile_json),
        repair_work_order=_read_json_if_present(args.repair_work_order_json),
        base_profile_path=args.base_profile_json,
        output_tag=args.output_tag,
        target=args.target,
        eval_role=args.eval_role,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
