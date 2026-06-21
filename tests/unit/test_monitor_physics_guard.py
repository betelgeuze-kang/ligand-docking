# tests/unit/test_monitor_physics_guard.py

import pytest
import torch
import numpy as np
from monitor.physics_guard import PhysicsGuard

def test_physics_guard_initialization():
    """PhysicsGuard 객체가 정상적으로 초기화되는지 테스트."""
    guard = PhysicsGuard(max_energy_drift=0.02, max_momentum_drift=0.015)
    assert guard is not None
    assert guard.max_energy_drift == 0.02
    assert guard.max_momentum_drift == 0.015
    assert guard.violation_count == 0

def test_physics_guard_check_conservation_no_violation():
    """PhysicsGuard.check_conservation이 위반 없이 정상적인 상태를 통과시키는지 테스트."""
    guard = PhysicsGuard(max_energy_drift=0.02, max_momentum_drift=0.015)
    B, N = 1, 10
    c = torch.randn(B, N, 3, device='cpu') # PhysicsGuard는 CPU에서 작동하도록 설계됨
    v = torch.randn(B, N, 3, device='cpu')
    pe = torch.tensor([[100.0]]) # Mock potential energy
    f_core = torch.randn(B, N, 3, device='cpu')
    f_ai_corr = torch.randn(B, N, 3, device='cpu') # Mock AI correction force
    step = 10

    # Initial call to establish baseline
    is_ok, msg = guard.check_conservation(c, v, pe, f_core, f_ai_corr, step)
    assert is_ok
    assert msg == "OK"

    # Second call with similar state (should pass)
    c2 = c + 0.001 * torch.randn_like(c) # Small change
    v2 = v + 0.001 * torch.randn_like(v)
    pe2 = pe + 0.1 # Small energy change
    f_core2 = torch.randn(B, N, 3, device='cpu')
    f_ai_corr2 = torch.randn(B, N, 3, device='cpu')

    is_ok2, msg2 = guard.check_conservation(c2, v2, pe2, f_core2, f_ai_corr2, step+1)
    assert is_ok2
    assert msg2 == "OK"

def test_physics_guard_check_conservation_with_violation():
    """PhysicsGuard.check_conservation이 에너지 드리프트를 감지하여 위반을 보고하는지 테스트."""
    guard = PhysicsGuard(max_energy_drift=0.01, max_momentum_drift=0.015) # Very strict drift limit
    B, N = 1, 10
    c = torch.randn(B, N, 3, device='cpu')
    v = torch.randn(B, N, 3, device='cpu')
    pe = torch.tensor([[100.0]])
    f_core = torch.randn(B, N, 3, device='cpu')
    f_ai_corr = torch.randn(B, N, 3, device='cpu')
    step = 10

    # Initial call to establish baseline
    is_ok, msg = guard.check_conservation(c, v, pe, f_core, f_ai_corr, step)
    assert is_ok

    # Second call with large energy change (should violate)
    c2 = c
    v2 = v
    pe2 = torch.tensor([[200.0]]) # Large energy change (>1% of 100.0)
    f_core2 = torch.randn(B, N, 3, device='cpu')
    f_ai_corr2 = torch.randn(B, N, 3, device='cpu')

    is_ok2, msg2 = guard.check_conservation(c2, v2, pe2, f_core2, f_ai_corr2, step+1)
    assert not is_ok2
    assert "Energy violation" in msg2
    assert guard.violation_count == 1 # Violation count should increment


def test_physics_guard_steric_overlap_violation():
    """min_interatomic_distance가 설정되면 원자 겹침을 위반으로 감지해야 한다."""
    guard = PhysicsGuard(
        max_energy_drift=0.02,
        max_momentum_drift=0.015,
        min_interatomic_distance=0.5,
    )
    B, N = 1, 4
    c = torch.zeros(B, N, 3, device='cpu')
    # 두 원자를 거의 같은 위치에 배치해 overlap 유도
    c[0, 1, 0] = 0.1
    c[0, 2, 0] = 1.0
    c[0, 3, 0] = 2.0
    v = torch.zeros(B, N, 3, device='cpu')
    pe = torch.tensor([[100.0]], device='cpu')
    f_core = torch.zeros(B, N, 3, device='cpu')
    f_ai_corr = torch.zeros(B, N, 3, device='cpu')

    is_ok, msg = guard.check_conservation(c, v, pe, f_core, f_ai_corr, step=0)
    assert not is_ok
    assert "Steric overlap violation" in msg
    assert guard.violation_count == 1


def test_physics_guard_provider_backed_overlap_check_blocks_overflow():
    guard = PhysicsGuard(
        max_energy_drift=0.02,
        max_momentum_drift=0.015,
        min_interatomic_distance=0.5,
        overlap_diagnostic_max_neighbors=1,
        enable_local_teacher=False,
    )
    B, N = 1, 4
    c = torch.zeros(B, N, 3, device='cpu')
    v = torch.zeros(B, N, 3, device='cpu')
    pe = torch.tensor([[100.0]], device='cpu')
    f_core = torch.zeros(B, N, 3, device='cpu')
    f_ai_corr = torch.zeros(B, N, 3, device='cpu')

    is_ok, msg = guard.check_conservation(c, v, pe, f_core, f_ai_corr, step=0)
    assert not is_ok
    assert "Steric overlap neighbor provider overflow" in msg
    assert guard.violation_count == 1

# 더 많은 테스트 케이스 추가 가능 (예: 운동량 드리프트, auto_recover 등)
