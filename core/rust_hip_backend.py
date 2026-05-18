import importlib
import os
import time
from dataclasses import dataclass
from typing import Any, Optional, Sequence

import torch
from .zero_copy import to_dlpack


# 안정 경로만 포함 — 실험적 fused cell-list 커널 제거 (2026-02-23)
_KERNEL_CANDIDATES = (
    "compute_nonbonded_nblist_gpu",
    "compute_nonbonded_gpu",
    "hip_nonbonded_kernel_fp16",
    "hip_nonbonded_kernel",
    "nonbonded_kernel",
    "hip_nonbonded",
)


@dataclass
class RustHipProbeStatus:
    enabled: bool
    reason: str
    module_name: str = "ldi_arc_rust"
    module_loaded: bool = False
    module_path: Optional[str] = None
    kernel_name: Optional[str] = None
    device_type: str = "unknown"
    torch_cuda_available: bool = False
    kfd_accessible: Optional[bool] = None
    kfd_error: Optional[str] = None
    isa_match: Optional[bool] = None
    isa_info: Optional[str] = None
    exported_symbols: Sequence[str] = ()


def _check_kfd_access(path: str = "/dev/kfd"):
    try:
        fd = os.open(path, os.O_RDWR | getattr(os, "O_CLOEXEC", 0))
        os.close(fd)
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _select_kernel(module: Any):
    """Select the fastest guarded kernel exposed by the loaded extension."""
    if os.getenv("RUST_HIP_USE_FUSED_CELL", "").strip().lower() in {"1", "true", "yes", "on"}:
        if hasattr(module, "compute_nonbonded_celllist_gpu"):
            return "compute_nonbonded_celllist_gpu"
    for name in _KERNEL_CANDIDATES:
        if hasattr(module, name):
            return name
    return None


def diagnose_hip_binary_mismatch() -> dict:
    """hipcc 버전 및 GPU ISA 확인으로 hipErrorNoBinaryForGpu 원인 진단.

    Returns:
        진단 결과 딕셔너리 (hipcc_version, gpu_arch, isa_match, details).
    """
    import subprocess
    result = {"hipcc_version": None, "gpu_arch": None, "isa_match": None, "details": ""}
    try:
        proc = subprocess.run(
            ["hipcc", "--version"],
            capture_output=True, text=True, timeout=5.0,
        )
        result["hipcc_version"] = proc.stdout.strip() or proc.stderr.strip()
    except Exception as exc:
        result["details"] += f"hipcc 실행 실패: {exc}. "
        return result

    try:
        proc2 = subprocess.run(
            ["rocminfo"],
            capture_output=True, text=True, timeout=5.0,
        )
        import re
        matches = re.findall(r"Name:\s+(gfx\w+)", proc2.stdout)
        if matches:
            result["gpu_arch"] = matches[0]
    except Exception as exc:
        result["details"] += f"rocminfo 실행 실패: {exc}. "

    if result["hipcc_version"] and result["gpu_arch"]:
        # 커널이 해당 ISA로 빌드되었는지 간접 확인
        result["isa_match"] = result["gpu_arch"] in (result["hipcc_version"] or "")
        if not result["isa_match"]:
            result["details"] += (
                f"GPU ISA ({result['gpu_arch']})가 hipcc 빌드 타겟에 "
                f"포함되지 않았을 수 있음. 재컴파일 필요."
            )
    return result


class KernelFusionOccupancyGuard:
    """커널 퓨전 occupancy 가드.

    커널 퓨전 시 레지스터 사용량이 증가하면 occupancy가 떨어져
    오히려 성능이 저하됩니다. 이 가드는 occupancy 비율이
    ``max_occupancy_ratio`` 이하인 경우에만 퓨전을 허용합니다.

    설정 예시 (settings.yaml):
        spatial:
          kernel_fusion:
            max_occupancy_ratio: 0.8
    """

    def __init__(self, max_occupancy_ratio: float = 0.8):
        self.max_occupancy_ratio = float(min(max(max_occupancy_ratio, 0.0), 1.0))
        self._last_occupancy: float = 1.0
        self._fusion_allowed: bool = True

    @staticmethod
    def query_kernel_occupancy(kernel_name: str) -> float:
        """HIP/CUDA 커널의 현재 occupancy를 쿼리합니다.

        실제 구현은 hipOccupancyMaxActiveBlocksPerMultiprocessor 또는
        torch.cuda.get_device_capability 기반 추정을 사용합니다.
        현재는 보수적 추정값(0.75)을 반환합니다.

        Returns:
            occupancy 비율 (0.0 ~ 1.0)
        """
        # 실제 HIP/CUDA occupancy API 호출 위치
        # hipOccupancyMaxActiveBlocksPerMultiprocessor 또는
        # cuOccupancyMaxActiveBlocksPerMultiprocessor 사용 예정
        try:
            if torch.cuda.is_available():
                cap = torch.cuda.get_device_capability()
                # SM 아키텍처별 보수적 추정
                if cap[0] >= 8:  # Ampere/Ada/Hopper
                    return 0.75
                elif cap[0] >= 7:  # Volta/Turing
                    return 0.65
                else:
                    return 0.50
        except Exception:
            pass
        return 0.75  # 기본 보수적 추정

    def check_fusion_allowed(self, kernel_name: str = "") -> bool:
        """퓨전 커널 사용이 occupancy 관점에서 허용되는지 검사.

        Args:
            kernel_name: 커널 이름 (occupancy 쿼리용)

        Returns:
            True면 퓨전 허용, False면 분리 커널 사용 권장
        """
        occ = self.query_kernel_occupancy(kernel_name)
        self._last_occupancy = occ
        self._fusion_allowed = occ >= self.max_occupancy_ratio
        return self._fusion_allowed

    @property
    def last_occupancy(self) -> float:
        return self._last_occupancy

    @property
    def fusion_allowed(self) -> bool:
        return self._fusion_allowed

    def get_status(self) -> dict:
        return {
            "max_occupancy_ratio": self.max_occupancy_ratio,
            "last_occupancy": self._last_occupancy,
            "fusion_allowed": self._fusion_allowed,
        }


