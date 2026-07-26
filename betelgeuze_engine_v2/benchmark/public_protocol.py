"""Frozen public redocking protocol definition without benchmark execution.

The protocol binds a small, public, license-metadata-reviewed contract cohort to
exact upstream bytes, predefined metrics, failure-inclusive denominators, and
the source identities of the bounded Engine v2 scorers.  It deliberately does
not download data, run docking, emit benchmark results, establish statistical
representativeness, or promote scientific, benchmark, product, or customer
claims.

The four cases are the packaged PDB examples in one immutable PoseBusters
repository commit.  They are protocol fixtures, not the PoseBusters Benchmark
and not a scientifically sufficient holdout.  Raw receptor and ligand files are
not bundled by this package.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from .manifest import (
    BenchmarkCase,
    BenchmarkManifest,
    BenchmarkReport,
    MetricAggregation,
    MetricDefinition,
    MetricDirection,
)

PUBLIC_BENCHMARK_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_benchmark_protocol/1.1.0"
)
PUBLIC_BENCHMARK_PROTOCOL_ID = (
    "posebusters_packaged_public_redocking_contract_cohort/1.1.0"
)
PUBLIC_BENCHMARK_PROTOCOL_VERSION = "1.1.0"
PUBLIC_BENCHMARK_PROTOCOL_FROZEN_AT_UTC = "2026-07-26T00:00:00Z"
FROZEN_PUBLIC_BENCHMARK_PROTOCOL_SHA256 = (
    "065a672ca7c1aa8979ea7b27121ba0d87dbae48c1c3d722513844c59d6bf0b6d"
)

POSEBUSTERS_REPOSITORY_URL = "https://github.com/maabuu/posebusters"
POSEBUSTERS_SOURCE_COMMIT_SHA = "1a5f26aa7270fafba21b7fec8b3633f4c4e45ead"
POSEBUSTERS_SOURCE_LICENSE_SPDX_ID = "MIT"
POSEBUSTERS_SOURCE_LICENSE_SHA256 = (
    "90bc701d0de82dc12c78cfde9f7d4c5d66e2dbc21604d95b67c5ad4e368a4149"
)
POSEBUSTERS_SOURCE_LICENSE_SIZE_BYTES = 1_076
POSEBUSTERS_DATASET_MANIFEST_SHA256 = (
    "a137dec32514708ab633b37b75fb2b0fe639acf91b252ed8d35f88facb91adaa"
)
POSEBUSTERS_DATASET_MANIFEST_SIZE_BYTES = 424

RCSB_USAGE_POLICY_URL = "https://www.rcsb.org/pages/usage-policy"
RCSB_ARCHIVE_LICENSE_SPDX_ID = "CC0-1.0"

PRIMARY_RMSD_METRIC_ID = "top1_symmetry_aware_heavy_atom_rmsd_angstrom"
BOUNDED_VALIDITY_METRIC_ID = "bounded_pose_valid"
PRIMARY_SUCCESS_METRIC_ID = "primary_pose_success"
PRIMARY_RMSD_THRESHOLD_ANGSTROM = 2.0

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


class PublicBenchmarkProtocolError(ValueError):
    """The frozen public protocol or a caller-supplied receipt drifted."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise PublicBenchmarkProtocolError(
            "public benchmark protocol is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: str, *, name: str) -> str:
    digest = str(value or "").lower()
    if not _SHA256_RE.fullmatch(digest):
        raise PublicBenchmarkProtocolError(f"{name} must be a lowercase SHA-256")
    return digest


def _immutable_raw_url(relative_path: str) -> str:
    return (
        "https://raw.githubusercontent.com/maabuu/posebusters/"
        f"{POSEBUSTERS_SOURCE_COMMIT_SHA}/{relative_path}"
    )


