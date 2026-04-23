# tests/unit/test_core_forcefield.py

import pytest
import torch
import numpy as np
from core.forcefield import ForceField
from core.topology import TopologyFactory
from core.spatial import GridSpatialHash
from core.definitions import Config

@pytest.fixture
def sample_topology():
    """Test용 간단한 Topology 객체 생성."""
    n_res = 5
    box = [10.0, 10.0, 10.0]
    top = TopologyFactory(n_res, 'protein', box, Config.DEVICE, target_name='test')
    return top

@pytest.fixture
def sample_forcefield(sample_topology):
    """Test용 ForceField 객체 생성."""
    ff_params = {'d_e': 20.0, 'eps_solv': 25.0, 'sigma': 3.8, 'r0': 4.2}
    ff = ForceField(sample_topology, params=ff_params)
    return ff

def test_forcefield_initialization(sample_forcefield):
    """ForceField 객체가 정상적으로 초기화되는지 테스트."""
    ff = sample_forcefield
    assert ff is not None
    assert hasattr(ff, 'top')
    assert hasattr(ff, 'sh')
    assert hasattr(ff, 'ff')

def test_forcefield_compute_basic(sample_forcefield):
    """ForceField.compute가 기본적인 좌표 입력에 대해 힘과 에너지를 반환하는지 테스트."""
    ff = sample_forcefield
    # 간단한 좌표 생성 (예: 선형 구조)
    n_res = 5
    c = torch.linspace(0, 4, n_res, device=Config.DEVICE).view(1, n_res, 1).repeat(1, 1, 3) # [1, 5, 3]

    sh = GridSpatialHash([10.0, 10.0, 10.0], 12.0, Config.DEVICE)
    nb = sh.get_neighbor_data(c)

    f, pe = ff.compute(c, nb)

    assert f.shape == c.shape # 힘 텐서의 모양이 좌표와 같아야 함
    assert pe.shape == (1, 1) # Potential energy는 스칼라 (batch, 1)
    assert isinstance(f, torch.Tensor)
    assert isinstance(pe, torch.Tensor)
    # 힘이나 에너지가 NaN이 아닌지 확인
    assert not torch.isnan(f).any()
    assert not torch.isnan(pe).any()


def test_forcefield_can_force_pytorch_backend(sample_topology):
    ff = ForceField(sample_topology, force_backend="pytorch")
    assert ff.physics_backend == "pytorch"


def test_compute_reference_pytorch_shapes(sample_forcefield):
    ff = sample_forcefield
    n_res = 5
    c = torch.linspace(0, 4, n_res, device=Config.DEVICE).view(1, n_res, 1).repeat(1, 1, 3)
    f_ref, pe_ref = ff.compute_reference_pytorch(c, cutoff=12.0, max_neighbors=80)
    assert f_ref.shape == c.shape
    assert pe_ref.shape == (1, 1)

# 더 많은 테스트 케이스 추가 가능 (예: 특정 거리에서의 힘, cutoff 테스트 등)
