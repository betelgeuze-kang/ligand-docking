# tests/unit/test_adress_selector.py
"""AdReSSSelector 단위 테스트."""

import pytest
import torch
from core.spatial import AdReSSSelector


class TestAdReSSSelectorInit:
    def test_default_params(self):
        sel = AdReSSSelector(pocket_center=[0.0, 0.0, 0.0])
        assert sel.high_res_radius == 15.0
        assert sel.hybrid_width == 5.0
        assert sel.max_high_res_fraction == 0.10

    def test_custom_params(self):
        sel = AdReSSSelector(
            pocket_center=[1.0, 2.0, 3.0],
            high_res_radius=10.0,
            hybrid_width=3.0,
            max_high_res_fraction=0.05,
        )
        assert sel.high_res_radius == 10.0
        assert sel.max_high_res_fraction == 0.05


class TestAdReSSSelectorClassify:
    def test_all_far_atoms_are_low(self):
        """모든 원자가 포켓 바깥이면 전부 low."""
        sel = AdReSSSelector(pocket_center=[0.0, 0.0, 0.0], high_res_radius=1.0)
        coords = torch.randn(1, 50, 3) * 100.0  # 매우 멀리 분산
        high, hybrid, low = sel.classify(coords)
        assert low.all()
        assert not high.any()

    def test_all_close_atoms_within_cap(self):
        """모든 원자가 포켓 안이고 캡 이내면 전부 high."""
        sel = AdReSSSelector(
            pocket_center=[0.0, 0.0, 0.0],
            high_res_radius=100.0,  # 매우 큰 반경
            max_high_res_fraction=1.0,  # 캡 비활성화
        )
        coords = torch.randn(1, 10, 3) * 0.1  # 원점 근처
        high, hybrid, low = sel.classify(coords)
        assert high.all()

    def test_hard_cap_limits_fraction(self):
        """10% 하드캡이 실제로 비율을 제한하는지 확인."""
        sel = AdReSSSelector(
            pocket_center=[0.0, 0.0, 0.0],
            high_res_radius=100.0,  # 엄청 넓은 반경 → 원래대로면 100% high
            hybrid_width=5.0,
            max_high_res_fraction=0.10,
        )
        # 100개 원자를 선형 배치 (0~99 거리)
        coords = torch.zeros(1, 100, 3)
        coords[0, :, 0] = torch.arange(100).float()
        high, hybrid, low = sel.classify(coords)
        active = (high | hybrid).sum().item()
        fraction = active / 100
        assert fraction <= 0.10 + 0.05  # 이진검색 허용 오차
        assert sel.last_high_fraction <= 0.15  # 하드캡 내

    def test_effective_radius_shrinks_under_cap(self):
        """하드캡 적용 시 effective_radius가 원래 radius보다 줄어들어야 함."""
        sel = AdReSSSelector(
            pocket_center=[0.0, 0.0, 0.0],
            high_res_radius=50.0,
            max_high_res_fraction=0.05,
        )
        coords = torch.zeros(1, 200, 3)
        coords[0, :, 0] = torch.arange(200).float()
        sel.classify(coords)
        assert sel.effective_radius < 50.0

    def test_masks_are_mutually_exclusive(self):
        """high, hybrid, low 마스크가 상호 배타적이고 모든 원자를 커버."""
        sel = AdReSSSelector(pocket_center=[5.0, 5.0, 5.0], high_res_radius=3.0)
        coords = torch.randn(2, 30, 3) * 10.0
        high, hybrid, low = sel.classify(coords)
        total = high.long() + hybrid.long() + low.long()
        assert (total == 1).all()

    def test_batch_dimension(self):
        """배치 차원이 올바르게 처리되는지 확인."""
        sel = AdReSSSelector(pocket_center=[0.0, 0.0, 0.0])
        coords = torch.randn(4, 20, 3) * 5.0
        high, hybrid, low = sel.classify(coords)
        assert high.shape == (4, 20)
        assert hybrid.shape == (4, 20)
        assert low.shape == (4, 20)
