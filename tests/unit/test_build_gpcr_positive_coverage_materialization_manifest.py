from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_positive_coverage_materialization_manifest as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _packet_payload() -> dict:
    return {
        "rows": [
            {
                "target": "CHEMBL234_DRD3_HUMAN",
                "candidate_ligand_id": "CHEMBL5841759",
                "canonical_smiles": "CCN",
                "pchembl_value": 10.0,
                "chembl_activity_id": 123,
                "standard_type": "Ki",
                "uniprot_accession": "P35462",
                "structure_source_priority": "rcsb_experimental_first",
                "rcsb_first_hit": "3PBL",
                "alphafold_model_count": 1,
                "pubchem_cid": 555,
                "inclusion_decision": "ready_for_frozen_pipeline_materialization",
            },
            {
                "target": "hold",
                "candidate_ligand_id": "hold_ligand",
                "pchembl_value": 9.0,
                "inclusion_decision": "hold_until_activity_smiles_target_or_structure_complete",
            },
        ]
    }


def test_build_manifest_writes_reference_and_split_append_rows(tmp_path: Path) -> None:
    packet = tmp_path / "packet.json"
    _write_json(packet, _packet_payload())

    payload, reference_rows, split_rows = mod.build_manifest(
        packet_json=packet,
        generated_at_local="2026-05-09T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "gpcr_positive_coverage_materialization_manifest_ready"
    assert summary["reference_append_row_count"] == 1
    assert summary["split_append_row_count"] == 1
    assert summary["projected_positive_count_after_append"] == 4
    assert summary["claim_promotion_allowed"] is False
    assert reference_rows[0]["target"] == "CHEMBL234_DRD3_HUMAN"
    assert reference_rows[0]["reference_binding_kcal_mol"] == -13.642
    assert reference_rows[0]["row_classification"] == "coverage_expansion_non_adrb2_gpcr_positive_candidate"
    assert split_rows[0]["role"] == "far_ood_eval"
    assert split_rows[0]["leakage_policy"] == "do_not_fit_or_calibrate"


def test_cli_writes_materialization_manifest_artifacts(tmp_path: Path) -> None:
    packet = tmp_path / "packet.json"
    out_json = tmp_path / "manifest.json"
    out_md = tmp_path / "manifest.md"
    ref_csv = tmp_path / "reference.csv"
    split_csv = tmp_path / "splits.csv"
    _write_json(packet, _packet_payload())

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_positive_coverage_materialization_manifest.py"),
            "--packet-json",
            str(packet),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--reference-append-csv",
            str(ref_csv),
            "--splits-append-csv",
            str(split_csv),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["packet_type"] == "gpcr_positive_coverage_materialization_manifest"
    assert "GPCR Positive Coverage Materialization Manifest" in out_md.read_text(encoding="utf-8")
    assert "CHEMBL234_DRD3_HUMAN" in ref_csv.read_text(encoding="utf-8")
    assert "do_not_fit_or_calibrate" in split_csv.read_text(encoding="utf-8")
