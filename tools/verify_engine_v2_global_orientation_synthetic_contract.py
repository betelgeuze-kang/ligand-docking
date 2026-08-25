#!/usr/bin/env python3
"""Verify the synthetic-only Engine V2 global-orientation contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping


SCHEMA_ID = "betelgeuze.engine_v2_global_orientation_synthetic_contract/2.1.0"
GENERATOR_ID = "deterministic_surface_aware_rigid_v2"
FIXTURE_SUITE_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_adversarial_fixture_suite/1.0.0"
)
FIXTURE_SUITE_PATH = "tests/fixtures/engine_v2_global_orientation_adversarial_v1.json"
GEODESIC_DUPLICATE_THRESHOLD_RADIANS = 1.0e-10
EXPECTED_SOURCE_SEED_BINDING_FIELDS = (
    "source_receipt_sha256",
    "ligand_input_sha256",
    "pocket_center_binary64_hex",
    "pocket_normal_binary64_hex",
    "profile_id",
)
EXPECTED_COVERAGE_STATISTIC_FIELDS = (
    "requested_orientation_count",
    "raw_sequence_count",
    "accepted_sequence_count",
    "duplicate_orientation_count",
    "geodesic_duplicate_tolerance_radians_binary64_hex",
    "minimum_pairwise_geodesic_distance_radians_binary64_hex",
    "mean_nearest_neighbor_geodesic_distance_radians_binary64_hex",
    "maximum_nearest_neighbor_geodesic_distance_radians_binary64_hex",
)
EXPECTED_FAILURE_CLASSES = (
    "success",
    "proposal_failure",
    "validity_failure",
    "ranking_failure",
)
FORBIDDEN_TRUE_AUTHORITY_KEYS = (
    "customer_pose_emission_authorized",
    "fresh_holdout_execution_authorized",
    "historical_ab_execution_authorized",
    "product_execution_authorized",
    "profile_promotion_authority",
    "public_or_scientific_claim_authorized",
    "stage0_admission_authority",
)
EXPECTED_ADVERSARIAL_FIXTURE_INVARIANTS = {
    "narrow_channel": (
        "failure_complete_denominator",
        "mixed_acceptance_and_receptor_clash",
        "accepted_slots_span_multiple_orientations",
    ),
    "two_lobe_pocket": (
        "failure_complete_denominator",
        "mixed_acceptance_and_receptor_clash",
        "accepted_centroids_occupy_both_lobes",
    ),
    "symmetry_decoy": (
        "failure_complete_denominator",
        "antipodal_symmetry_preserved",
        "distinct_orientation_receipts_for_symmetric_geometry",
    ),
    "mirror_decoy": (
        "failure_complete_denominator",
        "proper_rotation_preserves_chirality",
        "mirror_decoy_has_opposite_chirality",
    ),
    "tangent_placement": (
        "failure_complete_denominator",
        "shell_radius_preserved",
        "tangent_component_present",
        "normal_projection_spans_both_sides",
    ),
    "orientation_only": (
        "failure_complete_denominator",
        "single_translation_target",
        "centroid_fixed_at_pocket_center",
        "orientations_change_coordinates",
    ),
    "translation_only": (
        "failure_complete_denominator",
        "single_orientation_quaternion",
        "translation_targets_are_distinct",
        "intramolecular_distances_preserved",
    ),
}
EXPECTED_ADVERSARIAL_FIXTURE_IDS = tuple(EXPECTED_ADVERSARIAL_FIXTURE_INVARIANTS)
MAX_FIXTURE_LIGAND_ATOMS = 512
MAX_FIXTURE_RECEPTOR_SURFACE_POINTS = 4096
MAX_FIXTURE_ORIENTATIONS = 512
MAX_FIXTURE_TRANSLATION_SHELLS = 32
MAX_FIXTURE_TRANSLATION_POINTS_PER_SHELL = 256
MAX_FIXTURE_CANDIDATE_SLOTS = 65536


class GlobalOrientationSyntheticContractError(ValueError):
    """Raised when the synthetic global-orientation contract fails closed."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise GlobalOrientationSyntheticContractError(
            f"fixture suite is not readable: {exc}"
        ) from exc


