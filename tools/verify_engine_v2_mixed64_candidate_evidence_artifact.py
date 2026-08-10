#!/usr/bin/env python3
"""Replay a persisted mixed64 candidate-evidence artifact from canonical JSON.

This verifier intentionally does not import the producers it audits.  It
replays allocation, geometric admission, candidate lifecycle, and ranking from
the persisted receipt payload.  It grants no execution or scientific
authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, Final


MAX_ARTIFACT_BYTES: Final = 64 * 1024 * 1024
MAX_JSON_DEPTH: Final = 64
MAX_JSON_NODES: Final = 500_000
MAX_JSON_SEQUENCE_ITEMS: Final = 150_000
MAX_JSON_MAPPING_ITEMS: Final = 25_000
MAX_JSON_STRING_BYTES: Final = 4 * 1024 * 1024
MAX_JSON_KEY_BYTES: Final = 256
MAX_ABSOLUTE_JSON_INTEGER: Final = (1 << 53) - 1
MAX_LIGAND_ATOMS: Final = 512
MAX_RECEPTOR_ATOMS: Final = 4096
MAX_TOTAL_FEATURE_ATOM_REFERENCES: Final = 65_536
MAX_BATCH_EXACT_PAIR_EVALUATIONS: Final = 16_777_216
MAX_ABSOLUTE_COORDINATE_ANGSTROM: Final = 100_000.0
MIN_VDW_RADIUS_ANGSTROM: Final = 0.1
MAX_VDW_RADIUS_ANGSTROM: Final = 10.0
MAX_POCKET_RADIUS_ANGSTROM: Final = 1_000.0
HARD_REJECTION_MINIMUM_VDW_RATIO: Final = 0.55
TOP_K_LIMIT: Final = 5
AUTHORITY_LIKE_KEY_TOKENS: Final = frozenset(
    {
        "admissible", "admission", "admitted", "allowed", "approved",
        "attested", "authority",
        "authorization", "authorized", "calibrated", "certified", "claim",
        "claimable",
        "eligible", "eligibility", "execution", "fresh", "granted",
        "molecular", "official", "permitted", "production", "promotion",
        "promotable", "public",
        "scientific", "stage0", "validated",
    }
)
DENOMINATOR_FAILURE_COMPLETENESS_SCOPE: Final = (
    "allocation_and_supported_post_proposal_structural_stages_only"
)

PROFILE_ID: Final = "betelgeuze.engine_v2_global_orientation_fixed_mixed64/1.0.0"
ALLOCATION_SCHEMA: Final = (
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_allocation/2.0.0"
)
SLOT_SCHEMA: Final = (
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_slot/2.0.0"
)
FEATURE_SCHEMA: Final = (
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_feature_evidence/3.0.0"
)
ATOMIC_FEATURE_SCHEMA: Final = (
    "betelgeuze.engine_v2_global_orientation_atomic_feature/1.0.0"
)
CONFORMER_SCHEMA: Final = (
    "betelgeuze.engine_v2_global_orientation_conformer_source/1.0.0"
)
V7_CONTROL_SCHEMA: Final = (
    "betelgeuze.engine_v2_global_orientation_v7_control_source/2.0.0"
)
RETAINED_SCHEMA: Final = (
    "betelgeuze.engine_v2_global_orientation_retained_source/1.0.0"
)
RETAINED_NAMESPACE: Final = "current_v7_source_proposal_index"
V7_CONTROL_NAMESPACE: Final = "current_v7_source_proposal_index"
V7_CONTROL_MODE_POCKET_CENTERED: Final = "pocket_centered_control"
V7_CONTROL_MODE_UNIFORM_SOURCE: Final = "uniform_source_control"
GENERATION_PARENT_EXACT_PASSTHROUGH: Final = "exact_passthrough_parent"
GENERATION_PARENT_GENERATOR_INPUT: Final = "generator_input_parent"
GEOMETRIC_COMPONENT: Final = "betelgeuze.engine_v2_geometric_admission_v2/2.0.0"
GEOMETRIC_BATCH_SCHEMA: Final = (
    "betelgeuze.engine_v2_geometric_admission_v2_batch/2.0.0"
)
GEOMETRIC_INPUT_SCHEMA: Final = (
    "betelgeuze.engine_v2_geometric_admission_v2_exact_inputs/1.0.0"
)
GEOMETRIC_DECISION_SCHEMA: Final = (
    "betelgeuze.engine_v2_geometric_admission_v2_decision/2.0.0"
)
GEOMETRIC_METRICS_SCHEMA: Final = (
    "betelgeuze.engine_v2_geometric_admission_v2_metrics/2.0.0"
)
PIPELINE_BATCH_SCHEMA: Final = (
    "betelgeuze.engine_v2_pipeline_candidate_evidence_batch_v2/1.0.0"
)
PIPELINE_CANDIDATE_SCHEMA: Final = (
    "betelgeuze.engine_v2_pipeline_candidate_evidence_v2/1.0.0"
)
PIPELINE_BUILDER: Final = (
    "betelgeuze.engine_v2_pipeline_candidate_evidence_v2_builder/1.0.0"
)
PROPOSAL_SCHEMA: Final = (
    "betelgeuze.engine_v2_mixed64_proposal_execution_receipt_v2/1.0.0"
)
SCORER_BINDING_SCHEMA: Final = (
    "betelgeuze.engine_v2_pipeline_scorer_v1_evidence_binding_v2/1.0.0"
)
SCORER_TERMS_SCHEMA: Final = "betelgeuze.engine_v2_scorer_v1_terms/1.1.0"
SCORER_SCORE_ID: Final = "betelgeuze.engine_v2_chemistry_pose_scorer/1.0.0"
VALIDITY_SCHEMA: Final = (
    "betelgeuze.engine_v2_pipeline_pose_validity_receipt_v2/1.0.0"
)
REFINEMENT_SCHEMA: Final = (
    "betelgeuze.engine_v2_pipeline_refinement_receipt_binding_v2/1.0.0"
)
REFINEMENT_SOURCE_IDENTITY_SCHEMA: Final = (
    "betelgeuze.engine_v2_pipeline_refinement_source_receipt_identity_v2/1.0.0"
)
ALLOWED_REFINEMENT_SOURCE_SCHEMAS: Final = frozenset(
    {
        "betelgeuze.engine_v2_interaction_aware_torsion_contact_receipt/7.0.0",
        "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.1.0",
        "betelgeuze.engine_v2_interaction_aware_torsion_clearance_receipt/8.0.0",
    }
)

PAIR_TRAVERSAL_ORDER: Final = (
    "full_cartesian_ligand_index_major_receptor_index_minor"
)
OVERLAP_DEFINITION: Final = (
    "sum_of_pairwise_vdw_sphere_intersection_volumes_angstrom3"
)
ESCAPE_DEFINITION: Final = (
    "max_zero_or_ligand_center_distance_plus_vdw_radius_minus_pocket_radius"
)

LANE_RANGES: Final = (
    ("pocket_centered_controls", 0, 7),
    ("uniform_source_controls", 8, 23),
    ("deterministic_independent_so3", 24, 35),
    ("true_conformer_independent_so3", 36, 43),
    ("ligand_donor_to_receptor_acceptor", 44, 47),
    ("ligand_acceptor_to_receptor_donor", 48, 51),
    ("complementary_charge", 52, 55),
    ("aromatic_plane", 56, 57),
    ("principal_axis_shape", 58, 59),
    ("paired_retained_controls", 60, 63),
)
RETAINED_INDICES: Final = (36, 45, 54, 63)
V7_CONTROL_INDICES: Final = tuple(range(24))
TRUE_CONFORMER_RANKS: Final = (2, 3, 4, 5, 6, 7, 8)
TRUE_CONFORMER_SLOT_RANKS: Final = (2, 3, 4, 5, 6, 7, 8, 2)

FEATURE_KINDS: Final = frozenset(
    {
        "ligand_donor",
        "ligand_acceptor",
        "receptor_donor",
        "receptor_acceptor",
        "ligand_positive_site",
        "ligand_negative_site",
        "receptor_positive_site",
        "receptor_negative_site",
        "ligand_aromatic_plane",
        "receptor_aromatic_plane",
        "ligand_shape_axis",
        "pocket_shape_axis",
    }
)
REQUIRED_VALIDITY_CHECKS: Final = frozenset(
    {
        "proper_rotation",
        "bond_lengths_preserved",
        "ligand_self_clash_free",
        "receptor_ligand_clash_free",
        "declared_chirality_preserved",
        "inside_declared_pocket",
        "element_vdw_ligand_overlap_free",
        "element_vdw_receptor_overlap_free",
    }
)
TERM_NAMES: Final = (
    "typed_vdw",
    "electrostatics",
    "directional_hbond",
    "hydrophobic_contact",
    "desolvation_proxy",
    "torsion_energy",
    "ligand_strain",
    "weak_pocket_prior",
)
EXECUTION_FAILURE_STAGES: Final = frozenset({"refinement", "scoring", "validity"})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FAILURE_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{2,127}$")
ACTIVATION_EVIDENCE_BLOCKERS: Final = (
    "uniform_source_control_lineage_not_rederived",
    "independent_so3_base_source_not_bound",
    "independent_so3_orientation_receipt_not_implemented",
    "single_anchor_placement_receipt_not_implemented",
    "proposal_generation_failure_receipt_not_implemented",
    "post_refinement_geometric_admission_not_implemented",
    "source_parent_payload_rederivation_not_implemented",
    "producer_attestation_not_implemented",
    "score_term_reexecution_not_implemented",
    "pose_validity_reexecution_not_implemented",
)


class ArtifactVerificationError(ValueError):
    """The persisted evidence failed independent replay."""


def _fail(path: str, message: str) -> None:
    raise ArtifactVerificationError(f"{path}: {message}")


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ArtifactVerificationError("value is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactVerificationError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _parse_int(value: str) -> int:
    digits = value[1:] if value.startswith("-") else value
    if len(digits) > 16:
        raise ArtifactVerificationError("JSON integer exceeds bounded precision")
    try:
        observed = int(value)
    except ValueError as exc:
        raise ArtifactVerificationError(
            "JSON integer is not canonical"
        ) from exc
    if abs(observed) > MAX_ABSOLUTE_JSON_INTEGER:
        raise ArtifactVerificationError("JSON integer exceeds bounded precision")
    return observed


def _parse_float(value: str) -> float:
    observed = float(value)
    if not math.isfinite(observed):
        raise ArtifactVerificationError("JSON contains a non-finite number")
    return observed


def _utf8_length(value: str, path: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError:
        _fail(path, "contains a non-Unicode-scalar string")


def _bounded_json(value: object) -> None:
    nodes = 0
    stack: list[tuple[object, int, str]] = [(value, 0, "$")]
    while stack:
        item, depth, path = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            _fail(path, "JSON node capacity exceeded")
        if depth > MAX_JSON_DEPTH:
            _fail(path, "JSON depth capacity exceeded")
        if isinstance(item, dict):
            if len(item) > MAX_JSON_MAPPING_ITEMS:
                _fail(path, "JSON mapping capacity exceeded")
            for key, nested in item.items():
                if type(key) is not str or not key or key != key.strip():
                    _fail(path, "non-canonical JSON mapping key")
                if _utf8_length(key, path) > MAX_JSON_KEY_BYTES:
                    _fail(path, "oversized JSON mapping key")
                stack.append((nested, depth + 1, f"$.{key}"))
        elif isinstance(item, list):
            if len(item) > MAX_JSON_SEQUENCE_ITEMS:
                _fail(path, "JSON sequence capacity exceeded")
            for index, nested in enumerate(item):
                stack.append((nested, depth + 1, f"$[{index}]"))
        elif item is None or type(item) in {bool, int, float}:
            if type(item) is float and not math.isfinite(item):
                _fail(path, "non-finite JSON number")
        elif type(item) is str:
            if _utf8_length(item, path) > MAX_JSON_STRING_BYTES:
                _fail(path, "oversized JSON string")
        else:
            _fail(path, "unsupported JSON value")


def load_artifact(path: Path) -> tuple[dict[str, object], bytes]:
    descriptor: int | None = None
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0),
        )
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ArtifactVerificationError("artifact must be a regular file")
        if metadata.st_size < 1 or metadata.st_size > MAX_ARTIFACT_BYTES:
            raise ArtifactVerificationError(
                "artifact byte size is outside the fixed bound"
            )
        chunks: list[bytes] = []
        remaining = MAX_ARTIFACT_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
    except ArtifactVerificationError:
        raise
    except OSError as exc:
        raise ArtifactVerificationError(f"cannot read artifact: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if not raw or len(raw) > MAX_ARTIFACT_BYTES:
        raise ArtifactVerificationError("artifact byte size is outside the fixed bound")
    try:
        document = json.loads(
            raw,
            object_pairs_hook=_pairs_hook,
            parse_int=_parse_int,
            parse_float=_parse_float,
            parse_constant=lambda value: (_fail("$", f"invalid constant {value}")),
        )
    except ArtifactVerificationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ArtifactVerificationError(f"artifact is not bounded canonical JSON: {exc}") from exc
    if type(document) is not dict:
        raise ArtifactVerificationError("artifact root must be a JSON object")
    _bounded_json(document)
    expected = _canonical_bytes(document) + b"\n"
    if raw != expected:
        raise ArtifactVerificationError(
            "artifact bytes must be exact sorted canonical one-line JSON plus LF"
        )
    return document, raw


def _mapping(value: object, path: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail(path, "must be an exact JSON object")
    return value


def _sequence(value: object, path: str, *, length: int | None = None) -> list[object]:
    if type(value) is not list:
        _fail(path, "must be an exact JSON array")
    if length is not None and len(value) != length:
        _fail(path, f"must contain exactly {length} values")
    return value


def _exact_keys(document: dict[str, object], expected: set[str], path: str) -> None:
    if set(document) != expected:
        missing = sorted(expected - set(document))
        extra = sorted(set(document) - expected)
        _fail(path, f"schema keys changed (missing={missing}, extra={extra})")


def _digest(value: object, path: str) -> str:
    if type(value) is not str or SHA256_RE.fullmatch(value) is None:
        _fail(path, "must be an exact lowercase SHA-256")
    return value


def _exact_bool(value: object, path: str, expected: bool | None = None) -> bool:
    if type(value) is not bool:
        _fail(path, "must be an exact boolean")
    if expected is not None and value is not expected:
        _fail(path, f"must be {expected}")
    return value


def _exact_int(
    value: object,
    path: str,
    *,
    minimum: int = 0,
    maximum: int = 2**53 - 1,
) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        _fail(path, f"must be an integer in [{minimum}, {maximum}]")
    return value


def _exact_string(value: object, path: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        _fail(path, "must be an exact non-empty string")
    return value


def _float_hex(value: object, path: str) -> float:
    if type(value) is not str:
        _fail(path, "must be a canonical binary64 hex string")
    try:
        observed = float.fromhex(value)
    except (ValueError, OverflowError) as exc:
        raise ArtifactVerificationError(
            f"{path}: invalid binary64 hex string"
        ) from exc
    if not math.isfinite(observed) or observed.hex() != value:
        _fail(path, "must be finite canonical binary64 hex")
    return observed


def _verify_receipt(document: dict[str, object], path: str) -> str:
    receipt = _digest(document.get("receipt_sha256"), f"{path}.receipt_sha256")
    projection = dict(document)
    projection.pop("receipt_sha256")
    if _sha256(projection) != receipt:
        _fail(path, "receipt SHA-256 does not rederive")
    return receipt


def _verify_all_receipts(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        if "receipt_sha256" in value:
            _verify_receipt(value, path)
        for key, nested in value.items():
            _verify_all_receipts(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _verify_all_receipts(nested, f"{path}[{index}]")


def _require_false_authority(value: object, path: str = "$") -> None:
    false_names = {
        "calibrated",
        "claim_safe",
        "producer_attested",
        "scientifically_validated",
        "stage0_admission_authority",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            if (
                key in false_names
                or key.endswith("_authorized")
                or key.endswith("_claim_authorized")
            ):
                _exact_bool(nested, f"{path}.{key}", False)
            _require_false_authority(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _require_false_authority(nested, f"{path}[{index}]")


def _require_false_nested_source_authority(value: object, path: str) -> None:
    exact_names = {
        "calibrated",
        "claim_safe",
        "producer_attested",
        "scientifically_validated",
        "stage0_admission_authority",
        "profile_promotion_authority",
    }
    if isinstance(value, dict):
        for key, nested in value.items():
            authority_like_true = nested is True and bool(
                AUTHORITY_LIKE_KEY_TOKENS.intersection(key.split("_"))
            )
            if (
                key in exact_names
                or key.endswith("_authorized")
                or key.endswith("_claim_authorized")
                or key.endswith("_authority")
                or key.endswith("_eligible")
                or key.endswith("_admissible")
                or authority_like_true
            ):
                _exact_bool(nested, f"{path}.{key}", False)
            _require_false_nested_source_authority(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _require_false_nested_source_authority(
                nested,
                f"{path}[{index}]",
            )


def _verify_atomic_feature(row: object, path: str) -> dict[str, object]:
    document = _mapping(row, path)
    _exact_keys(
        document,
        {
            "schema_id",
            "kind",
            "atom_indices",
            "source_receipt_sha256",
            "geometry_receipt_sha256",
            "result_fields_consumed",
            "receipt_sha256",
        },
        path,
    )
    if document["schema_id"] != ATOMIC_FEATURE_SCHEMA:
        _fail(f"{path}.schema_id", "atomic-feature schema changed")
    kind = _exact_string(document["kind"], f"{path}.kind")
    if kind not in FEATURE_KINDS:
        _fail(f"{path}.kind", "feature kind is not frozen")
    indices = _sequence(document["atom_indices"], f"{path}.atom_indices")
    if not indices or len(indices) > MAX_RECEPTOR_ATOMS:
        _fail(f"{path}.atom_indices", "atom-index capacity is invalid")
    parsed = [
        _exact_int(value, f"{path}.atom_indices[{index}]")
        for index, value in enumerate(indices)
    ]
    if len(set(parsed)) != len(parsed):
        _fail(f"{path}.atom_indices", "atom indices must be unique")
    if kind in {"ligand_donor", "receptor_donor"} and len(parsed) != 2:
        _fail(path, "donor evidence must identify donor plus attached hydrogen")
    if kind in {"ligand_acceptor", "receptor_acceptor"} and len(parsed) != 1:
        _fail(path, "acceptor evidence must identify one atom")
    if kind in {"ligand_aromatic_plane", "receptor_aromatic_plane"} and len(parsed) < 3:
        _fail(path, "aromatic-plane evidence needs at least three atoms")
    _digest(document["source_receipt_sha256"], f"{path}.source_receipt_sha256")
    _digest(document["geometry_receipt_sha256"], f"{path}.geometry_receipt_sha256")
    _exact_bool(document["result_fields_consumed"], f"{path}.result_fields_consumed", False)
    _verify_receipt(document, path)
    return document


def _verify_features(value: object, path: str) -> dict[str, Any]:
    document = _mapping(value, path)
    expected_keys = {
        "schema_id",
        "exact_v11_source_receipt_sha256",
        "prepared_ligand_topology_sha256",
        "prepared_receptor_topology_sha256",
        "feature_extractor_policy_sha256",
        "true_conformer_available",
        "ligand_donor_available",
        "ligand_acceptor_available",
        "receptor_donor_available",
        "receptor_acceptor_available",
        "ligand_positive_site_available",
        "ligand_negative_site_available",
        "receptor_positive_site_available",
        "receptor_negative_site_available",
        "complementary_charge_anchor_available",
        "ligand_aromatic_plane_available",
        "receptor_aromatic_plane_available",
        "ligand_shape_axis_available",
        "pocket_shape_axis_available",
        "retained_source_indices_available",
        "v7_control_source_indices_available",
        "atomic_feature_receipt_sha256s",
        "atomic_features",
        "v7_control_source_receipt_sha256s",
        "v7_control_sources",
        "conformer_source_receipt_sha256s",
        "conformer_sources",
        "retained_source_receipt_sha256s",
        "retained_sources",
        "availability_caller_supplied",
        "result_fields_consumed",
        "receipt_sha256",
    }
    _exact_keys(document, expected_keys, path)
    if document["schema_id"] != FEATURE_SCHEMA:
        _fail(f"{path}.schema_id", "feature-evidence schema changed")
    for key in (
        "exact_v11_source_receipt_sha256",
        "prepared_ligand_topology_sha256",
        "prepared_receptor_topology_sha256",
        "feature_extractor_policy_sha256",
    ):
        _digest(document[key], f"{path}.{key}")

    atomic_rows = _sequence(document["atomic_features"], f"{path}.atomic_features")
    if len(atomic_rows) > len(FEATURE_KINDS) * 256:
        _fail(f"{path}.atomic_features", "feature capacity exceeded")
    atomic = [
        _verify_atomic_feature(row, f"{path}.atomic_features[{index}]")
        for index, row in enumerate(atomic_rows)
    ]
    if (
        sum(len(row["atom_indices"]) for row in atomic)
        > MAX_TOTAL_FEATURE_ATOM_REFERENCES
    ):
        _fail(path, "total atomic feature references exceed fixed capacity")
    atomic_receipts = [str(row["receipt_sha256"]) for row in atomic]
    if atomic_receipts != document["atomic_feature_receipt_sha256s"]:
        _fail(path, "atomic feature receipt list is cross-wired")
    if len(set(atomic_receipts)) != len(atomic_receipts):
        _fail(path, "atomic feature receipts are duplicated")
    if atomic != sorted(atomic, key=lambda row: (str(row["kind"]), str(row["receipt_sha256"]))):
        _fail(path, "atomic features are not canonically ordered")
    by_kind = {
        kind: [row for row in atomic if row["kind"] == kind] for kind in FEATURE_KINDS
    }
    if any(len(rows) > 256 for rows in by_kind.values()):
        _fail(path, "per-kind feature capacity exceeded")

    v7_rows = _sequence(
        document["v7_control_sources"],
        f"{path}.v7_control_sources",
    )
    if len(v7_rows) > len(V7_CONTROL_INDICES):
        _fail(f"{path}.v7_control_sources", "V7 control-source capacity exceeded")
    v7_controls: dict[int, dict[str, object]] = {}
    v7_receipts: list[str] = []
    observed_v7_indices: list[int] = []
    for index, row in enumerate(v7_rows):
        row_path = f"{path}.v7_control_sources[{index}]"
        item = _mapping(row, row_path)
        _exact_keys(
            item,
            {
                "schema_id",
                "source_namespace",
                "source_index",
                "proposal_mode",
                "proposal_sha256",
                "coordinate_sha256",
                "proposal_lineage_sha256",
                "source_receipt_sha256",
                "generation_parent_role",
                "receipt_sha256",
            },
            row_path,
        )
        if (
            item["schema_id"] != V7_CONTROL_SCHEMA
            or item["source_namespace"] != V7_CONTROL_NAMESPACE
            or item["generation_parent_role"]
            != GENERATION_PARENT_EXACT_PASSTHROUGH
        ):
            _fail(row_path, "V7 control-source schema, namespace, or role changed")
        source_index = _exact_int(
            item["source_index"],
            f"{row_path}.source_index",
            maximum=23,
        )
        if source_index not in V7_CONTROL_INDICES or source_index in v7_controls:
            _fail(row_path, "V7 control source is duplicated or unfrozen")
        expected_mode = (
            V7_CONTROL_MODE_POCKET_CENTERED
            if source_index < 8
            else V7_CONTROL_MODE_UNIFORM_SOURCE
        )
        if item["proposal_mode"] != expected_mode:
            _fail(row_path, "V7 control proposal mode disagrees with its frozen lane")
        for key in (
            "proposal_sha256",
            "coordinate_sha256",
            "proposal_lineage_sha256",
            "source_receipt_sha256",
        ):
            _digest(item[key], f"{row_path}.{key}")
        receipt = _verify_receipt(item, row_path)
        v7_controls[source_index] = item
        v7_receipts.append(receipt)
        observed_v7_indices.append(source_index)
    if observed_v7_indices != sorted(observed_v7_indices):
        _fail(path, "V7 control sources are not index sorted")
    if v7_receipts != document["v7_control_source_receipt_sha256s"]:
        _fail(path, "V7 control receipt list is cross-wired")
    if observed_v7_indices != document["v7_control_source_indices_available"]:
        _fail(path, "V7 control-source availability does not rederive")

    conformer_rows = _sequence(document["conformer_sources"], f"{path}.conformer_sources")
    if len(conformer_rows) > len(TRUE_CONFORMER_RANKS):
        _fail(f"{path}.conformer_sources", "conformer-source capacity exceeded")
    conformers: dict[int, dict[str, object]] = {}
    conformer_receipts: list[str] = []
    observed_ranks: list[int] = []
    for index, row in enumerate(conformer_rows):
        row_path = f"{path}.conformer_sources[{index}]"
        item = _mapping(row, row_path)
        _exact_keys(
            item,
            {
                "schema_id",
                "rank",
                "proposal_sha256",
                "coordinate_sha256",
                "source_receipt_sha256",
                "rank_selected_before_result",
                "receipt_sha256",
            },
            row_path,
        )
        if item["schema_id"] != CONFORMER_SCHEMA:
            _fail(f"{row_path}.schema_id", "conformer schema changed")
        rank = _exact_int(item["rank"], f"{row_path}.rank", minimum=2, maximum=8)
        if rank not in TRUE_CONFORMER_RANKS or rank in conformers:
            _fail(f"{row_path}.rank", "conformer rank is duplicated or unfrozen")
        for key in ("proposal_sha256", "coordinate_sha256", "source_receipt_sha256"):
            _digest(item[key], f"{row_path}.{key}")
        _exact_bool(item["rank_selected_before_result"], f"{row_path}.rank_selected_before_result", True)
        receipt = _verify_receipt(item, row_path)
        conformers[rank] = item
        observed_ranks.append(rank)
        conformer_receipts.append(receipt)
    if observed_ranks != sorted(observed_ranks):
        _fail(path, "conformer sources are not rank sorted")
    if conformer_receipts != document["conformer_source_receipt_sha256s"]:
        _fail(path, "conformer receipt list is cross-wired")

    retained_rows = _sequence(document["retained_sources"], f"{path}.retained_sources")
    if len(retained_rows) > len(RETAINED_INDICES):
        _fail(f"{path}.retained_sources", "retained-source capacity exceeded")
    retained: dict[int, dict[str, object]] = {}
    retained_receipts: list[str] = []
    observed_indices: list[int] = []
    for index, row in enumerate(retained_rows):
        row_path = f"{path}.retained_sources[{index}]"
        item = _mapping(row, row_path)
        _exact_keys(
            item,
            {
                "schema_id",
                "source_namespace",
                "source_index",
                "proposal_sha256",
                "coordinate_sha256",
                "source_receipt_sha256",
                "receipt_sha256",
            },
            row_path,
        )
        if item["schema_id"] != RETAINED_SCHEMA or item["source_namespace"] != RETAINED_NAMESPACE:
            _fail(row_path, "retained-source schema or namespace changed")
        source_index = _exact_int(item["source_index"], f"{row_path}.source_index", maximum=63)
        if source_index not in RETAINED_INDICES or source_index in retained:
            _fail(row_path, "retained source is duplicated or unfrozen")
        for key in ("proposal_sha256", "coordinate_sha256", "source_receipt_sha256"):
            _digest(item[key], f"{row_path}.{key}")
        receipt = _verify_receipt(item, row_path)
        retained[source_index] = item
        retained_receipts.append(receipt)
        observed_indices.append(source_index)
    if observed_indices != sorted(observed_indices):
        _fail(path, "retained sources are not index sorted")
    if retained_receipts != document["retained_source_receipt_sha256s"]:
        _fail(path, "retained receipt list is cross-wired")
    if observed_indices != document["retained_source_indices_available"]:
        _fail(path, "retained-source availability does not rederive")

    available = {kind: bool(rows) for kind, rows in by_kind.items()}
    derived = {
        "true_conformer_available": all(rank in conformers for rank in TRUE_CONFORMER_RANKS),
        **{f"{kind}_available": available[kind] for kind in FEATURE_KINDS},
        "complementary_charge_anchor_available": (
            (available["ligand_positive_site"] and available["receptor_negative_site"])
            or (available["ligand_negative_site"] and available["receptor_positive_site"])
        ),
    }
    for key, expected in derived.items():
        _exact_bool(document[key], f"{path}.{key}", expected)
    _exact_bool(document["availability_caller_supplied"], f"{path}.availability_caller_supplied", False)
    _exact_bool(document["result_fields_consumed"], f"{path}.result_fields_consumed", False)
    _verify_receipt(document, path)
    return {
        "document": document,
        "by_kind": by_kind,
        "v7_controls": v7_controls,
        "conformers": conformers,
        "retained": retained,
        "available": available,
    }


def _lane_for_slot(slot_index: int) -> tuple[str, int]:
    for lane, start, end in LANE_RANGES:
        if start <= slot_index <= end:
            return lane, slot_index - start
    raise AssertionError("frozen lane ranges are incomplete")


def _slot_expected(feature_state: dict[str, Any], slot_index: int) -> dict[str, object]:
    lane, offset = _lane_for_slot(slot_index)
    available: dict[str, bool] = feature_state["available"]
    by_kind: dict[str, list[dict[str, object]]] = feature_state["by_kind"]
    v7_controls: dict[int, dict[str, object]] = feature_state["v7_controls"]
    conformers: dict[int, dict[str, object]] = feature_state["conformers"]
    retained: dict[int, dict[str, object]] = feature_state["retained"]
    anchor: str | None = None
    required: tuple[str, ...] = ()
    missing: list[str] = []
    v7_index: int | None = None
    so3_index: int | None = None
    rank: int | None = None
    retained_index: int | None = None
    selected: list[str] = []
    parent_proposal: str | None = None
    parent_coordinate: str | None = None
    parent_role: str | None = None

    if lane == "pocket_centered_controls":
        v7_index = offset
    elif lane == "uniform_source_controls":
        v7_index = offset + 8
    elif lane == "deterministic_independent_so3":
        so3_index = offset
    elif lane == "true_conformer_independent_so3":
        so3_index = offset
        rank = TRUE_CONFORMER_SLOT_RANKS[offset]
        required = (f"true_conformer_rank_{rank}",)
        if rank not in conformers:
            missing.append(f"missing_true_conformer:{rank}")
        else:
            selected.append(str(conformers[rank]["receipt_sha256"]))
            parent_proposal = str(conformers[rank]["proposal_sha256"])
            parent_coordinate = str(conformers[rank]["coordinate_sha256"])
            parent_role = GENERATION_PARENT_GENERATOR_INPUT
    elif lane == "ligand_donor_to_receptor_acceptor":
        anchor = "single_ligand_donor_to_receptor_acceptor"
        required = ("ligand_donor", "receptor_acceptor")
    elif lane == "ligand_acceptor_to_receptor_donor":
        anchor = "single_ligand_acceptor_to_receptor_donor"
        required = ("ligand_acceptor", "receptor_donor")
    elif lane == "complementary_charge":
        anchor = "single_complementary_charge"
        required = ("complementary_charge_anchor",)
    elif lane == "aromatic_plane":
        anchor = "single_aromatic_plane"
        required = ("ligand_aromatic_plane", "receptor_aromatic_plane")
    elif lane == "principal_axis_shape":
        anchor = "single_principal_axis_shape"
        required = ("ligand_shape_axis", "pocket_shape_axis")
    elif lane == "paired_retained_controls":
        retained_index = RETAINED_INDICES[offset]
        required = (f"retained_source_{retained_index}",)
        if retained_index not in retained:
            missing.append(f"missing_retained_source:{retained_index}")
        else:
            selected.append(str(retained[retained_index]["receipt_sha256"]))
            parent_proposal = str(retained[retained_index]["proposal_sha256"])
            parent_coordinate = str(retained[retained_index]["coordinate_sha256"])
            parent_role = GENERATION_PARENT_EXACT_PASSTHROUGH

    if v7_index is not None:
        required = (f"v7_control_source_{v7_index}",)
        if v7_index not in v7_controls:
            missing.append(f"missing_v7_control_source:{v7_index}")
        else:
            source = v7_controls[v7_index]
            selected.append(str(source["receipt_sha256"]))
            parent_proposal = str(source["proposal_sha256"])
            parent_coordinate = str(source["coordinate_sha256"])
            parent_role = GENERATION_PARENT_EXACT_PASSTHROUGH

    missing_codes = {
        "ligand_donor": "missing_ligand_donor",
        "receptor_acceptor": "missing_receptor_acceptor",
        "ligand_acceptor": "missing_ligand_acceptor",
        "receptor_donor": "missing_receptor_donor",
        "ligand_aromatic_plane": "missing_ligand_aromatic_plane",
        "receptor_aromatic_plane": "missing_receptor_aromatic_plane",
        "ligand_shape_axis": "missing_ligand_shape_axis",
        "pocket_shape_axis": "missing_pocket_shape_axis",
    }
    for requirement in required:
        if requirement in missing_codes and not available[requirement]:
            missing.append(missing_codes[requirement])
    if required == ("complementary_charge_anchor",):
        pairs = [
            ("ligand_positive_site", "receptor_negative_site"),
            ("ligand_negative_site", "receptor_positive_site"),
        ]
        available_pairs = [pair for pair in pairs if all(available[kind] for kind in pair)]
        if not available_pairs:
            missing.append("missing_complementary_charge_anchor")
        else:
            pair = available_pairs[offset % len(available_pairs)]
            selected.extend(
                str(by_kind[kind][offset % len(by_kind[kind])]["receipt_sha256"])
                for kind in pair
            )
    elif anchor is not None:
        kinds = tuple(requirement for requirement in required if requirement in FEATURE_KINDS)
        if all(available[kind] for kind in kinds):
            selected.extend(
                str(by_kind[kind][offset % len(by_kind[kind])]["receipt_sha256"])
                for kind in kinds
            )
    eligible = not missing
    return {
        "schema_id": SLOT_SCHEMA,
        "slot_index": slot_index,
        "lane": lane,
        "lane_offset": offset,
        "declared_anchor_kind": anchor,
        "declared_anchor_count": 0 if anchor is None else 1,
        "required_features": list(required),
        "missing_feature_codes": missing,
        "v7_control_source_index": v7_index,
        "so3_sequence_index": so3_index,
        "true_conformer_rank": rank,
        "retained_source_index": retained_index,
        "selected_source_receipt_sha256s": selected,
        "selected_generation_parent_proposal_sha256": parent_proposal,
        "selected_generation_parent_coordinate_sha256": parent_coordinate,
        "generation_parent_role": parent_role,
        "generation_status": "ready" if eligible else "typed_missing_feature_failure",
        "generation_eligible": eligible,
        "fallback_lane": None,
        "fallback_allowed": False,
        "multi_anchor_allowed": False,
        "slot_preserved_on_failure": True,
    }


def _verify_allocation(value: object, path: str) -> dict[str, Any]:
    document = _mapping(value, path)
    _exact_keys(
        document,
        {
            "schema_id",
            "profile_id",
            "candidate_denominator",
            "features_receipt_sha256",
            "features",
            "lane_ranges_inclusive",
            "retained_source_indices",
            "ready_count",
            "typed_failure_count",
            "slot_receipt_sha256s",
            "slots",
            "allocation_result_dependent",
            "fallback_allowed",
            "multi_anchor_allowed",
            "failed_slots_preserved_in_denominator",
            "native_pose_input_consumed",
            "score_input_consumed",
            "benchmark_outcome_input_consumed",
            "fresh_holdout_input_consumed",
            "molecular_execution_authorized",
            "production_claim_authorized",
            "receipt_sha256",
        },
        path,
    )
    if document["schema_id"] != ALLOCATION_SCHEMA or document["profile_id"] != PROFILE_ID:
        _fail(path, "allocation schema or profile changed")
    if _exact_int(document["candidate_denominator"], f"{path}.candidate_denominator") != 64:
        _fail(path, "allocation denominator is not fixed64")
    features = _verify_features(document["features"], f"{path}.features")
    if document["features_receipt_sha256"] != features["document"]["receipt_sha256"]:
        _fail(path, "feature receipt reference is cross-wired")
    expected_ranges = [
        {"lane": lane, "start": start, "end": end} for lane, start, end in LANE_RANGES
    ]
    if document["lane_ranges_inclusive"] != expected_ranges:
        _fail(path, "lane ranges changed")
    if document["retained_source_indices"] != list(RETAINED_INDICES):
        _fail(path, "retained source indices changed")
    slots = _sequence(document["slots"], f"{path}.slots", length=64)
    slot_receipts: list[str] = []
    ready_count = 0
    for slot_index, value_slot in enumerate(slots):
        slot_path = f"{path}.slots[{slot_index}]"
        slot = _mapping(value_slot, slot_path)
        expected = _slot_expected(features, slot_index)
        _exact_keys(slot, set(expected) | {"receipt_sha256"}, slot_path)
        projection = dict(slot)
        projection.pop("receipt_sha256")
        if projection != expected:
            _fail(slot_path, "slot does not rederive from fixed profile and feature evidence")
        slot_receipts.append(_verify_receipt(slot, slot_path))
        ready_count += int(bool(slot["generation_eligible"]))
    if document["slot_receipt_sha256s"] != slot_receipts:
        _fail(path, "slot receipt list is cross-wired")
    if document["ready_count"] != ready_count or document["typed_failure_count"] != 64 - ready_count:
        _fail(path, "allocation counts do not rederive")
    for key in (
        "allocation_result_dependent",
        "fallback_allowed",
        "multi_anchor_allowed",
        "native_pose_input_consumed",
        "score_input_consumed",
        "benchmark_outcome_input_consumed",
        "fresh_holdout_input_consumed",
        "molecular_execution_authorized",
        "production_claim_authorized",
    ):
        _exact_bool(document[key], f"{path}.{key}", False)
    _exact_bool(document["failed_slots_preserved_in_denominator"], f"{path}.failed_slots_preserved_in_denominator", True)
    receipt = _verify_receipt(document, path)
    return {"document": document, "slots": slots, "receipt": receipt}


def _parse_coordinates(value: object, path: str, maximum: int) -> tuple[tuple[float, float, float], ...]:
    rows = _sequence(value, path)
    if not 1 <= len(rows) <= maximum:
        _fail(path, f"coordinate count must be in [1, {maximum}]")
    result: list[tuple[float, float, float]] = []
    for row_index, row in enumerate(rows):
        values = _sequence(row, f"{path}[{row_index}]", length=3)
        parsed = tuple(
            _float_hex(item, f"{path}[{row_index}][{component}]")
            for component, item in enumerate(values)
        )
        if any(abs(item) > MAX_ABSOLUTE_COORDINATE_ANGSTROM for item in parsed):
            _fail(f"{path}[{row_index}]", "coordinate exceeds safety envelope")
        result.append(parsed)  # type: ignore[arg-type]
    return tuple(result)


def _distance(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _sphere_intersection(left: float, right: float, distance: float) -> float:
    radius_sum = left + right
    if distance >= radius_sum:
        return 0.0
    difference = abs(left - right)
    if distance <= difference:
        smaller = min(left, right)
        result = (4.0 / 3.0) * math.pi * smaller**3
    else:
        result = (
            math.pi
            * (radius_sum - distance) ** 2
            * (distance**2 + 2.0 * distance * radius_sum - 3.0 * difference**2)
            / (12.0 * distance)
        )
    if not math.isfinite(result):
        raise ArtifactVerificationError("derived sphere-overlap proxy is non-finite")
    return max(0.0, result)


def _derive_metrics(
    ligand: tuple[tuple[float, float, float], ...],
    ligand_radii: tuple[float, ...],
    heavy_mask: tuple[bool, ...],
    receptor: tuple[tuple[float, float, float], ...],
    receptor_radii: tuple[float, ...],
    pocket_center: tuple[float, float, float],
    pocket_radius: float,
) -> dict[str, object]:
    raw = math.inf
    gap = math.inf
    ratio = math.inf
    penetration_pairs = 0
    penetrating: set[int] = set()
    heavy_penetrating: set[int] = set()
    overlap = 0.0
    for ligand_index, (ligand_point, ligand_radius) in enumerate(zip(ligand, ligand_radii, strict=True)):
        for receptor_point, receptor_radius in zip(receptor, receptor_radii, strict=True):
            distance = _distance(ligand_point, receptor_point)
            radius_sum = ligand_radius + receptor_radius
            raw = min(raw, distance)
            gap = min(gap, distance - radius_sum)
            ratio = min(ratio, distance / radius_sum)
            if distance < radius_sum:
                penetration_pairs += 1
                penetrating.add(ligand_index)
                if heavy_mask[ligand_index]:
                    heavy_penetrating.add(ligand_index)
                overlap = math.fsum((overlap, _sphere_intersection(ligand_radius, receptor_radius, distance)))
    escape = max(
        max(0.0, _distance(point, pocket_center) + radius - pocket_radius)
        for point, radius in zip(ligand, ligand_radii, strict=True)
    )
    return {
        "schema_id": GEOMETRIC_METRICS_SCHEMA,
        "ligand_atom_count": len(ligand),
        "receptor_atom_count": len(receptor),
        "exact_pair_count": len(ligand) * len(receptor),
        "pair_traversal_order": PAIR_TRAVERSAL_ORDER,
        "raw_minimum_distance_angstrom_binary64_hex": raw.hex(),
        "minimum_vdw_surface_gap_angstrom_binary64_hex": gap.hex(),
        "minimum_vdw_ratio_binary64_hex": ratio.hex(),
        "penetration_pair_count": penetration_pairs,
        "penetration_definition": "center_distance_less_than_vdw_radius_sum",
        "unique_ligand_penetration_atom_count": len(penetrating),
        "unique_ligand_heavy_atom_penetration_count": len(heavy_penetrating),
        "heavy_atom_definition": "exact_ligand_heavy_atom_mask_true",
        "sphere_overlap_proxy_angstrom3_binary64_hex": overlap.hex(),
        "sphere_overlap_proxy_definition": OVERLAP_DEFINITION,
        "pocket_escape_angstrom_binary64_hex": escape.hex(),
        "pocket_escape_definition": ESCAPE_DEFINITION,
    }


def _verify_geometric(value: object, path: str, allocation: dict[str, Any]) -> dict[str, Any]:
    document = _mapping(value, path)
    expected_keys = {
        "schema_id", "component_id", "candidate_denominator",
        "allocation_receipt_sha256", "allocation_profile_id", "allocation",
        "allocation_slot_receipt_sha256s", "exact_input_binding_sha256", "exact_inputs",
        "ligand_vdw_radii_sha256", "ligand_heavy_atom_mask_sha256",
        "receptor_geometry_sha256", "pocket_geometry_sha256",
        "hard_rejection_minimum_vdw_ratio_binary64_hex", "accepted_count",
        "nonaccepted_count", "typed_generation_failure_count", "geometric_rejected_count",
        "decision_receipt_sha256s", "decisions", "rejected_slots_preserved",
        "rejected_slots_rank_ineligible", "score_input_consumed",
        "benchmark_outcome_input_consumed", "molecular_execution_authorized",
        "production_claim_authorized", "receipt_sha256",
    }
    _exact_keys(document, expected_keys, path)
    if document["schema_id"] != GEOMETRIC_BATCH_SCHEMA or document["component_id"] != GEOMETRIC_COMPONENT:
        _fail(path, "geometric schema or component changed")
    if document["candidate_denominator"] != 64:
        _fail(path, "geometric denominator is not fixed64")
    if document["allocation"] != allocation["document"] or document["allocation_receipt_sha256"] != allocation["receipt"]:
        _fail(path, "geometric allocation is cross-wired")
    if document["allocation_profile_id"] != PROFILE_ID:
        _fail(path, "geometric allocation profile changed")
    slot_receipts = [slot["receipt_sha256"] for slot in allocation["slots"]]
    if document["allocation_slot_receipt_sha256s"] != slot_receipts:
        _fail(path, "geometric slot receipts are cross-wired")

    inputs = _mapping(document["exact_inputs"], f"{path}.exact_inputs")
    input_keys = {
        "schema_id", "allocation_receipt_sha256", "allocation_slot_receipt_sha256s",
        "candidate_coordinates_binary64_hex", "ligand_vdw_radii_binary64_hex",
        "ligand_heavy_atom_mask", "receptor_coordinates_binary64_hex",
        "receptor_vdw_radii_binary64_hex", "pocket_center_binary64_hex",
        "pocket_radius_binary64_hex", "pocket_escape_definition", "input_safety_envelope",
        "batch_exact_pair_evaluations", "maximum_batch_exact_pair_evaluations",
        "receipt_sha256",
    }
    _exact_keys(inputs, input_keys, f"{path}.exact_inputs")
    if inputs["schema_id"] != GEOMETRIC_INPUT_SCHEMA:
        _fail(f"{path}.exact_inputs.schema_id", "exact-input schema changed")
    if inputs["allocation_receipt_sha256"] != allocation["receipt"] or inputs["allocation_slot_receipt_sha256s"] != slot_receipts:
        _fail(f"{path}.exact_inputs", "exact inputs are cross-wired to allocation")
    input_receipt = _verify_receipt(inputs, f"{path}.exact_inputs")
    if document["exact_input_binding_sha256"] != input_receipt:
        _fail(path, "exact-input receipt reference is cross-wired")
    envelope = _mapping(inputs["input_safety_envelope"], f"{path}.exact_inputs.input_safety_envelope")
    expected_envelope = {
        "maximum_absolute_coordinate_angstrom_binary64_hex": MAX_ABSOLUTE_COORDINATE_ANGSTROM.hex(),
        "minimum_vdw_radius_angstrom_binary64_hex": MIN_VDW_RADIUS_ANGSTROM.hex(),
        "maximum_vdw_radius_angstrom_binary64_hex": MAX_VDW_RADIUS_ANGSTROM.hex(),
        "maximum_pocket_radius_angstrom_binary64_hex": MAX_POCKET_RADIUS_ANGSTROM.hex(),
    }
    if envelope != expected_envelope:
        _fail(f"{path}.exact_inputs.input_safety_envelope", "safety envelope changed")

    coordinate_rows = _sequence(inputs["candidate_coordinates_binary64_hex"], f"{path}.exact_inputs.candidate_coordinates_binary64_hex", length=64)
    coordinates: list[tuple[tuple[float, float, float], ...] | None] = []
    for slot_index, coordinate_row in enumerate(coordinate_rows):
        slot = allocation["slots"][slot_index]
        if coordinate_row is None:
            coordinates.append(None)
        else:
            coordinates.append(_parse_coordinates(coordinate_row, f"{path}.exact_inputs.candidate_coordinates_binary64_hex[{slot_index}]", MAX_LIGAND_ATOMS))
        if bool(slot["generation_eligible"]) is (coordinates[-1] is None):
            _fail(path, "coordinate presence disagrees with allocation eligibility")
    present = [value for value in coordinates if value is not None]
    if not present:
        _fail(path, "at least one coordinate-bearing slot is required")
    ligand_count = len(present[0])
    if any(len(value) != ligand_count for value in present):
        _fail(path, "ligand atom count changed between candidate slots")
    ligand_radii_values = _sequence(inputs["ligand_vdw_radii_binary64_hex"], f"{path}.exact_inputs.ligand_vdw_radii_binary64_hex", length=ligand_count)
    ligand_radii = tuple(_float_hex(value, f"{path}.exact_inputs.ligand_vdw_radii_binary64_hex[{index}]") for index, value in enumerate(ligand_radii_values))
    if any(not MIN_VDW_RADIUS_ANGSTROM <= radius <= MAX_VDW_RADIUS_ANGSTROM for radius in ligand_radii):
        _fail(path, "ligand vdW radius exceeds safety envelope")
    heavy_values = _sequence(inputs["ligand_heavy_atom_mask"], f"{path}.exact_inputs.ligand_heavy_atom_mask", length=ligand_count)
    heavy_mask = tuple(_exact_bool(value, f"{path}.exact_inputs.ligand_heavy_atom_mask[{index}]") for index, value in enumerate(heavy_values))
    receptor = _parse_coordinates(inputs["receptor_coordinates_binary64_hex"], f"{path}.exact_inputs.receptor_coordinates_binary64_hex", MAX_RECEPTOR_ATOMS)
    receptor_radius_values = _sequence(inputs["receptor_vdw_radii_binary64_hex"], f"{path}.exact_inputs.receptor_vdw_radii_binary64_hex", length=len(receptor))
    receptor_radii = tuple(_float_hex(value, f"{path}.exact_inputs.receptor_vdw_radii_binary64_hex[{index}]") for index, value in enumerate(receptor_radius_values))
    if any(not MIN_VDW_RADIUS_ANGSTROM <= radius <= MAX_VDW_RADIUS_ANGSTROM for radius in receptor_radii):
        _fail(path, "receptor vdW radius exceeds safety envelope")
    pocket_values = _sequence(inputs["pocket_center_binary64_hex"], f"{path}.exact_inputs.pocket_center_binary64_hex", length=3)
    pocket_center = tuple(_float_hex(value, f"{path}.exact_inputs.pocket_center_binary64_hex[{index}]") for index, value in enumerate(pocket_values))
    if any(abs(value) > MAX_ABSOLUTE_COORDINATE_ANGSTROM for value in pocket_center):
        _fail(path, "pocket center exceeds safety envelope")
    pocket_radius = _float_hex(inputs["pocket_radius_binary64_hex"], f"{path}.exact_inputs.pocket_radius_binary64_hex")
    if not 0.0 < pocket_radius <= MAX_POCKET_RADIUS_ANGSTROM:
        _fail(path, "pocket radius exceeds safety envelope")
    if inputs["pocket_escape_definition"] != ESCAPE_DEFINITION:
        _fail(path, "pocket escape definition changed")
    pair_evaluations = len(present) * ligand_count * len(receptor)
    if pair_evaluations > MAX_BATCH_EXACT_PAIR_EVALUATIONS:
        _fail(path, "exact pair replay exceeds fail-closed capacity")
    if inputs["batch_exact_pair_evaluations"] != pair_evaluations or inputs["maximum_batch_exact_pair_evaluations"] != MAX_BATCH_EXACT_PAIR_EVALUATIONS:
        _fail(path, "exact pair work accounting changed")

    expected_ligand_radii_sha = _sha256(list(inputs["ligand_vdw_radii_binary64_hex"]))
    expected_heavy_sha = _sha256(list(heavy_mask))
    expected_receptor_sha = _sha256({
        "coordinates_binary64_hex": inputs["receptor_coordinates_binary64_hex"],
        "vdw_radii_binary64_hex": inputs["receptor_vdw_radii_binary64_hex"],
    })
    expected_pocket_sha = _sha256({
        "center_binary64_hex": inputs["pocket_center_binary64_hex"],
        "radius_binary64_hex": inputs["pocket_radius_binary64_hex"],
        "escape_definition": ESCAPE_DEFINITION,
    })
    for key, expected in (
        ("ligand_vdw_radii_sha256", expected_ligand_radii_sha),
        ("ligand_heavy_atom_mask_sha256", expected_heavy_sha),
        ("receptor_geometry_sha256", expected_receptor_sha),
        ("pocket_geometry_sha256", expected_pocket_sha),
    ):
        if document[key] != expected:
            _fail(f"{path}.{key}", "exact-input binding does not rederive")
    if document["hard_rejection_minimum_vdw_ratio_binary64_hex"] != HARD_REJECTION_MINIMUM_VDW_RATIO.hex():
        _fail(path, "hard rejection threshold changed")

    decisions = _sequence(document["decisions"], f"{path}.decisions", length=64)
    decision_receipts: list[str] = []
    accepted_count = typed_count = geometric_rejected_count = 0
    for slot_index, (slot, coords, value_decision) in enumerate(zip(allocation["slots"], coordinates, decisions, strict=True)):
        decision_path = f"{path}.decisions[{slot_index}]"
        decision = _mapping(value_decision, decision_path)
        common = {
            "schema_id": GEOMETRIC_DECISION_SCHEMA,
            "component_id": GEOMETRIC_COMPONENT,
            "slot_index": slot_index,
            "allocation_slot_receipt_sha256": slot["receipt_sha256"],
            "lane": slot["lane"],
            "allocation_generation_eligible": slot["generation_eligible"],
            "allocation_missing_feature_codes": slot["missing_feature_codes"],
        }
        if coords is None:
            expected_decision = {
                **common,
                "candidate_coordinate_sha256": None,
                "metrics": None,
                "decision_basis": "allocation_typed_missing_feature",
                "hard_rejection_metric": None,
                "hard_rejection_operator": None,
                "hard_rejection_threshold_binary64_hex": None,
                "status": "typed_generation_failure",
                "rejection_code": "mixed64_typed_missing_feature",
                "rank_eligible": False,
                "slot_preserved_in_denominator": True,
            }
            typed_count += 1
        else:
            metrics_projection = _derive_metrics(coords, ligand_radii, heavy_mask, receptor, receptor_radii, pocket_center, pocket_radius)  # type: ignore[arg-type]
            metrics = _mapping(decision.get("metrics"), f"{decision_path}.metrics")
            _exact_keys(metrics, set(metrics_projection) | {"receipt_sha256"}, f"{decision_path}.metrics")
            observed_metrics = dict(metrics)
            observed_metrics.pop("receipt_sha256")
            if observed_metrics != metrics_projection:
                _fail(f"{decision_path}.metrics", "full-Cartesian metrics do not replay")
            _verify_receipt(metrics, f"{decision_path}.metrics")
            minimum_ratio = float.fromhex(str(metrics_projection["minimum_vdw_ratio_binary64_hex"]))
            accepted = minimum_ratio >= HARD_REJECTION_MINIMUM_VDW_RATIO
            coordinate_projection = [[component.hex() for component in point] for point in coords]
            expected_decision = {
                **common,
                "candidate_coordinate_sha256": _sha256(coordinate_projection),
                "metrics": metrics,
                "decision_basis": "minimum_vdw_ratio",
                "hard_rejection_metric": "minimum_vdw_ratio",
                "hard_rejection_operator": "strictly_less_than",
                "hard_rejection_threshold_binary64_hex": HARD_REJECTION_MINIMUM_VDW_RATIO.hex(),
                "status": "accepted" if accepted else "rejected",
                "rejection_code": None if accepted else "severe_receptor_penetration_min_vdw_ratio",
                "rank_eligible": accepted,
                "slot_preserved_in_denominator": True,
            }
            if accepted:
                accepted_count += 1
            else:
                geometric_rejected_count += 1
        _exact_keys(decision, set(expected_decision) | {"receipt_sha256"}, decision_path)
        observed_decision = dict(decision)
        observed_decision.pop("receipt_sha256")
        if observed_decision != expected_decision:
            _fail(decision_path, "geometric decision does not replay")
        decision_receipts.append(_verify_receipt(decision, decision_path))
    if document["decision_receipt_sha256s"] != decision_receipts:
        _fail(path, "decision receipt list is cross-wired")
    nonaccepted_count = typed_count + geometric_rejected_count
    if (
        document["accepted_count"] != accepted_count
        or document["typed_generation_failure_count"] != typed_count
        or document["geometric_rejected_count"] != geometric_rejected_count
        or document["nonaccepted_count"] != nonaccepted_count
        or accepted_count + nonaccepted_count != 64
    ):
        _fail(path, "geometric decision counts do not rederive")
    for key, expected in (
        ("rejected_slots_preserved", True),
        ("rejected_slots_rank_ineligible", True),
        ("score_input_consumed", False),
        ("benchmark_outcome_input_consumed", False),
        ("molecular_execution_authorized", False),
        ("production_claim_authorized", False),
    ):
        _exact_bool(document[key], f"{path}.{key}", expected)
    receipt = _verify_receipt(document, path)
    return {"document": document, "decisions": decisions, "receipt": receipt}


def _verify_proposal(
    value: object,
    path: str,
    *,
    slot_index: int,
    slot: dict[str, object],
    source_proposal: str,
    source_coordinate: str,
) -> dict[str, object]:
    document = _mapping(value, path)
    _exact_keys(
        document,
        {
            "schema_id",
            "slot_index",
            "allocation_slot_receipt_sha256",
            "allocation_source_receipt_sha256s",
            "generation_parent_proposal_sha256",
            "generation_parent_coordinate_sha256",
            "source_proposal_sha256",
            "source_coordinate_sha256",
            "generation_input_receipt_sha256",
            "generator_config_sha256",
            "generator_implementation_source_sha256",
            "generator_component_id",
            "structurally_complete",
            "producer_attested",
            "result_fields_consumed",
            "claim_safe",
            "receipt_sha256",
        },
        path,
    )
    if (
        document["schema_id"] != PROPOSAL_SCHEMA
        or document["slot_index"] != slot_index
        or document["allocation_slot_receipt_sha256"] != slot["receipt_sha256"]
        or document["allocation_source_receipt_sha256s"]
        != slot["selected_source_receipt_sha256s"]
        or document["source_proposal_sha256"] != source_proposal
        or document["source_coordinate_sha256"] != source_coordinate
    ):
        _fail(path, "proposal execution lifecycle is cross-wired")
    sources = _sequence(
        document["allocation_source_receipt_sha256s"],
        f"{path}.allocation_source_receipt_sha256s",
    )
    if len(set(sources)) != len(sources):
        _fail(path, "proposal allocation source receipts are duplicated")
    for index, source in enumerate(sources):
        _digest(source, f"{path}.allocation_source_receipt_sha256s[{index}]")
    parent_proposal = document["generation_parent_proposal_sha256"]
    parent_coordinate = document["generation_parent_coordinate_sha256"]
    if (parent_proposal is None) != (parent_coordinate is None):
        _fail(path, "proposal generation parent identities are not paired")
    if parent_proposal is not None:
        _digest(parent_proposal, f"{path}.generation_parent_proposal_sha256")
        _digest(parent_coordinate, f"{path}.generation_parent_coordinate_sha256")
    if (
        parent_proposal != slot["selected_generation_parent_proposal_sha256"]
        or parent_coordinate
        != slot["selected_generation_parent_coordinate_sha256"]
    ):
        _fail(path, "proposal generation parent identity is cross-wired")
    if slot["generation_parent_role"] == GENERATION_PARENT_EXACT_PASSTHROUGH:
        if (source_proposal, source_coordinate) != (
            parent_proposal,
            parent_coordinate,
        ):
            _fail(path, "exact-passthrough control changed its generation parent")
    elif slot["generation_parent_role"] == GENERATION_PARENT_GENERATOR_INPUT:
        if source_proposal == parent_proposal or source_coordinate == parent_coordinate:
            _fail(path, "true-conformer output is not transformed from its parent")
    for key in (
        "generation_input_receipt_sha256",
        "generator_config_sha256",
        "generator_implementation_source_sha256",
    ):
        _digest(document[key], f"{path}.{key}")
    _exact_string(document["generator_component_id"], f"{path}.generator_component_id")
    for key, expected in (
        ("structurally_complete", True),
        ("producer_attested", False),
        ("result_fields_consumed", False),
        ("claim_safe", False),
    ):
        _exact_bool(document[key], f"{path}.{key}", expected)
    _verify_receipt(document, path)
    return document


def _verify_scorer(value: object, path: str, result_proposal: str) -> tuple[dict[str, object], float]:
    document = _mapping(value, path)
    _exact_keys(document, {
        "schema_id", "result_proposal_sha256", "search_row_sha256",
        "search_term_row_receipt_sha256", "source_search_result_receipt_sha256",
        "scorer_implementation_source_sha256", "scorer_v1_terms_receipt_sha256",
        "scorer_v1_terms", "structurally_complete", "producer_attested",
        "claim_safe", "receipt_sha256",
    }, path)
    if document["schema_id"] != SCORER_BINDING_SCHEMA or document["result_proposal_sha256"] != result_proposal:
        _fail(path, "scorer binding schema or result proposal is cross-wired")
    for key in ("search_row_sha256", "search_term_row_receipt_sha256", "source_search_result_receipt_sha256", "scorer_implementation_source_sha256"):
        _digest(document[key], f"{path}.{key}")
    _exact_bool(document["structurally_complete"], f"{path}.structurally_complete", True)
    _exact_bool(document["producer_attested"], f"{path}.producer_attested", False)
    _exact_bool(document["claim_safe"], f"{path}.claim_safe", False)
    terms = _mapping(document["scorer_v1_terms"], f"{path}.scorer_v1_terms")
    term_keys = {
        "schema_id", "score_id", "proposal_fingerprint_sha256",
        "authority_input_receipt_sha256", "context_fingerprint_sha256",
        "config_fingerprint_sha256", "backend_receipt_sha256",
        *(f"{name}_binary64_hex" for name in (*TERM_NAMES, "total_score")),
        "receptor_candidate_pair_count", "ligand_pair_count", "hbond_count",
        "hydrophobic_contact_count", "buried_polar_count", "calibrated",
        "scientifically_validated", "claim_safe", "receipt_sha256",
    }
    _exact_keys(terms, term_keys, f"{path}.scorer_v1_terms")
    if terms["schema_id"] != SCORER_TERMS_SCHEMA or terms["score_id"] != SCORER_SCORE_ID or terms["proposal_fingerprint_sha256"] != result_proposal:
        _fail(path, "ScorerV1 terms identity is cross-wired")
    for key in ("authority_input_receipt_sha256", "context_fingerprint_sha256", "config_fingerprint_sha256", "backend_receipt_sha256"):
        _digest(terms[key], f"{path}.scorer_v1_terms.{key}")
    values = [_float_hex(terms[f"{name}_binary64_hex"], f"{path}.scorer_v1_terms.{name}_binary64_hex") for name in TERM_NAMES]
    total = _float_hex(terms["total_score_binary64_hex"], f"{path}.scorer_v1_terms.total_score_binary64_hex")
    if not math.isclose(total, sum(values), rel_tol=0.0, abs_tol=1.0e-12):
        _fail(path, "ScorerV1 total does not equal all eight terms")
    for key in ("receptor_candidate_pair_count", "ligand_pair_count", "hbond_count", "hydrophobic_contact_count", "buried_polar_count"):
        _exact_int(terms[key], f"{path}.scorer_v1_terms.{key}", maximum=MAX_BATCH_EXACT_PAIR_EVALUATIONS)
    for key in ("calibrated", "scientifically_validated", "claim_safe"):
        _exact_bool(terms[key], f"{path}.scorer_v1_terms.{key}", False)
    terms_receipt = _verify_receipt(terms, f"{path}.scorer_v1_terms")
    if document["scorer_v1_terms_receipt_sha256"] != terms_receipt:
        _fail(path, "ScorerV1 terms receipt reference is cross-wired")
    _verify_receipt(document, path)
    return terms, total


def _verify_refinement(value: object, path: str, source: str, result: str, source_coordinate: str) -> dict[str, object]:
    document = _mapping(value, path)
    _exact_keys(document, {
        "schema_id", "source_proposal_sha256", "result_proposal_sha256",
        "source_coordinate_sha256", "result_coordinate_sha256", "refiner_config_sha256",
        "refiner_implementation_source_sha256", "source_receipt_sha256", "source_receipt",
        "structurally_complete", "producer_attested", "claim_safe", "receipt_sha256",
    }, path)
    if document["schema_id"] != REFINEMENT_SCHEMA or document["source_proposal_sha256"] != source or document["result_proposal_sha256"] != result or document["source_coordinate_sha256"] != source_coordinate:
        _fail(path, "refinement lifecycle identity is cross-wired")
    for key in ("result_coordinate_sha256", "refiner_config_sha256", "refiner_implementation_source_sha256"):
        _digest(document[key], f"{path}.{key}")
    _exact_bool(document["structurally_complete"], f"{path}.structurally_complete", True)
    _exact_bool(document["producer_attested"], f"{path}.producer_attested", False)
    _exact_bool(document["claim_safe"], f"{path}.claim_safe", False)
    source_receipt = _mapping(document["source_receipt"], f"{path}.source_receipt")
    _exact_keys(
        source_receipt,
        {
            "schema_id",
            "source_receipt_schema_id",
            "source_proposal_sha256",
            "config_sha256",
            "pre_coordinates_sha256",
            "post_coordinates_sha256",
            "original_source_receipt_sha256",
            "source_payload_embedded",
            "source_payload_rederived",
            "scientifically_validated",
            "producer_attested",
            "claim_safe",
            "receipt_sha256",
        },
        f"{path}.source_receipt",
    )
    _require_false_nested_source_authority(
        source_receipt,
        f"{path}.source_receipt",
    )
    if source_receipt["schema_id"] != REFINEMENT_SOURCE_IDENTITY_SCHEMA:
        _fail(path, "refinement source identity schema changed")
    _verify_receipt(source_receipt, f"{path}.source_receipt")
    original_receipt_sha = _digest(
        source_receipt["original_source_receipt_sha256"],
        f"{path}.source_receipt.original_source_receipt_sha256",
    )
    if document["source_receipt_sha256"] != original_receipt_sha:
        _fail(path, "refinement source receipt reference is cross-wired")
    if source_receipt["source_receipt_schema_id"] not in ALLOWED_REFINEMENT_SOURCE_SCHEMAS:
        _fail(path, "refinement source schema is not allowed")
    if source_receipt["source_proposal_sha256"] != source or source_receipt["config_sha256"] != document["refiner_config_sha256"] or source_receipt["pre_coordinates_sha256"] != source_coordinate or source_receipt["post_coordinates_sha256"] != document["result_coordinate_sha256"]:
        _fail(path, "refinement source receipt is cross-wired")
    for key in (
        "source_payload_embedded",
        "source_payload_rederived",
        "scientifically_validated",
        "producer_attested",
        "claim_safe",
    ):
        _exact_bool(source_receipt[key], f"{path}.source_receipt.{key}", False)
    _verify_receipt(document, path)
    return document


def _verify_validity(value: object, path: str, result: str, coordinate: str) -> tuple[dict[str, object], bool]:
    document = _mapping(value, path)
    _exact_keys(document, {
        "schema_id", "result_proposal_sha256", "coordinate_sha256",
        "validity_context_fingerprint_sha256", "validity_config_fingerprint_sha256",
        "evaluator_implementation_source_sha256", "pose_validity", "complete", "valid",
        "structurally_complete", "producer_attested", "claim_safe", "receipt_sha256",
    }, path)
    if document["schema_id"] != VALIDITY_SCHEMA or document["result_proposal_sha256"] != result or document["coordinate_sha256"] != coordinate:
        _fail(path, "validity lifecycle identity is cross-wired")
    for key in ("validity_context_fingerprint_sha256", "validity_config_fingerprint_sha256", "evaluator_implementation_source_sha256"):
        _digest(document[key], f"{path}.{key}")
    validity = _mapping(document["pose_validity"], f"{path}.pose_validity")
    _exact_keys(validity, {"valid", "checks", "evaluated_checks", "complete", "valid_within_evaluated_scope", "measurements", "blockers", "not_evaluated_reasons", "claim_safe"}, f"{path}.pose_validity")
    checks = _mapping(validity["checks"], f"{path}.pose_validity.checks")
    evaluated = _mapping(validity["evaluated_checks"], f"{path}.pose_validity.evaluated_checks")
    if set(checks) != REQUIRED_VALIDITY_CHECKS or set(evaluated) != REQUIRED_VALIDITY_CHECKS:
        _fail(path, "validity receipt does not contain exactly eight required checks")
    if any(type(value) is not bool for value in checks.values()) or any(value is not True for value in evaluated.values()):
        _fail(path, "validity checks/evaluation flags are incomplete")
    _exact_bool(validity["complete"], f"{path}.pose_validity.complete", True)
    expected_valid = all(checks.values())
    _exact_bool(validity["valid_within_evaluated_scope"], f"{path}.pose_validity.valid_within_evaluated_scope", expected_valid)
    _exact_bool(validity["valid"], f"{path}.pose_validity.valid", expected_valid)
    measurements = _mapping(validity["measurements"], f"{path}.pose_validity.measurements")
    if len(measurements) > 256:
        _fail(path, "validity measurement capacity exceeded")
    for key, measurement in measurements.items():
        _exact_string(key, f"{path}.pose_validity.measurements.key")
        try:
            numeric_measurement = float(measurement)
        except (OverflowError, TypeError, ValueError):
            _fail(path, "validity measurement is not a bounded finite number")
        if (
            type(measurement) not in {int, float}
            or isinstance(measurement, bool)
            or not math.isfinite(numeric_measurement)
            or abs(numeric_measurement) > 1.0e15
        ):
            _fail(path, "validity measurement is not a bounded finite number")
    blockers = _sequence(validity["blockers"], f"{path}.pose_validity.blockers")
    if len(blockers) > 256:
        _fail(path, "validity blocker capacity exceeded")
    for index, blocker in enumerate(blockers):
        _exact_string(blocker, f"{path}.pose_validity.blockers[{index}]")
    if len(set(blockers)) != len(blockers):
        _fail(path, "validity blockers are duplicated")
    if expected_valid is bool(blockers):
        _fail(path, "validity blockers disagree with the exact check outcome")
    reasons = _mapping(validity["not_evaluated_reasons"], f"{path}.pose_validity.not_evaluated_reasons")
    if reasons:
        _fail(path, "complete validity cannot contain not-evaluated reasons")
    _exact_bool(validity["claim_safe"], f"{path}.pose_validity.claim_safe", False)
    for key, expected in (("complete", True), ("valid", expected_valid), ("structurally_complete", True), ("producer_attested", False), ("claim_safe", False)):
        _exact_bool(document[key], f"{path}.{key}", expected)
    _verify_receipt(document, path)
    return document, expected_valid


def _optional_digest_field(value: object, path: str) -> str | None:
    if value is None:
        return None
    return _digest(value, path)


def _verify_pipeline(value: object) -> dict[str, object]:
    document = _mapping(value, "$")
    batch_keys = {
        "schema_id", "builder_id", "candidate_denominator", "allocation_receipt_sha256",
        "allocation_profile_id", "allocation", "geometric_admission_batch_receipt_sha256",
        "geometric_admission_batch", "scored_success_count", "score_evidence_complete_count",
        "typed_failure_count", "stable_ranking_slot_indices", "top1_slot_index",
        "top5_slot_indices", "primary_ranking_semantics", "top1_pose_valid", "invalid_top1",
        "stable_valid_ranking_slot_indices", "valid_top1_slot_index", "valid_top5_slot_indices",
        "valid_only_ranking_semantics", "candidate_receipt_sha256s", "candidates",
        "ranking_order", "top_k_limit", "denominator_failure_complete",
        "denominator_failure_completeness_scope",
        "evidence_completion_flags_caller_supplied", "rank_eligibility_caller_supplied",
        "top_k_membership_caller_supplied", "activation_evidence_eligible",
        "activation_evidence_blockers", "historical_execution_authorized",
        "fresh_holdout_execution_authorized", "molecular_execution_authorized",
        "product_mutation_authorized", "existing_rank_auto_change_authorized",
        "customer_pose_emission_authorized", "public_benchmark_execution_authorized",
        "public_or_scientific_claim_authorized", "stage0_admission_authority",
        "receipt_sha256",
    }
    _exact_keys(document, batch_keys, "$")
    if document["schema_id"] != PIPELINE_BATCH_SCHEMA or document["builder_id"] != PIPELINE_BUILDER:
        _fail("$", "pipeline schema or builder changed")
    if document["candidate_denominator"] != 64 or document["allocation_profile_id"] != PROFILE_ID:
        _fail("$", "pipeline denominator or profile changed")
    allocation = _verify_allocation(document["allocation"], "$.allocation")
    if document["allocation_receipt_sha256"] != allocation["receipt"]:
        _fail("$", "pipeline allocation receipt reference is cross-wired")
    geometric = _verify_geometric(document["geometric_admission_batch"], "$.geometric_admission_batch", allocation)
    if document["geometric_admission_batch_receipt_sha256"] != geometric["receipt"]:
        _fail("$", "pipeline geometric receipt reference is cross-wired")

    candidates = _sequence(document["candidates"], "$.candidates", length=64)
    candidate_receipts: list[str] = []
    state: list[dict[str, Any]] = []
    scorer_batch_fields: dict[str, set[object]] = {
        key: set() for key in ("authority_input_receipt_sha256", "context_fingerprint_sha256", "config_fingerprint_sha256", "backend_receipt_sha256")
    }
    for slot_index, value_candidate in enumerate(candidates):
        path = f"$.candidates[{slot_index}]"
        candidate = _mapping(value_candidate, path)
        candidate_keys = {
            "schema_id", "builder_id", "slot_index", "allocation_receipt_sha256",
            "geometric_admission_batch_receipt_sha256", "allocation_slot_receipt_sha256",
            "allocation_lane", "allocation_lane_offset", "retained_source_index", "allocation_slot",
            "source_proposal_sha256", "result_proposal_sha256", "source_coordinate_sha256",
            "proposal_execution_receipt_sha256", "proposal_execution_receipt",
            "result_coordinate_sha256", "coordinate_sha256",
            "geometric_admission_decision_receipt_sha256", "geometric_admission_metrics_receipt_sha256",
            "geometric_admission_decision", "scorer_v1_evidence_binding_sha256",
            "scorer_v1_evidence", "pose_validity_receipt_sha256", "pose_validity_receipt",
            "refinement_receipt_binding_sha256", "refinement_receipt", "status",
            "execution_failure_stage", "execution_failure_code", "typed_failure_codes",
            "score_binary64_hex", "evidence_complete", "score_evidence_complete",
            "rank_eligible", "score_rank_includes_pose_invalid_candidates", "valid_rank_eligible",
            "selection_eligible", "stable_rank", "top1_member", "top5_member",
            "stable_valid_rank", "valid_top1_member", "valid_top5_member",
            "denominator_slot_preserved", "historical_execution_authorized",
            "fresh_holdout_execution_authorized", "molecular_execution_authorized",
            "product_mutation_authorized", "customer_pose_emission_authorized",
            "public_or_scientific_claim_authorized", "receipt_sha256",
        }
        _exact_keys(candidate, candidate_keys, path)
        if candidate["schema_id"] != PIPELINE_CANDIDATE_SCHEMA or candidate["builder_id"] != PIPELINE_BUILDER or candidate["slot_index"] != slot_index:
            _fail(path, "candidate schema/builder/index changed")
        slot = allocation["slots"][slot_index]
        decision = geometric["decisions"][slot_index]
        if candidate["allocation_receipt_sha256"] != allocation["receipt"] or candidate["geometric_admission_batch_receipt_sha256"] != geometric["receipt"] or candidate["allocation_slot"] != slot or candidate["allocation_slot_receipt_sha256"] != slot["receipt_sha256"] or candidate["geometric_admission_decision"] != decision or candidate["geometric_admission_decision_receipt_sha256"] != decision["receipt_sha256"]:
            _fail(path, "candidate allocation/geometric evidence is cross-wired")
        expected_metrics_receipt = None if decision["metrics"] is None else decision["metrics"]["receipt_sha256"]
        if candidate["geometric_admission_metrics_receipt_sha256"] != expected_metrics_receipt:
            _fail(path, "candidate metric receipt reference is cross-wired")
        if candidate["allocation_lane"] != slot["lane"] or candidate["allocation_lane_offset"] != slot["lane_offset"] or candidate["retained_source_index"] != slot["retained_source_index"]:
            _fail(path, "candidate allocation projection changed")

        source = _optional_digest_field(candidate["source_proposal_sha256"], f"{path}.source_proposal_sha256")
        result = _optional_digest_field(candidate["result_proposal_sha256"], f"{path}.result_proposal_sha256")
        expected_source_coordinate = decision["candidate_coordinate_sha256"]
        if candidate["source_coordinate_sha256"] != expected_source_coordinate:
            _fail(path, "source coordinate is not the geometric input coordinate")
        failure_stage = candidate["execution_failure_stage"]
        failure_code = candidate["execution_failure_code"]
        if (failure_stage is None) != (failure_code is None):
            _fail(path, "execution failure stage/code must be paired")
        if failure_stage is not None and failure_stage not in EXECUTION_FAILURE_STAGES:
            _fail(path, "execution failure stage is not frozen")
        if failure_code is not None:
            _exact_string(failure_code, f"{path}.execution_failure_code")
            if FAILURE_CODE_RE.fullmatch(failure_code) is None:
                _fail(path, "execution failure code is not a canonical identifier")
            prefixes = {
                "refinement": ("typed_refinement_",),
                "scoring": ("typed_scorer_", "typed_scoring_"),
                "validity": ("typed_validity_",),
            }
            if failure_stage is None or not failure_code.startswith(prefixes[failure_stage]):
                _fail(path, "execution failure code does not match its stage")

        proposal: dict[str, object] | None = None
        refinement: dict[str, object] | None = None
        scorer_terms: dict[str, object] | None = None
        score: float | None = None
        valid: bool | None = None
        if not slot["generation_eligible"]:
            if any(value is not None for value in (source, result, candidate["proposal_execution_receipt"], candidate["refinement_receipt"], candidate["scorer_v1_evidence"], candidate["pose_validity_receipt"], failure_stage, failure_code)):
                _fail(path, "allocation failure fabricated downstream evidence")
            expected_status = "allocation_typed_failure"
            expected_codes = slot["missing_feature_codes"]
        elif decision["status"] != "accepted":
            if source is None or candidate["proposal_execution_receipt"] is None or any(value is not None for value in (result, candidate["refinement_receipt"], candidate["scorer_v1_evidence"], candidate["pose_validity_receipt"], failure_stage, failure_code)):
                _fail(path, "geometric rejection lifecycle is invalid")
            proposal = _verify_proposal(
                candidate["proposal_execution_receipt"],
                f"{path}.proposal_execution_receipt",
                slot_index=slot_index,
                slot=slot,
                source_proposal=source,
                source_coordinate=str(expected_source_coordinate),
            )
            expected_status = "geometric_rejection"
            expected_codes = [decision["rejection_code"]]
        else:
            if source is None or candidate["proposal_execution_receipt"] is None:
                _fail(path, "admitted candidate lacks source proposal receipt")
            proposal = _verify_proposal(
                candidate["proposal_execution_receipt"],
                f"{path}.proposal_execution_receipt",
                slot_index=slot_index,
                slot=slot,
                source_proposal=source,
                source_coordinate=str(expected_source_coordinate),
            )
            if failure_stage == "refinement":
                if any(value is not None for value in (result, candidate["refinement_receipt"], candidate["scorer_v1_evidence"], candidate["pose_validity_receipt"])):
                    _fail(path, "refinement failure fabricated later-stage evidence")
            else:
                if result is None or candidate["refinement_receipt"] is None:
                    _fail(path, "post-refinement stage lacks result/refinement evidence")
                refinement = _verify_refinement(candidate["refinement_receipt"], f"{path}.refinement_receipt", source, result, str(expected_source_coordinate))
                if candidate["refinement_receipt_binding_sha256"] != refinement["receipt_sha256"]:
                    _fail(path, "refinement binding receipt reference is cross-wired")
            if failure_stage == "scoring":
                if candidate["scorer_v1_evidence"] is not None or candidate["pose_validity_receipt"] is not None:
                    _fail(path, "scoring failure fabricated scoring/validity evidence")
            elif failure_stage == "validity":
                if candidate["scorer_v1_evidence"] is None or candidate["pose_validity_receipt"] is not None:
                    _fail(path, "validity failure partial evidence is invalid")
            elif failure_stage is None:
                if candidate["scorer_v1_evidence"] is None or candidate["pose_validity_receipt"] is None:
                    _fail(path, "completed candidate lacks scorer/validity evidence")
            if candidate["scorer_v1_evidence"] is not None:
                if result is None:
                    _fail(path, "scorer evidence lacks result proposal")
                scorer_terms, score = _verify_scorer(candidate["scorer_v1_evidence"], f"{path}.scorer_v1_evidence", result)
                if candidate["scorer_v1_evidence_binding_sha256"] != candidate["scorer_v1_evidence"]["receipt_sha256"]:
                    _fail(path, "scorer binding receipt reference is cross-wired")
                for key in scorer_batch_fields:
                    scorer_batch_fields[key].add(scorer_terms[key])
            if candidate["pose_validity_receipt"] is not None:
                if result is None or refinement is None:
                    _fail(path, "validity evidence lacks result/refinement identity")
                _, valid = _verify_validity(candidate["pose_validity_receipt"], f"{path}.pose_validity_receipt", result, str(refinement["result_coordinate_sha256"]))
                if candidate["pose_validity_receipt_sha256"] != candidate["pose_validity_receipt"]["receipt_sha256"]:
                    _fail(path, "validity receipt reference is cross-wired")
            expected_status = "typed_execution_failure" if failure_stage is not None else "scored_success"
            expected_codes = [] if failure_code is None else [failure_code]

        if candidate["status"] != expected_status or candidate["typed_failure_codes"] != expected_codes:
            _fail(path, "candidate status/failure codes do not rederive")
        expected_result_coordinate = None if refinement is None else refinement["result_coordinate_sha256"]
        if candidate["result_coordinate_sha256"] != expected_result_coordinate or candidate["coordinate_sha256"] != (expected_result_coordinate or expected_source_coordinate):
            _fail(path, "candidate source-to-result coordinate lifecycle is cross-wired")
        for nested, reference, name in (
            (candidate["proposal_execution_receipt"], candidate["proposal_execution_receipt_sha256"], "proposal"),
            (candidate["refinement_receipt"], candidate["refinement_receipt_binding_sha256"], "refinement"),
            (candidate["scorer_v1_evidence"], candidate["scorer_v1_evidence_binding_sha256"], "scorer"),
            (candidate["pose_validity_receipt"], candidate["pose_validity_receipt_sha256"], "validity"),
        ):
            if nested is None and reference is not None:
                _fail(path, f"{name} receipt reference exists without payload")
            if nested is not None and reference != nested["receipt_sha256"]:
                _fail(path, f"{name} receipt reference is cross-wired")
        score_complete = score is not None and refinement is not None
        evidence_complete = expected_status == "scored_success"
        rank_eligible = score_complete
        valid_rank_eligible = rank_eligible and valid is True
        expected_score_hex = None if score is None else score.hex()
        for key, expected in (
            ("score_binary64_hex", expected_score_hex),
            ("evidence_complete", evidence_complete),
            ("score_evidence_complete", score_complete),
            ("rank_eligible", rank_eligible),
            ("score_rank_includes_pose_invalid_candidates", True),
            ("valid_rank_eligible", valid_rank_eligible),
            ("selection_eligible", valid_rank_eligible),
            ("denominator_slot_preserved", True),
        ):
            if candidate[key] != expected:
                _fail(f"{path}.{key}", "derived candidate field changed")
        candidate_receipts.append(_verify_receipt(candidate, path))
        state.append({"candidate": candidate, "proposal": proposal, "scorer_terms": scorer_terms, "score": score, "valid": valid, "rank_eligible": rank_eligible, "valid_rank_eligible": valid_rank_eligible, "result": result})

    if len(set(candidate_receipts)) != 64 or document["candidate_receipt_sha256s"] != candidate_receipts:
        _fail("$", "candidate receipts are duplicated or cross-wired")
    if any(len(values) > 1 for values in scorer_batch_fields.values()):
        _fail("$", "ScorerV1 batch semantics are cross-wired")
    generated = [row for row in state if row["proposal"] is not None]
    if len({row["candidate"]["source_proposal_sha256"] for row in generated}) != len(generated):
        _fail("$", "generated source proposal identities are not slot-unique")
    scored = [row for row in state if row["rank_eligible"]]
    refined = [
        row
        for row in state
        if row["candidate"]["refinement_receipt"] is not None
    ]
    if len({row["result"] for row in scored}) != len(scored):
        _fail("$", "scored result proposal identities are not slot-unique")
    for name, values, maximum in (
        (
            "scorer search row",
            {row["candidate"]["scorer_v1_evidence"]["search_row_sha256"] for row in scored},
            len(scored),
        ),
        (
            "scorer term row",
            {row["candidate"]["scorer_v1_evidence"]["search_term_row_receipt_sha256"] for row in scored},
            len(scored),
        ),
    ):
        if len(values) != maximum:
            _fail("$", f"{name} identities are not slot-unique")
    uniform_fields = (
        (
            "proposal generation input",
            {row["proposal"]["generation_input_receipt_sha256"] for row in generated},
        ),
        (
            "proposal generator config",
            {row["proposal"]["generator_config_sha256"] for row in generated},
        ),
        (
            "proposal generator implementation",
            {row["proposal"]["generator_implementation_source_sha256"] for row in generated},
        ),
        (
            "proposal generator component",
            {row["proposal"]["generator_component_id"] for row in generated},
        ),
        (
            "refiner config",
            {
                row["candidate"]["refinement_receipt"]["refiner_config_sha256"]
                for row in refined
            },
        ),
        (
            "refiner implementation",
            {
                row["candidate"]["refinement_receipt"][
                    "refiner_implementation_source_sha256"
                ]
                for row in refined
            },
        ),
        (
            "refinement source schema",
            {
                row["candidate"]["refinement_receipt"]["source_receipt"][
                    "source_receipt_schema_id"
                ]
                for row in refined
            },
        ),
        (
            "scorer source search result",
            {row["candidate"]["scorer_v1_evidence"]["source_search_result_receipt_sha256"] for row in scored},
        ),
        (
            "scorer implementation",
            {row["candidate"]["scorer_v1_evidence"]["scorer_implementation_source_sha256"] for row in scored},
        ),
        (
            "validity context",
            {row["candidate"]["pose_validity_receipt"]["validity_context_fingerprint_sha256"] for row in state if row["candidate"]["pose_validity_receipt"] is not None},
        ),
        (
            "validity config",
            {row["candidate"]["pose_validity_receipt"]["validity_config_fingerprint_sha256"] for row in state if row["candidate"]["pose_validity_receipt"] is not None},
        ),
        (
            "validity evaluator implementation",
            {row["candidate"]["pose_validity_receipt"]["evaluator_implementation_source_sha256"] for row in state if row["candidate"]["pose_validity_receipt"] is not None},
        ),
    )
    if any(len(values) > 1 for _, values in uniform_fields):
        _fail("$", "batch producer/config/context identity is cross-wired")
    proposal_inputs = {
        row["proposal"]["generation_input_receipt_sha256"] for row in generated
    }
    expected_source_receipt = allocation["document"]["features"][
        "exact_v11_source_receipt_sha256"
    ]
    if proposal_inputs and proposal_inputs != {expected_source_receipt}:
        _fail("$", "proposal generation input is not the exact V1.1 source receipt")
    primary = sorted((row for row in state if row["rank_eligible"]), key=lambda row: (float(row["score"]), int(row["candidate"]["slot_index"]), str(row["result"])))
    rank_by_slot = {int(row["candidate"]["slot_index"]): rank for rank, row in enumerate(primary, 1)}
    valid_rows = [row for row in primary if row["valid_rank_eligible"]]
    valid_rank_by_slot = {int(row["candidate"]["slot_index"]): rank for rank, row in enumerate(valid_rows, 1)}
    for slot_index, row in enumerate(state):
        candidate = row["candidate"]
        rank = rank_by_slot.get(slot_index)
        valid_rank = valid_rank_by_slot.get(slot_index)
        for key, expected in (
            ("stable_rank", rank), ("top1_member", rank == 1),
            ("top5_member", rank is not None and rank <= TOP_K_LIMIT),
            ("stable_valid_rank", valid_rank), ("valid_top1_member", valid_rank == 1),
            ("valid_top5_member", valid_rank is not None and valid_rank <= TOP_K_LIMIT),
        ):
            if candidate[key] != expected:
                _fail(f"$.candidates[{slot_index}].{key}", "ranking field does not replay")
    primary_slots = [int(row["candidate"]["slot_index"]) for row in primary]
    valid_slots = [int(row["candidate"]["slot_index"]) for row in valid_rows]
    top1 = primary_slots[0] if primary_slots else None
    valid_top1 = valid_slots[0] if valid_slots else None
    top1_valid = None if top1 is None else state[top1]["valid"]
    scored_success_count = sum(row["candidate"]["status"] == "scored_success" for row in state)
    score_complete_count = sum(bool(row["rank_eligible"]) for row in state)
    derived_root = {
        "scored_success_count": scored_success_count,
        "score_evidence_complete_count": score_complete_count,
        "typed_failure_count": 64 - scored_success_count,
        "stable_ranking_slot_indices": primary_slots,
        "top1_slot_index": top1,
        "top5_slot_indices": primary_slots[:TOP_K_LIMIT],
        "primary_ranking_semantics": "all_complete_score_evidence_geometrically_admitted_candidates_including_pose_invalid_and_validity_unavailable",
        "top1_pose_valid": top1_valid,
        "invalid_top1": None if top1_valid is None else not top1_valid,
        "stable_valid_ranking_slot_indices": valid_slots,
        "valid_top1_slot_index": valid_top1,
        "valid_top5_slot_indices": valid_slots[:TOP_K_LIMIT],
        "valid_only_ranking_semantics": "primary_score_order_filtered_by_complete_pose_validity_true",
        "ranking_order": "finite_total_score_ascending_then_slot_index_then_result_sha256",
        "top_k_limit": TOP_K_LIMIT,
        "denominator_failure_complete": True,
        "denominator_failure_completeness_scope": (
            DENOMINATOR_FAILURE_COMPLETENESS_SCOPE
        ),
        "evidence_completion_flags_caller_supplied": False,
        "rank_eligibility_caller_supplied": False,
        "top_k_membership_caller_supplied": False,
    }
    for key, expected in derived_root.items():
        if document[key] != expected:
            _fail(f"$.{key}", "batch field does not replay")
    _exact_bool(
        document["activation_evidence_eligible"],
        "$.activation_evidence_eligible",
        False,
    )
    if document["activation_evidence_blockers"] != list(ACTIVATION_EVIDENCE_BLOCKERS):
        _fail("$.activation_evidence_blockers", "activation blockers changed")
    for key in (
        "historical_execution_authorized", "fresh_holdout_execution_authorized",
        "molecular_execution_authorized", "product_mutation_authorized",
        "existing_rank_auto_change_authorized", "customer_pose_emission_authorized",
        "public_benchmark_execution_authorized", "public_or_scientific_claim_authorized",
        "stage0_admission_authority",
    ):
        _exact_bool(document[key], f"$.{key}", False)
    _verify_all_receipts(document)
    _require_false_authority(document)
    _verify_receipt(document, "$")
    return document


def verify_artifact(path: Path) -> dict[str, object]:
    document, raw = load_artifact(path)
    _verify_pipeline(document)
    return {
        "schema_id": "betelgeuze.engine_v2_mixed64_candidate_evidence_artifact_verification/1.0.0",
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "candidate_denominator": 64,
        "full_cartesian_geometric_replay": True,
        "primary_and_valid_rankings_rederived": True,
        "authority_granted": False,
        "verification_blockers": [],
        "activation_evidence_eligible": False,
        "activation_evidence_blockers": list(ACTIVATION_EVIDENCE_BLOCKERS),
        "verified": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path, help="canonical persisted candidate-evidence JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = verify_artifact(args.artifact)
    except (ArtifactVerificationError, MemoryError, OverflowError, RecursionError) as exc:
        print(
            json.dumps(
                {
                    "schema_id": "betelgeuze.engine_v2_mixed64_candidate_evidence_artifact_verification/1.0.0",
                    "authority_granted": False,
                    "verification_blockers": [str(exc)],
                    "activation_evidence_eligible": False,
                    "activation_evidence_blockers": list(
                        ACTIVATION_EVIDENCE_BLOCKERS
                    ),
                    "verified": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
