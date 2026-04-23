# tests/unit/test_adaptive_mts.py
"""AdaptiveMTSController 단위 테스트."""

import pytest
from core.mts_policy import AdaptiveMTSController


class TestAdaptiveMTSControllerInit:
    def test_defaults(self):
        ctrl = AdaptiveMTSController()
        assert ctrl.base_interval == 8
        assert ctrl.max_interval == 16
        assert ctrl.min_interval == 1
        assert ctrl.current_interval == 8

    def test_custom_params(self):
        ctrl = AdaptiveMTSController(base_interval=4, max_interval=12, min_interval=2)
        assert ctrl.base_interval == 4
        assert ctrl.max_interval == 12
        assert ctrl.min_interval == 2

    def test_min_clamped_to_base(self):
        """min_interval이 base_interval보다 크면 base로 클램프."""
        ctrl = AdaptiveMTSController(base_interval=4, min_interval=10)
        assert ctrl.min_interval == 4

    def test_max_clamped_to_base(self):
        """max_interval이 base_interval보다 작으면 base로 클램프."""
        ctrl = AdaptiveMTSController(base_interval=8, max_interval=3)
        assert ctrl.max_interval == 8


class TestAdaptiveMTSControllerStep:
    def test_hold_on_stable(self):
        """drift/잔차가 임계값 이하면 interval 유지(hold)."""
        ctrl = AdaptiveMTSController(drift_threshold=0.5, residual_threshold=2.0)
        interval, info = ctrl.step(residual_norm=0.1, displacement_norm=0.1)
        assert info["action"] == "hold"
        assert interval == ctrl.base_interval

    def test_downshift_on_drift(self):
        """drift 초과 시 interval=min_interval로 즉시 축소."""
        ctrl = AdaptiveMTSController(drift_threshold=0.25)
        interval, info = ctrl.step(residual_norm=0.0, displacement_norm=0.5)
        assert info["action"] == "downshift"
        assert interval == 1
        assert info["exceeded_drift"] is True
        assert ctrl.total_downshifts == 1

    def test_downshift_on_residual(self):
        """잔차 초과 시 interval=min_interval로 즉시 축소."""
        ctrl = AdaptiveMTSController(residual_threshold=1.0)
        interval, info = ctrl.step(residual_norm=2.0, displacement_norm=0.0)
        assert info["action"] == "downshift"
        assert interval == 1
        assert info["exceeded_residual"] is True

    def test_upshift_after_stable_window(self):
        """stable_upshift_window 연속 안정 후 interval 1 증가."""
        ctrl = AdaptiveMTSController(
            base_interval=4,
            max_interval=8,
            stable_upshift_window=3,
            drift_threshold=1.0,
            residual_threshold=1.0,
        )
        # min_interval로 먼저 축소
        ctrl.step(residual_norm=5.0, displacement_norm=0.0)
        assert ctrl.current_interval == 1

        # stable_upshift_window 스텝 안정
        for _ in range(3):
            interval, info = ctrl.step(0.0, 0.0)
        assert info["action"] == "upshift"
        assert ctrl.current_interval == 2
        assert ctrl.total_upshifts == 1

    def test_upshift_capped_at_max(self):
        """interval이 max_interval을 초과하지 않음."""
        ctrl = AdaptiveMTSController(
            base_interval=15,
            max_interval=16,
            stable_upshift_window=1,
        )
        for _ in range(10):
            ctrl.step(0.0, 0.0)
        assert ctrl.current_interval <= ctrl.max_interval

    def test_reset(self):
        ctrl = AdaptiveMTSController()
        ctrl.step(5.0, 5.0)  # downshift
        ctrl.reset()
        assert ctrl.current_interval == ctrl.base_interval
        assert ctrl.total_downshifts == 0
        assert ctrl.total_upshifts == 0


class TestAdaptiveMTSControllerEdgeCases:
    def test_zero_thresholds_never_trigger(self):
        """임계값이 0이면 downshift 안 됨."""
        ctrl = AdaptiveMTSController(drift_threshold=0.0, residual_threshold=0.0)
        interval, info = ctrl.step(100.0, 100.0)
        assert info["action"] == "hold"

    def test_already_at_min_no_extra_downshift_count(self):
        """이미 min에 있으면 downshift 횟수 증가 안 함."""
        ctrl = AdaptiveMTSController()
        ctrl.step(5.0, 5.0)  # first downshift
        assert ctrl.total_downshifts == 1
        ctrl.step(5.0, 5.0)  # already at min
        assert ctrl.total_downshifts == 1