def _sha256_identity(value: object, *, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise GlobalOrientationSyntheticContractError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _exact_nonnegative_int(value: object, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise GlobalOrientationSyntheticContractError(
            f"{name} must be a non-negative integer"
        )
    return value


def _bounded_positive_int(value: object, *, name: str, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise GlobalOrientationSyntheticContractError(
            f"{name} must be an integer within [1, {maximum}]"
        )
    return value


def _finite_number(value: object, *, name: str) -> float:
    if type(value) not in {int, float}:
        raise GlobalOrientationSyntheticContractError(f"{name} must be a finite number")
    observed = float(value)
    if not math.isfinite(observed):
        raise GlobalOrientationSyntheticContractError(f"{name} must be finite")
    return observed


def _vector(value: object, *, name: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise GlobalOrientationSyntheticContractError(
            f"{name} must contain exactly three values"
        )
    return tuple(
        _finite_number(component, name=f"{name}[{index}]")
        for index, component in enumerate(value)
    )  # type: ignore[return-value]


def _coordinates(
    value: object,
    *,
    name: str,
    minimum_count: int,
    maximum_count: int,
) -> tuple[tuple[float, float, float], ...]:
    if not isinstance(value, list):
        raise GlobalOrientationSyntheticContractError(f"{name} must be an array")
    if not minimum_count <= len(value) <= maximum_count:
        raise GlobalOrientationSyntheticContractError(
            f"{name} count must be within [{minimum_count}, {maximum_count}]"
        )
    return tuple(
        _vector(row, name=f"{name}[{index}]") for index, row in enumerate(value)
    )


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise GlobalOrientationSyntheticContractError(f"{name} must be an object")
    return value


def load_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GlobalOrientationSyntheticContractError(
            f"contract is not readable JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise GlobalOrientationSyntheticContractError("contract must be a JSON object")
    return payload


def load_fixture_suite(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GlobalOrientationSyntheticContractError(
            f"fixture suite is not readable JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise GlobalOrientationSyntheticContractError(
            "fixture suite must be a JSON object"
        )
    return payload


def verify_fixture_suite(suite: Mapping[str, Any]) -> str:
    if set(suite) != {
        "authority",
        "fixtures",
        "generator_id",
        "profile_id",
        "schema_id",
        "source_receipt_sha256",
        "suite_sha256",
    }:
        raise GlobalOrientationSyntheticContractError(
            "fixture suite key set is invalid"
        )
    if suite.get("schema_id") != FIXTURE_SUITE_SCHEMA_ID:
        raise GlobalOrientationSyntheticContractError("fixture suite schema is invalid")
    if suite.get("generator_id") != GENERATOR_ID:
        raise GlobalOrientationSyntheticContractError(
            "fixture suite generator identity drifted"
        )
    profile_id = suite.get("profile_id")
    if (
        type(profile_id) is not str
        or profile_id != "engine-v2-global-orientation-adversarial-v1"
    ):
        raise GlobalOrientationSyntheticContractError(
            "fixture suite profile identity drifted"
        )
    _sha256_identity(
        suite.get("source_receipt_sha256"),
        name="fixture suite source_receipt_sha256",
    )
    observed_hash = _sha256_identity(
        suite.get("suite_sha256"),
        name="fixture suite suite_sha256",
    )
    projection = dict(suite)
    projection.pop("suite_sha256", None)
    expected_hash = _sha256(projection)
    if observed_hash != expected_hash:
        raise GlobalOrientationSyntheticContractError(
            "fixture suite self-hash is invalid"
        )

    authority = _mapping(suite.get("authority"), name="fixture suite authority")
    if set(authority) != set(FORBIDDEN_TRUE_AUTHORITY_KEYS):
        raise GlobalOrientationSyntheticContractError(
            "fixture suite authority key set is invalid"
        )
    if any(authority.get(key) is not False for key in FORBIDDEN_TRUE_AUTHORITY_KEYS):
        raise GlobalOrientationSyntheticContractError(
            "fixture suite authority must remain false"
        )

    fixtures = suite.get("fixtures")
    if not isinstance(fixtures, list):
        raise GlobalOrientationSyntheticContractError(
            "fixture suite fixtures must be an array"
        )
    fixture_ids = tuple(
        fixture.get("fixture_id") if isinstance(fixture, dict) else None
        for fixture in fixtures
    )
    if fixture_ids != EXPECTED_ADVERSARIAL_FIXTURE_IDS:
        raise GlobalOrientationSyntheticContractError(
            "adversarial fixture IDs or order drifted"
        )
    fixture_keys = {
        "config",
        "expected_accepted_count",
        "expected_batch_receipt_sha256",
        "expected_candidate_slot_count",
        "expected_rejected_count",
        "fixture_id",
        "ligand_coordinates",
        "pocket_center",
        "pocket_normal",
        "receptor_surface_points",
        "required_invariants",
    }
    config_keys = {
        "minimum_receptor_distance",
        "orientation_count",
        "translation_points_per_shell",
        "translation_shell_radii",
    }
    for fixture in fixtures:
        fixture_id = fixture["fixture_id"]
        if set(fixture) != fixture_keys:
            raise GlobalOrientationSyntheticContractError(
                f"fixture key set is invalid for {fixture_id}"
            )
        config = _mapping(fixture.get("config"), name=f"{fixture_id} config")
        if set(config) != config_keys:
            raise GlobalOrientationSyntheticContractError(
                f"fixture config key set is invalid for {fixture_id}"
            )
        orientation_count = _bounded_positive_int(
            config.get("orientation_count"),
            name=f"{fixture_id} orientation_count",
            maximum=MAX_FIXTURE_ORIENTATIONS,
        )
        translation_points = _bounded_positive_int(
            config.get("translation_points_per_shell"),
            name=f"{fixture_id} translation_points_per_shell",
            maximum=MAX_FIXTURE_TRANSLATION_POINTS_PER_SHELL,
        )
        radii_value = config.get("translation_shell_radii")
        if not isinstance(radii_value, list):
            raise GlobalOrientationSyntheticContractError(
                f"{fixture_id} translation_shell_radii must be an array"
            )
        if len(radii_value) > MAX_FIXTURE_TRANSLATION_SHELLS:
            raise GlobalOrientationSyntheticContractError(
                f"{fixture_id} has too many translation shells"
            )
        radii = tuple(
            _finite_number(radius, name=f"{fixture_id} translation_shell_radii")
            for radius in radii_value
        )
        if any(radius <= 0.0 for radius in radii):
            raise GlobalOrientationSyntheticContractError(
                f"{fixture_id} translation shell radii must be positive"
            )
        if tuple(sorted(set(radii))) != radii:
            raise GlobalOrientationSyntheticContractError(
                f"{fixture_id} translation shell radii must be unique and increasing"
            )
        minimum_distance = _finite_number(
            config.get("minimum_receptor_distance"),
            name=f"{fixture_id} minimum_receptor_distance",
        )
        if minimum_distance < 0.0:
            raise GlobalOrientationSyntheticContractError(
                f"{fixture_id} minimum_receptor_distance must be non-negative"
            )
        derived_candidate_count = orientation_count * (
            1 + len(radii) * translation_points
        )
        if derived_candidate_count > MAX_FIXTURE_CANDIDATE_SLOTS:
            raise GlobalOrientationSyntheticContractError(
                f"{fixture_id} candidate slot count exceeds the cap"
            )
        candidate_count = _exact_nonnegative_int(
            fixture.get("expected_candidate_slot_count"),
            name=f"{fixture_id} expected_candidate_slot_count",
        )
        if candidate_count != derived_candidate_count:
            raise GlobalOrientationSyntheticContractError(
                f"fixture candidate count does not match config for {fixture_id}"
            )
        accepted_count = _exact_nonnegative_int(
            fixture.get("expected_accepted_count"),
            name=f"{fixture_id} expected_accepted_count",
        )
        rejected_count = _exact_nonnegative_int(
            fixture.get("expected_rejected_count"),
            name=f"{fixture_id} expected_rejected_count",
        )
        if accepted_count + rejected_count != candidate_count:
            raise GlobalOrientationSyntheticContractError(
                f"fixture denominator counts do not reconcile for {fixture_id}"
            )
        _sha256_identity(
            fixture.get("expected_batch_receipt_sha256"),
            name=f"{fixture_id} expected_batch_receipt_sha256",
        )
        if (
            tuple(fixture.get("required_invariants", ()))
            != (EXPECTED_ADVERSARIAL_FIXTURE_INVARIANTS[fixture_id])
        ):
            raise GlobalOrientationSyntheticContractError(
                f"fixture invariant set drifted for {fixture_id}"
            )
        _coordinates(
            fixture.get("ligand_coordinates"),
            name=f"{fixture_id} ligand_coordinates",
            minimum_count=2,
            maximum_count=MAX_FIXTURE_LIGAND_ATOMS,
        )
        _coordinates(
            fixture.get("receptor_surface_points"),
            name=f"{fixture_id} receptor_surface_points",
            minimum_count=0,
            maximum_count=MAX_FIXTURE_RECEPTOR_SURFACE_POINTS,
        )
        _vector(fixture.get("pocket_center"), name=f"{fixture_id} pocket_center")
        pocket_normal = _vector(
            fixture.get("pocket_normal"), name=f"{fixture_id} pocket_normal"
        )
        if sum(component * component for component in pocket_normal) == 0.0:
            raise GlobalOrientationSyntheticContractError(
                f"{fixture_id} pocket_normal must be non-zero"
            )
    return expected_hash


def verify_contract(
    contract: Mapping[str, Any],
    *,
    repository_root: Path | None = None,
) -> str:
    expected_keys = {
        "algorithm",
        "adversarial_fixture_suite",
        "authority",
        "contract_sha256",
        "metrics",
        "orientation_receipt",
        "schema_id",
        "status",
    }
    if set(contract) != expected_keys:
        raise GlobalOrientationSyntheticContractError("contract key set is invalid")
    if contract.get("schema_id") != SCHEMA_ID:
        raise GlobalOrientationSyntheticContractError("contract schema is invalid")
    if contract.get("status") != "implemented_synthetic_validation_only":
        raise GlobalOrientationSyntheticContractError("synthetic-only status drifted")
    observed_hash = contract.get("contract_sha256")
    projection = dict(contract)
    projection.pop("contract_sha256", None)
    expected_hash = _sha256(projection)
    if observed_hash != expected_hash:
        raise GlobalOrientationSyntheticContractError("contract self-hash is invalid")

    algorithm = _mapping(contract.get("algorithm"), name="algorithm")
    if set(algorithm) != {
        "candidate_denominator_failure_complete",
        "generator_id",
        "index_stable_orientation_sequence_required",
        "native_pose_input_allowed",
        "orientation_count_prefix_invariant_required",
        "receptor_surface_prefilter_allowed",
        "score_feedback_input_allowed",
        "source_dependent_seed_required",
        "source_rederivation_evidence_required",
        "synthetic_contract_only",
    }:
        raise GlobalOrientationSyntheticContractError("algorithm key set is invalid")
    if algorithm.get("generator_id") != GENERATOR_ID:
        raise GlobalOrientationSyntheticContractError("generator identity drifted")
    for required_true in (
        "candidate_denominator_failure_complete",
        "index_stable_orientation_sequence_required",
        "orientation_count_prefix_invariant_required",
        "receptor_surface_prefilter_allowed",
        "source_dependent_seed_required",
        "source_rederivation_evidence_required",
        "synthetic_contract_only",
    ):
        if algorithm.get(required_true) is not True:
            raise GlobalOrientationSyntheticContractError(
                f"{required_true} must remain true"
            )

    fixture_contract = _mapping(
        contract.get("adversarial_fixture_suite"),
        name="adversarial_fixture_suite",
    )
    if set(fixture_contract) != {
        "exact_batch_receipts_required",
        "failure_complete_denominators_required",
        "fixture_file_path",
        "fixture_file_sha256",
        "invariant_rederivation_required",
        "ordered_fixture_ids",
        "schema_id",
        "synthetic_inputs_only",
    }:
        raise GlobalOrientationSyntheticContractError(
            "adversarial fixture suite key set is invalid"
        )
    if fixture_contract.get("schema_id") != FIXTURE_SUITE_SCHEMA_ID:
        raise GlobalOrientationSyntheticContractError(
            "adversarial fixture suite schema drifted"
        )
    if fixture_contract.get("fixture_file_path") != FIXTURE_SUITE_PATH:
        raise GlobalOrientationSyntheticContractError(
            "adversarial fixture suite path drifted"
        )
    if tuple(fixture_contract.get("ordered_fixture_ids", ())) != (
        EXPECTED_ADVERSARIAL_FIXTURE_IDS
    ):
        raise GlobalOrientationSyntheticContractError(
            "adversarial fixture contract IDs drifted"
        )
    for required_true in (
        "exact_batch_receipts_required",
        "failure_complete_denominators_required",
        "invariant_rederivation_required",
        "synthetic_inputs_only",
    ):
        if fixture_contract.get(required_true) is not True:
            raise GlobalOrientationSyntheticContractError(
                f"{required_true} must remain true"
            )
    root = repository_root or Path(__file__).resolve().parents[1]
    fixture_path = root / FIXTURE_SUITE_PATH
    observed_fixture_file_sha256 = _sha256_identity(
        fixture_contract.get("fixture_file_sha256"),
        name="adversarial fixture file SHA-256",
    )
    if _sha256_file(fixture_path) != observed_fixture_file_sha256:
        raise GlobalOrientationSyntheticContractError(
            "adversarial fixture file SHA-256 drifted"
        )
    verify_fixture_suite(load_fixture_suite(fixture_path))
    for forbidden_input in (
        "native_pose_input_allowed",
        "score_feedback_input_allowed",
    ):
        if algorithm.get(forbidden_input) is not False:
            raise GlobalOrientationSyntheticContractError(
                f"{forbidden_input} must remain false"
            )

    orientation_receipt = _mapping(
        contract.get("orientation_receipt"),
        name="orientation_receipt",
    )
    if set(orientation_receipt) != {
        "accepted_sequence_indices_required",
        "canonical_quaternion_binary64_hex_required",
        "coverage_statistic_fields",
        "coverage_statistics_required",
        "duplicate_statistics_required",
        "geodesic_duplicate_threshold_radians_binary64_hex",
        "quaternion_sign_canonicalization_required",
        "raw_sequence_indices_required",
        "source_seed_binding_fields",
        "source_seed_sha256_required",
    }:
        raise GlobalOrientationSyntheticContractError(
            "orientation receipt key set is invalid"
        )
    for required_true in (
        "accepted_sequence_indices_required",
        "canonical_quaternion_binary64_hex_required",
        "coverage_statistics_required",
        "duplicate_statistics_required",
        "quaternion_sign_canonicalization_required",
        "raw_sequence_indices_required",
        "source_seed_sha256_required",
    ):
        if orientation_receipt.get(required_true) is not True:
            raise GlobalOrientationSyntheticContractError(
                f"{required_true} must remain true"
            )
    if tuple(orientation_receipt.get("source_seed_binding_fields", ())) != (
        EXPECTED_SOURCE_SEED_BINDING_FIELDS
    ):
        raise GlobalOrientationSyntheticContractError(
            "source seed binding fields drifted"
        )
    if tuple(orientation_receipt.get("coverage_statistic_fields", ())) != (
        EXPECTED_COVERAGE_STATISTIC_FIELDS
    ):
        raise GlobalOrientationSyntheticContractError(
            "coverage statistic fields drifted"
        )
    encoded_threshold = orientation_receipt.get(
        "geodesic_duplicate_threshold_radians_binary64_hex"
    )
    if type(encoded_threshold) is not str:
        raise GlobalOrientationSyntheticContractError(
            "geodesic duplicate threshold must be binary64 hex"
        )
    try:
        observed_threshold = float.fromhex(encoded_threshold)
    except ValueError as exc:
        raise GlobalOrientationSyntheticContractError(
            "geodesic duplicate threshold must be binary64 hex"
        ) from exc
    if observed_threshold != GEODESIC_DUPLICATE_THRESHOLD_RADIANS:
        raise GlobalOrientationSyntheticContractError(
            "geodesic duplicate threshold drifted"
        )

    authority = _mapping(contract.get("authority"), name="authority")
    if set(authority) != set(FORBIDDEN_TRUE_AUTHORITY_KEYS):
        raise GlobalOrientationSyntheticContractError("authority key set is invalid")
    for key in FORBIDDEN_TRUE_AUTHORITY_KEYS:
        if authority.get(key) is not False:
            raise GlobalOrientationSyntheticContractError(f"{key} must remain false")

    metrics = _mapping(contract.get("metrics"), name="metrics")
    if set(metrics) != {
        "failure_classes",
        "full_observation_rederivation_required",
        "proposal_oracle_and_selection_separated",
        "selection_regret_reported",
        "top_k_ranked_oracle_reported",
    }:
        raise GlobalOrientationSyntheticContractError("metrics key set is invalid")
    if tuple(metrics.get("failure_classes", ())) != EXPECTED_FAILURE_CLASSES:
        raise GlobalOrientationSyntheticContractError("failure class order drifted")
    for required_true in (
        "full_observation_rederivation_required",
        "proposal_oracle_and_selection_separated",
        "selection_regret_reported",
        "top_k_ranked_oracle_reported",
    ):
        if metrics.get(required_true) is not True:
            raise GlobalOrientationSyntheticContractError(
                f"{required_true} must remain true"
            )
    return expected_hash


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "config/engine_v2_global_orientation_synthetic_contract.json"
        ),
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    print(
        verify_contract(
            load_contract(arguments.contract),
            repository_root=arguments.contract.resolve().parent.parent,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
