"""Stratify all-case internal PoseBusters-oracle evidence.

This module joins the deterministic internal-oracle result, its measured
runtime companion, conservative observed-target clusters, normalized
RCSB/Pfam target annotations, the corpus audit, and the exact canonical
preparation artifact tree.  Every source case receives exactly one primary
target stratum and one primary chemistry stratum.  Missing target annotation,
preparation failure, chemistry abstention, and upstream failure are retained as
explicit strata rather than removed from denominators.

The receipt is an evidence carrier only.  It does not promote the internal
scorer, chemistry model, target annotation, sampled RSS measurements, or a
local/synthetic execution into a public benchmark claim.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Mapping, Sequence, cast

from betelgeuze_engine_v2.molecular import all_atom_system_from_canonical_json
from betelgeuze_engine_v2.molecular.serialization import canonical_system_sha256

from .public_posebusters_corpus_audit import (
    PoseBustersCorpusAuditReceipt,
    PoseBustersCorpusCaseAudit,
    _canonical_bytes,
    _canonical_sha256,
    _source_file_sha256,
    verify_posebusters_corpus_audit_receipt,
)
from .public_posebusters_generated_pose_evaluation import (
    _case_id,
    _digest,
)
from .public_posebusters_intake import (
    OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    PoseBustersArchiveContract,
    PoseBustersArchiveIntakeError,
    _read_exact_regular_file,
)
from .public_posebusters_internal_execution import (
    PoseBustersInternalExecutionConfig,
)
from .public_posebusters_internal_oracle_evaluation import (
    POSEBUSTERS_INTERNAL_ORACLE_MAX_RECEIPT_BYTES,
    PoseBustersInternalOracleCase,
    PoseBustersInternalOracleEvaluationReceipt,
    verify_posebusters_internal_oracle_evaluation_receipt,
)
from .public_posebusters_internal_oracle_runtime_observation import (
    POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_MAX_RECEIPT_BYTES,
    PoseBustersInternalOracleRuntimeCase,
    PoseBustersInternalOracleRuntimeObservationReceipt,
    _load_runtime_observation_receipt,
    _require_oracle_binding,
)
from .public_posebusters_internal_preparation import (
    POSEBUSTERS_INTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
    PoseBustersInternalPreparationCase,
    PoseBustersInternalPreparationConfig,
    PoseBustersInternalPreparationReceipt,
    verify_posebusters_internal_preparation_receipt,
)
from .public_posebusters_internal_rmsd_evaluation import (
    PoseBustersInternalRMSDConfig,
)
from .public_posebusters_rcsb_target_family_binding import (
    PoseBustersRcsbTargetCase,
    PoseBustersRcsbTargetFamilyReceipt,
    _pfam_set_id,
    verify_posebusters_rcsb_target_family_binding_receipt,
)
from .public_posebusters_target_cluster_binding import (
    PoseBustersTargetClusterCase,
    PoseBustersTargetClusterReceipt,
    verify_posebusters_target_cluster_binding_receipt,
)


POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_stratification_case/1.0.0"
)
POSEBUSTERS_INTERNAL_ORACLE_STRATUM_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_stratum/1.0.0"
)
POSEBUSTERS_INTERNAL_ORACLE_STRATUM_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_stratum_metric/1.0.0"
)
POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_stratification/1.0.0"
)

POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_MAX_CASES = 308
POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_MAX_RECEIPT_BYTES = 32 * 1024 * 1024
POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_Z = 1.959963984540054

POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_CONFIGURATION = {
    "chemistry_aromaticity_ring_stereo_source": (
        "exact_verified_canonical_prepared_ligand_only"
    ),
    "chemistry_charge_size_element_source": (
        "verified_canonical_prepared_ligand_then_corpus_native_ligand_fallback"
    ),
    "chemistry_heavy_atom_buckets": ["1_10", "11_20", "21_30", "31_50", "51_plus"],
    "chemistry_primary_stratum": (
        "ood_charge_size_element_aromaticity_ring_stereo_receptor_context_product"
    ),
    "confidence_interval": "two_sided_wilson_score_binary64",
    "confidence_level_binary64_hex": (
        POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_CONFIDENCE_LEVEL.hex()
    ),
    "failure_policy": "retain_every_failure_blocked_abstention_and_no_pose_case",
    "metric_denominator": "all_cases_in_each_primary_stratum",
    "per_case_runtime_scope": "downstream_posebusters_oracle_loop_only",
    "primary_target_fallback": (
        "explicit_annotation_or_mapping_status_plus_observed_sequence_cluster"
    ),
    "primary_target_precedence": "exact_pfam_set_then_observed_sequence_cluster",
    "rss_aggregation": "maximum_of_sampled_case_peaks_not_sum",
    "runtime_source": "bound_runtime_observation_companion",
    "target_ood_policy": "unknown_without_internal_fit_or_training_manifest",
}
POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_CONFIGURATION_SHA256 = (
    "9f53960eb542426f503f8b480511fd67186fc93c112775aaaa3073a7586f552e"
)

POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_BLOCKERS = (
    "internal_fit_or_training_manifest_missing_for_target_ood",
    "pfam_annotation_incomplete_and_not_an_experimental_target_family_assay",
    "chemistry_profile_and_parameterization_not_scientifically_validated",
    "prepared_perception_unavailable_for_failure_and_abstention_rows",
    "runtime_per_case_scope_excludes_upstream_redocking_stages",
    "sampled_rss_is_not_kernel_enforced_isolated_peak_memory",
    "runtime_measurements_are_not_byte_reproducible",
    "independent_second_cpu_host_observation_missing",
    "independent_scientific_review_missing",
    "public_result_bundle_validation_missing",
    "public_docking_benchmark_claim_not_authorized",
)

_DIMENSIONS = ("target", "chemistry")
_TARGET_STRATUM_KINDS = {
    "pfam_set",
    "observed_cluster_annotation_unavailable",
    "observed_cluster_mapping_unavailable",
}
_TARGET_MAPPING_STATUSES = {
    "complete",
    "pocket_chain_unmapped",
    "pocket_chain_ambiguous",
    "rcsb_entry_removed",
    "rcsb_entry_missing",
}
_TARGET_ANNOTATION_STATUSES = {
    "pfam_annotated",
    "uniprot_without_pfam",
    "entity_without_uniprot_or_pfam",
    "not_applicable",
}
_ORACLE_STATUSES = {
    "evaluated",
    "partial_evaluation",
    "evaluation_failure",
    "adapter_failure",
    "no_selected_pose",
    "blocked_upstream",
}
_CORPUS_STATUSES = {"audited", "failure"}
_PREPARATION_STATUSES = {
    "prepared",
    "preparation_failure",
    "abstain_chemistry_scope",
    "upstream_failure",
}
_CHEMISTRY_OOD_STATUSES = {
    "admitted_profile_unvalidated",
    "unsupported_scope",
    "preparation_failure",
    "unknown_upstream_failure",
    "unknown_corpus_failure",
}
_CHEMISTRY_IDENTITY_SOURCES = {
    "canonical_prepared_ligand",
    "corpus_native_ligand_fallback",
    "unavailable_corpus_failure",
}
_CHARGE_CLASSES = {"negative", "neutral", "positive", "unavailable"}
_HEAVY_ATOM_CLASSES = {
    "1_10",
    "11_20",
    "21_30",
    "31_50",
    "51_plus",
    "unavailable",
}
_AROMATICITY_CLASSES = {"aromatic", "nonaromatic", "unavailable"}
_RING_CLASSES = {"ring", "acyclic", "unavailable"}
_STEREO_CLASSES = {"assigned_stereo", "no_assigned_stereo", "unavailable"}
_RECEPTOR_CONTEXT_CLASSES = {
    "metal_and_cofactor",
    "metal",
    "cofactor",
    "none",
    "unavailable",
}
_METRIC_IDS = (
    "selected_pose_case_rate",
    "oracle_attempt_case_rate",
    "oracle_complete_case_rate",
    "oracle_failure_case_rate",
    "blocked_or_no_pose_case_rate",
    "any_physically_valid_pose_rate",
    "top_1_valid_pose_rate",
    "top_5_valid_pose_rate",
    "top_1_rmsd_hit_rate",
    "top_5_rmsd_hit_rate",
    "top_1_valid_rmsd_hit_rate",
    "top_5_valid_rmsd_hit_rate",
)
_SHA256_CHARACTERS = frozenset("0123456789abcdef")


class PoseBustersInternalOracleStratificationError(ValueError):
    """A prerequisite, stratum join, metric, or receipt is invalid."""


def _bounded_text(value: object, *, name: str, maximum: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > maximum
        or any(character in "\r\n\x00" for character in value)
    ):
        raise PoseBustersInternalOracleStratificationError(
            f"{name} must be bounded non-empty text"
        )
    return value


def _boolean(value: object, *, name: str) -> bool:
    if type(value) is not bool:
        raise PoseBustersInternalOracleStratificationError(f"{name} must be boolean")
    return value


def _nonnegative_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PoseBustersInternalOracleStratificationError(
            f"{name} must be a non-negative integer"
        )
    return value


def _positive_int(value: object, *, name: str) -> int:
    result = _nonnegative_int(value, name=name)
    if result == 0:
        raise PoseBustersInternalOracleStratificationError(
            f"{name} must be a positive integer"
        )
    return result


def _optional_int(value: object, *, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise PoseBustersInternalOracleStratificationError(
            f"{name} must be an integer or null"
        )
    return value


def _sha256_bytes(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def _wilson_interval(numerator: int, denominator: int) -> tuple[float, float]:
    if denominator <= 0 or numerator < 0 or numerator > denominator:
        raise PoseBustersInternalOracleStratificationError(
            "Wilson interval counts are invalid"
        )
    estimate = numerator / denominator
    z = POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_Z
    denominator_adjustment = 1.0 + z * z / denominator
    center = (estimate + z * z / (2.0 * denominator)) / denominator_adjustment
    margin = (
        z
        * math.sqrt(
            estimate * (1.0 - estimate) / denominator
            + z * z / (4.0 * denominator * denominator)
        )
        / denominator_adjustment
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _charge_class(value: int) -> str:
    if value < 0:
        return "negative"
    if value > 0:
        return "positive"
    return "neutral"


def _heavy_atom_class(value: int) -> str:
    if value <= 10:
        return "1_10"
    if value <= 20:
        return "11_20"
    if value <= 30:
        return "21_30"
    if value <= 50:
        return "31_50"
    return "51_plus"


def _element_class(atomic_numbers: Sequence[int]) -> str:
    values = set(atomic_numbers)
    if not values:
        return "unavailable"
    base = {1, 6, 7, 8}
    extras: list[str] = []
    if 15 in values:
        extras.append("phosphorus")
    if 16 in values:
        extras.append("sulfur")
    if values & {9, 17, 35, 53}:
        extras.append("halogen")
    accounted = base | {9, 15, 16, 17, 35, 53}
    if values - accounted:
        extras.append("other")
    return "chno_only" if not extras else "chno_plus_" + "_".join(extras)


def _receptor_context_class(row: PoseBustersCorpusCaseAudit) -> str:
    metal = bool(row.metal_atomic_numbers)
    cofactor = bool(row.receptor_nonwater_nonpolymer_residue_names)
    if metal and cofactor:
        return "metal_and_cofactor"
    if metal:
        return "metal"
    if cofactor:
        return "cofactor"
    return "none"


def _chemistry_stratum_id(
    *,
    ood_status: str,
    charge_class: str,
    heavy_atom_class: str,
    element_class: str,
    aromaticity_class: str,
    ring_class: str,
    stereo_class: str,
    receptor_context_class: str,
) -> str:
    return (
        "chemistry::"
        f"ood={ood_status}|charge={charge_class}|heavy={heavy_atom_class}|"
        f"elements={element_class}|aromaticity={aromaticity_class}|"
        f"ring={ring_class}|stereo={stereo_class}|"
        f"receptor={receptor_context_class}"
    )


@dataclass(frozen=True, slots=True)
class PoseBustersInternalOracleStratificationCase:
    case_id: str
    oracle_status: str
    selected_pose_count: int
    oracle_attempted: bool
    target_stratum_id: str
    target_stratum_kind: str
    target_cluster_id: str
    target_mapping_status: str
    target_annotation_status: str
    pfam_ids: tuple[str, ...]
    target_ood_status: str
    chemistry_stratum_id: str
    chemistry_ood_status: str
    chemistry_identity_source: str
    corpus_audit_status: str
    preparation_status: str
    reference_scorer_scope_status: str
    reference_scorer_scope_blockers: tuple[str, ...]
    ligand_formal_charge: int | None
    ligand_heavy_atom_count: int | None
    ligand_atomic_numbers: tuple[int, ...]
    charge_class: str
    heavy_atom_class: str
    element_class: str
    aromaticity_class: str
    ring_class: str
    stereo_class: str
    receptor_context_class: str
    prepared_aromatic_atom_count: int | None
    prepared_ring_atom_count: int | None
    prepared_stereo_feature_count: int | None
    has_any_valid_pose: bool
    top_1_valid_pose: bool
    top_5_valid_pose: bool
    top_1_rmsd_hit: bool
    top_5_rmsd_hit: bool
    top_1_valid_rmsd_hit: bool
    top_5_valid_rmsd_hit: bool
    wall_duration_ns: int
    rss_start_bytes: int
    rss_end_bytes: int
    sampled_peak_rss_bytes: int
    rss_sample_count: int
    schema_id: str = POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_CASE_SCHEMA_ID:
            raise PoseBustersInternalOracleStratificationError(
                "unsupported stratification-case schema"
            )
        case = _case_id(self.case_id)
        if self.oracle_status not in _ORACLE_STATUSES:
            raise PoseBustersInternalOracleStratificationError(
                "stratification oracle status is invalid"
            )
        selected = _nonnegative_int(
            self.selected_pose_count,
            name="stratification selected-pose count",
        )
        attempted = _boolean(self.oracle_attempted, name="oracle_attempted")
        target_id = _bounded_text(
            self.target_stratum_id,
            name="target stratum ID",
        )
        target_kind = _bounded_text(
            self.target_stratum_kind,
            name="target stratum kind",
        )
        if target_kind not in _TARGET_STRATUM_KINDS:
            raise PoseBustersInternalOracleStratificationError(
                "target stratum kind is invalid"
            )
        cluster = _bounded_text(
            self.target_cluster_id,
            name="observed target cluster ID",
        )
        mapping = _bounded_text(
            self.target_mapping_status,
            name="target mapping status",
        )
        annotation = _bounded_text(
            self.target_annotation_status,
            name="target annotation status",
        )
        if mapping not in _TARGET_MAPPING_STATUSES or annotation not in (
            _TARGET_ANNOTATION_STATUSES
        ):
            raise PoseBustersInternalOracleStratificationError(
                "target mapping or annotation status is invalid"
            )
        pfam = tuple(self.pfam_ids)
        if (
            tuple(sorted(pfam)) != pfam
            or len(set(pfam)) != len(pfam)
            or any(
                not value.startswith("PF") or not value[2:].isdigit() for value in pfam
            )
        ):
            raise PoseBustersInternalOracleStratificationError(
                "target Pfam IDs are invalid"
            )
        if target_kind == "pfam_set":
            target_valid = (
                mapping == "complete"
                and annotation == "pfam_annotated"
                and bool(pfam)
                and target_id == f"pfam_set::{_pfam_set_id(pfam)}"
            )
        elif target_kind == "observed_cluster_annotation_unavailable":
            target_valid = (
                mapping == "complete"
                and not pfam
                and target_id
                == (f"observed_cluster_annotation_unavailable::{annotation}::{cluster}")
            )
        else:
            target_valid = (
                mapping != "complete"
                and annotation == "not_applicable"
                and not pfam
                and target_id
                == (f"observed_cluster_mapping_unavailable::{mapping}::{cluster}")
            )
        if not target_valid or self.target_ood_status != (
            "unknown_no_internal_fit_or_training_manifest"
        ):
            raise PoseBustersInternalOracleStratificationError(
                "target primary-stratum disposition is inconsistent"
            )
        if self.chemistry_ood_status not in _CHEMISTRY_OOD_STATUSES:
            raise PoseBustersInternalOracleStratificationError(
                "chemistry OOD status is invalid"
            )
        if self.chemistry_identity_source not in _CHEMISTRY_IDENTITY_SOURCES:
            raise PoseBustersInternalOracleStratificationError(
                "chemistry identity source is invalid"
            )
        if self.corpus_audit_status not in _CORPUS_STATUSES:
            raise PoseBustersInternalOracleStratificationError(
                "corpus-audit status is invalid"
            )
        if self.preparation_status not in _PREPARATION_STATUSES:
            raise PoseBustersInternalOracleStratificationError(
                "preparation status is invalid"
            )
        scope_status = _bounded_text(
            self.reference_scorer_scope_status,
            name="reference-scorer scope status",
            maximum=128,
        )
        scope_blockers = tuple(self.reference_scorer_scope_blockers)
        if tuple(sorted(set(scope_blockers))) != scope_blockers:
            raise PoseBustersInternalOracleStratificationError(
                "scope blockers must be unique and ordered"
            )
        charge = _optional_int(
            self.ligand_formal_charge,
            name="ligand formal charge",
        )
        heavy = _optional_int(
            self.ligand_heavy_atom_count,
            name="ligand heavy-atom count",
        )
        if heavy is not None and heavy <= 0:
            raise PoseBustersInternalOracleStratificationError(
                "ligand heavy-atom count must be positive when present"
            )
        atomic_numbers = tuple(self.ligand_atomic_numbers)
        if tuple(sorted(set(atomic_numbers))) != atomic_numbers or any(
            value < 1 or value > 118 for value in atomic_numbers
        ):
            raise PoseBustersInternalOracleStratificationError(
                "ligand atomic-number projection is invalid"
            )
        if self.charge_class not in _CHARGE_CLASSES:
            raise PoseBustersInternalOracleStratificationError(
                "charge class is invalid"
            )
        if self.heavy_atom_class not in _HEAVY_ATOM_CLASSES:
            raise PoseBustersInternalOracleStratificationError(
                "heavy-atom class is invalid"
            )
        if self.aromaticity_class not in _AROMATICITY_CLASSES:
            raise PoseBustersInternalOracleStratificationError(
                "aromaticity class is invalid"
            )
        if self.ring_class not in _RING_CLASSES:
            raise PoseBustersInternalOracleStratificationError("ring class is invalid")
        if self.stereo_class not in _STEREO_CLASSES:
            raise PoseBustersInternalOracleStratificationError(
                "stereo class is invalid"
            )
        if self.receptor_context_class not in _RECEPTOR_CONTEXT_CLASSES:
            raise PoseBustersInternalOracleStratificationError(
                "receptor-context class is invalid"
            )
        perceived = tuple(
            _optional_int(getattr(self, name), name=name)
            for name in (
                "prepared_aromatic_atom_count",
                "prepared_ring_atom_count",
                "prepared_stereo_feature_count",
            )
        )
        if any(value is not None and value < 0 for value in perceived):
            raise PoseBustersInternalOracleStratificationError(
                "prepared chemistry counts cannot be negative"
            )
        if self.corpus_audit_status == "failure":
            chemistry_valid = (
                charge is None
                and heavy is None
                and not atomic_numbers
                and self.charge_class == "unavailable"
                and self.heavy_atom_class == "unavailable"
                and self.element_class == "unavailable"
                and self.receptor_context_class == "unavailable"
                and self.chemistry_ood_status == "unknown_corpus_failure"
                and self.chemistry_identity_source == "unavailable_corpus_failure"
            )
        else:
            expected_ood_status = {
                "prepared": "admitted_profile_unvalidated",
                "preparation_failure": "preparation_failure",
                "abstain_chemistry_scope": "unsupported_scope",
                "upstream_failure": "unknown_upstream_failure",
            }[self.preparation_status]
            chemistry_valid = (
                charge is not None
                and heavy is not None
                and bool(atomic_numbers)
                and self.charge_class == _charge_class(charge)
                and self.heavy_atom_class == _heavy_atom_class(heavy)
                and self.element_class == _element_class(atomic_numbers)
                and self.chemistry_ood_status == expected_ood_status
                and self.chemistry_identity_source
                == (
                    "canonical_prepared_ligand"
                    if self.preparation_status == "prepared"
                    else "corpus_native_ligand_fallback"
                )
            )
        if self.preparation_status == "prepared":
            chemistry_valid = chemistry_valid and (
                all(value is not None for value in perceived)
                and self.aromaticity_class
                == ("aromatic" if perceived[0] else "nonaromatic")
                and self.ring_class == ("ring" if perceived[1] else "acyclic")
                and self.stereo_class
                == ("assigned_stereo" if perceived[2] else "no_assigned_stereo")
                and self.chemistry_ood_status == "admitted_profile_unvalidated"
            )
        else:
            chemistry_valid = chemistry_valid and (
                not any(value is not None for value in perceived)
                and self.aromaticity_class == "unavailable"
                and self.ring_class == "unavailable"
                and self.stereo_class == "unavailable"
            )
        expected_chemistry_id = _chemistry_stratum_id(
            ood_status=self.chemistry_ood_status,
            charge_class=self.charge_class,
            heavy_atom_class=self.heavy_atom_class,
            element_class=self.element_class,
            aromaticity_class=self.aromaticity_class,
            ring_class=self.ring_class,
            stereo_class=self.stereo_class,
            receptor_context_class=self.receptor_context_class,
        )
        if not chemistry_valid or self.chemistry_stratum_id != expected_chemistry_id:
            raise PoseBustersInternalOracleStratificationError(
                "chemistry primary-stratum disposition is inconsistent"
            )
        outcome_names = (
            "has_any_valid_pose",
            "top_1_valid_pose",
            "top_5_valid_pose",
            "top_1_rmsd_hit",
            "top_5_rmsd_hit",
            "top_1_valid_rmsd_hit",
            "top_5_valid_rmsd_hit",
        )
        outcomes = tuple(
            _boolean(getattr(self, name), name=name) for name in outcome_names
        )
        if (
            outcomes[1]
            and not outcomes[2]
            or outcomes[3]
            and not outcomes[4]
            or outcomes[5]
            and not (outcomes[1] and outcomes[3])
            or outcomes[6]
            and not (outcomes[2] and outcomes[4])
            or outcomes[1]
            and not outcomes[0]
            or outcomes[2]
            and not outcomes[0]
        ):
            raise PoseBustersInternalOracleStratificationError(
                "stratified outcome flags are inconsistent"
            )
        if self.oracle_status in {
            "evaluated",
            "partial_evaluation",
            "evaluation_failure",
        }:
            oracle_disposition_valid = selected > 0 and attempted
        elif self.oracle_status == "adapter_failure":
            oracle_disposition_valid = selected > 0 and not attempted
        else:
            oracle_disposition_valid = selected == 0 and not attempted
        if not oracle_disposition_valid or (selected == 0 and any(outcomes)):
            raise PoseBustersInternalOracleStratificationError(
                "oracle status, selected count, attempt, and outcomes disagree"
            )
        duration = _nonnegative_int(self.wall_duration_ns, name="case wall duration")
        rss_start = _positive_int(self.rss_start_bytes, name="case start RSS")
        rss_end = _positive_int(self.rss_end_bytes, name="case end RSS")
        peak = _positive_int(
            self.sampled_peak_rss_bytes,
            name="case sampled peak RSS",
        )
        samples = _positive_int(self.rss_sample_count, name="case RSS sample count")
        if peak < max(rss_start, rss_end) or samples < 2:
            raise PoseBustersInternalOracleStratificationError(
                "stratification runtime summary is inconsistent"
            )
        object.__setattr__(self, "case_id", case)
        object.__setattr__(self, "selected_pose_count", selected)
        object.__setattr__(self, "oracle_attempted", attempted)
        object.__setattr__(self, "target_stratum_id", target_id)
        object.__setattr__(self, "target_stratum_kind", target_kind)
        object.__setattr__(self, "target_cluster_id", cluster)
        object.__setattr__(self, "pfam_ids", pfam)
        object.__setattr__(self, "reference_scorer_scope_status", scope_status)
        object.__setattr__(self, "reference_scorer_scope_blockers", scope_blockers)
        object.__setattr__(self, "ligand_formal_charge", charge)
        object.__setattr__(self, "ligand_heavy_atom_count", heavy)
        object.__setattr__(self, "ligand_atomic_numbers", atomic_numbers)
        object.__setattr__(self, "wall_duration_ns", duration)
        object.__setattr__(self, "rss_start_bytes", rss_start)
        object.__setattr__(self, "rss_end_bytes", rss_end)
        object.__setattr__(self, "sampled_peak_rss_bytes", peak)
        object.__setattr__(self, "rss_sample_count", samples)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "oracle_status": self.oracle_status,
            "selected_pose_count": self.selected_pose_count,
            "oracle_attempted": self.oracle_attempted,
            "target_stratum_id": self.target_stratum_id,
            "target_stratum_kind": self.target_stratum_kind,
            "target_cluster_id": self.target_cluster_id,
            "target_mapping_status": self.target_mapping_status,
            "target_annotation_status": self.target_annotation_status,
            "pfam_ids": list(self.pfam_ids),
            "target_ood_status": self.target_ood_status,
            "chemistry_stratum_id": self.chemistry_stratum_id,
            "chemistry_ood_status": self.chemistry_ood_status,
            "chemistry_identity_source": self.chemistry_identity_source,
            "corpus_audit_status": self.corpus_audit_status,
            "preparation_status": self.preparation_status,
            "reference_scorer_scope_status": self.reference_scorer_scope_status,
            "reference_scorer_scope_blockers": list(
                self.reference_scorer_scope_blockers
            ),
            "ligand_formal_charge": self.ligand_formal_charge,
            "ligand_heavy_atom_count": self.ligand_heavy_atom_count,
            "ligand_atomic_numbers": list(self.ligand_atomic_numbers),
            "charge_class": self.charge_class,
            "heavy_atom_class": self.heavy_atom_class,
            "element_class": self.element_class,
            "aromaticity_class": self.aromaticity_class,
            "ring_class": self.ring_class,
            "stereo_class": self.stereo_class,
            "receptor_context_class": self.receptor_context_class,
            "prepared_aromatic_atom_count": self.prepared_aromatic_atom_count,
            "prepared_ring_atom_count": self.prepared_ring_atom_count,
            "prepared_stereo_feature_count": self.prepared_stereo_feature_count,
            "has_any_valid_pose": self.has_any_valid_pose,
            "top_1_valid_pose": self.top_1_valid_pose,
            "top_5_valid_pose": self.top_5_valid_pose,
            "top_1_rmsd_hit": self.top_1_rmsd_hit,
            "top_5_rmsd_hit": self.top_5_rmsd_hit,
            "top_1_valid_rmsd_hit": self.top_1_valid_rmsd_hit,
            "top_5_valid_rmsd_hit": self.top_5_valid_rmsd_hit,
            "wall_duration_ns": self.wall_duration_ns,
            "rss_start_bytes": self.rss_start_bytes,
            "rss_end_bytes": self.rss_end_bytes,
            "sampled_peak_rss_bytes": self.sampled_peak_rss_bytes,
            "rss_sample_count": self.rss_sample_count,
        }

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, object],
    ) -> "PoseBustersInternalOracleStratificationCase":
        scalar_values = cast(
            dict[str, Any],
            {
                name: raw.get(name)
                for name in cls.__dataclass_fields__
                if name
                not in {
                    "pfam_ids",
                    "reference_scorer_scope_blockers",
                    "ligand_atomic_numbers",
                }
            },
        )
        return cls(
            **scalar_values,
            pfam_ids=tuple(raw.get("pfam_ids", ())),  # type: ignore[arg-type]
            reference_scorer_scope_blockers=tuple(
                raw.get("reference_scorer_scope_blockers", ())  # type: ignore[arg-type]
            ),
            ligand_atomic_numbers=tuple(
                raw.get("ligand_atomic_numbers", ())  # type: ignore[arg-type]
            ),
        )  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class PoseBustersInternalOracleStratum:
    dimension: str
    stratum_id: str
    stratum_kind: str
    member_case_ids: tuple[str, ...]
    wall_duration_total_ns: int
    wall_duration_min_ns: int
    wall_duration_max_ns: int
    sampled_peak_rss_max_bytes: int
    rss_sample_count_total: int
    schema_id: str = POSEBUSTERS_INTERNAL_ORACLE_STRATUM_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_ORACLE_STRATUM_SCHEMA_ID:
            raise PoseBustersInternalOracleStratificationError(
                "unsupported oracle-stratum schema"
            )
        if self.dimension not in _DIMENSIONS:
            raise PoseBustersInternalOracleStratificationError(
                "stratum dimension is invalid"
            )
        stratum_id = _bounded_text(self.stratum_id, name="stratum ID")
        kind = _bounded_text(self.stratum_kind, name="stratum kind")
        members = tuple(_case_id(value) for value in self.member_case_ids)
        if (
            not members
            or tuple(sorted(members)) != members
            or len(set(members)) != len(members)
        ):
            raise PoseBustersInternalOracleStratificationError(
                "stratum members must be non-empty, unique, and ordered"
            )
        total = _nonnegative_int(
            self.wall_duration_total_ns,
            name="stratum wall-duration total",
        )
        minimum = _nonnegative_int(
            self.wall_duration_min_ns,
            name="stratum minimum wall duration",
        )
        maximum = _nonnegative_int(
            self.wall_duration_max_ns,
            name="stratum maximum wall duration",
        )
        peak = _positive_int(
            self.sampled_peak_rss_max_bytes,
            name="stratum sampled peak RSS",
        )
        samples = _positive_int(
            self.rss_sample_count_total,
            name="stratum RSS sample total",
        )
        if minimum > maximum or total < maximum or samples < 2 * len(members):
            raise PoseBustersInternalOracleStratificationError(
                "stratum runtime aggregation is inconsistent"
            )
        object.__setattr__(self, "stratum_id", stratum_id)
        object.__setattr__(self, "stratum_kind", kind)
        object.__setattr__(self, "member_case_ids", members)
        object.__setattr__(self, "wall_duration_total_ns", total)
        object.__setattr__(self, "wall_duration_min_ns", minimum)
        object.__setattr__(self, "wall_duration_max_ns", maximum)
        object.__setattr__(self, "sampled_peak_rss_max_bytes", peak)
        object.__setattr__(self, "rss_sample_count_total", samples)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "dimension": self.dimension,
            "stratum_id": self.stratum_id,
            "stratum_kind": self.stratum_kind,
            "member_case_count": len(self.member_case_ids),
            "member_case_ids": list(self.member_case_ids),
            "wall_duration_total_ns": self.wall_duration_total_ns,
            "wall_duration_min_ns": self.wall_duration_min_ns,
            "wall_duration_max_ns": self.wall_duration_max_ns,
            "sampled_peak_rss_max_bytes": self.sampled_peak_rss_max_bytes,
            "rss_sample_count_total": self.rss_sample_count_total,
            "runtime_scope": "downstream_posebusters_oracle_loop_only",
            "sampled_peak_rss_is_additive": False,
        }

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, object],
    ) -> "PoseBustersInternalOracleStratum":
        return cls(
            dimension=raw.get("dimension"),  # type: ignore[arg-type]
            stratum_id=raw.get("stratum_id"),  # type: ignore[arg-type]
            stratum_kind=raw.get("stratum_kind"),  # type: ignore[arg-type]
            member_case_ids=tuple(raw.get("member_case_ids", ())),  # type: ignore[arg-type]
            wall_duration_total_ns=raw.get("wall_duration_total_ns"),  # type: ignore[arg-type]
            wall_duration_min_ns=raw.get("wall_duration_min_ns"),  # type: ignore[arg-type]
            wall_duration_max_ns=raw.get("wall_duration_max_ns"),  # type: ignore[arg-type]
            sampled_peak_rss_max_bytes=raw.get("sampled_peak_rss_max_bytes"),  # type: ignore[arg-type]
            rss_sample_count_total=raw.get("rss_sample_count_total"),  # type: ignore[arg-type]
            schema_id=raw.get("schema_id"),  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class PoseBustersInternalOracleStratumMetric:
    dimension: str
    stratum_id: str
    metric_id: str
    numerator: int
    denominator: int
    schema_id: str = POSEBUSTERS_INTERNAL_ORACLE_STRATUM_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_ORACLE_STRATUM_METRIC_SCHEMA_ID:
            raise PoseBustersInternalOracleStratificationError(
                "unsupported stratum-metric schema"
            )
        if self.dimension not in _DIMENSIONS:
            raise PoseBustersInternalOracleStratificationError(
                "stratum metric dimension is invalid"
            )
        object.__setattr__(
            self,
            "stratum_id",
            _bounded_text(self.stratum_id, name="metric stratum ID"),
        )
        if self.metric_id not in _METRIC_IDS:
            raise PoseBustersInternalOracleStratificationError(
                "stratum metric ID is invalid"
            )
        numerator = _nonnegative_int(self.numerator, name="metric numerator")
        denominator = _positive_int(self.denominator, name="metric denominator")
        if numerator > denominator:
            raise PoseBustersInternalOracleStratificationError(
                "metric numerator exceeds denominator"
            )
        object.__setattr__(self, "numerator", numerator)
        object.__setattr__(self, "denominator", denominator)

    @property
    def estimate_binary64_hex(self) -> str:
        return (self.numerator / self.denominator).hex()

    @property
    def confidence_interval_binary64_hex(self) -> tuple[str, str]:
        low, high = _wilson_interval(self.numerator, self.denominator)
        return low.hex(), high.hex()

    def to_dict(self) -> dict[str, object]:
        low, high = self.confidence_interval_binary64_hex
        return {
            "schema_id": self.schema_id,
            "dimension": self.dimension,
            "stratum_id": self.stratum_id,
            "metric_id": self.metric_id,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "denominator_scope": "all_cases_in_stratum",
            "estimate_binary64_hex": self.estimate_binary64_hex,
            "confidence_level_binary64_hex": (
                POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_CONFIDENCE_LEVEL.hex()
            ),
            "confidence_interval_low_binary64_hex": low,
            "confidence_interval_high_binary64_hex": high,
            "confidence_interval_method": "two_sided_wilson_score",
        }

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, object],
    ) -> "PoseBustersInternalOracleStratumMetric":
        return cls(
            dimension=raw.get("dimension"),  # type: ignore[arg-type]
            stratum_id=raw.get("stratum_id"),  # type: ignore[arg-type]
            metric_id=raw.get("metric_id"),  # type: ignore[arg-type]
            numerator=raw.get("numerator"),  # type: ignore[arg-type]
            denominator=raw.get("denominator"),  # type: ignore[arg-type]
            schema_id=raw.get("schema_id"),  # type: ignore[arg-type]
        )


def _aggregate_strata(
    cases: Sequence[PoseBustersInternalOracleStratificationCase],
) -> tuple[PoseBustersInternalOracleStratum, ...]:
    rows: list[PoseBustersInternalOracleStratum] = []
    for dimension in _DIMENSIONS:
        grouped: dict[
            str,
            list[PoseBustersInternalOracleStratificationCase],
        ] = {}
        for case in cases:
            stratum_id = (
                case.target_stratum_id
                if dimension == "target"
                else case.chemistry_stratum_id
            )
            grouped.setdefault(stratum_id, []).append(case)
        for stratum_id in sorted(grouped):
            members = grouped[stratum_id]
            kinds = {
                (
                    row.target_stratum_kind
                    if dimension == "target"
                    else row.chemistry_ood_status
                )
                for row in members
            }
            if len(kinds) != 1:
                raise PoseBustersInternalOracleStratificationError(
                    "one primary stratum carries multiple semantic kinds"
                )
            durations = [row.wall_duration_ns for row in members]
            rows.append(
                PoseBustersInternalOracleStratum(
                    dimension=dimension,
                    stratum_id=stratum_id,
                    stratum_kind=next(iter(kinds)),
                    member_case_ids=tuple(row.case_id for row in members),
                    wall_duration_total_ns=sum(durations),
                    wall_duration_min_ns=min(durations),
                    wall_duration_max_ns=max(durations),
                    sampled_peak_rss_max_bytes=max(
                        row.sampled_peak_rss_bytes for row in members
                    ),
                    rss_sample_count_total=sum(row.rss_sample_count for row in members),
                )
            )
    return tuple(rows)


def _metric_numerator(
    metric_id: str,
    row: PoseBustersInternalOracleStratificationCase,
) -> bool:
    if metric_id == "selected_pose_case_rate":
        return row.selected_pose_count > 0
    if metric_id == "oracle_attempt_case_rate":
        return row.oracle_attempted
    if metric_id == "oracle_complete_case_rate":
        return row.oracle_status == "evaluated"
    if metric_id == "oracle_failure_case_rate":
        return row.oracle_status in {
            "partial_evaluation",
            "evaluation_failure",
            "adapter_failure",
        }
    if metric_id == "blocked_or_no_pose_case_rate":
        return row.oracle_status in {"blocked_upstream", "no_selected_pose"}
    if metric_id == "any_physically_valid_pose_rate":
        return row.has_any_valid_pose
    if metric_id == "top_1_valid_pose_rate":
        return row.top_1_valid_pose
    if metric_id == "top_5_valid_pose_rate":
        return row.top_5_valid_pose
    if metric_id == "top_1_rmsd_hit_rate":
        return row.top_1_rmsd_hit
    if metric_id == "top_5_rmsd_hit_rate":
        return row.top_5_rmsd_hit
    if metric_id == "top_1_valid_rmsd_hit_rate":
        return row.top_1_valid_rmsd_hit
    if metric_id == "top_5_valid_rmsd_hit_rate":
        return row.top_5_valid_rmsd_hit
    raise PoseBustersInternalOracleStratificationError("unknown stratum metric")


def _summary_metrics(
    cases: Sequence[PoseBustersInternalOracleStratificationCase],
    strata: Sequence[PoseBustersInternalOracleStratum],
) -> tuple[PoseBustersInternalOracleStratumMetric, ...]:
    case_by_id = {row.case_id: row for row in cases}
    metrics: list[PoseBustersInternalOracleStratumMetric] = []
    for stratum in strata:
        members = tuple(case_by_id[case_id] for case_id in stratum.member_case_ids)
        for metric_id in _METRIC_IDS:
            metrics.append(
                PoseBustersInternalOracleStratumMetric(
                    dimension=stratum.dimension,
                    stratum_id=stratum.stratum_id,
                    metric_id=metric_id,
                    numerator=sum(_metric_numerator(metric_id, row) for row in members),
                    denominator=len(members),
                )
            )
    return tuple(metrics)


@dataclass(frozen=True, slots=True)
class PoseBustersInternalOracleStratificationReceipt:
    source_dataset_id: str
    official_cohort_bound: bool
    archive_intake_receipt_sha256: str
    corpus_audit_receipt_sha256: str
    preparation_receipt_sha256: str
    preparation_artifact_set_sha256: str
    oracle_receipt_sha256: str
    oracle_receipt_file_sha256: str
    oracle_runtime_identity_sha256: str
    runtime_observation_receipt_sha256: str
    runtime_observation_receipt_file_sha256: str
    runtime_environment_sha256: str
    runtime_engine_wheel_binding_sha256: str
    target_cluster_receipt_sha256: str
    target_family_receipt_sha256: str
    annotation_snapshot_sha256: str
    configuration_sha256: str
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    batch_wall_duration_ns: int
    batch_rss_start_bytes: int
    batch_rss_end_bytes: int
    batch_sampled_peak_rss_bytes: int
    batch_rss_sample_count: int
    case_rows: tuple[PoseBustersInternalOracleStratificationCase, ...]
    stratum_rows: tuple[PoseBustersInternalOracleStratum, ...]
    metrics: tuple[PoseBustersInternalOracleStratumMetric, ...]
    schema_id: str = POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_SCHEMA_ID:
            raise PoseBustersInternalOracleStratificationError(
                "unsupported internal-oracle stratification schema"
            )
        dataset = _bounded_text(
            self.source_dataset_id,
            name="stratification source dataset",
            maximum=128,
        )
        official = _boolean(
            self.official_cohort_bound,
            name="official_cohort_bound",
        )
        for name in (
            "archive_intake_receipt_sha256",
            "corpus_audit_receipt_sha256",
            "preparation_receipt_sha256",
            "preparation_artifact_set_sha256",
            "oracle_receipt_sha256",
            "oracle_receipt_file_sha256",
            "oracle_runtime_identity_sha256",
            "runtime_observation_receipt_sha256",
            "runtime_observation_receipt_file_sha256",
            "runtime_environment_sha256",
            "runtime_engine_wheel_binding_sha256",
            "target_cluster_receipt_sha256",
            "target_family_receipt_sha256",
            "annotation_snapshot_sha256",
            "configuration_sha256",
            "implementation_source_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if (
            self.configuration_sha256
            != POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_CONFIGURATION_SHA256
            or self.configuration_sha256
            != _canonical_sha256(
                POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_CONFIGURATION
            )
        ):
            raise PoseBustersInternalOracleStratificationError(
                "stratification configuration identity changed"
            )
        members = tuple(
            (
                _bounded_text(role, name="implementation source role", maximum=96),
                _digest(digest, name=f"implementation source {role}"),
            )
            for role, digest in self.implementation_source_members
        )
        if (
            not members
            or tuple(sorted(members)) != members
            or len({role for role, _digest_value in members}) != len(members)
            or self.implementation_source_sha256 != _canonical_sha256(dict(members))
        ):
            raise PoseBustersInternalOracleStratificationError(
                "stratification implementation-source identity is invalid"
            )
        cases = tuple(self.case_rows)
        if (
            not cases
            or len(cases) > POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_MAX_CASES
            or any(
                not isinstance(row, PoseBustersInternalOracleStratificationCase)
                for row in cases
            )
            or tuple(row.case_id for row in cases)
            != tuple(sorted(row.case_id for row in cases))
            or len({row.case_id for row in cases}) != len(cases)
        ):
            raise PoseBustersInternalOracleStratificationError(
                "stratification cases must be bounded, unique, and ordered"
            )
        if official and (
            dataset != OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT.dataset_id
            or len(cases) != OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT.selected_case_count
        ):
            raise PoseBustersInternalOracleStratificationError(
                "official cohort binding is inconsistent"
            )
        strata = tuple(self.stratum_rows)
        expected_strata = _aggregate_strata(cases)
        if tuple(row.to_dict() for row in strata) != tuple(
            row.to_dict() for row in expected_strata
        ):
            raise PoseBustersInternalOracleStratificationError(
                "primary strata do not exactly partition all cases"
            )
        metrics = tuple(self.metrics)
        expected_metrics = _summary_metrics(cases, strata)
        if tuple(row.to_dict() for row in metrics) != tuple(
            row.to_dict() for row in expected_metrics
        ):
            raise PoseBustersInternalOracleStratificationError(
                "stratified Wilson metrics disagree with case rows"
            )
        batch_duration = _nonnegative_int(
            self.batch_wall_duration_ns,
            name="batch wall duration",
        )
        batch_start = _positive_int(
            self.batch_rss_start_bytes,
            name="batch start RSS",
        )
        batch_end = _positive_int(
            self.batch_rss_end_bytes,
            name="batch end RSS",
        )
        batch_peak = _positive_int(
            self.batch_sampled_peak_rss_bytes,
            name="batch sampled peak RSS",
        )
        batch_samples = _positive_int(
            self.batch_rss_sample_count,
            name="batch RSS sample count",
        )
        if (
            batch_duration < sum(row.wall_duration_ns for row in cases)
            or batch_peak
            < max(
                batch_start,
                batch_end,
                *(row.sampled_peak_rss_bytes for row in cases),
            )
            or batch_samples < sum(row.rss_sample_count for row in cases)
        ):
            raise PoseBustersInternalOracleStratificationError(
                "batch runtime binding is inconsistent"
            )
        object.__setattr__(self, "source_dataset_id", dataset)
        object.__setattr__(self, "official_cohort_bound", official)
        object.__setattr__(self, "implementation_source_members", members)
        object.__setattr__(self, "case_rows", cases)
        object.__setattr__(self, "stratum_rows", strata)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "batch_wall_duration_ns", batch_duration)
        object.__setattr__(self, "batch_rss_start_bytes", batch_start)
        object.__setattr__(self, "batch_rss_end_bytes", batch_end)
        object.__setattr__(self, "batch_sampled_peak_rss_bytes", batch_peak)
        object.__setattr__(self, "batch_rss_sample_count", batch_samples)

    def _payload(self) -> dict[str, object]:
        target_strata = tuple(
            row for row in self.stratum_rows if row.dimension == "target"
        )
        chemistry_strata = tuple(
            row for row in self.stratum_rows if row.dimension == "chemistry"
        )
        return {
            "schema_id": self.schema_id,
            "source_dataset_id": self.source_dataset_id,
            "official_cohort_bound": self.official_cohort_bound,
            "archive_intake_receipt_sha256": self.archive_intake_receipt_sha256,
            "corpus_audit_receipt_sha256": self.corpus_audit_receipt_sha256,
            "preparation_receipt_sha256": self.preparation_receipt_sha256,
            "preparation_artifact_set_sha256": (self.preparation_artifact_set_sha256),
            "oracle_receipt_sha256": self.oracle_receipt_sha256,
            "oracle_receipt_file_sha256": self.oracle_receipt_file_sha256,
            "oracle_runtime_identity_sha256": self.oracle_runtime_identity_sha256,
            "runtime_observation_receipt_sha256": (
                self.runtime_observation_receipt_sha256
            ),
            "runtime_observation_receipt_file_sha256": (
                self.runtime_observation_receipt_file_sha256
            ),
            "runtime_environment_sha256": self.runtime_environment_sha256,
            "runtime_engine_wheel_binding_sha256": (
                self.runtime_engine_wheel_binding_sha256
            ),
            "target_cluster_receipt_sha256": self.target_cluster_receipt_sha256,
            "target_family_receipt_sha256": self.target_family_receipt_sha256,
            "annotation_snapshot_sha256": self.annotation_snapshot_sha256,
            "configuration": dict(
                POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_CONFIGURATION
            ),
            "configuration_sha256": self.configuration_sha256,
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": dict(self.implementation_source_members),
            "all_case_denominator": len(self.case_rows),
            "target_primary_stratum_count": len(target_strata),
            "chemistry_primary_stratum_count": len(chemistry_strata),
            "target_annotation_unavailable_case_count": sum(
                row.target_stratum_kind != "pfam_set" for row in self.case_rows
            ),
            "chemistry_ood_or_unavailable_case_count": sum(
                row.chemistry_ood_status != "admitted_profile_unvalidated"
                for row in self.case_rows
            ),
            "oracle_failure_blocked_or_no_pose_case_count": sum(
                row.oracle_status != "evaluated" for row in self.case_rows
            ),
            "batch_wall_duration_ns": self.batch_wall_duration_ns,
            "batch_rss_start_bytes": self.batch_rss_start_bytes,
            "batch_rss_end_bytes": self.batch_rss_end_bytes,
            "batch_sampled_peak_rss_bytes": self.batch_sampled_peak_rss_bytes,
            "batch_rss_sample_count": self.batch_rss_sample_count,
            "case_rows": [row.to_dict() for row in self.case_rows],
            "stratum_rows": [row.to_dict() for row in self.stratum_rows],
            "metrics": [row.to_dict() for row in self.metrics],
            "every_case_has_one_primary_target_stratum": True,
            "every_case_has_one_primary_chemistry_stratum": True,
            "all_failure_blocked_abstention_rows_retained": True,
            "target_family_metrics_present": True,
            "chemistry_stratified_metrics_present": True,
            "runtime_memory_stratified_metrics_present": True,
            "unknown_and_ood_strata_retained": True,
            "prepared_aromaticity_ring_stereo_used_only_when_verified": True,
            "raw_v2000_aromatic_bond_marks_used_for_stratification": False,
            "per_case_runtime_scope": "downstream_posebusters_oracle_loop_only",
            "per_case_full_redocking_pipeline_runtime_memory_measured": False,
            "sampled_peak_rss_is_kernel_enforced": False,
            "measurement_values_exactly_reexecutable": False,
            "target_ood_evaluated_against_training_manifest": False,
            "operator_signature_present": False,
            "independent_second_host_observation_present": False,
            "public_result_bundle_validated": False,
            "benchmark_executed": False,
            "scientific_blockers": list(
                POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_BLOCKERS
            ),
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "receipt_sha256": self.fingerprint_sha256}

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        output = Path(output_path)
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = _canonical_bytes(self.to_dict()) + b"\n"
        if len(payload) > POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_MAX_RECEIPT_BYTES:
            raise PoseBustersInternalOracleStratificationError(
                "stratification receipt exceeds its byte bound"
            )
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
                raise PoseBustersInternalOracleStratificationError(
                    "stratification receipt output already exists"
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


def _target_projection(
    target: PoseBustersRcsbTargetCase,
    cluster: PoseBustersTargetClusterCase,
) -> tuple[str, str]:
    if target.pfam_set_id is not None:
        return "pfam_set", f"pfam_set::{target.pfam_set_id}"
    if target.mapping_status == "complete":
        return (
            "observed_cluster_annotation_unavailable",
            "observed_cluster_annotation_unavailable::"
            f"{target.annotation_status}::{cluster.family_id}",
        )
    return (
        "observed_cluster_mapping_unavailable",
        "observed_cluster_mapping_unavailable::"
        f"{target.mapping_status}::{cluster.family_id}",
    )


def _prepared_perception(
    row: PoseBustersInternalPreparationCase,
    artifact_root: Path,
) -> tuple[int, int, tuple[int, ...], int, int, int]:
    artifacts = {artifact.role: artifact for artifact in row.artifacts}
    artifact = artifacts.get("canonical_ligand_json")
    if artifact is None:
        raise PoseBustersInternalOracleStratificationError(
            "prepared case lacks a canonical ligand artifact"
        )
    path = artifact_root / artifact.relative_path
    try:
        source = _read_exact_regular_file(
            path,
            maximum_bytes=POSEBUSTERS_INTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
        )
    except (PoseBustersArchiveIntakeError, OSError) as exc:
        raise PoseBustersInternalOracleStratificationError(
            "canonical prepared ligand could not be read securely"
        ) from exc
    if len(source) != artifact.size_bytes or _sha256_bytes(source) != artifact.sha256:
        raise PoseBustersInternalOracleStratificationError(
            "canonical prepared ligand artifact identity changed"
        )
    try:
        system = all_atom_system_from_canonical_json(source)
    except (TypeError, ValueError) as exc:
        raise PoseBustersInternalOracleStratificationError(
            "canonical prepared ligand is invalid"
        ) from exc
    if canonical_system_sha256(system) != artifact.system_sha256:
        raise PoseBustersInternalOracleStratificationError(
            "canonical prepared ligand system identity changed"
        )
    formal_charge = sum(atom.formal_charge for atom in system.atoms)
    heavy_atoms = sum(atom.atomic_number != 1 for atom in system.atoms)
    atomic_numbers = tuple(sorted({atom.atomic_number for atom in system.atoms}))
    aromatic_atoms = sum(atom.aromatic for atom in system.atoms)
    ring_atoms = sum(atom.metadata.get("is_in_ring") is True for atom in system.atoms)
    atom_stereo = sum(atom.stereo in {"R", "S"} for atom in system.atoms)
    bond_stereo = sum(
        bond.stereo not in {"none", "unspecified", "either", "unknown", ""}
        for bond in system.bonds
    )
    return (
        formal_charge,
        heavy_atoms,
        atomic_numbers,
        aromatic_atoms,
        ring_atoms,
        atom_stereo + bond_stereo,
    )


def _chemistry_projection(
    corpus: PoseBustersCorpusCaseAudit,
    preparation: PoseBustersInternalPreparationCase,
    artifact_root: Path,
) -> dict[str, object]:
    if corpus.status == "failure":
        charge: int | None = None
        heavy: int | None = None
        atomic_numbers: tuple[int, ...] = ()
        charge_class = "unavailable"
        heavy_class = "unavailable"
        element_class = "unavailable"
        receptor_context = "unavailable"
        ood_status = "unknown_corpus_failure"
        scope_status = "unavailable_corpus_failure"
        identity_source = "unavailable_corpus_failure"
    else:
        charge = corpus.ligand_formal_charge
        heavy = corpus.native_ligand_heavy_atom_count
        atomic_numbers = tuple(
            number for number, _count in corpus.ligand_element_counts
        )
        charge_class = _charge_class(charge)
        heavy_class = _heavy_atom_class(heavy)
        element_class = _element_class(atomic_numbers)
        receptor_context = _receptor_context_class(corpus)
        scope_status = preparation.reference_scorer_scope_status
        identity_source = "corpus_native_ligand_fallback"
        ood_status = {
            "prepared": "admitted_profile_unvalidated",
            "preparation_failure": "preparation_failure",
            "abstain_chemistry_scope": "unsupported_scope",
            "upstream_failure": "unknown_upstream_failure",
        }[preparation.status]
    if preparation.status == "prepared":
        if corpus.status == "failure":
            raise PoseBustersInternalOracleStratificationError(
                "prepared chemistry cannot follow a failed corpus audit"
            )
        (
            charge,
            heavy,
            atomic_numbers,
            aromatic_atoms,
            ring_atoms,
            stereo_features,
        ) = _prepared_perception(preparation, artifact_root)
        charge_class = _charge_class(charge)
        heavy_class = _heavy_atom_class(heavy)
        element_class = _element_class(atomic_numbers)
        identity_source = "canonical_prepared_ligand"
        aromaticity = "aromatic" if aromatic_atoms else "nonaromatic"
        ring = "ring" if ring_atoms else "acyclic"
        stereo = "assigned_stereo" if stereo_features else "no_assigned_stereo"
    else:
        aromatic_atoms = None
        ring_atoms = None
        stereo_features = None
        aromaticity = "unavailable"
        ring = "unavailable"
        stereo = "unavailable"
    chemistry_id = _chemistry_stratum_id(
        ood_status=ood_status,
        charge_class=charge_class,
        heavy_atom_class=heavy_class,
        element_class=element_class,
        aromaticity_class=aromaticity,
        ring_class=ring,
        stereo_class=stereo,
        receptor_context_class=receptor_context,
    )
    return {
        "chemistry_stratum_id": chemistry_id,
        "chemistry_ood_status": ood_status,
        "chemistry_identity_source": identity_source,
        "reference_scorer_scope_status": scope_status,
        "ligand_formal_charge": charge,
        "ligand_heavy_atom_count": heavy,
        "ligand_atomic_numbers": atomic_numbers,
        "charge_class": charge_class,
        "heavy_atom_class": heavy_class,
        "element_class": element_class,
        "aromaticity_class": aromaticity,
        "ring_class": ring,
        "stereo_class": stereo,
        "receptor_context_class": receptor_context,
        "prepared_aromatic_atom_count": aromatic_atoms,
        "prepared_ring_atom_count": ring_atoms,
        "prepared_stereo_feature_count": stereo_features,
    }


def _case_row(
    oracle: PoseBustersInternalOracleCase,
    runtime: PoseBustersInternalOracleRuntimeCase,
    corpus: PoseBustersCorpusCaseAudit,
    preparation: PoseBustersInternalPreparationCase,
    target_cluster: PoseBustersTargetClusterCase,
    target: PoseBustersRcsbTargetCase,
    preparation_artifact_root: Path,
) -> PoseBustersInternalOracleStratificationCase:
    target_kind, target_id = _target_projection(target, target_cluster)
    chemistry = _chemistry_projection(
        corpus,
        preparation,
        preparation_artifact_root,
    )
    return PoseBustersInternalOracleStratificationCase(
        case_id=oracle.case_id,
        oracle_status=oracle.status,
        selected_pose_count=oracle.selected_pose_count,
        oracle_attempted=oracle.oracle_attempted,
        target_stratum_id=target_id,
        target_stratum_kind=target_kind,
        target_cluster_id=target_cluster.family_id,
        target_mapping_status=target.mapping_status,
        target_annotation_status=target.annotation_status,
        pfam_ids=target.pfam_ids,
        target_ood_status="unknown_no_internal_fit_or_training_manifest",
        chemistry_stratum_id=chemistry["chemistry_stratum_id"],  # type: ignore[arg-type]
        chemistry_ood_status=chemistry["chemistry_ood_status"],  # type: ignore[arg-type]
        chemistry_identity_source=chemistry["chemistry_identity_source"],  # type: ignore[arg-type]
        corpus_audit_status=corpus.status,
        preparation_status=preparation.status,
        reference_scorer_scope_status=chemistry["reference_scorer_scope_status"],  # type: ignore[arg-type]
        reference_scorer_scope_blockers=(preparation.reference_scorer_scope_blockers),
        ligand_formal_charge=chemistry["ligand_formal_charge"],  # type: ignore[arg-type]
        ligand_heavy_atom_count=chemistry["ligand_heavy_atom_count"],  # type: ignore[arg-type]
        ligand_atomic_numbers=chemistry["ligand_atomic_numbers"],  # type: ignore[arg-type]
        charge_class=chemistry["charge_class"],  # type: ignore[arg-type]
        heavy_atom_class=chemistry["heavy_atom_class"],  # type: ignore[arg-type]
        element_class=chemistry["element_class"],  # type: ignore[arg-type]
        aromaticity_class=chemistry["aromaticity_class"],  # type: ignore[arg-type]
        ring_class=chemistry["ring_class"],  # type: ignore[arg-type]
        stereo_class=chemistry["stereo_class"],  # type: ignore[arg-type]
        receptor_context_class=chemistry["receptor_context_class"],  # type: ignore[arg-type]
        prepared_aromatic_atom_count=chemistry["prepared_aromatic_atom_count"],  # type: ignore[arg-type]
        prepared_ring_atom_count=chemistry["prepared_ring_atom_count"],  # type: ignore[arg-type]
        prepared_stereo_feature_count=chemistry["prepared_stereo_feature_count"],  # type: ignore[arg-type]
        has_any_valid_pose=oracle.has_any_valid_pose,
        top_1_valid_pose=oracle.top_valid(1),
        top_5_valid_pose=oracle.top_valid(5),
        top_1_rmsd_hit=oracle.top_rmsd_hit(1),
        top_5_rmsd_hit=oracle.top_rmsd_hit(5),
        top_1_valid_rmsd_hit=oracle.top_valid_rmsd_hit(1),
        top_5_valid_rmsd_hit=oracle.top_valid_rmsd_hit(5),
        wall_duration_ns=runtime.wall_duration_ns,
        rss_start_bytes=runtime.rss_start_bytes,
        rss_end_bytes=runtime.rss_end_bytes,
        sampled_peak_rss_bytes=runtime.sampled_peak_rss_bytes,
        rss_sample_count=runtime.rss_sample_count,
    )


def _current_source_members() -> tuple[tuple[str, str], ...]:
    package_root = Path(__file__).resolve().parents[1]
    paths = {
        "internal_oracle_stratification": Path(__file__),
        "molecular_models": package_root / "molecular" / "models.py",
        "molecular_serialization": package_root / "molecular" / "serialization.py",
    }
    return tuple((role, _source_file_sha256(paths[role])) for role in sorted(paths))


def _build_receipt(
    *,
    source_dataset_id: str,
    official_cohort_bound: bool,
    corpus: PoseBustersCorpusAuditReceipt,
    preparation: PoseBustersInternalPreparationReceipt,
    oracle: PoseBustersInternalOracleEvaluationReceipt,
    oracle_source: bytes,
    runtime: PoseBustersInternalOracleRuntimeObservationReceipt,
    runtime_source: bytes,
    target_cluster: PoseBustersTargetClusterReceipt,
    target_family: PoseBustersRcsbTargetFamilyReceipt,
    preparation_artifact_root: Path,
) -> PoseBustersInternalOracleStratificationReceipt:
    projections = (
        tuple(row.case_id for row in oracle.case_rows),
        tuple(row.case_id for row in runtime.case_rows),
        tuple(row.case_id for row in corpus.case_rows),
        tuple(row.case_id for row in preparation.case_rows),
        tuple(row.case_id for row in target_cluster.case_rows),
        tuple(row.case_id for row in target_family.case_rows),
    )
    if any(projection != projections[0] for projection in projections[1:]):
        raise PoseBustersInternalOracleStratificationError(
            "stratification prerequisites do not share one all-case projection"
        )
    intake_ids = {
        oracle.archive_intake_receipt_sha256,
        corpus.archive_intake_receipt_sha256,
        preparation.archive_intake_receipt_sha256,
        target_cluster.archive_intake_receipt_sha256,
        target_family.archive_intake_receipt_sha256,
    }
    if (
        len(intake_ids) != 1
        or preparation.corpus_audit_receipt_sha256 != corpus.fingerprint_sha256
        or target_family.target_cluster_receipt_sha256
        != target_cluster.fingerprint_sha256
    ):
        raise PoseBustersInternalOracleStratificationError(
            "stratification prerequisite receipts are cross-wired"
        )
    runtime_by_id = {row.case_id: row for row in runtime.case_rows}
    corpus_by_id = {row.case_id: row for row in corpus.case_rows}
    preparation_by_id = {row.case_id: row for row in preparation.case_rows}
    cluster_by_id = {row.case_id: row for row in target_cluster.case_rows}
    target_by_id = {row.case_id: row for row in target_family.case_rows}
    cases = tuple(
        _case_row(
            row,
            runtime_by_id[row.case_id],
            corpus_by_id[row.case_id],
            preparation_by_id[row.case_id],
            cluster_by_id[row.case_id],
            target_by_id[row.case_id],
            preparation_artifact_root,
        )
        for row in oracle.case_rows
    )
    strata = _aggregate_strata(cases)
    members = _current_source_members()
    return PoseBustersInternalOracleStratificationReceipt(
        source_dataset_id=source_dataset_id,
        official_cohort_bound=official_cohort_bound,
        archive_intake_receipt_sha256=next(iter(intake_ids)),
        corpus_audit_receipt_sha256=corpus.fingerprint_sha256,
        preparation_receipt_sha256=preparation.fingerprint_sha256,
        preparation_artifact_set_sha256=preparation.artifact_set_sha256,
        oracle_receipt_sha256=oracle.fingerprint_sha256,
        oracle_receipt_file_sha256=_sha256_bytes(oracle_source),
        oracle_runtime_identity_sha256=oracle.runtime_identity.fingerprint_sha256,
        runtime_observation_receipt_sha256=runtime.fingerprint_sha256,
        runtime_observation_receipt_file_sha256=_sha256_bytes(runtime_source),
        runtime_environment_sha256=runtime.runtime_environment.fingerprint_sha256,
        runtime_engine_wheel_binding_sha256=(
            runtime.engine_wheel_binding.fingerprint_sha256
        ),
        target_cluster_receipt_sha256=target_cluster.fingerprint_sha256,
        target_family_receipt_sha256=target_family.fingerprint_sha256,
        annotation_snapshot_sha256=target_family.annotation_snapshot_sha256,
        configuration_sha256=(
            POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_CONFIGURATION_SHA256
        ),
        implementation_source_sha256=_canonical_sha256(dict(members)),
        implementation_source_members=members,
        batch_wall_duration_ns=runtime.batch_wall_duration_ns,
        batch_rss_start_bytes=runtime.batch_rss_start_bytes,
        batch_rss_end_bytes=runtime.batch_rss_end_bytes,
        batch_sampled_peak_rss_bytes=runtime.batch_sampled_peak_rss_bytes,
        batch_rss_sample_count=runtime.batch_rss_sample_count,
        case_rows=cases,
        stratum_rows=strata,
        metrics=_summary_metrics(cases, strata),
    )


def _build_from_files(
    oracle_receipt_path: str | os.PathLike[str],
    runtime_observation_receipt_path: str | os.PathLike[str],
    internal_rmsd_receipt_path: str | os.PathLike[str],
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    target_cluster_receipt_path: str | os.PathLike[str],
    target_family_receipt_path: str | os.PathLike[str],
    annotation_snapshot_path: str | os.PathLike[str],
    vina_evaluation_receipt_path: str | os.PathLike[str],
    gnina_evaluation_receipt_path: str | os.PathLike[str],
    smina_evaluation_receipt_path: str | os.PathLike[str],
    *,
    expected_oracle_receipt_sha256: str,
    expected_runtime_observation_receipt_sha256: str,
    expected_internal_rmsd_receipt_sha256: str,
    expected_target_cluster_receipt_sha256: str,
    expected_annotation_snapshot_sha256: str,
    expected_vina_evaluation_receipt_sha256: str,
    expected_gnina_evaluation_receipt_sha256: str,
    expected_smina_evaluation_receipt_sha256: str,
    contract: PoseBustersArchiveContract,
    preparation_configuration: PoseBustersInternalPreparationConfig | None,
    execution_configuration: PoseBustersInternalExecutionConfig | None,
    rmsd_configuration: PoseBustersInternalRMSDConfig | None,
) -> PoseBustersInternalOracleStratificationReceipt:
    expected_oracle = _digest(
        expected_oracle_receipt_sha256,
        name="expected internal-oracle receipt",
    )
    expected_runtime = _digest(
        expected_runtime_observation_receipt_sha256,
        name="expected runtime-observation receipt",
    )
    expected_cluster = _digest(
        expected_target_cluster_receipt_sha256,
        name="expected target-cluster receipt",
    )
    try:
        corpus = verify_posebusters_corpus_audit_receipt(
            corpus_audit_receipt_path,
            archive_path,
            selection_path,
            intake_receipt_path,
            contract=contract,
        )
        preparation = verify_posebusters_internal_preparation_receipt(
            preparation_receipt_path,
            preparation_artifact_root,
            archive_path,
            selection_path,
            intake_receipt_path,
            corpus_audit_receipt_path,
            contract=contract,
            configuration=preparation_configuration,
        )
        oracle = verify_posebusters_internal_oracle_evaluation_receipt(
            oracle_receipt_path,
            internal_rmsd_receipt_path,
            execution_receipt_path,
            execution_artifact_root,
            preparation_receipt_path,
            preparation_artifact_root,
            archive_path,
            selection_path,
            intake_receipt_path,
            corpus_audit_receipt_path,
            posebusters_wheel_path,
            scratch_root,
            expected_internal_rmsd_receipt_sha256=(
                expected_internal_rmsd_receipt_sha256
            ),
            contract=contract,
            preparation_configuration=preparation_configuration,
            execution_configuration=execution_configuration,
            rmsd_configuration=rmsd_configuration,
        )
        if oracle.fingerprint_sha256 != expected_oracle:
            raise PoseBustersInternalOracleStratificationError(
                "verified oracle differs from its caller-pinned identity"
            )
        oracle_source = _read_exact_regular_file(
            oracle_receipt_path,
            maximum_bytes=POSEBUSTERS_INTERNAL_ORACLE_MAX_RECEIPT_BYTES,
        )
        runtime = _load_runtime_observation_receipt(runtime_observation_receipt_path)
        if runtime.fingerprint_sha256 != expected_runtime:
            raise PoseBustersInternalOracleStratificationError(
                "runtime observation differs from its caller-pinned identity"
            )
        runtime_source = _read_exact_regular_file(
            runtime_observation_receipt_path,
            maximum_bytes=POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_MAX_RECEIPT_BYTES,
        )
        _require_oracle_binding(runtime, oracle, oracle_source)
        target_cluster = verify_posebusters_target_cluster_binding_receipt(
            target_cluster_receipt_path,
            archive_path,
            selection_path,
            intake_receipt_path,
            vina_evaluation_receipt_path,
            gnina_evaluation_receipt_path,
            smina_evaluation_receipt_path,
            expected_vina_evaluation_receipt_sha256=(
                expected_vina_evaluation_receipt_sha256
            ),
            expected_gnina_evaluation_receipt_sha256=(
                expected_gnina_evaluation_receipt_sha256
            ),
            expected_smina_evaluation_receipt_sha256=(
                expected_smina_evaluation_receipt_sha256
            ),
            contract=contract,
        )
        if target_cluster.fingerprint_sha256 != expected_cluster:
            raise PoseBustersInternalOracleStratificationError(
                "verified target clusters differ from the pinned identity"
            )
        target_family = verify_posebusters_rcsb_target_family_binding_receipt(
            target_family_receipt_path,
            archive_path,
            selection_path,
            intake_receipt_path,
            target_cluster_receipt_path,
            annotation_snapshot_path,
            expected_target_cluster_receipt_sha256=expected_cluster,
            expected_annotation_snapshot_sha256=(expected_annotation_snapshot_sha256),
            contract=contract,
        )
    except PoseBustersInternalOracleStratificationError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise PoseBustersInternalOracleStratificationError(
            "stratification prerequisite verification failed"
        ) from exc
    official = contract.fingerprint_sha256 == (
        OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT.fingerprint_sha256
    )
    return _build_receipt(
        source_dataset_id=contract.dataset_id,
        official_cohort_bound=official,
        corpus=corpus,
        preparation=preparation,
        oracle=oracle,
        oracle_source=oracle_source,
        runtime=runtime,
        runtime_source=runtime_source,
        target_cluster=target_cluster,
        target_family=target_family,
        preparation_artifact_root=Path(preparation_artifact_root),
    )


def materialize_posebusters_internal_oracle_stratification(
    oracle_receipt_path: str | os.PathLike[str],
    runtime_observation_receipt_path: str | os.PathLike[str],
    internal_rmsd_receipt_path: str | os.PathLike[str],
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    target_cluster_receipt_path: str | os.PathLike[str],
    target_family_receipt_path: str | os.PathLike[str],
    annotation_snapshot_path: str | os.PathLike[str],
    vina_evaluation_receipt_path: str | os.PathLike[str],
    gnina_evaluation_receipt_path: str | os.PathLike[str],
    smina_evaluation_receipt_path: str | os.PathLike[str],
    *,
    expected_oracle_receipt_sha256: str,
    expected_runtime_observation_receipt_sha256: str,
    expected_internal_rmsd_receipt_sha256: str,
    expected_target_cluster_receipt_sha256: str,
    expected_annotation_snapshot_sha256: str,
    expected_vina_evaluation_receipt_sha256: str,
    expected_gnina_evaluation_receipt_sha256: str,
    expected_smina_evaluation_receipt_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    preparation_configuration: PoseBustersInternalPreparationConfig | None = None,
    execution_configuration: PoseBustersInternalExecutionConfig | None = None,
    rmsd_configuration: PoseBustersInternalRMSDConfig | None = None,
) -> PoseBustersInternalOracleStratificationReceipt:
    """Exactly verify prerequisites and build one all-case stratified receipt."""

    return _build_from_files(
        oracle_receipt_path,
        runtime_observation_receipt_path,
        internal_rmsd_receipt_path,
        execution_receipt_path,
        execution_artifact_root,
        preparation_receipt_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        posebusters_wheel_path,
        scratch_root,
        target_cluster_receipt_path,
        target_family_receipt_path,
        annotation_snapshot_path,
        vina_evaluation_receipt_path,
        gnina_evaluation_receipt_path,
        smina_evaluation_receipt_path,
        expected_oracle_receipt_sha256=expected_oracle_receipt_sha256,
        expected_runtime_observation_receipt_sha256=(
            expected_runtime_observation_receipt_sha256
        ),
        expected_internal_rmsd_receipt_sha256=(expected_internal_rmsd_receipt_sha256),
        expected_target_cluster_receipt_sha256=(expected_target_cluster_receipt_sha256),
        expected_annotation_snapshot_sha256=expected_annotation_snapshot_sha256,
        expected_vina_evaluation_receipt_sha256=(
            expected_vina_evaluation_receipt_sha256
        ),
        expected_gnina_evaluation_receipt_sha256=(
            expected_gnina_evaluation_receipt_sha256
        ),
        expected_smina_evaluation_receipt_sha256=(
            expected_smina_evaluation_receipt_sha256
        ),
        contract=contract,
        preparation_configuration=preparation_configuration,
        execution_configuration=execution_configuration,
        rmsd_configuration=rmsd_configuration,
    )


def _json_object_pairs(
    pairs: Sequence[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PoseBustersInternalOracleStratificationError(
                "stratification receipt contains a duplicate JSON key"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise PoseBustersInternalOracleStratificationError(
        f"stratification receipt contains forbidden JSON constant {value}"
    )


def _mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise PoseBustersInternalOracleStratificationError(
            f"{name} must be a JSON object"
        )
    return value


def _list(value: object, *, name: str) -> list[object]:
    if not isinstance(value, list):
        raise PoseBustersInternalOracleStratificationError(
            f"{name} must be a JSON array"
        )
    return value


def _load_stratification_receipt(
    receipt_path: str | os.PathLike[str],
) -> tuple[PoseBustersInternalOracleStratificationReceipt, bytes]:
    try:
        metadata = Path(receipt_path).stat(follow_symlinks=False)
    except OSError as exc:
        raise PoseBustersInternalOracleStratificationError(
            "stratification receipt metadata is unavailable"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersInternalOracleStratificationError(
            "stratification receipt must remain mode 0600"
        )
    try:
        source = _read_exact_regular_file(
            receipt_path,
            maximum_bytes=POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_MAX_RECEIPT_BYTES,
        )
    except (PoseBustersArchiveIntakeError, OSError) as exc:
        raise PoseBustersInternalOracleStratificationError(
            "stratification receipt could not be read securely"
        ) from exc
    try:
        raw = json.loads(
            source.decode("ascii"),
            object_pairs_hook=_json_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except PoseBustersInternalOracleStratificationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersInternalOracleStratificationError(
            "stratification receipt must be ASCII JSON"
        ) from exc
    document = _mapping(raw, name="stratification receipt")
    cases = tuple(
        PoseBustersInternalOracleStratificationCase.from_dict(
            _mapping(item, name="stratification case")
        )
        for item in _list(document.get("case_rows"), name="case rows")
    )
    strata = tuple(
        PoseBustersInternalOracleStratum.from_dict(_mapping(item, name="stratum row"))
        for item in _list(document.get("stratum_rows"), name="stratum rows")
    )
    metrics = tuple(
        PoseBustersInternalOracleStratumMetric.from_dict(
            _mapping(item, name="stratum metric")
        )
        for item in _list(document.get("metrics"), name="stratum metrics")
    )
    implementation_members = _mapping(
        document.get("implementation_source_members"),
        name="implementation source members",
    )
    receipt = PoseBustersInternalOracleStratificationReceipt(
        source_dataset_id=document.get("source_dataset_id"),  # type: ignore[arg-type]
        official_cohort_bound=document.get("official_cohort_bound"),  # type: ignore[arg-type]
        archive_intake_receipt_sha256=document.get("archive_intake_receipt_sha256"),  # type: ignore[arg-type]
        corpus_audit_receipt_sha256=document.get("corpus_audit_receipt_sha256"),  # type: ignore[arg-type]
        preparation_receipt_sha256=document.get("preparation_receipt_sha256"),  # type: ignore[arg-type]
        preparation_artifact_set_sha256=document.get("preparation_artifact_set_sha256"),  # type: ignore[arg-type]
        oracle_receipt_sha256=document.get("oracle_receipt_sha256"),  # type: ignore[arg-type]
        oracle_receipt_file_sha256=document.get("oracle_receipt_file_sha256"),  # type: ignore[arg-type]
        oracle_runtime_identity_sha256=document.get("oracle_runtime_identity_sha256"),  # type: ignore[arg-type]
        runtime_observation_receipt_sha256=document.get(
            "runtime_observation_receipt_sha256"
        ),  # type: ignore[arg-type]
        runtime_observation_receipt_file_sha256=document.get(
            "runtime_observation_receipt_file_sha256"
        ),  # type: ignore[arg-type]
        runtime_environment_sha256=document.get("runtime_environment_sha256"),  # type: ignore[arg-type]
        runtime_engine_wheel_binding_sha256=document.get(
            "runtime_engine_wheel_binding_sha256"
        ),  # type: ignore[arg-type]
        target_cluster_receipt_sha256=document.get("target_cluster_receipt_sha256"),  # type: ignore[arg-type]
        target_family_receipt_sha256=document.get("target_family_receipt_sha256"),  # type: ignore[arg-type]
        annotation_snapshot_sha256=document.get("annotation_snapshot_sha256"),  # type: ignore[arg-type]
        configuration_sha256=document.get("configuration_sha256"),  # type: ignore[arg-type]
        implementation_source_sha256=document.get("implementation_source_sha256"),  # type: ignore[arg-type]
        implementation_source_members=tuple(implementation_members.items()),  # type: ignore[arg-type]
        batch_wall_duration_ns=document.get("batch_wall_duration_ns"),  # type: ignore[arg-type]
        batch_rss_start_bytes=document.get("batch_rss_start_bytes"),  # type: ignore[arg-type]
        batch_rss_end_bytes=document.get("batch_rss_end_bytes"),  # type: ignore[arg-type]
        batch_sampled_peak_rss_bytes=document.get("batch_sampled_peak_rss_bytes"),  # type: ignore[arg-type]
        batch_rss_sample_count=document.get("batch_rss_sample_count"),  # type: ignore[arg-type]
        case_rows=cases,
        stratum_rows=strata,
        metrics=metrics,
        schema_id=document.get("schema_id"),  # type: ignore[arg-type]
    )
    if source != _canonical_bytes(receipt.to_dict()) + b"\n":
        raise PoseBustersInternalOracleStratificationError(
            "stratification receipt is not canonical or self-authenticating"
        )
    return receipt, source


def verify_posebusters_internal_oracle_stratification_receipt(
    stratification_receipt_path: str | os.PathLike[str],
    oracle_receipt_path: str | os.PathLike[str],
    runtime_observation_receipt_path: str | os.PathLike[str],
    internal_rmsd_receipt_path: str | os.PathLike[str],
    execution_receipt_path: str | os.PathLike[str],
    execution_artifact_root: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    corpus_audit_receipt_path: str | os.PathLike[str],
    posebusters_wheel_path: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    target_cluster_receipt_path: str | os.PathLike[str],
    target_family_receipt_path: str | os.PathLike[str],
    annotation_snapshot_path: str | os.PathLike[str],
    vina_evaluation_receipt_path: str | os.PathLike[str],
    gnina_evaluation_receipt_path: str | os.PathLike[str],
    smina_evaluation_receipt_path: str | os.PathLike[str],
    *,
    expected_stratification_receipt_sha256: str,
    expected_oracle_receipt_sha256: str,
    expected_runtime_observation_receipt_sha256: str,
    expected_internal_rmsd_receipt_sha256: str,
    expected_target_cluster_receipt_sha256: str,
    expected_annotation_snapshot_sha256: str,
    expected_vina_evaluation_receipt_sha256: str,
    expected_gnina_evaluation_receipt_sha256: str,
    expected_smina_evaluation_receipt_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
    preparation_configuration: PoseBustersInternalPreparationConfig | None = None,
    execution_configuration: PoseBustersInternalExecutionConfig | None = None,
    rmsd_configuration: PoseBustersInternalRMSDConfig | None = None,
) -> PoseBustersInternalOracleStratificationReceipt:
    """Rebuild the complete join and require byte-exact receipt equality."""

    observed, source = _load_stratification_receipt(stratification_receipt_path)
    expected_sha = _digest(
        expected_stratification_receipt_sha256,
        name="expected stratification receipt",
    )
    if observed.fingerprint_sha256 != expected_sha:
        raise PoseBustersInternalOracleStratificationError(
            "stratification receipt differs from its caller-pinned identity"
        )
    expected = materialize_posebusters_internal_oracle_stratification(
        oracle_receipt_path,
        runtime_observation_receipt_path,
        internal_rmsd_receipt_path,
        execution_receipt_path,
        execution_artifact_root,
        preparation_receipt_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_receipt_path,
        corpus_audit_receipt_path,
        posebusters_wheel_path,
        scratch_root,
        target_cluster_receipt_path,
        target_family_receipt_path,
        annotation_snapshot_path,
        vina_evaluation_receipt_path,
        gnina_evaluation_receipt_path,
        smina_evaluation_receipt_path,
        expected_oracle_receipt_sha256=expected_oracle_receipt_sha256,
        expected_runtime_observation_receipt_sha256=(
            expected_runtime_observation_receipt_sha256
        ),
        expected_internal_rmsd_receipt_sha256=(expected_internal_rmsd_receipt_sha256),
        expected_target_cluster_receipt_sha256=(expected_target_cluster_receipt_sha256),
        expected_annotation_snapshot_sha256=expected_annotation_snapshot_sha256,
        expected_vina_evaluation_receipt_sha256=(
            expected_vina_evaluation_receipt_sha256
        ),
        expected_gnina_evaluation_receipt_sha256=(
            expected_gnina_evaluation_receipt_sha256
        ),
        expected_smina_evaluation_receipt_sha256=(
            expected_smina_evaluation_receipt_sha256
        ),
        contract=contract,
        preparation_configuration=preparation_configuration,
        execution_configuration=execution_configuration,
        rmsd_configuration=rmsd_configuration,
    )
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersInternalOracleStratificationError(
            "stratification receipt does not match exact reconstruction"
        )
    return expected


def _add_common_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--oracle-receipt", required=True)
    command.add_argument("--runtime-observation-receipt", required=True)
    command.add_argument("--internal-rmsd-receipt", required=True)
    command.add_argument("--execution-receipt", required=True)
    command.add_argument("--execution-artifact-root", required=True)
    command.add_argument("--preparation-receipt", required=True)
    command.add_argument("--preparation-artifact-root", required=True)
    command.add_argument("--archive", required=True)
    command.add_argument("--selection", required=True)
    command.add_argument("--intake-receipt", required=True)
    command.add_argument("--corpus-audit-receipt", required=True)
    command.add_argument("--posebusters-wheel", required=True)
    command.add_argument("--scratch-root", required=True)
    command.add_argument("--target-cluster-receipt", required=True)
    command.add_argument("--target-family-receipt", required=True)
    command.add_argument("--annotation-snapshot", required=True)
    for engine in ("vina", "gnina", "smina"):
        command.add_argument(f"--{engine}-evaluation-receipt", required=True)
        command.add_argument(
            f"--expected-{engine}-evaluation-receipt-sha256",
            required=True,
        )
    command.add_argument("--expected-oracle-receipt-sha256", required=True)
    command.add_argument(
        "--expected-runtime-observation-receipt-sha256",
        required=True,
    )
    command.add_argument(
        "--expected-internal-rmsd-receipt-sha256",
        required=True,
    )
    command.add_argument(
        "--expected-target-cluster-receipt-sha256",
        required=True,
    )
    command.add_argument(
        "--expected-annotation-snapshot-sha256",
        required=True,
    )
    command.add_argument("--candidate-count", type=int, default=64)
    command.add_argument("--search-top-k", type=int, default=10)
    command.add_argument("--max-torsions", type=int, default=32)
    command.add_argument("--translation-radius", type=float, default=4.0)
    command.add_argument("--diversity-rmsd", type=float, default=0.5)
    command.add_argument("--max-refinement-steps", type=int, default=6)
    command.add_argument("--base-seed", type=int, default=7_301)
    command.add_argument("--rmsd-threshold", type=float, default=2.0)
    command.add_argument("--evaluation-top-k", type=int, default=5)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-internal-oracle-strata",
        description=(
            "Build all-case target-family, chemistry, Wilson-CI, runtime, and "
            "sampled-RSS strata for the internal PoseBusters oracle."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize")
    verify = subparsers.add_parser("verify")
    _add_common_arguments(materialize)
    _add_common_arguments(verify)
    materialize.add_argument("--receipt", required=True)
    verify.add_argument("--receipt", required=True)
    verify.add_argument(
        "--expected-stratification-receipt-sha256",
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    execution_configuration = PoseBustersInternalExecutionConfig(
        candidate_count=args.candidate_count,
        top_k=args.search_top_k,
        max_torsions=args.max_torsions,
        translation_radius_angstrom=args.translation_radius,
        diversity_rmsd_angstrom=args.diversity_rmsd,
        max_refinement_steps=args.max_refinement_steps,
        base_seed=args.base_seed,
    )
    rmsd_configuration = PoseBustersInternalRMSDConfig(
        rmsd_threshold_angstrom=args.rmsd_threshold,
        top_k=args.evaluation_top_k,
    )
    common = {
        "oracle_receipt_path": args.oracle_receipt,
        "runtime_observation_receipt_path": args.runtime_observation_receipt,
        "internal_rmsd_receipt_path": args.internal_rmsd_receipt,
        "execution_receipt_path": args.execution_receipt,
        "execution_artifact_root": args.execution_artifact_root,
        "preparation_receipt_path": args.preparation_receipt,
        "preparation_artifact_root": args.preparation_artifact_root,
        "archive_path": args.archive,
        "selection_path": args.selection,
        "intake_receipt_path": args.intake_receipt,
        "corpus_audit_receipt_path": args.corpus_audit_receipt,
        "posebusters_wheel_path": args.posebusters_wheel,
        "scratch_root": args.scratch_root,
        "target_cluster_receipt_path": args.target_cluster_receipt,
        "target_family_receipt_path": args.target_family_receipt,
        "annotation_snapshot_path": args.annotation_snapshot,
        "vina_evaluation_receipt_path": args.vina_evaluation_receipt,
        "gnina_evaluation_receipt_path": args.gnina_evaluation_receipt,
        "smina_evaluation_receipt_path": args.smina_evaluation_receipt,
        "expected_oracle_receipt_sha256": (args.expected_oracle_receipt_sha256),
        "expected_runtime_observation_receipt_sha256": (
            args.expected_runtime_observation_receipt_sha256
        ),
        "expected_internal_rmsd_receipt_sha256": (
            args.expected_internal_rmsd_receipt_sha256
        ),
        "expected_target_cluster_receipt_sha256": (
            args.expected_target_cluster_receipt_sha256
        ),
        "expected_annotation_snapshot_sha256": (
            args.expected_annotation_snapshot_sha256
        ),
        "expected_vina_evaluation_receipt_sha256": (
            args.expected_vina_evaluation_receipt_sha256
        ),
        "expected_gnina_evaluation_receipt_sha256": (
            args.expected_gnina_evaluation_receipt_sha256
        ),
        "expected_smina_evaluation_receipt_sha256": (
            args.expected_smina_evaluation_receipt_sha256
        ),
        "execution_configuration": execution_configuration,
        "rmsd_configuration": rmsd_configuration,
    }
    if args.command == "materialize":
        receipt = materialize_posebusters_internal_oracle_stratification(**common)
        receipt.write_json(args.receipt)
    else:
        receipt = verify_posebusters_internal_oracle_stratification_receipt(
            stratification_receipt_path=args.receipt,
            expected_stratification_receipt_sha256=(
                args.expected_stratification_receipt_sha256
            ),
            **common,
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "target_primary_stratum_count": sum(
                    row.dimension == "target" for row in receipt.stratum_rows
                ),
                "chemistry_primary_stratum_count": sum(
                    row.dimension == "chemistry" for row in receipt.stratum_rows
                ),
                "target_family_metrics_present": True,
                "chemistry_stratified_metrics_present": True,
                "runtime_memory_stratified_metrics_present": True,
                "benchmark_executed": False,
                "scientifically_validated": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
