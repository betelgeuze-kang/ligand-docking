from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Protocol

import numpy as np

COULOMB_KE_KCAL_A = 332.06371


class BeadKind(IntEnum):
    PROTEIN_CA = 1
    PROTEIN_SC = 2
    PROTEIN_HB_DONOR = 3
    PROTEIN_HB_ACCEPTOR = 4
    LIGAND_ANCHOR = 10
    LIGAND_POLAR = 11
    LIGAND_HYDROPHOBE = 12
    LIGAND_AROMATIC = 13
    LIGAND_CHARGED = 14
    WATER_SITE = 20
    METAL_SITE = 30


FEATURE_DONOR = 1 << 0
FEATURE_ACCEPTOR = 1 << 1
FEATURE_HYDROPHOBE = 1 << 2
FEATURE_AROMATIC = 1 << 3
FEATURE_CATION = 1 << 4
FEATURE_ANION = 1 << 5
FEATURE_METAL = 1 << 6
FEATURE_HALOGEN = 1 << 7
FEATURE_BACKBONE = 1 << 8
FEATURE_SIDECHAIN = 1 << 9


def _as_array(value: Any, *, dtype: Any, name: str, shape: tuple[int | None, ...]) -> np.ndarray:
    arr = np.asarray(value, dtype=dtype)
    if arr.ndim != len(shape):
        raise ValueError(f"{name} must have rank {len(shape)}")
    for observed, expected in zip(arr.shape, shape):
        if expected is not None and observed != expected:
            raise ValueError(f"{name} shape mismatch: expected {shape}, observed {arr.shape}")
    return arr


@dataclass
class CoarseState:
    """Structure-of-arrays state for the reference coarse dynamics oracle."""

    x: np.ndarray
    v: np.ndarray
    mass: np.ndarray
    charge: np.ndarray
    radius: np.ndarray
    epsilon: np.ndarray
    bead_type: np.ndarray
    feature: np.ndarray
    mol_id: np.ndarray
    fixed: np.ndarray

    def __post_init__(self) -> None:
        x = _as_array(self.x, dtype=np.float32, name="x", shape=(None, 3))
        n = int(x.shape[0])
        if n <= 0:
            raise ValueError("CoarseState requires at least one bead")
        self.x = x
        self.v = _as_array(self.v, dtype=np.float32, name="v", shape=(n, 3))
        self.mass = _as_array(self.mass, dtype=np.float32, name="mass", shape=(n,))
        self.charge = _as_array(self.charge, dtype=np.float32, name="charge", shape=(n,))
        self.radius = _as_array(self.radius, dtype=np.float32, name="radius", shape=(n,))
        self.epsilon = _as_array(self.epsilon, dtype=np.float32, name="epsilon", shape=(n,))
        self.bead_type = _as_array(self.bead_type, dtype=np.int32, name="bead_type", shape=(n,))
        self.feature = _as_array(self.feature, dtype=np.int32, name="feature", shape=(n,))
        self.mol_id = _as_array(self.mol_id, dtype=np.int32, name="mol_id", shape=(n,))
        self.fixed = _as_array(self.fixed, dtype=bool, name="fixed", shape=(n,))
        if not np.all(np.isfinite(self.x)):
            raise ValueError("x contains non-finite coordinates")
        if not np.all(self.mass > 0.0):
            raise ValueError("mass values must be positive")
        if not np.all(self.radius > 0.0):
            raise ValueError("radius values must be positive")
        if not np.all(self.epsilon >= 0.0):
            raise ValueError("epsilon values must be non-negative")

    def copy(self) -> "CoarseState":
        return CoarseState(
            x=self.x.copy(),
            v=self.v.copy(),
            mass=self.mass.copy(),
            charge=self.charge.copy(),
            radius=self.radius.copy(),
            epsilon=self.epsilon.copy(),
            bead_type=self.bead_type.copy(),
            feature=self.feature.copy(),
            mol_id=self.mol_id.copy(),
            fixed=self.fixed.copy(),
        )

    def with_positions(self, x: np.ndarray) -> "CoarseState":
        out = self.copy()
        out.x = _as_array(x, dtype=np.float32, name="x", shape=self.x.shape)
        return out


@dataclass
class NeighborList:
    pair_i: np.ndarray
    pair_j: np.ndarray
    cutoff: float
    skin: float
    ref_x: np.ndarray


