from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _native_adoption_fixture(tmp_path: Path, job_id: str):
    from api.job_store import EXECUTION_REQUEST_TRANSFORM_ID
    from betelgeuze_ai_md.contracts import EvidenceBundle

    result_file = tmp_path / "native" / job_id / "runner_result.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text('{"ok":true}\n', encoding="utf-8")
    result_sha256 = hashlib.sha256(result_file.read_bytes()).hexdigest()
    admission_sha256 = "a" * 64
    execution_sha256 = "b" * 64
    native_manifest = {
        "job_id": job_id,
        "status": "completed",
        "request_sha256": execution_sha256,
        "execution_request_sha256": execution_sha256,
        "execution_request_transform_id": "identity_v1",
        "result_file": str(result_file),
        "result_file_sha256": result_sha256,
    }
    final_manifest = {
        **native_manifest,
        "request_sha256": admission_sha256,
        "execution_request_transform_id": EXECUTION_REQUEST_TRANSFORM_ID,
    }
    bundle = EvidenceBundle(
        bundle_id=f"api_{job_id}_evidence_bundle",
        project_id=job_id,
        ranked_shortlist=[],
        trajectory_summary={"frame_count": 0},
        backmapped_poses=[],
        interaction_report={},
        topology_report={
            "status": "not_assessed",
            "topology_fidelity": "placeholder_alanine",
            "claim_blockers": ["topology_validity_not_assessed"],
        },
        ai_residual_report={
            "residual_mode": "disabled",
            "uncertainty": 1.0,
            "abstained": True,
        },
        failure_flags=["delivery_bundle_validation_not_attached"],
        source_hashes={
            "input_hash": execution_sha256,
            "config_hash": "c" * 64,
            "model_hash": "m" * 64,
            "executable_hash": "e" * 64,
        },
        viewer_assets=[],
        wetlab_handoff_table=[],
        verdict={
            "claim_safe": False,
            "verdict_label": "native_runner_review_only",
            "claim_scope": "restricted_local_delivery_proxy_refinement_only",
            "topology_fidelity": "placeholder_alanine",
            "accuracy_claim_grade": "restricted-local-delivery",
            "failure_flags": ["delivery_bundle_validation_not_attached"],
        },
        result_manifest=native_manifest,
        request_provenance={
            "admission_request_sha256": execution_sha256,
            "execution_request_sha256": execution_sha256,
            "execution_request_transform_id": "identity_v1",
        },
    )
    bundle_path = result_file.parent / "runner_native_bundle.json"
    bundle_path.write_text(
        json.dumps(bundle.to_dict(), sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    status_data = {
        "result_file": str(result_file),
        "result_file_sha256": result_sha256,
        "evidence_bundle": str(bundle_path),
        "evidence_bundle_sha256": bundle.fingerprint(),
        "evidence_bundle_source": "validated_runner_native",
    }
    return (
        bundle,
        status_data,
        final_manifest,
        admission_sha256,
        execution_sha256,
        EXECUTION_REQUEST_TRANSFORM_ID,
    )
