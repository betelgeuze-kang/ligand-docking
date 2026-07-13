"""Strict PDB and mmCIF coordinate ingestion for the Engine v2 identity layer.

These parsers preserve explicit atom/residue/chain/model identity and reject
features that the current canonical contract cannot interpret without loss.
Alternate locations remain rejected by default and are retained only after an
explicit conformer identifier is supplied.  mmCIF biological assemblies are
expanded only after an explicit assembly identifier is supplied.  The parsers
do not infer missing atoms, residue bonds, protonation, or stereochemistry.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
from dataclasses import dataclass, replace
import hashlib
import itertools
import math
import re
from typing import Any, Iterable

import torch

from .mmcif_syntax import (
    MAX_CIF_TOKEN_COUNT,
    CifBlock,
    CifLoop,
    CifSyntaxError,
    CifToken,
    parse_cif_block,
)
from .models import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    atomic_number_for_element,
    canonical_element_symbol,
)
from .missingness import (
    MAX_MISSING_ATOM_CLAIMS,
    MAX_MISSING_RESIDUE_CLAIMS,
    MAX_TOTAL_MISSINGNESS_CLAIMS,
    MISSINGNESS_PRESERVATION_POLICY_ID,
    MISSINGNESS_REPORT_SCHEMA_ID,
    SourceReportedMissingAtomClaim,
    SourceReportedMissingResidueClaim,
    SourceReportedMissingnessReport,
    build_source_reported_missingness_report,
)
from .observation import attach_parser_observation_digest
from .topology import CANONICAL_TOPOLOGY_SCHEMA_ID, canonical_topology_sha256
from .validation import MolecularValidationError, require_valid_all_atom_system


PDB_PARSER_VERSION = "1.8.0"
MMCIF_PARSER_VERSION = "1.9.0"
STRUCTURE_INGEST_SUPPORT_SCOPE = "syntax_and_canonical_projection_only"

_MAX_PDB_INPUT_BYTES = 64 * 1024 * 1024
_MAX_PDB_ATOM_ROWS = 80_000
_MAX_PDB_LINE_COUNT = 250_000
_MAX_PDB_MISSINGNESS_REMARK_LINES = 20_000
_MAX_PDB_MISSINGNESS_PROJECTED_CLAIMS = 25_000
_MAX_MMCIF_INPUT_BYTES = 64 * 1024 * 1024
_MAX_MMCIF_ATOM_ROWS = 80_000
_MAX_MMCIF_ASSEMBLY_DEFINITION_ROWS = 1_024
_MAX_MMCIF_ASSEMBLY_GENERATOR_ROWS = 1_024
_MAX_MMCIF_ASSEMBLY_OPERATOR_ROWS = 4_096
_MAX_MMCIF_OPER_EXPRESSION_CHARS = 4_096
_MAX_MMCIF_ASSEMBLY_OPERATION_SEQUENCES = 4_096
_MAX_MMCIF_ASSEMBLY_OPERATION_APPLICATIONS = 16_384
_MAX_MMCIF_ASSEMBLY_ASYM_ID_LIST_CHARS = 4_096
_MAX_MMCIF_ASSEMBLY_ASYM_IDS_PER_GENERATOR = 4_096
_MAX_MMCIF_ASSEMBLY_CHAIN_INSTANCES = 4_096
_MAX_MMCIF_ASSEMBLY_OUTPUT_ATOMS = 20_000
_MAX_MMCIF_ASSEMBLY_OUTPUT_MODEL_ATOM_ROWS = 40_000
_MAX_MMCIF_MISSINGNESS_TOKEN_CHARS = 4_096
_MAX_MMCIF_MISSINGNESS_PRESERVED_ITEMS = 40_000
_MAX_MMCIF_MISSINGNESS_PRESERVED_UTF8_BYTES = 12 * 1024 * 1024
_MAX_CANONICAL_JSON_INTEGER = (1 << 53) - 1
_MAX_ABS_CANONICAL_FORMAL_CHARGE = (1 << 15) - 1

_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_CIF_NUMBER_RE = re.compile(
    r"^(?P<mantissa>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
    r"(?P<uncertainty>\(\d+\))?"
    r"(?P<exponent>[eE][+-]?\d+)?$"
)
_ASSEMBLY_OPERATION_ID_RE = re.compile(
    r'''^[\[\]_,.;:"&<>()/{}'`~!@#$%A-Za-z0-9*|+\-]+$'''
)
_ASSEMBLY_OPERATION_CODE_RE = re.compile(
    r'''^[\[\]_;.:"&<>/{}'`~!@#$%A-Za-z0-9*|+\-]+$'''
)
_ASSEMBLY_CANONICAL_RANGE_RE = re.compile(
    r"^(?P<start>0|[1-9]\d*)-(?P<end>0|[1-9]\d*)$"
)
_ASSEMBLY_NUMERIC_RANGE_LIKE_RE = re.compile(r"^\d+-\d+$")
_COVERAGE_BLOCKERS = (
    "bond_topology_incomplete_or_unverified",
    "biological_assembly_not_applied",
    "missing_atom_and_residue_completion_not_assessed",
    "hydrogen_and_protonation_not_assessed",
    "stereochemistry_not_assessed",
    "modified_residue_cofactor_and_parameterability_not_assessed",
)


class StructureParseError(ValueError):
    """Stable fail-closed coordinate-format parse error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        source_format: str,
        line_number: int | None = None,
    ):
        self.code = str(code)
        self.source_format = str(source_format)
        self.line_number = None if line_number is None else int(line_number)
        self.detail = str(message)
        location = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(f"{self.source_format}:{self.code}{location}: {self.detail}")


@dataclass(frozen=True)
class StructureIngestCoverage:
    source_format: str
    atom_count: int
    bond_count: int
    residue_count: int
    chain_count: int
    model_count: int
    explicit_hydrogen_count: int
    hetero_residue_count: int
    cell_present: bool
    unknown_formal_charge_count: int = 0
    unknown_entity_type_count: int = 0
    uninterpreted_category_count: int = 0
    canonical_topology_schema_id: str = CANONICAL_TOPOLOGY_SCHEMA_ID
    canonical_topology_sha256: str = ""
    source_atom_row_count: int = 0
    altloc_status: str = "not_present"
    requested_altloc_id: str = ""
    altloc_affected_residue_count: int = 0
    altloc_kept_row_count: int = 0
    altloc_discarded_row_count: int = 0
    coordinate_scope: str = "deposited_coordinates"
    assembly_status: str = "not_present"
    requested_assembly_id: str = ""
    assembly_operation_sequence_count: int = 0
    assembly_operation_application_count: int = 0
    assembly_chain_instance_count: int = 0
    assembly_output_atom_count: int = 0
    missingness_evidence_status: str = "not_present"
    source_reported_missing_residue_claim_count: int = 0
    source_reported_missing_atom_claim_count: int = 0
    source_missingness_evidence_schema_id: str = MISSINGNESS_REPORT_SCHEMA_ID
    source_missingness_evidence_sha256: str = ""
    missingness_completion_policy_id: str = MISSINGNESS_PRESERVATION_POLICY_ID
    missingness_completion_status: str = "not_assessed"
    blockers: tuple[str, ...] = _COVERAGE_BLOCKERS
    supported: bool = True
    preparation_ready: bool = False
    claim_safe: bool = False

    @property
    def support_scope(self) -> str:
        """Return the fixed scope of a successful structure-ingest result."""
        return STRUCTURE_INGEST_SUPPORT_SCOPE

    @property
    def syntax_ingest_supported(self) -> bool:
        return self.supported

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_format": self.source_format,
            "support_scope": self.support_scope,
            "supported": self.supported,
            "syntax_ingest_supported": self.syntax_ingest_supported,
            "preparation_ready": self.preparation_ready,
            "claim_safe": self.claim_safe,
            "atom_count": self.atom_count,
            "bond_count": self.bond_count,
            "residue_count": self.residue_count,
            "chain_count": self.chain_count,
            "model_count": self.model_count,
            "explicit_hydrogen_count": self.explicit_hydrogen_count,
            "hetero_residue_count": self.hetero_residue_count,
            "cell_present": self.cell_present,
            "unknown_formal_charge_count": self.unknown_formal_charge_count,
            "unknown_entity_type_count": self.unknown_entity_type_count,
            "uninterpreted_category_count": self.uninterpreted_category_count,
            "canonical_topology_schema_id": self.canonical_topology_schema_id,
            "canonical_topology_sha256": self.canonical_topology_sha256,
            "source_atom_row_count": self.source_atom_row_count,
            "altloc_status": self.altloc_status,
            "requested_altloc_id": self.requested_altloc_id,
            "altloc_affected_residue_count": self.altloc_affected_residue_count,
            "altloc_kept_row_count": self.altloc_kept_row_count,
            "altloc_discarded_row_count": self.altloc_discarded_row_count,
            "coordinate_scope": self.coordinate_scope,
            "assembly_status": self.assembly_status,
            "requested_assembly_id": self.requested_assembly_id,
            "assembly_operation_sequence_count": self.assembly_operation_sequence_count,
            "assembly_operation_application_count": self.assembly_operation_application_count,
            "assembly_chain_instance_count": self.assembly_chain_instance_count,
            "assembly_output_atom_count": self.assembly_output_atom_count,
            "missingness_evidence_status": self.missingness_evidence_status,
            "source_reported_missing_residue_claim_count": self.source_reported_missing_residue_claim_count,
            "source_reported_missing_atom_claim_count": self.source_reported_missing_atom_claim_count,
            "source_missingness_evidence_schema_id": self.source_missingness_evidence_schema_id,
            "source_missingness_evidence_sha256": self.source_missingness_evidence_sha256,
            "missingness_completion_policy_id": self.missingness_completion_policy_id,
            "missingness_completion_status": self.missingness_completion_status,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class StructureIngestResult:
    system: AllAtomSystem
    coverage: StructureIngestCoverage
    missingness_evidence: SourceReportedMissingnessReport


@dataclass(frozen=True)
class _SourceAtom:
    record: str
    serial: int
    name: str
    residue_name: str
    chain_id: str
    residue_number: int
    insertion_code: str
    altloc: str
    element: str
    formal_charge: int
    occupancy: float | None
    b_factor: float | None
    coordinates: tuple[float, float, float]
    metadata: dict[str, Any]
    entity_id: str = ""
    entity_type: str = ""
    residue_namespace: str = ""
    residue_metadata: dict[str, Any] | None = None
    model_identity: tuple[Any, ...] | None = None

    def identity(self) -> tuple[Any, ...]:
        if self.model_identity is not None:
            return self.model_identity
        return (
            self.record,
            self.serial,
            self.name,
            self.residue_name,
            self.chain_id,
            self.residue_number,
            self.insertion_code,
            self.altloc,
            self.element,
            self.formal_charge,
            self.occupancy,
            self.b_factor,
            self.metadata,
        )


@dataclass(frozen=True)
class _SourceBond:
    serial_i: int
    serial_j: int
    order: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class _AltlocSelectionSummary:
    status: str
    requested_altloc_id: str
    source_atom_row_count: int
    affected_residue_count: int
    kept_row_count: int
    discarded_row_count: int
    ledger: dict[str, Any]


@dataclass(frozen=True)
class _AssemblyExpansionSummary:
    status: str
    coordinate_scope: str
    requested_assembly_id: str
    source_topology_atom_count: int
    expanded_topology_atom_count: int
    operation_sequence_count: int
    operation_application_count: int
    copy_group_count: int
    chain_instance_count: int
    expanded_model_atom_rows: int
    numeric_uncertainty_present: bool
    ledger: dict[str, Any]


@dataclass(frozen=True)
class _MmcifAssemblyOperation:
    operation_id: str
    rotation: tuple[tuple[float, float, float], ...]
    translation: tuple[float, float, float]
    source_row_index: int
    uncertainty_present: bool


@dataclass(frozen=True)
class _MmcifAssemblyGenerator:
    source_row_index: int
    asym_ids: tuple[str, ...]
    raw_oper_expression: str
    operation_sequences: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class _MmcifAssemblyPlan:
    assembly_id: str
    generators: tuple[_MmcifAssemblyGenerator, ...]
    operations: dict[str, _MmcifAssemblyOperation]
    definition_row_count: int
    generator_row_count: int
    selected_generator_row_count: int
    operator_row_count: int
    selected_oper_expression_character_count: int
    selected_oper_expression_max_character_count: int
    selected_asym_id_list_character_count: int
    selected_asym_id_list_max_character_count: int
    selected_asym_id_count: int


def _unapplied_assembly_summary(
    *,
    status: str,
    coordinate_scope: str,
    source_topology_atom_count: int,
) -> _AssemblyExpansionSummary:
    return _AssemblyExpansionSummary(
        status=status,
        coordinate_scope=coordinate_scope,
        requested_assembly_id="",
        source_topology_atom_count=source_topology_atom_count,
        expanded_topology_atom_count=source_topology_atom_count,
        operation_sequence_count=0,
        operation_application_count=0,
        copy_group_count=0,
        chain_instance_count=0,
        expanded_model_atom_rows=0,
        numeric_uncertainty_present=False,
        ledger={
            "status": status,
            "selection_policy": "explicit_only",
            "assembly_id": "",
        },
    )


def _source_residue_key(atom: _SourceAtom) -> tuple[Any, ...]:
    return (
        atom.chain_id,
        atom.residue_number,
        atom.insertion_code,
        atom.residue_name,
        atom.record,
        atom.entity_id,
        atom.entity_type,
        atom.residue_namespace,
    )


def _source_atom_site_key(atom: _SourceAtom) -> tuple[Any, ...]:
    return (
        atom.chain_id,
        atom.residue_number,
        atom.insertion_code,
        atom.residue_name,
        atom.name,
    )


def _altloc_atom_semantics(atom: _SourceAtom) -> tuple[Any, ...]:
    mmcif = atom.metadata.get("mmcif")
    auth_identity: tuple[tuple[str, Any], ...] = ()
    if isinstance(mmcif, dict):
        raw_auth_identity = mmcif.get("auth_identity")
        if isinstance(raw_auth_identity, dict):
            auth_identity = tuple(
                (field, raw_auth_identity.get(field))
                for field in ("atom_id", "comp_id", "asym_id", "seq_id")
            )
    return (
        atom.record,
        atom.name,
        atom.element,
        atom.formal_charge,
        atom.metadata.get("formal_charge_known", True),
        atom.entity_id,
        atom.entity_type,
        auth_identity,
    )


def _source_atom_identifier(atom: _SourceAtom) -> int | str:
    mmcif = atom.metadata.get("mmcif")
    if isinstance(mmcif, dict):
        source_id = mmcif.get("source_atom_site_id")
        if isinstance(source_id, str) and source_id:
            return source_id
    return atom.serial


def _altloc_inventory(
    model: list[_SourceAtom],
    *,
    source_format: str,
) -> tuple[
    dict[tuple[Any, ...], dict[str, dict[tuple[Any, ...], tuple[Any, ...]]]],
    dict[tuple[Any, ...], set[tuple[Any, ...]]],
]:
    alternates: dict[
        tuple[Any, ...],
        dict[str, dict[tuple[Any, ...], tuple[Any, ...]]],
    ] = {}
    blank_sites: dict[tuple[Any, ...], set[tuple[Any, ...]]] = {}
    for atom in model:
        residue_key = _source_residue_key(atom)
        site_key = _source_atom_site_key(atom)
        if not atom.altloc:
            sites = blank_sites.setdefault(residue_key, set())
            if site_key in sites:
                raise _error(
                    source_format,
                    "duplicate_atom_identity",
                    f"duplicate blank alternate-location atom identity {site_key!r}",
                )
            sites.add(site_key)
            continue
        labels = alternates.setdefault(residue_key, {})
        sites = labels.setdefault(atom.altloc, {})
        if site_key in sites:
            raise _error(
                source_format,
                "duplicate_altloc_atom_identity",
                f"alternate location {atom.altloc!r} repeats atom identity {site_key!r}",
            )
        sites[site_key] = _altloc_atom_semantics(atom)
    return alternates, blank_sites


def _residue_key_payload(residue_key: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "chain_id": residue_key[0],
        "sequence_number": residue_key[1],
        "insertion_code": residue_key[2],
        "residue_name": residue_key[3],
        "record": residue_key[4],
        "entity_id": residue_key[5],
        "entity_type": residue_key[6],
        "residue_namespace": residue_key[7],
    }


def _select_explicit_altloc(
    models: list[list[_SourceAtom]],
    model_ids: list[int],
    *,
    source_format: str,
    altloc_id: str | None,
) -> tuple[list[list[_SourceAtom]], _AltlocSelectionSummary]:
    source_atom_row_count = sum(len(model) for model in models)
    inventories = [
        _altloc_inventory(model, source_format=source_format) for model in models
    ]
    has_alternates = any(inventory for inventory, _ in inventories)
    if not has_alternates:
        if altloc_id is not None:
            raise _error(
                source_format,
                "requested_altloc_not_present",
                f"requested alternate location {altloc_id!r} is absent",
            )
        return models, _AltlocSelectionSummary(
            status="not_present",
            requested_altloc_id="",
            source_atom_row_count=source_atom_row_count,
            affected_residue_count=0,
            kept_row_count=source_atom_row_count,
            discarded_row_count=0,
            ledger={
                "status": "not_present",
                "requested_altloc_id": "",
                "models": [],
            },
        )
    if altloc_id is None:
        raise _error(
            source_format,
            "unsupported_altloc",
            "alternate locations require an explicit altloc_id selection",
        )

    reference_alternates = inventories[0][0]
    for model_index, (alternates, blank_sites) in enumerate(inventories):
        for residue_key, labels in alternates.items():
            label_maps = list(labels.values())
            if any(candidate != label_maps[0] for candidate in label_maps[1:]):
                raise _error(
                    source_format,
                    "inconsistent_altloc_atom_identity",
                    f"residue {_residue_key_payload(residue_key)!r} has unequal alternate atom identities",
                )
            alternate_sites = set().union(*(set(candidate) for candidate in label_maps))
            collision = alternate_sites & blank_sites.get(residue_key, set())
            if collision:
                collision_preview = sorted(collision)[:3]
                collision_suffix = (
                    ""
                    if len(collision) <= 3
                    else f"; +{len(collision) - 3} more"
                )
                raise _error(
                    source_format,
                    "altloc_blank_collision",
                    "blank and alternate rows both define atom identities "
                    f"{collision_preview!r}{collision_suffix}",
                )
            if altloc_id not in labels:
                raise _error(
                    source_format,
                    "requested_altloc_missing_for_residue",
                    f"model {model_ids[model_index]} residue {_residue_key_payload(residue_key)!r} "
                    f"does not provide alternate location {altloc_id!r}",
                )
        if model_index and alternates != reference_alternates:
            raise _error(
                source_format,
                "model_altloc_inventory_mismatch",
                f"model {model_ids[model_index]} alternate-location inventory differs from the first model",
            )

    selected_models: list[list[_SourceAtom]] = []
    ledger_models: list[dict[str, Any]] = []
    kept_row_count = 0
    for model_id, model, (alternates, _) in zip(model_ids, models, inventories):
        selected = [atom for atom in model if not atom.altloc or atom.altloc == altloc_id]
        selected_site_keys: set[tuple[Any, ...]] = set()
        for atom in selected:
            site_key = _source_atom_site_key(atom)
            if site_key in selected_site_keys:
                raise _error(
                    source_format,
                    "duplicate_atom_identity_after_altloc_selection",
                    f"explicit alternate selection leaves duplicate atom identity {site_key!r}",
                )
            selected_site_keys.add(site_key)
        kept_identifiers = {_source_atom_identifier(atom) for atom in selected}
        discarded = [
            _source_atom_identifier(atom)
            for atom in model
            if _source_atom_identifier(atom) not in kept_identifiers
        ]
        selected_models.append(selected)
        kept_row_count += len(selected)
        ledger_models.append(
            {
                "model_id": model_id,
                "residues": [
                    {
                        **_residue_key_payload(residue_key),
                        "available_altloc_ids": sorted(labels),
                    }
                    for residue_key, labels in sorted(alternates.items())
                ],
                "kept_source_atom_ids": [
                    _source_atom_identifier(atom) for atom in selected
                ],
                "discarded_source_atom_ids": discarded,
            }
        )

    return selected_models, _AltlocSelectionSummary(
        status="explicit_id_selected",
        requested_altloc_id=altloc_id,
        source_atom_row_count=source_atom_row_count,
        affected_residue_count=len(reference_alternates),
        kept_row_count=kept_row_count,
        discarded_row_count=source_atom_row_count - kept_row_count,
        ledger={
            "status": "explicit_id_selected",
            "requested_altloc_id": altloc_id,
            "models": ledger_models,
        },
    )


def _error(
    source_format: str,
    code: str,
    message: str,
    *,
    line_number: int | None = None,
) -> StructureParseError:
    return StructureParseError(code, message, source_format=source_format, line_number=line_number)


def _strict_int(text: str, *, source_format: str, code: str, field: str, line_number: int) -> int:
    value = text.strip()
    if _INTEGER_RE.fullmatch(value) is None:
        raise _error(source_format, code, f"{field} is not a decimal integer: {value!r}", line_number=line_number)
    return int(value, 10)


def _strict_float(text: str, *, source_format: str, code: str, field: str, line_number: int) -> float:
    value = text.strip()
    if _DECIMAL_RE.fullmatch(value) is None:
        raise _error(source_format, code, f"{field} is not a fixed-point decimal: {value!r}", line_number=line_number)
    number = float(value)
    if not math.isfinite(number):
        raise _error(source_format, code, f"{field} must be finite", line_number=line_number)
    return number


def _optional_float(
    text: str,
    *,
    source_format: str,
    code: str,
    field: str,
    line_number: int,
) -> float | None:
    if not text.strip():
        return None
    return _strict_float(text, source_format=source_format, code=code, field=field, line_number=line_number)