@dataclass
class PairMask:
    nonbonded: np.ndarray
    electrostatic: np.ndarray
    hbond_candidate: np.ndarray
    hydrophobic_candidate: np.ndarray
    clash_candidate: np.ndarray


@dataclass
class EnergyResult:
    energy: float
    forces: np.ndarray
    breakdown: dict[str, Any] = field(default_factory=dict)


class NeighborListBuilder:
    """Uniform cell-list neighbor candidate builder for bounded-density systems."""

    def __init__(self, cutoff: float, skin: float = 2.0):
        if cutoff <= 0.0:
            raise ValueError("cutoff must be positive")
        if skin < 0.0:
            raise ValueError("skin must be non-negative")
        self.cutoff = float(cutoff)
        self.skin = float(skin)
        self.list_cutoff = self.cutoff + self.skin
        self.cached: NeighborList | None = None

    def needs_rebuild(self, x: np.ndarray) -> bool:
        if self.cached is None:
            return True
        coords = np.asarray(x, dtype=np.float32)
        if coords.shape != self.cached.ref_x.shape:
            return True
        disp = np.linalg.norm(coords - self.cached.ref_x, axis=1)
        return bool(np.max(disp) > 0.5 * self.skin)

    def build(self, x: np.ndarray) -> NeighborList:
        coords = _as_array(x, dtype=np.float32, name="x", shape=(None, 3))
        cell_size = max(self.list_cutoff, 1e-6)
        min_corner = coords.min(axis=0) - 1e-3
        cell = np.floor((coords - min_corner) / cell_size).astype(np.int32)

        buckets: dict[tuple[int, int, int], list[int]] = {}
        for idx, c in enumerate(cell):
            buckets.setdefault(tuple(int(v) for v in c), []).append(idx)

        pair_i: list[int] = []
        pair_j: list[int] = []
        offsets = [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)]
        r2_cut = self.list_cutoff * self.list_cutoff
        for key, ids in buckets.items():
            for off in offsets:
                neighbor_key = (key[0] + off[0], key[1] + off[1], key[2] + off[2])
                if neighbor_key not in buckets:
                    continue
                for i in ids:
                    for j in buckets[neighbor_key]:
                        if j <= i:
                            continue
                        d = coords[i] - coords[j]
                        if float(np.dot(d, d)) <= r2_cut:
                            pair_i.append(i)
                            pair_j.append(j)

        nbl = NeighborList(
            pair_i=np.asarray(pair_i, dtype=np.int32),
            pair_j=np.asarray(pair_j, dtype=np.int32),
            cutoff=self.cutoff,
            skin=self.skin,
            ref_x=coords.copy(),
        )
        self.cached = nbl
        return nbl


def build_bruteforce_neighbor_list(
    x: np.ndarray,
    *,
    cutoff: float | None = None,
    skin: float = 0.0,
) -> NeighborList:
    """Build a simple O(N^2) pair list for reference parity checks."""

    coords = _as_array(x, dtype=np.float32, name="x", shape=(None, 3))
    if cutoff is not None and cutoff <= 0.0:
        raise ValueError("cutoff must be positive")
    if skin < 0.0:
        raise ValueError("skin must be non-negative")
    list_cutoff = np.inf if cutoff is None else float(cutoff) + float(skin)
    r2_cut = list_cutoff * list_cutoff
    pair_i: list[int] = []
    pair_j: list[int] = []
    for i in range(coords.shape[0]):
        for j in range(i + 1, coords.shape[0]):
            d = coords[i] - coords[j]
            if float(np.dot(d, d)) <= r2_cut:
                pair_i.append(i)
                pair_j.append(j)
    return NeighborList(
        pair_i=np.asarray(pair_i, dtype=np.int32),
        pair_j=np.asarray(pair_j, dtype=np.int32),
        cutoff=float("inf") if cutoff is None else float(cutoff),
        skin=float(skin),
        ref_x=coords.copy(),
    )


