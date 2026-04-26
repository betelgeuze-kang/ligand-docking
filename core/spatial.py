import os
import torch
import torch.nn as nn

class GridSpatialHash(nn.Module):
    """
    Grid-based neighbor list generation with cell lists.
    Average complexity is O(N) for bounded density systems.
    """
    def __init__(
        self,
        box_size,
        grid_spacing,
        device,
        cutoff=None,
        max_neighbors=100,
        skin=2.0,
        rebuild_stride=4,
        max_atoms_per_cell=64,
        use_morton_presort=True,
    ):
        super(GridSpatialHash, self).__init__()
        self.box_size = torch.as_tensor(box_size, dtype=torch.float32, device=device)
        self.grid_spacing = float(grid_spacing)
        if self.grid_spacing <= 0.0:
            raise ValueError("grid_spacing must be > 0.")
        self.device = device
        self.cutoff = float(cutoff if cutoff is not None else grid_spacing)
        if self.cutoff <= 0.0:
            raise ValueError("cutoff must be > 0.")
        self.max_neighbors = int(max_neighbors)
        if self.max_neighbors <= 0:
            raise ValueError("max_neighbors must be > 0.")
        self.max_atoms_per_cell = int(max_atoms_per_cell)
        if self.max_atoms_per_cell <= 0:
            raise ValueError("max_atoms_per_cell must be > 0.")
        self.auto_grow = os.environ.get("NBLIST_AUTOGROW", "1") == "1"
        self.max_neighbors_cap = max(
            self.max_neighbors,
            int(os.environ.get("NBLIST_MAX_NEIGHBORS_CAP", "256")),
        )
        self.max_autogrow_rounds = max(
            1,
            int(os.environ.get("NBLIST_AUTOGROW_ROUNDS", "3")),
        )
        self._last_max_required_neighbors = 0
        self._last_neighbor_saturated_atoms = 0
        self.skin = float(max(skin, 0.0))
        self.rebuild_stride = int(max(rebuild_stride, 1))

        self.list_cutoff = self.cutoff + self.skin
        self.cell_size = max(self.list_cutoff, 1e-6)

        raw_dims = torch.floor(self.box_size / self.cell_size).to(dtype=torch.int64)
        self.grid_dims = torch.clamp(raw_dims, min=1)
        self._cell_plane = int(self.grid_dims[1].item()) * int(self.grid_dims[2].item())

        self._cache_nb = None
        self._cache_ref_coords = None
        self._cache_shape = None
        self._call_counter = 0
        self._last_rebuild_call = -1
        self._last_displacement_check_call = -1
        self.use_morton_presort = bool(use_morton_presort)
        self._morton_sorter = MortonSorter(box_size, device) if self.use_morton_presort else None
        self._last_sort_indices = None
        self._last_inv_perm = None

    def reset_cache(self):
        self._cache_nb = None
        self._cache_ref_coords = None
        self._cache_shape = None
        self._last_rebuild_call = -1
        self._last_displacement_check_call = -1

    def _minimum_image(self, dr):
        return dr - self.box_size * torch.floor(dr / self.box_size + 0.5)

    def _needs_rebuild(self, c):
        if self._cache_nb is None or self._cache_ref_coords is None or self._cache_shape is None:
            return True
        if tuple(c.shape) != tuple(self._cache_shape):
            return True
        if c.device != self._cache_ref_coords.device:
            return True
        if self.skin <= 0.0:
            return True
        if (self._call_counter - self._last_displacement_check_call) < self.rebuild_stride:
            return False

        self._last_displacement_check_call = self._call_counter
        disp = self._minimum_image(c - self._cache_ref_coords)
        max_disp = disp.norm(dim=-1).amax()
        return bool(max_disp.item() >= (0.5 * self.skin))

    def _build_neighbor_data(self, c):
        B, N, _ = c.shape
        device = c.device
        dtype = c.dtype
        box = self.box_size.to(device=device, dtype=dtype)
        max_required_neighbors = 0
        saturated_atoms = 0

        nb_idx = torch.full((B, N, self.max_neighbors), -1, dtype=torch.long, device=device)
        nb_dist = torch.zeros((B, N, self.max_neighbors), dtype=torch.float32, device=device)
        nb_mask = torch.zeros((B, N, self.max_neighbors), dtype=torch.bool, device=device)

        cutoff_sq = float(self.list_cutoff * self.list_cutoff)
        gx = int(self.grid_dims[0].item())
        gy = int(self.grid_dims[1].item())
        gz = int(self.grid_dims[2].item())
        cell_plane = self._cell_plane

        for b in range(B):
            coords_b = c[b]
            cell_coords = torch.floor(coords_b / self.cell_size).to(dtype=torch.int64)
            cell_coords = torch.remainder(cell_coords, self.grid_dims.view(1, 3))

            cell_flat = (
                cell_coords[:, 0] * (self.grid_dims[1] * self.grid_dims[2])
                + cell_coords[:, 1] * self.grid_dims[2]
                + cell_coords[:, 2]
            )

            order = torch.argsort(cell_flat)
            flat_sorted = cell_flat[order]
            uniq, counts = torch.unique_consecutive(flat_sorted, return_counts=True)
            starts = torch.cumsum(
                torch.cat([counts.new_zeros(1), counts[:-1]], dim=0),
                dim=0,
            )
            cell_ranges = {
                int(cid): (int(st), int(st + cnt))
                for cid, st, cnt in zip(uniq.tolist(), starts.tolist(), counts.tolist())
            }

            for cell_id, (st, ed) in cell_ranges.items():
                if ed <= st:
                    continue
                cx = cell_id // cell_plane
                rem = cell_id % cell_plane
                cy = rem // gz
                cz = rem % gz

                candidate_chunks = []
                for dx in (-1, 0, 1):
                    nx = (cx + dx) % gx
                    for dy in (-1, 0, 1):
                        ny = (cy + dy) % gy
                        for dz in (-1, 0, 1):
                            nz = (cz + dz) % gz
                            ncell_id = nx * cell_plane + ny * gz + nz
                            rng = cell_ranges.get(ncell_id)
                            if rng is not None:
                                candidate_chunks.append(order[rng[0]:rng[1]])
                if not candidate_chunks:
                    continue

                candidate_idx = torch.cat(candidate_chunks, dim=0)
                candidate_pos = coords_b[candidate_idx]
                atom_idx_in_cell = order[st:ed]

                for atom_id in atom_idx_in_cell.tolist():
                    dr = coords_b[atom_id].unsqueeze(0) - candidate_pos
                    dr -= box * torch.floor(dr / box + 0.5)
                    r2 = (dr * dr).sum(dim=-1)
                    valid = (candidate_idx != atom_id) & (r2 < cutoff_sq)
                    if not valid.any():
                        continue

                    valid_idx = torch.nonzero(valid, as_tuple=False).squeeze(-1)
                    n_idx = candidate_idx[valid_idx]
                    n_r2 = r2[valid_idx]
                    sort = torch.argsort(n_r2)
                    n_idx = n_idx[sort]
                    n_r2 = n_r2[sort]

                    required = int(n_idx.numel())
                    if required > max_required_neighbors:
                        max_required_neighbors = required
                    if required > self.max_neighbors:
                        saturated_atoms += 1

                    if n_idx.numel() > self.max_neighbors:
                        n_idx = n_idx[: self.max_neighbors]
                        n_r2 = n_r2[: self.max_neighbors]

                    n_keep = int(n_idx.numel())
                    nb_idx[b, atom_id, :n_keep] = n_idx
                    nb_dist[b, atom_id, :n_keep] = torch.sqrt(torch.clamp(n_r2, min=0.01)).to(torch.float32)
                    nb_mask[b, atom_id, :n_keep] = True

        self._last_max_required_neighbors = int(max_required_neighbors)
        self._last_neighbor_saturated_atoms = int(saturated_atoms)
        return nb_idx, nb_dist, nb_mask

    def get_neighbor_data(self, c, force_rebuild=False):
        """
        Generates neighbor list using cached cell lists.
        Morton presort가 활성화되면 빌드 전 좌표를 Morton 순서로
        정렬하고, 결과를 원래 atom 순서로 복원합니다.
        Args:
            c: Coordinates [B, N, 3]
        Returns:
            nb_idx: Neighbor indices [B, N, K]
            nb_dist: Neighbor distances [B, N, K]
            nb_mask: Neighbor mask [B, N, K]
        """
        self._call_counter += 1
        if force_rebuild or self._needs_rebuild(c):
            # Morton presort 적용
            build_coords = c
            sort_indices = None
            inv_perm = None
            if self.use_morton_presort and self._morton_sorter is not None:
                build_coords, sort_indices = self._morton_sorter.sort(c)
                B, N = sort_indices.shape
                inv_perm = torch.zeros_like(sort_indices)
                for b in range(B):
                    inv_perm[b, sort_indices[b]] = torch.arange(N, device=c.device)
                self._last_sort_indices = sort_indices
                self._last_inv_perm = inv_perm

            rounds = self.max_autogrow_rounds if self.auto_grow else 1
            for _ in range(rounds):
                self._cache_nb = self._build_neighbor_data(build_coords)
                if self._last_max_required_neighbors <= self.max_neighbors:
                    break
                if self.max_neighbors >= self.max_neighbors_cap:
                    break
                new_max = min(
                    self.max_neighbors_cap,
                    max(self.max_neighbors * 2, self._last_max_required_neighbors),
                )
                if new_max <= self.max_neighbors:
                    break
                self.max_neighbors = int(new_max)

            # Morton 역순열 적용: neighbor data를 원래 atom 순서로 복원
            if inv_perm is not None and self._cache_nb is not None:
                nb_idx, nb_dist, nb_mask = self._cache_nb
                B, N, K = nb_idx.shape
                # 인덱스를 원래 순서로 변환
                valid = nb_idx >= 0
                nb_idx_orig = torch.where(
                    valid,
                    sort_indices.unsqueeze(-1)
                    .expand_as(nb_idx)
                    .gather(1, nb_idx.clamp(min=0)),
                    nb_idx,
                )
                # 행도 원래 순서로 재배열
                nb_idx_reorder = torch.zeros_like(nb_idx_orig)
                nb_dist_reorder = torch.zeros_like(nb_dist)
                nb_mask_reorder = torch.zeros_like(nb_mask)
                for b in range(B):
                    nb_idx_reorder[b] = nb_idx_orig[b][inv_perm[b]]
                    nb_dist_reorder[b] = nb_dist[b][inv_perm[b]]
                    nb_mask_reorder[b] = nb_mask[b][inv_perm[b]]
                self._cache_nb = (nb_idx_reorder, nb_dist_reorder, nb_mask_reorder)

            self._cache_ref_coords = c.detach().clone()
            self._cache_shape = tuple(c.shape)
            self._last_rebuild_call = self._call_counter
            self._last_displacement_check_call = self._call_counter
        return self._cache_nb

