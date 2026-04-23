# theory/strategy.py

import copy
import importlib
import inspect
import os
import math
import numpy as np
import torch
import torch.nn as nn
from typing import Dict, List, Optional, Sequence, Tuple
from core.definitions import Config
from core.sim_param_schema import (
    CORE_SIM_PARAM_DEFAULTS,
    DEFAULT_RUNTIME_CONDITIONING_KEYS,
    coerce_sim_param_float,
    vectorize_sim_params,
)
from theory.specialists import (
    SaltBridgeSpecialist,
    HydrophobicSpecialist,
    AromaticSpecialist,
    HBSpecialist,
    ChargeTransferSpecialist,
    PiCationSpecialist,
    CationPiSpecialist,
    HalogenBondSpecialist,
    ChalcogenBondSpecialist,
    StackingSpecialist,
)

try:
    import onnxruntime as ort  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    ort = None


_VALID_ROUTER_RUNTIME_MODES = ("auto", "eager", "scripted", "compiled", "onnx")


def _verbose_init_enabled() -> bool:
    return str(os.getenv("AI_ROUTER_VERBOSE_INIT", "0")).strip().lower() in ("1", "true", "yes", "on")


# [NEW] Branch 모듈을 동적으로 로드하기 위한 로직 추가
def _load_branch_modules():
    """theory.branches 패키지 내의 모든 Specialist 모듈을 로드합니다."""
    branch_dir = os.path.join(os.path.dirname(__file__), 'branches')
    modules = {}
    if not os.path.exists(branch_dir):
        if _verbose_init_enabled():
            print(f"Warning: Branch directory {branch_dir} does not exist.")
        return modules

    for filename in os.listdir(branch_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = f"theory.branches.{filename[:-3]}" # .py 제거
            try:
                mod = importlib.import_module(module_name)
                for name, obj in inspect.getmembers(mod, inspect.isclass):
                    if name.endswith('Logic') and issubclass(obj, nn.Module) and obj is not nn.Module:
                        instance = obj(Config.DEVICE)
                        modules[name.lower()] = instance
                        if _verbose_init_enabled():
                            print(f"Loaded branch module: {name.lower()} from {module_name}")
            except ImportError as e:
                if _verbose_init_enabled():
                    print(f"Could not import {module_name}: {e}")
    return modules


class _AIRouterTensorWrapper(nn.Module):
    """TorchScript trace wrapper: tensor-only inputs/outputs for AIRouter."""

    def __init__(self, router: "AIRouter"):
        super().__init__()
        self.router = router

    def forward(
        self,
        c: torch.Tensor,
        topo_features_batch: torch.Tensor,
        sim_param_tensor: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        weights, _is_explored, active_mask = self.router.forward_tensor(
            c=c,
            topo_features_batch=topo_features_batch,
            sim_param_tensor=sim_param_tensor,
        )
        return weights, active_mask


# [MODIFIED] AI Router 클래스 정의: Conditional Computation 지원
class AIRouter(nn.Module):
    """
    상태 정보와 각 Specialist의 보조 출력(aux_outputs)을 기반으로
    각 Specialist의 기여도를 결정하는 가중치를 예측합니다.
    탐색 기능 추가.
    """
    def __init__(self, num_modules, state_dim=128, hidden_dim=256, explore_prob=0.1, max_output_nodes=50):
        super(AIRouter, self).__init__()
        self.num_modules = num_modules
        self.state_dim = state_dim
        self.hidden_dim = hidden_dim
        self.explore_prob = nn.Parameter(torch.tensor(explore_prob), requires_grad=False) # 탐색 확률, 학습 X

        # [NEW] Output layer complexity restriction
        self.max_output_nodes = max_output_nodes
        effective_num_modules = min(num_modules, max_output_nodes)
        if _verbose_init_enabled():
            print(
                f"AIRouter: Requested {num_modules} modules, using {effective_num_modules} "
                f"(max_output_nodes={max_output_nodes}) for router_head."
            )
        self.effective_num_modules = effective_num_modules
        # Runtime-only acceleration knobs (no behavior change by default).
        # - AI_ROUTER_TOPK_ACTIVE: keep only top-k routed modules active per batch item (0 disables).
        # - AI_ROUTER_MASK_THRESHOLD: threshold used by mask_head path when top-k is disabled.
        topk_raw = os.getenv("AI_ROUTER_TOPK_ACTIVE", "0").strip()
        try:
            topk_val = int(topk_raw)
        except ValueError:
            topk_val = 0
        self.inference_topk_active = int(max(topk_val, 0))
        if self.inference_topk_active > 0:
            self.inference_topk_active = int(min(self.inference_topk_active, self.effective_num_modules))

        threshold_raw = os.getenv("AI_ROUTER_MASK_THRESHOLD", "0.5").strip()
        try:
            self.mask_threshold = float(threshold_raw)
        except ValueError:
            self.mask_threshold = 0.5

        runtime_mode_raw = os.getenv("AI_ROUTER_RUNTIME_MODE", "auto").strip().lower()
        if runtime_mode_raw not in _VALID_ROUTER_RUNTIME_MODES:
            runtime_mode_raw = "auto"
        self.runtime_mode = runtime_mode_raw
        self.disable_exploration = os.getenv("AI_ROUTER_DISABLE_EXPLORATION", "0") == "1"
        self.cache_router_inputs = os.getenv("AI_ROUTER_CACHE_INPUTS", "1") == "1"
        if self.disable_exploration:
            self.explore_prob.data.fill_(0.0)
        self._script_router: Optional[torch.jit.ScriptModule] = None
        self._script_router_error: Optional[str] = None
        self._compiled_router: Optional[nn.Module] = None
        self._compiled_router_unavailable: bool = False
        self._onnx_router_session = None
        self._onnx_router_input_names: Optional[Tuple[str, str, str]] = None
        self._onnx_router_output_names: Optional[Tuple[str, str]] = None
        self._onnx_router_providers: List[str] = []
        self._onnx_router_model_path: Optional[str] = None
        self._onnx_router_unavailable: bool = False
        self._onnx_router_iobinding_enabled: bool = False
        self._onnx_router_iobinding_error: Optional[str] = None
        self._last_effective_runtime_mode: str = "eager"
        self._cached_topo_key: Optional[Tuple] = None
        self._cached_topo_features_batch: Optional[torch.Tensor] = None
        self._cached_sim_params_key: Optional[Tuple] = None
        self._cached_sim_param_tensor: Optional[torch.Tensor] = None

        # 구조 상태 인코더 (좌표 기반) - O(N)
        self.coord_encoder = nn.Sequential(
            nn.Linear(3, hidden_dim // 4),
            nn.SiLU(),
            nn.Linear(hidden_dim // 4, hidden_dim // 2),
            nn.SiLU(),
            nn.Linear(hidden_dim // 2, hidden_dim),
            nn.SiLU()
        )

        # 토폴로지 상태 인코더 (잔기 타입, 전하 등) - O(N)
        self.topo_feature_dim = getattr(Config, 'TOPO_FEATURE_DIM', 64) # Config에 정의 필요 또는 기본값
        self.topo_encoder = nn.Sequential(
            nn.Linear(self.topo_feature_dim, hidden_dim // 2),
            nn.SiLU(),
            nn.Linear(hidden_dim // 2, hidden_dim),
            nn.SiLU()
        )

        self.sim_param_keys = tuple(DEFAULT_RUNTIME_CONDITIONING_KEYS)
        self.sim_param_dim = int(len(self.sim_param_keys))

        # 글로벌 시뮬레이션 파라미터 인코더 (염 농도, 온도 등) - O(1) per batch
        self.param_encoder = nn.Sequential(
            nn.Linear(self.sim_param_dim, hidden_dim // 4),
            nn.SiLU(),
            nn.Linear(hidden_dim // 4, hidden_dim // 2),
            nn.SiLU(),
            nn.Linear(hidden_dim // 2, hidden_dim),
            nn.SiLU()
        )

        # 각 모듈의 보조 출력은 lightweight summary만 사용합니다.
        # 기존 구현은 입력 차원 불일치(hidden_dim vs hidden_dim//4)로 런타임 오류가 발생했습니다.
        self.aux_info_encoded_dim = hidden_dim // 4
        self.aux_info_encoder = nn.Identity()

        # 상태 및 보조 정보를 결합하여 가중치 예측
        # combined_input_dim은 hidden_dim * 3 + (effective_num_modules * self.aux_info_encoded_dim) 에 비례
        # effective_num_modules가 상수로 제한되어 있으므로, 이 부분의 복잡도는 상수입니다.
        # 총 입력 크기는 O(N) 상태 정보 + O(상수) 보조 정보
        # 결합 자체는 O(N) 상태 정보에 기반하므로, 복잡도는 O(N) 상태 정보 처리 + O(상수) 결합 + O(상수) 헤드
        # 최종적으로, 헤드의 출력 크기가 effective_num_modules로 제한되어 있으므로 O(N) + O(effective_num_modules) = O(N) (effective_num_modules는 상수)
        combined_input_dim = hidden_dim + hidden_dim + hidden_dim + (effective_num_modules * self.aux_info_encoded_dim)
        self.router_head = nn.Sequential(
            nn.Linear(combined_input_dim, hidden_dim), # O(상수) 연산 (입력 차원이 고정됨)
            nn.SiLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),   # O(상수) 연산
            nn.SiLU(),
            nn.Linear(hidden_dim // 2, effective_num_modules), # O(상수) 연산 (출력 차원이 고정됨, effective_num_modules <= max_output_nodes)
            nn.Softmax(dim=-1) # O(effective_num_modules) 연산
        )

        # [NEW] Conditional Computation을 위한 Binary Mask 생성 Head
        # 이 헤드는 각 모듈이 활성화될지 여부를 나타내는 이진 마스크를 출력
        self.mask_head = nn.Sequential(
            nn.Linear(combined_input_dim, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.SiLU(),
            nn.Linear(hidden_dim // 2, effective_num_modules),
            nn.Sigmoid() # Output probability for each module
        )

    def set_runtime_mode(self, mode: str) -> None:
        mode_i = str(mode).strip().lower()
        if mode_i not in _VALID_ROUTER_RUNTIME_MODES:
            mode_i = "auto"
        self.runtime_mode = mode_i

    def set_disable_exploration(self, flag: bool) -> None:
        self.disable_exploration = bool(flag)
        if self.disable_exploration:
            self.explore_prob.data.fill_(0.0)

    def _build_topology_features(self, c: torch.Tensor, top) -> torch.Tensor:
        bsz, n_atoms, _ = c.shape
        topo_features = getattr(top, "residue_features", None)
        use_cache = bool(self.cache_router_inputs and (not self.training))
        if use_cache and isinstance(topo_features, torch.Tensor):
            cache_key = (
                int(id(topo_features)),
                int(bsz),
                int(n_atoms),
                str(c.device),
                str(c.dtype),
            )
            if (
                self._cached_topo_key == cache_key
                and isinstance(self._cached_topo_features_batch, torch.Tensor)
            ):
                return self._cached_topo_features_batch

        if topo_features is None:
            topo_features_batch = torch.zeros(bsz, n_atoms, self.topo_feature_dim, device=c.device)
        elif topo_features.dim() == 2:
            topo_features_batch = topo_features.unsqueeze(0).expand(bsz, -1, -1)
        elif topo_features.dim() == 3:
            topo_features_batch = topo_features
        else:
            topo_features_batch = torch.zeros(bsz, n_atoms, self.topo_feature_dim, device=c.device)
        topo_features_batch = topo_features_batch.to(device=c.device, dtype=c.dtype)
        if use_cache and isinstance(topo_features, torch.Tensor):
            self._cached_topo_key = cache_key
            self._cached_topo_features_batch = topo_features_batch
        return topo_features_batch

    def _build_sim_params_tensor(self, c: torch.Tensor, sim_params: Dict[str, float]) -> torch.Tensor:
        bsz = c.shape[0]
        params = sim_params if isinstance(sim_params, dict) else {}
        sim_values = tuple(
            coerce_sim_param_float(
                params.get(k, CORE_SIM_PARAM_DEFAULTS.get(k, 0.0)),
                CORE_SIM_PARAM_DEFAULTS.get(k, 0.0),
            )
            for k in self.sim_param_keys
        )
        use_cache = bool(self.cache_router_inputs and (not self.training))
        if use_cache:
            cache_key = (int(bsz), str(c.device), sim_values)
            if (
                self._cached_sim_params_key == cache_key
                and isinstance(self._cached_sim_param_tensor, torch.Tensor)
            ):
                # Return an owned tensor to avoid compile/cudagraph alias hazards.
                return self._cached_sim_param_tensor.clone()

        param_vec = vectorize_sim_params(
            params,
            keys=self.sim_param_keys,
            defaults=CORE_SIM_PARAM_DEFAULTS,
            device=c.device,
            dtype=torch.float32,
        )
        # `expand` creates a view; use repeat+contiguous for a stable owned buffer.
        param_tensor = param_vec.unsqueeze(0).repeat(int(bsz), 1).contiguous()
        if use_cache:
            self._cached_sim_params_key = cache_key
            self._cached_sim_param_tensor = param_tensor
        return param_tensor

    def forward_tensor(
        self,
        c: torch.Tensor,
        topo_features_batch: torch.Tensor,
        sim_param_tensor: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Tensor-only router path used for eager and TorchScript runtime."""
        bsz, _n_atoms, _ = c.shape

        coord_features = self.coord_encoder(c)
        state_encoded = coord_features.mean(dim=1)

        topo_encoded = self.topo_encoder(topo_features_batch)
        topo_summary = topo_encoded.mean(dim=1)

        param_encoded = self.param_encoder(sim_param_tensor)

        # Placeholder aux block is intentionally zeroed in fast runtime.
        aux_all = torch.zeros(
            bsz,
            self.effective_num_modules * self.aux_info_encoded_dim,
            dtype=state_encoded.dtype,
            device=c.device,
        )

        combined = torch.cat([state_encoded, topo_summary, param_encoded, aux_all], dim=1)

        weights_logits = self.router_head[:-1](combined)
        weights_normal = self.router_head[-1:](weights_logits)

        if self.disable_exploration or float(self.explore_prob.item()) <= 0.0:
            is_explored = torch.zeros(bsz, dtype=torch.bool, device=c.device)
            weights_final = weights_normal
        else:
            is_explored = torch.rand(bsz, device=c.device) < self.explore_prob
            exploration_noise = torch.randn_like(weights_logits) * 0.1
            weights_explore = torch.softmax(weights_logits + exploration_noise, dim=-1)
            weights_final = torch.where(is_explored.unsqueeze(-1), weights_explore, weights_normal)

        if 0 < int(self.inference_topk_active) < int(self.effective_num_modules):
            _, topk_idx = torch.topk(weights_final, k=int(self.inference_topk_active), dim=-1)
            active_mask = torch.zeros_like(weights_final)
            active_mask.scatter_(1, topk_idx, 1.0)
        else:
            mask_prob = self.mask_head(combined)
            active_mask = (mask_prob > float(self.mask_threshold)).float()

        weights_masked = weights_final * active_mask
        weights_sum = weights_masked.sum(dim=-1, keepdim=True)
        no_active = weights_sum <= 1e-8
        fallback_idx = torch.argmax(weights_normal, dim=-1, keepdim=True)
        fallback_mask = torch.zeros_like(active_mask).scatter_(1, fallback_idx, 1.0)
        active_mask = torch.where(no_active, fallback_mask, active_mask)
        weights_masked = torch.where(no_active, weights_normal * fallback_mask, weights_masked)
        weights_final = weights_masked / weights_masked.sum(dim=-1, keepdim=True).clamp_min(1e-8)

        return weights_final, is_explored, active_mask

    def _prepare_script_router(
        self,
        c: torch.Tensor,
        topo_features_batch: torch.Tensor,
        sim_param_tensor: torch.Tensor,
    ) -> bool:
        if self._script_router is not None:
            return True
        try:
            wrapper = _AIRouterTensorWrapper(self).to(device=c.device).eval()
            traced = torch.jit.trace(
                wrapper,
                (c, topo_features_batch, sim_param_tensor),
                strict=False,
                check_trace=False,
            )
            self._script_router = torch.jit.optimize_for_inference(traced)
            self._script_router_error = None
            return True
        except Exception as exc:
            self._script_router = None
            self._script_router_error = f"{type(exc).__name__}: {exc}"
            return False

    def _prepare_compiled_router(
        self,
        c: torch.Tensor,
        topo_features_batch: torch.Tensor,
        sim_param_tensor: torch.Tensor,
    ) -> bool:
        if self._compiled_router is not None:
            return True
        if self._compiled_router_unavailable:
            return False
        if not hasattr(torch, "compile"):
            self._script_router_error = "torch.compile unavailable in this PyTorch build"
            self._compiled_router_unavailable = True
            return False
        try:
            wrapper = _AIRouterTensorWrapper(self).to(device=c.device).eval()
            compile_kwargs: Dict[str, object] = {"fullgraph": False, "dynamic": True}
            compile_mode = str(os.getenv("AI_ROUTER_COMPILE_MODE", "reduce-overhead")).strip().lower()
            if compile_mode:
                compile_kwargs["mode"] = compile_mode
            self._compiled_router = torch.compile(wrapper, **compile_kwargs)
            # Trigger graph/materialization once to keep first inference predictable.
            _ = self._compiled_router(c, topo_features_batch, sim_param_tensor)
            self._script_router_error = None
            self._compiled_router_unavailable = False
            return True
        except Exception as exc:
            self._compiled_router = None
            self._script_router_error = f"{type(exc).__name__}: {exc}"
            self._compiled_router_unavailable = True
            return False

    def _prepare_onnx_router(
        self,
        c: torch.Tensor,
        topo_features_batch: torch.Tensor,
        sim_param_tensor: torch.Tensor,
    ) -> bool:
        if self._onnx_router_session is not None:
            return True
        if self._onnx_router_unavailable:
            return False
        if ort is None:
            self._script_router_error = "onnxruntime is not installed"
            self._onnx_router_unavailable = True
            return False
        try:
            cache_dir = str(
                os.getenv(
                    "AI_ROUTER_ONNX_CACHE_DIR",
                    os.path.join("runtime", "cache", "ai_router"),
                )
            ).strip()
            os.makedirs(cache_dir, exist_ok=True)
            model_path = os.path.join(
                cache_dir,
                (
                    f"airouter_router_m{int(self.effective_num_modules)}"
                    f"_topo{int(self.topo_feature_dim)}"
                    f"_sim{int(self.sim_param_dim)}.onnx"
                ),
            )
            force_reexport = str(os.getenv("AI_ROUTER_ONNX_REEXPORT", "0")).strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
            )

            if force_reexport or (not os.path.exists(model_path)):
                router_clone = copy.deepcopy(self).to(device="cpu").eval()
                router_clone.set_runtime_mode("eager")
                router_clone.set_disable_exploration(True)
                wrapper = _AIRouterTensorWrapper(router_clone).eval()
                c_cpu = c.detach().to(device="cpu", dtype=torch.float32)
                topo_cpu = topo_features_batch.detach().to(device="cpu", dtype=torch.float32)
                sim_cpu = sim_param_tensor.detach().to(device="cpu", dtype=torch.float32)
                with torch.inference_mode():
                    torch.onnx.export(
                        wrapper,
                        (c_cpu, topo_cpu, sim_cpu),
                        model_path,
                        opset_version=17,
                        do_constant_folding=True,
                        input_names=["c", "topo_features_batch", "sim_param_tensor"],
                        output_names=["weights", "active_mask"],
                        dynamic_axes={
                            "c": {0: "batch", 1: "atoms"},
                            "topo_features_batch": {0: "batch", 1: "atoms"},
                            "sim_param_tensor": {0: "batch"},
                            "weights": {0: "batch"},
                            "active_mask": {0: "batch"},
                        },
                    )

            allow_cpu = str(os.getenv("AI_ROUTER_ONNX_ALLOW_CPU", "0")).strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
            available = set(ort.get_available_providers())
            preferred_raw = os.getenv(
                "AI_ROUTER_ONNX_PROVIDERS",
                "ROCMExecutionProvider,CUDAExecutionProvider,MIGraphXExecutionProvider",
            )
            preferred = [x.strip() for x in str(preferred_raw).split(",") if str(x).strip()]
            if allow_cpu:
                preferred = preferred + ["CPUExecutionProvider"]
            providers = [p for p in preferred if p in available]
            if not allow_cpu:
                providers = [p for p in providers if p != "CPUExecutionProvider"]
            if not providers and allow_cpu:
                providers = ["CPUExecutionProvider"] if "CPUExecutionProvider" in available else []
            if not providers:
                self._script_router_error = "No ONNXRuntime execution providers are available"
                return False
            if (providers == ["CPUExecutionProvider"]) and (not allow_cpu):
                self._script_router_error = (
                    "ONNXRuntime GPU provider unavailable (set AI_ROUTER_ONNX_ALLOW_CPU=1 to force CPU)"
                )
                return False

            session_opts = ort.SessionOptions()
            graph_opt_raw = os.getenv("AI_ROUTER_ONNX_GRAPH_OPT_LEVEL")
            if graph_opt_raw is None:
                # On some ROCm stacks, aggressive graph fusion (e.g., QuickGeluFusion)
                # can emit kernels unavailable for older AMD architectures.
                graph_opt_raw = "basic" if "ROCMExecutionProvider" in providers else "all"
            graph_opt_key = str(graph_opt_raw).strip().lower()
            graph_opt_map = {
                "disable": ort.GraphOptimizationLevel.ORT_DISABLE_ALL,
                "none": ort.GraphOptimizationLevel.ORT_DISABLE_ALL,
                "basic": ort.GraphOptimizationLevel.ORT_ENABLE_BASIC,
                "extended": ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED,
                "all": ort.GraphOptimizationLevel.ORT_ENABLE_ALL,
            }
            session_opts.graph_optimization_level = graph_opt_map.get(
                graph_opt_key, ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )
            session = ort.InferenceSession(model_path, sess_options=session_opts, providers=providers)
            actual_providers = list(session.get_providers())
            input_names = tuple(x.name for x in session.get_inputs())
            output_names = tuple(x.name for x in session.get_outputs())
            if len(input_names) != 3 or len(output_names) < 2:
                self._script_router_error = "Unexpected ONNX router I/O signature"
                return False
            if not allow_cpu:
                gpu_eps = {"ROCMExecutionProvider", "CUDAExecutionProvider", "MIGraphXExecutionProvider"}
                if not any(p in gpu_eps for p in actual_providers):
                    self._script_router_error = (
                        f"ONNXRuntime GPU provider unavailable in strict GPU mode: {actual_providers}"
                    )
                    return False
                strict_no_cpu_provider = str(
                    os.getenv("AI_ROUTER_ONNX_STRICT_NO_CPU_PROVIDER", "0")
                ).strip().lower() in ("1", "true", "yes", "on")
                if strict_no_cpu_provider and any(p == "CPUExecutionProvider" for p in actual_providers):
                    self._script_router_error = (
                        f"ONNXRuntime CPU provider present in strict no-CPU mode: {actual_providers}"
                    )
                    return False

            self._onnx_router_session = session
            self._onnx_router_input_names = (input_names[0], input_names[1], input_names[2])
            self._onnx_router_output_names = (output_names[0], output_names[1])
            self._onnx_router_providers = list(actual_providers)
            self._onnx_router_model_path = model_path
            self._onnx_router_iobinding_enabled = bool(
                str(os.getenv("AI_ROUTER_ONNX_USE_IOBINDING", "1")).strip().lower() in ("1", "true", "yes", "on")
                and any(p in actual_providers for p in ("ROCMExecutionProvider", "CUDAExecutionProvider"))
            )
            self._onnx_router_iobinding_error = None
            self._script_router_error = None
            self._onnx_router_unavailable = False
            return True
        except Exception as exc:
            self._onnx_router_session = None
            self._onnx_router_input_names = None
            self._onnx_router_output_names = None
            self._onnx_router_providers = []
            self._onnx_router_model_path = None
            self._onnx_router_iobinding_enabled = False
            self._onnx_router_iobinding_error = f"{type(exc).__name__}: {exc}"
            self._script_router_error = f"{type(exc).__name__}: {exc}"
            self._onnx_router_unavailable = True
            return False

    def _run_onnx_router(
        self,
        c: torch.Tensor,
        topo_features_batch: torch.Tensor,
        sim_param_tensor: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        if self._onnx_router_session is None or self._onnx_router_input_names is None:
            raise RuntimeError("ONNX router session is not initialized")
        input_names = self._onnx_router_input_names
        output_names = self._onnx_router_output_names or ("weights", "active_mask")
        use_iobinding = bool(self._onnx_router_iobinding_enabled and c.is_cuda)
        require_iobinding = bool(
            c.is_cuda
            and str(os.getenv("AI_ROUTER_ONNX_IOBINDING_REQUIRED", "1")).strip().lower() in ("1", "true", "yes", "on")
        )
        allow_cpu_copy_fallback = str(os.getenv("AI_ROUTER_ONNX_ALLOW_CPU_COPY", "0")).strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

        c_i = c.detach().contiguous().to(dtype=torch.float32)
        topo_i = topo_features_batch.detach().contiguous().to(dtype=torch.float32)
        sim_i = sim_param_tensor.detach().contiguous().to(dtype=torch.float32)

        if (not use_iobinding) and require_iobinding:
            raise RuntimeError("onnx_iobinding_required_but_disabled")

        if use_iobinding:
            try:
                device_id = int(c_i.device.index or 0)
                io = self._onnx_router_session.io_binding()

                # Prefer DLPack ortvalue binding when supported by this ORT build.
                if hasattr(ort.OrtValue, "from_dlpack"):
                    c_ov = ort.OrtValue.from_dlpack(torch.utils.dlpack.to_dlpack(c_i))
                    topo_ov = ort.OrtValue.from_dlpack(torch.utils.dlpack.to_dlpack(topo_i))
                    sim_ov = ort.OrtValue.from_dlpack(torch.utils.dlpack.to_dlpack(sim_i))
                    io.bind_ortvalue_input(input_names[0], c_ov)
                    io.bind_ortvalue_input(input_names[1], topo_ov)
                    io.bind_ortvalue_input(input_names[2], sim_ov)
                else:
                    io.bind_input(
                        input_names[0],
                        "cuda",
                        device_id,
                        np.float32,
                        tuple(c_i.shape),
                        int(c_i.data_ptr()),
                    )
                    io.bind_input(
                        input_names[1],
                        "cuda",
                        device_id,
                        np.float32,
                        tuple(topo_i.shape),
                        int(topo_i.data_ptr()),
                    )
                    io.bind_input(
                        input_names[2],
                        "cuda",
                        device_id,
                        np.float32,
                        tuple(sim_i.shape),
                        int(sim_i.data_ptr()),
                    )

                bsz = int(c_i.shape[0])
                out_width = int(self.effective_num_modules)
                w_out = torch.empty((bsz, out_width), device=c_i.device, dtype=torch.float32)
                m_out = torch.empty((bsz, out_width), device=c_i.device, dtype=torch.float32)

                if hasattr(ort.OrtValue, "from_dlpack"):
                    w_ov = ort.OrtValue.from_dlpack(torch.utils.dlpack.to_dlpack(w_out))
                    m_ov = ort.OrtValue.from_dlpack(torch.utils.dlpack.to_dlpack(m_out))
                    io.bind_ortvalue_output(output_names[0], w_ov)
                    io.bind_ortvalue_output(output_names[1], m_ov)
                else:
                    io.bind_output(
                        output_names[0],
                        "cuda",
                        device_id,
                        np.float32,
                        tuple(w_out.shape),
                        int(w_out.data_ptr()),
                    )
                    io.bind_output(
                        output_names[1],
                        "cuda",
                        device_id,
                        np.float32,
                        tuple(m_out.shape),
                        int(m_out.data_ptr()),
                    )

                self._onnx_router_session.run_with_iobinding(io)
                self._onnx_router_iobinding_error = None
                return w_out.to(dtype=c.dtype), m_out.to(dtype=c.dtype)
            except Exception as exc:
                self._onnx_router_iobinding_error = f"{type(exc).__name__}: {exc}"
                if require_iobinding:
                    raise
                # Fall back to ORT regular run() path below.

        if not allow_cpu_copy_fallback:
            raise RuntimeError("onnx_cpu_copy_fallback_disabled")

        c_np = c_i.to(device="cpu").numpy()
        topo_np = topo_i.to(device="cpu").numpy()
        sim_np = sim_i.to(device="cpu").numpy()
        out = self._onnx_router_session.run(
            list(output_names),
            {input_names[0]: c_np, input_names[1]: topo_np, input_names[2]: sim_np},
        )
        if len(out) < 2:
            raise RuntimeError("ONNX router output is missing required tensors")
        weights = torch.from_numpy(out[0]).to(device=c.device, dtype=c.dtype)
        active_mask = torch.from_numpy(out[1]).to(device=c.device, dtype=c.dtype)
        return weights, active_mask

    def route(
        self,
        c: torch.Tensor,
        top,
        sim_params: Dict[str, float],
        module_keys: Sequence[str],
    ) -> Tuple[torch.Tensor, torch.Tensor, List[str], torch.Tensor]:
        module_keys_i = list(module_keys)[: self.effective_num_modules]
        if len(module_keys_i) < self.effective_num_modules:
            module_keys_i.extend(
                [f"module_{i}" for i in range(len(module_keys_i), self.effective_num_modules)]
            )

        topo_features_batch = self._build_topology_features(c, top)
        sim_param_tensor = self._build_sim_params_tensor(c, sim_params)

        runtime_mode_i = str(self.runtime_mode).strip().lower()
        self._last_effective_runtime_mode = "eager"
        if runtime_mode_i == "scripted":
            if self._prepare_script_router(c, topo_features_batch, sim_param_tensor):
                weights_script, active_mask_script = self._script_router(
                    c, topo_features_batch, sim_param_tensor
                )
                self._last_effective_runtime_mode = "scripted"
                is_explored = torch.zeros(c.shape[0], dtype=torch.bool, device=c.device)
                return weights_script, is_explored, module_keys_i, active_mask_script
        elif runtime_mode_i in ("compiled", "auto"):
            if self._prepare_compiled_router(c, topo_features_batch, sim_param_tensor):
                weights_compiled, active_mask_compiled = self._compiled_router(  # type: ignore[misc]
                    c, topo_features_batch, sim_param_tensor
                )
                self._last_effective_runtime_mode = "compiled"
                is_explored = torch.zeros(c.shape[0], dtype=torch.bool, device=c.device)
                return weights_compiled, is_explored, module_keys_i, active_mask_compiled
        auto_try_onnx = str(os.getenv("AI_ROUTER_AUTO_TRY_ONNX", "1")).strip().lower() in ("1", "true", "yes", "on")
        if (runtime_mode_i == "onnx") or (runtime_mode_i == "auto" and auto_try_onnx):
            if self._prepare_onnx_router(c, topo_features_batch, sim_param_tensor):
                try:
                    weights_onnx, active_mask_onnx = self._run_onnx_router(
                        c=c,
                        topo_features_batch=topo_features_batch,
                        sim_param_tensor=sim_param_tensor,
                    )
                    self._last_effective_runtime_mode = "onnx"
                    is_explored = torch.zeros(c.shape[0], dtype=torch.bool, device=c.device)
                    return weights_onnx, is_explored, module_keys_i, active_mask_onnx
                except Exception as exc:
                    # Keep simulation alive by falling back to eager path when ORT fails
                    # on the current GPU stack. Process restart will allow retry.
                    self._script_router_error = f"ONNX router runtime failed: {type(exc).__name__}: {exc}"
                    self._onnx_router_session = None
                    self._onnx_router_input_names = None
                    self._onnx_router_output_names = None
                    self._onnx_router_providers = []
                    self._onnx_router_model_path = None
                    self._onnx_router_iobinding_enabled = False
                    self._onnx_router_unavailable = True

        weights, is_explored, active_mask = self.forward_tensor(
            c=c,
            topo_features_batch=topo_features_batch,
            sim_param_tensor=sim_param_tensor,
        )
        self._last_effective_runtime_mode = "eager"
        return weights, is_explored, module_keys_i, active_mask

    def forward(self, c, top, aux_outputs, sim_params):
        """
        Args:
            c: Coordinates [B, N, 3]
            top: Topology object
            aux_outputs: Dict from StrategicOrchestrator.forward (key: module_name, value: info_dict)
            sim_params: Dict containing global params like temp, salt concentration etc.
        Returns:
            weights: [B, effective_num_modules] tensor of weights for each specialist module.
            is_explored: Boolean indicating if exploration was used for this prediction.
            active_mask: [B, effective_num_modules] binary mask indicating which modules are active for conditional computation.
        """
        if isinstance(aux_outputs, dict):
            module_keys = list(aux_outputs.keys())
        else:
            module_keys = [f"module_{i}" for i in range(self.effective_num_modules)]
        return self.route(c=c, top=top, sim_params=sim_params, module_keys=module_keys)


# [MODIFIED] StrategicOrchestrator 클래스: 위험요소 수정본 (Risk-Fix Version)
class StrategicOrchestrator(nn.Module):
    """[PRO] Physics-guided Specialist Orchestrator with Dynamic Branch Loading and AI Router."""
    
    def __init__(self, dev):
        super().__init__()
        self.dev = dev
        # [EXISTING] 기존 고정 Specialist 대신 동적으로 로드
        self.core_specialists = nn.ModuleDict({
            'salt': SaltBridgeSpecialist(dev),
            'hydrophobic': HydrophobicSpecialist(dev),
            'aromatic': AromaticSpecialist(dev),
            'hbond': HBSpecialist(dev),
            'ct': ChargeTransferSpecialist(dev),
            'picat': PiCationSpecialist(dev),
            'catpi': CationPiSpecialist(dev),
            'halogen': HalogenBondSpecialist(dev),
            'chalcogen': ChalcogenBondSpecialist(dev),
            'stacking': StackingSpecialist(dev),
        })
        # [NEW] Branch Specialist 로드
        self.branch_modules = nn.ModuleDict(_load_branch_modules())
        if _verbose_init_enabled():
            print(
                f"Total loaded specialists: Core({len(self.core_specialists)}), "
                f"Branch({len(self.branch_modules)})"
            )
        
        # Combine all modules into a single list for easier handling
        self.all_modules = list(self.core_specialists.items()) + list(self.branch_modules.items())
        self.num_modules = len(self.all_modules)

        # [MODIFIED] AI Router 생성: total_modules를 self.num_modules로 설정
        self.ai_router = AIRouter(num_modules=self.num_modules, explore_prob=0.1, max_output_nodes=self.num_modules) # Use all modules
        self.router_runtime_mode = str(self.ai_router.runtime_mode)

        # [NEW] Physics-AI Force Mixing Parameter
        self.balance_weight = nn.Parameter(torch.tensor(0.0)) # Start with neutral balance (sigmoid(0)=0.5)
        if _verbose_init_enabled():
            print(
                "  🎛️  ACTIVE (Learnable Physics-AI Balance Weight: "
                f"initial value = {self.balance_weight.item()})"
            )

        # Many specialist branches are placeholders that return zero force.
        # Keep O(N) complexity while preserving trainability with per-module fallback heads.
        self.module_fallback_heads = nn.ModuleDict(
            {
                name: nn.Sequential(
                    nn.Linear(3, 32),
                    nn.SiLU(),
                    nn.Linear(32, 3),
                )
                for name, _ in self.all_modules
            }
        )
        self.module_fallback_scales = nn.ParameterDict(
            {name: nn.Parameter(torch.tensor(0.1, device=self.dev)) for name, _ in self.all_modules}
        )
        self.skip_zero_specialists = os.getenv("AI_ROUTER_SKIP_ZERO_SPECIALISTS", "1") == "1"
        assume_branch_zero_default = os.getenv("AI_ROUTER_ASSUME_BRANCH_ZERO", "1") == "1"
        self.module_zero_output_hints = {}
        for name, module in self.all_modules:
            hint = getattr(module, "always_zero_output", None)
            if hint is None and assume_branch_zero_default:
                hint = str(module.__class__.__module__).startswith("theory.branches.")
            self.module_zero_output_hints[str(name)] = bool(hint)
        self.force_domain_adapters = os.getenv("AI_ROUTER_FORCE_DOMAIN_ADAPTERS", "1") == "1"
        self.domain_adapter_module_names = {
            "metal": ("metalcoordinationlogic",),
            "dna": ("nucleicacidlogic",),
            "membrane": ("membranelogic",),
        }

        # [NEW] Last router weights storage for explainability and exploration tracking
        self.last_router_weights = None
        self.last_router_module_names = None
        self.last_was_explored = None
        self.last_mixing_ratio = None
        self.last_effective_ai_influence = None
        self.last_active_mask = None
        self.last_active_modules_per_batch = None
        self.last_router_action_log_probs = None
        self.last_router_runtime_mode = str(
            getattr(self.ai_router, "_last_effective_runtime_mode", self.ai_router.runtime_mode)
        )
        self.last_router_script_error = None
        self.last_router_onnx_providers = None
        self.last_router_onnx_model_path = None
        self.last_router_onnx_iobinding_enabled = None
        self.last_router_onnx_iobinding_error = None

        # Uncertainty-aware safety fallback:
        # if router confidence is low, AI correction is suppressed (physics-only fallback).
        self.uncertainty_guard_enabled = os.getenv("AI_ROUTER_UNCERTAINTY_GUARD", "1") == "1"
        self.uncertainty_apply_in_train = os.getenv("AI_ROUTER_UNCERTAINTY_APPLY_IN_TRAIN", "0") == "1"
        try:
            self.uncertainty_entropy_threshold = float(
                os.getenv("AI_ROUTER_UNCERTAINTY_ENTROPY_THRESHOLD", "0.92")
            )
        except ValueError:
            self.uncertainty_entropy_threshold = 0.92
        try:
            self.uncertainty_top1_threshold = float(
                os.getenv("AI_ROUTER_UNCERTAINTY_TOP1_THRESHOLD", "0.20")
            )
        except ValueError:
            self.uncertainty_top1_threshold = 0.20
        self.last_uncertainty_score = None
        self.last_uncertainty_score_mean = None
        self.last_uncertainty_fallback_mask = None
        self.last_uncertainty_fallback_rate = 0.0

    @staticmethod
    def _truthy(v) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return float(v) != 0.0
        s = str(v).strip().lower()
        return s in ("1", "true", "yes", "y", "on")

    def _infer_forced_domain_adapter_indices(self, sim_params: Dict[str, float], active_width: int) -> List[int]:
        if not bool(self.force_domain_adapters):
            return []
        params = sim_params if isinstance(sim_params, dict) else {}
        domains = set()
        for key in ("domain", "special_domain", "target_domain", "biopolymer_domain"):
            raw = str(params.get(key, "")).strip().lower()
            if raw in self.domain_adapter_module_names:
                domains.add(raw)
            elif "," in raw:
                for token in raw.split(","):
                    tok = str(token).strip().lower()
                    if tok in self.domain_adapter_module_names:
                        domains.add(tok)

        if self._truthy(params.get("is_metal_target", False)) or self._truthy(params.get("enable_metal_adapter", False)):
            domains.add("metal")
        if self._truthy(params.get("is_dna_target", False)) or self._truthy(params.get("enable_dna_adapter", False)):
            domains.add("dna")
        if self._truthy(params.get("is_membrane_target", False)) or self._truthy(params.get("enable_membrane_adapter", False)):
            domains.add("membrane")

        forced = []
        if not domains:
            return forced
        for i, (name, _module) in enumerate(self.all_modules):
            if i >= int(active_width):
                break
            lname = str(name).strip().lower()
            for domain in domains:
                if lname in self.domain_adapter_module_names.get(domain, ()):
                    forced.append(i)
                    break
        return forced

    def set_router_runtime_mode(self, mode: str) -> None:
        self.ai_router.set_runtime_mode(mode)
        self.router_runtime_mode = str(self.ai_router.runtime_mode)

    def set_router_disable_exploration(self, flag: bool) -> None:
        self.ai_router.set_disable_exploration(bool(flag))

    def set_uncertainty_guard(self, enabled: bool) -> None:
        self.uncertainty_guard_enabled = bool(enabled)

    def _build_uncertainty_mask(self, weights: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        if weights.numel() == 0:
            zeros = torch.zeros((weights.shape[0],), device=weights.device, dtype=weights.dtype)
            mask = torch.zeros((weights.shape[0],), device=weights.device, dtype=torch.bool)
            return mask, zeros
        n_modules = max(int(weights.shape[-1]), 1)
        entropy = -(weights.clamp_min(1e-8) * torch.log(weights.clamp_min(1e-8))).sum(dim=-1)
        entropy_norm = entropy / max(float(math.log(float(n_modules))), 1e-8)
        top1 = torch.amax(weights, dim=-1)
        uncertain = (entropy_norm >= float(self.uncertainty_entropy_threshold)) & (
            top1 <= float(self.uncertainty_top1_threshold)
        )
        return uncertain, entropy_norm

    def forward(self, c, top, nb_data, pe, sim_params, ai_influence=1.0, collect_aux=True):
        """
        Orchestrates all specialists (core & branch) using AI Router weights.
        Implements TRUE Conditional Execution: Only active modules are executed.
        This is the RISK-FIX VERSION that avoids unnecessary computation.
        Args:
            c: Coordinates [B, N, 3]
            top: Topology object
            nb_ Neighbor data from spatial hash
            pe: Potential energy tensor (from core forces)
            sim_params: Simulation parameters (temperature, salt, etc.) - Dict
            ai_influence: Scalar value (0.0 to 1.0) controlling the *overall* influence of the AI correction (from Curriculum Learning).
            collect_aux: If False, skip expensive aux/log packaging for high-throughput inference.
        Returns:
            f_orchestrated: Aggregated force corrections [B, N, 3]
            aux_outputs: Dictionary of outputs from each specialist for logging/debugging.
        """
        B, N, _ = c.shape
        device = c.device
        f_total_ai = torch.zeros_like(c, device=device) # Initialize total AI force to zero
        collect_aux_i = bool(collect_aux)
        aux_outputs = {}

        # --- STEP 1: Run AIRouter FIRST to get weights and active mask ---
        module_keys_all = [name for name, _ in self.all_modules]
        weights, was_explored, module_keys, active_mask = self.ai_router.route(
            c=c,
            top=top,
            sim_params=sim_params,
            module_keys=module_keys_all,
        )
        self.last_router_runtime_mode = str(self.ai_router.runtime_mode)
        self.last_router_script_error = self.ai_router._script_router_error
        self.last_router_onnx_providers = list(getattr(self.ai_router, "_onnx_router_providers", []))
        self.last_router_onnx_model_path = getattr(self.ai_router, "_onnx_router_model_path", None)
        self.last_router_onnx_iobinding_enabled = bool(
            getattr(self.ai_router, "_onnx_router_iobinding_enabled", False)
        )
        self.last_router_onnx_iobinding_error = getattr(
            self.ai_router, "_onnx_router_iobinding_error", None
        )

        # --- STEP 2: Identify ACTIVE modules and execute ONLY them ---
        active_width = min(int(active_mask.shape[1]), int(len(self.all_modules)))
        active_mask_f = active_mask.to(dtype=c.dtype)
        forced_domain_indices = self._infer_forced_domain_adapter_indices(
            sim_params=sim_params,
            active_width=active_width,
        )
        if forced_domain_indices:
            force_idx = torch.tensor(forced_domain_indices, dtype=torch.long, device=device)
            active_mask_f[:, force_idx] = 1.0
            active_mask = active_mask_f
            weights_masked = weights * active_mask_f
            row_sum = weights_masked.sum(dim=-1, keepdim=True)
            fallback_idx = torch.argmax(weights, dim=-1, keepdim=True)
            fallback_mask = torch.zeros_like(active_mask_f).scatter_(1, fallback_idx, 1.0)
            row_sum_safe = row_sum.clamp_min(1e-8)
            weights = torch.where(
                row_sum <= 1e-8,
                weights * fallback_mask,
                weights_masked / row_sum_safe,
            )
        active_any = torch.zeros(len(self.all_modules), dtype=torch.bool, device=device)
        if active_width > 0:
            active_any[:active_width] = active_mask[:, :active_width].bool().any(dim=0)

        centered_cache = None

        def _fallback_force(module_name: str) -> torch.Tensor:
            nonlocal centered_cache
            if centered_cache is None:
                centered_cache = c - c.mean(dim=1, keepdim=True)
            head = self.module_fallback_heads[module_name]
            scale = torch.tanh(self.module_fallback_scales[module_name])
            return head(centered_cache) * scale

        if collect_aux_i:
            iter_indices = range(len(self.all_modules))
        else:
            iter_indices = torch.nonzero(active_any, as_tuple=False).flatten().tolist()

        for idx in iter_indices:
            name, module = self.all_modules[int(idx)]
            if int(idx) >= int(active_width):
                if collect_aux_i:
                    aux_outputs[name] = {"skipped": True}
                continue
            if not bool(active_any[int(idx)]):
                if collect_aux_i:
                    aux_outputs[name] = {"skipped": True}
                continue

            module_weight_expanded = weights[:, int(idx)].view(B, 1, 1)
            module_active_mask_expanded = active_mask_f[:, int(idx)].view(B, 1, 1)
            skip_specialist_call = bool(
                self.skip_zero_specialists and self.module_zero_output_hints.get(str(name), False)
            )

            try:
                used_fallback_head = False
                info = {}

                if skip_specialist_call:
                    f_spec = _fallback_force(name)
                    used_fallback_head = True
                    if collect_aux_i:
                        info = {
                            "skipped_specialist_call": True,
                            "used_fallback_head": True,
                            "mean_force": 0.0,
                        }
                else:
                    f_spec, raw_info = module(c, top, nb_data, pe, sim_params)
                    spec_is_invalid = (
                        (not isinstance(f_spec, torch.Tensor))
                        or (f_spec.shape != c.shape)
                        or (not torch.isfinite(f_spec).all())
                    )
                    if spec_is_invalid:
                        f_spec = _fallback_force(name)
                        used_fallback_head = True
                    else:
                        # Keep legacy behavior: zero-output specialists are replaced by
                        # learnable fallback force heads.
                        spec_zero_mask = (
                            f_spec.detach().abs().amax(dim=(1, 2), keepdim=True) < 1e-12
                        )
                        f_spec_fallback = _fallback_force(name)
                        f_spec = torch.where(spec_zero_mask, f_spec_fallback, f_spec)
                        if collect_aux_i and bool(spec_zero_mask.any().item()):
                            used_fallback_head = True
                    if collect_aux_i:
                        if isinstance(raw_info, dict):
                            info = dict(raw_info)
                        else:
                            info = {"module_info": str(type(raw_info))}
                        info["used_fallback_head"] = bool(used_fallback_head)

                f_total_ai += f_spec * module_weight_expanded * module_active_mask_expanded
                if collect_aux_i:
                    aux_outputs[name] = info
            except Exception as e:
                print(f"Warning: Error running module '{name}': {e}")
                if collect_aux_i:
                    aux_outputs[name] = {"error": str(e)}

        # --- STEP 3: Apply Learnable Mixing and Curriculum Influence ---
        mixing_ratio = torch.sigmoid(self.balance_weight) # Value between 0 and 1
        effective_ai_influence = ai_influence * mixing_ratio # [0, ai_influence]
        f_ai_corr_scaled = effective_ai_influence * f_total_ai # Scale the total AI correction force

        # --- STEP 4: Store last state for logging and feedback ---
        self.last_router_weights = weights.detach()
        self.last_router_module_names = [name for name, _ in self.all_modules] # Use the actual module order
        self.last_was_explored = was_explored.detach()
        self.last_mixing_ratio = mixing_ratio.detach()
        self.last_effective_ai_influence = effective_ai_influence.detach()
        self.last_active_mask = active_mask.detach()
        self.last_active_modules_per_batch = self.last_active_mask.sum(dim=-1).detach()
        self.last_router_action_log_probs = torch.log(weights.clamp_min(1e-8)).detach()

        uncertainty_mask, uncertainty_score = self._build_uncertainty_mask(weights.detach())
        guard_active = bool(self.uncertainty_guard_enabled) and (
            bool(self.uncertainty_apply_in_train) or (not bool(self.training))
        )
        if guard_active:
            f_ai_corr_scaled = torch.where(
                uncertainty_mask.view(-1, 1, 1),
                torch.zeros_like(f_ai_corr_scaled),
                f_ai_corr_scaled,
            )
        self.last_uncertainty_score = uncertainty_score.detach()
        self.last_uncertainty_score_mean = float(uncertainty_score.mean().item())
        self.last_uncertainty_fallback_mask = uncertainty_mask.detach()
        self.last_uncertainty_fallback_rate = float(uncertainty_mask.float().mean().item())

        if collect_aux_i:
            # [NEW] aux_outputs에 믹싱 비율 및 효과 정보 추가 (로그용)
            aux_outputs['router_balance_weight'] = self.balance_weight.detach().cpu()
            aux_outputs['router_mixing_ratio'] = self.last_mixing_ratio.cpu()
            aux_outputs['router_effective_ai_influence'] = self.last_effective_ai_influence.cpu()
            aux_outputs['router_active_mask'] = self.last_active_mask.cpu()
            aux_outputs['router_active_modules_per_batch'] = self.last_active_modules_per_batch.cpu()
            # Backward-compat keys used by existing tests/tools
            aux_outputs['router_was_explored'] = self.last_was_explored.cpu()
            aux_outputs['router_used_weights'] = self.last_router_weights.cpu()
            aux_outputs['router_action_log_probs'] = self.last_router_action_log_probs.cpu()
            aux_outputs['router_module_names'] = module_keys
            aux_outputs['router_runtime_mode'] = str(self.last_router_runtime_mode)
            aux_outputs['router_script_error'] = self.last_router_script_error
            aux_outputs['router_onnx_providers'] = list(self.last_router_onnx_providers or [])
            aux_outputs['router_onnx_model_path'] = self.last_router_onnx_model_path
            aux_outputs['router_onnx_iobinding_enabled'] = bool(
                self.last_router_onnx_iobinding_enabled
            )
            aux_outputs['router_onnx_iobinding_error'] = self.last_router_onnx_iobinding_error
            aux_outputs['router_uncertainty_score'] = self.last_uncertainty_score.cpu()
            aux_outputs['router_uncertainty_score_mean'] = float(self.last_uncertainty_score_mean)
            aux_outputs['router_uncertainty_fallback_mask'] = self.last_uncertainty_fallback_mask.cpu()
            aux_outputs['router_uncertainty_fallback_rate'] = float(self.last_uncertainty_fallback_rate)
            aux_outputs['router_uncertainty_guard_enabled'] = bool(guard_active)

        f_orchestrated = f_ai_corr_scaled # Return the scaled AI correction

        return f_orchestrated, aux_outputs

    # [MODIFIED] Method to retrieve last router info
    def get_last_router_info(self):
        """
        Returns the weights, exploration status, mixing information, and active mask from the last call to forward().
        """
        return self.last_router_weights, self.last_router_module_names, self.last_was_explored, self.last_mixing_ratio, self.last_effective_ai_influence, self.last_active_mask