class PairMaskBuilder:
    def build(self, state: CoarseState, neighbors: NeighborList) -> PairMask:
        i = neighbors.pair_i
        j = neighbors.pair_j
        fi = state.feature[i]
        fj = state.feature[j]
        nonbonded = np.ones(len(i), dtype=bool)
        electrostatic = np.abs(state.charge[i] * state.charge[j]) > 1e-6
        hbond_candidate = (((fi & FEATURE_DONOR) != 0) & ((fj & FEATURE_ACCEPTOR) != 0)) | (
            ((fj & FEATURE_DONOR) != 0) & ((fi & FEATURE_ACCEPTOR) != 0)
        )
        hydrophobic_candidate = ((fi & FEATURE_HYDROPHOBE) != 0) & ((fj & FEATURE_HYDROPHOBE) != 0)
        return PairMask(
            nonbonded=nonbonded,
            electrostatic=electrostatic,
            hbond_candidate=hbond_candidate,
            hydrophobic_candidate=hydrophobic_candidate,
            clash_candidate=nonbonded.copy(),
        )


class ForceTerm(Protocol):
    name: str

    def compute(self, state: CoarseState, neighbors: NeighborList, mask: PairMask) -> EnergyResult:
        ...


def _pair_geometry(state: CoarseState, neighbors: NeighborList) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    i = neighbors.pair_i
    j = neighbors.pair_j
    dx = state.x[i] - state.x[j]
    r = np.linalg.norm(dx, axis=1).clip(1e-6, None)
    unit = dx / r[:, None]
    return dx, r, unit


def _scatter_pair_forces(n: int, i: np.ndarray, j: np.ndarray, fij: np.ndarray) -> np.ndarray:
    forces = np.zeros((n, 3), dtype=np.float32)
    np.add.at(forces, i, fij.astype(np.float32))
    np.add.at(forces, j, -fij.astype(np.float32))
    return forces


def smooth_switch(r: np.ndarray, r_switch: float, r_cut: float) -> np.ndarray:
    x = np.clip((r - r_switch) / max(r_cut - r_switch, 1e-6), 0.0, 1.0)
    return 1.0 - 6.0 * x**5 + 15.0 * x**4 - 10.0 * x**3


def smooth_switch_derivative(r: np.ndarray, r_switch: float, r_cut: float) -> np.ndarray:
    width = max(r_cut - r_switch, 1e-6)
    x = np.clip((r - r_switch) / width, 0.0, 1.0)
    return (-30.0 * x**4 + 60.0 * x**3 - 30.0 * x**2) / width


class SoftcoreContactTerm:
    name = "softcore_contact"

    def __init__(self, alpha: float = 0.5, tau: float = 0.35, r_switch: float = 8.0, r_cut: float = 10.0):
        self.alpha = float(alpha)
        self.tau = float(tau)
        self.r_switch = float(r_switch)
        self.r_cut = float(r_cut)

    def compute(self, state: CoarseState, neighbors: NeighborList, mask: PairMask) -> EnergyResult:
        i = neighbors.pair_i
        j = neighbors.pair_j
        _, r, unit = _pair_geometry(state, neighbors)
        m = mask.nonbonded
        sigma = state.radius[i] + state.radius[j]
        eps_rep = np.sqrt(np.maximum(state.epsilon[i] * state.epsilon[j], 1e-8))
        eps_attr = 0.25 * eps_rep
        r_contact = sigma + 0.5
        r_eff = np.sqrt(r * r + self.alpha * self.alpha)
        rep = eps_rep * (sigma / r_eff) ** 12
        s = 1.0 / (1.0 + np.exp((r - r_contact) / self.tau))
        attr = -eps_attr * s
        switch = smooth_switch(r, self.r_switch, self.r_cut)
        base = rep + attr
        e_pair = base * switch * m

        drep = rep * (-12.0) * r / np.maximum(r_eff * r_eff, 1e-6)
        dattr = eps_attr / self.tau * s * (1.0 - s)
        dEdr = (
            (drep + dattr) * switch
            + base * smooth_switch_derivative(r, self.r_switch, self.r_cut)
        ) * m
        fij = -dEdr[:, None] * unit
        return EnergyResult(
            energy=float(np.sum(e_pair)),
            forces=_scatter_pair_forces(state.x.shape[0], i, j, fij),
            breakdown={"pair_count": int(np.sum(m))},
        )


