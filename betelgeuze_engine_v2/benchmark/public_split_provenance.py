"""Leakage-audited public docking split and result-provenance contracts.

The module binds caller-provisioned PDBbind v2020, CASF-2016, and the published
308-case PoseBusters Benchmark identities without downloading or redistributing
any dataset.  It connects exact dataset case manifests to the generic
pose-ranking calibration partitions, records target-sequence similarity to the
fit partition, and verifies target-family denominators in an evaluation report.

No license acceptance, dataset archive, fitted model, benchmark result, or
independent review is bundled.  Every receipt remains claim-closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import math
from numbers import Real
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from betelgeuze_engine_v2.docking.calibration import (
    PoseRankingCalibrationPartition,
    PoseRankingEvaluationReport,
    PoseRankingLeakageAudit,
    audit_pose_ranking_leakage,
)


PUBLIC_DOCKING_DATASET_SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_docking_dataset_source/1.0.0"
)
PUBLIC_DOCKING_SPLIT_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_docking_split_case/1.0.0"
)
PUBLIC_DOCKING_SPLIT_MANIFEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_docking_split_manifest/1.0.0"
)
PUBLIC_DOCKING_SEQUENCE_METHOD_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_docking_sequence_method/1.0.0"
)
PUBLIC_DOCKING_SEQUENCE_ROW_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_docking_sequence_row/1.0.0"
)
PUBLIC_DOCKING_SEQUENCE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_docking_sequence_receipt/1.0.0"
)
PUBLIC_DOCKING_LEAKAGE_AUDIT_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_docking_leakage_audit/1.0.0"
)
PUBLIC_DOCKING_PARTITION_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_docking_partition_binding/1.0.0"
)
PUBLIC_POSE_RANKING_EVALUATION_LINK_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_evaluation_link/1.0.0"
)
PUBLIC_POSE_RANKING_RESULT_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_pose_ranking_result_binding/1.0.0"
)

PDBBIND_V2020_DATASET_ID = "pdbbind_v2020"
CASF_2016_DATASET_ID = "casf_2016"
POSEBUSTERS_2023_308_DATASET_ID = "posebusters_benchmark_2023_308"
PUBLIC_DOCKING_DATASET_IDS = frozenset(
    {
        PDBBIND_V2020_DATASET_ID,
        CASF_2016_DATASET_ID,
        POSEBUSTERS_2023_308_DATASET_ID,
    }
)
PUBLIC_DOCKING_SEQUENCE_METHOD_ID = (
    "smith_waterman_blosum62_open11_extend1_query_fraction_v1"
)
POSEBUSTERS_2023_308_SELECTION_SHA256 = (
    "a69a7b6b9a5a52531933078ef983e6c069e3a987a1d7a733bd7d72cbe1793de6"
)
POSEBUSTERS_2023_ARCHIVE_SHA256 = (
    "495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c"
)
POSEBUSTERS_2023_ARCHIVE_SIZE_BYTES = 53_660_397
POSEBUSTERS_2023_308_CASE_ID_PROJECTION_SHA256 = (
    "fb3d12a98fb61d95f306ecf36188d66dddf64303389915a72b2a9b96cc97f3f6"
)
PUBLIC_DOCKING_MAX_CASES = 25_000
PUBLIC_DOCKING_MAX_SEQUENCE_CASE_PAIRS = 625_000_000

_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_SPLIT_ROLES = frozenset({"fit", "validation", "test", "ood"})
_PARTITION_SCOPES = frozenset(
    {
        "calibration_fit",
        "full_benchmark",
        "novel_target_subset",
        "development_subset",
    }
)
_COFACTOR_CATEGORIES = frozenset(
    {"none", "organic", "inorganic", "organic_and_inorganic", "unknown"}
)
_CHEMISTRY_STATUSES = frozenset({"supported", "unsupported", "unknown"})


class PublicDockingSplitError(ValueError):
    """Public dataset provenance, leakage, or result binding failed closed."""


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
        raise PublicDockingSplitError(
            "public docking provenance is not canonical JSON"
        ) from exc


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicDockingSplitError(f"{name} must be non-empty text")
    return value.strip()


def _sha256(value: object, *, name: str, allow_empty: bool = False) -> str:
    if allow_empty and value == "":
        return ""
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise PublicDockingSplitError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _positive_int(value: object, *, name: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PublicDockingSplitError(f"{name} must be a positive integer")
    if maximum is not None and value > maximum:
        raise PublicDockingSplitError(f"{name} exceeds the frozen maximum")
    return value


def _ratio(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PublicDockingSplitError(f"{name} must be a finite ratio")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise PublicDockingSplitError(f"{name} must be in [0,1]")
    return number


def _iso_date(value: object, *, name: str) -> str:
    text = _text(value, name=name)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise PublicDockingSplitError(f"{name} must be an ISO calendar date") from exc
    if parsed.isoformat() != text:
        raise PublicDockingSplitError(f"{name} must be a canonical ISO date")
    return text


@dataclass(frozen=True, slots=True)
class FrozenPublicDockingDatasetSpec:
    dataset_id: str
    dataset_version: str
    official_url: str
    citation_doi: str
    license_id: str
    license_url: str
    access_policy: str
    allowed_split_roles: tuple[str, ...]
    official_evaluation_case_count: int | None
    official_archive_sha256: str | None
    official_archive_size_bytes: int | None
    official_selection_manifest_sha256: str | None
    official_case_id_projection_sha256: str | None
    benchmark_endpoints: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "official_url": self.official_url,
            "citation_doi": self.citation_doi,
            "license_id": self.license_id,
            "license_url": self.license_url,
            "access_policy": self.access_policy,
            "allowed_split_roles": list(self.allowed_split_roles),
            "official_evaluation_case_count": self.official_evaluation_case_count,
            "official_archive_sha256": self.official_archive_sha256,
            "official_archive_size_bytes": self.official_archive_size_bytes,
            "official_selection_manifest_sha256": (
                self.official_selection_manifest_sha256
            ),
            "official_case_id_projection_sha256": (
                self.official_case_id_projection_sha256
            ),
            "benchmark_endpoints": list(self.benchmark_endpoints),
        }


PUBLIC_DOCKING_DATASET_SPECS: Mapping[str, FrozenPublicDockingDatasetSpec] = (
    MappingProxyType(
        {
            PDBBIND_V2020_DATASET_ID: FrozenPublicDockingDatasetSpec(
                dataset_id=PDBBIND_V2020_DATASET_ID,
                dataset_version="2020",
                official_url="https://www.pdbbind-plus.org.cn/",
                citation_doi="10.1093/bioinformatics/btu626",
                license_id="PDBbind+ demo-or-subscriber terms",
                license_url="https://www.pdbbind-plus.org.cn/termofuse",
                access_policy="registered_demo_or_subscriber",
                allowed_split_roles=("fit",),
                official_evaluation_case_count=None,
                official_archive_sha256=None,
                official_archive_size_bytes=None,
                official_selection_manifest_sha256=None,
                official_case_id_projection_sha256=None,
                benchmark_endpoints=("pose_ranking_calibration_fit",),
            ),
            CASF_2016_DATASET_ID: FrozenPublicDockingDatasetSpec(
                dataset_id=CASF_2016_DATASET_ID,
                dataset_version="2016",
                official_url="https://www.pdbbind-plus.org.cn/casf",
                citation_doi="10.1021/acs.jcim.8b00545",
                license_id="PDBbind+ related-material terms",
                license_url="https://www.pdbbind-plus.org.cn/termofuse",
                access_policy="registered_demo_or_subscriber",
                allowed_split_roles=("validation", "test", "ood"),
                official_evaluation_case_count=285,
                official_archive_sha256=None,
                official_archive_size_bytes=None,
                official_selection_manifest_sha256=None,
                official_case_id_projection_sha256=None,
                benchmark_endpoints=(
                    "scoring_power",
                    "ranking_power",
                    "docking_power",
                    "screening_power",
                ),
            ),
            POSEBUSTERS_2023_308_DATASET_ID: FrozenPublicDockingDatasetSpec(
                dataset_id=POSEBUSTERS_2023_308_DATASET_ID,
                dataset_version="zenodo-8278563-v1-journal-308",
                official_url="https://zenodo.org/records/8278563",
                citation_doi="10.1039/D3SC04185A",
                license_id="CC-BY-4.0",
                license_url="https://creativecommons.org/licenses/by/4.0/",
                access_policy="open_download_with_attribution",
                allowed_split_roles=("validation", "test", "ood"),
                official_evaluation_case_count=308,
                official_archive_sha256=POSEBUSTERS_2023_ARCHIVE_SHA256,
                official_archive_size_bytes=POSEBUSTERS_2023_ARCHIVE_SIZE_BYTES,
                official_selection_manifest_sha256=(
                    POSEBUSTERS_2023_308_SELECTION_SHA256
                ),
                official_case_id_projection_sha256=(
                    POSEBUSTERS_2023_308_CASE_ID_PROJECTION_SHA256
                ),
                benchmark_endpoints=(
                    "redocking",
                    "symmetry_aware_rmsd_2_angstrom",
                    "posebusters_validity",
                    "sequence_identity_stratification",
                ),
            ),
        }
    )
)


@dataclass(frozen=True, slots=True)
class PublicDockingDatasetSource:
    dataset_id: str
    archive_sha256: str
    archive_size_bytes: int
    selection_manifest_sha256: str
    license_terms_sha256: str
    access_authorization_receipt_sha256: str = ""
    selection_review_receipt_sha256: str = ""
    schema_id: str = PUBLIC_DOCKING_DATASET_SOURCE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_DOCKING_DATASET_SOURCE_SCHEMA_ID:
            raise PublicDockingSplitError("unsupported public dataset-source schema")
        dataset_id = _text(self.dataset_id, name="dataset_id")
        if dataset_id not in PUBLIC_DOCKING_DATASET_SPECS:
            raise PublicDockingSplitError("unsupported public docking dataset")
        object.__setattr__(self, "dataset_id", dataset_id)
        object.__setattr__(
            self,
            "archive_sha256",
            _sha256(self.archive_sha256, name="dataset archive"),
        )
        object.__setattr__(
            self,
            "archive_size_bytes",
            _positive_int(self.archive_size_bytes, name="dataset archive size"),
        )
        spec = PUBLIC_DOCKING_DATASET_SPECS[dataset_id]
        if (
            spec.official_archive_sha256 is not None
            and (
                self.archive_sha256 != spec.official_archive_sha256
                or self.archive_size_bytes != spec.official_archive_size_bytes
            )
        ):
            raise PublicDockingSplitError(
                "dataset archive does not match the frozen official identity"
            )
        object.__setattr__(
            self,
            "selection_manifest_sha256",
            _sha256(self.selection_manifest_sha256, name="selection manifest"),
        )
        expected_selection = PUBLIC_DOCKING_DATASET_SPECS[
            dataset_id
        ].official_selection_manifest_sha256
        if (
            expected_selection is not None
            and self.selection_manifest_sha256 != expected_selection
        ):
            raise PublicDockingSplitError(
                "selection manifest does not match the frozen official identity"
            )
        object.__setattr__(
            self,
            "license_terms_sha256",
            _sha256(self.license_terms_sha256, name="license terms"),
        )
        object.__setattr__(
            self,
            "access_authorization_receipt_sha256",
            _sha256(
                self.access_authorization_receipt_sha256,
                name="access authorization receipt",
                allow_empty=True,
            ),
        )
        object.__setattr__(
            self,
            "selection_review_receipt_sha256",
            _sha256(
                self.selection_review_receipt_sha256,
                name="selection review receipt",
                allow_empty=True,
            ),
        )

    @property
    def spec(self) -> FrozenPublicDockingDatasetSpec:
        return PUBLIC_DOCKING_DATASET_SPECS[self.dataset_id]

    @property
    def access_basis_present(self) -> bool:
        return (
            self.spec.access_policy == "open_download_with_attribution"
            or bool(self.access_authorization_receipt_sha256)
        )

    @property
    def selection_evidence_present(self) -> bool:
        return (
            self.spec.official_selection_manifest_sha256 is not None
            or bool(self.selection_review_receipt_sha256)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "dataset": self.spec.to_dict(),
            "archive_sha256": self.archive_sha256,
            "archive_size_bytes": self.archive_size_bytes,
            "selection_manifest_sha256": self.selection_manifest_sha256,
            "license_terms_sha256": self.license_terms_sha256,
            "access_authorization_receipt_sha256": (
                self.access_authorization_receipt_sha256
            ),
            "selection_review_receipt_sha256": (
                self.selection_review_receipt_sha256
            ),
            "access_basis_present": self.access_basis_present,
            "selection_evidence_present": self.selection_evidence_present,
            "dataset_bytes_bundled": False,
            "redistribution_authorized_by_this_receipt": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PublicDockingSplitCase:
    dataset_id: str
    case_id: str
    pdb_id: str
    target_id: str
    target_family: str
    split_role: str
    release_date: str
    receptor_sha256: str
    ligand_sha256: str
    scaffold_sha256: str
    target_sequence_set_sha256: str
    cofactor_category: str
    chemistry_status: str
    schema_id: str = PUBLIC_DOCKING_SPLIT_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_DOCKING_SPLIT_CASE_SCHEMA_ID:
            raise PublicDockingSplitError("unsupported public split-case schema")
        dataset_id = _text(self.dataset_id, name="case dataset_id")
        if dataset_id not in PUBLIC_DOCKING_DATASET_SPECS:
            raise PublicDockingSplitError("split case uses an unsupported dataset")
        object.__setattr__(self, "dataset_id", dataset_id)
        for name in ("case_id", "pdb_id", "target_id", "target_family"):
            object.__setattr__(self, name, _text(getattr(self, name), name=name))
        split_role = _text(self.split_role, name="split_role").lower()
        if split_role not in _SPLIT_ROLES:
            raise PublicDockingSplitError("unsupported public split role")
        object.__setattr__(self, "split_role", split_role)
        object.__setattr__(
            self,
            "release_date",
            _iso_date(self.release_date, name="case release_date"),
        )
        for name in (
            "receptor_sha256",
            "ligand_sha256",
            "scaffold_sha256",
            "target_sequence_set_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), name=name),
            )
        cofactor = _text(self.cofactor_category, name="cofactor_category").lower()
        if cofactor not in _COFACTOR_CATEGORIES:
            raise PublicDockingSplitError("unsupported cofactor_category")
        chemistry = _text(self.chemistry_status, name="chemistry_status").lower()
        if chemistry not in _CHEMISTRY_STATUSES:
            raise PublicDockingSplitError("unsupported chemistry_status")
        object.__setattr__(self, "cofactor_category", cofactor)
        object.__setattr__(self, "chemistry_status", chemistry)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "dataset_id": self.dataset_id,
            "case_id": self.case_id,
            "pdb_id": self.pdb_id,
            "target_id": self.target_id,
            "target_family": self.target_family,
            "split_role": self.split_role,
            "release_date": self.release_date,
            "receptor_sha256": self.receptor_sha256,
            "ligand_sha256": self.ligand_sha256,
            "scaffold_sha256": self.scaffold_sha256,
            "target_sequence_set_sha256": self.target_sequence_set_sha256,
            "cofactor_category": self.cofactor_category,
            "chemistry_status": self.chemistry_status,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PublicDockingSplitManifest:
    source: PublicDockingDatasetSource
    split_role: str
    partition_scope: str
    scoring_protocol_sha256: str
    preparation_profile_sha256: str
    cases: tuple[PublicDockingSplitCase, ...]
    complete_official_case_set: bool = False
    schema_id: str = PUBLIC_DOCKING_SPLIT_MANIFEST_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_DOCKING_SPLIT_MANIFEST_SCHEMA_ID:
            raise PublicDockingSplitError("unsupported public split-manifest schema")
        if not isinstance(self.source, PublicDockingDatasetSource):
            raise PublicDockingSplitError("split manifest source has the wrong type")
        split_role = _text(self.split_role, name="manifest split_role").lower()
        if split_role not in self.source.spec.allowed_split_roles:
            raise PublicDockingSplitError(
                "dataset does not admit the requested split role"
            )
        scope = _text(self.partition_scope, name="partition_scope").lower()
        if scope not in _PARTITION_SCOPES:
            raise PublicDockingSplitError("unsupported partition_scope")
        if split_role == "fit" and scope != "calibration_fit":
            raise PublicDockingSplitError(
                "fit manifests must use partition_scope=calibration_fit"
            )
        if split_role != "fit" and scope == "calibration_fit":
            raise PublicDockingSplitError(
                "evaluation manifests cannot use calibration_fit scope"
            )
        object.__setattr__(self, "split_role", split_role)
        object.__setattr__(self, "partition_scope", scope)
        for name in ("scoring_protocol_sha256", "preparation_profile_sha256"):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), name=name),
            )
        cases = tuple(self.cases)
        if (
            not cases
            or len(cases) > PUBLIC_DOCKING_MAX_CASES
            or any(not isinstance(case, PublicDockingSplitCase) for case in cases)
        ):
            raise PublicDockingSplitError(
                "split manifest requires a bounded non-empty case set"
            )
        if tuple(case.case_id for case in cases) != tuple(
            sorted(case.case_id for case in cases)
        ):
            raise PublicDockingSplitError("split cases must be canonically ordered")
        if len({case.case_id for case in cases}) != len(cases):
            raise PublicDockingSplitError("split case IDs must be unique")
        if any(
            case.dataset_id != self.source.dataset_id
            or case.split_role != split_role
            for case in cases
        ):
            raise PublicDockingSplitError(
                "split cases disagree with the source dataset or split role"
            )
        if not isinstance(self.complete_official_case_set, bool):
            raise PublicDockingSplitError(
                "complete_official_case_set must be boolean"
            )
        expected = self.source.spec.official_evaluation_case_count
        expected_case_ids = self.source.spec.official_case_id_projection_sha256
        if self.complete_official_case_set and (
            expected is None
            or len(cases) != expected
            or scope != "full_benchmark"
            or not self.source.selection_evidence_present
            or (
                expected_case_ids is not None
                and _canonical_sha256([case.case_id for case in cases])
                != expected_case_ids
            )
        ):
            raise PublicDockingSplitError(
                "complete official case-set declaration disagrees with the frozen source"
            )
        object.__setattr__(self, "cases", cases)

    @property
    def input_ready(self) -> bool:
        expected = self.source.spec.official_evaluation_case_count
        complete = expected is None or self.complete_official_case_set
        return (
            self.source.access_basis_present
            and self.source.selection_evidence_present
            and complete
            and all(case.target_family.lower() != "unknown" for case in self.cases)
            and all(case.chemistry_status != "unknown" for case in self.cases)
        )

    @property
    def blockers(self) -> tuple[str, ...]:
        blockers: list[str] = []
        if not self.source.access_basis_present:
            blockers.append("dataset_access_basis_missing")
        if not self.source.selection_evidence_present:
            blockers.append("dataset_selection_review_evidence_missing")
        if (
            self.source.spec.official_evaluation_case_count is not None
            and not self.complete_official_case_set
        ):
            blockers.append("complete_official_evaluation_case_set_missing")
        if any(case.target_family.lower() == "unknown" for case in self.cases):
            blockers.append("target_family_assignment_missing")
        if any(case.chemistry_status == "unknown" for case in self.cases):
            blockers.append("supported_chemistry_disposition_missing")
        return tuple(blockers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "source": self.source.to_dict(),
            "source_sha256": self.source.fingerprint_sha256,
            "split_role": self.split_role,
            "partition_scope": self.partition_scope,
            "scoring_protocol_sha256": self.scoring_protocol_sha256,
            "preparation_profile_sha256": self.preparation_profile_sha256,
            "case_count": len(self.cases),
            "official_evaluation_case_count": (
                self.source.spec.official_evaluation_case_count
            ),
            "complete_official_case_set": self.complete_official_case_set,
            "cases": [case.to_dict() for case in self.cases],
            "input_ready": self.input_ready,
            "blockers": list(self.blockers),
            "benchmark_executed": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PublicDockingSequenceIdentityMethod:
    tool_id: str
    tool_version: str
    executable_sha256: str
    configuration_sha256: str
    method_id: str = PUBLIC_DOCKING_SEQUENCE_METHOD_ID
    schema_id: str = PUBLIC_DOCKING_SEQUENCE_METHOD_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_DOCKING_SEQUENCE_METHOD_SCHEMA_ID:
            raise PublicDockingSplitError("unsupported sequence-method schema")
        if self.method_id != PUBLIC_DOCKING_SEQUENCE_METHOD_ID:
            raise PublicDockingSplitError("unsupported sequence-identity method")
        object.__setattr__(self, "tool_id", _text(self.tool_id, name="sequence tool"))
        object.__setattr__(
            self,
            "tool_version",
            _text(self.tool_version, name="sequence tool version"),
        )
        for name in ("executable_sha256", "configuration_sha256"):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), name=name),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "method_id": self.method_id,
            "tool_id": self.tool_id,
            "tool_version": self.tool_version,
            "executable_sha256": self.executable_sha256,
            "configuration_sha256": self.configuration_sha256,
            "alignment": "Smith-Waterman local alignment",
            "substitution_matrix": "BLOSUM62",
            "gap_open_score": -11,
            "gap_extension_score": -1,
            "identity_denominator": "evaluation_query_sequence_length",
            "chain_pair_policy": (
                "maximum_over_all_evaluation_and_fit_protein_chain_pairs"
            ),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PublicDockingSequenceIdentityRow:
    evaluation_case_id: str
    closest_fit_case_id: str
    maximum_sequence_identity: float
    fit_case_count: int
    comparison_evidence_sha256: str
    schema_id: str = PUBLIC_DOCKING_SEQUENCE_ROW_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_DOCKING_SEQUENCE_ROW_SCHEMA_ID:
            raise PublicDockingSplitError("unsupported sequence-row schema")
        object.__setattr__(
            self,
            "evaluation_case_id",
            _text(self.evaluation_case_id, name="evaluation_case_id"),
        )
        object.__setattr__(
            self,
            "closest_fit_case_id",
            _text(self.closest_fit_case_id, name="closest_fit_case_id"),
        )
        object.__setattr__(
            self,
            "maximum_sequence_identity",
            _ratio(self.maximum_sequence_identity, name="maximum_sequence_identity"),
        )
        object.__setattr__(
            self,
            "fit_case_count",
            _positive_int(
                self.fit_case_count,
                name="sequence fit-case count",
                maximum=PUBLIC_DOCKING_MAX_CASES,
            ),
        )
        object.__setattr__(
            self,
            "comparison_evidence_sha256",
            _sha256(self.comparison_evidence_sha256, name="sequence comparison evidence"),
        )

    @property
    def similarity_stratum(self) -> str:
        if self.maximum_sequence_identity <= 0.30:
            return "low_0_to_30_percent"
        if self.maximum_sequence_identity < 0.90:
            return "medium_above_30_below_90_percent"
        return "high_90_to_100_percent"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "evaluation_case_id": self.evaluation_case_id,
            "closest_fit_case_id": self.closest_fit_case_id,
            "maximum_sequence_identity": self.maximum_sequence_identity,
            "similarity_stratum": self.similarity_stratum,
            "fit_case_count": self.fit_case_count,
            "comparison_evidence_sha256": self.comparison_evidence_sha256,
        }


@dataclass(frozen=True, slots=True)
class PublicDockingSequenceIdentityReceipt:
    fit_manifest_sha256: str
    evaluation_manifest_sha256: str
    method: PublicDockingSequenceIdentityMethod
    rows: tuple[PublicDockingSequenceIdentityRow, ...]
    schema_id: str = PUBLIC_DOCKING_SEQUENCE_RECEIPT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_DOCKING_SEQUENCE_RECEIPT_SCHEMA_ID:
            raise PublicDockingSplitError("unsupported sequence-receipt schema")
        for name in ("fit_manifest_sha256", "evaluation_manifest_sha256"):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), name=name),
            )
        if not isinstance(self.method, PublicDockingSequenceIdentityMethod):
            raise PublicDockingSplitError("sequence receipt method has the wrong type")
        rows = tuple(self.rows)
        if (
            not rows
            or len(rows) > PUBLIC_DOCKING_MAX_CASES
            or any(not isinstance(row, PublicDockingSequenceIdentityRow) for row in rows)
            or tuple(row.evaluation_case_id for row in rows)
            != tuple(sorted(row.evaluation_case_id for row in rows))
            or len({row.evaluation_case_id for row in rows}) != len(rows)
        ):
            raise PublicDockingSplitError(
                "sequence receipt rows must be bounded, unique, and ordered"
            )
        if sum(row.fit_case_count for row in rows) > (
            PUBLIC_DOCKING_MAX_SEQUENCE_CASE_PAIRS
        ):
            raise PublicDockingSplitError(
                "sequence receipt exceeds the frozen comparison budget"
            )
        object.__setattr__(self, "rows", rows)

    @property
    def stratum_counts(self) -> dict[str, int]:
        counts = {
            "low_0_to_30_percent": 0,
            "medium_above_30_below_90_percent": 0,
            "high_90_to_100_percent": 0,
        }
        for row in self.rows:
            counts[row.similarity_stratum] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "fit_manifest_sha256": self.fit_manifest_sha256,
            "evaluation_manifest_sha256": self.evaluation_manifest_sha256,
            "method": self.method.to_dict(),
            "method_sha256": self.method.fingerprint_sha256,
            "rows": [row.to_dict() for row in self.rows],
            "case_count": len(self.rows),
            "stratum_counts": self.stratum_counts,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PublicDockingLeakagePolicy:
    maximum_allowed_target_sequence_identity: float = 1.0
    require_temporal_order: bool = False
    require_complete_official_evaluation: bool = True
    require_dataset_access_authorization: bool = True
    require_dataset_selection_evidence: bool = True
    require_receptor_disjoint: bool = True
    require_ligand_disjoint: bool = True
    require_scaffold_disjoint: bool = True
    require_target_sequence_disjoint: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "maximum_allowed_target_sequence_identity",
            _ratio(
                self.maximum_allowed_target_sequence_identity,
                name="maximum_allowed_target_sequence_identity",
            ),
        )
        for name in (
            "require_temporal_order",
            "require_complete_official_evaluation",
            "require_dataset_access_authorization",
            "require_dataset_selection_evidence",
            "require_receptor_disjoint",
            "require_ligand_disjoint",
            "require_scaffold_disjoint",
            "require_target_sequence_disjoint",
        ):
            if not isinstance(getattr(self, name), bool):
                raise PublicDockingSplitError(f"{name} must be boolean")

    def to_dict(self) -> dict[str, Any]:
        return {
            "maximum_allowed_target_sequence_identity": (
                self.maximum_allowed_target_sequence_identity
            ),
            "require_temporal_order": self.require_temporal_order,
            "require_complete_official_evaluation": (
                self.require_complete_official_evaluation
            ),
            "require_dataset_access_authorization": (
                self.require_dataset_access_authorization
            ),
            "require_dataset_selection_evidence": (
                self.require_dataset_selection_evidence
            ),
            "require_receptor_disjoint": self.require_receptor_disjoint,
            "require_ligand_disjoint": self.require_ligand_disjoint,
            "require_scaffold_disjoint": self.require_scaffold_disjoint,
            "require_target_sequence_disjoint": (
                self.require_target_sequence_disjoint
            ),
        }


@dataclass(frozen=True, slots=True)
class PublicDockingLeakageAudit:
    fit_manifest_sha256: str
    evaluation_manifest_sha256: str
    sequence_receipt_sha256: str
    policy: PublicDockingLeakagePolicy
    overlaps: Mapping[str, tuple[str, ...]]
    temporal_violation_case_ids: tuple[str, ...]
    sequence_identity_violation_case_ids: tuple[str, ...]
    sequence_identity_stratum_counts: Mapping[str, int]
    evaluation_case_count: int
    blockers: tuple[str, ...]
    schema_id: str = PUBLIC_DOCKING_LEAKAGE_AUDIT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_DOCKING_LEAKAGE_AUDIT_SCHEMA_ID:
            raise PublicDockingSplitError("unsupported public leakage-audit schema")
        for name in (
            "fit_manifest_sha256",
            "evaluation_manifest_sha256",
            "sequence_receipt_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), name=name),
            )
        if not isinstance(self.policy, PublicDockingLeakagePolicy):
            raise PublicDockingSplitError("public leakage policy has the wrong type")
        overlaps = {
            _text(key, name="overlap kind"): tuple(
                sorted(_text(value, name="overlap identity") for value in values)
            )
            for key, values in self.overlaps.items()
        }
        if any(len(values) != len(set(values)) for values in overlaps.values()):
            raise PublicDockingSplitError("public leakage overlaps must be unique")
        temporal = tuple(
            sorted(_text(value, name="temporal violation case") for value in self.temporal_violation_case_ids)
        )
        sequence = tuple(
            sorted(
                _text(value, name="sequence violation case")
                for value in self.sequence_identity_violation_case_ids
            )
        )
        if len(temporal) != len(set(temporal)) or len(sequence) != len(set(sequence)):
            raise PublicDockingSplitError("public leakage violation cases must be unique")
        counts = {
            _text(key, name="sequence stratum"): int(value)
            for key, value in self.sequence_identity_stratum_counts.items()
        }
        if any(value < 0 for value in counts.values()):
            raise PublicDockingSplitError("sequence stratum counts cannot be negative")
        expected_strata = {
            "low_0_to_30_percent",
            "medium_above_30_below_90_percent",
            "high_90_to_100_percent",
        }
        evaluation_case_count = _positive_int(
            self.evaluation_case_count,
            name="leakage evaluation case count",
            maximum=PUBLIC_DOCKING_MAX_CASES,
        )
        if set(counts) != expected_strata or sum(counts.values()) != evaluation_case_count:
            raise PublicDockingSplitError(
                "sequence stratum counts do not cover the evaluation cases"
            )
        blockers = tuple(_text(value, name="leakage blocker") for value in self.blockers)
        if len(blockers) != len(set(blockers)):
            raise PublicDockingSplitError("public leakage blockers must be unique")
        object.__setattr__(self, "overlaps", MappingProxyType(dict(sorted(overlaps.items()))))
        object.__setattr__(self, "temporal_violation_case_ids", temporal)
        object.__setattr__(self, "sequence_identity_violation_case_ids", sequence)
        object.__setattr__(
            self,
            "sequence_identity_stratum_counts",
            MappingProxyType(dict(sorted(counts.items()))),
        )
        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(self, "evaluation_case_count", evaluation_case_count)

    @property
    def passed(self) -> bool:
        return not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "fit_manifest_sha256": self.fit_manifest_sha256,
            "evaluation_manifest_sha256": self.evaluation_manifest_sha256,
            "sequence_receipt_sha256": self.sequence_receipt_sha256,
            "policy": self.policy.to_dict(),
            "overlaps": {key: list(values) for key, values in self.overlaps.items()},
            "temporal_violation_case_ids": list(self.temporal_violation_case_ids),
            "sequence_identity_violation_case_ids": list(
                self.sequence_identity_violation_case_ids
            ),
            "sequence_identity_stratum_counts": dict(
                self.sequence_identity_stratum_counts
            ),
            "evaluation_case_count": self.evaluation_case_count,
            "blockers": list(self.blockers),
            "passed": self.passed,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _case_values(
    cases: Sequence[PublicDockingSplitCase],
    field_name: str,
) -> set[str]:
    return {str(getattr(case, field_name)) for case in cases}


def audit_public_docking_split_leakage(
    fit: PublicDockingSplitManifest,
    evaluation: PublicDockingSplitManifest,
    sequence_receipt: PublicDockingSequenceIdentityReceipt,
    *,
    policy: PublicDockingLeakagePolicy | None = None,
) -> PublicDockingLeakageAudit:
    """Audit exact, temporal, and sequence-similarity leakage boundaries."""

    if fit.split_role != "fit" or evaluation.split_role == "fit":
        raise PublicDockingSplitError("public leakage audit requires fit/evaluation roles")
    active = policy or PublicDockingLeakagePolicy()
    if (
        sequence_receipt.fit_manifest_sha256 != fit.fingerprint_sha256
        or sequence_receipt.evaluation_manifest_sha256
        != evaluation.fingerprint_sha256
    ):
        raise PublicDockingSplitError(
            "sequence receipt does not bind the public split manifests"
        )
    evaluation_case_ids = tuple(case.case_id for case in evaluation.cases)
    if tuple(row.evaluation_case_id for row in sequence_receipt.rows) != evaluation_case_ids:
        raise PublicDockingSplitError(
            "sequence receipt does not cover every evaluation case"
        )
    fit_case_ids = {case.case_id for case in fit.cases}
    if any(
        row.closest_fit_case_id not in fit_case_ids
        or row.fit_case_count != len(fit.cases)
        for row in sequence_receipt.rows
    ):
        raise PublicDockingSplitError(
            "sequence receipt closest-fit or comparison count is invalid"
        )
    fields = (
        "case_id",
        "pdb_id",
        "target_id",
        "receptor_sha256",
        "ligand_sha256",
        "scaffold_sha256",
        "target_sequence_set_sha256",
        "target_family",
    )
    overlaps = {
        field_name: tuple(
            sorted(
                _case_values(fit.cases, field_name)
                & _case_values(evaluation.cases, field_name)
            )
        )
        for field_name in fields
    }
    blockers: list[str] = []
    required_overlap = {
        "case_id": True,
        "pdb_id": True,
        "target_id": True,
        "receptor_sha256": active.require_receptor_disjoint,
        "ligand_sha256": active.require_ligand_disjoint,
        "scaffold_sha256": active.require_scaffold_disjoint,
        "target_sequence_set_sha256": active.require_target_sequence_disjoint,
        "target_family": False,
    }
    blockers.extend(
        f"{field_name}_overlap"
        for field_name in fields
        if required_overlap[field_name] and overlaps[field_name]
    )
    if fit.source.dataset_id == evaluation.source.dataset_id:
        blockers.append("fit_and_evaluation_dataset_source_overlap")
    if fit.scoring_protocol_sha256 != evaluation.scoring_protocol_sha256:
        blockers.append("scoring_protocol_mismatch")
    if fit.preparation_profile_sha256 != evaluation.preparation_profile_sha256:
        blockers.append("preparation_profile_mismatch")
    if active.require_dataset_access_authorization and (
        not fit.source.access_basis_present
        or not evaluation.source.access_basis_present
    ):
        blockers.append("dataset_access_basis_missing")
    if active.require_dataset_selection_evidence and (
        not fit.source.selection_evidence_present
        or not evaluation.source.selection_evidence_present
    ):
        blockers.append("dataset_selection_review_evidence_missing")
    if (
        active.require_complete_official_evaluation
        and evaluation.source.spec.official_evaluation_case_count is not None
        and not evaluation.complete_official_case_set
    ):
        blockers.append("complete_official_evaluation_case_set_missing")
    if any(case.target_family.lower() == "unknown" for case in (*fit.cases, *evaluation.cases)):
        blockers.append("target_family_assignment_missing")
    if any(case.chemistry_status == "unknown" for case in evaluation.cases):
        blockers.append("supported_chemistry_disposition_missing")
    temporal_violations: tuple[str, ...] = ()
    if active.require_temporal_order:
        latest_fit_date = max(date.fromisoformat(case.release_date) for case in fit.cases)
        temporal_violations = tuple(
            case.case_id
            for case in evaluation.cases
            if date.fromisoformat(case.release_date) <= latest_fit_date
        )
        if temporal_violations:
            blockers.append("evaluation_release_not_after_fit_release")
    sequence_violations = tuple(
        row.evaluation_case_id
        for row in sequence_receipt.rows
        if row.maximum_sequence_identity
        > active.maximum_allowed_target_sequence_identity
    )
    if sequence_violations:
        blockers.append("target_sequence_identity_threshold_exceeded")
    return PublicDockingLeakageAudit(
        fit_manifest_sha256=fit.fingerprint_sha256,
        evaluation_manifest_sha256=evaluation.fingerprint_sha256,
        sequence_receipt_sha256=sequence_receipt.fingerprint_sha256,
        policy=active,
        overlaps=overlaps,
        temporal_violation_case_ids=temporal_violations,
        sequence_identity_violation_case_ids=sequence_violations,
        sequence_identity_stratum_counts=sequence_receipt.stratum_counts,
        evaluation_case_count=len(evaluation.cases),
        blockers=tuple(blockers),
    )


@dataclass(frozen=True, slots=True)
class PublicDockingPartitionBinding:
    split_manifest_sha256: str
    calibration_partition_sha256: str
    calibration_identity_sha256: str
    blockers: tuple[str, ...]
    schema_id: str = PUBLIC_DOCKING_PARTITION_BINDING_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_DOCKING_PARTITION_BINDING_SCHEMA_ID:
            raise PublicDockingSplitError("unsupported partition-binding schema")
        for name in (
            "split_manifest_sha256",
            "calibration_partition_sha256",
            "calibration_identity_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), name=name),
            )
        blockers = tuple(_text(value, name="binding blocker") for value in self.blockers)
        if len(blockers) != len(set(blockers)):
            raise PublicDockingSplitError("partition-binding blockers must be unique")
        object.__setattr__(self, "blockers", blockers)

    @property
    def passed(self) -> bool:
        return not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "split_manifest_sha256": self.split_manifest_sha256,
            "calibration_partition_sha256": self.calibration_partition_sha256,
            "calibration_identity_sha256": self.calibration_identity_sha256,
            "blockers": list(self.blockers),
            "passed": self.passed,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def bind_pose_ranking_partition_to_public_split(
    partition: PoseRankingCalibrationPartition,
    manifest: PublicDockingSplitManifest,
) -> PublicDockingPartitionBinding:
    """Bind every generic calibration row to one public split case manifest."""

    if not isinstance(partition, PoseRankingCalibrationPartition):
        raise PublicDockingSplitError("calibration partition has the wrong type")
    blockers: list[str] = []
    if partition.dataset_id != manifest.source.dataset_id:
        blockers.append("dataset_id_mismatch")
    if partition.dataset_version != manifest.source.spec.dataset_version:
        blockers.append("dataset_version_mismatch")
    if partition.split_role != manifest.split_role:
        blockers.append("split_role_mismatch")
    rows_by_case: dict[str, list[Any]] = {}
    for row in partition.rows:
        rows_by_case.setdefault(row.case_id, []).append(row)
    manifest_by_case = {case.case_id: case for case in manifest.cases}
    if set(rows_by_case) != set(manifest_by_case):
        blockers.append("case_coverage_mismatch")
    for case_id in sorted(set(rows_by_case) & set(manifest_by_case)):
        case = manifest_by_case[case_id]
        for row in rows_by_case[case_id]:
            if row.suite_id != manifest.fingerprint_sha256:
                blockers.append("suite_manifest_identity_mismatch")
            if (
                row.target_id != case.target_id
                or row.target_family != case.target_family
                or row.receptor_sha256 != case.receptor_sha256
                or row.ligand_sha256 != case.ligand_sha256
                or row.scaffold_sha256 != case.scaffold_sha256
            ):
                blockers.append("case_identity_mismatch")
            if row.scoring_protocol_sha256 != manifest.scoring_protocol_sha256:
                blockers.append("scoring_protocol_mismatch")
            if row.preparation_profile_sha256 != manifest.preparation_profile_sha256:
                blockers.append("preparation_profile_mismatch")
    return PublicDockingPartitionBinding(
        split_manifest_sha256=manifest.fingerprint_sha256,
        calibration_partition_sha256=partition.fingerprint_sha256,
        calibration_identity_sha256=partition.identity_fingerprint_sha256,
        blockers=tuple(dict.fromkeys(blockers)),
    )


@dataclass(frozen=True, slots=True)
class PublicPoseRankingEvaluationLink:
    fit_partition_sha256: str
    evaluation_partition_sha256: str
    fit_manifest_sha256: str
    evaluation_manifest_sha256: str
    fit_binding_sha256: str
    evaluation_binding_sha256: str
    public_leakage_audit_sha256: str
    calibration_leakage_audit_sha256: str
    blockers: tuple[str, ...]
    schema_id: str = PUBLIC_POSE_RANKING_EVALUATION_LINK_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_POSE_RANKING_EVALUATION_LINK_SCHEMA_ID:
            raise PublicDockingSplitError("unsupported pose-ranking link schema")
        for name in (
            "fit_partition_sha256",
            "evaluation_partition_sha256",
            "fit_manifest_sha256",
            "evaluation_manifest_sha256",
            "fit_binding_sha256",
            "evaluation_binding_sha256",
            "public_leakage_audit_sha256",
            "calibration_leakage_audit_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), name=name),
            )
        blockers = tuple(_text(value, name="evaluation-link blocker") for value in self.blockers)
        if len(blockers) != len(set(blockers)):
            raise PublicDockingSplitError("evaluation-link blockers must be unique")
        object.__setattr__(self, "blockers", blockers)

    @property
    def ready(self) -> bool:
        return not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "fit_partition_sha256": self.fit_partition_sha256,
            "evaluation_partition_sha256": self.evaluation_partition_sha256,
            "fit_manifest_sha256": self.fit_manifest_sha256,
            "evaluation_manifest_sha256": self.evaluation_manifest_sha256,
            "fit_binding_sha256": self.fit_binding_sha256,
            "evaluation_binding_sha256": self.evaluation_binding_sha256,
            "public_leakage_audit_sha256": self.public_leakage_audit_sha256,
            "calibration_leakage_audit_sha256": (
                self.calibration_leakage_audit_sha256
            ),
            "blockers": list(self.blockers),
            "ready": self.ready,
            "fitted_model_present": False,
            "benchmark_result_present": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def link_public_pose_ranking_evaluation(
    fit_partition: PoseRankingCalibrationPartition,
    evaluation_partition: PoseRankingCalibrationPartition,
    calibration_leakage_audit: PoseRankingLeakageAudit,
    fit_manifest: PublicDockingSplitManifest,
    evaluation_manifest: PublicDockingSplitManifest,
    sequence_receipt: PublicDockingSequenceIdentityReceipt,
    public_leakage_audit: PublicDockingLeakageAudit,
) -> PublicPoseRankingEvaluationLink:
    """Recompute all bindings before admitting public fit/evaluation inputs."""

    fit_binding = bind_pose_ranking_partition_to_public_split(
        fit_partition,
        fit_manifest,
    )
    evaluation_binding = bind_pose_ranking_partition_to_public_split(
        evaluation_partition,
        evaluation_manifest,
    )
    recomputed_public_audit = audit_public_docking_split_leakage(
        fit_manifest,
        evaluation_manifest,
        sequence_receipt,
        policy=public_leakage_audit.policy,
    )
    recomputed_calibration_audit = audit_pose_ranking_leakage(
        fit_partition,
        evaluation_partition,
        policy=calibration_leakage_audit.policy,
    )
    blockers: list[str] = []
    if not fit_binding.passed:
        blockers.append("fit_partition_public_manifest_binding_failed")
    if not evaluation_binding.passed:
        blockers.append("evaluation_partition_public_manifest_binding_failed")
    if (
        public_leakage_audit.fingerprint_sha256
        != recomputed_public_audit.fingerprint_sha256
        or not public_leakage_audit.passed
    ):
        blockers.append("public_split_leakage_audit_failed")
    if (
        calibration_leakage_audit.fingerprint_sha256
        != recomputed_calibration_audit.fingerprint_sha256
        or not calibration_leakage_audit.passed
    ):
        blockers.append("calibration_partition_leakage_audit_failed")
    return PublicPoseRankingEvaluationLink(
        fit_partition_sha256=fit_partition.fingerprint_sha256,
        evaluation_partition_sha256=evaluation_partition.fingerprint_sha256,
        fit_manifest_sha256=fit_manifest.fingerprint_sha256,
        evaluation_manifest_sha256=evaluation_manifest.fingerprint_sha256,
        fit_binding_sha256=fit_binding.fingerprint_sha256,
        evaluation_binding_sha256=evaluation_binding.fingerprint_sha256,
        public_leakage_audit_sha256=public_leakage_audit.fingerprint_sha256,
        calibration_leakage_audit_sha256=(
            calibration_leakage_audit.fingerprint_sha256
        ),
        blockers=tuple(blockers),
    )


@dataclass(frozen=True, slots=True)
class PublicPoseRankingResultBinding:
    evaluation_link_sha256: str
    evaluation_report_sha256: str
    evaluation_manifest_sha256: str
    all_case_denominator: int
    target_family_case_denominators: Mapping[str, int]
    blockers: tuple[str, ...]
    schema_id: str = PUBLIC_POSE_RANKING_RESULT_BINDING_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_POSE_RANKING_RESULT_BINDING_SCHEMA_ID:
            raise PublicDockingSplitError("unsupported public result-binding schema")
        for name in (
            "evaluation_link_sha256",
            "evaluation_report_sha256",
            "evaluation_manifest_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), name=name),
            )
        denominator = _positive_int(
            self.all_case_denominator,
            name="result all-case denominator",
            maximum=PUBLIC_DOCKING_MAX_CASES,
        )
        families = {
            _text(key, name="result target family"): _positive_int(
                value,
                name="result target-family denominator",
                maximum=PUBLIC_DOCKING_MAX_CASES,
            )
            for key, value in self.target_family_case_denominators.items()
        }
        if sum(families.values()) != denominator:
            raise PublicDockingSplitError(
                "target-family denominators do not sum to the all-case denominator"
            )
        blockers = tuple(_text(value, name="result-binding blocker") for value in self.blockers)
        if len(blockers) != len(set(blockers)):
            raise PublicDockingSplitError("result-binding blockers must be unique")
        object.__setattr__(self, "all_case_denominator", denominator)
        object.__setattr__(
            self,
            "target_family_case_denominators",
            MappingProxyType(dict(sorted(families.items()))),
        )
        object.__setattr__(self, "blockers", blockers)

    @property
    def passed(self) -> bool:
        return not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "evaluation_link_sha256": self.evaluation_link_sha256,
            "evaluation_report_sha256": self.evaluation_report_sha256,
            "evaluation_manifest_sha256": self.evaluation_manifest_sha256,
            "all_case_denominator": self.all_case_denominator,
            "target_family_case_denominators": dict(
                self.target_family_case_denominators
            ),
            "blockers": list(self.blockers),
            "passed": self.passed,
            "independent_rerun_complete": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def bind_public_pose_ranking_result(
    report: PoseRankingEvaluationReport,
    link: PublicPoseRankingEvaluationLink,
    evaluation_manifest: PublicDockingSplitManifest,
) -> PublicPoseRankingResultBinding:
    """Verify report case/family denominators against the public manifest."""

    if not isinstance(report, PoseRankingEvaluationReport):
        raise PublicDockingSplitError("pose-ranking report has the wrong type")
    manifest_cases = {case.case_id: case for case in evaluation_manifest.cases}
    report_cases = {case.case_id: case for case in report.cases}
    blockers: list[str] = []
    if not link.ready:
        blockers.append("public_pose_ranking_evaluation_link_not_ready")
    if evaluation_manifest.fingerprint_sha256 != link.evaluation_manifest_sha256:
        blockers.append("evaluation_manifest_link_mismatch")
    if report.evaluation_partition_sha256 != link.evaluation_partition_sha256:
        blockers.append("evaluation_partition_link_mismatch")
    if report.leakage_audit_sha256 != link.calibration_leakage_audit_sha256:
        blockers.append("calibration_leakage_audit_link_mismatch")
    if set(manifest_cases) != set(report_cases):
        blockers.append("result_all_case_denominator_mismatch")
    for case_id in sorted(set(manifest_cases) & set(report_cases)):
        manifest_case = manifest_cases[case_id]
        report_case = report_cases[case_id]
        if (
            report_case.target_id != manifest_case.target_id
            or report_case.target_family != manifest_case.target_family
        ):
            blockers.append("result_case_target_or_family_mismatch")
    expected_families: dict[str, int] = {}
    for case in evaluation_manifest.cases:
        expected_families[case.target_family] = (
            expected_families.get(case.target_family, 0) + 1
        )
    report_families = {
        family.target_family: family.case_count for family in report.family_metrics
    }
    if report_families != expected_families:
        blockers.append("result_target_family_denominator_mismatch")
    if report.all_case_denominator != len(evaluation_manifest.cases):
        blockers.append("result_all_case_denominator_mismatch")
    return PublicPoseRankingResultBinding(
        evaluation_link_sha256=link.fingerprint_sha256,
        evaluation_report_sha256=report.fingerprint_sha256,
        evaluation_manifest_sha256=evaluation_manifest.fingerprint_sha256,
        all_case_denominator=len(evaluation_manifest.cases),
        target_family_case_denominators=expected_families,
        blockers=tuple(dict.fromkeys(blockers)),
    )


__all__ = [
    "CASF_2016_DATASET_ID",
    "PDBBIND_V2020_DATASET_ID",
    "POSEBUSTERS_2023_308_DATASET_ID",
    "POSEBUSTERS_2023_308_CASE_ID_PROJECTION_SHA256",
    "POSEBUSTERS_2023_308_SELECTION_SHA256",
    "POSEBUSTERS_2023_ARCHIVE_SHA256",
    "POSEBUSTERS_2023_ARCHIVE_SIZE_BYTES",
    "PUBLIC_DOCKING_DATASET_IDS",
    "PUBLIC_DOCKING_DATASET_SOURCE_SCHEMA_ID",
    "PUBLIC_DOCKING_DATASET_SPECS",
    "PUBLIC_DOCKING_LEAKAGE_AUDIT_SCHEMA_ID",
    "PUBLIC_DOCKING_MAX_CASES",
    "PUBLIC_DOCKING_MAX_SEQUENCE_CASE_PAIRS",
    "PUBLIC_DOCKING_PARTITION_BINDING_SCHEMA_ID",
    "PUBLIC_DOCKING_SEQUENCE_METHOD_ID",
    "PUBLIC_DOCKING_SEQUENCE_METHOD_SCHEMA_ID",
    "PUBLIC_DOCKING_SEQUENCE_RECEIPT_SCHEMA_ID",
    "PUBLIC_DOCKING_SEQUENCE_ROW_SCHEMA_ID",
    "PUBLIC_DOCKING_SPLIT_CASE_SCHEMA_ID",
    "PUBLIC_DOCKING_SPLIT_MANIFEST_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_EVALUATION_LINK_SCHEMA_ID",
    "PUBLIC_POSE_RANKING_RESULT_BINDING_SCHEMA_ID",
    "FrozenPublicDockingDatasetSpec",
    "PublicDockingDatasetSource",
    "PublicDockingLeakageAudit",
    "PublicDockingLeakagePolicy",
    "PublicDockingPartitionBinding",
    "PublicDockingSequenceIdentityMethod",
    "PublicDockingSequenceIdentityReceipt",
    "PublicDockingSequenceIdentityRow",
    "PublicDockingSplitCase",
    "PublicDockingSplitError",
    "PublicDockingSplitManifest",
    "PublicPoseRankingEvaluationLink",
    "PublicPoseRankingResultBinding",
    "audit_public_docking_split_leakage",
    "bind_pose_ranking_partition_to_public_split",
    "bind_public_pose_ranking_result",
    "link_public_pose_ranking_evaluation",
]