class MortonSorter(nn.Module):
    """
    Morton sorting for improved cache locality in neighbor searches.
    """
    def __init__(self, box_size, device):
        super(MortonSorter, self).__init__()
        self.box_size = torch.tensor(box_size, dtype=torch.float32, device=device)
        self.device = device

    def encode_morton(self, coords):
        """
        Encodes 3D coordinates into a 1D Morton code.
        Args:
            coords: [N, 3] coordinates
        Returns:
            morton_codes: [N] Morton codes
        """
        # Normalize coordinates to integer grid
        max_bits = 10 # Example precision
        grid_coords = (coords / self.box_size * (2**max_bits - 1)).int()
        grid_coords = torch.clamp(grid_coords, 0, 2**max_bits - 1)

        # Interleave bits
        x, y, z = grid_coords.unbind(-1)
        morton = torch.zeros_like(x)
        for i in range(max_bits):
            morton |= ((x >> i & 1) << (3 * i)) | \
                      ((y >> i & 1) << (3 * i + 1)) | \
                      ((z >> i & 1) << (3 * i + 2))
        return morton

    def sort(self, coords):
        """
        Sorts coordinates based on Morton code.
        Args:
            coords: [B, N, 3] coordinates
        Returns:
            sorted_coords: [B, N, 3] sorted coordinates
            sort_indices: [B, N] indices used for sorting
        """
        B, N, _ = coords.shape
        sorted_coords = torch.zeros_like(coords)
        sort_indices = torch.zeros((B, N), dtype=torch.long, device=coords.device)

        for b in range(B):
            morton_codes = self.encode_morton(coords[b]) # [N]
            _, idx = torch.sort(morton_codes)
            sorted_coords[b] = coords[b][idx]
            sort_indices[b] = idx

        return sorted_coords, sort_indices


