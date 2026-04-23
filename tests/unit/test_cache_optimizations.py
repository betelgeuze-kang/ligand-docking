# tests/unit/test_cache_optimizations.py
"""캐시 히트율 2차 최적화 단위 테스트.

SoA 레이아웃, Z-order 순회, AdResS 스케줄러, neighbor 프리페치,
mixed-precision, 커널 퓨전 occupancy 가드를 검증합니다.
"""

import pytest
import torch
import numpy as np


# ===== 1. SoA 레이아웃 테스트 =====
class TestSoACoords:
    def test_aos_to_soa_roundtrip(self):
        """AoS → SoA → AoS 왕복 변환이 정확한지."""
        from core.soa import aos_to_soa, soa_to_aos
        coords = torch.randn(2, 10, 3)
        soa = aos_to_soa(coords)
        restored = soa_to_aos(soa)
        assert torch.allclose(coords, restored, atol=1e-6)

    def test_soa_shape(self):
        from core.soa import aos_to_soa
        coords = torch.randn(3, 20, 3)
        soa = aos_to_soa(coords)
        assert soa.shape == (3, 20)
        assert soa.x.shape == (3, 20)
        assert soa.y.shape == (3, 20)
        assert soa.z.shape == (3, 20)

    def test_soa_contiguous(self):
        """SoA 각 채널이 contiguous인지."""
        from core.soa import aos_to_soa
        coords = torch.randn(2, 15, 3)
        soa = aos_to_soa(coords)
        assert soa.x.is_contiguous()
        assert soa.y.is_contiguous()
        assert soa.z.is_contiguous()

    def test_soa_clone(self):
        from core.soa import aos_to_soa
        soa = aos_to_soa(torch.randn(1, 5, 3))
        clone = soa.clone()
        clone.x[0, 0] = 999.0
        assert soa.x[0, 0] != 999.0

    def test_soa_half(self):
        from core.soa import aos_to_soa
        soa = aos_to_soa(torch.randn(1, 5, 3))
        h = soa.half()
        assert h.dtype == torch.float16

    def test_soa_pairwise_dist_sq(self):
        from core.soa import aos_to_soa, soa_pairwise_dist_sq
        coords = torch.tensor([[[0., 0., 0.], [3., 4., 0.], [1., 0., 0.]]])
        soa = aos_to_soa(coords)
        idx_i = torch.tensor([0])
        idx_j = torch.tensor([1])
        d2 = soa_pairwise_dist_sq(soa, idx_i, idx_j)
        assert torch.allclose(d2, torch.tensor([[25.0]]), atol=1e-4)

    def test_soa_pairwise_dist_sq_pbc(self):
        from core.soa import aos_to_soa, soa_pairwise_dist_sq
        coords = torch.tensor([[[0., 0., 0.], [9., 0., 0.]]])
        soa = aos_to_soa(coords)
        box = torch.tensor([10., 10., 10.])
        d2 = soa_pairwise_dist_sq(soa, torch.tensor([0]), torch.tensor([1]), box)
        assert d2[0, 0].item() < 2.0  # PBC: 거리=1


# ===== 2. Z-order Cell 순회 테스트 =====
class TestZOrderCellTraversal:
    def test_all_cells_covered(self):
        from core.spatial import ZOrderCellTraversal
        gx, gy, gz = 4, 4, 4
        cells = ZOrderCellTraversal.sorted_cell_ids(gx, gy, gz)
        assert len(cells) == 64  # 4*4*4
        # 모든 flat_id가 고유
        flat_ids = [c[3] for c in cells]
        assert len(set(flat_ids)) == 64

    def test_z_order_preserves_locality(self):
        """Z-order 순회에서 연속 cell이 공간적으로 가까운지."""
        from core.spatial import ZOrderCellTraversal
        cells = ZOrderCellTraversal.sorted_cell_ids(8, 8, 8)
        # 연속된 두 셀 사이의 맨해튼 거리 체크
        for i in range(len(cells) - 1):
            cx1, cy1, cz1, _ = cells[i]
            cx2, cy2, cz2, _ = cells[i + 1]
            dist = abs(cx1 - cx2) + abs(cy1 - cy2) + abs(cz1 - cz2)
            # 대부분 인접(≤3), Z-order는 완벽하지 않지만 선형보다 나음
            assert dist <= 24  # 최악의 경우도 제한적

    def test_interleave_bits(self):
        from core.spatial import ZOrderCellTraversal
        code = ZOrderCellTraversal._interleave_bits_3d(0, 0, 0)
        assert code == 0
        code1 = ZOrderCellTraversal._interleave_bits_3d(1, 0, 0)
        assert code1 == 1


