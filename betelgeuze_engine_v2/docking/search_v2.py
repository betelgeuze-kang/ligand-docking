"""Fail-closed Python facade for the product-owned native docking search v2.

The public path always imports the compiled Rust extension.  It never imports
an external solver and never substitutes a Python evaluator when the native
artifact or its build identity is unavailable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
import hashlib
from importlib import import_module, machinery, metadata
import json
import math
import numbers
from pathlib import Path
import re
import struct
import sys
from types import MappingProxyType
import numpy as np


DOCKING_SEARCH_V2_RESULT_SCHEMA_ID = "betelgeuze.engine_v2.docking_search_result/2.0.0"
DOCKING_SEARCH_V2_NATIVE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2.docking_search_native_receipt/2.0.0"
)
DOCKING_SEARCH_V2_ALGORITHM_ID = (
    "native_low_discrepancy_so3_surface_dual_anchor_short_range/2.0.0"
)
DOCKING_SEARCH_V2_CORE_SCHEMA_ID = "betelgeuze.docking_search/2.0.0"
DOCKING_SEARCH_V2_CORE_RECEIPT_SCHEMA_ID = "betelgeuze.docking_search_receipt/2.0.0"
DOCKING_SEARCH_V2_NATIVE_DISTRIBUTION_VERSION = "0.2.0rc6"
DOCKING_SEARCH_V2_NATIVE_BACKEND_VERSION = "0.2.0-rc.6"
DOCKING_SEARCH_V2_NATIVE_RUSTC_VERSION = "rustc 1.93.0 (254b59607 2026-01-19)"
DOCKING_SEARCH_V2_NATIVE_TARGET_TRIPLE = "x86_64-unknown-linux-gnu"
DOCKING_SEARCH_V2_NATIVE_BUILD_FLAGS = (
    "profile=release,codegen-units=1,debug=false,lto=fat,opt-level=3,"
    "panic=abort,strip=symbols"
)
DOCKING_SEARCH_V2_CLAIM_BLOCKERS = ("public_development_cohort_gate_not_passed",)

MAX_DOCKING_SEARCH_V2_LIGAND_ATOMS = 512
MAX_DOCKING_SEARCH_V2_LIGAND_ANCHORS = 256
MAX_DOCKING_SEARCH_V2_RECEPTOR_ATOMS = 65_536
MAX_DOCKING_SEARCH_V2_SURFACE_SAMPLES = 4_096
MAX_DOCKING_SEARCH_V2_ORIENTATIONS = 512
MAX_DOCKING_SEARCH_V2_CANDIDATES = 65_536
MAX_DOCKING_SEARCH_V2_REFINEMENT_STEPS = 128
MAX_DOCKING_SEARCH_V2_TOP_K = 1_024
MAX_DOCKING_SEARCH_V2_ANCHOR_COMBINATIONS = 65_536
MAX_DOCKING_SEARCH_V2_COMPATIBLE_SINGLE_ANCHOR_PAIRS = 4_096
MAX_DOCKING_SEARCH_V2_CANDIDATE_COORDINATES = 4_000_000
MAX_DOCKING_SEARCH_V2_PAIR_EVALUATIONS = 250_000_000
MAX_DOCKING_SEARCH_V2_EVALUATION_DETAIL_BYTES = 4_096
MAX_DOCKING_SEARCH_V2_LEDGER_PAYLOAD_BYTES = 128 * 1_024 * 1_024
# Python tuples, floats, mappings, and their transient validation copies are
# materially larger than the packed Rust ledger.  Keep this bridge-specific
# projection conservative so a request which is legal for the native core
# cannot expand into an unbounded Python object graph.
MAX_DOCKING_SEARCH_V2_PYTHON_BRIDGE_BYTES = 64 * 1_024 * 1_024
_PYTHON_BRIDGE_COORDINATE_ROW_BYTES = 256
_PYTHON_BRIDGE_CANDIDATE_ROW_BYTES = 2_048
_PYTHON_BRIDGE_POSE_BYTES = 1_024
_PYTHON_BRIDGE_ORIENTATION_ROW_BYTES = 512
_LOW_DISCREPANCY_ORIENTATION_BASES = (2, 3, 5)
_MAX_RAW_ATTEMPTS_PER_ORIENTATION = 1_024
_TWO_POW_64 = 18_446_744_073_709_551_616.0
_ORIENTATION_DUPLICATE_TOLERANCE_RADIANS = 1.0e-10
# Rust and CPython can differ by a few last bits in platform sin/cos results.
# This remains two orders of magnitude tighter than the duplicate threshold and
# only admits numerically equivalent rotations.
_ORIENTATION_SEMANTIC_TOLERANCE_RADIANS = 1.0e-12

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CORE_STATUS_VALUES = frozenset(
    {
        "coarse_pruned",
        "detailed_pruned",
        "refinement_failed",
        "physical_rejected",
        "cluster_member",
        "cluster_representative",
        "top_k",
    }
)
_CORE_REASON_VALUES = frozenset(
    {
        "coarse_budget",
        "detailed_budget",
        "evaluator_failure",
        "non_finite_evaluation",
        "non_finite_coordinate",
        "coordinate_out_of_bounds",
        "ligand_self_overlap",
        "receptor_clash",
        "clustered_into_representative",
        "top_k_budget",
    }
)


class DockingSearchV2Error(RuntimeError):
    """The bounded native docking-search contract could not be satisfied."""


class DockingAnchorKind(str, Enum):
    HYDROGEN_BOND_DONOR = "hydrogen_bond_donor"
    HYDROGEN_BOND_ACCEPTOR = "hydrogen_bond_acceptor"
    HYDROPHOBE = "hydrophobe"
    AROMATIC = "aromatic"
    POSITIVE = "positive"
    NEGATIVE = "negative"

    @property
    def native_code(self) -> int:
        return tuple(DockingAnchorKind).index(self)


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise DockingSearchV2Error(
            "docking search v2 value is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite_float(
    value: object,
    *,
    name: str,
    minimum: float,
    maximum: float,
    minimum_inclusive: bool = True,
) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise DockingSearchV2Error(f"{name} must be a real scalar")
    result = float(value)
    lower_valid = result >= minimum if minimum_inclusive else result > minimum
    if not math.isfinite(result) or not lower_valid or result > maximum:
        boundary = "[" if minimum_inclusive else "("
        raise DockingSearchV2Error(
            f"{name} must be finite in {boundary}{minimum},{maximum}]"
        )
    return result


def _exact_int(value: object, *, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral):
        raise DockingSearchV2Error(f"{name} must be an integer")
    result = int(value)
    if not minimum <= result <= maximum:
        raise DockingSearchV2Error(f"{name} must be in [{minimum},{maximum}]")
    return result


def _plain_sequence(value: object, *, name: str) -> Sequence[object] | np.ndarray:
    if isinstance(value, np.ndarray):
        # Returning the bounded view avoids an eager object-dtype expansion.
        # Callers validate dimensionality and length before reading elements.
        return value
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise DockingSearchV2Error(f"{name} must be a bounded array or sequence")
    return value


def _rows3(
    value: object,
    *,
    name: str,
    minimum_rows: int,
    maximum_rows: int,
    maximum_absolute: float = 1.0e9,
) -> tuple[tuple[float, float, float], ...]:
    if isinstance(value, np.ndarray):
        if value.dtype != np.dtype(np.float64) or value.ndim != 2:
            raise DockingSearchV2Error(f"{name} numpy input must be float64 [N,3]")
        if value.shape[1:] != (3,):
            raise DockingSearchV2Error(f"{name} must have shape [N,3]")
        if not minimum_rows <= value.shape[0] <= maximum_rows:
            raise DockingSearchV2Error(
                f"{name} row count must be in [{minimum_rows},{maximum_rows}]"
            )
    rows = _plain_sequence(value, name=name)
    if not minimum_rows <= len(rows) <= maximum_rows:
        raise DockingSearchV2Error(
            f"{name} row count must be in [{minimum_rows},{maximum_rows}]"
        )
    output: list[tuple[float, float, float]] = []
    for row_index, raw_row in enumerate(rows):
        row = _plain_sequence(raw_row, name=f"{name}[{row_index}]")
        if len(row) != 3:
            raise DockingSearchV2Error(f"{name} must have shape [N,3]")
        output.append(
            tuple(
                _finite_float(
                    component,
                    name=f"{name}[{row_index}][{axis}]",
                    minimum=-maximum_absolute,
                    maximum=maximum_absolute,
                )
                for axis, component in enumerate(row)
            )  # type: ignore[arg-type]
        )
    return tuple(output)


def _float_vector(
    value: object,
    *,
    name: str,
    length: int,
    minimum: float,
    maximum: float,
    minimum_inclusive: bool = True,
) -> tuple[float, ...]:
    if isinstance(value, np.ndarray) and (
        value.dtype != np.dtype(np.float64) or value.ndim != 1
    ):
        raise DockingSearchV2Error(f"{name} numpy input must be float64 [N]")
    if isinstance(value, np.ndarray) and value.shape != (length,):
        raise DockingSearchV2Error(f"{name} length must equal {length}")
    values = _plain_sequence(value, name=name)
    if len(values) != length:
        raise DockingSearchV2Error(f"{name} length must equal {length}")
    return tuple(
        _finite_float(
            item,
            name=f"{name}[{index}]",
            minimum=minimum,
            maximum=maximum,
            minimum_inclusive=minimum_inclusive,
        )
        for index, item in enumerate(values)
    )


def _int_vector(
    value: object,
    *,
    name: str,
    length: int,
    minimum: int,
    maximum: int,
) -> tuple[int, ...]:
    if isinstance(value, np.ndarray) and (
        value.ndim != 1 or not np.issubdtype(value.dtype, np.integer)
    ):
        raise DockingSearchV2Error(f"{name} numpy input must be an integer [N] array")
    if isinstance(value, np.ndarray) and value.shape != (length,):
        raise DockingSearchV2Error(f"{name} length must equal {length}")
    values = _plain_sequence(value, name=name)
    if len(values) != length:
        raise DockingSearchV2Error(f"{name} length must equal {length}")
    return tuple(
        _exact_int(item, name=f"{name}[{index}]", minimum=minimum, maximum=maximum)
        for index, item in enumerate(values)
    )


def _anchor_kind(value: object, *, name: str) -> DockingAnchorKind:
    if isinstance(value, DockingAnchorKind):
        return value
    if isinstance(value, str):
        try:
            return DockingAnchorKind(value)
        except ValueError as exc:
            raise DockingSearchV2Error(
                f"{name} is not a canonical anchor kind"
            ) from exc
    if isinstance(value, numbers.Integral) and not isinstance(value, (bool, np.bool_)):
        code = _exact_int(value, name=name, minimum=0, maximum=5)
        return tuple(DockingAnchorKind)[code]
    raise DockingSearchV2Error(f"{name} is not a canonical anchor kind")


def _anchor_kinds(
    value: object, *, name: str, length: int
) -> tuple[DockingAnchorKind, ...]:
    if isinstance(value, np.ndarray) and value.ndim != 1:
        raise DockingSearchV2Error(f"{name} numpy input must have shape [N]")
    if isinstance(value, np.ndarray) and value.shape != (length,):
        raise DockingSearchV2Error(f"{name} length must equal {length}")
    values = _plain_sequence(value, name=name)
    if len(values) != length:
        raise DockingSearchV2Error(f"{name} length must equal {length}")
    return tuple(
        _anchor_kind(item, name=f"{name}[{index}]") for index, item in enumerate(values)
    )


def _source_seed_hex(value: object) -> str:
    if isinstance(value, bytes):
        if len(value) != 32:
            raise DockingSearchV2Error(
                "source_seed bytes must contain exactly 32 bytes"
            )
        return value.hex()
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise DockingSearchV2Error("source_seed must be 32 bytes or lowercase 64-hex")
    return value


@dataclass(frozen=True, slots=True)
class DockingSearchV2Input:
    source_seed: str | bytes
    ligand_coordinates_angstrom: object
    ligand_vdw_radii_angstrom: object
    ligand_epsilon_kcal_per_mol: object
    ligand_charge_elementary: object
    ligand_anchor_ids: object
    ligand_anchor_atom_indices: object
    ligand_anchor_directions: object
    ligand_anchor_kinds: object
    receptor_coordinates_angstrom: object
    receptor_vdw_radii_angstrom: object
    receptor_epsilon_kcal_per_mol: object
    receptor_charge_elementary: object
    surface_ids: object
    surface_positions_angstrom: object
    surface_outward_normals: object
    surface_anchor_kinds: object
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_seed", _source_seed_hex(self.source_seed))
        ligand_coordinates = _rows3(
            self.ligand_coordinates_angstrom,
            name="ligand_coordinates_angstrom",
            minimum_rows=1,
            maximum_rows=MAX_DOCKING_SEARCH_V2_LIGAND_ATOMS,
        )
        ligand_count = len(ligand_coordinates)
        object.__setattr__(self, "ligand_coordinates_angstrom", ligand_coordinates)
        object.__setattr__(
            self,
            "ligand_vdw_radii_angstrom",
            _float_vector(
                self.ligand_vdw_radii_angstrom,
                name="ligand_vdw_radii_angstrom",
                length=ligand_count,
                minimum=0.0,
                maximum=100.0,
                minimum_inclusive=False,
            ),
        )
        object.__setattr__(
            self,
            "ligand_epsilon_kcal_per_mol",
            _float_vector(
                self.ligand_epsilon_kcal_per_mol,
                name="ligand_epsilon_kcal_per_mol",
                length=ligand_count,
                minimum=0.0,
                maximum=1_000.0,
            ),
        )
        object.__setattr__(
            self,
            "ligand_charge_elementary",
            _float_vector(
                self.ligand_charge_elementary,
                name="ligand_charge_elementary",
                length=ligand_count,
                minimum=-16.0,
                maximum=16.0,
            ),
        )

        if isinstance(self.ligand_anchor_ids, np.ndarray):
            if self.ligand_anchor_ids.ndim != 1:
                raise DockingSearchV2Error("ligand_anchor_ids must have shape [N]")
            anchor_count = int(self.ligand_anchor_ids.shape[0])
        else:
            anchor_count = len(
                _plain_sequence(self.ligand_anchor_ids, name="ligand_anchor_ids")
            )
        if not 1 <= anchor_count <= MAX_DOCKING_SEARCH_V2_LIGAND_ANCHORS:
            raise DockingSearchV2Error(
                "ligand_anchor_ids length must be in "
                f"[1,{MAX_DOCKING_SEARCH_V2_LIGAND_ANCHORS}]"
            )
        anchor_ids = _int_vector(
            self.ligand_anchor_ids,
            name="ligand_anchor_ids",
            length=anchor_count,
            minimum=0,
            maximum=2**32 - 1,
        )
        if len(set(anchor_ids)) != anchor_count:
            raise DockingSearchV2Error("ligand_anchor_ids must be unique")
        object.__setattr__(self, "ligand_anchor_ids", anchor_ids)
        object.__setattr__(
            self,
            "ligand_anchor_atom_indices",
            _int_vector(
                self.ligand_anchor_atom_indices,
                name="ligand_anchor_atom_indices",
                length=anchor_count,
                minimum=0,
                maximum=ligand_count - 1,
            ),
        )
        anchor_directions = _rows3(
            self.ligand_anchor_directions,
            name="ligand_anchor_directions",
            minimum_rows=anchor_count,
            maximum_rows=anchor_count,
        )
        if any(math.hypot(*row) <= 1.0e-12 for row in anchor_directions):
            raise DockingSearchV2Error("ligand_anchor_directions must be non-zero")
        object.__setattr__(self, "ligand_anchor_directions", anchor_directions)
        object.__setattr__(
            self,
            "ligand_anchor_kinds",
            _anchor_kinds(
                self.ligand_anchor_kinds,
                name="ligand_anchor_kinds",
                length=anchor_count,
            ),
        )

        receptor_coordinates = _rows3(
            self.receptor_coordinates_angstrom,
            name="receptor_coordinates_angstrom",
            minimum_rows=0,
            maximum_rows=MAX_DOCKING_SEARCH_V2_RECEPTOR_ATOMS,
        )
        receptor_count = len(receptor_coordinates)
        object.__setattr__(self, "receptor_coordinates_angstrom", receptor_coordinates)
        for field_name, minimum, maximum, inclusive in (
            ("receptor_vdw_radii_angstrom", 0.0, 100.0, False),
            ("receptor_epsilon_kcal_per_mol", 0.0, 1_000.0, True),
            ("receptor_charge_elementary", -16.0, 16.0, True),
        ):
            object.__setattr__(
                self,
                field_name,
                _float_vector(
                    getattr(self, field_name),
                    name=field_name,
                    length=receptor_count,
                    minimum=minimum,
                    maximum=maximum,
                    minimum_inclusive=inclusive,
                ),
            )

        if isinstance(self.surface_ids, np.ndarray):
            if self.surface_ids.ndim != 1:
                raise DockingSearchV2Error("surface_ids must have shape [N]")
            surface_count = int(self.surface_ids.shape[0])
        else:
            surface_count = len(_plain_sequence(self.surface_ids, name="surface_ids"))
        if not 1 <= surface_count <= MAX_DOCKING_SEARCH_V2_SURFACE_SAMPLES:
            raise DockingSearchV2Error(
                "surface_ids length must be in "
                f"[1,{MAX_DOCKING_SEARCH_V2_SURFACE_SAMPLES}]"
            )
        surface_ids = _int_vector(
            self.surface_ids,
            name="surface_ids",
            length=surface_count,
            minimum=0,
            maximum=2**32 - 1,
        )
        if len(set(surface_ids)) != surface_count:
            raise DockingSearchV2Error("surface_ids must be unique")
        object.__setattr__(self, "surface_ids", surface_ids)
        object.__setattr__(
            self,
            "surface_positions_angstrom",
            _rows3(
                self.surface_positions_angstrom,
                name="surface_positions_angstrom",
                minimum_rows=surface_count,
                maximum_rows=surface_count,
            ),
        )
        surface_normals = _rows3(
            self.surface_outward_normals,
            name="surface_outward_normals",
            minimum_rows=surface_count,
            maximum_rows=surface_count,
        )
        if any(math.hypot(*row) <= 1.0e-12 for row in surface_normals):
            raise DockingSearchV2Error("surface_outward_normals must be non-zero")
        object.__setattr__(self, "surface_outward_normals", surface_normals)
        object.__setattr__(
            self,
            "surface_anchor_kinds",
            _anchor_kinds(
                self.surface_anchor_kinds,
                name="surface_anchor_kinds",
                length=surface_count,
            ),
        )
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "source_seed_hex": self.source_seed,
            "ligand_coordinates_angstrom": self.ligand_coordinates_angstrom,
            "ligand_vdw_radii_angstrom": self.ligand_vdw_radii_angstrom,
            "ligand_epsilon_kcal_per_mol": self.ligand_epsilon_kcal_per_mol,
            "ligand_charge_elementary": self.ligand_charge_elementary,
            "ligand_anchor_ids": self.ligand_anchor_ids,
            "ligand_anchor_atom_indices": self.ligand_anchor_atom_indices,
            "ligand_anchor_directions": self.ligand_anchor_directions,
            "ligand_anchor_kinds": tuple(
                value.value for value in self.ligand_anchor_kinds
            ),
            "receptor_coordinates_angstrom": self.receptor_coordinates_angstrom,
            "receptor_vdw_radii_angstrom": self.receptor_vdw_radii_angstrom,
            "receptor_epsilon_kcal_per_mol": self.receptor_epsilon_kcal_per_mol,
            "receptor_charge_elementary": self.receptor_charge_elementary,
            "surface_ids": self.surface_ids,
            "surface_positions_angstrom": self.surface_positions_angstrom,
            "surface_outward_normals": self.surface_outward_normals,
            "surface_anchor_kinds": tuple(
                value.value for value in self.surface_anchor_kinds
            ),
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise DockingSearchV2Error(
                "docking search v2 input changed after validation"
            )
        return observed

    def _native_arguments(self) -> dict[str, object]:
        self.fingerprint_sha256
        return {
            **self._projection(),
            "ligand_anchor_kinds": tuple(
                value.native_code for value in self.ligand_anchor_kinds
            ),
            "surface_anchor_kinds": tuple(
                value.native_code for value in self.surface_anchor_kinds
            ),
        }


@dataclass(frozen=True, slots=True)
class DockingSearchV2Config:
    orientation_count: int = 24
    generated_candidate_limit: int = 4_096
    coarse_keep: int = 512
    refinement_keep: int = 64
    top_k: int = 10
    placement_clearance_angstrom: float = 1.5
    dual_anchor_distance_tolerance_angstrom: float = 0.75
    coarse_clash_weight: float = 8.0
    refinement_steps: int = 12
    translation_step_angstrom2_per_kcal: float = 0.01
    rotation_step_per_torque: float = 0.001
    maximum_translation_step_angstrom: float = 0.25
    maximum_rotation_step_radians: float = 0.12
    maximum_absolute_coordinate_angstrom: float = 100_000.0
    minimum_ligand_atom_distance_angstrom: float = 0.05
    minimum_receptor_clearance_scale: float = 0.45
    cluster_rmsd_angstrom: float = 1.0

    def __post_init__(self) -> None:
        for name, maximum in (
            ("orientation_count", MAX_DOCKING_SEARCH_V2_ORIENTATIONS),
            ("generated_candidate_limit", MAX_DOCKING_SEARCH_V2_CANDIDATES),
            ("coarse_keep", MAX_DOCKING_SEARCH_V2_CANDIDATES),
            ("refinement_keep", MAX_DOCKING_SEARCH_V2_CANDIDATES),
            ("top_k", MAX_DOCKING_SEARCH_V2_TOP_K),
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(getattr(self, name), name=name, minimum=1, maximum=maximum),
            )
        object.__setattr__(
            self,
            "refinement_steps",
            _exact_int(
                self.refinement_steps,
                name="refinement_steps",
                minimum=0,
                maximum=MAX_DOCKING_SEARCH_V2_REFINEMENT_STEPS,
            ),
        )
        if self.coarse_keep > self.generated_candidate_limit:
            raise DockingSearchV2Error("coarse_keep exceeds generated_candidate_limit")
        if self.refinement_keep > self.coarse_keep:
            raise DockingSearchV2Error("refinement_keep exceeds coarse_keep")
        if self.top_k > self.refinement_keep:
            raise DockingSearchV2Error("top_k exceeds refinement_keep")
        for name, minimum, maximum, inclusive in (
            ("placement_clearance_angstrom", 0.0, 10_000.0, True),
            ("dual_anchor_distance_tolerance_angstrom", 1.0e-6, 10.0, True),
            ("coarse_clash_weight", 0.0, 1.0e12, True),
            ("translation_step_angstrom2_per_kcal", 0.0, 1.0e6, True),
            ("rotation_step_per_torque", 0.0, 1.0e6, True),
            ("maximum_translation_step_angstrom", 0.0, 10_000.0, False),
            ("maximum_rotation_step_radians", 0.0, math.pi, False),
            ("maximum_absolute_coordinate_angstrom", 0.0, 1.0e9, False),
            ("minimum_ligand_atom_distance_angstrom", 0.0, 100.0, False),
            ("minimum_receptor_clearance_scale", 0.0, 1.0, False),
            ("cluster_rmsd_angstrom", 0.0, 10_000.0, False),
        ):
            object.__setattr__(
                self,
                name,
                _finite_float(
                    getattr(self, name),
                    name=name,
                    minimum=minimum,
                    maximum=maximum,
                    minimum_inclusive=inclusive,
                ),
            )

    def to_native_dict(self) -> dict[str, int | float]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class DockingShortRangeV2Config:
    ligand_shape_force_constant_kcal_per_mol_angstrom2: float = 10.0
    cutoff_angstrom: float = 12.0
    switch_start_angstrom: float = 10.0
    softcore_angstrom: float = 0.25
    dielectric: float = 4.0

    def __post_init__(self) -> None:
        for name, minimum, maximum, inclusive in (
            ("ligand_shape_force_constant_kcal_per_mol_angstrom2", 0.0, 1.0e6, True),
            ("cutoff_angstrom", 0.0, 1_000.0, False),
            ("switch_start_angstrom", 0.0, 1_000.0, True),
            ("softcore_angstrom", 0.0, 10.0, False),
            ("dielectric", 1.0, 1.0e6, True),
        ):
            object.__setattr__(
                self,
                name,
                _finite_float(
                    getattr(self, name),
                    name=name,
                    minimum=minimum,
                    maximum=maximum,
                    minimum_inclusive=inclusive,
                ),
            )
        if self.switch_start_angstrom >= self.cutoff_angstrom:
            raise DockingSearchV2Error(
                "switch_start_angstrom must be below cutoff_angstrom"
            )

    def to_native_dict(self) -> dict[str, float]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


def _optional_int(
    value: object,
    *,
    name: str,
    maximum: int,
    minimum: int = 0,
) -> int | None:
    if value is None:
        return None
    return _exact_int(value, name=name, minimum=minimum, maximum=maximum)


def _optional_float(value: object, *, name: str) -> float | None:
    if value is None:
        return None
    return _finite_float(value, name=name, minimum=-1.0e300, maximum=1.0e300)


def _candidate_key(value: object, *, name: str) -> Mapping[str, int | None]:
    if not isinstance(value, Mapping):
        raise DockingSearchV2Error(f"{name} must be a mapping")
    expected = {
        "orientation_index",
        "primary_surface_id",
        "primary_ligand_anchor_id",
        "secondary_surface_id",
        "secondary_ligand_anchor_id",
    }
    if set(value) != expected:
        raise DockingSearchV2Error(f"{name} has an invalid key schema")
    result = {
        "orientation_index": _exact_int(
            value["orientation_index"],
            name=f"{name}.orientation_index",
            minimum=0,
            maximum=2**32 - 1,
        ),
        "primary_surface_id": _exact_int(
            value["primary_surface_id"],
            name=f"{name}.primary_surface_id",
            minimum=0,
            maximum=2**32 - 1,
        ),
        "primary_ligand_anchor_id": _exact_int(
            value["primary_ligand_anchor_id"],
            name=f"{name}.primary_ligand_anchor_id",
            minimum=0,
            maximum=2**32 - 1,
        ),
        "secondary_surface_id": _optional_int(
            value["secondary_surface_id"],
            name=f"{name}.secondary_surface_id",
            maximum=2**32 - 1,
        ),
        "secondary_ligand_anchor_id": _optional_int(
            value["secondary_ligand_anchor_id"],
            name=f"{name}.secondary_ligand_anchor_id",
            maximum=2**32 - 1,
        ),
    }
    if (result["secondary_surface_id"] is None) != (
        result["secondary_ligand_anchor_id"] is None
    ):
        raise DockingSearchV2Error(f"{name} secondary identities must be paired")
    return MappingProxyType(result)


def _exact_mapping(
    value: object,
    *,
    name: str,
    keys: frozenset[str],
) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise DockingSearchV2Error(f"{name} has an invalid key schema")
    return value


_CANDIDATE_ROW_KEYS = frozenset(
    {
        "slot_index",
        "key",
        "placement_mode",
        "status",
        "reason",
        "detail",
        "coordinates_angstrom",
        "anchor_fit_rmsd_angstrom",
        "coarse_score",
        "detailed_score",
        "energy_kcal_per_mol",
        "physically_valid",
        "minimum_receptor_gap_angstrom",
        "cluster_id",
        "final_rank",
    }
)
_POSE_KEYS = frozenset(
    {
        "rank",
        "key",
        "coordinates_angstrom",
        "energy_kcal_per_mol",
        "cluster_size",
        "minimum_receptor_gap_angstrom",
    }
)
_ORIENTATION_MATERIAL_KEYS = frozenset(
    {"orientation_index", "raw_sequence_index", "quaternion"}
)
_RESULT_KEYS = frozenset(
    {"schema_id", "orientation_material", "candidate_rows", "poses", "receipt"}
)
_SEARCH_RECEIPT_KEYS = frozenset(
    {
        "schema_id",
        "evaluator_id",
        "evaluator_config_sha256",
        "config_sha256",
        "input_sha256",
        "result_independent_allocation",
        "placement_mode",
        "requested_orientation_count",
        "accepted_orientation_count",
        "raw_orientation_attempt_count",
        "compatible_single_anchor_pair_count",
        "compatible_dual_anchor_combination_count",
        "used_anchor_combination_count",
        "possible_candidate_slot_count",
        "generated_candidate_limit",
        "allocated_candidate_slot_count",
        "allocation_sha256",
        "orientation_sha256",
        "candidate_rows_sha256",
        "poses_sha256",
        "coarse_keep_budget",
        "coarse_kept_count",
        "refinement_keep_budget",
        "refinement_selected_count",
        "refinement_steps_per_candidate",
        "refinement_succeeded_count",
        "refinement_evaluator_failed_count",
        "refinement_non_finite_failed_count",
        "evaluator_call_count",
        "maximum_evaluator_call_count",
        "physical_valid_count",
        "rejected_non_finite_coordinate_count",
        "rejected_coordinate_out_of_bounds_count",
        "rejected_ligand_self_overlap_count",
        "rejected_receptor_clash_count",
        "cluster_count",
        "top_k_budget",
        "returned_pose_count",
        "receipt_sha256",
    }
)


@dataclass(frozen=True, slots=True)
class DockingSearchV2CandidateRow:
    slot_index: int
    key: Mapping[str, int | None]
    placement_mode: str
    status: str
    reason: str | None
    detail: str | None
    coordinates_angstrom: tuple[tuple[float, float, float], ...]
    anchor_fit_rmsd_angstrom: float
    coarse_score: float | None
    detailed_score: float | None
    energy_kcal_per_mol: float | None
    physically_valid: bool | None
    minimum_receptor_gap_angstrom: float | None
    cluster_id: int | None
    final_rank: int | None

    def __post_init__(self) -> None:
        terminal = {
            "coarse_pruned": ({"coarse_budget"}, None, False, False),
            "detailed_pruned": ({"detailed_budget"}, None, False, False),
            "refinement_failed": (
                {"evaluator_failure", "non_finite_evaluation"},
                None,
                False,
                False,
            ),
            "physical_rejected": (
                {
                    "non_finite_coordinate",
                    "coordinate_out_of_bounds",
                    "ligand_self_overlap",
                    "receptor_clash",
                },
                False,
                False,
                False,
            ),
            "cluster_member": (
                {"clustered_into_representative"},
                True,
                True,
                False,
            ),
            "cluster_representative": ({"top_k_budget"}, True, True, False),
            "top_k": ({None}, True, True, True),
        }
        allowed_reasons, expected_validity, needs_cluster, needs_rank = terminal[
            self.status
        ]
        if (
            self.reason not in allowed_reasons
            or self.physically_valid is not expected_validity
        ):
            raise DockingSearchV2Error(
                "native candidate terminal status, reason, and validity disagree"
            )
        if (self.cluster_id is not None) is not needs_cluster:
            raise DockingSearchV2Error(
                "native candidate cluster identity is inconsistent"
            )
        if (self.final_rank is not None) is not needs_rank:
            raise DockingSearchV2Error("native candidate final rank is inconsistent")
        if needs_cluster and self.energy_kcal_per_mol is None:
            raise DockingSearchV2Error("native clustered candidate lacks finite energy")
        if self.status == "refinement_failed":
            if not self.detail:
                raise DockingSearchV2Error("native refinement failure lacks detail")
        elif self.detail is not None:
            raise DockingSearchV2Error(
                "native non-failure candidate contains failure detail"
            )
        secondary_present = self.key["secondary_surface_id"] is not None
        if secondary_present != (self.placement_mode == "dual_anchor"):
            raise DockingSearchV2Error(
                "native placement mode disagrees with candidate secondary identities"
            )
        if secondary_present and (
            self.key["secondary_surface_id"] == self.key["primary_surface_id"]
            or self.key["secondary_ligand_anchor_id"]
            == self.key["primary_ligand_anchor_id"]
        ):
            raise DockingSearchV2Error(
                "native dual-anchor candidate repeats a primary identity"
            )

    @classmethod
    def _from_native(
        cls, value: object, *, ligand_count: int
    ) -> "DockingSearchV2CandidateRow":
        value = _exact_mapping(
            value,
            name="native candidate row",
            keys=_CANDIDATE_ROW_KEYS,
        )
        status = str(value.get("status", ""))
        reason_value = value.get("reason")
        reason = None if reason_value is None else str(reason_value)
        if status not in _CORE_STATUS_VALUES or (
            reason is not None and reason not in _CORE_REASON_VALUES
        ):
            raise DockingSearchV2Error("native candidate status or reason is invalid")
        detail_value = value.get("detail")
        detail = None if detail_value is None else str(detail_value)
        if detail is not None and len(detail.encode("utf-8")) > 4_096:
            raise DockingSearchV2Error("native candidate detail exceeds its bound")
        physically_valid = value.get("physically_valid")
        if physically_valid is not None and type(physically_valid) is not bool:
            raise DockingSearchV2Error("native physically_valid must be bool or null")
        placement_mode = str(value.get("placement_mode", ""))
        if placement_mode not in {"dual_anchor", "single_anchor_fallback"}:
            raise DockingSearchV2Error("native placement_mode is invalid")
        return cls(
            slot_index=_exact_int(
                value.get("slot_index"),
                name="candidate.slot_index",
                minimum=0,
                maximum=MAX_DOCKING_SEARCH_V2_CANDIDATES - 1,
            ),
            key=_candidate_key(value.get("key"), name="candidate.key"),
            placement_mode=placement_mode,
            status=status,
            reason=reason,
            detail=detail,
            coordinates_angstrom=_rows3(
                value.get("coordinates_angstrom"),
                name="candidate.coordinates_angstrom",
                minimum_rows=ligand_count,
                maximum_rows=ligand_count,
            ),
            anchor_fit_rmsd_angstrom=_finite_float(
                value.get("anchor_fit_rmsd_angstrom"),
                name="candidate.anchor_fit_rmsd_angstrom",
                minimum=0.0,
                maximum=1.0e9,
            ),
            coarse_score=_optional_float(
                value.get("coarse_score"), name="candidate.coarse_score"
            ),
            detailed_score=_optional_float(
                value.get("detailed_score"), name="candidate.detailed_score"
            ),
            energy_kcal_per_mol=_optional_float(
                value.get("energy_kcal_per_mol"), name="candidate.energy_kcal_per_mol"
            ),
            physically_valid=physically_valid,
            minimum_receptor_gap_angstrom=_optional_float(
                value.get("minimum_receptor_gap_angstrom"),
                name="candidate.minimum_receptor_gap_angstrom",
            ),
            cluster_id=_optional_int(
                value.get("cluster_id"),
                name="candidate.cluster_id",
                maximum=MAX_DOCKING_SEARCH_V2_CANDIDATES,
                minimum=1,
            ),
            final_rank=_optional_int(
                value.get("final_rank"),
                name="candidate.final_rank",
                maximum=MAX_DOCKING_SEARCH_V2_TOP_K,
                minimum=1,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "slot_index": self.slot_index,
            "key": dict(self.key),
            "placement_mode": self.placement_mode,
            "status": self.status,
            "reason": self.reason,
            "detail": self.detail,
            "coordinates_angstrom": [list(row) for row in self.coordinates_angstrom],
            "anchor_fit_rmsd_angstrom": self.anchor_fit_rmsd_angstrom,
            "coarse_score": self.coarse_score,
            "detailed_score": self.detailed_score,
            "energy_kcal_per_mol": self.energy_kcal_per_mol,
            "physically_valid": self.physically_valid,
            "minimum_receptor_gap_angstrom": self.minimum_receptor_gap_angstrom,
            "cluster_id": self.cluster_id,
            "final_rank": self.final_rank,
        }


@dataclass(frozen=True, slots=True)
class DockingSearchV2Pose:
    rank: int
    key: Mapping[str, int | None]
    coordinates_angstrom: tuple[tuple[float, float, float], ...]
    energy_kcal_per_mol: float
    cluster_size: int
    minimum_receptor_gap_angstrom: float | None

    @classmethod
    def _from_native(cls, value: object, *, ligand_count: int) -> "DockingSearchV2Pose":
        value = _exact_mapping(value, name="native pose", keys=_POSE_KEYS)
        return cls(
            rank=_exact_int(
                value.get("rank"),
                name="pose.rank",
                minimum=1,
                maximum=MAX_DOCKING_SEARCH_V2_TOP_K,
            ),
            key=_candidate_key(value.get("key"), name="pose.key"),
            coordinates_angstrom=_rows3(
                value.get("coordinates_angstrom"),
                name="pose.coordinates_angstrom",
                minimum_rows=ligand_count,
                maximum_rows=ligand_count,
            ),
            energy_kcal_per_mol=_finite_float(
                value.get("energy_kcal_per_mol"),
                name="pose.energy_kcal_per_mol",
                minimum=-1.0e300,
                maximum=1.0e300,
            ),
            cluster_size=_exact_int(
                value.get("cluster_size"),
                name="pose.cluster_size",
                minimum=1,
                maximum=MAX_DOCKING_SEARCH_V2_CANDIDATES,
            ),
            minimum_receptor_gap_angstrom=_optional_float(
                value.get("minimum_receptor_gap_angstrom"),
                name="pose.minimum_receptor_gap_angstrom",
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "key": dict(self.key),
            "coordinates_angstrom": [list(row) for row in self.coordinates_angstrom],
            "energy_kcal_per_mol": self.energy_kcal_per_mol,
            "cluster_size": self.cluster_size,
            "minimum_receptor_gap_angstrom": self.minimum_receptor_gap_angstrom,
        }


@dataclass(frozen=True, slots=True)
class _NativeBinding:
    module: object
    receipt: Mapping[str, object]


def _native_build_receipt(
    module: object,
    *,
    extension_path: Path | None,
    distribution_version: str,
    test_double: bool,
) -> Mapping[str, object]:
    try:
        raw = module.build_info()  # type: ignore[attr-defined]
    except Exception as exc:
        raise DockingSearchV2Error(
            "native docking-search build receipt is unavailable"
        ) from exc
    if not isinstance(raw, Mapping):
        raise DockingSearchV2Error(
            "native docking-search build receipt must be a mapping"
        )
    required = {
        "backend_id": "rust_cpu_required",
        "backend_version": DOCKING_SEARCH_V2_NATIVE_BACKEND_VERSION,
        "crate_name": "betelgeuze-engine-v2-native",
        "implicit_fallback_allowed": "false",
        "docking_search_schema_id": DOCKING_SEARCH_V2_CORE_SCHEMA_ID,
        "docking_search_receipt_schema_id": DOCKING_SEARCH_V2_CORE_RECEIPT_SCHEMA_ID,
        "docking_search_evaluator_id": "betelgeuze_short_range_analytic/1.0.0",
        "rustc_version": DOCKING_SEARCH_V2_NATIVE_RUSTC_VERSION,
        "target_triple": DOCKING_SEARCH_V2_NATIVE_TARGET_TRIPLE,
        "build_profile": "release",
        "opt_level": "3",
        "debug": "false",
        "panic_strategy": "abort",
        "build_flags": DOCKING_SEARCH_V2_NATIVE_BUILD_FLAGS,
        "cargo_features": "extension-module",
    }
    if any(str(raw.get(key, "")) != expected for key, expected in required.items()):
        raise DockingSearchV2Error("native docking-search identity is invalid")
    cargo_lock_sha256 = str(raw.get("cargo_lock_sha256", ""))
    source_closure_sha256 = str(raw.get("native_source_closure_sha256", ""))
    if (
        _SHA256_RE.fullmatch(cargo_lock_sha256) is None
        or _SHA256_RE.fullmatch(source_closure_sha256) is None
    ):
        raise DockingSearchV2Error(
            "native docking-search source identity is incomplete"
        )
    source_file_count = _exact_int(
        int(str(raw.get("native_source_closure_file_count", "0"))),
        name="native_source_closure_file_count",
        minimum=2,
        maximum=100_000,
    )
    if extension_path is None:
        if not test_double:
            raise DockingSearchV2Error(
                "native docking-search extension path is missing"
            )
        extension_sha256 = "0" * 64
    else:
        extension_sha256 = _sha256_path(extension_path)
    projection: dict[str, object] = {
        "schema_id": DOCKING_SEARCH_V2_NATIVE_RECEIPT_SCHEMA_ID,
        "backend_id": required["backend_id"],
        "backend_version": required["backend_version"],
        "distribution_version": distribution_version,
        "extension_sha256": extension_sha256,
        "cargo_lock_sha256": cargo_lock_sha256,
        "native_source_closure_sha256": source_closure_sha256,
        "native_source_closure_file_count": source_file_count,
        "rustc_version": required["rustc_version"],
        "target_triple": required["target_triple"],
        "build_profile": required["build_profile"],
        "opt_level": required["opt_level"],
        "debug": required["debug"],
        "panic_strategy": required["panic_strategy"],
        "build_flags": required["build_flags"],
        "cargo_features": required["cargo_features"],
        "docking_search_schema_id": required["docking_search_schema_id"],
        "docking_search_receipt_schema_id": required[
            "docking_search_receipt_schema_id"
        ],
        "docking_search_evaluator_id": required["docking_search_evaluator_id"],
        "implicit_fallback_allowed": False,
        "test_double": test_double,
    }
    projection["receipt_sha256"] = _sha256(projection)
    return MappingProxyType(projection)


def _load_native_binding() -> _NativeBinding:
    try:
        module = import_module("betelgeuze_engine_v2_native")
    except (ImportError, OSError) as exc:
        raise DockingSearchV2Error(
            "required native docking-search extension is unavailable"
        ) from exc
    extension_module = getattr(module, "betelgeuze_engine_v2_native", module)
    module_path = Path(str(getattr(extension_module, "__file__", ""))).resolve()
    if not module_path.is_file() or not any(
        module_path.name.endswith(suffix) for suffix in machinery.EXTENSION_SUFFIXES
    ):
        raise DockingSearchV2Error("docking-search backend is not a native extension")
    try:
        distribution_version = metadata.version("betelgeuze-engine-v2-native")
    except metadata.PackageNotFoundError as exc:
        raise DockingSearchV2Error(
            "native docking-search distribution identity is missing"
        ) from exc
    if distribution_version != DOCKING_SEARCH_V2_NATIVE_DISTRIBUTION_VERSION:
        raise DockingSearchV2Error(
            "native docking-search distribution version is not rc6"
        )
    receipt = _native_build_receipt(
        module,
        extension_path=module_path,
        distribution_version=distribution_version,
        test_double=False,
    )
    return _NativeBinding(module=module, receipt=receipt)


@dataclass(frozen=True, slots=True)
class DockingSearchV2Result:
    input_fingerprint_sha256: str
    candidate_rows: tuple[DockingSearchV2CandidateRow, ...]
    poses: tuple[DockingSearchV2Pose, ...]
    search_receipt: Mapping[str, object]
    native_backend_receipt: Mapping[str, object]
    schema_id: str = field(init=False, default=DOCKING_SEARCH_V2_RESULT_SCHEMA_ID)
    algorithm_id: str = field(init=False, default=DOCKING_SEARCH_V2_ALGORITHM_ID)
    claim_safe: bool = field(init=False, default=False)
    claim_blockers: tuple[str, ...] = field(
        init=False, default=DOCKING_SEARCH_V2_CLAIM_BLOCKERS
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": self.algorithm_id,
            "claim_safe": self.claim_safe,
            "claim_blockers": list(self.claim_blockers),
            "input_fingerprint_sha256": self.input_fingerprint_sha256,
            "candidate_rows": [row.to_dict() for row in self.candidate_rows],
            "poses": [pose.to_dict() for pose in self.poses],
            "search_receipt": dict(self.search_receipt),
            "native_backend_receipt": dict(self.native_backend_receipt),
        }


def _key_identity(key: Mapping[str, int | None]) -> tuple[int | None, ...]:
    return (
        key["orientation_index"],
        key["primary_surface_id"],
        key["primary_ligand_anchor_id"],
        key["secondary_surface_id"],
        key["secondary_ligand_anchor_id"],
    )


def _sha256_text(value: object, *, name: str) -> str:
    text = str(value)
    if _SHA256_RE.fullmatch(text) is None:
        raise DockingSearchV2Error(f"{name} must be a lowercase SHA-256")
    return text


class _CanonicalSearchSha256:
    """Rust-compatible canonical binary SHA-256 projection."""

    __slots__ = ("_digest",)

    def __init__(self, domain: str) -> None:
        self._digest = hashlib.sha256()
        self.string(domain)

    def byte(self, value: int) -> None:
        self._digest.update(bytes((value,)))

    def boolean(self, value: bool) -> None:
        self.byte(1 if value else 0)

    def u32(self, value: int) -> None:
        self._digest.update(value.to_bytes(4, "big", signed=False))

    def u64(self, value: int) -> None:
        self._digest.update(value.to_bytes(8, "big", signed=False))

    def usize(self, value: int) -> None:
        self.u64(value)

    def f64(self, value: float) -> None:
        self._digest.update(struct.pack(">d", 0.0 if value == 0.0 else value))

    def raw(self, value: bytes) -> None:
        self._digest.update(value)

    def sized_bytes(self, value: bytes) -> None:
        self.usize(len(value))
        self.raw(value)

    def string(self, value: str) -> None:
        self.sized_bytes(value.encode("utf-8"))

    def fixed_sha256(self, value: str) -> None:
        self.raw(bytes.fromhex(value))

    def hexdigest(self) -> str:
        return self._digest.hexdigest()


_PLACEMENT_MODE_CODE = {"dual_anchor": 0, "single_anchor_fallback": 1}
_CANDIDATE_STATUS_CODE = {
    "coarse_pruned": 0,
    "detailed_pruned": 1,
    "refinement_failed": 2,
    "physical_rejected": 3,
    "cluster_member": 4,
    "cluster_representative": 5,
    "top_k": 6,
}
_CANDIDATE_REASON_CODE = {
    "coarse_budget": 0,
    "detailed_budget": 1,
    "evaluator_failure": 2,
    "non_finite_evaluation": 3,
    "non_finite_coordinate": 4,
    "coordinate_out_of_bounds": 5,
    "ligand_self_overlap": 6,
    "receptor_clash": 7,
    "clustered_into_representative": 8,
    "top_k_budget": 9,
}


def _canonical_direction(value: Sequence[float]) -> tuple[float, float, float]:
    maximum = max(abs(value[0]), abs(value[1]), abs(value[2]))
    if not math.isfinite(maximum) or maximum <= 1.0e-12:
        raise DockingSearchV2Error("canonical search direction is invalid")
    inverse_maximum = 1.0 / maximum
    return tuple(  # type: ignore[return-value]
        component * inverse_maximum for component in value
    )


def _hash_vec3(digest: _CanonicalSearchSha256, value: Sequence[float]) -> None:
    digest.f64(value[0])
    digest.f64(value[1])
    digest.f64(value[2])


def _hash_candidate_key(
    digest: _CanonicalSearchSha256,
    key: Mapping[str, int | None],
) -> None:
    digest.u32(int(key["orientation_index"]))
    digest.u32(int(key["primary_surface_id"]))
    digest.u32(int(key["primary_ligand_anchor_id"]))
    _hash_optional_u32(digest, key["secondary_surface_id"])
    _hash_optional_u32(digest, key["secondary_ligand_anchor_id"])


def _hash_optional_u32(digest: _CanonicalSearchSha256, value: int | None) -> None:
    digest.byte(0 if value is None else 1)
    if value is not None:
        digest.u32(value)


def _hash_optional_usize(digest: _CanonicalSearchSha256, value: int | None) -> None:
    digest.byte(0 if value is None else 1)
    if value is not None:
        digest.usize(value)


def _hash_optional_f64(digest: _CanonicalSearchSha256, value: float | None) -> None:
    digest.byte(0 if value is None else 1)
    if value is not None:
        digest.f64(value)


def _hash_optional_bool(digest: _CanonicalSearchSha256, value: bool | None) -> None:
    digest.byte(0 if value is None else 1)
    if value is not None:
        digest.boolean(value)


def _hash_optional_string(digest: _CanonicalSearchSha256, value: str | None) -> None:
    digest.byte(0 if value is None else 1)
    if value is not None:
        digest.string(value)


def _search_config_sha256(config: DockingSearchV2Config) -> str:
    digest = _CanonicalSearchSha256("betelgeuze.docking_search_config/canonical-v2")
    for value in (
        config.orientation_count,
        config.generated_candidate_limit,
        config.coarse_keep,
        config.refinement_keep,
        config.top_k,
    ):
        digest.usize(value)
    digest.f64(config.placement_clearance_angstrom)
    digest.f64(config.dual_anchor_distance_tolerance_angstrom)
    digest.f64(config.coarse_clash_weight)
    digest.usize(config.refinement_steps)
    for value in (
        config.translation_step_angstrom2_per_kcal,
        config.rotation_step_per_torque,
        config.maximum_translation_step_angstrom,
        config.maximum_rotation_step_radians,
        config.maximum_absolute_coordinate_angstrom,
        config.minimum_ligand_atom_distance_angstrom,
        config.minimum_receptor_clearance_scale,
        config.cluster_rmsd_angstrom,
    ):
        digest.f64(value)
    return digest.hexdigest()


def _short_range_config_sha256(config: DockingShortRangeV2Config) -> str:
    digest = _CanonicalSearchSha256("betelgeuze.short_range_config/canonical-v1")
    for value in (
        config.ligand_shape_force_constant_kcal_per_mol_angstrom2,
        config.cutoff_angstrom,
        config.switch_start_angstrom,
        config.softcore_angstrom,
        config.dielectric,
    ):
        digest.f64(value)
    return digest.hexdigest()


def _search_input_sha256(search_input: DockingSearchV2Input) -> str:
    digest = _CanonicalSearchSha256("betelgeuze.docking_search_input/canonical-v2")
    digest.raw(bytes.fromhex(str(search_input.source_seed)))
    digest.usize(len(search_input.ligand_coordinates_angstrom))
    for position, radius, epsilon, charge in zip(
        search_input.ligand_coordinates_angstrom,
        search_input.ligand_vdw_radii_angstrom,
        search_input.ligand_epsilon_kcal_per_mol,
        search_input.ligand_charge_elementary,
        strict=True,
    ):
        _hash_vec3(digest, position)
        digest.f64(radius)
        digest.f64(epsilon)
        digest.f64(charge)

    anchors = sorted(
        zip(
            search_input.ligand_anchor_ids,
            search_input.ligand_anchor_atom_indices,
            search_input.ligand_anchor_directions,
            search_input.ligand_anchor_kinds,
            strict=True,
        ),
        key=lambda row: row[0],
    )
    digest.usize(len(anchors))
    for anchor_id, atom_index, direction, kind in anchors:
        digest.u32(anchor_id)
        digest.usize(atom_index)
        _hash_vec3(digest, _canonical_direction(direction))
        digest.byte(kind.native_code)

    receptor_rows = sorted(
        zip(
            search_input.receptor_coordinates_angstrom,
            search_input.receptor_vdw_radii_angstrom,
            search_input.receptor_epsilon_kcal_per_mol,
            search_input.receptor_charge_elementary,
            strict=True,
        ),
        key=lambda row: tuple(
            0.0 if value == 0.0 else value
            for value in (*row[0], row[1], row[2], row[3])
        ),
    )
    digest.usize(len(receptor_rows))
    for position, radius, epsilon, charge in receptor_rows:
        _hash_vec3(digest, position)
        digest.f64(radius)
        digest.f64(epsilon)
        digest.f64(charge)

    surfaces = sorted(
        zip(
            search_input.surface_ids,
            search_input.surface_positions_angstrom,
            search_input.surface_outward_normals,
            search_input.surface_anchor_kinds,
            strict=True,
        ),
        key=lambda row: row[0],
    )
    digest.usize(len(surfaces))
    for surface_id, position, normal, kind in surfaces:
        digest.u32(surface_id)
        _hash_vec3(digest, position)
        _hash_vec3(digest, _canonical_direction(normal))
        digest.byte(kind.native_code)
    return digest.hexdigest()


def _radical_inverse(index: int, base: int) -> float:
    inverse_base = 1.0 / float(base)
    fraction = inverse_base
    value = 0.0
    while index != 0:
        digit = index % base
        index //= base
        value += float(digit) * fraction
        fraction *= inverse_base
    return value


def _canonical_expected_quaternion(
    quaternion: Sequence[float],
) -> tuple[float, float, float, float]:
    maximum = max(abs(component) for component in quaternion)
    scaled_norm = math.hypot(
        math.hypot(
            math.hypot(quaternion[0] / maximum, quaternion[1] / maximum),
            quaternion[2] / maximum,
        ),
        quaternion[3] / maximum,
    )
    norm = maximum * scaled_norm
    inverse = 1.0 if abs(norm - 1.0) <= 1.0e-15 else (1.0 / maximum) / scaled_norm
    output = [component * inverse for component in quaternion]
    for component in reversed(output):
        if component > 0.0:
            break
        if component < 0.0:
            output = [-item for item in output]
            break
    return tuple(0.0 if item == 0.0 else item for item in output)  # type: ignore[return-value]


def _expected_orientation_quaternion(
    raw_sequence_index: int, offsets: Sequence[float]
) -> tuple[float, float, float, float]:
    unit_values = []
    for index, base in enumerate(_LOW_DISCREPANCY_ORIENTATION_BASES):
        shifted = _radical_inverse(raw_sequence_index, base) + offsets[index]
        # Rust's f64::fract is `self - self.trunc()`; mirror that operation
        # rather than Python's modulo implementation at the wrap boundary.
        unit_values.append(shifted - math.trunc(shifted))
    unit = tuple(unit_values)
    first_radius = math.sqrt(max(0.0, 1.0 - unit[0]))
    second_radius = math.sqrt(max(0.0, unit[0]))
    first_angle = 2.0 * math.pi * unit[1]
    second_angle = 2.0 * math.pi * unit[2]
    return _canonical_expected_quaternion(
        (
            first_radius * math.sin(first_angle),
            first_radius * math.cos(first_angle),
            second_radius * math.sin(second_angle),
            second_radius * math.cos(second_angle),
        )
    )


def _quaternion_geodesic_distance(
    left: Sequence[float], right: Sequence[float]
) -> float:
    dot = math.fsum(
        left_component * right_component
        for left_component, right_component in zip(left, right, strict=True)
    )
    sign = -1.0 if dot < 0.0 else 1.0
    difference = math.sqrt(
        math.fsum(
            (left_component - sign * right_component) ** 2
            for left_component, right_component in zip(left, right, strict=True)
        )
    )
    total = math.sqrt(
        math.fsum(
            (left_component + sign * right_component) ** 2
            for left_component, right_component in zip(left, right, strict=True)
        )
    )
    return (
        0.0
        if difference <= 1.0e-12 and total <= 1.0e-12
        else 4.0 * math.atan2(difference, total)
    )


def _validate_orientation_prefix_semantics(
    material: Sequence[tuple[int, int, Sequence[float]]], *, source_seed: str
) -> None:
    seed = bytes.fromhex(_source_seed_hex(source_seed))
    offsets = tuple(
        float(int.from_bytes(seed[offset : offset + 8], "big")) / _TWO_POW_64
        for offset in range(0, 24, 8)
    )
    accepted: list[tuple[float, float, float, float]] = []
    maximum_attempts = len(material) * _MAX_RAW_ATTEMPTS_PER_ORIENTATION
    for raw_sequence_index in range(maximum_attempts):
        expected = _expected_orientation_quaternion(raw_sequence_index, offsets)
        if any(
            _quaternion_geodesic_distance(expected, existing)
            <= _ORIENTATION_DUPLICATE_TOLERANCE_RADIANS
            for existing in accepted
        ):
            continue
        orientation_index = len(accepted)
        returned_index, returned_raw_index, returned_quaternion = material[
            orientation_index
        ]
        if (
            returned_index != orientation_index
            or returned_raw_index != raw_sequence_index
        ):
            raise DockingSearchV2Error(
                "native orientation material is not the seed-derived canonical "
                "accepted prefix"
            )
        if (
            _quaternion_geodesic_distance(returned_quaternion, expected)
            > _ORIENTATION_SEMANTIC_TOLERANCE_RADIANS
        ):
            raise DockingSearchV2Error(
                "native orientation material quaternion does not match its "
                "seed-derived Halton/Shoemake orientation"
            )
        accepted.append(expected)
        if len(accepted) == len(material):
            return
    raise DockingSearchV2Error(
        "native orientation material did not complete its seed-derived "
        "canonical accepted prefix"
    )


def _orientation_material(
    value: object, *, expected_count: int, source_seed: str
) -> tuple[tuple[int, int, tuple[float, float, float, float]], ...]:
    rows = _plain_sequence(value, name="native orientation material")
    if len(rows) != expected_count or len(rows) > MAX_DOCKING_SEARCH_V2_ORIENTATIONS:
        raise DockingSearchV2Error(
            "native orientation material count disagrees with the request"
        )
    maximum_raw_index = expected_count * _MAX_RAW_ATTEMPTS_PER_ORIENTATION - 1
    output: list[tuple[int, int, tuple[float, float, float, float]]] = []
    previous_raw_index = -1
    for row_index, raw_row in enumerate(rows):
        row = _exact_mapping(
            raw_row,
            name=f"native orientation material[{row_index}]",
            keys=_ORIENTATION_MATERIAL_KEYS,
        )
        orientation_index = _exact_int(
            row["orientation_index"],
            name=f"native orientation material[{row_index}].orientation_index",
            minimum=0,
            maximum=2**32 - 1,
        )
        if orientation_index != row_index:
            raise DockingSearchV2Error(
                "native orientation material is not in canonical index order"
            )
        raw_sequence_index = _exact_int(
            row["raw_sequence_index"],
            name=f"native orientation material[{row_index}].raw_sequence_index",
            minimum=0,
            maximum=maximum_raw_index,
        )
        if raw_sequence_index <= previous_raw_index:
            raise DockingSearchV2Error(
                "native orientation raw sequence indices are not strictly increasing"
            )
        previous_raw_index = raw_sequence_index

        raw_quaternion = _plain_sequence(
            row["quaternion"],
            name=f"native orientation material[{row_index}].quaternion",
        )
        if len(raw_quaternion) != 4:
            raise DockingSearchV2Error(
                "native orientation material quaternion must have four components"
            )
        quaternion = tuple(
            _finite_float(
                component,
                name=(f"native orientation material[{row_index}].quaternion[{axis}]"),
                minimum=-1.0,
                maximum=1.0,
            )
            for axis, component in enumerate(raw_quaternion)
        )
        if any(
            component == 0.0 and math.copysign(1.0, component) < 0.0
            for component in quaternion
        ):
            raise DockingSearchV2Error(
                "native orientation material contains non-canonical signed zero"
            )
        maximum = max(abs(component) for component in quaternion)
        if maximum <= 1.0e-12:
            raise DockingSearchV2Error(
                "native orientation material quaternion must be non-zero"
            )
        norm = maximum * math.sqrt(
            math.fsum((component / maximum) ** 2 for component in quaternion)
        )
        if abs(norm - 1.0) > 4.0e-15:
            raise DockingSearchV2Error(
                "native orientation material quaternion is not unit length"
            )
        for component in reversed(quaternion):
            if component > 0.0:
                break
            if component < 0.0:
                raise DockingSearchV2Error(
                    "native orientation material quaternion sign is not canonical"
                )

        for _, _, existing in output:
            if (
                _quaternion_geodesic_distance(quaternion, existing)
                <= _ORIENTATION_DUPLICATE_TOLERANCE_RADIANS
            ):
                raise DockingSearchV2Error(
                    "native orientation material contains a duplicate quaternion"
                )
        output.append((orientation_index, raw_sequence_index, quaternion))
    result = tuple(output)
    _validate_orientation_prefix_semantics(result, source_seed=source_seed)
    return result


def _orientation_sha256(
    orientation_material: Sequence[tuple[int, int, Sequence[float]]],
) -> str:
    """Hash native-produced SO(3) material without re-running platform libm."""

    digest = _CanonicalSearchSha256(
        "betelgeuze.docking_orientation_prefix/canonical-v2"
    )
    digest.usize(len(orientation_material))
    for orientation_index, raw_sequence_index, quaternion in orientation_material:
        digest.u32(orientation_index)
        digest.u64(raw_sequence_index)
        for component in quaternion:
            digest.f64(component)
    return digest.hexdigest()


def _allocation_sha256(
    candidate_rows: Sequence[DockingSearchV2CandidateRow],
) -> str:
    digest = _CanonicalSearchSha256(
        "betelgeuze.docking_candidate_allocation/canonical-v2"
    )
    digest.usize(len(candidate_rows))
    for row in candidate_rows:
        digest.usize(row.slot_index)
        _hash_candidate_key(digest, row.key)
        digest.byte(_PLACEMENT_MODE_CODE[row.placement_mode])
    return digest.hexdigest()


def _candidate_rows_sha256(
    candidate_rows: Sequence[DockingSearchV2CandidateRow],
) -> str:
    digest = _CanonicalSearchSha256("betelgeuze.docking_candidate_rows/canonical-v2")
    digest.usize(len(candidate_rows))
    for row in candidate_rows:
        digest.usize(row.slot_index)
        _hash_candidate_key(digest, row.key)
        digest.byte(_PLACEMENT_MODE_CODE[row.placement_mode])
        digest.byte(_CANDIDATE_STATUS_CODE[row.status])
        digest.byte(0 if row.reason is None else 1)
        if row.reason is not None:
            digest.byte(_CANDIDATE_REASON_CODE[row.reason])
        _hash_optional_string(digest, row.detail)
        digest.usize(len(row.coordinates_angstrom))
        for coordinate in row.coordinates_angstrom:
            _hash_vec3(digest, coordinate)
        digest.f64(row.anchor_fit_rmsd_angstrom)
        _hash_optional_f64(digest, row.coarse_score)
        _hash_optional_f64(digest, row.detailed_score)
        _hash_optional_f64(digest, row.energy_kcal_per_mol)
        _hash_optional_bool(digest, row.physically_valid)
        _hash_optional_f64(digest, row.minimum_receptor_gap_angstrom)
        _hash_optional_usize(digest, row.cluster_id)
        _hash_optional_usize(digest, row.final_rank)
    return digest.hexdigest()


def _poses_sha256(poses: Sequence[DockingSearchV2Pose]) -> str:
    digest = _CanonicalSearchSha256("betelgeuze.docking_ranked_poses/canonical-v2")
    digest.usize(len(poses))
    for pose in poses:
        digest.usize(pose.rank)
        _hash_candidate_key(digest, pose.key)
        digest.usize(len(pose.coordinates_angstrom))
        for coordinate in pose.coordinates_angstrom:
            _hash_vec3(digest, coordinate)
        digest.f64(pose.energy_kcal_per_mol)
        digest.usize(pose.cluster_size)
        _hash_optional_f64(digest, pose.minimum_receptor_gap_angstrom)
    return digest.hexdigest()


def _search_receipt_sha256(receipt: Mapping[str, object]) -> str:
    digest = _CanonicalSearchSha256("betelgeuze.docking_search_receipt/canonical-v2")
    digest.string(str(receipt["schema_id"]))
    digest.string(str(receipt["evaluator_id"]))
    for name in ("evaluator_config_sha256", "config_sha256", "input_sha256"):
        digest.fixed_sha256(str(receipt[name]))
    digest.boolean(bool(receipt["result_independent_allocation"]))
    digest.byte(_PLACEMENT_MODE_CODE[str(receipt["placement_mode"])])
    for name in (
        "requested_orientation_count",
        "accepted_orientation_count",
    ):
        digest.usize(int(receipt[name]))
    digest.u64(int(receipt["raw_orientation_attempt_count"]))
    for name in (
        "compatible_single_anchor_pair_count",
        "compatible_dual_anchor_combination_count",
        "used_anchor_combination_count",
    ):
        digest.usize(int(receipt[name]))
    digest.u64(int(receipt["possible_candidate_slot_count"]))
    for name in ("generated_candidate_limit", "allocated_candidate_slot_count"):
        digest.usize(int(receipt[name]))
    for name in (
        "allocation_sha256",
        "orientation_sha256",
        "candidate_rows_sha256",
        "poses_sha256",
    ):
        digest.fixed_sha256(str(receipt[name]))
    for name in (
        "coarse_keep_budget",
        "coarse_kept_count",
        "refinement_keep_budget",
        "refinement_selected_count",
        "refinement_steps_per_candidate",
        "refinement_succeeded_count",
        "refinement_evaluator_failed_count",
        "refinement_non_finite_failed_count",
        "evaluator_call_count",
        "maximum_evaluator_call_count",
        "physical_valid_count",
        "rejected_non_finite_coordinate_count",
        "rejected_coordinate_out_of_bounds_count",
        "rejected_ligand_self_overlap_count",
        "rejected_receptor_clash_count",
        "cluster_count",
        "top_k_budget",
        "returned_pose_count",
    ):
        digest.usize(int(receipt[name]))
    return digest.hexdigest()


def _validate_search_receipt(
    raw_receipt: object,
    *,
    orientation_material: tuple[
        tuple[int, int, tuple[float, float, float, float]], ...
    ],
    candidate_rows: tuple[DockingSearchV2CandidateRow, ...],
    poses: tuple[DockingSearchV2Pose, ...],
    search_input: DockingSearchV2Input,
    config: DockingSearchV2Config,
    short_range_config: DockingShortRangeV2Config,
) -> Mapping[str, object]:
    raw = _exact_mapping(
        raw_receipt,
        name="native search receipt",
        keys=_SEARCH_RECEIPT_KEYS,
    )
    if raw["schema_id"] != DOCKING_SEARCH_V2_CORE_RECEIPT_SCHEMA_ID:
        raise DockingSearchV2Error("native search receipt schema is invalid")
    if raw["evaluator_id"] != "betelgeuze_short_range_analytic/1.0.0":
        raise DockingSearchV2Error(
            "native search receipt evaluator identity is invalid"
        )
    if (
        type(raw["result_independent_allocation"]) is not bool
        or not raw["result_independent_allocation"]
    ):
        raise DockingSearchV2Error("native search allocation is not result independent")
    placement_mode = str(raw["placement_mode"])
    if placement_mode not in {"dual_anchor", "single_anchor_fallback"}:
        raise DockingSearchV2Error("native search receipt placement mode is invalid")

    digest_fields = (
        "evaluator_config_sha256",
        "config_sha256",
        "input_sha256",
        "allocation_sha256",
        "orientation_sha256",
        "candidate_rows_sha256",
        "poses_sha256",
        "receipt_sha256",
    )
    digests = {
        name: _sha256_text(raw[name], name=f"receipt.{name}") for name in digest_fields
    }
    integer_fields = tuple(
        _SEARCH_RECEIPT_KEYS
        - {
            "schema_id",
            "evaluator_id",
            "result_independent_allocation",
            "placement_mode",
            *digest_fields,
        }
    )
    integers = {
        name: _exact_int(
            raw[name],
            name=f"receipt.{name}",
            minimum=0,
            maximum=2**64 - 1,
        )
        for name in integer_fields
    }
    for positive_name in (
        "requested_orientation_count",
        "accepted_orientation_count",
        "used_anchor_combination_count",
        "possible_candidate_slot_count",
        "generated_candidate_limit",
        "allocated_candidate_slot_count",
        "coarse_keep_budget",
        "refinement_keep_budget",
        "top_k_budget",
    ):
        if integers[positive_name] == 0:
            raise DockingSearchV2Error(f"receipt.{positive_name} must be positive")

    expected_config = {
        "requested_orientation_count": config.orientation_count,
        "generated_candidate_limit": config.generated_candidate_limit,
        "coarse_keep_budget": config.coarse_keep,
        "refinement_keep_budget": config.refinement_keep,
        "refinement_steps_per_candidate": config.refinement_steps,
        "top_k_budget": config.top_k,
    }
    if any(integers[name] != expected for name, expected in expected_config.items()):
        raise DockingSearchV2Error(
            "native search receipt disagrees with requested budgets"
        )
    if integers["accepted_orientation_count"] != integers[
        "requested_orientation_count"
    ] or integers["accepted_orientation_count"] != len(orientation_material):
        raise DockingSearchV2Error(
            "native search receipt orientation count is inconsistent"
        )
    if integers["raw_orientation_attempt_count"] != (orientation_material[-1][1] + 1):
        raise DockingSearchV2Error(
            "native search receipt orientation denominator is invalid"
        )
    if integers["allocated_candidate_slot_count"] != min(
        integers["generated_candidate_limit"],
        integers["possible_candidate_slot_count"],
    ):
        raise DockingSearchV2Error(
            "native allocated candidate denominator is inconsistent"
        )
    if integers["allocated_candidate_slot_count"] != len(candidate_rows):
        raise DockingSearchV2Error(
            "native candidate ledger count disagrees with receipt"
        )
    mode_combination_count = (
        integers["compatible_dual_anchor_combination_count"]
        if placement_mode == "dual_anchor"
        else integers["compatible_single_anchor_pair_count"]
    )
    if integers["possible_candidate_slot_count"] != (
        integers["accepted_orientation_count"] * mode_combination_count
    ):
        raise DockingSearchV2Error(
            "native possible candidate denominator is inconsistent"
        )
    used_combinations = {
        (
            row.key["primary_surface_id"],
            row.key["primary_ligand_anchor_id"],
            row.key["secondary_surface_id"],
            row.key["secondary_ligand_anchor_id"],
        )
        for row in candidate_rows
    }
    if integers["used_anchor_combination_count"] != len(used_combinations):
        raise DockingSearchV2Error(
            "native used anchor-combination count is inconsistent"
        )

    status_count = {
        status: sum(row.status == status for row in candidate_rows)
        for status in _CORE_STATUS_VALUES
    }
    reason_count = {
        reason: sum(row.reason == reason for row in candidate_rows)
        for reason in _CORE_REASON_VALUES
    }
    derived_coarse_kept = len(candidate_rows) - status_count["coarse_pruned"]
    derived_refinement_selected = derived_coarse_kept - status_count["detailed_pruned"]
    derived_refinement_succeeded = (
        derived_refinement_selected - status_count["refinement_failed"]
    )
    derived_physical_valid = (
        status_count["cluster_member"]
        + status_count["cluster_representative"]
        + status_count["top_k"]
    )
    derived = {
        "coarse_kept_count": derived_coarse_kept,
        "refinement_selected_count": derived_refinement_selected,
        "refinement_succeeded_count": derived_refinement_succeeded,
        "refinement_evaluator_failed_count": reason_count["evaluator_failure"],
        "refinement_non_finite_failed_count": reason_count["non_finite_evaluation"],
        "physical_valid_count": derived_physical_valid,
        "rejected_non_finite_coordinate_count": reason_count["non_finite_coordinate"],
        "rejected_coordinate_out_of_bounds_count": reason_count[
            "coordinate_out_of_bounds"
        ],
        "rejected_ligand_self_overlap_count": reason_count["ligand_self_overlap"],
        "rejected_receptor_clash_count": reason_count["receptor_clash"],
        "returned_pose_count": status_count["top_k"],
    }
    if any(integers[name] != expected for name, expected in derived.items()):
        raise DockingSearchV2Error(
            "native search receipt disagrees with candidate ledger"
        )
    if integers["coarse_kept_count"] != min(
        integers["coarse_keep_budget"], len(candidate_rows)
    ) or integers["refinement_selected_count"] != min(
        integers["refinement_keep_budget"], integers["coarse_kept_count"]
    ):
        raise DockingSearchV2Error(
            "native pruning budget denominators are inconsistent"
        )
    expected_maximum_calls = integers["refinement_selected_count"] * (
        integers["refinement_steps_per_candidate"] + 1
    )
    if integers["maximum_evaluator_call_count"] != expected_maximum_calls or not (
        integers["refinement_selected_count"]
        <= integers["evaluator_call_count"]
        <= expected_maximum_calls
    ):
        raise DockingSearchV2Error("native evaluator call denominator is inconsistent")

    cluster_ids = {
        row.cluster_id for row in candidate_rows if row.cluster_id is not None
    }
    if cluster_ids != set(range(1, integers["cluster_count"] + 1)):
        raise DockingSearchV2Error("native cluster identities are not canonical")
    if integers["returned_pose_count"] != min(
        integers["top_k_budget"], integers["cluster_count"]
    ) or integers["returned_pose_count"] != len(poses):
        raise DockingSearchV2Error("native Top-K receipt denominator is inconsistent")
    if any(row.placement_mode != placement_mode for row in candidate_rows):
        raise DockingSearchV2Error("native placement mode disagrees across ledger rows")
    if placement_mode == "dual_anchor":
        if (
            integers["compatible_dual_anchor_combination_count"] == 0
            or not 1
            <= integers["used_anchor_combination_count"]
            <= integers["compatible_dual_anchor_combination_count"]
        ):
            raise DockingSearchV2Error("native dual-anchor denominator is inconsistent")
    elif (
        integers["compatible_dual_anchor_combination_count"] != 0
        or not 1
        <= integers["used_anchor_combination_count"]
        <= integers["compatible_single_anchor_pair_count"]
    ):
        raise DockingSearchV2Error("native fallback-anchor denominator is inconsistent")

    result: dict[str, object] = {
        "schema_id": DOCKING_SEARCH_V2_CORE_RECEIPT_SCHEMA_ID,
        "evaluator_id": "betelgeuze_short_range_analytic/1.0.0",
        "result_independent_allocation": True,
        "placement_mode": placement_mode,
        **digests,
        **integers,
    }
    expected_digests = {
        "evaluator_config_sha256": _short_range_config_sha256(short_range_config),
        "config_sha256": _search_config_sha256(config),
        "input_sha256": _search_input_sha256(search_input),
        "orientation_sha256": _orientation_sha256(orientation_material),
        "allocation_sha256": _allocation_sha256(candidate_rows),
        "candidate_rows_sha256": _candidate_rows_sha256(candidate_rows),
        "poses_sha256": _poses_sha256(poses),
    }
    mismatched = tuple(
        name for name, expected in expected_digests.items() if digests[name] != expected
    )
    if mismatched:
        raise DockingSearchV2Error(
            "native search receipt digest disagrees with canonical "
            + ", ".join(mismatched)
        )
    if digests["receipt_sha256"] != _search_receipt_sha256(result):
        raise DockingSearchV2Error(
            "native search receipt SHA-256 does not seal its canonical fields"
        )
    _canonical_bytes(result)
    return MappingProxyType(result)


def _result_from_native(
    value: object,
    *,
    search_input: DockingSearchV2Input,
    config: DockingSearchV2Config,
    short_range_config: DockingShortRangeV2Config,
    binding: _NativeBinding,
) -> DockingSearchV2Result:
    value = _exact_mapping(
        value, name="native docking-search result", keys=_RESULT_KEYS
    )
    if value["schema_id"] != DOCKING_SEARCH_V2_CORE_SCHEMA_ID:
        raise DockingSearchV2Error("native docking-search result schema is invalid")
    orientation_material = _orientation_material(
        value.get("orientation_material"),
        expected_count=config.orientation_count,
        source_seed=str(search_input.source_seed),
    )
    raw_candidate_rows = value.get("candidate_rows")
    raw_poses = value.get("poses")
    raw_receipt = value.get("receipt")
    if (
        not isinstance(raw_candidate_rows, Sequence)
        or isinstance(raw_candidate_rows, (str, bytes))
        or not isinstance(raw_poses, Sequence)
        or isinstance(raw_poses, (str, bytes))
        or not isinstance(raw_receipt, Mapping)
    ):
        raise DockingSearchV2Error("native docking-search rows or receipt are invalid")
    if len(raw_candidate_rows) > MAX_DOCKING_SEARCH_V2_CANDIDATES:
        raise DockingSearchV2Error("native candidate row count exceeds its hard bound")
    if len(raw_poses) > MAX_DOCKING_SEARCH_V2_TOP_K:
        raise DockingSearchV2Error("native pose count exceeds its hard bound")
    candidate_rows = tuple(
        DockingSearchV2CandidateRow._from_native(
            row,
            ligand_count=len(search_input.ligand_coordinates_angstrom),
        )
        for row in raw_candidate_rows
    )
    if tuple(row.slot_index for row in candidate_rows) != tuple(
        range(len(candidate_rows))
    ):
        raise DockingSearchV2Error(
            "native candidate rows are not in canonical slot order"
        )
    ligand_anchor_ids = set(search_input.ligand_anchor_ids)
    surface_ids = set(search_input.surface_ids)
    for row in candidate_rows:
        if not 0 <= int(row.key["orientation_index"]) < len(orientation_material):
            raise DockingSearchV2Error(
                "native candidate orientation is outside the request"
            )
        ligand_ids = (
            row.key["primary_ligand_anchor_id"],
            row.key["secondary_ligand_anchor_id"],
        )
        receptor_surface_ids = (
            row.key["primary_surface_id"],
            row.key["secondary_surface_id"],
        )
        if any(
            value is not None and value not in ligand_anchor_ids for value in ligand_ids
        ):
            raise DockingSearchV2Error(
                "native candidate contains an invented ligand anchor"
            )
        if any(
            value is not None and value not in surface_ids
            for value in receptor_surface_ids
        ):
            raise DockingSearchV2Error(
                "native candidate contains an invented surface identity"
            )
    poses = tuple(
        DockingSearchV2Pose._from_native(
            row,
            ligand_count=len(search_input.ligand_coordinates_angstrom),
        )
        for row in raw_poses
    )
    if tuple(pose.rank for pose in poses) != tuple(range(1, len(poses) + 1)):
        raise DockingSearchV2Error("native poses are not in canonical rank order")
    key_identities = tuple(_key_identity(row.key) for row in candidate_rows)
    if len(set(key_identities)) != len(key_identities):
        raise DockingSearchV2Error("native candidate keys are not unique")
    top_k_by_rank = {
        row.final_rank: row for row in candidate_rows if row.status == "top_k"
    }
    if len(top_k_by_rank) != sum(row.status == "top_k" for row in candidate_rows):
        raise DockingSearchV2Error("native Top-K candidate ranks are not unique")
    for pose in poses:
        candidate = top_k_by_rank.get(pose.rank)
        if candidate is None or (
            _key_identity(candidate.key) != _key_identity(pose.key)
            or candidate.coordinates_angstrom != pose.coordinates_angstrom
            or candidate.energy_kcal_per_mol != pose.energy_kcal_per_mol
            or candidate.minimum_receptor_gap_angstrom
            != pose.minimum_receptor_gap_angstrom
        ):
            raise DockingSearchV2Error("native Top-K pose is not ledger-bound")
        if candidate.cluster_id is None or pose.cluster_size != sum(
            row.cluster_id == candidate.cluster_id for row in candidate_rows
        ):
            raise DockingSearchV2Error("native Top-K cluster size is not ledger-bound")
    receipt = _validate_search_receipt(
        raw_receipt,
        orientation_material=orientation_material,
        candidate_rows=candidate_rows,
        poses=poses,
        search_input=search_input,
        config=config,
        short_range_config=short_range_config,
    )
    return DockingSearchV2Result(
        input_fingerprint_sha256=search_input.fingerprint_sha256,
        candidate_rows=candidate_rows,
        poses=poses,
        search_receipt=receipt,
        native_backend_receipt=binding.receipt,
    )


def _anchor_kinds_compatible(
    ligand_kind: DockingAnchorKind,
    surface_kind: DockingAnchorKind,
) -> bool:
    return (ligand_kind, surface_kind) in {
        (
            DockingAnchorKind.HYDROGEN_BOND_DONOR,
            DockingAnchorKind.HYDROGEN_BOND_ACCEPTOR,
        ),
        (
            DockingAnchorKind.HYDROGEN_BOND_ACCEPTOR,
            DockingAnchorKind.HYDROGEN_BOND_DONOR,
        ),
        (DockingAnchorKind.HYDROPHOBE, DockingAnchorKind.HYDROPHOBE),
        (DockingAnchorKind.AROMATIC, DockingAnchorKind.AROMATIC),
        (DockingAnchorKind.POSITIVE, DockingAnchorKind.NEGATIVE),
        (DockingAnchorKind.NEGATIVE, DockingAnchorKind.POSITIVE),
    }


def _distance3(
    left: tuple[float, float, float], right: tuple[float, float, float]
) -> float:
    return math.hypot(
        left[0] - right[0],
        left[1] - right[1],
        left[2] - right[2],
    )


def _exact_anchor_combination_count(
    search_input: DockingSearchV2Input,
    config: DockingSearchV2Config,
) -> tuple[int, int]:
    """Return compatible singles and the exact geometry-valid proposal count."""
    singles = [
        (ligand_index, surface_index)
        for surface_index, surface_kind in enumerate(search_input.surface_anchor_kinds)
        for ligand_index, ligand_kind in enumerate(search_input.ligand_anchor_kinds)
        if _anchor_kinds_compatible(ligand_kind, surface_kind)
    ]
    compatible_single_count = len(singles)
    if compatible_single_count > MAX_DOCKING_SEARCH_V2_COMPATIBLE_SINGLE_ANCHOR_PAIRS:
        raise DockingSearchV2Error(
            "compatible single-anchor pairs exceed the composite hard cap"
        )
    if compatible_single_count == 0:
        # The core reports the canonical no-compatible-anchor error.  Keeping
        # this count at zero ensures preflight does not invent proposal work.
        return 0, 0

    ligand_positions = tuple(
        search_input.ligand_coordinates_angstrom[atom_index]
        for atom_index in search_input.ligand_anchor_atom_indices
    )
    surface_targets: list[tuple[float, float, float]] = []
    for position, normal in zip(
        search_input.surface_positions_angstrom,
        search_input.surface_outward_normals,
        strict=True,
    ):
        normal_length = math.hypot(*normal)
        surface_targets.append(
            (
                position[0]
                + normal[0] / normal_length * config.placement_clearance_angstrom,
                position[1]
                + normal[1] / normal_length * config.placement_clearance_angstrom,
                position[2]
                + normal[2] / normal_length * config.placement_clearance_angstrom,
            )
        )

    dual_count = 0
    tolerance = config.dual_anchor_distance_tolerance_angstrom
    for left_index, (left_ligand, left_surface) in enumerate(singles):
        for right_ligand, right_surface in singles[left_index + 1 :]:
            if left_ligand == right_ligand or left_surface == right_surface:
                continue
            source_distance = _distance3(
                ligand_positions[left_ligand], ligand_positions[right_ligand]
            )
            target_distance = _distance3(
                surface_targets[left_surface], surface_targets[right_surface]
            )
            if (
                source_distance <= 1.0e-12
                or target_distance <= 1.0e-12
                or abs(source_distance - target_distance) > tolerance
            ):
                continue
            dual_count += 1
            if dual_count > MAX_DOCKING_SEARCH_V2_ANCHOR_COMBINATIONS:
                raise DockingSearchV2Error(
                    "compatible dual-anchor combinations exceed the composite hard cap"
                )
    return compatible_single_count, dual_count or compatible_single_count


def _validate_composite_preflight(
    search_input: DockingSearchV2Input,
    config: DockingSearchV2Config,
) -> None:
    ligand_count = len(search_input.ligand_coordinates_angstrom)
    receptor_count = len(search_input.receptor_coordinates_angstrom)
    _, combination_count = _exact_anchor_combination_count(search_input, config)
    possible_upper = config.orientation_count * combination_count
    allocated_upper = min(config.generated_candidate_limit, possible_upper)
    candidate_coordinates = allocated_upper * ligand_count
    if candidate_coordinates > MAX_DOCKING_SEARCH_V2_CANDIDATE_COORDINATES:
        raise DockingSearchV2Error(
            "candidate coordinates exceed the composite hard cap"
        )
    coarse_count = min(config.coarse_keep, allocated_upper)
    refinement_count = min(config.refinement_keep, coarse_count)
    ledger_payload_bytes = (
        candidate_coordinates * 24
        + allocated_upper * 256
        + refinement_count * MAX_DOCKING_SEARCH_V2_EVALUATION_DETAIL_BYTES
        + min(config.top_k, refinement_count) * ligand_count * 24
    )
    if ledger_payload_bytes > MAX_DOCKING_SEARCH_V2_LEDGER_PAYLOAD_BYTES:
        raise DockingSearchV2Error("candidate ledger exceeds the composite byte cap")
    pose_count_upper = min(config.top_k, refinement_count)
    python_bridge_bytes = (
        (candidate_coordinates + pose_count_upper * ligand_count)
        * _PYTHON_BRIDGE_COORDINATE_ROW_BYTES
        + allocated_upper * _PYTHON_BRIDGE_CANDIDATE_ROW_BYTES
        + pose_count_upper * _PYTHON_BRIDGE_POSE_BYTES
        + config.orientation_count * _PYTHON_BRIDGE_ORIENTATION_ROW_BYTES
    )
    if python_bridge_bytes > MAX_DOCKING_SEARCH_V2_PYTHON_BRIDGE_BYTES:
        raise DockingSearchV2Error(
            "Python bridge output exceeds the composite byte cap"
        )
    ligand_receptor_pairs = ligand_count * receptor_count
    ligand_shape_pairs = ligand_count * max(ligand_count - 1, 0) // 2
    evaluator_pairs_per_call = ligand_receptor_pairs + ligand_shape_pairs
    evaluator_calls = refinement_count * (config.refinement_steps + 1)
    pair_evaluations = sum(
        (
            candidate_coordinates,
            allocated_upper * receptor_count,
            coarse_count * ligand_receptor_pairs,
            refinement_count * ligand_receptor_pairs,
            refinement_count * ligand_shape_pairs,
            evaluator_calls * evaluator_pairs_per_call,
        )
    )
    if pair_evaluations > MAX_DOCKING_SEARCH_V2_PAIR_EVALUATIONS:
        raise DockingSearchV2Error(
            "search work exceeds the composite pair-evaluation cap"
        )


def _run_with_binding(
    search_input: DockingSearchV2Input,
    config: DockingSearchV2Config,
    short_range_config: DockingShortRangeV2Config,
    binding: _NativeBinding,
) -> DockingSearchV2Result:
    if not isinstance(search_input, DockingSearchV2Input):
        raise DockingSearchV2Error("search_input must be DockingSearchV2Input")
    if not isinstance(config, DockingSearchV2Config):
        raise DockingSearchV2Error("config must be DockingSearchV2Config")
    if not isinstance(short_range_config, DockingShortRangeV2Config):
        raise DockingSearchV2Error(
            "short_range_config must be DockingShortRangeV2Config"
        )
    _validate_composite_preflight(search_input, config)
    maximum_coordinate = config.maximum_absolute_coordinate_angstrom
    for group_name, rows in (
        ("ligand", search_input.ligand_coordinates_angstrom),
        ("receptor", search_input.receptor_coordinates_angstrom),
        ("surface", search_input.surface_positions_angstrom),
    ):
        if any(
            abs(component) > maximum_coordinate for row in rows for component in row
        ):
            raise DockingSearchV2Error(
                f"{group_name} coordinate exceeds maximum_absolute_coordinate_angstrom"
            )
    arguments = search_input._native_arguments()
    arguments["search_config"] = config.to_native_dict()
    arguments["short_range_config"] = short_range_config.to_native_dict()
    try:
        raw_result = binding.module.docking_search_v2(**arguments)  # type: ignore[attr-defined]
    except Exception as exc:
        raise DockingSearchV2Error(f"native docking search v2 failed: {exc}") from exc
    return _result_from_native(
        raw_result,
        search_input=search_input,
        config=config,
        short_range_config=short_range_config,
        binding=binding,
    )


def run_docking_search_v2(
    search_input: DockingSearchV2Input,
    config: DockingSearchV2Config | None = None,
    short_range_config: DockingShortRangeV2Config | None = None,
) -> DockingSearchV2Result:
    """Run the native Rust search with no Python or external-solver fallback."""

    return _run_with_binding(
        search_input,
        DockingSearchV2Config() if config is None else config,
        DockingShortRangeV2Config()
        if short_range_config is None
        else short_range_config,
        _load_native_binding(),
    )


def _run_docking_search_v2_with_native_for_tests(
    search_input: DockingSearchV2Input,
    config: DockingSearchV2Config,
    short_range_config: DockingShortRangeV2Config,
    native_module: object,
) -> DockingSearchV2Result:
    """Inject a native-shaped double only while running a pytest unit test."""

    if "pytest" not in sys.modules:
        raise DockingSearchV2Error("native test-double injection is pytest-only")
    binding = _NativeBinding(
        module=native_module,
        receipt=_native_build_receipt(
            native_module,
            extension_path=None,
            distribution_version=DOCKING_SEARCH_V2_NATIVE_DISTRIBUTION_VERSION,
            test_double=True,
        ),
    )
    return _run_with_binding(search_input, config, short_range_config, binding)


__all__ = [
    "DOCKING_SEARCH_V2_ALGORITHM_ID",
    "DOCKING_SEARCH_V2_CLAIM_BLOCKERS",
    "DOCKING_SEARCH_V2_RESULT_SCHEMA_ID",
    "DockingAnchorKind",
    "DockingSearchV2CandidateRow",
    "DockingSearchV2Config",
    "DockingSearchV2Error",
    "DockingSearchV2Input",
    "DockingSearchV2Pose",
    "DockingSearchV2Result",
    "DockingShortRangeV2Config",
    "run_docking_search_v2",
]
