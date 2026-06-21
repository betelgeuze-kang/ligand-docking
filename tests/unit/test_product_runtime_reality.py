from __future__ import annotations

import json
import hashlib
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

from api.job_store import SQLiteJobStore, get_configured_job_store, reset_configured_job_store_for_tests


def _write_completed_job(
    *,
    main,
    store: SQLiteJobStore,
    job_id: str,
    result_file: Path,
    result_payload: str,
    result_manifest_payload: str = '{"status":"completed"}\n',
) -> None:
    results_dir = result_file.parent
    results_dir.mkdir(parents=True, exist_ok=True)
    result_file.write_text(result_payload, encoding="utf-8")
    manifest_path = results_dir / "result_manifest.json"
    bundle_path = results_dir / "evidence_bundle.json"
    manifest_path.write_text(result_manifest_payload, encoding="utf-8")
    bundle_path.write_text('{"bundle_schema_version":"ai_md_evidence_bundle_v1"}\n', encoding="utf-8")
    store.create_job(job_id, {"target_name": "Chignolin", "runner_profile_id": "smoke"}, status="completed")
    store.update_job(
        job_id,
        status="completed",
        result_file=str(result_file),
        result_manifest_path=str(manifest_path),
        evidence_bundle_path=str(bundle_path),
        evidence_bundle_sha256="d" * 64,
    )
    main.write_status_file(
        main.job_status_path(job_id),
        {
            "job_id": job_id,
            "status": "completed",
            "result_file": str(result_file),
            "result_manifest": str(manifest_path),
            "evidence_bundle": str(bundle_path),
            "evidence_bundle_sha256": "d" * 64,
        },
    )


def test_get_job_store_uses_late_configured_path(tmp_path: Path, monkeypatch) -> None:
    import api.main as main

    store_path = tmp_path / "late_config_jobs.sqlite3"
    reset_configured_job_store_for_tests()
    monkeypatch.setattr(main, "job_store", None)
    monkeypatch.setattr(main, "_job_store_path", None)
    monkeypatch.setattr(main.settings, "api_job_store_path", str(store_path))

    store = main.get_job_store()

    assert store.path == store_path
    assert store_path.exists()


def test_configured_job_store_lazy_factory_tracks_runtime_settings(tmp_path: Path, monkeypatch) -> None:
    import api.job_store as job_store_mod

    first_path = tmp_path / "first.sqlite3"
    second_path = tmp_path / "second.sqlite3"
    reset_configured_job_store_for_tests()

    monkeypatch.setattr(job_store_mod.settings, "api_job_store_path", str(first_path))
    first = get_configured_job_store()
    again = get_configured_job_store()

    assert first is again
    assert first.path == first_path

    monkeypatch.setattr(job_store_mod.settings, "api_job_store_path", str(second_path))
    second = get_configured_job_store()

    assert second is not first
    assert second.path == second_path
    assert second_path.exists()


def test_docking_dispatch_uses_configured_job_store_when_store_not_injected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import api.docking_dispatch as docking_dispatch
    import api.job_store as job_store_mod

    store_path = tmp_path / "dispatch.sqlite3"
    reset_configured_job_store_for_tests()
    monkeypatch.setattr(job_store_mod.settings, "api_job_store_path", str(store_path))
    monkeypatch.setattr(docking_dispatch.settings, "api_job_store_path", str(store_path))
    monkeypatch.setattr(docking_dispatch, "is_dispatch_eligible", lambda record: (True, "eligible"))
    monkeypatch.setattr(
        docking_dispatch,
        "mark_ledger_dispatched",
        lambda jobs_dir, job_id, worker_id="": {"progress_state": "worker_dispatch_enqueued"},
    )

    outcome = docking_dispatch.dispatch_docking_job_if_eligible(
        {
            "job_id": "dock_job_1",
            "target_id": "ADRB2",
            "request_sha256": "a" * 64,
            "family": "gpcr",
            "ligand_count": 1,
            "structure_source_kind": "operator_supplied_pdb",
            "engine_dispatch_manifest": {"runner_profile_id": "backmapping_scoring.production"},
        },
        jobs_dir=tmp_path / "jobs",
        store=None,
    )

    assert outcome["dispatched"] is True
    record = SQLiteJobStore(store_path).get_job("dock_job_1")
    assert record is not None
    assert record["status"] == "submitted"
    assert record["request"]["runner_profile_id"] == "backmapping_scoring.production"


