import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

from benchmark import accuracy_bench as acc

import torch


def test_accuracy_bench_import_defaults_hipblaslt_preference():
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.pop("TORCH_BLAS_PREFER_HIPBLASLT", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; "
                "import benchmark.accuracy_bench; "
                "print(os.environ.get('TORCH_BLAS_PREFER_HIPBLASLT'))"
            ),
        ],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "0"


def test_accuracy_bench_import_respects_existing_hipblaslt_preference():
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["TORCH_BLAS_PREFER_HIPBLASLT"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; "
                "import benchmark.accuracy_bench; "
                "print(os.environ.get('TORCH_BLAS_PREFER_HIPBLASLT'))"
            ),
        ],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "1"


def test_calculate_rmsd_aligned_removes_rigid_transform():
    a = torch.tensor(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=torch.float32,
    )
    # 90 deg rotation around z plus translation.
    rot = torch.tensor(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=torch.float32,
    )
    b = (a @ rot.T) + torch.tensor([3.0, -2.0, 1.5], dtype=torch.float32)
    raw = acc.calculate_rmsd(a, b)
    aligned = acc.calculate_rmsd_aligned(a, b)
    assert raw > 0.1
    assert aligned < 1e-5


def test_load_coords_file_npz_last_frame(tmp_path):
    arr = np.zeros((2, 4, 3), dtype=np.float32)
    arr[1, :, :] = 1.5
    fp = tmp_path / "traj.npz"
    np.savez(fp, coords=arr)

    coords = acc._load_coords_file(str(fp), key="coords", frame=-1)
    assert tuple(coords.shape) == (4, 3)
    assert torch.allclose(coords, torch.full((4, 3), 1.5, dtype=torch.float32, device=coords.device))


def test_read_manifest_and_load_external_reference(tmp_path):
    arr = np.arange(30, dtype=np.float32).reshape(1, 10, 3)
    coords_fp = tmp_path / "chig.npy"
    np.save(coords_fp, arr)

    manifest_fp = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "path": str(coords_fp),
                "frame": 0,
                "engine": "openmm",
                "label": "ref",
            }
        ]
    ).to_csv(manifest_fp, index=False)

    manifest = acc._read_external_manifest(str(manifest_fp))
    coords, meta = acc._load_reference_coords(
        target="Chignolin",
        reference_source="external",
        external_manifest=manifest,
    )
    assert tuple(coords.shape) == (10, 3)
    assert meta["reference_engine"] == "openmm"
    assert meta["reference_label"] == "ref"


def test_run_accuracy_report_external_smoke(tmp_path, monkeypatch):
    base = torch.zeros((10, 3), dtype=torch.float32)
    external = torch.ones((10, 3), dtype=torch.float32) * 2.0

    ext_fp = tmp_path / "ext.npy"
    np.save(ext_fp, external.cpu().numpy())

    manifest_fp = tmp_path / "manifest.csv"
    pd.DataFrame([{"target": "Chignolin", "path": str(ext_fp)}]).to_csv(manifest_fp, index=False)

    def fake_run_target(target, steps, noise_scale, seed, return_metrics=False):
        return base + 1.0

    def fake_load_native(target):
        return base.clone(), ""

    monkeypatch.setattr(acc, "run_target", fake_run_target)
    monkeypatch.setattr(acc, "load_native_structure", fake_load_native)

    out_csv = tmp_path / "report.csv"
    out_json = tmp_path / "report.json"
    args = argparse.Namespace(
        targets="Chignolin",
        steps=3,
        runs=2,
        noise=0.02,
        seed_base=42,
        reference_source="external",
        external_manifest=str(manifest_fp),
        external_key=None,
        external_frame=-1,
        external_summary_csv=None,
        out_csv=str(out_csv),
        out_json=str(out_json),
    )
    payload = acc.run_accuracy_report(args)

    assert payload["summary"]["targets"] == 1
    assert out_csv.exists()
    assert out_json.exists()
    saved = json.loads(Path(out_json).read_text(encoding="utf-8"))
    assert saved["summary"]["targets"] == 1
    # simulated=1, ref=2 for every atom -> RMSD should be sqrt(3)
    assert abs(float(saved["rows"][0]["avg_rmsd"]) - float(np.sqrt(3.0))) < 1e-6


def test_run_accuracy_report_external_2bead_reference_auto_projects_ca(tmp_path, monkeypatch):
    base = torch.zeros((10, 3), dtype=torch.float32)
    external_2bead = np.zeros((1, 20, 3), dtype=np.float32)
    external_2bead[0, :10, :] = 2.0
    external_2bead[0, 10:, :] = 9.0

    ext_fp = tmp_path / "ext_2bead.npy"
    np.save(ext_fp, external_2bead)

    manifest_fp = tmp_path / "manifest_2bead.csv"
    pd.DataFrame(
        [
            {
                "target": "Chignolin",
                "path": str(ext_fp),
                "representation": "ca_sc_2bead",
                "bead_order": "ca_then_sc",
                "engine": "openmm",
            }
        ]
    ).to_csv(manifest_fp, index=False)

    def fake_run_target(target, steps, noise_scale, seed, return_metrics=False):
        return base + 1.0

    def fake_load_native(target):
        return base.clone(), ""

    monkeypatch.setattr(acc, "run_target", fake_run_target)
    monkeypatch.setattr(acc, "load_native_structure", fake_load_native)

    out_csv = tmp_path / "report_2bead.csv"
    out_json = tmp_path / "report_2bead.json"
    args = argparse.Namespace(
        targets="Chignolin",
        steps=3,
        runs=2,
        noise=0.02,
        seed_base=42,
        reference_source="external",
        external_manifest=str(manifest_fp),
        external_key=None,
        external_frame=-1,
        external_summary_csv=None,
        out_csv=str(out_csv),
        out_json=str(out_json),
        compare_bead="auto",
    )
    payload = acc.run_accuracy_report(args)
    assert payload["summary"]["targets"] == 1
    saved = json.loads(Path(out_json).read_text(encoding="utf-8"))
    assert saved["rows"][0]["reference_representation"] == "ca_sc_2bead"
    assert saved["rows"][0]["comparison_projection"] == "reference_projected_to_ca"
    assert abs(float(saved["rows"][0]["avg_rmsd"]) - float(np.sqrt(3.0))) < 1e-6