class ScreenedElectrostaticTerm:
    name = "screened_electrostatic"

    def __init__(self, epsilon_r: float = 20.0, kappa: float = 0.15, r_switch: float = 10.0, r_cut: float = 12.0):
        self.epsilon_r = float(epsilon_r)
        self.kappa = float(kappa)
        self.r_switch = float(r_switch)
        self.r_cut = float(r_cut)

    def compute(self, state: CoarseState, neighbors: NeighborList, mask: PairMask) -> EnergyResult:
        i = neighbors.pair_i
        j = neighbors.pair_j
        _, r, unit = _pair_geometry(state, neighbors)
        m = mask.electrostatic
        qiqj = state.charge[i] * state.charge[j]
        pref = COULOMB_KE_KCAL_A * qiqj / self.epsilon_r
        expkr = np.exp(-self.kappa * r)
        switch = smooth_switch(r, self.r_switch, self.r_cut)
        base = pref * expkr / r
        e_pair = base * switch * m
        dbase = pref * expkr * (-self.kappa / r - 1.0 / (r * r))
        dEdr = (
            dbase * switch
            + base * smooth_switch_derivative(r, self.r_switch, self.r_cut)
        ) * m
        fij = -dEdr[:, None] * unit
        return EnergyResult(
            energy=float(np.sum(e_pair)),
            forces=_scatter_pair_forces(state.x.shape[0], i, j, fij),
            breakdown={"pair_count": int(np.sum(m))},
        )


class DirectionalHbondTerm:
    name = "directional_hbond_proxy"

    def __init__(self, eps: float = 1.5, r0: float = 2.9, sigma: float = 0.35):
        self.eps = float(eps)
        self.r0 = float(r0)
        self.sigma = float(sigma)

    def compute(self, state: CoarseState, neighbors: NeighborList, mask: PairMask) -> EnergyResult:
        i = neighbors.pair_i
        j = neighbors.pair_j
        _, r, unit = _pair_geometry(state, neighbors)
        m = mask.hbond_candidate
        z = (r - self.r0) / self.sigma
        score = np.exp(-0.5 * z * z)
        e_pair = -self.eps * score * m
        dscore = score * (-(r - self.r0) / (self.sigma * self.sigma))
        dEdr = -self.eps * dscore * m
        fij = -dEdr[:, None] * unit
        return EnergyResult(
            energy=float(np.sum(e_pair)),
            forces=_scatter_pair_forces(state.x.shape[0], i, j, fij),
            breakdown={"hbond_pair_count": int(np.sum(m))},
        )


class HydrophobicContactTerm:
    name = "hydrophobic_contact"

    def __init__(self, eps: float = 0.35, r_contact: float = 4.2, tau: float = 0.5):
        self.eps = float(eps)
        self.r_contact = float(r_contact)
        self.tau = float(tau)

    def compute(self, state: CoarseState, neighbors: NeighborList, mask: PairMask) -> EnergyResult:
        i = neighbors.pair_i
        j = neighbors.pair_j
        _, r, unit = _pair_geometry(state, neighbors)
        m = mask.hydrophobic_candidate
        s = 1.0 / (1.0 + np.exp((r - self.r_contact) / self.tau))
        e_pair = -self.eps * s * m
        dEdr = self.eps / self.tau * s * (1.0 - s) * m
        fij = -dEdr[:, None] * unit
        return EnergyResult(
            energy=float(np.sum(e_pair)),
            forces=_scatter_pair_forces(state.x.shape[0], i, j, fij),
            breakdown={"hydrophobic_pair_count": int(np.sum(m))},
        )


class PocketWallTerm:
    name = "pocket_wall"

    def __init__(self, pocket_center: np.ndarray, pocket_radius: float, ligand_mol_id: int, k_wall: float = 0.2):
        self.center = np.asarray(pocket_center, dtype=np.float32)
        if self.center.shape != (3,):
            raise ValueError("pocket_center must be length 3")
        self.radius = float(pocket_radius)
        self.ligand_mol_id = int(ligand_mol_id)
        self.k_wall = float(k_wall)

    def compute(self, state: CoarseState, neighbors: NeighborList, mask: PairMask) -> EnergyResult:
        del neighbors, mask
        idx = np.where(state.mol_id == self.ligand_mol_id)[0]
        forces = np.zeros_like(state.x, dtype=np.float32)
        if len(idx) == 0:
            return EnergyResult(0.0, forces, {"status": "no_ligand_beads"})
        centroid = state.x[idx].mean(axis=0)
        dvec = centroid - self.center
        distance = float(np.linalg.norm(dvec))
        excess = max(0.0, distance - self.radius)
        if excess <= 0.0 or distance <= 1e-6:
            return EnergyResult(0.0, forces, {"escape": False, "distance": distance})
        energy = 0.5 * self.k_wall * excess * excess
        f_centroid = -self.k_wall * excess * dvec / distance
        forces[idx] += (f_centroid / float(len(idx))).astype(np.float32)
        return EnergyResult(float(energy), forces, {"escape": True, "distance": distance})


