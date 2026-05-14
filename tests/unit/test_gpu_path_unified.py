# tests/unit/test_gpu_path_unified.py
"""GPU 경로 단일화 단위 테스트."""

import pytest
from unittest.mock import MagicMock, patch
import types


class TestUnifiedKernelCandidates:
    def test_fused_cell_not_in_candidates(self):
        """compute_nonbonded_celllist_gpu가 후보에서 제거됨."""
        from core.rust_hip_backend import _KERNEL_CANDIDATES
        assert "compute_nonbonded_celllist_gpu" not in _KERNEL_CANDIDATES

    def test_stable_kernels_present(self):
        """안정 커널이 후보에 포함됨."""
        from core.rust_hip_backend import _KERNEL_CANDIDATES
        assert "compute_nonbonded_nblist_gpu" in _KERNEL_CANDIDATES
        assert "compute_nonbonded_gpu" in _KERNEL_CANDIDATES


class TestSelectKernel:
    def test_ignores_fused_cell_even_if_present(self):
        """모듈에 compute_nonbonded_celllist_gpu가 있어도 선택하지 않음."""
        from core.rust_hip_backend import _select_kernel
        mock_module = MagicMock()
        mock_module.compute_nonbonded_celllist_gpu = lambda: None
        mock_module.compute_nonbonded_nblist_gpu = lambda: None
        result = _select_kernel(mock_module)
        assert result == "compute_nonbonded_nblist_gpu"

    def test_selects_nblist_first(self):
        from core.rust_hip_backend import _select_kernel
        mock_module = MagicMock()
        mock_module.compute_nonbonded_nblist_gpu = lambda: None
        mock_module.compute_nonbonded_gpu = lambda: None
        result = _select_kernel(mock_module)
        assert result == "compute_nonbonded_nblist_gpu"

    @patch.dict("os.environ", {"RUST_HIP_USE_FUSED_CELL": "1"})
    def test_env_toggle_has_no_effect(self):
        """RUST_HIP_USE_FUSED_CELL=1이면 명시적 fused cell 경로를 선택."""
        from core.rust_hip_backend import _select_kernel
        mock_module = MagicMock()
        mock_module.compute_nonbonded_celllist_gpu = lambda: None
        mock_module.compute_nonbonded_nblist_gpu = lambda: None
        result = _select_kernel(mock_module)
        assert result == "compute_nonbonded_celllist_gpu"

    def test_returns_none_if_no_kernel(self):
        from core.rust_hip_backend import _select_kernel
        mock_module = types.ModuleType("empty")
        result = _select_kernel(mock_module)
        assert result is None


class TestUsesFusedCellList:
    def test_always_false(self):
        """uses_fused_cell_list는 항상 False."""
        from core.rust_hip_backend import RustHipBackend
        backend = RustHipBackend.__new__(RustHipBackend)
        backend.status = MagicMock()
        backend.status.kernel_name = "compute_nonbonded_celllist_gpu"
        assert backend.uses_fused_cell_list() is False


class TestDiagnoseHipBinaryMismatch:
    def test_returns_dict(self):
        from core.rust_hip_backend import diagnose_hip_binary_mismatch
        result = diagnose_hip_binary_mismatch()
        assert isinstance(result, dict)
        assert "hipcc_version" in result
        assert "gpu_arch" in result
        assert "isa_match" in result
        assert "details" in result

    @patch("subprocess.run", side_effect=FileNotFoundError("hipcc not found"))
    def test_handles_missing_hipcc(self, mock_run):
        from core.rust_hip_backend import diagnose_hip_binary_mismatch
        result = diagnose_hip_binary_mismatch()
        assert result["hipcc_version"] is None
        assert "실행 실패" in result["details"]


class TestIsaMatchField:
    def test_probe_status_has_isa_fields(self):
        from core.rust_hip_backend import RustHipProbeStatus
        status = RustHipProbeStatus(enabled=False, reason="test")
        assert hasattr(status, "isa_match")
        assert hasattr(status, "isa_info")
        assert status.isa_match is None