@dataclass(frozen=True, slots=True)
class PublicBenchmarkArtifact:
    """Immutable identity of one upstream protocol input; bytes stay external."""

    role: str
    relative_path: str
    immutable_url: str
    sha256: str
    size_bytes: int
    media_type: str

    def __post_init__(self) -> None:
        for value in (
            self.role,
            self.relative_path,
            self.immutable_url,
            self.media_type,
        ):
            if not isinstance(value, str) or not value:
                raise PublicBenchmarkProtocolError(
                    "artifact text fields must be non-empty"
                )
        if not self.immutable_url.startswith("https://"):
            raise PublicBenchmarkProtocolError("artifact URL must use HTTPS")
        relative = Path(self.relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise PublicBenchmarkProtocolError(
                "artifact relative_path must stay within the source repository"
            )
        if POSEBUSTERS_SOURCE_COMMIT_SHA not in self.immutable_url:
            raise PublicBenchmarkProtocolError(
                "artifact URL must bind the reviewed source commit"
            )
        object.__setattr__(
            self, "sha256", _require_sha256(self.sha256, name="artifact.sha256")
        )
        if type(self.size_bytes) is not int or self.size_bytes <= 0:
            raise PublicBenchmarkProtocolError(
                "artifact size_bytes must be a positive integer"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "relative_path": self.relative_path,
            "immutable_url": self.immutable_url,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
            "bundled": False,
        }

    def verify_bytes(self, source: bytes) -> str:
        """Verify independently supplied bytes without network access or parsing."""

        if not isinstance(source, bytes):
            raise TypeError("public benchmark artifact source must be bytes")
        if len(source) != self.size_bytes:
            raise PublicBenchmarkProtocolError(
                "public benchmark artifact size mismatch"
            )
        observed = hashlib.sha256(source).hexdigest()
        if observed != self.sha256:
            raise PublicBenchmarkProtocolError(
                "public benchmark artifact SHA-256 mismatch"
            )
        return observed


@dataclass(frozen=True, slots=True)
class PublicBenchmarkCaseDefinition:
    """One frozen receptor/reference-ligand pair in the contract cohort."""

    case_id: str
    pdb_id: str
    receptor: PublicBenchmarkArtifact
    reference_ligands: PublicBenchmarkArtifact
    ligand_identity_seed: PublicBenchmarkArtifact

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id:
            raise PublicBenchmarkProtocolError("case_id must be non-empty")
        pdb_id = str(self.pdb_id or "").lower()
        if not re.fullmatch(r"[0-9][a-z0-9]{3}", pdb_id):
            raise PublicBenchmarkProtocolError("pdb_id must be a four-character PDB ID")
        object.__setattr__(self, "pdb_id", pdb_id)
        if (
            self.receptor.role != "receptor"
            or self.reference_ligands.role != "reference_ligands"
            or self.ligand_identity_seed.role != "ligand_identity_seed"
        ):
            raise PublicBenchmarkProtocolError("case artifact roles are inconsistent")
        if any(
            f"/{pdb_id}/" not in artifact.relative_path
            for artifact in (
                self.receptor,
                self.reference_ligands,
                self.ligand_identity_seed,
            )
        ):
            raise PublicBenchmarkProtocolError(
                "case artifacts must remain under the matching PDB ID"
            )

    @property
    def input_sha256(self) -> str:
        return _sha256(
            {
                "case_id": self.case_id,
                "pdb_id": self.pdb_id,
                "source_commit_sha": POSEBUSTERS_SOURCE_COMMIT_SHA,
                "receptor": self.receptor.to_dict(),
                "reference_ligands": self.reference_ligands.to_dict(),
                "ligand_identity_seed": self.ligand_identity_seed.to_dict(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "pdb_id": self.pdb_id,
            "input_sha256": self.input_sha256,
            "receptor": self.receptor.to_dict(),
            "reference_ligands": self.reference_ligands.to_dict(),
            "ligand_identity_seed": self.ligand_identity_seed.to_dict(),
            "split": "frozen_test_contract_cohort",
        }

    def to_benchmark_case(self) -> BenchmarkCase:
        return BenchmarkCase(
            case_id=self.case_id,
            input_sha256=self.input_sha256,
            task="public_redocking_protocol_definition",
            target_id=self.pdb_id,
            ligand_id=f"{self.pdb_id}:packaged_reference_ligands",
            metadata={
                "source_commit_sha": POSEBUSTERS_SOURCE_COMMIT_SHA,
                "receptor_sha256": self.receptor.sha256,
                "reference_ligands_sha256": self.reference_ligands.sha256,
                "ligand_identity_seed_sha256": self.ligand_identity_seed.sha256,
                "ligand_identity_seed_coordinates_used": False,
                "raw_data_bundled": False,
                "protocol_fixture_only": True,
            },
        )


@dataclass(frozen=True, slots=True)
class PublicBenchmarkScorerIdentity:
    """Reviewed source-file identity used by a future authorized evaluator."""

    purpose: str
    module: str
    relative_path: str
    source_sha256: str

    def __post_init__(self) -> None:
        for value in (self.purpose, self.module, self.relative_path):
            if not isinstance(value, str) or not value:
                raise PublicBenchmarkProtocolError(
                    "scorer identity text fields must be non-empty"
                )
        object.__setattr__(
            self,
            "source_sha256",
            _require_sha256(self.source_sha256, name="scorer.source_sha256"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "purpose": self.purpose,
            "module": self.module,
            "relative_path": self.relative_path,
            "source_sha256": self.source_sha256,
        }


def _metric_definitions() -> tuple[MetricDefinition, ...]:
    return (
        MetricDefinition(
            metric_id=PRIMARY_RMSD_METRIC_ID,
            unit="angstrom",
            direction=MetricDirection.MINIMIZE,
            required=True,
            valid_min=0.0,
            valid_max=100.0,
            pass_threshold=PRIMARY_RMSD_THRESHOLD_ANGSTROM,
            aggregation=MetricAggregation.MEAN,
            confidence_level=0.95,
            bootstrap_samples=0,
        ),
        MetricDefinition(
            metric_id=BOUNDED_VALIDITY_METRIC_ID,
            unit=None,
            direction=MetricDirection.MAXIMIZE,
            required=True,
            valid_min=0.0,
            valid_max=1.0,
            pass_threshold=1.0,
            aggregation=MetricAggregation.MEAN,
            confidence_level=0.95,
            bootstrap_samples=0,
        ),
        MetricDefinition(
            metric_id=PRIMARY_SUCCESS_METRIC_ID,
            unit=None,
            direction=MetricDirection.MAXIMIZE,
            required=True,
            valid_min=0.0,
            valid_max=1.0,
            pass_threshold=1.0,
            aggregation=MetricAggregation.MEAN,
            confidence_level=0.95,
            bootstrap_samples=0,
        ),
    )


@dataclass(frozen=True, slots=True)
class FrozenPublicBenchmarkProtocol:
    """Versioned protocol/manifest definition with every promotion path closed."""

    cases: tuple[PublicBenchmarkCaseDefinition, ...]
    scorer_identities: tuple[PublicBenchmarkScorerIdentity, ...]
    schema_id: str = PUBLIC_BENCHMARK_PROTOCOL_SCHEMA_ID
    protocol_id: str = PUBLIC_BENCHMARK_PROTOCOL_ID
    protocol_version: str = PUBLIC_BENCHMARK_PROTOCOL_VERSION
    frozen_at_utc: str = PUBLIC_BENCHMARK_PROTOCOL_FROZEN_AT_UTC

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_BENCHMARK_PROTOCOL_SCHEMA_ID:
            raise PublicBenchmarkProtocolError("unsupported public protocol schema")
        if self.protocol_id != PUBLIC_BENCHMARK_PROTOCOL_ID:
            raise PublicBenchmarkProtocolError("unsupported public protocol ID")
        if self.protocol_version != PUBLIC_BENCHMARK_PROTOCOL_VERSION:
            raise PublicBenchmarkProtocolError("unsupported public protocol version")
        if not _UTC_RE.fullmatch(self.frozen_at_utc):
            raise PublicBenchmarkProtocolError(
                "frozen_at_utc must be second-resolution UTC"
            )
        if len(self.cases) != 4:
            raise PublicBenchmarkProtocolError(
                "public protocol must contain exactly four cases"
            )
        case_ids = [case.case_id for case in self.cases]
        if case_ids != sorted(case_ids) or len(case_ids) != len(set(case_ids)):
            raise PublicBenchmarkProtocolError(
                "public protocol cases must be uniquely sorted by case_id"
            )
        purposes = [identity.purpose for identity in self.scorer_identities]
        if purposes != sorted(purposes) or len(purposes) != len(set(purposes)):
            raise PublicBenchmarkProtocolError(
                "scorer identities must be uniquely sorted by purpose"
            )
        if not _COMMIT_RE.fullmatch(POSEBUSTERS_SOURCE_COMMIT_SHA):
            raise PublicBenchmarkProtocolError("source commit must be a Git SHA-1")

    @property
    def benchmark_manifest(self) -> BenchmarkManifest:
        return BenchmarkManifest(
            benchmark_id="posebusters-packaged-public-redocking-contract-cohort",
            dataset_name="PoseBusters packaged PDB examples",
            dataset_version=POSEBUSTERS_SOURCE_COMMIT_SHA,
            cases=tuple(case.to_benchmark_case() for case in self.cases),
            protocol_id=self.protocol_id,
            metric_definitions=_metric_definitions(),
            metadata={
                "case_count": len(self.cases),
                "source_manifest_sha256": POSEBUSTERS_DATASET_MANIFEST_SHA256,
                "failure_rows_retained": True,
                "denominator": "all_manifest_cases",
                "raw_data_bundled": False,
                "test_set_tuning_allowed": False,
                "protocol_fixture_only": True,
                "statistical_representativeness_claimed": False,
                "posebusters_benchmark_equivalence_claimed": False,
                "reference_selection_rule": (
                    "all_reference_records_matching_seed_labeled_graph_identity"
                ),
                "ligand_identity_seed_coordinates_used": False,
                "rmsd_method": (
                    "minimum_direct_receptor_frame_rmsd_across_all_graph_matched_"
                    "reference_records_and_stereo_preserving_graph_automorphisms"
                ),
                "reference_pose_aggregation": "minimum_over_all_matched_records",
                "ligand_only_alignment_allowed": False,
                "receptor_frame_required": True,
            },
        )

    @property
    def protocol_payload(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "protocol_id": self.protocol_id,
            "protocol_version": self.protocol_version,
            "frozen_at_utc": self.frozen_at_utc,
            "source": {
                "repository_url": POSEBUSTERS_REPOSITORY_URL,
                "source_commit_sha": POSEBUSTERS_SOURCE_COMMIT_SHA,
                "dataset_manifest": {
                    "relative_path": "posebusters/datasets/pdb.csv",
                    "immutable_url": _immutable_raw_url("posebusters/datasets/pdb.csv"),
                    "sha256": POSEBUSTERS_DATASET_MANIFEST_SHA256,
                    "size_bytes": POSEBUSTERS_DATASET_MANIFEST_SIZE_BYTES,
                    "bundled": False,
                },
                "repository_license": {
                    "spdx_id": POSEBUSTERS_SOURCE_LICENSE_SPDX_ID,
                    "immutable_url": _immutable_raw_url("LICENSE"),
                    "sha256": POSEBUSTERS_SOURCE_LICENSE_SHA256,
                    "size_bytes": POSEBUSTERS_SOURCE_LICENSE_SIZE_BYTES,
                },
                "underlying_structure_archive_license": {
                    "spdx_id": RCSB_ARCHIVE_LICENSE_SPDX_ID,
                    "policy_url": RCSB_USAGE_POLICY_URL,
                },
                "license_metadata_reviewed": True,
                "legal_compliance_approved": False,
                "retrieved_at_utc": self.frozen_at_utc,
            },
            "review": {
                "reviewer_role": "repository_maintainer",
                "reviewer_identity_sha256": (
                    "ffaaea9cebb5975ed140fa0633ea4cb44e1f241f6bc73c916164c0ea5123b584"
                ),
                "reviewed_at_utc": self.frozen_at_utc,
                "superseded": False,
                "supersedes_protocol_sha256": (
                    "7888db6264aec25b8bf1f3c30b4c601062b0831cf610a84c9700d0c89a64ed90"
                ),
                "revoked": False,
                "revocation_reason": "",
            },
            "cases": [case.to_dict() for case in self.cases],
            "benchmark_manifest": self.benchmark_manifest.to_dict(),
            "benchmark_manifest_sha256": self.benchmark_manifest.fingerprint_sha256,
            "scorer_identities": [
                identity.to_dict() for identity in self.scorer_identities
            ],
            "endpoint_policy": {
                "rmsd_metric_id": PRIMARY_RMSD_METRIC_ID,
                "rmsd_threshold_angstrom": PRIMARY_RMSD_THRESHOLD_ANGSTROM,
                "rmsd_method": (
                    "minimum_direct_receptor_frame_rmsd_across_all_graph_matched_"
                    "reference_records_and_stereo_preserving_graph_automorphisms"
                ),
                "reference_pose_aggregation": "minimum_over_all_matched_records",
                "ligand_only_alignment_allowed": False,
                "receptor_frame_required": True,
                "reference_selection_rule": (
                    "all_reference_records_matching_seed_labeled_graph_identity"
                ),
                "ligand_identity_seed_coordinates_used": False,
                "validity_metric_id": BOUNDED_VALIDITY_METRIC_ID,
                "validity_method": (
                    "all_bounded_engine_v2_validity_checks_must_be_evaluated_and_pass"
                ),
                "primary_success_metric_id": PRIMARY_SUCCESS_METRIC_ID,
                "primary_success_rule": (
                    "rmsd_lte_2_angstrom_and_bounded_pose_valid_equals_1"
                ),
                "failure_rows_retained": True,
                "denominator": "all_manifest_cases",
                "missing_or_failed_case_counts_as_primary_failure": True,
                "symmetry_mapping_generation_implemented": True,
                "symmetry_permutation_direction": (
                    "reference_position_to_candidate_position"
                ),
                "reference_ligand_match_materializer_implemented": True,
                "posebusters_parity_claimed": False,
            },
            "split_policy": {
                "source_manifest_all_rows_included": True,
                "case_selection": "all_four_rows_from_immutable_source_manifest",
                "split": "test_contract_cohort_only",
                "training_use_allowed": False,
                "validation_tuning_use_allowed": False,
                "case_selection_frozen_before_results": True,
                "scientific_holdout_status": "not_established",
            },
            "execution_policy": {
                "network_fetch_implemented": False,
                "raw_data_bundled": False,
                "offline_reference_materialization_implemented": True,
                "direct_reference_rmsd_evaluation_implemented": True,
                "benchmark_execution_authorized": False,
                "result_document_created": False,
                "result_publication_authorized": False,
                "test_set_tuning_allowed": False,
                "ligand_identity_seed_coordinates_used": False,
                "future_report_must_bind": [
                    "code_commit",
                    "environment_fingerprint_sha256",
                    "exact_argv",
                    "global_seed",
                    "one_ordered_row_per_manifest_case",
                    "artifact_sha256_when_emitted",
                ],
            },
            "claim_policy": {
                "protocol_definition_frozen": True,
                "license_metadata_reviewed": True,
                "legal_compliance_approved": False,
                "statistical_representativeness_established": False,
                "scientifically_validated": False,
                "public_benchmark_validation": False,
                "benchmark_validated": False,
                "product_qualified": False,
                "customer_execution_enabled": False,
                "claim_safe": False,
            },
            "blockers": [
                "four_case_contract_cohort_not_statistically_representative",
                "posebusters_benchmark_equivalence_not_established",
                "v2000_labeled_graph_identity_not_independent_chemical_standardization",
                "atom_stereo_parity_beyond_directional_v2000_bonds_not_interpreted",
                "public_benchmark_not_executed",
                "public_holdout_results_missing",
                "independent_attestation_missing",
                "legal_compliance_determination_not_made",
                "scientific_validation_missing",
                "product_integration_not_qualified",
            ],
        }

    @property
    def protocol_sha256(self) -> str:
        return _sha256(self.protocol_payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.protocol_payload,
            "protocol_sha256": self.protocol_sha256,
        }


def _artifact(
    pdb_id: str,
    *,
    role: str,
    suffix: str,
    sha256: str,
    size_bytes: int,
    media_type: str,
) -> PublicBenchmarkArtifact:
    relative_path = f"posebusters/datasets/pdb/{pdb_id}/{pdb_id}_{suffix}"
    return PublicBenchmarkArtifact(
        role=role,
        relative_path=relative_path,
        immutable_url=_immutable_raw_url(relative_path),
        sha256=sha256,
        size_bytes=size_bytes,
        media_type=media_type,
    )


def _case(
    pdb_id: str,
    *,
    receptor_sha256: str,
    receptor_size_bytes: int,
    reference_sha256: str,
    reference_size_bytes: int,
    identity_seed_sha256: str,
    identity_seed_size_bytes: int,
) -> PublicBenchmarkCaseDefinition:
    return PublicBenchmarkCaseDefinition(
        case_id=f"posebusters-packaged-{pdb_id}",
        pdb_id=pdb_id,
        receptor=_artifact(
            pdb_id,
            role="receptor",
            suffix="protein_one_lig_removed.pdb",
            sha256=receptor_sha256,
            size_bytes=receptor_size_bytes,
            media_type="chemical/x-pdb",
        ),
        reference_ligands=_artifact(
            pdb_id,
            role="reference_ligands",
            suffix="ligands.sdf",
            sha256=reference_sha256,
            size_bytes=reference_size_bytes,
            media_type="chemical/x-mdl-sdfile",
        ),
        ligand_identity_seed=_artifact(
            pdb_id,
            role="ligand_identity_seed",
            suffix="ligand.sdf",
            sha256=identity_seed_sha256,
            size_bytes=identity_seed_size_bytes,
            media_type="chemical/x-mdl-sdfile",
        ),
    )


def _build_frozen_public_benchmark_protocol() -> FrozenPublicBenchmarkProtocol:
    return FrozenPublicBenchmarkProtocol(
        cases=(
            _case(
                "1ia1",
                receptor_sha256=(
                    "9c0f2d9afc49cd93aefad3a9a8365172f5378b72cae227c8db643a8c5570e487"
                ),
                receptor_size_bytes=265_544,
                reference_sha256=(
                    "04cd2739947ce7aaaa460ff596dccf297542556183e1902fa11bdf1391c0740e"
                ),
                reference_size_bytes=3_366,
                identity_seed_sha256=(
                    "1f956bad53c222ab67c0b1b618d1388f2fbae3c246923f29233da6cad7780cb4"
                ),
                identity_seed_size_bytes=1_678,
            ),
            _case(
                "1of6",
                receptor_sha256=(
                    "719dabf584c6fbc94a92a126ea8a9eacaa72ac4f2276c338246f96b3f9d88536"
                ),
                receptor_size_bytes=1_694_211,
                reference_sha256=(
                    "0e2bb788311a97619031d788958a443e14c6efaac544d75d9d4fbfc0f9f12ce5"
                ),
                reference_size_bytes=9_272,
                identity_seed_sha256=(
                    "0b767345fd5a0e6b1f4efcc677309f58c27afc475d4e5cea403e79d96907f99c"
                ),
                identity_seed_size_bytes=1_154,
            ),
            _case(
                "1s3v",
                receptor_sha256=(
                    "cefe1b69ac9716e7807ba51304130e4d5483855de9378b3d7165613df84bffa4"
                ),
                receptor_size_bytes=121_812,
                reference_sha256=(
                    "a48901fc0191c52bc31dabe35f87ceec3d6c9a094c89da693d1efaf81e3bc0de"
                ),
                reference_size_bytes=2_347,
                identity_seed_sha256=(
                    "5778a2503ef761960d2e366809bda4419cdece2e29a2b34def44a06bb20cc4a0"
                ),
                identity_seed_size_bytes=2_342,
            ),
            _case(
                "1uou",
                receptor_sha256=(
                    "91e9a7fb292444ac4fa0076c4fa981d2151952b60101f334e352db494a1cf4fc"
                ),
                receptor_size_bytes=260_079,
                reference_sha256=(
                    "208adf94ad061dc2e90012793b6a60de21a8fa7d5157b014be1579a07ab81d26"
                ),
                reference_size_bytes=1_421,
                identity_seed_sha256=(
                    "d2e305d4309c4474524805a08fc17568a8d8ca5815fbf697e1d95d15ed717871"
                ),
                identity_seed_size_bytes=1_416,
            ),
        ),
        scorer_identities=(
            PublicBenchmarkScorerIdentity(
                purpose="failure_inclusive_report",
                module="betelgeuze_engine_v2.benchmark.manifest",
                relative_path="betelgeuze_engine_v2/benchmark/manifest.py",
                source_sha256=(
                    "a105548267bc8167ff86f4da8542f9a27c3d8aa9912627eab7fd2a8188a9c9c2"
                ),
            ),
            PublicBenchmarkScorerIdentity(
                purpose="pose_validity",
                module="betelgeuze_engine_v2.docking.validity",
                relative_path="betelgeuze_engine_v2/docking/validity.py",
                source_sha256=(
                    "996cfd1ea8ea230a5cb3a8449142babc1e17cf4103f07e70054fe977aef0318e"
                ),
            ),
            PublicBenchmarkScorerIdentity(
                purpose="reference_materialization",
                module="betelgeuze_engine_v2.benchmark.public_materialization",
                relative_path=(
                    "betelgeuze_engine_v2/benchmark/public_materialization.py"
                ),
                source_sha256=(
                    "3feca800603b22e1ad89fb7a9d5a42ac412d7c4b3f4fa2ea539b3228da8987b2"
                ),
            ),
            PublicBenchmarkScorerIdentity(
                purpose="reference_molecular_models",
                module="betelgeuze_engine_v2.molecular.models",
                relative_path="betelgeuze_engine_v2/molecular/models.py",
                source_sha256=(
                    "b1aad45f4131c133a64049a31b809fcc481e92c29242a1ab9f0e2f2190dca638"
                ),
            ),
            PublicBenchmarkScorerIdentity(
                purpose="reference_molecular_validation",
                module="betelgeuze_engine_v2.molecular.validation",
                relative_path="betelgeuze_engine_v2/molecular/validation.py",
                source_sha256=(
                    "dfc5dbae1900095a74019db939efb4d4066dc1f50a0712bbcd5db125be9f6aba"
                ),
            ),
            PublicBenchmarkScorerIdentity(
                purpose="reference_sdf_parser",
                module="betelgeuze_engine_v2.io.sdf",
                relative_path="betelgeuze_engine_v2/io/sdf.py",
                source_sha256=(
                    "b0dd24c2902127606f053c09383bd0573f2c98fe3610a57557e4cc12098cc42e"
                ),
            ),
            PublicBenchmarkScorerIdentity(
                purpose="symmetry_aware_rmsd",
                module="betelgeuze_engine_v2.docking.metrics",
                relative_path="betelgeuze_engine_v2/docking/metrics.py",
                source_sha256=(
                    "e47915e80fdec830243f28105bee4f43b7f7b9d92a4ece73826dc29282305df9"
                ),
            ),
        ),
    )


def frozen_public_benchmark_protocol() -> FrozenPublicBenchmarkProtocol:
    """Return the exact reviewed protocol definition or fail on drift."""

    protocol = _build_frozen_public_benchmark_protocol()
    if protocol.protocol_sha256 != FROZEN_PUBLIC_BENCHMARK_PROTOCOL_SHA256:
        raise PublicBenchmarkProtocolError(
            "public benchmark protocol drifted from its frozen SHA-256"
        )
    return protocol


def public_benchmark_protocol_document() -> dict[str, Any]:
    return frozen_public_benchmark_protocol().to_dict()


def public_benchmark_protocol_json_bytes() -> bytes:
    return _canonical_bytes(public_benchmark_protocol_document()) + b"\n"


def require_public_benchmark_protocol_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise PublicBenchmarkProtocolError(
            "public benchmark protocol document must be a mapping"
        )
    if dict(payload) != public_benchmark_protocol_document():
        raise PublicBenchmarkProtocolError(
            "public benchmark protocol document drifted from the frozen definition"
        )
    return payload


def require_public_benchmark_case_metrics(
    metrics: Mapping[str, float],
) -> Mapping[str, float]:
    """Enforce the frozen primary endpoint relation on one successful row."""

    expected_ids = {
        PRIMARY_RMSD_METRIC_ID,
        BOUNDED_VALIDITY_METRIC_ID,
        PRIMARY_SUCCESS_METRIC_ID,
    }
    if set(metrics) != expected_ids:
        raise PublicBenchmarkProtocolError(
            "public benchmark success metrics do not match the frozen endpoint schema"
        )
    try:
        rmsd = float(metrics[PRIMARY_RMSD_METRIC_ID])
        validity = float(metrics[BOUNDED_VALIDITY_METRIC_ID])
        primary = float(metrics[PRIMARY_SUCCESS_METRIC_ID])
    except (TypeError, ValueError, OverflowError) as exc:
        raise PublicBenchmarkProtocolError(
            "public benchmark metrics must be finite numeric values"
        ) from exc
    if not math.isfinite(rmsd) or not 0.0 <= rmsd <= 100.0:
        raise PublicBenchmarkProtocolError(
            "public benchmark RMSD must be finite and in [0,100]"
        )
    if validity not in {0.0, 1.0} or primary not in {0.0, 1.0}:
        raise PublicBenchmarkProtocolError(
            "public benchmark Boolean metrics must be exactly 0 or 1"
        )
    expected_primary = float(
        rmsd <= PRIMARY_RMSD_THRESHOLD_ANGSTROM and validity == 1.0
    )
    if primary != expected_primary:
        raise PublicBenchmarkProtocolError(
            "primary_pose_success disagrees with the frozen RMSD/validity rule"
        )
    return metrics


def require_public_benchmark_report(report: BenchmarkReport) -> BenchmarkReport:
    """Require complete frozen-manifest rows; failures stay in the denominator."""

    if not isinstance(report, BenchmarkReport):
        raise TypeError("public benchmark report must be BenchmarkReport")
    protocol = frozen_public_benchmark_protocol()
    if (
        report.manifest.fingerprint_sha256
        != protocol.benchmark_manifest.fingerprint_sha256
    ):
        raise PublicBenchmarkProtocolError(
            "public benchmark report manifest does not match the frozen protocol"
        )
    if not report.complete or len(report.rows) != len(protocol.cases):
        raise PublicBenchmarkProtocolError(
            "public benchmark report must retain one row for every manifest case"
        )
    for row in report.rows:
        if row.status == "success":
            require_public_benchmark_case_metrics(row.metrics)
    if report.claim_safe:
        raise PublicBenchmarkProtocolError(
            "public benchmark protocol reports cannot be claim-safe"
        )
    return report


def verify_public_benchmark_scorer_sources(
    repository_root: str | os.PathLike[str],
) -> dict[str, str]:
    """Verify reviewed scorer source files in a checkout without executing them."""

    root = Path(repository_root).resolve(strict=True)
    observed: dict[str, str] = {}
    for identity in frozen_public_benchmark_protocol().scorer_identities:
        candidate = root.joinpath(identity.relative_path)
        if candidate.is_symlink():
            raise PublicBenchmarkProtocolError(
                "scorer source must be a non-symlink regular file"
            )
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise PublicBenchmarkProtocolError(
                "scorer source path escaped the repository root"
            ) from exc
        if not resolved.is_file():
            raise PublicBenchmarkProtocolError(
                "scorer source must be a non-symlink regular file"
            )
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if digest != identity.source_sha256:
            raise PublicBenchmarkProtocolError(
                f"scorer source SHA-256 mismatch for {identity.purpose}"
            )
        observed[identity.purpose] = digest
    return observed


def write_public_benchmark_protocol_json(
    path: str | os.PathLike[str],
) -> Path:
    """Atomically write the protocol document with private file permissions."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=str(output.parent)
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(public_benchmark_protocol_json_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output)
        os.chmod(output, 0o600)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return output


__all__ = [
    "BOUNDED_VALIDITY_METRIC_ID",
    "FROZEN_PUBLIC_BENCHMARK_PROTOCOL_SHA256",
    "POSEBUSTERS_SOURCE_COMMIT_SHA",
    "PRIMARY_RMSD_METRIC_ID",
    "PRIMARY_RMSD_THRESHOLD_ANGSTROM",
    "PRIMARY_SUCCESS_METRIC_ID",
    "PUBLIC_BENCHMARK_PROTOCOL_ID",
    "PUBLIC_BENCHMARK_PROTOCOL_SCHEMA_ID",
    "FrozenPublicBenchmarkProtocol",
    "PublicBenchmarkArtifact",
    "PublicBenchmarkCaseDefinition",
    "PublicBenchmarkProtocolError",
    "PublicBenchmarkScorerIdentity",
    "frozen_public_benchmark_protocol",
    "public_benchmark_protocol_document",
    "public_benchmark_protocol_json_bytes",
    "require_public_benchmark_case_metrics",
    "require_public_benchmark_protocol_document",
    "require_public_benchmark_report",
    "verify_public_benchmark_scorer_sources",
    "write_public_benchmark_protocol_json",
]
