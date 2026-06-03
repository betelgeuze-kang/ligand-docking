from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product.docking_request import build_docking_job_record, persist_docking_job_record, validate_docking_request


def test_docking_request_accepts_restricted_scope_but_keeps_execution_disabled() -> None:
    record = build_docking_job_record(
        {
            "request_type": "structure_analysis_ligand_docking",
            "family": "gpcr",
            "target_id": "ADRB2",
            "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
            "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
        },
        job_id="job_001",
    )

    assert record["status"] == "accepted_fail_closed"
    assert record["validation_status"] == "pass"
    assert record["family"] == "gpcr"
    assert record["structure_source_kind"] == "pdb_content"
    assert record["ligand_count"] == 1
    assert record["structure_analysis_status"] == "structure_analysis_ready"
    assert record["structure_atom_count"] == 1
    assert record["structure_chain_count"] == 1
    assert record["execution_enabled"] is False
    assert record["docking_results_emitted"] is False
    assert record["external_state_mutated"] is False


def test_docking_request_blocks_scope_widening_and_missing_ligand_source() -> None:
    validation = validate_docking_request(
        {
            "family": "transporter",
            "target_id": "AQP1",
            "pdb_id": "1J4N",
            "ligands": [{"ligand_id": "lig_1"}],
        }
    )
    codes = {blocker["code"] for blocker in validation["blockers"]}

    assert validation["status"] == "fail"
    assert "scope_family_not_delivery_ready" in codes
    assert "ligand_source_missing" in codes


def test_docking_request_blocks_duplicate_ligands_and_multiple_structure_sources() -> None:
    validation = validate_docking_request(
        {
            "family": "kinase",
            "target_id": "ABL1",
            "pdb_id": "2HYY",
            "pdb_path": "local.pdb",
            "ligands": [{"ligand_id": "dup", "smiles": "CCO"}, {"ligand_id": "dup", "smiles": "CCC"}],
        }
    )
    codes = {blocker["code"] for blocker in validation["blockers"]}

    assert validation["status"] == "fail"
    assert "multiple_structure_sources" in codes
    assert "duplicate_ligand_ids" in codes


def test_persist_docking_job_record_writes_local_ledger(tmp_path: Path) -> None:
    record = build_docking_job_record(
        {
            "family": "ion_channel",
            "target_id": "TRPV1",
            "mmcif_path": "trpv1.cif",
            "ligands": [{"ligand_id": "cap", "compound_id": "CHEMBL123"}],
        },
        job_id="job_ledger",
    )

    out_path = persist_docking_job_record(record, tmp_path)
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert payload["job_id"] == "job_ledger"
    assert payload["status"] == "accepted_fail_closed"
    assert payload["heavy_artifact_policy"] == "manifest_first_externalize_before_delete"
