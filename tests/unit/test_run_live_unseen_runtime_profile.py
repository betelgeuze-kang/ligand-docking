import argparse
import os

from core.config import config as core_config
from tools import run_live_unseen_protein_learning_loop as mod


def test_parser_has_runtime_and_env_perturb_flags():
    parser = mod.build_parser()
    args = parser.parse_args([])
    assert args.ai_router_runtime_mode in ("auto", "eager", "scripted", "compiled", "onnx")
    assert isinstance(args.env_perturb_enabled, bool)
    assert isinstance(args.rust_native_probe_enabled, bool)
    assert isinstance(args.trainer_torch_compile, bool)


def test_env_perturb_profile_is_deterministic():
    args = argparse.Namespace(
        seed=20260219,
        env_perturb_enabled=True,
        env_perturb_temp_grid="280,300,420",
        env_perturb_salt_conc_grid="0.05,0.30",
        env_perturb_ph_grid="6.5,7.4",
        env_perturb_ionic_strength_grid="0.15,0.50",
        env_perturb_ptm_count_grid="0,2",
        env_perturb_force_scale_grid="0.9,1.1",
        env_perturb_cooling_rate_grid="-1,1",
        env_perturb_hydro_strength_grid="0.9,1.1",
        env_perturb_k_angle_grid="20,30",
        env_perturb_theta0_grid="100,120",
        env_perturb_k_dihedral_grid="0.5,2.0",
        env_perturb_phi0_alpha_grid="-70,-45",
        env_perturb_ai_correction_active_grid="1",
    )
    grids = mod._resolve_env_perturb_grids(args)
    p1 = mod._pick_env_perturb_profile(
        args=args,
        cycle_idx=11,
        protein_id="U:P12345",
        runtime_target="Live_test_target",
        grids=grids,
    )
    p2 = mod._pick_env_perturb_profile(
        args=args,
        cycle_idx=11,
        protein_id="U:P12345",
        runtime_target="Live_test_target",
        grids=grids,
    )
    assert p1 == p2
    assert float(p1["temp"]) in (280.0, 300.0, 420.0)
    assert int(p1["ptm_count"]) in (0, 2)


def test_apply_runtime_acceleration_profile_sets_env_and_compile():
    args = argparse.Namespace(
        ai_router_runtime_mode="auto",
        ai_router_auto_try_onnx=True,
        ai_router_compile_mode="reduce-overhead",
        ai_router_onnx_providers="ROCMExecutionProvider,CUDAExecutionProvider",
        onnx_require_iobinding=True,
        onnx_allow_cpu_copy=False,
        require_gpu=True,
        trainer_torch_compile=True,
        trainer_torch_compile_mode="reduce-overhead",
        trainer_torch_compile_fullgraph=False,
        trainer_torch_compile_dynamic=True,
    )
    payload = mod._apply_runtime_acceleration_profile(args)
    env = payload["env"]
    assert env["AI_ROUTER_RUNTIME_MODE"] == "auto"
    assert env["AI_ROUTER_ONNX_IOBINDING_REQUIRED"] == "1"
    assert env["AI_ROUTER_ONNX_ALLOW_CPU_COPY"] == "0"
    assert os.environ.get("AI_ROUTER_ONNX_ALLOW_CPU") == "0"
    tc = core_config.config.get("torch_compile", {})
    assert bool(tc.get("enabled", False)) is True
    assert str(tc.get("mode", "")) == "reduce-overhead"


def test_rust_native_probe_skip_on_cycle_interval():
    args = argparse.Namespace(
        rust_native_probe_enabled=True,
        rust_native_probe_every_cycles=3,
    )
    out = mod._run_rust_native_probe(
        args=args,
        cycle_prefix="runs/test_cycle",
        cycle_idx=1,
    )
    assert out["enabled"] is True
    assert out["attempted"] is False
    assert out["reason"] == "cycle_skip"
