"""Frozen, benchmark-only Docking Search v2 development-cohort protocol.

The module consumes already-computed RMSD and PoseBusters facts.  It never
opens molecular structures, invokes PoseBusters, allocates search work from an
observed result, or authorizes product dispatch.  Complete external-fact and
native-search sidecars are required: their canonical seals, exact schemas,
subjects, values, ranks, evaluator identity, and all 22 PoseBusters checks are
independently rederived before any development metric is accepted.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping, Sequence


PROTOCOL_SCHEMA_ID = "betelgeuze.docking_search_v2_development_protocol/1.2.0"
ALLOCATION_SCHEMA_ID = "betelgeuze.docking_search_v2_fixed_allocation/1.2.0"
RESULT_SCHEMA_ID = "betelgeuze.docking_search_v2_development_result/1.2.0"
EVIDENCE_SCHEMA_ID = "betelgeuze.docking_search_v2_development_evidence/1.2.0"

SOURCE_ARCHIVE_SHA256 = (
    "495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c"
)
ROSTER_SHA256 = "cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1"
EXTERNAL_POSEBUSTERS_FACT_ORIGIN = "externally_supplied_posebusters_0.3.1_redock_fact"
EXTERNAL_RMSD_FACT_ORIGIN = (
    "externally_supplied_posebusters_0.3.1_symmetry_aware_redock_rmsd_fact"
)
FIXED_ALLOCATION_POLICY_ID = "case_major_fixed_8x64_before_results/1.2.0"
GENERATION_POLICY_ID = (
    "betelgeuze_halton_so3_surface_multi_anchor_force_refinement_fixed64/1.0.0"
)
KNOWN_POCKET_POLICY_ID = (
    "authenticated_reference_heavy_atom_centroid_predeclared_before_search/1.0.0"
)
SEARCH_CRATE_ID = "betelgeuze-docking-search/0.1.0"
NATIVE_EXTENSION_VERSION = "0.2.0rc6"
PREPARATION_FAILURE_CASE_ID = "6M73_FNR"
PREPARATION_FAILURE_CODE = "unsupported_large_ring_system"
PRESERVED_RECOVERY_CASE_ID = "6T88_MWQ"
CANDIDATE_SLOTS_PER_SCORED_CASE = 64
RECOVERY_RMSD_ANGSTROM = 2.0

SEARCH_BINDING_SCHEMA_ID = "betelgeuze.docking_search_v2_search_binding/1.1.0"
RANK_RECEIPT_SCHEMA_ID = "betelgeuze.docking_search_v2_score_rank_receipt/1.1.0"
RANK_POLICY_ID = "native_final_rank_then_energy_detailed_coarse_slot/1.0.0"
RMSD_FACT_SCHEMA_ID = "betelgeuze.docking_search_v2_external_rmsd_fact/1.1.0"
POSEBUSTERS_FACT_SCHEMA_ID = (
    "betelgeuze.docking_search_v2_external_posebusters_fact/1.1.0"
)
EVALUATION_BATCH_SCHEMA_ID = (
    "betelgeuze.docking_search_v2_external_evaluation_batch/1.1.0"
)
EVALUATION_SIDECAR_SCHEMA_ID = (
    "betelgeuze.docking_search_v2_external_evaluation_sidecar/1.0.0"
)
POSEBUSTERS_VERSION = "0.3.1"
POSEBUSTERS_EVALUATOR_ID = "posebusters/0.3.1/redock/full_report"
POSEBUSTERS_RMSD_METHOD_ID = "posebusters_symmetry_aware_rmsd/0.3.1"
FROZEN_POSEBUSTERS_EVALUATOR_SOURCE_SHA256 = (
    "045267dcdbf27cf18a29dee55a95d3cf123b14e857b10c7cb9971b47a8955169"
)
POSEBUSTERS_CHEMICAL_CHECK_IDS = (
    "sanitization",
    "inchi_convertible",
    "all_atoms_connected",
    "molecular_formula",
    "molecular_bonds",
    "double_bond_stereochemistry",
    "tetrahedral_chirality",
    "bond_lengths",
    "bond_angles",
    "internal_steric_clash",
    "aromatic_ring_flatness",
    "double_bond_flatness",
    "internal_energy",
)
POSEBUSTERS_GEOMETRIC_CHECK_IDS = (
    "protein-ligand_maximum_distance",
    "minimum_distance_to_protein",
    "minimum_distance_to_organic_cofactors",
    "minimum_distance_to_inorganic_cofactors",
    "minimum_distance_to_waters",
    "volume_overlap_with_protein",
    "volume_overlap_with_organic_cofactors",
    "volume_overlap_with_inorganic_cofactors",
    "volume_overlap_with_waters",
)
POSEBUSTERS_CHECK_IDS = (
    *POSEBUSTERS_CHEMICAL_CHECK_IDS,
    *POSEBUSTERS_GEOMETRIC_CHECK_IDS,
)

NATIVE_BACKEND_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2.docking_search_native_receipt/2.0.0"
)
NATIVE_BACKEND_VERSION = "0.2.0-rc.6"
NATIVE_RUSTC_VERSION = "rustc 1.93.0 (254b59607 2026-01-19)"
NATIVE_TARGET_TRIPLE = "x86_64-unknown-linux-gnu"
NATIVE_BUILD_FLAGS = (
    "profile=release,codegen-units=1,debug=false,lto=fat,opt-level=3,"
    "panic=abort,strip=symbols"
)
NATIVE_CORE_SCHEMA_ID = "betelgeuze.docking_search/2.0.0"
NATIVE_CORE_RECEIPT_SCHEMA_ID = "betelgeuze.docking_search_receipt/2.0.0"
NATIVE_EVALUATOR_ID = "betelgeuze_short_range_analytic/1.0.0"
FROZEN_NATIVE_EXTENSION_SHA256 = (
    "c914ca62e3cbf9abc052462a386ad702025b2176c0dd3d726456ba1ca27eff3c"
)
FROZEN_NATIVE_SOURCE_CLOSURE_SHA256 = (
    "474f2351ac576e66f9609d22d509ca0a5faea81bbfd8955c1a89d455d6ad0be6"
)
FROZEN_NATIVE_CARGO_LOCK_SHA256 = (
    "2b8cfac4162a1571c177ece26fe8e2b3ebea25306d87ce31f3243fe4e6e925d5"
)


@dataclass(frozen=True, slots=True)
class FrozenCase:
    case_id: str
    source_receipt_sha256: str
    baseline_oracle_minimum_rmsd_angstrom: float | None
    baseline_exact_valid_candidate_count: int
    rigid_lower_bound_rmsd_angstrom: float
    preparation_failure_code: str | None = None

    @property
    def scored(self) -> bool:
        return self.preparation_failure_code is None

    @property
    def previously_recovered_at_2a(self) -> bool:
        value = self.baseline_oracle_minimum_rmsd_angstrom
        return value is not None and value <= RECOVERY_RMSD_ANGSTROM

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "source_receipt_sha256": self.source_receipt_sha256,
            "baseline_oracle_minimum_rmsd_angstrom": (
                self.baseline_oracle_minimum_rmsd_angstrom
            ),
            "baseline_exact_valid_candidate_count": (
                self.baseline_exact_valid_candidate_count
            ),
            "rigid_lower_bound_rmsd_angstrom": self.rigid_lower_bound_rmsd_angstrom,
            "rigid_lower_bound_role": "frozen_diagnostic_fact_not_gate_truth",
            "preparation_failure_code": self.preparation_failure_code,
            "scored": self.scored,
            "previously_recovered_at_or_below_2a": (self.previously_recovered_at_2a),
        }


FROZEN_CASES = (
    FrozenCase(
        "5SD5_HWI",
        "120d4d28e04604941b93b17d491682526b977971777db53bf964d1d5d2a12dfb",
        4.281296,
        0,
        1.4805,
    ),
    FrozenCase(
        "5SIS_JSM",
        "92a2bfadcf27ec61a620e387aa8e21ac87ae4e09e15c4a0c2035c4de538c2201",
        2.715571,
        0,
        1.6119,
    ),
    FrozenCase(
        "6M2B_EZO",
        "d9702520e85a459ae1e5fc4843bcd88c05dd0c3f316258971f3e61859088ec4e",
        3.048952,
        0,
        2.4242,
    ),
    FrozenCase(
        "6M73_FNR",
        "fdf1646d366a4adad31ed9ef973e53cf576d07f22aff03b0c486baaf353eb07e",
        None,
        0,
        1.9172,
        PREPARATION_FAILURE_CODE,
    ),
    FrozenCase(
        "6T88_MWQ",
        "82e4ad0942b85141a5f17b5a5c36744e40fe4ce863d4006ef29801d377bd5f06",
        1.576141,
        4,
        0.9844,
    ),
    FrozenCase(
        "6TW5_9M2",
        "076e1fa07a885cd231a557162f73c2f56912a7a6d237d3f4972b12ff59ebef9e",
        4.293041,
        0,
        2.9375,
    ),
    FrozenCase(
        "6TW7_NZB",
        "521cb3fa141424e0d7b57bfc667718b305e1cd8f02f12ac05ddffe264b76d6d1",
        3.625075,
        0,
        2.9226,
    ),
    FrozenCase(
        "6VTA_AKN",
        "79d66ad929ee3c38b4f6af120167bd9bb719fe393534d74733268197611498a2",
        4.394676,
        2,
        2.1031,
    ),
    FrozenCase(
        "6WTN_RXT",
        "35f47abe5e7ea517fa08a90a1a301d1672dba5a5e18c7cbf2211f21032b97adf",
        2.882795,
        1,
        1.9271,
    ),
)

CASE_IDS = tuple(row.case_id for row in FROZEN_CASES)
SCORED_CASE_IDS = tuple(row.case_id for row in FROZEN_CASES if row.scored)
PREVIOUSLY_UNCOVERED_CASE_IDS = tuple(
    row.case_id
    for row in FROZEN_CASES
    if row.scored and not row.previously_recovered_at_2a
)
_CASE_BY_ID = {row.case_id: row for row in FROZEN_CASES}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

FROZEN_ALLOCATION_RECEIPT_SHA256 = (
    "9c2d18c6aad0c67922d7aab0dd34e22dabcc913678f522bf65a7ca21d256aa48"
)
FROZEN_PROTOCOL_SHA256 = (
    "cc251f5922321da57fb9e97feb23de1f51eaab1e29940fe6ea5bf55642b863c5"
)

_CANDIDATE_SEARCH_STATUSES = frozenset(
    {
        "retained_top_k",
        "clustered_out",
        "physical_valid_unclustered",
        "rejected_physical",
        "pruned_detailed",
        "pruned_coarse",
        "refinement_failed",
    }
)
_FAILURE_SEARCH_STATUSES = frozenset({"rejected_physical", "refinement_failed"})
_FAILURE_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class ProtocolError(ValueError):
    """A result or evidence document violates the frozen protocol."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(f"{self.code}: {self.detail}")