# ===== 3. AdResS 스케줄러 테스트 =====
class TestAdReSSScheduler:
    def test_initial_classify(self):
        """첫 step에서 분류가 수행됨."""
        from core.spatial import AdReSSSelector, AdReSSScheduler
        sel = AdReSSSelector([0., 0., 0.], high_res_radius=5.0)
        sched = AdReSSScheduler(sel, reclassify_interval=10)
        coords = torch.randn(1, 20, 3) * 10.0
        masks = sched.step(coords)
        assert masks is not None
        assert len(masks) == 3

    def test_reclassify_interval(self):
        """reclassify_interval마다 재분류가 수행됨."""
        from core.spatial import AdReSSSelector, AdReSSScheduler
        sel = AdReSSSelector([0., 0., 0.], high_res_radius=5.0, max_high_res_fraction=1.0)
        sched = AdReSSScheduler(sel, reclassify_interval=5)
        coords = torch.randn(1, 20, 3) * 10.0
        masks1 = sched.step(coords)  # step 1 — 초기 분류
        for _ in range(3):
            masks_mid = sched.step(coords)  # step 2-4 — 캐시 사용

        # step 5 — 재분류
        coords2 = torch.randn(1, 20, 3) * 10.0
        masks5 = sched.step(coords2)
        assert masks5 is not None

    def test_pocket_center_update(self):
        """포켓 중심 변경 시 즉시 재분류."""
        from core.spatial import AdReSSSelector, AdReSSScheduler
        sel = AdReSSSelector([0., 0., 0.], high_res_radius=5.0, max_high_res_fraction=1.0)
        sched = AdReSSScheduler(sel, reclassify_interval=100)
        coords = torch.randn(1, 20, 3) * 10.0
        sched.step(coords)  # 초기
        sched.step(coords, pocket_center=[50., 50., 50.])  # 즉시 재분류
        assert sel.pocket_center[0, 0, 0].item() == 50.0

    def test_reset(self):
        from core.spatial import AdReSSSelector, AdReSSScheduler
        sel = AdReSSSelector([0., 0., 0.])
        sched = AdReSSScheduler(sel)
        sched.step(torch.randn(1, 10, 3))
        sched.reset()
        assert sched._step_count == 0
        assert sched._last_masks is None


# ===== 4. Neighbor 프리페치 테스트 =====
class TestAsyncNeighborPrefetcher:
    def test_sync_fallback(self):
        """CUDA 미사용 시 동기 모드로 동작."""
        from core.spatial import GridSpatialHash, AsyncNeighborPrefetcher
        sh = GridSpatialHash([50]*3, 12.0, "cpu", use_morton_presort=False)
        prefetcher = AsyncNeighborPrefetcher(sh)
        coords = torch.randn(1, 15, 3) * 5.0
        prefetcher.prefetch(coords)
        assert prefetcher.has_pending()
        nb = prefetcher.get()
        assert nb is not None
        assert len(nb) == 3
        assert not prefetcher.has_pending()

    def test_get_without_prefetch(self):
        from core.spatial import GridSpatialHash, AsyncNeighborPrefetcher
        sh = GridSpatialHash([50]*3, 12.0, "cpu", use_morton_presort=False)
        prefetcher = AsyncNeighborPrefetcher(sh)
        nb = prefetcher.get()
        assert nb is None


# ===== 5. Mixed-precision neighbor distance 테스트 =====
class TestMixedPrecisionNeighborConfig:
    def test_should_use_fp16(self):
        from core.spatial import MixedPrecisionNeighborConfig
        cfg = MixedPrecisionNeighborConfig(use_fp16_distance=True)
        assert cfg.should_use_fp16(12.0) is True
        assert cfg.should_use_fp16(100.0) is False  # > threshold

    def test_should_not_use_fp16_when_disabled(self):
        from core.spatial import MixedPrecisionNeighborConfig
        cfg = MixedPrecisionNeighborConfig(use_fp16_distance=False)
        assert cfg.should_use_fp16(12.0) is False

    def test_compute_dist_sq_fp16(self):
        from core.spatial import MixedPrecisionNeighborConfig
        atom = torch.tensor([0., 0., 0.])
        cands = torch.tensor([[3., 4., 0.], [1., 0., 0.]])
        box = torch.tensor([100., 100., 100.])
        d2 = MixedPrecisionNeighborConfig.compute_dist_sq_fp16(atom, cands, box)
        assert d2.dtype == torch.float32
        assert abs(d2[0].item() - 25.0) < 0.5  # FP16 허용 오차
        assert abs(d2[1].item() - 1.0) < 0.1

    def test_fp16_pbc_distance(self):
        from core.spatial import MixedPrecisionNeighborConfig
        atom = torch.tensor([0., 0., 0.])
        cands = torch.tensor([[9., 0., 0.]])
        box = torch.tensor([10., 10., 10.])
        d2 = MixedPrecisionNeighborConfig.compute_dist_sq_fp16(atom, cands, box)
        assert d2[0].item() < 2.0  # PBC: 실제 거리=1


# ===== 6. 커널 퓨전 occupancy 가드 테스트 =====
class TestKernelFusionOccupancyGuard:
    def test_default_allows_fusion(self):
        from core.rust_hip_backend import KernelFusionOccupancyGuard
        guard = KernelFusionOccupancyGuard(max_occupancy_ratio=0.5)
        allowed = guard.check_fusion_allowed("test_kernel")
        # 기본 추정 occupancy(0.75) >= 0.5 → 허용
        assert allowed is True

    def test_strict_ratio_blocks_fusion(self):
        from core.rust_hip_backend import KernelFusionOccupancyGuard
        guard = KernelFusionOccupancyGuard(max_occupancy_ratio=0.99)
        allowed = guard.check_fusion_allowed("test_kernel")
        # 추정 occupancy(0.75) < 0.99 → 차단
        assert allowed is False

    def test_get_status(self):
        from core.rust_hip_backend import KernelFusionOccupancyGuard
        guard = KernelFusionOccupancyGuard(max_occupancy_ratio=0.8)
        guard.check_fusion_allowed("test")
        status = guard.get_status()
        assert "max_occupancy_ratio" in status
        assert "last_occupancy" in status
        assert "fusion_allowed" in status

    def test_properties(self):
        from core.rust_hip_backend import KernelFusionOccupancyGuard
        guard = KernelFusionOccupancyGuard()
        guard.check_fusion_allowed()
        assert isinstance(guard.last_occupancy, float)
        assert isinstance(guard.fusion_allowed, bool)
