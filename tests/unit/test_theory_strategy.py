# tests/unit/test_theory_strategy.py

import pytest
import torch
import numpy as np
from core.sim_param_schema import DEFAULT_RUNTIME_CONDITIONING_KEYS
from theory.strategy import StrategicOrchestrator, AIRouter
from core.definitions import Config

@pytest.fixture
def sample_orchestrator():
    """Test용 StrategicOrchestrator 객체 생성."""
    orchestrator = StrategicOrchestrator(Config.DEVICE).to(Config.DEVICE)
    return orchestrator

def test_orchestrator_initialization(sample_orchestrator):
    """StrategicOrchestrator 객체가 정상적으로 초기화되는지 테스트."""
    orch = sample_orchestrator
    assert orch is not None
    assert hasattr(orch, 'core_specialists')
    assert hasattr(orch, 'branch_modules')
    assert hasattr(orch, 'ai_router')

def test_airouter_forward_basic():
    """AIRouter.forward가 기본적인 입력에 대해 출력을 반환하는지 테스트."""
    num_modules = 5
    router = AIRouter(num_modules=num_modules, explore_prob=0.0).to(Config.DEVICE) # 탐색 비활성화
    B, N = 1, 10
    c = torch.randn(B, N, 3, device=Config.DEVICE)
    top = type('MockTop', (), {'residue_features': torch.randn(N, 64, device=Config.DEVICE)})() # Mock topology
    aux_outputs = {f'module_{i}': torch.randn(B, N, 4, device=Config.DEVICE) for i in range(num_modules)} # Mock aux outputs
    sim_params = {
        'temp': 300.0,
        'salt_conc': 0.1,
        'pH': 7.2,
        'ionic_strength': 0.2,
        'ptm_count': 2.0,
        'cooling_rate': 0.03,
        'force_scale': 1.0,
        'k_angle': 20.0,
        'theta0': 1.8,
        'k_dihedral': 0.5,
        'phi0_alpha': -0.6,
        'hydro_strength': 0.9,
        'ai_correction_active': 1.0,
    }

    weights, is_explored, names, active_mask = router(c, top, aux_outputs, sim_params)
    assert router.param_encoder[0].in_features == len(DEFAULT_RUNTIME_CONDITIONING_KEYS)

    assert weights.shape == (B, num_modules) # 가중치 모양 확인
    assert is_explored.shape == (B,) # 탐색 여부 모양 확인
    assert len(names) == num_modules # 모듈 이름 수 확인
    assert active_mask.shape == (B, num_modules)
    assert weights.sum(dim=-1).allclose(torch.ones(B, device=Config.DEVICE)) # 가중치 합이 1인지 확인
    assert not torch.isnan(weights).any() # NaN 확인
    assert not torch.isnan(active_mask).any()


def test_airouter_runtime_mode_accepts_extended_values():
    router = AIRouter(num_modules=3, explore_prob=0.0).to(Config.DEVICE)
    router.set_runtime_mode("compiled")
    assert router.runtime_mode == "compiled"
    router.set_runtime_mode("onnx")
    assert router.runtime_mode == "onnx"
    router.set_runtime_mode("invalid-mode")
    assert router.runtime_mode == "eager"


@pytest.mark.parametrize(
    "runtime_mode,prepare_attr",
    [("compiled", "_prepare_compiled_router"), ("onnx", "_prepare_onnx_router")],
)
def test_airouter_extended_runtime_mode_fallback_to_eager(monkeypatch, runtime_mode, prepare_attr):
    router = AIRouter(num_modules=4, explore_prob=0.0).to(Config.DEVICE)
    router.eval()
    router.set_runtime_mode(runtime_mode)
    monkeypatch.setattr(router, prepare_attr, lambda *_args, **_kwargs: False)
    B, N = 1, 8
    c = torch.randn(B, N, 3, device=Config.DEVICE)
    top = type("MockTop", (), {"residue_features": torch.randn(N, 64, device=Config.DEVICE)})()
    weights, is_explored, names, active_mask = router.route(
        c=c,
        top=top,
        sim_params={"temp": 300.0},
        module_keys=[f"module_{i}" for i in range(4)],
    )
    assert weights.shape == (B, 4)
    assert active_mask.shape == (B, 4)
    assert is_explored.shape == (B,)
    assert len(names) == 4
    assert torch.isfinite(weights).all()
    assert torch.isfinite(active_mask).all()

