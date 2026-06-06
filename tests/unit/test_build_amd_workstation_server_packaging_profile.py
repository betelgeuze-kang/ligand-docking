from __future__ import annotations

import json
from pathlib import Path

from tools import build_amd_workstation_server_packaging_profile as mod


def _rocm_manifest() -> dict[str, object]:
    return {
        "summary": {
            "status": "rocm_environment_manifest_ready",
            "manifest_ready": True,
            "device_names": ["AMD Radeon RX 6900 XT"],
            "visible_device_count": 1,
            "rocm_version": "6.0.2",
            "torch_version": "2.6.0+rocm6.1",
            "torch_hip_version": "6.1.40091",
        },
        "command_probes": {
            "rocm_smi": {
                "stdout_excerpt": "GPU[0] : VRAM Total Memory (B): 17163091968\n",
            }
        },
    }


def _throughput() -> dict[str, object]:
    return {
        "summary": {
            "status": "amd_hardware_throughput_scorecard_ready",
            "scorecard_ready": True,
            "ligands_per_hour": 1000.0,
            "cpu_vs_rocm_speedup": 2.0,
        }
    }


def _public_gate() -> dict[str, object]:
    return {"summary": {"status": "public_benchmark_residual_regression_gate_ready", "regression_gate_ready": True}}


def _gpcr_proof() -> dict[str, object]:
    return {"summary": {"status": "gpcr_hard_decoy_residual_proof_ready", "proof_ready": True}}


def _residual_shadow() -> dict[str, object]:
    return {"summary": {"status": "residual_shadow_ab_scaffold_ready", "scaffold_ready": True}}


def _write_requirements(tmp_path: Path) -> tuple[Path, Path, Path]:
    rocm = tmp_path / "requirements-rocm.txt"
    cpu = tmp_path / "requirements-cpu.txt"
    dev = tmp_path / "requirements-dev.txt"
    for path in (rocm, cpu, dev):
        path.write_text("numpy==1.26.4\n", encoding="utf-8")
    return rocm, cpu, dev


def test_build_amd_workstation_server_packaging_profile_ready(tmp_path: Path) -> None:
    rocm_req, cpu_req, dev_req = _write_requirements(tmp_path)

    payload = mod.build_amd_workstation_server_packaging_profile(
        rocm_manifest_packet=_rocm_manifest(),
        throughput_scorecard_packet=_throughput(),
        public_regression_packet=_public_gate(),
        gpcr_proof_packet=_gpcr_proof(),
        residual_shadow_packet=_residual_shadow(),
        requirements_rocm_path=str(rocm_req),
        requirements_cpu_path=str(cpu_req),
        requirements_dev_path=str(dev_req),
    )

    summary = payload["summary"]
    assert summary["status"] == "amd_workstation_server_packaging_profile_ready"
    assert summary["packaging_ready"] is True
    assert summary["workstation_profile_ready"] is True
    assert summary["server_profile_ready"] is True
    assert summary["current_topology"] == "single_gpu"
    assert summary["server_multi_gpu_claim_ready"] is False
    assert summary["pass_component_count"] == summary["component_count"]
    assert summary["external_state_mutated"] is False


def test_build_amd_workstation_server_packaging_profile_blocks_missing_requirements(tmp_path: Path) -> None:
    rocm_req, cpu_req, dev_req = _write_requirements(tmp_path)
    cpu_req.unlink()

    payload = mod.build_amd_workstation_server_packaging_profile(
        rocm_manifest_packet=_rocm_manifest(),
        throughput_scorecard_packet=_throughput(),
        public_regression_packet=_public_gate(),
        gpcr_proof_packet=_gpcr_proof(),
        residual_shadow_packet=_residual_shadow(),
        requirements_rocm_path=str(rocm_req),
        requirements_cpu_path=str(cpu_req),
        requirements_dev_path=str(dev_req),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_amd_workstation_server_packaging_profile"
    assert summary["packaging_ready"] is False
    assert summary["fail_component_count"] >= 1


def test_amd_workstation_server_packaging_profile_cli_writes_outputs(tmp_path: Path) -> None:
    rocm_req, cpu_req, dev_req = _write_requirements(tmp_path)
    rocm_json = tmp_path / "rocm.json"
    throughput_json = tmp_path / "throughput.json"
    public_json = tmp_path / "public.json"
    gpcr_json = tmp_path / "gpcr.json"
    residual_json = tmp_path / "residual.json"
    out_json = tmp_path / "packaging.json"
    out_csv = tmp_path / "packaging.csv"
    out_md = tmp_path / "packaging.md"
    rocm_json.write_text(json.dumps(_rocm_manifest()) + "\n", encoding="utf-8")
    throughput_json.write_text(json.dumps(_throughput()) + "\n", encoding="utf-8")
    public_json.write_text(json.dumps(_public_gate()) + "\n", encoding="utf-8")
    gpcr_json.write_text(json.dumps(_gpcr_proof()) + "\n", encoding="utf-8")
    residual_json.write_text(json.dumps(_residual_shadow()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--rocm-manifest-json",
            str(rocm_json),
            "--throughput-scorecard-json",
            str(throughput_json),
            "--public-regression-json",
            str(public_json),
            "--gpcr-proof-json",
            str(gpcr_json),
            "--residual-shadow-json",
            str(residual_json),
            "--requirements-rocm",
            str(rocm_req),
            "--requirements-cpu",
            str(cpu_req),
            "--requirements-dev",
            str(dev_req),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["packaging_ready"] is True
    assert "component" in out_csv.read_text(encoding="utf-8")
    assert "AMD Workstation/Server Packaging Profile" in out_md.read_text(encoding="utf-8")
