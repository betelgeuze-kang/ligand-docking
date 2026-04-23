# tests/unit/test_runtime_governance.py

import pytest
import torch
import numpy as np
from runtime.governance import RuntimeGovernanceLayer, AIControlModel

@pytest.fixture
def sample_ai_ctrl_model():
    """Test용 AIControlModel 객체 생성."""
    input_dim = 11
    output_dim = 3
    model = AIControlModel(input_dim=input_dim, output_dim=output_dim)
    return model

@pytest.fixture
def sample_governance_layer(sample_ai_ctrl_model):
    """Test용 RuntimeGovernanceLayer 객체 생성."""
    layer = RuntimeGovernanceLayer(sample_ai_ctrl_model)
    return layer

def test_governance_layer_initialization(sample_governance_layer):
    """RuntimeGovernanceLayer 객체가 정상적으로 초기화되는지 테스트."""
    gov = sample_governance_layer
    assert gov is not None
    assert hasattr(gov, 'ai_ctrl_model')
    assert hasattr(gov, 'current_intervention_rate')
    assert hasattr(gov, 'current_correction_strength')

def test_governance_layer_calculate_reward_basic(sample_governance_layer):
    """RuntimeGovernanceLayer.calculate_reward가 기본적인 상태 입력에 대해 보상을 계산하는지 테스트."""
    gov = sample_governance_layer

    # Mock state dicts
    sim_state = {'RMSD': 2.0, 'energy': -100.0, 'temp': 300.0, 'ionic_strength': 0.1, 'Rg': 1.5, 'SASA': 100.0}
    router_info = (torch.tensor([[0.1, 0.2, 0.3, 0.2, 0.2]]), ['mod1', 'mod2', 'mod3', 'mod4', 'mod5'], torch.tensor([False]))
    guard_status = {'violation_count': 0, 'last_energy_drift': 0.001, 'last_momentum_drift': 0.0005}

    # First call to store previous state (will not calculate reward as prev_state is None)
    gov.update(sim_state, router_info, guard_status)

    # Second call to calculate reward
    sim_state2 = {'RMSD': 1.8, 'energy': -101.0, 'temp': 300.0, 'ionic_strength': 0.1, 'Rg': 1.4, 'SASA': 105.0} # Improved RMSD and energy
    router_info2 = (torch.tensor([[0.15, 0.15, 0.3, 0.2, 0.2]]), ['mod1', 'mod2', 'mod3', 'mod4', 'mod5'], torch.tensor([True])) # Exploratory action
    guard_status2 = {'violation_count': 0, 'last_energy_drift': 0.0008, 'last_momentum_drift': 0.0003}

    reward = gov.calculate_reward(sim_state2, router_info2, guard_status2)

    # Should be positive due to improvement and exploration
    assert reward > 0.0

# 더 많은 테스트 케이스 추가 가능 (예: 위반 증가, 구조 안정화 등)
