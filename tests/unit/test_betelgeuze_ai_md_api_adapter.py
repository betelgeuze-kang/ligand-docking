from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_ai_md.contracts import (
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
    EvidenceBundle,
    TopologyValidityReport,
    maybe_write_runner_native_evidence_bundle,
)
from betelgeuze_ai_md.contracts.api_adapter import build_api_evidence_bundle, write_api_evidence_bundle
from betelgeuze_engine.product.selection_score_authority import SelectionScoreAuthority


def _manifest(result_file: Path) -> dict:
    return {
        "job_id": "job_api_contract",
        "status": "completed",
        "request_sha256": "i" * 64,
        "result_file": str(result_file),
        "result_file_sha256": "r" * 64,
        "claim_scope": "product_ligand_htvs_backmapping",
        "topology_fidelity": "placeholder_alanine",
        "accuracy_claim_grade": "restricted-local-delivery",
        "signature_key_id": "unit-test-key",
    }


def test_build_api_evidence_bundle_is_review_only_even_with_structured_result(tmp_path: Path) -> None:
    result_file = tmp_path / "runner_result.json"
    result_payload = {
        "model_hash": "m" * 64,
        "ranked_shortlist": [{"ligand_id": "lig1", "rank": 1, "score": -7.2}],
        "trajectory_summary": {
            "frame_count": 5,
            "energy_trace": [0.2, -0.1],
            "contact_trace": [0.3, 0.6],
            "stability_score": 0.72,
            "mean_min_distance_A": 2.8,
        },
        "backmapped_poses": [
            {
                "pose_id": "pose_001",
                "structure_path": "runs/job_api_contract/pose_001.sdf",
                "structure_sha256": "p" * 64,
                "chemical_validity_summary": {"status": "pass"},
                "backmap_confidence": 0.85,
            }
        ],
        "interaction_report": {
            "interactions": [
                {
                    "interaction_id": "hbond_001",
                    "interaction_type": "hbond",
                    "partners": ["SER:OG", "lig1:O1"],
                    "distance": 2.9,
                    "angle": 155.0,
                    "occupancy": 0.62,
                    "confidence": 0.76,
                }
            ],
            "interaction_confidence": 0.7,
        },
        "topology_report": {"status": "pass", "topology_fidelity": "placeholder_alanine"},
        "ai_residual_report": {
            "residual_mode": "shadow",
            "correction_applied": False,
            "uncertainty": 0.4,
            "abstained": True,
            "residual_delta": 1.2,
            "bounded_residual_delta": 0.45,
            "score_max_delta": 1.0,
            "guard": 0.5,
            "active_score_col": "binding_score_composite_v7_residual_active",
            "base_score_col": "binding_score_composite_v7",
            "ranking_changed": True,
            "guard_components": {"topology": 1.0, "domain": 0.5, "calibration": 1.0},
        },
    }
    result_file.write_text(json.dumps(result_payload, sort_keys=True) + "\n", encoding="utf-8")

    bundle = build_api_evidence_bundle(
        job_id="job_api_contract",
        request={"target_name": "ADRB2", "runner_profile_id": "smoke"},
        result_manifest=_manifest(result_file),
        result_payload=result_payload,
        runner_execution={
            "runner_script": "tools/run_ligand_topk_delivery.py",
            "profile_readiness": {"runner_script_sha256": "e" * 64},
        },
        status_payload={"status": "completed"},
    )

    assert bundle.project_id == "ADRB2"
    assert bundle.verdict.claim_safe is False
    assert bundle.verdict.verdict_label == "api_completed_evidence_review_only"
    assert bundle.failure_flags == ["delivery_bundle_validation_not_attached"]
    assert bundle.source_hashes["input_hash"] == "i" * 64
    assert bundle.source_hashes["model_hash"] == "m" * 64
    assert bundle.source_hashes["executable_hash"] == "e" * 64
    assert bundle.backmapped_poses[0].pose_id == "pose_001"
    assert bundle.backmapped_poses[0].chemical_validity_summary["status"] == "pass"
    assert bundle.backmapped_poses[0].chemical_validity_summary["check_id"] == "onsps_4bead_backmap"
    assert isinstance(bundle.topology_report, TopologyValidityReport)
    assert bundle.topology_report.status == "pass"
    assert bundle.topology_report.topology_fidelity == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
    assert bundle.ai_residual_report.bounded_residual_delta == 0.45
    assert bundle.ai_residual_report.active_score_col == "binding_score_composite_v7_residual_active"
    assert bundle.ai_residual_report.ranking_changed is True
    assert bundle.ai_residual_report.guard_components["domain"] == 0.5
    assert len(bundle.fingerprint()) == 64