class AdReSSSelector:
    """AdResS 선택적 해상도 분류기 (포켓 주변 고해상도 + 하드캡).

    포켓 중심으로부터의 거리를 기반으로 원자를 세 영역으로 분류합니다:
    - **high**: 전원자(all-atom) 해상도
    - **hybrid**: 전원자-CG 혼합 전이 영역
    - **low**: 조립된(coarse-grained) 해상도

    ``max_high_res_fraction`` 하드캡(기본 10%)을 초과하면 유효 반경을
    자동으로 축소하여 tail latency/속도 붕괴를 방지합니다.
    """

    def __init__(
        self,
        pocket_center,
        high_res_radius: float = 15.0,
        hybrid_width: float = 5.0,
        max_high_res_fraction: float = 0.10,
        device=None,
    ):
        if device is None:
            device = torch.device("cpu")
        self.pocket_center = torch.as_tensor(
            pocket_center, dtype=torch.float32, device=device
        ).view(1, 1, 3)
        self.high_res_radius = float(max(high_res_radius, 0.0))
        self.hybrid_width = float(max(hybrid_width, 0.0))
        self.max_high_res_fraction = float(
            min(max(max_high_res_fraction, 0.0), 1.0)
        )
        self.device = device
        self._effective_radius: float = self.high_res_radius
        self._last_high_fraction: float = 0.0

    @property
    def effective_radius(self) -> float:
        """현재 적용 중인 유효 high-res 반경."""
        return self._effective_radius

    @property
    def last_high_fraction(self) -> float:
        """마지막 classify 호출의 high+hybrid 비율."""
        return self._last_high_fraction

    def classify(self, coords: torch.Tensor):
        """원자를 high/hybrid/low 영역으로 분류합니다.

        Args:
            coords: 좌표 텐서 ``[B, N, 3]``.

        Returns:
            ``(high_mask, hybrid_mask, low_mask)`` — 각각 ``[B, N]`` bool 텐서.
        """
        B, N, _ = coords.shape
        center = self.pocket_center.to(device=coords.device, dtype=coords.dtype)
        dist = (coords - center).norm(dim=-1)  # [B, N]

        radius = self.high_res_radius
        outer = radius + self.hybrid_width

        high_mask = dist <= radius
        hybrid_mask = (dist > radius) & (dist <= outer)

        # 하드캡 적용: high+hybrid 비율이 max_high_res_fraction 초과 시
        # 반경을 이진검색으로 축소
        total_atoms = B * N
        active_count = int((high_mask | hybrid_mask).sum().item())
        fraction = active_count / max(total_atoms, 1)

        if fraction > self.max_high_res_fraction and N > 0:
            radius = self._shrink_radius_to_cap(dist, N)
            outer = radius + self.hybrid_width
            high_mask = dist <= radius
            hybrid_mask = (dist > radius) & (dist <= outer)
            active_count = int((high_mask | hybrid_mask).sum().item())
            fraction = active_count / max(total_atoms, 1)

        low_mask = ~(high_mask | hybrid_mask)
        self._effective_radius = float(radius)
        self._last_high_fraction = float(fraction)
        return high_mask, hybrid_mask, low_mask

    def _shrink_radius_to_cap(self, dist: torch.Tensor, N: int) -> float:
        """이진 검색으로 하드캡을 만족하는 최대 반경을 찾습니다."""
        lo, hi = 0.0, self.high_res_radius
        target_max = self.max_high_res_fraction
        total = dist.numel()
        for _ in range(32):
            mid = (lo + hi) * 0.5
            outer_mid = mid + self.hybrid_width
            cnt = int(((dist <= outer_mid)).sum().item())
            frac = cnt / max(total, 1)
            if frac > target_max:
                hi = mid
            else:
                lo = mid
        return lo

    def get_effective_radius(self) -> float:
        """현재 유효 반경 반환 (classify 호출 후 갱신됨)."""
        return self._effective_radius