def test_run_accuracy_report_benchmark_engine_uses_checkpoint_flag(tmp_path, monkeypatch):
    base = torch.zeros((10, 3), dtype=torch.float32)
    external = torch.ones((10, 3), dtype=torch.float32) * 2.0

    ext_fp = tmp_path / "ext.npy"
    np.save(ext_fp, external.cpu().numpy())
    manifest_fp = tmp_path / "manifest.csv"
    pd.DataFrame([{"target": "Chignolin", "path": str(ext_fp)}]).to_csv(manifest_fp, index=False)

    captured = {}

    def fake_benchmark_simulation(**kwargs):
        captured.update(kwargs)
        sim = (base + 1.0).cpu().numpy()[None, :, :]
        return {
            "final_coords": sim,
            "ai_router_checkpoint_loaded": True,
        }

    def fake_load_native(target):
        return base.clone(), ""

    monkeypatch.setattr(acc, "benchmark_simulation", fake_benchmark_simulation)
    monkeypatch.setattr(acc, "load_native_structure", fake_load_native)

    out_csv = tmp_path / "report_bench.csv"
    out_json = tmp_path / "report_bench.json"
    args = argparse.Namespace(
        targets="Chignolin",
        steps=5,
        runs=2,
        noise=0.02,
        seed_base=42,
        reference_source="external",
        external_manifest=str(manifest_fp),
        external_key=None,
        external_frame=-1,
        external_summary_csv=None,
        compare_bead="auto",
        simulation_engine="benchmark",
        use_ai_router=True,
        ai_interval=2,
        benchmark_warmup_steps=0,
        benchmark_replicas=1,
        benchmark_force_backend="auto",
        benchmark_neighbor_settings="grid_spacing=12,cutoff=12,skin=2,max_neighbors=100,rebuild_stride=4,max_atoms_per_cell=64",
        benchmark_force_clip=180.0,
        benchmark_ai_correction_clip=90.0,
        ai_router_checkpoint="models/best_airouter_model_StrategicOrchestrator.pth",
        ai_router_checkpoint_strict=False,
        ai_collect_aux=False,
        out_csv=str(out_csv),
        out_json=str(out_json),
    )
    payload = acc.run_accuracy_report(args)

    assert payload["summary"]["simulation_engine"] == "benchmark"
    assert payload["summary"]["ai_router_checkpoint_loaded_targets"] == 1
    assert float(captured["force_clip"]) == 180.0
    assert float(captured["ai_correction_clip"]) == 90.0
    assert abs(float(payload["rows"][0]["avg_rmsd"]) - float(np.sqrt(3.0))) < 1e-6


def test_run_accuracy_report_benchmark_engine_none_checkpoint_not_string(tmp_path, monkeypatch):
    base = torch.zeros((10, 3), dtype=torch.float32)
    external = torch.ones((10, 3), dtype=torch.float32) * 2.0
    ext_fp = tmp_path / "ext.npy"
    np.save(ext_fp, external.cpu().numpy())
    manifest_fp = tmp_path / "manifest.csv"
    pd.DataFrame([{"target": "Chignolin", "path": str(ext_fp)}]).to_csv(manifest_fp, index=False)

    def fake_benchmark_simulation(**kwargs):
        assert kwargs.get("ai_router_checkpoint") is None
        sim = (base + 1.0).cpu().numpy()[None, :, :]
        return {"final_coords": sim, "ai_router_checkpoint_loaded": False}

    def fake_load_native(target):
        return base.clone(), ""

    monkeypatch.setattr(acc, "benchmark_simulation", fake_benchmark_simulation)
    monkeypatch.setattr(acc, "load_native_structure", fake_load_native)

    out_csv = tmp_path / "report_bench_no_ckpt.csv"
    out_json = tmp_path / "report_bench_no_ckpt.json"
    args = argparse.Namespace(
        targets="Chignolin",
        steps=5,
        runs=1,
        noise=0.02,
        seed_base=42,
        reference_source="external",
        external_manifest=str(manifest_fp),
        external_key=None,
        external_frame=-1,
        external_summary_csv=None,
        compare_bead="auto",
        simulation_engine="benchmark",
        use_ai_router=False,
        ai_interval=1,
        benchmark_warmup_steps=0,
        benchmark_replicas=1,
        benchmark_force_backend="auto",
        benchmark_neighbor_settings="grid_spacing=12,cutoff=12,skin=2,max_neighbors=100,rebuild_stride=4,max_atoms_per_cell=64",
        ai_router_checkpoint=None,
        ai_router_checkpoint_strict=False,
        ai_collect_aux=False,
        out_csv=str(out_csv),
        out_json=str(out_json),
    )
    payload = acc.run_accuracy_report(args)
    assert payload["summary"]["targets"] == 1
