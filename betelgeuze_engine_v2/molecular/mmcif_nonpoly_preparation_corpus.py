"""Frozen executable corpus for bounded nonpoly preparation coverage.

The corpus is intentionally synthetic and small.  It freezes exact ASCII mmCIF
inputs for the first neutral, acyclic C/O/H preparation profile, retains both
supported and expected-failure rows, and classifies every declared coverage
axis.  It is a contract-regression corpus, not scientific validation data and
not a parameter-fitting dataset.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from types import MappingProxyType
from typing import Any, Mapping

from betelgeuze_engine_v2.parameter_source_provenance import (
    PARAMETER_SOURCE_PROVENANCE_PROFILE_ID,
    PARAMETER_SOURCE_PROVENANCE_REVIEW_VERSION,
    reviewed_parameter_source_provenance,
)

from .mmcif_atom_site_model_policy import (
    MMCIF_ATOM_SITE_MODEL_POLICY_PARSER_VERSION,
    MMCIF_ATOM_SITE_MODEL_POLICY_PROFILE_ID,
    parse_mmcif_atom_site_model_policy,
)
from .mmcif_biological_assembly_policy import (
    MMCIF_BIOLOGICAL_ASSEMBLY_DEFINITION_HEADERS,
    MMCIF_BIOLOGICAL_ASSEMBLY_GENERATOR_HEADERS,
    MMCIF_BIOLOGICAL_ASSEMBLY_OPERATOR_HEADERS,
    MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PARSER_VERSION,
    MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROFILE_ID,
    parse_mmcif_biological_assembly_policy,
)
from .mmcif_missing_atom_residue_policy import (
    MMCIF_MISSING_ATOM_RESIDUE_POLICY_PARSER_VERSION,
    MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROFILE_ID,
    parse_mmcif_missing_atom_residue_policy,
)
from .mmcif_nonpoly_atom_site_observations import (
    MMCIF_NONPOLY_ATOM_SITE_HEADERS,
    MmcifNonpolyAtomSiteObservationError,
)
from .mmcif_nonpoly_all_atom_systems import (
    MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION,
    MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID,
    parse_mmcif_nonpoly_all_atom_systems,
)
from .mmcif_modified_residue_declarations import (
    MMCIF_MODIFIED_RESIDUE_DECLARATION_HEADERS,
    MMCIF_MODIFIED_RESIDUE_DECLARATION_PARSER_VERSION,
    MMCIF_MODIFIED_RESIDUE_DECLARATION_PROFILE_ID,
    parse_mmcif_modified_residue_declarations,
)
from .mmcif_nonpoly_component_declarations import (
    MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS,
    MMCIF_NONPOLY_COMPONENT_BOND_HEADERS,
)
from .mmcif_nonpoly_component_roles import (
    MMCIF_NONPOLY_COMPONENT_ROLE_PARSER_VERSION,
    MMCIF_NONPOLY_COMPONENT_ROLE_PROFILE_ID,
    parse_mmcif_nonpoly_component_roles,
)
from .mmcif_nonpoly_preparation import (
    MMCIF_NONPOLY_PREPARATION_PARSER_VERSION,
    MMCIF_NONPOLY_PREPARATION_PROFILE_ID,
    MMCIF_PREPARATION_UNIVERSAL_PARAMETERABILITY_BLOCKERS,
    MmcifNonpolyPreparationError,
    parse_mmcif_nonpoly_preparation,
)
from .mmcif_nonpoly_hydrogen_coordinates import (
    MMCIF_NONPOLY_HYDROGEN_COORDINATE_GENERATOR_VERSION,
    MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROFILE_ID,
    parse_mmcif_nonpoly_hydrogen_coordinates,
)
from .mmcif_struct_conn_declarations import MMCIF_STRUCT_CONN_HEADERS
from .mmcif_zero_occupancy import (
    MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS,
)


MMCIF_NONPOLY_PREPARATION_CORPUS_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_preparation_corpus_projection/1.0.0"
)
MMCIF_NONPOLY_PREPARATION_CORPUS_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_preparation_corpus_source_binding/1.0.0"
)
MMCIF_NONPOLY_PREPARATION_CORPUS_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_preparation_corpus_document/1.0.0"
)
MMCIF_NONPOLY_PREPARATION_CORPUS_PROFILE_ID = (
    "frozen_bounded_neutral_coh_preparation_corpus/1.0.0"
)
MMCIF_NONPOLY_PREPARATION_CORPUS_RUNNER_VERSION = "1.0.0"
FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_SNAPSHOT_SHA256 = (
    "d01d6620930c876eadf133561eeebf634f81cc8b9b45478bde2034aaa9e74b32"
)

_ENTITY_HEADERS = ("_entity.id", "_entity.type")
_ASYM_HEADERS = ("_struct_asym.id", "_struct_asym.entity_id")
_ENTITY_POLY_HEADERS = ("_entity_poly.entity_id", "_entity_poly.type")
_ENTITY_POLY_SEQ_HEADERS = (
    "_entity_poly_seq.entity_id",
    "_entity_poly_seq.num",
    "_entity_poly_seq.mon_id",
    "_entity_poly_seq.hetero",
)
_CHEM_COMP_HEADERS = (
    "_chem_comp.id",
    "_chem_comp.type",
    "_chem_comp.pdbx_formal_charge",
)
_ENTITY_NONPOLY_HEADERS = (
    "_pdbx_entity_nonpoly.entity_id",
    "_pdbx_entity_nonpoly.name",
    "_pdbx_entity_nonpoly.comp_id",
)
_SCHEME_HEADERS = (
    "_pdbx_nonpoly_scheme.asym_id",
    "_pdbx_nonpoly_scheme.entity_id",
    "_pdbx_nonpoly_scheme.mon_id",
    "_pdbx_nonpoly_scheme.ndb_seq_num",
    "_pdbx_nonpoly_scheme.pdb_seq_num",
    "_pdbx_nonpoly_scheme.auth_seq_num",
    "_pdbx_nonpoly_scheme.pdb_mon_id",
    "_pdbx_nonpoly_scheme.auth_mon_id",
    "_pdbx_nonpoly_scheme.pdb_strand_id",
    "_pdbx_nonpoly_scheme.pdb_ins_code",
)

_UNIVERSAL_BLOCKERS = tuple(MMCIF_PREPARATION_UNIVERSAL_PARAMETERABILITY_BLOCKERS)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyPreparationCorpusError(ValueError):
    """The frozen corpus, expectation, or coverage ledger drifted."""


@dataclass(frozen=True, slots=True)
class MmcifPreparationCorpusAtom:
    atom_id: str
    element: str
    formal_charge: str = "0"
    aromatic_flag: str = "N"
    stereo_config: str = "N"
    site_element: str | None = None
    site_formal_charge: str | None = None


@dataclass(frozen=True, slots=True)
class MmcifPreparationCorpusBond:
    atom_id_1: str
    atom_id_2: str
    order_code: str
    aromatic_flag: str = "N"
    stereo_config: str = "N"


@dataclass(frozen=True, slots=True)
class MmcifPreparationCorpusExpectedReport:
    component_id: str
    preparation_status: str
    chemistry_blockers: tuple[str, ...]
    parameterability_status: str
    parameterability_blockers: tuple[str, ...]
    formula: tuple[tuple[str, int], ...]
    total_formal_charge: int | None
    added_hydrogen_count: int
    prepared_atom_count: int
    prepared_bond_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "preparation_status": self.preparation_status,
            "chemistry_blockers": list(self.chemistry_blockers),
            "parameterability_status": self.parameterability_status,
            "parameterability_blockers": list(self.parameterability_blockers),
            "formula": dict(self.formula),
            "total_formal_charge": self.total_formal_charge,
            "added_hydrogen_count": self.added_hydrogen_count,
            "prepared_atom_count": self.prepared_atom_count,
            "prepared_bond_count": self.prepared_bond_count,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifPreparationCorpusCase:
    case_id: str
    cohort: str
    source_text: str
    input_sha256: str
    source_features: tuple[str, ...]
    expected_reports: tuple[MmcifPreparationCorpusExpectedReport, ...] = ()
    expected_error_code: str = ""

    def __repr__(self) -> str:
        return (
            "MmcifPreparationCorpusCase("
            f"case_id={self.case_id!r}, cohort={self.cohort!r})"
        )

    def binding_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "cohort": self.cohort,
            "input_sha256": self.input_sha256,
            "input_byte_count": len(self.source_text.encode("ascii")),
            "source_features": list(self.source_features),
            "expected_reports": [row.to_dict() for row in self.expected_reports],
            "expected_error_code": self.expected_error_code,
        }


@dataclass(frozen=True, slots=True)
class MmcifPreparationCoverageRow:
    coverage_id: str
    scope_area: str
    policy_status: str
    expected_signal: str
    evidence_case_ids: tuple[str, ...]
    blocker: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_id": self.coverage_id,
            "scope_area": self.scope_area,
            "policy_status": self.policy_status,
            "expected_signal": self.expected_signal,
            "evidence_case_ids": list(self.evidence_case_ids),
            "blocker": self.blocker,
            "parameter_fitting_eligible": False,
        }


@dataclass(frozen=True, slots=True)
class MmcifPreparationCorpusCaseResult:
    case_id: str
    cohort: str
    input_sha256: str
    observed_outcome: str
    preparation_snapshot_sha256: str
    atom_site_model_policy_snapshot_sha256: str
    biological_assembly_policy_snapshot_sha256: str
    missing_atom_residue_policy_snapshot_sha256: str
    hydrogen_coordinate_snapshot_sha256: str
    all_atom_system_snapshot_sha256: str
    component_role_snapshot_sha256: str
    modified_residue_declaration_snapshot_sha256: str
    error_code: str
    reports: tuple[Mapping[str, Any], ...]
    atom_site_model_policy: Mapping[str, Any]
    biological_assembly_policy: Mapping[str, Any]
    missing_atom_residue_policy: Mapping[str, Any]
    hydrogen_coordinate_summary: Mapping[str, Any]
    all_atom_system_summary: Mapping[str, Any]
    component_roles: tuple[Mapping[str, Any], ...]
    modified_residue_declarations: tuple[Mapping[str, Any], ...]
    signals: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "cohort": self.cohort,
            "input_sha256": self.input_sha256,
            "observed_outcome": self.observed_outcome,
            "expectation_matched": True,
            "preparation_snapshot_sha256": self.preparation_snapshot_sha256,
            "atom_site_model_policy_snapshot_sha256": (
                self.atom_site_model_policy_snapshot_sha256
            ),
            "biological_assembly_policy_snapshot_sha256": (
                self.biological_assembly_policy_snapshot_sha256
            ),
            "missing_atom_residue_policy_snapshot_sha256": (
                self.missing_atom_residue_policy_snapshot_sha256
            ),
            "hydrogen_coordinate_snapshot_sha256": (
                self.hydrogen_coordinate_snapshot_sha256
            ),
            "all_atom_system_snapshot_sha256": (
                self.all_atom_system_snapshot_sha256
            ),
            "component_role_snapshot_sha256": self.component_role_snapshot_sha256,
            "modified_residue_declaration_snapshot_sha256": (
                self.modified_residue_declaration_snapshot_sha256
            ),
            "error_code": self.error_code,
            "reports": [dict(row) for row in self.reports],
            "atom_site_model_policy": dict(self.atom_site_model_policy),
            "biological_assembly_policy": dict(self.biological_assembly_policy),
            "missing_atom_residue_policy": dict(
                self.missing_atom_residue_policy
            ),
            "hydrogen_coordinate_summary": dict(self.hydrogen_coordinate_summary),
            "all_atom_system_summary": dict(self.all_atom_system_summary),
            "component_roles": [dict(row) for row in self.component_roles],
            "modified_residue_declarations": [
                dict(row) for row in self.modified_residue_declarations
            ],
            "signals": list(self.signals),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyPreparationCorpusSnapshot:
    case_results: tuple[MmcifPreparationCorpusCaseResult, ...]
    coverage_rows: tuple[MmcifPreparationCoverageRow, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyPreparationCorpusSnapshot("
            f"case_count={len(self.case_results)}, "
            f"coverage_row_count={len(self.coverage_rows)})"
        )

    @property
    def corpus_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_preparation_corpus_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_preparation_corpus_source_binding())

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_PREPARATION_CORPUS_DOCUMENT_SCHEMA_ID,
                "corpus_projection_sha256": self.corpus_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        cohorts = sorted({row.cohort for row in self.case_results})
        statuses = sorted({row.policy_status for row in self.coverage_rows})
        return {
            "schema_id": MMCIF_NONPOLY_PREPARATION_CORPUS_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_PREPARATION_CORPUS_PROFILE_ID,
            "runner_version": MMCIF_NONPOLY_PREPARATION_CORPUS_RUNNER_VERSION,
            "case_count": len(self.case_results),
            "cohort_counts": {
                value: sum(row.cohort == value for row in self.case_results)
                for value in cohorts
            },
            "coverage_row_count": len(self.coverage_rows),
            "coverage_status_counts": {
                value: sum(row.policy_status == value for row in self.coverage_rows)
                for value in statuses
            },
            "unclassified_coverage_row_count": 0,
            "expectation_mismatch_count": 0,
            "parameter_fitting_allowed": False,
            "v2_1_exit_ready": False,
            "corpus_projection_sha256": self.corpus_projection_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _claim_policy() -> dict[str, bool]:
    return {
        "exact_ascii_inputs_frozen": True,
        "input_sha256_bound": True,
        "supported_and_failure_cohorts_retained": True,
        "failure_complete_case_rows": True,
        "declared_coverage_axes_classified": True,
        "expectations_executed_against_current_parser": True,
        "reviewed_parameter_source_provenance_bound": True,
        "canonical_all_atom_materialization_bound": True,
        "corpus_is_parameter_fitting_data": False,
        "parameter_fitting_allowed": False,
        "v2_1_exit_ready": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _loop(headers: tuple[str, ...], rows: tuple[Mapping[str, str], ...]) -> str:
    if not rows:
        raise MmcifNonpolyPreparationCorpusError("corpus loop rows must be non-empty")
    lines = ["loop_", *headers]
    lines.extend(" ".join(row[header] for header in headers) for row in rows)
    lines.append("#")
    return "\n".join(lines) + "\n"


def _atom_row(atom: MmcifPreparationCorpusAtom, ordinal: int) -> dict[str, str]:
    return {
        "_chem_comp_atom.comp_id": "LIG",
        "_chem_comp_atom.atom_id": atom.atom_id,
        "_chem_comp_atom.type_symbol": atom.element,
        "_chem_comp_atom.charge": atom.formal_charge,
        "_chem_comp_atom.pdbx_aromatic_flag": atom.aromatic_flag,
        "_chem_comp_atom.pdbx_stereo_config": atom.stereo_config,
        "_chem_comp_atom.pdbx_ordinal": str(ordinal),
    }


def _bond_row(bond: MmcifPreparationCorpusBond, ordinal: int) -> dict[str, str]:
    return {
        "_chem_comp_bond.comp_id": "LIG",
        "_chem_comp_bond.atom_id_1": bond.atom_id_1,
        "_chem_comp_bond.atom_id_2": bond.atom_id_2,
        "_chem_comp_bond.value_order": bond.order_code,
        "_chem_comp_bond.pdbx_aromatic_flag": bond.aromatic_flag,
        "_chem_comp_bond.pdbx_stereo_config": bond.stereo_config,
        "_chem_comp_bond.pdbx_ordinal": str(ordinal),
    }


def _site_row(
    atom: MmcifPreparationCorpusAtom,
    source_id: int,
    *,
    label_alt_id: str = ".",
    insertion_code: str = ".",
) -> dict[str, str]:
    return {
        "_atom_site.group_pdb": "HETATM",
        "_atom_site.id": str(source_id),
        "_atom_site.type_symbol": atom.site_element or atom.element,
        "_atom_site.label_atom_id": atom.atom_id,
        "_atom_site.label_alt_id": label_alt_id,
        "_atom_site.label_comp_id": "LIG",
        "_atom_site.label_asym_id": "L",
        "_atom_site.label_entity_id": "1",
        "_atom_site.label_seq_id": ".",
        "_atom_site.cartn_x": f"{source_id}.0",
        "_atom_site.cartn_y": f"{source_id + 1}.0",
        "_atom_site.cartn_z": f"{source_id + 2}.0",
        "_atom_site.occupancy": "1.0",
        "_atom_site.b_iso_or_equiv": "10.0",
        "_atom_site.pdbx_formal_charge": (
            atom.formal_charge
            if atom.site_formal_charge is None
            else atom.site_formal_charge
        ),
        "_atom_site.auth_seq_id": "501",
        "_atom_site.auth_comp_id": "LIG",
        "_atom_site.auth_asym_id": "L",
        "_atom_site.auth_atom_id": atom.atom_id,
        "_atom_site.pdbx_pdb_model_num": "1",
        "_atom_site.pdbx_pdb_ins_code": insertion_code,
    }


def _water_atom_row() -> dict[str, str]:
    return {
        "_chem_comp_atom.comp_id": "HOH",
        "_chem_comp_atom.atom_id": "O",
        "_chem_comp_atom.type_symbol": "O",
        "_chem_comp_atom.charge": "0",
        "_chem_comp_atom.pdbx_aromatic_flag": "N",
        "_chem_comp_atom.pdbx_stereo_config": "N",
        "_chem_comp_atom.pdbx_ordinal": "1",
    }


def _water_site_row(source_id: int, *, model_number: str = "1") -> dict[str, str]:
    return {
        "_atom_site.group_pdb": "HETATM",
        "_atom_site.id": str(source_id),
        "_atom_site.type_symbol": "O",
        "_atom_site.label_atom_id": "O",
        "_atom_site.label_alt_id": "?",
        "_atom_site.label_comp_id": "HOH",
        "_atom_site.label_asym_id": "W",
        "_atom_site.label_entity_id": "2",
        "_atom_site.label_seq_id": "?",
        "_atom_site.cartn_x": "20.0",
        "_atom_site.cartn_y": "21.0",
        "_atom_site.cartn_z": "22.0",
        "_atom_site.occupancy": "1.0",
        "_atom_site.b_iso_or_equiv": "10.0",
        "_atom_site.pdbx_formal_charge": "0",
        "_atom_site.auth_seq_id": "601",
        "_atom_site.auth_comp_id": "HOH",
        "_atom_site.auth_asym_id": "W",
        "_atom_site.auth_atom_id": "O",
        "_atom_site.pdbx_pdb_model_num": model_number,
        "_atom_site.pdbx_pdb_ins_code": "?",
    }


def _corpus_source(
    atoms: tuple[MmcifPreparationCorpusAtom, ...],
    bonds: tuple[MmcifPreparationCorpusBond, ...],
    *,
    connection_type: str = "metalc",
    connection_order: str = "?",
    modified_residue: bool = False,
    water_model_number: str = "1",
    ligand_alt_id: str = ".",
    ligand_insertion_code: str = ".",
    observation_gap: str = "",
    biological_assembly: bool = False,
) -> str:
    if not atoms:
        raise MmcifNonpolyPreparationCorpusError(
            "corpus ligand atoms must be non-empty"
        )
    atom_ids = [row.atom_id for row in atoms]
    if len(set(atom_ids)) != len(atom_ids):
        raise MmcifNonpolyPreparationCorpusError("corpus atom IDs must be unique")
    atom_rows = tuple(
        _atom_row(atom, ordinal) for ordinal, atom in enumerate(atoms, start=1)
    ) + (_water_atom_row(),)
    bond_rows = tuple(
        _bond_row(bond, ordinal) for ordinal, bond in enumerate(bonds, start=1)
    )
    site_rows = tuple(
        _site_row(
            atom,
            source_id,
            label_alt_id=ligand_alt_id,
            insertion_code=ligand_insertion_code,
        )
        for source_id, atom in enumerate(atoms, start=1)
    ) + (_water_site_row(len(atoms) + 1, model_number=water_model_number),)
    connection = {
        "_struct_conn.id": "conn-1",
        "_struct_conn.conn_type_id": connection_type,
        "_struct_conn.ptnr1_label_asym_id": "L",
        "_struct_conn.ptnr1_label_comp_id": "LIG",
        "_struct_conn.ptnr1_label_seq_id": ".",
        "_struct_conn.ptnr1_label_atom_id": atoms[0].atom_id,
        "_struct_conn.pdbx_ptnr1_label_alt_id": ".",
        "_struct_conn.pdbx_ptnr1_pdb_ins_code": ligand_insertion_code,
        "_struct_conn.ptnr1_symmetry": "1_555",
        "_struct_conn.ptnr2_label_asym_id": "W",
        "_struct_conn.ptnr2_label_comp_id": "HOH",
        "_struct_conn.ptnr2_label_seq_id": "?",
        "_struct_conn.ptnr2_label_atom_id": "O",
        "_struct_conn.pdbx_ptnr2_label_alt_id": "?",
        "_struct_conn.pdbx_ptnr2_pdb_ins_code": "?",
        "_struct_conn.ptnr1_auth_asym_id": "L",
        "_struct_conn.ptnr1_auth_comp_id": "LIG",
        "_struct_conn.ptnr1_auth_seq_id": "501",
        "_struct_conn.ptnr2_auth_asym_id": "W",
        "_struct_conn.ptnr2_auth_comp_id": "HOH",
        "_struct_conn.ptnr2_auth_seq_id": "601",
        "_struct_conn.ptnr2_symmetry": "1_555",
        "_struct_conn.pdbx_value_order": connection_order,
    }
    include_polymer = modified_residue or bool(observation_gap)
    entity_rows = (
        {"_entity.id": "1", "_entity.type": "non-polymer"},
        {"_entity.id": "2", "_entity.type": "water"},
    ) + (
        ({"_entity.id": "3", "_entity.type": "polymer"},)
        if include_polymer
        else ()
    )
    asym_rows = (
        {"_struct_asym.id": "L", "_struct_asym.entity_id": "1"},
        {"_struct_asym.id": "W", "_struct_asym.entity_id": "2"},
    ) + (
        ({"_struct_asym.id": "P", "_struct_asym.entity_id": "3"},)
        if include_polymer
        else ()
    )
    chem_comp_rows = (
        {
            "_chem_comp.id": "LIG",
            "_chem_comp.type": "non-polymer",
            "_chem_comp.pdbx_formal_charge": "0",
        },
        {
            "_chem_comp.id": "HOH",
            "_chem_comp.type": "non-polymer",
            "_chem_comp.pdbx_formal_charge": "0",
        },
    ) + (
        (
            {
                "_chem_comp.id": "MSE",
                "_chem_comp.type": "'L-peptide linking'",
                "_chem_comp.pdbx_formal_charge": "0",
            },
            {
                "_chem_comp.id": "MET",
                "_chem_comp.type": "'L-peptide linking'",
                "_chem_comp.pdbx_formal_charge": "0",
            },
        )
        if modified_residue
        else (
            (
                {
                    "_chem_comp.id": "GLY",
                    "_chem_comp.type": "'L-peptide linking'",
                    "_chem_comp.pdbx_formal_charge": "0",
                },
            )
            if observation_gap
            else ()
        )
    )
    source = (
        "data_v2_preparation_corpus\n#\n"
        + _loop(_ENTITY_HEADERS, entity_rows)
        + _loop(_ASYM_HEADERS, asym_rows)
        + _loop(_CHEM_COMP_HEADERS, chem_comp_rows)
        + _loop(
            _ENTITY_NONPOLY_HEADERS,
            (
                {
                    "_pdbx_entity_nonpoly.entity_id": "1",
                    "_pdbx_entity_nonpoly.name": "ligand",
                    "_pdbx_entity_nonpoly.comp_id": "LIG",
                },
                {
                    "_pdbx_entity_nonpoly.entity_id": "2",
                    "_pdbx_entity_nonpoly.name": "water",
                    "_pdbx_entity_nonpoly.comp_id": "HOH",
                },
            ),
        )
        + _loop(
            _SCHEME_HEADERS,
            (
                {
                    "_pdbx_nonpoly_scheme.asym_id": "L",
                    "_pdbx_nonpoly_scheme.entity_id": "1",
                    "_pdbx_nonpoly_scheme.mon_id": "LIG",
                    "_pdbx_nonpoly_scheme.ndb_seq_num": "1",
                    "_pdbx_nonpoly_scheme.pdb_seq_num": "501",
                    "_pdbx_nonpoly_scheme.auth_seq_num": "501",
                    "_pdbx_nonpoly_scheme.pdb_mon_id": "LIG",
                    "_pdbx_nonpoly_scheme.auth_mon_id": "LIG",
                    "_pdbx_nonpoly_scheme.pdb_strand_id": "L",
                    "_pdbx_nonpoly_scheme.pdb_ins_code": ligand_insertion_code,
                },
                {
                    "_pdbx_nonpoly_scheme.asym_id": "W",
                    "_pdbx_nonpoly_scheme.entity_id": "2",
                    "_pdbx_nonpoly_scheme.mon_id": "HOH",
                    "_pdbx_nonpoly_scheme.ndb_seq_num": "1",
                    "_pdbx_nonpoly_scheme.pdb_seq_num": "601",
                    "_pdbx_nonpoly_scheme.auth_seq_num": "601",
                    "_pdbx_nonpoly_scheme.pdb_mon_id": "HOH",
                    "_pdbx_nonpoly_scheme.auth_mon_id": "HOH",
                    "_pdbx_nonpoly_scheme.pdb_strand_id": "W",
                    "_pdbx_nonpoly_scheme.pdb_ins_code": "?",
                },
            ),
        )
    )
    if include_polymer:
        source += _loop(
            _ENTITY_POLY_HEADERS,
            (
                {
                    "_entity_poly.entity_id": "3",
                    "_entity_poly.type": "'polypeptide(L)'",
                },
            ),
        )
        source += _loop(
            _ENTITY_POLY_SEQ_HEADERS,
            (
                {
                    "_entity_poly_seq.entity_id": "3",
                    "_entity_poly_seq.num": "1",
                    "_entity_poly_seq.mon_id": "MSE" if modified_residue else "GLY",
                    "_entity_poly_seq.hetero": "n",
                },
            ),
        )
    if modified_residue:
        source += _loop(
            MMCIF_MODIFIED_RESIDUE_DECLARATION_HEADERS,
            (
                {
                    "_pdbx_struct_mod_residue.id": "1",
                    "_pdbx_struct_mod_residue.label_asym_id": "P",
                    "_pdbx_struct_mod_residue.label_seq_id": "1",
                    "_pdbx_struct_mod_residue.label_comp_id": "MSE",
                    "_pdbx_struct_mod_residue.parent_comp_id": "MET",
                    "_pdbx_struct_mod_residue.pdb_model_num": "1",
                    "_pdbx_struct_mod_residue.pdb_ins_code": ".",
                },
            ),
        )
    if observation_gap == "zero_occupancy_residue":
        source += _loop(
            MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS,
            (
                {
                    "_pdbx_unobs_or_zero_occ_residues.id": "1",
                    "_pdbx_unobs_or_zero_occ_residues.polymer_flag": "Y",
                    "_pdbx_unobs_or_zero_occ_residues.occupancy_flag": "0",
                    "_pdbx_unobs_or_zero_occ_residues.pdb_model_num": "1",
                    "_pdbx_unobs_or_zero_occ_residues.auth_asym_id": "P",
                    "_pdbx_unobs_or_zero_occ_residues.auth_comp_id": "GLY",
                    "_pdbx_unobs_or_zero_occ_residues.auth_seq_id": "1",
                    "_pdbx_unobs_or_zero_occ_residues.pdb_ins_code": ".",
                    "_pdbx_unobs_or_zero_occ_residues.label_asym_id": "P",
                    "_pdbx_unobs_or_zero_occ_residues.label_comp_id": "GLY",
                    "_pdbx_unobs_or_zero_occ_residues.label_seq_id": "1",
                },
            ),
        )
    elif observation_gap == "unobserved_atom":
        source += _loop(
            MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS,
            (
                {
                    "_pdbx_unobs_or_zero_occ_atoms.id": "1",
                    "_pdbx_unobs_or_zero_occ_atoms.polymer_flag": "Y",
                    "_pdbx_unobs_or_zero_occ_atoms.occupancy_flag": "1",
                    "_pdbx_unobs_or_zero_occ_atoms.pdb_model_num": "1",
                    "_pdbx_unobs_or_zero_occ_atoms.auth_asym_id": "P",
                    "_pdbx_unobs_or_zero_occ_atoms.auth_comp_id": "GLY",
                    "_pdbx_unobs_or_zero_occ_atoms.auth_seq_id": "1",
                    "_pdbx_unobs_or_zero_occ_atoms.pdb_ins_code": ".",
                    "_pdbx_unobs_or_zero_occ_atoms.auth_atom_id": "CA",
                    "_pdbx_unobs_or_zero_occ_atoms.label_alt_id": ".",
                    "_pdbx_unobs_or_zero_occ_atoms.label_asym_id": "P",
                    "_pdbx_unobs_or_zero_occ_atoms.label_comp_id": "GLY",
                    "_pdbx_unobs_or_zero_occ_atoms.label_seq_id": "1",
                    "_pdbx_unobs_or_zero_occ_atoms.label_atom_id": "CA",
                },
            ),
        )
    elif observation_gap:
        raise MmcifNonpolyPreparationCorpusError(
            "corpus observation-gap fixture is unsupported"
        )
    if biological_assembly:
        source += _loop(
            MMCIF_BIOLOGICAL_ASSEMBLY_DEFINITION_HEADERS,
            ({"_pdbx_struct_assembly.id": "1"},),
        )
        source += _loop(
            MMCIF_BIOLOGICAL_ASSEMBLY_GENERATOR_HEADERS,
            (
                {
                    "_pdbx_struct_assembly_gen.assembly_id": "1",
                    "_pdbx_struct_assembly_gen.oper_expression": "1",
                    "_pdbx_struct_assembly_gen.asym_id_list": "L",
                },
            ),
        )
        source += _loop(
            MMCIF_BIOLOGICAL_ASSEMBLY_OPERATOR_HEADERS,
            (
                {
                    "_pdbx_struct_oper_list.id": "1",
                    "_pdbx_struct_oper_list.matrix[1][1]": "1",
                    "_pdbx_struct_oper_list.matrix[1][2]": "0",
                    "_pdbx_struct_oper_list.matrix[1][3]": "0",
                    "_pdbx_struct_oper_list.matrix[2][1]": "0",
                    "_pdbx_struct_oper_list.matrix[2][2]": "1",
                    "_pdbx_struct_oper_list.matrix[2][3]": "0",
                    "_pdbx_struct_oper_list.matrix[3][1]": "0",
                    "_pdbx_struct_oper_list.matrix[3][2]": "0",
                    "_pdbx_struct_oper_list.matrix[3][3]": "1",
                    "_pdbx_struct_oper_list.vector[1]": "0",
                    "_pdbx_struct_oper_list.vector[2]": "0",
                    "_pdbx_struct_oper_list.vector[3]": "0",
                },
            ),
        )
    source += _loop(MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS, atom_rows)
    if bond_rows:
        source += _loop(MMCIF_NONPOLY_COMPONENT_BOND_HEADERS, bond_rows)
    source += (
        _loop(MMCIF_STRUCT_CONN_HEADERS, (connection,))
        + _loop(MMCIF_NONPOLY_ATOM_SITE_HEADERS, site_rows)
        + "_audit_conform.dict_name CORPUS_ONLY\n"
    )
    source.encode("ascii")
    return source


FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_INPUT_SHA256: Mapping[str, str] = (
    MappingProxyType(
        {
            "supported_carbonyl": "368b6aede70a893c9f2e60c50b18d1c2d1399bc8039c42b1c2613cd1601050fb",
            "supported_single_coh": "0b33ffb7d232a58664293085c5086f7991e596d10cc161bd7b4b9be6dd4c7238",
            "supported_source_hydrogen": "a6a2dab9058b48956c8514291ce672d2f8b05b049d6138d36bb93c85dc62f5a8",
            "supported_nonpoly_insertion_code": "ae9b5768e9f02fbff5cbf8e719dfadb3f3493645c7a461502f6002bd719372da",
            "unprepared_intercomponent_covalent": "2764644c17bd5c32a5277efdc17ddaa1092c06b294f6c5ebdf05f14462199906",
            "unsupported_charged_component": "e0129d499970f12c91d39fa404985ab23228f456615e8a50d6e7e40468f6f97c",
            "unsupported_extended_element": "0f6c47a87a2c8871e4bb3fc3b765f3ecbf5d28b09011a7883fed6e83bcd33499",
            "unsupported_aromatic_atom": "de7032783768797897048a8da450561227373565ba0adae053312f6c594df836",
            "unsupported_atom_stereo": "c70e5f5d02f7945d87a1549588ba5c5ec95ddb3c234dcaa5884bf6a2ba73ba2f",
            "unsupported_bond_stereo": "6941d3495fca99b96533655dfe2f3761d7c1fd4fcf99c379cb60d07962a1a508",
            "unsupported_triple_bond": "534ac463a3727a40c167ebc7169805a5fb4ff2ec7efc4da3f1e1b2364c1e5687",
            "unsupported_quadruple_bond": "19f03c9920763e0bc45a2ad51ab340a7fb54ef758e5b34faeaf156d1e34a9b98",
            "unsupported_aromatic_bond": "f6a282fa552ea0ad095de942ad3bb7892e4f46d46cc401cdadeed1b9f90288e2",
            "unsupported_cyclic_graph": "13ff3145c90c8366da052ee2c368364b441034fd8d8df460ede319009b33ec07",
            "unsupported_disconnected_graph": "83619ddd5d600cbeefaba78f4e28338589c9102a4d63b7c1b1b641941063ac82",
            "unsupported_element_crosscheck_mismatch": "ed43b77f64df81e268245bbd37b2d6f826ae5640e08ec438090e0114b1f340f6",
            "unsupported_charge_crosscheck_mismatch": "e4d4480020b34d4281a1ebcccc7d7e73e7d334e9dd7e05cced948562b0897052",
            "unsupported_formal_charge_unavailable": "cc1aa1d60caa878feef838756064f514be50bff5ed8dca08c1fd64c4f02ac94c",
            "unsupported_overfull_valence": "af6d1eec54281f3e0cb05dd5c8c69567dc6ffc882cac41a38bd11f718192b466",
            "unsupported_incomplete_source_hydrogen": "9741a52326e820ce70b075ada0854c859d1aa42bda70efeec7562b6550f6f158",
            "unsupported_monoatomic_metal": "5d33f6f81bfe91e59b419993d37c51fee8bc9934a3cb0160d33824d67c2122e7",
            "unsupported_monoatomic_nonmetal_ion": "cb03af1d7e2626d4b74d55c84929e87ced1953f6fedc0a67f17d9cf7bb78dd4c",
            "unsupported_source_declared_modified_residue": "ff1f1c1053df34f121fa85cfec2f91d247a3d0e898cf0e14a1ca68bce1c20570",
            "unsupported_multimodel_input": "9aaa7806cf65ca5d2d8d0b667aa9afb5833d5da88851e8372e8c01b710296d0b",
            "unsupported_altloc_input": "3c76390e49d672ab9d3a4aff02590382096550e7c762451ea201e10456796673",
            "unsupported_zero_occupancy_residue_input": "4fda53fbe92eb89adb8a27e67749a84672a5c930c8e6a5aa747bf3d951ee0df0",
            "unsupported_unobserved_atom_input": "1b35f9b45192f46565b88be9d3e9d7a8abd81081c2f63233e9c95e718bd2eb42",
            "unsupported_biological_assembly_input": "70b49622c1b2c3597e94ad4342553292fab01a6009e6cd72615a77c48246eaf3",
            "invalid_component_charge_grammar": "43f64cf79729dbbf92a858cb315421067393e5796466e0614a65f6db937c5ed5",
            "invalid_component_charge_range": "a7a25d9fa84a602b3221faf553918e54bfbad06d443355fca8b3eb67df81438d",
        }
    )
)


def _parameterability_blockers(
    chemistry: tuple[str, ...], integration: str
) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*chemistry, integration, *_UNIVERSAL_BLOCKERS)))


def _prepared_report(
    component_id: str,
    *,
    formula: tuple[tuple[str, int], ...],
    added_hydrogens: int,
    atom_count: int,
    bond_count: int,
    integration: str,
) -> MmcifPreparationCorpusExpectedReport:
    return MmcifPreparationCorpusExpectedReport(
        component_id=component_id,
        preparation_status="prepared_component_graph",
        chemistry_blockers=(),
        parameterability_status="graph_ready_external_connection_blocked",
        parameterability_blockers=_parameterability_blockers((), integration),
        formula=formula,
        total_formal_charge=0,
        added_hydrogen_count=added_hydrogens,
        prepared_atom_count=atom_count,
        prepared_bond_count=bond_count,
    )


def _unsupported_report(
    blockers: tuple[str, ...], *, integration: str
) -> MmcifPreparationCorpusExpectedReport:
    return MmcifPreparationCorpusExpectedReport(
        component_id="LIG",
        preparation_status="unsupported_chemistry",
        chemistry_blockers=blockers,
        parameterability_status="unsupported_chemistry",
        parameterability_blockers=_parameterability_blockers(blockers, integration),
        formula=(),
        total_formal_charge=None,
        added_hydrogen_count=0,
        prepared_atom_count=0,
        prepared_bond_count=0,
    )


def _water_report(integration: str) -> MmcifPreparationCorpusExpectedReport:
    return _prepared_report(
        "HOH",
        formula=(("H", 2), ("O", 1)),
        added_hydrogens=2,
        atom_count=3,
        bond_count=2,
        integration=integration,
    )


def _case(
    case_id: str,
    cohort: str,
    atoms: tuple[MmcifPreparationCorpusAtom, ...],
    bonds: tuple[MmcifPreparationCorpusBond, ...],
    source_features: tuple[str, ...],
    *,
    ligand_report: MmcifPreparationCorpusExpectedReport | None = None,
    expected_error_code: str = "",
    connection_type: str = "metalc",
    connection_order: str = "?",
    modified_residue: bool = False,
    water_model_number: str = "1",
    ligand_alt_id: str = ".",
    ligand_insertion_code: str = ".",
    observation_gap: str = "",
    biological_assembly: bool = False,
) -> MmcifPreparationCorpusCase:
    source = _corpus_source(
        atoms,
        bonds,
        connection_type=connection_type,
        connection_order=connection_order,
        modified_residue=modified_residue,
        water_model_number=water_model_number,
        ligand_alt_id=ligand_alt_id,
        ligand_insertion_code=ligand_insertion_code,
        observation_gap=observation_gap,
        biological_assembly=biological_assembly,
    )
    digest = hashlib.sha256(source.encode("ascii")).hexdigest()
    frozen = FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_INPUT_SHA256.get(case_id, "")
    if frozen and frozen != digest:
        raise MmcifNonpolyPreparationCorpusError(
            f"frozen corpus input digest drifted for {case_id}"
        )
    integration = (
        "intercomponent_covalent_connection_not_prepared"
        if connection_type == "covale"
        else "intercomponent_coordination_not_prepared"
    )
    reports = () if expected_error_code else (ligand_report, _water_report(integration))
    if any(row is None for row in reports):
        raise MmcifNonpolyPreparationCorpusError(
            "non-error corpus cases require a ligand expectation"
        )
    return MmcifPreparationCorpusCase(
        case_id=case_id,
        cohort=cohort,
        source_text=source,
        input_sha256=digest,
        source_features=tuple(source_features),
        expected_reports=tuple(row for row in reports if row is not None),
        expected_error_code=expected_error_code,
    )


def mmcif_nonpoly_preparation_corpus_cases() -> tuple[MmcifPreparationCorpusCase, ...]:
    """Return the exact, ordered, executable preparation corpus."""

    coordination = "intercomponent_coordination_not_prepared"
    covalent = "intercomponent_covalent_connection_not_prepared"
    carbonyl_atoms = (
        MmcifPreparationCorpusAtom("C1", "C"),
        MmcifPreparationCorpusAtom("O1", "O"),
    )
    carbonyl_bond = (MmcifPreparationCorpusBond("C1", "O1", "DOUB"),)
    cases = (
        _case(
            "supported_carbonyl",
            "supported_graph",
            carbonyl_atoms,
            carbonyl_bond,
            (
                "entity_type:non-polymer",
                "entity_type:water",
                "element:C",
                "element:O",
                "formal_charge:zero",
                "aromaticity:nonaromatic",
                "atom_stereo:none",
                "bond_stereo:none",
                "bond_order:double",
                "topology:connected",
                "topology:acyclic",
                "hydrogen_completion:fixed_neutral_valence",
            ),
            ligand_report=_prepared_report(
                "LIG",
                formula=(("C", 1), ("H", 2), ("O", 1)),
                added_hydrogens=2,
                atom_count=4,
                bond_count=3,
                integration=coordination,
            ),
        ),
        _case(
            "supported_single_coh",
            "supported_graph",
            carbonyl_atoms,
            (MmcifPreparationCorpusBond("C1", "O1", "SING"),),
            ("bond_order:single", "hydrogen_completion:fixed_neutral_valence"),
            ligand_report=_prepared_report(
                "LIG",
                formula=(("C", 1), ("H", 4), ("O", 1)),
                added_hydrogens=4,
                atom_count=6,
                bond_count=5,
                integration=coordination,
            ),
        ),
        _case(
            "supported_source_hydrogen",
            "supported_graph",
            (
                MmcifPreparationCorpusAtom("C1", "C"),
                MmcifPreparationCorpusAtom("O1", "O"),
                MmcifPreparationCorpusAtom("H1", "H"),
            ),
            (
                MmcifPreparationCorpusBond("C1", "O1", "SING"),
                MmcifPreparationCorpusBond("C1", "H1", "SING"),
            ),
            ("element:H", "source_hydrogen:complete"),
            ligand_report=_prepared_report(
                "LIG",
                formula=(("C", 1), ("H", 4), ("O", 1)),
                added_hydrogens=3,
                atom_count=6,
                bond_count=5,
                integration=coordination,
            ),
        ),
        _case(
            "supported_nonpoly_insertion_code",
            "supported_graph",
            carbonyl_atoms,
            carbonyl_bond,
            ("insertion_code:known_exact_nonpoly_identity",),
            ligand_report=_prepared_report(
                "LIG",
                formula=(("C", 1), ("H", 2), ("O", 1)),
                added_hydrogens=2,
                atom_count=4,
                bond_count=3,
                integration=coordination,
            ),
            ligand_insertion_code="A",
        ),
        _case(
            "unprepared_intercomponent_covalent",
            "unprepared_integration",
            carbonyl_atoms,
            carbonyl_bond,
            ("connection:intercomponent_covalent",),
            ligand_report=_prepared_report(
                "LIG",
                formula=(("C", 1), ("H", 2), ("O", 1)),
                added_hydrogens=2,
                atom_count=4,
                bond_count=3,
                integration=covalent,
            ),
            connection_type="covale",
            connection_order="SING",
        ),
        _case(
            "unsupported_charged_component",
            "unsupported_chemistry",
            (
                MmcifPreparationCorpusAtom("C1", "C", "+1"),
                MmcifPreparationCorpusAtom("O1", "O"),
            ),
            carbonyl_bond,
            ("formal_charge:nonzero",),
            ligand_report=_unsupported_report(
                ("charged_chemistry_not_supported",), integration=coordination
            ),
        ),
        _case(
            "unsupported_extended_element",
            "unsupported_chemistry",
            (
                MmcifPreparationCorpusAtom("N1", "N"),
                MmcifPreparationCorpusAtom("O1", "O"),
            ),
            (MmcifPreparationCorpusBond("N1", "O1", "DOUB"),),
            ("element:outside_coh",),
            ligand_report=_unsupported_report(
                ("element_outside_neutral_coh_scope",), integration=coordination
            ),
        ),
        _case(
            "unsupported_aromatic_atom",
            "unsupported_chemistry",
            (
                MmcifPreparationCorpusAtom("C1", "C", aromatic_flag="Y"),
                MmcifPreparationCorpusAtom("O1", "O"),
            ),
            carbonyl_bond,
            ("aromaticity:atom_aromatic",),
            ligand_report=_unsupported_report(
                ("aromatic_chemistry_not_supported",), integration=coordination
            ),
        ),
        _case(
            "unsupported_atom_stereo",
            "unsupported_chemistry",
            (
                MmcifPreparationCorpusAtom("C1", "C", stereo_config="R"),
                MmcifPreparationCorpusAtom("O1", "O"),
            ),
            carbonyl_bond,
            ("atom_stereo:R",),
            ligand_report=_unsupported_report(
                ("atom_stereochemistry_not_prepared",), integration=coordination
            ),
        ),
        _case(
            "unsupported_bond_stereo",
            "unsupported_chemistry",
            carbonyl_atoms,
            (MmcifPreparationCorpusBond("C1", "O1", "DOUB", stereo_config="E"),),
            ("bond_stereo:E",),
            ligand_report=_unsupported_report(
                ("bond_stereochemistry_not_prepared",), integration=coordination
            ),
        ),
        _case(
            "unsupported_triple_bond",
            "unsupported_chemistry",
            carbonyl_atoms,
            (MmcifPreparationCorpusBond("C1", "O1", "TRIP"),),
            ("bond_order:triple",),
            ligand_report=_unsupported_report(
                ("bond_order_outside_neutral_coh_scope",), integration=coordination
            ),
        ),
        _case(
            "unsupported_quadruple_bond",
            "unsupported_chemistry",
            carbonyl_atoms,
            (MmcifPreparationCorpusBond("C1", "O1", "QUAD"),),
            ("bond_order:quadruple",),
            ligand_report=_unsupported_report(
                ("bond_order_outside_neutral_coh_scope",), integration=coordination
            ),
        ),
        _case(
            "unsupported_aromatic_bond",
            "unsupported_chemistry",
            carbonyl_atoms,
            (MmcifPreparationCorpusBond("C1", "O1", "AROM", aromatic_flag="Y"),),
            ("bond_order:aromatic",),
            ligand_report=_unsupported_report(
                ("bond_order_outside_neutral_coh_scope",), integration=coordination
            ),
        ),
        _case(
            "unsupported_cyclic_graph",
            "unsupported_chemistry",
            (
                MmcifPreparationCorpusAtom("C1", "C"),
                MmcifPreparationCorpusAtom("C2", "C"),
                MmcifPreparationCorpusAtom("O1", "O"),
            ),
            (
                MmcifPreparationCorpusBond("C1", "C2", "SING"),
                MmcifPreparationCorpusBond("C2", "O1", "SING"),
                MmcifPreparationCorpusBond("O1", "C1", "SING"),
            ),
            ("topology:cyclic",),
            ligand_report=_unsupported_report(
                ("cyclic_chemistry_not_supported",), integration=coordination
            ),
        ),
        _case(
            "unsupported_disconnected_graph",
            "unsupported_chemistry",
            (
                MmcifPreparationCorpusAtom("C1", "C"),
                MmcifPreparationCorpusAtom("O1", "O"),
                MmcifPreparationCorpusAtom("C2", "C"),
            ),
            carbonyl_bond,
            ("topology:disconnected",),
            ligand_report=_unsupported_report(
                ("component_graph_disconnected",), integration=coordination
            ),
        ),
        _case(
            "unsupported_element_crosscheck_mismatch",
            "unsupported_chemistry",
            (
                MmcifPreparationCorpusAtom("C1", "C", site_element="O"),
                MmcifPreparationCorpusAtom("O1", "O"),
            ),
            carbonyl_bond,
            ("source_crosscheck:element_mismatch",),
            ligand_report=_unsupported_report(
                ("atom_site_component_element_mismatch",), integration=coordination
            ),
        ),
        _case(
            "unsupported_charge_crosscheck_mismatch",
            "unsupported_chemistry",
            (
                MmcifPreparationCorpusAtom("C1", "C", site_formal_charge="+1"),
                MmcifPreparationCorpusAtom("O1", "O"),
            ),
            carbonyl_bond,
            ("source_crosscheck:formal_charge_mismatch",),
            ligand_report=_unsupported_report(
                ("atom_site_component_formal_charge_mismatch",),
                integration=coordination,
            ),
        ),
        _case(
            "unsupported_formal_charge_unavailable",
            "unsupported_chemistry",
            (
                MmcifPreparationCorpusAtom("C1", "C", "?"),
                MmcifPreparationCorpusAtom("O1", "O"),
            ),
            carbonyl_bond,
            ("formal_charge:unavailable",),
            ligand_report=_unsupported_report(
                ("component_formal_charge_unavailable",), integration=coordination
            ),
        ),
        _case(
            "unsupported_overfull_valence",
            "unsupported_chemistry",
            (
                MmcifPreparationCorpusAtom("C1", "C"),
                MmcifPreparationCorpusAtom("O1", "O"),
                MmcifPreparationCorpusAtom("O2", "O"),
                MmcifPreparationCorpusAtom("H1", "H"),
            ),
            (
                MmcifPreparationCorpusBond("C1", "O1", "DOUB"),
                MmcifPreparationCorpusBond("C1", "O2", "DOUB"),
                MmcifPreparationCorpusBond("C1", "H1", "SING"),
            ),
            ("valence:overfull",),
            ligand_report=_unsupported_report(
                ("neutral_valence_not_satisfied",), integration=coordination
            ),
        ),
        _case(
            "unsupported_incomplete_source_hydrogen",
            "unsupported_chemistry",
            (MmcifPreparationCorpusAtom("H1", "H"),),
            (),
            ("source_hydrogen:incomplete",),
            ligand_report=_unsupported_report(
                ("source_hydrogen_valence_incomplete",), integration=coordination
            ),
        ),
        _case(
            "unsupported_monoatomic_metal",
            "unsupported_chemistry",
            (MmcifPreparationCorpusAtom("ZN1", "Zn", "+2"),),
            (),
            ("composition_role:monoatomic_metal_component",),
            ligand_report=_unsupported_report(
                (
                    "element_outside_neutral_coh_scope",
                    "charged_chemistry_not_supported",
                ),
                integration=coordination,
            ),
        ),
        _case(
            "unsupported_monoatomic_nonmetal_ion",
            "unsupported_chemistry",
            (MmcifPreparationCorpusAtom("CL1", "Cl", "-1"),),
            (),
            ("composition_role:monoatomic_nonmetal_ion",),
            ligand_report=_unsupported_report(
                (
                    "element_outside_neutral_coh_scope",
                    "charged_chemistry_not_supported",
                ),
                integration=coordination,
            ),
        ),
        _case(
            "unsupported_source_declared_modified_residue",
            "unsupported_chemistry",
            carbonyl_atoms,
            carbonyl_bond,
            ("source_declared_modified_residue",),
            ligand_report=_prepared_report(
                "LIG",
                formula=(("C", 1), ("H", 2), ("O", 1)),
                added_hydrogens=2,
                atom_count=4,
                bond_count=3,
                integration=coordination,
            ),
            modified_residue=True,
        ),
        _case(
            "unsupported_multimodel_input",
            "unsupported_upstream_policy",
            carbonyl_atoms,
            carbonyl_bond,
            ("atom_site_model_set:multimodel",),
            expected_error_code="selected_model_not_supported",
            water_model_number="2",
        ),
        _case(
            "unsupported_altloc_input",
            "unsupported_upstream_policy",
            carbonyl_atoms,
            carbonyl_bond,
            ("atom_site_label_alt_id:explicit",),
            expected_error_code="nonblank_atom_site_marker_not_supported",
            ligand_alt_id="A",
        ),
        _case(
            "unsupported_zero_occupancy_residue_input",
            "unsupported_upstream_policy",
            carbonyl_atoms,
            carbonyl_bond,
            ("source_declared_observation_gap:zero_occupancy_residue",),
            expected_error_code="source_declared_observation_gap_not_supported",
            observation_gap="zero_occupancy_residue",
        ),
        _case(
            "unsupported_unobserved_atom_input",
            "unsupported_upstream_policy",
            carbonyl_atoms,
            carbonyl_bond,
            ("source_declared_observation_gap:unobserved_atom",),
            expected_error_code="source_declared_observation_gap_not_supported",
            observation_gap="unobserved_atom",
        ),
        _case(
            "unsupported_biological_assembly_input",
            "unsupported_upstream_policy",
            carbonyl_atoms,
            carbonyl_bond,
            ("source_declared_biological_assembly",),
            expected_error_code="source_declared_biological_assembly_not_supported",
            biological_assembly=True,
        ),
        _case(
            "invalid_component_charge_grammar",
            "invalid_source",
            (
                MmcifPreparationCorpusAtom("C1", "C", "1.0", site_formal_charge="0"),
                MmcifPreparationCorpusAtom("O1", "O"),
            ),
            carbonyl_bond,
            ("formal_charge:invalid_grammar",),
            expected_error_code="invalid_component_formal_charge",
        ),
        _case(
            "invalid_component_charge_range",
            "invalid_source",
            (
                MmcifPreparationCorpusAtom("C1", "C", "9", site_formal_charge="0"),
                MmcifPreparationCorpusAtom("O1", "O"),
            ),
            carbonyl_bond,
            ("formal_charge:out_of_range",),
            expected_error_code="component_formal_charge_out_of_bounds",
        ),
    )
    case_ids = [row.case_id for row in cases]
    if len(set(case_ids)) != len(case_ids):
        raise MmcifNonpolyPreparationCorpusError("corpus case IDs must be unique")
    frozen_ids = set(FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_INPUT_SHA256)
    if frozen_ids and frozen_ids != set(case_ids):
        raise MmcifNonpolyPreparationCorpusError(
            "frozen corpus input digest coverage is incomplete"
        )
    return cases


MMCIF_NONPOLY_PREPARATION_REQUIRED_COVERAGE_IDS = (
    "source_entity.nonpolymer",
    "source_entity.water",
    "element.carbon",
    "element.oxygen",
    "element.hydrogen",
    "formal_charge.zero",
    "aromaticity.nonaromatic",
    "atom_stereo.none",
    "bond_stereo.none",
    "bond_order.single",
    "bond_order.double",
    "topology.connected",
    "topology.acyclic",
    "hydrogen_completion.fixed_neutral_valence",
    "source_hydrogen.complete",
    "parameterability.failure_complete_report",
    "element.outside_coh",
    "formal_charge.nonzero",
    "aromaticity.atom_aromatic",
    "atom_stereo.r_or_s",
    "bond_stereo.e_or_z",
    "bond_order.triple",
    "bond_order.quadruple",
    "bond_order.aromatic",
    "topology.cyclic",
    "topology.disconnected",
    "source_crosscheck.element_mismatch",
    "source_crosscheck.formal_charge_mismatch",
    "formal_charge.unavailable",
    "valence.overfull",
    "source_hydrogen.incomplete",
    "formal_charge.invalid_grammar",
    "formal_charge.out_of_range",
    "connection.intercomponent_coordination",
    "connection.intercomponent_covalent",
    "protonation.ph_dependent",
    "tautomer.selection",
    "role.ion",
    "role.metal",
    "role.cofactor",
    "role.modified_residue",
    "hydrogen.coordinates",
    "parameter_source.reviewed",
    "partial_charge.assignment",
    "all_atom_system.creation",
    "upstream.altloc_selection",
    "upstream.biological_assembly",
    "upstream.insertion_semantics",
    "upstream.missing_atom_residue_policy",
    "upstream.multimodel_policy",
    "round_trip.all_atom_identity",
)


def _coverage(
    coverage_id: str,
    scope_area: str,
    policy_status: str,
    expected_signal: str,
    evidence_case_ids: tuple[str, ...],
    blocker: str = "",
) -> MmcifPreparationCoverageRow:
    return MmcifPreparationCoverageRow(
        coverage_id=coverage_id,
        scope_area=scope_area,
        policy_status=policy_status,
        expected_signal=expected_signal,
        evidence_case_ids=evidence_case_ids,
        blocker=blocker,
    )


def mmcif_nonpoly_preparation_coverage_rows() -> tuple[
    MmcifPreparationCoverageRow, ...
]:
    """Return the frozen current-scope classification for every V2-1 axis."""

    supported = "supported"
    unsupported = "explicitly_unsupported"
    missing = "not_implemented"
    rows = (
        _coverage(
            "source_entity.nonpolymer",
            "source_identity",
            supported,
            "source_feature:entity_type:non-polymer",
            ("supported_carbonyl",),
        ),
        _coverage(
            "source_entity.water",
            "source_identity",
            supported,
            "report:HOH:prepared_component_graph",
            ("supported_carbonyl",),
        ),
        _coverage(
            "element.carbon",
            "chemistry",
            supported,
            "source_feature:element:C",
            ("supported_carbonyl",),
        ),
        _coverage(
            "element.oxygen",
            "chemistry",
            supported,
            "source_feature:element:O",
            ("supported_carbonyl",),
        ),
        _coverage(
            "element.hydrogen",
            "chemistry",
            supported,
            "source_feature:element:H",
            ("supported_source_hydrogen",),
        ),
        _coverage(
            "formal_charge.zero",
            "chemistry",
            supported,
            "source_feature:formal_charge:zero",
            ("supported_carbonyl",),
        ),
        _coverage(
            "aromaticity.nonaromatic",
            "chemistry",
            supported,
            "source_feature:aromaticity:nonaromatic",
            ("supported_carbonyl",),
        ),
        _coverage(
            "atom_stereo.none",
            "chemistry",
            supported,
            "source_feature:atom_stereo:none",
            ("supported_carbonyl",),
        ),
        _coverage(
            "bond_stereo.none",
            "chemistry",
            supported,
            "source_feature:bond_stereo:none",
            ("supported_carbonyl",),
        ),
        _coverage(
            "bond_order.single",
            "topology",
            supported,
            "source_feature:bond_order:single",
            ("supported_single_coh",),
        ),
        _coverage(
            "bond_order.double",
            "topology",
            supported,
            "source_feature:bond_order:double",
            ("supported_carbonyl",),
        ),
        _coverage(
            "topology.connected",
            "topology",
            supported,
            "source_feature:topology:connected",
            ("supported_carbonyl",),
        ),
        _coverage(
            "topology.acyclic",
            "topology",
            supported,
            "source_feature:topology:acyclic",
            ("supported_carbonyl",),
        ),
        _coverage(
            "hydrogen_completion.fixed_neutral_valence",
            "preparation",
            supported,
            "source_feature:hydrogen_completion:fixed_neutral_valence",
            ("supported_carbonyl", "supported_single_coh"),
        ),
        _coverage(
            "source_hydrogen.complete",
            "preparation",
            supported,
            "source_feature:source_hydrogen:complete",
            ("supported_source_hydrogen",),
        ),
        _coverage(
            "parameterability.failure_complete_report",
            "parameterability",
            supported,
            "parameterable:LIG:false",
            ("supported_carbonyl", "unsupported_charged_component"),
        ),
        _coverage(
            "element.outside_coh",
            "chemistry",
            unsupported,
            "chemistry_blocker:LIG:element_outside_neutral_coh_scope",
            ("unsupported_extended_element",),
            "element_outside_neutral_coh_scope",
        ),
        _coverage(
            "formal_charge.nonzero",
            "chemistry",
            unsupported,
            "chemistry_blocker:LIG:charged_chemistry_not_supported",
            ("unsupported_charged_component",),
            "charged_chemistry_not_supported",
        ),
        _coverage(
            "aromaticity.atom_aromatic",
            "chemistry",
            unsupported,
            "chemistry_blocker:LIG:aromatic_chemistry_not_supported",
            ("unsupported_aromatic_atom",),
            "aromatic_chemistry_not_supported",
        ),
        _coverage(
            "atom_stereo.r_or_s",
            "chemistry",
            unsupported,
            "chemistry_blocker:LIG:atom_stereochemistry_not_prepared",
            ("unsupported_atom_stereo",),
            "atom_stereochemistry_not_prepared",
        ),
        _coverage(
            "bond_stereo.e_or_z",
            "chemistry",
            unsupported,
            "chemistry_blocker:LIG:bond_stereochemistry_not_prepared",
            ("unsupported_bond_stereo",),
            "bond_stereochemistry_not_prepared",
        ),
        _coverage(
            "bond_order.triple",
            "topology",
            unsupported,
            "chemistry_blocker:LIG:bond_order_outside_neutral_coh_scope",
            ("unsupported_triple_bond",),
            "bond_order_outside_neutral_coh_scope",
        ),
        _coverage(
            "bond_order.quadruple",
            "topology",
            unsupported,
            "chemistry_blocker:LIG:bond_order_outside_neutral_coh_scope",
            ("unsupported_quadruple_bond",),
            "bond_order_outside_neutral_coh_scope",
        ),
        _coverage(
            "bond_order.aromatic",
            "topology",
            unsupported,
            "chemistry_blocker:LIG:bond_order_outside_neutral_coh_scope",
            ("unsupported_aromatic_bond",),
            "bond_order_outside_neutral_coh_scope",
        ),
        _coverage(
            "topology.cyclic",
            "topology",
            unsupported,
            "chemistry_blocker:LIG:cyclic_chemistry_not_supported",
            ("unsupported_cyclic_graph",),
            "cyclic_chemistry_not_supported",
        ),
        _coverage(
            "topology.disconnected",
            "topology",
            unsupported,
            "chemistry_blocker:LIG:component_graph_disconnected",
            ("unsupported_disconnected_graph",),
            "component_graph_disconnected",
        ),
        _coverage(
            "source_crosscheck.element_mismatch",
            "source_crosscheck",
            unsupported,
            "chemistry_blocker:LIG:atom_site_component_element_mismatch",
            ("unsupported_element_crosscheck_mismatch",),
            "atom_site_component_element_mismatch",
        ),
        _coverage(
            "source_crosscheck.formal_charge_mismatch",
            "source_crosscheck",
            unsupported,
            "chemistry_blocker:LIG:atom_site_component_formal_charge_mismatch",
            ("unsupported_charge_crosscheck_mismatch",),
            "atom_site_component_formal_charge_mismatch",
        ),
        _coverage(
            "formal_charge.unavailable",
            "source_crosscheck",
            unsupported,
            "chemistry_blocker:LIG:component_formal_charge_unavailable",
            ("unsupported_formal_charge_unavailable",),
            "component_formal_charge_unavailable",
        ),
        _coverage(
            "valence.overfull",
            "preparation",
            unsupported,
            "chemistry_blocker:LIG:neutral_valence_not_satisfied",
            ("unsupported_overfull_valence",),
            "neutral_valence_not_satisfied",
        ),
        _coverage(
            "source_hydrogen.incomplete",
            "preparation",
            unsupported,
            "chemistry_blocker:LIG:source_hydrogen_valence_incomplete",
            ("unsupported_incomplete_source_hydrogen",),
            "source_hydrogen_valence_incomplete",
        ),
        _coverage(
            "formal_charge.invalid_grammar",
            "source_crosscheck",
            unsupported,
            "error:invalid_component_formal_charge",
            ("invalid_component_charge_grammar",),
            "invalid_component_formal_charge",
        ),
        _coverage(
            "formal_charge.out_of_range",
            "source_crosscheck",
            unsupported,
            "error:component_formal_charge_out_of_bounds",
            ("invalid_component_charge_range",),
            "component_formal_charge_out_of_bounds",
        ),
        _coverage(
            "connection.intercomponent_coordination",
            "integration",
            unsupported,
            "parameterability_blocker:LIG:intercomponent_coordination_not_prepared",
            ("supported_carbonyl",),
            "intercomponent_coordination_not_prepared",
        ),
        _coverage(
            "connection.intercomponent_covalent",
            "integration",
            unsupported,
            "parameterability_blocker:LIG:intercomponent_covalent_connection_not_prepared",
            ("unprepared_intercomponent_covalent",),
            "intercomponent_covalent_connection_not_prepared",
        ),
        _coverage(
            "protonation.ph_dependent",
            "chemistry",
            missing,
            "",
            (),
            "ph_dependent_protonation_not_implemented",
        ),
        _coverage(
            "tautomer.selection",
            "chemistry",
            missing,
            "",
            (),
            "tautomer_selection_not_implemented",
        ),
        _coverage(
            "role.ion",
            "role_assignment",
            unsupported,
            "composition_role:LIG:monoatomic_nonmetal_ion",
            ("unsupported_monoatomic_nonmetal_ion",),
            "monoatomic_nonmetal_ion_preparation_not_supported",
        ),
        _coverage(
            "role.metal",
            "role_assignment",
            unsupported,
            "composition_role:LIG:monoatomic_metal_component",
            ("unsupported_monoatomic_metal",),
            "monoatomic_metal_preparation_not_supported",
        ),
        _coverage(
            "role.cofactor",
            "role_assignment",
            unsupported,
            "role_blocker:LIG:ligand_cofactor_and_other_nonpoly_roles_not_interpreted",
            ("supported_carbonyl",),
            "cofactor_role_not_interpreted",
        ),
        _coverage(
            "role.modified_residue",
            "role_assignment",
            unsupported,
            (
                "modified_residue_role:"
                "source_declared_modified_polymer_component"
            ),
            ("unsupported_source_declared_modified_residue",),
            "modified_residue_preparation_not_supported",
        ),
        _coverage(
            "hydrogen.coordinates",
            "preparation",
            supported,
            "hydrogen_coordinate_status:coordinate_bearing_prepared_graph",
            ("supported_carbonyl", "supported_source_hydrogen"),
        ),
        _coverage(
            "parameter_source.reviewed",
            "parameterability",
            supported,
            (
                "parameter_source_provenance_status:"
                "reviewed_identity_license_and_scope_only"
            ),
            ("supported_carbonyl",),
        ),
        _coverage(
            "partial_charge.assignment",
            "parameterability",
            missing,
            "",
            (),
            "partial_charge_assignment_not_implemented",
        ),
        _coverage(
            "all_atom_system.creation",
            "preparation",
            supported,
            "all_atom_system_status:canonical_all_atom_system_created",
            ("supported_single_coh", "supported_source_hydrogen"),
        ),
        _coverage(
            "upstream.altloc_selection",
            "upstream_ingest",
            unsupported,
            "error:nonblank_atom_site_marker_not_supported",
            ("unsupported_altloc_input",),
            "altloc_selection_not_implemented",
        ),
        _coverage(
            "upstream.biological_assembly",
            "upstream_ingest",
            unsupported,
            (
                "biological_assembly_policy_status:"
                "explicitly_unsupported_source_declared_biological_assembly"
            ),
            ("unsupported_biological_assembly_input",),
            "source_declared_biological_assembly_preparation_not_supported",
        ),
        _coverage(
            "upstream.insertion_semantics",
            "upstream_ingest",
            supported,
            "source_feature:insertion_code:known_exact_nonpoly_identity",
            ("supported_nonpoly_insertion_code",),
        ),
        _coverage(
            "upstream.missing_atom_residue_policy",
            "upstream_ingest",
            unsupported,
            (
                "missing_atom_residue_policy_status:"
                "explicitly_unsupported_source_declared_observation_gaps"
            ),
            (
                "unsupported_zero_occupancy_residue_input",
                "unsupported_unobserved_atom_input",
            ),
            "source_declared_observation_gap_preparation_not_supported",
        ),
        _coverage(
            "upstream.multimodel_policy",
            "upstream_ingest",
            unsupported,
            "model_policy_status:explicitly_unsupported_multimodel",
            ("unsupported_multimodel_input",),
            "multimodel_execution_not_supported",
        ),
        _coverage(
            "round_trip.all_atom_identity",
            "canonical_ingest",
            missing,
            "",
            (),
            "prepared_all_atom_round_trip_not_implemented",
        ),
    )
    if (
        tuple(row.coverage_id for row in rows)
        != MMCIF_NONPOLY_PREPARATION_REQUIRED_COVERAGE_IDS
    ):
        raise MmcifNonpolyPreparationCorpusError(
            "preparation coverage rows do not match the required ordered axes"
        )
    return rows


def _report_projection(report: Any) -> dict[str, Any]:
    payload = report.to_dict()
    return {
        "component_id": payload["component_id"],
        "preparation_status": payload["preparation_status"],
        "chemistry_blockers": list(payload["chemistry_blockers"]),
        "parameterability_status": payload["parameterability_status"],
        "parameterability_blockers": list(payload["parameterability_blockers"]),
        "parameterable": payload["parameterable"],
        "formula": dict(payload["formula"]),
        "total_formal_charge": payload["total_formal_charge"],
        "added_hydrogen_count": payload["added_hydrogen_count"],
        "prepared_atom_count": payload["prepared_atom_count"],
        "prepared_bond_count": payload["prepared_bond_count"],
        "preparation_graph_sha256": payload["preparation_graph_sha256"],
    }


def _expected_report_projection(
    report: MmcifPreparationCorpusExpectedReport,
) -> dict[str, Any]:
    payload = report.to_dict()
    return {
        **payload,
        "parameterable": False,
    }


def _signals_for_reports(
    case: MmcifPreparationCorpusCase,
    reports: tuple[Mapping[str, Any], ...],
    atom_site_model_policy: Mapping[str, Any],
    biological_assembly_policy: Mapping[str, Any],
    missing_atom_residue_policy: Mapping[str, Any],
    hydrogen_coordinate_summary: Mapping[str, Any],
    all_atom_system_summary: Mapping[str, Any],
    component_roles: tuple[Mapping[str, Any], ...],
    modified_residue_declarations: tuple[Mapping[str, Any], ...],
    claim_payload: Mapping[str, Any],
) -> tuple[str, ...]:
    parameter_source_provenance = reviewed_parameter_source_provenance()
    signals = [f"source_feature:{value}" for value in case.source_features]
    signals.extend(
        (
            "parameter_source_provenance_status:"
            f"{parameter_source_provenance.review_status}",
            "parameter_source_provenance_snapshot_sha256:"
            f"{parameter_source_provenance.snapshot_sha256}",
            "parameter_source_assignment_implemented:false",
            "parameter_source_applicability_validated:false",
        )
    )
    signals.extend(
        (
            f"model_policy_status:{atom_site_model_policy['execution_policy_status']}",
            "model_policy_execution_allowed:"
            f"{str(atom_site_model_policy['execution_allowed']).lower()}",
        )
    )
    signals.extend(
        f"model_policy_blocker:{value}"
        for value in atom_site_model_policy["execution_blockers"]
    )
    signals.extend(
        (
            "biological_assembly_policy_status:"
            f"{biological_assembly_policy['execution_policy_status']}",
            "biological_assembly_policy_execution_allowed:"
            f"{str(biological_assembly_policy['execution_allowed']).lower()}",
        )
    )
    signals.extend(
        f"biological_assembly_policy_blocker:{value}"
        for value in biological_assembly_policy["execution_blockers"]
    )
    signals.extend(
        (
            "missing_atom_residue_policy_status:"
            f"{missing_atom_residue_policy['execution_policy_status']}",
            "missing_atom_residue_policy_execution_allowed:"
            f"{str(missing_atom_residue_policy['execution_allowed']).lower()}",
        )
    )
    signals.extend(
        f"missing_atom_residue_policy_blocker:{value}"
        for value in missing_atom_residue_policy["execution_blockers"]
    )
    signals.extend(
        (
            "hydrogen_coordinate_generated_instance_count:"
            f"{hydrogen_coordinate_summary['generated_instance_count']}",
            "hydrogen_coordinate_added_count:"
            f"{hydrogen_coordinate_summary['added_hydrogen_coordinate_count']}",
            "hydrogen_coordinate_all_prepared_graphs_coordinate_bearing:"
            f"{str(hydrogen_coordinate_summary['all_prepared_graphs_coordinate_bearing']).lower()}",
        )
    )
    signals.extend(
        f"hydrogen_coordinate_status:{row['coordinate_status']}"
        for row in hydrogen_coordinate_summary["instance_reports"]
    )
    signals.extend(
        (
            "all_atom_system_created_count:"
            f"{all_atom_system_summary['created_system_count']}",
            "all_atom_system_unavailable_count:"
            f"{all_atom_system_summary['unavailable_system_count']}",
        )
    )
    signals.extend(
        f"all_atom_system_status:{row['materialization_status']}"
        for row in all_atom_system_summary["instance_reports"]
    )
    for report in reports:
        component = str(report["component_id"])
        signals.extend(
            (
                f"report:{component}:{report['preparation_status']}",
                f"parameterability:{component}:{report['parameterability_status']}",
                f"parameterable:{component}:{str(report['parameterable']).lower()}",
                f"added_hydrogens:{component}:{report['added_hydrogen_count']}",
            )
        )
        signals.extend(
            f"chemistry_blocker:{component}:{value}"
            for value in report["chemistry_blockers"]
        )
        signals.extend(
            f"parameterability_blocker:{component}:{value}"
            for value in report["parameterability_blockers"]
        )
    for role in component_roles:
        component = str(role["component_id"])
        signals.extend(
            (
                f"composition_role:{component}:{role['composition_role']}",
                f"role_status:{component}:{role['role_status']}",
                f"preparation_disposition:{component}:{role['preparation_disposition']}",
            )
        )
        signals.extend(
            f"role_blocker:{component}:{value}" for value in role["role_blockers"]
        )
    for declaration in modified_residue_declarations:
        signals.extend(
            (
                f"modified_residue_role:{declaration['modified_residue_role']}",
                f"modified_residue_role_status:{declaration['role_status']}",
                "preparation_disposition:modified_residue:"
                f"{declaration['preparation_disposition']}",
            )
        )
        signals.extend(
            f"modified_residue_blocker:{value}"
            for value in declaration["role_blockers"]
        )
    for key, value in sorted(claim_payload.items()):
        if type(value) is bool:
            signals.append(f"claim:{str(value).lower()}:{key}")
    return tuple(dict.fromkeys(signals))


def _run_case(case: MmcifPreparationCorpusCase) -> MmcifPreparationCorpusCaseResult:
    if not _SHA256_RE.fullmatch(case.input_sha256):
        raise MmcifNonpolyPreparationCorpusError("corpus input digest is invalid")
    model_policy_snapshot = parse_mmcif_atom_site_model_policy(case.source_text)
    model_policy = model_policy_snapshot.to_dict()
    assembly_policy_snapshot = parse_mmcif_biological_assembly_policy(
        case.source_text
    )
    assembly_policy = assembly_policy_snapshot.to_dict()
    missing_policy_snapshot = parse_mmcif_missing_atom_residue_policy(
        case.source_text
    )
    missing_policy = missing_policy_snapshot.to_dict()
    try:
        snapshot = parse_mmcif_nonpoly_preparation(case.source_text)
    except (MmcifNonpolyPreparationError, MmcifNonpolyAtomSiteObservationError) as exc:
        if not case.expected_error_code or exc.code != case.expected_error_code:
            raise MmcifNonpolyPreparationCorpusError(
                f"corpus case {case.case_id} produced an unexpected preparation error"
            ) from exc
        return MmcifPreparationCorpusCaseResult(
            case_id=case.case_id,
            cohort=case.cohort,
            input_sha256=case.input_sha256,
            observed_outcome="expected_error",
            preparation_snapshot_sha256="",
            atom_site_model_policy_snapshot_sha256=(
                model_policy_snapshot.snapshot_sha256
            ),
            biological_assembly_policy_snapshot_sha256=(
                assembly_policy_snapshot.snapshot_sha256
            ),
            missing_atom_residue_policy_snapshot_sha256=(
                missing_policy_snapshot.snapshot_sha256
            ),
            hydrogen_coordinate_snapshot_sha256="",
            all_atom_system_snapshot_sha256="",
            component_role_snapshot_sha256="",
            modified_residue_declaration_snapshot_sha256="",
            error_code=exc.code,
            reports=(),
            atom_site_model_policy=model_policy,
            biological_assembly_policy=assembly_policy,
            missing_atom_residue_policy=missing_policy,
            hydrogen_coordinate_summary={},
            all_atom_system_summary={},
            component_roles=(),
            modified_residue_declarations=(),
            signals=tuple(
                dict.fromkeys(
                    (
                        *(f"source_feature:{value}" for value in case.source_features),
                        f"model_policy_status:{model_policy['execution_policy_status']}",
                        "model_policy_execution_allowed:"
                        f"{str(model_policy['execution_allowed']).lower()}",
                        *(
                            f"model_policy_blocker:{value}"
                            for value in model_policy["execution_blockers"]
                        ),
                        "biological_assembly_policy_status:"
                        f"{assembly_policy['execution_policy_status']}",
                        "biological_assembly_policy_execution_allowed:"
                        f"{str(assembly_policy['execution_allowed']).lower()}",
                        *(
                            f"biological_assembly_policy_blocker:{value}"
                            for value in assembly_policy["execution_blockers"]
                        ),
                        "missing_atom_residue_policy_status:"
                        f"{missing_policy['execution_policy_status']}",
                        "missing_atom_residue_policy_execution_allowed:"
                        f"{str(missing_policy['execution_allowed']).lower()}",
                        *(
                            f"missing_atom_residue_policy_blocker:{value}"
                            for value in missing_policy["execution_blockers"]
                        ),
                        f"error:{exc.code}",
                    )
                )
            ),
        )
    if case.expected_error_code:
        raise MmcifNonpolyPreparationCorpusError(
            f"corpus case {case.case_id} accepted an invalid source"
        )
    hydrogen_coordinate_snapshot = parse_mmcif_nonpoly_hydrogen_coordinates(
        case.source_text
    )
    hydrogen_coordinate_summary = {
        **hydrogen_coordinate_snapshot.to_dict(),
        "instance_reports": [
            row.to_dict() for row in hydrogen_coordinate_snapshot.instance_reports
        ],
    }
    all_atom_system_snapshot = parse_mmcif_nonpoly_all_atom_systems(case.source_text)
    all_atom_system_summary = {
        **all_atom_system_snapshot.to_dict(),
        "instance_reports": [
            {
                key: value
                for key, value in row.to_dict().items()
                if key != "canonical_system_document"
            }
            for row in all_atom_system_snapshot.instance_reports
        ],
    }
    role_snapshot = parse_mmcif_nonpoly_component_roles(case.source_text)
    modified_residue_snapshot = (
        parse_mmcif_modified_residue_declarations(case.source_text)
        if "source_declared_modified_residue" in case.source_features
        else None
    )
    reports = tuple(_report_projection(row) for row in snapshot.instance_reports)
    component_roles = tuple(row.to_dict() for row in role_snapshot.roles)
    modified_residue_declarations = (
        tuple(row.to_dict() for row in modified_residue_snapshot.declarations)
        if modified_residue_snapshot is not None
        else ()
    )
    if [row["component_id"] for row in reports] != [
        row.component_id for row in case.expected_reports
    ] or [row["component_id"] for row in component_roles] != [
        row["component_id"] for row in reports
    ]:
        raise MmcifNonpolyPreparationCorpusError(
            f"corpus case {case.case_id} report coverage drifted"
        )
    for actual, expected in zip(reports, case.expected_reports, strict=True):
        comparison = dict(actual)
        comparison.pop("preparation_graph_sha256")
        if comparison != _expected_report_projection(expected):
            raise MmcifNonpolyPreparationCorpusError(
                f"corpus case {case.case_id} report expectation drifted"
            )
    return MmcifPreparationCorpusCaseResult(
        case_id=case.case_id,
        cohort=case.cohort,
        input_sha256=case.input_sha256,
        observed_outcome="failure_complete_reports",
        preparation_snapshot_sha256=snapshot.snapshot_sha256,
        atom_site_model_policy_snapshot_sha256=(
            model_policy_snapshot.snapshot_sha256
        ),
        biological_assembly_policy_snapshot_sha256=(
            assembly_policy_snapshot.snapshot_sha256
        ),
        missing_atom_residue_policy_snapshot_sha256=(
            missing_policy_snapshot.snapshot_sha256
        ),
        hydrogen_coordinate_snapshot_sha256=(
            hydrogen_coordinate_snapshot.snapshot_sha256
        ),
        all_atom_system_snapshot_sha256=all_atom_system_snapshot.snapshot_sha256,
        component_role_snapshot_sha256=role_snapshot.snapshot_sha256,
        modified_residue_declaration_snapshot_sha256=(
            modified_residue_snapshot.snapshot_sha256
            if modified_residue_snapshot is not None
            else ""
        ),
        error_code="",
        reports=reports,
        atom_site_model_policy=model_policy,
        biological_assembly_policy=assembly_policy,
        missing_atom_residue_policy=missing_policy,
        hydrogen_coordinate_summary=hydrogen_coordinate_summary,
        all_atom_system_summary=all_atom_system_summary,
        component_roles=component_roles,
        modified_residue_declarations=modified_residue_declarations,
        signals=_signals_for_reports(
            case,
            reports,
            model_policy,
            assembly_policy,
            missing_policy,
            hydrogen_coordinate_summary,
            all_atom_system_summary,
            component_roles,
            modified_residue_declarations,
            snapshot.to_dict(),
        ),
    )


def run_mmcif_nonpoly_preparation_corpus() -> MmcifNonpolyPreparationCorpusSnapshot:
    """Execute every frozen case and require complete coverage evidence."""

    cases = mmcif_nonpoly_preparation_corpus_cases()
    if not FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_INPUT_SHA256:
        raise MmcifNonpolyPreparationCorpusError(
            "frozen corpus input digests have not been recorded"
        )
    results = tuple(_run_case(case) for case in cases)
    result_map = {row.case_id: row for row in results}
    coverage = mmcif_nonpoly_preparation_coverage_rows()
    referenced_cases: set[str] = set()
    for row in coverage:
        if row.policy_status not in {
            "supported",
            "explicitly_unsupported",
            "not_implemented",
        }:
            raise MmcifNonpolyPreparationCorpusError(
                "coverage row policy status is invalid"
            )
        if row.policy_status == "not_implemented":
            if row.evidence_case_ids or row.expected_signal or not row.blocker:
                raise MmcifNonpolyPreparationCorpusError(
                    "not-implemented coverage rows require only an explicit blocker"
                )
            continue
        if not row.evidence_case_ids or not row.expected_signal:
            raise MmcifNonpolyPreparationCorpusError(
                "executable coverage rows require evidence and a signal"
            )
        if row.policy_status == "explicitly_unsupported" and not row.blocker:
            raise MmcifNonpolyPreparationCorpusError(
                "unsupported coverage rows require an explicit blocker"
            )
        for case_id in row.evidence_case_ids:
            result = result_map.get(case_id)
            if result is None or row.expected_signal not in result.signals:
                raise MmcifNonpolyPreparationCorpusError(
                    f"coverage evidence signal missing for {row.coverage_id}"
                )
            referenced_cases.add(case_id)
    if referenced_cases != set(result_map):
        raise MmcifNonpolyPreparationCorpusError(
            "every executable corpus case must support at least one coverage row"
        )
    cohorts = {row.cohort for row in results}
    if cohorts != {
        "supported_graph",
        "unprepared_integration",
        "unsupported_chemistry",
        "unsupported_upstream_policy",
        "invalid_source",
    }:
        raise MmcifNonpolyPreparationCorpusError(
            "corpus must retain every supported and failure cohort"
        )
    snapshot = MmcifNonpolyPreparationCorpusSnapshot(
        case_results=results,
        coverage_rows=coverage,
    )
    if (
        snapshot.snapshot_sha256
        != FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_SNAPSHOT_SHA256
    ):
        raise MmcifNonpolyPreparationCorpusError(
            "executable corpus snapshot drifted from the frozen review boundary"
        )
    return snapshot


def mmcif_nonpoly_preparation_corpus_projection(
    snapshot: MmcifNonpolyPreparationCorpusSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_PREPARATION_CORPUS_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_PREPARATION_CORPUS_PROFILE_ID,
        "runner_version": MMCIF_NONPOLY_PREPARATION_CORPUS_RUNNER_VERSION,
        "case_results": [row.to_dict() for row in snapshot.case_results],
        "coverage_rows": [row.to_dict() for row in snapshot.coverage_rows],
        "case_order": "frozen_manifest_order",
        "coverage_order": "required_axis_order",
        **_claim_policy(),
    }


def mmcif_nonpoly_preparation_corpus_source_binding() -> dict[str, Any]:
    cases = mmcif_nonpoly_preparation_corpus_cases()
    parameter_source_provenance = reviewed_parameter_source_provenance()
    return {
        "schema_id": MMCIF_NONPOLY_PREPARATION_CORPUS_SOURCE_BINDING_SCHEMA_ID,
        "preparation_profile_id": MMCIF_NONPOLY_PREPARATION_PROFILE_ID,
        "preparation_parser_version": MMCIF_NONPOLY_PREPARATION_PARSER_VERSION,
        "atom_site_model_policy_profile_id": MMCIF_ATOM_SITE_MODEL_POLICY_PROFILE_ID,
        "atom_site_model_policy_parser_version": (
            MMCIF_ATOM_SITE_MODEL_POLICY_PARSER_VERSION
        ),
        "biological_assembly_policy_profile_id": (
            MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PROFILE_ID
        ),
        "biological_assembly_policy_parser_version": (
            MMCIF_BIOLOGICAL_ASSEMBLY_POLICY_PARSER_VERSION
        ),
        "missing_atom_residue_policy_profile_id": (
            MMCIF_MISSING_ATOM_RESIDUE_POLICY_PROFILE_ID
        ),
        "missing_atom_residue_policy_parser_version": (
            MMCIF_MISSING_ATOM_RESIDUE_POLICY_PARSER_VERSION
        ),
        "hydrogen_coordinate_profile_id": (
            MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROFILE_ID
        ),
        "hydrogen_coordinate_generator_version": (
            MMCIF_NONPOLY_HYDROGEN_COORDINATE_GENERATOR_VERSION
        ),
        "all_atom_system_profile_id": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID,
        "all_atom_system_materializer_version": (
            MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION
        ),
        "parameter_source_provenance_profile_id": (
            PARAMETER_SOURCE_PROVENANCE_PROFILE_ID
        ),
        "parameter_source_provenance_review_version": (
            PARAMETER_SOURCE_PROVENANCE_REVIEW_VERSION
        ),
        "parameter_source_provenance_snapshot_sha256": (
            parameter_source_provenance.snapshot_sha256
        ),
        "component_role_profile_id": MMCIF_NONPOLY_COMPONENT_ROLE_PROFILE_ID,
        "component_role_parser_version": MMCIF_NONPOLY_COMPONENT_ROLE_PARSER_VERSION,
        "modified_residue_declaration_profile_id": (
            MMCIF_MODIFIED_RESIDUE_DECLARATION_PROFILE_ID
        ),
        "modified_residue_declaration_parser_version": (
            MMCIF_MODIFIED_RESIDUE_DECLARATION_PARSER_VERSION
        ),
        "corpus_profile_id": MMCIF_NONPOLY_PREPARATION_CORPUS_PROFILE_ID,
        "corpus_runner_version": MMCIF_NONPOLY_PREPARATION_CORPUS_RUNNER_VERSION,
        "cases": [row.binding_dict() for row in cases],
        "frozen_input_sha256": dict(
            FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_INPUT_SHA256
        ),
        "required_coverage_ids": list(MMCIF_NONPOLY_PREPARATION_REQUIRED_COVERAGE_IDS),
        "raw_input_embedded_in_document": False,
        "corpus_use": "contract_regression_only",
    }


def mmcif_nonpoly_preparation_corpus_document(
    snapshot: MmcifNonpolyPreparationCorpusSnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_preparation_corpus_projection(snapshot)
    binding = mmcif_nonpoly_preparation_corpus_source_binding()
    return {
        "schema_id": MMCIF_NONPOLY_PREPARATION_CORPUS_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_PREPARATION_CORPUS_PROFILE_ID,
        "runner_version": MMCIF_NONPOLY_PREPARATION_CORPUS_RUNNER_VERSION,
        "corpus_projection": projection,
        "source_binding": binding,
        "corpus_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def require_mmcif_nonpoly_preparation_corpus_document(
    payload: object,
) -> Mapping[str, object]:
    """Re-execute the bundled corpus and require exact canonical agreement."""

    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly preparation corpus document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_NONPOLY_PREPARATION_CORPUS_DOCUMENT_SCHEMA_ID:
        raise ValueError("nonpoly preparation corpus document schema mismatch")
    if document.get("profile_id") != MMCIF_NONPOLY_PREPARATION_CORPUS_PROFILE_ID:
        raise ValueError("nonpoly preparation corpus profile mismatch")
    expected = mmcif_nonpoly_preparation_corpus_document(
        run_mmcif_nonpoly_preparation_corpus()
    )
    if document != expected:
        raise ValueError(
            "nonpoly preparation corpus document drifted from executable evidence"
        )
    return payload


def mmcif_nonpoly_preparation_corpus_json_bytes(
    snapshot: MmcifNonpolyPreparationCorpusSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_preparation_corpus_document(snapshot))


def write_mmcif_nonpoly_preparation_corpus_json(
    path: str | Path,
    snapshot: MmcifNonpolyPreparationCorpusSnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_preparation_corpus_json_bytes(snapshot) + b"\n"
    file_fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(file_fd, 0o600)
        with os.fdopen(file_fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        file_fd = -1
        os.replace(temporary_path, destination)
        directory_fd = os.open(
            destination.parent,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        if file_fd >= 0:
            try:
                os.close(file_fd)
            except OSError:
                pass
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise
    return destination


__all__ = [
    "FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_INPUT_SHA256",
    "FROZEN_MMCIF_NONPOLY_PREPARATION_CORPUS_SNAPSHOT_SHA256",
    "MMCIF_NONPOLY_PREPARATION_CORPUS_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_PREPARATION_CORPUS_PROFILE_ID",
    "MMCIF_NONPOLY_PREPARATION_CORPUS_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_PREPARATION_CORPUS_RUNNER_VERSION",
    "MMCIF_NONPOLY_PREPARATION_CORPUS_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_NONPOLY_PREPARATION_REQUIRED_COVERAGE_IDS",
    "MmcifNonpolyPreparationCorpusError",
    "MmcifNonpolyPreparationCorpusSnapshot",
    "MmcifPreparationCorpusAtom",
    "MmcifPreparationCorpusBond",
    "MmcifPreparationCorpusCase",
    "MmcifPreparationCorpusCaseResult",
    "MmcifPreparationCorpusExpectedReport",
    "MmcifPreparationCoverageRow",
    "mmcif_nonpoly_preparation_corpus_cases",
    "mmcif_nonpoly_preparation_corpus_document",
    "mmcif_nonpoly_preparation_corpus_json_bytes",
    "mmcif_nonpoly_preparation_corpus_projection",
    "mmcif_nonpoly_preparation_corpus_source_binding",
    "mmcif_nonpoly_preparation_coverage_rows",
    "require_mmcif_nonpoly_preparation_corpus_document",
    "run_mmcif_nonpoly_preparation_corpus",
    "write_mmcif_nonpoly_preparation_corpus_json",
]