def _build_system(
    *,
    source_format: str,
    parser_version: str,
    data: bytes,
    source_id: str,
    suggested_system_id: str,
    models: list[list[_SourceAtom]],
    model_ids: list[int],
    altloc_summary: _AltlocSelectionSummary,
    assembly_summary: _AssemblyExpansionSummary,
    source_bonds: list[_SourceBond],
    cell: UnitCell | None,
    format_metadata: dict[str, Any],
    operations: Iterable[str],
    missing_residue_claims: tuple[SourceReportedMissingResidueClaim, ...] = (),
    missing_atom_claims: tuple[SourceReportedMissingAtomClaim, ...] = (),
    missingness_evidence_present: bool = False,
    missingness_evidence_partially_interpreted: bool = False,
    extra_blockers: Iterable[str] = (),
    uninterpreted_category_count: int = 0,
) -> StructureIngestResult:
    if not models or not models[0]:
        raise _error(source_format, "empty_atom_site", "at least one explicit atom is required")
    reference = models[0]
    reference_serials = [atom.serial for atom in reference]
    if len(set(reference_serials)) != len(reference_serials):
        raise _error(source_format, "duplicate_atom_serial", "source atom identifiers must be unique")
    reference_identity = [atom.identity() for atom in reference]
    atom_keys: set[tuple[Any, ...]] = set()
    for atom in reference:
        key = (
            atom.chain_id,
            atom.residue_number,
            atom.insertion_code,
            atom.residue_name,
            atom.name,
        )
        if key in atom_keys:
            raise _error(source_format, "duplicate_atom_identity", f"duplicate atom identity {key!r}")
        atom_keys.add(key)
    for model_index, model in enumerate(models[1:], start=1):
        if len(model) != len(reference):
            raise _error(
                source_format,
                "model_topology_mismatch",
                f"model {model_ids[model_index]} has {len(model)} atoms; expected {len(reference)}",
            )
        for atom_index, atom in enumerate(model):
            if atom.identity() != reference_identity[atom_index]:
                raise _error(
                    source_format,
                    "model_atom_identity_mismatch",
                    f"model {model_ids[model_index]} atom {atom_index + 1} does not match the first model",
                )

    chain_order: list[str] = []
    chain_residue_keys: dict[str, list[tuple[Any, ...]]] = {}
    residue_atoms: dict[tuple[Any, ...], list[int]] = {}
    residue_base_identity: dict[tuple[str, int, str], tuple[str, bool, str, str, str]] = {}
    chain_entity_ids: dict[str, set[str]] = {}
    chain_auth_ids: dict[str, set[str]] = {}
    chain_assembly_instances: dict[str, dict[str, Any]] = {}
    for atom_index, atom in enumerate(reference):
        hetero = atom.record == "HETATM"
        entity_type = atom.entity_type or ("unknown" if hetero else "polymer")
        base = (atom.chain_id, atom.residue_number, atom.insertion_code)
        observed = (
            atom.residue_name,
            hetero,
            atom.entity_id,
            entity_type,
            atom.residue_namespace,
        )
        previous = residue_base_identity.get(base)
        if previous is not None and previous != observed:
            raise _error(
                source_format,
                "conflicting_residue_identity",
                f"residue {base!r} has conflicting names or ATOM/HETATM classes",
            )
        residue_base_identity[base] = observed
        key = (
            *base,
            atom.residue_name,
            hetero,
            atom.entity_id,
            entity_type,
            atom.residue_namespace,
        )
        if atom.chain_id not in chain_residue_keys:
            chain_order.append(atom.chain_id)
            chain_residue_keys[atom.chain_id] = []
            chain_entity_ids[atom.chain_id] = set()
            chain_auth_ids[atom.chain_id] = set()
        if atom.entity_id:
            chain_entity_ids[atom.chain_id].add(atom.entity_id)
        auth_asym_id = atom.metadata.get("mmcif_auth_asym_id")
        if isinstance(auth_asym_id, str) and auth_asym_id:
            chain_auth_ids[atom.chain_id].add(auth_asym_id)
        assembly_instance = atom.metadata.get("assembly_instance")
        if isinstance(assembly_instance, dict):
            previous_assembly_instance = chain_assembly_instances.get(atom.chain_id)
            if (
                previous_assembly_instance is not None
                and previous_assembly_instance != assembly_instance
            ):
                raise _error(
                    source_format,
                    "conflicting_chain_assembly_instance",
                    f"chain {atom.chain_id!r} carries conflicting assembly instance pointers",
                )
            chain_assembly_instances[atom.chain_id] = dict(assembly_instance)
        if key not in residue_atoms:
            residue_atoms[key] = []
            chain_residue_keys[atom.chain_id].append(key)
        residue_atoms[key].append(atom_index)

    for chain_id, entity_ids in chain_entity_ids.items():
        if len(entity_ids) > 1:
            raise _error(
                source_format,
                "conflicting_chain_entity",
                f"chain {chain_id!r} maps to multiple entity identifiers {sorted(entity_ids)!r}",
            )

    residue_index_by_key: dict[tuple[Any, ...], int] = {}
    residues: list[Residue] = []
    chains: list[Chain] = []
    chain_index_by_id = {chain_id: index for index, chain_id in enumerate(chain_order)}
    for chain_id in chain_order:
        indices: list[int] = []
        for key in chain_residue_keys[chain_id]:
            residue_index = len(residues)
            residue_index_by_key[key] = residue_index
            indices.append(residue_index)
            (
                _,
                sequence_number,
                insertion_code,
                residue_name,
                hetero,
                entity_id,
                entity_type,
                residue_namespace,
            ) = key
            source_residue_atom = reference[residue_atoms[key][0]]
            explicit_entity_type = bool(source_residue_atom.entity_type)
            source_residue_metadata = source_residue_atom.residue_metadata or {}
            residues.append(
                Residue(
                    index=residue_index,
                    name=residue_name,
                    chain_index=chain_index_by_id[chain_id],
                    sequence_number=sequence_number,
                    atom_indices=tuple(residue_atoms[key]),
                    insertion_code=insertion_code,
                    entity_type=entity_type,
                    hetero=hetero,
                    metadata={
                        "source_record": "HETATM" if hetero else "ATOM",
                        "entity_id": entity_id,
                        "source_residue_namespace": residue_namespace,
                        "entity_type_basis": (
                            "mmcif_entity_category"
                            if explicit_entity_type and entity_type != "unknown"
                            else "unresolved_from_source"
                            if explicit_entity_type
                            else "unresolved_from_hetero_record"
                            if hetero
                            else "atom_record"
                        ),
                        **source_residue_metadata,
                    },
                )
            )
        entity_ids = sorted(chain_entity_ids[chain_id])
        auth_ids = sorted(chain_auth_ids[chain_id])
        chains.append(
            Chain(
                index=chain_index_by_id[chain_id],
                chain_id=chain_id,
                residue_indices=tuple(indices),
                entity_id=entity_ids[0] if entity_ids else "",
                metadata={
                    "source_format": source_format,
                    "auth_asym_ids": auth_ids,
                    **(
                        {
                            "assembly_instance": chain_assembly_instances[
                                chain_id
                            ]
                        }
                        if chain_id in chain_assembly_instances
                        else {}
                    ),
                },
            )
        )

    atoms: list[Atom] = []
    for index, source_atom in enumerate(reference):
        residue_key = (
            source_atom.chain_id,
            source_atom.residue_number,
            source_atom.insertion_code,
            source_atom.residue_name,
            source_atom.record == "HETATM",
            source_atom.entity_id,
            source_atom.entity_type
            or ("unknown" if source_atom.record == "HETATM" else "polymer"),
            source_atom.residue_namespace,
        )
        atoms.append(
            Atom(
                index=index,
                name=source_atom.name,
                element=source_atom.element,
                atomic_number=atomic_number_for_element(source_atom.element),
                residue_index=residue_index_by_key[residue_key],
                formal_charge=source_atom.formal_charge,
                formal_charge_known=source_atom.metadata.get("formal_charge_known", True),
                serial=source_atom.serial,
                altloc=source_atom.altloc,
                occupancy=source_atom.occupancy,
                b_factor=source_atom.b_factor,
                metadata={
                    "source_record": source_atom.record,
                    **source_atom.metadata,
                    "hydrogen_origin": (
                        "source"
                        if source_atom.element == "H"
                        else "not_hydrogen"
                    ),
                },
            )
        )

    serial_to_index = {atom.serial: atom.index for atom in atoms}
    pair_set: set[tuple[int, int]] = set()
    bonds: list[Bond] = []
    for source_bond in source_bonds:
        if source_bond.serial_i not in serial_to_index or source_bond.serial_j not in serial_to_index:
            raise _error(source_format, "bond_atom_out_of_range", "bond references an unknown atom identifier")
        atom_i, atom_j = sorted((serial_to_index[source_bond.serial_i], serial_to_index[source_bond.serial_j]))
        if atom_i == atom_j:
            raise _error(source_format, "self_bond", "self-bonds are not supported")
        pair = (atom_i, atom_j)
        if pair in pair_set:
            raise _error(source_format, "duplicate_bond", f"duplicate bond {pair}")
        pair_set.add(pair)
        bonds.append(
            Bond(
                index=len(bonds),
                atom_i=atom_i,
                atom_j=atom_j,
                order=source_bond.order,
                source=source_format,
                metadata=source_bond.metadata,
            )
        )

    coordinates = torch.tensor(
        [[atom.coordinates for atom in model] for model in models],
        dtype=torch.float64,
    )
    hetero_residue_count = sum(residue.hetero for residue in residues)
    unknown_formal_charge_count = sum(
        source_atom.metadata.get("formal_charge_known") is False for source_atom in reference
    )
    unknown_entity_type_count = sum(residue.entity_type == "unknown" for residue in residues)
    coverage_blockers = [
        blocker
        for blocker in _COVERAGE_BLOCKERS
        if not (
            blocker == "biological_assembly_not_applied"
            and assembly_summary.status == "explicit_id_applied"
        )
    ]
    if unknown_formal_charge_count:
        coverage_blockers.append("formal_charge_unknown_for_some_atoms")
    if unknown_entity_type_count:
        coverage_blockers.append("entity_type_unknown_for_some_residues")
    if missing_residue_claims:
        coverage_blockers.append("source_reports_missing_residues")
    if missing_atom_claims:
        coverage_blockers.append("source_reports_missing_atoms")
    if missingness_evidence_partially_interpreted:
        coverage_blockers.append(
            "source_missingness_evidence_partially_interpreted"
        )
    coverage_blockers.extend(str(blocker) for blocker in extra_blockers)
    coverage_blockers = list(dict.fromkeys(coverage_blockers))
    coverage = StructureIngestCoverage(
        source_format=source_format,
        atom_count=len(atoms),
        bond_count=len(bonds),
        residue_count=len(residues),
        chain_count=len(chains),
        model_count=len(models),
        explicit_hydrogen_count=sum(atom.element == "H" for atom in atoms),
        hetero_residue_count=hetero_residue_count,
        cell_present=cell is not None,
        unknown_formal_charge_count=unknown_formal_charge_count,
        unknown_entity_type_count=unknown_entity_type_count,
        uninterpreted_category_count=int(uninterpreted_category_count),
        source_atom_row_count=altloc_summary.source_atom_row_count,
        altloc_status=altloc_summary.status,
        requested_altloc_id=altloc_summary.requested_altloc_id,
        altloc_affected_residue_count=altloc_summary.affected_residue_count,
        altloc_kept_row_count=altloc_summary.kept_row_count,
        altloc_discarded_row_count=altloc_summary.discarded_row_count,
        coordinate_scope=assembly_summary.coordinate_scope,
        assembly_status=assembly_summary.status,
        requested_assembly_id=assembly_summary.requested_assembly_id,
        assembly_operation_sequence_count=assembly_summary.operation_sequence_count,
        assembly_operation_application_count=(
            assembly_summary.operation_application_count
        ),
        assembly_chain_instance_count=assembly_summary.chain_instance_count,
        assembly_output_atom_count=(
            assembly_summary.expanded_topology_atom_count
            if assembly_summary.status == "explicit_id_applied"
            else 0
        ),
        blockers=tuple(coverage_blockers),
    )
    source_sha256 = hashlib.sha256(data).hexdigest()
    system_id = source_id.strip() or suggested_system_id.strip() or f"{source_format}-{source_sha256[:16]}"
    try:
        system = AllAtomSystem(
            system_id=system_id,
            atoms=tuple(atoms),
            bonds=tuple(bonds),
            residues=tuple(residues),
            chains=tuple(chains),
            coordinates=coordinates,
            provenance=StructureProvenance(
                source_format=source_format,
                source_id=source_id,
                source_sha256=source_sha256,
                parser_name=(
                    "betelgeuze_engine_v2.molecular.pdb_mmcif."
                    f"parse_{source_format}"
                ),
                parser_version=parser_version,
                operations=tuple(operations),
                preparation_ready=False,
                claim_safe=False,
                metadata={
                    "coverage": coverage.to_dict(),
                    "model_ids": list(model_ids),
                },
            ),
            cell=cell,
            metadata=format_metadata,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise _error(
            source_format,
            "canonical_construction_failed",
            "parsed structure exceeds or violates the canonical system contract",
        ) from exc
    try:
        require_valid_all_atom_system(system)
    except MolecularValidationError as exc:
        raise _error(source_format, "canonical_validation_failed", str(exc)) from exc
    topology_sha256 = canonical_topology_sha256(system)
    try:
        missingness_evidence = build_source_reported_missingness_report(
            source_format=source_format,
            source_sha256=source_sha256,
            canonical_topology_sha256=topology_sha256,
            coordinate_scope=assembly_summary.coordinate_scope,
            altloc_status=altloc_summary.status,
            requested_altloc_id=altloc_summary.requested_altloc_id,
            assembly_status=assembly_summary.status,
            requested_assembly_id=assembly_summary.requested_assembly_id,
            missing_residue_claims=missing_residue_claims,
            missing_atom_claims=missing_atom_claims,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise _error(
            source_format,
            "invalid_missingness_evidence",
            "source-reported missingness evidence violates the canonical contract",
        ) from exc
    evidence_status = (
        "present_partially_interpreted"
        if missingness_evidence_partially_interpreted
        else "present_fully_preserved"
        if missingness_evidence_present
        else "not_present"
    )
    coverage = replace(
        coverage,
        canonical_topology_sha256=topology_sha256,
        missingness_evidence_status=evidence_status,
        source_reported_missing_residue_claim_count=(
            missingness_evidence.source_reported_missing_residue_count
        ),
        source_reported_missing_atom_claim_count=(
            missingness_evidence.source_reported_missing_atom_count
        ),
        source_missingness_evidence_sha256=missingness_evidence.report_sha256,
    )
    provenance_metadata = dict(system.provenance.metadata)
    provenance_metadata["coverage"] = coverage.to_dict()
    provenance_metadata["canonical_topology_schema_id"] = (
        CANONICAL_TOPOLOGY_SCHEMA_ID
    )
    provenance_metadata["canonical_topology_sha256"] = topology_sha256
    provenance_metadata["source_missingness_evidence_schema_id"] = (
        MISSINGNESS_REPORT_SCHEMA_ID
    )
    provenance_metadata["source_missingness_evidence_sha256"] = (
        missingness_evidence.report_sha256
    )
    system_metadata = dict(system.metadata)
    source_metadata = dict(system_metadata[source_format])
    source_metadata["source_reported_missingness"] = missingness_evidence.to_dict()
    system_metadata[source_format] = source_metadata
    try:
        system = replace(
            system,
            provenance=replace(system.provenance, metadata=provenance_metadata),
            metadata=system_metadata,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise _error(
            source_format,
            "invalid_missingness_evidence",
            "attached source missingness evidence exceeds the canonical contract",
        ) from exc
    try:
        system = attach_parser_observation_digest(system)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _error(
            source_format,
            "parser_observation_attachment_failed",
            "parser-observed chemical-state evidence violates the canonical contract",
        ) from exc
    return StructureIngestResult(
        system=system,
        coverage=coverage,
        missingness_evidence=missingness_evidence,
    )


@dataclass(frozen=True)
class _PdbTerRecord:
    serial: int
    residue_name: str
    chain_id: str
    residue_number: int
    insertion_code: str
    after_atom_index: int
    after_atom_serial: int
    line_number: int

    def layout_identity(self) -> tuple[Any, ...]:
        return (
            self.serial,
            self.residue_name,
            self.chain_id,
            self.residue_number,
            self.insertion_code,
            self.after_atom_index,
            self.after_atom_serial,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "serial": self.serial,
            "residue_name": self.residue_name,
            "chain_id": self.chain_id,
            "residue_number": self.residue_number,
            "insertion_code": self.insertion_code,
            "after_atom_index": self.after_atom_index,
            "after_atom_serial": self.after_atom_serial,
            "line_number": self.line_number,
        }


@dataclass(frozen=True)
class _PdbMissingnessRemarkLine:
    remark_number: int
    line_number: int
    raw_line: str

    @property
    def padded(self) -> str:
        return self.raw_line.ljust(80)

    def to_dict(self) -> dict[str, Any]:
        return {
            "remark_number": self.remark_number,
            "line_number": self.line_number,
            "raw_line": self.raw_line,
        }


@dataclass(frozen=True)
class _MmcifMissingnessCoordinateCheck:
    line_number: int
    occupancy_flag: int
    model_id: int
    chain_id: str
    residue_id: str
    residue_name: str
    insertion_code: str
    identity_basis: str
    atom_name: str | None = None
    altloc_id: str = ""


@dataclass
class _MmcifOccupancySummary:
    presence_count: int = 0
    any_nonzero: bool = False
    any_unavailable: bool = False

    def observe(self, occupancy: float | None) -> None:
        self.presence_count += 1
        if occupancy is None:
            self.any_unavailable = True
        elif occupancy != 0.0:
            self.any_nonzero = True


_PDB_MODELS_RANGE_RE = re.compile(
    r"^  MODELS (?P<start>[1-9]\d*)-(?P<end>[1-9]\d*)$"
)


def _parse_pdb_missingness_remarks(
    records: list[_PdbMissingnessRemarkLine],
    *,
    raw_models: list[list[_SourceAtom]],
    model_ids: list[int],
    explicit_models: bool,
) -> tuple[
    tuple[SourceReportedMissingResidueClaim, ...],
    tuple[SourceReportedMissingAtomClaim, ...],
    bool,
    tuple[str, ...],
    dict[str, Any],
]:
    if not records:
        return (), (), False, (), {
            "interpretation_policy": "strict_remark_465_470_preserve_only/v1",
            "remark_line_count": 0,
            "remark_465_line_count": 0,
            "remark_470_line_count": 0,
            "raw_records": [],
        }

    model_id_set = set(model_ids)
    active_ranges: dict[int, tuple[int, int] | None] = {465: None, 470: None}
    active_range_lines: dict[int, int | None] = {465: None, 470: None}
    scope_modes: dict[int, str | None] = {465: None, 470: None}
    range_has_data: dict[int, bool] = {465: False, 470: False}
    residue_claims: list[SourceReportedMissingResidueClaim] = []
    atom_claims: list[SourceReportedMissingAtomClaim] = []
    residue_targets: list[range | tuple[int, ...]] = []
    atom_targets: list[range | tuple[int, ...]] = []
    residue_keys: set[tuple[str, ...]] = set()
    atom_keys: set[tuple[str, ...]] = set()

    def declare_range(record: _PdbMissingnessRemarkLine) -> bool:
        content = record.padded[11:80].rstrip()
        if not content.lstrip().upper().startswith("MODELS"):
            return False
        match = _PDB_MODELS_RANGE_RE.fullmatch(content)
        if match is None:
            raise _error(
                "pdb",
                "invalid_missingness_model_range",
                "REMARK MODELS scope must be an ascending positive integer range",
                line_number=record.line_number,
            )
        remark_number = record.remark_number
        if scope_modes[remark_number] == "row" or active_ranges[remark_number] is not None:
            raise _error(
                "pdb",
                "mixed_missingness_model_scope",
                "REMARK missingness rows cannot mix or repeat model-range scopes",
                line_number=record.line_number,
            )
        start = int(match.group("start"), 10)
        end = int(match.group("end"), 10)
        if end < start:
            raise _error(
                "pdb",
                "invalid_missingness_model_range",
                "REMARK MODELS range must be ascending",
                line_number=record.line_number,
            )
        matching_model_count = sum(start <= model_id <= end for model_id in model_ids)
        if matching_model_count != end - start + 1:
            raise _error(
                "pdb",
                "missingness_model_out_of_range",
                "REMARK MODELS range is not exactly represented by coordinate MODEL ids",
                line_number=record.line_number,
            )
        active_ranges[remark_number] = (start, end)
        active_range_lines[remark_number] = record.line_number
        scope_modes[remark_number] = "range"
        return True

    def row_scope(
        record: _PdbMissingnessRemarkLine,
        model_field: str,
    ) -> tuple[str, range | tuple[int, ...]]:
        remark_number = record.remark_number
        active_range = active_ranges[remark_number]
        if active_range is not None:
            if model_field.strip():
                raise _error(
                    "pdb",
                    "mixed_missingness_model_scope",
                    "row model ids are forbidden inside a MODELS range scope",
                    line_number=record.line_number,
                )
            range_has_data[remark_number] = True
            start, end = active_range
            return f"{start}-{end}", range(start, end + 1)
        if scope_modes[remark_number] == "range":
            raise _error(
                "pdb",
                "mixed_missingness_model_scope",
                "missingness model scope is inconsistent",
                line_number=record.line_number,
            )
        scope_modes[remark_number] = "row"
        if not model_field.strip():
            if explicit_models:
                raise _error(
                    "pdb",
                    "invalid_missingness_model",
                    "explicit coordinate models require a row model id or MODELS range",
                    line_number=record.line_number,
                )
            return "", tuple(model_ids)
        model_id = _strict_int(
            model_field,
            source_format="pdb",
            code="invalid_missingness_model",
            field="missingness model id",
            line_number=record.line_number,
        )
        if model_id < 1 or model_id not in model_id_set:
            raise _error(
                "pdb",
                "missingness_model_out_of_range",
                f"missingness row references coordinate model {model_id} that is absent",
                line_number=record.line_number,
            )
        return str(model_id), (model_id,)

    def target_scope_payload(
        targets: range | tuple[int, ...],
    ) -> dict[str, Any]:
        if isinstance(targets, range):
            return {
                "kind": "inclusive_model_range",
                "start": targets.start,
                "end": targets.stop - 1,
                "count": len(targets),
            }
        return {
            "kind": "explicit_model_ids",
            "model_ids": list(targets),
            "count": len(targets),
        }

    def table_header(record: _PdbMissingnessRemarkLine) -> bool:
        padded = record.padded
        if record.remark_number == 465:
            return (
                padded[11:14]
                == ("   " if active_ranges[465] is not None else "  M")
                and padded[15:18] == "RES"
                and padded[19] == "C"
                and padded[21:26] == "SSSEQ"
                and padded[26] == "I"
                and not padded[27:80].strip()
            )
        if active_ranges[470] is None:
            return (
                padded[11:14] == "  M"
                and padded[15:18] == "RES"
                and padded[20] == "C"
                and padded[21:25] == "SSEQ"
                and padded[25] == "I"
                and padded[28:33] == "ATOMS"
                and not padded[33:80].strip()
            )
        return (
            not padded[11:15].strip()
            and padded[15:18] == "RES"
            and padded[19] == "C"
            and padded[20:24] == "SSEQ"
            and padded[24] == "I"
            and padded[27:32] == "ATOMS"
            and not padded[32:80].strip()
        )

    def boilerplate(record: _PdbMissingnessRemarkLine) -> bool:
        content = record.padded[11:80].strip().upper()
        if not content:
            return True
        return content.startswith(
            (
                "MISSING ",
                "THE FOLLOWING ",
                "EXPERIMENT.",
                "IDENTIFIER;",
                "RES=RESIDUE NAME;",
                "C=CHAIN IDENTIFIER;",
                "I=INSERTION CODE",
                "SSSEQ=SEQUENCE NUMBER;",
            )
        )

    def residue_data_like(record: _PdbMissingnessRemarkLine) -> bool:
        return bool(record.padded[11:80].strip())

    def require_claim_capacity(
        *,
        claim_kind: str,
        line_number: int,
    ) -> None:
        next_residue_count = len(residue_claims) + (claim_kind == "residue")
        next_atom_count = len(atom_claims) + (claim_kind == "atom")
        if next_residue_count > MAX_MISSING_RESIDUE_CLAIMS:
            raise _error(
                "pdb",
                "missing_residue_evidence_limit_exceeded",
                "REMARK 465 claim count exceeds the fixed limit",
                line_number=line_number,
            )
        if next_atom_count > MAX_MISSING_ATOM_CLAIMS:
            raise _error(
                "pdb",
                "missing_atom_evidence_limit_exceeded",
                "REMARK 470 atom claim count exceeds the fixed limit",
                line_number=line_number,
            )
        if next_residue_count + next_atom_count > MAX_TOTAL_MISSINGNESS_CLAIMS:
            raise _error(
                "pdb",
                "combined_missingness_evidence_limit_exceeded",
                "combined REMARK 465/470 claim count exceeds the fixed limit",
                line_number=line_number,
            )
        if (
            next_residue_count + next_atom_count
            > _MAX_PDB_MISSINGNESS_PROJECTED_CLAIMS
        ):
            raise _error(
                "pdb",
                "missingness_metadata_projection_limit_exceeded",
                "source missingness claims exceed the canonical metadata projection limit",
                line_number=line_number,
            )

    for record in records:
        if declare_range(record):
            continue
        if table_header(record):
            continue
        if boilerplate(record):
            continue
        padded = record.padded
        if record.remark_number == 470:
            tail_start = 27 if active_ranges[470] is not None else 28
            if (
                not padded[11:tail_start].strip()
                and padded[tail_start:80].strip()
            ):
                raise _error(
                    "pdb",
                    "unsupported_missing_atom_continuation",
                    "REMARK 470 atoms-only continuation rows are not supported",
                    line_number=record.line_number,
                )
        if not residue_data_like(record):
            continue
        if record.remark_number == 465:
            if (
                padded[14] != " "
                or padded[18] != " "
                or padded[20] != " "
                or padded[27:80].strip()
            ):
                raise _error(
                    "pdb",
                    "invalid_remark_465_layout",
                    "REMARK 465 data row violates fixed reserved columns",
                    line_number=record.line_number,
                )
            residue_name = padded[15:18].strip().upper()
            if not residue_name or any(
                character.isspace() for character in residue_name
            ):
                raise _error(
                    "pdb",
                    "missing_residue_identity",
                    "REMARK 465 residue name must be nonempty without whitespace",
                    line_number=record.line_number,
                )
            chain_id = padded[19].strip()
            residue_number = _strict_int(
                padded[21:26],
                source_format="pdb",
                code="missing_residue_identity",
                field="missing residue sequence number",
                line_number=record.line_number,
            )
            insertion_code = padded[26].strip()
            source_model_id, targets = row_scope(record, padded[11:14])
            semantic_key = (
                source_model_id,
                chain_id,
                str(residue_number),
                residue_name,
                insertion_code,
            )
            if semantic_key in residue_keys:
                raise _error(
                    "pdb",
                    "duplicate_missingness_record",
                    "duplicate REMARK 465 missing-residue claim",
                    line_number=record.line_number,
                )
            require_claim_capacity(
                claim_kind="residue",
                line_number=record.line_number,
            )
            try:
                claim = SourceReportedMissingResidueClaim(
                    source_ordinal=len(residue_claims) + 1,
                    source_category="PDB_REMARK_465",
                    source_model_id=source_model_id,
                    source_chain_id=chain_id,
                    source_residue_id=str(residue_number),
                    source_residue_name=residue_name,
                    source_insertion_code=insertion_code,
                    raw_payload={
                        "line_number": record.line_number,
                        "raw_line": record.raw_line,
                        "model_field": padded[11:14],
                        "target_model_scope": target_scope_payload(targets),
                    },
                )
            except (TypeError, ValueError, OverflowError) as exc:
                raise _error(
                    "pdb",
                    "invalid_missingness_evidence",
                    "REMARK 465 claim violates the canonical evidence contract",
                    line_number=record.line_number,
                ) from exc
            residue_keys.add(semantic_key)
            residue_claims.append(claim)
            residue_targets.append(targets)
            continue

        active_range = active_ranges[470]
        if active_range is None:
            if (
                padded[14] != " "
                or padded[18:20] != "  "
                or padded[26:28] != "  "
            ):
                raise _error(
                    "pdb",
                    "invalid_remark_470_layout",
                    "REMARK 470 row violates the non-NMR fixed layout",
                    line_number=record.line_number,
                )
            residue_name = padded[15:18].strip().upper()
            chain_id = padded[20].strip()
            residue_field = padded[21:25]
            insertion_code = padded[25].strip()
            atom_tail = padded[28:80]
            model_field = padded[11:14]
        else:
            if padded[11:15].strip() or padded[18] != " " or padded[25:27] != "  ":
                raise _error(
                    "pdb",
                    "invalid_remark_470_layout",
                    "REMARK 470 row violates the NMR model-range fixed layout",
                    line_number=record.line_number,
                )
            residue_name = padded[15:18].strip().upper()
            chain_id = padded[19].strip()
            residue_field = padded[20:24]
            insertion_code = padded[24].strip()
            atom_tail = padded[27:80]
            model_field = ""
        if not residue_name or any(
            character.isspace() for character in residue_name
        ):
            raise _error(
                "pdb",
                "missing_atom_identity",
                "REMARK 470 residue name must be nonempty without whitespace",
                line_number=record.line_number,
            )
        residue_number = _strict_int(
            residue_field,
            source_format="pdb",
            code="missing_atom_identity",
            field="missing-atom residue sequence number",
            line_number=record.line_number,
        )
        atom_names = atom_tail.split()
        if not atom_names:
            raise _error(
                "pdb",
                "empty_missing_atom_list",
                "REMARK 470 row must list at least one atom name",
                line_number=record.line_number,
            )
        if any(
            len(atom_name) > 4
            or not atom_name.isascii()
            or not atom_name.isprintable()
            for atom_name in atom_names
        ):
            raise _error(
                "pdb",
                "invalid_missing_atom_name",
                "REMARK 470 atom names must be one to four printable ASCII characters",
                line_number=record.line_number,
            )
        source_model_id, targets = row_scope(record, model_field)
        for atom_position, atom_name in enumerate(atom_names, start=1):
            semantic_key = (
                source_model_id,
                chain_id,
                str(residue_number),
                residue_name,
                insertion_code,
                atom_name,
            )
            if semantic_key in atom_keys:
                raise _error(
                    "pdb",
                    "duplicate_missingness_record",
                    "duplicate REMARK 470 missing-atom claim",
                    line_number=record.line_number,
                )
            require_claim_capacity(
                claim_kind="atom",
                line_number=record.line_number,
            )
            try:
                claim = SourceReportedMissingAtomClaim(
                    source_ordinal=len(atom_claims) + 1,
                    source_category="PDB_REMARK_470",
                    source_model_id=source_model_id,
                    source_chain_id=chain_id,
                    source_residue_id=str(residue_number),
                    source_residue_name=residue_name,
                    source_insertion_code=insertion_code,
                    source_atom_name=atom_name,
                    raw_payload={
                        "line_number": record.line_number,
                        "raw_line": record.raw_line,
                        "atom_position_in_row": atom_position,
                        "model_field": model_field,
                        "target_model_scope": target_scope_payload(targets),
                    },
                )
            except (TypeError, ValueError, OverflowError) as exc:
                raise _error(
                    "pdb",
                    "invalid_missingness_evidence",
                    "REMARK 470 claim violates the canonical evidence contract",
                    line_number=record.line_number,
                ) from exc
            atom_keys.add(semantic_key)
            atom_claims.append(claim)
            atom_targets.append(targets)

    for remark_number, active_range in active_ranges.items():
        if active_range is not None and not range_has_data[remark_number]:
            raise _error(
                "pdb",
                "invalid_missingness_model_range",
                f"REMARK {remark_number} MODELS range has no following data rows",
                line_number=active_range_lines[remark_number],
            )

    residue_model_sets: dict[tuple[str, ...], set[int]] = {}
    atom_model_sets: dict[tuple[str, ...], set[int]] = {}
    for model_id, model in zip(model_ids, raw_models):
        for atom in model:
            residue_key = (
                atom.chain_id,
                str(atom.residue_number),
                atom.residue_name,
                atom.insertion_code,
            )
            atom_key = (*residue_key, atom.name)
            residue_model_sets.setdefault(residue_key, set()).add(model_id)
            atom_model_sets.setdefault(atom_key, set()).add(model_id)
    residue_models = {
        key: tuple(sorted(present_models))
        for key, present_models in residue_model_sets.items()
    }
    atom_models = {
        key: tuple(sorted(present_models))
        for key, present_models in atom_model_sets.items()
    }

    def scope_intersects(
        targets: range | tuple[int, ...],
        present_models: tuple[int, ...],
    ) -> bool:
        if not present_models:
            return False
        if isinstance(targets, range):
            left = bisect_left(present_models, targets.start)
            right = bisect_left(present_models, targets.stop)
            return right > left
        return any(
            (index := bisect_left(present_models, model_id)) < len(present_models)
            and present_models[index] == model_id
            for model_id in targets
        )

    def scope_is_covered(
        targets: range | tuple[int, ...],
        present_models: tuple[int, ...],
    ) -> bool:
        if isinstance(targets, range):
            left = bisect_left(present_models, targets.start)
            right = bisect_right(present_models, targets.stop - 1)
            return right - left == len(targets)
        return all(
            (index := bisect_left(present_models, model_id)) < len(present_models)
            and present_models[index] == model_id
            for model_id in targets
        )

    def claim_line_number(
        claim: SourceReportedMissingResidueClaim | SourceReportedMissingAtomClaim,
    ) -> int | None:
        line_number = claim.raw_payload.get("line_number")
        return line_number if type(line_number) is int else None

    for claim, targets in zip(residue_claims, residue_targets):
        residue_key = (
            claim.source_chain_id,
            claim.source_residue_id,
            claim.source_residue_name,
            claim.source_insertion_code,
        )
        if scope_intersects(targets, residue_models.get(residue_key, ())):
            raise _error(
                "pdb",
                "missing_residue_present_in_coordinates",
                "REMARK 465 declares a residue that is present in deposited coordinates",
                line_number=claim_line_number(claim),
            )
    for claim, targets in zip(atom_claims, atom_targets):
        residue_key = (
            claim.source_chain_id,
            claim.source_residue_id,
            claim.source_residue_name,
            claim.source_insertion_code,
        )
        if not scope_is_covered(targets, residue_models.get(residue_key, ())):
            raise _error(
                "pdb",
                "missing_atom_residue_absent",
                "REMARK 470 references a residue absent from deposited coordinates",
                line_number=claim_line_number(claim),
            )
        atom_key = (*residue_key, claim.source_atom_name)
        if scope_intersects(targets, atom_models.get(atom_key, ())):
            raise _error(
                "pdb",
                "declared_missing_atom_present",
                "REMARK 470 declares an atom present in deposited coordinates",
                line_number=claim_line_number(claim),
            )

    return (
        tuple(residue_claims),
        tuple(atom_claims),
        True,
        ("source_missingness_seqres_membership_not_assessed",),
        {
            "interpretation_policy": "strict_remark_465_470_preserve_only/v1",
            "remark_line_count": len(records),
            "remark_465_line_count": sum(
                record.remark_number == 465 for record in records
            ),
            "remark_470_line_count": sum(
                record.remark_number == 470 for record in records
            ),
            "raw_records": [record.to_dict() for record in records],
        },
    )


def _remap_pdb_ter_records_after_altloc_selection(
    raw_models: list[list[_SourceAtom]],
    selected_models: list[list[_SourceAtom]],
    records_by_model: list[list[_PdbTerRecord]],
) -> list[list[_PdbTerRecord]]:
    remapped_by_model: list[list[_PdbTerRecord]] = []
    for raw_model, selected_model, records in zip(
        raw_models,
        selected_models,
        records_by_model,
    ):
        selected_index_by_serial = {
            atom.serial: index for index, atom in enumerate(selected_model)
        }
        remapped: list[_PdbTerRecord] = []
        for record in records:
            preceding = [
                atom
                for atom in raw_model[: record.after_atom_index + 1]
                if atom.serial in selected_index_by_serial
            ]
            if not preceding:
                raise _error(
                    "pdb",
                    "altloc_ter_selection_empty",
                    "alternate-location selection removed every atom preceding TER",
                    line_number=record.line_number,
                )
            selected_preceding = preceding[-1]
            if (
                selected_preceding.residue_name != record.residue_name
                or selected_preceding.chain_id != record.chain_id
                or selected_preceding.residue_number != record.residue_number
                or selected_preceding.insertion_code != record.insertion_code
            ):
                raise _error(
                    "pdb",
                    "altloc_ter_identity_mismatch",
                    "alternate-location selection changed the residue immediately preceding TER",
                    line_number=record.line_number,
                )
            remapped.append(
                replace(
                    record,
                    after_atom_index=selected_index_by_serial[selected_preceding.serial],
                    after_atom_serial=selected_preceding.serial,
                )
            )
        remapped_by_model.append(remapped)
    return remapped_by_model


def _parse_pdb_charge(text: str, *, line_number: int) -> int:
    value = text.strip()
    if not value:
        return 0
    if len(value) != 2 or value[0] not in "123456789" or value[1] not in "+-":
        raise _error("pdb", "invalid_formal_charge", f"invalid PDB formal charge {value!r}", line_number=line_number)
    magnitude = int(value[0])
    return magnitude if value[1] == "+" else -magnitude


def _parse_pdb_atom(line: str, *, line_number: int) -> _SourceAtom:
    if len(line) < 78 or len(line) > 80:
        raise _error(
            "pdb",
            "invalid_atom_line",
            "ATOM/HETATM line must occupy 78 through 80 columns",
            line_number=line_number,
        )
    padded = line.ljust(80)
    if padded[0:6] not in {"ATOM  ", "HETATM"}:
        raise _error("pdb", "invalid_atom_line", "ATOM/HETATM record field is malformed", line_number=line_number)
    if padded[11] != " " or padded[20] != " " or padded[27:30] != "   ":
        raise _error(
            "pdb",
            "invalid_atom_reserved_columns",
            "ATOM/HETATM reserved columns 12, 21, and 28-30 must be blank",
            line_number=line_number,
        )
    record = padded[0:6].strip()
    serial = _strict_int(padded[6:11], source_format="pdb", code="invalid_atom_serial", field="serial", line_number=line_number)
    if serial < 1:
        raise _error("pdb", "invalid_atom_serial", "atom serial must be positive", line_number=line_number)
    atom_name = padded[12:16].strip()
    if not atom_name:
        raise _error("pdb", "missing_atom_name", "atom name is empty", line_number=line_number)
    raw_altloc = padded[16]
    if raw_altloc == " ":
        altloc = ""
    elif raw_altloc.isspace() or not raw_altloc.isprintable():
        raise _error(
            "pdb",
            "invalid_altloc_id",
            "PDB alternate-location column must be blank or printable non-whitespace ASCII",
            line_number=line_number,
        )
    else:
        altloc = raw_altloc
    residue_name = padded[17:20].strip().upper()
    if not residue_name:
        raise _error("pdb", "missing_residue_name", "residue name is empty", line_number=line_number)
    chain_id = padded[21].strip()
    residue_number = _strict_int(
        padded[22:26], source_format="pdb", code="invalid_residue_number", field="residue_number", line_number=line_number
    )
    insertion_code = padded[26].strip()
    x = _strict_float(padded[30:38], source_format="pdb", code="invalid_atom_coordinate", field="x", line_number=line_number)
    y = _strict_float(padded[38:46], source_format="pdb", code="invalid_atom_coordinate", field="y", line_number=line_number)
    z = _strict_float(padded[46:54], source_format="pdb", code="invalid_atom_coordinate", field="z", line_number=line_number)
    occupancy = _optional_float(
        padded[54:60], source_format="pdb", code="invalid_occupancy", field="occupancy", line_number=line_number
    )
    if occupancy is not None and not 0.0 <= occupancy <= 1.0:
        raise _error("pdb", "invalid_occupancy", "occupancy must be in [0, 1]", line_number=line_number)
    b_factor = _optional_float(
        padded[60:66], source_format="pdb", code="invalid_b_factor", field="b_factor", line_number=line_number
    )
    element = canonical_element_symbol(padded[76:78])
    if not element:
        raise _error("pdb", "missing_element", "element columns are required; atom-name inference is disabled", line_number=line_number)
    if atomic_number_for_element(element) == 0:
        raise _error("pdb", "unknown_element", f"unknown element {element!r}", line_number=line_number)
    charge_field = padded[78:80]
    formal_charge_known = bool(charge_field.strip())
    formal_charge = _parse_pdb_charge(charge_field, line_number=line_number)
    if padded[66:72].strip():
        raise _error("pdb", "unsupported_atom_columns", "columns 67-72 must be blank", line_number=line_number)
    return _SourceAtom(
        record=record,
        serial=serial,
        name=atom_name,
        residue_name=residue_name,
        chain_id=chain_id,
        residue_number=residue_number,
        insertion_code=insertion_code,
        altloc=altloc,
        element=element,
        formal_charge=formal_charge,
        occupancy=occupancy,
        b_factor=b_factor,
        coordinates=(x, y, z),
        metadata={
            "pdb_atom_name_field": padded[12:16],
            "pdb_altloc": altloc,
            "pdb_segment_id": padded[72:76].strip(),
            "formal_charge_known": formal_charge_known,
            "formal_charge_source": "pdb_columns_79_80" if formal_charge_known else "missing_in_pdb",
            "formal_charge_interpretation": "explicit" if formal_charge_known else "placeholder_zero_unknown",
        },
        residue_namespace=padded[72:76].strip(),
        residue_metadata={"pdb_segment_id": padded[72:76].strip()},
    )


def _parse_pdb_ter(
    line: str,
    *,
    line_number: int,
    preceding_atom: _SourceAtom,
    after_atom_index: int,
) -> _PdbTerRecord:
    if len(line) < 26 or len(line) > 80:
        raise _error(
            "pdb",
            "invalid_ter",
            "TER line must provide fixed fields through residue sequence number and may omit a blank insertion code",
            line_number=line_number,
        )
    padded = line.ljust(80)
    if padded[0:6] != "TER   ":
        raise _error("pdb", "invalid_ter", "TER record field is malformed", line_number=line_number)
    if padded[11:17] != "      " or padded[20] != " " or padded[27:80].strip():
        raise _error("pdb", "invalid_ter", "TER reserved and trailing columns must be blank", line_number=line_number)
    serial = _strict_int(
        padded[6:11], source_format="pdb", code="invalid_ter_serial", field="serial", line_number=line_number
    )
    if serial != preceding_atom.serial + 1:
        raise _error(
            "pdb",
            "ter_identity_mismatch",
            f"TER serial {serial} must immediately follow atom serial {preceding_atom.serial}",
            line_number=line_number,
        )
    residue_name = padded[17:20].strip().upper()
    chain_id = padded[21].strip()
    residue_number = _strict_int(
        padded[22:26],
        source_format="pdb",
        code="invalid_ter_residue_number",
        field="residue_number",
        line_number=line_number,
    )
    insertion_code = padded[26].strip()
    ter_residue_identity = (residue_name, chain_id, residue_number, insertion_code)
    preceding_residue_identity = (
        preceding_atom.residue_name,
        preceding_atom.chain_id,
        preceding_atom.residue_number,
        preceding_atom.insertion_code,
    )
    if ter_residue_identity != preceding_residue_identity:
        raise _error(
            "pdb",
            "ter_identity_mismatch",
            f"TER residue identity {ter_residue_identity!r} does not match the preceding atom",
            line_number=line_number,
        )
    return _PdbTerRecord(
        serial=serial,
        residue_name=residue_name,
        chain_id=chain_id,
        residue_number=residue_number,
        insertion_code=insertion_code,
        after_atom_index=after_atom_index,
        after_atom_serial=preceding_atom.serial,
        line_number=line_number,
    )


def _parse_cryst1(line: str, *, line_number: int) -> tuple[UnitCell, dict[str, Any]]:
    if len(line) < 70 or len(line) > 80:
        raise _error("pdb", "invalid_cryst1", "CRYST1 line must occupy 70 through 80 columns", line_number=line_number)
    padded = line.ljust(80)
    if padded[0:6] != "CRYST1" or padded[54] != " " or padded[70:80].strip():
        raise _error("pdb", "invalid_cryst1", "CRYST1 reserved and trailing columns must be blank", line_number=line_number)
    a = _strict_float(padded[6:15], source_format="pdb", code="invalid_cryst1", field="a", line_number=line_number)
    b = _strict_float(padded[15:24], source_format="pdb", code="invalid_cryst1", field="b", line_number=line_number)
    c = _strict_float(padded[24:33], source_format="pdb", code="invalid_cryst1", field="c", line_number=line_number)
    alpha = _strict_float(padded[33:40], source_format="pdb", code="invalid_cryst1", field="alpha", line_number=line_number)
    beta = _strict_float(padded[40:47], source_format="pdb", code="invalid_cryst1", field="beta", line_number=line_number)
    gamma = _strict_float(padded[47:54], source_format="pdb", code="invalid_cryst1", field="gamma", line_number=line_number)
    if min(a, b, c) <= 0.0 or not all(0.0 < angle < 180.0 for angle in (alpha, beta, gamma)):
        raise _error("pdb", "invalid_cryst1", "cell lengths and angles must define a positive cell", line_number=line_number)
    space_group = padded[55:66].strip()
    normalized_space_group = " ".join(space_group.upper().split())
    if (
        all(math.isclose(length, 1.0, rel_tol=0.0, abs_tol=1.0e-6) for length in (a, b, c))
        and all(math.isclose(angle, 90.0, rel_tol=0.0, abs_tol=1.0e-6) for angle in (alpha, beta, gamma))
        and normalized_space_group == "P 1"
    ):
        raise _error(
            "pdb",
            "dummy_cryst1",
            "1x1x1 A, 90-degree P 1 CRYST1 placeholder is not a physical periodic cell",
            line_number=line_number,
        )
    alpha_r, beta_r, gamma_r = map(math.radians, (alpha, beta, gamma))
    sin_gamma = math.sin(gamma_r)
    if abs(sin_gamma) <= 1.0e-12:
        raise _error("pdb", "invalid_cryst1", "gamma produces a singular cell", line_number=line_number)
    vector_a = (a, 0.0, 0.0)
    vector_b = (b * math.cos(gamma_r), b * sin_gamma, 0.0)
    c_x = c * math.cos(beta_r)
    c_y = c * (math.cos(alpha_r) - math.cos(beta_r) * math.cos(gamma_r)) / sin_gamma
    c_z_squared = c * c - c_x * c_x - c_y * c_y
    if c_z_squared <= 1.0e-12:
        raise _error("pdb", "invalid_cryst1", "cell vectors do not form positive volume", line_number=line_number)
    vectors = torch.tensor([vector_a, vector_b, (c_x, c_y, math.sqrt(c_z_squared))], dtype=torch.float64)
    z_text = padded[66:70].strip()
    z_value = None
    if z_text:
        z_value = _strict_int(z_text, source_format="pdb", code="invalid_cryst1", field="z", line_number=line_number)
        if z_value < 1:
            raise _error("pdb", "invalid_cryst1", "z must be positive when present", line_number=line_number)
    return UnitCell(vectors=vectors, periodic=(False, False, False)), {
        "lengths_angstrom": [a, b, c],
        "angles_degrees": [alpha, beta, gamma],
        "space_group": space_group,
        "z": z_value,
    }


def _parse_conect(line: str, *, line_number: int) -> tuple[int, tuple[int, ...]]:
    if len(line) < 11 or len(line) > 80:
        raise _error("pdb", "invalid_conect", "CONECT supports one source and up to four targets", line_number=line_number)
    padded = line.ljust(80)
    if padded[0:6] != "CONECT" or padded[31:80].strip():
        raise _error("pdb", "invalid_conect", "CONECT reserved and trailing columns must be blank", line_number=line_number)
    source = _strict_int(padded[6:11], source_format="pdb", code="invalid_conect", field="source", line_number=line_number)
    targets: list[int] = []
    for start in (11, 16, 21, 26):
        field = padded[start : start + 5]
        if not field.strip():
            continue
        targets.append(
            _strict_int(field, source_format="pdb", code="invalid_conect", field="target", line_number=line_number)
        )
    if not targets:
        raise _error("pdb", "invalid_conect", "CONECT requires at least one target", line_number=line_number)
    return source, tuple(targets)


def parse_pdb(
    data: bytes,
    *,
    source_id: str = "",
    altloc_id: str | None = None,
) -> StructureIngestResult:
    """Parse one PDB object, requiring ``altloc_id`` for alternate rows."""

    if type(data) is not bytes:
        raise TypeError("PDB input must be bytes")
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    if altloc_id is not None and type(altloc_id) is not str:
        raise TypeError("altloc_id must be a string or None")
    if altloc_id is not None and (
        len(altloc_id) != 1
        or not altloc_id.isascii()
        or altloc_id.isspace()
        or not altloc_id.isprintable()
    ):
        raise _error(
            "pdb",
            "invalid_altloc_id",
            "PDB altloc_id must be one printable non-whitespace ASCII character",
        )
    if not data:
        raise _error("pdb", "empty_input", "PDB input is empty")
    if len(data) > _MAX_PDB_INPUT_BYTES:
        raise _error(
            "pdb",
            "input_too_large",
            f"PDB input exceeds the {_MAX_PDB_INPUT_BYTES}-byte safety limit",
        )
    if any(
        (byte < 0x20 and byte not in {0x0A, 0x0D}) or byte == 0x7F
        for byte in data
    ):
        raise _error(
            "pdb",
            "invalid_text",
            "PDB input may contain only printable ASCII plus CR/LF line separators",
        )
    line_separator_count = data.count(b"\n") + data.count(b"\r")
    if line_separator_count + 1 > _MAX_PDB_LINE_COUNT:
        raise _error(
            "pdb",
            "too_many_lines",
            f"PDB input may contain at most {_MAX_PDB_LINE_COUNT} physical lines",
        )
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise _error("pdb", "invalid_ascii", "fixed-column PDB input must be ASCII") from exc
    lines = text.splitlines()
    explicit_models = any(line[0:6].strip().upper() == "MODEL" for line in lines)
    models: list[list[_SourceAtom]] = []
    model_ids: list[int] = []
    model_ter_records: list[list[_PdbTerRecord]] = []
    seen_model_ids: set[int] = set()
    current_model: list[_SourceAtom] | None = None
    current_model_id: int | None = None
    current_model_ters: list[_PdbTerRecord] | None = None
    implicit_model: list[_SourceAtom] = []
    implicit_model_ters: list[_PdbTerRecord] = []
    current_terminated_chains: set[str] = set()
    last_atom: _SourceAtom | None = None
    directed_conect: Counter[tuple[int, int]] = Counter()
    cell: UnitCell | None = None
    cryst1_metadata: dict[str, Any] | None = None
    end_seen = False
    atom_row_count = 0
    coordinate_records_started = False
    missingness_remark_lines: list[_PdbMissingnessRemarkLine] = []

    for line_number, line in enumerate(lines, start=1):
        if end_seen:
            if line.strip():
                raise _error("pdb", "content_after_end", "nonblank content after END", line_number=line_number)
            continue
        if not line.strip():
            continue
        record = line[0:6].strip().upper()
        if record == "REMARK":
            if len(line) < 10 or len(line) > 80:
                raise _error(
                    "pdb",
                    "invalid_remark_record",
                    "REMARK record must provide columns 1-10 and fit within 80 columns",
                    line_number=line_number,
                )
            padded = line.ljust(80)
            if (
                padded[0:6] != "REMARK"
                or padded[6] != " "
                or padded[10] != " "
                or _INTEGER_RE.fullmatch(padded[7:10].strip()) is None
            ):
                raise _error(
                    "pdb",
                    "invalid_remark_record",
                    "REMARK number must occupy columns 8-10 with blank separators",
                    line_number=line_number,
                )
            remark_number = int(padded[7:10], 10)
            if remark_number not in {465, 470}:
                raise _error(
                    "pdb",
                    "unsupported_record",
                    f"PDB REMARK {remark_number} is not supported",
                    line_number=line_number,
                )
            if coordinate_records_started:
                raise _error(
                    "pdb",
                    "misplaced_missingness_remark",
                    "REMARK 465/470 must precede coordinate MODEL/ATOM records",
                    line_number=line_number,
                )
            missingness_remark_lines.append(
                _PdbMissingnessRemarkLine(
                    remark_number=remark_number,
                    line_number=line_number,
                    raw_line=line,
                )
            )
            if len(missingness_remark_lines) > _MAX_PDB_MISSINGNESS_REMARK_LINES:
                raise _error(
                    "pdb",
                    "missingness_remark_line_limit_exceeded",
                    "REMARK 465/470 lines exceed the fixed safety limit",
                    line_number=line_number,
                )
            last_atom = None
        elif record == "MODEL":
            coordinate_records_started = True
            if not explicit_models or current_model is not None:
                raise _error("pdb", "invalid_model_block", "nested MODEL records are not allowed", line_number=line_number)
            if len(line) < 14 or len(line) > 80:
                raise _error("pdb", "invalid_model_line", "MODEL line must occupy 14 through 80 columns", line_number=line_number)
            padded = line.ljust(80)
            if padded[0:6] != "MODEL " or padded[6:10].strip() or padded[14:80].strip():
                raise _error(
                    "pdb",
                    "invalid_model_line",
                    "MODEL identifier must occupy columns 11-14 and all other trailing columns must be blank",
                    line_number=line_number,
                )
            model_id = _strict_int(
                padded[10:14], source_format="pdb", code="invalid_model_id", field="model_id", line_number=line_number
            )
            if model_id < 1 or model_id in seen_model_ids:
                raise _error("pdb", "invalid_model_id", "model identifiers must be positive and unique", line_number=line_number)
            seen_model_ids.add(model_id)
            current_model = []
            current_model_id = model_id
            current_model_ters = []
            current_terminated_chains = set()
            last_atom = None
        elif record == "ENDMDL":
            if len(line) > 80 or line[0:6] != "ENDMDL" or line[6:].strip():
                raise _error("pdb", "invalid_endmdl_line", "ENDMDL trailing columns must be blank", line_number=line_number)
            if current_model is None or current_model_id is None:
                raise _error("pdb", "invalid_model_block", "ENDMDL without MODEL", line_number=line_number)
            if not current_model:
                raise _error("pdb", "empty_model", "MODEL contains no atoms", line_number=line_number)
            models.append(current_model)
            model_ids.append(current_model_id)
            assert current_model_ters is not None
            model_ter_records.append(current_model_ters)
            current_model = None
            current_model_id = None
            current_model_ters = None
            last_atom = None
        elif record in {"ATOM", "HETATM"}:
            coordinate_records_started = True
            if explicit_models and current_model is None:
                raise _error("pdb", "atom_outside_model", "ATOM/HETATM must be inside MODEL/ENDMDL", line_number=line_number)
            atom = _parse_pdb_atom(line, line_number=line_number)
            atom_row_count += 1
            if atom_row_count > _MAX_PDB_ATOM_ROWS:
                raise _error(
                    "pdb",
                    "too_many_atom_rows",
                    f"PDB input may contain at most {_MAX_PDB_ATOM_ROWS} ATOM/HETATM rows",
                    line_number=line_number,
                )
            if atom.chain_id in current_terminated_chains:
                raise _error("pdb", "chain_reopened_after_ter", f"chain {atom.chain_id!r} reappears after TER", line_number=line_number)
            target = current_model if explicit_models else implicit_model
            assert target is not None
            target.append(atom)
            last_atom = atom
        elif record == "TER":
            if explicit_models and current_model is None:
                raise _error("pdb", "invalid_ter", "TER must be inside a MODEL/ENDMDL block", line_number=line_number)
            if last_atom is None:
                raise _error("pdb", "invalid_ter", "TER appears before any atom in the model", line_number=line_number)
            target = current_model if explicit_models else implicit_model
            assert target is not None
            ter_record = _parse_pdb_ter(
                line,
                line_number=line_number,
                preceding_atom=last_atom,
                after_atom_index=len(target) - 1,
            )
            target_ters = current_model_ters if explicit_models else implicit_model_ters
            assert target_ters is not None
            target_ters.append(ter_record)
            current_terminated_chains.add(last_atom.chain_id)
            last_atom = None
        elif record == "CONECT":
            if current_model is not None:
                raise _error("pdb", "conect_inside_model", "CONECT must be outside MODEL blocks", line_number=line_number)
            source, targets = _parse_conect(line, line_number=line_number)
            for target in targets:
                directed_conect[(source, target)] += 1
            last_atom = None
        elif record == "CRYST1":
            if cell is not None:
                raise _error("pdb", "duplicate_cryst1", "only one CRYST1 record is supported", line_number=line_number)
            cell, cryst1_metadata = _parse_cryst1(line, line_number=line_number)
            last_atom = None
        elif record == "END":
            if len(line) > 80 or line[0:3] != "END" or line[3:].strip():
                raise _error("pdb", "invalid_end_line", "END trailing columns must be blank", line_number=line_number)
            if current_model is not None:
                raise _error("pdb", "missing_endmdl", "END encountered before ENDMDL", line_number=line_number)
            end_seen = True
        else:
            raise _error("pdb", "unsupported_record", f"PDB record {record!r} is not supported", line_number=line_number)

    if current_model is not None:
        raise _error("pdb", "missing_endmdl", "final MODEL is missing ENDMDL")
    if not end_seen:
        raise _error("pdb", "missing_end", "PDB input is missing the required END record")
    if explicit_models:
        if not models:
            raise _error("pdb", "empty_atom_site", "no complete MODEL blocks were found")
    else:
        models = [implicit_model]
        model_ids = [1]
        model_ter_records = [implicit_model_ters]

    raw_models = [list(model) for model in models]
    for model_id, model in zip(model_ids, raw_models):
        serials = [atom.serial for atom in model]
        if len(set(serials)) != len(serials):
            raise _error(
                "pdb",
                "duplicate_atom_serial",
                f"model {model_id} source atom serials must be unique before altloc selection",
            )
    (
        missing_residue_claims,
        missing_atom_claims,
        missingness_evidence_present,
        missingness_blockers,
        missingness_metadata,
    ) = _parse_pdb_missingness_remarks(
        missingness_remark_lines,
        raw_models=raw_models,
        model_ids=model_ids,
        explicit_models=explicit_models,
    )
    models, altloc_summary = _select_explicit_altloc(
        raw_models,
        model_ids,
        source_format="pdb",
        altloc_id=altloc_id,
    )
    if altloc_summary.status == "explicit_id_selected":
        model_ter_records = _remap_pdb_ter_records_after_altloc_selection(
            raw_models,
            models,
            model_ter_records,
        )

    reference_ter_layout = tuple(record.layout_identity() for record in model_ter_records[0])
    for model_index, records in enumerate(model_ter_records[1:], start=1):
        layout = tuple(record.layout_identity() for record in records)
        if layout != reference_ter_layout:
            raise _error(
                "pdb",
                "model_ter_layout_mismatch",
                f"model {model_ids[model_index]} TER placement does not match the first model",
            )

    alternate_serials = {
        atom.serial for atom in raw_models[0] if atom.altloc
    }
    if any(
        source in alternate_serials or target in alternate_serials
        for source, target in directed_conect
    ):
        raise _error(
            "pdb",
            "altloc_conect_not_supported",
            "CONECT records that reference alternate-location serials are not supported",
        )
    first_model_serials = {atom.serial for atom in models[0]}
    source_bonds: list[_SourceBond] = []
    processed_pairs: set[tuple[int, int]] = set()
    for directed_pair in sorted(directed_conect):
        source, target = directed_pair
        pair = tuple(sorted((source, target)))
        if pair in processed_pairs:
            continue
        processed_pairs.add(pair)
        if source not in first_model_serials or target not in first_model_serials:
            raise _error("pdb", "conect_atom_out_of_range", f"CONECT pair {pair} references an unknown serial")
        forward_multiplicity = directed_conect[(pair[0], pair[1])]
        reverse_multiplicity = directed_conect[(pair[1], pair[0])]
        if (
            pair[0] != pair[1]
            and forward_multiplicity
            and reverse_multiplicity
            and forward_multiplicity != reverse_multiplicity
        ):
            raise _error(
                "pdb",
                "contradictory_conect_multiplicity",
                f"CONECT pair {pair} has conflicting directional multiplicities "
                f"{forward_multiplicity} and {reverse_multiplicity}",
            )
        multiplicity = forward_multiplicity or reverse_multiplicity
        if multiplicity < 1 or multiplicity > 3:
            raise _error("pdb", "unsupported_conect_multiplicity", f"CONECT pair {pair} has multiplicity {multiplicity}")
    if directed_conect:
        raise _error(
            "pdb",
            "unsupported_contextual_conect_semantics",
            "CONECT requires residue templates and explicit covalent or coordination bond-kind context",
        )
    ter_count = sum(len(records) for records in model_ter_records)
    ter_records_by_model = [
        {
            "model_id": model_id,
            "records": [record.to_dict() for record in records],
        }
        for model_id, records in zip(model_ids, model_ter_records)
    ]
    extra_blockers: list[str] = list(missingness_blockers)
    if cell is not None:
        extra_blockers.append("crystallographic_cell_not_simulation_box")
        space_group = "" if cryst1_metadata is None else str(cryst1_metadata.get("space_group", ""))
        if space_group.replace(" ", "").upper() != "P1":
            extra_blockers.append("crystallographic_symmetry_not_expanded")
    assembly_summary = _unapplied_assembly_summary(
        status="not_supported_for_pdb",
        coordinate_scope="deposited_coordinates",
        source_topology_atom_count=len(models[0]),
    )
    return _build_system(
        source_format="pdb",
        parser_version=PDB_PARSER_VERSION,
        data=data,
        source_id=source_id,
        suggested_system_id="",
        models=models,
        model_ids=model_ids,
        altloc_summary=altloc_summary,
        assembly_summary=assembly_summary,
        source_bonds=source_bonds,
        cell=cell,
        format_metadata={
            "pdb": {
                "ter_count": ter_count,
                "ter_records_by_model": ter_records_by_model,
                "cryst1": cryst1_metadata,
                "altloc_selection": altloc_summary.ledger,
                "source_missingness": missingness_metadata,
                "resource_usage": {
                    "input_bytes": len(data),
                    "atom_rows": atom_row_count,
                    "physical_line_upper_bound": line_separator_count + 1,
                    "missingness_remark_lines": len(missingness_remark_lines),
                    "missing_residue_claims": len(missing_residue_claims),
                    "missing_atom_claims": len(missing_atom_claims),
                    "total_missingness_claims": (
                        len(missing_residue_claims) + len(missing_atom_claims)
                    ),
                },
                "resource_limits": {
                    "input_bytes": _MAX_PDB_INPUT_BYTES,
                    "atom_rows": _MAX_PDB_ATOM_ROWS,
                    "physical_lines": _MAX_PDB_LINE_COUNT,
                    "missingness_remark_lines": _MAX_PDB_MISSINGNESS_REMARK_LINES,
                    "missing_residue_claims": MAX_MISSING_RESIDUE_CLAIMS,
                    "missing_atom_claims": MAX_MISSING_ATOM_CLAIMS,
                    "total_missingness_claims": MAX_TOTAL_MISSINGNESS_CLAIMS,
                    "missingness_metadata_projected_claims": (
                        _MAX_PDB_MISSINGNESS_PROJECTED_CLAIMS
                    ),
                },
            }
        },
        operations=(
            "parse_strict_fixed_column_pdb",
            *(
                ("preserve_source_reported_missingness_without_completion/v1",)
                if missingness_evidence_present
                else ()
            ),
            "preserve_source_atom_order",
            *(
                ("select_explicit_altloc_id/v1",)
                if altloc_summary.status == "explicit_id_selected"
                else ()
            ),
        ),
        missing_residue_claims=missing_residue_claims,
        missing_atom_claims=missing_atom_claims,
        missingness_evidence_present=missingness_evidence_present,
        extra_blockers=extra_blockers,
    )


_MMCIF_TOPOLOGY_CATEGORIES = frozenset(
    {
        "_struct_conn",
        "_chem_comp_atom",
        "_chem_comp_bond",
        "_chem_link_bond",
        "_geom_bond",
        "_pdbx_entity_branch_link",
    }
)
_MMCIF_CONTEXT_CATEGORIES = frozenset(
    {
        "_pdbx_entity_nonpoly",
        "_pdbx_ion_info",
        "_pdbx_nonpoly_scheme",
        "_pdbx_struct_mod_residue",
    }
)
_MMCIF_CONTEXT_CATEGORY_PREFIXES = (
    "_chem_link",
    "_chem_comp",
    "_entity_link",
    "_entity_poly",
    "_pdbx_branch_scheme",
    "_pdbx_chem_comp",
    "_pdbx_entity_branch",
    "_pdbx_entity_func",
    "_pdbx_entity_nonpoly",
    "_pdbx_connect",
    "_pdbx_ion",
    "_pdbx_linked_entity",
    "_pdbx_modification",
    "_pdbx_nonpoly",
    "_pdbx_poly_seq",
    "_pdbx_solvent",
    "_pdbx_struct_mod",
)
_MMCIF_REVIEWED_DROPPABLE_METADATA_CATEGORIES = frozenset(
    {
        "_audit_author",
        "_entry",
    }
)


def _is_unsupported_mmcif_context_category(category: str) -> bool:
    return category in _MMCIF_CONTEXT_CATEGORIES or category.startswith(
        _MMCIF_CONTEXT_CATEGORY_PREFIXES
    )


_MMCIF_ASSEMBLY_CATEGORIES = frozenset(
    {
        "_pdbx_struct_assembly",
        "_pdbx_struct_assembly_gen",
        "_pdbx_struct_oper_list",
    }
)
_MMCIF_MISSINGNESS_CATEGORIES = frozenset(
    {
        "_pdbx_unobs_or_zero_occ_residues",
        "_pdbx_unobs_or_zero_occ_atoms",
    }
)
_MMCIF_SYMMETRY_OPERATION_CATEGORIES = frozenset(
    {"_space_group_symop", "_symmetry_equiv"}
)
_MMCIF_PARTIALLY_INTERPRETED_CATEGORIES = frozenset(
    {"_cell", "_entity", "_struct_asym", "_space_group", "_symmetry"}
)
_MMCIF_ATOM_SITE_ESD_TAGS = frozenset(
    {
        "_atom_site.cartn_x_esd",
        "_atom_site.cartn_y_esd",
        "_atom_site.cartn_z_esd",
        "_atom_site.occupancy_esd",
        "_atom_site.b_iso_or_equiv_esd",
    }
)
_MMCIF_ENTITY_TYPES = {
    "polymer": "polymer",
    "non-polymer": "non_polymer",
    "water": "water",
    "branched": "branched",
    "macrolide": "macrolide",
}
def _cif_token_is_missing(token: CifToken | None) -> bool:
    return token is None or (not token.quoted and token.value in {".", "?"})


def _cif_token_value(row: dict[str, CifToken], tag: str) -> CifToken | None:
    token = row.get(tag.lower())
    return None if _cif_token_is_missing(token) else token


def _required_cif_token(
    row: dict[str, CifToken],
    tag: str,
    *,
    code: str,
    description: str,
    line_number: int,
) -> CifToken:
    token = _cif_token_value(row, tag)
    if token is None:
        raise _error("mmcif", code, f"{description} is required", line_number=line_number)
    return token


def _strict_cif_int(token: CifToken, *, code: str, field: str) -> int:
    if token.quoted or token.multiline:
        raise _error(
            "mmcif",
            code,
            f"{field} must be an unquoted CIF integer",
            line_number=token.line_number,
        )
    if _INTEGER_RE.fullmatch(token.value) is None:
        raise _error(
            "mmcif",
            code,
            f"{field} is not a decimal integer: {token.value!r}",
            line_number=token.line_number,
        )
    significant_digits = token.value.lstrip("+-").lstrip("0") or "0"
    if len(significant_digits) > 16:
        raise _error(
            "mmcif",
            code,
            f"{field} exceeds the interoperable JSON integer range",
            line_number=token.line_number,
        )
    magnitude = int(significant_digits, 10)
    value = -magnitude if token.value.startswith("-") else magnitude
    if abs(value) > _MAX_CANONICAL_JSON_INTEGER:
        raise _error(
            "mmcif",
            code,
            f"{field} exceeds the interoperable JSON integer range",
            line_number=token.line_number,
        )
    return value


def _strict_cif_float(token: CifToken, *, code: str, field: str) -> tuple[float, bool]:
    if token.quoted or token.multiline:
        raise _error(
            "mmcif",
            code,
            f"{field} must be an unquoted CIF number",
            line_number=token.line_number,
        )
    match = _CIF_NUMBER_RE.fullmatch(token.value)
    if match is None:
        raise _error(
            "mmcif",
            code,
            f"{field} is not a CIF number: {token.value!r}",
            line_number=token.line_number,
        )
    number = float(match.group("mantissa") + (match.group("exponent") or ""))
    if not math.isfinite(number):
        raise _error("mmcif", code, f"{field} must be finite", line_number=token.line_number)
    return number, match.group("uncertainty") is not None


def _cif_token_payload(token: CifToken) -> dict[str, Any]:
    return {
        "value": token.value,
        "quoted": token.quoted,
        "multiline": token.multiline,
    }


def _preflight_mmcif_assembly_resources(block: CifBlock) -> None:
    """Bound assembly metadata before any nested preservation projection."""

    category_limits = {
        "_pdbx_struct_assembly": (
            _MAX_MMCIF_ASSEMBLY_DEFINITION_ROWS,
            "assembly_definition_limit_exceeded",
            "assembly definition list",
        ),
        "_pdbx_struct_assembly_gen": (
            _MAX_MMCIF_ASSEMBLY_GENERATOR_ROWS,
            "assembly_generator_limit_exceeded",
            "assembly generator list",
        ),
        "_pdbx_struct_oper_list": (
            _MAX_MMCIF_ASSEMBLY_OPERATOR_ROWS,
            "assembly_operator_limit_exceeded",
            "assembly operator list",
        ),
    }
    for category, (limit, code, description) in category_limits.items():
        scalar_tokens = [
            token
            for tag, token in block.scalar_values.items()
            if tag.split(".", 1)[0] == category
        ]
        row_count = 1 if scalar_tokens else 0
        line_number = scalar_tokens[0].line_number if scalar_tokens else None
        for loop in block.loops:
            if category not in loop.categories:
                continue
            if line_number is None:
                line_number = loop.line_number
            row_count += len(loop.rows)
            if row_count > limit:
                raise _error(
                    "mmcif",
                    code,
                    f"{description} exceeds the fixed row limit",
                    line_number=line_number,
                )

    for tag, character_limit, code, description in (
        (
            "_pdbx_struct_assembly_gen.oper_expression",
            _MAX_MMCIF_OPER_EXPRESSION_CHARS,
            "assembly_expression_limit_exceeded",
            "assembly operation expression",
        ),
        (
            "_pdbx_struct_assembly_gen.asym_id_list",
            _MAX_MMCIF_ASSEMBLY_ASYM_ID_LIST_CHARS,
            "assembly_asym_id_list_limit_exceeded",
            "assembly asym_id_list",
        ),
    ):
        tokens: list[CifToken] = []
        scalar_token = block.scalar_values.get(tag)
        if scalar_token is not None:
            tokens.append(scalar_token)
        for loop in block.loops:
            if tag not in loop.tags:
                continue
            tag_index = loop.tags.index(tag)
            tokens.extend(row[tag_index] for row in loop.rows)
        for token in tokens:
            too_many_asym_ids = (
                tag.endswith(".asym_id_list")
                and token.value.count(",") + 1
                > _MAX_MMCIF_ASSEMBLY_ASYM_IDS_PER_GENERATOR
            )
            if len(token.value) > character_limit or too_many_asym_ids:
                raise _error(
                    "mmcif",
                    code,
                    f"{description} exceeds the fixed preflight limit",
                    line_number=token.line_number,
                )


def _preflight_mmcif_missingness_resources(block: CifBlock) -> dict[str, int]:
    """Bound source missingness categories before preservation projection."""

    total_row_count = 0
    total_item_count = 0
    total_utf8_bytes = 0
    for category, limit, code in (
        (
            "_pdbx_unobs_or_zero_occ_residues",
            MAX_MISSING_RESIDUE_CLAIMS,
            "missing_residue_evidence_limit_exceeded",
        ),
        (
            "_pdbx_unobs_or_zero_occ_atoms",
            MAX_MISSING_ATOM_CLAIMS,
            "missing_atom_evidence_limit_exceeded",
        ),
    ):
        category_tokens = [
            token
            for tag, token in block.scalar_values.items()
            if tag.split(".", 1)[0] == category
        ]
        row_count = 1 if category_tokens else 0
        line_number = category_tokens[0].line_number if category_tokens else None
        for loop in block.loops:
            if category not in loop.categories:
                continue
            if line_number is None:
                line_number = loop.line_number
            row_count += len(loop.rows)
            tag_indexes = [
                index
                for index, tag in enumerate(loop.tags)
                if tag.split(".", 1)[0] == category
            ]
            category_tokens.extend(
                row[index] for row in loop.rows for index in tag_indexes
            )
        if row_count > limit:
            raise _error(
                "mmcif",
                code,
                f"{category} exceeds the fixed {limit}-row limit",
                line_number=line_number,
            )
        for token in category_tokens:
            if len(token.value) > _MAX_MMCIF_MISSINGNESS_TOKEN_CHARS:
                raise _error(
                    "mmcif",
                    "missingness_token_limit_exceeded",
                    "source missingness token exceeds the fixed character limit",
                    line_number=token.line_number,
                )
            total_utf8_bytes += len(token.value.encode("utf-8"))
        total_item_count += len(category_tokens)
        if total_item_count > _MAX_MMCIF_MISSINGNESS_PRESERVED_ITEMS:
            raise _error(
                "mmcif",
                "missingness_preservation_item_limit_exceeded",
                "source missingness items exceed the fixed preservation limit",
                line_number=line_number,
            )
        if total_utf8_bytes > _MAX_MMCIF_MISSINGNESS_PRESERVED_UTF8_BYTES:
            raise _error(
                "mmcif",
                "missingness_preservation_byte_limit_exceeded",
                "source missingness values exceed the fixed UTF-8 preservation limit",
                line_number=line_number,
            )
        total_row_count += row_count
        if total_row_count > MAX_TOTAL_MISSINGNESS_CLAIMS:
            raise _error(
                "mmcif",
                "combined_missingness_evidence_limit_exceeded",
                "combined source missingness rows exceed the fixed limit",
                line_number=line_number,
            )
    return {
        "row_count": total_row_count,
        "preserved_item_count": total_item_count,
        "preserved_value_utf8_bytes": total_utf8_bytes,
    }


def _mmcif_category_policy(category: str) -> str:
    if category == "_atom_site":
        return "interpreted_with_source_values_preserved"
    if category in _MMCIF_PARTIALLY_INTERPRETED_CATEGORIES:
        return "partially_interpreted"
    if category in _MMCIF_ASSEMBLY_CATEGORIES:
        return "deferred_biological_assembly"
    if category in _MMCIF_MISSINGNESS_CATEGORIES:
        return "source_reported_missingness_preserved_only"
    if category in _MMCIF_SYMMETRY_OPERATION_CATEGORIES:
        return "deferred_symmetry_expansion"
    return "uninterpreted_metadata"


def _mmcif_preserved_category_payloads(block: CifBlock) -> list[dict[str, Any]]:
    """Preserve values needed for later completion of partially handled categories."""

    preserved_categories = (
        _MMCIF_PARTIALLY_INTERPRETED_CATEGORIES
        | _MMCIF_ASSEMBLY_CATEGORIES
        | _MMCIF_MISSINGNESS_CATEGORIES
        | _MMCIF_SYMMETRY_OPERATION_CATEGORIES
    )
    payloads: list[dict[str, Any]] = []
    for category in block.categories:
        if category not in preserved_categories:
            continue
        scalar_items = [
            {"tag": tag, "value": _cif_token_payload(token)}
            for tag, token in block.scalar_values.items()
            if tag.split(".", 1)[0] == category
        ]
        loops: list[dict[str, Any]] = []
        for loop_index, loop in enumerate(block.loops):
            tag_indexes = [
                index
                for index, tag in enumerate(loop.tags)
                if tag.split(".", 1)[0] == category
            ]
            if not tag_indexes:
                continue
            loops.append(
                {
                    "source_loop_index": loop_index,
                    "tags": [loop.tags[index] for index in tag_indexes],
                    "rows": [
                        [_cif_token_payload(row[index]) for index in tag_indexes]
                        for row in loop.rows
                    ],
                }
            )
        payloads.append(
            {
                "category": category,
                "policy": _mmcif_category_policy(category),
                "scalar_items": scalar_items,
                "loops": loops,
            }
        )
    return payloads


def _category_rows(block: CifBlock, category: str) -> list[dict[str, CifToken]]:
    normalized = category.lower()
    scalar_items = {
        tag: token
        for tag, token in block.scalar_values.items()
        if tag.split(".", 1)[0] == normalized
    }
    category_loops = [loop for loop in block.loops if normalized in loop.categories]
    mixed_loop = next(
        (loop for loop in category_loops if loop.categories != (normalized,)),
        None,
    )
    if mixed_loop is not None:
        raise _error(
            "mmcif",
            "mixed_interpreted_category_loop",
            f"{normalized} must not share a loop with another category",
            line_number=mixed_loop.line_number,
        )
    if scalar_items and category_loops:
        line_number = min(token.line_number for token in scalar_items.values())
        raise _error(
            "mmcif",
            "mixed_category_representation",
            f"{normalized} cannot be split between scalar items and a loop",
            line_number=line_number,
        )
    if len(category_loops) > 1:
        raise _error(
            "mmcif",
            "multiple_category_loops",
            f"{normalized} must occur in at most one loop",
            line_number=category_loops[1].line_number,
        )
    if scalar_items:
        return [scalar_items]
    if not category_loops:
        return []
    loop = category_loops[0]
    return [dict(zip(loop.tags, tokens)) for tokens in loop.rows]


def _parse_mmcif_source_missingness(
    block: CifBlock,
    *,
    model_ids: list[int],
    raw_models: list[list[_SourceAtom]],
) -> tuple[
    tuple[SourceReportedMissingResidueClaim, ...],
    tuple[SourceReportedMissingAtomClaim, ...],
    bool,
    bool,
    tuple[str, ...],
    dict[str, Any],
]:
    """Preserve explicit unobserved claims without treating zero occupancy as missing."""

    residue_category = "_pdbx_unobs_or_zero_occ_residues"
    atom_category = "_pdbx_unobs_or_zero_occ_atoms"
    residue_rows = _category_rows(block, residue_category)
    atom_rows = _category_rows(block, atom_category)
    evidence_present = bool(residue_rows or atom_rows)
    if not evidence_present:
        return (), (), False, False, (), {
            "interpretation_policy": (
                "documented_items_preserved_without_full_dictionary_validation/v1"
            ),
            "dictionary_validation_status": "not_assessed",
            "residue_row_count": 0,
            "atom_row_count": 0,
            "unobserved_residue_claim_count": 0,
            "unobserved_atom_claim_count": 0,
            "zero_occupancy_residue_row_count": 0,
            "zero_occupancy_atom_row_count": 0,
            "extension_item_count": 0,
        }
    known_residue_tags = {
        f"{residue_category}.{suffix}"
        for suffix in (
            "id",
            "polymer_flag",
            "occupancy_flag",
            "pdb_model_num",
            "auth_asym_id",
            "auth_comp_id",
            "auth_seq_id",
            "pdb_ins_code",
            "label_asym_id",
            "label_comp_id",
            "label_seq_id",
        )
    }
    known_atom_tags = {
        f"{atom_category}.{suffix}"
        for suffix in (
            "id",
            "polymer_flag",
            "occupancy_flag",
            "pdb_model_num",
            "auth_asym_id",
            "auth_atom_id",
            "auth_comp_id",
            "auth_seq_id",
            "pdb_ins_code",
            "label_alt_id",
            "label_asym_id",
            "label_atom_id",
            "label_comp_id",
            "label_seq_id",
        )
    }
    residue_claims: list[SourceReportedMissingResidueClaim] = []
    atom_claims: list[SourceReportedMissingAtomClaim] = []
    blockers: list[str] = []
    partial = False
    model_id_set = set(model_ids)
    zero_occupancy_residue_rows = 0
    zero_occupancy_atom_rows = 0
    extension_item_count = 0
    seen_residue_source_ids: set[int] = set()
    seen_atom_source_ids: set[int] = set()
    residue_semantic_keys: set[tuple[str, ...]] = set()
    atom_semantic_keys: set[tuple[str, ...]] = set()
    coordinate_checks: list[_MmcifMissingnessCoordinateCheck] = []

    def queue_coordinate_consistency_check(
        *,
        row: dict[str, CifToken],
        occupancy_flag: int,
        model_id: str,
        chain_id: str,
        residue_id: str,
        residue_name: str,
        insertion_code: str,
        identity_basis: str | None,
        atom_name: str | None = None,
        altloc_id: str = "",
    ) -> None:
        nonlocal partial

        line_number = next(iter(row.values())).line_number
        if identity_basis is None:
            partial = True
            blockers.append(
                "source_missingness_coordinate_consistency_partially_assessed"
            )
            return
        coordinate_checks.append(
            _MmcifMissingnessCoordinateCheck(
                line_number=line_number,
                occupancy_flag=occupancy_flag,
                model_id=int(model_id, 10),
                chain_id=chain_id,
                residue_id=residue_id,
                residue_name=residue_name,
                insertion_code=insertion_code,
                identity_basis=identity_basis,
                atom_name=atom_name,
                altloc_id=altloc_id,
            )
        )

    def parse_common(
        row: dict[str, CifToken],
        *,
        category: str,
        seen_source_ids: set[int],
    ) -> tuple[int, int, str, str, str, str, str, str, dict[str, Any]]:
        nonlocal partial

        line_number = next(iter(row.values())).line_number
        source_id_token = _required_cif_token(
            row,
            f"{category}.id",
            code="incomplete_missingness_evidence",
            description=f"{category}.id",
            line_number=line_number,
        )
        source_row_id = _strict_cif_int(
            source_id_token,
            code="invalid_missingness_source_id",
            field=f"{category}.id",
        )
        if source_row_id < 1 or source_row_id in seen_source_ids:
            raise _error(
                "mmcif",
                "duplicate_or_invalid_missingness_source_id",
                f"{category}.id must be positive and unique",
                line_number=line_number,
            )
        seen_source_ids.add(source_row_id)
        polymer_token = _required_cif_token(
            row,
            f"{category}.polymer_flag",
            code="incomplete_missingness_evidence",
            description=f"{category}.polymer_flag",
            line_number=line_number,
        )
        polymer_flag = polymer_token.value.upper()
        if polymer_flag not in {"Y", "N"}:
            raise _error(
                "mmcif",
                "invalid_missingness_polymer_flag",
                "missingness polymer_flag must be Y or N",
                line_number=polymer_token.line_number,
            )
        occupancy_token = _required_cif_token(
            row,
            f"{category}.occupancy_flag",
            code="incomplete_missingness_evidence",
            description=f"{category}.occupancy_flag",
            line_number=line_number,
        )
        occupancy_flag = _strict_cif_int(
            occupancy_token,
            code="invalid_missingness_occupancy_flag",
            field=f"{category}.occupancy_flag",
        )
        if occupancy_flag not in {0, 1}:
            raise _error(
                "mmcif",
                "invalid_missingness_occupancy_flag",
                "missingness occupancy_flag must be 0 or 1",
                line_number=occupancy_token.line_number,
            )
        model_token = _required_cif_token(
            row,
            f"{category}.pdb_model_num",
            code="incomplete_missingness_evidence",
            description=f"{category}.PDB_model_num",
            line_number=line_number,
        )
        model_id = _strict_cif_int(
            model_token,
            code="invalid_missingness_model_id",
            field=f"{category}.PDB_model_num",
        )
        if model_id not in model_id_set:
            raise _error(
                "mmcif",
                "unknown_missingness_model_id",
                f"missingness row references model {model_id} absent from atom_site",
                line_number=model_token.line_number,
            )
        auth_values: dict[str, str] = {}
        for field_name in ("asym_id", "comp_id", "seq_id"):
            token = _required_cif_token(
                row,
                f"{category}.auth_{field_name}",
                code="incomplete_missingness_evidence",
                description=f"{category}.auth_{field_name}",
                line_number=line_number,
            )
            if not token.value:
                raise _error(
                    "mmcif",
                    "incomplete_missingness_evidence",
                    f"{category}.auth_{field_name} must be nonempty",
                    line_number=token.line_number,
                )
            auth_values[field_name] = token.value
        label_values = {
            field_name: (
                ""
                if _cif_token_value(row, f"{category}.label_{field_name}") is None
                else row[f"{category}.label_{field_name}"].value
            )
            for field_name in ("asym_id", "comp_id", "seq_id")
        }
        label_present_count = sum(bool(value) for value in label_values.values())
        identity_basis = "label" if label_present_count == 3 else "auth"
        if label_present_count not in {0, 3}:
            partial = True
            blockers.append("partial_label_identity_in_missingness_evidence")
        if identity_basis == "label":
            label_seq_token = row[f"{category}.label_seq_id"]
            label_seq_id = _strict_cif_int(
                label_seq_token,
                code="invalid_missingness_label_seq_id",
                field=f"{category}.label_seq_id",
            )
            if label_seq_id < 1:
                raise _error(
                    "mmcif",
                    "invalid_missingness_label_seq_id",
                    "missingness label_seq_id pointer must be positive",
                    line_number=label_seq_token.line_number,
                )
            label_values["seq_id"] = str(label_seq_id)
        selected = label_values if identity_basis == "label" else auth_values
        insertion_token = _cif_token_value(row, f"{category}.pdb_ins_code")
        insertion_code = "" if insertion_token is None else insertion_token.value
        raw_payload = {
            "source_row_id": source_row_id,
            "source_line_number": line_number,
            "polymer_flag": polymer_flag,
            "occupancy_flag": occupancy_flag,
            "identity_basis": identity_basis,
            "tokens": {
                tag: _cif_token_payload(token) for tag, token in sorted(row.items())
            },
        }
        return (
            source_row_id,
            occupancy_flag,
            str(model_id),
            selected["asym_id"],
            selected["seq_id"],
            selected["comp_id"],
            insertion_code,
            identity_basis,
            raw_payload,
        )

    for row_index, row in enumerate(residue_rows, start=1):
        extension_tags = set(row) - known_residue_tags
        if extension_tags:
            partial = True
            extension_item_count += len(extension_tags)
            blockers.append("missingness_extension_items_uninterpreted")
        (
            _,
            occupancy_flag,
            model_id,
            chain_id,
            residue_id,
            residue_name,
            insertion_code,
            identity_basis,
            raw_payload,
        ) = parse_common(
            row,
            category=residue_category,
            seen_source_ids=seen_residue_source_ids,
        )
        queue_coordinate_consistency_check(
            row=row,
            occupancy_flag=occupancy_flag,
            model_id=model_id,
            chain_id=chain_id,
            residue_id=residue_id,
            residue_name=residue_name,
            insertion_code=insertion_code,
            identity_basis=identity_basis,
        )
        if occupancy_flag == 0:
            zero_occupancy_residue_rows += 1
            continue
        semantic_key = (
            model_id,
            chain_id,
            residue_id,
            residue_name,
            insertion_code,
        )
        if semantic_key in residue_semantic_keys:
            partial = True
            blockers.append("duplicate_missing_residue_claims_preserved")
        try:
            claim = SourceReportedMissingResidueClaim(
                source_ordinal=row_index,
                source_category=residue_category,
                source_model_id=model_id,
                source_chain_id=chain_id,
                source_residue_id=residue_id,
                source_residue_name=residue_name,
                source_insertion_code=insertion_code,
                raw_payload=raw_payload,
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise _error(
                "mmcif",
                "invalid_missingness_evidence",
                "source missing-residue row violates the canonical evidence contract",
                line_number=next(iter(row.values())).line_number,
            ) from exc
        residue_semantic_keys.add(semantic_key)
        residue_claims.append(claim)

    for row_index, row in enumerate(atom_rows, start=1):
        extension_tags = set(row) - known_atom_tags
        if extension_tags:
            partial = True
            extension_item_count += len(extension_tags)
            blockers.append("missingness_extension_items_uninterpreted")
        (
            _,
            occupancy_flag,
            model_id,
            chain_id,
            residue_id,
            residue_name,
            insertion_code,
            identity_basis,
            raw_payload,
        ) = parse_common(
            row,
            category=atom_category,
            seen_source_ids=seen_atom_source_ids,
        )
        auth_atom_token = _required_cif_token(
            row,
            f"{atom_category}.auth_atom_id",
            code="incomplete_missingness_evidence",
            description=f"{atom_category}.auth_atom_id",
            line_number=next(iter(row.values())).line_number,
        )
        label_atom_token = _cif_token_value(row, f"{atom_category}.label_atom_id")
        atom_name = (
            label_atom_token.value
            if identity_basis == "label" and label_atom_token is not None
            else auth_atom_token.value
        )
        if not atom_name:
            raise _error(
                "mmcif",
                "incomplete_missingness_evidence",
                "missing atom identity must be nonempty",
                line_number=auth_atom_token.line_number,
            )
        if identity_basis == "label" and label_atom_token is None:
            partial = True
            blockers.append("partial_label_identity_in_missingness_evidence")
            atom_name = auth_atom_token.value
            raw_payload["identity_basis"] = "mixed_label_residue_auth_atom"
        elif identity_basis == "auth" and label_atom_token is not None:
            partial = True
            blockers.append("partial_label_identity_in_missingness_evidence")
            raw_payload["identity_basis"] = "mixed_auth_residue_label_atom_ignored"
        altloc_token = _cif_token_value(row, f"{atom_category}.label_alt_id")
        altloc_id = "" if altloc_token is None else altloc_token.value
        coordinate_identity_basis = (
            None
            if raw_payload["identity_basis"]
            == "mixed_label_residue_auth_atom"
            else identity_basis
        )
        queue_coordinate_consistency_check(
            row=row,
            occupancy_flag=occupancy_flag,
            model_id=model_id,
            chain_id=chain_id,
            residue_id=residue_id,
            residue_name=residue_name,
            insertion_code=insertion_code,
            identity_basis=coordinate_identity_basis,
            atom_name=atom_name,
            altloc_id=altloc_id,
        )
        if occupancy_flag == 0:
            zero_occupancy_atom_rows += 1
            continue
        semantic_key = (
            model_id,
            chain_id,
            residue_id,
            residue_name,
            insertion_code,
            atom_name,
            altloc_id,
        )
        if semantic_key in atom_semantic_keys:
            partial = True
            blockers.append("duplicate_missing_atom_claims_preserved")
        try:
            claim = SourceReportedMissingAtomClaim(
                source_ordinal=row_index,
                source_category=atom_category,
                source_model_id=model_id,
                source_chain_id=chain_id,
                source_residue_id=residue_id,
                source_residue_name=residue_name,
                source_insertion_code=insertion_code,
                source_atom_name=atom_name,
                source_altloc_id=altloc_id,
                raw_payload=raw_payload,
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise _error(
                "mmcif",
                "invalid_missingness_evidence",
                "source missing-atom row violates the canonical evidence contract",
                line_number=next(iter(row.values())).line_number,
            ) from exc
        atom_semantic_keys.add(semantic_key)
        atom_claims.append(claim)

    def residue_coordinate_key(
        check: _MmcifMissingnessCoordinateCheck,
    ) -> tuple[int, str, str, str, str]:
        return (
            check.model_id,
            check.chain_id,
            check.residue_id,
            check.residue_name.upper(),
            check.insertion_code,
        )

    requested_label_residue_keys = {
        residue_coordinate_key(check)
        for check in coordinate_checks
        if check.identity_basis == "label" and check.atom_name is None
    }
    requested_label_atom_keys = {
        (*residue_coordinate_key(check), check.atom_name, check.altloc_id)
        for check in coordinate_checks
        if check.identity_basis == "label" and check.atom_name is not None
    }
    requested_auth_residue_keys = {
        residue_coordinate_key(check)
        for check in coordinate_checks
        if check.identity_basis == "auth" and check.atom_name is None
    }
    requested_auth_atom_keys = {
        (*residue_coordinate_key(check), check.atom_name, check.altloc_id)
        for check in coordinate_checks
        if check.identity_basis == "auth" and check.atom_name is not None
    }
    requested_auth_models = {
        check.model_id
        for check in coordinate_checks
        if check.identity_basis == "auth"
    }
    requested_models = {check.model_id for check in coordinate_checks}
    label_residue_occupancies: dict[
        tuple[int, str, str, str, str],
        _MmcifOccupancySummary,
    ] = {}
    label_atom_occupancies: dict[
        tuple[int, str, str, str, str, str, str],
        _MmcifOccupancySummary,
    ] = {}
    auth_residue_occupancies: dict[
        tuple[int, str, str, str, str],
        _MmcifOccupancySummary,
    ] = {}
    auth_atom_occupancies: dict[
        tuple[int, str, str, str, str, str, str],
        _MmcifOccupancySummary,
    ] = {}

    def observe_occupancy(
        index: dict[tuple[Any, ...], _MmcifOccupancySummary],
        key: tuple[Any, ...],
        occupancy: float | None,
    ) -> None:
        summary = index.get(key)
        if summary is None:
            summary = _MmcifOccupancySummary()
            index[key] = summary
        summary.observe(occupancy)

    complete_auth_residue_identity_models = set(requested_auth_models)
    complete_auth_atom_identity_models = set(requested_auth_models)
    for model_id, model in zip(model_ids, raw_models):
        if model_id not in requested_models:
            continue
        for atom in model:
            label_residue_key = (
                model_id,
                atom.chain_id,
                str(atom.residue_number),
                atom.residue_name.upper(),
                atom.insertion_code,
            )
            if label_residue_key in requested_label_residue_keys:
                observe_occupancy(
                    label_residue_occupancies,
                    label_residue_key,
                    atom.occupancy,
                )
            label_atom_key = (*label_residue_key, atom.name, atom.altloc)
            if label_atom_key in requested_label_atom_keys:
                observe_occupancy(
                    label_atom_occupancies,
                    label_atom_key,
                    atom.occupancy,
                )
            if model_id not in requested_auth_models:
                continue
            mmcif_metadata = atom.metadata.get("mmcif")
            auth_identity = (
                mmcif_metadata.get("auth_identity")
                if isinstance(mmcif_metadata, dict)
                else None
            )
            if not isinstance(auth_identity, dict):
                complete_auth_residue_identity_models.discard(model_id)
                complete_auth_atom_identity_models.discard(model_id)
                continue
            auth_asym_id = auth_identity.get("asym_id")
            auth_comp_id = auth_identity.get("comp_id")
            auth_seq_id = auth_identity.get("seq_id")
            if not all(
                type(value) is str and value
                for value in (auth_asym_id, auth_comp_id, auth_seq_id)
            ):
                complete_auth_residue_identity_models.discard(model_id)
                complete_auth_atom_identity_models.discard(model_id)
                continue
            auth_residue_key = (
                model_id,
                auth_asym_id,
                auth_seq_id,
                auth_comp_id.upper(),
                atom.insertion_code,
            )
            if auth_residue_key in requested_auth_residue_keys:
                observe_occupancy(
                    auth_residue_occupancies,
                    auth_residue_key,
                    atom.occupancy,
                )
            auth_atom_id = auth_identity.get("atom_id")
            if type(auth_atom_id) is str and auth_atom_id:
                auth_atom_key = (*auth_residue_key, auth_atom_id, atom.altloc)
                if auth_atom_key in requested_auth_atom_keys:
                    observe_occupancy(
                        auth_atom_occupancies,
                        auth_atom_key,
                        atom.occupancy,
                    )
            else:
                complete_auth_atom_identity_models.discard(model_id)

    for check in coordinate_checks:
        residue_key = residue_coordinate_key(check)
        residue_index = (
            label_residue_occupancies
            if check.identity_basis == "label"
            else auth_residue_occupancies
        )
        atom_index = (
            label_atom_occupancies
            if check.identity_basis == "label"
            else auth_atom_occupancies
        )
        occupancy_summary = (
            residue_index.get(residue_key)
            if check.atom_name is None
            else atom_index.get(
                (*residue_key, check.atom_name, check.altloc_id),
            )
        )
        if (
            (
                occupancy_summary is None
                or occupancy_summary.presence_count == 0
            )
            and check.identity_basis == "auth"
            and check.model_id
            not in (
                complete_auth_residue_identity_models
                if check.atom_name is None
                else complete_auth_atom_identity_models
            )
        ):
            partial = True
            blockers.append(
                "source_missingness_coordinate_consistency_partially_assessed"
            )
            continue
        if check.occupancy_flag == 1:
            if (
                occupancy_summary is not None
                and occupancy_summary.presence_count > 0
            ):
                raise _error(
                    "mmcif",
                    (
                        "missing_residue_present_in_coordinates"
                        if check.atom_name is None
                        else "declared_missing_atom_present"
                    ),
                    "source declares an unobserved identity present in raw atom_site",
                    line_number=check.line_number,
                )
            continue
        if (
            occupancy_summary is None
            or occupancy_summary.presence_count == 0
        ):
            raise _error(
                "mmcif",
                (
                    "zero_occupancy_residue_absent_from_coordinates"
                    if check.atom_name is None
                    else "zero_occupancy_atom_absent_from_coordinates"
                ),
                "zero-occupancy source identity is absent from raw atom_site",
                line_number=check.line_number,
            )
        if occupancy_summary.any_nonzero:
            raise _error(
                "mmcif",
                (
                    "zero_occupancy_residue_value_conflict"
                    if check.atom_name is None
                    else "zero_occupancy_atom_value_conflict"
                ),
                "zero-occupancy source identity has a nonzero atom_site occupancy",
                line_number=check.line_number,
            )
        if occupancy_summary.any_unavailable:
            partial = True
            blockers.append("zero_occupancy_coordinate_values_not_available")

    if zero_occupancy_residue_rows:
        blockers.append("source_reports_zero_occupancy_residues")
    if zero_occupancy_atom_rows:
        blockers.append("source_reports_zero_occupancy_atoms")
    if evidence_present:
        blockers.append("missingness_full_dictionary_validation_not_assessed")
    metadata = {
        "interpretation_policy": "documented_items_preserved_without_full_dictionary_validation/v1",
        "dictionary_validation_status": "not_assessed",
        "residue_row_count": len(residue_rows),
        "atom_row_count": len(atom_rows),
        "unobserved_residue_claim_count": len(residue_claims),
        "unobserved_atom_claim_count": len(atom_claims),
        "zero_occupancy_residue_row_count": zero_occupancy_residue_rows,
        "zero_occupancy_atom_row_count": zero_occupancy_atom_rows,
        "extension_item_count": extension_item_count,
    }
    return (
        tuple(residue_claims),
        tuple(atom_claims),
        evidence_present,
        partial,
        tuple(dict.fromkeys(blockers)),
        metadata,
    )


def _validate_mmcif_code(
    token: CifToken,
    *,
    code: str,
    description: str,
    maximum_length: int = 256,
) -> str:
    value = token.value
    if (
        not value
        or len(value) > maximum_length
        or value != value.strip()
        or any(character.isspace() for character in value)
    ):
        raise _error(
            "mmcif",
            code,
            f"{description} must be a nonempty single-word identifier of at most {maximum_length} characters",
            line_number=token.line_number,
        )
    return value


def _parse_mmcif_oper_expression(
    token: CifToken,
) -> tuple[tuple[str, ...], ...]:
    expression = token.value
    if not expression or len(expression) > _MAX_MMCIF_OPER_EXPRESSION_CHARS:
        raise _error(
            "mmcif",
            "assembly_expression_limit_exceeded",
            "assembly operation expression is empty or exceeds the fixed character limit",
            line_number=token.line_number,
        )
    if any(character.isspace() and character not in {" ", "\t"} for character in expression):
        raise _error(
            "mmcif",
            "invalid_oper_expression",
            "assembly operation expression contains unsupported whitespace",
            line_number=token.line_number,
        )
    if expression != expression.strip(" \t") or re.search(
        r"(?<=[^(),\s])[ \t]+(?=[^(),\s])",
        expression,
    ):
        raise _error(
            "mmcif",
            "invalid_oper_expression",
            "assembly operation expression whitespace must not split an operator identifier",
            line_number=token.line_number,
        )
    compact = expression.replace(" ", "").replace("\t", "")
    if not compact:
        raise _error(
            "mmcif",
            "invalid_oper_expression",
            "assembly operation expression is empty",
            line_number=token.line_number,
        )
    if "(" in compact or ")" in compact:
        if re.fullmatch(r"(?:\([^()]+\))+", compact) is None:
            raise _error(
                "mmcif",
                "invalid_oper_expression",
                "assembly operation expression has malformed parentheses",
                line_number=token.line_number,
            )
        raw_groups = re.findall(r"\(([^()]+)\)", compact)
    else:
        if "," in compact or _ASSEMBLY_NUMERIC_RANGE_LIKE_RE.fullmatch(compact):
            raise _error(
                "mmcif",
                "invalid_oper_expression",
                "bare assembly operation expression must contain exactly one code",
                line_number=token.line_number,
            )
        raw_groups = [compact]

    groups: list[tuple[str, ...]] = []
    for raw_group in raw_groups:
        expanded: list[str] = []
        for item in raw_group.split(","):
            if not item:
                raise _error(
                    "mmcif",
                    "invalid_oper_expression",
                    "assembly operation list contains an empty item",
                    line_number=token.line_number,
                )
            range_match = _ASSEMBLY_CANONICAL_RANGE_RE.fullmatch(item)
            if range_match is not None:
                start = int(range_match.group("start"), 10)
                end = int(range_match.group("end"), 10)
                if end < start:
                    raise _error(
                        "mmcif",
                        "descending_oper_range",
                        "assembly operation ranges must be ascending",
                        line_number=token.line_number,
                    )
                range_length = end - start + 1
                if range_length > _MAX_MMCIF_ASSEMBLY_OPERATION_SEQUENCES:
                    raise _error(
                        "mmcif",
                        "assembly_expression_limit_exceeded",
                        "assembly operation range exceeds the fixed expansion limit",
                        line_number=token.line_number,
                    )
                expanded.extend(str(value) for value in range(start, end + 1))
            elif _ASSEMBLY_NUMERIC_RANGE_LIKE_RE.fullmatch(item) is not None:
                raise _error(
                    "mmcif",
                    "invalid_oper_expression",
                    "assembly operation ranges must use canonical decimal integers without leading zeros",
                    line_number=token.line_number,
                )
            elif _ASSEMBLY_OPERATION_CODE_RE.fullmatch(item) is not None:
                expanded.append(item)
            else:
                raise _error(
                    "mmcif",
                    "invalid_oper_expression",
                    f"assembly operation item {item!r} is outside the supported grammar",
                    line_number=token.line_number,
                )
        if len(set(expanded)) != len(expanded):
            raise _error(
                "mmcif",
                "invalid_oper_expression",
                "assembly operation factor contains duplicate identifiers",
                line_number=token.line_number,
            )
        groups.append(tuple(expanded))

    sequence_count = 1
    for group in groups:
        if sequence_count > _MAX_MMCIF_ASSEMBLY_OPERATION_SEQUENCES // len(group):
            raise _error(
                "mmcif",
                "assembly_expression_limit_exceeded",
                "assembly operation Cartesian product exceeds the fixed expansion limit",
                line_number=token.line_number,
            )
        sequence_count *= len(group)
    if len(groups) > _MAX_MMCIF_ASSEMBLY_OPERATION_APPLICATIONS // sequence_count:
        raise _error(
            "mmcif",
            "assembly_operation_application_limit_exceeded",
            "assembly operation expression exceeds the fixed operator-application limit",
            line_number=token.line_number,
        )
    return tuple(tuple(sequence) for sequence in itertools.product(*groups))


def _parse_mmcif_asym_id_list(token: CifToken) -> tuple[str, ...]:
    if (
        len(token.value) > _MAX_MMCIF_ASSEMBLY_ASYM_ID_LIST_CHARS
        or token.value.count(",") + 1
        > _MAX_MMCIF_ASSEMBLY_ASYM_IDS_PER_GENERATOR
    ):
        raise _error(
            "mmcif",
            "assembly_asym_id_list_limit_exceeded",
            "assembly asym_id_list exceeds the fixed character or identifier-count limit",
            line_number=token.line_number,
        )
    values = tuple(part.strip() for part in token.value.split(","))
    if (
        not values
        or any(
            not value
            or len(value) > 256
            or any(character.isspace() for character in value)
            for value in values
        )
    ):
        raise _error(
            "mmcif",
            "invalid_assembly_asym_id_list",
            "assembly asym_id_list must contain comma-separated single-word label asym IDs",
            line_number=token.line_number,
        )
    if len(set(values)) != len(values):
        raise _error(
            "mmcif",
            "duplicate_assembly_asym_id",
            "assembly asym_id_list contains duplicate label asym IDs",
            line_number=token.line_number,
        )
    return values


def _parse_mmcif_assembly_operations(
    block: CifBlock,
) -> dict[str, _MmcifAssemblyOperation]:
    rows = _category_rows(block, "_pdbx_struct_oper_list")
    if not rows:
        raise _error(
            "mmcif",
            "assembly_operator_list_missing",
            "explicit biological assembly requires _pdbx_struct_oper_list",
        )
    if len(rows) > _MAX_MMCIF_ASSEMBLY_OPERATOR_ROWS:
        raise _error(
            "mmcif",
            "assembly_operator_limit_exceeded",
            "assembly operator list exceeds the fixed row limit",
        )
    matrix_tags = tuple(
        f"_pdbx_struct_oper_list.matrix[{row_index}][{column_index}]"
        for row_index in range(1, 4)
        for column_index in range(1, 4)
    )
    vector_tags = tuple(
        f"_pdbx_struct_oper_list.vector[{index}]" for index in range(1, 4)
    )
    operations: dict[str, _MmcifAssemblyOperation] = {}
    for row_index, row in enumerate(rows):
        line_number = next(iter(row.values())).line_number
        operation_id = _validate_mmcif_code(
            _required_cif_token(
                row,
                "_pdbx_struct_oper_list.id",
                code="incomplete_assembly_operator",
                description="assembly operator id",
                line_number=line_number,
            ),
            code="invalid_assembly_operator",
            description="assembly operator id",
        )
        if _ASSEMBLY_OPERATION_ID_RE.fullmatch(operation_id) is None:
            raise _error(
                "mmcif",
                "invalid_assembly_operator",
                f"assembly operator id {operation_id!r} is outside the PDBx character-code grammar",
                line_number=line_number,
            )
        if operation_id in operations:
            raise _error(
                "mmcif",
                "duplicate_assembly_operator_id",
                f"duplicate assembly operator {operation_id!r}",
                line_number=line_number,
            )
        if any(
            tag.startswith("_pdbx_struct_oper_list.full_matrix")
            and not _cif_token_is_missing(value)
            for tag, value in row.items()
        ):
            raise _error(
                "mmcif",
                "unsupported_assembly_full_matrix",
                "assembly full_matrix representation is not supported",
                line_number=line_number,
            )
        parsed_values: list[float] = []
        uncertainty_present = False
        for tag in (*matrix_tags, *vector_tags):
            token = _required_cif_token(
                row,
                tag,
                code="incomplete_assembly_operator",
                description=tag,
                line_number=line_number,
            )
            value, uncertainty = _strict_cif_float(
                token,
                code="invalid_assembly_operator",
                field=tag,
            )
            parsed_values.append(value)
            uncertainty_present = uncertainty_present or uncertainty
        rotation = torch.tensor(parsed_values[:9], dtype=torch.float64).reshape(3, 3)
        translation = torch.tensor(parsed_values[9:], dtype=torch.float64)
        identity = torch.eye(3, dtype=torch.float64)
        if not bool(
            torch.allclose(
                rotation.T @ rotation,
                identity,
                atol=1.0e-4,
                rtol=0.0,
            )
        ) or not math.isclose(
            float(torch.linalg.det(rotation).item()),
            1.0,
            abs_tol=1.0e-4,
            rel_tol=0.0,
        ):
            raise _error(
                "mmcif",
                "non_rigid_assembly_operator",
                f"assembly operator {operation_id!r} is not a proper rigid transform",
                line_number=line_number,
            )
        operations[operation_id] = _MmcifAssemblyOperation(
            operation_id=operation_id,
            rotation=tuple(
                tuple(float(value) for value in rotation[row].tolist())
                for row in range(3)
            ),
            translation=tuple(float(value) for value in translation.tolist()),
            source_row_index=row_index,
            uncertainty_present=uncertainty_present,
        )
    return operations


def _parse_mmcif_assembly_plan(
    block: CifBlock,
    assembly_id: str,
) -> _MmcifAssemblyPlan:
    assembly_rows = _category_rows(block, "_pdbx_struct_assembly")
    if not assembly_rows:
        raise _error(
            "mmcif",
            "assembly_definition_missing",
            "explicit assembly selection requires _pdbx_struct_assembly",
        )
    if len(assembly_rows) > _MAX_MMCIF_ASSEMBLY_DEFINITION_ROWS:
        raise _error(
            "mmcif",
            "assembly_definition_limit_exceeded",
            "assembly definition list exceeds the fixed row limit",
        )
    assembly_ids: set[str] = set()
    for row in assembly_rows:
        line_number = next(iter(row.values())).line_number
        observed_id = _validate_mmcif_code(
            _required_cif_token(
                row,
                "_pdbx_struct_assembly.id",
                code="invalid_assembly_id",
                description="assembly id",
                line_number=line_number,
            ),
            code="invalid_assembly_id",
            description="assembly id",
        )
        if observed_id in assembly_ids:
            raise _error(
                "mmcif",
                "duplicate_assembly_id",
                f"duplicate assembly id {observed_id!r}",
                line_number=line_number,
            )
        assembly_ids.add(observed_id)
    if assembly_id not in assembly_ids:
        raise _error(
            "mmcif",
            "assembly_id_not_found",
            f"requested assembly {assembly_id!r} is not defined",
        )

    generator_rows = _category_rows(block, "_pdbx_struct_assembly_gen")
    if not generator_rows:
        raise _error(
            "mmcif",
            "assembly_generator_missing",
            "explicit assembly selection requires _pdbx_struct_assembly_gen",
        )
    if len(generator_rows) > _MAX_MMCIF_ASSEMBLY_GENERATOR_ROWS:
        raise _error(
            "mmcif",
            "assembly_generator_limit_exceeded",
            "assembly generator list exceeds the fixed row limit",
        )
    selected_generators: list[_MmcifAssemblyGenerator] = []
    total_sequences = 0
    total_operation_applications = 0
    total_chain_instances = 0
    selected_oper_expression_character_count = 0
    selected_oper_expression_max_character_count = 0
    selected_asym_id_list_character_count = 0
    selected_asym_id_list_max_character_count = 0
    selected_asym_id_count = 0
    for row_index, row in enumerate(generator_rows):
        line_number = next(iter(row.values())).line_number
        generator_assembly_id = _validate_mmcif_code(
            _required_cif_token(
                row,
                "_pdbx_struct_assembly_gen.assembly_id",
                code="unknown_assembly_gen_id",
                description="assembly generator id",
                line_number=line_number,
            ),
            code="unknown_assembly_gen_id",
            description="assembly generator id",
        )
        if generator_assembly_id not in assembly_ids:
            raise _error(
                "mmcif",
                "unknown_assembly_gen_id",
                f"assembly generator references undefined assembly {generator_assembly_id!r}",
                line_number=line_number,
            )
        if generator_assembly_id != assembly_id:
            continue
        expression_token = _required_cif_token(
            row,
            "_pdbx_struct_assembly_gen.oper_expression",
            code="invalid_oper_expression",
            description="assembly operation expression",
            line_number=line_number,
        )
        asym_token = _required_cif_token(
            row,
            "_pdbx_struct_assembly_gen.asym_id_list",
            code="invalid_assembly_asym_id_list",
            description="assembly asym_id_list",
            line_number=line_number,
        )
        sequences = _parse_mmcif_oper_expression(expression_token)
        asym_ids = _parse_mmcif_asym_id_list(asym_token)
        if total_sequences > _MAX_MMCIF_ASSEMBLY_OPERATION_SEQUENCES - len(sequences):
            raise _error(
                "mmcif",
                "assembly_expression_limit_exceeded",
                "selected assembly exceeds the fixed operation-sequence limit",
                line_number=line_number,
            )
        total_sequences += len(sequences)
        operation_applications = sum(len(sequence) for sequence in sequences)
        if (
            total_operation_applications
            > _MAX_MMCIF_ASSEMBLY_OPERATION_APPLICATIONS
            - operation_applications
        ):
            raise _error(
                "mmcif",
                "assembly_operation_application_limit_exceeded",
                "selected assembly exceeds the fixed operator-application limit",
                line_number=line_number,
            )
        total_operation_applications += operation_applications
        if len(sequences) > _MAX_MMCIF_ASSEMBLY_CHAIN_INSTANCES // len(asym_ids):
            raise _error(
                "mmcif",
                "assembly_chain_instance_limit_exceeded",
                "selected assembly exceeds the fixed output chain-instance limit",
                line_number=line_number,
            )
        generator_chain_instances = len(sequences) * len(asym_ids)
        if (
            total_chain_instances
            > _MAX_MMCIF_ASSEMBLY_CHAIN_INSTANCES - generator_chain_instances
        ):
            raise _error(
                "mmcif",
                "assembly_chain_instance_limit_exceeded",
                "selected assembly exceeds the fixed output chain-instance limit",
                line_number=line_number,
            )
        total_chain_instances += generator_chain_instances
        selected_oper_expression_character_count += len(expression_token.value)
        selected_oper_expression_max_character_count = max(
            selected_oper_expression_max_character_count,
            len(expression_token.value),
        )
        selected_asym_id_list_character_count += len(asym_token.value)
        selected_asym_id_list_max_character_count = max(
            selected_asym_id_list_max_character_count,
            len(asym_token.value),
        )
        selected_asym_id_count += len(asym_ids)
        selected_generators.append(
            _MmcifAssemblyGenerator(
                source_row_index=row_index,
                asym_ids=asym_ids,
                raw_oper_expression=expression_token.value,
                operation_sequences=sequences,
            )
        )
    if not selected_generators:
        raise _error(
            "mmcif",
            "assembly_generator_missing",
            f"assembly {assembly_id!r} has no generator rows",
        )
    operations = _parse_mmcif_assembly_operations(block)
    for generator in selected_generators:
        for sequence in generator.operation_sequences:
            unknown = next(
                (operation_id for operation_id in sequence if operation_id not in operations),
                None,
            )
            if unknown is not None:
                raise _error(
                    "mmcif",
                    "unknown_assembly_operator_id",
                    f"assembly expression references undefined operator {unknown!r}",
                )
    return _MmcifAssemblyPlan(
        assembly_id=assembly_id,
        generators=tuple(selected_generators),
        operations=operations,
        definition_row_count=len(assembly_rows),
        generator_row_count=len(generator_rows),
        selected_generator_row_count=len(selected_generators),
        operator_row_count=len(operations),
        selected_oper_expression_character_count=(
            selected_oper_expression_character_count
        ),
        selected_oper_expression_max_character_count=(
            selected_oper_expression_max_character_count
        ),
        selected_asym_id_list_character_count=(
            selected_asym_id_list_character_count
        ),
        selected_asym_id_list_max_character_count=(
            selected_asym_id_list_max_character_count
        ),
        selected_asym_id_count=selected_asym_id_count,
    )


def _compose_mmcif_assembly_operations(
    plan: _MmcifAssemblyPlan,
    sequence: tuple[str, ...],
) -> tuple[torch.Tensor, torch.Tensor]:
    rotation = torch.eye(3, dtype=torch.float64)
    translation = torch.zeros(3, dtype=torch.float64)
    for operation_id in sequence:
        operation = plan.operations[operation_id]
        next_rotation = torch.tensor(operation.rotation, dtype=torch.float64)
        next_translation = torch.tensor(operation.translation, dtype=torch.float64)
        translation = rotation @ next_translation + translation
        rotation = rotation @ next_rotation
    if not bool(torch.isfinite(rotation).all().item()) or not bool(
        torch.isfinite(translation).all().item()
    ):
        raise _error(
            "mmcif",
            "invalid_assembly_operator",
            "composed assembly operation is non-finite",
        )
    identity = torch.eye(3, dtype=torch.float64)
    if not bool(
        torch.allclose(
            rotation.T @ rotation,
            identity,
            atol=1.0e-4,
            rtol=0.0,
        )
    ) or not math.isclose(
        float(torch.linalg.det(rotation).item()),
        1.0,
        abs_tol=1.0e-4,
        rel_tol=0.0,
    ):
        raise _error(
            "mmcif",
            "non_rigid_assembly_operator",
            f"composed assembly operation sequence {sequence[:5]!r} is not a proper rigid transform",
        )
    return rotation, translation


def _expand_mmcif_assembly_models(
    models: list[list[_SourceAtom]],
    model_ids: list[int],
    plan: _MmcifAssemblyPlan,
) -> tuple[list[list[_SourceAtom]], _AssemblyExpansionSummary]:
    source_chain_indices: dict[str, list[int]] = {}
    for atom_index, atom in enumerate(models[0]):
        source_chain_indices.setdefault(atom.chain_id, []).append(atom_index)

    components: list[
        tuple[int, int, str, tuple[str, ...], torch.Tensor, torch.Tensor]
    ] = []
    seen_instances: set[tuple[str, tuple[str, ...]]] = set()
    copy_group_index = 0
    for generator in plan.generators:
        for asym_id in generator.asym_ids:
            if asym_id not in source_chain_indices:
                raise _error(
                    "mmcif",
                    "unknown_assembly_asym_id",
                    f"assembly generator references label asym ID {asym_id!r} absent from selected atom_site rows",
                )
        for sequence in generator.operation_sequences:
            copy_group_index += 1
            rotation, translation = _compose_mmcif_assembly_operations(
                plan,
                sequence,
            )
            for asym_id in generator.asym_ids:
                instance_key = (asym_id, sequence)
                if instance_key in seen_instances:
                    raise _error(
                        "mmcif",
                        "duplicate_assembly_instance",
                        f"assembly repeats label asym ID {asym_id!r} with operation sequence {sequence!r}",
                    )
                seen_instances.add(instance_key)
                components.append(
                    (
                        len(components) + 1,
                        copy_group_index,
                        asym_id,
                        sequence,
                        rotation,
                        translation,
                    )
                )
                if len(components) > _MAX_MMCIF_ASSEMBLY_CHAIN_INSTANCES:
                    raise _error(
                        "mmcif",
                        "assembly_chain_instance_limit_exceeded",
                        "assembly exceeds the fixed output chain-instance limit",
                    )

    expanded_atom_count = 0
    for _, _, asym_id, _, _, _ in components:
        chain_atom_count = len(source_chain_indices[asym_id])
        if expanded_atom_count > _MAX_MMCIF_ASSEMBLY_OUTPUT_ATOMS - chain_atom_count:
            raise _error(
                "mmcif",
                "assembly_atom_limit_exceeded",
                "assembly exceeds the fixed output topology atom limit",
            )
        expanded_atom_count += chain_atom_count
    if not models or expanded_atom_count < 1:
        raise _error(
            "mmcif",
            "assembly_generator_missing",
            "selected assembly produces no atom instances",
        )
    if len(models) > _MAX_MMCIF_ASSEMBLY_OUTPUT_MODEL_ATOM_ROWS // expanded_atom_count:
        raise _error(
            "mmcif",
            "assembly_model_atom_limit_exceeded",
            "assembly exceeds the fixed model-by-atom output limit",
        )

    instance_ledger: list[dict[str, Any]] = []
    for (
        instance_index,
        group_index,
        asym_id,
        sequence,
        rotation,
        translation,
    ) in components:
        instance_ledger.append(
            {
                "instance_index": instance_index,
                "copy_group_index": group_index,
                "source_label_asym_id": asym_id,
                "output_chain_id": f"ASM{instance_index:06d}",
                "operation_sequence": list(sequence),
                "rotation": rotation.tolist(),
                "translation": translation.tolist(),
                "source_atom_count": len(source_chain_indices[asym_id]),
            }
        )

    expanded_models: list[list[_SourceAtom]] = []
    for model_id, model in zip(model_ids, models):
        expanded_model: list[_SourceAtom] = []
        for (
            instance_index,
            group_index,
            asym_id,
            sequence,
            rotation,
            translation,
        ) in components:
            output_chain_id = f"ASM{instance_index:06d}"
            pointer = {
                "assembly_id": plan.assembly_id,
                "assembly_instance_index": instance_index,
                "assembly_copy_group_index": group_index,
                "source_label_asym_id": asym_id,
                "output_chain_id": output_chain_id,
            }
            for source_atom_index in source_chain_indices[asym_id]:
                source_atom = model[source_atom_index]
                source_coordinates = torch.tensor(
                    source_atom.coordinates,
                    dtype=torch.float64,
                )
                transformed = rotation @ source_coordinates + translation
                if not bool(torch.isfinite(transformed).all().item()):
                    raise _error(
                        "mmcif",
                        "nonfinite_assembly_coordinate",
                        f"assembly transform produced non-finite coordinates in model {model_id}",
                )
                metadata = dict(source_atom.metadata)
                metadata["assembly_instance"] = dict(pointer)
                source_identity = (
                    source_atom.model_identity
                    if source_atom.model_identity is not None
                    else source_atom.identity()
                )
                expanded_model.append(
                    replace(
                        source_atom,
                        serial=len(expanded_model) + 1,
                        chain_id=output_chain_id,
                        coordinates=tuple(float(value) for value in transformed.tolist()),
                        metadata=metadata,
                        model_identity=(
                            "mmcif_explicit_assembly/v1",
                            instance_index,
                            source_identity,
                        ),
                    )
                )
        expanded_models.append(expanded_model)

    used_operation_ids = {
        operation_id
        for generator in plan.generators
        for sequence in generator.operation_sequences
        for operation_id in sequence
    }
    uncertainty_present = any(
        plan.operations[operation_id].uncertainty_present
        for operation_id in used_operation_ids
    )
    operation_sequence_count = sum(
        len(generator.operation_sequences) for generator in plan.generators
    )
    operation_application_count = sum(
        len(sequence)
        for generator in plan.generators
        for sequence in generator.operation_sequences
    )
    summary = _AssemblyExpansionSummary(
        status="explicit_id_applied",
        coordinate_scope="explicit_biological_assembly",
        requested_assembly_id=plan.assembly_id,
        source_topology_atom_count=len(models[0]),
        expanded_topology_atom_count=expanded_atom_count,
        operation_sequence_count=operation_sequence_count,
        operation_application_count=operation_application_count,
        copy_group_count=copy_group_index,
        chain_instance_count=len(components),
        expanded_model_atom_rows=expanded_atom_count * len(models),
        numeric_uncertainty_present=uncertainty_present,
        ledger={
            "status": "explicit_id_applied",
            "selection_policy": "explicit_only",
            "assembly_id": plan.assembly_id,
            "expression_semantics": "pdbx_right_to_left/v1",
            "source_topology_atom_count": len(models[0]),
            "expanded_topology_atom_count": expanded_atom_count,
            "operation_sequence_count": operation_sequence_count,
            "operation_application_count": operation_application_count,
            "copy_group_count": copy_group_index,
            "chain_instance_count": len(components),
            "expanded_model_atom_rows": expanded_atom_count * len(models),
            "resource_usage": {
                "definition_rows": plan.definition_row_count,
                "generator_rows": plan.generator_row_count,
                "selected_generator_rows": plan.selected_generator_row_count,
                "operator_rows": plan.operator_row_count,
                "selected_oper_expression_characters": (
                    plan.selected_oper_expression_character_count
                ),
                "selected_oper_expression_max_characters": (
                    plan.selected_oper_expression_max_character_count
                ),
                "selected_asym_id_list_characters": (
                    plan.selected_asym_id_list_character_count
                ),
                "selected_asym_id_list_max_characters": (
                    plan.selected_asym_id_list_max_character_count
                ),
                "selected_asym_ids": plan.selected_asym_id_count,
                "operation_sequences": operation_sequence_count,
                "operation_applications": operation_application_count,
                "chain_instances": len(components),
                "topology_atoms": expanded_atom_count,
                "model_atom_rows": expanded_atom_count * len(models),
            },
            "generators": [
                {
                    "source_row_index": generator.source_row_index,
                    "asym_ids": list(generator.asym_ids),
                    "raw_oper_expression": generator.raw_oper_expression,
                    "operation_sequences": [
                        list(sequence) for sequence in generator.operation_sequences
                    ],
                }
                for generator in plan.generators
            ],
            "instances": instance_ledger,
            "resource_limits": {
                "definition_rows": _MAX_MMCIF_ASSEMBLY_DEFINITION_ROWS,
                "generator_rows": _MAX_MMCIF_ASSEMBLY_GENERATOR_ROWS,
                "operator_rows": _MAX_MMCIF_ASSEMBLY_OPERATOR_ROWS,
                "oper_expression_characters": _MAX_MMCIF_OPER_EXPRESSION_CHARS,
                "operation_sequences": _MAX_MMCIF_ASSEMBLY_OPERATION_SEQUENCES,
                "operation_applications": _MAX_MMCIF_ASSEMBLY_OPERATION_APPLICATIONS,
                "asym_id_list_characters": _MAX_MMCIF_ASSEMBLY_ASYM_ID_LIST_CHARS,
                "asym_ids_per_generator": _MAX_MMCIF_ASSEMBLY_ASYM_IDS_PER_GENERATOR,
                "chain_instances": _MAX_MMCIF_ASSEMBLY_CHAIN_INSTANCES,
                "topology_atoms": _MAX_MMCIF_ASSEMBLY_OUTPUT_ATOMS,
                "model_atom_rows": _MAX_MMCIF_ASSEMBLY_OUTPUT_MODEL_ATOM_ROWS,
            },
        },
    )
    return expanded_models, summary


def _parse_mmcif_entity_maps(block: CifBlock) -> tuple[dict[str, str], dict[str, str]]:
    entity_types: dict[str, str] = {}
    for row in _category_rows(block, "_entity"):
        line_number = next(iter(row.values())).line_number
        entity_id = _required_cif_token(
            row,
            "_entity.id",
            code="missing_entity_id",
            description="_entity.id",
            line_number=line_number,
        ).value
        if not entity_id:
            raise _error("mmcif", "missing_entity_id", "_entity.id is empty", line_number=line_number)
        if entity_id in entity_types:
            raise _error("mmcif", "duplicate_entity_id", f"duplicate entity {entity_id!r}", line_number=line_number)
        type_token = _cif_token_value(row, "_entity.type")
        raw_type = "" if type_token is None else type_token.value.strip().lower()
        entity_types[entity_id] = _MMCIF_ENTITY_TYPES.get(raw_type, "unknown")

    asym_entities: dict[str, str] = {}
    for row in _category_rows(block, "_struct_asym"):
        line_number = next(iter(row.values())).line_number
        asym_id = _required_cif_token(
            row,
            "_struct_asym.id",
            code="missing_struct_asym_id",
            description="_struct_asym.id",
            line_number=line_number,
        ).value
        entity_id = _required_cif_token(
            row,
            "_struct_asym.entity_id",
            code="missing_struct_asym_entity",
            description="_struct_asym.entity_id",
            line_number=line_number,
        ).value
        if not asym_id or not entity_id:
            raise _error(
                "mmcif",
                "missing_struct_asym_identity",
                "_struct_asym.id and entity_id must be nonempty",
                line_number=line_number,
            )
        if asym_id in asym_entities:
            raise _error("mmcif", "duplicate_struct_asym_id", f"duplicate asym id {asym_id!r}", line_number=line_number)
        if entity_types and entity_id not in entity_types:
            raise _error(
                "mmcif",
                "unknown_struct_asym_entity",
                f"_struct_asym {asym_id!r} references unknown entity {entity_id!r}",
                line_number=line_number,
            )
        asym_entities[asym_id] = entity_id
    return entity_types, asym_entities


def _mmcif_space_group(block: CifBlock) -> str | None:
    candidates = [
        token
        for token in (
            block.scalar_values.get("_space_group.name_h-m_alt"),
            block.scalar_values.get("_symmetry.space_group_name_h-m"),
        )
        if not _cif_token_is_missing(token)
    ]
    if not candidates:
        return None
    normalized = {token.value.replace(" ", "").upper() for token in candidates}
    if len(normalized) != 1:
        raise _error(
            "mmcif",
            "conflicting_space_group",
            "_space_group and _symmetry space-group names disagree",
            line_number=candidates[1].line_number,
        )
    return candidates[0].value


def _parse_mmcif_cell(block: CifBlock) -> tuple[UnitCell | None, dict[str, Any] | None, bool]:
    rows = _category_rows(block, "_cell")
    if not rows:
        return None, None, False
    if len(rows) != 1:
        raise _error("mmcif", "multiple_cells", "exactly one unit cell is supported")
    row = rows[0]
    uncertainty_present = False
    for esd_tag in sorted(
        tag
        for tag in row
        if tag.startswith("_cell.") and tag.endswith("_esd")
    ):
        esd_token = _cif_token_value(row, esd_tag)
        if esd_token is None:
            continue
        esd_value, _ = _strict_cif_float(
            esd_token,
            code="invalid_numeric_standard_uncertainty",
            field=esd_tag,
        )
        if esd_value < 0.0:
            raise _error(
                "mmcif",
                "invalid_numeric_standard_uncertainty",
                f"{esd_tag} must be nonnegative",
                line_number=esd_token.line_number,
            )
        uncertainty_present = True
    tags = (
        "_cell.length_a",
        "_cell.length_b",
        "_cell.length_c",
        "_cell.angle_alpha",
        "_cell.angle_beta",
        "_cell.angle_gamma",
    )
    if not any(tag in row for tag in tags):
        return None, None, uncertainty_present
    missing = [tag for tag in tags if _cif_token_value(row, tag) is None]
    if missing:
        line_number = next(iter(row.values())).line_number
        raise _error(
            "mmcif",
            "incomplete_cell",
            f"unit-cell definition is missing {missing!r}",
            line_number=line_number,
        )
    parsed = [
        _strict_cif_float(row[tag], code="invalid_cell", field=tag)
        for tag in tags
    ]
    values = [item[0] for item in parsed]
    uncertainty_present = uncertainty_present or any(item[1] for item in parsed)
    a, b, c, alpha, beta, gamma = values
    if min(a, b, c) <= 0.0 or not all(0.0 < angle < 180.0 for angle in (alpha, beta, gamma)):
        raise _error("mmcif", "invalid_cell", "cell lengths and angles must define a positive cell")

    alpha_r, beta_r, gamma_r = map(math.radians, (alpha, beta, gamma))
    sin_gamma = math.sin(gamma_r)
    if abs(sin_gamma) <= 1.0e-12:
        raise _error("mmcif", "invalid_cell", "gamma produces a singular cell")
    vector_a = (a, 0.0, 0.0)
    vector_b = (b * math.cos(gamma_r), b * sin_gamma, 0.0)
    c_x = c * math.cos(beta_r)
    c_y = c * (math.cos(alpha_r) - math.cos(beta_r) * math.cos(gamma_r)) / sin_gamma
    c_z_squared = c * c - c_x * c_x - c_y * c_y
    if c_z_squared <= 1.0e-12:
        raise _error("mmcif", "invalid_cell", "cell vectors do not form positive volume")

    space_group = _mmcif_space_group(block)
    is_dummy = (
        all(math.isclose(length, 1.0, abs_tol=1.0e-9) for length in (a, b, c))
        and all(math.isclose(angle, 90.0, abs_tol=1.0e-9) for angle in (alpha, beta, gamma))
        and (space_group is None or space_group.replace(" ", "").upper() == "P1")
    )
    if is_dummy:
        raise _error("mmcif", "dummy_cell", "1x1x1 P1 placeholder is not a physical periodic cell")
    vectors = torch.tensor(
        [vector_a, vector_b, (c_x, c_y, math.sqrt(c_z_squared))],
        dtype=torch.float64,
    )
    return UnitCell(vectors=vectors, periodic=(False, False, False)), {
        "parameters": {tag: _cif_token_payload(row[tag]) for tag in tags},
        "space_group": space_group,
        "standard_uncertainty_present": uncertainty_present,
    }, uncertainty_present


def _mmcif_category_inventory(block: CifBlock) -> tuple[list[dict[str, Any]], int, tuple[str, ...]]:
    inventory: list[dict[str, Any]] = []
    uninterpreted_count = 0
    blockers: list[str] = []
    for category in block.categories:
        scalar_count = sum(
            tag.split(".", 1)[0] == category for tag in block.scalar_values
        )
        loops = [loop for loop in block.loops if category in loop.categories]
        row_count = sum(len(loop.rows) for loop in loops)
        policy = _mmcif_category_policy(category)
        if category in _MMCIF_SYMMETRY_OPERATION_CATEGORIES:
            blockers.append("crystallographic_symmetry_not_expanded")
        elif policy == "uninterpreted_metadata":
            uninterpreted_count += 1
        inventory.append(
            {
                "category": category,
                "scalar_item_count": scalar_count,
                "loop_count": len(loops),
                "row_count": row_count,
                "policy": policy,
            }
        )
    if uninterpreted_count:
        blockers.append("uninterpreted_mmcif_categories_present")
    return inventory, uninterpreted_count, tuple(dict.fromkeys(blockers))


def _parse_mmcif_atom_row(
    row: dict[str, CifToken],
    *,
    entity_types: dict[str, str],
    asym_entities: dict[str, str],
    nonpoly_residue_numbers: dict[tuple[str, str, str, str], int],
    next_nonpoly_number_by_chain: dict[str, int],
) -> tuple[_SourceAtom, int, tuple[Any, ...], bool, str]:
    line_number = next(iter(row.values())).line_number
    group_token = _required_cif_token(
        row,
        "_atom_site.group_pdb",
        code="invalid_group_pdb",
        description="_atom_site.group_PDB",
        line_number=line_number,
    )
    group = group_token.value.upper()
    if group not in {"ATOM", "HETATM"}:
        raise _error("mmcif", "invalid_group_pdb", "group_PDB must be ATOM or HETATM", line_number=line_number)

    serial_token = _required_cif_token(
        row,
        "_atom_site.id",
        code="missing_atom_id",
        description="_atom_site.id",
        line_number=line_number,
    )
    source_atom_id = serial_token.value
    if not source_atom_id or any(character.isspace() for character in source_atom_id):
        raise _error(
            "mmcif",
            "invalid_atom_id",
            "_atom_site.id must be a nonempty single-word identifier",
            line_number=line_number,
        )

    element_token = _required_cif_token(
        row,
        "_atom_site.type_symbol",
        code="missing_element",
        description="_atom_site.type_symbol",
        line_number=line_number,
    )
    element = canonical_element_symbol(element_token.value)
    if not element or atomic_number_for_element(element) == 0:
        raise _error("mmcif", "unknown_element", f"unknown element {element!r}", line_number=line_number)

    identity_tags = {
        "atom_name": "_atom_site.label_atom_id",
        "residue_name": "_atom_site.label_comp_id",
        "chain_id": "_atom_site.label_asym_id",
    }
    identity_values: dict[str, str] = {}
    for field, tag in identity_tags.items():
        token = _required_cif_token(
            row,
            tag,
            code="missing_label_identity",
            description=tag,
            line_number=line_number,
        )
        if not token.value:
            raise _error("mmcif", "missing_label_identity", f"{tag} is empty", line_number=line_number)
        if token.value != token.value.strip():
            raise _error(
                "mmcif",
                "label_identity_whitespace_not_supported",
                f"{tag} has leading or trailing whitespace that canonical identity cannot preserve",
                line_number=line_number,
            )
        identity_values[field] = token.value
    atom_name = identity_values["atom_name"]
    residue_name = identity_values["residue_name"].upper()
    chain_id = identity_values["chain_id"]

    label_entity_token = _cif_token_value(row, "_atom_site.label_entity_id")
    label_entity_id = "" if label_entity_token is None else label_entity_token.value
    if asym_entities and chain_id not in asym_entities:
        raise _error(
            "mmcif",
            "unknown_label_asym_id",
            f"label_asym_id {chain_id!r} is absent from _struct_asym",
            line_number=line_number,
        )
    mapped_entity_id = asym_entities.get(chain_id, "")
    if label_entity_id and mapped_entity_id and label_entity_id != mapped_entity_id:
        raise _error(
            "mmcif",
            "conflicting_entity_identity",
            f"label entity {label_entity_id!r} conflicts with _struct_asym entity {mapped_entity_id!r}",
            line_number=line_number,
        )
    entity_id = label_entity_id or mapped_entity_id
    if entity_types and entity_id and entity_id not in entity_types:
        raise _error(
            "mmcif",
            "unknown_atom_site_entity",
            f"atom label entity {entity_id!r} is absent from _entity",
            line_number=line_number,
        )
    entity_type = entity_types.get(entity_id, "unknown")

    insertion_token = _cif_token_value(row, "_atom_site.pdbx_pdb_ins_code")
    insertion_code = "" if insertion_token is None else insertion_token.value
    if insertion_code != insertion_code.strip():
        raise _error(
            "mmcif",
            "insertion_code_whitespace_not_supported",
            "pdbx_PDB_ins_code has leading or trailing whitespace",
            line_number=line_number,
        )

    label_seq_token = _cif_token_value(row, "_atom_site.label_seq_id")
    auth_seq_token = _cif_token_value(row, "_atom_site.auth_seq_id")
    sequence_source = "label_seq_id"
    if label_seq_token is not None:
        residue_number = _strict_cif_int(
            label_seq_token,
            code="invalid_residue_number",
            field="label_seq_id",
        )
        if residue_number < 1:
            raise _error(
                "mmcif",
                "invalid_residue_number",
                "label_seq_id must be a positive integer",
                line_number=label_seq_token.line_number,
            )
    else:
        if entity_type == "polymer":
            raise _error(
                "mmcif",
                "missing_polymer_label_seq_id",
                "polymer atoms require _atom_site.label_seq_id",
                line_number=line_number,
            )
        if auth_seq_token is None or not auth_seq_token.value:
            raise _error(
                "mmcif",
                "missing_residue_number",
                "non-polymer atoms without label_seq_id require auth_seq_id",
                line_number=line_number,
            )
        sequence_source = "synthetic_negative_from_nonpolymer_auth_identity"
        nonpoly_key = (chain_id, auth_seq_token.value, insertion_code, residue_name)
        if nonpoly_key not in nonpoly_residue_numbers:
            next_number = next_nonpoly_number_by_chain.get(chain_id, -1)
            nonpoly_residue_numbers[nonpoly_key] = next_number
            next_nonpoly_number_by_chain[chain_id] = next_number - 1
        residue_number = nonpoly_residue_numbers[nonpoly_key]
    label_alt_token = _cif_token_value(row, "_atom_site.label_alt_id")
    altloc = "" if label_alt_token is None else label_alt_token.value
    if not altloc and label_alt_token is not None:
        raise _error(
            "mmcif",
            "invalid_altloc_id",
            "_atom_site.label_alt_id must not be an empty value",
            line_number=label_alt_token.line_number,
        )
    if altloc and (
        len(altloc) > 256
        or altloc != altloc.strip()
        or any(character.isspace() for character in altloc)
        or any(0xD800 <= ord(character) <= 0xDFFF for character in altloc)
    ):
        raise _error(
            "mmcif",
            "invalid_altloc_id",
            "_atom_site.label_alt_id must be a single-word identifier of at most 256 characters",
            line_number=label_alt_token.line_number,
        )

    coordinate_tokens = [
        _required_cif_token(
            row,
            tag,
            code="missing_atom_coordinate",
            description=tag,
            line_number=line_number,
        )
        for tag in ("_atom_site.cartn_x", "_atom_site.cartn_y", "_atom_site.cartn_z")
    ]
    parsed_coordinates = [
        _strict_cif_float(token, code="invalid_atom_coordinate", field=field)
        for token, field in zip(coordinate_tokens, ("Cartn_x", "Cartn_y", "Cartn_z"))
    ]
    coordinates = tuple(item[0] for item in parsed_coordinates)
    numeric_uncertainty = any(item[1] for item in parsed_coordinates)

    occupancy_token = _cif_token_value(row, "_atom_site.occupancy")
    occupancy = None
    if occupancy_token is not None:
        occupancy, has_uncertainty = _strict_cif_float(
            occupancy_token,
            code="invalid_occupancy",
            field="occupancy",
        )
        numeric_uncertainty = numeric_uncertainty or has_uncertainty
        if not 0.0 <= occupancy <= 1.0:
            raise _error("mmcif", "invalid_occupancy", "occupancy must be in [0, 1]", line_number=line_number)

    b_factor_token = _cif_token_value(row, "_atom_site.b_iso_or_equiv")
    b_factor = None
    if b_factor_token is not None:
        b_factor, has_uncertainty = _strict_cif_float(
            b_factor_token,
            code="invalid_b_factor",
            field="B_iso_or_equiv",
        )
        numeric_uncertainty = numeric_uncertainty or has_uncertainty

    for esd_tag in sorted(_MMCIF_ATOM_SITE_ESD_TAGS):
        esd_token = _cif_token_value(row, esd_tag)
        if esd_token is None:
            continue
        esd_value, _ = _strict_cif_float(
            esd_token,
            code="invalid_numeric_standard_uncertainty",
            field=esd_tag,
        )
        if esd_value < 0.0:
            raise _error(
                "mmcif",
                "invalid_numeric_standard_uncertainty",
                f"{esd_tag} must be nonnegative",
                line_number=esd_token.line_number,
            )
        numeric_uncertainty = True

    charge_token = _cif_token_value(row, "_atom_site.pdbx_formal_charge")
    formal_charge_known = charge_token is not None
    formal_charge = 0
    if charge_token is not None:
        formal_charge = _strict_cif_int(
            charge_token,
            code="invalid_formal_charge",
            field="formal_charge",
        )
        if abs(formal_charge) > _MAX_ABS_CANONICAL_FORMAL_CHARGE:
            raise _error(
                "mmcif",
                "invalid_formal_charge",
                "formal_charge exceeds the canonical magnitude limit",
                line_number=charge_token.line_number,
            )

    model_token = _cif_token_value(row, "_atom_site.pdbx_pdb_model_num")
    model_id = 1 if model_token is None else _strict_cif_int(
        model_token,
        code="invalid_model_id",
        field="model_id",
    )
    if model_id < 0:
        raise _error("mmcif", "invalid_model_id", "model id must be nonnegative", line_number=line_number)

    auth_values = {
        name: (None if _cif_token_value(row, tag) is None else row[tag].value)
        for name, tag in {
            "atom_id": "_atom_site.auth_atom_id",
            "comp_id": "_atom_site.auth_comp_id",
            "asym_id": "_atom_site.auth_asym_id",
            "seq_id": "_atom_site.auth_seq_id",
            "alt_id": "_atom_site.pdbx_auth_alt_id",
        }.items()
    }
    canonical_key = (chain_id, residue_number, insertion_code, residue_name, atom_name)
    metadata = {
        "formal_charge_known": formal_charge_known,
        "formal_charge_source": (
            "_atom_site.pdbx_formal_charge" if formal_charge_known else "missing_in_mmcif"
        ),
        "formal_charge_interpretation": (
            "explicit" if formal_charge_known else "placeholder_zero_unknown"
        ),
        "mmcif_auth_asym_id": auth_values["asym_id"] or "",
        "mmcif": {
            "atom_site": {tag: _cif_token_payload(token) for tag, token in sorted(row.items())},
            "canonical_identity_namespace": "label",
            "residue_sequence_source": sequence_source,
            "auth_identity": auth_values,
            "entity_id": entity_id,
            "entity_type": entity_type,
            "source_atom_site_id": source_atom_id,
        },
    }
    model_identity = (
        group,
        canonical_key,
        element,
        formal_charge,
        formal_charge_known,
        entity_id,
        entity_type,
        altloc,
        tuple(auth_values.items()),
    )
    return (
        _SourceAtom(
            record=group,
            serial=1,
            name=atom_name,
            residue_name=residue_name,
            chain_id=chain_id,
            residue_number=residue_number,
            insertion_code=insertion_code,
            altloc=altloc,
            element=element,
            formal_charge=formal_charge,
            occupancy=occupancy,
            b_factor=b_factor,
            coordinates=coordinates,
            metadata=metadata,
            entity_id=entity_id,
            entity_type=entity_type,
            residue_metadata={
                "mmcif_label_seq_id": None if label_seq_token is None else label_seq_token.value,
                "mmcif_auth_seq_id": None if auth_seq_token is None else auth_seq_token.value,
                "canonical_sequence_source": sequence_source,
            },
            model_identity=model_identity,
        ),
        model_id,
        canonical_key,
        numeric_uncertainty,
        source_atom_id,
    )


def parse_mmcif(
    data: bytes,
    *,
    source_id: str = "",
    altloc_id: str | None = None,
    assembly_id: str | None = None,
) -> StructureIngestResult:
    """Parse PDBx coordinates with explicit-only altloc and assembly selection."""

    if type(data) is not bytes:
        raise TypeError("mmCIF input must be bytes")
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    if altloc_id is not None and type(altloc_id) is not str:
        raise TypeError("altloc_id must be a string or None")
    if assembly_id is not None and type(assembly_id) is not str:
        raise TypeError("assembly_id must be a string or None")
    if altloc_id is not None and (
        not altloc_id
        or len(altloc_id) > 256
        or altloc_id != altloc_id.strip()
        or any(character.isspace() for character in altloc_id)
        or any(0xD800 <= ord(character) <= 0xDFFF for character in altloc_id)
    ):
        raise _error(
            "mmcif",
            "invalid_altloc_id",
            "mmCIF altloc_id must be a nonempty single-word identifier of at most 256 characters",
        )
    if assembly_id is not None and (
        not assembly_id
        or len(assembly_id) > 256
        or assembly_id != assembly_id.strip()
        or any(character.isspace() for character in assembly_id)
        or any(0xD800 <= ord(character) <= 0xDFFF for character in assembly_id)
    ):
        raise _error(
            "mmcif",
            "invalid_assembly_id",
            "mmCIF assembly_id must be a nonempty single-word identifier of at most 256 characters",
        )
    if not data:
        raise _error("mmcif", "empty_input", "mmCIF input is empty")
    if len(data) > _MAX_MMCIF_INPUT_BYTES:
        raise _error(
            "mmcif",
            "input_too_large",
            f"mmCIF input exceeds the {_MAX_MMCIF_INPUT_BYTES}-byte safety limit",
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _error("mmcif", "invalid_utf8", "mmCIF input must be valid UTF-8") from exc
    if "\x00" in text:
        raise _error("mmcif", "invalid_text", "NUL bytes are not allowed")
    try:
        block = parse_cif_block(text)
    except CifSyntaxError as exc:
        raise _error(
            "mmcif",
            exc.code,
            exc.detail,
            line_number=exc.line_number,
        ) from exc

    _preflight_mmcif_assembly_resources(block)
    missingness_resource_usage = _preflight_mmcif_missingness_resources(block)

    topology_category = next(
        (category for category in block.categories if category in _MMCIF_TOPOLOGY_CATEGORIES),
        None,
    )
    if topology_category is not None:
        raise _error(
            "mmcif",
            "unsupported_topology_category",
            f"explicit topology category {topology_category!r} is not yet ingested losslessly",
        )

    context_category = next(
        (
            category
            for category in block.categories
            if _is_unsupported_mmcif_context_category(category)
        ),
        None,
    )
    if context_category is not None:
        raise _error(
            "mmcif",
            "unsupported_context_category",
            f"chemical context category {context_category!r} is not yet "
            "ingested losslessly",
        )

    scalar_atom_site = [
        tag for tag in block.scalar_values if tag.split(".", 1)[0] == "_atom_site"
    ]
    atom_site_loops = [loop for loop in block.loops if "_atom_site" in loop.categories]
    if scalar_atom_site:
        raise _error(
            "mmcif",
            "scalar_atom_site_not_supported",
            "_atom_site must be represented by exactly one loop",
            line_number=block.scalar_values[scalar_atom_site[0]].line_number,
        )
    if not atom_site_loops:
        raise _error("mmcif", "missing_atom_site_loop", "one _atom_site loop is required")
    if len(atom_site_loops) > 1:
        raise _error(
            "mmcif",
            "multiple_atom_site_loops",
            "exactly one _atom_site loop is supported",
            line_number=atom_site_loops[1].line_number,
        )
    atom_site_loop: CifLoop = atom_site_loops[0]
    if atom_site_loop.categories != ("_atom_site",):
        raise _error(
            "mmcif",
            "mixed_atom_site_loop",
            "_atom_site must not share a loop with another category",
            line_number=atom_site_loop.line_number,
        )
    if len(atom_site_loop.rows) > _MAX_MMCIF_ATOM_ROWS:
        raise _error(
            "mmcif",
            "too_many_atom_rows",
            f"_atom_site may contain at most {_MAX_MMCIF_ATOM_ROWS} rows",
            line_number=atom_site_loop.line_number,
        )

    unreviewed_category = next(
        (
            category
            for category in block.categories
            if _mmcif_category_policy(category) == "uninterpreted_metadata"
            and category not in _MMCIF_REVIEWED_DROPPABLE_METADATA_CATEGORIES
        ),
        None,
    )
    if unreviewed_category is not None:
        raise _error(
            "mmcif",
            "unsupported_uninterpreted_category",
            f"unreviewed category {unreviewed_category!r} is not preserved "
            "losslessly",
        )

    entity_types, asym_entities = _parse_mmcif_entity_maps(block)
    cell, cell_metadata, cell_uncertainty = _parse_mmcif_cell(block)
    inventory, uninterpreted_count, inventory_blockers = _mmcif_category_inventory(block)
    preserved_category_payloads = _mmcif_preserved_category_payloads(block)

    raw_model_maps: dict[
        int,
        dict[tuple[tuple[Any, ...], str], _SourceAtom],
    ] = {}
    source_atom_site_ids: set[str] = set()
    nonpoly_residue_numbers: dict[tuple[str, str, str, str], int] = {}
    next_nonpoly_number_by_chain: dict[str, int] = {}
    numeric_uncertainty = cell_uncertainty
    for row_tokens in atom_site_loop.rows:
        row = dict(zip(atom_site_loop.tags, row_tokens))
        atom, model_id, canonical_key, row_uncertainty, source_atom_id = _parse_mmcif_atom_row(
            row,
            entity_types=entity_types,
            asym_entities=asym_entities,
            nonpoly_residue_numbers=nonpoly_residue_numbers,
            next_nonpoly_number_by_chain=next_nonpoly_number_by_chain,
        )
        numeric_uncertainty = numeric_uncertainty or row_uncertainty
        if source_atom_id in source_atom_site_ids:
            raise _error(
                "mmcif",
                "duplicate_atom_site_id",
                f"_atom_site.id {source_atom_id!r} is not unique across the atom_site list",
                line_number=row_tokens[0].line_number,
            )
        source_atom_site_ids.add(source_atom_id)
        model = raw_model_maps.setdefault(model_id, {})
        raw_key = (canonical_key, atom.altloc)
        if raw_key in model:
            raise _error(
                "mmcif",
                "duplicate_altloc_atom_identity",
                f"model {model_id} contains duplicate label/altloc identity {raw_key!r}",
                line_number=row_tokens[0].line_number,
            )
        model[raw_key] = atom

    model_ids = list(raw_model_maps)
    if not model_ids:
        raise _error("mmcif", "empty_atom_site", "_atom_site loop has no atom rows")
    raw_models = [list(raw_model_maps[model_id].values()) for model_id in model_ids]
    (
        missing_residue_claims,
        missing_atom_claims,
        missingness_evidence_present,
        missingness_evidence_partially_interpreted,
        missingness_blockers,
        missingness_metadata,
    ) = _parse_mmcif_source_missingness(
        block,
        model_ids=model_ids,
        raw_models=raw_models,
    )
    selected_models, altloc_summary = _select_explicit_altloc(
        raw_models,
        model_ids,
        source_format="mmcif",
        altloc_id=altloc_id,
    )
    model_maps: dict[int, dict[tuple[Any, ...], _SourceAtom]] = {}
    for model_id, selected_model in zip(model_ids, selected_models):
        model: dict[tuple[Any, ...], _SourceAtom] = {}
        for atom in selected_model:
            canonical_key = _source_atom_site_key(atom)
            if canonical_key in model:
                raise _error(
                    "mmcif",
                    "duplicate_atom_identity_after_altloc_selection",
                    f"model {model_id} contains duplicate selected label identity {canonical_key!r}",
                )
            model[canonical_key] = atom
        model_maps[model_id] = model
    reference_keys = list(model_maps[model_ids[0]])
    reference_key_set = set(reference_keys)
    models: list[list[_SourceAtom]] = []
    for model_id in model_ids:
        model = model_maps[model_id]
        if set(model) != reference_key_set:
            missing = [key for key in reference_keys if key not in model]
            extra = [key for key in model if key not in reference_key_set]
            raise _error(
                "mmcif",
                "model_topology_mismatch",
                f"model {model_id} label identities differ; missing={missing[:3]!r}, extra={extra[:3]!r}",
            )
        models.append([model[key] for key in reference_keys])

    reference_model = model_maps[model_ids[0]]
    model_variant_measurements = any(
        model_maps[model_id][key].occupancy != reference_model[key].occupancy
        or model_maps[model_id][key].b_factor != reference_model[key].b_factor
        for model_id in model_ids[1:]
        for key in reference_keys
    )

    for atom_index, key in enumerate(reference_keys):
        source_ids = [
            {
                "model_id": model_id,
                "atom_site_id": model_maps[model_id][key].metadata["mmcif"]["source_atom_site_id"],
            }
            for model_id in model_ids
        ]
        atom = models[0][atom_index]
        metadata = dict(atom.metadata)
        mmcif_metadata = dict(metadata["mmcif"])
        mmcif_metadata["atom_site_id_by_model"] = source_ids
        mmcif_metadata["atom_site_by_model"] = [
            {
                "model_id": model_id,
                "values": model_maps[model_id][key].metadata["mmcif"]["atom_site"],
            }
            for model_id in model_ids
        ]
        metadata["mmcif"] = mmcif_metadata
        models[0][atom_index] = replace(atom, serial=atom_index + 1, metadata=metadata)

    assembly_categories_present = any(
        category in _MMCIF_ASSEMBLY_CATEGORIES for category in block.categories
    )
    if assembly_id is None:
        assembly_summary = _unapplied_assembly_summary(
            status=(
                "present_not_requested" if assembly_categories_present else "not_present"
            ),
            coordinate_scope="deposited_asymmetric_unit",
            source_topology_atom_count=len(models[0]),
        )
    else:
        assembly_plan = _parse_mmcif_assembly_plan(block, assembly_id)
        models, assembly_summary = _expand_mmcif_assembly_models(
            models,
            model_ids,
            assembly_plan,
        )
        for item in inventory:
            if item["category"] in _MMCIF_ASSEMBLY_CATEGORIES:
                item["policy"] = (
                    "partially_interpreted_explicit_biological_assembly_applied"
                )
        for payload in preserved_category_payloads:
            if payload["category"] in _MMCIF_ASSEMBLY_CATEGORIES:
                payload["policy"] = (
                    "partially_interpreted_explicit_biological_assembly_applied"
                )

    extra_blockers = list(inventory_blockers)
    extra_blockers.extend(missingness_blockers)
    space_group = _mmcif_space_group(block)
    if cell is not None:
        extra_blockers.append("crystallographic_cell_not_simulation_box")
    if space_group is not None and space_group.replace(" ", "").upper() != "P1":
        extra_blockers.append("crystallographic_symmetry_not_expanded")
    elif cell is not None and space_group is None:
        extra_blockers.append("crystallographic_symmetry_not_expanded")
    if model_variant_measurements:
        extra_blockers.append("model_variant_atom_properties_preserved_as_metadata")
    if numeric_uncertainty:
        extra_blockers.append("numeric_standard_uncertainty_not_propagated")
    if assembly_summary.numeric_uncertainty_present:
        extra_blockers.append(
            "assembly_operation_numeric_standard_uncertainty_not_propagated"
        )
    return _build_system(
        source_format="mmcif",
        parser_version=MMCIF_PARSER_VERSION,
        data=data,
        source_id=source_id,
        suggested_system_id=block.name,
        models=models,
        model_ids=model_ids,
        altloc_summary=altloc_summary,
        assembly_summary=assembly_summary,
        source_bonds=[],
        cell=cell,
        format_metadata={
            "mmcif": {
                "data_block": block.name,
                "coordinate_scope": assembly_summary.coordinate_scope,
                "assembly": assembly_summary.ledger,
                "altloc_selection": altloc_summary.ledger,
                "atom_site_headers": list(atom_site_loop.tags),
                "category_inventory": inventory,
                "preserved_category_payloads": preserved_category_payloads,
                "source_missingness": missingness_metadata,
                "cell": cell_metadata,
                "resource_usage": {
                    "input_bytes": len(data),
                    "token_count": block.token_count,
                    "atom_site_rows": len(atom_site_loop.rows),
                    "missing_residue_evidence_rows": missingness_metadata[
                        "residue_row_count"
                    ],
                    "missing_atom_evidence_rows": missingness_metadata[
                        "atom_row_count"
                    ],
                    "total_missingness_evidence_rows": (
                        missingness_metadata["residue_row_count"]
                        + missingness_metadata["atom_row_count"]
                    ),
                    "missingness_preserved_items": missingness_resource_usage[
                        "preserved_item_count"
                    ],
                    "missingness_preserved_value_utf8_bytes": (
                        missingness_resource_usage[
                            "preserved_value_utf8_bytes"
                        ]
                    ),
                },
                "resource_limits": {
                    "input_bytes": _MAX_MMCIF_INPUT_BYTES,
                    "token_count": MAX_CIF_TOKEN_COUNT,
                    "atom_site_rows": _MAX_MMCIF_ATOM_ROWS,
                    "missing_residue_evidence_rows": MAX_MISSING_RESIDUE_CLAIMS,
                    "missing_atom_evidence_rows": MAX_MISSING_ATOM_CLAIMS,
                    "total_missingness_evidence_rows": (
                        MAX_TOTAL_MISSINGNESS_CLAIMS
                    ),
                    "missingness_token_characters": (
                        _MAX_MMCIF_MISSINGNESS_TOKEN_CHARS
                    ),
                    "missingness_preserved_items": (
                        _MAX_MMCIF_MISSINGNESS_PRESERVED_ITEMS
                    ),
                    "missingness_preserved_value_utf8_bytes": (
                        _MAX_MMCIF_MISSINGNESS_PRESERVED_UTF8_BYTES
                    ),
                    "assembly_definition_rows": (
                        _MAX_MMCIF_ASSEMBLY_DEFINITION_ROWS
                    ),
                    "assembly_generator_rows": (
                        _MAX_MMCIF_ASSEMBLY_GENERATOR_ROWS
                    ),
                    "assembly_operator_rows": _MAX_MMCIF_ASSEMBLY_OPERATOR_ROWS,
                    "assembly_oper_expression_characters": (
                        _MAX_MMCIF_OPER_EXPRESSION_CHARS
                    ),
                    "assembly_asym_id_list_characters": (
                        _MAX_MMCIF_ASSEMBLY_ASYM_ID_LIST_CHARS
                    ),
                    "assembly_asym_ids_per_generator": (
                        _MAX_MMCIF_ASSEMBLY_ASYM_IDS_PER_GENERATOR
                    ),
                },
            }
        },
        operations=(
            "parse_cif_1_1_block_structure",
            "parse_pdbx_atom_site_label_identity",
            *(
                ("preserve_source_reported_missingness_without_completion/v1",)
                if missingness_evidence_present
                else ()
            ),
            *(
                ("select_explicit_altloc_id/v1",)
                if altloc_summary.status == "explicit_id_selected"
                else ()
            ),
            "align_models_by_canonical_label_identity",
            *(
                (
                    "parse_explicit_pdbx_biological_assembly/v1",
                    "compose_pdbx_oper_expression_right_to_left/v1",
                    "expand_explicit_biological_assembly/v1",
                    "reorder_atoms_by_assembly_instance_then_source_order/v1",
                    "preserve_source_atom_order_within_each_assembly_instance/v1",
                    "synthesize_assembly_chain_ids/v1",
                    "synthesize_canonical_atom_serials_from_assembly_instance_order/v1",
                )
                if assembly_summary.status == "explicit_id_applied"
                else (
                    "preserve_source_atom_order_from_first_model",
                    "synthesize_canonical_atom_serials_from_first_model_order",
                )
            ),
        ),
        missing_residue_claims=missing_residue_claims,
        missing_atom_claims=missing_atom_claims,
        missingness_evidence_present=missingness_evidence_present,
        missingness_evidence_partially_interpreted=(
            missingness_evidence_partially_interpreted
        ),
        extra_blockers=extra_blockers,
        uninterpreted_category_count=uninterpreted_count,
    )
