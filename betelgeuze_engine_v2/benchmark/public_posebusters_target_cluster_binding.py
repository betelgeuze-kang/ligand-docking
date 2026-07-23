"""Bind PoseBusters engine results to conservative observed-target clusters.

The receipt in this module is deliberately narrower than a biological target-
family or training-leakage audit.  It reconstructs residue-label sequences from
the exact receptor PDB ``ATOM`` rows, clusters cases only when at least one
eligible chain pair has at least 90 percent global edit similarity, and projects
the frozen Vina, GNINA, and Smina PoseBusters result receipts onto the same
cluster denominator.  Missing external training or parameter-fit manifests
remain explicit blockers, so no leakage-free or public-benchmark claim opens.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
import math
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Sequence
import zipfile

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _positive_int,
    _source_file_sha256,
    _token,
)
from .public_posebusters_external_generated_pose_evaluation import (
    POSEBUSTERS_EXTERNAL_GENERATED_POSE_CASE_SCHEMA_ID,
    POSEBUSTERS_EXTERNAL_GENERATED_POSE_EVALUATION_SCHEMA_ID,
    POSEBUSTERS_EXTERNAL_GENERATED_POSE_MAX_RECEIPT_BYTES,
)
from .public_posebusters_generated_pose_evaluation import (
    POSEBUSTERS_GENERATED_POSE_CASE_SCHEMA_ID,
    POSEBUSTERS_GENERATED_POSE_EVALUATION_SCHEMA_ID,
    POSEBUSTERS_GENERATED_POSE_MAX_RECEIPT_BYTES,
    _case_id,
    _digest,
    _hash_bytes,
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


POSEBUSTERS_TARGET_CLUSTER_CHAIN_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_target_cluster_chain/1.0.0"
)
POSEBUSTERS_TARGET_CLUSTER_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_target_cluster_case/1.0.0"
)
POSEBUSTERS_TARGET_CLUSTER_LINK_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_target_cluster_link/1.0.0"
)
POSEBUSTERS_TARGET_CLUSTER_FAMILY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_target_cluster_family/1.0.0"
)
POSEBUSTERS_TARGET_CLUSTER_EVALUATION_INPUT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_target_cluster_evaluation_input/1.0.0"
)
POSEBUSTERS_TARGET_CLUSTER_ENGINE_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_target_cluster_engine_case/1.0.0"
)
POSEBUSTERS_TARGET_CLUSTER_ENGINE_FAMILY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_target_cluster_engine_family/1.0.0"
)
POSEBUSTERS_TARGET_CLUSTER_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_target_cluster_metric/1.0.0"
)
POSEBUSTERS_TARGET_CLUSTER_LEAKAGE_DISPOSITION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_target_cluster_leakage_disposition/1.0.0"
)
POSEBUSTERS_TARGET_CLUSTER_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_target_cluster_receipt/1.0.0"
)

POSEBUSTERS_TARGET_CLUSTER_ENGINES = ("vina", "gnina", "smina")
POSEBUSTERS_TARGET_CLUSTER_MINIMUM_CHAIN_RESIDUES = 20
POSEBUSTERS_TARGET_CLUSTER_SIMILARITY_NUMERATOR = 9
POSEBUSTERS_TARGET_CLUSTER_SIMILARITY_DENOMINATOR = 10
POSEBUSTERS_TARGET_CLUSTER_MAX_CHAINS_PER_CASE = 64
POSEBUSTERS_TARGET_CLUSTER_MAX_RESIDUES_PER_CHAIN = 10_000
POSEBUSTERS_TARGET_CLUSTER_MAX_CASES = 308
POSEBUSTERS_TARGET_CLUSTER_MAX_RECEIPT_BYTES = 16 * 1024 * 1024
POSEBUSTERS_TARGET_CLUSTER_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_TARGET_CLUSTER_Z = 1.959963984540054

POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION = {
    "archive_access": "bounded_zip_member_access_without_extraction",
    "case_link_evidence": (
        "one_maximum_similarity_chain_pair_ties_by_distance_then_ordinals"
    ),
    "case_link_policy": "any_eligible_chain_pair_meets_threshold",
    "chain_identity": "pdb_chain_id_in_first_coordinate_model",
    "chain_order": "first_residue_appearance_order",
    "family_construction": "connected_components_of_case_links",
    "family_id": "sha256_of_configuration_and_sorted_member_case_ids",
    "family_metric_aggregation": (
        "binary_any_member_for_pose_outcome_with_complete_coverage_separate"
    ),
    "minimum_chain_residues": POSEBUSTERS_TARGET_CLUSTER_MINIMUM_CHAIN_RESIDUES,
    "pdb_record_type": "ATOM_only",
    "residue_identity": "exact_three_character_residue_label",
    "sequence_distance": "global_unit_cost_levenshtein_myers_bit_vector",
    "sequence_similarity": "1_minus_edit_distance_divided_by_maximum_chain_length",
    "similarity_threshold_denominator": (
        POSEBUSTERS_TARGET_CLUSTER_SIMILARITY_DENOMINATOR
    ),
    "similarity_threshold_numerator": (
        POSEBUSTERS_TARGET_CLUSTER_SIMILARITY_NUMERATOR
    ),
    "short_chain_policy": "retained_in_case_identity_but_ineligible_for_links",
    "target_cluster_semantics": "observed_receptor_near_identity_proxy_not_biological_family",
}
POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION_SHA256 = (
    "5b713f0680f796457da8f48261d78dee5e5c2caf36677f5f9777276083dc3c94"
)

POSEBUSTERS_TARGET_CLUSTER_SCIENTIFIC_BLOCKERS = (
    "observed_sequence_clusters_are_not_biological_target_family_annotations",
    "external_engine_training_or_parameter_fit_manifests_missing",
    "target_sequence_training_leakage_not_evaluated",
    "ligand_and_scaffold_training_leakage_not_evaluated",
    "independent_target_cluster_review_missing",
    "public_docking_benchmark_claim_not_authorized",
)

_EXECUTION_STATUSES = {
    "success",
    "engine_failure",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "abstain_chemistry_scope",
}
_EVALUATION_STATUSES = {
    "evaluated",
    "partial_evaluation",
    "evaluation_failure",
    "blocked_engine_failure",
    "blocked_vina_engine_failure",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "abstain_chemistry_scope",
}
_SHA256_CHARACTERS = frozenset("0123456789abcdef")


class PoseBustersTargetClusterBindingError(ValueError):
    """Target-cluster source, result, aggregation, or receipt is invalid."""


def _engine_id(value: object) -> str:
    engine = _token(value, name="target-cluster engine")
    if engine not in POSEBUSTERS_TARGET_CLUSTER_ENGINES:
        raise PoseBustersTargetClusterBindingError(
            "target-cluster engine must be vina, gnina, or smina"
        )
    return engine


def _boolean(value: object, *, name: str) -> bool:
    if type(value) is not bool:
        raise PoseBustersTargetClusterBindingError(f"{name} must be boolean")
    return value


def _bounded_text(value: object, *, name: str, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > maximum
        or any(character in "\r\n\x00" for character in value)
    ):
        raise PoseBustersTargetClusterBindingError(
            f"{name} must be bounded non-empty text"
        )
    return value


def _nonnegative_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PoseBustersTargetClusterBindingError(
            f"{name} must be a non-negative integer"
        )
    return value


def _family_id(member_case_ids: Sequence[str]) -> str:
    members = tuple(member_case_ids)
    digest = _canonical_sha256(
        {
            "configuration_sha256": (
                POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION_SHA256
            ),
            "member_case_ids": list(members),
        }
    )
    return f"observed_target_cluster_{digest}"


@dataclass(frozen=True, slots=True)
class PoseBustersObservedTargetChain:
    chain_ordinal: int
    chain_id: str
    residue_count: int
    residue_label_sequence_sha256: str
    comparison_eligible: bool
    schema_id: str = POSEBUSTERS_TARGET_CLUSTER_CHAIN_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_TARGET_CLUSTER_CHAIN_SCHEMA_ID:
            raise PoseBustersTargetClusterBindingError(
                "unsupported target-cluster chain schema"
            )
        ordinal = _nonnegative_int(
            self.chain_ordinal,
            name="target-cluster chain ordinal",
        )
        if not isinstance(self.chain_id, str) or len(self.chain_id) != 1:
            raise PoseBustersTargetClusterBindingError(
                "target-cluster chain ID must be one character"
            )
        count = _positive_int(
            self.residue_count,
            name="target-cluster residue count",
        )
        if count > POSEBUSTERS_TARGET_CLUSTER_MAX_RESIDUES_PER_CHAIN:
            raise PoseBustersTargetClusterBindingError(
                "target-cluster chain exceeds its residue bound"
            )
        digest = _digest(
            self.residue_label_sequence_sha256,
            name="target-cluster residue-label sequence",
        )
        eligible = _boolean(
            self.comparison_eligible,
            name="target-cluster comparison eligibility",
        )
        if eligible != (
            count >= POSEBUSTERS_TARGET_CLUSTER_MINIMUM_CHAIN_RESIDUES
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster chain eligibility is inconsistent"
            )
        object.__setattr__(self, "chain_ordinal", ordinal)
        object.__setattr__(self, "residue_count", count)
        object.__setattr__(self, "residue_label_sequence_sha256", digest)
        object.__setattr__(self, "comparison_eligible", eligible)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "chain_ordinal": self.chain_ordinal,
            "chain_id": self.chain_id,
            "residue_count": self.residue_count,
            "residue_label_sequence_sha256": (
                self.residue_label_sequence_sha256
            ),
            "comparison_eligible": self.comparison_eligible,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersTargetClusterCase:
    case_id: str
    pdb_id: str
    receptor_sha256: str
    target_sequence_set_sha256: str
    family_id: str
    chains: tuple[PoseBustersObservedTargetChain, ...]
    schema_id: str = POSEBUSTERS_TARGET_CLUSTER_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_TARGET_CLUSTER_CASE_SCHEMA_ID:
            raise PoseBustersTargetClusterBindingError(
                "unsupported target-cluster case schema"
            )
        case = _case_id(self.case_id)
        pdb = _bounded_text(self.pdb_id, name="target-cluster PDB ID")
        if case.split("_", 1)[0] != pdb:
            raise PoseBustersTargetClusterBindingError(
                "target-cluster PDB and case identities disagree"
            )
        receptor = _digest(self.receptor_sha256, name="target-cluster receptor")
        sequence_set = _digest(
            self.target_sequence_set_sha256,
            name="target-cluster sequence set",
        )
        family = _bounded_text(
            self.family_id,
            name="target-cluster family ID",
            maximum=128,
        )
        chains = tuple(self.chains)
        if (
            not chains
            or len(chains) > POSEBUSTERS_TARGET_CLUSTER_MAX_CHAINS_PER_CASE
            or tuple(row.chain_ordinal for row in chains)
            != tuple(range(len(chains)))
            or not any(row.comparison_eligible for row in chains)
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster case chains are invalid or ineligible"
            )
        if sequence_set != _canonical_sha256(
            [row.to_dict() for row in chains]
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster sequence-set identity is inconsistent"
            )
        object.__setattr__(self, "case_id", case)
        object.__setattr__(self, "pdb_id", pdb)
        object.__setattr__(self, "receptor_sha256", receptor)
        object.__setattr__(self, "target_sequence_set_sha256", sequence_set)
        object.__setattr__(self, "family_id", family)
        object.__setattr__(self, "chains", chains)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "pdb_id": self.pdb_id,
            "receptor_sha256": self.receptor_sha256,
            "target_sequence_set_sha256": self.target_sequence_set_sha256,
            "family_id": self.family_id,
            "chain_count": len(self.chains),
            "eligible_chain_count": sum(
                row.comparison_eligible for row in self.chains
            ),
            "chains": [row.to_dict() for row in self.chains],
        }


@dataclass(frozen=True, slots=True)
class PoseBustersTargetClusterLink:
    left_case_id: str
    right_case_id: str
    left_chain_ordinal: int
    right_chain_ordinal: int
    edit_distance: int
    maximum_chain_length: int
    schema_id: str = POSEBUSTERS_TARGET_CLUSTER_LINK_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_TARGET_CLUSTER_LINK_SCHEMA_ID:
            raise PoseBustersTargetClusterBindingError(
                "unsupported target-cluster link schema"
            )
        left = _case_id(self.left_case_id)
        right = _case_id(self.right_case_id)
        if left >= right:
            raise PoseBustersTargetClusterBindingError(
                "target-cluster link endpoints must be ordered"
            )
        left_ordinal = _nonnegative_int(
            self.left_chain_ordinal,
            name="left target-cluster chain ordinal",
        )
        right_ordinal = _nonnegative_int(
            self.right_chain_ordinal,
            name="right target-cluster chain ordinal",
        )
        distance = _nonnegative_int(
            self.edit_distance,
            name="target-cluster edit distance",
        )
        maximum = _positive_int(
            self.maximum_chain_length,
            name="target-cluster maximum chain length",
        )
        if (
            distance > maximum
            or distance * POSEBUSTERS_TARGET_CLUSTER_SIMILARITY_DENOMINATOR
            > maximum
            * (
                POSEBUSTERS_TARGET_CLUSTER_SIMILARITY_DENOMINATOR
                - POSEBUSTERS_TARGET_CLUSTER_SIMILARITY_NUMERATOR
            )
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster link does not meet the frozen threshold"
            )
        object.__setattr__(self, "left_case_id", left)
        object.__setattr__(self, "right_case_id", right)
        object.__setattr__(self, "left_chain_ordinal", left_ordinal)
        object.__setattr__(self, "right_chain_ordinal", right_ordinal)
        object.__setattr__(self, "edit_distance", distance)
        object.__setattr__(self, "maximum_chain_length", maximum)

    @property
    def similarity_binary64_hex(self) -> str:
        return (1.0 - self.edit_distance / self.maximum_chain_length).hex()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "left_case_id": self.left_case_id,
            "right_case_id": self.right_case_id,
            "left_chain_ordinal": self.left_chain_ordinal,
            "right_chain_ordinal": self.right_chain_ordinal,
            "edit_distance": self.edit_distance,
            "maximum_chain_length": self.maximum_chain_length,
            "similarity_binary64_hex": self.similarity_binary64_hex,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersTargetClusterFamily:
    family_id: str
    member_case_ids: tuple[str, ...]
    schema_id: str = POSEBUSTERS_TARGET_CLUSTER_FAMILY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_TARGET_CLUSTER_FAMILY_SCHEMA_ID:
            raise PoseBustersTargetClusterBindingError(
                "unsupported target-cluster family schema"
            )
        members = tuple(_case_id(value) for value in self.member_case_ids)
        if (
            not members
            or tuple(sorted(members)) != members
            or len(set(members)) != len(members)
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster family members must be unique and ordered"
            )
        family = _bounded_text(
            self.family_id,
            name="target-cluster family ID",
            maximum=128,
        )
        if family != _family_id(members):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster family identity is inconsistent"
            )
        object.__setattr__(self, "family_id", family)
        object.__setattr__(self, "member_case_ids", members)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "family_id": self.family_id,
            "member_case_count": len(self.member_case_ids),
            "member_case_ids": list(self.member_case_ids),
        }


@dataclass(frozen=True, slots=True)
class PoseBustersTargetClusterEvaluationInput:
    engine_id: str
    evaluation_receipt_sha256: str
    evaluation_receipt_file_sha256: str
    execution_receipt_sha256: str
    generated_pose_count: int
    evaluated_pose_count: int
    schema_id: str = POSEBUSTERS_TARGET_CLUSTER_EVALUATION_INPUT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_TARGET_CLUSTER_EVALUATION_INPUT_SCHEMA_ID:
            raise PoseBustersTargetClusterBindingError(
                "unsupported target-cluster evaluation-input schema"
            )
        engine = _engine_id(self.engine_id)
        for name in (
            "evaluation_receipt_sha256",
            "evaluation_receipt_file_sha256",
            "execution_receipt_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        generated = _positive_int(
            self.generated_pose_count,
            name="target-cluster generated-pose count",
        )
        evaluated = _positive_int(
            self.evaluated_pose_count,
            name="target-cluster evaluated-pose count",
        )
        if evaluated > generated:
            raise PoseBustersTargetClusterBindingError(
                "evaluated-pose count exceeds generated-pose count"
            )
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "generated_pose_count", generated)
        object.__setattr__(self, "evaluated_pose_count", evaluated)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "engine_id": self.engine_id,
            "evaluation_receipt_sha256": self.evaluation_receipt_sha256,
            "evaluation_receipt_file_sha256": (
                self.evaluation_receipt_file_sha256
            ),
            "execution_receipt_sha256": self.execution_receipt_sha256,
            "generated_pose_count": self.generated_pose_count,
            "evaluated_pose_count": self.evaluated_pose_count,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersTargetClusterEngineCase:
    engine_id: str
    case_id: str
    family_id: str
    execution_status: str
    evaluation_status: str
    execution_pose_count: int
    evaluated_pose_count: int
    physically_valid_pose_count: int
    top_1_physically_valid: bool
    top_5_physically_valid: bool
    top_1_rmsd_hit: bool
    top_5_rmsd_hit: bool
    top_1_valid_rmsd_hit: bool
    top_5_valid_rmsd_hit: bool
    schema_id: str = POSEBUSTERS_TARGET_CLUSTER_ENGINE_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_TARGET_CLUSTER_ENGINE_CASE_SCHEMA_ID:
            raise PoseBustersTargetClusterBindingError(
                "unsupported target-cluster engine-case schema"
            )
        engine = _engine_id(self.engine_id)
        case = _case_id(self.case_id)
        family = _bounded_text(
            self.family_id,
            name="engine-case target-cluster family",
            maximum=128,
        )
        if self.execution_status not in _EXECUTION_STATUSES:
            raise PoseBustersTargetClusterBindingError(
                "target-cluster execution status is invalid"
            )
        if self.evaluation_status not in _EVALUATION_STATUSES:
            raise PoseBustersTargetClusterBindingError(
                "target-cluster evaluation status is invalid"
            )
        execution_poses = _nonnegative_int(
            self.execution_pose_count,
            name="target-cluster execution-pose count",
        )
        evaluated_poses = _nonnegative_int(
            self.evaluated_pose_count,
            name="target-cluster evaluated-pose count",
        )
        valid_poses = _nonnegative_int(
            self.physically_valid_pose_count,
            name="target-cluster physically-valid-pose count",
        )
        flags = tuple(
            _boolean(getattr(self, name), name=name)
            for name in (
                "top_1_physically_valid",
                "top_5_physically_valid",
                "top_1_rmsd_hit",
                "top_5_rmsd_hit",
                "top_1_valid_rmsd_hit",
                "top_5_valid_rmsd_hit",
            )
        )
        if self.execution_status == "success":
            valid = (
                execution_poses > 0
                and evaluated_poses <= execution_poses
                and valid_poses <= evaluated_poses
                and self.evaluation_status
                in {"evaluated", "partial_evaluation", "evaluation_failure"}
                and (not flags[0] or flags[1])
                and (not flags[2] or flags[3])
                and (not flags[4] or (flags[0] and flags[2]))
                and (not flags[5] or (flags[1] and flags[3]))
            )
        else:
            expected = {
                "engine_failure": {
                    "blocked_engine_failure",
                    "blocked_vina_engine_failure",
                },
                "blocked_preparation_failure": {"blocked_preparation_failure"},
                "blocked_upstream_failure": {"blocked_upstream_failure"},
                "abstain_chemistry_scope": {"abstain_chemistry_scope"},
            }[self.execution_status]
            valid = (
                self.evaluation_status in expected
                and execution_poses == 0
                and evaluated_poses == 0
                and valid_poses == 0
                and not any(flags)
            )
        if not valid:
            raise PoseBustersTargetClusterBindingError(
                "target-cluster engine-case disposition is inconsistent"
            )
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "case_id", case)
        object.__setattr__(self, "family_id", family)
        object.__setattr__(self, "execution_pose_count", execution_poses)
        object.__setattr__(self, "evaluated_pose_count", evaluated_poses)
        object.__setattr__(self, "physically_valid_pose_count", valid_poses)

    @property
    def execution_success(self) -> bool:
        return self.execution_status == "success"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "engine_id": self.engine_id,
            "case_id": self.case_id,
            "family_id": self.family_id,
            "execution_status": self.execution_status,
            "evaluation_status": self.evaluation_status,
            "execution_pose_count": self.execution_pose_count,
            "evaluated_pose_count": self.evaluated_pose_count,
            "physically_valid_pose_count": self.physically_valid_pose_count,
            "top_1_physically_valid": self.top_1_physically_valid,
            "top_5_physically_valid": self.top_5_physically_valid,
            "top_1_rmsd_hit": self.top_1_rmsd_hit,
            "top_5_rmsd_hit": self.top_5_rmsd_hit,
            "top_1_valid_rmsd_hit": self.top_1_valid_rmsd_hit,
            "top_5_valid_rmsd_hit": self.top_5_valid_rmsd_hit,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersTargetClusterEngineFamily:
    engine_id: str
    family_id: str
    member_case_count: int
    execution_success_case_count: int
    top_1_physically_valid_case_count: int
    top_5_physically_valid_case_count: int
    top_1_rmsd_hit_case_count: int
    top_5_rmsd_hit_case_count: int
    top_1_valid_rmsd_hit_case_count: int
    top_5_valid_rmsd_hit_case_count: int
    schema_id: str = POSEBUSTERS_TARGET_CLUSTER_ENGINE_FAMILY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_TARGET_CLUSTER_ENGINE_FAMILY_SCHEMA_ID:
            raise PoseBustersTargetClusterBindingError(
                "unsupported target-cluster engine-family schema"
            )
        engine = _engine_id(self.engine_id)
        family = _bounded_text(
            self.family_id,
            name="engine-family target cluster",
            maximum=128,
        )
        member_count = _positive_int(
            self.member_case_count,
            name="engine-family member-case count",
        )
        count_names = (
            "execution_success_case_count",
            "top_1_physically_valid_case_count",
            "top_5_physically_valid_case_count",
            "top_1_rmsd_hit_case_count",
            "top_5_rmsd_hit_case_count",
            "top_1_valid_rmsd_hit_case_count",
            "top_5_valid_rmsd_hit_case_count",
        )
        counts = tuple(
            _nonnegative_int(getattr(self, name), name=name)
            for name in count_names
        )
        success = counts[0]
        if (
            success > member_count
            or any(value > success for value in counts[1:])
            or counts[1] > counts[2]
            or counts[3] > counts[4]
            or counts[5] > counts[1]
            or counts[5] > counts[3]
            or counts[6] > counts[2]
            or counts[6] > counts[4]
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster engine-family counts are inconsistent"
            )
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "family_id", family)
        object.__setattr__(self, "member_case_count", member_count)
        for name, value in zip(count_names, counts):
            object.__setattr__(self, name, value)

    @property
    def covered(self) -> bool:
        return self.execution_success_case_count > 0

    @property
    def completely_covered(self) -> bool:
        return self.execution_success_case_count == self.member_case_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "engine_id": self.engine_id,
            "family_id": self.family_id,
            "member_case_count": self.member_case_count,
            "execution_success_case_count": self.execution_success_case_count,
            "covered": self.covered,
            "completely_covered": self.completely_covered,
            "top_1_physically_valid_case_count": (
                self.top_1_physically_valid_case_count
            ),
            "top_5_physically_valid_case_count": (
                self.top_5_physically_valid_case_count
            ),
            "top_1_rmsd_hit_case_count": self.top_1_rmsd_hit_case_count,
            "top_5_rmsd_hit_case_count": self.top_5_rmsd_hit_case_count,
            "top_1_valid_rmsd_hit_case_count": (
                self.top_1_valid_rmsd_hit_case_count
            ),
            "top_5_valid_rmsd_hit_case_count": (
                self.top_5_valid_rmsd_hit_case_count
            ),
        }


@dataclass(frozen=True, slots=True)
class PoseBustersTargetClusterMetric:
    engine_id: str
    metric_id: str
    denominator_scope: str
    numerator: int
    denominator: int
    estimate: float
    confidence_interval_low: float
    confidence_interval_high: float
    schema_id: str = POSEBUSTERS_TARGET_CLUSTER_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_TARGET_CLUSTER_METRIC_SCHEMA_ID:
            raise PoseBustersTargetClusterBindingError(
                "unsupported target-cluster metric schema"
            )
        engine = _engine_id(self.engine_id)
        metric = _token(self.metric_id, name="target-cluster metric")
        scope = _token(
            self.denominator_scope,
            name="target-cluster metric denominator scope",
        )
        numerator = _nonnegative_int(
            self.numerator,
            name="target-cluster metric numerator",
        )
        denominator = _positive_int(
            self.denominator,
            name="target-cluster metric denominator",
        )
        values = (
            float(self.estimate),
            float(self.confidence_interval_low),
            float(self.confidence_interval_high),
        )
        if (
            numerator > denominator
            or any(
                not math.isfinite(value) or not 0.0 <= value <= 1.0
                for value in values
            )
            or not values[1] <= values[0] <= values[2]
            or not math.isclose(
                values[0],
                numerator / denominator,
                abs_tol=1.0e-15,
            )
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster metric is inconsistent"
            )
        object.__setattr__(self, "engine_id", engine)
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
            "metric_id": self.metric_id,
            "denominator_scope": self.denominator_scope,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "estimate": self.estimate,
            "confidence_level": POSEBUSTERS_TARGET_CLUSTER_CONFIDENCE_LEVEL,
            "confidence_interval_method": "wilson_score_binomial",
            "confidence_interval_low": self.confidence_interval_low,
            "confidence_interval_high": self.confidence_interval_high,
        }


def _metric(
    engine_id: str,
    metric_id: str,
    denominator_scope: str,
    numerator: int,
    denominator: int,
) -> PoseBustersTargetClusterMetric:
    proportion = numerator / denominator
    z2 = POSEBUSTERS_TARGET_CLUSTER_Z**2
    scale = 1.0 + z2 / denominator
    center = (proportion + z2 / (2.0 * denominator)) / scale
    radius = (
        POSEBUSTERS_TARGET_CLUSTER_Z
        * math.sqrt(
            proportion * (1.0 - proportion) / denominator
            + z2 / (4.0 * denominator**2)
        )
        / scale
    )
    return PoseBustersTargetClusterMetric(
        engine_id=engine_id,
        metric_id=metric_id,
        denominator_scope=denominator_scope,
        numerator=numerator,
        denominator=denominator,
        estimate=proportion,
        confidence_interval_low=min(proportion, max(0.0, center - radius)),
        confidence_interval_high=max(proportion, min(1.0, center + radius)),
    )


def _summary_metrics(
    rows: Sequence[PoseBustersTargetClusterEngineFamily],
) -> tuple[PoseBustersTargetClusterMetric, ...]:
    metrics: list[PoseBustersTargetClusterMetric] = []
    for engine in POSEBUSTERS_TARGET_CLUSTER_ENGINES:
        engine_rows = tuple(row for row in rows if row.engine_id == engine)
        covered = tuple(row for row in engine_rows if row.covered)
        if not engine_rows or not covered:
            raise PoseBustersTargetClusterBindingError(
                "target-cluster metrics require covered rows for every engine"
            )
        all_predicates = (
            ("target_cluster_coverage_rate", lambda row: row.covered),
            (
                "complete_target_cluster_coverage_rate",
                lambda row: row.completely_covered,
            ),
            (
                "target_cluster_with_any_top_1_rmsd_hit_rate",
                lambda row: row.top_1_rmsd_hit_case_count > 0,
            ),
            (
                "target_cluster_with_any_top_5_rmsd_hit_rate",
                lambda row: row.top_5_rmsd_hit_case_count > 0,
            ),
            (
                "target_cluster_with_any_top_1_valid_rmsd_hit_rate",
                lambda row: row.top_1_valid_rmsd_hit_case_count > 0,
            ),
            (
                "target_cluster_with_any_top_5_valid_rmsd_hit_rate",
                lambda row: row.top_5_valid_rmsd_hit_case_count > 0,
            ),
        )
        conditional_predicates = (
            (
                "covered_target_cluster_with_any_top_1_physically_valid_rate",
                lambda row: row.top_1_physically_valid_case_count > 0,
            ),
            (
                "covered_target_cluster_with_any_top_5_physically_valid_rate",
                lambda row: row.top_5_physically_valid_case_count > 0,
            ),
            (
                "covered_target_cluster_with_any_top_1_rmsd_hit_rate",
                lambda row: row.top_1_rmsd_hit_case_count > 0,
            ),
            (
                "covered_target_cluster_with_any_top_5_rmsd_hit_rate",
                lambda row: row.top_5_rmsd_hit_case_count > 0,
            ),
            (
                "covered_target_cluster_with_any_top_1_valid_rmsd_hit_rate",
                lambda row: row.top_1_valid_rmsd_hit_case_count > 0,
            ),
            (
                "covered_target_cluster_with_any_top_5_valid_rmsd_hit_rate",
                lambda row: row.top_5_valid_rmsd_hit_case_count > 0,
            ),
        )
        metrics.extend(
            _metric(
                engine,
                metric_id,
                "all_target_clusters",
                sum(bool(predicate(row)) for row in engine_rows),
                len(engine_rows),
            )
            for metric_id, predicate in all_predicates
        )
        metrics.extend(
            _metric(
                engine,
                metric_id,
                f"{engine}_covered_target_clusters",
                sum(bool(predicate(row)) for row in covered),
                len(covered),
            )
            for metric_id, predicate in conditional_predicates
        )
    return tuple(metrics)


@dataclass(frozen=True, slots=True)
class PoseBustersExternalTrainingLeakageDisposition:
    engine_id: str
    fit_or_training_manifest_status: str = "missing"
    target_sequence_leakage_evaluated: bool = False
    ligand_scaffold_leakage_evaluated: bool = False
    schema_id: str = POSEBUSTERS_TARGET_CLUSTER_LEAKAGE_DISPOSITION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_TARGET_CLUSTER_LEAKAGE_DISPOSITION_SCHEMA_ID:
            raise PoseBustersTargetClusterBindingError(
                "unsupported target-cluster leakage-disposition schema"
            )
        engine = _engine_id(self.engine_id)
        if self.fit_or_training_manifest_status != "missing":
            raise PoseBustersTargetClusterBindingError(
                "only an explicitly missing external fit manifest is supported"
            )
        if _boolean(
            self.target_sequence_leakage_evaluated,
            name="target-sequence leakage evaluated",
        ) or _boolean(
            self.ligand_scaffold_leakage_evaluated,
            name="ligand/scaffold leakage evaluated",
        ):
            raise PoseBustersTargetClusterBindingError(
                "leakage cannot be evaluated without an external fit manifest"
            )
        object.__setattr__(self, "engine_id", engine)

    @property
    def blockers(self) -> tuple[str, ...]:
        return (
            f"{self.engine_id}_fit_or_training_manifest_missing",
            f"{self.engine_id}_target_sequence_training_leakage_not_evaluated",
            f"{self.engine_id}_ligand_scaffold_training_leakage_not_evaluated",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "engine_id": self.engine_id,
            "fit_or_training_manifest_status": (
                self.fit_or_training_manifest_status
            ),
            "target_sequence_leakage_evaluated": (
                self.target_sequence_leakage_evaluated
            ),
            "ligand_scaffold_leakage_evaluated": (
                self.ligand_scaffold_leakage_evaluated
            ),
            "blockers": list(self.blockers),
            "leakage_control_passed": False,
        }


def _aggregate_engine_families(
    families: Sequence[PoseBustersTargetClusterFamily],
    engine_cases: Sequence[PoseBustersTargetClusterEngineCase],
) -> tuple[PoseBustersTargetClusterEngineFamily, ...]:
    by_identity = {
        (row.engine_id, row.case_id): row for row in engine_cases
    }
    rows: list[PoseBustersTargetClusterEngineFamily] = []
    for engine in POSEBUSTERS_TARGET_CLUSTER_ENGINES:
        for family in families:
            members = tuple(
                by_identity[(engine, case_id)]
                for case_id in family.member_case_ids
            )
            rows.append(
                PoseBustersTargetClusterEngineFamily(
                    engine_id=engine,
                    family_id=family.family_id,
                    member_case_count=len(members),
                    execution_success_case_count=sum(
                        row.execution_success for row in members
                    ),
                    top_1_physically_valid_case_count=sum(
                        row.top_1_physically_valid for row in members
                    ),
                    top_5_physically_valid_case_count=sum(
                        row.top_5_physically_valid for row in members
                    ),
                    top_1_rmsd_hit_case_count=sum(
                        row.top_1_rmsd_hit for row in members
                    ),
                    top_5_rmsd_hit_case_count=sum(
                        row.top_5_rmsd_hit for row in members
                    ),
                    top_1_valid_rmsd_hit_case_count=sum(
                        row.top_1_valid_rmsd_hit for row in members
                    ),
                    top_5_valid_rmsd_hit_case_count=sum(
                        row.top_5_valid_rmsd_hit for row in members
                    ),
                )
            )
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class PoseBustersTargetClusterReceipt:
    archive_intake_receipt_sha256: str
    corpus_audit_receipt_sha256: str
    preparation_receipt_sha256: str
    configuration_sha256: str
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    evaluation_inputs: tuple[PoseBustersTargetClusterEvaluationInput, ...]
    case_rows: tuple[PoseBustersTargetClusterCase, ...]
    cluster_links: tuple[PoseBustersTargetClusterLink, ...]
    family_rows: tuple[PoseBustersTargetClusterFamily, ...]
    engine_case_rows: tuple[PoseBustersTargetClusterEngineCase, ...]
    engine_family_rows: tuple[PoseBustersTargetClusterEngineFamily, ...]
    metrics: tuple[PoseBustersTargetClusterMetric, ...]
    leakage_dispositions: tuple[
        PoseBustersExternalTrainingLeakageDisposition, ...
    ]
    schema_id: str = POSEBUSTERS_TARGET_CLUSTER_RECEIPT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_TARGET_CLUSTER_RECEIPT_SCHEMA_ID:
            raise PoseBustersTargetClusterBindingError(
                "unsupported target-cluster receipt schema"
            )
        for name in (
            "archive_intake_receipt_sha256",
            "corpus_audit_receipt_sha256",
            "preparation_receipt_sha256",
            "configuration_sha256",
            "implementation_source_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if self.configuration_sha256 != (
            POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION_SHA256
        ) or self.configuration_sha256 != _canonical_sha256(
            POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster configuration identity changed"
            )
        source_members = tuple(
            (
                _token(role, name="target-cluster source role"),
                _digest(digest, name="target-cluster implementation source"),
            )
            for role, digest in self.implementation_source_members
        )
        if (
            not source_members
            or tuple(sorted(source_members)) != source_members
            or len({role for role, _digest_value in source_members})
            != len(source_members)
            or self.implementation_source_sha256
            != _canonical_sha256(dict(source_members))
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster implementation-source identity is invalid"
            )
        inputs = tuple(self.evaluation_inputs)
        if tuple(row.engine_id for row in inputs) != (
            POSEBUSTERS_TARGET_CLUSTER_ENGINES
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster evaluation inputs must cover three engines"
            )
        cases = tuple(self.case_rows)
        if (
            not cases
            or tuple(row.case_id for row in cases)
            != tuple(sorted(row.case_id for row in cases))
            or len({row.case_id for row in cases}) != len(cases)
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster cases must be unique and ordered"
            )
        case_by_id = {row.case_id: row for row in cases}
        families = tuple(self.family_rows)
        if (
            not families
            or tuple(row.family_id for row in families)
            != tuple(sorted(row.family_id for row in families))
            or len({row.family_id for row in families}) != len(families)
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster families must be unique and ordered"
            )
        projected_members = tuple(
            sorted(
                case_id
                for family in families
                for case_id in family.member_case_ids
            )
        )
        if projected_members != tuple(row.case_id for row in cases) or any(
            case_by_id[case_id].family_id != family.family_id
            for family in families
            for case_id in family.member_case_ids
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster families do not partition the cases"
            )
        links = tuple(self.cluster_links)
        if tuple(
            (
                row.left_case_id,
                row.right_case_id,
                row.left_chain_ordinal,
                row.right_chain_ordinal,
            )
            for row in links
        ) != tuple(
            sorted(
                (
                    row.left_case_id,
                    row.right_case_id,
                    row.left_chain_ordinal,
                    row.right_chain_ordinal,
                )
                for row in links
            )
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster links must be canonically ordered"
            )
        for link in links:
            if (
                link.left_case_id not in case_by_id
                or link.right_case_id not in case_by_id
                or case_by_id[link.left_case_id].family_id
                != case_by_id[link.right_case_id].family_id
            ):
                raise PoseBustersTargetClusterBindingError(
                    "target-cluster link endpoints are missing or cross-wired"
                )
            left_chains = case_by_id[link.left_case_id].chains
            right_chains = case_by_id[link.right_case_id].chains
            if (
                link.left_chain_ordinal >= len(left_chains)
                or link.right_chain_ordinal >= len(right_chains)
                or not left_chains[link.left_chain_ordinal].comparison_eligible
                or not right_chains[
                    link.right_chain_ordinal
                ].comparison_eligible
                or link.maximum_chain_length
                != max(
                    left_chains[link.left_chain_ordinal].residue_count,
                    right_chains[link.right_chain_ordinal].residue_count,
                )
            ):
                raise PoseBustersTargetClusterBindingError(
                    "target-cluster link chain projection is invalid"
                )
        adjacency: dict[str, set[str]] = {
            row.case_id: set() for row in cases
        }
        for link in links:
            adjacency[link.left_case_id].add(link.right_case_id)
            adjacency[link.right_case_id].add(link.left_case_id)
        for family in families:
            visited = {family.member_case_ids[0]}
            frontier = [family.member_case_ids[0]]
            while frontier:
                current = frontier.pop()
                for neighbor in adjacency[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        frontier.append(neighbor)
            if visited != set(family.member_case_ids):
                raise PoseBustersTargetClusterBindingError(
                    "target-cluster family graph is not connected"
                )
        engine_cases = tuple(self.engine_case_rows)
        expected_engine_case_keys = tuple(
            (engine, case.case_id)
            for engine in POSEBUSTERS_TARGET_CLUSTER_ENGINES
            for case in cases
        )
        if tuple((row.engine_id, row.case_id) for row in engine_cases) != (
            expected_engine_case_keys
        ) or any(
            row.family_id != case_by_id[row.case_id].family_id
            for row in engine_cases
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster engine cases do not cover the source cases"
            )
        for evaluation_input in inputs:
            selected = tuple(
                row
                for row in engine_cases
                if row.engine_id == evaluation_input.engine_id
            )
            if (
                sum(row.execution_pose_count for row in selected)
                != evaluation_input.generated_pose_count
                or sum(row.evaluated_pose_count for row in selected)
                != evaluation_input.evaluated_pose_count
            ):
                raise PoseBustersTargetClusterBindingError(
                    "target-cluster evaluation counts do not match engine cases"
                )
        engine_families = tuple(self.engine_family_rows)
        expected_engine_families = _aggregate_engine_families(
            families,
            engine_cases,
        )
        if tuple(row.to_dict() for row in engine_families) != tuple(
            row.to_dict() for row in expected_engine_families
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster engine-family aggregation is inconsistent"
            )
        metrics = _summary_metrics(engine_families)
        if tuple(row.to_dict() for row in self.metrics) != tuple(
            row.to_dict() for row in metrics
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster metrics do not match family rows"
            )
        leakage = tuple(self.leakage_dispositions)
        if tuple(row.engine_id for row in leakage) != (
            POSEBUSTERS_TARGET_CLUSTER_ENGINES
        ):
            raise PoseBustersTargetClusterBindingError(
                "target-cluster leakage dispositions must cover three engines"
            )
        object.__setattr__(self, "implementation_source_members", source_members)
        object.__setattr__(self, "evaluation_inputs", inputs)
        object.__setattr__(self, "case_rows", cases)
        object.__setattr__(self, "cluster_links", links)
        object.__setattr__(self, "family_rows", families)
        object.__setattr__(self, "engine_case_rows", engine_cases)
        object.__setattr__(self, "engine_family_rows", engine_families)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "leakage_dispositions", leakage)

    def _payload(self) -> dict[str, Any]:
        family_sizes = [len(row.member_case_ids) for row in self.family_rows]
        return {
            "schema_id": self.schema_id,
            "archive_intake_receipt_sha256": (
                self.archive_intake_receipt_sha256
            ),
            "corpus_audit_receipt_sha256": self.corpus_audit_receipt_sha256,
            "preparation_receipt_sha256": self.preparation_receipt_sha256,
            "configuration": POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION,
            "configuration_sha256": self.configuration_sha256,
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": dict(
                self.implementation_source_members
            ),
            "evaluation_inputs": [
                row.to_dict() for row in self.evaluation_inputs
            ],
            "all_case_denominator": len(self.case_rows),
            "observed_target_cluster_count": len(self.family_rows),
            "multi_case_target_cluster_count": sum(
                size > 1 for size in family_sizes
            ),
            "maximum_target_cluster_size": max(family_sizes),
            "cluster_link_count": len(self.cluster_links),
            "case_rows": [row.to_dict() for row in self.case_rows],
            "cluster_links": [row.to_dict() for row in self.cluster_links],
            "family_rows": [row.to_dict() for row in self.family_rows],
            "engine_case_rows": [
                row.to_dict() for row in self.engine_case_rows
            ],
            "engine_family_rows": [
                row.to_dict() for row in self.engine_family_rows
            ],
            "metrics": [row.to_dict() for row in self.metrics],
            "leakage_dispositions": [
                row.to_dict() for row in self.leakage_dispositions
            ],
            "observed_target_cluster_metrics_present": True,
            "biological_target_family_annotations_present": False,
            "intra_evaluation_near_identity_control_present": True,
            "external_fit_training_leakage_audit_present": False,
            "leakage_control_passed": False,
            "scientific_blockers": list(
                POSEBUSTERS_TARGET_CLUSTER_SCIENTIFIC_BLOCKERS
            ),
            "benchmark_executed": False,
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
        source = _canonical_bytes(self.to_dict()) + b"\n"
        if len(source) > POSEBUSTERS_TARGET_CLUSTER_MAX_RECEIPT_BYTES:
            raise PoseBustersTargetClusterBindingError(
                "target-cluster receipt exceeds its byte bound"
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
                raise PoseBustersTargetClusterBindingError(
                    "target-cluster output already exists"
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
class _EvaluationCaseView:
    case_id: str
    execution_status: str
    evaluation_status: str
    execution_pose_count: int
    evaluated_pose_count: int
    physically_valid_pose_count: int
    top_1_physically_valid: bool
    top_5_physically_valid: bool
    top_1_rmsd_hit: bool
    top_5_rmsd_hit: bool
    top_1_valid_rmsd_hit: bool
    top_5_valid_rmsd_hit: bool


@dataclass(frozen=True, slots=True)
class _EvaluationReceiptView:
    engine_id: str
    archive_intake_receipt_sha256: str
    corpus_audit_receipt_sha256: str
    preparation_receipt_sha256: str
    evaluation_input: PoseBustersTargetClusterEvaluationInput
    case_rows: tuple[_EvaluationCaseView, ...]


def _load_evaluation_receipt(
    engine_id: str,
    receipt_path: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
    expected_case_ids: Sequence[str],
) -> _EvaluationReceiptView:
    engine = _engine_id(engine_id)
    expected_sha = _digest(
        expected_receipt_sha256,
        name=f"expected {engine} evaluation receipt",
    )
    source = _read_exact_regular_file(
        receipt_path,
        maximum_bytes=max(
            POSEBUSTERS_GENERATED_POSE_MAX_RECEIPT_BYTES,
            POSEBUSTERS_EXTERNAL_GENERATED_POSE_MAX_RECEIPT_BYTES,
        ),
    )
    try:
        metadata = Path(receipt_path).stat(follow_symlinks=False)
    except OSError as exc:
        raise PoseBustersTargetClusterBindingError(
            f"{engine} evaluation receipt metadata is unavailable"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersTargetClusterBindingError(
            f"{engine} evaluation receipt must remain mode 0600"
        )
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersTargetClusterBindingError(
            f"{engine} evaluation receipt is not canonical JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersTargetClusterBindingError(
            f"{engine} evaluation receipt bytes are not canonical"
        )
    receipt_sha = raw.get("receipt_sha256")
    payload = dict(raw)
    payload.pop("receipt_sha256", None)
    source_members = raw.get("implementation_source_members")
    if engine == "vina":
        expected_schema = POSEBUSTERS_GENERATED_POSE_EVALUATION_SCHEMA_ID
        expected_case_schema = POSEBUSTERS_GENERATED_POSE_CASE_SCHEMA_ID
        expected_source_role = "generated_pose_evaluation"
        expected_source_path = Path(__file__).with_name(
            "public_posebusters_generated_pose_evaluation.py"
        )
        execution_receipt_key = "vina_receipt_sha256"
        execution_status_key = "vina_status"
        execution_pose_count_key = "vina_pose_count"
    else:
        expected_schema = (
            POSEBUSTERS_EXTERNAL_GENERATED_POSE_EVALUATION_SCHEMA_ID
        )
        expected_case_schema = (
            POSEBUSTERS_EXTERNAL_GENERATED_POSE_CASE_SCHEMA_ID
        )
        expected_source_role = "external_generated_pose_evaluation"
        expected_source_path = Path(__file__).with_name(
            "public_posebusters_external_generated_pose_evaluation.py"
        )
        execution_receipt_key = "execution_receipt_sha256"
        execution_status_key = "execution_status"
        execution_pose_count_key = "execution_pose_count"
    if (
        raw.get("schema_id") != expected_schema
        or (engine != "vina" and raw.get("engine_id") != engine)
        or not isinstance(receipt_sha, str)
        or _canonical_sha256(payload) != receipt_sha
        or receipt_sha != expected_sha
        or raw.get("all_case_denominator") != len(expected_case_ids)
        or raw.get("benchmark_executed") is not False
        or raw.get("scientifically_validated") is not False
        or (engine == "vina" and raw.get("claim_safe") is not False)
        or raw.get("target_family_metrics_present") is not False
        or raw.get("leakage_receipt_present") is not False
        or not isinstance(source_members, dict)
        or source_members.get(expected_source_role)
        != _source_file_sha256(expected_source_path)
        or _canonical_sha256(source_members)
        != raw.get("implementation_source_sha256")
    ):
        raise PoseBustersTargetClusterBindingError(
            f"{engine} evaluation receipt contract or source identity is invalid"
        )
    archive_intake_sha = _digest(
        raw.get("archive_intake_receipt_sha256"),
        name=f"{engine} archive-intake receipt",
    )
    corpus_sha = _digest(
        raw.get("corpus_audit_receipt_sha256"),
        name=f"{engine} corpus-audit receipt",
    )
    preparation_sha = _digest(
        raw.get("preparation_receipt_sha256"),
        name=f"{engine} preparation receipt",
    )
    execution_sha = _digest(
        raw.get(execution_receipt_key),
        name=f"{engine} execution receipt",
    )
    raw_rows = raw.get("case_rows")
    if not isinstance(raw_rows, list) or len(raw_rows) != len(
        expected_case_ids
    ):
        raise PoseBustersTargetClusterBindingError(
            f"{engine} evaluation receipt case denominator is inconsistent"
        )
    rows: list[_EvaluationCaseView] = []
    for raw_row in raw_rows:
        if (
            not isinstance(raw_row, dict)
            or raw_row.get("schema_id") != expected_case_schema
            or (engine != "vina" and raw_row.get("engine_id") != engine)
        ):
            raise PoseBustersTargetClusterBindingError(
                f"{engine} evaluation case schema is invalid"
            )
        case = _case_id(raw_row.get("case_id"))
        execution_status = str(raw_row.get(execution_status_key, ""))
        evaluation_status = str(raw_row.get("status", ""))
        if (
            execution_status not in _EXECUTION_STATUSES
            or evaluation_status not in _EVALUATION_STATUSES
        ):
            raise PoseBustersTargetClusterBindingError(
                f"{engine} evaluation case status is invalid"
            )
        execution_poses = _nonnegative_int(
            raw_row.get(execution_pose_count_key),
            name=f"{engine} execution-pose count",
        )
        evaluated_poses = _nonnegative_int(
            raw_row.get("evaluated_pose_count"),
            name=f"{engine} evaluated-pose count",
        )
        valid_poses = _nonnegative_int(
            raw_row.get("physically_valid_pose_count"),
            name=f"{engine} physically-valid-pose count",
        )
        flags = tuple(
            _boolean(raw_row.get(source_name), name=f"{engine} {source_name}")
            for source_name in (
                "top_1_valid",
                "top_5_valid",
                "top_1_rmsd_within_2_angstrom",
                "top_5_rmsd_within_2_angstrom",
                "top_1_valid_and_rmsd_within_2_angstrom",
                "top_5_valid_and_rmsd_within_2_angstrom",
            )
        )
        row = PoseBustersTargetClusterEngineCase(
            engine_id=engine,
            case_id=case,
            family_id="pending_target_cluster_family",
            execution_status=execution_status,
            evaluation_status=evaluation_status,
            execution_pose_count=execution_poses,
            evaluated_pose_count=evaluated_poses,
            physically_valid_pose_count=valid_poses,
            top_1_physically_valid=flags[0],
            top_5_physically_valid=flags[1],
            top_1_rmsd_hit=flags[2],
            top_5_rmsd_hit=flags[3],
            top_1_valid_rmsd_hit=flags[4],
            top_5_valid_rmsd_hit=flags[5],
        )
        rows.append(
            _EvaluationCaseView(
                case_id=row.case_id,
                execution_status=row.execution_status,
                evaluation_status=row.evaluation_status,
                execution_pose_count=row.execution_pose_count,
                evaluated_pose_count=row.evaluated_pose_count,
                physically_valid_pose_count=row.physically_valid_pose_count,
                top_1_physically_valid=row.top_1_physically_valid,
                top_5_physically_valid=row.top_5_physically_valid,
                top_1_rmsd_hit=row.top_1_rmsd_hit,
                top_5_rmsd_hit=row.top_5_rmsd_hit,
                top_1_valid_rmsd_hit=row.top_1_valid_rmsd_hit,
                top_5_valid_rmsd_hit=row.top_5_valid_rmsd_hit,
            )
        )
    rows_tuple = tuple(rows)
    generated = _positive_int(
        raw.get("generated_pose_count"),
        name=f"{engine} generated-pose count",
    )
    evaluated = _positive_int(
        raw.get("evaluated_pose_count"),
        name=f"{engine} evaluated-pose count",
    )
    if (
        tuple(row.case_id for row in rows_tuple) != tuple(expected_case_ids)
        or len({row.case_id for row in rows_tuple}) != len(rows_tuple)
        or generated != sum(row.execution_pose_count for row in rows_tuple)
        or evaluated != sum(row.evaluated_pose_count for row in rows_tuple)
    ):
        raise PoseBustersTargetClusterBindingError(
            f"{engine} evaluation row order or counts are inconsistent"
        )
    return _EvaluationReceiptView(
        engine_id=engine,
        archive_intake_receipt_sha256=archive_intake_sha,
        corpus_audit_receipt_sha256=corpus_sha,
        preparation_receipt_sha256=preparation_sha,
        evaluation_input=PoseBustersTargetClusterEvaluationInput(
            engine_id=engine,
            evaluation_receipt_sha256=receipt_sha,
            evaluation_receipt_file_sha256=_hash_bytes(source),
            execution_receipt_sha256=execution_sha,
            generated_pose_count=generated,
            evaluated_pose_count=evaluated,
        ),
        case_rows=rows_tuple,
    )


@dataclass(frozen=True, slots=True)
class _ObservedCasePayload:
    case_id: str
    pdb_id: str
    receptor_sha256: str
    chains: tuple[PoseBustersObservedTargetChain, ...]
    residue_label_sequences: tuple[tuple[str, ...], ...]


def _parse_observed_target_chains(
    case_id: str,
    receptor_pdb: bytes,
) -> tuple[
    tuple[PoseBustersObservedTargetChain, ...],
    tuple[tuple[str, ...], ...],
]:
    case = _case_id(case_id)
    try:
        lines = receptor_pdb.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise PoseBustersTargetClusterBindingError(
            f"{case} receptor PDB is not ASCII"
        ) from exc
    chain_order: list[str] = []
    chain_residues: dict[str, list[str]] = {}
    observed_residues: dict[tuple[str, str, str], str] = {}
    model_records_present = any(line[:6] == "MODEL " for line in lines)
    first_model_seen = False
    active_model = not model_records_present
    for line in lines:
        record = line[:6]
        if record == "MODEL ":
            if first_model_seen:
                break
            else:
                first_model_seen = True
                active_model = True
            continue
        if record == "ENDMDL" and active_model:
            break
        if not active_model or record != "ATOM  ":
            continue
        if len(line) < 27:
            raise PoseBustersTargetClusterBindingError(
                f"{case} receptor contains a short ATOM row"
            )
        residue_label = line[17:20].strip().upper()
        chain_id = line[21]
        residue_key = (chain_id, line[22:26], line[26])
        if not residue_label:
            raise PoseBustersTargetClusterBindingError(
                f"{case} receptor contains an empty residue label"
            )
        previous = observed_residues.get(residue_key)
        if previous is not None:
            if previous != residue_label:
                raise PoseBustersTargetClusterBindingError(
                    f"{case} receptor residue identity changes within one key"
                )
            continue
        observed_residues[residue_key] = residue_label
        if chain_id not in chain_residues:
            if len(chain_order) >= POSEBUSTERS_TARGET_CLUSTER_MAX_CHAINS_PER_CASE:
                raise PoseBustersTargetClusterBindingError(
                    f"{case} receptor exceeds the chain bound"
                )
            chain_order.append(chain_id)
            chain_residues[chain_id] = []
        chain_residues[chain_id].append(residue_label)
    sequences = tuple(tuple(chain_residues[chain]) for chain in chain_order)
    if not sequences:
        raise PoseBustersTargetClusterBindingError(
            f"{case} receptor contains no observed ATOM residue sequence"
        )
    chains = tuple(
        PoseBustersObservedTargetChain(
            chain_ordinal=ordinal,
            chain_id=chain_id,
            residue_count=len(sequence),
            residue_label_sequence_sha256=_canonical_sha256(list(sequence)),
            comparison_eligible=(
                len(sequence)
                >= POSEBUSTERS_TARGET_CLUSTER_MINIMUM_CHAIN_RESIDUES
            ),
        )
        for ordinal, (chain_id, sequence) in enumerate(
            zip(chain_order, sequences)
        )
    )
    if not any(row.comparison_eligible for row in chains):
        raise PoseBustersTargetClusterBindingError(
            f"{case} receptor has no comparison-eligible protein chain"
        )
    return chains, sequences


def _global_edit_distance(
    left: Sequence[str],
    right: Sequence[str],
) -> int:
    """Return unit-cost Levenshtein distance using Myers bit vectors."""

    first = tuple(left)
    second = tuple(right)
    if not first:
        return len(second)
    if not second:
        return len(first)
    if len(first) > len(second):
        first, second = second, first
    width = len(first)
    mask = (1 << width) - 1
    last = 1 << (width - 1)
    equality: dict[str, int] = {}
    for index, value in enumerate(first):
        equality[value] = equality.get(value, 0) | (1 << index)
    positive = mask
    negative = 0
    score = width
    for value in second:
        equal = equality.get(value, 0)
        combined = equal | negative
        horizontal = (((equal & positive) + positive) ^ positive) | equal
        positive_horizontal = negative | ~(horizontal | positive)
        negative_horizontal = positive & horizontal
        if positive_horizontal & last:
            score += 1
        elif negative_horizontal & last:
            score -= 1
        positive_horizontal = ((positive_horizontal << 1) | 1) & mask
        negative_horizontal = (negative_horizontal << 1) & mask
        positive = (
            negative_horizontal | ~(combined | positive_horizontal)
        ) & mask
        negative = positive_horizontal & combined
    return score


def _candidate_link_is_better(
    candidate: tuple[int, int, int, int],
    incumbent: tuple[int, int, int, int],
) -> bool:
    candidate_distance, candidate_maximum, candidate_left, candidate_right = (
        candidate
    )
    incumbent_distance, incumbent_maximum, incumbent_left, incumbent_right = (
        incumbent
    )
    candidate_scaled = candidate_distance * incumbent_maximum
    incumbent_scaled = incumbent_distance * candidate_maximum
    if candidate_scaled != incumbent_scaled:
        return candidate_scaled < incumbent_scaled
    return (
        candidate_distance,
        candidate_left,
        candidate_right,
    ) < (
        incumbent_distance,
        incumbent_left,
        incumbent_right,
    )


def _cluster_observed_cases(
    observed_cases: Sequence[_ObservedCasePayload],
) -> tuple[
    tuple[PoseBustersTargetClusterCase, ...],
    tuple[PoseBustersTargetClusterLink, ...],
    tuple[PoseBustersTargetClusterFamily, ...],
]:
    observed = tuple(observed_cases)
    case_ids = tuple(row.case_id for row in observed)
    if (
        not observed
        or len(observed) > POSEBUSTERS_TARGET_CLUSTER_MAX_CASES
        or case_ids != tuple(sorted(case_ids))
        or len(set(case_ids)) != len(case_ids)
    ):
        raise PoseBustersTargetClusterBindingError(
            "observed target cases must be bounded, unique, and ordered"
        )
    parent = {case_id: case_id for case_id in case_ids}

    def find(case_id: str) -> str:
        root = case_id
        while parent[root] != root:
            root = parent[root]
        while parent[case_id] != case_id:
            next_case = parent[case_id]
            parent[case_id] = root
            case_id = next_case
        return root

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        first, second = sorted((left_root, right_root))
        parent[second] = first

    links: list[PoseBustersTargetClusterLink] = []
    threshold_difference = (
        POSEBUSTERS_TARGET_CLUSTER_SIMILARITY_DENOMINATOR
        - POSEBUSTERS_TARGET_CLUSTER_SIMILARITY_NUMERATOR
    )
    for left_index, left in enumerate(observed):
        for right in observed[left_index + 1 :]:
            best: tuple[int, int, int, int] | None = None
            for left_ordinal, (left_chain, left_sequence) in enumerate(
                zip(left.chains, left.residue_label_sequences)
            ):
                if not left_chain.comparison_eligible:
                    continue
                for right_ordinal, (right_chain, right_sequence) in enumerate(
                    zip(right.chains, right.residue_label_sequences)
                ):
                    if not right_chain.comparison_eligible:
                        continue
                    maximum = max(len(left_sequence), len(right_sequence))
                    minimum_distance = abs(
                        len(left_sequence) - len(right_sequence)
                    )
                    if (
                        minimum_distance
                        * POSEBUSTERS_TARGET_CLUSTER_SIMILARITY_DENOMINATOR
                        > maximum * threshold_difference
                    ):
                        continue
                    distance = _global_edit_distance(
                        left_sequence,
                        right_sequence,
                    )
                    if (
                        distance
                        * POSEBUSTERS_TARGET_CLUSTER_SIMILARITY_DENOMINATOR
                        > maximum * threshold_difference
                    ):
                        continue
                    candidate = (
                        distance,
                        maximum,
                        left_ordinal,
                        right_ordinal,
                    )
                    if best is None or _candidate_link_is_better(
                        candidate,
                        best,
                    ):
                        best = candidate
            if best is None:
                continue
            distance, maximum, left_ordinal, right_ordinal = best
            links.append(
                PoseBustersTargetClusterLink(
                    left_case_id=left.case_id,
                    right_case_id=right.case_id,
                    left_chain_ordinal=left_ordinal,
                    right_chain_ordinal=right_ordinal,
                    edit_distance=distance,
                    maximum_chain_length=maximum,
                )
            )
            union(left.case_id, right.case_id)

    components: dict[str, list[str]] = {}
    for case_id in case_ids:
        components.setdefault(find(case_id), []).append(case_id)
    families = tuple(
        sorted(
            (
                PoseBustersTargetClusterFamily(
                    family_id=_family_id(tuple(sorted(members))),
                    member_case_ids=tuple(sorted(members)),
                )
                for members in components.values()
            ),
            key=lambda row: row.family_id,
        )
    )
    family_by_case = {
        case_id: family.family_id
        for family in families
        for case_id in family.member_case_ids
    }
    cases = tuple(
        PoseBustersTargetClusterCase(
            case_id=row.case_id,
            pdb_id=row.pdb_id,
            receptor_sha256=row.receptor_sha256,
            target_sequence_set_sha256=_canonical_sha256(
                [chain.to_dict() for chain in row.chains]
            ),
            family_id=family_by_case[row.case_id],
            chains=row.chains,
        )
        for row in observed
    )
    return cases, tuple(links), families


def _read_receptor_pdb(
    archive: zipfile.ZipFile,
    intake_row: Any,
) -> tuple[bytes, str]:
    if intake_row.status != "ready":
        raise PoseBustersTargetClusterBindingError(
            "target-cluster construction requires every intake case"
        )
    artifacts = {row.role: row for row in intake_row.artifacts}
    artifact = artifacts.get("receptor_pdb")
    if artifact is None:
        raise PoseBustersTargetClusterBindingError(
            "target-cluster receptor artifact is missing"
        )
    try:
        info = archive.getinfo(artifact.member_path)
        if info.is_dir() or info.file_size != artifact.size_bytes:
            raise PoseBustersTargetClusterBindingError(
                "target-cluster receptor member size changed"
            )
        source = archive.read(info)
    except PoseBustersTargetClusterBindingError:
        raise
    except (KeyError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise PoseBustersTargetClusterBindingError(
            "target-cluster receptor member could not be read"
        ) from exc
    if len(source) != artifact.size_bytes or _hash_bytes(source) != artifact.sha256:
        raise PoseBustersTargetClusterBindingError(
            "target-cluster receptor changed after intake verification"
        )
    return source, artifact.sha256


def _implementation_source_members() -> tuple[tuple[str, str], ...]:
    module_root = Path(__file__).parent
    return tuple(
        sorted(
            {
                "corpus_audit_utilities": _source_file_sha256(
                    module_root / "public_posebusters_corpus_audit.py"
                ),
                "external_generated_pose_evaluation": _source_file_sha256(
                    module_root
                    / "public_posebusters_external_generated_pose_evaluation.py"
                ),
                "posebusters_archive_intake": _source_file_sha256(
                    module_root / "public_posebusters_intake.py"
                ),
                "target_cluster_binding": _source_file_sha256(__file__),
                "vina_generated_pose_evaluation": _source_file_sha256(
                    module_root
                    / "public_posebusters_generated_pose_evaluation.py"
                ),
            }.items()
        )
    )


def _build_target_cluster_receipt(
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    vina_evaluation_receipt_path: str | os.PathLike[str],
    gnina_evaluation_receipt_path: str | os.PathLike[str],
    smina_evaluation_receipt_path: str | os.PathLike[str],
    *,
    expected_vina_evaluation_receipt_sha256: str,
    expected_gnina_evaluation_receipt_sha256: str,
    expected_smina_evaluation_receipt_sha256: str,
    contract: PoseBustersArchiveContract,
) -> PoseBustersTargetClusterReceipt:
    if _canonical_sha256(POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION) != (
        POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION_SHA256
    ):
        raise PoseBustersTargetClusterBindingError(
            "target-cluster frozen configuration was mutated"
        )
    try:
        intake = verify_posebusters_archive_intake_receipt(
            intake_receipt_path,
            archive_path,
            selection_path,
            contract=contract,
        )
    except PoseBustersArchiveIntakeError as exc:
        raise PoseBustersTargetClusterBindingError(
            "target-cluster archive intake did not verify"
        ) from exc
    if (
        intake.global_error_codes
        or any(row.status != "ready" for row in intake.case_rows)
        or not intake.case_rows
        or len(intake.case_rows) > POSEBUSTERS_TARGET_CLUSTER_MAX_CASES
    ):
        raise PoseBustersTargetClusterBindingError(
            "target-cluster construction requires a bounded all-ready intake"
        )
    expected_case_ids = tuple(row.case_id for row in intake.case_rows)
    evaluation_specs = (
        (
            "vina",
            vina_evaluation_receipt_path,
            expected_vina_evaluation_receipt_sha256,
        ),
        (
            "gnina",
            gnina_evaluation_receipt_path,
            expected_gnina_evaluation_receipt_sha256,
        ),
        (
            "smina",
            smina_evaluation_receipt_path,
            expected_smina_evaluation_receipt_sha256,
        ),
    )
    try:
        evaluations = tuple(
            _load_evaluation_receipt(
                engine,
                receipt_path,
                expected_receipt_sha256=expected_sha,
                expected_case_ids=expected_case_ids,
            )
            for engine, receipt_path, expected_sha in evaluation_specs
        )
    except PoseBustersArchiveIntakeError as exc:
        raise PoseBustersTargetClusterBindingError(
            "target-cluster evaluation receipt could not be read securely"
        ) from exc
    if any(
        row.archive_intake_receipt_sha256 != intake.fingerprint_sha256
        for row in evaluations
    ):
        raise PoseBustersTargetClusterBindingError(
            "target-cluster evaluation inputs cross-wire archive intake"
        )
    corpus_receipts = {
        row.corpus_audit_receipt_sha256 for row in evaluations
    }
    preparation_receipts = {
        row.preparation_receipt_sha256 for row in evaluations
    }
    if len(corpus_receipts) != 1 or len(preparation_receipts) != 1:
        raise PoseBustersTargetClusterBindingError(
            "target-cluster evaluation inputs do not share one source chain"
        )

    observed: list[_ObservedCasePayload] = []
    try:
        descriptor, size = _regular_file_descriptor(
            archive_path,
            maximum_bytes=contract.archive_size_bytes,
        )
        try:
            if (
                size != contract.archive_size_bytes
                or _hash_descriptor(descriptor, size) != contract.archive_sha256
            ):
                raise PoseBustersTargetClusterBindingError(
                    "target-cluster archive changed after intake verification"
                )
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                with zipfile.ZipFile(handle, "r") as archive:
                    for intake_row in intake.case_rows:
                        receptor, receptor_sha256 = _read_receptor_pdb(
                            archive,
                            intake_row,
                        )
                        chains, sequences = _parse_observed_target_chains(
                            intake_row.case_id,
                            receptor,
                        )
                        observed.append(
                            _ObservedCasePayload(
                                case_id=intake_row.case_id,
                                pdb_id=intake_row.case_id.split("_", 1)[0],
                                receptor_sha256=receptor_sha256,
                                chains=chains,
                                residue_label_sequences=sequences,
                            )
                        )
        finally:
            os.close(descriptor)
    except PoseBustersTargetClusterBindingError:
        raise
    except (PoseBustersArchiveIntakeError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise PoseBustersTargetClusterBindingError(
            "target-cluster archive failed bounded receptor access"
        ) from exc

    cases, links, families = _cluster_observed_cases(observed)
    family_by_case = {row.case_id: row.family_id for row in cases}
    engine_cases = tuple(
        PoseBustersTargetClusterEngineCase(
            engine_id=evaluation.engine_id,
            case_id=row.case_id,
            family_id=family_by_case[row.case_id],
            execution_status=row.execution_status,
            evaluation_status=row.evaluation_status,
            execution_pose_count=row.execution_pose_count,
            evaluated_pose_count=row.evaluated_pose_count,
            physically_valid_pose_count=row.physically_valid_pose_count,
            top_1_physically_valid=row.top_1_physically_valid,
            top_5_physically_valid=row.top_5_physically_valid,
            top_1_rmsd_hit=row.top_1_rmsd_hit,
            top_5_rmsd_hit=row.top_5_rmsd_hit,
            top_1_valid_rmsd_hit=row.top_1_valid_rmsd_hit,
            top_5_valid_rmsd_hit=row.top_5_valid_rmsd_hit,
        )
        for evaluation in evaluations
        for row in evaluation.case_rows
    )
    engine_families = _aggregate_engine_families(families, engine_cases)
    source_members = _implementation_source_members()
    leakage = tuple(
        PoseBustersExternalTrainingLeakageDisposition(engine_id=engine)
        for engine in POSEBUSTERS_TARGET_CLUSTER_ENGINES
    )
    return PoseBustersTargetClusterReceipt(
        archive_intake_receipt_sha256=intake.fingerprint_sha256,
        corpus_audit_receipt_sha256=next(iter(corpus_receipts)),
        preparation_receipt_sha256=next(iter(preparation_receipts)),
        configuration_sha256=POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION_SHA256,
        implementation_source_sha256=_canonical_sha256(dict(source_members)),
        implementation_source_members=source_members,
        evaluation_inputs=tuple(
            row.evaluation_input for row in evaluations
        ),
        case_rows=cases,
        cluster_links=links,
        family_rows=families,
        engine_case_rows=engine_cases,
        engine_family_rows=engine_families,
        metrics=_summary_metrics(engine_families),
        leakage_dispositions=leakage,
    )


def materialize_posebusters_target_cluster_binding(
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    vina_evaluation_receipt_path: str | os.PathLike[str],
    gnina_evaluation_receipt_path: str | os.PathLike[str],
    smina_evaluation_receipt_path: str | os.PathLike[str],
    *,
    expected_vina_evaluation_receipt_sha256: str,
    expected_gnina_evaluation_receipt_sha256: str,
    expected_smina_evaluation_receipt_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersTargetClusterReceipt:
    """Build conservative target-cluster metrics from three frozen receipts."""

    return _build_target_cluster_receipt(
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


def verify_posebusters_target_cluster_binding_receipt(
    target_cluster_receipt_path: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    selection_path: str | os.PathLike[str],
    intake_receipt_path: str | os.PathLike[str],
    vina_evaluation_receipt_path: str | os.PathLike[str],
    gnina_evaluation_receipt_path: str | os.PathLike[str],
    smina_evaluation_receipt_path: str | os.PathLike[str],
    *,
    expected_vina_evaluation_receipt_sha256: str,
    expected_gnina_evaluation_receipt_sha256: str,
    expected_smina_evaluation_receipt_sha256: str,
    contract: PoseBustersArchiveContract = OFFICIAL_POSEBUSTERS_ARCHIVE_CONTRACT,
) -> PoseBustersTargetClusterReceipt:
    """Require byte-exact target-cluster reconstruction and receipt equality."""

    try:
        source = _read_exact_regular_file(
            target_cluster_receipt_path,
            maximum_bytes=POSEBUSTERS_TARGET_CLUSTER_MAX_RECEIPT_BYTES,
        )
        metadata = Path(target_cluster_receipt_path).stat(
            follow_symlinks=False
        )
    except (PoseBustersArchiveIntakeError, OSError) as exc:
        raise PoseBustersTargetClusterBindingError(
            "target-cluster receipt could not be read securely"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersTargetClusterBindingError(
            "target-cluster receipt must remain mode 0600"
        )
    expected = _build_target_cluster_receipt(
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
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersTargetClusterBindingError(
            "target-cluster receipt does not match exact reexecution"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-target-clusters",
        description=(
            "Bind frozen Vina, GNINA, and Smina results to conservative "
            "observed-target clusters."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--archive", required=True)
        subparser.add_argument("--selection", required=True)
        subparser.add_argument("--intake-receipt", required=True)
        for engine in POSEBUSTERS_TARGET_CLUSTER_ENGINES:
            subparser.add_argument(
                f"--{engine}-evaluation-receipt",
                required=True,
            )
            subparser.add_argument(
                f"--expected-{engine}-evaluation-receipt-sha256",
                required=True,
            )
    subparsers.choices["materialize"].add_argument("--output", required=True)
    subparsers.choices["verify"].add_argument(
        "--target-cluster-receipt",
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {
        "archive_path": args.archive,
        "selection_path": args.selection,
        "intake_receipt_path": args.intake_receipt,
        "vina_evaluation_receipt_path": args.vina_evaluation_receipt,
        "gnina_evaluation_receipt_path": args.gnina_evaluation_receipt,
        "smina_evaluation_receipt_path": args.smina_evaluation_receipt,
        "expected_vina_evaluation_receipt_sha256": (
            args.expected_vina_evaluation_receipt_sha256
        ),
        "expected_gnina_evaluation_receipt_sha256": (
            args.expected_gnina_evaluation_receipt_sha256
        ),
        "expected_smina_evaluation_receipt_sha256": (
            args.expected_smina_evaluation_receipt_sha256
        ),
    }
    if args.command == "materialize":
        if Path(args.output).exists():
            raise PoseBustersTargetClusterBindingError(
                "target-cluster output already exists"
            )
        receipt = materialize_posebusters_target_cluster_binding(**common)
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_target_cluster_binding_receipt(
            target_cluster_receipt_path=args.target_cluster_receipt,
            **common,
        )
    family_sizes = tuple(
        len(row.member_case_ids) for row in receipt.family_rows
    )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "observed_target_cluster_count": len(receipt.family_rows),
                "multi_case_target_cluster_count": sum(
                    size > 1 for size in family_sizes
                ),
                "maximum_target_cluster_size": max(family_sizes),
                "cluster_link_count": len(receipt.cluster_links),
                "leakage_control_passed": False,
                "benchmark_executed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION",
    "POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION_SHA256",
    "POSEBUSTERS_TARGET_CLUSTER_ENGINES",
    "POSEBUSTERS_TARGET_CLUSTER_RECEIPT_SCHEMA_ID",
    "POSEBUSTERS_TARGET_CLUSTER_SCIENTIFIC_BLOCKERS",
    "PoseBustersExternalTrainingLeakageDisposition",
    "PoseBustersObservedTargetChain",
    "PoseBustersTargetClusterBindingError",
    "PoseBustersTargetClusterCase",
    "PoseBustersTargetClusterEngineCase",
    "PoseBustersTargetClusterEngineFamily",
    "PoseBustersTargetClusterEvaluationInput",
    "PoseBustersTargetClusterFamily",
    "PoseBustersTargetClusterLink",
    "PoseBustersTargetClusterMetric",
    "PoseBustersTargetClusterReceipt",
    "main",
    "materialize_posebusters_target_cluster_binding",
    "verify_posebusters_target_cluster_binding_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
