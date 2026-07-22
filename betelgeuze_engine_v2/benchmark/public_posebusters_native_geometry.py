"""Failure-inclusive native-pose geometry preflight for PoseBusters 308.

The source archive defines the native ligand as a crystal pose in the receptor
frame and the start conformer as an RDKit ETKDGv3 conformer minimized with UFF.
This module evaluates only fixed, unvalidated geometry heuristics: element-
radius receptor penetration, topology-excluded ligand self-overlap, and native
versus start heavy-bond length deviation.  It does not perceive chemistry,
validate a generated pose, execute docking, or reproduce the PoseBusters tool.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
import math
import os
import platform
from pathlib import Path
import tempfile
from typing import Any, Callable, Sequence
import zipfile

import torch

from betelgeuze_engine_v2.docking.flexible_geometric_scoring import (
    FlexibleGeometryDiagnosticScoreConfig,
)
from betelgeuze_engine_v2.docking.geometric_scoring import (
    GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM,
    GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256,
    ElementGeometryDiagnosticScoreConfig,
)
from betelgeuze_engine_v2.docking.validity import PoseValidityConfig
from betelgeuze_engine_v2.io import (
    PDBParseError,
    SDFParseError,
    parse_pdb,
    parse_sdf_v2000,
)

from .public_ligand_graph_audit import (
    PublicLigandHeavyGraphComparison,
    compare_public_ligand_heavy_atom_graphs,
)
from .public_materialization import PublicReferenceMaterializationError
from .public_posebusters_corpus_audit import (
    PoseBustersCorpusAuditError,
    PoseBustersCorpusAuditReceipt,
    _canonical_bytes,
    _canonical_sha256,
    _digest,
    _positive_int,
    _read_member,
    _source_file_sha256,
    _token,
    verify_posebusters_corpus_audit_receipt,
)
from .public_posebusters_intake import (
    OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    PoseBustersArchiveContract,
    PoseBustersArchiveIntakeError,
    _hash_descriptor,
    _read_exact_regular_file,
    _regular_file_descriptor,
    verify_posebusters_archive_intake_receipt,
)


POSEBUSTERS_NATIVE_GEOMETRY_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_native_geometry_case/1.0.0"
)
POSEBUSTERS_NATIVE_GEOMETRY_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_native_geometry_metric/1.0.0"
)
POSEBUSTERS_NATIVE_GEOMETRY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_native_geometry/1.0.0"
)
POSEBUSTERS_NATIVE_GEOMETRY_MAX_RECEIPT_BYTES = 4 * 1024 * 1024
POSEBUSTERS_NATIVE_GEOMETRY_MAX_CROSS_PAIRS = 4_000_000
POSEBUSTERS_NATIVE_GEOMETRY_RECEPTOR_CHUNK_ATOMS = 8_192
POSEBUSTERS_NATIVE_GEOMETRY_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_NATIVE_GEOMETRY_Z = 1.959963984540054
POSEBUSTERS_NATIVE_GEOMETRY_OVERLAP_SCALE = (
    ElementGeometryDiagnosticScoreConfig().overlap_contact_scale
)
POSEBUSTERS_NATIVE_GEOMETRY_DEEP_PENETRATION_SCALE = (
    ElementGeometryDiagnosticScoreConfig().deep_penetration_scale
)
POSEBUSTERS_NATIVE_GEOMETRY_LIGAND_SELF_OVERLAP_SCALE = (
    FlexibleGeometryDiagnosticScoreConfig().ligand_self_overlap_scale
)
POSEBUSTERS_NATIVE_GEOMETRY_BOND_DELTA_ANGSTROM = (
    PoseValidityConfig().bond_length_tolerance_angstrom
)
POSEBUSTERS_NATIVE_GEOMETRY_BLOCKERS = (
    "native_crystal_pose_positive_control_not_generated_pose_evidence",
    "fixed_element_radii_are_unvalidated_geometry_heuristics",
    "formal_and_partial_charge_not_used",
    "metal_and_cofactor_chemistry_not_interpreted",
    "covalent_ligand_attachment_not_interpreted",
    "explicit_hydrogen_completeness_not_established",
    "aromaticity_and_atom_stereo_not_perceived",
    "bond_delta_is_not_force_field_strain_energy",
    "posebusters_external_validity_oracle_not_executed",
    "pose_generation_scoring_ranking_and_redocking_not_executed",
    "target_family_and_leakage_receipts_missing",
    "independent_external_rerun_missing",
    "scientific_review_missing",
)
_CASE_STATUSES = {
    "evaluated",
    "partial_unsupported_element",
    "failure",
}
_SHA256_CHARACTERS = frozenset("0123456789abcdef")


class PoseBustersNativeGeometryError(ValueError):
    """PoseBusters native-geometry preflight failed closed."""


def _finite_hex(value: float, *, name: str) -> str:
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise PoseBustersNativeGeometryError(f"{name} must be finite and non-negative")
    return number.hex()


def _validate_optional_hex(value: object, *, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PoseBustersNativeGeometryError(f"{name} must be hexadecimal binary64")
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise PoseBustersNativeGeometryError(
            f"{name} must be hexadecimal binary64"
        ) from exc
    if not math.isfinite(number) or number < 0.0 or number.hex() != value:
        raise PoseBustersNativeGeometryError(
            f"{name} must be canonical finite non-negative binary64"
        )
    return value


def _validate_optional_index(value: object, *, name: str) -> int | None:
    if value is None:
        return None
    return _positive_int(value, name=name, allow_zero=True)


def _validate_optional_bool(value: object, *, name: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise PoseBustersNativeGeometryError(f"{name} must be boolean or null")
    return value


def _case_id(value: object) -> str:
    if not isinstance(value, str):
        raise PoseBustersNativeGeometryError("case ID must be text")
    result = value.strip()
    parts = result.split("_")
    if (
        len(parts) != 2
        or len(parts[0]) != 4
        or len(parts[1]) != 3
        or not all(
            part.isascii() and part.isalnum() and part.upper() == part
            for part in parts
        )
    ):
        raise PoseBustersNativeGeometryError(
            "case ID must use uppercase PDB4_CCD3 form"
        )
    return result


def _optional_atomic_number(value: object, *, name: str) -> int | None:
    result = _validate_optional_index(value, name=name)
    if result is not None and (result < 1 or result > 118):
        raise PoseBustersNativeGeometryError(f"{name} is outside [1,118]")
    return result


@dataclass(frozen=True, slots=True)
class PoseBustersNativeGeometryCase:
    case_id: str
    status: str
    error_code: str
    receptor_atom_count: int = 0
    native_ligand_atom_count: int = 0
    start_ligand_atom_count: int = 0
    cross_pair_count: int = 0
    unsupported_atomic_numbers: tuple[int, ...] = ()
    metal_atomic_numbers: tuple[int, ...] = ()
    nonwater_cofactor_residue_names: tuple[str, ...] = ()
    reference_ligand_residue_present_in_receptor: bool | None = None
    reference_scorer_chemistry_scope: bool | None = None
    receptor_ligand_geometry_evaluated: bool | None = None
    minimum_receptor_ligand_ratio_hex: str | None = None
    minimum_receptor_ligand_distance_angstrom_hex: str | None = None
    minimum_receptor_atom_index: int | None = None
    minimum_ligand_atom_index: int | None = None
    minimum_receptor_atomic_number: int | None = None
    minimum_ligand_atomic_number: int | None = None
    deep_penetration_free: bool | None = None
    overlap_free: bool | None = None
    ligand_self_pair_count: int = 0
    minimum_ligand_self_ratio_hex: str | None = None
    minimum_ligand_self_distance_angstrom_hex: str | None = None
    minimum_ligand_self_atom_i: int | None = None
    minimum_ligand_self_atom_j: int | None = None
    ligand_self_overlap_free: bool | None = None
    compared_heavy_bond_count: int = 0
    maximum_native_start_bond_delta_angstrom_hex: str | None = None
    maximum_bond_native_atom_i: int | None = None
    maximum_bond_native_atom_j: int | None = None
    maximum_bond_start_atom_i: int | None = None
    maximum_bond_start_atom_j: int | None = None
    bond_delta_within_tolerance: bool | None = None
    bounded_geometry_pass: bool | None = None
    bounded_geometry_and_reference_chemistry_scope: bool | None = None
    full_pose_validity_complete: bool = False
    schema_id: str = POSEBUSTERS_NATIVE_GEOMETRY_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_NATIVE_GEOMETRY_CASE_SCHEMA_ID:
            raise PoseBustersNativeGeometryError(
                "unsupported native-geometry case schema"
            )
        case_id = _case_id(self.case_id)
        if self.status not in _CASE_STATUSES:
            raise PoseBustersNativeGeometryError(
                "native-geometry case status is invalid"
            )
        error = str(self.error_code).strip()
        for name in (
            "receptor_atom_count",
            "native_ligand_atom_count",
            "start_ligand_atom_count",
            "cross_pair_count",
            "ligand_self_pair_count",
            "compared_heavy_bond_count",
        ):
            object.__setattr__(
                self,
                name,
                _positive_int(getattr(self, name), name=name, allow_zero=True),
            )
        unsupported = tuple(sorted(set(int(v) for v in self.unsupported_atomic_numbers)))
        metals = tuple(sorted(set(int(v) for v in self.metal_atomic_numbers)))
        if any(v < 1 or v > 118 for v in (*unsupported, *metals)):
            raise PoseBustersNativeGeometryError(
                "case atomic-number inventory is invalid"
            )
        if not set(metals).issubset(unsupported):
            raise PoseBustersNativeGeometryError(
                "case metal inventory is not included in unsupported elements"
            )
        names = tuple(
            sorted(
                set(
                    _token(str(v).strip().lower(), name="cofactor residue name").upper()
                    for v in self.nonwater_cofactor_residue_names
                )
            )
        )
        hex_names = (
            "minimum_receptor_ligand_ratio_hex",
            "minimum_receptor_ligand_distance_angstrom_hex",
            "minimum_ligand_self_ratio_hex",
            "minimum_ligand_self_distance_angstrom_hex",
            "maximum_native_start_bond_delta_angstrom_hex",
        )
        index_names = (
            "minimum_receptor_atom_index",
            "minimum_ligand_atom_index",
            "minimum_ligand_self_atom_i",
            "minimum_ligand_self_atom_j",
            "maximum_bond_native_atom_i",
            "maximum_bond_native_atom_j",
            "maximum_bond_start_atom_i",
            "maximum_bond_start_atom_j",
        )
        atomic_number_names = (
            "minimum_receptor_atomic_number",
            "minimum_ligand_atomic_number",
        )
        boolean_names = (
            "reference_ligand_residue_present_in_receptor",
            "reference_scorer_chemistry_scope",
            "receptor_ligand_geometry_evaluated",
            "deep_penetration_free",
            "overlap_free",
            "ligand_self_overlap_free",
            "bond_delta_within_tolerance",
            "bounded_geometry_pass",
            "bounded_geometry_and_reference_chemistry_scope",
        )
        for name in hex_names:
            object.__setattr__(
                self,
                name,
                _validate_optional_hex(getattr(self, name), name=name),
            )
        for name in index_names:
            object.__setattr__(
                self,
                name,
                _validate_optional_index(getattr(self, name), name=name),
            )
        for name in atomic_number_names:
            object.__setattr__(
                self,
                name,
                _optional_atomic_number(getattr(self, name), name=name),
            )
        for name in boolean_names:
            object.__setattr__(
                self,
                name,
                _validate_optional_bool(getattr(self, name), name=name),
            )
        if not isinstance(self.full_pose_validity_complete, bool) or self.full_pose_validity_complete:
            raise PoseBustersNativeGeometryError(
                "native geometry cannot complete full pose validity"
            )
        optional_values = tuple(getattr(self, name) for name in (*hex_names, *index_names, *atomic_number_names, *boolean_names))
        if self.status == "failure":
            if (
                not error
                or any(
                    getattr(self, name)
                    for name in (
                        "receptor_atom_count",
                        "native_ligand_atom_count",
                        "start_ligand_atom_count",
                        "cross_pair_count",
                        "ligand_self_pair_count",
                        "compared_heavy_bond_count",
                    )
                )
                or unsupported
                or metals
                or names
                or any(value is not None for value in optional_values)
            ):
                raise PoseBustersNativeGeometryError(
                    "failure native-geometry row contains scientific outputs"
                )
        else:
            if (
                error
                or self.receptor_atom_count < 1
                or self.native_ligand_atom_count < 1
                or self.start_ligand_atom_count < 1
                or self.cross_pair_count
                != self.receptor_atom_count * self.native_ligand_atom_count
                or self.cross_pair_count > POSEBUSTERS_NATIVE_GEOMETRY_MAX_CROSS_PAIRS
                or self.reference_ligand_residue_present_in_receptor is None
                or self.reference_scorer_chemistry_scope is None
                or self.receptor_ligand_geometry_evaluated
                != (self.status == "evaluated")
                or self.ligand_self_overlap_free is None
                or self.bond_delta_within_tolerance is None
                or self.bounded_geometry_pass is None
                or self.bounded_geometry_and_reference_chemistry_scope is None
            ):
                raise PoseBustersNativeGeometryError(
                    "native-geometry case row is incomplete"
                )
            expected_reference_residue_present = (
                case_id.split("_", maxsplit=1)[1] in names
            )
            if (
                self.reference_ligand_residue_present_in_receptor
                != expected_reference_residue_present
            ):
                raise PoseBustersNativeGeometryError(
                    "reference-ligand receptor-residue observation is inconsistent"
                )
            if self.reference_scorer_chemistry_scope and (
                self.status != "evaluated"
                or unsupported
                or metals
                or names
                or self.reference_ligand_residue_present_in_receptor
            ):
                raise PoseBustersNativeGeometryError(
                    "reference-scorer chemistry scope contradicts case inventory"
                )
            cross_values = (
                self.minimum_receptor_ligand_ratio_hex,
                self.minimum_receptor_ligand_distance_angstrom_hex,
                self.minimum_receptor_atom_index,
                self.minimum_ligand_atom_index,
                self.minimum_receptor_atomic_number,
                self.minimum_ligand_atomic_number,
                self.deep_penetration_free,
                self.overlap_free,
            )
            if self.status == "evaluated":
                if unsupported or any(value is None for value in cross_values):
                    raise PoseBustersNativeGeometryError(
                        "evaluated native-geometry row lacks cross geometry"
                    )
                if (
                    self.minimum_receptor_atom_index >= self.receptor_atom_count
                    or self.minimum_ligand_atom_index
                    >= self.native_ligand_atom_count
                ):
                    raise PoseBustersNativeGeometryError(
                        "minimum receptor-ligand pair is out of bounds"
                    )
            elif not unsupported or any(value is not None for value in cross_values):
                raise PoseBustersNativeGeometryError(
                    "partial native-geometry row has inconsistent cross geometry"
                )
            if self.ligand_self_pair_count:
                if any(
                    value is None
                    for value in (
                        self.minimum_ligand_self_ratio_hex,
                        self.minimum_ligand_self_distance_angstrom_hex,
                        self.minimum_ligand_self_atom_i,
                        self.minimum_ligand_self_atom_j,
                    )
                ):
                    raise PoseBustersNativeGeometryError(
                        "ligand self-overlap observation is incomplete"
                    )
                if (
                    self.minimum_ligand_self_atom_i
                    >= self.minimum_ligand_self_atom_j
                    or self.minimum_ligand_self_atom_j
                    >= self.native_ligand_atom_count
                    or self.ligand_self_pair_count
                    > (
                        self.native_ligand_atom_count
                        * (self.native_ligand_atom_count - 1)
                        // 2
                    )
                ):
                    raise PoseBustersNativeGeometryError(
                        "ligand self-overlap pair inventory is out of bounds"
                    )
            elif any(
                value is not None
                for value in (
                    self.minimum_ligand_self_ratio_hex,
                    self.minimum_ligand_self_distance_angstrom_hex,
                    self.minimum_ligand_self_atom_i,
                    self.minimum_ligand_self_atom_j,
                )
            ):
                raise PoseBustersNativeGeometryError(
                    "empty ligand self-pair set retained a minimum pair"
                )
            if self.compared_heavy_bond_count:
                if any(
                    value is None
                    for value in (
                        self.maximum_native_start_bond_delta_angstrom_hex,
                        self.maximum_bond_native_atom_i,
                        self.maximum_bond_native_atom_j,
                        self.maximum_bond_start_atom_i,
                        self.maximum_bond_start_atom_j,
                    )
                ):
                    raise PoseBustersNativeGeometryError(
                        "bond-delta observation is incomplete"
                    )
                if (
                    self.maximum_bond_native_atom_i
                    == self.maximum_bond_native_atom_j
                    or self.maximum_bond_start_atom_i
                    == self.maximum_bond_start_atom_j
                    or max(
                        self.maximum_bond_native_atom_i,
                        self.maximum_bond_native_atom_j,
                    )
                    >= self.native_ligand_atom_count
                    or max(
                        self.maximum_bond_start_atom_i,
                        self.maximum_bond_start_atom_j,
                    )
                    >= self.start_ligand_atom_count
                    or self.compared_heavy_bond_count
                    > (
                        self.native_ligand_atom_count
                        * (self.native_ligand_atom_count - 1)
                        // 2
                    )
                ):
                    raise PoseBustersNativeGeometryError(
                        "heavy-bond comparison inventory is out of bounds"
                    )
            elif (
                self.maximum_native_start_bond_delta_angstrom_hex != 0.0.hex()
                or any(
                    getattr(self, name) is not None
                    for name in (
                        "maximum_bond_native_atom_i",
                        "maximum_bond_native_atom_j",
                        "maximum_bond_start_atom_i",
                        "maximum_bond_start_atom_j",
                    )
                )
            ):
                raise PoseBustersNativeGeometryError(
                    "zero-bond observation must retain only an exact zero delta"
                )
            expected_bounded = bool(
                self.status == "evaluated"
                and self.deep_penetration_free
                and self.overlap_free
                and self.ligand_self_overlap_free
                and self.bond_delta_within_tolerance
            )
            if (
                self.bounded_geometry_pass != expected_bounded
                or self.bounded_geometry_and_reference_chemistry_scope
                != bool(
                    expected_bounded and self.reference_scorer_chemistry_scope
                )
            ):
                raise PoseBustersNativeGeometryError(
                    "native-geometry aggregate disposition is inconsistent"
                )
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "error_code", error)
        object.__setattr__(self, "unsupported_atomic_numbers", unsupported)
        object.__setattr__(self, "metal_atomic_numbers", metals)
        object.__setattr__(self, "nonwater_cofactor_residue_names", names)

    @property
    def processed(self) -> bool:
        return self.status != "failure"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "status": self.status,
            "error_code": self.error_code,
            "receptor_atom_count": self.receptor_atom_count,
            "native_ligand_atom_count": self.native_ligand_atom_count,
            "start_ligand_atom_count": self.start_ligand_atom_count,
            "cross_pair_count": self.cross_pair_count,
            "unsupported_atomic_numbers": list(self.unsupported_atomic_numbers),
            "metal_atomic_numbers": list(self.metal_atomic_numbers),
            "nonwater_cofactor_residue_names": list(
                self.nonwater_cofactor_residue_names
            ),
            "reference_ligand_residue_present_in_receptor": (
                self.reference_ligand_residue_present_in_receptor
            ),
            "reference_scorer_chemistry_scope": (
                self.reference_scorer_chemistry_scope
            ),
            "receptor_ligand_geometry_evaluated": (
                self.receptor_ligand_geometry_evaluated
            ),
            "minimum_receptor_ligand_ratio_hex": (
                self.minimum_receptor_ligand_ratio_hex
            ),
            "minimum_receptor_ligand_distance_angstrom_hex": (
                self.minimum_receptor_ligand_distance_angstrom_hex
            ),
            "minimum_receptor_atom_index": self.minimum_receptor_atom_index,
            "minimum_ligand_atom_index": self.minimum_ligand_atom_index,
            "minimum_receptor_atomic_number": self.minimum_receptor_atomic_number,
            "minimum_ligand_atomic_number": self.minimum_ligand_atomic_number,
            "deep_penetration_free": self.deep_penetration_free,
            "overlap_free": self.overlap_free,
            "ligand_self_pair_count": self.ligand_self_pair_count,
            "minimum_ligand_self_ratio_hex": self.minimum_ligand_self_ratio_hex,
            "minimum_ligand_self_distance_angstrom_hex": (
                self.minimum_ligand_self_distance_angstrom_hex
            ),
            "minimum_ligand_self_atom_i": self.minimum_ligand_self_atom_i,
            "minimum_ligand_self_atom_j": self.minimum_ligand_self_atom_j,
            "ligand_self_overlap_free": self.ligand_self_overlap_free,
            "compared_heavy_bond_count": self.compared_heavy_bond_count,
            "maximum_native_start_bond_delta_angstrom_hex": (
                self.maximum_native_start_bond_delta_angstrom_hex
            ),
            "maximum_bond_native_atom_i": self.maximum_bond_native_atom_i,
            "maximum_bond_native_atom_j": self.maximum_bond_native_atom_j,
            "maximum_bond_start_atom_i": self.maximum_bond_start_atom_i,
            "maximum_bond_start_atom_j": self.maximum_bond_start_atom_j,
            "bond_delta_within_tolerance": self.bond_delta_within_tolerance,
            "bounded_geometry_pass": self.bounded_geometry_pass,
            "bounded_geometry_and_reference_chemistry_scope": (
                self.bounded_geometry_and_reference_chemistry_scope
            ),
            "full_pose_validity_complete": False,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersNativeGeometryMetric:
    metric_id: str
    numerator: int
    denominator: int
    estimate: float
    confidence_interval_low: float
    confidence_interval_high: float
    schema_id: str = POSEBUSTERS_NATIVE_GEOMETRY_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_NATIVE_GEOMETRY_METRIC_SCHEMA_ID:
            raise PoseBustersNativeGeometryError(
                "unsupported native-geometry metric schema"
            )
        metric_id = _token(self.metric_id, name="metric_id")
        numerator = _positive_int(self.numerator, name="numerator", allow_zero=True)
        denominator = _positive_int(self.denominator, name="denominator")
        values = tuple(
            float(value)
            for value in (
                self.estimate,
                self.confidence_interval_low,
                self.confidence_interval_high,
            )
        )
        if (
            numerator > denominator
            or any(not math.isfinite(v) or v < 0.0 or v > 1.0 for v in values)
            or not values[1] <= values[0] <= values[2]
            or not math.isclose(values[0], numerator / denominator, abs_tol=1.0e-15)
        ):
            raise PoseBustersNativeGeometryError(
                "native-geometry metric is inconsistent"
            )
        object.__setattr__(self, "metric_id", metric_id)
        object.__setattr__(self, "numerator", numerator)
        object.__setattr__(self, "denominator", denominator)
        object.__setattr__(self, "estimate", values[0])
        object.__setattr__(self, "confidence_interval_low", values[1])
        object.__setattr__(self, "confidence_interval_high", values[2])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "metric_id": self.metric_id,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "estimate": self.estimate,
            "confidence_level": POSEBUSTERS_NATIVE_GEOMETRY_CONFIDENCE_LEVEL,
            "confidence_interval_method": "wilson_score_binomial",
            "confidence_interval_low": self.confidence_interval_low,
            "confidence_interval_high": self.confidence_interval_high,
        }


def _metric(
    metric_id: str,
    numerator: int,
    denominator: int,
) -> PoseBustersNativeGeometryMetric:
    proportion = numerator / denominator
    z2 = POSEBUSTERS_NATIVE_GEOMETRY_Z**2
    scale = 1.0 + z2 / denominator
    center = (proportion + z2 / (2.0 * denominator)) / scale
    radius = (
        POSEBUSTERS_NATIVE_GEOMETRY_Z
        * math.sqrt(
            proportion * (1.0 - proportion) / denominator
            + z2 / (4.0 * denominator**2)
        )
        / scale
    )
    return PoseBustersNativeGeometryMetric(
        metric_id=metric_id,
        numerator=numerator,
        denominator=denominator,
        estimate=proportion,
        confidence_interval_low=min(proportion, max(0.0, center - radius)),
        confidence_interval_high=max(proportion, min(1.0, center + radius)),
    )


def _summary_metrics(
    rows: Sequence[PoseBustersNativeGeometryCase],
) -> tuple[PoseBustersNativeGeometryMetric, ...]:
    predicates: tuple[tuple[str, Callable[[PoseBustersNativeGeometryCase], bool]], ...] = (
        ("case_processed_rate", lambda row: row.processed),
        (
            "receptor_ligand_element_geometry_evaluated_rate",
            lambda row: row.receptor_ligand_geometry_evaluated is True,
        ),
        (
            "deep_penetration_free_all_case_rate",
            lambda row: row.deep_penetration_free is True,
        ),
        ("overlap_free_all_case_rate", lambda row: row.overlap_free is True),
        (
            "ligand_self_overlap_free_all_case_rate",
            lambda row: row.ligand_self_overlap_free is True,
        ),
        (
            "native_start_bond_delta_within_tolerance_rate",
            lambda row: row.bond_delta_within_tolerance is True,
        ),
        (
            "bounded_geometry_pass_rate",
            lambda row: row.bounded_geometry_pass is True,
        ),
        (
            "reference_ligand_residue_absent_from_receptor_rate",
            lambda row: row.reference_ligand_residue_present_in_receptor is False,
        ),
        (
            "reference_scorer_chemistry_scope_rate",
            lambda row: row.reference_scorer_chemistry_scope is True,
        ),
        (
            "bounded_geometry_and_reference_chemistry_scope_rate",
            lambda row: (
                row.bounded_geometry_and_reference_chemistry_scope is True
            ),
        ),
        (
            "complete_pose_validity_rate",
            lambda row: row.full_pose_validity_complete,
        ),
    )
    denominator = len(rows)
    return tuple(
        _metric(metric_id, sum(bool(predicate(row)) for row in rows), denominator)
        for metric_id, predicate in predicates
    )


@dataclass(frozen=True, slots=True)
class PoseBustersNativeGeometryReceipt:
    corpus_audit_receipt_sha256: str
    archive_contract_sha256: str
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    python_implementation: str
    python_version: str
    torch_version: str
    torch_num_threads: int
    case_rows: tuple[PoseBustersNativeGeometryCase, ...]
    metrics: tuple[PoseBustersNativeGeometryMetric, ...]
    schema_id: str = POSEBUSTERS_NATIVE_GEOMETRY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_NATIVE_GEOMETRY_SCHEMA_ID:
            raise PoseBustersNativeGeometryError(
                "unsupported native-geometry receipt schema"
            )
        for name in (
            "corpus_audit_receipt_sha256",
            "archive_contract_sha256",
            "implementation_source_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        members = tuple(
            (
                _token(role, name="implementation source role"),
                _digest(digest, name=f"{role} source SHA-256"),
            )
            for role, digest in self.implementation_source_members
        )
        if (
            not members
            or tuple(sorted(members)) != members
            or len({role for role, _digest_value in members}) != len(members)
            or self.implementation_source_sha256 != _canonical_sha256(dict(members))
        ):
            raise PoseBustersNativeGeometryError(
                "native-geometry implementation-source identity is inconsistent"
            )
        python_implementation = str(self.python_implementation).strip()
        python_version = str(self.python_version).strip()
        torch_version = str(self.torch_version).strip()
        threads = _positive_int(self.torch_num_threads, name="torch_num_threads")
        if not python_implementation or not python_version or not torch_version:
            raise PoseBustersNativeGeometryError(
                "native-geometry runtime identity is incomplete"
            )
        rows = tuple(self.case_rows)
        if (
            not rows
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
        ):
            raise PoseBustersNativeGeometryError(
                "native-geometry rows must be canonical unique cases"
            )
        expected_metrics = _summary_metrics(rows)
        if tuple(metric.to_dict() for metric in self.metrics) != tuple(
            metric.to_dict() for metric in expected_metrics
        ):
            raise PoseBustersNativeGeometryError(
                "native-geometry metrics do not match all-case rows"
            )
        object.__setattr__(self, "implementation_source_members", members)
        object.__setattr__(self, "python_implementation", python_implementation)
        object.__setattr__(self, "python_version", python_version)
        object.__setattr__(self, "torch_version", torch_version)
        object.__setattr__(self, "torch_num_threads", threads)
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "metrics", expected_metrics)

    @property
    def processed_case_count(self) -> int:
        return sum(row.processed for row in self.case_rows)

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "corpus_audit_receipt_sha256": self.corpus_audit_receipt_sha256,
            "archive_contract_sha256": self.archive_contract_sha256,
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": dict(self.implementation_source_members),
            "runtime_identity": {
                "python_implementation": self.python_implementation,
                "python_version": self.python_version,
                "torch_version": self.torch_version,
                "torch_num_threads": self.torch_num_threads,
                "device": "cpu",
                "dtype": "float64",
            },
            "algorithm_contract": {
                "source_coordinate_roles": {
                    "reference_ligand_sdf": (
                        "native_crystal_pose_in_receptor_frame"
                    ),
                    "ligand_start_conformer_sdf": (
                        "rdkit_etkdgv3_then_uff_minimized_conformer_not_a_pose"
                    ),
                },
                "reference_ligand_residue_observation": (
                    "case_ccd_suffix_exact_match_in_receptor_nonwater_"
                    "nonpolymer_residue_names"
                ),
                "radius_profile_sha256": (
                    GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256
                ),
                "supported_atomic_numbers": sorted(
                    GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM
                ),
                "radii_angstrom": {
                    str(number): GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[number]
                    for number in sorted(GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM)
                },
                "overlap_scale": POSEBUSTERS_NATIVE_GEOMETRY_OVERLAP_SCALE,
                "deep_penetration_scale": (
                    POSEBUSTERS_NATIVE_GEOMETRY_DEEP_PENETRATION_SCALE
                ),
                "ligand_self_overlap_scale": (
                    POSEBUSTERS_NATIVE_GEOMETRY_LIGAND_SELF_OVERLAP_SCALE
                ),
                "native_start_bond_delta_tolerance_angstrom": (
                    POSEBUSTERS_NATIVE_GEOMETRY_BOND_DELTA_ANGSTROM
                ),
                "ligand_self_pair_exclusion": "exclude_covalent_1_2_and_angular_1_3",
                "native_start_bond_policy": (
                    "heavy_bonds_under_canonical_connectivity_mapping"
                ),
                "max_cross_pairs": POSEBUSTERS_NATIVE_GEOMETRY_MAX_CROSS_PAIRS,
                "receptor_chunk_atoms": (
                    POSEBUSTERS_NATIVE_GEOMETRY_RECEPTOR_CHUNK_ATOMS
                ),
            },
            "all_case_denominator": len(self.case_rows),
            "processed_case_count": self.processed_case_count,
            "failed_case_count": len(self.case_rows) - self.processed_case_count,
            "case_rows": [row.to_dict() for row in self.case_rows],
            "metrics": [metric.to_dict() for metric in self.metrics],
            "archive_extracted": False,
            "native_crystal_pose_positive_control": True,
            "generated_pose_evaluated": False,
            "formal_or_partial_charge_used": False,
            "aromaticity_or_atom_stereo_perceived": False,
            "force_field_strain_energy_evaluated": False,
            "posebusters_external_oracle_executed": False,
            "pose_generation_performed": False,
            "pose_scoring_or_ranking_performed": False,
            "benchmark_executed": False,
            "scientific_blockers": list(POSEBUSTERS_NATIVE_GEOMETRY_BLOCKERS),
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "receipt_sha256": self.fingerprint_sha256}

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        output = Path(output_path)
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = _canonical_bytes(self.to_dict()) + b"\n"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=str(output.parent),
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_name, output, follow_symlinks=False)
            except FileExistsError as exc:
                raise PoseBustersNativeGeometryError(
                    "PoseBusters native-geometry output already exists"
                ) from exc
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        return output


def _coordinates(system: Any) -> torch.Tensor:
    coordinates = system.coordinates
    if (
        not isinstance(coordinates, torch.Tensor)
        or coordinates.shape != (1, system.atom_count, 3)
        or coordinates.dtype != torch.float64
        or coordinates.device.type != "cpu"
        or not bool(torch.isfinite(coordinates).all().item())
    ):
        raise PoseBustersNativeGeometryError(
            "native-geometry input must be one CPU float64 coordinate model"
        )
    return coordinates[0]


def _minimum_cross_geometry(
    receptor: Any,
    ligand: Any,
) -> tuple[float, float, int, int]:
    receptor_coordinates = _coordinates(receptor)
    ligand_coordinates = _coordinates(ligand)
    receptor_radii = torch.tensor(
        [GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[a.atomic_number] for a in receptor.atoms],
        dtype=torch.float64,
    )
    ligand_radii = torch.tensor(
        [GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[a.atomic_number] for a in ligand.atoms],
        dtype=torch.float64,
    )
    best: tuple[float, int, int, float] | None = None
    for start in range(
        0,
        receptor.atom_count,
        POSEBUSTERS_NATIVE_GEOMETRY_RECEPTOR_CHUNK_ATOMS,
    ):
        stop = min(
            start + POSEBUSTERS_NATIVE_GEOMETRY_RECEPTOR_CHUNK_ATOMS,
            receptor.atom_count,
        )
        delta = (
            receptor_coordinates[start:stop, None, :]
            - ligand_coordinates[None, :, :]
        )
        distance_squared = delta.square().sum(dim=2)
        radius_sum = receptor_radii[start:stop, None] + ligand_radii[None, :]
        ratio_squared = distance_squared / radius_sum.square()
        value, flat_index = torch.min(ratio_squared.reshape(-1), dim=0)
        flat = int(flat_index.item())
        receptor_index = start + flat // ligand.atom_count
        ligand_index = flat % ligand.atom_count
        ratio_squared_value = float(value.item())
        distance_squared_value = float(
            distance_squared.reshape(-1)[flat].item()
        )
        candidate = (
            ratio_squared_value,
            receptor_index,
            ligand_index,
            distance_squared_value,
        )
        if best is None or candidate[:3] < best[:3]:
            best = candidate
    if best is None:
        raise PoseBustersNativeGeometryError(
            "receptor-ligand geometry produced no atom pair"
        )
    return math.sqrt(best[0]), math.sqrt(best[3]), best[1], best[2]


def _distance(coordinates: torch.Tensor, first: int, second: int) -> float:
    delta = coordinates[first] - coordinates[second]
    return math.sqrt(sum(float(value) ** 2 for value in delta.tolist()))


def _ligand_self_geometry(
    ligand: Any,
) -> tuple[int, float | None, float | None, int | None, int | None]:
    coordinates = _coordinates(ligand)
    adjacency: list[set[int]] = [set() for _ in ligand.atoms]
    excluded: set[tuple[int, int]] = set()
    for bond in ligand.bonds:
        first, second = sorted((int(bond.atom_i), int(bond.atom_j)))
        adjacency[first].add(second)
        adjacency[second].add(first)
        excluded.add((first, second))
    for center in range(ligand.atom_count):
        neighbors = sorted(adjacency[center])
        for first_offset, first in enumerate(neighbors):
            for second in neighbors[first_offset + 1 :]:
                excluded.add(tuple(sorted((first, second))))
    pairs = tuple(
        (first, second)
        for first in range(ligand.atom_count)
        for second in range(first + 1, ligand.atom_count)
        if (first, second) not in excluded
    )
    if not pairs:
        return 0, None, None, None, None
    best: tuple[float, int, int, float] | None = None
    for first, second in pairs:
        radius_sum = (
            GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[ligand.atoms[first].atomic_number]
            + GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[ligand.atoms[second].atomic_number]
        )
        distance = _distance(coordinates, first, second)
        candidate = (distance / radius_sum, first, second, distance)
        if best is None or candidate[:3] < best[:3]:
            best = candidate
    assert best is not None
    return len(pairs), best[0], best[3], best[1], best[2]


def _heavy_bond_delta(
    native: Any,
    start: Any,
    comparison: PublicLigandHeavyGraphComparison,
) -> tuple[int, float, int | None, int | None, int | None, int | None]:
    if not comparison.graph_match:
        raise PoseBustersNativeGeometryError(
            "native/start heavy connectivity does not match"
        )
    native_coordinates = _coordinates(native)
    start_coordinates = _coordinates(start)
    source_position = {
        atom_index: position
        for position, atom_index in enumerate(comparison.source_heavy_atom_indices)
    }
    rows: list[tuple[float, int, int, int, int]] = []
    for bond in native.bonds:
        native_first = int(bond.atom_i)
        native_second = int(bond.atom_j)
        if native_first not in source_position or native_second not in source_position:
            continue
        start_first_position = comparison.canonical_connectivity_mapping[
            source_position[native_first]
        ]
        start_second_position = comparison.canonical_connectivity_mapping[
            source_position[native_second]
        ]
        start_first = comparison.target_heavy_atom_indices[start_first_position]
        start_second = comparison.target_heavy_atom_indices[start_second_position]
        delta = abs(
            _distance(native_coordinates, native_first, native_second)
            - _distance(start_coordinates, start_first, start_second)
        )
        rows.append(
            (
                delta,
                native_first,
                native_second,
                start_first,
                start_second,
            )
        )
    if not rows:
        return 0, 0.0, None, None, None, None
    maximum = max(rows, key=lambda row: (row[0], -row[1], -row[2], -row[3], -row[4]))
    return len(rows), *maximum


def _failure_row(case_id: str, error_code: str) -> PoseBustersNativeGeometryCase:
    return PoseBustersNativeGeometryCase(
        case_id=case_id,
        status="failure",
        error_code=error_code,
    )


def _audit_case(
    archive: zipfile.ZipFile,
    intake_row: Any,
    corpus_row: Any,
) -> PoseBustersNativeGeometryCase:
    artifacts = {artifact.role: artifact for artifact in intake_row.artifacts}
    sources: dict[str, bytes] = {}
    for role in (
        "receptor_pdb",
        "reference_ligand_sdf",
        "ligand_start_conformer_sdf",
    ):
        artifact = artifacts.get(role)
        if artifact is None:
            return _failure_row(intake_row.case_id, "artifact_identity_missing")
        try:
            sources[role] = _read_member(
                archive,
                artifact.member_path,
                expected_sha256=artifact.sha256,
                expected_size=artifact.size_bytes,
            )
        except PoseBustersCorpusAuditError:
            return _failure_row(
                intake_row.case_id,
                f"{role}_identity_verification_failed",
            )
    try:
        receptor = parse_pdb(
            sources["receptor_pdb"],
            source_id=f"{intake_row.case_id}:receptor",
            connectivity_policy="record_unrepresented",
            crystallographic_cell_policy="record_only",
        )
        native = parse_sdf_v2000(
            sources["reference_ligand_sdf"],
            source_id=f"{intake_row.case_id}:native",
        )
        start = parse_sdf_v2000(
            sources["ligand_start_conformer_sdf"],
            source_id=f"{intake_row.case_id}:start",
        )
    except (PDBParseError, SDFParseError):
        return _failure_row(intake_row.case_id, "source_parse_failed")
    if (
        receptor.atom_count != corpus_row.receptor_atom_count
        or native.atom_count != corpus_row.native_ligand_atom_count
        or start.atom_count != corpus_row.start_ligand_atom_count
    ):
        return _failure_row(intake_row.case_id, "corpus_audit_count_mismatch")
    cross_pairs = receptor.atom_count * native.atom_count
    if cross_pairs > POSEBUSTERS_NATIVE_GEOMETRY_MAX_CROSS_PAIRS:
        return _failure_row(intake_row.case_id, "cross_pair_capacity_exceeded")
    try:
        comparison = compare_public_ligand_heavy_atom_graphs(native, start)
    except PublicReferenceMaterializationError:
        return _failure_row(intake_row.case_id, "heavy_graph_comparison_failed")
    if not comparison.graph_match:
        return _failure_row(intake_row.case_id, "heavy_graph_mismatch")
    supported = set(GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM)
    unsupported = tuple(
        sorted(
            {
                atom.atomic_number
                for atom in (*receptor.atoms, *native.atoms)
                if atom.atomic_number not in supported
            }
        )
    )
    try:
        self_count, self_ratio, self_distance, self_i, self_j = (
            _ligand_self_geometry(native)
        )
        bond_count, bond_delta, native_i, native_j, start_i, start_j = (
            _heavy_bond_delta(native, start, comparison)
        )
    except (KeyError, PoseBustersNativeGeometryError):
        return _failure_row(intake_row.case_id, "ligand_geometry_failed")
    self_free = bool(
        self_ratio is None
        or self_ratio >= POSEBUSTERS_NATIVE_GEOMETRY_LIGAND_SELF_OVERLAP_SCALE
    )
    bond_ok = bond_delta <= POSEBUSTERS_NATIVE_GEOMETRY_BOND_DELTA_ANGSTROM
    cross_evaluated = not unsupported
    cross_ratio: float | None = None
    cross_distance: float | None = None
    receptor_index: int | None = None
    ligand_index: int | None = None
    receptor_number: int | None = None
    ligand_number: int | None = None
    deep_free: bool | None = None
    overlap_free: bool | None = None
    if cross_evaluated:
        try:
            cross_ratio, cross_distance, receptor_index, ligand_index = (
                _minimum_cross_geometry(receptor, native)
            )
        except (KeyError, PoseBustersNativeGeometryError, RuntimeError):
            return _failure_row(
                intake_row.case_id,
                "receptor_ligand_geometry_failed",
            )
        receptor_number = receptor.atoms[receptor_index].atomic_number
        ligand_number = native.atoms[ligand_index].atomic_number
        deep_free = (
            cross_ratio
            >= POSEBUSTERS_NATIVE_GEOMETRY_DEEP_PENETRATION_SCALE
        )
        overlap_free = cross_ratio >= POSEBUSTERS_NATIVE_GEOMETRY_OVERLAP_SCALE
    reference_scorer_chemistry_scope = corpus_row.reference_scorer_scope_blockers == (
        "parameters_and_partial_charges_missing",
    )
    bounded_pass = bool(
        cross_evaluated and deep_free and overlap_free and self_free and bond_ok
    )
    return PoseBustersNativeGeometryCase(
        case_id=intake_row.case_id,
        status=("evaluated" if cross_evaluated else "partial_unsupported_element"),
        error_code="",
        receptor_atom_count=receptor.atom_count,
        native_ligand_atom_count=native.atom_count,
        start_ligand_atom_count=start.atom_count,
        cross_pair_count=cross_pairs,
        unsupported_atomic_numbers=unsupported,
        metal_atomic_numbers=corpus_row.metal_atomic_numbers,
        nonwater_cofactor_residue_names=(
            corpus_row.receptor_nonwater_nonpolymer_residue_names
        ),
        reference_ligand_residue_present_in_receptor=(
            intake_row.case_id.split("_", maxsplit=1)[1]
            in corpus_row.receptor_nonwater_nonpolymer_residue_names
        ),
        reference_scorer_chemistry_scope=reference_scorer_chemistry_scope,
        receptor_ligand_geometry_evaluated=cross_evaluated,
        minimum_receptor_ligand_ratio_hex=(
            None
            if cross_ratio is None
            else _finite_hex(cross_ratio, name="minimum receptor-ligand ratio")
        ),
        minimum_receptor_ligand_distance_angstrom_hex=(
            None
            if cross_distance is None
            else _finite_hex(
                cross_distance,
                name="minimum receptor-ligand distance",
            )
        ),
        minimum_receptor_atom_index=receptor_index,
        minimum_ligand_atom_index=ligand_index,
        minimum_receptor_atomic_number=receptor_number,
        minimum_ligand_atomic_number=ligand_number,
        deep_penetration_free=deep_free,
        overlap_free=overlap_free,
        ligand_self_pair_count=self_count,
        minimum_ligand_self_ratio_hex=(
            None
            if self_ratio is None
            else _finite_hex(self_ratio, name="minimum ligand self ratio")
        ),
        minimum_ligand_self_distance_angstrom_hex=(
            None
            if self_distance is None
            else _finite_hex(
                self_distance,
                name="minimum ligand self distance",
            )
        ),
        minimum_ligand_self_atom_i=self_i,
        minimum_ligand_self_atom_j=self_j,
        ligand_self_overlap_free=self_free,
        compared_heavy_bond_count=bond_count,
        maximum_native_start_bond_delta_angstrom_hex=_finite_hex(
            bond_delta,
            name="maximum native-start bond delta",
        ),
        maximum_bond_native_atom_i=native_i,
        maximum_bond_native_atom_j=native_j,
        maximum_bond_start_atom_i=start_i,
        maximum_bond_start_atom_j=start_j,
        bond_delta_within_tolerance=bond_ok,
        bounded_geometry_pass=bounded_pass,
        bounded_geometry_and_reference_chemistry_scope=bool(
            bounded_pass and reference_scorer_chemistry_scope
        ),
    )


def _implementation_source_members(
    corpus: PoseBustersCorpusAuditReceipt,
) -> tuple[tuple[str, str], ...]:
    members = dict(corpus.implementation_source_members)
    members.update(
        {
            "native_geometry_audit": _source_file_sha256(__file__),
            "element_geometry_diagnostic": _source_file_sha256(
                ElementGeometryDiagnosticScoreConfig.__post_init__.__code__.co_filename
            ),
            "flexible_geometry_diagnostic": _source_file_sha256(
                FlexibleGeometryDiagnosticScoreConfig.__post_init__.__code__.co_filename
            ),
            "pose_validity_config": _source_file_sha256(
                PoseValidityConfig.__post_init__.__code__.co_filename
            ),
        }
    )
    return tuple(sorted(members.items()))


def materialize_posebusters_native_geometry(
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersNativeGeometryReceipt:
    """Materialize the claim-closed native crystal-pose geometry preflight."""

    try:
        corpus = verify_posebusters_corpus_audit_receipt(
            corpus_audit_receipt_path,
            archive_path,
            selection_path,
            intake_receipt_path,
            contract=contract,
        )
        intake = verify_posebusters_archive_intake_receipt(
            intake_receipt_path,
            archive_path,
            selection_path,
            contract=contract,
        )
    except (PoseBustersCorpusAuditError, PoseBustersArchiveIntakeError) as exc:
        raise PoseBustersNativeGeometryError(
            "native geometry requires exact verified corpus and intake receipts"
        ) from exc
    if tuple(row.case_id for row in corpus.case_rows) != tuple(
        row.case_id for row in intake.case_rows
    ):
        raise PoseBustersNativeGeometryError(
            "corpus and intake case identities disagree"
        )
    corpus_rows = {row.case_id: row for row in corpus.case_rows}
    descriptor, size = _regular_file_descriptor(
        archive_path,
        maximum_bytes=contract.archive_size_bytes,
    )
    try:
        if (
            size != contract.archive_size_bytes
            or _hash_descriptor(descriptor, size) != contract.archive_sha256
        ):
            raise PoseBustersNativeGeometryError(
                "native-geometry archive changed after receipt verification"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            try:
                with zipfile.ZipFile(handle, "r") as archive:
                    rows = tuple(
                        _audit_case(archive, row, corpus_rows[row.case_id])
                        for row in intake.case_rows
                    )
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise PoseBustersNativeGeometryError(
                    "native geometry failed bounded ZIP access"
                ) from exc
    finally:
        os.close(descriptor)
    source_members = _implementation_source_members(corpus)
    metrics = _summary_metrics(rows)
    return PoseBustersNativeGeometryReceipt(
        corpus_audit_receipt_sha256=corpus.fingerprint_sha256,
        archive_contract_sha256=contract.fingerprint_sha256,
        implementation_source_sha256=_canonical_sha256(dict(source_members)),
        implementation_source_members=source_members,
        python_implementation=platform.python_implementation(),
        python_version=platform.python_version(),
        torch_version=str(torch.__version__),
        torch_num_threads=torch.get_num_threads(),
        case_rows=rows,
        metrics=metrics,
    )


def verify_posebusters_native_geometry_receipt(
    native_geometry_receipt_path: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersNativeGeometryReceipt:
    """Require byte-exact native-geometry reexecution equality."""

    source = _read_exact_regular_file(
        native_geometry_receipt_path,
        maximum_bytes=POSEBUSTERS_NATIVE_GEOMETRY_MAX_RECEIPT_BYTES,
    )
    expected = materialize_posebusters_native_geometry(
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        contract=contract,
    )
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersNativeGeometryError(
            "PoseBusters native-geometry receipt does not match exact reexecution"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-native-geometry",
        description=(
            "Audit native crystal-pose geometry without extraction or docking."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--archive", required=True)
    materialize.add_argument("--selection", required=True)
    materialize.add_argument("--intake-receipt", required=True)
    materialize.add_argument("--corpus-audit-receipt", required=True)
    materialize.add_argument("--output", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--archive", required=True)
    verify.add_argument("--selection", required=True)
    verify.add_argument("--intake-receipt", required=True)
    verify.add_argument("--corpus-audit-receipt", required=True)
    verify.add_argument("--native-geometry-receipt", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "materialize":
        receipt = materialize_posebusters_native_geometry(
            args.archive,
            args.selection,
            args.intake_receipt,
            args.corpus_audit_receipt,
        )
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_native_geometry_receipt(
            args.native_geometry_receipt,
            args.archive,
            args.selection,
            args.intake_receipt,
            args.corpus_audit_receipt,
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "processed_case_count": receipt.processed_case_count,
                "benchmark_executed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_NATIVE_GEOMETRY_BLOCKERS",
    "POSEBUSTERS_NATIVE_GEOMETRY_BOND_DELTA_ANGSTROM",
    "POSEBUSTERS_NATIVE_GEOMETRY_CASE_SCHEMA_ID",
    "POSEBUSTERS_NATIVE_GEOMETRY_CONFIDENCE_LEVEL",
    "POSEBUSTERS_NATIVE_GEOMETRY_DEEP_PENETRATION_SCALE",
    "POSEBUSTERS_NATIVE_GEOMETRY_LIGAND_SELF_OVERLAP_SCALE",
    "POSEBUSTERS_NATIVE_GEOMETRY_MAX_CROSS_PAIRS",
    "POSEBUSTERS_NATIVE_GEOMETRY_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_NATIVE_GEOMETRY_METRIC_SCHEMA_ID",
    "POSEBUSTERS_NATIVE_GEOMETRY_OVERLAP_SCALE",
    "POSEBUSTERS_NATIVE_GEOMETRY_RECEPTOR_CHUNK_ATOMS",
    "POSEBUSTERS_NATIVE_GEOMETRY_SCHEMA_ID",
    "PoseBustersNativeGeometryCase",
    "PoseBustersNativeGeometryError",
    "PoseBustersNativeGeometryMetric",
    "PoseBustersNativeGeometryReceipt",
    "main",
    "materialize_posebusters_native_geometry",
    "verify_posebusters_native_geometry_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