def test_api_adapter_preserves_explicit_zero_ai_residual_deltas(tmp_path: Path) -> None:
    result_file = tmp_path / "runner_result.json"
    result_payload = {
        "ai_residual_report": {
            "residual_delta": 0.0,
            "score_delta": 0.9,
            "bounded_residual_delta": 0.0,
            "applied_delta_score": 0.8,
            "max_delta": 1.0,
            "guard": 1.0,
        }
    }

    bundle = build_api_evidence_bundle(
        job_id="job_ai_residual_zero",
        request={"target_name": "ADRB2"},
        result_manifest=_manifest(result_file),
        result_payload=result_payload,
        runner_execution={},
        status_payload={"status": "completed"},
    )

    assert bundle.ai_residual_report.residual_delta == 0.0
    assert bundle.ai_residual_report.bounded_residual_delta == 0.0


def test_write_api_evidence_bundle_falls_back_for_unstructured_runner_result(tmp_path: Path) -> None:
    result_file = tmp_path / "result.pdb"
    result_file.write_text("ATOM\n", encoding="utf-8")
    bundle_path = tmp_path / "evidence_bundle.json"

    bundle = write_api_evidence_bundle(
        bundle_path,
        job_id="job_pdb_result",
        request={"target_name": "Chignolin"},
        result_manifest=_manifest(result_file),
        result_payload=None,
        runner_execution={},
        status_payload={"status": "completed"},
    )

    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert payload["bundle_schema_version"] == "ai_md_evidence_bundle_v1"
    assert bundle.verdict.claim_safe is False
    assert "backmapped_pose_contract_missing" in bundle.failure_flags
    assert "interaction_report_contract_missing" in bundle.failure_flags
    assert "topology_report_contract_missing" in bundle.failure_flags
    assert bundle.backmapped_poses[0].pose_id == "runner_result_file"
    assert bundle.backmapped_poses[0].chemical_validity_summary["status"] == "not_assessed"
    assert "backmapping_empty_input" in bundle.backmapped_poses[0].chemical_validity_summary["claim_blockers"]
    assert bundle.interaction_report.claim_blockers == ["interaction_evidence_missing"]
    assert isinstance(bundle.topology_report, TopologyValidityReport)
    assert bundle.topology_report.status == "not_assessed"
    assert bundle.topology_report.topology_fidelity == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
    assert "topology_validity_not_assessed" in bundle.topology_report.claim_blockers
    payload_topology = payload["topology_report"]
    assert payload_topology["status"] == "not_assessed"
    assert payload_topology["topology_fidelity"] == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
    assert "topology_validity_not_assessed" in payload_topology["claim_blockers"]


def test_api_adapter_preserves_structured_topology_validity_rows(tmp_path: Path) -> None:
    result_file = tmp_path / "runner_result.json"
    result_payload = {
        "topology_report": {
            "status": "pass",
            "topology_fidelity": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            "confidence": 0.81,
            "validity_rows": [{"check_id": "chain_break_scan", "status": "pass"}],
            "atom_count": 144,
            "notes": ["no chain breaks detected"],
        }
    }
    result_file.write_text(json.dumps(result_payload, sort_keys=True) + "\n", encoding="utf-8")

    bundle = build_api_evidence_bundle(
        job_id="job_topology_structured",
        request={"target_name": "ADRB2"},
        result_manifest=_manifest(result_file),
        result_payload=result_payload,
        runner_execution={},
        status_payload={"status": "completed"},
    )

    assert isinstance(bundle.topology_report, TopologyValidityReport)
    assert bundle.topology_report.status == "pass"
    assert bundle.topology_report.topology_fidelity == TOPOLOGY_FIDELITY_SEQUENCE_MAPPED
    assert bundle.topology_report.confidence == 0.81
    assert bundle.topology_report.validity_rows == [{"check_id": "chain_break_scan", "status": "pass"}]
    assert bundle.topology_report.metadata["atom_count"] == 144
    assert bundle.topology_report.notes == ["no chain breaks detected"]
    assert bundle.topology_report.claim_blockers == []
    assert bundle.verdict.claim_safe is False