def test_results_endpoint_returns_json_artifact_as_json(tmp_path: Path, monkeypatch) -> None:
    import api.main as main

    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    monkeypatch.setattr(main, "job_store", store)
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))
    result_file = tmp_path / "results" / "job_json" / "runner_result.json"
    _write_completed_job(
        main=main,
        store=store,
        job_id="job_json",
        result_file=result_file,
        result_payload=json.dumps({"ok": True, "runner_kind": "fake_validated_runner"}) + "\n",
    )

    response = TestClient(main.app).get("/results/job_json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["runner_kind"] == "fake_validated_runner"


def test_results_endpoint_keeps_pdb_content_type(tmp_path: Path, monkeypatch) -> None:
    import api.main as main

    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    monkeypatch.setattr(main, "job_store", store)
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))
    result_file = tmp_path / "results" / "job_pdb" / "result.pdb"
    _write_completed_job(
        main=main,
        store=store,
        job_id="job_pdb",
        result_file=result_file,
        result_payload="ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00  0.00           C\n",
    )

    response = TestClient(main.app).get("/results/job_pdb")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("chemical/x-pdb")
    assert "ATOM" in response.text


def test_results_endpoint_returns_unknown_artifact_as_octet_stream(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import api.main as main

    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    monkeypatch.setattr(main, "job_store", store)
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))
    result_file = tmp_path / "results" / "job_binary" / "result.bin"
    _write_completed_job(
        main=main,
        store=store,
        job_id="job_binary",
        result_file=result_file,
        result_payload="opaque-bytes\n",
    )

    response = TestClient(main.app).get("/results/job_binary")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/octet-stream")
    assert response.content == b"opaque-bytes\n"


