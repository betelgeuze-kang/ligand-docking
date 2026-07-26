"""Bounded receptor-steric-field translation guidance for docking proposals.

This module is intentionally claim-closed.  It uses fixed diagnostic element
radii and a deterministic pocket lattice to reduce obvious receptor overlap;
it is not an interaction-energy grid, docking score, or validated sampler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from numbers import Integral, Real

import torch

from betelgeuze_engine_v2.molecular import canonical_system_sha256

from .geometric_scoring import (
    GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM,
    GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256,
)
from .identity import coordinate_fingerprint
from .problem import DockingProblemInput
from .proposals import (
    DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID,
    DockingTranslationPlacementReceipt,
)


STERIC_FIELD_PLACEMENT_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_steric_field_placement_config/1.0.0"
)
STERIC_FIELD_PLACEMENT_PLAN_SCHEMA_ID = (
    "betelgeuze.engine_v2_steric_field_placement_plan/1.0.0"
)
STERIC_FIELD_SITE_SCHEMA_ID = (
    "betelgeuze.engine_v2_steric_field_translation_site/1.0.0"
)

MAX_STERIC_FIELD_GRID_POINTS = 100_000
MAX_STERIC_FIELD_RETAINED_SITES = 256
MAX_STERIC_FIELD_RECEPTOR_ATOMS = 8_192
MAX_STERIC_FIELD_ANCHOR_PAIRS = 8_000_000
MAX_STERIC_FIELD_POSE_PAIRS_PER_PROPOSAL = 8_000_000
MAX_STERIC_FIELD_PAIR_CHUNK = 262_144

STERIC_FIELD_PLACEMENT_BLOCKERS = (
    "steric_field_fixed_radii_not_calibrated",
    "steric_field_guidance_not_scientifically_validated",
    "steric_field_omits_electrostatics_hydrogen_bonding_and_desolvation",
    "steric_field_uses_rigid_receptor_without_water_or_cofactor_response",
)


class StericFieldPlacementError(ValueError):
    """A steric-field placement request is invalid or exceeds a hard bound."""


def _canonical_sha256(value: object) -> str:
    try:
        raw = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise StericFieldPlacementError(
            "steric-field identity is not canonical JSON"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def _finite(
    value: object,
    *,
    name: str,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise StericFieldPlacementError(f"{name} must be a real number")
    number = float(value)
    if not math.isfinite(number):
        raise StericFieldPlacementError(f"{name} must be finite")
    if positive and number <= 0.0:
        raise StericFieldPlacementError(f"{name} must be positive")
    if nonnegative and number < 0.0:
        raise StericFieldPlacementError(f"{name} must be non-negative")
    return number


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise StericFieldPlacementError(f"{name} must be an integer")
    number = int(value)
    if not minimum <= number <= maximum:
        raise StericFieldPlacementError(
            f"{name} must be in [{minimum}, {maximum}]"
        )
    return number


def _frozen_cpu_float64(value: torch.Tensor, *, name: str) -> torch.Tensor:
    if (
        not isinstance(value, torch.Tensor)
        or not value.is_floating_point()
        or value.device.type != "cpu"
        or value.dtype != torch.float64
        or not bool(torch.isfinite(value).all().item())
    ):
        raise StericFieldPlacementError(
            f"{name} must be a finite CPU float64 tensor"
        )
    return value.detach().clone().contiguous().requires_grad_(False)


def _tensor_payload(value: torch.Tensor) -> dict[str, object]:
    flattened = value.detach().to(dtype=torch.float64, device="cpu").reshape(-1)
    return {
        "shape": [int(size) for size in value.shape],
        "values_hex": [float(item).hex() for item in flattened.tolist()],
    }


def _tensor_sha256(value: torch.Tensor) -> str:
    return _canonical_sha256(_tensor_payload(value))


@dataclass(frozen=True, slots=True)
class StericFieldPlacementConfig:
    translation_radius_angstrom: float
    grid_spacing_angstrom: float = 1.5
    receptor_shell_padding_angstrom: float = 8.0
    overlap_scale: float = 0.82
    deep_overlap_scale: float = 0.58
    anchor_probe_radius_angstrom: float = 1.5
    maximum_site_count: int = 64
    site_cycle_depth: int = 8
    max_grid_point_count: int = MAX_STERIC_FIELD_GRID_POINTS
    max_receptor_shell_atoms: int = MAX_STERIC_FIELD_RECEPTOR_ATOMS
    max_anchor_pairs: int = MAX_STERIC_FIELD_ANCHOR_PAIRS
    max_pose_pairs_per_proposal: int = (
        MAX_STERIC_FIELD_POSE_PAIRS_PER_PROPOSAL
    )
    max_pair_chunk: int = MAX_STERIC_FIELD_PAIR_CHUNK
    schema_id: str = STERIC_FIELD_PLACEMENT_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != STERIC_FIELD_PLACEMENT_CONFIG_SCHEMA_ID:
            raise StericFieldPlacementError(
                "unsupported steric-field placement config schema"
            )
        for name, positive, nonnegative in (
            ("translation_radius_angstrom", False, True),
            ("grid_spacing_angstrom", True, False),
            ("receptor_shell_padding_angstrom", True, False),
            ("anchor_probe_radius_angstrom", True, False),
        ):
            object.__setattr__(
                self,
                name,
                _finite(
                    getattr(self, name),
                    name=name,
                    positive=positive,
                    nonnegative=nonnegative,
                ),
            )
        for name in ("overlap_scale", "deep_overlap_scale"):
            number = _finite(getattr(self, name), name=name, positive=True)
            if number >= 1.0:
                raise StericFieldPlacementError(f"{name} must be less than one")
            object.__setattr__(self, name, number)
        if self.deep_overlap_scale >= self.overlap_scale:
            raise StericFieldPlacementError(
                "deep_overlap_scale must be smaller than overlap_scale"
            )
        object.__setattr__(
            self,
            "maximum_site_count",
            _exact_int(
                self.maximum_site_count,
                name="maximum_site_count",
                minimum=1,
                maximum=MAX_STERIC_FIELD_RETAINED_SITES,
            ),
        )
        object.__setattr__(
            self,
            "site_cycle_depth",
            _exact_int(
                self.site_cycle_depth,
                name="site_cycle_depth",
                minimum=1,
                maximum=self.maximum_site_count,
            ),
        )
        for name, maximum in (
            ("max_grid_point_count", MAX_STERIC_FIELD_GRID_POINTS),
            ("max_receptor_shell_atoms", MAX_STERIC_FIELD_RECEPTOR_ATOMS),
            ("max_anchor_pairs", MAX_STERIC_FIELD_ANCHOR_PAIRS),
            (
                "max_pose_pairs_per_proposal",
                MAX_STERIC_FIELD_POSE_PAIRS_PER_PROPOSAL,
            ),
            ("max_pair_chunk", MAX_STERIC_FIELD_PAIR_CHUNK),
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(
                    getattr(self, name),
                    name=name,
                    minimum=1,
                    maximum=maximum,
                ),
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "translation_radius_angstrom_hex": (
                self.translation_radius_angstrom.hex()
            ),
            "grid_spacing_angstrom_hex": self.grid_spacing_angstrom.hex(),
            "receptor_shell_padding_angstrom_hex": (
                self.receptor_shell_padding_angstrom.hex()
            ),
            "overlap_scale_hex": self.overlap_scale.hex(),
            "deep_overlap_scale_hex": self.deep_overlap_scale.hex(),
            "anchor_probe_radius_angstrom_hex": (
                self.anchor_probe_radius_angstrom.hex()
            ),
            "maximum_site_count": self.maximum_site_count,
            "site_cycle_depth": self.site_cycle_depth,
            "max_grid_point_count": self.max_grid_point_count,
            "max_receptor_shell_atoms": self.max_receptor_shell_atoms,
            "max_anchor_pairs": self.max_anchor_pairs,
            "max_pose_pairs_per_proposal": (
                self.max_pose_pairs_per_proposal
            ),
            "max_pair_chunk": self.max_pair_chunk,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class StericFieldPlacementPlan:
    """Immutable receptor field and retained translation-site lattice."""

    problem_fingerprint_sha256: str
    search_space_fingerprint_sha256: str
    problem_input_fingerprint_sha256: str
    receptor_system_sha256: str
    ligand_system_sha256: str
    pocket_definition_sha256: str
    receptor_coordinates: torch.Tensor
    receptor_radii: torch.Tensor
    ligand_radii: torch.Tensor
    pocket_center: torch.Tensor
    pocket_radius_angstrom: float
    site_translations: torch.Tensor
    site_ids: tuple[str, ...]
    site_anchor_overlap_counts: tuple[int, ...]
    site_anchor_penalties: tuple[float, ...]
    source_grid_point_count: int
    config: StericFieldPlacementConfig
    placement_policy_id: str = (
        DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID
    )
    blockers: tuple[str, ...] = STERIC_FIELD_PLACEMENT_BLOCKERS
    schema_id: str = STERIC_FIELD_PLACEMENT_PLAN_SCHEMA_ID
    _frozen_fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != STERIC_FIELD_PLACEMENT_PLAN_SCHEMA_ID:
            raise StericFieldPlacementError(
                "unsupported steric-field placement plan schema"
            )
        if not isinstance(self.config, StericFieldPlacementConfig):
            raise TypeError("config must be StericFieldPlacementConfig")
        for name in (
            "problem_fingerprint_sha256",
            "search_space_fingerprint_sha256",
            "problem_input_fingerprint_sha256",
            "receptor_system_sha256",
            "ligand_system_sha256",
            "pocket_definition_sha256",
        ):
            digest = str(getattr(self, name) or "")
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise StericFieldPlacementError(
                    f"{name} must be a lowercase SHA-256"
                )
            object.__setattr__(self, name, digest)
        if (
            self.placement_policy_id
            != DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID
        ):
            raise StericFieldPlacementError(
                "unsupported steric-field placement policy"
            )
        receptor = _frozen_cpu_float64(
            self.receptor_coordinates,
            name="receptor_coordinates",
        )
        receptor_radii = _frozen_cpu_float64(
            self.receptor_radii,
            name="receptor_radii",
        )
        ligand_radii = _frozen_cpu_float64(
            self.ligand_radii,
            name="ligand_radii",
        )
        pocket_center = _frozen_cpu_float64(
            self.pocket_center,
            name="pocket_center",
        )
        pocket_radius = _finite(
            self.pocket_radius_angstrom,
            name="pocket_radius_angstrom",
            positive=True,
        )
        sites = _frozen_cpu_float64(
            self.site_translations,
            name="site_translations",
        )
        if receptor.ndim != 2 or receptor.shape[1] != 3:
            raise StericFieldPlacementError(
                "receptor_coordinates must have shape [R,3]"
            )
        if receptor_radii.shape != (int(receptor.shape[0]),):
            raise StericFieldPlacementError(
                "receptor radii do not match receptor coordinates"
            )
        if ligand_radii.ndim != 1 or int(ligand_radii.numel()) < 1:
            raise StericFieldPlacementError("ligand_radii must have shape [L]")
        if pocket_center.shape != (3,):
            raise StericFieldPlacementError("pocket_center must have shape [3]")
        site_count = int(sites.shape[0]) if sites.ndim == 2 else -1
        if (
            site_count < 1
            or sites.shape != (site_count, 3)
            or site_count > self.config.maximum_site_count
        ):
            raise StericFieldPlacementError(
                "site_translations has invalid shape or exceeds capacity"
            )
        if bool(
            (
                torch.linalg.vector_norm(sites, dim=1)
                > self.config.translation_radius_angstrom + 1.0e-12
            ).any().item()
        ):
            raise StericFieldPlacementError(
                "steric-field site exceeds the translation radius"
            )
        site_ids = tuple(str(value or "").strip() for value in self.site_ids)
        anchor_counts = tuple(int(value) for value in self.site_anchor_overlap_counts)
        anchor_penalties = tuple(float(value) for value in self.site_anchor_penalties)
        if (
            len(site_ids) != site_count
            or len(set(site_ids)) != site_count
            or any(not value for value in site_ids)
            or len(anchor_counts) != site_count
            or any(value < 0 for value in anchor_counts)
            or len(anchor_penalties) != site_count
            or any(not math.isfinite(value) or value < 0.0 for value in anchor_penalties)
        ):
            raise StericFieldPlacementError(
                "steric-field site metadata is incomplete"
            )
        source_count = int(self.source_grid_point_count)
        if not site_count <= source_count <= self.config.max_grid_point_count:
            raise StericFieldPlacementError(
                "source grid point count is inconsistent"
            )
        blockers = tuple(str(value or "").strip() for value in self.blockers)
        if (
            not blockers
            or any(not value for value in blockers)
            or len(blockers) != len(set(blockers))
        ):
            raise StericFieldPlacementError(
                "steric-field blockers must be non-empty and unique"
            )
        if site_count * int(receptor.shape[0]) * int(ligand_radii.numel()) > (
            self.config.max_pose_pairs_per_proposal
        ):
            raise StericFieldPlacementError(
                "steric-field pose pair capacity exceeded"
            )
        object.__setattr__(self, "receptor_coordinates", receptor)
        object.__setattr__(self, "receptor_radii", receptor_radii)
        object.__setattr__(self, "ligand_radii", ligand_radii)
        object.__setattr__(self, "pocket_center", pocket_center)
        object.__setattr__(self, "pocket_radius_angstrom", pocket_radius)
        object.__setattr__(self, "site_translations", sites)
        object.__setattr__(self, "site_ids", site_ids)
        object.__setattr__(self, "site_anchor_overlap_counts", anchor_counts)
        object.__setattr__(self, "site_anchor_penalties", anchor_penalties)
        object.__setattr__(self, "source_grid_point_count", source_count)
        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(
            self,
            "_frozen_fingerprint_sha256",
            self._current_fingerprint_sha256(),
        )

    @property
    def retained_site_count(self) -> int:
        return int(self.site_translations.shape[0])

    @property
    def receptor_shell_atom_count(self) -> int:
        return int(self.receptor_coordinates.shape[0])

    @property
    def ligand_atom_count(self) -> int:
        return int(self.ligand_radii.shape[0])

    def _site_rows(self) -> list[dict[str, object]]:
        return [
            {
                "schema_id": STERIC_FIELD_SITE_SCHEMA_ID,
                "site_id": self.site_ids[index],
                "site_index": index,
                "translation_angstrom_hex": [
                    float(value).hex()
                    for value in self.site_translations[index].tolist()
                ],
                "anchor_overlap_pair_count": (
                    self.site_anchor_overlap_counts[index]
                ),
                "anchor_overlap_penalty_hex": (
                    self.site_anchor_penalties[index].hex()
                ),
            }
            for index in range(self.retained_site_count)
        ]

    def _payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "placement_policy_id": self.placement_policy_id,
            "problem_fingerprint_sha256": self.problem_fingerprint_sha256,
            "problem_input_fingerprint_sha256": (
                self.problem_input_fingerprint_sha256
            ),
            "search_space_fingerprint_sha256": (
                self.search_space_fingerprint_sha256
            ),
            "receptor_system_sha256": self.receptor_system_sha256,
            "ligand_system_sha256": self.ligand_system_sha256,
            "pocket_definition_sha256": self.pocket_definition_sha256,
            "receptor_shell_coordinate_sha256": coordinate_fingerprint(
                self.receptor_coordinates
            ),
            "receptor_radii_sha256": _tensor_sha256(self.receptor_radii),
            "ligand_radii_sha256": _tensor_sha256(self.ligand_radii),
            "pocket_center_angstrom_hex": [
                float(value).hex() for value in self.pocket_center.tolist()
            ],
            "pocket_radius_angstrom_hex": self.pocket_radius_angstrom.hex(),
            "radius_profile_sha256": (
                GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256
            ),
            "config": self.config.to_dict(),
            "config_sha256": self.config.fingerprint_sha256,
            "source_grid_point_count": self.source_grid_point_count,
            "retained_site_count": self.retained_site_count,
            "site_selection_order": (
                "anchor_overlap_count_then_penalty_then_center_distance_then_xyz"
            ),
            "pose_selection_order": (
                "deep_overlap_count_then_overlap_count_then_overlap_penalty_"
                "then_pocket_boundary_then_site_index"
            ),
            "candidate_zero_policy": "force_zero_translation_site",
            "later_candidate_policy": (
                "cycle_over_orientation_conditioned_top_nonzero_steric_sites"
            ),
            "sites": self._site_rows(),
            "scientifically_validated": False,
            "claim_safe": False,
            "blockers": list(self.blockers),
        }

    def _current_fingerprint_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    @property
    def fingerprint_sha256(self) -> str:
        self.assert_integrity()
        return self._frozen_fingerprint_sha256

    def assert_integrity(self) -> None:
        if self._current_fingerprint_sha256() != self._frozen_fingerprint_sha256:
            raise StericFieldPlacementError(
                "steric-field placement plan changed after construction"
            )

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "receipt_sha256": self.fingerprint_sha256}

    def place(
        self,
        oriented_coordinates: torch.Tensor,
        *,
        proposal_index: int,
        translation_radius_angstrom: float,
    ) -> DockingTranslationPlacementReceipt:
        self.assert_integrity()
        index = int(proposal_index)
        if index < 0:
            raise StericFieldPlacementError("proposal_index must be non-negative")
        radius = _finite(
            translation_radius_angstrom,
            name="translation_radius_angstrom",
            nonnegative=True,
        )
        if radius.hex() != self.config.translation_radius_angstrom.hex():
            raise StericFieldPlacementError(
                "translation radius does not match the steric-field plan"
            )
        coordinates = _frozen_cpu_float64(
            oriented_coordinates,
            name="oriented_coordinates",
        )
        if coordinates.shape != (self.ligand_atom_count, 3):
            raise StericFieldPlacementError(
                "oriented coordinates do not match the ligand atom count"
        )
        placed = coordinates.unsqueeze(0) + self.site_translations.unsqueeze(1)
        overlap_count_values: list[int] = []
        deep_count_values: list[int] = []
        overlap_penalty_values: list[float] = []
        minimum_separation_values: list[float] = []
        ligand_chunk_size = min(
            self.ligand_atom_count,
            self.config.max_pair_chunk,
        )
        for site_index in range(self.retained_site_count):
            overlap_count = 0
            deep_count = 0
            overlap_penalty = 0.0
            minimum_separation = math.inf
            for ligand_start in range(
                0,
                self.ligand_atom_count,
                ligand_chunk_size,
            ):
                ligand_stop = min(
                    ligand_start + ligand_chunk_size,
                    self.ligand_atom_count,
                )
                ligand_coordinates = placed[
                    site_index,
                    ligand_start:ligand_stop,
                ]
                ligand_radii = self.ligand_radii[ligand_start:ligand_stop]
                receptor_chunk_size = max(
                    1,
                    self.config.max_pair_chunk
                    // int(ligand_coordinates.shape[0]),
                )
                for receptor_start in range(
                    0,
                    self.receptor_shell_atom_count,
                    receptor_chunk_size,
                ):
                    receptor_stop = min(
                        receptor_start + receptor_chunk_size,
                        self.receptor_shell_atom_count,
                    )
                    receptor_coordinates = self.receptor_coordinates[
                        receptor_start:receptor_stop
                    ]
                    receptor_radii = self.receptor_radii[
                        receptor_start:receptor_stop
                    ]
                    delta = (
                        ligand_coordinates.unsqueeze(1)
                        - receptor_coordinates.unsqueeze(0)
                    )
                    distances = torch.linalg.vector_norm(delta, dim=2)
                    radius_sums = (
                        ligand_radii.unsqueeze(1)
                        + receptor_radii.unsqueeze(0)
                    )
                    overlap_thresholds = self.config.overlap_scale * radius_sums
                    deep_thresholds = self.config.deep_overlap_scale * radius_sums
                    penetrations = torch.clamp(
                        overlap_thresholds - distances,
                        min=0.0,
                    )
                    overlap_count += int(
                        (distances < overlap_thresholds).sum().item()
                    )
                    deep_count += int(
                        (distances < deep_thresholds).sum().item()
                    )
                    overlap_penalty += float(
                        (penetrations * penetrations).sum().item()
                    )
                    minimum_separation = min(
                        minimum_separation,
                        float((distances - radius_sums).amin().item()),
                    )
            overlap_count_values.append(overlap_count)
            deep_count_values.append(deep_count)
            overlap_penalty_values.append(overlap_penalty)
            minimum_separation_values.append(minimum_separation)
        overlap_counts = torch.tensor(overlap_count_values, dtype=torch.long)
        deep_counts = torch.tensor(deep_count_values, dtype=torch.long)
        overlap_penalties = torch.tensor(
            overlap_penalty_values,
            dtype=torch.float64,
        )
        minimum_separations = torch.tensor(
            minimum_separation_values,
            dtype=torch.float64,
        )
        pocket_distances = torch.linalg.vector_norm(
            placed - self.pocket_center.reshape(1, 1, 3),
            dim=2,
        )
        outside_depths = torch.clamp(
            pocket_distances - self.pocket_radius_angstrom,
            min=0.0,
        )
        outside_counts = (outside_depths > 0.0).sum(dim=1)
        boundary_penalties = (outside_depths * outside_depths).sum(dim=1)
        ranked_indices = sorted(
            range(self.retained_site_count),
            key=lambda site_index: (
                int(deep_counts[site_index].item()),
                int(overlap_counts[site_index].item()),
                float(overlap_penalties[site_index].item()),
                int(outside_counts[site_index].item()),
                float(boundary_penalties[site_index].item()),
                site_index,
            ),
        )
        if index == 0:
            zero_site_index = next(
                site_index
                for site_index in range(self.retained_site_count)
                if bool((self.site_translations[site_index] == 0.0).all().item())
            )
            selected_site_index = zero_site_index
            selected_rank = ranked_indices.index(zero_site_index)
        else:
            zero_site_indices = {
                site_index
                for site_index in range(self.retained_site_count)
                if bool((self.site_translations[site_index] == 0.0).all().item())
            }
            movable_ranked_indices = [
                site_index
                for site_index in ranked_indices
                if site_index not in zero_site_indices
            ]
            if not movable_ranked_indices:
                movable_ranked_indices = ranked_indices
            cycle_depth = min(
                self.config.site_cycle_depth,
                len(movable_ranked_indices),
            )
            cycle_rank = (index - 1) % cycle_depth
            selected_site_index = movable_ranked_indices[cycle_rank]
            selected_rank = ranked_indices.index(selected_site_index)
        translation = self.site_translations[selected_site_index]
        translation_values = translation.tolist()
        return DockingTranslationPlacementReceipt(
            proposal_index=index,
            placement_policy_id=self.placement_policy_id,
            placement_plan_sha256=self.fingerprint_sha256,
            problem_fingerprint_sha256=self.problem_fingerprint_sha256,
            search_space_fingerprint_sha256=self.search_space_fingerprint_sha256,
            site_id=self.site_ids[selected_site_index],
            site_index=selected_site_index,
            selected_rank=selected_rank,
            evaluated_site_count=self.retained_site_count,
            translation_angstrom=(
                float(translation_values[0]),
                float(translation_values[1]),
                float(translation_values[2]),
            ),
            steric_overlap_penalty=float(
                overlap_penalties[selected_site_index].item()
            ),
            overlap_pair_count=int(overlap_counts[selected_site_index].item()),
            deep_overlap_pair_count=int(deep_counts[selected_site_index].item()),
            pocket_outside_atom_count=int(outside_counts[selected_site_index].item()),
            pocket_boundary_penalty=float(
                boundary_penalties[selected_site_index].item()
            ),
            minimum_surface_separation_angstrom=float(
                minimum_separations[selected_site_index].item()
            ),
            blockers=self.blockers,
        )

def _grid_translations(config: StericFieldPlacementConfig) -> torch.Tensor:
    radius = config.translation_radius_angstrom
    spacing = config.grid_spacing_angstrom
    extent = int(math.floor(radius / spacing))
    values: list[tuple[float, float, float]] = []
    tolerance = 1.0e-12
    for x_index in range(-extent, extent + 1):
        x = x_index * spacing
        for y_index in range(-extent, extent + 1):
            y = y_index * spacing
            for z_index in range(-extent, extent + 1):
                z = z_index * spacing
                if x * x + y * y + z * z <= radius * radius + tolerance:
                    values.append((x, y, z))
                    if len(values) > config.max_grid_point_count:
                        raise StericFieldPlacementError(
                            "steric-field grid exceeds the point capacity"
                        )
    if not values:
        values.append((0.0, 0.0, 0.0))
    return torch.tensor(values, dtype=torch.float64)


def build_steric_field_placement_plan(
    problem: DockingProblemInput,
    *,
    config: StericFieldPlacementConfig,
) -> StericFieldPlacementPlan:
    """Build a receptor/pocket/search-space-bound deterministic site plan."""

    if not isinstance(problem, DockingProblemInput):
        raise TypeError("problem must be DockingProblemInput")
    if not isinstance(config, StericFieldPlacementConfig):
        raise TypeError("config must be StericFieldPlacementConfig")
    problem.assert_integrity()
    receptor_coordinates = _frozen_cpu_float64(
        problem.receptor.coordinates[0],
        name="receptor coordinates",
    )
    ligand_coordinates = _frozen_cpu_float64(
        problem.ligand.coordinates[0],
        name="ligand coordinates",
    )
    pocket_center = problem.pocket.center_tensor
    shell_radius = (
        problem.pocket.radius_angstrom
        + config.receptor_shell_padding_angstrom
    )
    shell_mask = torch.linalg.vector_norm(
        receptor_coordinates - pocket_center.reshape(1, 3),
        dim=1,
    ) <= shell_radius
    shell_indices = torch.nonzero(shell_mask, as_tuple=False).reshape(-1)
    shell_count = int(shell_indices.numel())
    if shell_count < 1:
        raise StericFieldPlacementError(
            "steric-field receptor shell contains no atoms"
        )
    if shell_count > config.max_receptor_shell_atoms:
        raise StericFieldPlacementError(
            "steric-field receptor shell exceeds the atom capacity"
        )
    shell_coordinates = receptor_coordinates.index_select(0, shell_indices)
    receptor_atomic_numbers = tuple(
        problem.receptor.atoms[int(index)].atomic_number
        for index in shell_indices.tolist()
    )
    ligand_atomic_numbers = tuple(atom.atomic_number for atom in problem.ligand.atoms)
    unsupported = sorted(
        (set(receptor_atomic_numbers) | set(ligand_atomic_numbers))
        - set(GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM)
    )
    if unsupported:
        raise StericFieldPlacementError(
            "steric-field radius profile does not support atomic numbers: "
            + ", ".join(str(value) for value in unsupported)
        )
    receptor_radii = torch.tensor(
        [
            GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[value]
            for value in receptor_atomic_numbers
        ],
        dtype=torch.float64,
    )
    ligand_radii = torch.tensor(
        [
            GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[value]
            for value in ligand_atomic_numbers
        ],
        dtype=torch.float64,
    )
    translations = _grid_translations(config)
    source_grid_count = int(translations.shape[0])
    if source_grid_count * shell_count > config.max_anchor_pairs:
        raise StericFieldPlacementError(
            "steric-field anchor pair capacity exceeded"
        )
    heavy_indices = tuple(
        index for index, value in enumerate(ligand_atomic_numbers) if value != 1
    )
    if not heavy_indices:
        heavy_indices = tuple(range(problem.ligand.atom_count))
    heavy_index_tensor = torch.tensor(heavy_indices, dtype=torch.long)
    reference_anchor = ligand_coordinates.index_select(
        0,
        heavy_index_tensor,
    ).mean(dim=0)
    anchor_positions = reference_anchor.reshape(1, 3) + translations
    anchor_distances = torch.linalg.vector_norm(
        anchor_positions.unsqueeze(1) - shell_coordinates.unsqueeze(0),
        dim=2,
    )
    anchor_thresholds = config.overlap_scale * (
        receptor_radii.reshape(1, -1) + config.anchor_probe_radius_angstrom
    )
    anchor_penetrations = torch.clamp(
        anchor_thresholds - anchor_distances,
        min=0.0,
    )
    anchor_overlap_counts = (anchor_distances < anchor_thresholds).sum(dim=1)
    anchor_penalties = (anchor_penetrations * anchor_penetrations).sum(dim=1)
    ranked_source_indices = sorted(
        range(source_grid_count),
        key=lambda index: (
            int(anchor_overlap_counts[index].item()),
            float(anchor_penalties[index].item()),
            float(torch.dot(translations[index], translations[index]).item()),
            float(translations[index, 0].item()),
            float(translations[index, 1].item()),
            float(translations[index, 2].item()),
        ),
    )
    retained_source_indices = ranked_source_indices[: config.maximum_site_count]
    zero_source_index = next(
        index
        for index in range(source_grid_count)
        if bool((translations[index] == 0.0).all().item())
    )
    if zero_source_index not in retained_source_indices:
        retained_source_indices[-1] = zero_source_index
        retained_source_indices.sort(
            key=lambda index: ranked_source_indices.index(index)
        )
    retained_translations = translations.index_select(
        0,
        torch.tensor(retained_source_indices, dtype=torch.long),
    )
    site_ids = tuple(
        "steric-site-"
        f"{index:04d}-"
        f"{_canonical_sha256(_tensor_payload(retained_translations[index]))[:12]}"
        for index in range(int(retained_translations.shape[0]))
    )
    plan = StericFieldPlacementPlan(
        problem_fingerprint_sha256=problem.identity.fingerprint_sha256,
        search_space_fingerprint_sha256=problem.search_space.fingerprint_sha256,
        problem_input_fingerprint_sha256=problem.input_fingerprint_sha256,
        receptor_system_sha256=canonical_system_sha256(problem.receptor),
        ligand_system_sha256=canonical_system_sha256(problem.ligand),
        pocket_definition_sha256=problem.pocket.fingerprint_sha256,
        receptor_coordinates=shell_coordinates,
        receptor_radii=receptor_radii,
        ligand_radii=ligand_radii,
        pocket_center=pocket_center,
        pocket_radius_angstrom=problem.pocket.radius_angstrom,
        site_translations=retained_translations,
        site_ids=site_ids,
        site_anchor_overlap_counts=tuple(
            int(anchor_overlap_counts[index].item())
            for index in retained_source_indices
        ),
        site_anchor_penalties=tuple(
            float(anchor_penalties[index].item())
            for index in retained_source_indices
        ),
        source_grid_point_count=source_grid_count,
        config=config,
    )
    plan.assert_integrity()
    return plan


__all__ = [
    "MAX_STERIC_FIELD_ANCHOR_PAIRS",
    "MAX_STERIC_FIELD_GRID_POINTS",
    "MAX_STERIC_FIELD_PAIR_CHUNK",
    "MAX_STERIC_FIELD_POSE_PAIRS_PER_PROPOSAL",
    "MAX_STERIC_FIELD_RECEPTOR_ATOMS",
    "MAX_STERIC_FIELD_RETAINED_SITES",
    "STERIC_FIELD_PLACEMENT_BLOCKERS",
    "STERIC_FIELD_PLACEMENT_CONFIG_SCHEMA_ID",
    "STERIC_FIELD_PLACEMENT_PLAN_SCHEMA_ID",
    "STERIC_FIELD_SITE_SCHEMA_ID",
    "StericFieldPlacementConfig",
    "StericFieldPlacementError",
    "StericFieldPlacementPlan",
    "build_steric_field_placement_plan",
]
