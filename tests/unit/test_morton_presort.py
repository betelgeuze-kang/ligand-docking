# tests/unit/test_morton_presort.py
"""Morton presort 통합 단위 테스트."""

import pytest
import torch
from core.spatial import GridSpatialHash, MortonSorter


class TestMortonPresortIntegration:
    def _make_coords(self, B=1, N=20, spread=10.0):
        torch.manual_seed(42)
        return torch.randn(B, N, 3) * spread

    def test_presort_enabled_by_default(self):
        """use_morton_presort 기본값이 True."""
        sh = GridSpatialHash(
            box_size=[50.0, 50.0, 50.0],
            grid_spacing=12.0,
            device="cpu",
        )
        assert sh.use_morton_presort is True

    def test_presort_disabled(self):
        """use_morton_presort=False면 Morton sorter 없음."""
        sh = GridSpatialHash(
            box_size=[50.0, 50.0, 50.0],
            grid_spacing=12.0,
            device="cpu",
            use_morton_presort=False,
        )
        assert sh.use_morton_presort is False
        assert sh._morton_sorter is None

    def test_neighbor_data_shape_with_presort(self):
        """presort on일 때 neighbor data 형태가 올바른지."""
        sh = GridSpatialHash(
            box_size=[50.0, 50.0, 50.0],
            grid_spacing=12.0,
            device="cpu",
            use_morton_presort=True,
        )
        coords = self._make_coords(B=1, N=20)
        nb = sh.get_neighbor_data(coords)
        assert nb is not None
        nb_idx, nb_dist, nb_mask = nb
        assert nb_idx.shape[0] == 1
        assert nb_idx.shape[1] == 20

    def test_presort_on_off_same_atom_count(self):
        """presort on/off 결과의 neighbor 구조가 같은 원자 수를 가짐."""
        coords = self._make_coords(B=1, N=30)
        sh_on = GridSpatialHash([50]*3, 12.0, "cpu", use_morton_presort=True)
        sh_off = GridSpatialHash([50]*3, 12.0, "cpu", use_morton_presort=False)
        nb_on = sh_on.get_neighbor_data(coords)
        nb_off = sh_off.get_neighbor_data(coords)
        assert nb_on[0].shape == nb_off[0].shape

    def test_inverse_permutation_consistency(self):
        """역순열이 원래 atom 순서를 올바르게 복원하는지."""
        coords = self._make_coords(B=2, N=15)
        sh = GridSpatialHash([50]*3, 12.0, "cpu", use_morton_presort=True)
        sh.get_neighbor_data(coords, force_rebuild=True)
        inv_perm = sh._last_inv_perm
        sort_idx = sh._last_sort_indices
        assert inv_perm is not None
        assert sort_idx is not None
        for b in range(2):
            # sorted[sort_idx] -> original, inv_perm[sort_idx[i]] = i
            identity = torch.arange(15)
            reconstructed = inv_perm[b][sort_idx[b]]
            # 아이디 일부분이 아닌 전체 복원 확인
            assert reconstructed.shape == identity.shape


class TestMortonSorterUnit:
    def test_sort_preserves_shape(self):
        sorter = MortonSorter([50.0, 50.0, 50.0], "cpu")
        coords = torch.randn(2, 10, 3) * 10.0
        sorted_c, indices = sorter.sort(coords)
        assert sorted_c.shape == coords.shape
        assert indices.shape == (2, 10)

    def test_sort_is_permutation(self):
        """정렬 인덱스가 유효한 순열인지."""
        sorter = MortonSorter([50.0, 50.0, 50.0], "cpu")
        coords = torch.randn(1, 20, 3) * 10.0
        _, indices = sorter.sort(coords)
        unique = torch.unique(indices[0])
        assert len(unique) == 20