def test_maybe_write_runner_native_evidence_bundle_writes_valid_review_only_bundle(tmp_path: Path) -> None:
    request_file = tmp_path / "job_runner_native" / "request.json"
    request_file.parent.mkdir(parents=True, exist_ok=True)
    request_payload = {
        "job_id": "job_runner_native",
        "target_name": "ADRB2",
        "runner_profile_id": "backmapping_scoring.production",
    }
    request_file.write_text(json.dumps(request_payload, sort_keys=True) + "\n", encoding="utf-8")

    result_file = tmp_path / "runner_result.json"
    result_payload = {
        "model_hash": "m" * 64,
        "ranked_shortlist": [{"ligand_id": "lig1", "rank": 1, "score": -7.2}],
        "score": {
            "refine_element_model": "typed_pairwise",
            "refine_element_fallback_used": False,
            "refine_protein_element_source": "sequence_residue_element_proxy",
            "refine_ligand_element_source": "rdkit_atom_elements_projected_to_model_coords",
        },
    }
    result_file.write_text(json.dumps(result_payload, sort_keys=True) + "\n", encoding="utf-8")
    bundle_file = tmp_path / "evidence_bundle.json"
    selection_score_authority = SelectionScoreAuthority.create(
        score_column="binding_score_composite_v7",
        score_direction="ascending",
    ).to_dict()

    bundle = maybe_write_runner_native_evidence_bundle(
        bundle_file,
        request_json_path=request_file,
        result_file=result_file,
        result_payload=result_payload,
        runner_script="tools/run_ligand_backmapping_scoring.py",
        runner_metadata={
            "runner_kind": "unit",
            "selection_score_authority": selection_score_authority,
        },
    )

    payload = json.loads(bundle_file.read_text(encoding="utf-8"))
    reloaded = EvidenceBundle(**payload)
    assert bundle is not None
    assert payload["bundle_schema_version"] == "ai_md_evidence_bundle_v1"
    assert reloaded.fingerprint() == bundle.fingerprint()
    assert bundle.project_id == "ADRB2"
    assert bundle.verdict.claim_safe is False
    assert "delivery_bundle_validation_not_attached" in bundle.failure_flags
    assert bundle.source_hashes["input_hash"]
    assert bundle.source_hashes["model_hash"] == "m" * 64
    assert bundle.source_hashes["executable_hash"]
    assert (
        payload["result_manifest"]["runner_metadata"]["selection_score_authority"]
        == selection_score_authority
    )
    assert (
        payload["result_manifest"]["refine_element_summary"]["refine_element_model"]
        == "typed_pairwise"
    )
    assert (
        payload["result_manifest"]["refine_element_summary"]["refine_ligand_element_source"]
        == "rdkit_atom_elements_projected_to_model_coords"
    )


def test_api_config_hash_binds_selection_score_authority(tmp_path: Path) -> None:
    result_file = tmp_path / "runner_result.json"
    result_file.write_text("{}\n", encoding="utf-8")
    manifest_without = _manifest(result_file)
    manifest_with = {
        **manifest_without,
        "runner_metadata": {
            "selection_score_authority": SelectionScoreAuthority.create(
                score_column="binding_score_composite_v7",
                score_direction="ascending",
            ).to_dict()
        },
    }
    kwargs = {
        "job_id": "job_authority_hash",
        "request": {"target_name": "ADRB2", "runner_profile_id": "smoke"},
        "result_payload": {},
        "runner_execution": {},
        "status_payload": {"status": "completed"},
    }

    without = build_api_evidence_bundle(result_manifest=manifest_without, **kwargs)
    with_authority = build_api_evidence_bundle(result_manifest=manifest_with, **kwargs)

    assert without.source_hashes["config_hash"] != with_authority.source_hashes["config_hash"]


def test_maybe_write_runner_native_evidence_bundle_requires_result_file(tmp_path: Path) -> None:
    bundle_file = tmp_path / "evidence_bundle.json"
    missing_result = tmp_path / "missing.json"

    try:
        maybe_write_runner_native_evidence_bundle(
            bundle_file,
            request={"job_id": "job_missing_result"},
            result_file=missing_result,
        )
    except FileNotFoundError as exc:
        assert str(missing_result) in str(exc)
    else:
        raise AssertionError("missing result_file should fail native EvidenceBundle emission")
    assert not bundle_file.exists()
