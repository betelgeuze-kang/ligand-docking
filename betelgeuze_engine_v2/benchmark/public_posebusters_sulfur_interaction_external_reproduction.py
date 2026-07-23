"""Two-host reproduction and independent-review receipts for sulfur interaction.

The local neutral-thioether interaction observation deliberately remains
immutable and claim-closed.  This module preregisters one external-host rerun,
retains the complete second observation, compares every counterpoise SCF and
all 308 dispositions, and supports a role-separated detached Ed25519 reviewer
approval.

Even an accepted review closes only the bounded two-host/review evidence gap.
The orientation counterexample, small model scope, missing receptor/solvent
context, and incomplete AD4 score keep chemical and product claims closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from typing import Any
import zipfile

from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (
    ReferenceMinimizationValidationEd25519Error,
    ed25519_public_key_bytes,
    sign_ed25519,
    verify_ed25519,
)

from . import public_posebusters_sulfur_interaction_energy as interaction
from . import public_posebusters_sulfur_qm_esp as qm_esp
from . import public_posebusters_vina_sulfur_type_invariance as vina_invariance


POSEBUSTERS_SULFUR_REPRODUCTION_WORK_ORDER_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_interaction_"
    "external_reproduction_work_order/1.0.0"
)
POSEBUSTERS_SULFUR_REPRODUCTION_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_interaction_"
    "external_reproduction_result/1.0.0"
)
POSEBUSTERS_SULFUR_REPRODUCTION_COMPARISON_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_interaction_"
    "cross_host_comparison/1.0.0"
)
POSEBUSTERS_SULFUR_REPRODUCTION_REVIEW_REQUEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_interaction_"
    "review_signing_request/1.0.0"
)
POSEBUSTERS_SULFUR_REPRODUCTION_REVIEW_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_sulfur_interaction_"
    "independent_review/1.0.0"
)

POSEBUSTERS_SULFUR_REPRODUCTION_MAX_WORK_ORDER_BYTES = 4 * 1024 * 1024
POSEBUSTERS_SULFUR_REPRODUCTION_MAX_RESULT_BYTES = 32 * 1024 * 1024
POSEBUSTERS_SULFUR_REPRODUCTION_MAX_REVIEW_BYTES = 4 * 1024 * 1024
POSEBUSTERS_SULFUR_REPRODUCTION_MAX_SIGNING_BYTES = 4 * 1024 * 1024
POSEBUSTERS_SULFUR_REPRODUCTION_MAX_ENGINE_WHEEL_BYTES = 16 * 1024 * 1024
POSEBUSTERS_SULFUR_REPRODUCTION_MAX_ENGINE_WHEEL_MEMBERS = 4096
POSEBUSTERS_SULFUR_REPRODUCTION_SIGNATURE_ALGORITHM = "ed25519"
POSEBUSTERS_SULFUR_REPRODUCTION_MAX_REVIEW_VALIDITY = timedelta(days=30)

_KEY_ID_RE = re.compile(r"\A[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,127}\Z")
_COUNTERPOISE_COMPONENTS = (
    "complex",
    "acceptor_with_probe_ghost_basis",
    "probe_with_acceptor_ghost_basis",
)
_HOST_SPECIFIC_BASE_RUNTIME_FIELDS = {
    "affinity_cpu_count",
    "cpu_identity_sha256",
    "cpu_model",
}
_RUNTIME_TOP_DIGEST_FIELDS = {
    "base_pyscf_runtime_sha256",
    "runtime_identity_sha256",
}

POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION = {
    "all_case_denominator": (
        interaction.POSEBUSTERS_SULFUR_INTERACTION_ALL_CASE_DENOMINATOR
    ),
    "scope_case_count": len(
        interaction.POSEBUSTERS_SULFUR_INTERACTION_SCOPE_CASE_IDS
    ),
    "expected_point_count": 21,
    "expected_counterpoise_scf_count": 63,
    "cross_host_numeric_tolerances": {
        # The SCF convergence tolerance is 1e-9 Hartree.  Five times that
        # tolerance is allowed per total energy; the three-term counterpoise
        # bound is rounded upward after conversion to kcal/mol.
        "maximum_scf_total_energy_absolute_error_hartree": float(5.0e-9).hex(),
        "maximum_counterpoise_interaction_absolute_error_kcal_per_mol": (
            float(1.0e-5).hex()
        ),
        "maximum_counterpoise_interaction_absolute_error_hartree": (
            float(1.0e-5 / interaction._HARTREE_TO_KCAL_PER_MOL).hex()
        ),
        "maximum_dispersion_energy_absolute_error_hartree": float(1.0e-12).hex(),
        "maximum_scf_cycle_count_delta": 1,
    },
    "exact_invariants": [
        "ordered_308_case_dispositions",
        "ordered_21_geometry_identities",
        "geometry_and_ad4_pair_term_hashes",
        "electron_ao_and_grid_counts",
        "case_gate_outcomes_and_minimum_distances",
        "implementation_source_members",
        "engine_pyscf_dispersion_and_vina_source_binaries",
        "shared_runtime_projection_except_host_cpu_identity_and_affinity",
    ],
    "host_policy": {
        "baseline_and_external_host_identities_preregistered": True,
        "baseline_and_external_host_identities_distinct": True,
        "external_executor_identity_preregistered": True,
        "single_use_external_execution_nonce_preregistered": True,
        "execution_nonce_reuse_checked_by_independent_reviewer": True,
        "cpu_identity_is_recorded_but_same_cpu_model_is_allowed": True,
        "physical_host_independence_requires_reviewer_attestation": True,
    },
    "review_policy": {
        "signature_algorithm": POSEBUSTERS_SULFUR_REPRODUCTION_SIGNATURE_ALGORITHM,
        "maximum_validity_seconds": int(
            POSEBUSTERS_SULFUR_REPRODUCTION_MAX_REVIEW_VALIDITY.total_seconds()
        ),
        "reviewer_distinct_from_work_order_operator_external_executor_and_hosts": (
            True
        ),
        "trusted_public_keys_out_of_band": True,
        "revocation_and_supersession_inputs_required": True,
        "private_key_forbidden_in_signing_request_and_cli": True,
    },
}


def _canonical_bytes(value: object) -> bytes:
    return interaction._canonical_bytes(value)


def _canonical_sha256(value: object) -> str:
    return interaction._canonical_sha256(value)


POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION
)

_REQUIRED_REVIEW_CHECK_IDS = (
    "work_order_registered_before_external_qm_execution",
    "external_execution_nonce_single_use_confirmed_against_operator_registry",
    "baseline_and_external_physical_hosts_independently_verified",
    "baseline_and_external_host_and_executor_identities_distinct",
    "source_binary_environment_and_dependency_projection_verified",
    "all_308_dispositions_21_points_and_63_scfs_reviewed",
    "counterpoise_cross_host_numeric_tolerances_passed",
    "all_failure_and_abstention_rows_retained",
    "orientation_control_counterexample_reviewed",
)
_REQUIRED_REVIEW_LIMITATION_IDS = (
    "one_oh_donor_probe_does_not_cover_other_donor_classes",
    "three_fixed_gas_phase_models_are_not_representative_chemistry",
    "receptor_solvent_and_complete_ad4_score_are_not_evaluated",
    "orientation_directionality_remains_unresolved",
    "review_approval_does_not_authorize_scientific_or_product_promotion",
)
_POST_REVIEW_BLOCKERS = (
    "neutral_thioether_directionality_unresolved",
    "additional_donor_classes_and_conformations_required",
    "receptor_and_solvent_context_required",
    "complete_ad4_and_product_scorer_validation_required",
    "representative_chemistry_confidence_interval_required",
    "public_docking_calibration_and_ood_validation_required",
)
_REVIEW_PAYLOAD_FIELDS = {
    "schema_id",
    "work_order_receipt_sha256",
    "result_receipt_sha256",
    "baseline_observation_receipt_sha256",
    "external_observation_receipt_sha256",
    "comparison_sha256",
    "reviewer_identity_sha256",
    "reviewer_key_id",
    "reviewed_at_utc",
    "expires_at_utc",
    "review_nonce_sha256",
    "accepted_check_ids",
    "acknowledged_limitation_ids",
    "physical_host_independence_reviewed",
    "source_binary_environment_dependency_identity_reviewed",
    "all_failure_and_abstention_rows_reviewed",
    "review_outcome",
    "second_cpu_host_reproduced",
    "independent_reviewer_receipt_approved",
    "chemical_acceptor_semantics_adjudicated",
    "scientifically_validated",
    "benchmark_executed",
    "product_promotion_allowed",
    "claim_safe",
    "scientific_blockers",
    "revoked",
    "superseded",
    "review_receipt_sha256",
}


class PoseBustersSulfurReproductionError(ValueError):
    """The external work order, result, review, or trust input is invalid."""


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PoseBustersSulfurReproductionError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _key_id(value: object) -> str:
    if not isinstance(value, str) or _KEY_ID_RE.fullmatch(value) is None:
        raise PoseBustersSulfurReproductionError("reviewer key id is invalid")
    return value


def _key_bytes(value: bytes | str, *, name: str) -> bytes:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        try:
            raw = bytes.fromhex(value)
        except ValueError as exc:
            raise PoseBustersSulfurReproductionError(
                f"{name} is not hexadecimal"
            ) from exc
    else:
        raise PoseBustersSulfurReproductionError(f"{name} must be bytes or hex")
    if len(raw) != 32:
        raise PoseBustersSulfurReproductionError(f"{name} must be 32 bytes")
    return raw


def _utc(value: object, *, name: str) -> str:
    try:
        return interaction._utc_timestamp(value, name=name)
    except interaction.PoseBustersSulfurInteractionError as exc:
        raise PoseBustersSulfurReproductionError(str(exc)) from exc


def _parse_utc(value: object, *, name: str) -> datetime:
    normalized = _utc(value, name=name)
    return datetime.fromisoformat(normalized.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


def _float_from_hex(value: object, *, name: str) -> float:
    if not isinstance(value, str):
        raise PoseBustersSulfurReproductionError(f"{name} must be binary64 hex")
    try:
        result = float.fromhex(value)
    except ValueError as exc:
        raise PoseBustersSulfurReproductionError(
            f"{name} must be binary64 hex"
        ) from exc
    if not math.isfinite(result):
        raise PoseBustersSulfurReproductionError(f"{name} must be finite")
    return result


def _source_members() -> list[dict[str, str]]:
    modules = {
        "public_posebusters_sulfur_interaction_energy.py": interaction,
        "public_posebusters_sulfur_interaction_external_reproduction.py": (
            sys.modules[__name__]
        ),
        "public_posebusters_sulfur_qm_esp.py": qm_esp,
        "public_posebusters_vina_sulfur_type_invariance.py": vina_invariance,
    }
    rows: list[dict[str, str]] = []
    for relative_path, module in sorted(modules.items()):
        module_path = getattr(module, "__file__", None)
        if not isinstance(module_path, str) or not module_path:
            raise PoseBustersSulfurReproductionError(
                f"{relative_path} source path is unavailable"
            )
        rows.append(
            {
                "relative_path": relative_path,
                "sha256": interaction._source_file_sha256(module_path),
            }
        )
    return rows


def _read_private_receipt(
    path: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
    expected_schema_id: str,
    maximum_bytes: int,
) -> tuple[dict[str, Any], bytes]:
    try:
        return interaction._read_private_canonical_receipt(
            path,
            expected_receipt_sha256=expected_receipt_sha256,
            expected_schema_id=expected_schema_id,
            maximum_bytes=maximum_bytes,
        )
    except interaction.PoseBustersSulfurInteractionError as exc:
        raise PoseBustersSulfurReproductionError(str(exc)) from exc


def _write_private(
    payload: Mapping[str, Any],
    output_path: str | os.PathLike[str],
) -> None:
    try:
        interaction._write_private_no_overwrite(payload, output_path)
    except interaction.PoseBustersSulfurInteractionError as exc:
        raise PoseBustersSulfurReproductionError(str(exc)) from exc


def _write_private_bytes_no_overwrite(
    payload: bytes,
    output_path: str | os.PathLike[str],
) -> None:
    if not isinstance(payload, bytes) or not payload:
        raise PoseBustersSulfurReproductionError(
            "private byte payload must be non-empty bytes"
        )
    if len(payload) > POSEBUSTERS_SULFUR_REPRODUCTION_MAX_SIGNING_BYTES:
        raise PoseBustersSulfurReproductionError(
            "private byte payload is oversized"
        )
    output = Path(output_path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = -1
    try:
        descriptor = os.open(
            output,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise PoseBustersSulfurReproductionError(
            f"private byte output already exists: {output}"
        ) from exc
    except OSError:
        if descriptor >= 0:
            os.close(descriptor)
        raise


def _require_receipt_mapping(
    value: object,
    *,
    expected_schema_id: str,
    name: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PoseBustersSulfurReproductionError(f"{name} must be a mapping")
    receipt = dict(value)
    if receipt.get("schema_id") != expected_schema_id:
        raise PoseBustersSulfurReproductionError(f"{name} schema is invalid")
    receipt_sha = _digest(receipt.pop("receipt_sha256", None), name=name)
    if receipt_sha != _canonical_sha256(receipt):
        raise PoseBustersSulfurReproductionError(f"{name} digest is invalid")
    return {**receipt, "receipt_sha256": receipt_sha}


def _reject_private_signing_material(value: object) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise PoseBustersSulfurReproductionError(
                    "review signing request contains a non-string field"
                )
            lowered = key.lower()
            if (
                "private_key" in lowered
                or "signing_key" in lowered
                or lowered in {"secret", "secret_hex", "seed", "seed_hex"}
            ):
                raise PoseBustersSulfurReproductionError(
                    "review signing request contains private signing material"
                )
            _reject_private_signing_material(child)
    elif isinstance(value, list):
        for child in value:
            _reject_private_signing_material(child)


def _regular_file_sha256(
    path: str | os.PathLike[str],
    *,
    maximum_bytes: int,
    name: str,
) -> tuple[str, int]:
    try:
        digest, size, _mode = interaction._hash_regular_file(
            Path(path),
            maximum_bytes=maximum_bytes,
        )
    except (OSError, ValueError) as exc:
        raise PoseBustersSulfurReproductionError(
            f"{name} cannot be hashed safely"
        ) from exc
    return digest, size


def _engine_wheel_binding(
    wheel_path: str | os.PathLike[str],
    *,
    expected_sha256: str,
    source_members: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    expected = _digest(expected_sha256, name="expected Engine v2 wheel")
    path = Path(wheel_path)
    digest, size = _regular_file_sha256(
        path,
        maximum_bytes=POSEBUSTERS_SULFUR_REPRODUCTION_MAX_ENGINE_WHEEL_BYTES,
        name="Engine v2 wheel",
    )
    if (
        digest != expected
        or not path.name.startswith("betelgeuze_engine_v2-0.2.0rc2-")
        or path.suffix != ".whl"
    ):
        raise PoseBustersSulfurReproductionError(
            "Engine v2 wheel filename or digest is not caller-frozen"
        )
    content: dict[str, dict[str, Any]] = {}
    total = 0
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if (
                not infos
                or len(infos)
                > POSEBUSTERS_SULFUR_REPRODUCTION_MAX_ENGINE_WHEEL_MEMBERS
            ):
                raise PoseBustersSulfurReproductionError(
                    "Engine v2 wheel member count is invalid"
                )
            for info in infos:
                relative = PurePosixPath(info.filename)
                if (
                    info.is_dir()
                    or relative.is_absolute()
                    or ".." in relative.parts
                    or info.flag_bits & 0x1
                ):
                    if info.is_dir():
                        continue
                    raise PoseBustersSulfurReproductionError(
                        "Engine v2 wheel contains an unsafe member"
                    )
                mode = (info.external_attr >> 16) & 0o170000
                if mode not in (0, stat.S_IFREG):
                    raise PoseBustersSulfurReproductionError(
                        "Engine v2 wheel contains a non-regular member"
                    )
                if info.file_size < 0:
                    raise PoseBustersSulfurReproductionError(
                        "Engine v2 wheel member size is invalid"
                    )
                total += info.file_size
                if total > POSEBUSTERS_SULFUR_REPRODUCTION_MAX_ENGINE_WHEEL_BYTES:
                    raise PoseBustersSulfurReproductionError(
                        "Engine v2 wheel uncompressed payload is oversized"
                    )
                with archive.open(info) as handle:
                    payload = handle.read(
                        POSEBUSTERS_SULFUR_REPRODUCTION_MAX_ENGINE_WHEEL_BYTES + 1
                    )
                if len(payload) != info.file_size:
                    raise PoseBustersSulfurReproductionError(
                        "Engine v2 wheel member size changed"
                    )
                content[relative.as_posix()] = {
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                }
    except (OSError, zipfile.BadZipFile) as exc:
        raise PoseBustersSulfurReproductionError(
            "Engine v2 wheel is not a valid bounded archive"
        ) from exc
    for row in source_members:
        relative_path = row["relative_path"]
        member = (
            "betelgeuze_engine_v2/benchmark/"
            + PurePosixPath(relative_path).name
        )
        observed = content.get(member)
        if observed is None or observed["sha256"] != row["sha256"]:
            raise PoseBustersSulfurReproductionError(
                f"Engine v2 wheel source member disagrees: {relative_path}"
            )
    return {
        "filename": path.name,
        "sha256": digest,
        "size_bytes": size,
        "content_sha256": _canonical_sha256(content),
        "content_file_count": len(content),
        "content_size_bytes": total,
        "bound_source_members": [dict(row) for row in source_members],
    }


def _baseline_receipts(
    protocol_path: str | os.PathLike[str],
    observation_path: str | os.PathLike[str],
    *,
    expected_protocol_sha256: str,
    expected_observation_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    protocol, protocol_source = _read_private_receipt(
        protocol_path,
        expected_receipt_sha256=expected_protocol_sha256,
        expected_schema_id=interaction.POSEBUSTERS_SULFUR_INTERACTION_PROTOCOL_SCHEMA_ID,
        maximum_bytes=interaction.POSEBUSTERS_SULFUR_INTERACTION_MAX_PROTOCOL_BYTES,
    )
    observation, observation_source = _read_private_receipt(
        observation_path,
        expected_receipt_sha256=expected_observation_sha256,
        expected_schema_id=(
            interaction.POSEBUSTERS_SULFUR_INTERACTION_OBSERVATION_SCHEMA_ID
        ),
        maximum_bytes=interaction.POSEBUSTERS_SULFUR_INTERACTION_MAX_OBSERVATION_BYTES,
    )
    protocol_file_sha = hashlib.sha256(protocol_source).hexdigest()
    observation_file_sha = hashlib.sha256(observation_source).hexdigest()
    if (
        observation.get("protocol_receipt_sha256") != protocol["receipt_sha256"]
        or observation.get("protocol_receipt_file_sha256") != protocol_file_sha
        or observation.get("configuration_sha256")
        != interaction.POSEBUSTERS_SULFUR_INTERACTION_CONFIGURATION_SHA256
        or observation.get("implementation_source_sha256")
        != protocol.get("implementation_source_sha256")
        or observation.get("evaluated_case_count") != 3
        or observation.get("qm_failure_case_count") != 0
        or observation.get("scope_abstention_case_count") != 305
        or observation.get("local_three_model_oh_acceptor_gate_pass") is not True
        or observation.get("local_ad4_sa_pair_profile_gate_pass") is not True
        or observation.get("chemical_acceptor_semantics_adjudicated") is not False
        or observation.get("scientifically_validated") is not False
        or observation.get("claim_safe") is not False
    ):
        raise PoseBustersSulfurReproductionError(
            "baseline interaction protocol or observation is not the accepted local input"
        )
    return (
        protocol,
        observation,
        {
            "baseline_protocol_file_sha256": protocol_file_sha,
            "baseline_observation_file_sha256": observation_file_sha,
        },
    )


def _runtime_shared_projection(runtime: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(runtime, Mapping):
        raise PoseBustersSulfurReproductionError(
            "interaction runtime identity must be a mapping"
        )
    base = runtime.get("base_pyscf_runtime")
    if not isinstance(base, Mapping):
        raise PoseBustersSulfurReproductionError(
            "base PySCF runtime identity is missing"
        )
    for field_name in (
        "cpu_identity_sha256",
        "cpu_model",
        "affinity_cpu_count",
        "kernel_release",
        "libc_name",
        "libc_version",
        "python_executable_sha256",
        "distribution_payloads",
        "native_thread_pool_identity_sha256",
        "numpy_configuration_sha256",
        "scipy_configuration_sha256",
        "wheel_sha256",
    ):
        if field_name not in base:
            raise PoseBustersSulfurReproductionError(
                f"base runtime field is missing: {field_name}"
            )
    shared_base = {
        key: value
        for key, value in base.items()
        if key not in _HOST_SPECIFIC_BASE_RUNTIME_FIELDS
    }
    shared_top = {
        key: value
        for key, value in runtime.items()
        if key
        not in {
            "base_pyscf_runtime",
            *_RUNTIME_TOP_DIGEST_FIELDS,
        }
    }
    return {**shared_top, "base_pyscf_runtime": shared_base}


def _validated_runtime_identity(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PoseBustersSulfurReproductionError(
            "interaction runtime identity must be a mapping"
        )
    runtime = dict(value)
    runtime_sha = _digest(
        runtime.pop("runtime_identity_sha256", None),
        name="runtime identity",
    )
    if runtime_sha != _canonical_sha256(runtime):
        raise PoseBustersSulfurReproductionError(
            "interaction runtime identity digest is invalid"
        )
    base = runtime.get("base_pyscf_runtime")
    if not isinstance(base, Mapping):
        raise PoseBustersSulfurReproductionError(
            "base PySCF runtime identity is missing"
        )
    base_sha = _digest(
        runtime.get("base_pyscf_runtime_sha256"),
        name="base PySCF runtime identity",
    )
    if base_sha != _canonical_sha256(base):
        raise PoseBustersSulfurReproductionError(
            "base PySCF runtime identity digest is invalid"
        )
    result = {**runtime, "runtime_identity_sha256": runtime_sha}
    _runtime_shared_projection(result)
    _runtime_host_projection(result)
    return result


def _runtime_host_projection(runtime: Mapping[str, Any]) -> dict[str, Any]:
    base = runtime.get("base_pyscf_runtime")
    if not isinstance(base, Mapping):
        raise PoseBustersSulfurReproductionError(
            "base PySCF runtime identity is missing"
        )
    return {
        "runtime_identity_sha256": _digest(
            runtime.get("runtime_identity_sha256"),
            name="runtime identity",
        ),
        "cpu_identity_sha256": _digest(
            base.get("cpu_identity_sha256"),
            name="runtime CPU identity",
        ),
        "cpu_model": base.get("cpu_model"),
        "affinity_cpu_count": base.get("affinity_cpu_count"),
        "kernel_release": base.get("kernel_release"),
    }


def _point_static_projection(point: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in point.items()
        if key
        not in {
            "counterpoise",
            "counterpoise_interaction_energy_kcal_per_mol_binary64_hex",
            "error_code",
            "error_message_sha256",
            "error_type",
            "status",
        }
    }


def _case_static_projection(case: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in case.items()
        if key not in {"point_rows", "metrics"}
    }


def _metric_minimum_distance(case: Mapping[str, Any]) -> object:
    metrics = case.get("metrics")
    if not isinstance(metrics, Mapping):
        return None
    profile = metrics.get("qm_profile")
    if not isinstance(profile, Mapping):
        return None
    return profile.get("minimum_distance_angstrom_binary64_hex")


def compare_posebusters_sulfur_cross_host_observations(
    baseline: Mapping[str, Any],
    external: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare every disposition, point, and SCF under preregistered bounds."""

    structural_mismatches = 0
    external_failure_points = 0
    compared_points = 0
    compared_scfs = 0
    interaction_errors: list[float] = []
    interaction_hartree_errors: list[float] = []
    total_energy_errors: list[float] = []
    dispersion_errors: list[float] = []
    cycle_deltas: list[int] = []
    all_failure_rows_retained = True

    baseline_rows = baseline.get("case_rows")
    external_rows = external.get("case_rows")
    if (
        not isinstance(baseline_rows, list)
        or not isinstance(external_rows, list)
        or len(baseline_rows)
        != interaction.POSEBUSTERS_SULFUR_INTERACTION_ALL_CASE_DENOMINATOR
        or len(external_rows) != len(baseline_rows)
    ):
        raise PoseBustersSulfurReproductionError(
            "cross-host observations must retain all 308 case rows"
        )

    top_exact_fields = (
        "schema_id",
        "all_case_denominator",
        "scope_case_count",
        "scope_abstention_case_count",
        "configuration",
        "configuration_sha256",
        "implementation_source_members",
        "implementation_source_sha256",
        "protocol_receipt_sha256",
        "protocol_receipt_file_sha256",
        "protocol_registered_before_qm_execution",
        "ad4_pair_formula_executed",
        "all_scoped_cases_evaluated",
        "bounded_local_interaction_evidence_generated",
        "benchmark_executed",
        "independent_reviewer_receipt_approved",
        "second_cpu_host_reproduced",
        "product_promotion_allowed",
        "scientific_blockers",
    )
    structural_mismatches += sum(
        baseline.get(field_name) != external.get(field_name)
        for field_name in top_exact_fields
    )

    for baseline_case, external_case in zip(
        baseline_rows,
        external_rows,
        strict=True,
    ):
        if not isinstance(baseline_case, Mapping) or not isinstance(
            external_case, Mapping
        ):
            structural_mismatches += 1
            all_failure_rows_retained = False
            continue
        if (
            baseline_case.get("case_id") != external_case.get("case_id")
            or baseline_case.get("protocol_status")
            != external_case.get("protocol_status")
        ):
            structural_mismatches += 1
        baseline_status = baseline_case.get("status")
        if baseline_status == "abstain_protocol_scope":
            if dict(baseline_case) != dict(external_case):
                structural_mismatches += 1
            continue
        if baseline_status != "evaluated":
            raise PoseBustersSulfurReproductionError(
                "baseline contains an unexpected scoped failure"
            )
        if external_case.get("status") != "evaluated":
            structural_mismatches += 1
        if _case_static_projection(baseline_case) != _case_static_projection(
            external_case
        ):
            structural_mismatches += 1
        baseline_points = baseline_case.get("point_rows")
        external_points = external_case.get("point_rows")
        if (
            not isinstance(baseline_points, list)
            or not isinstance(external_points, list)
            or len(baseline_points) != 7
            or len(external_points) != len(baseline_points)
        ):
            structural_mismatches += 1
            all_failure_rows_retained = False
            continue
        for baseline_point, external_point in zip(
            baseline_points,
            external_points,
            strict=True,
        ):
            compared_points += 1
            if not isinstance(baseline_point, Mapping) or not isinstance(
                external_point, Mapping
            ):
                structural_mismatches += 1
                all_failure_rows_retained = False
                continue
            if _point_static_projection(
                baseline_point
            ) != _point_static_projection(external_point):
                structural_mismatches += 1
            if external_point.get("status") != "evaluated":
                external_failure_points += 1
                if (
                    external_point.get("status") != "qm_failure"
                    or not external_point.get("error_code")
                    or not external_point.get("error_type")
                    or not isinstance(
                        external_point.get("error_message_sha256"), str
                    )
                ):
                    all_failure_rows_retained = False
                else:
                    try:
                        _digest(
                            external_point["error_message_sha256"],
                            name="external point error message",
                        )
                    except PoseBustersSulfurReproductionError:
                        all_failure_rows_retained = False
                continue
            if (
                baseline_point.get("status") != "evaluated"
                or any(
                    baseline_point.get(field_name) is not None
                    or external_point.get(field_name) is not None
                    for field_name in (
                        "error_code",
                        "error_type",
                        "error_message_sha256",
                    )
                )
            ):
                structural_mismatches += 1
            baseline_cp = baseline_point.get("counterpoise")
            external_cp = external_point.get("counterpoise")
            if not isinstance(baseline_cp, Mapping) or not isinstance(
                external_cp, Mapping
            ):
                structural_mismatches += 1
                continue
            if any(
                not isinstance(counterpoise.get(component_name), Mapping)
                for counterpoise in (baseline_cp, external_cp)
                for component_name in _COUNTERPOISE_COMPONENTS
            ):
                structural_mismatches += 1
                continue
            baseline_interaction = _float_from_hex(
                baseline_point.get(
                    "counterpoise_interaction_energy_kcal_per_mol_binary64_hex"
                ),
                name="baseline counterpoise interaction energy",
            )
            external_interaction = _float_from_hex(
                external_point.get(
                    "counterpoise_interaction_energy_kcal_per_mol_binary64_hex"
                ),
                name="external counterpoise interaction energy",
            )
            interaction_errors.append(abs(external_interaction - baseline_interaction))
            for label, point, counterpoise in (
                ("baseline", baseline_point, baseline_cp),
                ("external", external_point, external_cp),
            ):
                stated_kcal = _float_from_hex(
                    counterpoise.get(
                        "counterpoise_interaction_energy_kcal_per_mol_binary64_hex"
                    ),
                    name=f"{label} counterpoise interaction kcal",
                )
                stated_hartree = _float_from_hex(
                    counterpoise.get(
                        "counterpoise_interaction_energy_hartree_binary64_hex"
                    ),
                    name=f"{label} counterpoise interaction Hartree",
                )
                derived_hartree = (
                    _float_from_hex(
                        counterpoise["complex"].get(
                            "total_energy_hartree_binary64_hex"
                        ),
                        name=f"{label} complex total energy",
                    )
                    - _float_from_hex(
                        counterpoise["acceptor_with_probe_ghost_basis"].get(
                            "total_energy_hartree_binary64_hex"
                        ),
                        name=f"{label} acceptor total energy",
                    )
                    - _float_from_hex(
                        counterpoise["probe_with_acceptor_ghost_basis"].get(
                            "total_energy_hartree_binary64_hex"
                        ),
                        name=f"{label} probe total energy",
                    )
                )
                if (
                    point.get(
                        "counterpoise_interaction_energy_kcal_per_mol_binary64_hex"
                    )
                    != counterpoise.get(
                        "counterpoise_interaction_energy_kcal_per_mol_binary64_hex"
                    )
                    or derived_hartree != stated_hartree
                    or (
                        stated_hartree * interaction._HARTREE_TO_KCAL_PER_MOL
                        != stated_kcal
                    )
                ):
                    structural_mismatches += 1
            baseline_interaction_hartree = _float_from_hex(
                baseline_cp.get(
                    "counterpoise_interaction_energy_hartree_binary64_hex"
                ),
                name="baseline counterpoise interaction energy Hartree",
            )
            external_interaction_hartree = _float_from_hex(
                external_cp.get(
                    "counterpoise_interaction_energy_hartree_binary64_hex"
                ),
                name="external counterpoise interaction energy Hartree",
            )
            interaction_hartree_errors.append(
                abs(external_interaction_hartree - baseline_interaction_hartree)
            )
            for component_name in _COUNTERPOISE_COMPONENTS:
                baseline_component = baseline_cp.get(component_name)
                external_component = external_cp.get(component_name)
                if not isinstance(baseline_component, Mapping) or not isinstance(
                    external_component, Mapping
                ):
                    structural_mismatches += 1
                    continue
                compared_scfs += 1
                for field_name in (
                    "electron_count",
                    "atomic_orbital_count",
                    "integration_grid_point_count",
                    "converged",
                ):
                    if baseline_component.get(field_name) != external_component.get(
                        field_name
                    ):
                        structural_mismatches += 1
                baseline_total = _float_from_hex(
                    baseline_component.get("total_energy_hartree_binary64_hex"),
                    name="baseline SCF total energy",
                )
                external_total = _float_from_hex(
                    external_component.get("total_energy_hartree_binary64_hex"),
                    name="external SCF total energy",
                )
                total_energy_errors.append(abs(external_total - baseline_total))
                baseline_dispersion = _float_from_hex(
                    baseline_component.get("dispersion_energy_hartree_binary64_hex"),
                    name="baseline dispersion energy",
                )
                external_dispersion = _float_from_hex(
                    external_component.get("dispersion_energy_hartree_binary64_hex"),
                    name="external dispersion energy",
                )
                dispersion_errors.append(
                    abs(external_dispersion - baseline_dispersion)
                )
                baseline_cycles = baseline_component.get("cycle_count")
                external_cycles = external_component.get("cycle_count")
                if type(baseline_cycles) is not int or type(external_cycles) is not int:
                    structural_mismatches += 1
                else:
                    cycle_deltas.append(abs(external_cycles - baseline_cycles))
        baseline_metrics = baseline_case.get("metrics")
        external_metrics = external_case.get("metrics")
        if not isinstance(baseline_metrics, Mapping) or not isinstance(
            external_metrics, Mapping
        ):
            structural_mismatches += 1
        else:
            if baseline_metrics.get("binding_gates") != external_metrics.get(
                "binding_gates"
            ):
                structural_mismatches += 1
            if _metric_minimum_distance(baseline_case) != _metric_minimum_distance(
                external_case
            ):
                structural_mismatches += 1

    tolerance = POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION[
        "cross_host_numeric_tolerances"
    ]
    total_limit = float.fromhex(
        tolerance["maximum_scf_total_energy_absolute_error_hartree"]
    )
    interaction_limit = float.fromhex(
        tolerance[
            "maximum_counterpoise_interaction_absolute_error_kcal_per_mol"
        ]
    )
    interaction_hartree_limit = float.fromhex(
        tolerance[
            "maximum_counterpoise_interaction_absolute_error_hartree"
        ]
    )
    dispersion_limit = float.fromhex(
        tolerance["maximum_dispersion_energy_absolute_error_hartree"]
    )
    cycle_limit = tolerance["maximum_scf_cycle_count_delta"]
    max_total = max(total_energy_errors, default=math.inf)
    max_interaction = max(interaction_errors, default=math.inf)
    max_interaction_hartree = max(interaction_hartree_errors, default=math.inf)
    max_dispersion = max(dispersion_errors, default=math.inf)
    max_cycle = max(cycle_deltas, default=10**9)
    rms_interaction = (
        math.sqrt(
            math.fsum(value * value for value in interaction_errors)
            / len(interaction_errors)
        )
        if interaction_errors
        else math.inf
    )
    exact_counts = (
        compared_points
        == POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION["expected_point_count"]
        and compared_scfs
        == POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION[
            "expected_counterpoise_scf_count"
        ]
    )
    external_top_gate_pass = (
        external.get("evaluated_case_count") == 3
        and external.get("qm_failure_case_count") == 0
        and external.get("scope_abstention_case_count") == 305
        and external.get("local_three_model_oh_acceptor_gate_pass") is True
        and external.get("local_ad4_sa_pair_profile_gate_pass") is True
        and external.get("chemical_acceptor_semantics_adjudicated") is False
        and external.get("scientifically_validated") is False
        and external.get("claim_safe") is False
    )
    numeric_pass = (
        max_total <= total_limit
        and max_interaction <= interaction_limit
        and max_interaction_hartree <= interaction_hartree_limit
        and max_dispersion <= dispersion_limit
        and max_cycle <= cycle_limit
    )
    reproduction_pass = (
        structural_mismatches == 0
        and external_failure_points == 0
        and all_failure_rows_retained
        and exact_counts
        and external_top_gate_pass
        and numeric_pass
    )

    def finite_hex(value: float) -> str | None:
        return value.hex() if math.isfinite(value) else None

    payload = {
        "schema_id": POSEBUSTERS_SULFUR_REPRODUCTION_COMPARISON_SCHEMA_ID,
        "configuration_sha256": (
            POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION_SHA256
        ),
        "all_case_denominator": len(external_rows),
        "compared_point_count": compared_points,
        "compared_counterpoise_scf_count": compared_scfs,
        "external_qm_failure_point_count": external_failure_points,
        "structural_mismatch_count": structural_mismatches,
        "all_failure_and_abstention_rows_retained": all_failure_rows_retained,
        "maximum_scf_total_energy_absolute_error_hartree_binary64_hex": (
            finite_hex(max_total)
        ),
        "maximum_counterpoise_interaction_absolute_error_kcal_per_mol_binary64_hex": (
            finite_hex(max_interaction)
        ),
        "maximum_counterpoise_interaction_absolute_error_hartree_binary64_hex": (
            finite_hex(max_interaction_hartree)
        ),
        "rms_counterpoise_interaction_error_kcal_per_mol_binary64_hex": (
            finite_hex(rms_interaction)
        ),
        "maximum_dispersion_energy_absolute_error_hartree_binary64_hex": (
            finite_hex(max_dispersion)
        ),
        "maximum_scf_cycle_count_delta": (
            max_cycle if max_cycle != 10**9 else None
        ),
        "numeric_tolerance_pass": numeric_pass,
        "structural_invariants_pass": structural_mismatches == 0 and exact_counts,
        "external_local_gate_outcomes_match": external_top_gate_pass,
        "scientific_case_rows_bitwise_equal": (
            baseline_rows == external_rows
        ),
        "cross_host_numerical_reproduction_pass": reproduction_pass,
    }
    return {**payload, "comparison_sha256": _canonical_sha256(payload)}


