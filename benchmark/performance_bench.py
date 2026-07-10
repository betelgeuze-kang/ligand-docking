# benchmark/performance_bench.py

import json
import time
import torch
import numpy as np
from typing import Any, Dict, Mapping, Optional, Tuple
from core.config import config, logger
from core.topology import TopologyFactory
from core.spatial import GridSpatialHash
from core.forcefield import ForceField
from core.integrator import LangevinIntegrator
from core.mts_policy import resolve_target_ai_interval, resolve_target_float_value
from monitor.physics_guard import PhysicsGuard
from theory.strategy import StrategicOrchestrator
from tools.pdb_loader import load_native_structure
from core.definitions import ResearchConstants
import pandas as pd
import psutil # For CPU monitoring
import os

from core.gpu_metrics import sample_gpu_metrics as _sample_gpu_metrics
from train.checkpoint_contracts import (
    load_state_dict_fail_closed,
    resolve_checkpoint_state_dict,
)
from train.runtime_inputs import (
    build_runtime_inputs,
    current_runtime_input_schema_metadata,
    require_runtime_input_checkpoint_schema,
)

def _sync_if_cuda():
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def _reset_forcefield_runtime_caches(ff: ForceField) -> None:
    """Drop cached buffers that may have been created inside inference_mode."""
    try:
        if hasattr(ff, "sh") and hasattr(ff.sh, "reset_cache"):
            ff.sh.reset_cache()
    except Exception:
        pass
    try:
        ff._rust_nb_cache = None
        ff._rust_nb_ref_coords = None
        ff._rust_nb_shape = None
    except Exception:
        pass
    rb = getattr(ff, "rust_backend", None)
    if rb is None:
        return
    for attr in (
        "_cached_force",
        "_cached_energy",
        "_cached_shape",
        "_cached_device",
        "_cached_nb_idx",
        "_cached_nb_mask",
        "_cached_nb_dist",
        "_cached_nb_shape",
        "_cached_cell_counts",
        "_cached_cell_atoms",
        "_cached_cells_shape",
    ):
        try:
            setattr(rb, attr, None)
        except Exception:
            pass


class _AIGraphRunner:
    """Optional CUDA/HIP graph replay wrapper for orchestrator inference."""

    def __init__(self):
        self.enabled = False
        self.reason = "not_initialized"
        self.graph = None
        self.static_c = None
        self.static_nb_idx = None
        self.static_nb_dist = None
        self.static_nb_mask = None
        self.static_pe = None
        self.static_out = None

    def can_run_for(self, c: torch.Tensor, nb_data: Tuple[torch.Tensor, ...], pe: torch.Tensor) -> bool:
        if not self.enabled:
            return False
        if self.static_c is None or self.static_pe is None:
            return False
        if tuple(c.shape) != tuple(self.static_c.shape):
            return False
        if tuple(pe.shape) != tuple(self.static_pe.shape):
            return False
        if nb_data is None or len(nb_data) < 3:
            return False
        return (
            tuple(nb_data[0].shape) == tuple(self.static_nb_idx.shape)
            and tuple(nb_data[1].shape) == tuple(self.static_nb_dist.shape)
            and tuple(nb_data[2].shape) == tuple(self.static_nb_mask.shape)
        )

    def run(self, c: torch.Tensor, nb_data: Tuple[torch.Tensor, ...], pe: torch.Tensor) -> Optional[torch.Tensor]:
        if not self.can_run_for(c, nb_data, pe):
            return None
        self.static_c.copy_(c)
        self.static_nb_idx.copy_(nb_data[0])
        self.static_nb_dist.copy_(nb_data[1])
        self.static_nb_mask.copy_(nb_data[2])
        self.static_pe.copy_(pe)
        self.graph.replay()
        return self.static_out.clone()


def _build_ai_graph_runner(
    ai_model: torch.nn.Module,
    top: Any,
    sim_params_batch: Dict[str, float],
    c_example: torch.Tensor,
    nb_example: Tuple[torch.Tensor, ...],
    pe_example: torch.Tensor,
    collect_aux: bool,
    warmup_iters: int,
) -> _AIGraphRunner:
    runner = _AIGraphRunner()
    if not torch.cuda.is_available():
        runner.reason = "cuda_unavailable"
        return runner
    if not hasattr(torch.cuda, "CUDAGraph"):
        runner.reason = "cuda_graph_unsupported"
        return runner
    if nb_example is None or len(nb_example) < 3:
        runner.reason = "neighbor_data_missing"
        return runner

    try:
        runner.static_c = c_example.clone().contiguous()
        runner.static_nb_idx = nb_example[0].clone().contiguous()
        runner.static_nb_dist = nb_example[1].clone().contiguous()
        runner.static_nb_mask = nb_example[2].clone().contiguous()
        runner.static_pe = pe_example.clone().contiguous()

        stream = torch.cuda.Stream()
        with torch.cuda.stream(stream):
            for _ in range(max(int(warmup_iters), 1)):
                ai_model(
                    runner.static_c,
                    top,
                    (runner.static_nb_idx, runner.static_nb_dist, runner.static_nb_mask),
                    runner.static_pe,
                    sim_params_batch,
                    collect_aux=bool(collect_aux),
                )
        torch.cuda.current_stream().wait_stream(stream)
        _sync_if_cuda()

        runner.graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(runner.graph):
            runner.static_out, _ = ai_model(
                runner.static_c,
                top,
                (runner.static_nb_idx, runner.static_nb_dist, runner.static_nb_mask),
                runner.static_pe,
                sim_params_batch,
                collect_aux=bool(collect_aux),
            )
        _sync_if_cuda()
        runner.enabled = True
        runner.reason = "ok"
    except Exception as exc:
        runner.enabled = False
        runner.reason = f"{type(exc).__name__}: {exc}"
    return runner


