#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from tools.lib.artifacts import artifact as _artifact
from tools.lib.artifacts import read_json as _read_json
from tools.lib.artifacts import resolve as _resolve
from tools.lib.artifacts import write_csv as _write_csv
from tools.lib.artifacts import write_json as _write_json

DEFAULT_PACKET_JSON = "runs/gpcr_positive_coverage_expansion_packet_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_positive_coverage_materialization_manifest_current.json"
DEFAULT_OUT_MD = "runs/gpcr_positive_coverage_materialization_manifest_current.md"
DEFAULT_REFERENCE_APPEND_CSV = "runs/gpcr_positive_coverage_candidate_reference_append_current.csv"
DEFAULT_SPLITS_APPEND_CSV = "runs/gpcr_positive_coverage_candidate_splits_append_current.csv"

RT_KCAL_298K = 0.00198720425864083 * 298.15


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


def _binding_kcal_from_pchembl(pchembl: float | None) -> float | None:
    if pchembl is None:
        return None
    return float(RT_KCAL_298K * math.log(10 ** (-float(pchembl))))


def _source_url(activity_id: Any) -> str:
    activity_id_text = _text(activity_id)
    return f"https://www.ebi.ac.uk/chembl/api/data/activity/{activity_id_text}.json" if activity_id_text else ""


def build_manifest(
    *,
    packet_json: str | Path = DEFAULT_PACKET_JSON,
    generated_at_local: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    packet = _read_json(packet_json)
    rows = packet.get("rows", [])
    rows = rows if isinstance(rows, list) else []
    ready_rows = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("inclusion_decision") == "ready_for_frozen_pipeline_materialization"
    ]
    reference_rows: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    for row in ready_rows:
        pchembl = _float(row.get("pchembl_value"))
        binding_kcal = _binding_kcal_from_pchembl(pchembl)
        if binding_kcal is None:
            blockers.append(f"{row.get('target')}:{row.get('candidate_ligand_id')}:missing_pchembl")
            continue
        if not row.get("canonical_smiles"):
            blockers.append(f"{row.get('target')}:{row.get('candidate_ligand_id')}:missing_smiles")
            continue
        target = _text(row.get("target"))
        ligand_id = _text(row.get("candidate_ligand_id"))
        source = (
            f"ChEMBL activity {row.get('chembl_activity_id')} "
            f"{row.get('standard_type')} pChEMBL {row.get('pchembl_value')}"
        )
        reference_rows.append(
            {
                "target": target,
                "ligand_id": ligand_id,
                "reference_binding_kcal_mol": round(binding_kcal, 3),
                "is_binder": 1,
                "source": source,
                "source_url": _source_url(row.get("chembl_activity_id")),
                "row_classification": "coverage_expansion_non_adrb2_gpcr_positive_candidate",
                "canonical_smiles": row.get("canonical_smiles"),
                "uniprot_accession": row.get("uniprot_accession"),
                "structure_source_priority": row.get("structure_source_priority"),
                "rcsb_first_hit": row.get("rcsb_first_hit"),
                "alphafold_model_count": row.get("alphafold_model_count"),
                "pubchem_cid": row.get("pubchem_cid"),
            }
        )
        split_rows.append(
            {
                "target": target,
                "ligand_id": ligand_id,
                "split_id": "gpcr_positive_coverage_expansion_v1",
                "role": "far_ood_eval",
                "leakage_policy": "do_not_fit_or_calibrate",
                "row_classification": "coverage_expansion_non_adrb2_gpcr_positive_candidate",
                "materialization_state": "reference_and_split_ready_decoys_and_trajectories_pending",
            }
        )

    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": (
            "gpcr_positive_coverage_materialization_manifest_ready"
            if reference_rows and not blockers
            else "blocked_gpcr_positive_coverage_materialization_manifest"
        ),
        "packet_json": _artifact(packet_json),
        "ready_input_row_count": len(ready_rows),
        "reference_append_row_count": len(reference_rows),
        "split_append_row_count": len(split_rows),
        "projected_positive_count_after_append": 3 + len(reference_rows),
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "blockers": blockers,
        "next_required_step": (
            "Append these reference/split rows only inside a new frozen candidate-profile build, generate matched decoys "
            "and trajectories/caches, then rerun guarded 100k review. Do not mutate the existing frozen current CSVs in place."
        ),
    }
    payload = {
        "packet_type": "gpcr_positive_coverage_materialization_manifest",
        "summary": summary,
        "reference_append_rows": reference_rows,
        "split_append_rows": split_rows,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "target_identity_feature_allowed": False,
            "threshold_relaxation_allowed": False,
            "append_manifest_only_not_accuracy_evidence": True,
        },
    }
    return payload, reference_rows, split_rows


def _render_md(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# GPCR Positive Coverage Materialization Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- reference_append_row_count: `{s['reference_append_row_count']}`",
        f"- split_append_row_count: `{s['split_append_row_count']}`",
        f"- projected_positive_count_after_append: `{s['projected_positive_count_after_append']}`",
        f"- claim_promotion_allowed: `{str(s['claim_promotion_allowed']).lower()}`",
        "",
        "## Reference Append Rows",
        "",
        "| Target | Ligand | dG kcal/mol | UniProt | Structure | PubChem |",
        "|---|---|---:|---|---|---|",
    ]
    for row in payload["reference_append_rows"]:
        lines.append(
            f"| `{row['target']}` | `{row['ligand_id']}` | {row['reference_binding_kcal_mol']} | "
            f"`{row['uniprot_accession']}` | `{row['structure_source_priority']}:{row['rcsb_first_hit']}` | "
            f"`{row['pubchem_cid']}` |"
        )
    lines.extend(["", "## Next Required Step", "", s["next_required_step"], ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR coverage expansion append manifest rows.")
    parser.add_argument("--packet-json", default=DEFAULT_PACKET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--reference-append-csv", default=DEFAULT_REFERENCE_APPEND_CSV)
    parser.add_argument("--splits-append-csv", default=DEFAULT_SPLITS_APPEND_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload, reference_rows, split_rows = build_manifest(packet_json=args.packet_json)
    _write_json(args.out_json, payload)
    _write_csv(args.reference_append_csv, reference_rows)
    _write_csv(args.splits_append_csv, split_rows)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