def canonical_json_bytes(value: object) -> bytes:
    """Return deterministic UTF-8 JSON bytes with non-finite values forbidden."""

    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProtocolError("non_canonical_json", str(exc)) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _allocation_projection() -> dict[str, object]:
    return {
        "schema_id": ALLOCATION_SCHEMA_ID,
        "policy_id": FIXED_ALLOCATION_POLICY_ID,
        "roster_sha256": ROSTER_SHA256,
        "scored_case_ids": list(SCORED_CASE_IDS),
        "candidate_slots_per_scored_case": CANDIDATE_SLOTS_PER_SCORED_CASE,
        "slot_index_start": 0,
        "slot_index_stop_exclusive": CANDIDATE_SLOTS_PER_SCORED_CASE,
        "total_candidate_budget": (
            len(SCORED_CASE_IDS) * CANDIDATE_SLOTS_PER_SCORED_CASE
        ),
        "sealed_before_results": True,
        "result_dependent": False,
        "result_fields_used": [],
    }


def frozen_allocation_receipt() -> dict[str, object]:
    projection = _allocation_projection()
    observed = _sha256(projection)
    if observed != FROZEN_ALLOCATION_RECEIPT_SHA256:
        raise RuntimeError("frozen allocation projection changed")
    return {**projection, "allocation_receipt_sha256": observed}


def _protocol_projection() -> dict[str, object]:
    return {
        "schema_id": PROTOCOL_SCHEMA_ID,
        "protocol_id": "posebusters_nine_case_docking_search_v2_development/1.2.0",
        "scope": {
            "benchmark_only": True,
            "development_only": True,
            "retrospective": True,
            "prospective": False,
            "product_dispatch_authority": False,
            "product_promotion_eligible": False,
            "public_claim_eligible": False,
            "scientific_validation_claimed": False,
        },
        "source": {
            "dataset": "PoseBusters",
            "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
            "ordered_roster_sha256": ROSTER_SHA256,
            "molecular_structures_embedded": False,
            "archive_embedded": False,
        },
        "cohort": {
            "case_count": len(CASE_IDS),
            "ordered_case_ids": list(CASE_IDS),
            "scored_case_count": len(SCORED_CASE_IDS),
            "ordered_scored_case_ids": list(SCORED_CASE_IDS),
            "preparation_failure_case_id": PREPARATION_FAILURE_CASE_ID,
            "preparation_failure_code": PREPARATION_FAILURE_CODE,
            "previously_uncovered_case_ids": list(PREVIOUSLY_UNCOVERED_CASE_IDS),
            "previously_recovered_case_ids": [PRESERVED_RECOVERY_CASE_ID],
            "cases": [row.to_dict() for row in FROZEN_CASES],
        },
        "allocation": frozen_allocation_receipt(),
        "external_facts": {
            "posebusters_validity_origin": EXTERNAL_POSEBUSTERS_FACT_ORIGIN,
            "posebusters_validity_computed_here": False,
            "posebusters_fact_receipt_required_per_candidate": True,
            "posebusters_subject_bound_to_proposal_artifact": True,
            "symmetry_aware_rmsd_origin": EXTERNAL_RMSD_FACT_ORIGIN,
            "symmetry_aware_rmsd_externally_supplied": True,
            "symmetry_aware_rmsd_receipt_required_per_candidate": True,
            "symmetry_aware_rmsd_subject_bound_to_proposal_artifact": True,
            "complete_sealed_fact_sidecars_required": True,
            "fact_receipt_seals_recomputed_by_protocol": True,
            "posebusters_check_fact_count": len(POSEBUSTERS_CHECK_IDS),
            "posebusters_exact_valid_rederived_from_all_checks": True,
            "evaluator_implementation_source_sha256": (
                FROZEN_POSEBUSTERS_EVALUATOR_SOURCE_SHA256
            ),
        },
        "generation": {
            "policy_id": GENERATION_POLICY_ID,
            "search_crate_id": SEARCH_CRATE_ID,
            "native_extension_version": NATIVE_EXTENSION_VERSION,
            "fixed_candidate_slots_per_scored_case": (CANDIDATE_SLOTS_PER_SCORED_CASE),
            "implementation_sha256_required": True,
            "native_extension_sha256_required": True,
            "search_config_sha256_required": True,
            "case_search_receipt_sha256_required": True,
            "candidate_proposal_artifact_sha256_required": True,
            "candidate_coordinate_sha256_required": True,
            "complete_sealed_search_sidecar_required": True,
            "complete_sealed_rank_sidecar_required": True,
            "native_backend_receipt_required": True,
            "native_source_closure_sha256": FROZEN_NATIVE_SOURCE_CLOSURE_SHA256,
            "native_extension_sha256": FROZEN_NATIVE_EXTENSION_SHA256,
            "native_cargo_lock_sha256": FROZEN_NATIVE_CARGO_LOCK_SHA256,
            "result_dependent_allocation": False,
            "external_solver_used_for_generation": False,
            "full_reference_pose_used_by_search": False,
            "rmsd_used_by_search": False,
            "posebusters_used_by_search": False,
            "baseline_outcomes_used_by_search": False,
            "known_pocket_policy_id": KNOWN_POCKET_POLICY_ID,
            "known_pocket_derived_from_reference_before_search": True,
            "allowed_generation_input_roles": [
                "authenticated_protein_structure",
                "authenticated_ligand_start_conformer",
                "predeclared_known_pocket",
                "public_force_field_parameters",
            ],
        },
        "gate": {
            "rmsd_threshold_angstrom": RECOVERY_RMSD_ANGSTROM,
            "minimum_proposal_oracle_recovered_cases": 2,
            "minimum_new_previously_uncovered_exact_valid_recovered_cases": 1,
            "maximum_invalid_top1_cases": 4,
            "preserved_recovery_case_id": PRESERVED_RECOVERY_CASE_ID,
            "preserved_recovery_requires_exact_valid_at_or_below_2a": True,
            "all_conditions_required": True,
            "rigid_lower_bounds_used_for_gate": False,
        },
    }


def frozen_protocol() -> dict[str, object]:
    projection = _protocol_projection()
    observed = _sha256(projection)
    if observed != FROZEN_PROTOCOL_SHA256:
        raise RuntimeError("frozen development protocol projection changed")
    return {**deepcopy(projection), "protocol_sha256": observed}


def _require_exact_keys(
    value: Mapping[str, object], expected: set[str], *, location: str
) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise ProtocolError(
            "schema_keys_mismatch",
            f"{location} missing={missing!r} extra={extra!r}",
        )