class ZOrderCellTraversal:
    """Z-order(Morton) 순서로 cell을 순회하는 이터레이터.

    cell-list 구축 시 cell 순회 순서를 선형(0,1,2,...)이 아니라
    Morton 순서로 통일하면 인접 셀이 메모리에서도 가까워져
    L2 캐시 지역성이 향상됩니다.
    """

    @staticmethod
    def _interleave_bits_3d(x: int, y: int, z: int, bits: int = 10) -> int:
        code = 0
        for i in range(bits):
            code |= ((x >> i & 1) << (3 * i)) | \
                    ((y >> i & 1) << (3 * i + 1)) | \
                    ((z >> i & 1) << (3 * i + 2))
        return code

    @staticmethod
    def sorted_cell_ids(gx: int, gy: int, gz: int) -> list:
        """그리드 차원을 받아 Z-order로 정렬된 cell ID 리스트 반환.

        Args:
            gx, gy, gz: 그리드 x, y, z 차원

        Returns:
            Z-order 정렬된 (cx, cy, cz, flat_id) 튜플 리스트
        """
        cells = []
        cell_plane = gy * gz
        for cx in range(gx):
            for cy in range(gy):
                for cz in range(gz):
                    flat_id = cx * cell_plane + cy * gz + cz
                    morton = ZOrderCellTraversal._interleave_bits_3d(cx, cy, cz)
                    cells.append((morton, cx, cy, cz, flat_id))
        cells.sort(key=lambda t: t[0])
        return [(cx, cy, cz, fid) for _, cx, cy, cz, fid in cells]


