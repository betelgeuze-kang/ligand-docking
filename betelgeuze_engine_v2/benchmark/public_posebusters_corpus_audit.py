"""Failure-inclusive chemistry and ingest audit for the PoseBusters 308 corpus.

The audit consumes the exact archive-intake receipt and streams three source
artifacts per selected case without extracting the ZIP.  It records bounded
parser coverage, heavy-atom graph identity, raw directional V2000 bond-stereo
identity, elements, formal charge, metals, and non-water cofactors.  It does not
prepare molecules, infer atom stereochemistry, generate or score poses, or run a
docking benchmark.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Sequence
import zipfile

from betelgeuze_engine_v2.docking.reference_scoring import (
    DEFAULT_SUPPORTED_DOCKING_ATOMIC_NUMBERS,
    ReferenceDockingChemistryScope,
    ReferenceDockingScoreConfig,
)
from betelgeuze_engine_v2.io import (
    PDBParseError,
    PDB_PARSER_NAME,
    PDB_PARSER_VERSION,
    SDFParseError,
    SDF_PARSER_NAME,
    SDF_PARSER_VERSION,
    parse_pdb,
    parse_sdf_v2000,
)
from betelgeuze_engine_v2.io.pdb import parse_pdb as parse_pdb_subset

from .public_ligand_graph_audit import (
    PublicLigandHeavyGraphComparison,
    compare_public_ligand_heavy_atom_graphs,
)
from .public_materialization import PublicReferenceMaterializationError
from .public_materialization import PublicReferenceMaterializationLimits
from .public_posebusters_intake import (
    OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    POSEBUSTERS_ARCHIVE_MAX_MEMBER_BYTES,
    POSEBUSTERS_ARCHIVE_STREAM_CHUNK_BYTES,
    PoseBustersArchiveContract,
    PoseBustersArchiveIntakeError,
    _hash_descriptor,
    _read_exact_regular_file,
    _regular_file_descriptor,
    verify_posebusters_archive_intake_receipt,
)


POSEBUSTERS_CORPUS_CASE_AUDIT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_corpus_case_audit/1.0.0"
)
POSEBUSTERS_CORPUS_AUDIT_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_corpus_audit_metric/1.0.0"
)
POSEBUSTERS_CORPUS_AUDIT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_corpus_audit/1.0.0"
)
POSEBUSTERS_CORPUS_AUDIT_MAX_RECEIPT_BYTES = 4 * 1024 * 1024
POSEBUSTERS_CORPUS_AUDIT_MAX_IMPLEMENTATION_SOURCE_BYTES = 2 * 1024 * 1024
POSEBUSTERS_CORPUS_AUDIT_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_CORPUS_AUDIT_Z = 1.959963984540054
POSEBUSTERS_CORPUS_AUDIT_WATER_RESIDUES = ("DOD", "HOH", "WAT")
POSEBUSTERS_CORPUS_AUDIT_MAXIMUM_ABSOLUTE_FORMAL_CHARGE = (
    ReferenceDockingChemistryScope().maximum_absolute_formal_charge
)
POSEBUSTERS_CORPUS_AUDIT_MAX_LIGAND_ATOMS = (
    ReferenceDockingScoreConfig().max_ligand_atoms
)
POSEBUSTERS_CORPUS_AUDIT_METAL_ATOMIC_NUMBERS = tuple(
    sorted(
        {
            3,
            4,
            11,
            12,
            13,
            19,
            20,
            *range(21, 32),
            37,
            38,
            *range(39, 51),
            55,
            56,
            *range(57, 84),
            87,
            88,
            *range(89, 113),
        }
    )
)
POSEBUSTERS_CORPUS_AUDIT_BLOCKERS = (
    "atom_stereo_oracle_missing",
    "aromaticity_perception_not_performed",
    "partial_charge_and_parameter_assignment_missing",
    "target_family_assignments_missing",
    "release_date_and_sequence_leakage_receipts_missing",
    "pose_preparation_generation_validity_and_scoring_not_executed",
    "same_input_external_baseline_results_missing",
    "independent_external_rerun_missing",
    "scientific_review_missing",
)
_AUDITED_STATUS = "audited"
_FAILURE_STATUS = "failure"
_SCOPE_STATUSES = {
    "abstain_unsupported_ligand_element",
    "abstain_unsupported_receptor_element",
    "abstain_formal_charge",
    "abstain_ligand_atom_capacity",
    "abstain_metal",
    "abstain_cofactor",
    "blocked_parameters_and_partial_charges_missing",
}
_PARAMETER_BLOCKER = "parameters_and_partial_charges_missing"
_IMPLEMENTATION_SOURCE_ROLES = (
    "corpus_audit",
    "heavy_graph_audit",
    "pdb_connectivity_parser",
    "pdb_subset_parser",
    "posebusters_archive_intake",
    "public_materialization_graph_search",
    "reference_docking_scope",
    "sdf_v2000_parser",
)
_SHA256_CHARACTERS = frozenset("0123456789abcdef")


class PoseBustersCorpusAuditError(ValueError):
    """PoseBusters corpus audit failed closed."""


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
        raise PoseBustersCorpusAuditError(
            "PoseBusters corpus audit value is not canonical JSON"
        ) from exc


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise PoseBustersCorpusAuditError(f"{name} must be a lowercase SHA-256")
    return value


def _positive_int(value: object, *, name: str, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "non-negative" if allow_zero else "positive"
        raise PoseBustersCorpusAuditError(f"{name} must be a {qualifier} integer")
    return value


def _exact_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PoseBustersCorpusAuditError(f"{name} must be an integer")
    return value


def _token(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PoseBustersCorpusAuditError(f"{name} must be non-empty text")
    result = value.strip()
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in result):
        raise PoseBustersCorpusAuditError(f"{name} contains unsupported characters")
    return result


def _element_counts(atomic_numbers: Sequence[int]) -> tuple[tuple[int, int], ...]:
    counts = Counter(int(value) for value in atomic_numbers)
    if any(value < 1 or value > 118 for value in counts):
        raise PoseBustersCorpusAuditError("atomic number is outside [1,118]")
    return tuple(sorted(counts.items()))


def _validate_element_counts(
    value: Sequence[tuple[int, int]],
    *,
    name: str,
) -> tuple[tuple[int, int], ...]:
    rows = tuple(
        (
            _positive_int(number, name=f"{name} atomic number"),
            _positive_int(count, name=f"{name} count"),
        )
        for number, count in value
    )
    if (
        tuple(sorted(rows)) != rows
        or len({number for number, _count in rows}) != len(rows)
        or any(number > 118 for number, _count in rows)
    ):
        raise PoseBustersCorpusAuditError(f"{name} must be sorted unique element counts")
    return rows


def _element_count_dict(value: Sequence[tuple[int, int]]) -> dict[str, int]:
    return {str(number): count for number, count in value}


def _source_file_sha256(path: str | os.PathLike[str]) -> str:
    descriptor, size = _regular_file_descriptor(
        path,
        maximum_bytes=POSEBUSTERS_CORPUS_AUDIT_MAX_IMPLEMENTATION_SOURCE_BYTES,
    )
    try:
        return _hash_descriptor(descriptor, size)
    finally:
        os.close(descriptor)


def _implementation_source_members() -> tuple[tuple[str, str], ...]:
    paths = {
        "corpus_audit": __file__,
        "heavy_graph_audit": compare_public_ligand_heavy_atom_graphs.__code__.co_filename,
        "pdb_connectivity_parser": parse_pdb.__code__.co_filename,
        "pdb_subset_parser": parse_pdb_subset.__code__.co_filename,
        "posebusters_archive_intake": (
            verify_posebusters_archive_intake_receipt.__code__.co_filename
        ),
        "public_materialization_graph_search": (
            PublicReferenceMaterializationLimits.__post_init__.__code__.co_filename
        ),
        "reference_docking_scope": (
            ReferenceDockingScoreConfig.__post_init__.__code__.co_filename
        ),
        "sdf_v2000_parser": parse_sdf_v2000.__code__.co_filename,
    }
    if tuple(sorted(paths)) != _IMPLEMENTATION_SOURCE_ROLES:
        raise PoseBustersCorpusAuditError(
            "corpus audit implementation-source roles are incomplete"
        )
    return tuple(
        (role, _source_file_sha256(paths[role]))
        for role in _IMPLEMENTATION_SOURCE_ROLES
    )


def _scope_disposition(
    *,
    unsupported_receptor: Sequence[int],
    unsupported_ligand: Sequence[int],
    receptor_maximum_absolute_atom_formal_charge: int,
    ligand_maximum_absolute_atom_formal_charge: int,
    native_ligand_atom_count: int,
    start_ligand_atom_count: int,
    metals: Sequence[int],
    nonwater_names: Sequence[str],
) -> tuple[str, tuple[str, ...]]:
    blockers = {_PARAMETER_BLOCKER}
    if unsupported_ligand:
        blockers.add("unsupported_ligand_element")
    if unsupported_receptor:
        blockers.add("unsupported_receptor_element")
    if (
        receptor_maximum_absolute_atom_formal_charge
        > POSEBUSTERS_CORPUS_AUDIT_MAXIMUM_ABSOLUTE_FORMAL_CHARGE
        or ligand_maximum_absolute_atom_formal_charge
        > POSEBUSTERS_CORPUS_AUDIT_MAXIMUM_ABSOLUTE_FORMAL_CHARGE
    ):
        blockers.add("formal_charge_out_of_scope")
    if (
        native_ligand_atom_count > POSEBUSTERS_CORPUS_AUDIT_MAX_LIGAND_ATOMS
        or start_ligand_atom_count > POSEBUSTERS_CORPUS_AUDIT_MAX_LIGAND_ATOMS
    ):
        blockers.add("ligand_atom_capacity_exceeded")
    if metals:
        blockers.add("metal_present")
    if nonwater_names:
        blockers.add("nonwater_cofactor_present")
    if unsupported_ligand:
        status = "abstain_unsupported_ligand_element"
    elif unsupported_receptor:
        status = "abstain_unsupported_receptor_element"
    elif "formal_charge_out_of_scope" in blockers:
        status = "abstain_formal_charge"
    elif "ligand_atom_capacity_exceeded" in blockers:
        status = "abstain_ligand_atom_capacity"
    elif metals:
        status = "abstain_metal"
    elif nonwater_names:
        status = "abstain_cofactor"
    else:
        status = "blocked_parameters_and_partial_charges_missing"
    return status, tuple(sorted(blockers))


@dataclass(frozen=True, slots=True)
class PoseBustersCorpusCaseAudit:
    case_id: str
    status: str
    error_code: str
    receptor_atom_count: int = 0
    receptor_polymer_atom_count: int = 0
    receptor_nonpolymer_atom_count: int = 0
    receptor_element_counts: tuple[tuple[int, int], ...] = ()
    receptor_formal_charge: int = 0
    receptor_maximum_absolute_atom_formal_charge: int = 0
    receptor_nonwater_nonpolymer_residue_names: tuple[str, ...] = ()
    metal_atomic_numbers: tuple[int, ...] = ()
    native_ligand_atom_count: int = 0
    native_ligand_heavy_atom_count: int = 0
    start_ligand_atom_count: int = 0
    start_ligand_heavy_atom_count: int = 0
    ligand_element_counts: tuple[tuple[int, int], ...] = ()
    ligand_formal_charge: int = 0
    native_ligand_maximum_absolute_atom_formal_charge: int = 0
    native_raw_aromatic_bond_count: int = 0
    start_raw_aromatic_bond_count: int = 0
    native_directional_stereo_bond_count: int = 0
    start_directional_stereo_bond_count: int = 0
    unsupported_receptor_atomic_numbers: tuple[int, ...] = ()
    unsupported_ligand_atomic_numbers: tuple[int, ...] = ()
    reference_scorer_scope_status: str = ""
    reference_scorer_scope_blockers: tuple[str, ...] = ()
    heavy_graph_comparison: PublicLigandHeavyGraphComparison | None = None
    schema_id: str = POSEBUSTERS_CORPUS_CASE_AUDIT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_CORPUS_CASE_AUDIT_SCHEMA_ID:
            raise PoseBustersCorpusAuditError("unsupported corpus case-audit schema")
        case_id = str(self.case_id).strip()
        if len(case_id.split("_")) != 2 or case_id.upper() != case_id:
            raise PoseBustersCorpusAuditError("corpus case ID is invalid")
        if self.status not in {_AUDITED_STATUS, _FAILURE_STATUS}:
            raise PoseBustersCorpusAuditError("corpus case status is invalid")
        error = str(self.error_code).strip()
        numeric_names = (
            "receptor_atom_count",
            "receptor_polymer_atom_count",
            "receptor_nonpolymer_atom_count",
            "receptor_maximum_absolute_atom_formal_charge",
            "native_ligand_atom_count",
            "native_ligand_heavy_atom_count",
            "start_ligand_atom_count",
            "start_ligand_heavy_atom_count",
            "native_ligand_maximum_absolute_atom_formal_charge",
            "native_raw_aromatic_bond_count",
            "start_raw_aromatic_bond_count",
            "native_directional_stereo_bond_count",
            "start_directional_stereo_bond_count",
        )
        for name in numeric_names:
            object.__setattr__(
                self,
                name,
                _positive_int(getattr(self, name), name=name, allow_zero=True),
            )
        receptor_counts = _validate_element_counts(
            self.receptor_element_counts,
            name="receptor_element_counts",
        )
        ligand_counts = _validate_element_counts(
            self.ligand_element_counts,
            name="ligand_element_counts",
        )
        names = tuple(sorted(set(str(value).strip().upper() for value in self.receptor_nonwater_nonpolymer_residue_names)))
        if any(not value for value in names):
            raise PoseBustersCorpusAuditError("cofactor residue names cannot be empty")
        metals = tuple(sorted(set(int(value) for value in self.metal_atomic_numbers)))
        unsupported_receptor = tuple(
            sorted(set(int(value) for value in self.unsupported_receptor_atomic_numbers))
        )
        unsupported_ligand = tuple(
            sorted(set(int(value) for value in self.unsupported_ligand_atomic_numbers))
        )
        receptor_formal_charge = _exact_int(
            self.receptor_formal_charge,
            name="receptor_formal_charge",
        )
        ligand_formal_charge = _exact_int(
            self.ligand_formal_charge,
            name="ligand_formal_charge",
        )
        scope_blockers = tuple(
            sorted(set(_token(value, name="reference_scorer_scope_blocker") for value in self.reference_scorer_scope_blockers))
        )
        if any(value < 1 or value > 118 for value in (*metals, *unsupported_receptor, *unsupported_ligand)):
            raise PoseBustersCorpusAuditError("case atomic-number disposition is invalid")
        if self.status == _FAILURE_STATUS:
            if not error or any(getattr(self, name) for name in numeric_names) or any(
                (
                    receptor_counts,
                    ligand_counts,
                    names,
                    metals,
                    unsupported_receptor,
                    unsupported_ligand,
                    scope_blockers,
                )
            ) or receptor_formal_charge or ligand_formal_charge or self.reference_scorer_scope_status or self.heavy_graph_comparison is not None:
                raise PoseBustersCorpusAuditError("failure corpus row contains scientific outputs")
        else:
            supported = set(DEFAULT_SUPPORTED_DOCKING_ATOMIC_NUMBERS)
            expected_unsupported_receptor = tuple(
                number for number, _count in receptor_counts if number not in supported
            )
            expected_unsupported_ligand = tuple(
                number for number, _count in ligand_counts if number not in supported
            )
            expected_metals = tuple(
                sorted(
                    {
                        number
                        for number, _count in (*receptor_counts, *ligand_counts)
                        if number in POSEBUSTERS_CORPUS_AUDIT_METAL_ATOMIC_NUMBERS
                    }
                )
            )
            expected_scope_status, expected_scope_blockers = _scope_disposition(
                unsupported_receptor=unsupported_receptor,
                unsupported_ligand=unsupported_ligand,
                receptor_maximum_absolute_atom_formal_charge=(
                    self.receptor_maximum_absolute_atom_formal_charge
                ),
                ligand_maximum_absolute_atom_formal_charge=(
                    self.native_ligand_maximum_absolute_atom_formal_charge
                ),
                native_ligand_atom_count=self.native_ligand_atom_count,
                start_ligand_atom_count=self.start_ligand_atom_count,
                metals=metals,
                nonwater_names=names,
            )
            if error:
                raise PoseBustersCorpusAuditError("audited corpus row cannot contain an error")
            if (
                self.receptor_atom_count < 1
                or self.native_ligand_atom_count < 1
                or self.start_ligand_atom_count < 1
                or self.native_ligand_heavy_atom_count < 1
                or self.start_ligand_heavy_atom_count < 1
                or self.receptor_polymer_atom_count + self.receptor_nonpolymer_atom_count
                != self.receptor_atom_count
                or sum(receptor_counts[index][1] for index in range(len(receptor_counts)))
                != self.receptor_atom_count
                or sum(ligand_counts[index][1] for index in range(len(ligand_counts)))
                != self.native_ligand_atom_count
                or not isinstance(
                    self.heavy_graph_comparison,
                    PublicLigandHeavyGraphComparison,
                )
                or self.native_ligand_heavy_atom_count
                != sum(count for number, count in ligand_counts if number != 1)
                or self.native_ligand_heavy_atom_count
                != len(self.heavy_graph_comparison.source_heavy_atom_indices)
                or self.start_ligand_heavy_atom_count
                != len(self.heavy_graph_comparison.target_heavy_atom_indices)
                or unsupported_receptor != expected_unsupported_receptor
                or unsupported_ligand != expected_unsupported_ligand
                or metals != expected_metals
                or self.reference_scorer_scope_status not in _SCOPE_STATUSES
                or self.reference_scorer_scope_status != expected_scope_status
                or scope_blockers != expected_scope_blockers
            ):
                raise PoseBustersCorpusAuditError("audited corpus row is incomplete")
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "error_code", error)
        object.__setattr__(self, "receptor_element_counts", receptor_counts)
        object.__setattr__(self, "ligand_element_counts", ligand_counts)
        object.__setattr__(self, "receptor_formal_charge", receptor_formal_charge)
        object.__setattr__(self, "ligand_formal_charge", ligand_formal_charge)
        object.__setattr__(
            self,
            "receptor_nonwater_nonpolymer_residue_names",
            names,
        )
        object.__setattr__(self, "metal_atomic_numbers", metals)
        object.__setattr__(
            self,
            "unsupported_receptor_atomic_numbers",
            unsupported_receptor,
        )
        object.__setattr__(
            self,
            "unsupported_ligand_atomic_numbers",
            unsupported_ligand,
        )
        object.__setattr__(
            self,
            "reference_scorer_scope_blockers",
            scope_blockers,
        )

    @property
    def audited(self) -> bool:
        return self.status == _AUDITED_STATUS

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "status": self.status,
            "error_code": self.error_code,
            "receptor_atom_count": self.receptor_atom_count,
            "receptor_polymer_atom_count": self.receptor_polymer_atom_count,
            "receptor_nonpolymer_atom_count": self.receptor_nonpolymer_atom_count,
            "receptor_element_counts": _element_count_dict(self.receptor_element_counts),
            "receptor_formal_charge": self.receptor_formal_charge,
            "receptor_maximum_absolute_atom_formal_charge": (
                self.receptor_maximum_absolute_atom_formal_charge
            ),
            "receptor_nonwater_nonpolymer_residue_names": list(
                self.receptor_nonwater_nonpolymer_residue_names
            ),
            "metal_atomic_numbers": list(self.metal_atomic_numbers),
            "native_ligand_atom_count": self.native_ligand_atom_count,
            "native_ligand_heavy_atom_count": self.native_ligand_heavy_atom_count,
            "start_ligand_atom_count": self.start_ligand_atom_count,
            "start_ligand_heavy_atom_count": self.start_ligand_heavy_atom_count,
            "ligand_element_counts": _element_count_dict(self.ligand_element_counts),
            "ligand_formal_charge": self.ligand_formal_charge,
            "native_ligand_maximum_absolute_atom_formal_charge": (
                self.native_ligand_maximum_absolute_atom_formal_charge
            ),
            "native_raw_aromatic_bond_count": self.native_raw_aromatic_bond_count,
            "start_raw_aromatic_bond_count": self.start_raw_aromatic_bond_count,
            "native_directional_stereo_bond_count": (
                self.native_directional_stereo_bond_count
            ),
            "start_directional_stereo_bond_count": (
                self.start_directional_stereo_bond_count
            ),
            "unsupported_receptor_atomic_numbers": list(
                self.unsupported_receptor_atomic_numbers
            ),
            "unsupported_ligand_atomic_numbers": list(
                self.unsupported_ligand_atomic_numbers
            ),
            "reference_scorer_scope_status": self.reference_scorer_scope_status,
            "reference_scorer_scope_blockers": list(
                self.reference_scorer_scope_blockers
            ),
            "heavy_graph_comparison": (
                None
                if self.heavy_graph_comparison is None
                else self.heavy_graph_comparison.to_dict()
            ),
        }


@dataclass(frozen=True, slots=True)
class PoseBustersCorpusAuditMetric:
    metric_id: str
    numerator: int
    denominator: int
    estimate: float
    confidence_interval_low: float
    confidence_interval_high: float
    schema_id: str = POSEBUSTERS_CORPUS_AUDIT_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_CORPUS_AUDIT_METRIC_SCHEMA_ID:
            raise PoseBustersCorpusAuditError("unsupported corpus audit-metric schema")
        metric_id = _token(self.metric_id, name="metric_id")
        numerator = _positive_int(self.numerator, name="numerator", allow_zero=True)
        denominator = _positive_int(self.denominator, name="denominator")
        values = (
            float(self.estimate),
            float(self.confidence_interval_low),
            float(self.confidence_interval_high),
        )
        if numerator > denominator or any(
            not math.isfinite(value) or value < 0.0 or value > 1.0
            for value in values
        ) or not values[1] <= values[0] <= values[2]:
            raise PoseBustersCorpusAuditError("corpus audit metric is inconsistent")
        if not math.isclose(values[0], numerator / denominator, abs_tol=1.0e-15):
            raise PoseBustersCorpusAuditError("corpus audit estimate is inconsistent")
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
            "confidence_level": POSEBUSTERS_CORPUS_AUDIT_CONFIDENCE_LEVEL,
            "confidence_interval_method": "wilson_score_binomial",
            "confidence_interval_low": self.confidence_interval_low,
            "confidence_interval_high": self.confidence_interval_high,
        }


def _metric(metric_id: str, numerator: int, denominator: int) -> PoseBustersCorpusAuditMetric:
    proportion = numerator / denominator
    z2 = POSEBUSTERS_CORPUS_AUDIT_Z**2
    scale = 1.0 + z2 / denominator
    center = (proportion + z2 / (2.0 * denominator)) / scale
    radius = (
        POSEBUSTERS_CORPUS_AUDIT_Z
        * math.sqrt(
            proportion * (1.0 - proportion) / denominator
            + z2 / (4.0 * denominator**2)
        )
        / scale
    )
    return PoseBustersCorpusAuditMetric(
        metric_id=metric_id,
        numerator=numerator,
        denominator=denominator,
        estimate=proportion,
        confidence_interval_low=min(
            proportion,
            max(0.0, center - radius),
        ),
        confidence_interval_high=max(
            proportion,
            min(1.0, center + radius),
        ),
    )


def _summary_metrics(
    rows: Sequence[PoseBustersCorpusCaseAudit],
) -> tuple[PoseBustersCorpusAuditMetric, ...]:
    denominator = len(rows)
    predicates = (
        ("corpus_audited_rate", lambda row: row.audited),
        (
            "heavy_connectivity_match_rate",
            lambda row: row.audited
            and row.heavy_graph_comparison is not None
            and row.heavy_graph_comparison.graph_match,
        ),
        (
            "raw_directional_bond_stereo_match_rate",
            lambda row: row.audited
            and row.heavy_graph_comparison is not None
            and row.heavy_graph_comparison.directional_stereo_match,
        ),
        (
            "raw_aromatic_bond_presence_rate",
            lambda row: row.audited and row.native_raw_aromatic_bond_count > 0,
        ),
        (
            "raw_aromatic_bond_count_match_rate",
            lambda row: row.audited
            and row.native_raw_aromatic_bond_count
            == row.start_raw_aromatic_bond_count,
        ),
        (
            "ligand_element_scope_rate",
            lambda row: row.audited and not row.unsupported_ligand_atomic_numbers,
        ),
        (
            "receptor_element_scope_rate",
            lambda row: row.audited and not row.unsupported_receptor_atomic_numbers,
        ),
        (
            "formal_charge_scope_rate",
            lambda row: row.audited
            and row.receptor_maximum_absolute_atom_formal_charge
            <= POSEBUSTERS_CORPUS_AUDIT_MAXIMUM_ABSOLUTE_FORMAL_CHARGE
            and row.native_ligand_maximum_absolute_atom_formal_charge
            <= POSEBUSTERS_CORPUS_AUDIT_MAXIMUM_ABSOLUTE_FORMAL_CHARGE,
        ),
        (
            "ligand_atom_capacity_scope_rate",
            lambda row: row.audited
            and row.native_ligand_atom_count
            <= POSEBUSTERS_CORPUS_AUDIT_MAX_LIGAND_ATOMS
            and row.start_ligand_atom_count
            <= POSEBUSTERS_CORPUS_AUDIT_MAX_LIGAND_ATOMS,
        ),
        (
            "metal_free_rate",
            lambda row: row.audited
            and not row.metal_atomic_numbers,
        ),
        (
            "nonwater_cofactor_free_rate",
            lambda row: row.audited
            and not row.receptor_nonwater_nonpolymer_residue_names,
        ),
        (
            "reference_scorer_chemistry_scope_rate",
            lambda row: row.audited
            and row.reference_scorer_scope_blockers == (_PARAMETER_BLOCKER,),
        ),
        (
            "reference_scorer_admission_rate",
            lambda row: row.audited
            and row.reference_scorer_scope_status == "admitted",
        ),
    )
    return tuple(
        _metric(metric_id, sum(bool(predicate(row)) for row in rows), denominator)
        for metric_id, predicate in predicates
    )


@dataclass(frozen=True, slots=True)
class PoseBustersCorpusAuditReceipt:
    archive_intake_receipt_sha256: str
    archive_contract_sha256: str
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    case_rows: tuple[PoseBustersCorpusCaseAudit, ...]
    metrics: tuple[PoseBustersCorpusAuditMetric, ...]
    schema_id: str = POSEBUSTERS_CORPUS_AUDIT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_CORPUS_AUDIT_SCHEMA_ID:
            raise PoseBustersCorpusAuditError("unsupported corpus-audit schema")
        for name in (
            "archive_intake_receipt_sha256",
            "archive_contract_sha256",
            "implementation_source_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        source_members = tuple(
            (
                _token(role, name="implementation source role"),
                _digest(digest, name=f"{role} implementation source SHA-256"),
            )
            for role, digest in self.implementation_source_members
        )
        if (
            tuple(role for role, _digest_value in source_members)
            != _IMPLEMENTATION_SOURCE_ROLES
            or len({role for role, _digest_value in source_members})
            != len(source_members)
            or self.implementation_source_sha256
            != _canonical_sha256(dict(source_members))
        ):
            raise PoseBustersCorpusAuditError(
                "corpus audit implementation-source identity is inconsistent"
            )
        rows = tuple(self.case_rows)
        if (
            not rows
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
        ):
            raise PoseBustersCorpusAuditError(
                "corpus audit rows must be non-empty canonical unique cases"
            )
        expected_metrics = _summary_metrics(rows)
        if tuple(metric.to_dict() for metric in self.metrics) != tuple(
            metric.to_dict() for metric in expected_metrics
        ):
            raise PoseBustersCorpusAuditError(
                "corpus audit metrics do not match all-case rows"
            )
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "metrics", expected_metrics)
        object.__setattr__(self, "implementation_source_members", source_members)

    @property
    def audited_case_count(self) -> int:
        return sum(row.audited for row in self.case_rows)

    @property
    def input_identity_ready(self) -> bool:
        return (
            self.archive_contract_sha256
            == OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT.fingerprint_sha256
            and self.audited_case_count == len(self.case_rows)
        )

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "archive_intake_receipt_sha256": self.archive_intake_receipt_sha256,
            "archive_contract_sha256": self.archive_contract_sha256,
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": {
                role: digest for role, digest in self.implementation_source_members
            },
            "parser_contract": {
                "pdb_parser_name": PDB_PARSER_NAME,
                "pdb_parser_version": PDB_PARSER_VERSION,
                "pdb_connectivity_policy": "record_unrepresented",
                "pdb_crystallographic_cell_policy": "record_only",
                "sdf_parser_name": SDF_PARSER_NAME,
                "sdf_parser_version": SDF_PARSER_VERSION,
                "heavy_graph_policy": (
                    "connectivity_and_raw_directional_v2000_bond_stereo_separate"
                ),
                "aromatic_inventory_policy": (
                    "raw_v2000_bond_type_4_only_without_aromaticity_perception"
                ),
                "aromaticity_perception_performed": False,
                "atom_stereo_perception_performed": False,
            },
            "scope_contract": {
                "reference_scorer_supported_atomic_numbers": list(
                    DEFAULT_SUPPORTED_DOCKING_ATOMIC_NUMBERS
                ),
                "reference_scorer_maximum_absolute_atom_formal_charge": (
                    POSEBUSTERS_CORPUS_AUDIT_MAXIMUM_ABSOLUTE_FORMAL_CHARGE
                ),
                "reference_scorer_maximum_ligand_atoms": (
                    POSEBUSTERS_CORPUS_AUDIT_MAX_LIGAND_ATOMS
                ),
                "operational_metal_atomic_numbers": list(
                    POSEBUSTERS_CORPUS_AUDIT_METAL_ATOMIC_NUMBERS
                ),
                "water_residue_names": list(POSEBUSTERS_CORPUS_AUDIT_WATER_RESIDUES),
                "no_case_can_be_admitted_without_partial_charges_and_parameters": True,
            },
            "all_case_denominator": len(self.case_rows),
            "audited_case_count": self.audited_case_count,
            "failed_case_count": len(self.case_rows) - self.audited_case_count,
            "case_rows": [row.to_dict() for row in self.case_rows],
            "metrics": [metric.to_dict() for metric in self.metrics],
            "input_identity_ready": self.input_identity_ready,
            "archive_extracted": False,
            "external_stereo_oracle_present": False,
            "target_family_metrics_present": False,
            "pose_preparation_performed": False,
            "pose_generation_performed": False,
            "pose_validity_evaluated": False,
            "pose_scoring_evaluated": False,
            "benchmark_executed": False,
            "scientific_blockers": list(POSEBUSTERS_CORPUS_AUDIT_BLOCKERS),
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
                raise PoseBustersCorpusAuditError(
                    "PoseBusters corpus audit output already exists"
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


def _read_member(
    archive: zipfile.ZipFile,
    member_name: str,
    *,
    expected_sha256: str,
    expected_size: int,
) -> bytes:
    try:
        info = archive.getinfo(member_name)
    except KeyError as exc:
        raise PoseBustersCorpusAuditError("required corpus member is missing") from exc
    if (
        info.is_dir()
        or info.file_size != expected_size
        or info.file_size < 1
        or info.file_size > POSEBUSTERS_ARCHIVE_MAX_MEMBER_BYTES
    ):
        raise PoseBustersCorpusAuditError("corpus member size identity is invalid")
    chunks: list[bytes] = []
    observed = 0
    digest = hashlib.sha256()
    try:
        with archive.open(info, "r") as handle:
            while True:
                chunk = handle.read(POSEBUSTERS_ARCHIVE_STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                observed += len(chunk)
                if observed > expected_size:
                    raise PoseBustersCorpusAuditError(
                        "corpus member exceeded its frozen size"
                    )
                digest.update(chunk)
                chunks.append(chunk)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise PoseBustersCorpusAuditError(
            "corpus member failed CRC-checked streaming"
        ) from exc
    if observed != expected_size or digest.hexdigest() != expected_sha256:
        raise PoseBustersCorpusAuditError("corpus member identity verification failed")
    return b"".join(chunks)


def _directional_stereo_count(system: Any) -> int:
    return sum(
        str(bond.stereo).strip().lower() not in {"", "none", "unknown", "unspecified"}
        for bond in system.bonds
    )


def _failure_row(case_id: str, error_code: str) -> PoseBustersCorpusCaseAudit:
    return PoseBustersCorpusCaseAudit(
        case_id=case_id,
        status=_FAILURE_STATUS,
        error_code=error_code,
    )


def _audit_case(
    archive: zipfile.ZipFile,
    intake_row: Any,
) -> PoseBustersCorpusCaseAudit:
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
    except PDBParseError:
        return _failure_row(intake_row.case_id, "receptor_parse_failed")
    try:
        native = parse_sdf_v2000(
            sources["reference_ligand_sdf"],
            source_id=f"{intake_row.case_id}:native",
        )
    except SDFParseError:
        return _failure_row(intake_row.case_id, "native_ligand_parse_failed")
    try:
        start = parse_sdf_v2000(
            sources["ligand_start_conformer_sdf"],
            source_id=f"{intake_row.case_id}:start",
        )
    except SDFParseError:
        return _failure_row(intake_row.case_id, "start_ligand_parse_failed")
    try:
        comparison = compare_public_ligand_heavy_atom_graphs(native, start)
    except PublicReferenceMaterializationError:
        return _failure_row(intake_row.case_id, "heavy_graph_comparison_failed")

    polymer_atom_count = sum(
        len(residue.atom_indices)
        for residue in receptor.residues
        if residue.entity_type.strip().lower() == "polymer"
    )
    nonwater_names = tuple(
        sorted(
            {
                residue.name.strip().upper()
                for residue in receptor.residues
                if residue.entity_type.strip().lower() != "polymer"
                and residue.name.strip().upper()
                not in POSEBUSTERS_CORPUS_AUDIT_WATER_RESIDUES
            }
        )
    )
    receptor_numbers = tuple(atom.atomic_number for atom in receptor.atoms)
    native_numbers = tuple(atom.atomic_number for atom in native.atoms)
    receptor_formal_charges = tuple(atom.formal_charge for atom in receptor.atoms)
    native_formal_charges = tuple(atom.formal_charge for atom in native.atoms)
    all_numbers = set((*receptor_numbers, *native_numbers))
    metals = tuple(
        sorted(all_numbers.intersection(POSEBUSTERS_CORPUS_AUDIT_METAL_ATOMIC_NUMBERS))
    )
    supported = set(DEFAULT_SUPPORTED_DOCKING_ATOMIC_NUMBERS)
    unsupported_receptor = tuple(sorted(set(receptor_numbers) - supported))
    unsupported_ligand = tuple(sorted(set(native_numbers) - supported))
    receptor_maximum_charge = max(map(abs, receptor_formal_charges), default=0)
    ligand_maximum_charge = max(map(abs, native_formal_charges), default=0)
    scope_status, scope_blockers = _scope_disposition(
        unsupported_receptor=unsupported_receptor,
        unsupported_ligand=unsupported_ligand,
        receptor_maximum_absolute_atom_formal_charge=receptor_maximum_charge,
        ligand_maximum_absolute_atom_formal_charge=ligand_maximum_charge,
        native_ligand_atom_count=native.atom_count,
        start_ligand_atom_count=start.atom_count,
        metals=metals,
        nonwater_names=nonwater_names,
    )
    native_heavy = sum(atom.atomic_number != 1 for atom in native.atoms)
    start_heavy = sum(atom.atomic_number != 1 for atom in start.atoms)
    return PoseBustersCorpusCaseAudit(
        case_id=intake_row.case_id,
        status=_AUDITED_STATUS,
        error_code="",
        receptor_atom_count=receptor.atom_count,
        receptor_polymer_atom_count=polymer_atom_count,
        receptor_nonpolymer_atom_count=receptor.atom_count - polymer_atom_count,
        receptor_element_counts=_element_counts(receptor_numbers),
        receptor_formal_charge=sum(receptor_formal_charges),
        receptor_maximum_absolute_atom_formal_charge=receptor_maximum_charge,
        receptor_nonwater_nonpolymer_residue_names=nonwater_names,
        metal_atomic_numbers=metals,
        native_ligand_atom_count=native.atom_count,
        native_ligand_heavy_atom_count=native_heavy,
        start_ligand_atom_count=start.atom_count,
        start_ligand_heavy_atom_count=start_heavy,
        ligand_element_counts=_element_counts(native_numbers),
        ligand_formal_charge=sum(native_formal_charges),
        native_ligand_maximum_absolute_atom_formal_charge=ligand_maximum_charge,
        native_raw_aromatic_bond_count=sum(bond.aromatic for bond in native.bonds),
        start_raw_aromatic_bond_count=sum(bond.aromatic for bond in start.bonds),
        native_directional_stereo_bond_count=_directional_stereo_count(native),
        start_directional_stereo_bond_count=_directional_stereo_count(start),
        unsupported_receptor_atomic_numbers=unsupported_receptor,
        unsupported_ligand_atomic_numbers=unsupported_ligand,
        reference_scorer_scope_status=scope_status,
        reference_scorer_scope_blockers=scope_blockers,
        heavy_graph_comparison=comparison,
    )


def materialize_posebusters_corpus_audit(
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersCorpusAuditReceipt:
    """Materialize the bounded corpus audit after exact intake reexecution."""

    try:
        intake = verify_posebusters_archive_intake_receipt(
            intake_receipt_path,
            archive_path,
            selection_path,
            contract=contract,
        )
    except PoseBustersArchiveIntakeError as exc:
        raise PoseBustersCorpusAuditError(
            "PoseBusters archive intake receipt did not verify"
        ) from exc
    if intake.ready_case_count != len(intake.case_rows):
        raise PoseBustersCorpusAuditError(
            "corpus audit requires every archive-intake case to be ready"
        )
    descriptor, size = _regular_file_descriptor(
        archive_path,
        maximum_bytes=contract.archive_size_bytes,
    )
    try:
        if size != contract.archive_size_bytes or _hash_descriptor(descriptor, size) != contract.archive_sha256:
            raise PoseBustersCorpusAuditError(
                "corpus archive changed after intake verification"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            try:
                with zipfile.ZipFile(handle, "r") as archive:
                    rows = tuple(_audit_case(archive, row) for row in intake.case_rows)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise PoseBustersCorpusAuditError(
                    "corpus archive failed bounded ZIP access"
                ) from exc
    finally:
        os.close(descriptor)
    implementation_source_members = _implementation_source_members()
    implementation_source_sha256 = _canonical_sha256(
        dict(implementation_source_members)
    )
    metrics = _summary_metrics(rows)
    return PoseBustersCorpusAuditReceipt(
        archive_intake_receipt_sha256=intake.fingerprint_sha256,
        archive_contract_sha256=contract.fingerprint_sha256,
        implementation_source_sha256=implementation_source_sha256,
        implementation_source_members=implementation_source_members,
        case_rows=rows,
        metrics=metrics,
    )


def verify_posebusters_corpus_audit_receipt(
    audit_receipt_path: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    *,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersCorpusAuditReceipt:
    """Require byte-exact corpus-audit reexecution equality."""

    source = _read_exact_regular_file(
        audit_receipt_path,
        maximum_bytes=POSEBUSTERS_CORPUS_AUDIT_MAX_RECEIPT_BYTES,
    )
    expected = materialize_posebusters_corpus_audit(
        archive_path,
        selection_path,
        intake_receipt_path,
        contract=contract,
    )
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersCorpusAuditError(
            "PoseBusters corpus audit receipt does not match exact reexecution"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-corpus-audit",
        description=(
            "Audit the exact PoseBusters 308 corpus without extraction or docking."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--archive", required=True)
    materialize.add_argument("--selection", required=True)
    materialize.add_argument("--intake-receipt", required=True)
    materialize.add_argument("--output", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--archive", required=True)
    verify.add_argument("--selection", required=True)
    verify.add_argument("--intake-receipt", required=True)
    verify.add_argument("--audit-receipt", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "materialize":
        receipt = materialize_posebusters_corpus_audit(
            args.archive,
            args.selection,
            args.intake_receipt,
        )
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_corpus_audit_receipt(
            args.audit_receipt,
            args.archive,
            args.selection,
            args.intake_receipt,
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "audited_case_count": receipt.audited_case_count,
                "input_identity_ready": receipt.input_identity_ready,
                "benchmark_executed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_CORPUS_AUDIT_BLOCKERS",
    "POSEBUSTERS_CORPUS_AUDIT_CONFIDENCE_LEVEL",
    "POSEBUSTERS_CORPUS_AUDIT_MAX_IMPLEMENTATION_SOURCE_BYTES",
    "POSEBUSTERS_CORPUS_AUDIT_MAX_LIGAND_ATOMS",
    "POSEBUSTERS_CORPUS_AUDIT_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_CORPUS_AUDIT_MAXIMUM_ABSOLUTE_FORMAL_CHARGE",
    "POSEBUSTERS_CORPUS_AUDIT_METAL_ATOMIC_NUMBERS",
    "POSEBUSTERS_CORPUS_AUDIT_METRIC_SCHEMA_ID",
    "POSEBUSTERS_CORPUS_AUDIT_SCHEMA_ID",
    "POSEBUSTERS_CORPUS_AUDIT_WATER_RESIDUES",
    "POSEBUSTERS_CORPUS_CASE_AUDIT_SCHEMA_ID",
    "PoseBustersCorpusAuditError",
    "PoseBustersCorpusAuditMetric",
    "PoseBustersCorpusAuditReceipt",
    "PoseBustersCorpusCaseAudit",
    "main",
    "materialize_posebusters_corpus_audit",
    "verify_posebusters_corpus_audit_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