def _mapping(value: object, *, location: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProtocolError("invalid_mapping", f"{location} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise ProtocolError("invalid_mapping_key", f"{location} keys must be strings")
    return value


def _sequence(value: object, *, location: str) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        raise ProtocolError("invalid_sequence", f"{location} must be an array")
    return value


def _digest(value: object, *, location: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ProtocolError("invalid_sha256", f"{location} must be lowercase SHA-256")
    return value


def _validate_sealed(
    value: object,
    *,
    keys: set[str],
    location: str,
) -> dict[str, object]:
    row = _mapping(value, location=location)
    _require_exact_keys(row, keys | {"receipt_sha256"}, location=location)
    observed = _digest(row["receipt_sha256"], location=f"{location}.receipt_sha256")
    projection = {
        key: deepcopy(item) for key, item in row.items() if key != "receipt_sha256"
    }
    if observed != _sha256(projection):
        raise ProtocolError(
            "receipt_hash_mismatch", f"{location} seal does not rederive"
        )
    return {**projection, "receipt_sha256": observed}


def _validate_evaluator_identity(value: object, *, location: str) -> dict[str, object]:
    row = _mapping(value, location=location)
    expected = {
        "evaluator_id": POSEBUSTERS_EVALUATOR_ID,
        "posebusters_version": POSEBUSTERS_VERSION,
        "rmsd_method_id": POSEBUSTERS_RMSD_METHOD_ID,
        "full_report": True,
        "external_solver_used_for_generation": False,
    }
    _require_exact_keys(
        row,
        set(expected) | {"implementation_source_sha256"},
        location=location,
    )
    if any(row[name] != expected_value for name, expected_value in expected.items()):
        raise ProtocolError(
            "evaluator_identity_mismatch", f"{location} evaluator changed"
        )
    source_sha256 = _digest(
        row["implementation_source_sha256"],
        location=f"{location}.implementation_source_sha256",
    )
    if source_sha256 != FROZEN_POSEBUSTERS_EVALUATOR_SOURCE_SHA256:
        raise ProtocolError(
            "evaluator_identity_mismatch",
            f"{location} evaluator source is not the frozen implementation",
        )
    return {
        **expected,
        "implementation_source_sha256": source_sha256,
    }


_NATIVE_BACKEND_KEYS = {
    "schema_id",
    "backend_id",
    "backend_version",
    "distribution_version",
    "extension_sha256",
    "cargo_lock_sha256",
    "native_source_closure_sha256",
    "native_source_closure_file_count",
    "rustc_version",
    "target_triple",
    "build_profile",
    "opt_level",
    "debug",
    "panic_strategy",
    "build_flags",
    "cargo_features",
    "docking_search_schema_id",
    "docking_search_receipt_schema_id",
    "docking_search_evaluator_id",
    "implicit_fallback_allowed",
    "test_double",
}


def _validate_native_backend_receipt(
    value: object,
    *,
    expected_source_sha256: str,
    expected_extension_sha256: str,
) -> dict[str, object]:
    row = _validate_sealed(
        value,
        keys=_NATIVE_BACKEND_KEYS,
        location="implementation.native_backend_receipt",
    )
    expected = {
        "schema_id": NATIVE_BACKEND_RECEIPT_SCHEMA_ID,
        "backend_id": "rust_cpu_required",
        "backend_version": NATIVE_BACKEND_VERSION,
        "distribution_version": NATIVE_EXTENSION_VERSION,
        "extension_sha256": expected_extension_sha256,
        "native_source_closure_sha256": expected_source_sha256,
        "rustc_version": NATIVE_RUSTC_VERSION,
        "target_triple": NATIVE_TARGET_TRIPLE,
        "build_profile": "release",
        "opt_level": "3",
        "debug": "false",
        "panic_strategy": "abort",
        "build_flags": NATIVE_BUILD_FLAGS,
        "cargo_features": "extension-module",
        "docking_search_schema_id": NATIVE_CORE_SCHEMA_ID,
        "docking_search_receipt_schema_id": NATIVE_CORE_RECEIPT_SCHEMA_ID,
        "docking_search_evaluator_id": NATIVE_EVALUATOR_ID,
        "implicit_fallback_allowed": False,
        "test_double": False,
    }
    if any(row[name] != expected_value for name, expected_value in expected.items()):
        raise ProtocolError(
            "native_backend_identity_mismatch",
            "implementation backend is not the authenticated release facade",
        )
    cargo_lock_sha256 = _digest(
        row["cargo_lock_sha256"], location="native backend cargo lock"
    )
    if cargo_lock_sha256 != FROZEN_NATIVE_CARGO_LOCK_SHA256:
        raise ProtocolError(
            "native_backend_identity_mismatch",
            "native Cargo.lock is not the frozen release input",
        )
    count = row["native_source_closure_file_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 2:
        raise ProtocolError(
            "native_backend_identity_mismatch", "native source closure is incomplete"
        )
    return row


def _validate_implementation(value: object) -> dict[str, object]:
    row = _mapping(value, location="implementation")
    _require_exact_keys(
        row,
        {
            "engine_id",
            "search_crate_id",
            "search_implementation_sha256",
            "native_extension_version",
            "native_extension_sha256",
            "generation_backend",
            "external_solver_used",
            "native_backend_receipt",
        },
        location="implementation",
    )
    expected_text = {
        "engine_id": "betelgeuze",
        "search_crate_id": SEARCH_CRATE_ID,
        "native_extension_version": NATIVE_EXTENSION_VERSION,
        "generation_backend": "betelgeuze_rust_native",
    }
    if any(row[name] != expected for name, expected in expected_text.items()):
        raise ProtocolError(
            "implementation_identity_mismatch",
            "result does not identify the frozen Betelgeuze native search path",
        )
    if row["external_solver_used"] is not False:
        raise ProtocolError(
            "external_solver_generation_forbidden",
            "external solvers cannot generate product-path proposals",
        )
    source_sha256 = _digest(
        row["search_implementation_sha256"],
        location="implementation.search_implementation_sha256",
    )
    extension_sha256 = _digest(
        row["native_extension_sha256"],
        location="implementation.native_extension_sha256",
    )
    if (
        source_sha256 != FROZEN_NATIVE_SOURCE_CLOSURE_SHA256
        or extension_sha256 != FROZEN_NATIVE_EXTENSION_SHA256
    ):
        raise ProtocolError(
            "implementation_identity_mismatch",
            "result does not use the frozen native source closure and extension",
        )
    backend_receipt = _validate_native_backend_receipt(
        row["native_backend_receipt"],
        expected_source_sha256=source_sha256,
        expected_extension_sha256=extension_sha256,
    )
    return {
        **expected_text,
        "search_implementation_sha256": source_sha256,
        "native_extension_sha256": extension_sha256,
        "native_backend_receipt": backend_receipt,
        "external_solver_used": False,
    }


def _validate_generation_boundary(value: object) -> dict[str, object]:
    row = _mapping(value, location="generation_boundary")
    expected = {
        "policy_id": GENERATION_POLICY_ID,
        "known_pocket_policy_id": KNOWN_POCKET_POLICY_ID,
        "fixed_candidate_slots_per_scored_case": (CANDIDATE_SLOTS_PER_SCORED_CASE),
        "allocation_sealed_before_results": True,
        "result_dependent_allocation": False,
        "external_solver_used": False,
        "full_reference_pose_used_by_search": False,
        "rmsd_used_by_search": False,
        "posebusters_used_by_search": False,
        "baseline_outcomes_used_by_search": False,
        "known_pocket_derived_from_reference_before_search": True,
        "allowed_generation_input_roles": [
            "authenticated_protein_structure",
            "authenticated_ligand_start_conformer",
            "predeclared_known_pocket",
            "public_force_field_parameters",
        ],
    }
    _require_exact_keys(
        row,
        set(expected) | {"search_config_sha256"},
        location="generation_boundary",
    )
    if any(row[name] != item for name, item in expected.items()):
        raise ProtocolError(
            "generation_boundary_changed",
            "search inputs, fixed budget, or feedback boundary changed",
        )
    return {
        **expected,
        "search_config_sha256": _digest(
            row["search_config_sha256"],
            location="generation_boundary.search_config_sha256",
        ),
    }


def _finite_nonnegative(value: object, *, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolError("invalid_rmsd", f"{location} must be a number")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ProtocolError(
            "invalid_rmsd", f"{location} must be finite and non-negative"
        )
    return number


_NATIVE_SEARCH_RECEIPT_DIGEST_KEYS = {
    "evaluator_config_sha256",
    "config_sha256",
    "input_sha256",
    "allocation_sha256",
    "orientation_sha256",
    "candidate_rows_sha256",
    "poses_sha256",
    "receipt_sha256",
}
_NATIVE_SEARCH_RECEIPT_TEXT_KEYS = {
    "schema_id",
    "evaluator_id",
    "placement_mode",
}
_NATIVE_SEARCH_RECEIPT_BOOL_KEYS = {"result_independent_allocation"}
_NATIVE_SEARCH_RECEIPT_INTEGER_KEYS = {
    "requested_orientation_count",
    "accepted_orientation_count",
    "raw_orientation_attempt_count",
    "compatible_single_anchor_pair_count",
    "compatible_dual_anchor_combination_count",
    "used_anchor_combination_count",
    "possible_candidate_slot_count",
    "generated_candidate_limit",
    "allocated_candidate_slot_count",
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
}
_NATIVE_SEARCH_RECEIPT_KEYS = (
    _NATIVE_SEARCH_RECEIPT_DIGEST_KEYS
    | _NATIVE_SEARCH_RECEIPT_TEXT_KEYS
    | _NATIVE_SEARCH_RECEIPT_BOOL_KEYS
    | _NATIVE_SEARCH_RECEIPT_INTEGER_KEYS
)


def _validate_native_search_receipt(
    value: object, *, location: str
) -> dict[str, object]:
    row = _mapping(value, location=location)
    _require_exact_keys(row, _NATIVE_SEARCH_RECEIPT_KEYS, location=location)
    if (
        row["schema_id"] != NATIVE_CORE_RECEIPT_SCHEMA_ID
        or row["evaluator_id"] != NATIVE_EVALUATOR_ID
        or row["result_independent_allocation"] is not True
        or row["placement_mode"] not in {"dual_anchor", "single_anchor_fallback"}
    ):
        raise ProtocolError(
            "native_search_receipt_identity_mismatch",
            f"{location} is not an authenticated native search receipt",
        )
    normalized = dict(row)
    for name in _NATIVE_SEARCH_RECEIPT_DIGEST_KEYS:
        normalized[name] = _digest(row[name], location=f"{location}.{name}")
    for name in _NATIVE_SEARCH_RECEIPT_INTEGER_KEYS:
        item = row[name]
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            raise ProtocolError(
                "native_search_receipt_invalid",
                f"{location}.{name} must be a non-negative integer",
            )
    if (
        row["requested_orientation_count"] != 64
        or row["accepted_orientation_count"] != 64
        or row["generated_candidate_limit"] != CANDIDATE_SLOTS_PER_SCORED_CASE
        or row["allocated_candidate_slot_count"] != CANDIDATE_SLOTS_PER_SCORED_CASE
        or row["possible_candidate_slot_count"] < CANDIDATE_SLOTS_PER_SCORED_CASE
    ):
        raise ProtocolError(
            "native_search_receipt_allocation_mismatch",
            f"{location} does not describe the fixed 64-slot search",
        )
    return normalized


def _validate_rank_receipt(
    value: object,
    *,
    case_id: str,
    candidates: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    row = _validate_sealed(
        value,
        keys={
            "schema_id",
            "case_id",
            "policy_id",
            "candidate_count",
            "ranked_candidates",
            "oracle_fields_used",
            "native_fields_used",
        },
        location=f"{case_id}.rank_receipt",
    )
    expected_native_fields = [
        "final_rank",
        "energy_kcal_per_mol",
        "detailed_score",
        "coarse_score",
        "slot_index",
    ]
    if (
        row["schema_id"] != RANK_RECEIPT_SCHEMA_ID
        or row["case_id"] != case_id
        or row["policy_id"] != RANK_POLICY_ID
        or row["candidate_count"] != CANDIDATE_SLOTS_PER_SCORED_CASE
        or row["oracle_fields_used"] != []
        or row["native_fields_used"] != expected_native_fields
    ):
        raise ProtocolError("rank_receipt_mismatch", f"{case_id} rank policy changed")
    ranked = _sequence(
        row["ranked_candidates"], location=f"{case_id}.rank_receipt.ranked_candidates"
    )
    if len(ranked) != CANDIDATE_SLOTS_PER_SCORED_CASE:
        raise ProtocolError("rank_receipt_mismatch", f"{case_id} rank count changed")
    by_rank = sorted(candidates, key=lambda candidate: int(candidate["score_rank"]))
    normalized_ranked: list[dict[str, object]] = []
    for expected_rank, (item, candidate) in enumerate(
        zip(ranked, by_rank, strict=True), start=1
    ):
        rank_row = _mapping(
            item,
            location=f"{case_id}.rank_receipt.ranked_candidates[{expected_rank - 1}]",
        )
        _require_exact_keys(
            rank_row,
            {"score_rank", "slot_index", "native_row_sha256"},
            location=f"{case_id}.rank_receipt.ranked_candidates[{expected_rank - 1}]",
        )
        expected = {
            "score_rank": expected_rank,
            "slot_index": candidate["slot_index"],
            "native_row_sha256": candidate["native_row_sha256"],
        }
        if dict(rank_row) != expected:
            raise ProtocolError(
                "rank_candidate_binding_mismatch",
                f"{case_id} rank {expected_rank} is not bound to its candidate",
            )
        normalized_ranked.append(expected)
    return {**row, "ranked_candidates": normalized_ranked}


def _validate_candidate(
    value: object, *, case_id: str, expected_slot: int
) -> dict[str, object]:
    row = _mapping(value, location=f"{case_id}.candidates[{expected_slot}]")
    _require_exact_keys(
        row,
        {
            "slot_index",
            "score_rank",
            "search_status",
            "search_failure_code",
            "proposal_artifact_sha256",
            "coordinate_sha256",
            "native_coordinate_sha256",
            "native_row_sha256",
            "candidate_search_receipt_sha256",
            "rmsd_angstrom",
            "rmsd_fact_origin",
            "rmsd_subject_proposal_artifact_sha256",
            "rmsd_subject_coordinate_sha256",
            "rmsd_fact_receipt_sha256",
            "posebusters_exact_valid",
            "posebusters_fact_origin",
            "posebusters_subject_proposal_artifact_sha256",
            "posebusters_subject_coordinate_sha256",
            "posebusters_fact_receipt_sha256",
        },
        location=f"{case_id}.candidates[{expected_slot}]",
    )
    slot = row["slot_index"]
    rank = row["score_rank"]
    if isinstance(slot, bool) or not isinstance(slot, int) or slot != expected_slot:
        raise ProtocolError(
            "allocation_slot_mismatch",
            f"{case_id} slot {expected_slot} is not fixed",
        )
    if isinstance(rank, bool) or not isinstance(rank, int):
        raise ProtocolError("invalid_score_rank", f"{case_id} rank must be an integer")
    search_status = row["search_status"]
    failure_code = row["search_failure_code"]
    if search_status not in _CANDIDATE_SEARCH_STATUSES:
        raise ProtocolError(
            "invalid_search_status",
            f"{case_id} slot {expected_slot} has an unknown search status",
        )
    if search_status in _FAILURE_SEARCH_STATUSES:
        if (
            not isinstance(failure_code, str)
            or _FAILURE_CODE_RE.fullmatch(failure_code) is None
        ):
            raise ProtocolError(
                "invalid_search_failure_code",
                f"{case_id} slot {expected_slot} requires a typed failure code",
            )
    elif failure_code is not None:
        raise ProtocolError(
            "unexpected_search_failure_code",
            f"{case_id} slot {expected_slot} is not a failed search row",
        )
    proposal_artifact_sha256 = _digest(
        row["proposal_artifact_sha256"],
        location=f"{case_id}.proposal_artifact_sha256",
    )
    coordinate_sha256 = _digest(
        row["coordinate_sha256"], location=f"{case_id}.coordinate_sha256"
    )
    native_coordinate_sha256 = _digest(
        row["native_coordinate_sha256"],
        location=f"{case_id}.native_coordinate_sha256",
    )
    native_row_sha256 = _digest(
        row["native_row_sha256"], location=f"{case_id}.native_row_sha256"
    )
    candidate_search_receipt_sha256 = _digest(
        row["candidate_search_receipt_sha256"],
        location=f"{case_id}.candidate_search_receipt_sha256",
    )
    if row["rmsd_fact_origin"] != EXTERNAL_RMSD_FACT_ORIGIN:
        raise ProtocolError(
            "rmsd_fact_not_external",
            f"{case_id} RMSD origin is not the frozen external fact origin",
        )
    if (
        row["rmsd_subject_proposal_artifact_sha256"] != proposal_artifact_sha256
        or row["rmsd_subject_coordinate_sha256"] != coordinate_sha256
    ):
        raise ProtocolError(
            "rmsd_subject_mismatch",
            f"{case_id} RMSD fact is not bound to this proposal",
        )
    rmsd_receipt = _digest(
        row["rmsd_fact_receipt_sha256"],
        location=f"{case_id}.rmsd_fact_receipt_sha256",
    )
    validity = row["posebusters_exact_valid"]
    if not isinstance(validity, bool):
        raise ProtocolError(
            "invalid_posebusters_fact", f"{case_id} validity must be boolean"
        )
    if row["posebusters_fact_origin"] != EXTERNAL_POSEBUSTERS_FACT_ORIGIN:
        raise ProtocolError(
            "posebusters_fact_not_external",
            f"{case_id} validity origin is not the frozen external fact origin",
        )
    if (
        row["posebusters_subject_proposal_artifact_sha256"] != proposal_artifact_sha256
        or row["posebusters_subject_coordinate_sha256"] != coordinate_sha256
    ):
        raise ProtocolError(
            "posebusters_subject_mismatch",
            f"{case_id} PoseBusters fact is not bound to this proposal",
        )
    receipt = _digest(
        row["posebusters_fact_receipt_sha256"],
        location=f"{case_id}.posebusters_fact_receipt_sha256",
    )
    return {
        "slot_index": slot,
        "score_rank": rank,
        "search_status": search_status,
        "search_failure_code": failure_code,
        "proposal_artifact_sha256": proposal_artifact_sha256,
        "coordinate_sha256": coordinate_sha256,
        "native_coordinate_sha256": native_coordinate_sha256,
        "native_row_sha256": native_row_sha256,
        "candidate_search_receipt_sha256": candidate_search_receipt_sha256,
        "rmsd_angstrom": _finite_nonnegative(
            row["rmsd_angstrom"], location=f"{case_id}.rmsd_angstrom"
        ),
        "rmsd_fact_origin": EXTERNAL_RMSD_FACT_ORIGIN,
        "rmsd_subject_proposal_artifact_sha256": proposal_artifact_sha256,
        "rmsd_subject_coordinate_sha256": coordinate_sha256,
        "rmsd_fact_receipt_sha256": rmsd_receipt,
        "posebusters_exact_valid": validity,
        "posebusters_fact_origin": EXTERNAL_POSEBUSTERS_FACT_ORIGIN,
        "posebusters_subject_proposal_artifact_sha256": (proposal_artifact_sha256),
        "posebusters_subject_coordinate_sha256": coordinate_sha256,
        "posebusters_fact_receipt_sha256": receipt,
    }


def _validate_evaluation_receipt(
    value: object,
    *,
    case_id: str,
    candidates: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    sidecar = _validate_sealed(
        value,
        keys={"schema_id", "case_id", "batch_receipt", "candidate_facts"},
        location=f"{case_id}.evaluation_receipt",
    )
    if (
        sidecar["schema_id"] != EVALUATION_SIDECAR_SCHEMA_ID
        or sidecar["case_id"] != case_id
    ):
        raise ProtocolError(
            "evaluation_sidecar_identity_mismatch", f"{case_id} sidecar changed"
        )
    candidate_facts = _sequence(
        sidecar["candidate_facts"],
        location=f"{case_id}.evaluation_receipt.candidate_facts",
    )
    if len(candidate_facts) != CANDIDATE_SLOTS_PER_SCORED_CASE:
        raise ProtocolError(
            "evaluation_fact_count_mismatch", f"{case_id} must contain 64 fact pairs"
        )

    normalized_facts: list[dict[str, object]] = []
    evaluator_identity: dict[str, object] | None = None
    report_columns: list[str] | None = None
    fact_digest_rows: list[dict[str, object]] = []
    for expected_slot, (fact_value, candidate) in enumerate(
        zip(candidate_facts, candidates, strict=True)
    ):
        location = f"{case_id}.evaluation_receipt.candidate_facts[{expected_slot}]"
        fact_row = _mapping(fact_value, location=location)
        _require_exact_keys(
            fact_row,
            {
                "slot_index",
                "native_coordinate_sha256",
                "rmsd_fact",
                "posebusters_fact",
            },
            location=location,
        )
        if (
            fact_row["slot_index"] != expected_slot
            or fact_row["native_coordinate_sha256"]
            != candidate["native_coordinate_sha256"]
        ):
            raise ProtocolError(
                "evaluation_subject_mismatch",
                f"{case_id} slot {expected_slot} sidecar subject changed",
            )
        subject = {
            "proposal_artifact_sha256": candidate["proposal_artifact_sha256"],
            "coordinate_sha256": candidate["coordinate_sha256"],
        }
        rmsd = _validate_sealed(
            fact_row["rmsd_fact"],
            keys={
                "schema_id",
                "case_id",
                "slot_index",
                "origin",
                "proposal_artifact_sha256",
                "coordinate_sha256",
                "rmsd_angstrom",
                "evaluator_identity",
            },
            location=f"{location}.rmsd_fact",
        )
        rmsd_identity = _validate_evaluator_identity(
            rmsd["evaluator_identity"],
            location=f"{location}.rmsd_fact.evaluator_identity",
        )
        if (
            rmsd["schema_id"] != RMSD_FACT_SCHEMA_ID
            or rmsd["case_id"] != case_id
            or rmsd["slot_index"] != expected_slot
            or rmsd["origin"] != EXTERNAL_RMSD_FACT_ORIGIN
            or any(rmsd[name] != digest for name, digest in subject.items())
            or _finite_nonnegative(
                rmsd["rmsd_angstrom"], location=f"{location}.rmsd_fact.rmsd_angstrom"
            )
            != candidate["rmsd_angstrom"]
            or rmsd["receipt_sha256"] != candidate["rmsd_fact_receipt_sha256"]
        ):
            raise ProtocolError(
                "rmsd_fact_binding_mismatch",
                f"{case_id} slot {expected_slot} RMSD fact changed",
            )

        posebusters = _validate_sealed(
            fact_row["posebusters_fact"],
            keys={
                "schema_id",
                "case_id",
                "slot_index",
                "origin",
                "proposal_artifact_sha256",
                "coordinate_sha256",
                "posebusters_exact_valid",
                "chemical_check_ids",
                "geometric_check_ids",
                "check_facts",
                "full_report_columns",
                "full_report_facts",
                "evaluator_identity",
            },
            location=f"{location}.posebusters_fact",
        )
        posebusters_identity = _validate_evaluator_identity(
            posebusters["evaluator_identity"],
            location=f"{location}.posebusters_fact.evaluator_identity",
        )
        checks = _mapping(
            posebusters["check_facts"], location=f"{location}.check_facts"
        )
        _require_exact_keys(
            checks, set(POSEBUSTERS_CHECK_IDS), location=f"{location}.check_facts"
        )
        if any(type(checks[name]) is not bool for name in POSEBUSTERS_CHECK_IDS):
            raise ProtocolError(
                "posebusters_check_fact_invalid",
                f"{case_id} slot {expected_slot} check facts must be boolean",
            )
        exact_valid = all(bool(checks[name]) for name in POSEBUSTERS_CHECK_IDS)
        columns_value = _sequence(
            posebusters["full_report_columns"],
            location=f"{location}.full_report_columns",
        )
        columns = list(columns_value)
        if (
            not all(isinstance(column, str) for column in columns)
            or len(columns) != len(set(columns))
            or not {"rmsd", *POSEBUSTERS_CHECK_IDS}.issubset(columns)
        ):
            raise ProtocolError(
                "posebusters_report_columns_invalid",
                f"{case_id} slot {expected_slot} full report columns changed",
            )
        full_facts = _mapping(
            posebusters["full_report_facts"],
            location=f"{location}.full_report_facts",
        )
        _require_exact_keys(
            full_facts, set(columns), location=f"{location}.full_report_facts"
        )
        full_rmsd = _finite_nonnegative(
            full_facts["rmsd"], location=f"{location}.full_report_facts.rmsd"
        )
        if any(
            type(full_facts[name]) is not bool or full_facts[name] is not checks[name]
            for name in POSEBUSTERS_CHECK_IDS
        ):
            raise ProtocolError(
                "posebusters_full_report_mismatch",
                f"{case_id} slot {expected_slot} checks disagree with full report",
            )
        if (
            posebusters["schema_id"] != POSEBUSTERS_FACT_SCHEMA_ID
            or posebusters["case_id"] != case_id
            or posebusters["slot_index"] != expected_slot
            or posebusters["origin"] != EXTERNAL_POSEBUSTERS_FACT_ORIGIN
            or any(posebusters[name] != digest for name, digest in subject.items())
            or posebusters["chemical_check_ids"] != list(POSEBUSTERS_CHEMICAL_CHECK_IDS)
            or posebusters["geometric_check_ids"]
            != list(POSEBUSTERS_GEOMETRIC_CHECK_IDS)
            or type(posebusters["posebusters_exact_valid"]) is not bool
            or posebusters["posebusters_exact_valid"] is not exact_valid
            or candidate["posebusters_exact_valid"] is not exact_valid
            or full_rmsd != candidate["rmsd_angstrom"]
            or posebusters["receipt_sha256"]
            != candidate["posebusters_fact_receipt_sha256"]
            or rmsd_identity != posebusters_identity
        ):
            raise ProtocolError(
                "posebusters_fact_binding_mismatch",
                f"{case_id} slot {expected_slot} PoseBusters fact changed",
            )
        if evaluator_identity is None:
            evaluator_identity = rmsd_identity
            report_columns = columns
        elif evaluator_identity != rmsd_identity or report_columns != columns:
            raise ProtocolError(
                "evaluation_batch_identity_drift",
                f"{case_id} external evaluator or columns drifted",
            )
        fact_digest_rows.append(
            {
                "slot_index": expected_slot,
                "rmsd_fact_receipt_sha256": rmsd["receipt_sha256"],
                "posebusters_fact_receipt_sha256": posebusters["receipt_sha256"],
            }
        )
        normalized_facts.append(
            {
                "slot_index": expected_slot,
                "native_coordinate_sha256": candidate["native_coordinate_sha256"],
                "rmsd_fact": {**rmsd, "evaluator_identity": rmsd_identity},
                "posebusters_fact": {
                    **posebusters,
                    "check_facts": dict(checks),
                    "full_report_columns": columns,
                    "full_report_facts": dict(full_facts),
                    "evaluator_identity": posebusters_identity,
                },
            }
        )
    assert evaluator_identity is not None and report_columns is not None
    batch = _validate_sealed(
        sidecar["batch_receipt"],
        keys={
            "schema_id",
            "case_id",
            "candidate_count",
            "report_columns",
            "candidate_fact_receipt_sha256s",
            "evaluator_identity",
        },
        location=f"{case_id}.evaluation_receipt.batch_receipt",
    )
    batch_identity = _validate_evaluator_identity(
        batch["evaluator_identity"],
        location=f"{case_id}.evaluation_receipt.batch_receipt.evaluator_identity",
    )
    if (
        batch["schema_id"] != EVALUATION_BATCH_SCHEMA_ID
        or batch["case_id"] != case_id
        or batch["candidate_count"] != CANDIDATE_SLOTS_PER_SCORED_CASE
        or batch["report_columns"] != report_columns
        or batch["candidate_fact_receipt_sha256s"] != fact_digest_rows
        or batch_identity != evaluator_identity
    ):
        raise ProtocolError(
            "evaluation_batch_binding_mismatch", f"{case_id} batch receipt changed"
        )
    return (
        {
            **sidecar,
            "batch_receipt": {**batch, "evaluator_identity": batch_identity},
            "candidate_facts": normalized_facts,
        },
        evaluator_identity,
    )


def _validate_search_receipt(
    value: object,
    *,
    case_id: str,
    generation_input_receipt_sha256: str,
    known_pocket_receipt_sha256: str,
    candidates: Sequence[Mapping[str, object]],
    rank_receipt: Mapping[str, object],
    implementation: Mapping[str, object],
    search_config_sha256: str,
) -> dict[str, object]:
    row = _validate_sealed(
        value,
        keys={
            "schema_id",
            "case_id",
            "generation_policy_id",
            "generation_input_receipt_sha256",
            "known_pocket_receipt_sha256",
            "search_config_sha256",
            "search_implementation_sha256",
            "native_extension_sha256",
            "native_backend_receipt_sha256",
            "native_search_receipt_sha256",
            "native_search_receipt",
            "native_result_sha256",
            "rank_receipt_sha256",
            "candidate_count",
            "candidate_subjects",
            "external_solver_used",
            "rmsd_used_for_ranking",
            "posebusters_used_for_ranking",
        },
        location=f"{case_id}.search_receipt",
    )
    native_receipt = _validate_native_search_receipt(
        row["native_search_receipt"],
        location=f"{case_id}.search_receipt.native_search_receipt",
    )
    subjects = _sequence(
        row["candidate_subjects"],
        location=f"{case_id}.search_receipt.candidate_subjects",
    )
    expected_subjects = [
        {
            "slot_index": candidate["slot_index"],
            "proposal_artifact_sha256": candidate["proposal_artifact_sha256"],
            "coordinate_sha256": candidate["coordinate_sha256"],
            "native_coordinate_sha256": candidate["native_coordinate_sha256"],
            "native_row_sha256": candidate["native_row_sha256"],
            "score_rank": candidate["score_rank"],
            "search_status": candidate["search_status"],
            "search_failure_code": candidate["search_failure_code"],
        }
        for candidate in candidates
    ]
    normalized_subjects: list[dict[str, object]] = []
    if len(subjects) != CANDIDATE_SLOTS_PER_SCORED_CASE:
        raise ProtocolError(
            "search_candidate_binding_mismatch",
            f"{case_id} search subject count changed",
        )
    for index, (subject_value, expected) in enumerate(
        zip(subjects, expected_subjects, strict=True)
    ):
        subject = _mapping(
            subject_value,
            location=f"{case_id}.search_receipt.candidate_subjects[{index}]",
        )
        _require_exact_keys(
            subject,
            set(expected),
            location=f"{case_id}.search_receipt.candidate_subjects[{index}]",
        )
        if dict(subject) != expected:
            raise ProtocolError(
                "search_candidate_binding_mismatch",
                f"{case_id} slot {index} search subject changed",
            )
        normalized_subjects.append(expected)
    backend = implementation["native_backend_receipt"]
    expected = {
        "schema_id": SEARCH_BINDING_SCHEMA_ID,
        "case_id": case_id,
        "generation_policy_id": GENERATION_POLICY_ID,
        "generation_input_receipt_sha256": generation_input_receipt_sha256,
        "known_pocket_receipt_sha256": known_pocket_receipt_sha256,
        "search_config_sha256": search_config_sha256,
        "search_implementation_sha256": implementation["search_implementation_sha256"],
        "native_extension_sha256": implementation["native_extension_sha256"],
        "native_backend_receipt_sha256": backend["receipt_sha256"],
        "native_search_receipt_sha256": _sha256(native_receipt),
        "native_result_sha256": row["native_result_sha256"],
        "rank_receipt_sha256": rank_receipt["receipt_sha256"],
        "candidate_count": CANDIDATE_SLOTS_PER_SCORED_CASE,
        "candidate_subjects": normalized_subjects,
        "external_solver_used": False,
        "rmsd_used_for_ranking": False,
        "posebusters_used_for_ranking": False,
    }
    _digest(row["native_result_sha256"], location=f"{case_id}.native_result_sha256")
    for name in ("native_search_receipt_sha256", "native_backend_receipt_sha256"):
        _digest(row[name], location=f"{case_id}.{name}")
    if any(row[name] != item for name, item in expected.items()):
        raise ProtocolError(
            "search_receipt_binding_mismatch", f"{case_id} search receipt changed"
        )
    return {
        **row,
        "native_search_receipt": native_receipt,
        "candidate_subjects": normalized_subjects,
    }


def _validate_case(
    value: object,
    expected: FrozenCase,
    *,
    implementation: Mapping[str, object],
    generation_boundary: Mapping[str, object],
) -> dict[str, object]:
    row = _mapping(value, location=expected.case_id)
    _require_exact_keys(
        row,
        {
            "case_id",
            "source_receipt_sha256",
            "generation_input_receipt_sha256",
            "known_pocket_receipt_sha256",
            "search_receipt_sha256",
            "search_receipt",
            "rank_receipt",
            "evaluation_receipt",
            "preparation_status",
            "preparation_failure_code",
            "candidates",
        },
        location=expected.case_id,
    )
    if row["case_id"] != expected.case_id:
        raise ProtocolError("case_order_mismatch", f"expected {expected.case_id}")
    if row["source_receipt_sha256"] != expected.source_receipt_sha256:
        raise ProtocolError(
            "source_receipt_mismatch", f"{expected.case_id} source receipt changed"
        )
    generation_input_receipt_sha256 = _digest(
        row["generation_input_receipt_sha256"],
        location=f"{expected.case_id}.generation_input_receipt_sha256",
    )
    known_pocket_receipt_sha256 = _digest(
        row["known_pocket_receipt_sha256"],
        location=f"{expected.case_id}.known_pocket_receipt_sha256",
    )
    candidates = _sequence(row["candidates"], location=f"{expected.case_id}.candidates")
    if not expected.scored:
        if (
            row["preparation_status"] != "failed"
            or row["preparation_failure_code"] != expected.preparation_failure_code
            or row["search_receipt_sha256"] is not None
            or row["search_receipt"] is not None
            or row["rank_receipt"] is not None
            or row["evaluation_receipt"] is not None
            or candidates
        ):
            raise ProtocolError(
                "preparation_failure_mismatch",
                f"{expected.case_id} must retain its typed empty preparation failure",
            )
        return {
            "case_id": expected.case_id,
            "source_receipt_sha256": expected.source_receipt_sha256,
            "generation_input_receipt_sha256": generation_input_receipt_sha256,
            "known_pocket_receipt_sha256": known_pocket_receipt_sha256,
            "search_receipt_sha256": None,
            "search_receipt": None,
            "rank_receipt": None,
            "evaluation_receipt": None,
            "preparation_status": "failed",
            "preparation_failure_code": expected.preparation_failure_code,
            "candidates": [],
        }
    if (
        row["preparation_status"] != "success"
        or row["preparation_failure_code"] is not None
    ):
        raise ProtocolError(
            "preparation_status_mismatch", f"{expected.case_id} must be scored"
        )
    search_receipt_sha256 = _digest(
        row["search_receipt_sha256"],
        location=f"{expected.case_id}.search_receipt_sha256",
    )
    if len(candidates) != CANDIDATE_SLOTS_PER_SCORED_CASE:
        raise ProtocolError(
            "candidate_budget_mismatch",
            f"{expected.case_id} must contain exactly 64 candidates",
        )
    normalized = [
        _validate_candidate(candidate, case_id=expected.case_id, expected_slot=index)
        for index, candidate in enumerate(candidates)
    ]
    if any(
        candidate["candidate_search_receipt_sha256"] != search_receipt_sha256
        for candidate in normalized
    ):
        raise ProtocolError(
            "candidate_search_receipt_mismatch",
            f"{expected.case_id} candidates are cross-wired to another search run",
        )
    ranks = sorted(candidate["score_rank"] for candidate in normalized)
    if ranks != list(range(1, CANDIDATE_SLOTS_PER_SCORED_CASE + 1)):
        raise ProtocolError(
            "score_rank_set_mismatch",
            f"{expected.case_id} ranks must be exactly 1..64",
        )
    rank_receipt = _validate_rank_receipt(
        row["rank_receipt"], case_id=expected.case_id, candidates=normalized
    )
    search_receipt = _validate_search_receipt(
        row["search_receipt"],
        case_id=expected.case_id,
        generation_input_receipt_sha256=generation_input_receipt_sha256,
        known_pocket_receipt_sha256=known_pocket_receipt_sha256,
        candidates=normalized,
        rank_receipt=rank_receipt,
        implementation=implementation,
        search_config_sha256=str(generation_boundary["search_config_sha256"]),
    )
    if search_receipt["receipt_sha256"] != search_receipt_sha256:
        raise ProtocolError(
            "search_receipt_binding_mismatch",
            f"{expected.case_id} case search digest does not seal its sidecar",
        )
    evaluation_receipt, _ = _validate_evaluation_receipt(
        row["evaluation_receipt"],
        case_id=expected.case_id,
        candidates=normalized,
    )
    return {
        "case_id": expected.case_id,
        "source_receipt_sha256": expected.source_receipt_sha256,
        "generation_input_receipt_sha256": generation_input_receipt_sha256,
        "known_pocket_receipt_sha256": known_pocket_receipt_sha256,
        "search_receipt_sha256": search_receipt_sha256,
        "search_receipt": search_receipt,
        "rank_receipt": rank_receipt,
        "evaluation_receipt": evaluation_receipt,
        "preparation_status": "success",
        "preparation_failure_code": None,
        "candidates": normalized,
    }


def _normalize_result(value: object) -> dict[str, object]:
    root = _mapping(value, location="result")
    _require_exact_keys(
        root,
        {
            "schema_id",
            "protocol_sha256",
            "source_archive_sha256",
            "roster_sha256",
            "allocation",
            "implementation",
            "generation_boundary",
            "cases",
            "claim_boundary",
        },
        location="result",
    )
    if root["schema_id"] != RESULT_SCHEMA_ID:
        raise ProtocolError("schema_id_mismatch", "result schema is not frozen")
    if root["protocol_sha256"] != FROZEN_PROTOCOL_SHA256:
        raise ProtocolError("protocol_hash_mismatch", "result is cross-wired")
    if root["source_archive_sha256"] != SOURCE_ARCHIVE_SHA256:
        raise ProtocolError("source_archive_mismatch", "source archive changed")
    if root["roster_sha256"] != ROSTER_SHA256:
        raise ProtocolError("roster_hash_mismatch", "cohort roster changed")
    if (
        dict(_mapping(root["allocation"], location="allocation"))
        != frozen_allocation_receipt()
    ):
        raise ProtocolError(
            "allocation_receipt_mismatch",
            "allocation is missing, changed, or result-dependent",
        )
    implementation = _validate_implementation(root["implementation"])
    generation_boundary = _validate_generation_boundary(root["generation_boundary"])
    claim_boundary = _mapping(root["claim_boundary"], location="claim_boundary")
    expected_claim_boundary = {
        "development_only": True,
        "retrospective": True,
        "product_dispatch_authorized": False,
        "product_promotion_eligible": False,
        "public_claim_eligible": False,
        "scientific_validation_claimed": False,
    }
    if dict(claim_boundary) != expected_claim_boundary:
        raise ProtocolError(
            "claim_boundary_widened", "result widened benchmark authority"
        )
    cases = _sequence(root["cases"], location="cases")
    if len(cases) != len(FROZEN_CASES):
        raise ProtocolError("case_count_mismatch", "all nine frozen cases are required")
    normalized_cases = [
        _validate_case(
            value,
            expected,
            implementation=implementation,
            generation_boundary=generation_boundary,
        )
        for value, expected in zip(cases, FROZEN_CASES, strict=True)
    ]
    evaluator_identities = {
        canonical_json_bytes(
            case["evaluation_receipt"]["batch_receipt"]["evaluator_identity"]
        )
        for case in normalized_cases
        if case["preparation_status"] == "success"
    }
    if len(evaluator_identities) != 1:
        raise ProtocolError(
            "cohort_evaluator_identity_drift",
            "all eight scored cases must use one authenticated evaluator",
        )
    return {
        "schema_id": RESULT_SCHEMA_ID,
        "protocol_sha256": FROZEN_PROTOCOL_SHA256,
        "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
        "roster_sha256": ROSTER_SHA256,
        "allocation": frozen_allocation_receipt(),
        "implementation": implementation,
        "generation_boundary": generation_boundary,
        "cases": normalized_cases,
        "claim_boundary": expected_claim_boundary,
    }


def _case_metric(case: Mapping[str, object]) -> dict[str, object]:
    frozen = _CASE_BY_ID[str(case["case_id"])]
    if not frozen.scored:
        return {
            "case_id": frozen.case_id,
            "source_receipt_sha256": frozen.source_receipt_sha256,
            "scored": False,
            "preparation_failure_code": frozen.preparation_failure_code,
            "baseline_oracle_minimum_rmsd_angstrom": None,
            "rigid_lower_bound_rmsd_angstrom": frozen.rigid_lower_bound_rmsd_angstrom,
            "rigid_lower_bound_used_for_gate": False,
        }
    candidates = list(case["candidates"])
    minimum = min(float(row["rmsd_angstrom"]) for row in candidates)
    exact_valid_count = sum(bool(row["posebusters_exact_valid"]) for row in candidates)
    exact_valid_values = [
        float(row["rmsd_angstrom"])
        for row in candidates
        if bool(row["posebusters_exact_valid"])
    ]
    exact_valid_minimum = min(exact_valid_values, default=None)
    exact_valid_2a = (
        exact_valid_minimum is not None
        and exact_valid_minimum <= RECOVERY_RMSD_ANGSTROM
    )
    top1 = next(row for row in candidates if row["score_rank"] == 1)
    return {
        "case_id": frozen.case_id,
        "source_receipt_sha256": frozen.source_receipt_sha256,
        "scored": True,
        "preparation_failure_code": None,
        "baseline_oracle_minimum_rmsd_angstrom": (
            frozen.baseline_oracle_minimum_rmsd_angstrom
        ),
        "baseline_exact_valid_candidate_count": (
            frozen.baseline_exact_valid_candidate_count
        ),
        "rigid_lower_bound_rmsd_angstrom": frozen.rigid_lower_bound_rmsd_angstrom,
        "rigid_lower_bound_used_for_gate": False,
        "proposal_oracle_minimum_rmsd_angstrom": minimum,
        "proposal_oracle_recovered_at_or_below_2a": (minimum <= RECOVERY_RMSD_ANGSTROM),
        "exact_valid_candidate_count": exact_valid_count,
        "exact_valid_minimum_rmsd_angstrom": exact_valid_minimum,
        "exact_valid_recovered_at_or_below_2a": exact_valid_2a,
        "top1_posebusters_exact_valid": bool(top1["posebusters_exact_valid"]),
    }


def _summary(case_metrics: Sequence[Mapping[str, object]]) -> dict[str, object]:
    scored = [row for row in case_metrics if row["scored"] is True]
    recovered = [
        str(row["case_id"])
        for row in scored
        if row["proposal_oracle_recovered_at_or_below_2a"] is True
    ]
    newly_recovered = [
        str(row["case_id"])
        for row in scored
        if row["case_id"] in PREVIOUSLY_UNCOVERED_CASE_IDS
        and row["exact_valid_recovered_at_or_below_2a"] is True
    ]
    invalid_top1 = [
        str(row["case_id"])
        for row in scored
        if row["top1_posebusters_exact_valid"] is False
    ]
    preserved = (
        next(row for row in scored if row["case_id"] == PRESERVED_RECOVERY_CASE_ID)[
            "exact_valid_recovered_at_or_below_2a"
        ]
        is True
    )
    gates = {
        "proposal_oracle_recovery_at_least_2_of_8": len(recovered) >= 2,
        "new_previously_uncovered_exact_valid_recovery_at_least_1": (
            len(newly_recovered) >= 1
        ),
        "invalid_top1_at_most_4_of_8": len(invalid_top1) <= 4,
        "preserve_6T88_exact_valid_recovery": preserved,
        "fixed_8x64_allocation": True,
        "no_result_dependent_allocation": True,
    }
    return {
        "scored_case_count": len(scored),
        "candidate_budget": len(scored) * CANDIDATE_SLOTS_PER_SCORED_CASE,
        "proposal_oracle_recovered_case_ids": recovered,
        "proposal_oracle_recovered_case_count": len(recovered),
        "new_previously_uncovered_exact_valid_recovered_case_ids": newly_recovered,
        "new_previously_uncovered_exact_valid_recovered_case_count": (
            len(newly_recovered)
        ),
        "invalid_top1_case_ids": invalid_top1,
        "invalid_top1_case_count": len(invalid_top1),
        "preserved_6T88": preserved,
        "gates": gates,
        "development_gate_pass": all(gates.values()),
    }


def evaluate_development_result(value: object) -> dict[str, object]:
    """Validate a complete fixed-budget result and return canonical evidence."""

    normalized = _normalize_result(value)
    metrics = [_case_metric(row) for row in normalized["cases"]]
    summary = _summary(metrics)
    external_fact_receipts = [
        {
            "case_id": case["case_id"],
            "candidate_facts": [
                {
                    "proposal_artifact_sha256": candidate["proposal_artifact_sha256"],
                    "coordinate_sha256": candidate["coordinate_sha256"],
                    "rmsd_fact_receipt_sha256": candidate["rmsd_fact_receipt_sha256"],
                    "posebusters_fact_receipt_sha256": candidate[
                        "posebusters_fact_receipt_sha256"
                    ],
                }
                for candidate in case["candidates"]
            ],
        }
        for case in normalized["cases"]
        if case["preparation_status"] == "success"
    ]
    search_receipts = [
        {
            "case_id": case["case_id"],
            "generation_input_receipt_sha256": case["generation_input_receipt_sha256"],
            "known_pocket_receipt_sha256": case["known_pocket_receipt_sha256"],
            "search_receipt_sha256": case["search_receipt_sha256"],
        }
        for case in normalized["cases"]
    ]
    projection = {
        "schema_id": EVIDENCE_SCHEMA_ID,
        "protocol_sha256": FROZEN_PROTOCOL_SHA256,
        "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
        "roster_sha256": ROSTER_SHA256,
        "allocation_receipt_sha256": FROZEN_ALLOCATION_RECEIPT_SHA256,
        "input_result_sha256": _sha256(normalized),
        "implementation": normalized["implementation"],
        "generation_boundary": normalized["generation_boundary"],
        "case_search_receipts_sha256": _sha256(search_receipts),
        "candidate_proposal_and_fact_bindings_sha256": _sha256(external_fact_receipts),
        "external_rmsd_fact_count": (
            len(SCORED_CASE_IDS) * CANDIDATE_SLOTS_PER_SCORED_CASE
        ),
        "external_posebusters_fact_count": (
            len(SCORED_CASE_IDS) * CANDIDATE_SLOTS_PER_SCORED_CASE
        ),
        "external_posebusters_fact_receipts_sha256": _sha256(
            [
                {
                    "case_id": row["case_id"],
                    "receipt_sha256s": [
                        fact["posebusters_fact_receipt_sha256"]
                        for fact in row["candidate_facts"]
                    ],
                }
                for row in external_fact_receipts
            ]
        ),
        "external_rmsd_fact_receipts_sha256": _sha256(
            [
                {
                    "case_id": row["case_id"],
                    "receipt_sha256s": [
                        fact["rmsd_fact_receipt_sha256"]
                        for fact in row["candidate_facts"]
                    ],
                }
                for row in external_fact_receipts
            ]
        ),
        "case_metrics": metrics,
        "summary": summary,
        "decision": "pass" if summary["development_gate_pass"] else "blocked",
        "claim_boundary": {
            "development_only": True,
            "retrospective": True,
            "product_dispatch_authorized": False,
            "product_promotion_eligible": False,
            "public_claim_eligible": False,
            "scientific_validation_claimed": False,
        },
        "external_fact_boundary": {
            "posebusters_validity_origin": EXTERNAL_POSEBUSTERS_FACT_ORIGIN,
            "symmetry_aware_rmsd_origin": EXTERNAL_RMSD_FACT_ORIGIN,
            "posebusters_validity_computed_here": False,
            "symmetry_aware_rmsd_computed_here": False,
            "molecular_structures_read_by_receipt_evaluator": False,
            "external_engine_invoked_by_receipt_evaluator": False,
        },
    }
    return {**projection, "receipt_sha256": _sha256(projection)}


def verify_evidence_receipt(value: object, result: object) -> dict[str, object]:
    """Verify evidence against the complete result that produced it.

    A receipt SHA-256 is an integrity checksum, not an authenticity signature.
    Consequently, compact evidence is never accepted without independently
    validating and re-evaluating its complete result document.
    """

    receipt = _mapping(value, location="evidence")
    _require_exact_keys(
        receipt,
        {
            "schema_id",
            "protocol_sha256",
            "source_archive_sha256",
            "roster_sha256",
            "allocation_receipt_sha256",
            "input_result_sha256",
            "implementation",
            "generation_boundary",
            "case_search_receipts_sha256",
            "candidate_proposal_and_fact_bindings_sha256",
            "external_rmsd_fact_count",
            "external_posebusters_fact_count",
            "external_posebusters_fact_receipts_sha256",
            "external_rmsd_fact_receipts_sha256",
            "case_metrics",
            "summary",
            "decision",
            "claim_boundary",
            "external_fact_boundary",
            "receipt_sha256",
        },
        location="evidence",
    )
    projection = {
        key: deepcopy(item) for key, item in receipt.items() if key != "receipt_sha256"
    }
    expected_hash = _sha256(projection)
    if receipt["receipt_sha256"] != expected_hash:
        raise ProtocolError("evidence_hash_mismatch", "evidence receipt was modified")
    if (
        receipt["schema_id"] != EVIDENCE_SCHEMA_ID
        or receipt["protocol_sha256"] != FROZEN_PROTOCOL_SHA256
        or receipt["source_archive_sha256"] != SOURCE_ARCHIVE_SHA256
        or receipt["roster_sha256"] != ROSTER_SHA256
        or receipt["allocation_receipt_sha256"] != FROZEN_ALLOCATION_RECEIPT_SHA256
    ):
        raise ProtocolError("evidence_binding_mismatch", "evidence is cross-wired")
    _digest(receipt["input_result_sha256"], location="evidence.input_result_sha256")
    _validate_implementation(receipt["implementation"])
    _validate_generation_boundary(receipt["generation_boundary"])
    _digest(
        receipt["case_search_receipts_sha256"],
        location="evidence.case_search_receipts_sha256",
    )
    _digest(
        receipt["candidate_proposal_and_fact_bindings_sha256"],
        location="evidence.candidate_proposal_and_fact_bindings_sha256",
    )
    _digest(
        receipt["external_posebusters_fact_receipts_sha256"],
        location="evidence.external_posebusters_fact_receipts_sha256",
    )
    _digest(
        receipt["external_rmsd_fact_receipts_sha256"],
        location="evidence.external_rmsd_fact_receipts_sha256",
    )
    if (
        receipt["external_posebusters_fact_count"] != 512
        or receipt["external_rmsd_fact_count"] != 512
    ):
        raise ProtocolError(
            "evidence_external_fact_count_mismatch",
            "all 512 RMSD and 512 PoseBusters facts are required",
        )
    expected_claim_boundary = {
        "development_only": True,
        "retrospective": True,
        "product_dispatch_authorized": False,
        "product_promotion_eligible": False,
        "public_claim_eligible": False,
        "scientific_validation_claimed": False,
    }
    if receipt["claim_boundary"] != expected_claim_boundary:
        raise ProtocolError(
            "evidence_claim_boundary_widened", "evidence widened benchmark authority"
        )
    expected_external_boundary = {
        "posebusters_validity_origin": EXTERNAL_POSEBUSTERS_FACT_ORIGIN,
        "symmetry_aware_rmsd_origin": EXTERNAL_RMSD_FACT_ORIGIN,
        "posebusters_validity_computed_here": False,
        "symmetry_aware_rmsd_computed_here": False,
        "molecular_structures_read_by_receipt_evaluator": False,
        "external_engine_invoked_by_receipt_evaluator": False,
    }
    if receipt["external_fact_boundary"] != expected_external_boundary:
        raise ProtocolError(
            "evidence_external_fact_boundary_changed",
            "evidence changed the external-fact boundary",
        )
    metrics = _sequence(receipt["case_metrics"], location="evidence.case_metrics")
    observed_case_ids = [
        row.get("case_id") if isinstance(row, Mapping) else None for row in metrics
    ]
    if observed_case_ids != list(CASE_IDS):
        raise ProtocolError("evidence_case_mismatch", "evidence case roster changed")
    normalized_metrics = [
        _validate_evidence_case_metric(row, frozen)
        for row, frozen in zip(metrics, FROZEN_CASES, strict=True)
    ]
    expected_summary = _summary(normalized_metrics)
    if receipt["summary"] != expected_summary:
        raise ProtocolError(
            "evidence_summary_mismatch", "gate summary does not rederive"
        )
    expected_decision = (
        "pass" if expected_summary["development_gate_pass"] else "blocked"
    )
    if receipt["decision"] != expected_decision:
        raise ProtocolError("evidence_decision_mismatch", "decision does not rederive")
    expected_receipt = evaluate_development_result(result)
    if canonical_json_bytes(receipt) != canonical_json_bytes(expected_receipt):
        raise ProtocolError(
            "evidence_result_mismatch",
            "evidence does not exactly rederive from the supplied complete result",
        )
    return deepcopy(dict(receipt))


def _validate_evidence_case_metric(
    value: object, frozen: FrozenCase
) -> dict[str, object]:
    row = _mapping(value, location=f"evidence.case_metrics.{frozen.case_id}")
    common = {
        "case_id",
        "source_receipt_sha256",
        "scored",
        "preparation_failure_code",
        "baseline_oracle_minimum_rmsd_angstrom",
        "rigid_lower_bound_rmsd_angstrom",
        "rigid_lower_bound_used_for_gate",
    }
    scored_only = {
        "baseline_exact_valid_candidate_count",
        "proposal_oracle_minimum_rmsd_angstrom",
        "proposal_oracle_recovered_at_or_below_2a",
        "exact_valid_candidate_count",
        "exact_valid_minimum_rmsd_angstrom",
        "exact_valid_recovered_at_or_below_2a",
        "top1_posebusters_exact_valid",
    }
    _require_exact_keys(
        row,
        common | (scored_only if frozen.scored else set()),
        location=f"evidence.case_metrics.{frozen.case_id}",
    )
    expected_frozen = {
        "case_id": frozen.case_id,
        "source_receipt_sha256": frozen.source_receipt_sha256,
        "scored": frozen.scored,
        "preparation_failure_code": frozen.preparation_failure_code,
        "baseline_oracle_minimum_rmsd_angstrom": (
            frozen.baseline_oracle_minimum_rmsd_angstrom
        ),
        "rigid_lower_bound_rmsd_angstrom": frozen.rigid_lower_bound_rmsd_angstrom,
        "rigid_lower_bound_used_for_gate": False,
    }
    if any(row[name] != expected for name, expected in expected_frozen.items()):
        raise ProtocolError(
            "evidence_case_fact_mismatch",
            f"{frozen.case_id} frozen source or diagnostic fact changed",
        )
    if not frozen.scored:
        return dict(row)
    if (
        row["baseline_exact_valid_candidate_count"]
        != frozen.baseline_exact_valid_candidate_count
    ):
        raise ProtocolError(
            "evidence_case_fact_mismatch",
            f"{frozen.case_id} baseline validity count changed",
        )
    minimum = _finite_nonnegative(
        row["proposal_oracle_minimum_rmsd_angstrom"],
        location=f"evidence.{frozen.case_id}.proposal_oracle_minimum_rmsd_angstrom",
    )
    if row["proposal_oracle_recovered_at_or_below_2a"] != (
        minimum <= RECOVERY_RMSD_ANGSTROM
    ):
        raise ProtocolError(
            "evidence_case_metric_mismatch",
            f"{frozen.case_id} proposal-oracle classification does not rederive",
        )
    count = row["exact_valid_candidate_count"]
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 64:
        raise ProtocolError(
            "evidence_case_metric_mismatch",
            f"{frozen.case_id} exact-valid count is invalid",
        )
    exact_valid_minimum_value = row["exact_valid_minimum_rmsd_angstrom"]
    if count == 0:
        if exact_valid_minimum_value is not None:
            raise ProtocolError(
                "evidence_case_metric_mismatch",
                f"{frozen.case_id} has an exact-valid minimum without a valid row",
            )
        exact_valid_minimum = None
    else:
        exact_valid_minimum = _finite_nonnegative(
            exact_valid_minimum_value,
            location=(f"evidence.{frozen.case_id}.exact_valid_minimum_rmsd_angstrom"),
        )
    for name in (
        "proposal_oracle_recovered_at_or_below_2a",
        "exact_valid_recovered_at_or_below_2a",
        "top1_posebusters_exact_valid",
    ):
        if not isinstance(row[name], bool):
            raise ProtocolError(
                "evidence_case_metric_mismatch",
                f"{frozen.case_id}.{name} is not boolean",
            )
    if row["exact_valid_recovered_at_or_below_2a"] != (
        exact_valid_minimum is not None
        and exact_valid_minimum <= RECOVERY_RMSD_ANGSTROM
    ):
        raise ProtocolError(
            "evidence_case_metric_mismatch",
            f"{frozen.case_id} exact-valid recovery does not rederive",
        )
    return dict(row)


def _assert_frozen_invariants() -> None:
    if _sha256(list(CASE_IDS)) != ROSTER_SHA256:
        raise RuntimeError("frozen cohort roster hash is invalid")
    if len(CASE_IDS) != 9 or len(SCORED_CASE_IDS) != 8:
        raise RuntimeError("frozen cohort denominator changed")
    if PREVIOUSLY_UNCOVERED_CASE_IDS != (
        "5SD5_HWI",
        "5SIS_JSM",
        "6M2B_EZO",
        "6TW5_9M2",
        "6TW7_NZB",
        "6VTA_AKN",
        "6WTN_RXT",
    ):
        raise RuntimeError("baseline recovery partition changed")


_assert_frozen_invariants()