class CoarseForceField:
    def __init__(
        self,
        terms: list[ForceTerm],
        pair_mask_builder: PairMaskBuilder | None = None,
        force_clip: float = 500.0,
    ):
        self.terms = list(terms)
        self.pair_mask_builder = pair_mask_builder or PairMaskBuilder()
        self.force_clip = float(force_clip)

    def compute(self, state: CoarseState, neighbors: NeighborList) -> EnergyResult:
        mask = self.pair_mask_builder.build(state, neighbors)
        total_energy = 0.0
        total_forces = np.zeros_like(state.x, dtype=np.float32)
        breakdown: dict[str, Any] = {}
        for term in self.terms:
            result = term.compute(state, neighbors, mask)
            total_energy += float(result.energy)
            total_forces += result.forces.astype(np.float32)
            breakdown[term.name] = {"energy": float(result.energy), **result.breakdown}

        total_forces = np.nan_to_num(total_forces, nan=0.0, posinf=0.0, neginf=0.0)
        norm = np.linalg.norm(total_forces, axis=1).clip(1e-6, None)
        scale = np.minimum(1.0, self.force_clip / norm)
        total_forces *= scale[:, None]
        total_forces[state.fixed] = 0.0
        return EnergyResult(total_energy, total_forces, breakdown)


@dataclass
class IntegratorConfig:
    dt_ps: float = 0.002
    max_steps: int = 1000
    save_every: int = 20
    damping: float = 0.98


@dataclass
class TrajectoryFrame:
    step: int
    x: np.ndarray
    energy: float
    breakdown: dict[str, Any]


@dataclass
class Trajectory:
    frames: list[TrajectoryFrame]


def _frame_min_distance(frame_x: np.ndarray, state: CoarseState, ligand_mol_id: int) -> float:
    ligand_idx = np.where(state.mol_id == int(ligand_mol_id))[0]
    other_idx = np.where(state.mol_id != int(ligand_mol_id))[0]
    if len(ligand_idx) == 0 or len(other_idx) == 0:
        return 0.0
    ligand_x = frame_x[ligand_idx]
    other_x = frame_x[other_idx]
    distances = np.linalg.norm(ligand_x[:, None, :] - other_x[None, :, :], axis=2)
    return float(np.min(distances))


def _frame_has_clash(
    frame_x: np.ndarray,
    state: CoarseState,
    ligand_mol_id: int,
    clash_scale: float,
) -> bool:
    ligand_idx = np.where(state.mol_id == int(ligand_mol_id))[0]
    other_idx = np.where(state.mol_id != int(ligand_mol_id))[0]
    if len(ligand_idx) == 0 or len(other_idx) == 0:
        return False
    ligand_x = frame_x[ligand_idx]
    other_x = frame_x[other_idx]
    distances = np.linalg.norm(ligand_x[:, None, :] - other_x[None, :, :], axis=2)
    thresholds = clash_scale * (state.radius[ligand_idx][:, None] + state.radius[other_idx][None, :])
    return bool(np.any(distances < thresholds))


