from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_amd_rocm_residual_productization_status as mod


DOC_TEXT = """
residual_mode=shadow
ROCm/HIP
E(3)/SE(3)
PINN
AMD Workstation Profile
public benchmark
"""


def _rocm_ready() -> dict[str, object]:
    return {"summary": {"status": "rocm_environment_manifest_ready", "manifest_ready": True}}


def _throughput_ready() -> dict[str, object]:
    return {"summary": {"status": "amd_hardware_throughput_scorecard_ready", "scorecard_ready": True}}


def _ready(status: str, **keys: object) -> dict[str, object]:
    return {"summary": {"status": status, **keys}}


def test_productization_status_reports_phase2_as_next_after_rocm_proof() -> None:
    payload = mod.build_amd_rocm_residual_productization_status(
        master_doc_text=DOC_TEXT,
        rocm_manifest_packet=_rocm_ready(),
        throughput_scorecard_packet=_throughput_ready(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_amd_rocm_residual_productization"
    assert summary["complete_phase_count"] == 2
    assert summary["completion_percent"] == 28.571
    assert summary["phase0_document_contract_ready"] is True
    assert summary["phase1_rocm_manifest_ready"] is True
    assert summary["phase1_hardware_throughput_scorecard_ready"] is True
    assert summary["phase2_residual_shadow_ab_ready"] is False
    assert summary["primary_bottleneck_phase"] == "phase_2"
    assert summary["residual_mode_default"] == "shadow"
    assert summary["benchmark_executed"] is False
    assert summary["external_state_mutated"] is False


def test_productization_status_reports_no_bottleneck_when_complete() -> None:
    payload = mod.build_amd_rocm_residual_productization_status(
        master_doc_text=DOC_TEXT,
        rocm_manifest_packet=_rocm_ready(),
        throughput_scorecard_packet=_throughput_ready(),
        residual_shadow_ab_packet=_ready("residual_shadow_ab_scaffold_ready", scaffold_ready=True),
        gpcr_proof_packet=_ready("gpcr_hard_decoy_residual_proof_ready", proof_ready=True),
        public_benchmark_packet=_ready("product_public_benchmark_contract_ready", public_benchmark_validation_ready=True),
        public_regression_packet=_ready("public_benchmark_residual_regression_gate_ready", regression_gate_ready=True),
        amd_packaging_packet=_ready("amd_workstation_server_packaging_profile_ready", packaging_ready=True),
        alpha_bundle_packet=_ready("customer_alpha_bundle_manifest_ready", alpha_bundle_ready=True),
    )

    summary = payload["summary"]
    assert summary["status"] == "amd_rocm_residual_productization_complete"
    assert summary["roadmap_complete"] is True
    assert summary["complete_phase_count"] == 7
    assert summary["primary_bottleneck_phase"] == "none"
    assert summary["next_command"] == "none"


def test_productization_status_blocks_on_missing_master_doc_terms() -> None:
    payload = mod.build_amd_rocm_residual_productization_status(
        master_doc_text="ROCm/HIP only",
        rocm_manifest_packet=_rocm_ready(),
        throughput_scorecard_packet=_throughput_ready(),
    )

    summary = payload["summary"]
    assert summary["phase0_document_contract_ready"] is False
    assert summary["primary_bottleneck_phase"] == "phase_0"
    assert payload["rows"][0]["status"] == "blocked"
    assert "missing_terms=" in payload["rows"][0]["observed"]


def test_productization_status_cli_writes_outputs(tmp_path: Path) -> None:
    doc = tmp_path / "master.md"
    rocm = tmp_path / "rocm.json"
    throughput = tmp_path / "throughput.json"
    out_json = tmp_path / "status.json"
    out_csv = tmp_path / "status.csv"
    out_md = tmp_path / "status.md"
    doc.write_text(DOC_TEXT, encoding="utf-8")
    rocm.write_text(json.dumps(_rocm_ready()) + "\n", encoding="utf-8")
    throughput.write_text(json.dumps(_throughput_ready()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--master-doc",
            str(doc),
            "--rocm-manifest-json",
            str(rocm),
            "--throughput-scorecard-json",
            str(throughput),
            "--residual-shadow-ab-json",
            str(tmp_path / "missing_residual_shadow_ab.json"),
            "--gpcr-proof-json",
            str(tmp_path / "missing_gpcr_proof.json"),
            "--public-benchmark-json",
            str(tmp_path / "missing_public_benchmark.json"),
            "--public-regression-json",
            str(tmp_path / "missing_public_regression.json"),
            "--amd-packaging-json",
            str(tmp_path / "missing_packaging.json"),
            "--alpha-bundle-json",
            str(tmp_path / "missing_alpha.json"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["primary_bottleneck_phase"] == "phase_2"
    assert "phase_id" in out_csv.read_text(encoding="utf-8")
    assert "AMD ROCm Residual Productization Status" in out_md.read_text(encoding="utf-8")