def test_orchestrator_forward_basic(sample_orchestrator):
    """StrategicOrchestrator.forward가 기본적인 입력에 대해 출력을 반환하는지 테스트."""
    orch = sample_orchestrator
    B, N = 1, 10
    c = torch.randn(B, N, 3, device=Config.DEVICE)
    # Mock topology, nb_data, pe, sim_params
    top = type('MockTop', (), {'residue_types': torch.randint(0, 20, (B, N), device=Config.DEVICE)})()
    nb_data = (torch.randint(0, N, (B, N, 10), device=Config.DEVICE), torch.randn(B, N, 10, device=Config.DEVICE), torch.ones(B, N, 10, device=Config.DEVICE))
    pe = torch.randn(B, 1, device=Config.DEVICE)
    sim_params = {'temp': 300.0, 'salt_conc': 0.1}

    f_orchestrated, aux_out = orch(c, top, nb_data, pe, sim_params)

    assert f_orchestrated.shape == c.shape # 출력 힘 모양 확인
    assert isinstance(aux_out, dict) # aux_out이 딕셔너리인지 확인
    assert 'router_was_explored' in aux_out # 필요한 키 존재 여부 확인
    assert 'router_used_weights' in aux_out
    assert 'router_action_log_probs' in aux_out
    assert 'router_onnx_providers' in aux_out
    assert 'router_onnx_iobinding_enabled' in aux_out
    assert 'router_onnx_iobinding_error' in aux_out
    assert not torch.isnan(f_orchestrated).any() # NaN 확인


def test_orchestrator_backward_nonzero_grad(sample_orchestrator):
    orch = sample_orchestrator
    B, N = 2, 10
    c = torch.randn(B, N, 3, device=Config.DEVICE)
    top = type('MockTop', (), {'residue_types': torch.randint(0, 20, (B, N), device=Config.DEVICE)})()
    nb_data = (
        torch.randint(0, N, (B, N, 10), device=Config.DEVICE),
        torch.randn(B, N, 10, device=Config.DEVICE),
        torch.ones(B, N, 10, device=Config.DEVICE),
    )
    pe = torch.randn(B, 1, device=Config.DEVICE)
    sim_params = {'temp': 300.0, 'salt_conc': 0.1}
    target = torch.randn(B, N, 3, device=Config.DEVICE)

    orch.zero_grad(set_to_none=True)
    pred, _ = orch(c, top, nb_data, pe, sim_params, ai_influence=1.0)
    loss = torch.nn.functional.mse_loss(pred, target)
    loss.backward()

    grad_sum = 0.0
    grad_count = 0
    for name, p in orch.named_parameters():
        if p.grad is None:
            continue
        g = float(p.grad.detach().abs().sum().item())
        if g > 0.0:
            grad_sum += g
            grad_count += 1

    assert grad_count > 0
    assert grad_sum > 0.0


def test_orchestrator_uncertainty_guard_forces_physics_fallback(monkeypatch):
    monkeypatch.setenv("AI_ROUTER_UNCERTAINTY_GUARD", "1")
    monkeypatch.setenv("AI_ROUTER_UNCERTAINTY_ENTROPY_THRESHOLD", "0.0")
    monkeypatch.setenv("AI_ROUTER_UNCERTAINTY_TOP1_THRESHOLD", "1.0")

    orch = StrategicOrchestrator(Config.DEVICE).to(Config.DEVICE)
    orch.eval()
    B, N = 1, 10
    c = torch.randn(B, N, 3, device=Config.DEVICE)
    top = type('MockTop', (), {'residue_types': torch.randint(0, 20, (B, N), device=Config.DEVICE)})()
    nb_data = (
        torch.randint(0, N, (B, N, 10), device=Config.DEVICE),
        torch.randn(B, N, 10, device=Config.DEVICE),
        torch.ones(B, N, 10, device=Config.DEVICE),
    )
    pe = torch.randn(B, 1, device=Config.DEVICE)
    sim_params = {'temp': 300.0, 'salt_conc': 0.1}

    f_orchestrated, aux_out = orch(c, top, nb_data, pe, sim_params, ai_influence=1.0)
    assert torch.allclose(f_orchestrated, torch.zeros_like(f_orchestrated), atol=1e-8)
    assert float(orch.last_uncertainty_fallback_rate) > 0.0
    assert 'router_uncertainty_fallback_rate' in aux_out

# 더 많은 테스트 케이스 추가 가능 (예: branch 모듈 호출, 탐색 기능 등)