def summarize_trajectory(
    trajectory: Trajectory,
    state: CoarseState,
    *,
    ligand_mol_id: int = 1,
    clash_scale: float = 0.75,
) -> Any:
    from betelgeuze_ai_md.contracts import TrajectorySummary

    frames = list(trajectory.frames)
    if not frames:
        return TrajectorySummary(frame_count=0)
    energy_trace = [float(frame.energy) for frame in frames]
    contact_trace = []
    escape_count = 0
    min_distances = []
    clash_count = 0
    for frame in frames:
        hbond_count = float(frame.breakdown.get("directional_hbond_proxy", {}).get("hbond_pair_count", 0))
        hydrophobic_count = float(frame.breakdown.get("hydrophobic_contact", {}).get("hydrophobic_pair_count", 0))
        contact_trace.append(hbond_count + hydrophobic_count)
        escape_count += int(bool(frame.breakdown.get("pocket_wall", {}).get("escape", False)))
        min_distances.append(_frame_min_distance(frame.x, state, ligand_mol_id))
        clash_count += int(_frame_has_clash(frame.x, state, ligand_mol_id, float(clash_scale)))
    energy_std = float(np.std(np.asarray(energy_trace, dtype=np.float64)))
    stability_score = 1.0 / (1.0 + energy_std)
    return TrajectorySummary(
        frame_count=len(frames),
        energy_trace=energy_trace,
        contact_trace=contact_trace,
        stability_score=float(np.clip(stability_score, 0.0, 1.0)),
        mean_min_distance=float(np.mean(min_distances)) if min_distances else 0.0,
        escape_fraction=float(escape_count / len(frames)),
        clash_fraction=float(clash_count / len(frames)),
    )


class DampedVelocityVerletIntegrator:
    def step(self, state: CoarseState, forces: np.ndarray, config: IntegratorConfig) -> CoarseState:
        out = state.copy()
        dt = float(config.dt_ps)
        inv_m = 1.0 / np.maximum(out.mass, 1e-6)
        accel = forces * inv_m[:, None]
        out.v = (out.v + dt * accel).astype(np.float32)
        out.v *= float(config.damping)
        out.v[out.fixed] = 0.0
        out.x = (out.x + dt * out.v).astype(np.float32)
        return out


class DynamicsEngine:
    def __init__(
        self,
        forcefield: CoarseForceField,
        neighbor_builder: NeighborListBuilder,
        integrator: DampedVelocityVerletIntegrator | None = None,
    ):
        self.forcefield = forcefield
        self.neighbor_builder = neighbor_builder
        self.integrator = integrator or DampedVelocityVerletIntegrator()

    def run(self, state: CoarseState, config: IntegratorConfig) -> Trajectory:
        frames: list[TrajectoryFrame] = []
        current = state.copy()
        neighbors = self.neighbor_builder.build(current.x)
        for step in range(int(config.max_steps)):
            if self.neighbor_builder.needs_rebuild(current.x):
                neighbors = self.neighbor_builder.build(current.x)
            result = self.forcefield.compute(current, neighbors)
            if not np.isfinite(result.energy) or not np.isfinite(result.forces).all():
                raise FloatingPointError("non-finite energy or force")
            if step % int(config.save_every) == 0:
                frames.append(
                    TrajectoryFrame(
                        step=step,
                        x=current.x.copy(),
                        energy=result.energy,
                        breakdown=result.breakdown,
                    )
                )
            current = self.integrator.step(current, result.forces, config)
            if not np.isfinite(current.x).all():
                raise FloatingPointError("non-finite coordinate")
        return Trajectory(frames=frames)


def kabsch(mobile: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mobile_arr = np.asarray(mobile, dtype=np.float64)
    target_arr = np.asarray(target, dtype=np.float64)
    if mobile_arr.shape != target_arr.shape or mobile_arr.ndim != 2 or mobile_arr.shape[1] != 3:
        raise ValueError("mobile and target must both be [N,3]")
    mobile_centered = mobile_arr - mobile_arr.mean(axis=0, keepdims=True)
    target_centered = target_arr - target_arr.mean(axis=0, keepdims=True)
    h = mobile_centered.T @ target_centered
    u, _, vt = np.linalg.svd(h)
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) < 0.0:
        vt[-1, :] *= -1.0
        rotation = vt.T @ u.T
    translation = target_arr.mean(axis=0) - rotation @ mobile_arr.mean(axis=0)
    return rotation.astype(np.float32), translation.astype(np.float32)


def finite_difference_force(energy_fn: Any, x: np.ndarray, h: float = 1e-4) -> np.ndarray:
    coords = np.asarray(x, dtype=np.float64)
    forces = np.zeros_like(coords, dtype=np.float64)
    for i in range(coords.shape[0]):
        for k in range(3):
            xp = coords.copy()
            xm = coords.copy()
            xp[i, k] += h
            xm[i, k] -= h
            forces[i, k] = -(float(energy_fn(xp)) - float(energy_fn(xm))) / (2.0 * h)
    return forces.astype(np.float32)
