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
            assert torch.equal(reconstructed.cpu(), identity)

    def test_presort_preserves_neighbor_sets_by_original_atom_id(self):
        """presort on/off는 원래 atom id 기준 neighbor set이 같아야 함."""
        coords = torch.tensor(
            [
                [
                    [8.0, 8.0, 8.0],
                    [1.0, 1.0, 1.0],
                    [1.6, 1.0, 1.0],
                    [2.0, 1.0, 1.0],
                    [10.0, 10.0, 10.0],
                    [10.5, 10.0, 10.0],
                ],
                [
                    [11.0, 1.0, 1.0],
                    [3.2, 3.0, 3.0],
                    [2.6, 3.0, 3.0],
                    [2.0, 3.0, 3.0],
                    [12.1, 1.0, 1.0],
                    [12.7, 1.0, 1.0],
                ],
            ],
            dtype=torch.float32,
        )
        sorter = MortonSorter([16.0, 16.0, 16.0], "cpu")
        _, sort_indices = sorter.sort(coords)
        assert any(
            not torch.equal(sort_indices[b], torch.arange(coords.shape[1]))
            for b in range(coords.shape[0])
        )

        sh_on = GridSpatialHash(
            [16.0, 16.0, 16.0],
            1.1,
            "cpu",
            skin=0.0,
            max_neighbors=8,
            use_morton_presort=True,
        )
        sh_off = GridSpatialHash(
            [16.0, 16.0, 16.0],
            1.1,
            "cpu",
            skin=0.0,
            max_neighbors=8,
            use_morton_presort=False,
        )
        nb_on = sh_on.get_neighbor_data(coords, force_rebuild=True)
        nb_off = sh_off.get_neighbor_data(coords, force_rebuild=True)

        for b in range(coords.shape[0]):
            for atom_id in range(coords.shape[1]):
                on_neighbors = set(nb_on[0][b, atom_id][nb_on[2][b, atom_id]].tolist())
                off_neighbors = set(nb_off[0][b, atom_id][nb_off[2][b, atom_id]].tolist())
                assert on_neighbors == off_neighbors

    def test_presort_does_not_emit_self_neighbor_indices(self):
        """presort on의 유효 neighbor index에는 자기 atom id가 없어야 함."""
        coords = torch.tensor(
            [
                [
                    [8.0, 8.0, 8.0],
                    [1.0, 1.0, 1.0],
                    [1.6, 1.0, 1.0],
                    [2.0, 1.0, 1.0],
                    [10.0, 10.0, 10.0],
                    [10.5, 10.0, 10.0],
                ],
                [
                    [11.0, 1.0, 1.0],
                    [3.2, 3.0, 3.0],
                    [2.6, 3.0, 3.0],
                    [2.0, 3.0, 3.0],
                    [12.1, 1.0, 1.0],
                    [12.7, 1.0, 1.0],
                ],
            ],
            dtype=torch.float32,
        )
        sh = GridSpatialHash(
            [16.0, 16.0, 16.0],
            1.1,
            "cpu",
            skin=0.0,
            max_neighbors=8,
            use_morton_presort=True,
        )
        nb_idx, _, nb_mask = sh.get_neighbor_data(coords, force_rebuild=True)

        for b in range(coords.shape[0]):
            for atom_id in range(coords.shape[1]):
                valid_neighbors = nb_idx[b, atom_id][nb_mask[b, atom_id]]
                assert atom_id not in valid_neighbors.tolist()


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