def probe_rust_hip_backend(module_name: str = "ldi_arc_rust", device=None) -> RustHipProbeStatus:
    if device is None:
        from core.config import config

        device = config.DEVICE

    device_type = getattr(device, "type", str(device))
    cuda_available = torch.cuda.is_available()
    kfd_ok, kfd_error = _check_kfd_access()

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return RustHipProbeStatus(
            enabled=False,
            reason=f"module import failed: {type(exc).__name__}: {exc}",
            module_name=module_name,
            module_loaded=False,
            device_type=device_type,
            torch_cuda_available=cuda_available,
            kfd_accessible=kfd_ok,
            kfd_error=kfd_error,
        )

    exported = tuple(
        sorted(
            name
            for name in dir(module)
            if ("hip" in name.lower()) or ("nonbonded" in name.lower()) or ("kernel" in name.lower())
        )
    )
    kernel_name = _select_kernel(module)

    if kernel_name is None:
        return RustHipProbeStatus(
            enabled=False,
            reason="no supported nonbonded HIP kernel symbol in module",
            module_name=module_name,
            module_loaded=True,
            module_path=getattr(module, "__file__", None),
            kernel_name=None,
            device_type=device_type,
            torch_cuda_available=cuda_available,
            kfd_accessible=kfd_ok,
            kfd_error=kfd_error,
            exported_symbols=exported,
        )

    if device_type != "cuda":
        return RustHipProbeStatus(
            enabled=False,
            reason=f"device.type is '{device_type}' (requires 'cuda' for HIP path)",
            module_name=module_name,
            module_loaded=True,
            module_path=getattr(module, "__file__", None),
            kernel_name=kernel_name,
            device_type=device_type,
            torch_cuda_available=cuda_available,
            kfd_accessible=kfd_ok,
            kfd_error=kfd_error,
            exported_symbols=exported,
        )

    if not cuda_available:
        return RustHipProbeStatus(
            enabled=False,
            reason="torch.cuda.is_available() is False",
            module_name=module_name,
            module_loaded=True,
            module_path=getattr(module, "__file__", None),
            kernel_name=kernel_name,
            device_type=device_type,
            torch_cuda_available=cuda_available,
            kfd_accessible=kfd_ok,
            kfd_error=kfd_error,
            exported_symbols=exported,
        )

    if not kfd_ok:
        return RustHipProbeStatus(
            enabled=False,
            reason=f"/dev/kfd not accessible: {kfd_error}",
            module_name=module_name,
            module_loaded=True,
            module_path=getattr(module, "__file__", None),
            kernel_name=kernel_name,
            device_type=device_type,
            torch_cuda_available=cuda_available,
            kfd_accessible=kfd_ok,
            kfd_error=kfd_error,
            exported_symbols=exported,
        )

    return RustHipProbeStatus(
        enabled=True,
        reason="ready",
        module_name=module_name,
        module_loaded=True,
        module_path=getattr(module, "__file__", None),
        kernel_name=kernel_name,
        device_type=device_type,
        torch_cuda_available=cuda_available,
        kfd_accessible=kfd_ok,
        kfd_error=kfd_error,
        exported_symbols=exported,
    )


