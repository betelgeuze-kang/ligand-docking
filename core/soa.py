# core/soa.py
"""SoA (Structure of Arrays) 메모리 레이아웃 유틸리티.

GPU 캐시 히트율 극대화를 위해 좌표/힘 텐서를 AoS ↔ SoA 변환합니다.
AoS: [B, N, 3] — x0y0z0 x1y1z1 ... (인터리빙)
SoA: (x[B,N], y[B,N], z[B,N]) — x0x1x2... y0y1y2... z0z1z2... (분리)

SoA 레이아웃의 이점:
- GPU 워프 내 coalesced memory access
- 캐시라인 당 유효 데이터 비율 향상 (x만 필요한 연산에서 y,z 로드 불필요)
- SIMD 벡터라이제이션 효율 향상
"""

import torch
from typing import Tuple, Optional


class SoACoords:
    """SoA 좌표 래퍼.

    ``x``, ``y``, ``z`` 필드로 직접 접근 가능하며,
    ``to_aos()``로 언제든 ``[B, N, 3]`` 형태로 복원 가능합니다.
    """

    __slots__ = ("x", "y", "z", "_B", "_N")

    def __init__(self, x: torch.Tensor, y: torch.Tensor, z: torch.Tensor):
        """
        Args:
            x: [B, N] x 좌표
            y: [B, N] y 좌표
            z: [B, N] z 좌표
        """
        assert x.shape == y.shape == z.shape, "x, y, z shape must match"
        assert x.ndim == 2, "expected [B, N] shape"
        self.x = x.contiguous()
        self.y = y.contiguous()
        self.z = z.contiguous()
        self._B = x.shape[0]
        self._N = x.shape[1]

    @property
    def shape(self) -> Tuple[int, int]:
        return (self._B, self._N)

    @property
    def device(self):
        return self.x.device

    @property
    def dtype(self):
        return self.x.dtype

    def to_aos(self) -> torch.Tensor:
        """SoA → AoS 변환: [B, N, 3] 텐서 반환."""
        return torch.stack([self.x, self.y, self.z], dim=-1)

    def to(self, device=None, dtype=None) -> "SoACoords":
        """디바이스/dtype 변환."""
        kwargs = {}
        if device is not None:
            kwargs["device"] = device
        if dtype is not None:
            kwargs["dtype"] = dtype
        return SoACoords(
            self.x.to(**kwargs),
            self.y.to(**kwargs),
            self.z.to(**kwargs),
        )

    def clone(self) -> "SoACoords":
        return SoACoords(self.x.clone(), self.y.clone(), self.z.clone())

    def half(self) -> "SoACoords":
        return SoACoords(self.x.half(), self.y.half(), self.z.half())

    def float(self) -> "SoACoords":
        return SoACoords(self.x.float(), self.y.float(), self.z.float())


def aos_to_soa(coords: torch.Tensor) -> SoACoords:
    """AoS [B, N, 3] → SoA (x[B,N], y[B,N], z[B,N]) 변환.

    변환 시 각 배열이 contiguous하게 배치되어
    GPU 캐시라인 활용이 극대화됩니다.
    """
    assert coords.ndim == 3 and coords.shape[-1] == 3, "expected [B, N, 3]"
    x = coords[:, :, 0].contiguous()
    y = coords[:, :, 1].contiguous()
    z = coords[:, :, 2].contiguous()
    return SoACoords(x, y, z)


def soa_to_aos(soa: SoACoords) -> torch.Tensor:
    """SoA → AoS [B, N, 3] 변환."""
    return soa.to_aos()


def soa_pairwise_dist_sq(
    soa: SoACoords,
    idx_i: torch.Tensor,
    idx_j: torch.Tensor,
    box: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """SoA 레이아웃에서 쌍별 거리 제곱 계산.

    AoS 대비 메모리 접근 패턴이 개선됩니다:
    - x 채널만 로드 → x 차이 계산
    - y 채널만 로드 → y 차이 계산
    - z 채널만 로드 → z 차이 계산

    Args:
        soa: SoA 좌표
        idx_i: [M] 원자 i 인덱스
        idx_j: [M] 원자 j 인덱스
        box: [3] 또는 None, PBC 박스 크기

    Returns:
        dist_sq: [B, M] 거리 제곱
    """
    # 각 채널별로 독립 로드 — coalesced access
    dx = soa.x[:, idx_j] - soa.x[:, idx_i]
    dy = soa.y[:, idx_j] - soa.y[:, idx_i]
    dz = soa.z[:, idx_j] - soa.z[:, idx_i]

    if box is not None:
        bx = box[0]
        by = box[1]
        bz = box[2]
        dx = dx - bx * torch.round(dx / bx)
        dy = dy - by * torch.round(dy / by)
        dz = dz - bz * torch.round(dz / bz)

    return dx * dx + dy * dy + dz * dz


def soa_neighbor_dist_sq(
    soa: SoACoords,
    atom_x: torch.Tensor,
    atom_y: torch.Tensor,
    atom_z: torch.Tensor,
    candidate_x: torch.Tensor,
    candidate_y: torch.Tensor,
    candidate_z: torch.Tensor,
    box: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """SoA 레이아웃에서 단일 원자 ↔ 후보 목록 거리 제곱 계산.

    Args:
        atom_x, atom_y, atom_z: 스칼라 또는 [1]
        candidate_x, candidate_y, candidate_z: [M]
        box: [3] 또는 None

    Returns:
        dist_sq: [M]
    """
    dx = candidate_x - atom_x
    dy = candidate_y - atom_y
    dz = candidate_z - atom_z

    if box is not None:
        dx = dx - box[0] * torch.round(dx / box[0])
        dy = dy - box[1] * torch.round(dy / box[1])
        dz = dz - box[2] * torch.round(dz / box[2])

    return dx * dx + dy * dy + dz * dz
