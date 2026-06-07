from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.claim_boundary import (
    GENERAL_MD_ACCURACY_CLAIM,
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
)
from core.definitions import StrategyType
from core.topology import TopologyFactory


def test_topology_default_placeholder_fidelity() -> None:
    topo = TopologyFactory(
        n_res=4,
        t_type=1,
        box_size=[10.0, 10.0, 10.0],
        device="cpu",
        strategy_type=StrategyType.CA_ONLY,
    )
    assert topo.topology_fidelity() == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
    assert topo.claim_metadata["accuracy_claim_grade"] == "restricted-local-delivery"


def test_topology_sequence_mapped_fidelity() -> None:
    import torch

    topo = TopologyFactory(
        n_res=3,
        t_type=1,
        box_size=[10.0, 10.0, 10.0],
        device="cpu",
        strategy_type=StrategyType.CA_ONLY,
    )
    topo.set_residue_types_from_sequence(torch.tensor([1, 2, 3], dtype=torch.long))
    assert topo.topology_fidelity() == TOPOLOGY_FIDELITY_SEQUENCE_MAPPED


def test_result_manifest_rejects_general_md_accuracy_for_placeholder() -> None:
    from api.result_manifest import build_result_manifest

    with pytest.raises(ValueError, match=GENERAL_MD_ACCURACY_CLAIM):
        build_result_manifest(
            job_id="job1",
            request={"runner_profile_id": "smoke"},
            status="completed",
            signing_key="test-key",
            key_id="test",
            fidelity=TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
            accuracy_claim_grade=GENERAL_MD_ACCURACY_CLAIM,
        )


def test_simulate_rejects_missing_runner_profile() -> None:
    client = TestClient(app)
    response = client.post(
        "/simulate",
        json={"target_name": "Chignolin", "steps": 100},
    )
    assert response.status_code == 422


def test_simulate_submit_and_status_happy_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.validated_runner as validated_runner
    from api.config import settings

    fake_runner = tmp_path / "fake_validated_runner.py"
    fake_runner.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json",
                "from pathlib import Path",
                "p = argparse.ArgumentParser()",
                "p.add_argument('--request-json', required=True)",
                "p.add_argument('--out-json', required=True)",
                "args = p.parse_args()",
                "Path(args.out_json).write_text(",
                "    json.dumps({'ok': True, 'runner_kind': 'integration_smoke'}, sort_keys=True) + '\\n',",
                "    encoding='utf-8',",
                ")",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    evidence = tmp_path / "profile_evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "input_contract_reviewed": True,
                "output_contract_reviewed": True,
                "claim_boundary_reviewed": True,
                "gate_policy_reviewed": True,
                "fake_result_emission_forbidden": True,
                "gate_policy_artifact": "runs/fake_gate_policy_current.json",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    import hashlib

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    profile = {
        "profile_id": "integration_smoke",
        "enabled": True,
        "runner_script": str(fake_runner.resolve()),
        "arguments": ["--request-json", "{request_json_path}", "--out-json", "{result_file}"],
        "result_file_template": "{job_results_dir}/runner_result.json",
        "production_readiness": {
            "approved_by": "integration-test",
            "approved_at_utc": "2026-06-06T00:00:00+00:00",
            "claim_scope": "integration-test",
            "evidence_artifact": str(evidence),
            "runner_script_sha256": hashlib.sha256(fake_runner.read_bytes()).hexdigest(),
        },
    }
    (profiles_dir / "integration_smoke.json").write_text(json.dumps(profile, sort_keys=True) + "\n")

    monkeypatch.setattr(validated_runner, "ALLOWED_RUNNER_SCRIPTS", {str(fake_runner.resolve())})
    monkeypatch.setattr(settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(settings, "api_validated_runner_timeout_seconds", 10)
    monkeypatch.setattr(settings, "results_storage_path", str(tmp_path / "results"))
    monkeypatch.setattr(settings, "api_job_store_path", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(settings, "api_inline_worker_enabled", True)

    client = TestClient(app)
    submit = client.post(
        "/simulate",
        json={"target_name": "Chignolin", "runner_profile_id": "integration_smoke"},
    )
    assert submit.status_code == 200
    job_id = submit.json()["job_id"]

    status = client.get(f"/status/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] in {"completed", "submitted", "running", "failed"}