class AdReSSScheduler:
    """AdResS 실시간 재분류 스케줄러.

    포켓 중심이 시뮬레이션 중 이동할 수 있으므로,
    N스텝마다 ``AdReSSSelector.classify()``를 재호출하여
    영역 마스크를 갱신합니다. 포켓 중심도 동적으로 업데이트 가능합니다.
    """

    def __init__(
        self,
        selector: AdReSSSelector,
        reclassify_interval: int = 100,
    ):
        self.selector = selector
        self.reclassify_interval = max(int(reclassify_interval), 1)
        self._step_count = 0
        self._last_masks = None
        self._needs_initial = True

    def step(self, coords: torch.Tensor, pocket_center=None):
        """매 스텝 호출. 필요 시 재분류 수행.

        Args:
            coords: [B, N, 3] 현재 좌표
            pocket_center: (선택) 갱신할 포켓 중심 [3]

        Returns:
            ``(high_mask, hybrid_mask, low_mask)`` 또는 캐시된 이전 결과
        """
        self._step_count += 1

        if pocket_center is not None:
            self.selector.pocket_center = torch.as_tensor(
                pocket_center,
                dtype=torch.float32,
                device=coords.device,
            ).view(1, 1, 3)
            self._needs_initial = True  # 중심 변경 → 즉시 재분류

        if self._needs_initial or (self._step_count % self.reclassify_interval == 0):
            self._last_masks = self.selector.classify(coords)
            self._needs_initial = False

        return self._last_masks

    def reset(self):
        self._step_count = 0
        self._last_masks = None
        self._needs_initial = True

    @property
    def last_effective_radius(self) -> float:
        return self.selector.effective_radius


