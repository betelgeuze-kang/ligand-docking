from __future__ import annotations

import json
from pathlib import Path

from tools import build_customer_alpha_bundle_manifest as mod


def _packaging() -> dict[str, object]:
    return {"summary": {"status": "amd_workstation_server_packaging_profile_ready", "packaging_ready": True, "install_guide_ready": True}}


def _rocm() -> dict[str, object]:
    return {"summary": {"status": "rocm_environment_manifest_ready", "manifest_ready": True}}


def _throughput() -> dict[str, object]:
    return {"summary": {"status": "amd_hardware_throughput_scorecard_ready", "scorecard_ready": True}}


def _residual() -> dict[str, object]:
    return {"summary": {"status": "residual_shadow_ab_scaffold_ready", "scaffold_ready": True}}


def _gpcr() -> dict[str, object]:
    return {"summary": {"status": "gpcr_hard_decoy_residual_proof_ready", "proof_ready": True}}


def _public_regression() -> dict[str, object]:
    return {"summary": {"status": "public_benchmark_residual_regression_gate_ready", "regression_gate_ready": True}}


def _product_bundle() -> dict[str, object]:
    return {
        "summary": {
            "status": "product_bundle_contract_ready",
            "bundle_assembled": True,
            "bundle_validation_passed": True,
            "expected_bundle_dir": "runs/local_delivery/bundle_product_gpcr_adrb2",
        }
    }


def _commercial() -> dict[str, object]:
    return {
        "summary": {
            "status": "product_commercial_independence_gate_ready",
            "commercial_independent_product_claim_allowed": True,
            "external_saas_runtime_dependency_count": 0,
            "reproducible_install_manifest_ready": True,
            "external_state_mutated": False,
        }
    }


def _readiness() -> dict[str, object]:
    return {
        "summary": {
            "status": "product_handoff_ready",
            "local_delivery_delivery_ready": True,
            "source_artifacts_all_fingerprinted": True,
            "external_state_mutated": False,
        }
    }


def _local_env() -> dict[str, object]:
    return {"summary": {"requirements_lock_complete": True, "missing_requirement_count": 0, "external_state_mutated": False}}


def _ready_payload(**overrides: dict[str, object]) -> dict[str, object]:
    packets = {
        "packaging_packet": _packaging(),
        "rocm_manifest_packet": _rocm(),
        "throughput_scorecard_packet": _throughput(),
        "residual_shadow_packet": _residual(),
        "gpcr_proof_packet": _gpcr(),
        "public_regression_packet": _public_regression(),
        "product_bundle_packet": _product_bundle(),
        "commercial_independence_packet": _commercial(),
        "product_readiness_packet": _readiness(),
        "local_env_packet": _local_env(),
    }
    packets.update(overrides)
    return mod.build_customer_alpha_bundle_manifest(**packets)


def test_customer_alpha_bundle_manifest_ready() -> None:
    payload = _ready_payload()

    summary = payload["summary"]
    assert summary["status"] == "customer_alpha_bundle_manifest_ready"
    assert summary["customer_alpha_bundle_ready"] is True
    assert summary["alpha_bundle_ready"] is True
    assert summary["residual_mode_default"] == "shadow"
    assert summary["rocm_smoke_benchmark_succeeds"] is True
    assert summary["benchmark_evidence_ready"] is True
    assert summary["pass_component_count"] == summary["component_count"]
    assert summary["external_state_mutated"] is False


def test_customer_alpha_bundle_manifest_blocks_missing_product_bundle() -> None:
    payload = _ready_payload(product_bundle_packet={"summary": {"status": "missing"}})

    summary = payload["summary"]
    assert summary["status"] == "blocked_customer_alpha_bundle_manifest"
    assert summary["customer_alpha_bundle_ready"] is False
    assert summary["docking_job_evidence_ready"] is False
    assert summary["report_bundle_generated"] is False
    assert summary["fail_component_count"] >= 1


def test_customer_alpha_bundle_manifest_blocks_external_mutation() -> None:
    commercial = _commercial()
    commercial["summary"]["external_state_mutated"] = True  # type: ignore[index]

    payload = _ready_payload(commercial_independence_packet=commercial)

    summary = payload["summary"]
    assert summary["status"] == "blocked_customer_alpha_bundle_manifest"
    assert summary["approval_safety_ready"] is False
    assert any(row["component"] == "approval_safety" and row["status"] == "fail" for row in payload["rows"])


def test_customer_alpha_bundle_manifest_cli_writes_outputs(tmp_path: Path) -> None:
    inputs = {
        "packaging": _packaging(),
        "rocm": _rocm(),
        "throughput": _throughput(),
        "residual": _residual(),
        "gpcr": _gpcr(),
        "public": _public_regression(),
        "bundle": _product_bundle(),
        "commercial": _commercial(),
        "readiness": _readiness(),
        "local_env": _local_env(),
    }
    paths = {}
    for name, packet in inputs.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(packet) + "\n", encoding="utf-8")
        paths[name] = path
    out_json = tmp_path / "alpha.json"
    out_csv = tmp_path / "alpha.csv"
    out_md = tmp_path / "alpha.md"

    mod.main(
        [
            "--packaging-json",
            str(paths["packaging"]),
            "--rocm-manifest-json",
            str(paths["rocm"]),
            "--throughput-scorecard-json",
            str(paths["throughput"]),
            "--residual-shadow-json",
            str(paths["residual"]),
            "--gpcr-proof-json",
            str(paths["gpcr"]),
            "--public-regression-json",
            str(paths["public"]),
            "--product-bundle-json",
            str(paths["bundle"]),
            "--commercial-independence-json",
            str(paths["commercial"]),
            "--product-readiness-json",
            str(paths["readiness"]),
            "--local-env-json",
            str(paths["local_env"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["alpha_bundle_ready"] is True
    assert "component" in out_csv.read_text(encoding="utf-8")
    assert "Customer Alpha Bundle Manifest" in out_md.read_text(encoding="utf-8")
