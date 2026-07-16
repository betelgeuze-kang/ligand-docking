from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from api.product_docking import DockingJobRequest, _model_to_dict, _scientific_input_summary
from betelgeuze_product.scientific_input_provenance import (
    build_scientific_input_provenance,
    verify_scientific_input_provenance,
)


PDB_TEXT = "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n"


def _manifest(profile_id: str = "ligand_htvs_pipeline_default") -> dict:
    return {
        "job_id": "job-input-receipt",
        "target_id": "ADRB2",
        "family": "gpcr",
        "runner_profile_id": profile_id,
        "execution_mode": "smoke",
        "customer_submission_allowed": False,
        "synthetic_input_allowed": True,
        "production_claim_allowed": False,
        "customer_pose_emission_allowed": False,
    }


def _request_sha(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _ready_payload() -> dict:
    return {
        "request_type": "structure_analysis_ligand_docking",
        "family": "gpcr",
        "target_id": "ADRB2",
        "pdb_content": PDB_TEXT,
        "ligands": [{"ligand_id": "lig-1", "smiles": "CCO"}],
        "pocket_residue_indices": [9, 3, 5],
    }


def test_inline_inputs_and_explicit_pocket_build_redacted_deterministic_receipt(tmp_path: Path) -> None:
    payload = _ready_payload()
    manifest = _manifest()
    receipt = build_scientific_input_provenance(
        payload,
        request_sha256=_request_sha(payload),
        dispatch_manifest=manifest,
        root=tmp_path,
    )
    repeated = build_scientific_input_provenance(
        payload,
        request_sha256=_request_sha(payload),
        dispatch_manifest=manifest,
        root=tmp_path,
    )

    assert receipt == repeated
    assert receipt["content_identity_ready"] is True
    assert receipt["execution_input_ready"] is True
    assert receipt["blockers"] == []
    assert receipt["structure"]["source_kind"] == "pdb_content"
    assert receipt["structure"]["source_sha256"] == hashlib.sha256(PDB_TEXT.encode()).hexdigest()
    assert receipt["ligands"][0]["source_kind"] == "smiles"
    assert receipt["ligands"][0]["source_sha256"] == hashlib.sha256(b"CCO").hexdigest()
    assert receipt["ligands"][0]["materialization_supported"] is True
    assert receipt["pocket"]["explicit"] is True
    assert receipt["pocket"]["definition_kind"] == "residue_indices"
    assert receipt["scientifically_validated"] is False
    assert receipt["benchmark_validated"] is False
    assert receipt["customer_execution_enabled"] is False
    assert receipt["claim_safe"] is False

    serialized = json.dumps(receipt, sort_keys=True)
    assert PDB_TEXT.strip() not in serialized
    assert "CCO" not in serialized
    assert "[9, 3, 5]" not in serialized

    assert verify_scientific_input_provenance(
        receipt,
        request_sha256=_request_sha(payload),
        dispatch_manifest=manifest,
    ) == (True, "ready")


def test_missing_explicit_pocket_is_recorded_without_rejecting_input_identity(tmp_path: Path) -> None:
    payload = _ready_payload()
    payload.pop("pocket_residue_indices")
    receipt = build_scientific_input_provenance(
        payload,
        request_sha256=_request_sha(payload),
        dispatch_manifest=_manifest(),
        root=tmp_path,
    )

    assert receipt["structure"]["content_bytes_verified"] is True
    assert receipt["ligands"][0]["content_bytes_verified"] is True
    assert receipt["content_identity_ready"] is False
    assert receipt["execution_input_ready"] is False
    assert receipt["pocket"]["explicit"] is False
    assert "explicit_pocket_definition_missing" in receipt["blockers"]
    assert verify_scientific_input_provenance(
        receipt,
        request_sha256=_request_sha(payload),
        dispatch_manifest=_manifest(),
    ) == (False, "scientific_input_provenance_not_ready")


def test_identifier_only_sources_do_not_masquerade_as_verified_bytes(tmp_path: Path) -> None:
    payload = {
        "family": "gpcr",
        "target_id": "ADRB2",
        "pdb_id": "2RH1",
        "ligands": [{"ligand_id": "lig-1", "compound_id": "CHEMBL123"}],
        "pocket_center": [1.0, 2.0, 3.0],
        "pocket_radius_a": 8.0,
    }
    receipt = build_scientific_input_provenance(
        payload,
        request_sha256=_request_sha(payload),
        dispatch_manifest=_manifest(),
        root=tmp_path,
    )

    assert receipt["structure"]["content_bytes_verified"] is False
    assert receipt["ligands"][0]["content_bytes_verified"] is False
    assert receipt["ligands"][0]["materialization_supported"] is False
    assert receipt["execution_input_ready"] is False
    assert any("scientific_input_source_bytes_unavailable" in reason for reason in receipt["blockers"])
    assert any("ligand_source_not_materializable_by_current_runner" in reason for reason in receipt["blockers"])


def test_path_source_rejects_symlink_without_disclosing_path(tmp_path: Path) -> None:
    real = tmp_path / "real.pdb"
    real.write_text(PDB_TEXT, encoding="utf-8")
    link = tmp_path / "link.pdb"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlinks unavailable")

    payload = {
        "family": "gpcr",
        "target_id": "ADRB2",
        "pdb_path": str(link),
        "ligands": [{"ligand_id": "lig-1", "smiles": "CCO"}],
        "pocket_center": [1.0, 2.0, 3.0],
        "pocket_box_size": [20.0, 20.0, 20.0],
    }
    receipt = build_scientific_input_provenance(
        payload,
        request_sha256=_request_sha(payload),
        dispatch_manifest=_manifest(),
        root=tmp_path,
    )

    assert receipt["structure"]["content_bytes_verified"] is False
    assert "scientific_input_file_unavailable_or_unsafe" in receipt["blockers"]
    assert str(link) not in json.dumps(receipt, sort_keys=True)


def test_receipt_tamper_and_dispatch_rebinding_are_rejected(tmp_path: Path) -> None:
    payload = _ready_payload()
    receipt = build_scientific_input_provenance(
        payload,
        request_sha256=_request_sha(payload),
        dispatch_manifest=_manifest(),
        root=tmp_path,
    )
    tampered = json.loads(json.dumps(receipt))
    tampered["pocket"]["definition_kind"] = "center_box"

    assert verify_scientific_input_provenance(
        tampered,
        request_sha256=_request_sha(payload),
        dispatch_manifest=_manifest(),
    ) == (False, "scientific_input_provenance_digest_mismatch")
    assert verify_scientific_input_provenance(
        receipt,
        request_sha256=_request_sha(payload),
        dispatch_manifest=_manifest("backmapping_scoring.production"),
    ) == (False, "scientific_input_provenance_dispatch_mismatch")


def test_api_request_exposes_explicit_pocket_fields_and_summary_is_redacted(tmp_path: Path) -> None:
    model = DockingJobRequest(
        family="gpcr",
        target_id="ADRB2",
        pdb_content=PDB_TEXT,
        ligands=[{"ligand_id": "lig-1", "smiles": "CCO"}],
        pocket_center=[1.0, 2.0, 3.0],
        pocket_box_size=[20.0, 18.0, 16.0],
    )
    payload = _model_to_dict(model)
    receipt = build_scientific_input_provenance(
        payload,
        request_sha256=_request_sha(payload),
        dispatch_manifest=_manifest(),
        root=tmp_path,
    )
    summary = _scientific_input_summary(
        {
            "scientific_input_provenance": receipt,
            "private_payload_stored": True,
        }
    )

    assert payload["pocket_center"] == [1.0, 2.0, 3.0]
    assert payload["pocket_box_size"] == [20.0, 18.0, 16.0]
    assert summary == {
        "schema_version": "scientific_input_provenance_v1",
        "receipt_sha256": receipt["receipt_sha256"],
        "content_identity_ready": True,
        "execution_input_ready": True,
        "explicit_pocket": True,
        "pocket_definition_kind": "center_box",
        "ligand_count": 1,
        "private_payload_stored": True,
        "blockers": [],
        "claim_safe": False,
    }