class AsyncNeighborPrefetcher:
    """비동기 neighbor list 프리페치.

    현재 스텝의 force 계산과 다음 스텝의 neighbor list 빌드를
    별도 CUDA stream에서 겹쳐서 실행하여 latency를 숨깁니다.

    CPU 또는 CUDA 미지원 환경에서는 동기 모드로 폴백합니다.
    """

    def __init__(self, spatial_hash: "GridSpatialHash"):
        self.sh = spatial_hash
        self._stream = None
        self._pending_nb = None
        self._pending_event = None
        self._async_enabled = False

        if torch.cuda.is_available():
            try:
                self._stream = torch.cuda.Stream()
                self._async_enabled = True
            except Exception:
                self._async_enabled = False

    @property
    def is_async(self) -> bool:
        return self._async_enabled

    def prefetch(self, next_coords: torch.Tensor):
        """다음 스텝 좌표로 neighbor list 프리페치를 시작합니다.

        Args:
            next_coords: [B, N, 3] 다음 스텝 예상 좌표
        """
        if not self._async_enabled:
            self._pending_nb = self.sh.get_neighbor_data(next_coords, force_rebuild=True)
            return

        stream = self._stream
        event = torch.cuda.Event()
        with torch.cuda.stream(stream):
            self._pending_nb = self.sh.get_neighbor_data(
                next_coords, force_rebuild=True
            )
        event.record(stream)
        self._pending_event = event

    def get(self):
        """프리페치된 neighbor list를 반환합니다. 완료까지 대기."""
        if self._pending_event is not None:
            self._pending_event.synchronize()
            self._pending_event = None
        result = self._pending_nb
        self._pending_nb = None
        return result

    def has_pending(self) -> bool:
        return self._pending_nb is not None


class MixedPrecisionNeighborConfig:
    """Mixed-precision neighbor distance 설정.

    거리 계산을 FP16으로 수행하여 메모리 대역폭을 절감하고,
    force 계산에서만 FP32를 사용합니다.
    """

    def __init__(
        self,
        use_fp16_distance: bool = False,
        fp16_cutoff_threshold: float = 50.0,
    ):
        self.use_fp16_distance = bool(use_fp16_distance)
        self.fp16_cutoff_threshold = float(fp16_cutoff_threshold)

    def should_use_fp16(self, cutoff: float) -> bool:
        """cutoff이 임계값 이하면 FP16 거리 계산이 안전합니다.

        FP16의 정밀도 한계(~0.001 at magnitude ~50)로 인해
        너무 큰 cutoff에서는 FP32를 유지합니다.
        """
        return self.use_fp16_distance and cutoff <= self.fp16_cutoff_threshold

    @staticmethod
    def compute_dist_sq_fp16(
        coords_atom: torch.Tensor,
        coords_candidates: torch.Tensor,
        box: torch.Tensor,
    ) -> torch.Tensor:
        """FP16으로 거리 제곱 계산 후 FP32로 반환.

        Args:
            coords_atom: [1, 3] 또는 [3]
            coords_candidates: [M, 3]
            box: [3]

        Returns:
            dist_sq: [M] (FP32)
        """
        atom_h = coords_atom.half()
        cand_h = coords_candidates.half()
        box_h = box.half()

        dr = atom_h.unsqueeze(0) - cand_h if atom_h.ndim == 1 else atom_h - cand_h
        dr = dr - box_h * torch.round(dr / box_h)
        r2 = (dr * dr).sum(dim=-1)
        return r2.float()
