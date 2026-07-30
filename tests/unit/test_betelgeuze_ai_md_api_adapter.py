from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
import numpy as np

from betelgeuze_ai_md.contracts import (
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
    EvidenceBundle,
    TopologyValidityReport,
    maybe_write_runner_native_evidence_bundle,
)
from betelgeuze_ai_md.contracts.api_adapter import build_api_evidence_bundle, write_api_evidence_bundle
from betelgeuze_ai_md.contracts.errors import ContractValidationError
from betelgeuze_ai_md.contracts.job_scoped_hbond import JobScopedHbondEvidence
from betelgeuze_ai_md.contracts.job_scoped_hbond import (
    build_job_scoped_hbond_evidence,
)
from betelgeuze_ai_md.contracts.serialization import sha256_payload
from betelgeuze_engine.product.selection_score_authority import SelectionScoreAuthority
from betelgeuze_engine.product.implementation_provenance import (
    build_implementation_source_manifest,
)
from betelgeuze_product.pocketmd_lite_contract import PocketMdAdmissionPolicy


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
    implementation = build_implementation_source_manifest()
    result_manifest = {
        **_manifest(result_file),
        "execution_request_sha256": "i" * 64,
        "runner_metadata": {
            "runner_kind": "ligand_topk_delivery",
            "implementation_source_manifest": implementation,
            "implementation_fingerprint_sha256": implementation[
                "manifest_sha256"
            ],
            "effective_runner_config": {"topk_global": 10},
        },
    }

    bundle = build_api_evidence_bundle(
        job_id="job_api_contract",
        request={"target_name": "ADRB2", "runner_profile_id": "smoke"},
        result_manifest=result_manifest,
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
    assert set(bundle.failure_flags) == {
        "delivery_bundle_validation_not_attached",
        "job_scoped_hbond_evidence_missing",
    }
    assert bundle.source_hashes["input_hash"] == "i" * 64
    assert bundle.source_hashes["model_hash"] == "m" * 64
    assert bundle.source_hashes["executable_hash"] == implementation[
        "manifest_sha256"
    ]
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
    implementation = build_implementation_source_manifest()

    bundle = maybe_write_runner_native_evidence_bundle(
        bundle_file,
        request_json_path=request_file,
        result_file=result_file,
        result_payload=result_payload,
        runner_script="tools/run_ligand_backmapping_scoring.py",
        runner_script_sha256=implementation["manifest_sha256"],
        runner_metadata={
            "runner_kind": "ligand_backmapping_scoring",
            "selection_score_authority": selection_score_authority,
            "implementation_source_manifest": implementation,
            "implementation_fingerprint_sha256": implementation[
                "manifest_sha256"
            ],
            "effective_runner_config": {"score_only": False},
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


def test_api_config_hash_binds_selection_and_pocketmd_policies(tmp_path: Path) -> None:
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
    manifest_with_pocketmd = {
        **manifest_with,
        "runner_metadata": {
            **manifest_with["runner_metadata"],
            "pocketmd_admission_policy": PocketMdAdmissionPolicy.create().to_dict(),
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
    with_pocketmd = build_api_evidence_bundle(
        result_manifest=manifest_with_pocketmd,
        **kwargs,
    )
    implementation = build_implementation_source_manifest()
    manifest_with_implementation = {
        **manifest_with_pocketmd,
        "runner_metadata": {
            **manifest_with_pocketmd["runner_metadata"],
            "implementation_source_manifest": implementation,
            "implementation_fingerprint_sha256": implementation[
                "manifest_sha256"
            ],
        },
    }
    with_implementation = build_api_evidence_bundle(
        result_manifest=manifest_with_implementation,
        **kwargs,
    )

    assert without.source_hashes["config_hash"] != with_authority.source_hashes["config_hash"]
    assert with_authority.source_hashes["config_hash"] != with_pocketmd.source_hashes["config_hash"]
    assert with_pocketmd.source_hashes["config_hash"] != with_implementation.source_hashes["config_hash"]
    assert with_implementation.source_hashes["executable_hash"] == implementation[
        "manifest_sha256"
    ]

    tampered = copy.deepcopy(manifest_with_implementation)
    tampered["runner_metadata"]["implementation_source_manifest"]["files"][0][
        "sha256"
    ] = "0" * 64
    with pytest.raises(ValueError, match="manifest_sha256 mismatch"):
        build_api_evidence_bundle(result_manifest=tampered, **kwargs)

    stale_but_internally_consistent = copy.deepcopy(
        manifest_with_implementation
    )
    stale_manifest = stale_but_internally_consistent["runner_metadata"][
        "implementation_source_manifest"
    ]
    stale_manifest["files"][0]["sha256"] = "0" * 64
    unsigned = {
        key: stale_manifest[key]
        for key in ("schema_version", "algorithm", "files")
    }
    stale_manifest["manifest_sha256"] = hashlib.sha256(
        json.dumps(
            unsigned,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    stale_but_internally_consistent["runner_metadata"][
        "implementation_fingerprint_sha256"
    ] = stale_manifest["manifest_sha256"]
    with pytest.raises(ValueError, match="does not match current source tree"):
        build_api_evidence_bundle(
            result_manifest=stale_but_internally_consistent,
            **kwargs,
        )


def test_api_config_hash_binds_effective_runner_config(tmp_path: Path) -> None:
    result_file = tmp_path / "runner_result.json"
    result_file.write_text("{}\n", encoding="utf-8")
    implementation = build_implementation_source_manifest()
    base_manifest = {
        **_manifest(result_file),
        "runner_metadata": {
            "implementation_source_manifest": implementation,
            "implementation_fingerprint_sha256": implementation[
                "manifest_sha256"
            ],
            "effective_runner_config": {"topk_global": 8},
        },
    }
    kwargs = {
        "job_id": "job_effective_config_hash",
        "request": {"target_name": "ADRB2"},
        "result_payload": {},
        "runner_execution": {},
        "status_payload": {"status": "completed"},
    }

    first = build_api_evidence_bundle(
        result_manifest=base_manifest,
        **kwargs,
    )
    changed_manifest = copy.deepcopy(base_manifest)
    changed_manifest["runner_metadata"]["effective_runner_config"][
        "topk_global"
    ] = 16
    changed = build_api_evidence_bundle(
        result_manifest=changed_manifest,
        **kwargs,
    )

    assert first.source_hashes["config_hash"] != changed.source_hashes[
        "config_hash"
    ]


def test_native_runner_rejects_thin_shim_hash_without_full_manifest(
    tmp_path: Path,
) -> None:
    result_file = tmp_path / "runner_result.json"
    result_file.write_text("{}\n", encoding="utf-8")
    result_manifest = {
        **_manifest(result_file),
        "runner_metadata": {
            "runner_kind": "ligand_topk_delivery",
            "effective_runner_config": {"topk_global": 8},
        },
    }

    with pytest.raises(
        ValueError,
        match="native runner implementation manifest is required",
    ):
        build_api_evidence_bundle(
            job_id="job_shim_only",
            request={"target_name": "ADRB2"},
            result_manifest=result_manifest,
            result_payload={},
            runner_execution={
                "runner_script": "tools/run_ligand_topk_delivery.py",
                "profile_readiness": {"runner_script_sha256": "e" * 64},
            },
            status_payload={"status": "completed"},
        )


def test_native_runner_rejects_same_basename_noncanonical_executable(
    tmp_path: Path,
) -> None:
    result_file = tmp_path / "runner_result.json"
    result_file.write_text("{}\n", encoding="utf-8")
    spoof_runner = tmp_path / "run_ligand_topk_delivery.py"
    spoof_runner.write_text(
        'raise RuntimeError("arbitrary executable")\n',
        encoding="utf-8",
    )
    implementation = build_implementation_source_manifest()
    result_manifest = {
        **_manifest(result_file),
        "runner_metadata": {
            "runner_kind": "ligand_topk_delivery",
            "implementation_source_manifest": implementation,
            "implementation_fingerprint_sha256": implementation[
                "manifest_sha256"
            ],
            "effective_runner_config": {"topk_global": 8},
        },
    }

    with pytest.raises(ValueError, match="executable path mismatch"):
        build_api_evidence_bundle(
            job_id="job_spoofed_native_runner",
            request={"target_name": "ADRB2"},
            result_manifest=result_manifest,
            result_payload={},
            runner_execution={"runner_script": str(spoof_runner)},
            status_payload={"status": "completed"},
        )


def test_htvs_runtime_config_is_local_content_bound(tmp_path: Path) -> None:
    result_file = tmp_path / "runner_result.json"
    result_file.write_text("{}\n", encoding="utf-8")
    config_path = Path("config/ligand_engine_production.json").resolve()
    resolved_config = json.loads(config_path.read_text(encoding="utf-8"))
    source_sha256 = hashlib.sha256(config_path.read_bytes()).hexdigest()
    resolved_config_sha256 = hashlib.sha256(
        json.dumps(
            resolved_config,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    implementation = build_implementation_source_manifest()
    result_manifest = {
        **_manifest(result_file),
        "runner_metadata": {
            "runner_kind": "ligand_htvs_pipeline",
            "implementation_source_manifest": implementation,
            "implementation_fingerprint_sha256": implementation[
                "manifest_sha256"
            ],
            "effective_runner_config": {"run_scope": "smoke"},
            "engine_refinement_config": {
                "schema_version": "ligand_engine_runtime_config_v1",
                "requested_path": "config/ligand_engine_production.json",
                "resolved_path": str(config_path),
                "source_sha256": source_sha256,
                "resolved_config": resolved_config,
                "resolved_config_sha256": resolved_config_sha256,
            },
        },
    }
    kwargs = {
        "job_id": "job_htvs_config",
        "request": {"target_name": "ADRB2"},
        "result_payload": {},
        "runner_execution": {
            "runner_script": "tools/run_ligand_htvs_pipeline.py"
        },
        "status_payload": {"status": "completed"},
    }

    bundle = build_api_evidence_bundle(
        result_manifest=result_manifest,
        **kwargs,
    )
    assert bundle.source_hashes["config_hash"]

    tampered = copy.deepcopy(result_manifest)
    tampered["runner_metadata"]["engine_refinement_config"][
        "source_sha256"
    ] = "0" * 64
    with pytest.raises(
        ValueError,
        match="engine configuration source hash mismatch",
    ):
        build_api_evidence_bundle(
            result_manifest=tampered,
            **kwargs,
        )

    fabricated_resolution = copy.deepcopy(result_manifest)
    fabricated_config = fabricated_resolution["runner_metadata"][
        "engine_refinement_config"
    ]["resolved_config"]
    fabricated_config["stage3b"]["pocketmd_max_per_job"] = 999
    fabricated_resolution["runner_metadata"]["engine_refinement_config"][
        "resolved_config_sha256"
    ] = hashlib.sha256(
        json.dumps(
            fabricated_config,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    with pytest.raises(
        ValueError,
        match="engine configuration content mismatch",
    ):
        build_api_evidence_bundle(
            result_manifest=fabricated_resolution,
            **kwargs,
        )


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


def test_native_bundle_rejects_request_job_id_conflicting_with_attempt_path(
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "job_attempt_owner" / ".attempts" / "attempt-000001-test"
    attempt_dir.mkdir(parents=True)
    request_file = attempt_dir / "request.json"
    request = {"job_id": "job_foreign", "target_name": "ADRB2"}
    request_file.write_text(json.dumps(request) + "\n", encoding="utf-8")
    result_file = attempt_dir / "runner_result.json"
    result_file.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="active attempt path"):
        maybe_write_runner_native_evidence_bundle(
            attempt_dir / "evidence_bundle.json",
            request_json_path=request_file,
            request=request,
            result_file=result_file,
        )


def test_backmapping_native_bundle_binds_full_hbond_evidence_to_durable_job(
    tmp_path: Path,
) -> None:
    job_id = "job_hbond_scoped"
    attempt_dir = tmp_path / job_id / ".attempts" / "attempt-000001-test"
    attempt_dir.mkdir(parents=True)
    request_file = attempt_dir / "request.json"
    request = {
        "target_name": "ADRB2",
        "runner_profile_id": "backmapping_scoring.production",
    }
    request_file.write_text(
        json.dumps(request, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    from betelgeuze_engine.product.runners.backmapping_scoring import (
        _flatten_hbond_evidence_for_runner,
    )

    hbond_evidence = _flatten_hbond_evidence_for_runner(
        smiles="CCO",
        protein_xyz=np.asarray(
            [[0.0, 0.0, 3.0], [1.6, 0.0, 3.0]],
            dtype=np.float32,
        ),
        ligand_xyz=np.asarray(
            [[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]],
            dtype=np.float32,
        ),
    )["hbond_evidence"]
    result_payload = {
        "hbond_evidence_summary": {
            "schema_version": "hbond_evidence_v1",
            "status": "pass",
            "evaluated_row_count": 1,
        },
        "topk": [
            {
                "queue_id": "ADRB2__lig1__rep0001",
                "target": "ADRB2",
                "ligand_id": "lig1",
                "ligand_smiles": "CCO",
                "hbond_evidence": hbond_evidence,
            }
        ],
    }
    result_file = attempt_dir / "runner_result.json"
    result_file.write_text(
        json.dumps(result_payload, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    implementation = build_implementation_source_manifest()
    bundle_file = attempt_dir / "evidence_bundle.json"

    bundle = maybe_write_runner_native_evidence_bundle(
        bundle_file,
        request_json_path=request_file,
        request=request,
        result_file=result_file,
        result_payload={
            **result_payload,
            "topk": [{**result_payload["topk"][0], "queue_id": "foreign_job_row"}],
        },
        runner_script="tools/run_ligand_backmapping_scoring.py",
        runner_metadata={
            "runner_kind": "ligand_backmapping_scoring",
            "selection_score_authority": SelectionScoreAuthority.create(
                score_column="binding_score_composite_v7",
                score_direction="ascending",
            ).to_dict(),
            "implementation_source_manifest": implementation,
            "implementation_fingerprint_sha256": implementation["manifest_sha256"],
            "effective_runner_config": {"score_only": True},
        },
    )

    assert bundle is not None
    payload = bundle.to_dict()
    scoped = payload["job_scoped_hbond_evidence"]
    request_sha256 = sha256_payload(request)
    assert bundle.bundle_id == f"api_{job_id}_evidence_bundle"
    assert bundle.result_manifest["job_id"] == job_id
    assert scoped["job_id"] == job_id
    assert scoped["admission_request_sha256"] == request_sha256
    assert scoped["execution_request_sha256"] == request_sha256
    assert scoped["result_file_sha256"] == bundle.result_manifest["result_file_sha256"]
    assert scoped["candidates"][0]["candidate_id"] == "ADRB2__lig1__rep0001"
    assert scoped["candidates"][0]["hbond_evidence"]["donor_acceptor_pairs"][0][
        "nearest_distance"
    ] > 0.0
    assert len(bundle.interaction_report.interactions) == hbond_evidence["site_count"]
    assert "interaction_report_contract_missing" not in bundle.failure_flags
    assert "job_scoped_hbond_evidence_missing" not in bundle.failure_flags

    replayed = JobScopedHbondEvidence.create(
        job_id="job_hbond_replay",
        admission_request_sha256=request_sha256,
        execution_request_sha256=request_sha256,
        result_file_sha256=scoped["result_file_sha256"],
        aggregate_summary=scoped["aggregate_summary"],
        candidates=scoped["candidates"],
    )
    replay_payload = copy.deepcopy(payload)
    replay_payload["bundle_id"] = "api_job_hbond_replay_evidence_bundle"
    replay_payload["job_scoped_hbond_evidence"] = replayed.to_dict()
    with pytest.raises(ContractValidationError, match="manifest job binding mismatch"):
        EvidenceBundle(**replay_payload)

    foreign_candidates = copy.deepcopy(scoped["candidates"])
    foreign_candidates[0]["target"] = "FOREIGN"
    unsigned_foreign = {
        key: value
        for key, value in foreign_candidates[0].items()
        if key != "candidate_evidence_sha256"
    }
    foreign_candidates[0]["candidate_evidence_sha256"] = sha256_payload(
        unsigned_foreign
    )
    foreign_scoped = JobScopedHbondEvidence.create(
        job_id=job_id,
        admission_request_sha256=request_sha256,
        execution_request_sha256=request_sha256,
        result_file_sha256=scoped["result_file_sha256"],
        aggregate_summary=scoped["aggregate_summary"],
        candidates=foreign_candidates,
    )
    foreign_payload = copy.deepcopy(payload)
    foreign_payload["job_scoped_hbond_evidence"] = foreign_scoped.to_dict()
    foreign_bundle = EvidenceBundle(**foreign_payload)
    from api.validated_runner import _validate_native_bundle_execution_binding

    with pytest.raises(
        ContractValidationError,
        match="does not match the bound result payload",
    ):
        _validate_native_bundle_execution_binding(
            foreign_bundle,
            job_id=job_id,
            request_payload=request,
            result_file=result_file,
            result_file_sha256=scoped["result_file_sha256"],
            result_payload=result_payload,
        )


def test_job_scoped_hbond_rejects_claim_safe_without_distance_support() -> None:
    from betelgeuze_engine.product.runners.backmapping_scoring import (
        _flatten_hbond_evidence_for_runner,
    )

    evidence = _flatten_hbond_evidence_for_runner(
        smiles="CCO",
        protein_xyz=np.asarray(
            [[0.0, 0.0, 3.0], [1.6, 0.0, 3.0]],
            dtype=np.float32,
        ),
        ligand_xyz=np.asarray(
            [[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]],
            dtype=np.float32,
        ),
    )["hbond_evidence"]
    evidence["distance_pass_count"] = 0
    for pair in evidence["donor_acceptor_pairs"]:
        pair["distance_pass"] = False
    payload = {
        "hbond_evidence_summary": {
            "schema_version": "hbond_evidence_v1",
            "status": "pass",
        },
        "topk": [
            {
                "queue_id": "q1",
                "target": "ADRB2",
                "ligand_id": "lig1",
                "ligand_smiles": "CCO",
                "hbond_evidence": evidence,
            }
        ],
    }

    with pytest.raises(
        ContractValidationError,
        match="distance pass fraction contradicts pairs",
    ):
        build_job_scoped_hbond_evidence(
            payload,
            job_id="job_contradictory",
            admission_request_sha256="a" * 64,
            execution_request_sha256="b" * 64,
            result_file_sha256="c" * 64,
        )


def test_job_scoped_hbond_accepts_review_evidence_with_missing_ligand_geometry() -> None:
    from betelgeuze_engine.product.runners.backmapping_scoring import (
        _flatten_hbond_evidence_for_runner,
    )

    evidence = _flatten_hbond_evidence_for_runner(
        smiles="CCO",
        protein_xyz=np.asarray([[0.0, 0.0, 3.0]], dtype=np.float32),
        ligand_xyz=np.zeros((0, 3), dtype=np.float32),
    )["hbond_evidence"]
    assert evidence["geometry_evaluated"] is False
    assert evidence["missing_expected_anchor_flag"] is True
    scoped = build_job_scoped_hbond_evidence(
        {
            "hbond_evidence_summary": {
                "schema_version": "hbond_evidence_v1",
                "status": "review",
            },
            "topk": [
                {
                    "queue_id": "q_missing_geometry",
                    "target": "ADRB2",
                    "ligand_id": "lig1",
                    "ligand_smiles": "CCO",
                    "hbond_evidence": evidence,
                }
            ],
        },
        job_id="job_missing_geometry",
        admission_request_sha256="a" * 64,
        execution_request_sha256="b" * 64,
        result_file_sha256="c" * 64,
    )

    assert scoped is not None
    assert scoped.candidates[0]["hbond_evidence"][
        "missing_expected_anchor_flag"
    ] is True


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda evidence: evidence["onsps_backmap_metadata"].update(
                {"claim_safe": False, "blocked_reason": "forced_review"}
            ),
            "claim-safe invariants",
        ),
        (
            lambda evidence: evidence.update(
                {
                    "delta_backmap": evidence["delta_backmap_max"] + 0.1,
                    "delta_backmap_evaluated": True,
                    "delta_backmap_yellow_band": False,
                }
            ),
            "delta yellow-band flag contradicts thresholds",
        ),
        (
            lambda evidence: evidence["thresholds"].update(
                {"claim_safe_confidence_min": 0.1}
            ),
            "claim-safe threshold is non-canonical",
        ),
    ],
)
def test_job_scoped_hbond_rejects_tampered_claim_safe_metadata(
    mutate,
    error: str,
) -> None:
    from betelgeuze_engine.product.runners.backmapping_scoring import (
        _flatten_hbond_evidence_for_runner,
    )

    evidence = _flatten_hbond_evidence_for_runner(
        smiles="CCO",
        protein_xyz=np.asarray(
            [[0.0, 0.0, 3.0], [1.6, 0.0, 3.0]],
            dtype=np.float32,
        ),
        ligand_xyz=np.asarray(
            [[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]],
            dtype=np.float32,
        ),
    )["hbond_evidence"]
    assert evidence["claim_safe"] is True
    mutate(evidence)
    payload = {
        "hbond_evidence_summary": {
            "schema_version": "hbond_evidence_v1",
            "status": "pass",
        },
        "topk": [
            {
                "queue_id": "q_tampered",
                "target": "ADRB2",
                "ligand_id": "lig1",
                "ligand_smiles": "CCO",
                "hbond_evidence": evidence,
            }
        ],
    }

    with pytest.raises(ContractValidationError, match=error):
        build_job_scoped_hbond_evidence(
            payload,
            job_id="job_tampered",
            admission_request_sha256="a" * 64,
            execution_request_sha256="b" * 64,
            result_file_sha256="c" * 64,
        )


@pytest.mark.parametrize(
    ("summary_updates", "error"),
    [
        (
            {"claim_safe_row_count": 2},
            "claim-safe count exceeds evaluated rows",
        ),
        (
            {"blocked_row_count": 1},
            "blocked count contradicts evaluated rows",
        ),
        (
            {"claim_safe_rate": 0.0},
            "claim-safe rate contradicts counts",
        ),
        (
            {"status": "review"},
            "aggregate status contradicts counts",
        ),
        (
            {"topk_claim_safe_row_count": 0},
            "Top-K claim-safe count contradicts candidates",
        ),
        (
            {"schema_ready_row_count": 99},
            "schema_ready_row_count exceeds evaluated rows",
        ),
    ],
)
def test_job_scoped_hbond_rejects_contradictory_aggregate_summary(
    summary_updates: dict,
    error: str,
) -> None:
    from betelgeuze_engine.product.runners.backmapping_scoring import (
        _flatten_hbond_evidence_for_runner,
    )

    evidence = _flatten_hbond_evidence_for_runner(
        smiles="CCO",
        protein_xyz=np.asarray(
            [[0.0, 0.0, 3.0], [1.6, 0.0, 3.0]],
            dtype=np.float32,
        ),
        ligand_xyz=np.asarray(
            [[0.0, 0.0, 0.0], [1.6, 0.0, 0.0]],
            dtype=np.float32,
        ),
    )["hbond_evidence"]
    summary = {
        "schema_version": "hbond_evidence_v1",
        "status": "pass",
        "evaluated_row_count": 1,
        "claim_safe_row_count": 1,
        "claim_safe_rate": 1.0,
        "blocked_row_count": 0,
        "topk_claim_safe_row_count": 1,
        **summary_updates,
    }

    with pytest.raises(ContractValidationError, match=error):
        build_job_scoped_hbond_evidence(
            {
                "hbond_evidence_summary": summary,
                "topk": [
                    {
                        "queue_id": "q_summary",
                        "target": "ADRB2",
                        "ligand_id": "lig1",
                        "ligand_smiles": "CCO",
                        "hbond_evidence": evidence,
                    }
                ],
            },
            job_id="job_summary",
            admission_request_sha256="a" * 64,
            execution_request_sha256="b" * 64,
            result_file_sha256="c" * 64,
        )


def test_job_scoped_hbond_rejects_contradictory_topk_blocker_counts() -> None:
    from betelgeuze_engine.product.runners.backmapping_scoring import (
        _flatten_hbond_evidence_for_runner,
    )

    evidence = _flatten_hbond_evidence_for_runner(
        smiles="CCO",
        protein_xyz=np.asarray([[0.0, 0.0, 3.0]], dtype=np.float32),
        ligand_xyz=np.zeros((0, 3), dtype=np.float32),
    )["hbond_evidence"]
    assert evidence["claim_safe"] is False
    assert evidence["blocked_reason"]

    with pytest.raises(
        ContractValidationError,
        match="Top-K blocker counts contradict candidates",
    ):
        build_job_scoped_hbond_evidence(
            {
                "hbond_evidence_summary": {
                    "schema_version": "hbond_evidence_v1",
                    "status": "review",
                    "evaluated_row_count": 1,
                    "claim_safe_row_count": 0,
                    "claim_safe_rate": 0.0,
                    "blocked_row_count": 1,
                    "topk_claim_safe_row_count": 0,
                    "topk_blocked_reason_counts": {},
                },
                "topk": [
                    {
                        "queue_id": "q_blocked_summary",
                        "target": "ADRB2",
                        "ligand_id": "lig1",
                        "ligand_smiles": "CCO",
                        "hbond_evidence": evidence,
                    }
                ],
            },
            job_id="job_blocked_summary",
            admission_request_sha256="a" * 64,
            execution_request_sha256="b" * 64,
            result_file_sha256="c" * 64,
        )
