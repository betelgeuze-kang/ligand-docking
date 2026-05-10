from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_positive_coverage_candidate_profile_plan as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _base_reference_rows() -> list[dict[str, object]]:
    return [
        {
            "target": "ADRB2_GPCR_BLIND",
            "ligand_id": "carazolol",
            "reference_binding_kcal_mol": -10.0,
            "is_binder": 1,
            "source": "base",
            "source_url": "",
            "row_classification": "base_profile_row",
        },
        {
            "target": "DRD2_GPCR_BLIND",
            "ligand_id": "spiperone",
            "reference_binding_kcal_mol": -11.0,
            "is_binder": 1,
            "source": "base",
            "source_url": "",
            "row_classification": "frozen_non_adrb2_gpcr_candidate",
        },
    ]


def _base_split_rows() -> list[dict[str, object]]:
    return [
        {"target": "ADRB2_GPCR_BLIND", "ligand_id": "carazolol", "role": "far_ood_eval"},
        {"target": "DRD2_GPCR_BLIND", "ligand_id": "spiperone", "role": "far_ood_eval"},
    ]


def _append_reference_rows() -> list[dict[str, object]]:
    return [
        {
            "target": "CHEMBL234_DRD3_HUMAN",
            "ligand_id": "CHEMBL5841759",
            "reference_binding_kcal_mol": -14.898,
            "is_binder": 1,
            "source": "ChEMBL activity 28708679 Ki pChEMBL 10.92",
            "source_url": "https://example.invalid/activity/28708679",
            "row_classification": "coverage_expansion_non_adrb2_gpcr_positive_candidate",
            "canonical_smiles": "CCN",
            "uniprot_accession": "P35462",
            "structure_source_priority": "rcsb_experimental_first",
            "rcsb_first_hit": "3PBL",
            "alphafold_model_count": 2,
            "pubchem_cid": "",
        }
    ]


def _append_split_rows() -> list[dict[str, object]]:
    return [
        {
            "target": "CHEMBL234_DRD3_HUMAN",
            "ligand_id": "CHEMBL5841759",
            "split_id": "gpcr_positive_coverage_expansion_v1",
            "role": "far_ood_eval",
            "leakage_policy": "do_not_fit_or_calibrate",
            "row_classification": "coverage_expansion_non_adrb2_gpcr_positive_candidate",
            "materialization_state": "reference_and_split_ready_decoys_and_trajectories_pending",
        }
    ]


def test_build_plan_projects_append_rows_without_mutating_base(tmp_path: Path) -> None:
    base_ref = tmp_path / "base_reference.csv"
    base_splits = tmp_path / "base_splits.csv"
    append_ref = tmp_path / "append_reference.csv"
    append_splits = tmp_path / "append_splits.csv"
    out_dir = tmp_path / "out"
    _write_csv(base_ref, _base_reference_rows())
    _write_csv(base_splits, _base_split_rows())
    _write_csv(append_ref, _append_reference_rows())
    _write_csv(append_splits, _append_split_rows())

    payload = mod.build_plan(
        base_reference_csv=base_ref,
        base_splits_csv=base_splits,
        append_reference_csv=append_ref,
        append_splits_csv=append_splits,
        out_dir=out_dir,
        generated_at_local="2026-05-10T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "gpcr_positive_coverage_candidate_profile_build_plan_ready"
    assert summary["base_reference_row_count"] == 2
    assert summary["append_reference_row_count"] == 1
    assert summary["projected_reference_row_count"] == 3
    assert summary["projected_positive_count"] == 3
    assert summary["existing_frozen_current_mutated"] is False
    assert payload["quality_gates"]["append_leakage_policy_locked"] is True
    projected_rows = _read_csv(out_dir / "candidate_reference.csv")
    assert [row["build_row_origin"] for row in projected_rows] == [
        "base_frozen_candidate_profile_support_current",
        "base_frozen_candidate_profile_support_current",
        "gpcr_positive_coverage_append_v1",
    ]
    assert (out_dir / "build_plan.md").read_text(encoding="utf-8").startswith(
        "# GPCR Positive Coverage Candidate Profile Build Plan"
    )


def test_build_plan_blocks_duplicate_append_pair(tmp_path: Path) -> None:
    base_ref = tmp_path / "base_reference.csv"
    base_splits = tmp_path / "base_splits.csv"
    append_ref = tmp_path / "append_reference.csv"
    append_splits = tmp_path / "append_splits.csv"
    out_dir = tmp_path / "out"
    _write_csv(base_ref, _base_reference_rows())
    _write_csv(base_splits, _base_split_rows())
    duplicate_ref = _append_reference_rows()
    duplicate_ref[0]["target"] = "DRD2_GPCR_BLIND"
    duplicate_ref[0]["ligand_id"] = "spiperone"
    duplicate_split = _append_split_rows()
    duplicate_split[0]["target"] = "DRD2_GPCR_BLIND"
    duplicate_split[0]["ligand_id"] = "spiperone"
    _write_csv(append_ref, duplicate_ref)
    _write_csv(append_splits, duplicate_split)

    payload = mod.build_plan(
        base_reference_csv=base_ref,
        base_splits_csv=base_splits,
        append_reference_csv=append_ref,
        append_splits_csv=append_splits,
        out_dir=out_dir,
    )

    assert payload["summary"]["status"] == "blocked_gpcr_positive_coverage_candidate_profile_build_plan"
    assert "append_reference:already_in_base_reference:DRD2_GPCR_BLIND:spiperone" in payload["blockers"]
    assert "append_splits:already_in_base_splits:DRD2_GPCR_BLIND:spiperone" in payload["blockers"]


def test_cli_writes_build_plan_artifacts(tmp_path: Path) -> None:
    base_ref = tmp_path / "base_reference.csv"
    base_splits = tmp_path / "base_splits.csv"
    append_ref = tmp_path / "append_reference.csv"
    append_splits = tmp_path / "append_splits.csv"
    out_dir = tmp_path / "out"
    _write_csv(base_ref, _base_reference_rows())
    _write_csv(base_splits, _base_split_rows())
    _write_csv(append_ref, _append_reference_rows())
    _write_csv(append_splits, _append_split_rows())

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_positive_coverage_candidate_profile_plan.py"),
            "--base-reference-csv",
            str(base_ref),
            "--base-splits-csv",
            str(base_splits),
            "--append-reference-csv",
            str(append_ref),
            "--append-splits-csv",
            str(append_splits),
            "--out-dir",
            str(out_dir),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((out_dir / "build_plan.json").read_text(encoding="utf-8"))
    assert payload["packet_type"] == "gpcr_positive_coverage_candidate_profile_build_plan"
    assert "CHEMBL234_DRD3_HUMAN" in (out_dir / "candidate_reference.csv").read_text(encoding="utf-8")
    assert "do_not_fit_or_calibrate" in (out_dir / "candidate_splits.csv").read_text(encoding="utf-8")