def _work_order_payload(
    *,
    registered_utc: str,
    baseline_protocol: Mapping[str, Any],
    baseline_observation: Mapping[str, Any],
    baseline_file_hashes: Mapping[str, str],
    baseline_host_identity_sha256: str,
    expected_external_host_identity_sha256: str,
    work_order_operator_identity_sha256: str,
    external_execution_operator_identity_sha256: str,
    external_execution_nonce_sha256: str,
    engine_wheel_binding: Mapping[str, Any],
    source_members: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    baseline_runtime = baseline_observation["pyscf_interaction_runtime_identity"]
    payload = {
        "schema_id": POSEBUSTERS_SULFUR_REPRODUCTION_WORK_ORDER_SCHEMA_ID,
        "registered_utc": registered_utc,
        "baseline_protocol_receipt_sha256": baseline_protocol["receipt_sha256"],
        "baseline_observation_receipt_sha256": (
            baseline_observation["receipt_sha256"]
        ),
        **dict(baseline_file_hashes),
        "baseline_observation_utc": baseline_observation["observation_utc"],
        "baseline_runtime_identity_sha256": baseline_observation[
            "pyscf_interaction_runtime_identity_sha256"
        ],
        "baseline_runtime_host_projection": _runtime_host_projection(
            baseline_runtime
        ),
        "baseline_runtime_shared_projection_sha256": _canonical_sha256(
            _runtime_shared_projection(baseline_runtime)
        ),
        "baseline_host_identity_sha256": baseline_host_identity_sha256,
        "expected_external_host_identity_sha256": (
            expected_external_host_identity_sha256
        ),
        "work_order_operator_identity_sha256": (
            work_order_operator_identity_sha256
        ),
        "external_execution_operator_identity_sha256": (
            external_execution_operator_identity_sha256
        ),
        "external_execution_nonce_sha256": external_execution_nonce_sha256,
        "engine_wheel_binding": dict(engine_wheel_binding),
        "pyscf_wheel_binding": dict(baseline_protocol["pyscf_wheel_binding"]),
        "pyscf_dispersion_wheel_binding": dict(
            baseline_protocol["pyscf_dispersion_wheel_binding"]
        ),
        "vina_ad4_source_binding": dict(
            baseline_protocol["vina_ad4_source_binding"]
        ),
        "implementation_source_members": [dict(row) for row in source_members],
        "implementation_source_sha256": _canonical_sha256(source_members),
        "configuration": POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION,
        "configuration_sha256": (
            POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION_SHA256
        ),
        "external_qm_execution_performed": False,
        "two_cpu_host_reproduced": False,
        "independent_reviewer_receipt_approved": False,
        "chemical_acceptor_semantics_adjudicated": False,
        "scientifically_validated": False,
        "product_promotion_allowed": False,
        "claim_safe": False,
    }
    return {**payload, "receipt_sha256": _canonical_sha256(payload)}


def materialize_posebusters_sulfur_reproduction_work_order(
    baseline_protocol_path: str | os.PathLike[str],
    baseline_observation_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    *,
    expected_baseline_protocol_sha256: str,
    expected_baseline_observation_sha256: str,
    expected_engine_wheel_sha256: str,
    baseline_host_identity_sha256: str,
    expected_external_host_identity_sha256: str,
    work_order_operator_identity_sha256: str,
    external_execution_operator_identity_sha256: str,
    external_execution_nonce_sha256: str,
    registered_utc: str,
) -> dict[str, Any]:
    """Preregister one external host and execution nonce without running QM."""

    registered = _utc(registered_utc, name="work-order registration UTC")
    protocol, observation, file_hashes = _baseline_receipts(
        baseline_protocol_path,
        baseline_observation_path,
        expected_protocol_sha256=expected_baseline_protocol_sha256,
        expected_observation_sha256=expected_baseline_observation_sha256,
    )
    if _parse_utc(
        registered,
        name="work-order registration UTC",
    ) <= _parse_utc(
        observation["observation_utc"],
        name="baseline observation UTC",
    ):
        raise PoseBustersSulfurReproductionError(
            "work order must be registered after the baseline observation"
        )
    identity_values = (
        _digest(baseline_host_identity_sha256, name="baseline host identity"),
        _digest(
            expected_external_host_identity_sha256,
            name="expected external host identity",
        ),
        _digest(
            work_order_operator_identity_sha256,
            name="work-order operator identity",
        ),
        _digest(
            external_execution_operator_identity_sha256,
            name="external execution operator identity",
        ),
    )
    if len(set(identity_values)) != len(identity_values):
        raise PoseBustersSulfurReproductionError(
            "host and operator identities must be role-separated"
        )
    nonce = _digest(external_execution_nonce_sha256, name="external execution nonce")
    if nonce in identity_values:
        raise PoseBustersSulfurReproductionError(
            "external execution nonce reuses an identity"
        )
    source_members = _source_members()
    engine_binding = _engine_wheel_binding(
        engine_wheel_path,
        expected_sha256=expected_engine_wheel_sha256,
        source_members=source_members,
    )
    return _work_order_payload(
        registered_utc=registered,
        baseline_protocol=protocol,
        baseline_observation=observation,
        baseline_file_hashes=file_hashes,
        baseline_host_identity_sha256=identity_values[0],
        expected_external_host_identity_sha256=identity_values[1],
        work_order_operator_identity_sha256=identity_values[2],
        external_execution_operator_identity_sha256=identity_values[3],
        external_execution_nonce_sha256=nonce,
        engine_wheel_binding=engine_binding,
        source_members=source_members,
    )


def verify_posebusters_sulfur_reproduction_work_order(
    work_order_path: str | os.PathLike[str],
    baseline_protocol_path: str | os.PathLike[str],
    baseline_observation_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    *,
    expected_work_order_sha256: str,
    expected_baseline_protocol_sha256: str,
    expected_baseline_observation_sha256: str,
    expected_engine_wheel_sha256: str,
) -> dict[str, Any]:
    raw, source = _read_private_receipt(
        work_order_path,
        expected_receipt_sha256=expected_work_order_sha256,
        expected_schema_id=POSEBUSTERS_SULFUR_REPRODUCTION_WORK_ORDER_SCHEMA_ID,
        maximum_bytes=POSEBUSTERS_SULFUR_REPRODUCTION_MAX_WORK_ORDER_BYTES,
    )
    expected = materialize_posebusters_sulfur_reproduction_work_order(
        baseline_protocol_path,
        baseline_observation_path,
        engine_wheel_path,
        expected_baseline_protocol_sha256=expected_baseline_protocol_sha256,
        expected_baseline_observation_sha256=expected_baseline_observation_sha256,
        expected_engine_wheel_sha256=expected_engine_wheel_sha256,
        baseline_host_identity_sha256=raw.get("baseline_host_identity_sha256"),
        expected_external_host_identity_sha256=raw.get(
            "expected_external_host_identity_sha256"
        ),
        work_order_operator_identity_sha256=raw.get(
            "work_order_operator_identity_sha256"
        ),
        external_execution_operator_identity_sha256=raw.get(
            "external_execution_operator_identity_sha256"
        ),
        external_execution_nonce_sha256=raw.get(
            "external_execution_nonce_sha256"
        ),
        registered_utc=raw.get("registered_utc"),
    )
    if source != _canonical_bytes(expected) + b"\n":
        raise PoseBustersSulfurReproductionError(
            "external reproduction work order failed exact reconstruction"
        )
    return expected


def _result_payload(
    *,
    work_order: Mapping[str, Any],
    work_order_file_sha256: str,
    baseline_observation: Mapping[str, Any],
    observed_utc: str,
    external_runtime_identity: Mapping[str, Any] | None,
    external_observation: Mapping[str, Any] | None,
    status: str,
    error_code: str | None,
    error_type: str | None,
    error_message_sha256: str | None,
) -> dict[str, Any]:
    shared_runtime_equal = False
    comparison: dict[str, Any] | None = None
    if external_runtime_identity is not None:
        shared_runtime_equal = _runtime_shared_projection(
            baseline_observation["pyscf_interaction_runtime_identity"]
        ) == _runtime_shared_projection(external_runtime_identity)
    if external_observation is not None:
        comparison = compare_posebusters_sulfur_cross_host_observations(
            baseline_observation,
            external_observation,
        )
    reproduced = (
        status == "reproduced"
        and shared_runtime_equal
        and comparison is not None
        and comparison["cross_host_numerical_reproduction_pass"] is True
    )
    blockers = [
        blocker
        for blocker in interaction.POSEBUSTERS_SULFUR_INTERACTION_SCIENTIFIC_BLOCKERS
        if blocker != "second_cpu_host_reproduction_missing" or not reproduced
    ]
    payload = {
        "schema_id": POSEBUSTERS_SULFUR_REPRODUCTION_RESULT_SCHEMA_ID,
        "observed_utc": observed_utc,
        "work_order_receipt_sha256": work_order["receipt_sha256"],
        "work_order_file_sha256": work_order_file_sha256,
        "baseline_protocol_receipt_sha256": work_order[
            "baseline_protocol_receipt_sha256"
        ],
        "baseline_observation_receipt_sha256": work_order[
            "baseline_observation_receipt_sha256"
        ],
        "baseline_host_identity_sha256": work_order[
            "baseline_host_identity_sha256"
        ],
        "external_host_identity_sha256": work_order[
            "expected_external_host_identity_sha256"
        ],
        "external_execution_operator_identity_sha256": work_order[
            "external_execution_operator_identity_sha256"
        ],
        "external_execution_nonce_sha256": work_order[
            "external_execution_nonce_sha256"
        ],
        "engine_wheel_binding": dict(work_order["engine_wheel_binding"]),
        "implementation_source_sha256": work_order[
            "implementation_source_sha256"
        ],
        "configuration_sha256": (
            POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION_SHA256
        ),
        "status": status,
        "external_execution_performed": True,
        "execution_nonce_single_use_operator_attestation_required": True,
        "error_code": error_code,
        "error_type": error_type,
        "error_message_sha256": error_message_sha256,
        "external_runtime_identity": (
            dict(external_runtime_identity)
            if external_runtime_identity is not None
            else None
        ),
        "external_runtime_host_projection": (
            _runtime_host_projection(external_runtime_identity)
            if external_runtime_identity is not None
            else None
        ),
        "shared_runtime_projection_equal": shared_runtime_equal,
        "external_observation": (
            dict(external_observation) if external_observation is not None else None
        ),
        "external_observation_receipt_sha256": (
            external_observation["receipt_sha256"]
            if external_observation is not None
            else None
        ),
        "comparison": comparison,
        "all_case_denominator": (
            interaction.POSEBUSTERS_SULFUR_INTERACTION_ALL_CASE_DENOMINATOR
        ),
        "second_cpu_host_reproduced": reproduced,
        "independent_reviewer_receipt_approved": False,
        "chemical_acceptor_semantics_adjudicated": False,
        "scientific_blockers": blockers,
        "scientifically_validated": False,
        "benchmark_executed": False,
        "product_promotion_allowed": False,
        "claim_safe": False,
    }
    return {**payload, "receipt_sha256": _canonical_sha256(payload)}


def materialize_posebusters_sulfur_reproduction_result(
    work_order_path: str | os.PathLike[str],
    baseline_protocol_path: str | os.PathLike[str],
    baseline_observation_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    vina_source_root: str | os.PathLike[str],
    pyscf_wheel_path: str | os.PathLike[str],
    pyscf_dispersion_wheel_path: str | os.PathLike[str],
    *,
    expected_work_order_sha256: str,
    expected_baseline_protocol_sha256: str,
    expected_baseline_observation_sha256: str,
    expected_engine_wheel_sha256: str,
    expected_pyscf_wheel_sha256: str,
    expected_pyscf_dispersion_wheel_sha256: str,
    observed_external_host_identity_sha256: str,
    observed_external_execution_operator_identity_sha256: str,
    external_observation_utc: str,
) -> dict[str, Any]:
    """Execute or retain one preregistered external-host reproduction attempt."""

    work_order = verify_posebusters_sulfur_reproduction_work_order(
        work_order_path,
        baseline_protocol_path,
        baseline_observation_path,
        engine_wheel_path,
        expected_work_order_sha256=expected_work_order_sha256,
        expected_baseline_protocol_sha256=expected_baseline_protocol_sha256,
        expected_baseline_observation_sha256=expected_baseline_observation_sha256,
        expected_engine_wheel_sha256=expected_engine_wheel_sha256,
    )
    observed_host = _digest(
        observed_external_host_identity_sha256,
        name="observed external host identity",
    )
    observed_operator = _digest(
        observed_external_execution_operator_identity_sha256,
        name="observed external execution operator identity",
    )
    if (
        observed_host != work_order["expected_external_host_identity_sha256"]
        or observed_operator
        != work_order["external_execution_operator_identity_sha256"]
    ):
        raise PoseBustersSulfurReproductionError(
            "external host or executor identity is not the preregistered identity"
        )
    observed = _utc(external_observation_utc, name="external observation UTC")
    if (
        _parse_utc(observed, name="external observation UTC")
        <= _parse_utc(work_order["registered_utc"], name="work-order registration UTC")
    ):
        raise PoseBustersSulfurReproductionError(
            "external observation must follow work-order registration"
        )
    _, baseline_observation, _ = _baseline_receipts(
        baseline_protocol_path,
        baseline_observation_path,
        expected_protocol_sha256=expected_baseline_protocol_sha256,
        expected_observation_sha256=expected_baseline_observation_sha256,
    )
    work_order_file_sha, _size = _regular_file_sha256(
        work_order_path,
        maximum_bytes=POSEBUSTERS_SULFUR_REPRODUCTION_MAX_WORK_ORDER_BYTES,
        name="work order",
    )
    runtime: interaction._PyscfInteractionRuntime | None = None
    try:
        runtime = interaction._PyscfInteractionRuntime(
            pyscf_wheel_path,
            pyscf_dispersion_wheel_path,
            expected_pyscf_wheel_sha256=expected_pyscf_wheel_sha256,
            expected_pyscf_dispersion_wheel_sha256=(
                expected_pyscf_dispersion_wheel_sha256
            ),
        )
    except Exception as exc:  # retain bounded external runtime failures
        normalized = interaction._normalized_error(exc)
        return _result_payload(
            work_order=work_order,
            work_order_file_sha256=work_order_file_sha,
            baseline_observation=baseline_observation,
            observed_utc=observed,
            external_runtime_identity=None,
            external_observation=None,
            status="blocked_external_runtime",
            error_code="external_runtime_initialization_failed",
            error_type=type(exc).__name__,
            error_message_sha256=hashlib.sha256(normalized).hexdigest(),
        )
    if _runtime_shared_projection(
        runtime.identity
    ) != _runtime_shared_projection(
        baseline_observation["pyscf_interaction_runtime_identity"]
    ):
        return _result_payload(
            work_order=work_order,
            work_order_file_sha256=work_order_file_sha,
            baseline_observation=baseline_observation,
            observed_utc=observed,
            external_runtime_identity=runtime.identity,
            external_observation=None,
            status="blocked_shared_runtime_mismatch",
            error_code="shared_runtime_projection_mismatch",
            error_type=None,
            error_message_sha256=None,
        )
    try:
        external_observation = (
            interaction.materialize_posebusters_sulfur_interaction_observation(
                baseline_protocol_path,
                vina_source_root,
                pyscf_wheel_path,
                pyscf_dispersion_wheel_path,
                expected_protocol_receipt_sha256=(
                    expected_baseline_protocol_sha256
                ),
                expected_pyscf_wheel_sha256=expected_pyscf_wheel_sha256,
                expected_pyscf_dispersion_wheel_sha256=(
                    expected_pyscf_dispersion_wheel_sha256
                ),
                observation_utc=observed,
                _runtime=runtime,
            )
        )
    except Exception as exc:  # retain bounded post-runtime execution failures
        normalized = interaction._normalized_error(exc)
        return _result_payload(
            work_order=work_order,
            work_order_file_sha256=work_order_file_sha,
            baseline_observation=baseline_observation,
            observed_utc=observed,
            external_runtime_identity=runtime.identity,
            external_observation=None,
            status="blocked_external_execution",
            error_code="external_observation_materialization_failed",
            error_type=type(exc).__name__,
            error_message_sha256=hashlib.sha256(normalized).hexdigest(),
        )
    comparison = compare_posebusters_sulfur_cross_host_observations(
        baseline_observation,
        external_observation,
    )
    status = (
        "reproduced"
        if comparison["cross_host_numerical_reproduction_pass"]
        else "cross_host_comparison_failed"
    )
    return _result_payload(
        work_order=work_order,
        work_order_file_sha256=work_order_file_sha,
        baseline_observation=baseline_observation,
        observed_utc=observed,
        external_runtime_identity=runtime.identity,
        external_observation=external_observation,
        status=status,
        error_code=None,
        error_type=None,
        error_message_sha256=None,
    )


def _validate_embedded_observation(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PoseBustersSulfurReproductionError(
            "external result does not contain an observation"
        )
    observation = dict(value)
    if (
        observation.get("schema_id")
        != interaction.POSEBUSTERS_SULFUR_INTERACTION_OBSERVATION_SCHEMA_ID
    ):
        raise PoseBustersSulfurReproductionError(
            "embedded external observation schema is invalid"
        )
    receipt_sha = _digest(
        observation.get("receipt_sha256"),
        name="embedded external observation",
    )
    payload = dict(observation)
    payload.pop("receipt_sha256")
    if _canonical_sha256(payload) != receipt_sha:
        raise PoseBustersSulfurReproductionError(
            "embedded external observation digest is invalid"
        )
    return observation


def verify_posebusters_sulfur_reproduction_result(
    result_path: str | os.PathLike[str],
    work_order_path: str | os.PathLike[str],
    baseline_protocol_path: str | os.PathLike[str],
    baseline_observation_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    *,
    expected_result_sha256: str,
    expected_work_order_sha256: str,
    expected_baseline_protocol_sha256: str,
    expected_baseline_observation_sha256: str,
    expected_engine_wheel_sha256: str,
) -> dict[str, Any]:
    """Verify result custody and rederive every cross-host comparison metric."""

    raw, source = _read_private_receipt(
        result_path,
        expected_receipt_sha256=expected_result_sha256,
        expected_schema_id=POSEBUSTERS_SULFUR_REPRODUCTION_RESULT_SCHEMA_ID,
        maximum_bytes=POSEBUSTERS_SULFUR_REPRODUCTION_MAX_RESULT_BYTES,
    )
    work_order = verify_posebusters_sulfur_reproduction_work_order(
        work_order_path,
        baseline_protocol_path,
        baseline_observation_path,
        engine_wheel_path,
        expected_work_order_sha256=expected_work_order_sha256,
        expected_baseline_protocol_sha256=expected_baseline_protocol_sha256,
        expected_baseline_observation_sha256=expected_baseline_observation_sha256,
        expected_engine_wheel_sha256=expected_engine_wheel_sha256,
    )
    _, baseline_observation, _ = _baseline_receipts(
        baseline_protocol_path,
        baseline_observation_path,
        expected_protocol_sha256=expected_baseline_protocol_sha256,
        expected_observation_sha256=expected_baseline_observation_sha256,
    )
    work_order_file_sha, _size = _regular_file_sha256(
        work_order_path,
        maximum_bytes=POSEBUSTERS_SULFUR_REPRODUCTION_MAX_WORK_ORDER_BYTES,
        name="work order",
    )
    observed_utc = _utc(
        raw.get("observed_utc"),
        name="external observation UTC",
    )
    if _parse_utc(
        observed_utc,
        name="external observation UTC",
    ) <= _parse_utc(
        work_order["registered_utc"],
        name="work-order registration UTC",
    ):
        raise PoseBustersSulfurReproductionError(
            "external result predates its work-order registration"
        )
    external_runtime = raw.get("external_runtime_identity")
    if external_runtime is not None:
        external_runtime = _validated_runtime_identity(external_runtime)
    external_observation = raw.get("external_observation")
    if external_observation is not None:
        external_observation = _validate_embedded_observation(external_observation)
        if (
            external_runtime is None
            or external_observation.get("observation_utc") != observed_utc
            or external_observation.get("pyscf_interaction_runtime_identity")
            != external_runtime
            or external_observation.get(
                "pyscf_interaction_runtime_identity_sha256"
            )
            != external_runtime["runtime_identity_sha256"]
        ):
            raise PoseBustersSulfurReproductionError(
                "external observation is not bound to the result runtime and time"
            )
    status = raw.get("status")
    error_code = raw.get("error_code")
    error_type = raw.get("error_type")
    error_message_sha256 = raw.get("error_message_sha256")
    no_error = (
        error_code is None
        and error_type is None
        and error_message_sha256 is None
    )
    if status in {"reproduced", "cross_host_comparison_failed"}:
        if (
            external_runtime is None
            or external_observation is None
            or not no_error
        ):
            raise PoseBustersSulfurReproductionError(
                "cross-host comparison result fields are invalid"
            )
        if _runtime_shared_projection(
            external_runtime
        ) != _runtime_shared_projection(
            baseline_observation["pyscf_interaction_runtime_identity"]
        ):
            raise PoseBustersSulfurReproductionError(
                "compared result does not retain the shared runtime projection"
            )
        comparison = compare_posebusters_sulfur_cross_host_observations(
            baseline_observation,
            external_observation,
        )
        derived_status = (
            "reproduced"
            if comparison["cross_host_numerical_reproduction_pass"]
            else "cross_host_comparison_failed"
        )
        if status != derived_status:
            raise PoseBustersSulfurReproductionError(
                "cross-host result status disagrees with rederived metrics"
            )
    elif status == "blocked_external_runtime":
        if (
            external_runtime is not None
            or external_observation is not None
            or error_code != "external_runtime_initialization_failed"
            or not isinstance(error_type, str)
            or not error_type
        ):
            raise PoseBustersSulfurReproductionError(
                "blocked external-runtime result fields are invalid"
            )
        _digest(
            error_message_sha256,
            name="external runtime error message",
        )
    elif status == "blocked_shared_runtime_mismatch":
        if (
            external_runtime is None
            or external_observation is not None
            or error_code != "shared_runtime_projection_mismatch"
            or error_type is not None
            or error_message_sha256 is not None
            or _runtime_shared_projection(external_runtime)
            == _runtime_shared_projection(
                baseline_observation["pyscf_interaction_runtime_identity"]
            )
        ):
            raise PoseBustersSulfurReproductionError(
                "blocked shared-runtime result fields are invalid"
            )
    elif status == "blocked_external_execution":
        if (
            external_runtime is None
            or external_observation is not None
            or error_code != "external_observation_materialization_failed"
            or not isinstance(error_type, str)
            or not error_type
            or _runtime_shared_projection(external_runtime)
            != _runtime_shared_projection(
                baseline_observation["pyscf_interaction_runtime_identity"]
            )
        ):
            raise PoseBustersSulfurReproductionError(
                "blocked external-execution result fields are invalid"
            )
        _digest(
            error_message_sha256,
            name="external execution error message",
        )
    else:
        raise PoseBustersSulfurReproductionError(
            "external reproduction result status is invalid"
        )
    expected = _result_payload(
        work_order=work_order,
        work_order_file_sha256=work_order_file_sha,
        baseline_observation=baseline_observation,
        observed_utc=observed_utc,
        external_runtime_identity=(
            dict(external_runtime) if external_runtime is not None else None
        ),
        external_observation=external_observation,
        status=status,
        error_code=error_code,
        error_type=error_type,
        error_message_sha256=error_message_sha256,
    )
    if source != _canonical_bytes(expected) + b"\n":
        raise PoseBustersSulfurReproductionError(
            "external reproduction result failed exact reconstruction"
        )
    return expected


@dataclass(frozen=True, slots=True)
class PoseBustersSulfurReviewerTrustAnchor:
    """Out-of-band reviewer identity and raw Ed25519 public key."""

    reviewer_identity_sha256: str
    verification_key: bytes = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reviewer_identity_sha256",
            _digest(self.reviewer_identity_sha256, name="trusted reviewer identity"),
        )
        object.__setattr__(
            self,
            "verification_key",
            _key_bytes(self.verification_key, name="reviewer verification key"),
        )


def _review_payload(
    *,
    work_order: Mapping[str, Any],
    result: Mapping[str, Any],
    reviewer_identity_sha256: str,
    reviewer_key_id: str,
    reviewed_at_utc: str,
    expires_at_utc: str,
    review_nonce_sha256: str,
) -> dict[str, Any]:
    work_order = _require_receipt_mapping(
        work_order,
        expected_schema_id=POSEBUSTERS_SULFUR_REPRODUCTION_WORK_ORDER_SCHEMA_ID,
        name="external reproduction work order",
    )
    result = _require_receipt_mapping(
        result,
        expected_schema_id=POSEBUSTERS_SULFUR_REPRODUCTION_RESULT_SCHEMA_ID,
        name="external reproduction result",
    )
    comparison = result.get("comparison")
    if (
        result.get("work_order_receipt_sha256")
        != work_order["receipt_sha256"]
        or result.get("status") != "reproduced"
        or result.get("second_cpu_host_reproduced") is not True
        or result.get("shared_runtime_projection_equal") is not True
        or not isinstance(comparison, Mapping)
        or comparison.get("cross_host_numerical_reproduction_pass") is not True
        or result.get("external_observation_receipt_sha256") is None
    ):
        raise PoseBustersSulfurReproductionError(
            "independent review requires a passing two-host result"
        )
    reviewer = _digest(reviewer_identity_sha256, name="reviewer identity")
    nested_role_values = [
        _digest(
            work_order[field_name],
            name=f"work-order role {field_name}",
        )
        for field_name in (
            "baseline_host_identity_sha256",
            "expected_external_host_identity_sha256",
            "work_order_operator_identity_sha256",
            "external_execution_operator_identity_sha256",
        )
    ]
    if len(nested_role_values) != len(set(nested_role_values)):
        raise PoseBustersSulfurReproductionError(
            "work-order host and operator roles are not separated"
        )
    nested_roles = set(nested_role_values)
    if reviewer in nested_roles:
        raise PoseBustersSulfurReproductionError(
            "independent reviewer must be distinct from host and operator roles"
        )
    reviewed = _parse_utc(reviewed_at_utc, name="reviewed_at")
    expires = _parse_utc(expires_at_utc, name="expires_at")
    if (
        reviewed < _parse_utc(result["observed_utc"], name="external observation UTC")
        or expires <= reviewed
        or expires - reviewed > POSEBUSTERS_SULFUR_REPRODUCTION_MAX_REVIEW_VALIDITY
    ):
        raise PoseBustersSulfurReproductionError(
            "review validity window is invalid"
        )
    nonce = _digest(review_nonce_sha256, name="review nonce")
    if nonce in {
        work_order["external_execution_nonce_sha256"],
        *nested_roles,
    }:
        raise PoseBustersSulfurReproductionError(
            "review nonce reuses an execution or identity value"
        )
    payload = {
        "schema_id": POSEBUSTERS_SULFUR_REPRODUCTION_REVIEW_SCHEMA_ID,
        "work_order_receipt_sha256": work_order["receipt_sha256"],
        "result_receipt_sha256": result["receipt_sha256"],
        "baseline_observation_receipt_sha256": result[
            "baseline_observation_receipt_sha256"
        ],
        "external_observation_receipt_sha256": result[
            "external_observation_receipt_sha256"
        ],
        "comparison_sha256": comparison["comparison_sha256"],
        "reviewer_identity_sha256": reviewer,
        "reviewer_key_id": _key_id(reviewer_key_id),
        "reviewed_at_utc": reviewed_at_utc,
        "expires_at_utc": expires_at_utc,
        "review_nonce_sha256": nonce,
        "accepted_check_ids": list(_REQUIRED_REVIEW_CHECK_IDS),
        "acknowledged_limitation_ids": list(_REQUIRED_REVIEW_LIMITATION_IDS),
        "physical_host_independence_reviewed": True,
        "source_binary_environment_dependency_identity_reviewed": True,
        "all_failure_and_abstention_rows_reviewed": True,
        "review_outcome": "accepted",
        "second_cpu_host_reproduced": True,
        "independent_reviewer_receipt_approved": True,
        "chemical_acceptor_semantics_adjudicated": False,
        "scientifically_validated": False,
        "benchmark_executed": False,
        "product_promotion_allowed": False,
        "claim_safe": False,
        "scientific_blockers": list(_POST_REVIEW_BLOCKERS),
        "revoked": False,
        "superseded": False,
    }
    return {**payload, "review_receipt_sha256": _canonical_sha256(payload)}


def build_posebusters_sulfur_review_signing_request(
    *,
    work_order: Mapping[str, Any],
    result: Mapping[str, Any],
    reviewer_identity_sha256: str,
    reviewer_key_id: str,
    reviewed_at_utc: str,
    expires_at_utc: str,
    review_nonce_sha256: str,
) -> dict[str, Any]:
    """Build canonical secret-free bytes for an external reviewer signer."""

    payload = _review_payload(
        work_order=work_order,
        result=result,
        reviewer_identity_sha256=reviewer_identity_sha256,
        reviewer_key_id=reviewer_key_id,
        reviewed_at_utc=_utc(reviewed_at_utc, name="reviewed_at"),
        expires_at_utc=_utc(expires_at_utc, name="expires_at"),
        review_nonce_sha256=review_nonce_sha256,
    )
    projection = {
        "schema_id": POSEBUSTERS_SULFUR_REPRODUCTION_REVIEW_REQUEST_SCHEMA_ID,
        "signature_algorithm": POSEBUSTERS_SULFUR_REPRODUCTION_SIGNATURE_ALGORITHM,
        "reviewer_identity_sha256": payload["reviewer_identity_sha256"],
        "reviewer_key_id": payload["reviewer_key_id"],
        "review_payload": payload,
        "signing_bytes_sha256": hashlib.sha256(_canonical_bytes(payload)).hexdigest(),
    }
    return {**projection, "request_sha256": _canonical_sha256(projection)}


def require_posebusters_sulfur_review_signing_request(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PoseBustersSulfurReproductionError(
            "review signing request must be a mapping"
        )
    request = dict(value)
    _reject_private_signing_material(request)
    expected_fields = {
        "schema_id",
        "signature_algorithm",
        "reviewer_identity_sha256",
        "reviewer_key_id",
        "review_payload",
        "signing_bytes_sha256",
        "request_sha256",
    }
    if set(request) != expected_fields:
        raise PoseBustersSulfurReproductionError(
            "review signing request fields are invalid"
        )
    request_sha = _digest(request.pop("request_sha256"), name="review request")
    if request_sha != _canonical_sha256(request):
        raise PoseBustersSulfurReproductionError(
            "review signing request digest is invalid"
        )
    payload = request.get("review_payload")
    if not isinstance(payload, Mapping) or "signature" in payload:
        raise PoseBustersSulfurReproductionError(
            "review signing request payload is invalid"
        )
    payload_dict = dict(payload)
    if set(payload_dict) != _REVIEW_PAYLOAD_FIELDS:
        raise PoseBustersSulfurReproductionError(
            "unsigned review payload fields are invalid"
        )
    receipt_sha = _digest(
        payload_dict.pop("review_receipt_sha256", None),
        name="unsigned review receipt",
    )
    if receipt_sha != _canonical_sha256(payload_dict):
        raise PoseBustersSulfurReproductionError(
            "unsigned review receipt digest is invalid"
        )
    payload_dict["review_receipt_sha256"] = receipt_sha
    request_reviewer = _digest(
        request.get("reviewer_identity_sha256"),
        name="review request reviewer identity",
    )
    request_key_id = _key_id(request.get("reviewer_key_id"))
    for field_name in (
        "work_order_receipt_sha256",
        "result_receipt_sha256",
        "baseline_observation_receipt_sha256",
        "external_observation_receipt_sha256",
        "comparison_sha256",
        "reviewer_identity_sha256",
        "review_nonce_sha256",
    ):
        _digest(payload_dict.get(field_name), name=f"review payload {field_name}")
    reviewed = _parse_utc(payload_dict.get("reviewed_at_utc"), name="reviewed_at")
    expires = _parse_utc(payload_dict.get("expires_at_utc"), name="expires_at")
    if (
        expires <= reviewed
        or expires - reviewed > POSEBUSTERS_SULFUR_REPRODUCTION_MAX_REVIEW_VALIDITY
    ):
        raise PoseBustersSulfurReproductionError(
            "unsigned review validity window is invalid"
        )
    if (
        request.get("schema_id")
        != POSEBUSTERS_SULFUR_REPRODUCTION_REVIEW_REQUEST_SCHEMA_ID
        or request.get("signature_algorithm")
        != POSEBUSTERS_SULFUR_REPRODUCTION_SIGNATURE_ALGORITHM
        or request_reviewer
        != payload_dict["reviewer_identity_sha256"]
        or request_key_id != _key_id(payload_dict["reviewer_key_id"])
        or payload_dict.get("schema_id")
        != POSEBUSTERS_SULFUR_REPRODUCTION_REVIEW_SCHEMA_ID
        or payload_dict.get("accepted_check_ids")
        != list(_REQUIRED_REVIEW_CHECK_IDS)
        or payload_dict.get("acknowledged_limitation_ids")
        != list(_REQUIRED_REVIEW_LIMITATION_IDS)
        or payload_dict.get("scientific_blockers")
        != list(_POST_REVIEW_BLOCKERS)
        or any(
            payload_dict.get(field_name) is not expected_value
            for field_name, expected_value in {
                "physical_host_independence_reviewed": True,
                "source_binary_environment_dependency_identity_reviewed": True,
                "all_failure_and_abstention_rows_reviewed": True,
                "second_cpu_host_reproduced": True,
                "independent_reviewer_receipt_approved": True,
                "chemical_acceptor_semantics_adjudicated": False,
                "scientifically_validated": False,
                "benchmark_executed": False,
                "product_promotion_allowed": False,
                "claim_safe": False,
                "revoked": False,
                "superseded": False,
            }.items()
        )
        or payload_dict.get("review_outcome") != "accepted"
        or _digest(
            request.get("signing_bytes_sha256"),
            name="review signing bytes",
        )
        != hashlib.sha256(_canonical_bytes(payload_dict)).hexdigest()
    ):
        raise PoseBustersSulfurReproductionError(
            "review signing request identity is cross-wired"
        )
    return {
        **request,
        "review_payload": payload_dict,
        "request_sha256": request_sha,
    }


def posebusters_sulfur_review_signing_bytes(value: Mapping[str, Any]) -> bytes:
    request = require_posebusters_sulfur_review_signing_request(value)
    return _canonical_bytes(request["review_payload"])


def attach_posebusters_sulfur_review_signature(
    request_value: Mapping[str, Any],
    *,
    signature_hex: str,
    verification_key: bytes | str,
) -> dict[str, Any]:
    """Verify and attach a detached signature; no private key is accepted."""

    request = require_posebusters_sulfur_review_signing_request(request_value)
    public_key = _key_bytes(verification_key, name="reviewer verification key")
    try:
        verified = verify_ed25519(
            _canonical_bytes(request["review_payload"]),
            signature_hex,
            public_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise PoseBustersSulfurReproductionError(
            "review signature verifier is unavailable"
        ) from exc
    if not verified:
        raise PoseBustersSulfurReproductionError(
            "detached review signature verification failed"
        )
    return {
        **request["review_payload"],
        "signature": {
            "algorithm": POSEBUSTERS_SULFUR_REPRODUCTION_SIGNATURE_ALGORITHM,
            "key_id": request["reviewer_key_id"],
            "value": signature_hex,
        },
    }


def build_signed_posebusters_sulfur_review(
    *,
    work_order: Mapping[str, Any],
    result: Mapping[str, Any],
    reviewer_identity_sha256: str,
    reviewer_key_id: str,
    reviewed_at_utc: str,
    expires_at_utc: str,
    review_nonce_sha256: str,
    signing_key: bytes | str,
) -> dict[str, Any]:
    """Test/convenience builder; production CLI never accepts private keys."""

    request = build_posebusters_sulfur_review_signing_request(
        work_order=work_order,
        result=result,
        reviewer_identity_sha256=reviewer_identity_sha256,
        reviewer_key_id=reviewer_key_id,
        reviewed_at_utc=reviewed_at_utc,
        expires_at_utc=expires_at_utc,
        review_nonce_sha256=review_nonce_sha256,
    )
    private_key = _key_bytes(signing_key, name="reviewer signing key")
    try:
        signature = sign_ed25519(
            posebusters_sulfur_review_signing_bytes(request),
            private_key,
        )
        public_key = ed25519_public_key_bytes(private_key)
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise PoseBustersSulfurReproductionError("review signing failed") from exc
    return attach_posebusters_sulfur_review_signature(
        request,
        signature_hex=signature,
        verification_key=public_key,
    )


def _approval_without_signature(value: Mapping[str, Any]) -> tuple[dict[str, Any], Any]:
    if not isinstance(value, Mapping):
        raise PoseBustersSulfurReproductionError(
            "independent review approval must be a mapping"
        )
    approval = dict(value)
    signature = approval.pop("signature", None)
    receipt_sha = approval.pop("review_receipt_sha256", None)
    digest = _digest(receipt_sha, name="independent review receipt")
    if digest != _canonical_sha256(approval):
        raise PoseBustersSulfurReproductionError(
            "independent review receipt digest is invalid"
        )
    approval["review_receipt_sha256"] = digest
    return approval, signature


def verify_signed_posebusters_sulfur_review(
    approval_value: Mapping[str, Any],
    *,
    work_order: Mapping[str, Any],
    result: Mapping[str, Any],
    trusted_reviewer_keys: Mapping[str, PoseBustersSulfurReviewerTrustAnchor],
    checked_at_utc: str,
    revoked_reviewer_key_ids: Sequence[str],
    revoked_review_receipt_sha256s: Sequence[str],
    superseded_review_receipt_sha256s: Sequence[str],
) -> dict[str, Any]:
    """Verify signature, freshness, trust, revocation, and derived evidence."""

    approval, signature = _approval_without_signature(approval_value)
    if (
        not isinstance(signature, Mapping)
        or set(signature) != {"algorithm", "key_id", "value"}
        or signature.get("algorithm")
        != POSEBUSTERS_SULFUR_REPRODUCTION_SIGNATURE_ALGORITHM
    ):
        raise PoseBustersSulfurReproductionError(
            "independent review signature envelope is invalid"
        )
    key_id = _key_id(signature.get("key_id"))
    revoked_keys = {_key_id(value) for value in revoked_reviewer_key_ids}
    if key_id in revoked_keys:
        raise PoseBustersSulfurReproductionError("reviewer key is revoked")
    anchor = trusted_reviewer_keys.get(key_id)
    if anchor is None or not isinstance(
        anchor, PoseBustersSulfurReviewerTrustAnchor
    ):
        raise PoseBustersSulfurReproductionError("reviewer key is not trusted")
    if (
        approval.get("reviewer_identity_sha256")
        != anchor.reviewer_identity_sha256
        or approval.get("reviewer_key_id") != key_id
    ):
        raise PoseBustersSulfurReproductionError(
            "reviewer identity is cross-wired"
        )
    review_sha = approval["review_receipt_sha256"]
    for values, message in (
        (revoked_review_receipt_sha256s, "independent review is revoked"),
        (
            superseded_review_receipt_sha256s,
            "independent review is superseded",
        ),
    ):
        digests = [_digest(value, name="external review state") for value in values]
        if len(digests) != len(set(digests)):
            raise PoseBustersSulfurReproductionError(
                "external review state contains duplicates"
            )
        if review_sha in digests:
            raise PoseBustersSulfurReproductionError(message)
    try:
        verified = verify_ed25519(
            _canonical_bytes(approval),
            signature.get("value"),
            anchor.verification_key,
        )
    except ReferenceMinimizationValidationEd25519Error as exc:
        raise PoseBustersSulfurReproductionError(
            "review signature verifier is unavailable"
        ) from exc
    if not verified:
        raise PoseBustersSulfurReproductionError(
            "independent review signature verification failed"
        )
    checked = _parse_utc(checked_at_utc, name="checked_at")
    reviewed = _parse_utc(approval.get("reviewed_at_utc"), name="reviewed_at")
    expires = _parse_utc(approval.get("expires_at_utc"), name="expires_at")
    if checked < reviewed or checked > expires:
        raise PoseBustersSulfurReproductionError(
            "independent review is not currently valid"
        )
    expected = _review_payload(
        work_order=work_order,
        result=result,
        reviewer_identity_sha256=anchor.reviewer_identity_sha256,
        reviewer_key_id=key_id,
        reviewed_at_utc=approval["reviewed_at_utc"],
        expires_at_utc=approval["expires_at_utc"],
        review_nonce_sha256=approval["review_nonce_sha256"],
    )
    if approval != expected:
        raise PoseBustersSulfurReproductionError(
            "independent review fields do not match the derived evidence"
        )
    return {
        "schema_id": POSEBUSTERS_SULFUR_REPRODUCTION_REVIEW_SCHEMA_ID,
        "review_receipt_sha256": review_sha,
        "work_order_receipt_sha256": work_order["receipt_sha256"],
        "result_receipt_sha256": result["receipt_sha256"],
        "reviewer_identity_sha256": anchor.reviewer_identity_sha256,
        "reviewer_key_id": key_id,
        "reviewed_at_utc": approval["reviewed_at_utc"],
        "expires_at_utc": approval["expires_at_utc"],
        "second_cpu_host_reproduced": True,
        "independent_reviewer_receipt_approved": True,
        "chemical_acceptor_semantics_adjudicated": False,
        "scientifically_validated": False,
        "benchmark_executed": False,
        "product_promotion_allowed": False,
        "claim_safe": False,
        "scientific_blockers": list(_POST_REVIEW_BLOCKERS),
    }


def _summary(receipt: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "schema_id",
        "receipt_sha256",
        "review_receipt_sha256",
        "status",
        "registered_utc",
        "observed_utc",
        "second_cpu_host_reproduced",
        "independent_reviewer_receipt_approved",
        "scientifically_validated",
        "claim_safe",
    )
    return {key: receipt[key] for key in keys if key in receipt}


def _add_baseline_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--baseline-protocol", required=True)
    parser.add_argument("--baseline-observation", required=True)
    parser.add_argument("--expected-baseline-protocol-sha256", required=True)
    parser.add_argument("--expected-baseline-observation-sha256", required=True)
    parser.add_argument("--engine-wheel", required=True)
    parser.add_argument("--expected-engine-wheel-sha256", required=True)


def _add_result_verification_arguments(parser: argparse.ArgumentParser) -> None:
    _add_baseline_arguments(parser)
    parser.add_argument("--work-order", required=True)
    parser.add_argument("--expected-work-order-sha256", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--expected-result-sha256", required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "preregister, execute, and review a two-host neutral-thioether "
            "interaction-energy reproduction"
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)

    register = commands.add_parser("register", help="write an external work order")
    _add_baseline_arguments(register)
    register.add_argument("--baseline-host-identity-sha256", required=True)
    register.add_argument("--external-host-identity-sha256", required=True)
    register.add_argument("--work-order-operator-identity-sha256", required=True)
    register.add_argument("--external-executor-identity-sha256", required=True)
    register.add_argument("--external-execution-nonce-sha256", required=True)
    register.add_argument("--registered-utc", required=True)
    register.add_argument("--output", required=True)

    verify_work_order = commands.add_parser(
        "verify-work-order",
        help="reconstruct one external work order exactly",
    )
    _add_baseline_arguments(verify_work_order)
    verify_work_order.add_argument("--work-order", required=True)
    verify_work_order.add_argument("--expected-work-order-sha256", required=True)

    execute = commands.add_parser(
        "execute",
        help="run or retain one preregistered external-host attempt",
    )
    _add_baseline_arguments(execute)
    execute.add_argument("--work-order", required=True)
    execute.add_argument("--expected-work-order-sha256", required=True)
    execute.add_argument("--vina-source-root", required=True)
    execute.add_argument("--pyscf-wheel", required=True)
    execute.add_argument("--pyscf-dispersion-wheel", required=True)
    execute.add_argument("--expected-pyscf-wheel-sha256", required=True)
    execute.add_argument(
        "--expected-pyscf-dispersion-wheel-sha256",
        required=True,
    )
    execute.add_argument("--external-host-identity-sha256", required=True)
    execute.add_argument("--external-executor-identity-sha256", required=True)
    execute.add_argument("--external-observation-utc", required=True)
    execute.add_argument("--output", required=True)

    verify_result = commands.add_parser(
        "verify-result",
        help="rederive one retained external-host result exactly",
    )
    _add_result_verification_arguments(verify_result)

    build_review = commands.add_parser(
        "build-review-request",
        help="verify evidence and write a secret-free reviewer signing request",
    )
    _add_result_verification_arguments(build_review)
    build_review.add_argument("--reviewer-identity-sha256", required=True)
    build_review.add_argument("--reviewer-key-id", required=True)
    build_review.add_argument("--reviewed-at-utc", required=True)
    build_review.add_argument("--expires-at-utc", required=True)
    build_review.add_argument("--review-nonce-sha256", required=True)
    build_review.add_argument("--output", required=True)

    signing_bytes = commands.add_parser(
        "review-signing-bytes",
        help="emit exact canonical bytes from a secret-free review request",
    )
    signing_bytes.add_argument("--request", required=True)
    signing_bytes.add_argument("--output", required=True)

    attach = commands.add_parser(
        "attach-review-signature",
        help="verify and attach a detached Ed25519 review signature",
    )
    attach.add_argument("--request", required=True)
    attach.add_argument("--signature-hex", required=True)
    attach.add_argument("--verification-key-hex", required=True)
    attach.add_argument("--output", required=True)

    verify_review = commands.add_parser(
        "verify-review",
        help="verify evidence plus a detached, trusted Ed25519 reviewer approval",
    )
    _add_result_verification_arguments(verify_review)
    verify_review.add_argument("--review", required=True)
    verify_review.add_argument("--expected-review-sha256", required=True)
    verify_review.add_argument("--reviewer-identity-sha256", required=True)
    verify_review.add_argument("--reviewer-key-id", required=True)
    verify_review.add_argument("--verification-key-hex", required=True)
    verify_review.add_argument("--checked-at-utc", required=True)
    verify_review.add_argument(
        "--revoked-reviewer-key-id",
        action="append",
        default=[],
    )
    verify_review.add_argument(
        "--revoked-review-sha256",
        action="append",
        default=[],
    )
    verify_review.add_argument(
        "--superseded-review-sha256",
        action="append",
        default=[],
    )
    return parser


def _load_private_mapping(
    path: str | os.PathLike[str],
    *,
    maximum_bytes: int,
) -> dict[str, Any]:
    source_path = Path(path)
    descriptor = -1
    try:
        descriptor = os.open(source_path, os.O_RDONLY | os.O_NOFOLLOW)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_size < 3
            or metadata.st_size > maximum_bytes
        ):
            raise PoseBustersSulfurReproductionError(
                "input must be a bounded private regular file"
            )
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            source = handle.read(maximum_bytes + 1)
    except OSError as exc:
        if descriptor >= 0:
            os.close(descriptor)
        raise PoseBustersSulfurReproductionError(
            "input cannot be read safely"
        ) from exc
    if len(source) > maximum_bytes or not source.endswith(b"\n"):
        raise PoseBustersSulfurReproductionError(
            "input is oversized or not newline terminated"
        )
    try:
        value = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersSulfurReproductionError(
            "input is not canonical JSON"
        ) from exc
    if not isinstance(value, dict) or source != _canonical_bytes(value) + b"\n":
        raise PoseBustersSulfurReproductionError(
            "input is not a canonical JSON mapping"
        )
    return value


def _verified_work_order_and_result(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    work_order = verify_posebusters_sulfur_reproduction_work_order(
        args.work_order,
        args.baseline_protocol,
        args.baseline_observation,
        args.engine_wheel,
        expected_work_order_sha256=args.expected_work_order_sha256,
        expected_baseline_protocol_sha256=(
            args.expected_baseline_protocol_sha256
        ),
        expected_baseline_observation_sha256=(
            args.expected_baseline_observation_sha256
        ),
        expected_engine_wheel_sha256=args.expected_engine_wheel_sha256,
    )
    result = verify_posebusters_sulfur_reproduction_result(
        args.result,
        args.work_order,
        args.baseline_protocol,
        args.baseline_observation,
        args.engine_wheel,
        expected_result_sha256=args.expected_result_sha256,
        expected_work_order_sha256=args.expected_work_order_sha256,
        expected_baseline_protocol_sha256=(
            args.expected_baseline_protocol_sha256
        ),
        expected_baseline_observation_sha256=(
            args.expected_baseline_observation_sha256
        ),
        expected_engine_wheel_sha256=args.expected_engine_wheel_sha256,
    )
    return work_order, result


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "register":
        receipt = materialize_posebusters_sulfur_reproduction_work_order(
            args.baseline_protocol,
            args.baseline_observation,
            args.engine_wheel,
            expected_baseline_protocol_sha256=(
                args.expected_baseline_protocol_sha256
            ),
            expected_baseline_observation_sha256=(
                args.expected_baseline_observation_sha256
            ),
            expected_engine_wheel_sha256=args.expected_engine_wheel_sha256,
            baseline_host_identity_sha256=args.baseline_host_identity_sha256,
            expected_external_host_identity_sha256=(
                args.external_host_identity_sha256
            ),
            work_order_operator_identity_sha256=(
                args.work_order_operator_identity_sha256
            ),
            external_execution_operator_identity_sha256=(
                args.external_executor_identity_sha256
            ),
            external_execution_nonce_sha256=(
                args.external_execution_nonce_sha256
            ),
            registered_utc=args.registered_utc,
        )
        _write_private(receipt, args.output)
    elif args.command == "verify-work-order":
        receipt = verify_posebusters_sulfur_reproduction_work_order(
            args.work_order,
            args.baseline_protocol,
            args.baseline_observation,
            args.engine_wheel,
            expected_work_order_sha256=args.expected_work_order_sha256,
            expected_baseline_protocol_sha256=(
                args.expected_baseline_protocol_sha256
            ),
            expected_baseline_observation_sha256=(
                args.expected_baseline_observation_sha256
            ),
            expected_engine_wheel_sha256=args.expected_engine_wheel_sha256,
        )
    elif args.command == "execute":
        receipt = materialize_posebusters_sulfur_reproduction_result(
            args.work_order,
            args.baseline_protocol,
            args.baseline_observation,
            args.engine_wheel,
            args.vina_source_root,
            args.pyscf_wheel,
            args.pyscf_dispersion_wheel,
            expected_work_order_sha256=args.expected_work_order_sha256,
            expected_baseline_protocol_sha256=(
                args.expected_baseline_protocol_sha256
            ),
            expected_baseline_observation_sha256=(
                args.expected_baseline_observation_sha256
            ),
            expected_engine_wheel_sha256=args.expected_engine_wheel_sha256,
            expected_pyscf_wheel_sha256=args.expected_pyscf_wheel_sha256,
            expected_pyscf_dispersion_wheel_sha256=(
                args.expected_pyscf_dispersion_wheel_sha256
            ),
            observed_external_host_identity_sha256=(
                args.external_host_identity_sha256
            ),
            observed_external_execution_operator_identity_sha256=(
                args.external_executor_identity_sha256
            ),
            external_observation_utc=args.external_observation_utc,
        )
        _write_private(receipt, args.output)
    elif args.command == "verify-result":
        _work_order, receipt = _verified_work_order_and_result(args)
    elif args.command == "build-review-request":
        work_order, result = _verified_work_order_and_result(args)
        receipt = build_posebusters_sulfur_review_signing_request(
            work_order=work_order,
            result=result,
            reviewer_identity_sha256=args.reviewer_identity_sha256,
            reviewer_key_id=args.reviewer_key_id,
            reviewed_at_utc=args.reviewed_at_utc,
            expires_at_utc=args.expires_at_utc,
            review_nonce_sha256=args.review_nonce_sha256,
        )
        _write_private(receipt, args.output)
    elif args.command == "review-signing-bytes":
        request = _load_private_mapping(
            args.request,
            maximum_bytes=POSEBUSTERS_SULFUR_REPRODUCTION_MAX_REVIEW_BYTES,
        )
        output = posebusters_sulfur_review_signing_bytes(request)
        _write_private_bytes_no_overwrite(output, args.output)
        receipt = {"schema_id": "raw_signing_bytes", "claim_safe": False}
    elif args.command == "attach-review-signature":
        request = _load_private_mapping(
            args.request,
            maximum_bytes=POSEBUSTERS_SULFUR_REPRODUCTION_MAX_REVIEW_BYTES,
        )
        approval = attach_posebusters_sulfur_review_signature(
            request,
            signature_hex=args.signature_hex,
            verification_key=args.verification_key_hex,
        )
        _write_private(approval, args.output)
        receipt = approval
    else:
        work_order, result = _verified_work_order_and_result(args)
        approval = _load_private_mapping(
            args.review,
            maximum_bytes=POSEBUSTERS_SULFUR_REPRODUCTION_MAX_REVIEW_BYTES,
        )
        approval_payload, _signature = _approval_without_signature(approval)
        expected_review_sha = _digest(
            args.expected_review_sha256,
            name="expected independent review",
        )
        if approval_payload["review_receipt_sha256"] != expected_review_sha:
            raise PoseBustersSulfurReproductionError(
                "independent review disagrees with the caller-frozen digest"
            )
        key_id = _key_id(args.reviewer_key_id)
        receipt = verify_signed_posebusters_sulfur_review(
            approval,
            work_order=work_order,
            result=result,
            trusted_reviewer_keys={
                key_id: PoseBustersSulfurReviewerTrustAnchor(
                    reviewer_identity_sha256=args.reviewer_identity_sha256,
                    verification_key=args.verification_key_hex,
                )
            },
            checked_at_utc=args.checked_at_utc,
            revoked_reviewer_key_ids=args.revoked_reviewer_key_id,
            revoked_review_receipt_sha256s=args.revoked_review_sha256,
            superseded_review_receipt_sha256s=(
                args.superseded_review_sha256
            ),
        )
    print(json.dumps(_summary(receipt), sort_keys=True))
    return 0


__all__ = [
    "POSEBUSTERS_SULFUR_REPRODUCTION_COMPARISON_SCHEMA_ID",
    "POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION",
    "POSEBUSTERS_SULFUR_REPRODUCTION_CONFIGURATION_SHA256",
    "POSEBUSTERS_SULFUR_REPRODUCTION_RESULT_SCHEMA_ID",
    "POSEBUSTERS_SULFUR_REPRODUCTION_REVIEW_REQUEST_SCHEMA_ID",
    "POSEBUSTERS_SULFUR_REPRODUCTION_REVIEW_SCHEMA_ID",
    "POSEBUSTERS_SULFUR_REPRODUCTION_WORK_ORDER_SCHEMA_ID",
    "PoseBustersSulfurReproductionError",
    "PoseBustersSulfurReviewerTrustAnchor",
    "attach_posebusters_sulfur_review_signature",
    "build_posebusters_sulfur_review_signing_request",
    "build_signed_posebusters_sulfur_review",
    "compare_posebusters_sulfur_cross_host_observations",
    "main",
    "materialize_posebusters_sulfur_reproduction_result",
    "materialize_posebusters_sulfur_reproduction_work_order",
    "posebusters_sulfur_review_signing_bytes",
    "require_posebusters_sulfur_review_signing_request",
    "verify_posebusters_sulfur_reproduction_result",
    "verify_posebusters_sulfur_reproduction_work_order",
    "verify_signed_posebusters_sulfur_review",
]


if __name__ == "__main__":
    raise SystemExit(main())