class RustHipBackend:
    def __init__(self, module_name: str = "ldi_arc_rust", device=None):
        self.status = probe_rust_hip_backend(module_name=module_name, device=device)
        self.module_name = module_name
        self._kernel = None
        self._neighbor_builder = None
        self._direct_rollout = None
        self._idp_virtual_hbond = None
        self._idp_local_density = None
        self._idp_sticker_bridge = None
        self._cached_force = None
        self._cached_energy = None
        self._cached_idp_force = None
        self._cached_idp_contacts = None
        self._cached_idp_mean_distance = None
        self._cached_idp_local_density = None
        self._cached_idp_sticker_force = None
        self._cached_idp_bridge_force = None
        self._cached_idp_sticker_contacts = None
        self._cached_idp_pi_pi_contacts = None
        self._cached_idp_cation_pi_contacts = None
        self._cached_idp_bridge_contacts = None
        self._cached_shape = None
        self._cached_device = None
        self._cached_idp_shape = None
        self._cached_idp_pair_shape = None
        self._cached_nb_idx = None
        self._cached_nb_mask = None
        self._cached_nb_dist = None
        self._cached_nb_shape = None
        self._cached_cell_counts = None
        self._cached_cell_atoms = None
        self._cached_cells_shape = None
        self.last_idp_virtual_hbond_profile = {}
        self.last_idp_sticker_bridge_profile = {}
        self.last_neighbor_build_stats = {}
        if self.status.enabled and self.status.kernel_name:
            module = importlib.import_module(module_name)
            self._kernel = getattr(module, self.status.kernel_name)
            if hasattr(module, "build_neighbor_list_gpu"):
                self._neighbor_builder = getattr(module, "build_neighbor_list_gpu")
            if hasattr(module, "rollout_ligand_direct_gpu"):
                self._direct_rollout = getattr(module, "rollout_ligand_direct_gpu")
            if hasattr(module, "compute_idp_virtual_hbond_nblist_gpu"):
                self._idp_virtual_hbond = getattr(module, "compute_idp_virtual_hbond_nblist_gpu")
            if hasattr(module, "compute_idp_local_density_nblist_gpu"):
                self._idp_local_density = getattr(module, "compute_idp_local_density_nblist_gpu")
            if hasattr(module, "compute_idp_sticker_bridge_nblist_gpu"):
                self._idp_sticker_bridge = getattr(module, "compute_idp_sticker_bridge_nblist_gpu")

    @property
    def enabled(self):
        return self.status.enabled and self._kernel is not None

    def needs_neighbor_list(self):
        return self.status.kernel_name == "compute_nonbonded_nblist_gpu"

    def uses_fused_cell_list(self):
        # 실험적 fused cell-list 경로 비활성화 (2026-02-23)
        return False

    def has_neighbor_builder(self):
        return (
            self._neighbor_builder is not None
            and self.enabled
            and os.environ.get("RUST_HIP_USE_GPU_NBLIST_BUILDER", "0") == "1"
        )

    def supports_direct_rollout(self):
        return self._direct_rollout is not None and self.enabled

    def supports_idp_virtual_hbond(self):
        return self._idp_virtual_hbond is not None and self.enabled

    def supports_idp_local_density(self):
        return self._idp_local_density is not None and self.enabled

    def supports_idp_sticker_bridge(self):
        return self._idp_sticker_bridge is not None and self.enabled

    def _prepare_output_buffers(self, coords_input: torch.Tensor):
        batch_size, n_per_replica, _ = coords_input.shape
        device = coords_input.device
        shape = (batch_size, n_per_replica, 3)

        if (
            self._cached_force is None
            or self._cached_energy is None
            or self._cached_shape != shape
            or self._cached_device != device
        ):
            self._cached_force = torch.zeros(shape, dtype=torch.float32, device=device)
            self._cached_energy = torch.zeros((batch_size, 1), dtype=torch.float32, device=device)
            self._cached_shape = shape
            self._cached_device = device
        else:
            self._cached_force.zero_()
            self._cached_energy.zero_()
        return self._cached_force, self._cached_energy

    def _prepare_idp_virtual_hbond_buffers(self, donor_input: torch.Tensor):
        batch_size, n_per_replica, _ = donor_input.shape
        device = donor_input.device
        shape = (batch_size, n_per_replica, 3)
        if (
            self._cached_idp_force is None
            or self._cached_idp_contacts is None
            or self._cached_idp_mean_distance is None
            or self._cached_idp_shape != shape
            or self._cached_device != device
        ):
            self._cached_idp_force = torch.zeros(shape, dtype=torch.float32, device=device)
            self._cached_idp_contacts = torch.zeros((batch_size,), dtype=torch.float32, device=device)
            self._cached_idp_mean_distance = torch.zeros((batch_size,), dtype=torch.float32, device=device)
            self._cached_idp_shape = shape
            self._cached_device = device
        return self._cached_idp_force, self._cached_idp_contacts, self._cached_idp_mean_distance

    def _prepare_idp_local_density_buffer(self, nb_idx: torch.Tensor):
        batch_size, n_per_replica, _ = nb_idx.shape
        device = nb_idx.device
        shape = (batch_size, n_per_replica)
        if (
            self._cached_idp_local_density is None
            or self._cached_idp_local_density.shape != shape
            or self._cached_device != device
        ):
            self._cached_idp_local_density = torch.zeros(shape, dtype=torch.float32, device=device)
            self._cached_device = device
        return self._cached_idp_local_density

    def _prepare_idp_sticker_bridge_buffers(self, coords_input: torch.Tensor):
        batch_size, n_per_replica, _ = coords_input.shape
        device = coords_input.device
        shape = (batch_size, n_per_replica, 3)
        if (
            self._cached_idp_sticker_force is None
            or self._cached_idp_bridge_force is None
            or self._cached_idp_sticker_contacts is None
            or self._cached_idp_pi_pi_contacts is None
            or self._cached_idp_cation_pi_contacts is None
            or self._cached_idp_bridge_contacts is None
            or self._cached_idp_pair_shape != shape
            or self._cached_device != device
        ):
            self._cached_idp_sticker_force = torch.zeros(shape, dtype=torch.float32, device=device)
            self._cached_idp_bridge_force = torch.zeros(shape, dtype=torch.float32, device=device)
            self._cached_idp_sticker_contacts = torch.zeros((batch_size,), dtype=torch.float32, device=device)
            self._cached_idp_pi_pi_contacts = torch.zeros((batch_size,), dtype=torch.float32, device=device)
            self._cached_idp_cation_pi_contacts = torch.zeros((batch_size,), dtype=torch.float32, device=device)
            self._cached_idp_bridge_contacts = torch.zeros((batch_size,), dtype=torch.float32, device=device)
            self._cached_idp_pair_shape = shape
            self._cached_device = device
        return (
            self._cached_idp_sticker_force,
            self._cached_idp_bridge_force,
            self._cached_idp_sticker_contacts,
            self._cached_idp_pi_pi_contacts,
            self._cached_idp_cation_pi_contacts,
            self._cached_idp_bridge_contacts,
        )

    def _launch_idp_virtual_hbond(
        self,
        donor: torch.Tensor,
        acceptor: torch.Tensor,
        ca: torch.Tensor,
        sc: torch.Tensor,
        disorder: torch.Tensor,
        aromatic_mask: torch.Tensor,
        cationic_mask: torch.Tensor,
        sticker_mask: torch.Tensor,
        nb_idx: torch.Tensor,
        nb_dist: torch.Tensor,
        nb_mask: torch.Tensor,
        vh_scale: torch.Tensor,
        contact_gain_scale: torch.Tensor,
        exposure_sensitivity: torch.Tensor,
        exposure_gain_scale: torch.Tensor,
        center: torch.Tensor,
        width: torch.Tensor,
        llps_branch: torch.Tensor,
        is_llps_target: torch.Tensor,
        is_hnrn_target: torch.Tensor,
        is_fus_target: torch.Tensor,
        env_scale: torch.Tensor,
        vh_strength: torch.Tensor,
        unsat_penalty: torch.Tensor,
    ):
        profile_enabled = str(os.environ.get("IDP_VIRTUAL_HBOND_PROFILE", "0")).strip().lower() not in {"", "0", "false", "off", "no"}
        total_started = time.perf_counter() if profile_enabled else 0.0
        buffer_started = time.perf_counter() if profile_enabled else 0.0
        force, contacts, mean_distance = self._prepare_idp_virtual_hbond_buffers(donor)
        local_density = self._prepare_idp_local_density_buffer(nb_idx)
        buffer_elapsed_ms = (time.perf_counter() - buffer_started) * 1000.0 if profile_enabled else 0.0
        batch_size, n_per_replica, _ = donor.shape
        max_neighbors = int(nb_idx.shape[-1])
        stream = torch.cuda.current_stream(device=donor.device)
        stream_ptr = int(getattr(stream, "cuda_stream", 0) or 0)
        kernel_ms = 0.0
        post_ms = 0.0
        if profile_enabled:
            kernel_start = torch.cuda.Event(enable_timing=True)
            kernel_end = torch.cuda.Event(enable_timing=True)
            post_start = torch.cuda.Event(enable_timing=True)
            post_end = torch.cuda.Event(enable_timing=True)
            kernel_start.record(stream)

        self._idp_virtual_hbond(
            int(donor.data_ptr()),
            int(acceptor.data_ptr()),
            int(ca.data_ptr()),
            int(sc.data_ptr()),
            int(disorder.data_ptr()),
            int(aromatic_mask.data_ptr()),
            int(cationic_mask.data_ptr()),
            int(sticker_mask.data_ptr()),
            int(local_density.data_ptr()),
            int(nb_idx.data_ptr()),
            int(nb_dist.data_ptr()),
            int(nb_mask.data_ptr()),
            int(force.data_ptr()),
            int(contacts.data_ptr()),
            int(mean_distance.data_ptr()),
            int(n_per_replica),
            int(batch_size),
            int(max_neighbors),
            int(center.data_ptr()),
            int(width.data_ptr()),
            int(vh_strength.data_ptr()),
            int(env_scale.data_ptr()),
            int(vh_scale.data_ptr()),
            int(contact_gain_scale.data_ptr()),
            int(exposure_sensitivity.data_ptr()),
            int(exposure_gain_scale.data_ptr()),
            int(llps_branch.data_ptr()),
            int(is_llps_target.data_ptr()),
            int(is_hnrn_target.data_ptr()),
            int(is_fus_target.data_ptr()),
            int(unsat_penalty.data_ptr()),
            int(stream_ptr),
        )
        if profile_enabled:
            kernel_end.record(stream)
            post_start.record(stream)
        if profile_enabled:
            post_end.record(stream)
            post_end.synchronize()
            kernel_ms = float(kernel_start.elapsed_time(kernel_end))
            post_ms = float(post_start.elapsed_time(post_end))
            self.last_idp_virtual_hbond_profile = {
                "buffer_ms": float(buffer_elapsed_ms),
                "kernel_ms": float(kernel_ms),
                "post_ms": float(post_ms),
                "launch_cpu_ms": float((time.perf_counter() - total_started) * 1000.0),
            }
        else:
            self.last_idp_virtual_hbond_profile = {}
        return force, contacts, mean_distance

    def compute_idp_virtual_hbond_prepared(
        self,
        *,
        donor: torch.Tensor,
        acceptor: torch.Tensor,
        ca: torch.Tensor,
        sc: torch.Tensor,
        disorder: torch.Tensor,
        aromatic_mask: torch.Tensor,
        cationic_mask: torch.Tensor,
        sticker_mask: torch.Tensor,
        nb_idx: torch.Tensor,
        nb_dist: torch.Tensor,
        nb_mask: torch.Tensor,
        virtual_hbond_scale: torch.Tensor,
        contact_gain_scale: torch.Tensor,
        exposure_sensitivity: torch.Tensor,
        exposure_gain_scale: torch.Tensor,
        virtual_hbond_center_A: torch.Tensor,
        virtual_hbond_width_A: torch.Tensor,
        llps_branch: torch.Tensor,
        is_llps_target: torch.Tensor,
        is_hnrn_target: torch.Tensor,
        is_fus_target: torch.Tensor,
        env_scale: torch.Tensor,
        virtual_hbond_strength: torch.Tensor,
        unsat_penalty_strength: torch.Tensor,
    ):
        if not self.supports_idp_virtual_hbond():
            raise RuntimeError("Rust HIP IDP virtual_hbond backend is unavailable")
        if not donor.is_cuda:
            raise RuntimeError("compute_idp_virtual_hbond_prepared requires CUDA tensors")
        return self._launch_idp_virtual_hbond(
            donor=donor,
            acceptor=acceptor,
            ca=ca,
            sc=sc,
            disorder=disorder,
            aromatic_mask=aromatic_mask,
            cationic_mask=cationic_mask,
            sticker_mask=sticker_mask,
            nb_idx=nb_idx,
            nb_dist=nb_dist,
            nb_mask=nb_mask,
            vh_scale=virtual_hbond_scale,
            contact_gain_scale=contact_gain_scale,
            exposure_sensitivity=exposure_sensitivity,
            exposure_gain_scale=exposure_gain_scale,
            center=virtual_hbond_center_A,
            width=virtual_hbond_width_A,
            llps_branch=llps_branch,
            is_llps_target=is_llps_target,
            is_hnrn_target=is_hnrn_target,
            is_fus_target=is_fus_target,
            env_scale=env_scale,
            vh_strength=virtual_hbond_strength,
            unsat_penalty=unsat_penalty_strength,
        )

    def compute_idp_local_density_prepared(
        self,
        *,
        nb_idx: torch.Tensor,
        nb_dist: torch.Tensor,
        nb_mask: torch.Tensor,
        min_gap: int = 3,
    ) -> torch.Tensor:
        if not self.supports_idp_local_density():
            raise RuntimeError("Rust HIP IDP local_density backend is unavailable")
        if not nb_idx.is_cuda or not nb_dist.is_cuda or not nb_mask.is_cuda:
            raise RuntimeError("compute_idp_local_density_prepared requires CUDA tensors")
        if nb_idx.dtype != torch.int64:
            nb_idx = nb_idx.to(dtype=torch.int64)
        if nb_dist.dtype != torch.float32:
            nb_dist = nb_dist.to(dtype=torch.float32)
        if nb_mask.dtype != torch.uint8:
            nb_mask = (nb_mask > 0.5).to(dtype=torch.uint8)
        if not nb_idx.is_contiguous():
            nb_idx = nb_idx.contiguous()
        if not nb_dist.is_contiguous():
            nb_dist = nb_dist.contiguous()
        if not nb_mask.is_contiguous():
            nb_mask = nb_mask.contiguous()
        out = self._prepare_idp_local_density_buffer(nb_idx)
        batch_size, n_per_replica, max_neighbors = nb_idx.shape
        self._idp_local_density(
            int(nb_idx.data_ptr()),
            int(nb_dist.data_ptr()),
            int(nb_mask.data_ptr()),
            int(out.data_ptr()),
            int(n_per_replica),
            int(batch_size),
            int(max_neighbors),
            int(min_gap),
        )
        return out

    def _launch_idp_sticker_bridge(
        self,
        *,
        ca: torch.Tensor,
        sc: torch.Tensor,
        aromatic_mask: torch.Tensor,
        cationic_mask: torch.Tensor,
        sticker_mask: torch.Tensor,
        nb_idx: torch.Tensor,
        nb_dist: torch.Tensor,
        nb_mask: torch.Tensor,
        sticker_strength: torch.Tensor,
        bridge_strength: torch.Tensor,
        env_scale: torch.Tensor,
        llps_branch: torch.Tensor,
        agg_branch: torch.Tensor,
        helix_branch: torch.Tensor,
        is_llps_target: torch.Tensor,
        is_hnrn_target: torch.Tensor,
        is_fus_target: torch.Tensor,
        arg_fraction: torch.Tensor,
        aromatic_fraction: torch.Tensor,
        collect_contacts: bool,
    ):
        profile_enabled = str(os.environ.get("IDP_STICKER_BRIDGE_PROFILE", "0")).strip().lower() not in {"", "0", "false", "off", "no"}
        total_started = time.perf_counter() if profile_enabled else 0.0
        buffer_started = time.perf_counter() if profile_enabled else 0.0
        (
            sticker_force,
            bridge_force,
            sticker_contacts,
            pi_pi_contacts,
            cation_pi_contacts,
            bridge_contacts,
        ) = self._prepare_idp_sticker_bridge_buffers(ca)
        local_density = self._prepare_idp_local_density_buffer(nb_idx)
        buffer_elapsed_ms = (time.perf_counter() - buffer_started) * 1000.0 if profile_enabled else 0.0
        batch_size, n_per_replica, _ = ca.shape
        max_neighbors = int(nb_idx.shape[-1])
        stream = torch.cuda.current_stream(device=ca.device)
        stream_ptr = int(getattr(stream, "cuda_stream", 0) or 0)
        launch_started = time.perf_counter() if profile_enabled else 0.0
        self._idp_sticker_bridge(
            int(ca.data_ptr()),
            int(sc.data_ptr()),
            int(aromatic_mask.data_ptr()),
            int(cationic_mask.data_ptr()),
            int(sticker_mask.data_ptr()),
            int(local_density.data_ptr()),
            int(nb_idx.data_ptr()),
            int(nb_dist.data_ptr()),
            int(nb_mask.data_ptr()),
            int(sticker_force.data_ptr()),
            int(bridge_force.data_ptr()),
            int(sticker_contacts.data_ptr()),
            int(pi_pi_contacts.data_ptr()),
            int(cation_pi_contacts.data_ptr()),
            int(bridge_contacts.data_ptr()),
            int(n_per_replica),
            int(batch_size),
            int(max_neighbors),
            int(sticker_strength.data_ptr()),
            int(bridge_strength.data_ptr()),
            int(env_scale.data_ptr()),
            int(llps_branch.data_ptr()),
            int(agg_branch.data_ptr()),
            int(helix_branch.data_ptr()),
            int(is_llps_target.data_ptr()),
            int(is_hnrn_target.data_ptr()),
            int(is_fus_target.data_ptr()),
            int(arg_fraction.data_ptr()),
            int(aromatic_fraction.data_ptr()),
            int(1 if collect_contacts else 0),
            int(stream_ptr),
        )
        if profile_enabled:
            self.last_idp_sticker_bridge_profile = {
                "buffer_ms": float(buffer_elapsed_ms),
                "launch_cpu_ms": float((time.perf_counter() - launch_started) * 1000.0),
                "total_cpu_ms": float((time.perf_counter() - total_started) * 1000.0),
            }
        else:
            self.last_idp_sticker_bridge_profile = {}
        return (
            sticker_force,
            bridge_force,
            sticker_contacts,
            pi_pi_contacts,
            cation_pi_contacts,
            bridge_contacts,
        )

    def compute_idp_sticker_bridge_prepared(
        self,
        *,
        ca: torch.Tensor,
        sc: torch.Tensor,
        aromatic_mask: torch.Tensor,
        cationic_mask: torch.Tensor,
        sticker_mask: torch.Tensor,
        nb_idx: torch.Tensor,
        nb_dist: torch.Tensor,
        nb_mask: torch.Tensor,
        sticker_strength: torch.Tensor,
        bridge_strength: torch.Tensor,
        env_scale: torch.Tensor,
        llps_branch: torch.Tensor,
        agg_branch: torch.Tensor,
        helix_branch: torch.Tensor,
        is_llps_target: torch.Tensor,
        is_hnrn_target: torch.Tensor,
        is_fus_target: torch.Tensor,
        arg_fraction: torch.Tensor,
        aromatic_fraction: torch.Tensor,
        collect_contacts: bool = False,
    ):
        if not self.supports_idp_sticker_bridge():
            raise RuntimeError("Rust HIP IDP sticker_bridge backend is unavailable")
        if not ca.is_cuda:
            raise RuntimeError("compute_idp_sticker_bridge_prepared requires CUDA tensors")
        return self._launch_idp_sticker_bridge(
            ca=ca,
            sc=sc,
            aromatic_mask=aromatic_mask,
            cationic_mask=cationic_mask,
            sticker_mask=sticker_mask,
            nb_idx=nb_idx,
            nb_dist=nb_dist,
            nb_mask=nb_mask,
            sticker_strength=sticker_strength,
            bridge_strength=bridge_strength,
            env_scale=env_scale,
            llps_branch=llps_branch,
            agg_branch=agg_branch,
            helix_branch=helix_branch,
            is_llps_target=is_llps_target,
            is_hnrn_target=is_hnrn_target,
            is_fus_target=is_fus_target,
            arg_fraction=arg_fraction,
            aromatic_fraction=aromatic_fraction,
            collect_contacts=collect_contacts,
        )

    def export_cached_force_dlpack(self):
        if not isinstance(self._cached_force, torch.Tensor):
            return None
        return to_dlpack(self._cached_force)

    def export_cached_energy_dlpack(self):
        if not isinstance(self._cached_energy, torch.Tensor):
            return None
        return to_dlpack(self._cached_energy)

    def _prepare_neighbor_buffers(self, coords_input: torch.Tensor, max_neighbors: int):
        batch_size, n_per_replica, _ = coords_input.shape
        device = coords_input.device
        nb_shape = (batch_size, n_per_replica, max_neighbors)
        if (
            self._cached_nb_idx is None
            or self._cached_nb_mask is None
            or self._cached_nb_dist is None
            or self._cached_nb_shape != nb_shape
            or self._cached_device != device
        ):
            self._cached_nb_idx = torch.full(nb_shape, -1, dtype=torch.int64, device=device)
            self._cached_nb_mask = torch.zeros(nb_shape, dtype=torch.uint8, device=device)
            self._cached_nb_dist = torch.zeros(nb_shape, dtype=torch.float32, device=device)
            self._cached_nb_shape = nb_shape
            self._cached_device = device
        else:
            self._cached_nb_idx.fill_(-1)
            self._cached_nb_mask.zero_()
            self._cached_nb_dist.zero_()
        return self._cached_nb_idx, self._cached_nb_dist, self._cached_nb_mask

    def _prepare_cell_buffers(self, coords_input: torch.Tensor, n_cells: int, max_atoms_per_cell: int):
        batch_size, _, _ = coords_input.shape
        device = coords_input.device
        cells_shape = (batch_size, n_cells, max_atoms_per_cell)
        counts_shape = (batch_size, n_cells)
        if (
            self._cached_cell_counts is None
            or self._cached_cell_atoms is None
            or self._cached_cells_shape != cells_shape
            or self._cached_device != device
        ):
            self._cached_cell_counts = torch.zeros(counts_shape, dtype=torch.int32, device=device)
            self._cached_cell_atoms = torch.zeros(cells_shape, dtype=torch.int32, device=device)
            self._cached_cells_shape = cells_shape
            self._cached_device = device
        else:
            self._cached_cell_counts.zero_()
            self._cached_cell_atoms.zero_()
        return self._cached_cell_counts, self._cached_cell_atoms

    def build_neighbor_list(self, coords_input, box_size, cutoff, max_neighbors, grid_dims, max_atoms_per_cell=64):
        if not self.has_neighbor_builder():
            raise RuntimeError("Rust HIP neighbor builder is unavailable")
        if not isinstance(coords_input, torch.Tensor):
            raise TypeError("coords_input must be torch.Tensor for build_neighbor_list")
        if not coords_input.is_cuda:
            raise RuntimeError("build_neighbor_list requires CUDA tensor coordinates")
        if coords_input.dtype != torch.float32:
            coords_input = coords_input.float()
        coords_input = coords_input.contiguous()

        gx = int(grid_dims[0].item()) if isinstance(grid_dims, torch.Tensor) else int(grid_dims[0])
        gy = int(grid_dims[1].item()) if isinstance(grid_dims, torch.Tensor) else int(grid_dims[1])
        gz = int(grid_dims[2].item()) if isinstance(grid_dims, torch.Tensor) else int(grid_dims[2])
        n_cells = gx * gy * gz

        batch_size, n_per_replica, _ = coords_input.shape
        current_max_neighbors = int(max(max_neighbors, 1))
        current_max_atoms_per_cell = int(max(max_atoms_per_cell, 1))

        auto_grow = os.environ.get("RUST_HIP_NBLIST_AUTOGROW", "1") == "1"
        auto_rounds = max(1, int(os.environ.get("RUST_HIP_NBLIST_AUTOGROW_ROUNDS", "3")))
        max_neighbors_cap = int(
            os.environ.get(
                "RUST_HIP_NBLIST_MAX_NEIGHBORS_CAP",
                str(max(current_max_neighbors, 256)),
            )
        )
        max_atoms_per_cell_cap = int(
            os.environ.get(
                "RUST_HIP_MAX_ATOMS_PER_CELL_CAP",
                str(max(current_max_atoms_per_cell, 256)),
            )
        )
        if n_per_replica > 1:
            max_neighbors_cap = min(max_neighbors_cap, n_per_replica - 1)
        max_neighbors_cap = max(max_neighbors_cap, current_max_neighbors)
        max_atoms_per_cell_cap = max(max_atoms_per_cell_cap, current_max_atoms_per_cell)

        rounds = auto_rounds if auto_grow else 1
        nb_idx = None
        nb_dist = None
        nb_mask = None
        for attempt in range(rounds):
            nb_idx, nb_dist, nb_mask = self._prepare_neighbor_buffers(coords_input, current_max_neighbors)
            cell_counts, cell_atoms = self._prepare_cell_buffers(coords_input, n_cells, current_max_atoms_per_cell)

            self._neighbor_builder(
                int(coords_input.data_ptr()),
                int(cell_counts.data_ptr()),
                int(cell_atoms.data_ptr()),
                int(nb_idx.data_ptr()),
                int(nb_dist.data_ptr()),
                int(nb_mask.data_ptr()),
                int(n_per_replica),
                int(batch_size),
                float(box_size),
                float(cutoff),
                int(gx),
                int(gy),
                int(gz),
                int(current_max_atoms_per_cell),
                int(current_max_neighbors),
            )

            with torch.no_grad():
                row_counts = nb_mask.sum(dim=-1)
                max_row_count = int(row_counts.max().item()) if row_counts.numel() > 0 else 0
                saturated_atoms = int((row_counts >= current_max_neighbors).sum().item()) if row_counts.numel() > 0 else 0
                saturated_ratio = (
                    float((row_counts >= current_max_neighbors).float().mean().item()) if row_counts.numel() > 0 else 0.0
                )
                max_cell_count = int(cell_counts.max().item()) if cell_counts.numel() > 0 else 0

            neighbor_saturated = max_row_count >= current_max_neighbors and saturated_atoms > 0
            cell_overflow = max_cell_count > current_max_atoms_per_cell
            self.last_neighbor_build_stats = {
                "attempt": int(attempt + 1),
                "max_neighbors": int(current_max_neighbors),
                "max_atoms_per_cell": int(current_max_atoms_per_cell),
                "max_row_count": int(max_row_count),
                "saturated_atoms": int(saturated_atoms),
                "saturated_ratio": float(saturated_ratio),
                "max_cell_count": int(max_cell_count),
                "neighbor_saturated": bool(neighbor_saturated),
                "cell_overflow": bool(cell_overflow),
            }

            if not auto_grow:
                break
            if not neighbor_saturated and not cell_overflow:
                break
            if attempt >= (rounds - 1):
                break

            grew = False
            if cell_overflow and current_max_atoms_per_cell < max_atoms_per_cell_cap:
                next_atoms = max(current_max_atoms_per_cell * 2, max_cell_count)
                next_atoms = min(next_atoms, max_atoms_per_cell_cap)
                if next_atoms > current_max_atoms_per_cell:
                    current_max_atoms_per_cell = int(next_atoms)
                    grew = True

            if neighbor_saturated and current_max_neighbors < max_neighbors_cap:
                next_neighbors = max(current_max_neighbors * 2, current_max_neighbors + 16)
                next_neighbors = min(next_neighbors, max_neighbors_cap)
                if next_neighbors > current_max_neighbors:
                    current_max_neighbors = int(next_neighbors)
                    grew = True

            if not grew:
                break

        return nb_idx, nb_dist, nb_mask

    def compute_nonbonded(self, coords_input, nb_data, params):
        if not self.enabled:
            raise RuntimeError(f"Rust HIP backend unavailable: {self.status.reason}")

        if self.status.kernel_name == "compute_nonbonded_celllist_gpu":
            if not isinstance(coords_input, torch.Tensor):
                raise TypeError("coords_input must be torch.Tensor for compute_nonbonded_celllist_gpu")
            if not coords_input.is_cuda:
                raise RuntimeError("compute_nonbonded_celllist_gpu requires CUDA tensor coordinates")
            if coords_input.dtype != torch.float32:
                coords_input = coords_input.float()
            coords_input = coords_input.contiguous()

            batch_size, n_per_replica, _ = coords_input.shape
            force, energy = self._prepare_output_buffers(coords_input)

            sigma = float(params.get("sigma", 3.8))
            epsilon = float(params.get("eps_solv", params.get("epsilon", 25.0)))
            box_size = float(params.get("box_size", 100.0))
            cutoff = float(params.get("cutoff", 12.0))
            gx = int(params.get("grid_x", 8))
            gy = int(params.get("grid_y", 8))
            gz = int(params.get("grid_z", 8))
            max_atoms_per_cell = int(params.get("max_atoms_per_cell", 64))

            n_cells = gx * gy * gz
            cell_counts, cell_atoms = self._prepare_cell_buffers(coords_input, n_cells, max_atoms_per_cell)

            self._kernel(
                int(coords_input.data_ptr()),
                int(cell_counts.data_ptr()),
                int(cell_atoms.data_ptr()),
                int(force.data_ptr()),
                int(energy.data_ptr()),
                int(n_per_replica),
                int(batch_size),
                box_size,
                cutoff,
                int(gx),
                int(gy),
                int(gz),
                int(max_atoms_per_cell),
                sigma,
                epsilon,
            )
            return force, energy

        if self.status.kernel_name == "compute_nonbonded_nblist_gpu":
            if not isinstance(coords_input, torch.Tensor):
                raise TypeError("coords_input must be torch.Tensor for compute_nonbonded_nblist_gpu")
            if not coords_input.is_cuda:
                raise RuntimeError("compute_nonbonded_nblist_gpu requires CUDA tensor coordinates")
            if nb_data is None or len(nb_data) < 3:
                raise RuntimeError("compute_nonbonded_nblist_gpu requires (nb_idx, nb_dist, nb_mask)")

            nb_idx, _nb_dist, nb_mask = nb_data
            if not isinstance(nb_idx, torch.Tensor) or not isinstance(nb_mask, torch.Tensor):
                raise TypeError("nb_idx and nb_mask must be torch.Tensor")
            if not nb_idx.is_cuda or not nb_mask.is_cuda:
                raise RuntimeError("compute_nonbonded_nblist_gpu requires CUDA neighbor tensors")

            if coords_input.dtype != torch.float32:
                coords_input = coords_input.float()
            coords_input = coords_input.contiguous()
            if nb_idx.dtype != torch.int64:
                nb_idx = nb_idx.to(dtype=torch.int64)
            nb_idx = nb_idx.contiguous()
            if nb_mask.dtype != torch.uint8:
                nb_mask = nb_mask.to(dtype=torch.uint8)
            nb_mask = nb_mask.contiguous()

            batch_size, n_per_replica, _ = coords_input.shape
            max_neighbors = int(nb_idx.shape[-1])
            force, energy = self._prepare_output_buffers(coords_input)

            sigma = float(params.get("sigma", 3.8))
            epsilon = float(params.get("eps_solv", params.get("epsilon", 25.0)))
            box_size = float(params.get("box_size", 100.0))

            self._kernel(
                int(coords_input.data_ptr()),
                int(nb_idx.data_ptr()),
                int(nb_mask.data_ptr()),
                int(force.data_ptr()),
                int(energy.data_ptr()),
                int(n_per_replica),
                int(batch_size),
                int(max_neighbors),
                box_size,
                sigma,
                epsilon,
            )
            return force, energy

        if self.status.kernel_name == "compute_nonbonded_gpu":
            if not isinstance(coords_input, torch.Tensor):
                raise TypeError("coords_input must be torch.Tensor for compute_nonbonded_gpu")
            if not coords_input.is_cuda:
                raise RuntimeError("compute_nonbonded_gpu requires CUDA tensor coordinates")
            if coords_input.dtype != torch.float32:
                coords_input = coords_input.float()
            coords_input = coords_input.contiguous()

            batch_size, n_per_replica, _ = coords_input.shape
            force, energy = self._prepare_output_buffers(coords_input)

            sigma = float(params.get("sigma", 3.8))
            # Align with existing parameter naming in the Python force field config.
            epsilon = float(params.get("eps_solv", params.get("epsilon", 25.0)))
            box_size = float(params.get("box_size", 100.0))

            self._kernel(
                int(coords_input.data_ptr()),
                int(force.data_ptr()),
                int(energy.data_ptr()),
                int(n_per_replica),
                int(batch_size),
                box_size,
                sigma,
                epsilon,
            )
            return force, energy

        output = self._kernel(coords_input, nb_data, params)
        if isinstance(output, tuple) and len(output) == 2:
            f_core, pe = output
        else:
            f_core, pe = output, torch.zeros((coords_input.shape[0], 1), device=coords_input.device)

        if not isinstance(f_core, torch.Tensor):
            f_core = torch.as_tensor(f_core, dtype=torch.float32, device=coords_input.device)
        else:
            f_core = f_core.to(device=coords_input.device, dtype=torch.float32)

        if not isinstance(pe, torch.Tensor):
            pe = torch.as_tensor(pe, dtype=torch.float32, device=coords_input.device)
        else:
            pe = pe.to(device=coords_input.device, dtype=torch.float32)

        if f_core.ndim == 1:
            f_core = f_core.view(coords_input.shape[0], coords_input.shape[1], 3)
        if pe.ndim == 1:
            pe = pe.view(-1, 1)

        return f_core, pe

    def compute_idp_virtual_hbond(self, backend_inputs, params):
        if not self.supports_idp_virtual_hbond():
            raise RuntimeError("Rust HIP IDP virtual_hbond backend is unavailable")
        def _as_cuda_tensor(x, *, dtype, device, flatten: bool = False):
            if not isinstance(x, torch.Tensor):
                raise TypeError("backend_inputs must include all virtual_hbond tensors")
            out = x
            if out.device != device or out.dtype != dtype:
                out = out.to(device=device, dtype=dtype)
            if flatten:
                if out.ndim != 1:
                    out = out.reshape(-1)
            if not out.is_contiguous():
                out = out.contiguous()
            return out

        donor = backend_inputs.get("donor")
        acceptor = backend_inputs.get("acceptor")
        ca = backend_inputs.get("ca")
        sc = backend_inputs.get("sc")
        disorder = backend_inputs.get("disorder")
        aromatic_mask = backend_inputs.get("aromatic_mask")
        cationic_mask = backend_inputs.get("cationic_mask")
        sticker_mask = backend_inputs.get("sticker_mask")
        nb_idx = backend_inputs.get("nb_idx")
        nb_dist = backend_inputs.get("nb_dist")
        nb_mask = backend_inputs.get("nb_mask")
        vh_scale = backend_inputs.get("virtual_hbond_scale")
        contact_gain_scale = backend_inputs.get("contact_gain_scale")
        exposure_sensitivity = backend_inputs.get("exposure_sensitivity")
        center = backend_inputs.get("virtual_hbond_center_A")
        width = backend_inputs.get("virtual_hbond_width_A")
        llps_branch = backend_inputs.get("llps_branch")
        is_llps_target = backend_inputs.get("is_llps_target")
        is_hnrn_target = backend_inputs.get("is_hnrn_target")
        is_fus_target = backend_inputs.get("is_fus_target")
        env_scale = backend_inputs.get("env_scale")
        vh_strength = backend_inputs.get("virtual_hbond_strength")
        unsat_penalty = backend_inputs.get("unsat_penalty_strength")
        required = (
            donor,
            acceptor,
            ca,
            sc,
            disorder,
            aromatic_mask,
            cationic_mask,
            sticker_mask,
            nb_idx,
            nb_dist,
            nb_mask,
            vh_scale,
            contact_gain_scale,
            exposure_sensitivity,
            center,
            width,
            llps_branch,
            is_llps_target,
            is_hnrn_target,
            is_fus_target,
            env_scale,
            vh_strength,
            unsat_penalty,
        )
        if not all(isinstance(x, torch.Tensor) for x in required):
            raise TypeError("backend_inputs must include all virtual_hbond tensors")
        if not donor.is_cuda:
            raise RuntimeError("compute_idp_virtual_hbond requires CUDA tensors")
        device = donor.device
        donor = _as_cuda_tensor(donor, dtype=torch.float32, device=device)
        acceptor = _as_cuda_tensor(acceptor, dtype=torch.float32, device=device)
        ca = _as_cuda_tensor(ca, dtype=torch.float32, device=device)
        sc = _as_cuda_tensor(sc, dtype=torch.float32, device=device)
        disorder = _as_cuda_tensor(disorder, dtype=torch.float32, device=device)
        aromatic_mask = _as_cuda_tensor(aromatic_mask, dtype=torch.uint8, device=device)
        cationic_mask = _as_cuda_tensor(cationic_mask, dtype=torch.uint8, device=device)
        sticker_mask = _as_cuda_tensor(sticker_mask, dtype=torch.uint8, device=device)
        nb_idx = _as_cuda_tensor(nb_idx, dtype=torch.int64, device=device)
        nb_dist = _as_cuda_tensor(nb_dist, dtype=torch.float32, device=device)
        nb_mask = _as_cuda_tensor(nb_mask, dtype=torch.uint8, device=device)
        vh_scale = _as_cuda_tensor(vh_scale, dtype=torch.float32, device=device, flatten=True)
        contact_gain_scale = _as_cuda_tensor(contact_gain_scale, dtype=torch.float32, device=device, flatten=True)
        exposure_sensitivity = _as_cuda_tensor(exposure_sensitivity, dtype=torch.float32, device=device, flatten=True)
        center = _as_cuda_tensor(center, dtype=torch.float32, device=device, flatten=True)
        width = _as_cuda_tensor(width, dtype=torch.float32, device=device, flatten=True)
        llps_branch = _as_cuda_tensor(llps_branch, dtype=torch.float32, device=device, flatten=True)
        is_llps_target = _as_cuda_tensor(is_llps_target, dtype=torch.float32, device=device, flatten=True)
        is_hnrn_target = _as_cuda_tensor(is_hnrn_target, dtype=torch.float32, device=device, flatten=True)
        is_fus_target = _as_cuda_tensor(is_fus_target, dtype=torch.float32, device=device, flatten=True)
        env_scale = _as_cuda_tensor(env_scale, dtype=torch.float32, device=device, flatten=True)
        vh_strength = _as_cuda_tensor(vh_strength, dtype=torch.float32, device=device, flatten=True)
        unsat_penalty = _as_cuda_tensor(unsat_penalty, dtype=torch.float32, device=device, flatten=True)

        return self._launch_idp_virtual_hbond(
            donor=donor,
            acceptor=acceptor,
            ca=ca,
            sc=sc,
            disorder=disorder,
            aromatic_mask=aromatic_mask,
            cationic_mask=cationic_mask,
            sticker_mask=sticker_mask,
            nb_idx=nb_idx,
            nb_dist=nb_dist,
            nb_mask=nb_mask,
            vh_scale=vh_scale,
            contact_gain_scale=contact_gain_scale,
            exposure_sensitivity=exposure_sensitivity,
            center=center,
            width=width,
            llps_branch=llps_branch,
            is_llps_target=is_llps_target,
            is_hnrn_target=is_hnrn_target,
            is_fus_target=is_fus_target,
            env_scale=env_scale,
            vh_strength=vh_strength,
            unsat_penalty=unsat_penalty,
        )

    def rollout_ligand_direct(
        self,
        coords_input: torch.Tensor,
        vel_input: torch.Tensor,
        selected_out: torch.Tensor,
        pocket_xyz: torch.Tensor,
        pocket_attract: torch.Tensor,
        protein_repulse: torch.Tensor,
        bond_ref: torch.Tensor,
        keep_steps,
        params,
        *,
        n_protein: int,
        n_ligand: int,
        frames: int,
        noise_bank: Optional[torch.Tensor] = None,
    ) -> None:
        if not self.supports_direct_rollout():
            raise RuntimeError("Rust HIP direct rollout is unavailable")
        if not isinstance(coords_input, torch.Tensor) or not isinstance(vel_input, torch.Tensor):
            raise TypeError("coords_input and vel_input must be torch.Tensor")
        if not coords_input.is_cuda or not vel_input.is_cuda:
            raise RuntimeError("rollout_ligand_direct requires CUDA tensors")
        if coords_input.dtype != torch.float32:
            coords_input = coords_input.float()
        if vel_input.dtype != torch.float32:
            vel_input = vel_input.float()
        coords_input = coords_input.contiguous()
        vel_input = vel_input.contiguous()
        selected_out = selected_out.contiguous()
        pocket_xyz = pocket_xyz.to(device=coords_input.device, dtype=torch.float32).contiguous()
        pocket_attract = pocket_attract.to(device=coords_input.device, dtype=torch.float32).contiguous()
        protein_repulse = protein_repulse.to(device=coords_input.device, dtype=torch.float32).contiguous()
        bond_ref = bond_ref.to(device=coords_input.device, dtype=torch.float32).contiguous()
        if noise_bank is not None:
            if not isinstance(noise_bank, torch.Tensor):
                raise TypeError("noise_bank must be torch.Tensor or None")
            if not noise_bank.is_cuda:
                raise RuntimeError("noise_bank must be a CUDA tensor")
            noise_bank = noise_bank.to(device=coords_input.device, dtype=torch.float32).contiguous()

        batch_size, n_per_replica, _ = coords_input.shape
        force, energy = self._prepare_output_buffers(coords_input)
        sigma = float(params.get("sigma", 3.8))
        epsilon = float(params.get("eps_solv", params.get("epsilon", 25.0)))
        box_size = float(params.get("box_size", 100.0))
        repulse_cutoff = float(params.get("repulse_cutoff", 6.5))
        max_pocket_radius = float(params.get("max_pocket_radius", 14.0))
        force_clip = float(params.get("force_clip", 0.0))
        dt = float(params.get("dt", 0.002))
        gamma = float(params.get("friction", 1.0))
        bond_k = float(params.get("bond_k", 0.0))

        keep_steps_list = [int(x) for x in keep_steps]
        self._direct_rollout(
            int(coords_input.data_ptr()),
            int(vel_input.data_ptr()),
            int(force.data_ptr()),
            int(energy.data_ptr()),
            int(selected_out.data_ptr()),
            int(pocket_xyz.data_ptr()),
            int(pocket_attract.data_ptr()),
            int(protein_repulse.data_ptr()),
            int(bond_ref.data_ptr()),
            int(noise_bank.data_ptr()) if isinstance(noise_bank, torch.Tensor) else 0,
            int(n_per_replica),
            int(batch_size),
            int(n_protein),
            int(n_ligand),
            int(frames),
            keep_steps_list,
            box_size,
            sigma,
            epsilon,
            bond_k,
            repulse_cutoff,
            max_pocket_radius,
            force_clip,
            dt,
            gamma,
        )
