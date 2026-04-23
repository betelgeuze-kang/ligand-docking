# tests/unit/test_operational_gate.py
"""OperationalGate 단위 테스트."""

import pytest
from monitor.physics_guard import OperationalGate


class TestOperationalGateInit:
    def test_defaults(self):
        gate = OperationalGate()
        assert gate.p95_speed_min == 50.0
        assert gate.worst_speed_min == 20.0
        assert gate.max_overflow_count == 0
        assert gate.accuracy_rmsd_max == 5.0

    def test_custom(self):
        gate = OperationalGate(p95_speed_min=100.0, worst_speed_min=30.0)
        assert gate.p95_speed_min == 100.0


class TestOperationalGateCheck:
    def test_pass_with_fast_steps(self):
        """빠른 step이면 모든 게이트 통과."""
        gate = OperationalGate(p95_speed_min=10.0, worst_speed_min=5.0)
        for _ in range(100):
            gate.record_step(0.001)  # 1000 steps/s
        passed, reasons = gate.check()
        assert passed
        assert len(reasons) == 0

    def test_fail_p95(self):
        """느린 p95 step time이면 fail."""
        gate = OperationalGate(p95_speed_min=100.0, worst_speed_min=1.0)
        for _ in range(95):
            gate.record_step(0.001)   # 1000 steps/s — 빠름
        for _ in range(5):
            gate.record_step(1.0)     # 1 step/s — 느림
        passed, reasons = gate.check()
        assert not passed
        assert any("p95" in r for r in reasons)

    def test_fail_worst(self):
        """worst step time이 하한 미만이면 fail."""
        gate = OperationalGate(p95_speed_min=1.0, worst_speed_min=100.0)
        for _ in range(99):
            gate.record_step(0.001)
        gate.record_step(0.5)  # worst = 2 steps/s < 100
        passed, reasons = gate.check()
        assert not passed
        assert any("worst" in r for r in reasons)

    def test_fail_overflow(self):
        """overflow 누적이 허용치 초과이면 fail."""
        gate = OperationalGate(max_overflow_count=5)
        gate.record_step(0.001)
        for _ in range(6):
            gate.record_overflow()
        passed, reasons = gate.check()
        assert not passed
        assert any("overflow" in r for r in reasons)

    def test_fail_saturation(self):
        """saturation 비율이 허용치 초과이면 fail."""
        gate = OperationalGate(max_saturation_ratio=0.0)
        gate.record_step(0.001)
        gate.record_saturation(5, 100)
        passed, reasons = gate.check()
        assert not passed
        assert any("saturation" in r for r in reasons)

    def test_fail_rmsd(self):
        """RMSD가 허용치 초과이면 fail."""
        gate = OperationalGate(accuracy_rmsd_max=2.0)
        gate.record_step(0.001)
        gate.record_rmsd(3.5)
        passed, reasons = gate.check()
        assert not passed
        assert any("RMSD" in r for r in reasons)

    def test_multiple_failures(self):
        """여러 게이트가 동시에 실패할 수 있음."""
        gate = OperationalGate(
            p95_speed_min=1000.0,
            worst_speed_min=1000.0,
            max_overflow_count=0,
            accuracy_rmsd_max=1.0,
        )
        gate.record_step(1.0)  # 1 step/s
        gate.record_overflow(1)
        gate.record_rmsd(5.0)
        passed, reasons = gate.check()
        assert not passed
        assert len(reasons) >= 3  # p95 + worst + overflow + RMSD


class TestOperationalGateReset:
    def test_reset_clears_state(self):
        gate = OperationalGate()
        gate.record_step(1.0)
        gate.record_overflow(5)
        gate.record_rmsd(10.0)
        gate.reset()
        passed, reasons = gate.check()
        assert passed  # 데이터 없으면 통과


class TestOperationalGateStats:
    def test_stats_empty(self):
        gate = OperationalGate()
        stats = gate.get_stats()
        assert stats["mean_steps_per_sec"] == 0.0

    def test_stats_correct(self):
        gate = OperationalGate()
        for _ in range(10):
            gate.record_step(0.01)  # 100 steps/s
        stats = gate.get_stats()
        assert abs(stats["mean_steps_per_sec"] - 100.0) < 5.0

    def test_window_size(self):
        """window_size를 초과하면 오래된 기록이 제거됨."""
        gate = OperationalGate(window_size=5)
        for _ in range(10):
            gate.record_step(0.01)
        assert len(gate._step_times) == 5