def test_results_endpoint_uses_manifest_artifact_type_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import api.main as main

    store = SQLiteJobStore(tmp_path / "api_jobs.sqlite3")
    monkeypatch.setattr(main, "job_store", store)
    monkeypatch.setattr(main.settings, "results_storage_path", str(tmp_path / "results"))
    result_file = tmp_path / "results" / "job_manifest_json" / "runner_result.artifact"
    _write_completed_job(
        main=main,
        store=store,
        job_id="job_manifest_json",
        result_file=result_file,
        result_payload=json.dumps({"ok": True, "source": "manifest_metadata"}) + "\n",
        result_manifest_payload=json.dumps(
            {
                "status": "completed",
                "result_artifact_type": "json",
                "result_file_media_type": "application/json",
            }
        )
        + "\n",
    )

    response = TestClient(main.app).get("/results/job_manifest_json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["source"] == "manifest_metadata"


def test_results_endpoint_openapi_matches_polymorphic_artifact_responses() -> None:
    import api.main as main

    operation = TestClient(main.app).get("/openapi.json").json()["paths"]["/results/{job_id}"]["get"]
    response_200 = operation["responses"]["200"]

    assert response_200.get("content", {}).get("application/json", {}).get("schema", {}) == {}
    assert "ResultsResponse" not in json.dumps(response_200)
    assert set(response_200["content"]) >= {
        "application/json",
        "chemical/x-pdb",
        "chemical/x-mdl-sdfile",
        "chemical/x-mdl-molfile",
        "application/zip",
        "application/octet-stream",
    }


def test_product_rocm_hip_rust_requirements_are_installed_by_product_dockerfile() -> None:
    dockerfile = Path("Dockerfile.product").read_text(encoding="utf-8")
    base_requirements = Path("requirements-base.txt").read_text(encoding="utf-8")
    default_requirements = Path("requirements.txt").read_text(encoding="utf-8")
    rocm_requirements = Path("requirements-rocm.txt").read_text(encoding="utf-8")
    product_rocm_requirements = Path("requirements-product-rocm.txt").read_text(encoding="utf-8")
    base_requirement_lines = set(base_requirements.splitlines())
    default_requirement_lines = set(default_requirements.splitlines())
    rocm_requirement_lines = set(rocm_requirements.splitlines())
    product_rocm_requirement_lines = set(product_rocm_requirements.splitlines())

    assert "rocm/pytorch" in dockerfile
    assert "requirements-base.txt" in dockerfile
    assert "requirements-product-rocm.txt" in dockerfile
    assert "-r requirements-product-rocm.txt" in dockerfile
    assert "runs/independent_engine_roadmap_status_current.json" in dockerfile
    assert "COPY runs/" not in dockerfile
    assert "independent_engine_roadmap_closed" in dockerfile
    assert "product_image_build_time_fixture" in dockerfile
    assert "requirements.txt" in dockerfile
    assert "FORCE_RUST_HIP=1" in dockerfile
    assert "RUST_HIP_USE_GPU_NBLIST_BUILDER=1" in dockerfile
    assert "TORCH_BLAS_PREFER_HIPBLASLT=0" in dockerfile
    assert "COPY rust_engine ./rust_engine" in dockerfile
    assert "COPY third_party ./third_party" in dockerfile
    assert "tools/build_rust_hip_engine.py --output /app" in dockerfile
    assert "torch.version.hip" in dockerfile
    assert "ldi_arc_rust" in dockerfile
    assert "torch==2.6.0" not in base_requirement_lines
    assert "-r requirements-base.txt" in default_requirement_lines
    assert "torch==2.6.0" in default_requirement_lines
    assert "-r requirements-base.txt" in product_rocm_requirement_lines
    assert "rdkit-pypi==2022.9.5" in product_rocm_requirement_lines
    assert "-r requirements-rocm.txt" not in product_rocm_requirement_lines
    assert "-r requirements.txt" not in product_rocm_requirement_lines
    assert "torch==2.6.0" not in product_rocm_requirement_lines
    assert "-r requirements-base.txt" in rocm_requirement_lines
    assert "-r requirements.txt" not in rocm_requirement_lines
    assert "torch==2.6.0" not in rocm_requirement_lines
    assert "torch==2.6.0+rocm6.1" in rocm_requirement_lines


def test_product_image_smoke_script_is_fail_closed_and_has_rocm_runtime_mode() -> None:
    script = Path("deploy/verify_product_image.sh").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/product-image-smoke.yml").read_text(encoding="utf-8")

    assert 'VERIFY_MODE="${PRODUCT_IMAGE_VERIFY_MODE:-build}"' in script
    assert "PRODUCT_IMAGE_SMOKE_RECEIPT_JSON" in script
    assert "build|rocm-runtime" in script
    assert "docker_cli_missing" in script
    assert "does not mark missing Docker as green" in script
    assert 'HOST_PYTHON="${PRODUCT_IMAGE_HOST_PYTHON:-python3}"' in script
    assert "host_python_missing" in script
    assert '"${HOST_PYTHON}" - <<' in script
    assert "exit 2" in script
    assert "--device=/dev/kfd" in script
    assert "--device=/dev/dri" in script
    assert "torch.cuda.is_available()" in script
    assert "torch.cuda.device_count() > 0" in script
    assert "API_VALIDATED_RUNNER_ENABLED=1" in script
    assert "run_tier_alpha_adrb2_dispatch_smoke.py" in script
    assert "tier_alpha_adrb2_dispatch_smoke.json" in script
    assert "tools/run_ligand_backmapping_scoring.py" in script
    assert "backmapping_summary.json" in script
    assert "container_native.pdb" in script
    assert "native_pdb_path" in script
    assert "hbond_evidence_v1" in script
    assert "onsps_backmap_evidence_v1" in script
    assert "clean_container_smoke_ready" in script
    assert "product_runner_smoke_ready" in script
    assert "product_runner_claim_metadata_ready" in script
    assert "backmapping_ligand_topology_claim_safe" in script
    assert "backmapping_ligand_topology_receipt_ready" in script
    assert "product claim promotion requires mode=rocm-runtime" in script
    assert "product_runner_claim_metadata_ready=true" in script
    assert "pull_request:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "verify_mode:" in workflow
    assert "PRODUCT_IMAGE_VERIFY_MODE: build" in workflow
    assert "product-image-rocm-runtime-smoke" in workflow
    assert "runs-on: [self-hosted, linux, rocm]" in workflow
    assert "PRODUCT_IMAGE_VERIFY_MODE: rocm-runtime" in workflow
    assert "product runtime claim: `false`" in workflow


def test_rust_hip_builder_shim_accepts_cli_arguments() -> None:
    result = subprocess.run(
        [sys.executable, "tools/build_rust_hip_engine.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "--output" in result.stdout


def test_allowlisted_runner_legacy_paths_point_to_engine_adapters_and_profile_hashes_match() -> None:
    cases = [
        (
            Path("tools/run_ligand_backmapping_scoring.py"),
            Path("config/api_validated_runner_profiles/backmapping_scoring.production.json"),
            "betelgeuze_engine.product.runners.backmapping_scoring",
        ),
        (
            Path("tools/run_ligand_htvs_pipeline.py"),
            Path("config/api_validated_runner_profiles/ligand_htvs_pipeline_default.json"),
            "betelgeuze_engine.product.runners.htvs_pipeline",
        ),
        (
            Path("tools/run_ligand_topk_delivery.py"),
            Path("config/api_validated_runner_profiles/ligand_topk_delivery.production.json"),
            "betelgeuze_engine.product.runners.topk_delivery",
        ),
    ]

    for script, profile_path, adapter_import in cases:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        text = script.read_text(encoding="utf-8")

        assert adapter_import in text
        assert profile["runner_script"] == str(script)
        assert profile["production_readiness"]["runner_script_sha256"] == hashlib.sha256(script.read_bytes()).hexdigest()


def test_backmapping_runner_adapter_preserves_private_scoring_imports() -> None:
    from tools.run_ligand_backmapping_scoring import _ligand_props
    from betelgeuze_engine.product.runners.backmapping_scoring import main

    assert callable(main)
    assert _ligand_props({"ligand_mw": 100.0})["mw"] == 100.0