def _resolve_checkpoint_state_dict(payload: Any) -> Tuple[Dict[str, torch.Tensor], str]:
    state, source = resolve_checkpoint_state_dict(payload)
    return dict(state), source


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _extract_checkpoint_map(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("checkpoint map must be a JSON object")
    for key in ("target_checkpoints", "checkpoints", "targets", "map"):
        candidate = payload.get(key)
        if isinstance(candidate, dict):
            return candidate
    if payload and all(isinstance(k, str) for k in payload.keys()):
        return payload
    raise ValueError("checkpoint map JSON has no usable mapping object")


def _resolve_ai_router_checkpoint_path(
    checkpoint_spec: str,
    target: str,
) -> Tuple[str, Dict[str, Any]]:
    spec = str(checkpoint_spec).strip()
    if not spec:
        return "", {"is_map": False, "map_path": None, "target_key": str(target), "selected_key": None}

    # Convention: @path/to/map.json
    if not spec.startswith("@"):
        return os.path.abspath(spec), {
            "is_map": False,
            "map_path": None,
            "target_key": str(target),
            "selected_key": None,
        }

    map_path_raw = spec[1:].strip()
    if not map_path_raw:
        raise ValueError("empty checkpoint map path after '@'")
    map_path = os.path.abspath(map_path_raw)
    if not os.path.exists(map_path):
        raise FileNotFoundError(f"ai router checkpoint map not found: {map_path}")

    with open(map_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    mapping = _extract_checkpoint_map(payload)

    target_norm = _normalize_target_key(target)
    selected_key = None
    selected_value = None
    for k, v in mapping.items():
        if _normalize_target_key(k) == target_norm:
            selected_key = str(k)
            selected_value = v
            break
    if selected_value in (None, ""):
        for fallback_key in ("default", "*", "all", "any"):
            if fallback_key in mapping and str(mapping[fallback_key]).strip():
                selected_key = fallback_key
                selected_value = mapping[fallback_key]
                break
    if selected_value in (None, ""):
        raise KeyError(f"target '{target}' not found in checkpoint map and no default provided: {map_path}")

    selected_path = str(selected_value).strip()
    if not os.path.isabs(selected_path):
        selected_path = os.path.join(os.path.dirname(map_path), selected_path)
    return os.path.abspath(selected_path), {
        "is_map": True,
        "map_path": map_path,
        "target_key": str(target),
        "selected_key": selected_key,
    }


def _load_ai_router_checkpoint(
    ai_model: torch.nn.Module,
    checkpoint_path: str,
    strict: bool = False,
) -> Dict[str, Any]:
    path_i = os.path.abspath(str(checkpoint_path))
    if not os.path.exists(path_i):
        raise FileNotFoundError(f"ai router checkpoint not found: {path_i}")

    payload = torch.load(path_i, map_location=config.DEVICE)
    runtime_schema = require_runtime_input_checkpoint_schema(
        payload,
        expected=current_runtime_input_schema_metadata(),
    )
    state_dict, state_source = _resolve_checkpoint_state_dict(payload)
    load_info = load_state_dict_fail_closed(
        ai_model,
        state_dict,
        strict=bool(strict),
        allow_partial=False,
    )
    return {
        "path": path_i,
        "loaded": True,
        "state_source": state_source,
        **load_info,
        "runtime_input_schema": dict(runtime_schema),
    }


def _build_checkpoint_compatible_ai_inputs(
    coordinates: torch.Tensor,
    topology: Any,
    sim_params: Mapping[str, object],
) -> Tuple[Any, Tuple[torch.Tensor, torch.Tensor, torch.Tensor], torch.Tensor, Dict[str, float]]:
    """Use exactly the runtime-input schema recorded by current checkpoints."""

    schema = current_runtime_input_schema_metadata()
    if bool(schema.get("periodic", True)):
        raise ValueError("legacy AI checkpoint runtime currently supports non-periodic inputs only")
    resolver = getattr(topology, "residue_types_for_coordinate_count", None)
    if callable(resolver):
        residue_types = resolver(int(coordinates.shape[1]))
    else:
        residue_types = getattr(topology, "residue_types", None)
    if not isinstance(residue_types, torch.Tensor) or residue_types.ndim != 1:
        raise ValueError("benchmark topology cannot provide residue types aligned to coordinates")
    if int(residue_types.shape[0]) != int(coordinates.shape[1]):
        raise ValueError("benchmark residue types do not match the coordinate atom count")
    residue_types_batch = residue_types.to(device=coordinates.device).unsqueeze(0).expand(
        int(coordinates.shape[0]), -1
    )
    return build_runtime_inputs(
        coordinates,
        residue_types_batch,
        sim_params_batch=sim_params,
        neighbor_k=int(schema["neighbor_k"]),
        neighbor_cutoff_angstrom=float(schema["cutoff_angstrom"]),
        max_neighbor_candidates=int(schema["max_neighbor_candidates"]),
        max_atoms_per_cell=int(schema["max_atoms_per_cell"]),
    )


def _clip_tensor_abs(x: torch.Tensor, clip_value: float) -> Tuple[torch.Tensor, int]:
    clip_v = max(float(clip_value), 0.0)
    if clip_v <= 0.0:
        return x, 0
    over = torch.abs(x) > clip_v
    hit_count = int(over.sum().item())
    if hit_count <= 0:
        return x, 0
    return torch.clamp(x, min=-clip_v, max=clip_v), hit_count


def _clip_tensor_abs_runtime(
    x: torch.Tensor,
    clip_value: float,
    track_hits: bool,
) -> Tuple[torch.Tensor, int]:
    clip_v = max(float(clip_value), 0.0)
    if clip_v <= 0.0:
        return x, 0
    if bool(track_hits):
        return _clip_tensor_abs(x, clip_v)
    # Fast path for performance benchmarking where hit statistics are not required.
    return torch.clamp(x, min=-clip_v, max=clip_v), 0


class _StochasticNoisePrefetcher:
    """Precompute Langevin random-force tensors in fixed-size chunks.

    This keeps statistical properties identical to per-step torch.randn while reducing
    Python-level RNG dispatch overhead during hot loops.
    """

    def __init__(
        self,
        shape: Tuple[int, ...],
        total_steps: int,
        device,
        dtype,
        noise_std: float,
        block_steps: int,
    ) -> None:
        self.shape = tuple(int(x) for x in shape)
        self.total_steps = max(int(total_steps), 0)
        self.device = device
        self.dtype = dtype
        self.noise_std = float(noise_std)
        self.block_steps = max(int(block_steps), 1)
        self.generated = 0
        self.block = None
        self.block_cursor = 0

    def reset(self) -> None:
        self.generated = 0
        self.block = None
        self.block_cursor = 0

    def next(self) -> Optional[torch.Tensor]:
        if self.total_steps <= 0 or self.generated >= self.total_steps:
            return None
        if self.block is None or self.block_cursor >= self.block.shape[0]:
            remaining = max(self.total_steps - self.generated, 0)
            if remaining <= 0:
                return None
            size = min(self.block_steps, remaining)
            batch = torch.randn((size, *self.shape), device=self.device, dtype=self.dtype)
            if self.noise_std != 0.0:
                batch = batch * self.noise_std
            self.block = batch
            self.block_cursor = 0
        item = self.block[self.block_cursor]
        self.block_cursor += 1
        self.generated += 1
        return item


def benchmark_simulation(
    target,
    steps=10000,
    use_ai_router=False,
    num_runs=3,
    warmup_steps=40,
    batch_replicas=1,
    ai_interval=1,
    enable_physics_filter=False,
    physics_filter_mode="rollback",
    physics_filter_max_energy_drift=0.015,
    physics_filter_max_momentum_drift=0.015,
    physics_filter_min_interatomic_distance=0.0,
    output_file="benchmark_results.csv",
    neighbor_settings=None,
    force_backend="auto",
    random_seed=None,
    ai_collect_aux=False,
    capture_final_coords=False,
    target_ai_interval_policy: Optional[Mapping[str, int]] = None,
    adaptive_ai_interval=False,
    ai_interval_min=1,
    ai_interval_max=0,
    ai_downshift_factor=2,
    ai_drift_disp_threshold=0.25,
    ai_drift_check_stride=1,
    ai_stable_upshift_window=0,
    ai_interval_min_ratio=0.0,
    target_ai_drift_threshold_policy: Optional[Mapping[str, float]] = None,
    ai_router_checkpoint: Optional[str] = None,
    ai_router_checkpoint_strict: bool = False,
    ai_runtime_mode: str = "eager",
    ai_disable_exploration: bool = False,
    ai_use_hip_graph: bool = False,
    ai_graph_warmup_iters: int = 2,
    initial_noise_scale: float = 0.0,
    force_clip: float = 200.0,
    ai_correction_clip: float = 100.0,
    disable_stochastic_noise: bool = False,
    precompute_stochastic_noise: bool = False,
    precompute_stochastic_noise_block_steps: int = 0,
    track_clip_hits: bool = True,
    profile_components: bool = True,
    sample_gpu_metrics: bool = True,
):
    """
    시뮬레이션 성능을 벤치마킹합니다.
    Args:
        target (str): 벤치마크할 타겟 이름
        steps (int): 벤치마크용 시뮬레이션 스텝 수
        use_ai_router (bool): AI 라우터 사용 여부
        num_runs (int): 평균을 내기 위한 실행 횟수
        warmup_steps (int): 측정 전에 수행할 워밍업 스텝 수
        batch_replicas (int): 병렬로 처리할 독립 트래젝토리 수
        ai_interval (int): AI correction 추론 간격 (MTS). 1이면 매 스텝.
        enable_physics_filter (bool): PhysicsGuard 기반 hard filter 사용 여부
        physics_filter_mode (str): rollback 또는 hard_fail
        output_file (str): 결과를 저장할 CSV 파일 이름
        random_seed (Optional[int]): 실험 재현성을 위한 랜덤 시드
        ai_collect_aux (bool): AI 오케스트레이터 aux/log 수집 여부 (False 권장, faster)
        capture_final_coords (bool): True면 마지막 run의 final coords를 결과에 포함
        target_ai_interval_policy (Optional[Mapping[str, int]]): target별 MTS interval override
        adaptive_ai_interval (bool): drift 기반 interval 자동 조절 사용 여부
        ai_interval_min (int): adaptive 모드에서 interval 하한
        ai_interval_max (int): adaptive 모드에서 interval 상한 (0이면 target/base interval)
        ai_downshift_factor (int): drift 발생 시 interval 축소 배수
        ai_drift_disp_threshold (float): drift 감지 평균 원자 변위 임계치
        ai_drift_check_stride (int): drift 체크 간격(스텝)
        ai_stable_upshift_window (int): 안정 상태 n스텝 지속 시 interval 1씩 복구 (0 비활성)
        ai_interval_min_ratio (float): target interval 비율 기반 adaptive 하한(0 비활성)
        target_ai_drift_threshold_policy (Optional[Mapping[str, float]]): target별 drift threshold override
        ai_router_checkpoint (Optional[str]): 학습된 AI Router 체크포인트(.pth) 경로
        ai_router_checkpoint_strict (bool): checkpoint load_state_dict strict 모드 여부
        ai_runtime_mode (str): AIRouter runtime mode ("eager", "scripted", "compiled", "onnx")
        ai_disable_exploration (bool): router exploration 완전 비활성화 여부
        ai_use_hip_graph (bool): CUDA/HIP graph로 AI 추론 replay 시도 여부
        ai_graph_warmup_iters (int): graph capture 전 warmup 반복 횟수
        initial_noise_scale (float): 각 run 시작 시 native 좌표에 추가할 가우시안 노이즈 스케일
        force_clip (float): total force 절대값 클립. <=0이면 비활성.
        ai_correction_clip (float): AI correction 절대값 클립. <=0이면 비활성.
        disable_stochastic_noise (bool): 적분 단계의 무작위 항을 비활성화해 속도/재현성 개선.
        track_clip_hits (bool): True면 clip hit 통계를 수집한다. False면 고속 경로 사용.
        profile_components (bool): True면 step별 component timing 분해를 기록한다.
        sample_gpu_metrics (bool): False면 GPU 메트릭 샘플링을 생략.
    Returns:
        results (dict): 성능 지표 딕셔너리
    """
    ai_interval_i = max(int(ai_interval), 1)
    ai_interval_i = resolve_target_ai_interval(target, ai_interval_i, target_ai_interval_policy)
    ai_interval_target_i = ai_interval_i
    ai_interval_min_i = max(int(ai_interval_min), 1)
    ai_interval_min_ratio_f = max(float(ai_interval_min_ratio), 0.0)
    if ai_interval_min_ratio_f > 0.0:
        ai_interval_min_i = max(ai_interval_min_i, int(np.ceil(float(ai_interval_target_i) * ai_interval_min_ratio_f)))
    ai_interval_max_i = int(ai_interval_max)
    if ai_interval_max_i <= 0:
        ai_interval_max_i = int(ai_interval_target_i)
    ai_interval_max_i = max(ai_interval_max_i, ai_interval_min_i)
    ai_downshift_factor_i = max(int(ai_downshift_factor), 2)
    ai_drift_check_stride_i = max(int(ai_drift_check_stride), 1)
    ai_stable_upshift_window_i = max(int(ai_stable_upshift_window), 0)
    ai_drift_disp_threshold_f = max(float(ai_drift_disp_threshold), 0.0)
    ai_drift_disp_threshold_eff = resolve_target_float_value(
        target=target,
        default_value=ai_drift_disp_threshold_f,
        policy=target_ai_drift_threshold_policy,
        floor=0.0,
    )
    adaptive_ai_interval_b = bool(adaptive_ai_interval)
    random_seed_i = None if random_seed is None else int(random_seed)
    ai_collect_aux_i = bool(ai_collect_aux)
    capture_final_coords_i = bool(capture_final_coords)
    initial_noise_scale_f = max(float(initial_noise_scale), 0.0)
    force_clip_f = max(float(force_clip), 0.0)
    ai_correction_clip_f = max(float(ai_correction_clip), 0.0)
    track_clip_hits_b = bool(track_clip_hits)
    profile_components_b = bool(profile_components)
    ai_runtime_mode_i = str(ai_runtime_mode).strip().lower()
    if ai_runtime_mode_i not in ("eager", "scripted", "compiled", "onnx"):
        ai_runtime_mode_i = "eager"
    ai_disable_exploration_b = bool(ai_disable_exploration)
    ai_use_hip_graph_b = bool(ai_use_hip_graph)
    ai_graph_warmup_iters_i = max(int(ai_graph_warmup_iters), 1)
    disable_stochastic_noise_b = bool(disable_stochastic_noise)
    precompute_stochastic_noise_b = bool(precompute_stochastic_noise)
    sample_gpu_metrics_b = bool(sample_gpu_metrics)
    precompute_stochastic_noise_block_steps_i = max(int(precompute_stochastic_noise_block_steps), 0)
    filter_mode = str(physics_filter_mode).strip().lower()
    if filter_mode not in ("rollback", "hard_fail"):
        raise ValueError("physics_filter_mode must be one of: rollback, hard_fail")

    logger.info(f"Benchmarking {target} for {steps} steps (AI Router: {use_ai_router}, Runs: {num_runs})")
    t_conf = ResearchConstants.CHALLENGES[target]
    n_res = t_conf['n_res']
    box_size = t_conf['box']

    # Setup system components (same as run_long_trajectory)
    top = TopologyFactory(n_res, t_conf['type'], box_size, config.DEVICE, target_name=target)
    neighbor_settings = dict(neighbor_settings or {})
    grid_spacing = float(neighbor_settings.get("grid_spacing", 12.0))
    sh = GridSpatialHash(box_size, grid_spacing, config.DEVICE, **{k: v for k, v in neighbor_settings.items() if k != "grid_spacing"})
    ff_params = {'d_e': 20.0, 'eps_solv': 25.0, 'sigma': 3.8, 'r0': 4.2}
    ff = ForceField(
        top,
        params=ff_params,
        neighbor_settings=neighbor_settings,
        force_backend=force_backend,
    ).to(config.DEVICE)
    integrator = LangevinIntegrator(dt=0.002, friction=1.0, kT=0.001987 * 300.0)

    ai_model = StrategicOrchestrator(config.DEVICE).to(config.DEVICE) if use_ai_router else None
    ai_enabled = ai_model is not None
    if ai_enabled and hasattr(ai_model, "set_router_runtime_mode"):
        ai_model.set_router_runtime_mode(ai_runtime_mode_i)
    if ai_enabled and hasattr(ai_model, "set_router_disable_exploration"):
        ai_model.set_router_disable_exploration(ai_disable_exploration_b)
    if ai_router_checkpoint is None:
        ai_ckpt_spec = ""
    else:
        ai_ckpt_spec = str(ai_router_checkpoint).strip()
        if ai_ckpt_spec.lower() in ("none", "null"):
            ai_ckpt_spec = ""
    ai_ckpt_path = ""
    ai_ckpt_policy = {"is_map": False, "map_path": None, "target_key": str(target), "selected_key": None}
    if ai_ckpt_spec:
        ai_ckpt_path, ai_ckpt_policy = _resolve_ai_router_checkpoint_path(
            checkpoint_spec=ai_ckpt_spec,
            target=str(target),
        )
    ai_ckpt_info: Dict[str, Any] = {
        "requested": bool(ai_ckpt_spec),
        "requested_spec": ai_ckpt_spec or None,
        "path": os.path.abspath(ai_ckpt_path) if ai_ckpt_path else None,
        "map_enabled": bool(ai_ckpt_policy.get("is_map", False)),
        "map_path": ai_ckpt_policy.get("map_path"),
        "map_selected_key": ai_ckpt_policy.get("selected_key"),
        "loaded": False,
        "state_source": None,
        "missing_keys_count": 0,
        "unexpected_keys_count": 0,
    }
    if ai_model is not None:
        if ai_ckpt_path:
            ai_ckpt_info = {
                "requested": True,
                **_load_ai_router_checkpoint(
                    ai_model=ai_model,
                    checkpoint_path=ai_ckpt_path,
                    strict=bool(ai_router_checkpoint_strict),
                ),
            }
            logger.info(
                "AI Router checkpoint loaded: %s (source=%s, missing=%d, unexpected=%d)",
                ai_ckpt_info.get("path"),
                ai_ckpt_info.get("state_source"),
                int(ai_ckpt_info.get("missing_keys_count", 0)),
                int(ai_ckpt_info.get("unexpected_keys_count", 0)),
            )
        ai_model.eval()
    elif ai_ckpt_path:
        logger.warning("ai_router_checkpoint was provided but ignored because use_ai_router=False")
    sim_params_batch = {'temp': 300.0, 'salt_conc': 0.1, 'pH': 7.0, 'ionic_strength': 0.15}

    # Initialize coordinates
    native_coords, seq = load_native_structure(target)
    batch_replicas_i = max(int(batch_replicas), 1)
    if native_coords is not None:
        c = (
            native_coords.clone()
            .detach()
            .unsqueeze(0)
            .repeat(batch_replicas_i, 1, 1)
            .to(config.DEVICE)
        )
    else:
        c = (
            torch.linspace(0, n_res - 1, n_res, device=config.DEVICE)
            .view(1, n_res, 1)
            .repeat(batch_replicas_i, 1, 3)
        )
    c_base = c.clone().detach()
    v_base = torch.zeros_like(c_base, device=config.DEVICE)
    warmup_steps_i = max(int(warmup_steps), 0)

    if precompute_stochastic_noise_b and getattr(integrator, "adaptive_dt", False):
        # Adaptive timestep changes would require per-step rescaling of the stochastic term.
        # Keep exact behavior when adaptive stepping is active.
        logger.warning("precompute_stochastic_noise is disabled: adaptive_dt=True")
        precompute_stochastic_noise_b = False

    times_per_run = []
    gpu_utils_per_run = []
    gpu_mem_utils_per_run = []
    gpu_backend_per_run = []
    cpu_utils_per_run = []
    ai_calls_per_run = []
    ai_reuse_steps_per_run = []
    ai_forced_eval_by_drift_per_run = []
    ai_interval_downshifts_per_run = []
    ai_interval_upshifts_per_run = []
    ai_interval_final_per_run = []
    ai_interval_active_mean_per_run = []
    ai_active_modules_per_eval_per_run = []
    ai_active_module_ratio_per_eval_per_run = []
    ai_uncertainty_fallback_steps_per_run = []
    ai_uncertainty_fallback_ratio_per_run = []
    ai_uncertainty_score_per_eval_per_run = []
    ai_correction_clip_hits_per_run = []
    total_force_clip_hits_per_run = []
    physics_violations_per_run = []
    physics_recoveries_per_run = []
    ai_graph_enabled_per_run = []
    ai_graph_fallback_reason_per_run = []
    component_breakdown = {
        "neighbor_sec": 0.0,
        "force_sec": 0.0,
        "ai_sec": 0.0,
        "ai_infer_sec": 0.0,
        "integrator_sec": 0.0,
    }
    final_coords_last = None

    noise_std_default = torch.sqrt(2.0 * integrator.gamma * integrator.kT * integrator.dt)
    noise_std_default_f = float(noise_std_default.item()) if torch.is_tensor(noise_std_default) else float(noise_std_default)
    for run in range(num_runs):
        logger.info(f"  Run {run+1}/{num_runs}")
        c = c_base.clone()
        v = v_base.clone()
        noise_tensor = torch.zeros_like(v) if disable_stochastic_noise_b else None
        warmup_noise_prefetcher: Optional[_StochasticNoisePrefetcher] = None
        main_noise_prefetcher: Optional[_StochasticNoisePrefetcher] = None
        if precompute_stochastic_noise_b and (not disable_stochastic_noise_b):
            warmup_noise_prefetcher = _StochasticNoisePrefetcher(
                shape=tuple(v.shape),
                total_steps=max(int(warmup_steps_i), 0),
                device=v.device,
                dtype=v.dtype,
                noise_std=noise_std_default_f,
                block_steps=(
                    precompute_stochastic_noise_block_steps_i
                    if precompute_stochastic_noise_block_steps_i > 0
                    else max(1, min(int(warmup_steps_i), 1024))
                ),
            )
            main_noise_prefetcher = _StochasticNoisePrefetcher(
                shape=tuple(v.shape),
                total_steps=int(steps),
                device=v.device,
                dtype=v.dtype,
                noise_std=noise_std_default_f,
                block_steps=(
                    precompute_stochastic_noise_block_steps_i
                    if precompute_stochastic_noise_block_steps_i > 0
                    else max(1, min(int(steps), 1024))
                ),
            )
        if random_seed_i is not None:
            seed_run = int(random_seed_i + run)
            torch.manual_seed(seed_run)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed_run)
        if initial_noise_scale_f > 0.0:
            c = c + torch.randn_like(c) * initial_noise_scale_f
        _sync_if_cuda()
        ai_calls_run = 0
        ai_reuse_steps_run = 0
        ai_forced_eval_by_drift_run = 0
        ai_interval_downshifts_run = 0
        ai_interval_upshifts_run = 0
        physics_violations_run = 0
        physics_recoveries_run = 0
        ai_active_modules_accum_run = 0.0
        ai_active_modules_count_run = 0
        ai_uncertainty_fallback_steps_run = 0
        ai_uncertainty_fallback_ratio_accum_run = 0.0
        ai_uncertainty_score_accum_run = 0.0
        ai_uncertainty_eval_count_run = 0
        ai_correction_clip_hits_run = 0
        total_force_clip_hits_run = 0
        current_ai_interval = int(ai_interval_target_i)
        ai_interval_accum = 0
        ai_interval_accum_count = 0
        physics_guard = None
        zero_force_for_guard = None
        if enable_physics_filter:
            physics_guard = PhysicsGuard(
                max_energy_drift=float(physics_filter_max_energy_drift),
                max_momentum_drift=float(physics_filter_max_momentum_drift),
                min_interatomic_distance=float(physics_filter_min_interatomic_distance),
                enable_local_teacher=False,
                enable_momentum_check=False,
            )
            physics_guard.set_system_size(n_res)
            if not ai_enabled:
                zero_force_for_guard = torch.zeros_like(c)

        cached_ai_corr_warm = None
        if warmup_steps_i > 0:
            with torch.inference_mode():
                for warm_step in range(warmup_steps_i):
                    needs_ai_eval = bool(
                        ai_enabled
                        and (cached_ai_corr_warm is None or (warm_step % ai_interval_i == 0))
                    )
                    nb_warm = None
                    if needs_ai_eval:
                        nb_warm = sh.get_neighbor_data(c)

                    f_core_warm, pe_warm = ff.compute(c, nb_warm)
                    f_total_warm = f_core_warm
                    f_ai_corr_warm = None
                    if ai_enabled:
                        if needs_ai_eval:
                            ai_top_warm, ai_nb_warm, ai_pe_warm, ai_sim_warm = (
                                _build_checkpoint_compatible_ai_inputs(c, top, sim_params_batch)
                            )
                            f_ai_corr_warm, _ = ai_model(
                                c,
                                ai_top_warm,
                                ai_nb_warm,
                                ai_pe_warm,
                                ai_sim_warm,
                                collect_aux=ai_collect_aux_i,
                            )
                            f_ai_corr_warm, ai_clip_hits_warm = _clip_tensor_abs_runtime(
                                f_ai_corr_warm,
                                ai_correction_clip_f,
                                track_clip_hits_b,
                            )
                            ai_correction_clip_hits_run += int(ai_clip_hits_warm)
                            cached_ai_corr_warm = f_ai_corr_warm
                            ai_calls_run += 1
                        else:
                            f_ai_corr_warm = cached_ai_corr_warm
                            ai_reuse_steps_run += 1
                        f_total_warm = f_core_warm + f_ai_corr_warm
                    elif zero_force_for_guard is not None:
                        f_ai_corr_warm = zero_force_for_guard
                    f_total_warm, total_clip_hits_warm = _clip_tensor_abs_runtime(
                        f_total_warm,
                        force_clip_f,
                        track_clip_hits_b,
                    )
                    total_force_clip_hits_run += int(total_clip_hits_warm)

                    c_prev = c.clone() if physics_guard is not None else None
                    v_prev = v.clone() if physics_guard is not None else None
                    if disable_stochastic_noise_b:
                        v_next, c_next = integrator.step(c, v, f_total_warm, noise=noise_tensor)
                    elif warmup_noise_prefetcher is not None:
                        v_next, c_next = integrator.step(
                            c,
                            v,
                            f_total_warm,
                            noise=warmup_noise_prefetcher.next(),
                        )
                    else:
                        v_next, c_next = integrator.step(c, v, f_total_warm)
                    if physics_guard is not None:
                        is_ok, msg = physics_guard.check_conservation(
                            c_next,
                            v_next,
                            pe_warm,
                            f_core_warm,
                            f_ai_corr_warm if f_ai_corr_warm is not None else zero_force_for_guard,
                            warm_step,
                        )
                        if not is_ok:
                            physics_violations_run += 1
                            if filter_mode == "hard_fail":
                                raise RuntimeError(f"Physics filter hard fail during warmup: {msg}")
                            c_next, v_next = physics_guard.auto_recover(c_next, v_next, c_prev, v_prev)
                            physics_recoveries_run += 1
                    c, v = c_next, v_next
            _sync_if_cuda()
            # warmup loop runs in inference_mode; clone to regular tensors before
            # optional graph pre-capture work executed outside inference_mode.
            c = c.clone().detach()
            v = v.clone().detach()
            _reset_forcefield_runtime_caches(ff)

        ai_graph_runner = _AIGraphRunner()
        if ai_enabled and ai_use_hip_graph_b:
            try:
                ai_top_graph, ai_nb_graph, ai_pe_graph, ai_sim_graph = (
                    _build_checkpoint_compatible_ai_inputs(c, top, sim_params_batch)
                )
                ai_graph_runner = _build_ai_graph_runner(
                    ai_model=ai_model,
                    top=ai_top_graph,
                    sim_params_batch=ai_sim_graph,
                    c_example=c,
                    nb_example=ai_nb_graph,
                    pe_example=ai_pe_graph,
                    collect_aux=ai_collect_aux_i,
                    warmup_iters=ai_graph_warmup_iters_i,
                )
            except Exception as exc:
                ai_graph_runner.enabled = False
                ai_graph_runner.reason = f"{type(exc).__name__}: {exc}"

        has_ai_active_mask = bool(ai_enabled and hasattr(ai_model, "last_active_mask"))
        has_ai_uncertainty_rate = bool(
            ai_enabled and hasattr(ai_model, "last_uncertainty_fallback_rate")
        )
        ai_fastpath_enabled = bool(
            ai_enabled
            and (physics_guard is None)
            and (not profile_components_b)
            and (not adaptive_ai_interval_b)
            and (not ai_collect_aux_i)
        )

        start_gpu = (
            _sample_gpu_metrics()
            if sample_gpu_metrics_b
            else {
                "util_percent": 0.0,
                "mem_util_percent": 0.0,
                "backend": "disabled",
                "ok": False,
            }
        )
        start_time = time.perf_counter()  # Use perf_counter for higher resolution timing
        initial_cpu_util = psutil.cpu_percent(interval=None)

        cached_ai_corr = None
        last_ai_eval_step = -1
        coords_at_last_ai_eval = None
        stable_steps_since_downshift = 0
        with torch.inference_mode():
            # Hot-path: physics-only benchmark with lightweight timing/metrics.
            if (not ai_enabled) and (physics_guard is None) and (not profile_components_b):
                for _ in range(steps):
                    f_core, _ = ff.compute(c, None)
                    if force_clip_f > 0.0:
                        f_total, total_clip_hits = _clip_tensor_abs_runtime(
                            f_core,
                            force_clip_f,
                            track_clip_hits_b,
                        )
                        total_force_clip_hits_run += int(total_clip_hits)
                    else:
                        f_total = f_core
                    if disable_stochastic_noise_b:
                        v, c = integrator.step(c, v, f_total, noise=noise_tensor)
                    elif main_noise_prefetcher is not None:
                        v, c = integrator.step(
                            c,
                            v,
                            f_total,
                            noise=main_noise_prefetcher.next(),
                        )
                    else:
                        v, c = integrator.step(c, v, f_total)
            elif ai_fastpath_enabled:
                # Hot-path: fixed-interval AI correction without adaptive drift checks.
                for step in range(steps):
                    ai_interval_accum += int(current_ai_interval)
                    ai_interval_accum_count += 1

                    steps_since_last_eval = (
                        step - last_ai_eval_step
                        if last_ai_eval_step >= 0
                        else int(current_ai_interval)
                    )
                    needs_ai_eval = bool(
                        (cached_ai_corr is None)
                        or (steps_since_last_eval >= int(current_ai_interval))
                    )

                    nb = sh.get_neighbor_data(c) if needs_ai_eval else None
                    f_core, pe = ff.compute(c, nb)
                    if needs_ai_eval:
                        ai_top, ai_nb, ai_pe, ai_sim = _build_checkpoint_compatible_ai_inputs(
                            c, top, sim_params_batch
                        )
                        f_ai_corr = None
                        if ai_graph_runner.enabled:
                            f_ai_corr = ai_graph_runner.run(c, ai_nb, ai_pe)
                            if f_ai_corr is None:
                                ai_graph_runner.enabled = False
                                if ai_graph_runner.reason == "ok":
                                    ai_graph_runner.reason = "shape_mismatch_or_runtime_fallback"
                        if f_ai_corr is None:
                            f_ai_corr, _ = ai_model(
                                c,
                                ai_top,
                                ai_nb,
                                ai_pe,
                                ai_sim,
                                collect_aux=False,
                            )
                        if ai_correction_clip_f > 0.0:
                            f_ai_corr, ai_clip_hits = _clip_tensor_abs_runtime(
                                f_ai_corr,
                                ai_correction_clip_f,
                                track_clip_hits_b,
                            )
                            ai_correction_clip_hits_run += int(ai_clip_hits)
                        cached_ai_corr = f_ai_corr
                        last_ai_eval_step = int(step)
                        ai_calls_run += 1

                        if has_ai_active_mask:
                            active_mask = getattr(ai_model, "last_active_mask")
                            if isinstance(active_mask, torch.Tensor):
                                try:
                                    active_cnt = float(active_mask.float().sum(dim=-1).mean().item())
                                    ai_active_modules_accum_run += active_cnt
                                    ai_active_modules_count_run += 1
                                except Exception:
                                    pass
                        if has_ai_uncertainty_rate:
                            try:
                                fallback_rate = float(
                                    getattr(ai_model, "last_uncertainty_fallback_rate", 0.0)
                                )
                            except Exception:
                                fallback_rate = 0.0
                            ai_uncertainty_fallback_ratio_accum_run += fallback_rate
                            ai_uncertainty_eval_count_run += 1
                            if fallback_rate > 0.0:
                                ai_uncertainty_fallback_steps_run += 1
                            try:
                                score_mean = float(
                                    getattr(ai_model, "last_uncertainty_score_mean", 0.0)
                                )
                            except Exception:
                                score_mean = 0.0
                            ai_uncertainty_score_accum_run += score_mean
                    else:
                        ai_reuse_steps_run += 1

                    f_total = f_core + cached_ai_corr
                    if force_clip_f > 0.0:
                        f_total, total_clip_hits = _clip_tensor_abs_runtime(
                            f_total,
                            force_clip_f,
                            track_clip_hits_b,
                        )
                        total_force_clip_hits_run += int(total_clip_hits)

                    if disable_stochastic_noise_b:
                        v, c = integrator.step(c, v, f_total, noise=noise_tensor)
                    elif main_noise_prefetcher is not None:
                        v, c = integrator.step(
                            c,
                            v,
                            f_total,
                            noise=main_noise_prefetcher.next(),
                        )
                    else:
                        v, c = integrator.step(c, v, f_total)
            else:
                for step in range(steps):
                    if profile_components_b:
                        t0 = time.perf_counter()
                    if ai_enabled:
                        ai_interval_accum += int(current_ai_interval)
                        ai_interval_accum_count += 1
                    steps_since_last_eval = step - last_ai_eval_step if last_ai_eval_step >= 0 else int(current_ai_interval)
                    needs_ai_eval = bool(
                        ai_enabled and (cached_ai_corr is None or (steps_since_last_eval >= int(current_ai_interval)))
                    )
                    if (
                        ai_enabled
                        and adaptive_ai_interval_b
                        and not needs_ai_eval
                        and coords_at_last_ai_eval is not None
                        and (step % ai_drift_check_stride_i == 0)
                    ):
                        displacement = torch.norm(c - coords_at_last_ai_eval, dim=-1).mean().item()
                        if displacement > ai_drift_disp_threshold_eff:
                            needs_ai_eval = True
                            ai_forced_eval_by_drift_run += 1
                            new_interval = max(
                                int(ai_interval_min_i),
                                int(current_ai_interval) // int(ai_downshift_factor_i),
                            )
                            if new_interval < int(current_ai_interval):
                                current_ai_interval = int(new_interval)
                                ai_interval_downshifts_run += 1
                            stable_steps_since_downshift = 0
                        else:
                            stable_steps_since_downshift += 1
                            if (
                                ai_stable_upshift_window_i > 0
                                and stable_steps_since_downshift >= ai_stable_upshift_window_i
                                and int(current_ai_interval) < int(ai_interval_max_i)
                            ):
                                current_ai_interval = int(min(int(current_ai_interval) + 1, int(ai_interval_max_i)))
                                ai_interval_upshifts_run += 1
                                stable_steps_since_downshift = 0
                    nb = None
                    if needs_ai_eval:
                        nb = sh.get_neighbor_data(c)
                    if profile_components_b:
                        t1 = time.perf_counter()

                    f_core, pe = ff.compute(c, nb)
                    if profile_components_b:
                        t2 = time.perf_counter()

                    f_total = f_core
                    f_ai_corr = None
                    if ai_enabled:
                        if needs_ai_eval:
                            ai_top, ai_nb, ai_pe, ai_sim = (
                                _build_checkpoint_compatible_ai_inputs(c, top, sim_params_batch)
                            )
                            t_ai_infer_start = time.perf_counter()
                            f_ai_corr = None
                            if ai_graph_runner.enabled:
                                f_ai_corr = ai_graph_runner.run(c, ai_nb, ai_pe)
                                if f_ai_corr is None:
                                    ai_graph_runner.enabled = False
                                    if ai_graph_runner.reason == "ok":
                                        ai_graph_runner.reason = "shape_mismatch_or_runtime_fallback"
                            if f_ai_corr is None:
                                f_ai_corr, _ = ai_model(
                                    c,
                                    ai_top,
                                    ai_nb,
                                    ai_pe,
                                    ai_sim,
                                    collect_aux=ai_collect_aux_i,
                                )
                            component_breakdown["ai_infer_sec"] += max(time.perf_counter() - t_ai_infer_start, 0.0)
                            f_ai_corr, ai_clip_hits = _clip_tensor_abs_runtime(
                                f_ai_corr,
                                ai_correction_clip_f,
                                track_clip_hits_b,
                            )
                            ai_correction_clip_hits_run += int(ai_clip_hits)
                            cached_ai_corr = f_ai_corr
                            last_ai_eval_step = int(step)
                            if adaptive_ai_interval_b:
                                coords_at_last_ai_eval = c.detach().clone()
                            ai_calls_run += 1
                            if has_ai_active_mask:
                                active_mask = getattr(ai_model, "last_active_mask")
                                if isinstance(active_mask, torch.Tensor):
                                    try:
                                        active_cnt = float(active_mask.float().sum(dim=-1).mean().item())
                                        ai_active_modules_accum_run += active_cnt
                                        ai_active_modules_count_run += 1
                                    except Exception:
                                        pass
                            if has_ai_uncertainty_rate:
                                try:
                                    fallback_rate = float(
                                        getattr(ai_model, "last_uncertainty_fallback_rate", 0.0)
                                    )
                                except Exception:
                                    fallback_rate = 0.0
                                ai_uncertainty_fallback_ratio_accum_run += fallback_rate
                                ai_uncertainty_eval_count_run += 1
                                if fallback_rate > 0.0:
                                    ai_uncertainty_fallback_steps_run += 1
                                try:
                                    score_mean = float(
                                        getattr(ai_model, "last_uncertainty_score_mean", 0.0)
                                    )
                                except Exception:
                                    score_mean = 0.0
                                ai_uncertainty_score_accum_run += score_mean
                        else:
                            f_ai_corr = cached_ai_corr
                            ai_reuse_steps_run += 1
                        f_total = f_core + f_ai_corr
                    elif zero_force_for_guard is not None:
                        f_ai_corr = zero_force_for_guard
                    f_total, total_clip_hits = _clip_tensor_abs_runtime(
                        f_total,
                        force_clip_f,
                        track_clip_hits_b,
                    )
                    total_force_clip_hits_run += int(total_clip_hits)
                    if profile_components_b:
                        t3 = time.perf_counter()

                    c_prev = c.clone() if physics_guard is not None else None
                    v_prev = v.clone() if physics_guard is not None else None
                    if disable_stochastic_noise_b:
                        v_new, c_new = integrator.step(c, v, f_total, noise=noise_tensor)
                    elif main_noise_prefetcher is not None:
                        v_new, c_new = integrator.step(
                            c,
                            v,
                            f_total,
                            noise=main_noise_prefetcher.next(),
                        )
                    else:
                        v_new, c_new = integrator.step(c, v, f_total)
                    if physics_guard is not None:
                        is_ok, msg = physics_guard.check_conservation(
                            c_new,
                            v_new,
                            pe,
                            f_core,
                            f_ai_corr if f_ai_corr is not None else zero_force_for_guard,
                            step,
                        )
                        if not is_ok:
                            physics_violations_run += 1
                            if filter_mode == "hard_fail":
                                raise RuntimeError(f"Physics filter hard fail: {msg}")
                            c_new, v_new = physics_guard.auto_recover(c_new, v_new, c_prev, v_prev)
                            physics_recoveries_run += 1
                    c, v = c_new, v_new
                    if profile_components_b:
                        t4 = time.perf_counter()
                        component_breakdown["neighbor_sec"] += (t1 - t0)
                        component_breakdown["force_sec"] += (t2 - t1)
                        component_breakdown["ai_sec"] += (t3 - t2)
                        component_breakdown["integrator_sec"] += (t4 - t3)

        _sync_if_cuda()
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        times_per_run.append(elapsed_time)
        if capture_final_coords_i:
            final_coords_last = c.detach().clone().cpu().numpy()

        end_gpu = (
            _sample_gpu_metrics()
            if sample_gpu_metrics_b
            else {
                "util_percent": start_gpu.get("util_percent", 0.0),
                "mem_util_percent": start_gpu.get("mem_util_percent", 0.0),
                "backend": start_gpu.get("backend", "disabled"),
                "ok": False,
            }
        )
        run_gpu_utils = [
            float(start_gpu.get("util_percent", 0.0)),
            float(end_gpu.get("util_percent", 0.0)),
        ]
        run_gpu_mems = [
            float(start_gpu.get("mem_util_percent", 0.0)),
            float(end_gpu.get("mem_util_percent", 0.0)),
        ]
        run_gpu_backends = [str(start_gpu.get("backend", "none")), str(end_gpu.get("backend", "none"))]
        final_cpu_util = psutil.cpu_percent(interval=None)

        if run_gpu_utils:
            gpu_utils_per_run.append(sum(run_gpu_utils) / len(run_gpu_utils))
        else:
            gpu_utils_per_run.append(0.0)
        if run_gpu_mems:
            gpu_mem_utils_per_run.append(sum(run_gpu_mems) / len(run_gpu_mems))
        else:
            gpu_mem_utils_per_run.append(0.0)
        if run_gpu_backends:
            backend_counts = {}
            for name in run_gpu_backends:
                backend_counts[name] = backend_counts.get(name, 0) + 1
            gpu_backend_per_run.append(max(backend_counts, key=backend_counts.get))
        else:
            gpu_backend_per_run.append("none")
        cpu_utils_per_run.append((initial_cpu_util + final_cpu_util) / 2.0)
        ai_calls_per_run.append(ai_calls_run)
        ai_reuse_steps_per_run.append(ai_reuse_steps_run)
        ai_forced_eval_by_drift_per_run.append(ai_forced_eval_by_drift_run)
        ai_interval_downshifts_per_run.append(ai_interval_downshifts_run)
        ai_interval_upshifts_per_run.append(ai_interval_upshifts_run)
        ai_interval_final_per_run.append(float(current_ai_interval))
        ai_interval_active_mean_per_run.append(
            float(ai_interval_accum) / max(float(ai_interval_accum_count), 1.0)
        )
        ai_active_modules_per_eval_per_run.append(
            float(ai_active_modules_accum_run) / max(float(ai_active_modules_count_run), 1.0)
        )
        ai_active_module_ratio_per_eval_per_run.append(
            (
                float(ai_active_modules_accum_run) / max(float(ai_active_modules_count_run), 1.0)
            )
            / max(float(getattr(ai_model, "num_modules", 1)) if ai_model is not None else 1.0, 1.0)
        )
        ai_uncertainty_fallback_steps_per_run.append(float(ai_uncertainty_fallback_steps_run))
        ai_uncertainty_fallback_ratio_per_run.append(
            float(ai_uncertainty_fallback_ratio_accum_run) / max(float(ai_uncertainty_eval_count_run), 1.0)
        )
        ai_uncertainty_score_per_eval_per_run.append(
            float(ai_uncertainty_score_accum_run) / max(float(ai_uncertainty_eval_count_run), 1.0)
        )
        ai_correction_clip_hits_per_run.append(float(ai_correction_clip_hits_run))
        total_force_clip_hits_per_run.append(float(total_force_clip_hits_run))
        physics_violations_per_run.append(physics_violations_run)
        physics_recoveries_per_run.append(physics_recoveries_run)
        ai_graph_enabled_per_run.append(1.0 if ai_graph_runner.enabled else 0.0)
        ai_graph_fallback_reason_per_run.append(str(ai_graph_runner.reason))

    avg_time = sum(times_per_run) / len(times_per_run)
    effective_steps = max(int(steps * num_runs * batch_replicas_i), 1)
    steps_per_sec = effective_steps / sum(times_per_run)
    avg_gpu_util = (sum(gpu_utils_per_run) / len(gpu_utils_per_run)) if gpu_utils_per_run else 0.0
    avg_gpu_mem_util = (sum(gpu_mem_utils_per_run) / len(gpu_mem_utils_per_run)) if gpu_mem_utils_per_run else 0.0
    gpu_backend_name = "none"
    if gpu_backend_per_run:
        backend_counts = {}
        for name in gpu_backend_per_run:
            backend_counts[name] = backend_counts.get(name, 0) + 1
        gpu_backend_name = max(backend_counts, key=backend_counts.get)
    avg_cpu_util = sum(cpu_utils_per_run) / len(cpu_utils_per_run) # Average across runs

    # Memory Usage (Peak, if possible)
    # This is harder to measure accurately during the simulation without pausing
    # psutil.virtual_memory().percent gives current usage, not peak during simulation
    # peak_memory_usage = psutil.virtual_memory().percent # Not truly peak during sim

    results = {
        'target': target,
        'n_res': n_res,
        'steps': steps,
        'warmup_steps': int(warmup_steps),
        'batch_replicas': int(batch_replicas_i),
        'ai_interval': int(ai_interval_i),
        'target_ai_interval_policy_applied': bool(target_ai_interval_policy is not None and target in target_ai_interval_policy),
        'ai_interval_target': int(ai_interval_target_i),
        'adaptive_ai_interval': bool(adaptive_ai_interval_b),
        'ai_interval_min': int(ai_interval_min_i),
        'ai_interval_min_ratio': float(ai_interval_min_ratio_f),
        'ai_interval_max': int(ai_interval_max_i),
        'ai_downshift_factor': int(ai_downshift_factor_i),
        'ai_drift_disp_threshold': float(ai_drift_disp_threshold_eff),
        'target_ai_drift_threshold_policy_applied': bool(
            target_ai_drift_threshold_policy is not None and target in target_ai_drift_threshold_policy
        ),
        'ai_drift_check_stride': int(ai_drift_check_stride_i),
        'ai_stable_upshift_window': int(ai_stable_upshift_window_i),
        'use_ai_router': use_ai_router,
        'ai_runtime_mode': ai_runtime_mode_i,
        'ai_disable_exploration': bool(ai_disable_exploration_b),
        'ai_use_hip_graph': bool(ai_use_hip_graph_b),
        'ai_graph_warmup_iters': int(ai_graph_warmup_iters_i),
        'num_runs': num_runs,
        'force_backend': force_backend,
        'enable_physics_filter': bool(enable_physics_filter),
        'physics_filter_mode': filter_mode,
        'physics_filter_max_energy_drift': float(physics_filter_max_energy_drift),
        'physics_filter_max_momentum_drift': float(physics_filter_max_momentum_drift),
        'physics_filter_min_interatomic_distance': float(physics_filter_min_interatomic_distance),
        'avg_time_per_run_sec': avg_time,
        'disable_stochastic_noise': bool(disable_stochastic_noise_b),
        'precompute_stochastic_noise': bool(precompute_stochastic_noise_b),
        'precompute_stochastic_noise_block_steps': int(
            precompute_stochastic_noise_block_steps_i
            if precompute_stochastic_noise_b
            else 0
        ),
        'stochastic_noise_std': float(noise_std_default_f),
        'avg_throughput_steps_per_sec': steps_per_sec,
        'avg_time_per_step_ms': (avg_time / max(int(steps * batch_replicas_i), 1)) * 1000,
        'avg_gpu_util_percent': avg_gpu_util,
        'peak_gpu_memory_util_percent': avg_gpu_mem_util,
        'gpu_metrics_backend': gpu_backend_name,
        'avg_cpu_util_percent': avg_cpu_util,
        'avg_ai_inference_calls_per_run': float(sum(ai_calls_per_run) / max(len(ai_calls_per_run), 1)),
        'avg_ai_reuse_steps_per_run': float(sum(ai_reuse_steps_per_run) / max(len(ai_reuse_steps_per_run), 1)),
        'avg_ai_forced_eval_by_drift_per_run': float(sum(ai_forced_eval_by_drift_per_run) / max(len(ai_forced_eval_by_drift_per_run), 1)),
        'avg_ai_interval_downshifts_per_run': float(sum(ai_interval_downshifts_per_run) / max(len(ai_interval_downshifts_per_run), 1)),
        'avg_ai_interval_upshifts_per_run': float(sum(ai_interval_upshifts_per_run) / max(len(ai_interval_upshifts_per_run), 1)),
        'avg_ai_interval_final_per_run': float(sum(ai_interval_final_per_run) / max(len(ai_interval_final_per_run), 1)),
        'avg_ai_interval_active_per_step': float(sum(ai_interval_active_mean_per_run) / max(len(ai_interval_active_mean_per_run), 1)),
        'avg_ai_active_modules_per_eval': float(
            sum(ai_active_modules_per_eval_per_run) / max(len(ai_active_modules_per_eval_per_run), 1)
        ),
        'avg_ai_active_module_ratio_per_eval': float(
            sum(ai_active_module_ratio_per_eval_per_run) / max(len(ai_active_module_ratio_per_eval_per_run), 1)
        ),
        'avg_ai_uncertainty_fallback_steps_per_run': float(
            sum(ai_uncertainty_fallback_steps_per_run) / max(len(ai_uncertainty_fallback_steps_per_run), 1)
        ),
        'avg_ai_uncertainty_fallback_ratio_per_eval': float(
            sum(ai_uncertainty_fallback_ratio_per_run) / max(len(ai_uncertainty_fallback_ratio_per_run), 1)
        ),
        'avg_ai_uncertainty_score_per_eval': float(
            sum(ai_uncertainty_score_per_eval_per_run) / max(len(ai_uncertainty_score_per_eval_per_run), 1)
        ),
        'ai_router_num_modules': int(getattr(ai_model, "num_modules", 0)) if ai_model is not None else 0,
        'force_clip': float(force_clip_f),
        'ai_correction_clip': float(ai_correction_clip_f),
        'avg_ai_correction_clip_hits_per_run': float(
            sum(ai_correction_clip_hits_per_run) / max(len(ai_correction_clip_hits_per_run), 1)
        ),
        'avg_total_force_clip_hits_per_run': float(
            sum(total_force_clip_hits_per_run) / max(len(total_force_clip_hits_per_run), 1)
        ),
        'avg_physics_violations_per_run': float(sum(physics_violations_per_run) / max(len(physics_violations_per_run), 1)),
        'avg_physics_recoveries_per_run': float(sum(physics_recoveries_per_run) / max(len(physics_recoveries_per_run), 1)),
        'ai_router_checkpoint_path': ai_ckpt_info.get("path"),
        'ai_router_checkpoint_requested': bool(ai_ckpt_info.get("requested", False)),
        'ai_router_checkpoint_loaded': bool(ai_ckpt_info.get("loaded", False)),
        'ai_router_checkpoint_strict': bool(ai_router_checkpoint_strict),
        'ai_router_checkpoint_state_source': ai_ckpt_info.get("state_source"),
        'ai_router_checkpoint_missing_keys_count': int(ai_ckpt_info.get("missing_keys_count", 0)),
        'ai_router_checkpoint_unexpected_keys_count': int(ai_ckpt_info.get("unexpected_keys_count", 0)),
        'ai_router_script_error': getattr(getattr(ai_model, "ai_router", None), "_script_router_error", None)
        if ai_model is not None
        else None,
        'avg_ai_graph_enabled_flag': float(sum(ai_graph_enabled_per_run) / max(len(ai_graph_enabled_per_run), 1)),
        'ai_graph_last_reason': (ai_graph_fallback_reason_per_run[-1] if ai_graph_fallback_reason_per_run else "unused"),
        'initial_noise_scale': float(initial_noise_scale_f),
        'neighbor_time_per_step_ms': (component_breakdown["neighbor_sec"] / max(effective_steps, 1)) * 1000.0,
        'force_time_per_step_ms': (component_breakdown["force_sec"] / max(effective_steps, 1)) * 1000.0,
        'ai_time_per_step_ms': (
            component_breakdown["ai_sec"] / max(effective_steps, 1)
            if component_breakdown["ai_sec"] > 0.0
            else component_breakdown["ai_infer_sec"] / max(effective_steps, 1)
        ) * 1000.0,
        'ai_inference_time_per_step_ms': (component_breakdown["ai_infer_sec"] / max(effective_steps, 1)) * 1000.0,
        'integrator_time_per_step_ms': (component_breakdown["integrator_sec"] / max(effective_steps, 1)) * 1000.0,
        # 'peak_memory_usage_percent': peak_memory_usage, # Currently not accurately measured
    }
    if capture_final_coords_i and final_coords_last is not None:
        results["final_coords"] = final_coords_last
    logger.info(f"  Avg Throughput: {steps_per_sec:.2f} steps/sec, Avg Time per Step: {(avg_time / steps)*1000:.3f} ms")
    logger.info(
        "  Breakdown per step (ms): neighbor=%.3f force=%.3f ai=%.3f integrator=%.3f",
        results["neighbor_time_per_step_ms"],
        results["force_time_per_step_ms"],
        results["ai_time_per_step_ms"],
        results["integrator_time_per_step_ms"],
    )
    if use_ai_router:
        logger.info(
            "  AI MTS: interval(target=%d, active=%.2f, final=%.2f), avg inference calls/run=%.1f, avg reuse steps/run=%.1f",
            int(ai_interval_target_i),
            results["avg_ai_interval_active_per_step"],
            results["avg_ai_interval_final_per_run"],
            results["avg_ai_inference_calls_per_run"],
            results["avg_ai_reuse_steps_per_run"],
        )
        if adaptive_ai_interval_b:
            logger.info(
                "  AI MTS adaptive: drift_forced=%.2f downshift=%.2f upshift=%.2f (threshold=%.3f)",
                results["avg_ai_forced_eval_by_drift_per_run"],
                results["avg_ai_interval_downshifts_per_run"],
                results["avg_ai_interval_upshifts_per_run"],
                float(ai_drift_disp_threshold_eff),
            )
        logger.info(
            "  AI runtime: mode=%s, disable_exploration=%s, graph=%s (enabled_avg=%.2f, last_reason=%s)",
            ai_runtime_mode_i,
            str(bool(ai_disable_exploration_b)),
            str(bool(ai_use_hip_graph_b)),
            float(results.get("avg_ai_graph_enabled_flag", 0.0)),
            str(results.get("ai_graph_last_reason", "unused")),
        )
    if enable_physics_filter:
        logger.info(
            "  Physics filter: mode=%s, avg violations/run=%.2f, avg recoveries/run=%.2f",
            filter_mode,
            results["avg_physics_violations_per_run"],
            results["avg_physics_recoveries_per_run"],
        )
    logger.info(
        f"  Avg GPU Util: {avg_gpu_util:.1f}%, "
        f"Peak GPU Mem Util: {avg_gpu_mem_util:.1f}% "
        f"(source={gpu_backend_name})"
    )
    logger.info(f"  Avg CPU Util: {avg_cpu_util:.1f}%")

    # Append to CSV file
    if output_file:
        output_file_i = os.path.abspath(output_file)
        output_dir = os.path.dirname(output_file_i)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        row_for_csv = {
            k: v
            for k, v in results.items()
            if not isinstance(v, (np.ndarray, torch.Tensor, dict, list, tuple))
        }
        df_new = pd.DataFrame([row_for_csv])
        header_needed = not os.path.exists(output_file_i)
        df_new.to_csv(output_file_i, mode="a", index=False, header=header_needed)
        logger.info(f"  Results appended to {output_file_i}")

    return results

def run_benchmark_suite(targets_list, steps_list=[10000], ai_options=[False, True]):
    """
    다양한 설정에 대한 벤치마크 스위트를 실행합니다.
    """
    all_results = []
    for target in targets_list:
        for steps in steps_list:
            for use_ai in ai_options:
                result = benchmark_simulation(target, steps=steps, use_ai_router=use_ai)
                all_results.append(result)

    df = pd.DataFrame(all_results)
    output_file = "benchmark_results.csv"
    df.to_csv(output_file, index=False)
    logger.info(f"Benchmark results saved to {output_file}")
    print(df) # Print to console as well
    return df

if __name__ == "__main__":
    # Example targets and configurations
    targets = ['Chignolin', 'Trp_Cage'] # Add more targets like TMV if data is available
    df_results = run_benchmark_suite(targets, steps_list=[10000, 50000], ai_options=[False, True])
    print("\n--- Benchmark Summary ---")
    print(df_results[['target', 'use_ai_router', 'avg_throughput_steps_per_sec', 'avg_time_per_step_ms', 'avg_gpu_util_percent']])
