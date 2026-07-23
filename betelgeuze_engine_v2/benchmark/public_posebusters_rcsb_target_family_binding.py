"""Bind PoseBusters results to pocket-associated RCSB/Pfam annotations.

This module consumes a normalized, immutable observation of the official RCSB
Data API rather than making network requests at product runtime.  It recomputes
the protein chains within six angstrom of each exact reference ligand, maps
those one-character archive chain IDs first by exact RCSB ``asym_id`` and only
then by exact ``auth_asym_id`` fallback, and projects the frozen Vina, GNINA,
and Smina case outcomes
onto Pfam multi-label families and exact Pfam-set partitions.

The observation is not an RCSB-signed statement, Pfam coverage is incomplete,
and external fit/training manifests remain absent.  The resulting receipt is
therefore target-family evidence with an all-case denominator, not a leakage-
free public benchmark or product claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import json
import math
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Iterable, Mapping, Sequence
import zipfile

import torch

from betelgeuze_engine_v2.io import (
    PDBParseError,
    SDFParseError,
    parse_pdb,
    parse_sdf_v2000,
)

from .public_posebusters_corpus_audit import (
    PoseBustersCorpusAuditError,
    _canonical_bytes,
    _canonical_sha256,
    _positive_int,
    _read_member,
    _source_file_sha256,
    _token,
)
from .public_posebusters_generated_pose_evaluation import (
    _case_id,
    _digest,
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
from .public_posebusters_target_cluster_binding import (
    POSEBUSTERS_TARGET_CLUSTER_ENGINES,
    POSEBUSTERS_TARGET_CLUSTER_MAX_RECEIPT_BYTES,
    POSEBUSTERS_TARGET_CLUSTER_RECEIPT_SCHEMA_ID,
    PoseBustersTargetClusterEngineCase,
)


POSEBUSTERS_RCSB_REFERENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_rcsb_reference/1.0.0"
)
POSEBUSTERS_RCSB_PFAM_ANNOTATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_rcsb_pfam_annotation/1.0.0"
)
POSEBUSTERS_RCSB_POLYMER_ENTITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_rcsb_polymer_entity/1.0.0"
)
POSEBUSTERS_RCSB_TARGET_ENTRY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_rcsb_target_entry/1.0.0"
)
POSEBUSTERS_RCSB_REQUEST_BATCH_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_rcsb_request_batch/1.0.0"
)
POSEBUSTERS_RCSB_TARGET_ANNOTATION_SNAPSHOT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_rcsb_target_annotation_snapshot/1.0.0"
)
POSEBUSTERS_RCSB_TARGET_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_rcsb_target_case/1.0.0"
)
POSEBUSTERS_RCSB_PFAM_FAMILY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_rcsb_pfam_family/1.0.0"
)
POSEBUSTERS_RCSB_PFAM_SET_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_rcsb_pfam_set/1.0.0"
)
POSEBUSTERS_RCSB_ENGINE_FAMILY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_rcsb_engine_family/1.0.0"
)
POSEBUSTERS_RCSB_TARGET_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_rcsb_target_metric/1.0.0"
)
POSEBUSTERS_RCSB_LEAKAGE_DISPOSITION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_rcsb_leakage_disposition/1.0.0"
)
POSEBUSTERS_RCSB_TARGET_FAMILY_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_rcsb_target_family_receipt/1.0.0"
)

POSEBUSTERS_RCSB_GRAPHQL_ENDPOINT = "https://data.rcsb.org/graphql"
POSEBUSTERS_RCSB_HOLDINGS_ENDPOINT = (
    "https://data.rcsb.org/rest/v1/holdings"
)
POSEBUSTERS_RCSB_GRAPHQL_QUERY = """query PoseBustersTargetAnnotations($ids: [String!]!) {
  entries(entry_ids: $ids) {
    rcsb_id
    polymer_entities {
      rcsb_id
      rcsb_polymer_entity_container_identifiers {
        asym_ids
        auth_asym_ids
        entity_id
        entry_id
        uniprot_ids
        reference_sequence_identifiers {
          database_accession
          database_name
          provenance_source
          entity_sequence_coverage
          reference_sequence_coverage
        }
      }
      rcsb_polymer_entity_annotation {
        annotation_id
        name
        provenance_source
        type
        assignment_version
      }
    }
  }
}"""
POSEBUSTERS_RCSB_GRAPHQL_QUERY_SHA256 = (
    "ae19930d182dfd20570bea726cdcfcfee8788555cbec9f62ab6e071c8728fe83"
)
POSEBUSTERS_RCSB_TARGET_FAMILY_MAX_CASES = 308
POSEBUSTERS_RCSB_TARGET_FAMILY_MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
POSEBUSTERS_RCSB_TARGET_FAMILY_MAX_RECEIPT_BYTES = 24 * 1024 * 1024
POSEBUSTERS_RCSB_TARGET_FAMILY_POCKET_CUTOFF_ANGSTROM = 6.0
POSEBUSTERS_RCSB_TARGET_FAMILY_MAX_CROSS_PAIRS = 4_000_000
POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_RCSB_TARGET_FAMILY_Z = 1.959963984540054
POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIGURATION = {
    "annotation_semantics": "rcsb_pfam_annotation_not_experimental_family_assay",
    "archive_access": "bounded_zip_member_access_without_extraction",
    "chain_mapping": "exact_rcsb_asym_id_then_auth_asym_id_fallback",
    "engine_family_denominator": "all_members_including_execution_failures",
    "family_aggregation": "pfam_multi_label_and_exact_pfam_set_partition",
    "ligand_atoms": "strict_sdf_v2000_non_hydrogen_atoms",
    "pocket_association": "any_protein_heavy_atom_within_inclusive_cutoff",
    "pocket_cutoff_angstrom_binary64_hex": (
        POSEBUSTERS_RCSB_TARGET_FAMILY_POCKET_CUTOFF_ANGSTROM.hex()
    ),
    "receptor_atoms": "strict_pdb_first_model_atom_records_non_hydrogen",
    "removed_entry_policy": "explicit_disposition_without_replacement_remap",
    "unmapped_chain_policy": "fail_closed_without_truncation_or_alias_inference",
}
POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIGURATION_SHA256 = (
    "be8966a25136e3cd74456cc0a4b228a012dec4995933489fbaeb6039aa5bbad8"
)
POSEBUSTERS_RCSB_TARGET_FAMILY_SCIENTIFIC_BLOCKERS = (
    "rcsb_https_observation_is_not_independently_signed_by_rcsb",
    "pfam_annotation_is_incomplete_for_the_all_case_denominator",
    "pfam_multi_label_families_are_not_independent_statistical_samples",
    "archive_chain_aliases_are_not_inferred_for_unmapped_cases",
    "removed_rcsb_entries_are_not_remapped_to_replacements",
    "external_engine_fit_or_training_manifests_missing",
    "target_sequence_training_leakage_not_evaluated",
    "ligand_and_scaffold_training_leakage_not_evaluated",
    "ranking_scoring_and_screening_evidence_not_present",
    "independent_target_family_review_missing",
    "public_docking_benchmark_claim_not_authorized",
)

_MAPPING_STATUSES = {
    "complete",
    "pocket_chain_unmapped",
    "pocket_chain_ambiguous",
    "rcsb_entry_removed",
    "rcsb_entry_missing",
}
_ANNOTATION_STATUSES = {
    "pfam_annotated",
    "uniprot_without_pfam",
    "entity_without_uniprot_or_pfam",
    "not_applicable",
}
_ENTRY_STATUSES = {"active", "removed", "missing"}
_FAMILY_KINDS = {"pfam_multi_label", "pfam_set_partition"}
_SHA256_CHARACTERS = frozenset("0123456789abcdef")


class PoseBustersRcsbTargetFamilyBindingError(ValueError):
    """RCSB snapshot, archive mapping, aggregation, or receipt is invalid."""


def _bounded_text(
    value: object,
    *,
    name: str,
    maximum: int = 256,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise PoseBustersRcsbTargetFamilyBindingError(f"{name} must be text")
    if (
        (not value and not allow_empty)
        or len(value.encode("utf-8")) > maximum
        or any(character in "\r\n\x00" for character in value)
    ):
        raise PoseBustersRcsbTargetFamilyBindingError(
            f"{name} must be bounded single-line text"
        )
    return value


def _boolean(value: object, *, name: str) -> bool:
    if type(value) is not bool:
        raise PoseBustersRcsbTargetFamilyBindingError(f"{name} must be boolean")
    return value


def _nonnegative_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PoseBustersRcsbTargetFamilyBindingError(
            f"{name} must be a non-negative integer"
        )
    return value


def _pdb_id(value: object) -> str:
    text = _bounded_text(value, name="RCSB PDB ID", maximum=4).upper()
    if len(text) != 4 or not text.isalnum():
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB PDB ID must be four alphanumeric characters"
        )
    return text


def _unique_sorted_text(
    values: Iterable[object],
    *,
    name: str,
    maximum: int = 128,
) -> tuple[str, ...]:
    rows = tuple(
        sorted(
            _bounded_text(value, name=name, maximum=maximum)
            for value in values
        )
    )
    if len(rows) != len(set(rows)):
        raise PoseBustersRcsbTargetFamilyBindingError(f"{name} values repeat")
    return rows


def _fraction_hex(value: object, *, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PoseBustersRcsbTargetFamilyBindingError(
            f"{name} must be binary64 hexadecimal"
        )
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise PoseBustersRcsbTargetFamilyBindingError(
            f"{name} must be binary64 hexadecimal"
        ) from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise PoseBustersRcsbTargetFamilyBindingError(
            f"{name} must be a finite fraction"
        )
    return number.hex()


def _utc_timestamp(value: object) -> str:
    text = _bounded_text(value, name="RCSB observation UTC", maximum=40)
    if not text.endswith("Z"):
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB observation UTC must end in Z"
        )
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB observation UTC is invalid"
        ) from exc
    if parsed.tzinfo != timezone.utc:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB observation UTC must use UTC"
        )
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_write_new(
    output_path: str | os.PathLike[str],
    payload: Mapping[str, Any],
    *,
    maximum_bytes: int,
    label: str,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    source = _canonical_bytes(dict(payload)) + b"\n"
    if len(source) > maximum_bytes:
        raise PoseBustersRcsbTargetFamilyBindingError(
            f"{label} exceeds its byte bound"
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(source)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise PoseBustersRcsbTargetFamilyBindingError(
                f"{label} output already exists"
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


@dataclass(frozen=True, slots=True)
class PoseBustersRcsbReferenceSequence:
    database_name: str
    database_accession: str
    provenance_source: str
    entity_sequence_coverage_hex: str | None
    reference_sequence_coverage_hex: str | None
    schema_id: str = POSEBUSTERS_RCSB_REFERENCE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_RCSB_REFERENCE_SCHEMA_ID:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "unsupported RCSB reference schema"
            )
        object.__setattr__(
            self,
            "database_name",
            _bounded_text(self.database_name, name="reference database", maximum=64),
        )
        object.__setattr__(
            self,
            "database_accession",
            _bounded_text(
                self.database_accession,
                name="reference database accession",
                maximum=128,
            ),
        )
        object.__setattr__(
            self,
            "provenance_source",
            _bounded_text(
                self.provenance_source,
                name="reference provenance",
                maximum=128,
            ),
        )
        object.__setattr__(
            self,
            "entity_sequence_coverage_hex",
            _fraction_hex(
                self.entity_sequence_coverage_hex,
                name="entity sequence coverage",
            ),
        )
        object.__setattr__(
            self,
            "reference_sequence_coverage_hex",
            _fraction_hex(
                self.reference_sequence_coverage_hex,
                name="reference sequence coverage",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "database_name": self.database_name,
            "database_accession": self.database_accession,
            "provenance_source": self.provenance_source,
            "entity_sequence_coverage_binary64_hex": (
                self.entity_sequence_coverage_hex
            ),
            "reference_sequence_coverage_binary64_hex": (
                self.reference_sequence_coverage_hex
            ),
        }


@dataclass(frozen=True, slots=True)
class PoseBustersRcsbPfamAnnotation:
    annotation_id: str
    name: str
    provenance_source: str
    assignment_version: str
    schema_id: str = POSEBUSTERS_RCSB_PFAM_ANNOTATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_RCSB_PFAM_ANNOTATION_SCHEMA_ID:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "unsupported RCSB Pfam annotation schema"
            )
        annotation = _bounded_text(
            self.annotation_id,
            name="Pfam annotation ID",
            maximum=32,
        ).upper()
        if not annotation.startswith("PF") or not annotation[2:].isdigit():
            raise PoseBustersRcsbTargetFamilyBindingError(
                "Pfam annotation ID is invalid"
            )
        object.__setattr__(self, "annotation_id", annotation)
        object.__setattr__(
            self,
            "name",
            _bounded_text(self.name, name="Pfam annotation name", maximum=256),
        )
        object.__setattr__(
            self,
            "provenance_source",
            _bounded_text(
                self.provenance_source,
                name="Pfam provenance",
                maximum=128,
            ),
        )
        object.__setattr__(
            self,
            "assignment_version",
            _bounded_text(
                self.assignment_version,
                name="Pfam assignment version",
                maximum=64,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "annotation_id": self.annotation_id,
            "name": self.name,
            "provenance_source": self.provenance_source,
            "assignment_version": self.assignment_version,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersRcsbPolymerEntity:
    rcsb_entity_id: str
    entity_id: str
    asym_ids: tuple[str, ...]
    auth_asym_ids: tuple[str, ...]
    uniprot_ids: tuple[str, ...]
    reference_sequences: tuple[PoseBustersRcsbReferenceSequence, ...]
    pfam_annotations: tuple[PoseBustersRcsbPfamAnnotation, ...]
    schema_id: str = POSEBUSTERS_RCSB_POLYMER_ENTITY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_RCSB_POLYMER_ENTITY_SCHEMA_ID:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "unsupported RCSB polymer-entity schema"
            )
        rcsb_id = _bounded_text(
            self.rcsb_entity_id,
            name="RCSB polymer entity ID",
            maximum=32,
        ).upper()
        entity_id = _bounded_text(
            self.entity_id,
            name="RCSB entity ID",
            maximum=16,
        )
        asym_ids = _unique_sorted_text(
            self.asym_ids,
            name="RCSB asym ID",
            maximum=16,
        )
        auth_ids = _unique_sorted_text(
            self.auth_asym_ids,
            name="RCSB auth asym ID",
            maximum=16,
        )
        if not asym_ids and not auth_ids:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB polymer entity must expose a chain identifier"
            )
        uniprot = _unique_sorted_text(
            self.uniprot_ids,
            name="UniProt ID",
            maximum=32,
        )
        references = tuple(self.reference_sequences)
        annotations = tuple(self.pfam_annotations)
        if any(
            not isinstance(row, PoseBustersRcsbReferenceSequence)
            for row in references
        ) or any(
            not isinstance(row, PoseBustersRcsbPfamAnnotation)
            for row in annotations
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB entity annotations have invalid types"
            )
        if tuple(row.to_dict() for row in references) != tuple(
            sorted(
                (row.to_dict() for row in references),
                key=lambda row: (
                    row["database_name"],
                    row["database_accession"],
                    row["provenance_source"],
                ),
            )
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB reference sequences must be canonically ordered"
            )
        if tuple(row.annotation_id for row in annotations) != tuple(
            sorted(row.annotation_id for row in annotations)
        ) or len({row.annotation_id for row in annotations}) != len(annotations):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB Pfam annotations must be unique and ordered"
            )
        object.__setattr__(self, "rcsb_entity_id", rcsb_id)
        object.__setattr__(self, "entity_id", entity_id)
        object.__setattr__(self, "asym_ids", asym_ids)
        object.__setattr__(self, "auth_asym_ids", auth_ids)
        object.__setattr__(self, "uniprot_ids", uniprot)
        object.__setattr__(self, "reference_sequences", references)
        object.__setattr__(self, "pfam_annotations", annotations)

    @property
    def all_chain_ids(self) -> frozenset[str]:
        return frozenset((*self.asym_ids, *self.auth_asym_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "rcsb_entity_id": self.rcsb_entity_id,
            "entity_id": self.entity_id,
            "asym_ids": list(self.asym_ids),
            "auth_asym_ids": list(self.auth_asym_ids),
            "uniprot_ids": list(self.uniprot_ids),
            "reference_sequences": [
                row.to_dict() for row in self.reference_sequences
            ],
            "pfam_annotations": [
                row.to_dict() for row in self.pfam_annotations
            ],
        }


@dataclass(frozen=True, slots=True)
class PoseBustersRcsbTargetEntry:
    pdb_id: str
    status: str
    polymer_entities: tuple[PoseBustersRcsbPolymerEntity, ...]
    disposition_code: str = ""
    disposition_date: str = ""
    disposition_reason: str = ""
    replacement_pdb_ids: tuple[str, ...] = ()
    schema_id: str = POSEBUSTERS_RCSB_TARGET_ENTRY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_RCSB_TARGET_ENTRY_SCHEMA_ID:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "unsupported RCSB target-entry schema"
            )
        pdb = _pdb_id(self.pdb_id)
        status_value = _token(self.status, name="RCSB entry status")
        if status_value not in _ENTRY_STATUSES:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB entry status is invalid"
            )
        entities = tuple(self.polymer_entities)
        if any(
            not isinstance(row, PoseBustersRcsbPolymerEntity)
            for row in entities
        ) or tuple(row.rcsb_entity_id for row in entities) != tuple(
            sorted(row.rcsb_entity_id for row in entities)
        ) or len({row.rcsb_entity_id for row in entities}) != len(entities):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB polymer entities must be unique and ordered"
            )
        code = _bounded_text(
            self.disposition_code,
            name="RCSB disposition code",
            maximum=32,
            allow_empty=True,
        )
        date = _bounded_text(
            self.disposition_date,
            name="RCSB disposition date",
            maximum=32,
            allow_empty=True,
        )
        reason = _bounded_text(
            self.disposition_reason,
            name="RCSB disposition reason",
            maximum=512,
            allow_empty=True,
        )
        replacements = tuple(sorted(_pdb_id(value) for value in self.replacement_pdb_ids))
        if len(replacements) != len(set(replacements)):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB replacement PDB IDs repeat"
            )
        if status_value == "active":
            valid = bool(entities) and not code and not date and not reason and not replacements
        elif status_value == "removed":
            valid = not entities and bool(code and date and reason)
        else:
            valid = not entities and bool(reason) and not replacements
        if not valid:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB entry status and disposition are inconsistent"
            )
        object.__setattr__(self, "pdb_id", pdb)
        object.__setattr__(self, "status", status_value)
        object.__setattr__(self, "polymer_entities", entities)
        object.__setattr__(self, "disposition_code", code)
        object.__setattr__(self, "disposition_date", date)
        object.__setattr__(self, "disposition_reason", reason)
        object.__setattr__(self, "replacement_pdb_ids", replacements)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "pdb_id": self.pdb_id,
            "status": self.status,
            "polymer_entities": [
                row.to_dict() for row in self.polymer_entities
            ],
            "disposition_code": self.disposition_code,
            "disposition_date": self.disposition_date,
            "disposition_reason": self.disposition_reason,
            "replacement_pdb_ids": list(self.replacement_pdb_ids),
        }


@dataclass(frozen=True, slots=True)
class PoseBustersRcsbRequestBatch:
    batch_index: int
    requested_pdb_ids: tuple[str, ...]
    returned_active_pdb_ids: tuple[str, ...]
    normalized_response_sha256: str
    http_status_code: int = 200
    schema_id: str = POSEBUSTERS_RCSB_REQUEST_BATCH_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_RCSB_REQUEST_BATCH_SCHEMA_ID:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "unsupported RCSB request-batch schema"
            )
        index = _nonnegative_int(self.batch_index, name="RCSB batch index")
        requested = tuple(sorted(_pdb_id(value) for value in self.requested_pdb_ids))
        returned = tuple(
            sorted(_pdb_id(value) for value in self.returned_active_pdb_ids)
        )
        if (
            not requested
            or len(requested) != len(set(requested))
            or len(returned) != len(set(returned))
            or not set(returned).issubset(requested)
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB request-batch IDs are inconsistent"
            )
        status_code = _positive_int(
            self.http_status_code,
            name="RCSB HTTP status code",
        )
        if status_code != 200:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB request batch must have HTTP status 200"
            )
        object.__setattr__(self, "batch_index", index)
        object.__setattr__(self, "requested_pdb_ids", requested)
        object.__setattr__(self, "returned_active_pdb_ids", returned)
        object.__setattr__(
            self,
            "normalized_response_sha256",
            _digest(
                self.normalized_response_sha256,
                name="normalized RCSB response",
            ),
        )
        object.__setattr__(self, "http_status_code", status_code)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "batch_index": self.batch_index,
            "requested_pdb_ids": list(self.requested_pdb_ids),
            "returned_active_pdb_ids": list(self.returned_active_pdb_ids),
            "normalized_response_sha256": self.normalized_response_sha256,
            "http_status_code": self.http_status_code,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersRcsbTargetAnnotationSnapshot:
    observation_utc: str
    retrieval_tool_identity: str
    retrieval_tool_sha256: str
    request_batches: tuple[PoseBustersRcsbRequestBatch, ...]
    entries: tuple[PoseBustersRcsbTargetEntry, ...]
    schema_id: str = POSEBUSTERS_RCSB_TARGET_ANNOTATION_SNAPSHOT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_RCSB_TARGET_ANNOTATION_SNAPSHOT_SCHEMA_ID:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "unsupported RCSB target-annotation snapshot schema"
            )
        if _canonical_sha256(POSEBUSTERS_RCSB_GRAPHQL_QUERY) != (
            POSEBUSTERS_RCSB_GRAPHQL_QUERY_SHA256
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "frozen RCSB GraphQL query was mutated"
            )
        observed = _utc_timestamp(self.observation_utc)
        tool_identity = _bounded_text(
            self.retrieval_tool_identity,
            name="RCSB retrieval tool identity",
            maximum=256,
        )
        tool_sha = _digest(
            self.retrieval_tool_sha256,
            name="RCSB retrieval tool",
        )
        batches = tuple(self.request_batches)
        entries = tuple(self.entries)
        if (
            not batches
            or any(not isinstance(row, PoseBustersRcsbRequestBatch) for row in batches)
            or tuple(row.batch_index for row in batches) != tuple(range(len(batches)))
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB request batches must be contiguous and ordered"
            )
        if (
            not entries
            or len(entries) > POSEBUSTERS_RCSB_TARGET_FAMILY_MAX_CASES
            or any(not isinstance(row, PoseBustersRcsbTargetEntry) for row in entries)
            or tuple(row.pdb_id for row in entries)
            != tuple(sorted(row.pdb_id for row in entries))
            or len({row.pdb_id for row in entries}) != len(entries)
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB target entries must be bounded, unique, and ordered"
            )
        requested = tuple(
            pdb_id for batch in batches for pdb_id in batch.requested_pdb_ids
        )
        if len(requested) != len(set(requested)) or set(requested) != {
            row.pdb_id for row in entries
        }:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB request batches do not partition target entries"
            )
        entries_by_id = {row.pdb_id: row for row in entries}
        for batch in batches:
            active_rows = tuple(
                entries_by_id[pdb_id]
                for pdb_id in batch.requested_pdb_ids
                if entries_by_id[pdb_id].status == "active"
            )
            if tuple(row.pdb_id for row in active_rows) != (
                batch.returned_active_pdb_ids
            ) or _canonical_sha256([row.to_dict() for row in active_rows]) != (
                batch.normalized_response_sha256
            ):
                raise PoseBustersRcsbTargetFamilyBindingError(
                    "RCSB normalized request-batch evidence is inconsistent"
                )
        object.__setattr__(self, "observation_utc", observed)
        object.__setattr__(self, "retrieval_tool_identity", tool_identity)
        object.__setattr__(self, "retrieval_tool_sha256", tool_sha)
        object.__setattr__(self, "request_batches", batches)
        object.__setattr__(self, "entries", entries)

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "observation_utc": self.observation_utc,
            "source_graphql_endpoint": POSEBUSTERS_RCSB_GRAPHQL_ENDPOINT,
            "source_holdings_endpoint": POSEBUSTERS_RCSB_HOLDINGS_ENDPOINT,
            "graphql_query_sha256": POSEBUSTERS_RCSB_GRAPHQL_QUERY_SHA256,
            "retrieval_tool_identity": self.retrieval_tool_identity,
            "retrieval_tool_sha256": self.retrieval_tool_sha256,
            "normalizer_source_sha256": _source_file_sha256(__file__),
            "raw_response_persisted": False,
            "source_response_signature_present": False,
            "request_batch_count": len(self.request_batches),
            "requested_pdb_count": len(self.entries),
            "active_entry_count": sum(row.status == "active" for row in self.entries),
            "removed_entry_count": sum(row.status == "removed" for row in self.entries),
            "missing_entry_count": sum(row.status == "missing" for row in self.entries),
            "request_batches": [row.to_dict() for row in self.request_batches],
            "entries": [row.to_dict() for row in self.entries],
            "official_source_observation": True,
            "independently_signed_by_source": False,
            "scientifically_validated": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "receipt_sha256": self.fingerprint_sha256}

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        return _atomic_write_new(
            output_path,
            self.to_dict(),
            maximum_bytes=POSEBUSTERS_RCSB_TARGET_FAMILY_MAX_SNAPSHOT_BYTES,
            label="RCSB target-annotation snapshot",
        )


def _required_mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PoseBustersRcsbTargetFamilyBindingError(f"{name} must be an object")
    return value


def _required_list(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PoseBustersRcsbTargetFamilyBindingError(f"{name} must be a list")
    return value


def _reference_from_dict(raw: object) -> PoseBustersRcsbReferenceSequence:
    row = _required_mapping(raw, name="RCSB reference row")
    return PoseBustersRcsbReferenceSequence(
        database_name=row.get("database_name"),
        database_accession=row.get("database_accession"),
        provenance_source=row.get("provenance_source"),
        entity_sequence_coverage_hex=row.get(
            "entity_sequence_coverage_binary64_hex"
        ),
        reference_sequence_coverage_hex=row.get(
            "reference_sequence_coverage_binary64_hex"
        ),
        schema_id=row.get("schema_id"),
    )


def _pfam_annotation_from_dict(raw: object) -> PoseBustersRcsbPfamAnnotation:
    row = _required_mapping(raw, name="RCSB Pfam annotation row")
    return PoseBustersRcsbPfamAnnotation(
        annotation_id=row.get("annotation_id"),
        name=row.get("name"),
        provenance_source=row.get("provenance_source"),
        assignment_version=row.get("assignment_version"),
        schema_id=row.get("schema_id"),
    )


def _polymer_entity_from_dict(raw: object) -> PoseBustersRcsbPolymerEntity:
    row = _required_mapping(raw, name="RCSB polymer-entity row")
    return PoseBustersRcsbPolymerEntity(
        rcsb_entity_id=row.get("rcsb_entity_id"),
        entity_id=row.get("entity_id"),
        asym_ids=tuple(_required_list(row.get("asym_ids"), name="RCSB asym IDs")),
        auth_asym_ids=tuple(
            _required_list(row.get("auth_asym_ids"), name="RCSB auth asym IDs")
        ),
        uniprot_ids=tuple(
            _required_list(row.get("uniprot_ids"), name="RCSB UniProt IDs")
        ),
        reference_sequences=tuple(
            _reference_from_dict(item)
            for item in _required_list(
                row.get("reference_sequences"),
                name="RCSB reference sequences",
            )
        ),
        pfam_annotations=tuple(
            _pfam_annotation_from_dict(item)
            for item in _required_list(
                row.get("pfam_annotations"),
                name="RCSB Pfam annotations",
            )
        ),
        schema_id=row.get("schema_id"),
    )


def _target_entry_from_dict(raw: object) -> PoseBustersRcsbTargetEntry:
    row = _required_mapping(raw, name="RCSB target-entry row")
    return PoseBustersRcsbTargetEntry(
        pdb_id=row.get("pdb_id"),
        status=row.get("status"),
        polymer_entities=tuple(
            _polymer_entity_from_dict(item)
            for item in _required_list(
                row.get("polymer_entities"),
                name="RCSB polymer entities",
            )
        ),
        disposition_code=row.get("disposition_code"),
        disposition_date=row.get("disposition_date"),
        disposition_reason=row.get("disposition_reason"),
        replacement_pdb_ids=tuple(
            _required_list(
                row.get("replacement_pdb_ids"),
                name="RCSB replacement PDB IDs",
            )
        ),
        schema_id=row.get("schema_id"),
    )


def _request_batch_from_dict(raw: object) -> PoseBustersRcsbRequestBatch:
    row = _required_mapping(raw, name="RCSB request-batch row")
    return PoseBustersRcsbRequestBatch(
        batch_index=row.get("batch_index"),
        requested_pdb_ids=tuple(
            _required_list(
                row.get("requested_pdb_ids"),
                name="requested RCSB PDB IDs",
            )
        ),
        returned_active_pdb_ids=tuple(
            _required_list(
                row.get("returned_active_pdb_ids"),
                name="returned active RCSB PDB IDs",
            )
        ),
        normalized_response_sha256=row.get("normalized_response_sha256"),
        http_status_code=row.get("http_status_code"),
        schema_id=row.get("schema_id"),
    )


def load_posebusters_rcsb_target_annotation_snapshot(
    snapshot_path: str | os.PathLike[str],
    *,
    expected_snapshot_sha256: str,
) -> PoseBustersRcsbTargetAnnotationSnapshot:
    """Load one exact canonical normalized RCSB observation without networking."""

    expected_sha = _digest(
        expected_snapshot_sha256,
        name="expected RCSB target-annotation snapshot",
    )
    try:
        source = _read_exact_regular_file(
            snapshot_path,
            maximum_bytes=POSEBUSTERS_RCSB_TARGET_FAMILY_MAX_SNAPSHOT_BYTES,
        )
        metadata = Path(snapshot_path).stat(follow_symlinks=False)
    except (PoseBustersArchiveIntakeError, OSError) as exc:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB target-annotation snapshot could not be read securely"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB target-annotation snapshot must remain mode 0600"
        )
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB target-annotation snapshot is not canonical JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB target-annotation snapshot bytes are not canonical"
        )
    snapshot = PoseBustersRcsbTargetAnnotationSnapshot(
        observation_utc=raw.get("observation_utc"),
        retrieval_tool_identity=raw.get("retrieval_tool_identity"),
        retrieval_tool_sha256=raw.get("retrieval_tool_sha256"),
        request_batches=tuple(
            _request_batch_from_dict(item)
            for item in _required_list(
                raw.get("request_batches"),
                name="RCSB request batches",
            )
        ),
        entries=tuple(
            _target_entry_from_dict(item)
            for item in _required_list(raw.get("entries"), name="RCSB entries")
        ),
        schema_id=raw.get("schema_id"),
    )
    if snapshot.to_dict() != raw or snapshot.fingerprint_sha256 != expected_sha:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB target-annotation snapshot contract or identity is invalid"
        )
    return snapshot


def _chain_ids(values: Iterable[object], *, name: str) -> tuple[str, ...]:
    rows = tuple(sorted(_bounded_text(value, name=name, maximum=1) for value in values))
    if len(rows) != len(set(rows)):
        raise PoseBustersRcsbTargetFamilyBindingError(f"{name} values repeat")
    return rows


def _pfam_set_id(pfam_ids: Sequence[str]) -> str:
    ids = tuple(pfam_ids)
    if not ids:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "Pfam-set identity requires at least one Pfam ID"
        )
    return f"pfam_set_{_canonical_sha256({'pfam_ids': list(ids)})}"


@dataclass(frozen=True, slots=True)
class PoseBustersRcsbTargetCase:
    case_id: str
    pdb_id: str
    receptor_sha256: str
    reference_ligand_sha256: str
    pocket_chain_ids: tuple[str, ...]
    mapping_status: str
    mapped_entity_ids: tuple[str, ...]
    unmapped_chain_ids: tuple[str, ...]
    ambiguous_chain_ids: tuple[str, ...]
    uniprot_ids: tuple[str, ...]
    pfam_ids: tuple[str, ...]
    pfam_set_id: str | None
    annotation_status: str
    schema_id: str = POSEBUSTERS_RCSB_TARGET_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_RCSB_TARGET_CASE_SCHEMA_ID:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "unsupported RCSB target-case schema"
            )
        case = _case_id(self.case_id)
        pdb = _pdb_id(self.pdb_id)
        if case.split("_", 1)[0].upper() != pdb:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "target-case PDB ID is inconsistent"
            )
        receptor_sha = _digest(self.receptor_sha256, name="target receptor")
        ligand_sha = _digest(
            self.reference_ligand_sha256,
            name="target reference ligand",
        )
        pocket = _chain_ids(self.pocket_chain_ids, name="pocket chain ID")
        if not pocket:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "target case must have a pocket-associated chain"
            )
        mapping = _token(self.mapping_status, name="RCSB chain-mapping status")
        if mapping not in _MAPPING_STATUSES:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB chain-mapping status is invalid"
            )
        entities = _unique_sorted_text(
            self.mapped_entity_ids,
            name="mapped RCSB entity ID",
            maximum=32,
        )
        unmapped = _chain_ids(self.unmapped_chain_ids, name="unmapped chain ID")
        ambiguous = _chain_ids(
            self.ambiguous_chain_ids,
            name="ambiguous chain ID",
        )
        if not set((*unmapped, *ambiguous)).issubset(pocket) or set(unmapped) & set(
            ambiguous
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "target-case chain dispositions are inconsistent"
            )
        uniprot = _unique_sorted_text(
            self.uniprot_ids,
            name="case UniProt ID",
            maximum=32,
        )
        pfam = _unique_sorted_text(
            self.pfam_ids,
            name="case Pfam ID",
            maximum=32,
        )
        if any(not value.startswith("PF") or not value[2:].isdigit() for value in pfam):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "target-case Pfam ID is invalid"
            )
        set_id = self.pfam_set_id
        expected_set = _pfam_set_id(pfam) if pfam else None
        if set_id != expected_set:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "target-case Pfam-set identity is inconsistent"
            )
        annotation = _token(
            self.annotation_status,
            name="RCSB target annotation status",
        )
        if annotation not in _ANNOTATION_STATUSES:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB target annotation status is invalid"
            )
        if mapping == "complete":
            valid = (
                bool(entities)
                and not unmapped
                and not ambiguous
                and annotation != "not_applicable"
                and ((annotation == "pfam_annotated") == bool(pfam))
                and (
                    annotation != "uniprot_without_pfam"
                    or (bool(uniprot) and not pfam)
                )
                and (
                    annotation != "entity_without_uniprot_or_pfam"
                    or (not uniprot and not pfam)
                )
            )
        else:
            valid = (
                annotation == "not_applicable"
                and not uniprot
                and not pfam
                and set_id is None
                and (
                    (mapping == "pocket_chain_unmapped" and bool(unmapped))
                    or (mapping == "pocket_chain_ambiguous" and bool(ambiguous))
                    or (
                        mapping in {"rcsb_entry_removed", "rcsb_entry_missing"}
                        and not entities
                        and not unmapped
                        and not ambiguous
                    )
                )
            )
        if not valid:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "target-case mapping and annotation disposition is inconsistent"
            )
        object.__setattr__(self, "case_id", case)
        object.__setattr__(self, "pdb_id", pdb)
        object.__setattr__(self, "receptor_sha256", receptor_sha)
        object.__setattr__(self, "reference_ligand_sha256", ligand_sha)
        object.__setattr__(self, "pocket_chain_ids", pocket)
        object.__setattr__(self, "mapping_status", mapping)
        object.__setattr__(self, "mapped_entity_ids", entities)
        object.__setattr__(self, "unmapped_chain_ids", unmapped)
        object.__setattr__(self, "ambiguous_chain_ids", ambiguous)
        object.__setattr__(self, "uniprot_ids", uniprot)
        object.__setattr__(self, "pfam_ids", pfam)
        object.__setattr__(self, "annotation_status", annotation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "pdb_id": self.pdb_id,
            "receptor_sha256": self.receptor_sha256,
            "reference_ligand_sha256": self.reference_ligand_sha256,
            "pocket_chain_ids": list(self.pocket_chain_ids),
            "mapping_status": self.mapping_status,
            "mapped_entity_ids": list(self.mapped_entity_ids),
            "unmapped_chain_ids": list(self.unmapped_chain_ids),
            "ambiguous_chain_ids": list(self.ambiguous_chain_ids),
            "uniprot_ids": list(self.uniprot_ids),
            "pfam_ids": list(self.pfam_ids),
            "pfam_set_id": self.pfam_set_id,
            "annotation_status": self.annotation_status,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersRcsbPfamFamily:
    pfam_id: str
    names: tuple[str, ...]
    provenance_sources: tuple[str, ...]
    assignment_versions: tuple[str, ...]
    member_case_ids: tuple[str, ...]
    schema_id: str = POSEBUSTERS_RCSB_PFAM_FAMILY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_RCSB_PFAM_FAMILY_SCHEMA_ID:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "unsupported RCSB Pfam-family schema"
            )
        pfam = _bounded_text(self.pfam_id, name="Pfam family ID", maximum=32).upper()
        if not pfam.startswith("PF") or not pfam[2:].isdigit():
            raise PoseBustersRcsbTargetFamilyBindingError("Pfam family ID is invalid")
        names = _unique_sorted_text(self.names, name="Pfam family name", maximum=256)
        provenance = _unique_sorted_text(
            self.provenance_sources,
            name="Pfam family provenance",
            maximum=128,
        )
        versions = _unique_sorted_text(
            self.assignment_versions,
            name="Pfam assignment version",
            maximum=64,
        )
        members = tuple(sorted(_case_id(value) for value in self.member_case_ids))
        if not names or not provenance or not versions or not members or len(members) != len(set(members)):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "Pfam family metadata and members must be populated and unique"
            )
        object.__setattr__(self, "pfam_id", pfam)
        object.__setattr__(self, "names", names)
        object.__setattr__(self, "provenance_sources", provenance)
        object.__setattr__(self, "assignment_versions", versions)
        object.__setattr__(self, "member_case_ids", members)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "pfam_id": self.pfam_id,
            "names": list(self.names),
            "provenance_sources": list(self.provenance_sources),
            "assignment_versions": list(self.assignment_versions),
            "member_case_count": len(self.member_case_ids),
            "member_case_ids": list(self.member_case_ids),
        }


@dataclass(frozen=True, slots=True)
class PoseBustersRcsbPfamSet:
    pfam_set_id: str
    pfam_ids: tuple[str, ...]
    member_case_ids: tuple[str, ...]
    schema_id: str = POSEBUSTERS_RCSB_PFAM_SET_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_RCSB_PFAM_SET_SCHEMA_ID:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "unsupported RCSB Pfam-set schema"
            )
        pfam_ids = _unique_sorted_text(
            self.pfam_ids,
            name="Pfam-set family ID",
            maximum=32,
        )
        set_id = _bounded_text(
            self.pfam_set_id,
            name="Pfam-set ID",
            maximum=80,
        )
        if set_id != _pfam_set_id(pfam_ids):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "Pfam-set ID is inconsistent"
            )
        members = tuple(sorted(_case_id(value) for value in self.member_case_ids))
        if not members or len(members) != len(set(members)):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "Pfam-set members must be populated and unique"
            )
        object.__setattr__(self, "pfam_set_id", set_id)
        object.__setattr__(self, "pfam_ids", pfam_ids)
        object.__setattr__(self, "member_case_ids", members)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "pfam_set_id": self.pfam_set_id,
            "pfam_ids": list(self.pfam_ids),
            "member_case_count": len(self.member_case_ids),
            "member_case_ids": list(self.member_case_ids),
        }


@dataclass(frozen=True, slots=True)
class PoseBustersRcsbEngineFamily:
    engine_id: str
    family_kind: str
    family_id: str
    member_case_count: int
    execution_success_case_count: int
    top_1_rmsd_hit_case_count: int
    top_5_rmsd_hit_case_count: int
    top_1_valid_rmsd_hit_case_count: int
    top_5_valid_rmsd_hit_case_count: int
    schema_id: str = POSEBUSTERS_RCSB_ENGINE_FAMILY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_RCSB_ENGINE_FAMILY_SCHEMA_ID:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "unsupported RCSB engine-family schema"
            )
        engine = _token(self.engine_id, name="RCSB target-family engine")
        if engine not in POSEBUSTERS_TARGET_CLUSTER_ENGINES:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB target-family engine is invalid"
            )
        kind = _token(self.family_kind, name="RCSB target family kind")
        if kind not in _FAMILY_KINDS:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB target family kind is invalid"
            )
        family = _bounded_text(
            self.family_id,
            name="RCSB target family ID",
            maximum=80,
        )
        member_count = _positive_int(
            self.member_case_count,
            name="RCSB target-family member count",
        )
        counts = tuple(
            _nonnegative_int(getattr(self, name), name=name)
            for name in (
                "execution_success_case_count",
                "top_1_rmsd_hit_case_count",
                "top_5_rmsd_hit_case_count",
                "top_1_valid_rmsd_hit_case_count",
                "top_5_valid_rmsd_hit_case_count",
            )
        )
        success, top1, top5, valid1, valid5 = counts
        if (
            success > member_count
            or any(value > success for value in counts[1:])
            or top1 > top5
            or valid1 > valid5
            or valid1 > top1
            or valid5 > top5
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB engine-family counts are inconsistent"
            )
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "family_kind", kind)
        object.__setattr__(self, "family_id", family)
        object.__setattr__(self, "member_case_count", member_count)
        for name, value in zip(
            (
                "execution_success_case_count",
                "top_1_rmsd_hit_case_count",
                "top_5_rmsd_hit_case_count",
                "top_1_valid_rmsd_hit_case_count",
                "top_5_valid_rmsd_hit_case_count",
            ),
            counts,
        ):
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "engine_id": self.engine_id,
            "family_kind": self.family_kind,
            "family_id": self.family_id,
            "member_case_count": self.member_case_count,
            "execution_success_case_count": self.execution_success_case_count,
            "top_1_rmsd_hit_case_count": self.top_1_rmsd_hit_case_count,
            "top_5_rmsd_hit_case_count": self.top_5_rmsd_hit_case_count,
            "top_1_valid_rmsd_hit_case_count": self.top_1_valid_rmsd_hit_case_count,
            "top_5_valid_rmsd_hit_case_count": self.top_5_valid_rmsd_hit_case_count,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersRcsbTargetMetric:
    engine_id: str | None
    family_kind: str
    family_id: str
    metric_id: str
    denominator_scope: str
    numerator: int
    denominator: int
    estimate: float
    confidence_interval_low: float
    confidence_interval_high: float
    schema_id: str = POSEBUSTERS_RCSB_TARGET_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_RCSB_TARGET_METRIC_SCHEMA_ID:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "unsupported RCSB target-metric schema"
            )
        engine: str | None
        if self.engine_id is None:
            engine = None
        else:
            engine = _token(self.engine_id, name="RCSB target-metric engine")
            if engine not in POSEBUSTERS_TARGET_CLUSTER_ENGINES:
                raise PoseBustersRcsbTargetFamilyBindingError(
                    "RCSB target-metric engine is invalid"
                )
        kind = _token(self.family_kind, name="RCSB target-metric family kind")
        if kind not in {*_FAMILY_KINDS, "all_case_annotation"}:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB target-metric family kind is invalid"
            )
        if (kind == "all_case_annotation") != (engine is None):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB target-metric engine and family kind are inconsistent"
            )
        family = _bounded_text(
            self.family_id,
            name="RCSB target-metric family ID",
            maximum=80,
        )
        metric = _token(self.metric_id, name="RCSB target metric")
        scope = _token(
            self.denominator_scope,
            name="RCSB target-metric denominator scope",
        )
        numerator = _nonnegative_int(self.numerator, name="RCSB metric numerator")
        denominator = _positive_int(
            self.denominator,
            name="RCSB metric denominator",
        )
        values = (
            float(self.estimate),
            float(self.confidence_interval_low),
            float(self.confidence_interval_high),
        )
        if (
            numerator > denominator
            or any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in values)
            or not values[1] <= values[0] <= values[2]
            or not math.isclose(values[0], numerator / denominator, abs_tol=1.0e-15)
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB target metric is inconsistent"
            )
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "family_kind", kind)
        object.__setattr__(self, "family_id", family)
        object.__setattr__(self, "metric_id", metric)
        object.__setattr__(self, "denominator_scope", scope)
        object.__setattr__(self, "numerator", numerator)
        object.__setattr__(self, "denominator", denominator)
        object.__setattr__(self, "estimate", values[0])
        object.__setattr__(self, "confidence_interval_low", values[1])
        object.__setattr__(self, "confidence_interval_high", values[2])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "engine_id": self.engine_id,
            "family_kind": self.family_kind,
            "family_id": self.family_id,
            "metric_id": self.metric_id,
            "denominator_scope": self.denominator_scope,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "estimate": self.estimate,
            "confidence_level": POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIDENCE_LEVEL,
            "confidence_interval_method": "wilson_score_binomial",
            "confidence_interval_low": self.confidence_interval_low,
            "confidence_interval_high": self.confidence_interval_high,
        }


def _metric(
    engine_id: str | None,
    family_kind: str,
    family_id: str,
    metric_id: str,
    denominator_scope: str,
    numerator: int,
    denominator: int,
) -> PoseBustersRcsbTargetMetric:
    proportion = numerator / denominator
    z2 = POSEBUSTERS_RCSB_TARGET_FAMILY_Z**2
    scale = 1.0 + z2 / denominator
    center = (proportion + z2 / (2.0 * denominator)) / scale
    radius = (
        POSEBUSTERS_RCSB_TARGET_FAMILY_Z
        * math.sqrt(
            proportion * (1.0 - proportion) / denominator
            + z2 / (4.0 * denominator**2)
        )
        / scale
    )
    return PoseBustersRcsbTargetMetric(
        engine_id=engine_id,
        family_kind=family_kind,
        family_id=family_id,
        metric_id=metric_id,
        denominator_scope=denominator_scope,
        numerator=numerator,
        denominator=denominator,
        estimate=proportion,
        confidence_interval_low=min(proportion, max(0.0, center - radius)),
        confidence_interval_high=max(proportion, min(1.0, center + radius)),
    )


@dataclass(frozen=True, slots=True)
class PoseBustersRcsbLeakageDisposition:
    engine_id: str
    fit_or_training_manifest_status: str = "missing"
    target_sequence_leakage_status: str = "not_evaluated"
    ligand_scaffold_leakage_status: str = "not_evaluated"
    leakage_control_passed: bool = False
    schema_id: str = POSEBUSTERS_RCSB_LEAKAGE_DISPOSITION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_RCSB_LEAKAGE_DISPOSITION_SCHEMA_ID:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "unsupported RCSB leakage-disposition schema"
            )
        engine = _token(self.engine_id, name="RCSB leakage engine")
        if engine not in POSEBUSTERS_TARGET_CLUSTER_ENGINES:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB leakage engine is invalid"
            )
        if (
            self.fit_or_training_manifest_status != "missing"
            or self.target_sequence_leakage_status != "not_evaluated"
            or self.ligand_scaffold_leakage_status != "not_evaluated"
            or self.leakage_control_passed is not False
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB leakage disposition must remain fail-closed"
            )
        object.__setattr__(self, "engine_id", engine)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "engine_id": self.engine_id,
            "fit_or_training_manifest_status": self.fit_or_training_manifest_status,
            "target_sequence_leakage_status": self.target_sequence_leakage_status,
            "ligand_scaffold_leakage_status": self.ligand_scaffold_leakage_status,
            "leakage_control_passed": self.leakage_control_passed,
        }


def _metrics_for_receipt(
    cases: Sequence[PoseBustersRcsbTargetCase],
    engine_families: Sequence[PoseBustersRcsbEngineFamily],
) -> tuple[PoseBustersRcsbTargetMetric, ...]:
    denominator = len(cases)
    mapping_complete = sum(row.mapping_status == "complete" for row in cases)
    uniprot = sum(bool(row.uniprot_ids) for row in cases)
    pfam = sum(bool(row.pfam_ids) for row in cases)
    removed = sum(row.mapping_status == "rcsb_entry_removed" for row in cases)
    mapping_failure = sum(
        row.mapping_status in {"pocket_chain_unmapped", "pocket_chain_ambiguous"}
        for row in cases
    )
    rows: list[PoseBustersRcsbTargetMetric] = [
        _metric(
            None,
            "all_case_annotation",
            "all_cases",
            metric_id,
            scope,
            numerator,
            metric_denominator,
        )
        for metric_id, scope, numerator, metric_denominator in (
            (
                "pocket_chain_mapping_complete_rate",
                "all_cases",
                mapping_complete,
                denominator,
            ),
            ("uniprot_annotation_case_rate", "all_cases", uniprot, denominator),
            ("pfam_annotation_case_rate", "all_cases", pfam, denominator),
            (
                "pfam_annotation_rate_among_mapping_complete_cases",
                "mapping_complete_cases",
                pfam,
                mapping_complete,
            ),
            ("removed_rcsb_entry_rate", "all_cases", removed, denominator),
            ("pocket_chain_mapping_failure_rate", "all_cases", mapping_failure, denominator),
        )
    ]
    for family in engine_families:
        counts = (
            (
                "execution_coverage_rate",
                family.execution_success_case_count,
            ),
            (
                "top_1_rmsd_hit_rate_all_family_members",
                family.top_1_rmsd_hit_case_count,
            ),
            (
                "top_5_rmsd_hit_rate_all_family_members",
                family.top_5_rmsd_hit_case_count,
            ),
            (
                "top_1_valid_rmsd_hit_rate_all_family_members",
                family.top_1_valid_rmsd_hit_case_count,
            ),
            (
                "top_5_valid_rmsd_hit_rate_all_family_members",
                family.top_5_valid_rmsd_hit_case_count,
            ),
        )
        rows.extend(
            _metric(
                family.engine_id,
                family.family_kind,
                family.family_id,
                metric_id,
                "family_all_members",
                numerator,
                family.member_case_count,
            )
            for metric_id, numerator in counts
        )
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class PoseBustersRcsbTargetFamilyReceipt:
    archive_intake_receipt_sha256: str
    target_cluster_receipt_sha256: str
    annotation_snapshot_sha256: str
    annotation_observation_utc: str
    configuration_sha256: str
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    case_rows: tuple[PoseBustersRcsbTargetCase, ...]
    pfam_family_rows: tuple[PoseBustersRcsbPfamFamily, ...]
    pfam_set_rows: tuple[PoseBustersRcsbPfamSet, ...]
    engine_family_rows: tuple[PoseBustersRcsbEngineFamily, ...]
    metrics: tuple[PoseBustersRcsbTargetMetric, ...]
    leakage_dispositions: tuple[PoseBustersRcsbLeakageDisposition, ...]
    schema_id: str = POSEBUSTERS_RCSB_TARGET_FAMILY_RECEIPT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_RCSB_TARGET_FAMILY_RECEIPT_SCHEMA_ID:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "unsupported RCSB target-family receipt schema"
            )
        intake_sha = _digest(
            self.archive_intake_receipt_sha256,
            name="RCSB target-family archive intake",
        )
        target_cluster_sha = _digest(
            self.target_cluster_receipt_sha256,
            name="RCSB target-family target-cluster receipt",
        )
        snapshot_sha = _digest(
            self.annotation_snapshot_sha256,
            name="RCSB target-family annotation snapshot",
        )
        observed = _utc_timestamp(self.annotation_observation_utc)
        configuration_sha = _digest(
            self.configuration_sha256,
            name="RCSB target-family configuration",
        )
        if configuration_sha != POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIGURATION_SHA256:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB target-family configuration identity is invalid"
            )
        source_members = tuple(self.implementation_source_members)
        if (
            not source_members
            or tuple(role for role, _sha in source_members)
            != tuple(sorted(role for role, _sha in source_members))
            or len({role for role, _sha in source_members}) != len(source_members)
            or any(
                not _bounded_text(role, name="implementation source role", maximum=80)
                or _digest(sha, name=f"implementation source {role}") != sha
                for role, sha in source_members
            )
            or _canonical_sha256(dict(source_members))
            != _digest(
                self.implementation_source_sha256,
                name="RCSB target-family implementation source",
            )
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB target-family source identity is invalid"
            )
        cases = tuple(self.case_rows)
        pfam_families = tuple(self.pfam_family_rows)
        pfam_sets = tuple(self.pfam_set_rows)
        engine_families = tuple(self.engine_family_rows)
        metrics = tuple(self.metrics)
        leakage = tuple(self.leakage_dispositions)
        if (
            not cases
            or len(cases) > POSEBUSTERS_RCSB_TARGET_FAMILY_MAX_CASES
            or any(not isinstance(row, PoseBustersRcsbTargetCase) for row in cases)
            or tuple(row.case_id for row in cases)
            != tuple(sorted(row.case_id for row in cases))
            or len({row.case_id for row in cases}) != len(cases)
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB target-family cases must be bounded, unique, and ordered"
            )
        if (
            any(not isinstance(row, PoseBustersRcsbPfamFamily) for row in pfam_families)
            or tuple(row.pfam_id for row in pfam_families)
            != tuple(sorted(row.pfam_id for row in pfam_families))
            or any(not isinstance(row, PoseBustersRcsbPfamSet) for row in pfam_sets)
            or tuple(row.pfam_set_id for row in pfam_sets)
            != tuple(sorted(row.pfam_set_id for row in pfam_sets))
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB Pfam family rows are not canonically ordered"
            )
        expected_family_members = {
            pfam_id: tuple(row.case_id for row in cases if pfam_id in row.pfam_ids)
            for pfam_id in sorted({value for row in cases for value in row.pfam_ids})
        }
        if {
            row.pfam_id: row.member_case_ids for row in pfam_families
        } != expected_family_members:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB Pfam family membership is inconsistent"
            )
        expected_set_members = {
            set_id: tuple(row.case_id for row in cases if row.pfam_set_id == set_id)
            for set_id in sorted(
                {row.pfam_set_id for row in cases if row.pfam_set_id is not None}
            )
        }
        if {row.pfam_set_id: row.member_case_ids for row in pfam_sets} != (
            expected_set_members
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB Pfam-set membership is inconsistent"
            )
        if any(
            not isinstance(row, PoseBustersRcsbEngineFamily)
            for row in engine_families
        ) or tuple(
            (row.engine_id, row.family_kind, row.family_id) for row in engine_families
        ) != tuple(
            sorted(
                (row.engine_id, row.family_kind, row.family_id)
                for row in engine_families
            )
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB engine-family rows are not canonically ordered"
            )
        expected_metrics = _metrics_for_receipt(cases, engine_families)
        if tuple(row.to_dict() for row in metrics) != tuple(
            row.to_dict() for row in expected_metrics
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB target-family metrics are inconsistent"
            )
        if tuple(row.engine_id for row in leakage) != (
            POSEBUSTERS_TARGET_CLUSTER_ENGINES
        ):
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB leakage dispositions must cover all engines"
            )
        object.__setattr__(self, "archive_intake_receipt_sha256", intake_sha)
        object.__setattr__(self, "target_cluster_receipt_sha256", target_cluster_sha)
        object.__setattr__(self, "annotation_snapshot_sha256", snapshot_sha)
        object.__setattr__(self, "annotation_observation_utc", observed)
        object.__setattr__(self, "configuration_sha256", configuration_sha)
        object.__setattr__(self, "implementation_source_members", source_members)
        object.__setattr__(self, "case_rows", cases)
        object.__setattr__(self, "pfam_family_rows", pfam_families)
        object.__setattr__(self, "pfam_set_rows", pfam_sets)
        object.__setattr__(self, "engine_family_rows", engine_families)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "leakage_dispositions", leakage)

    def _payload(self) -> dict[str, Any]:
        pfam_sizes = tuple(len(row.member_case_ids) for row in self.pfam_family_rows)
        set_sizes = tuple(len(row.member_case_ids) for row in self.pfam_set_rows)
        return {
            "schema_id": self.schema_id,
            "archive_intake_receipt_sha256": self.archive_intake_receipt_sha256,
            "target_cluster_receipt_sha256": self.target_cluster_receipt_sha256,
            "annotation_snapshot_sha256": self.annotation_snapshot_sha256,
            "annotation_observation_utc": self.annotation_observation_utc,
            "configuration": POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIGURATION,
            "configuration_sha256": self.configuration_sha256,
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": dict(self.implementation_source_members),
            "all_case_denominator": len(self.case_rows),
            "mapping_complete_case_count": sum(
                row.mapping_status == "complete" for row in self.case_rows
            ),
            "uniprot_annotated_case_count": sum(bool(row.uniprot_ids) for row in self.case_rows),
            "pfam_annotated_case_count": sum(bool(row.pfam_ids) for row in self.case_rows),
            "rcsb_removed_case_count": sum(
                row.mapping_status == "rcsb_entry_removed" for row in self.case_rows
            ),
            "pocket_chain_mapping_failure_case_count": sum(
                row.mapping_status in {"pocket_chain_unmapped", "pocket_chain_ambiguous"}
                for row in self.case_rows
            ),
            "pfam_multi_label_family_count": len(self.pfam_family_rows),
            "repeated_pfam_family_count": sum(size > 1 for size in pfam_sizes),
            "maximum_pfam_family_size": max(pfam_sizes, default=0),
            "exact_pfam_set_count": len(self.pfam_set_rows),
            "repeated_exact_pfam_set_count": sum(size > 1 for size in set_sizes),
            "maximum_exact_pfam_set_size": max(set_sizes, default=0),
            "case_rows": [row.to_dict() for row in self.case_rows],
            "pfam_family_rows": [row.to_dict() for row in self.pfam_family_rows],
            "pfam_set_rows": [row.to_dict() for row in self.pfam_set_rows],
            "engine_family_rows": [row.to_dict() for row in self.engine_family_rows],
            "metrics": [row.to_dict() for row in self.metrics],
            "leakage_dispositions": [
                row.to_dict() for row in self.leakage_dispositions
            ],
            "pocket_associated_rcsb_pfam_annotations_present": True,
            "complete_target_family_annotation_coverage": False,
            "target_family_metrics_present": True,
            "external_fit_training_leakage_audit_present": False,
            "leakage_control_passed": False,
            "new_benchmark_execution_performed": False,
            "public_benchmark_claim_authorized": False,
            "scientific_blockers": list(
                POSEBUSTERS_RCSB_TARGET_FAMILY_SCIENTIFIC_BLOCKERS
            ),
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "receipt_sha256": self.fingerprint_sha256}

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        return _atomic_write_new(
            output_path,
            self.to_dict(),
            maximum_bytes=POSEBUSTERS_RCSB_TARGET_FAMILY_MAX_RECEIPT_BYTES,
            label="RCSB target-family receipt",
        )


def normalize_rcsb_graphql_target_entry(raw_entry: object) -> PoseBustersRcsbTargetEntry:
    """Normalize one active RCSB GraphQL entry without retaining raw response data."""

    raw = _required_mapping(raw_entry, name="raw RCSB GraphQL entry")
    pdb = _pdb_id(raw.get("rcsb_id"))
    entities: list[PoseBustersRcsbPolymerEntity] = []
    for raw_entity in _required_list(
        raw.get("polymer_entities"),
        name="raw RCSB polymer entities",
    ):
        entity_row = _required_mapping(raw_entity, name="raw RCSB polymer entity")
        container = _required_mapping(
            entity_row.get("rcsb_polymer_entity_container_identifiers"),
            name="raw RCSB polymer identifiers",
        )
        if _pdb_id(container.get("entry_id")) != pdb:
            raise PoseBustersRcsbTargetFamilyBindingError(
                "raw RCSB entity entry ID is inconsistent"
            )
        references: list[PoseBustersRcsbReferenceSequence] = []
        for raw_reference in container.get("reference_sequence_identifiers") or []:
            reference = _required_mapping(
                raw_reference,
                name="raw RCSB reference identifier",
            )
            database_name = str(reference.get("database_name") or "")
            if "uniprot" not in database_name.lower():
                continue
            entity_coverage = reference.get("entity_sequence_coverage")
            reference_coverage = reference.get("reference_sequence_coverage")
            references.append(
                PoseBustersRcsbReferenceSequence(
                    database_name=database_name,
                    database_accession=str(
                        reference.get("database_accession") or ""
                    ),
                    provenance_source=str(
                        reference.get("provenance_source") or ""
                    ),
                    entity_sequence_coverage_hex=(
                        None
                        if entity_coverage is None
                        else float(entity_coverage).hex()
                    ),
                    reference_sequence_coverage_hex=(
                        None
                        if reference_coverage is None
                        else float(reference_coverage).hex()
                    ),
                )
            )
        reference_by_payload = {
            _canonical_sha256(row.to_dict()): row for row in references
        }
        references = sorted(
            reference_by_payload.values(),
            key=lambda row: (
                row.database_name,
                row.database_accession,
                row.provenance_source,
            ),
        )
        pfam_by_id: dict[str, PoseBustersRcsbPfamAnnotation] = {}
        for raw_annotation in entity_row.get("rcsb_polymer_entity_annotation") or []:
            annotation = _required_mapping(
                raw_annotation,
                name="raw RCSB polymer annotation",
            )
            if str(annotation.get("type") or "").lower() != "pfam":
                continue
            normalized = PoseBustersRcsbPfamAnnotation(
                annotation_id=str(annotation.get("annotation_id") or ""),
                name=str(annotation.get("name") or ""),
                provenance_source=str(annotation.get("provenance_source") or ""),
                assignment_version=str(annotation.get("assignment_version") or ""),
            )
            previous = pfam_by_id.get(normalized.annotation_id)
            if previous is not None and previous.to_dict() != normalized.to_dict():
                raise PoseBustersRcsbTargetFamilyBindingError(
                    "raw RCSB Pfam annotations conflict for one ID"
                )
            pfam_by_id[normalized.annotation_id] = normalized
        asym_ids = tuple(str(value) for value in (container.get("asym_ids") or []))
        auth_asym_ids = tuple(
            str(value) for value in (container.get("auth_asym_ids") or [])
        )
        uniprot_ids = tuple(
            str(value) for value in (container.get("uniprot_ids") or [])
        )
        entities.append(
            PoseBustersRcsbPolymerEntity(
                rcsb_entity_id=str(entity_row.get("rcsb_id") or ""),
                entity_id=str(container.get("entity_id") or ""),
                asym_ids=tuple(sorted(asym_ids)),
                auth_asym_ids=tuple(sorted(auth_asym_ids)),
                uniprot_ids=tuple(sorted(uniprot_ids)),
                reference_sequences=tuple(references),
                pfam_annotations=tuple(
                    pfam_by_id[key] for key in sorted(pfam_by_id)
                ),
            )
        )
    return PoseBustersRcsbTargetEntry(
        pdb_id=pdb,
        status="active",
        polymer_entities=tuple(sorted(entities, key=lambda row: row.rcsb_entity_id)),
    )


def make_rcsb_request_batch(
    batch_index: int,
    requested_pdb_ids: Sequence[str],
    active_entries: Sequence[PoseBustersRcsbTargetEntry],
) -> PoseBustersRcsbRequestBatch:
    """Build the normalized evidence row for one successful GraphQL request."""

    entries = tuple(sorted(active_entries, key=lambda row: row.pdb_id))
    return PoseBustersRcsbRequestBatch(
        batch_index=batch_index,
        requested_pdb_ids=tuple(sorted(requested_pdb_ids)),
        returned_active_pdb_ids=tuple(row.pdb_id for row in entries),
        normalized_response_sha256=_canonical_sha256(
            [row.to_dict() for row in entries]
        ),
    )


@dataclass(frozen=True, slots=True)
class _TargetClusterView:
    receipt_sha256: str
    archive_intake_receipt_sha256: str
    case_ids: tuple[str, ...]
    engine_cases: tuple[PoseBustersTargetClusterEngineCase, ...]


def _load_target_cluster_receipt(
    receipt_path: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
    expected_case_ids: Sequence[str],
) -> _TargetClusterView:
    expected_sha = _digest(
        expected_receipt_sha256,
        name="expected target-cluster receipt",
    )
    try:
        source = _read_exact_regular_file(
            receipt_path,
            maximum_bytes=POSEBUSTERS_TARGET_CLUSTER_MAX_RECEIPT_BYTES,
        )
        metadata = Path(receipt_path).stat(follow_symlinks=False)
    except (PoseBustersArchiveIntakeError, OSError) as exc:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "target-cluster receipt could not be read securely"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "target-cluster receipt must remain mode 0600"
        )
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "target-cluster receipt is not canonical JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersRcsbTargetFamilyBindingError(
            "target-cluster receipt bytes are not canonical"
        )
    payload = dict(raw)
    receipt_sha = payload.pop("receipt_sha256", None)
    source_members = raw.get("implementation_source_members")
    target_module = Path(__file__).with_name(
        "public_posebusters_target_cluster_binding.py"
    )
    if (
        raw.get("schema_id") != POSEBUSTERS_TARGET_CLUSTER_RECEIPT_SCHEMA_ID
        or receipt_sha != expected_sha
        or _canonical_sha256(payload) != receipt_sha
        or raw.get("all_case_denominator") != len(expected_case_ids)
        or raw.get("biological_target_family_annotations_present") is not False
        or raw.get("external_fit_training_leakage_audit_present") is not False
        or raw.get("leakage_control_passed") is not False
        or raw.get("benchmark_executed") is not False
        or raw.get("claim_safe") is not False
        or not isinstance(source_members, dict)
        or source_members.get("target_cluster_binding")
        != _source_file_sha256(target_module)
        or _canonical_sha256(source_members)
        != raw.get("implementation_source_sha256")
    ):
        raise PoseBustersRcsbTargetFamilyBindingError(
            "target-cluster receipt contract or source identity is invalid"
        )
    raw_case_rows = _required_list(
        raw.get("case_rows"),
        name="target-cluster case rows",
    )
    case_ids = tuple(
        _case_id(_required_mapping(row, name="target-cluster case row").get("case_id"))
        for row in raw_case_rows
    )
    if case_ids != tuple(expected_case_ids):
        raise PoseBustersRcsbTargetFamilyBindingError(
            "target-cluster cases do not match archive intake"
        )
    engine_cases: list[PoseBustersTargetClusterEngineCase] = []
    try:
        for raw_engine_case in _required_list(
            raw.get("engine_case_rows"),
            name="target-cluster engine cases",
        ):
            row = _required_mapping(
                raw_engine_case,
                name="target-cluster engine-case row",
            )
            engine_cases.append(
                PoseBustersTargetClusterEngineCase(
                    engine_id=row.get("engine_id"),
                    case_id=row.get("case_id"),
                    family_id=row.get("family_id"),
                    execution_status=row.get("execution_status"),
                    evaluation_status=row.get("evaluation_status"),
                    execution_pose_count=row.get("execution_pose_count"),
                    evaluated_pose_count=row.get("evaluated_pose_count"),
                    physically_valid_pose_count=row.get(
                        "physically_valid_pose_count"
                    ),
                    top_1_physically_valid=row.get("top_1_physically_valid"),
                    top_5_physically_valid=row.get("top_5_physically_valid"),
                    top_1_rmsd_hit=row.get("top_1_rmsd_hit"),
                    top_5_rmsd_hit=row.get("top_5_rmsd_hit"),
                    top_1_valid_rmsd_hit=row.get("top_1_valid_rmsd_hit"),
                    top_5_valid_rmsd_hit=row.get("top_5_valid_rmsd_hit"),
                    schema_id=row.get("schema_id"),
                )
            )
    except ValueError as exc:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "target-cluster engine-case row is invalid"
        ) from exc
    expected_order = tuple(
        (engine, case_id)
        for engine in POSEBUSTERS_TARGET_CLUSTER_ENGINES
        for case_id in expected_case_ids
    )
    if tuple((row.engine_id, row.case_id) for row in engine_cases) != expected_order:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "target-cluster engine cases are incomplete or cross-wired"
        )
    return _TargetClusterView(
        receipt_sha256=expected_sha,
        archive_intake_receipt_sha256=_digest(
            raw.get("archive_intake_receipt_sha256"),
            name="target-cluster archive intake",
        ),
        case_ids=case_ids,
        engine_cases=tuple(engine_cases),
    )


def _system_coordinates(system: Any, *, name: str) -> torch.Tensor:
    coordinates = system.coordinates
    if (
        not isinstance(coordinates, torch.Tensor)
        or coordinates.shape != (1, system.atom_count, 3)
        or coordinates.dtype != torch.float64
        or coordinates.device.type != "cpu"
        or not bool(torch.isfinite(coordinates).all().item())
    ):
        raise PoseBustersRcsbTargetFamilyBindingError(
            f"{name} must have one finite CPU float64 coordinate model"
        )
    return coordinates[0]


def _pocket_associated_chains(
    case_id: str,
    receptor_pdb: bytes,
    reference_ligand_sdf: bytes,
) -> tuple[str, ...]:
    try:
        receptor = parse_pdb(
            receptor_pdb,
            source_id=f"{case_id}:target-family-receptor",
            connectivity_policy="record_unrepresented",
            crystallographic_cell_policy="record_only",
        )
        ligand = parse_sdf_v2000(
            reference_ligand_sdf,
            source_id=f"{case_id}:target-family-reference-ligand",
        )
    except (PDBParseError, SDFParseError) as exc:
        raise PoseBustersRcsbTargetFamilyBindingError(
            f"{case_id} target-family source parse failed"
        ) from exc
    receptor_coordinates = _system_coordinates(receptor, name="target receptor")
    ligand_coordinates = _system_coordinates(ligand, name="target reference ligand")
    ligand_indices = tuple(
        index for index, atom in enumerate(ligand.atoms) if atom.atomic_number != 1
    )
    if not ligand_indices:
        raise PoseBustersRcsbTargetFamilyBindingError(
            f"{case_id} reference ligand has no heavy atom"
        )
    chain_atom_indices: dict[str, list[int]] = {}
    for atom_index, atom in enumerate(receptor.atoms):
        residue = receptor.residues[atom.residue_index]
        if residue.hetero or atom.atomic_number == 1:
            continue
        chain_id = receptor.chains[residue.chain_index].chain_id or " "
        chain_atom_indices.setdefault(chain_id, []).append(atom_index)
    pair_count = sum(len(indices) for indices in chain_atom_indices.values()) * len(
        ligand_indices
    )
    if not chain_atom_indices or pair_count > POSEBUSTERS_RCSB_TARGET_FAMILY_MAX_CROSS_PAIRS:
        raise PoseBustersRcsbTargetFamilyBindingError(
            f"{case_id} pocket association exceeds its bounded input"
        )
    ligand_heavy = ligand_coordinates[list(ligand_indices)]
    cutoff_squared = POSEBUSTERS_RCSB_TARGET_FAMILY_POCKET_CUTOFF_ANGSTROM**2
    pocket: list[str] = []
    for chain_id in sorted(chain_atom_indices):
        receptor_chain = receptor_coordinates[chain_atom_indices[chain_id]]
        squared = (
            receptor_chain[:, None, :] - ligand_heavy[None, :, :]
        ).square().sum(dim=2)
        if bool((squared <= cutoff_squared).any().item()):
            pocket.append(chain_id)
    if not pocket:
        raise PoseBustersRcsbTargetFamilyBindingError(
            f"{case_id} has no pocket-associated protein chain"
        )
    return tuple(pocket)


def _target_case_from_entry(
    *,
    case_id: str,
    receptor_sha256: str,
    reference_ligand_sha256: str,
    pocket_chain_ids: Sequence[str],
    entry: PoseBustersRcsbTargetEntry,
) -> tuple[PoseBustersRcsbTargetCase, tuple[PoseBustersRcsbPfamAnnotation, ...]]:
    common = {
        "case_id": case_id,
        "pdb_id": entry.pdb_id,
        "receptor_sha256": receptor_sha256,
        "reference_ligand_sha256": reference_ligand_sha256,
        "pocket_chain_ids": tuple(pocket_chain_ids),
    }
    if entry.status != "active":
        mapping_status = (
            "rcsb_entry_removed" if entry.status == "removed" else "rcsb_entry_missing"
        )
        return (
            PoseBustersRcsbTargetCase(
                **common,
                mapping_status=mapping_status,
                mapped_entity_ids=(),
                unmapped_chain_ids=(),
                ambiguous_chain_ids=(),
                uniprot_ids=(),
                pfam_ids=(),
                pfam_set_id=None,
                annotation_status="not_applicable",
            ),
            (),
        )
    candidates: dict[str, tuple[PoseBustersRcsbPolymerEntity, ...]] = {}
    for chain_id in pocket_chain_ids:
        asym_matches = tuple(
            entity
            for entity in entry.polymer_entities
            if chain_id in entity.asym_ids
        )
        candidates[chain_id] = asym_matches or tuple(
            entity
            for entity in entry.polymer_entities
            if chain_id in entity.auth_asym_ids
        )
    unmapped = tuple(sorted(chain for chain, rows in candidates.items() if not rows))
    ambiguous = tuple(
        sorted(chain for chain, rows in candidates.items() if len(rows) > 1)
    )
    selected = tuple(
        sorted(
            {
                rows[0].rcsb_entity_id: rows[0]
                for rows in candidates.values()
                if len(rows) == 1
            }.values(),
            key=lambda row: row.rcsb_entity_id,
        )
    )
    if unmapped or ambiguous:
        return (
            PoseBustersRcsbTargetCase(
                **common,
                mapping_status=(
                    "pocket_chain_ambiguous" if ambiguous else "pocket_chain_unmapped"
                ),
                mapped_entity_ids=tuple(row.rcsb_entity_id for row in selected),
                unmapped_chain_ids=unmapped,
                ambiguous_chain_ids=ambiguous,
                uniprot_ids=(),
                pfam_ids=(),
                pfam_set_id=None,
                annotation_status="not_applicable",
            ),
            (),
        )
    annotations_by_payload: dict[str, PoseBustersRcsbPfamAnnotation] = {}
    for entity in selected:
        for annotation in entity.pfam_annotations:
            annotations_by_payload[_canonical_sha256(annotation.to_dict())] = annotation
    annotations = tuple(
        sorted(
            annotations_by_payload.values(),
            key=lambda row: (
                row.annotation_id,
                row.name,
                row.provenance_source,
                row.assignment_version,
            ),
        )
    )
    pfam_ids = tuple(sorted({row.annotation_id for row in annotations}))
    uniprot_ids = tuple(
        sorted(
            {
                identifier
                for entity in selected
                for identifier in (
                    *entity.uniprot_ids,
                    *(
                        reference.database_accession
                        for reference in entity.reference_sequences
                    ),
                )
            }
        )
    )
    annotation_status = (
        "pfam_annotated"
        if pfam_ids
        else "uniprot_without_pfam"
        if uniprot_ids
        else "entity_without_uniprot_or_pfam"
    )
    return (
        PoseBustersRcsbTargetCase(
            **common,
            mapping_status="complete",
            mapped_entity_ids=tuple(row.rcsb_entity_id for row in selected),
            unmapped_chain_ids=(),
            ambiguous_chain_ids=(),
            uniprot_ids=uniprot_ids,
            pfam_ids=pfam_ids,
            pfam_set_id=(_pfam_set_id(pfam_ids) if pfam_ids else None),
            annotation_status=annotation_status,
        ),
        annotations,
    )


def _pfam_family_rows(
    cases: Sequence[PoseBustersRcsbTargetCase],
    annotations_by_case: Mapping[
        str,
        Sequence[PoseBustersRcsbPfamAnnotation],
    ],
) -> tuple[PoseBustersRcsbPfamFamily, ...]:
    all_ids = sorted({pfam_id for row in cases for pfam_id in row.pfam_ids})
    rows: list[PoseBustersRcsbPfamFamily] = []
    for pfam_id in all_ids:
        annotations = tuple(
            annotation
            for case in cases
            for annotation in annotations_by_case[case.case_id]
            if annotation.annotation_id == pfam_id
        )
        rows.append(
            PoseBustersRcsbPfamFamily(
                pfam_id=pfam_id,
                names=tuple(sorted({row.name for row in annotations})),
                provenance_sources=tuple(
                    sorted({row.provenance_source for row in annotations})
                ),
                assignment_versions=tuple(
                    sorted({row.assignment_version for row in annotations})
                ),
                member_case_ids=tuple(
                    row.case_id for row in cases if pfam_id in row.pfam_ids
                ),
            )
        )
    return tuple(rows)


def _pfam_set_rows(
    cases: Sequence[PoseBustersRcsbTargetCase],
) -> tuple[PoseBustersRcsbPfamSet, ...]:
    set_ids = sorted(
        {row.pfam_set_id for row in cases if row.pfam_set_id is not None}
    )
    rows: list[PoseBustersRcsbPfamSet] = []
    for set_id in set_ids:
        members = tuple(row for row in cases if row.pfam_set_id == set_id)
        rows.append(
            PoseBustersRcsbPfamSet(
                pfam_set_id=set_id,
                pfam_ids=members[0].pfam_ids,
                member_case_ids=tuple(row.case_id for row in members),
            )
        )
    return tuple(rows)


def _aggregate_engine_families(
    pfam_families: Sequence[PoseBustersRcsbPfamFamily],
    pfam_sets: Sequence[PoseBustersRcsbPfamSet],
    engine_cases: Sequence[PoseBustersTargetClusterEngineCase],
) -> tuple[PoseBustersRcsbEngineFamily, ...]:
    source = {(row.engine_id, row.case_id): row for row in engine_cases}
    families = tuple(
        ("pfam_multi_label", row.pfam_id, row.member_case_ids)
        for row in pfam_families
    ) + tuple(
        ("pfam_set_partition", row.pfam_set_id, row.member_case_ids)
        for row in pfam_sets
    )
    rows: list[PoseBustersRcsbEngineFamily] = []
    for engine in POSEBUSTERS_TARGET_CLUSTER_ENGINES:
        for kind, family_id, member_ids in families:
            members = tuple(source[(engine, case_id)] for case_id in member_ids)
            rows.append(
                PoseBustersRcsbEngineFamily(
                    engine_id=engine,
                    family_kind=kind,
                    family_id=family_id,
                    member_case_count=len(members),
                    execution_success_case_count=sum(
                        row.execution_success for row in members
                    ),
                    top_1_rmsd_hit_case_count=sum(row.top_1_rmsd_hit for row in members),
                    top_5_rmsd_hit_case_count=sum(row.top_5_rmsd_hit for row in members),
                    top_1_valid_rmsd_hit_case_count=sum(
                        row.top_1_valid_rmsd_hit for row in members
                    ),
                    top_5_valid_rmsd_hit_case_count=sum(
                        row.top_5_valid_rmsd_hit for row in members
                    ),
                )
            )
    return tuple(
        sorted(rows, key=lambda row: (row.engine_id, row.family_kind, row.family_id))
    )


def _implementation_source_members() -> tuple[tuple[str, str], ...]:
    module_root = Path(__file__).parent
    package_root = module_root.parent
    return tuple(
        sorted(
            {
                "corpus_audit_utilities": _source_file_sha256(
                    module_root / "public_posebusters_corpus_audit.py"
                ),
                "posebusters_archive_intake": _source_file_sha256(
                    module_root / "public_posebusters_intake.py"
                ),
                "rcsb_target_family_binding": _source_file_sha256(__file__),
                "strict_pdb_parser": _source_file_sha256(
                    package_root / "io" / "pdb.py"
                ),
                "strict_sdf_parser": _source_file_sha256(
                    package_root / "io" / "sdf.py"
                ),
                "target_cluster_binding": _source_file_sha256(
                    module_root / "public_posebusters_target_cluster_binding.py"
                ),
            }.items()
        )
    )


def _build_rcsb_target_family_receipt(
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    target_cluster_receipt_path: str | os.PathLike[str],
    annotation_snapshot_path: str | os.PathLike[str],
    *,
    expected_target_cluster_receipt_sha256: str,
    expected_annotation_snapshot_sha256: str,
    contract: PoseBustersArchiveContract,
) -> PoseBustersRcsbTargetFamilyReceipt:
    if _canonical_sha256(POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIGURATION) != (
        POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIGURATION_SHA256
    ):
        raise PoseBustersRcsbTargetFamilyBindingError(
            "frozen RCSB target-family configuration was mutated"
        )
    try:
        intake = verify_posebusters_archive_intake_receipt(
            intake_receipt_path,
            archive_path,
            selection_path,
            contract=contract,
        )
    except PoseBustersArchiveIntakeError as exc:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB target-family archive intake did not verify"
        ) from exc
    if (
        intake.global_error_codes
        or not intake.case_rows
        or len(intake.case_rows) > POSEBUSTERS_RCSB_TARGET_FAMILY_MAX_CASES
        or any(row.status != "ready" for row in intake.case_rows)
    ):
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB target-family binding requires a bounded all-ready intake"
        )
    expected_case_ids = tuple(row.case_id for row in intake.case_rows)
    target_cluster = _load_target_cluster_receipt(
        target_cluster_receipt_path,
        expected_receipt_sha256=expected_target_cluster_receipt_sha256,
        expected_case_ids=expected_case_ids,
    )
    if target_cluster.archive_intake_receipt_sha256 != intake.fingerprint_sha256:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "target-cluster receipt cross-wires archive intake"
        )
    snapshot = load_posebusters_rcsb_target_annotation_snapshot(
        annotation_snapshot_path,
        expected_snapshot_sha256=expected_annotation_snapshot_sha256,
    )
    expected_pdb_ids = tuple(
        sorted({case_id.split("_", 1)[0].upper() for case_id in expected_case_ids})
    )
    if tuple(row.pdb_id for row in snapshot.entries) != expected_pdb_ids:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB annotation snapshot does not match archive PDB IDs"
        )
    entries_by_id = {row.pdb_id: row for row in snapshot.entries}
    cases: list[PoseBustersRcsbTargetCase] = []
    annotations_by_case: dict[str, tuple[PoseBustersRcsbPfamAnnotation, ...]] = {}
    try:
        descriptor, size = _regular_file_descriptor(
            archive_path,
            maximum_bytes=contract.archive_size_bytes,
        )
        try:
            if size != contract.archive_size_bytes or _hash_descriptor(descriptor, size) != (
                contract.archive_sha256
            ):
                raise PoseBustersRcsbTargetFamilyBindingError(
                    "RCSB target-family archive identity changed"
                )
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                with zipfile.ZipFile(handle, "r") as archive:
                    for intake_row in intake.case_rows:
                        artifacts = {row.role: row for row in intake_row.artifacts}
                        receptor_artifact = artifacts["receptor_pdb"]
                        ligand_artifact = artifacts["reference_ligand_sdf"]
                        receptor = _read_member(
                            archive,
                            receptor_artifact.member_path,
                            expected_sha256=receptor_artifact.sha256,
                            expected_size=receptor_artifact.size_bytes,
                        )
                        ligand = _read_member(
                            archive,
                            ligand_artifact.member_path,
                            expected_sha256=ligand_artifact.sha256,
                            expected_size=ligand_artifact.size_bytes,
                        )
                        pocket = _pocket_associated_chains(
                            intake_row.case_id,
                            receptor,
                            ligand,
                        )
                        case, annotations = _target_case_from_entry(
                            case_id=intake_row.case_id,
                            receptor_sha256=receptor_artifact.sha256,
                            reference_ligand_sha256=ligand_artifact.sha256,
                            pocket_chain_ids=pocket,
                            entry=entries_by_id[
                                intake_row.case_id.split("_", 1)[0].upper()
                            ],
                        )
                        cases.append(case)
                        annotations_by_case[case.case_id] = annotations
        finally:
            os.close(descriptor)
    except PoseBustersRcsbTargetFamilyBindingError:
        raise
    except (
        KeyError,
        OSError,
        RuntimeError,
        zipfile.BadZipFile,
        PoseBustersCorpusAuditError,
        PoseBustersArchiveIntakeError,
    ) as exc:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB target-family archive access failed closed"
        ) from exc
    case_rows = tuple(cases)
    pfam_families = _pfam_family_rows(case_rows, annotations_by_case)
    pfam_sets = _pfam_set_rows(case_rows)
    engine_families = _aggregate_engine_families(
        pfam_families,
        pfam_sets,
        target_cluster.engine_cases,
    )
    metrics = _metrics_for_receipt(case_rows, engine_families)
    source_members = _implementation_source_members()
    return PoseBustersRcsbTargetFamilyReceipt(
        archive_intake_receipt_sha256=intake.fingerprint_sha256,
        target_cluster_receipt_sha256=target_cluster.receipt_sha256,
        annotation_snapshot_sha256=snapshot.fingerprint_sha256,
        annotation_observation_utc=snapshot.observation_utc,
        configuration_sha256=POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIGURATION_SHA256,
        implementation_source_sha256=_canonical_sha256(dict(source_members)),
        implementation_source_members=source_members,
        case_rows=case_rows,
        pfam_family_rows=pfam_families,
        pfam_set_rows=pfam_sets,
        engine_family_rows=engine_families,
        metrics=metrics,
        leakage_dispositions=tuple(
            PoseBustersRcsbLeakageDisposition(engine_id=engine)
            for engine in POSEBUSTERS_TARGET_CLUSTER_ENGINES
        ),
    )


def materialize_posebusters_rcsb_target_family_binding(
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    target_cluster_receipt_path: str | os.PathLike[str],
    annotation_snapshot_path: str | os.PathLike[str],
    *,
    expected_target_cluster_receipt_sha256: str,
    expected_annotation_snapshot_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersRcsbTargetFamilyReceipt:
    """Build pocket-associated RCSB/Pfam metrics from frozen local evidence."""

    return _build_rcsb_target_family_receipt(
        archive_path,
        selection_path,
        intake_receipt_path,
        target_cluster_receipt_path,
        annotation_snapshot_path,
        expected_target_cluster_receipt_sha256=(
            expected_target_cluster_receipt_sha256
        ),
        expected_annotation_snapshot_sha256=expected_annotation_snapshot_sha256,
        contract=contract,
    )


def verify_posebusters_rcsb_target_family_binding_receipt(
    target_family_receipt_path: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    target_cluster_receipt_path: str | os.PathLike[str],
    annotation_snapshot_path: str | os.PathLike[str],
    *,
    expected_target_cluster_receipt_sha256: str,
    expected_annotation_snapshot_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersRcsbTargetFamilyReceipt:
    """Require exact local reconstruction and canonical receipt equality."""

    try:
        source = _read_exact_regular_file(
            target_family_receipt_path,
            maximum_bytes=POSEBUSTERS_RCSB_TARGET_FAMILY_MAX_RECEIPT_BYTES,
        )
        metadata = Path(target_family_receipt_path).stat(follow_symlinks=False)
    except (PoseBustersArchiveIntakeError, OSError) as exc:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB target-family receipt could not be read securely"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB target-family receipt must remain mode 0600"
        )
    expected = _build_rcsb_target_family_receipt(
        archive_path,
        selection_path,
        intake_receipt_path,
        target_cluster_receipt_path,
        annotation_snapshot_path,
        expected_target_cluster_receipt_sha256=(
            expected_target_cluster_receipt_sha256
        ),
        expected_annotation_snapshot_sha256=expected_annotation_snapshot_sha256,
        contract=contract,
    )
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersRcsbTargetFamilyBindingError(
            "RCSB target-family receipt does not match exact reexecution"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-rcsb-target-families",
        description=(
            "Bind frozen PoseBusters engine outcomes to pocket-associated "
            "RCSB/Pfam annotations without runtime networking."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot = subparsers.add_parser("verify-snapshot")
    snapshot.add_argument("--annotation-snapshot", required=True)
    snapshot.add_argument("--expected-annotation-snapshot-sha256", required=True)
    for command in ("materialize", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--archive", required=True)
        subparser.add_argument("--selection", required=True)
        subparser.add_argument("--intake-receipt", required=True)
        subparser.add_argument("--target-cluster-receipt", required=True)
        subparser.add_argument(
            "--expected-target-cluster-receipt-sha256",
            required=True,
        )
        subparser.add_argument("--annotation-snapshot", required=True)
        subparser.add_argument(
            "--expected-annotation-snapshot-sha256",
            required=True,
        )
    subparsers.choices["materialize"].add_argument("--output", required=True)
    subparsers.choices["verify"].add_argument(
        "--target-family-receipt",
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "verify-snapshot":
        snapshot = load_posebusters_rcsb_target_annotation_snapshot(
            args.annotation_snapshot,
            expected_snapshot_sha256=args.expected_annotation_snapshot_sha256,
        )
        print(
            json.dumps(
                {
                    "receipt_sha256": snapshot.fingerprint_sha256,
                    "observation_utc": snapshot.observation_utc,
                    "requested_pdb_count": len(snapshot.entries),
                    "active_entry_count": sum(
                        row.status == "active" for row in snapshot.entries
                    ),
                    "removed_entry_count": sum(
                        row.status == "removed" for row in snapshot.entries
                    ),
                    "raw_response_persisted": False,
                    "independently_signed_by_source": False,
                    "scientifically_validated": False,
                },
                sort_keys=True,
            )
        )
        return 0
    common = {
        "archive_path": args.archive,
        "selection_path": args.selection,
        "intake_receipt_path": args.intake_receipt,
        "target_cluster_receipt_path": args.target_cluster_receipt,
        "annotation_snapshot_path": args.annotation_snapshot,
        "expected_target_cluster_receipt_sha256": (
            args.expected_target_cluster_receipt_sha256
        ),
        "expected_annotation_snapshot_sha256": (
            args.expected_annotation_snapshot_sha256
        ),
    }
    if args.command == "materialize":
        if Path(args.output).exists():
            raise PoseBustersRcsbTargetFamilyBindingError(
                "RCSB target-family output already exists"
            )
        receipt = materialize_posebusters_rcsb_target_family_binding(**common)
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_rcsb_target_family_binding_receipt(
            target_family_receipt_path=args.target_family_receipt,
            **common,
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "mapping_complete_case_count": sum(
                    row.mapping_status == "complete" for row in receipt.case_rows
                ),
                "pfam_annotated_case_count": sum(
                    bool(row.pfam_ids) for row in receipt.case_rows
                ),
                "pfam_multi_label_family_count": len(receipt.pfam_family_rows),
                "exact_pfam_set_count": len(receipt.pfam_set_rows),
                "leakage_control_passed": False,
                "public_benchmark_claim_authorized": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_RCSB_GRAPHQL_ENDPOINT",
    "POSEBUSTERS_RCSB_GRAPHQL_QUERY",
    "POSEBUSTERS_RCSB_GRAPHQL_QUERY_SHA256",
    "POSEBUSTERS_RCSB_TARGET_ANNOTATION_SNAPSHOT_SCHEMA_ID",
    "POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIGURATION",
    "POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIGURATION_SHA256",
    "POSEBUSTERS_RCSB_TARGET_FAMILY_RECEIPT_SCHEMA_ID",
    "POSEBUSTERS_RCSB_TARGET_FAMILY_SCIENTIFIC_BLOCKERS",
    "PoseBustersRcsbEngineFamily",
    "PoseBustersRcsbLeakageDisposition",
    "PoseBustersRcsbPfamAnnotation",
    "PoseBustersRcsbPfamFamily",
    "PoseBustersRcsbPfamSet",
    "PoseBustersRcsbPolymerEntity",
    "PoseBustersRcsbReferenceSequence",
    "PoseBustersRcsbRequestBatch",
    "PoseBustersRcsbTargetAnnotationSnapshot",
    "PoseBustersRcsbTargetCase",
    "PoseBustersRcsbTargetEntry",
    "PoseBustersRcsbTargetFamilyBindingError",
    "PoseBustersRcsbTargetFamilyReceipt",
    "PoseBustersRcsbTargetMetric",
    "load_posebusters_rcsb_target_annotation_snapshot",
    "main",
    "make_rcsb_request_batch",
    "materialize_posebusters_rcsb_target_family_binding",
    "normalize_rcsb_graphql_target_entry",
    "verify_posebusters_rcsb_target_family_binding_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
