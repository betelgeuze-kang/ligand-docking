"""Fail-closed receipts for the single-attempt Fresh-128 execution lane.

The Stage 0 admission policy is evaluated before the holdout is opened.  This
module covers the other side of that boundary: one permanent local run marker
bound to a separately verified external WORM reservation,
an exact 128 x 3 engine-row denominator, an exact 128 x 64 Engine V2 slot
denominator, and one terminal completion receipt.  A slot is retained even when
case preparation fails, so preparation failures cannot silently shrink the
8,192-slot denominator.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field as dataclass_field, fields
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Mapping, Sequence

from . import public_redocking_benchmark as benchmark_contract
from .blind_stage0 import (
    STAGE0_CANONICAL_FRESH_RETENTION_ROOT,
    STAGE0_CORE_RUNTIME_DISTRIBUTIONS,
    STAGE0_EVALUATOR_DISTRIBUTION_VERSIONS,
    STAGE0_RUNTIME_DEPENDENCY_AUTHORITY_SCHEMA_ID,
    Stage0AdmissionError,
    VerifiedStage0Admission,
    compute_stage0_policy_sha256,
    stage0_engine_implementation_sha256,
    stage0_fresh_execution_runtime_arguments,
    validate_stage0_admission_receipt_document,
    verify_stage0_admission,
)
from .fresh_artifacts import (
    FRESH_ARTIFACT_MANIFEST_FILENAME,
    FRESH_EXECUTION_ENVIRONMENT_FILENAME,
    FRESH_EXECUTION_LOG_FILENAME,
    FRESH_STAGE0_POLICY_SNAPSHOT_FILENAME,
    FreshArtifactManifestError,
    verify_fresh_artifact_manifest_document,
    verify_fresh_artifact_set,
)
from .fresh_redocking_holdout import (
    FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256,
    FRESH_REDOCKING_HOLDOUT_SEED_BASE,
    FrozenFreshRedockingCase,
    FrozenFreshRedockingHoldout,
    require_fresh_redocking_holdout_manifest,
)
from .public_redocking_benchmark import (
    FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS,
    PUBLIC_REDOCKING_ALLOWED_TORCH_VERSIONS,
    PUBLIC_REDOCKING_ARCHIVE_SHA256,
    PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID,
    PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT,
    PUBLIC_REDOCKING_ENGINE_V2_ALGORITHM_PROFILE_ID,
    PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID,
    PUBLIC_REDOCKING_ENGINE_V2_REFINEMENT_STEPS,
    PUBLIC_REDOCKING_ENGINE_V2_REFINER_CONFIG_SHA256,
    PUBLIC_REDOCKING_ENGINE_V2_REFINER_POLICY_ID,
    PUBLIC_REDOCKING_ENGINE_V2_DIAGNOSTIC_SCHEMA_ID,
    PUBLIC_REDOCKING_PROFILE_METHOD_ID,
    PUBLIC_REDOCKING_RING_PROFILE_METHOD_ID,
    PUBLIC_REDOCKING_RUNNER_ID,
    PUBLIC_REDOCKING_PRIMARY_ENGINES,
    PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
    PublicRedockingEngineIdentity,
    PublicRedockingEngineV2CandidateDiagnostic,
    PublicRedockingEngineV2Diagnostics,
    PublicRedockingEvaluationPolicy,
)
from .public_redocking_pipeline import (
    PUBLIC_REDOCKING_STAGE0_PIPELINE_PROFILE_ID,
    public_redocking_pipeline_profile_identity,
)


FRESH_INTERNAL_REPORT_SCHEMA_ID = (
    "betelgeuze.engine_v2_fresh_redocking_internal_report/1.2.0"
)
FRESH_CANDIDATE_SLOT_SCHEMA_ID = (
    "betelgeuze.engine_v2_fresh_redocking_candidate_slot/1.0.0"
)
FRESH_RUN_ONCE_RESERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_fresh_redocking_run_once_reservation/1.1.0"
)
FRESH_RUN_ONCE_COMPLETION_SCHEMA_ID = (
    "betelgeuze.engine_v2_fresh_redocking_run_once_completion/1.1.0"
)
FRESH_RUN_TERMINAL_FAILURE_SCHEMA_ID = (
    "betelgeuze.engine_v2_fresh_redocking_terminal_failure/1.0.0"
)
FRESH_VERIFIED_RUN_SCHEMA_ID = "betelgeuze.engine_v2_fresh_redocking_verified_run/1.0.0"
FRESH_RUNNER_ID = "betelgeuze.engine_v2_fresh_redocking_128_runner/1.0.0"
FRESH_CASE_COUNT = 128
FRESH_ENGINE_ROW_COUNT = FRESH_CASE_COUNT * len(PUBLIC_REDOCKING_PRIMARY_ENGINES)
FRESH_ENGINE_V2_SLOT_COUNT = (
    FRESH_CASE_COUNT * PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
)
FRESH_RESERVATION_FILENAME = "fresh-redocking-run-once-reservation.json"
FRESH_REPORT_FILENAME = "fresh-redocking-internal-report.json"
FRESH_COMPLETION_FILENAME = "fresh-redocking-run-once-completion.json"
FRESH_FAILURE_FILENAME = "fresh-redocking-terminal-failure.json"
FRESH_STAGE0_ADMISSION_RECEIPT_FILENAME = "stage0-admission-receipt.json"
_HEX = frozenset("0123456789abcdef")
_MAX_RECEIPT_BYTES = 8 * 1024 * 1024
_MAX_REPORT_BYTES = 512 * 1024 * 1024
_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
_VERIFIED_FRESH_RUN_AUTHORITY = object()


class FreshRunVerificationError(ValueError):
    """Fresh-128 evidence is incomplete, mutable, or cross-wired."""


@dataclass(frozen=True, slots=True, init=False)
class VerifiedFreshRun:
    """Factory-only verification of one complete, retained Fresh-128 run."""

    reservation_sha256: str
    report_fingerprint_sha256: str
    report_file_sha256: str
    artifact_manifest_sha256: str
    artifact_manifest_file_sha256: str
    completion_sha256: str
    stage0_admission_receipt_sha256: str
    external_run_once_reservation_sha256: str
    fresh_run_identity_sha256: str
    docking_pipeline_profile_id: str
    docking_pipeline_profile_sha256: str
    stage0_binding_authority: str
    stage0_policy_verified: bool
    external_worm_reservation_cryptographically_verified: bool
    exactly_once_verified: bool
    case_count: int = FRESH_CASE_COUNT
    engine_case_row_count: int = FRESH_ENGINE_ROW_COUNT
    engine_v2_candidate_slot_count: int = FRESH_ENGINE_V2_SLOT_COUNT
    schema_id: str = FRESH_VERIFIED_RUN_SCHEMA_ID
    _receipt_sha256: str = dataclass_field(repr=False)
    _verification_authority: object = dataclass_field(repr=False)

    @classmethod
    def _from_verified_root(
        cls,
        *,
        reservation_sha256: str,
        report_fingerprint_sha256: str,
        report_file_sha256: str,
        artifact_manifest_sha256: str,
        artifact_manifest_file_sha256: str,
        completion_sha256: str,
        stage0_admission_receipt_sha256: str,
        external_run_once_reservation_sha256: str,
        fresh_run_identity_sha256: str,
        docking_pipeline_profile_id: str,
        docking_pipeline_profile_sha256: str,
        stage0_binding_authority: str,
        stage0_policy_verified: bool,
        external_worm_reservation_cryptographically_verified: bool,
        exactly_once_verified: bool,
        verification_authority: object,
    ) -> "VerifiedFreshRun":
        if verification_authority is not _VERIFIED_FRESH_RUN_AUTHORITY:
            raise TypeError("VerifiedFreshRun requires verifier authority")
        digests = {
            "reservation_sha256": reservation_sha256,
            "report_fingerprint_sha256": report_fingerprint_sha256,
            "report_file_sha256": report_file_sha256,
            "artifact_manifest_sha256": artifact_manifest_sha256,
            "artifact_manifest_file_sha256": artifact_manifest_file_sha256,
            "completion_sha256": completion_sha256,
            "stage0_admission_receipt_sha256": (stage0_admission_receipt_sha256),
            "external_run_once_reservation_sha256": (
                external_run_once_reservation_sha256
            ),
            "fresh_run_identity_sha256": fresh_run_identity_sha256,
            "docking_pipeline_profile_sha256": docking_pipeline_profile_sha256,
        }
        if any(not _is_sha256(value) for value in digests.values()):
            raise TypeError("VerifiedFreshRun digest is invalid")
        if (
            not docking_pipeline_profile_id
            or stage0_binding_authority
            not in {
                "verified_stage0_policy",
                "verified_stage0_receipt",
                "on_disk_stage0_admission_receipt",
            }
            or type(stage0_policy_verified) is not bool
            or type(external_worm_reservation_cryptographically_verified) is not bool
            or type(exactly_once_verified) is not bool
        ):
            raise TypeError("VerifiedFreshRun authority is invalid")
        instance = object.__new__(cls)
        for name, value in digests.items():
            object.__setattr__(instance, name, value)
        object.__setattr__(
            instance, "docking_pipeline_profile_id", docking_pipeline_profile_id
        )
        object.__setattr__(
            instance, "stage0_binding_authority", stage0_binding_authority
        )
        object.__setattr__(instance, "stage0_policy_verified", stage0_policy_verified)
        object.__setattr__(
            instance,
            "external_worm_reservation_cryptographically_verified",
            external_worm_reservation_cryptographically_verified,
        )
        object.__setattr__(instance, "exactly_once_verified", exactly_once_verified)
        object.__setattr__(instance, "case_count", FRESH_CASE_COUNT)
        object.__setattr__(instance, "engine_case_row_count", FRESH_ENGINE_ROW_COUNT)
        object.__setattr__(
            instance,
            "engine_v2_candidate_slot_count",
            FRESH_ENGINE_V2_SLOT_COUNT,
        )
        object.__setattr__(instance, "schema_id", FRESH_VERIFIED_RUN_SCHEMA_ID)
        object.__setattr__(
            instance, "_verification_authority", _VERIFIED_FRESH_RUN_AUTHORITY
        )
        object.__setattr__(
            instance,
            "_receipt_sha256",
            hashlib.sha256(canonical_bytes(instance._projection())).hexdigest(),
        )
        return instance

    def _projection(self) -> dict[str, object]:
        activation_eligible = (
            self.exactly_once_verified
            and self.stage0_policy_verified
            and self.external_worm_reservation_cryptographically_verified
        )
        return {
            "schema_id": self.schema_id,
            "reservation_sha256": self.reservation_sha256,
            "report_fingerprint_sha256": self.report_fingerprint_sha256,
            "report_file_sha256": self.report_file_sha256,
            "artifact_manifest_sha256": self.artifact_manifest_sha256,
            "artifact_manifest_file_sha256": self.artifact_manifest_file_sha256,
            "completion_sha256": self.completion_sha256,
            "stage0_admission_receipt_sha256": (self.stage0_admission_receipt_sha256),
            "external_run_once_reservation_sha256": (
                self.external_run_once_reservation_sha256
            ),
            "fresh_run_identity_sha256": self.fresh_run_identity_sha256,
            "docking_pipeline_profile_id": self.docking_pipeline_profile_id,
            "docking_pipeline_profile_sha256": (self.docking_pipeline_profile_sha256),
            "case_count": self.case_count,
            "engine_case_row_count": self.engine_case_row_count,
            "engine_v2_candidate_slot_count": self.engine_v2_candidate_slot_count,
            "single_local_attempt_marker_verified": True,
            "exactly_once_verified": self.exactly_once_verified,
            "external_worm_reservation_bound": True,
            "external_worm_reservation_cryptographically_verified": (
                self.external_worm_reservation_cryptographically_verified
            ),
            "global_exactly_once_requires_live_authority_reverification": (
                not self.exactly_once_verified
            ),
            "stage0_binding_authority": self.stage0_binding_authority,
            "stage0_policy_verified": self.stage0_policy_verified,
            "product_shadow_activation_eligible": activation_eligible,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        if (
            self._verification_authority is not _VERIFIED_FRESH_RUN_AUTHORITY
            or self.schema_id != FRESH_VERIFIED_RUN_SCHEMA_ID
        ):
            raise FreshRunVerificationError(
                "Fresh run verification authority is invalid"
            )
        observed = hashlib.sha256(canonical_bytes(self._projection())).hexdigest()
        if observed != self._receipt_sha256:
            raise FreshRunVerificationError("Fresh run verification receipt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        payload = self._projection()
        payload["receipt_sha256"] = self.receipt_sha256
        return payload


def require_fresh_run_product_shadow_activation(
    value: object,
    *,
    stage0_admission: object,
) -> dict[str, object]:
    """Require Fresh-128 completion plus live exactly-once activation authority."""

    if type(value) is not VerifiedFreshRun:
        raise TypeError("factory-created VerifiedFreshRun is required")
    if type(stage0_admission) is not VerifiedStage0Admission:
        raise TypeError("factory-created VerifiedStage0Admission is required")
    document = value.to_dict()
    admission = stage0_admission.to_dict()
    if (
        document.get("stage0_admission_receipt_sha256")
        != admission.get("receipt_sha256")
        or document.get("external_run_once_reservation_sha256")
        != admission.get("external_run_once_reservation_sha256")
        or document.get("fresh_run_identity_sha256")
        != admission.get("fresh_run_identity_sha256")
        or document.get("docking_pipeline_profile_id")
        != admission.get("docking_pipeline_profile_id")
        or document.get("docking_pipeline_profile_sha256")
        != admission.get("docking_pipeline_profile_sha256")
    ):
        raise FreshRunVerificationError(
            "Fresh-128 and Stage 0 admission are cross-wired"
        )
    if (
        document.get("case_count") != FRESH_CASE_COUNT
        or document.get("engine_case_row_count") != FRESH_ENGINE_ROW_COUNT
        or document.get("engine_v2_candidate_slot_count") != FRESH_ENGINE_V2_SLOT_COUNT
        or document.get("stage0_policy_verified") is not True
        or document.get("external_worm_reservation_cryptographically_verified")
        is not True
        or document.get("exactly_once_verified") is not True
        or document.get("product_shadow_activation_eligible") is not True
        or document.get("claim_safe") is not False
    ):
        raise FreshRunVerificationError(
            "Fresh-128 product shadow activation authority is incomplete"
        )
    return document


@dataclass(frozen=True, slots=True)
class _OwnedCanonicalJson:
    payload: dict[str, object]
    raw: bytes


@dataclass(frozen=True, slots=True)
class FreshRedockingCaseProfile:
    """A closed profile projection whose case namespace is the frozen Fresh-128."""

    case_id: str
    heavy_atom_count: int
    rotor_count: int
    ring_count: int
    ligand_artifact_sha256: str

    def __post_init__(self) -> None:
        if self.case_id not in FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS:
            raise FreshRunVerificationError("Fresh-128 profile case_id is invalid")
        if (
            type(self.heavy_atom_count) is not int
            or not 1 <= self.heavy_atom_count <= 512
            or type(self.rotor_count) is not int
            or not 0 <= self.rotor_count <= 128
            or type(self.ring_count) is not int
            or not 0 <= self.ring_count <= 128
            or not _is_sha256(self.ligand_artifact_sha256)
        ):
            raise FreshRunVerificationError("Fresh-128 profile values are invalid")

    @property
    def size_subgroup(self) -> str:
        if self.heavy_atom_count <= 20:
            return "size_small_1_20"
        if self.heavy_atom_count <= 40:
            return "size_medium_21_40"
        return "size_large_41_plus"

    @property
    def rotor_subgroup(self) -> str:
        if self.rotor_count == 0:
            return "rotor_rigid_0"
        if self.rotor_count <= 4:
            return "rotor_low_1_4"
        return "rotor_flexible_5_plus"

    @property
    def ring_subgroup(self) -> str:
        if self.ring_count == 0:
            return "ring_acyclic_0"
        if self.ring_count == 1:
            return "ring_single_1"
        return "ring_multi_2_plus"

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "heavy_atom_count": self.heavy_atom_count,
            "rotor_count": self.rotor_count,
            "ring_count": self.ring_count,
            "ligand_artifact_sha256": self.ligand_artifact_sha256,
            "profile_method_id": PUBLIC_REDOCKING_PROFILE_METHOD_ID,
            "ring_profile_method_id": PUBLIC_REDOCKING_RING_PROFILE_METHOD_ID,
            "size_subgroup": self.size_subgroup,
            "rotor_subgroup": self.rotor_subgroup,
            "ring_subgroup": self.ring_subgroup,
        }


@dataclass(frozen=True, slots=True)
class FreshRedockingCaseResult:
    """A typed benchmark row using the frozen Fresh-128 case namespace."""

    case_id: str
    engine_id: str
    status: str
    runtime_seconds: float
    receptor_artifact_sha256: str
    reference_artifact_sha256: str
    native_artifact_sha256: str
    seed_artifact_sha256: str
    execution_command: tuple[str, ...]
    execution_policy: tuple[str, ...]
    rmsd_angstroms: tuple[float, ...] = ()
    geometric_valid: tuple[bool, ...] = ()
    chemical_valid: tuple[bool, ...] = ()
    pose_artifact_sha256s: tuple[str, ...] = ()
    failure_code: str = ""
    engine_v2_diagnostics: PublicRedockingEngineV2Diagnostics | None = None

    def __post_init__(self) -> None:
        if self.case_id not in FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS:
            raise FreshRunVerificationError("Fresh-128 row case_id is invalid")
        engine_id = str(self.engine_id or "").strip().lower()
        status = str(self.status or "").strip().lower()
        if engine_id not in PUBLIC_REDOCKING_PRIMARY_ENGINES:
            raise FreshRunVerificationError("Fresh-128 row engine_id is invalid")
        if status not in {"success", "failure"}:
            raise FreshRunVerificationError("Fresh-128 row status is invalid")
        try:
            runtime = benchmark_contract._finite(
                self.runtime_seconds,
                name="runtime_seconds",
                minimum=0.0,
            )
            digests = {
                name: benchmark_contract._digest(getattr(self, name), name=name)
                for name in (
                    "receptor_artifact_sha256",
                    "reference_artifact_sha256",
                    "native_artifact_sha256",
                    "seed_artifact_sha256",
                )
            }
            rmsds = tuple(
                benchmark_contract._finite(
                    value,
                    name="rmsd_angstrom",
                    minimum=0.0,
                )
                for value in self.rmsd_angstroms
            )
        except (TypeError, ValueError) as exc:
            raise FreshRunVerificationError("Fresh-128 row values are invalid") from exc
        command = tuple(str(value) for value in self.execution_command)
        execution_policy = tuple(str(value) for value in self.execution_policy)
        if not command or any(not value for value in command):
            raise FreshRunVerificationError("Fresh-128 row command is invalid")
        if (
            not execution_policy
            or execution_policy != tuple(sorted(execution_policy))
            or any("=" not in value for value in execution_policy)
        ):
            raise FreshRunVerificationError("Fresh-128 row policy is invalid")
        try:
            benchmark_contract._execution_policy_mapping(execution_policy)
        except (TypeError, ValueError) as exc:
            raise FreshRunVerificationError("Fresh-128 row policy is invalid") from exc
        geometric = tuple(self.geometric_valid)
        chemical = tuple(self.chemical_valid)
        pose_artifacts = tuple(self.pose_artifact_sha256s)
        if any(type(value) is not bool for value in (*geometric, *chemical)):
            raise FreshRunVerificationError("Fresh-128 pose validity is invalid")
        failure_code = str(self.failure_code or "").strip()
        diagnostics = self.engine_v2_diagnostics
        if diagnostics is not None and type(diagnostics) is not (
            PublicRedockingEngineV2Diagnostics
        ):
            raise FreshRunVerificationError("Fresh-128 diagnostics are not typed")
        if engine_id != "engine_v2" and diagnostics is not None:
            raise FreshRunVerificationError(
                "Fresh-128 external row contains Engine V2 diagnostics"
            )
        if status == "success":
            if not (
                len(rmsds)
                == len(geometric)
                == len(chemical)
                == len(pose_artifacts)
                == 5
            ):
                raise FreshRunVerificationError(
                    "Fresh-128 success row lacks five ranked poses"
                )
            try:
                pose_artifacts = tuple(
                    benchmark_contract._digest(value, name="pose_artifact_sha256")
                    for value in pose_artifacts
                )
            except (TypeError, ValueError) as exc:
                raise FreshRunVerificationError(
                    "Fresh-128 pose artifact identity is invalid"
                ) from exc
            if failure_code:
                raise FreshRunVerificationError(
                    "Fresh-128 success row contains a failure code"
                )
        elif rmsds or geometric or chemical or pose_artifacts or not failure_code:
            raise FreshRunVerificationError(
                "Fresh-128 failure row has fabricated pose outcomes"
            )
        object.__setattr__(self, "engine_id", engine_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "runtime_seconds", runtime)
        for name, value in digests.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "execution_command", command)
        object.__setattr__(self, "execution_policy", execution_policy)
        object.__setattr__(self, "rmsd_angstroms", rmsds)
        object.__setattr__(self, "geometric_valid", geometric)
        object.__setattr__(self, "chemical_valid", chemical)
        object.__setattr__(self, "pose_artifact_sha256s", pose_artifacts)
        object.__setattr__(self, "failure_code", failure_code)
        object.__setattr__(self, "engine_v2_diagnostics", diagnostics)
        if engine_id == "engine_v2":
            try:
                benchmark_contract._validate_engine_v2_result_diagnostics(self)
            except (TypeError, ValueError) as exc:
                raise FreshRunVerificationError(
                    "Fresh-128 Engine V2 diagnostics contradict the row"
                ) from exc

    def recovery(self, top_k: int, threshold: float) -> float:
        if self.status == "failure":
            return 0.0
        return float(min(self.rmsd_angstroms[:top_k]) <= threshold)

    def valid_recovery(self, top_k: int, threshold: float) -> float:
        if self.status == "failure":
            return 0.0
        return float(
            any(
                rmsd <= threshold and geometric and chemical
                for rmsd, geometric, chemical in zip(
                    self.rmsd_angstroms[:top_k],
                    self.geometric_valid[:top_k],
                    self.chemical_valid[:top_k],
                    strict=True,
                )
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "engine_id": self.engine_id,
            "status": self.status,
            "runtime_seconds": self.runtime_seconds,
            "receptor_artifact_sha256": self.receptor_artifact_sha256,
            "reference_artifact_sha256": self.reference_artifact_sha256,
            "native_artifact_sha256": self.native_artifact_sha256,
            "seed_artifact_sha256": self.seed_artifact_sha256,
            "execution_command": list(self.execution_command),
            "execution_policy": list(self.execution_policy),
            "rmsd_angstroms": list(self.rmsd_angstroms),
            "geometric_valid": list(self.geometric_valid),
            "chemical_valid": list(self.chemical_valid),
            "pose_artifact_sha256s": list(self.pose_artifact_sha256s),
            "failure_code": self.failure_code,
            "engine_v2_diagnostics": (
                None
                if self.engine_v2_diagnostics is None
                else self.engine_v2_diagnostics.to_dict()
            ),
        }


def canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise FreshRunVerificationError(
            "Fresh-128 evidence is not canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def fresh_engine_v2_execution_command(
    case_id: str,
    *,
    output_root: Path,
) -> tuple[str, ...]:
    """Return the one canonical Engine V2 command authorized for Fresh-128."""

    if case_id not in FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS:
        raise FreshRunVerificationError("Fresh-128 command case_id is invalid")
    root_text = os.fspath(output_root)
    root = Path(root_text)
    if (
        not root.is_absolute()
        or os.path.normpath(root_text) != root_text
        or str(root) != root_text
    ):
        raise FreshRunVerificationError(
            "Fresh-128 command output root is not a canonical absolute path"
        )
    case_root = root / "inputs" / case_id
    seed = FRESH_REDOCKING_HOLDOUT_SEED_BASE + (
        FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS.index(case_id)
    )
    return (
        PUBLIC_REDOCKING_RUNNER_ID,
        "engine_v2",
        "--case-id",
        case_id,
        "--receptor",
        str(case_root / f"{case_id}_protein.pdb"),
        "--ligand",
        str(case_root / f"{case_id}_ligand_start_conf.sdf"),
        "--pocket-source",
        str(case_root / f"{case_id}_ligand.sdf"),
        "--candidate-count",
        str(PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT),
        "--cpu",
        "1",
        "--scorer-backend",
        "rust_cpu_required",
        "--seed",
        str(seed),
        "--out",
        str(root / "poses" / "engine_v2" / f"{case_id}.sdf"),
    )


def _validated_fresh_engine_v2_command_root(
    row: FreshRedockingCaseResult,
    *,
    expected_output_root: Path | None,
) -> Path:
    command = row.execution_command
    if len(command) != 20 or command[18] != "--out":
        raise FreshRunVerificationError("Fresh-128 Engine V2 command is not canonical")
    output_text = command[19]
    output = Path(output_text)
    if (
        not output.is_absolute()
        or os.path.normpath(output_text) != output_text
        or str(output) != output_text
        or output.name != f"{row.case_id}.sdf"
        or output.parent.name != "engine_v2"
        or output.parent.parent.name != "poses"
    ):
        raise FreshRunVerificationError("Fresh-128 Engine V2 command is not canonical")
    root = output.parents[2]
    if expected_output_root is not None and root != expected_output_root:
        raise FreshRunVerificationError(
            "Fresh-128 Engine V2 command output root is cross-wired"
        )
    if command != fresh_engine_v2_execution_command(
        row.case_id,
        output_root=root,
    ):
        raise FreshRunVerificationError("Fresh-128 Engine V2 command is not canonical")
    return root


def _fresh_engine_v2_source_identity(repo_root: Path) -> tuple[str, str, str]:
    try:
        implementation_sha256 = stage0_engine_implementation_sha256(repo_root)
        profile_id, profile_sha256 = public_redocking_pipeline_profile_identity(
            engine_implementation_sha256=implementation_sha256,
            variant_kind="",
        )
    except (OSError, TypeError, ValueError) as exc:
        raise FreshRunVerificationError(
            "Fresh-128 Engine V2 source closure cannot be reconstructed"
        ) from exc
    if profile_id != PUBLIC_REDOCKING_STAGE0_PIPELINE_PROFILE_ID:
        raise FreshRunVerificationError(
            "Fresh-128 Engine V2 pipeline profile authority drifted"
        )
    return implementation_sha256, profile_id, profile_sha256


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _HEX for character in value)
    )


def _mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise FreshRunVerificationError(f"{name} must be a JSON object")
    return value


def _sequence(value: object, *, name: str) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        raise FreshRunVerificationError(f"{name} must be a JSON array")
    return value


def _self_hash(
    payload: Mapping[str, object],
    *,
    field: str,
    name: str,
) -> str:
    observed = payload.get(field)
    projection = dict(payload)
    projection.pop(field, None)
    expected = canonical_sha256(projection)
    if observed != expected:
        raise FreshRunVerificationError(f"{name} self-hash is invalid")
    return expected


def _stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_uid,
        value.st_nlink,
        stat.S_IMODE(value.st_mode),
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _trusted_holdout(repo_root: Path) -> FrozenFreshRedockingHoldout:
    directory_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_DIRECTORY"):
        directory_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        directory_flags |= os.O_NOFOLLOW
    file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        file_flags |= os.O_NOFOLLOW
    repo_descriptor = -1
    config_descriptor = -1
    manifest_descriptor = -1
    try:
        repo_descriptor = _directory_descriptor(repo_root)
        _require_owned_directory(repo_descriptor, name="repository root")
        config_descriptor = os.open(
            "config",
            directory_flags,
            dir_fd=repo_descriptor,
        )
        config_status = os.fstat(config_descriptor)
        if not stat.S_ISDIR(config_status.st_mode) or (
            hasattr(os, "geteuid") and config_status.st_uid != os.geteuid()
        ):
            raise FreshRunVerificationError(
                "frozen Fresh-128 manifest directory is not owned"
            )
        manifest_descriptor = os.open(
            "engine_v2_fresh_redocking_holdout_manifest.json",
            file_flags,
            dir_fd=config_descriptor,
        )
        before = os.fstat(manifest_descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or (hasattr(os, "geteuid") and before.st_uid != os.geteuid())
            or before.st_size < 2
            or before.st_size > _MAX_RECEIPT_BYTES
        ):
            raise FreshRunVerificationError(
                "frozen Fresh-128 manifest is not a safe owned regular file"
            )
        raw = os.pread(manifest_descriptor, before.st_size + 1, 0)
        after = os.fstat(manifest_descriptor)
        if len(raw) != before.st_size or _stat_identity(before) != _stat_identity(
            after
        ):
            raise FreshRunVerificationError(
                "frozen Fresh-128 manifest changed while it was read"
            )
        payload = json.loads(raw.decode("ascii"))
        holdout = require_fresh_redocking_holdout_manifest(payload)
    except FreshRunVerificationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise FreshRunVerificationError(
            "frozen Fresh-128 manifest failed descriptor-safe verification"
        ) from exc
    finally:
        for descriptor in (
            manifest_descriptor,
            config_descriptor,
            repo_descriptor,
        ):
            if descriptor >= 0:
                os.close(descriptor)
    if (
        holdout.manifest_sha256 != FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256
        or holdout.case_ids != FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS
        or len(holdout.cases) != FRESH_CASE_COUNT
    ):
        raise FreshRunVerificationError("frozen Fresh-128 manifest identity drifted")
    return holdout


def _typed_policy(value: object) -> PublicRedockingEvaluationPolicy:
    raw = dict(_mapping(value, name="Fresh-128 evaluation policy"))
    try:
        typed = PublicRedockingEvaluationPolicy(
            **{
                field.name: raw[field.name]
                for field in fields(PublicRedockingEvaluationPolicy)
                if field.init
            }
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FreshRunVerificationError(
            "Fresh-128 evaluation policy is not typed"
        ) from exc
    frozen = stage0_fresh_execution_runtime_arguments()
    if (
        typed.to_dict() != raw
        or typed.bootstrap_samples != frozen["bootstrap_samples"]
        or typed.bootstrap_seed != frozen["seed"]
        or typed.external_timeout_seconds != frozen["external_timeout_seconds"]
        or typed.cpu_count != 1
    ):
        raise FreshRunVerificationError(
            "Fresh-128 evaluation policy is not the frozen Stage 0 policy"
        )
    return typed


def _typed_profile(
    value: object,
    *,
    frozen_case: FrozenFreshRedockingCase,
) -> FreshRedockingCaseProfile:
    raw = dict(_mapping(value, name="Fresh-128 profile"))
    try:
        typed = FreshRedockingCaseProfile(
            **{
                field.name: raw[field.name]
                for field in fields(FreshRedockingCaseProfile)
                if field.init
            }
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FreshRunVerificationError("Fresh-128 profile is not typed") from exc
    expected = FreshRedockingCaseProfile(
        case_id=frozen_case.case_id,
        heavy_atom_count=int(frozen_case.profile["heavy_atom_count"]),
        rotor_count=int(frozen_case.profile["rotatable_bond_count_strict"]),
        ring_count=int(frozen_case.profile["ring_count"]),
        ligand_artifact_sha256=frozen_case.artifact_sha256s["native"],
    )
    if typed.to_dict() != raw or typed != expected:
        raise FreshRunVerificationError(
            "Fresh-128 profile does not match the frozen manifest"
        )
    return typed


def _typed_materialization(
    value: object,
    *,
    frozen_case: FrozenFreshRedockingCase,
) -> FrozenFreshRedockingCase:
    raw = dict(_mapping(value, name="Fresh-128 materialization"))
    try:
        typed = FrozenFreshRedockingCase(
            **{
                field.name: raw[field.name]
                for field in fields(FrozenFreshRedockingCase)
                if field.init
            }
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FreshRunVerificationError(
            "Fresh-128 materialization is not typed"
        ) from exc
    if typed.to_dict() != raw or raw != frozen_case.to_dict():
        raise FreshRunVerificationError(
            "Fresh-128 materialization does not match the frozen manifest"
        )
    return typed


def _typed_identity(value: object) -> PublicRedockingEngineIdentity:
    raw = dict(_mapping(value, name="Fresh-128 engine identity"))
    try:
        typed = PublicRedockingEngineIdentity(
            **{
                field.name: raw[field.name]
                for field in fields(PublicRedockingEngineIdentity)
                if field.init
            }
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FreshRunVerificationError(
            "Fresh-128 engine identity is not typed"
        ) from exc
    if typed.to_dict() != raw:
        raise FreshRunVerificationError(
            "Fresh-128 engine identity schema is not closed"
        )
    return typed


def _typed_engine_v2_diagnostics(value: object) -> PublicRedockingEngineV2Diagnostics:
    raw = dict(_mapping(value, name="Fresh-128 Engine V2 diagnostics"))
    raw_candidates = _sequence(
        raw.get("candidates"),
        name="Fresh-128 Engine V2 candidates",
    )
    try:
        candidate_field_names = tuple(
            field.name
            for field in fields(PublicRedockingEngineV2CandidateDiagnostic)
            if field.init
        )
        candidates: list[PublicRedockingEngineV2CandidateDiagnostic] = []
        for value in raw_candidates:
            candidate_raw = dict(_mapping(value, name="Fresh-128 Engine V2 candidate"))
            required_names = candidate_field_names
            if candidate_raw.get("schema_id") == (
                PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID
            ):
                required_names = tuple(
                    name
                    for name in required_names
                    if name != "torsion_rescue_parent_proposal_index"
                )
            candidates.append(
                PublicRedockingEngineV2CandidateDiagnostic(
                    **{name: candidate_raw[name] for name in required_names}
                )
            )
        if [candidate.to_dict() for candidate in candidates] != list(raw_candidates):
            raise ValueError("candidate projection drifted")
        diagnostic_kwargs = {
            field.name: raw[field.name]
            for field in fields(PublicRedockingEngineV2Diagnostics)
            if field.init
            and field.name != "candidates"
            and not (
                raw.get("schema_id") == PUBLIC_REDOCKING_ENGINE_V2_DIAGNOSTIC_SCHEMA_ID
                and field.name == "source_paired_torsion_rescue_proposal_receipt"
            )
        }
        typed = PublicRedockingEngineV2Diagnostics(
            **diagnostic_kwargs,
            candidates=tuple(candidates),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FreshRunVerificationError(
            "Fresh-128 Engine V2 diagnostics are not typed"
        ) from exc
    if typed.to_dict() != raw:
        raise FreshRunVerificationError(
            "Fresh-128 Engine V2 diagnostic schema is not closed"
        )
    return typed


def _typed_result(value: object) -> FreshRedockingCaseResult:
    raw = dict(_mapping(value, name="Fresh-128 engine row"))
    try:
        if raw.get("engine_id") == "engine_v2":
            diagnostics = _typed_engine_v2_diagnostics(raw.get("engine_v2_diagnostics"))
        else:
            if raw.get("engine_v2_diagnostics") is not None:
                raise ValueError("external row contains Engine V2 diagnostics")
            diagnostics = None
        typed = FreshRedockingCaseResult(
            **{
                field.name: raw[field.name]
                for field in fields(FreshRedockingCaseResult)
                if field.init and field.name != "engine_v2_diagnostics"
            },
            engine_v2_diagnostics=diagnostics,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FreshRunVerificationError("Fresh-128 engine row is not typed") from exc
    if typed.to_dict() != raw:
        raise FreshRunVerificationError("Fresh-128 engine row schema is not closed")
    if (
        typed.status == "failure"
        and typed.failure_code
        not in benchmark_contract._PUBLIC_REDOCKING_FAILURE_CODES[typed.engine_id]
    ):
        raise FreshRunVerificationError(
            "Fresh-128 engine row uses an unfrozen failure code"
        )
    return typed


def _execution_policy(row: FreshRedockingCaseResult) -> dict[str, object]:
    try:
        policy = benchmark_contract._execution_policy_mapping(row.execution_policy)
    except (TypeError, ValueError) as exc:
        raise FreshRunVerificationError(
            "Fresh-128 row execution policy is malformed"
        ) from exc
    return policy


def _validate_row_policy(
    row: FreshRedockingCaseResult,
    *,
    execution_profile_sha256: str,
    policy: PublicRedockingEvaluationPolicy,
    engine_v2_pipeline_profile_id: str,
    engine_v2_pipeline_profile_sha256: str,
) -> None:
    observed = _execution_policy(row)
    if row.engine_id == "engine_v2":
        required = {
            "algorithm_profile_id",
            "candidate_schema_id",
            "cpu_count",
            "docking_pipeline_profile_id",
            "docking_pipeline_profile_sha256",
            "execution_profile_sha256",
            "interaction_refinement_steps",
            "interaction_refiner",
            "interaction_refiner_config_sha256",
            "runner_id",
            "scorer_backend",
            "scorer_thread_count",
            "torch_interop_threads",
            "torch_intraop_threads",
            "torch_version",
        }
        if (
            set(observed) != required
            or observed.get("algorithm_profile_id")
            != PUBLIC_REDOCKING_ENGINE_V2_ALGORITHM_PROFILE_ID
            or observed.get("candidate_schema_id")
            != PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID
            or observed.get("cpu_count") != 1
            or observed.get("docking_pipeline_profile_id")
            != engine_v2_pipeline_profile_id
            or observed.get("docking_pipeline_profile_sha256")
            != engine_v2_pipeline_profile_sha256
            or observed.get("execution_profile_sha256") != execution_profile_sha256
            or observed.get("interaction_refinement_steps")
            != PUBLIC_REDOCKING_ENGINE_V2_REFINEMENT_STEPS
            or observed.get("interaction_refiner")
            != PUBLIC_REDOCKING_ENGINE_V2_REFINER_POLICY_ID
            or observed.get("interaction_refiner_config_sha256")
            != PUBLIC_REDOCKING_ENGINE_V2_REFINER_CONFIG_SHA256
            or observed.get("runner_id") != PUBLIC_REDOCKING_RUNNER_ID
            or observed.get("scorer_backend") != "rust_cpu_required"
            or observed.get("scorer_thread_count") != 1
            or observed.get("torch_interop_threads") != 1
            or observed.get("torch_intraop_threads") != 1
            or observed.get("torch_version")
            not in PUBLIC_REDOCKING_ALLOWED_TORCH_VERSIONS
        ):
            raise FreshRunVerificationError(
                "Fresh-128 Engine V2 row policy is not frozen"
            )
        return
    if observed != {
        "cpu_count": 1,
        "execution_profile_sha256": execution_profile_sha256,
        "timeout_seconds": policy.external_timeout_seconds,
    }:
        raise FreshRunVerificationError("Fresh-128 external row policy is not frozen")


def derive_fresh_subgroup_results(
    *,
    profiles: Sequence[FreshRedockingCaseProfile],
    row_map: Mapping[tuple[str, str], FreshRedockingCaseResult],
    policy: PublicRedockingEvaluationPolicy,
) -> list[dict[str, object]]:
    """Recompute the exact frozen size/rotor/ring descriptive ledger."""

    results: list[dict[str, object]] = []
    for attribute in ("size_subgroup", "rotor_subgroup", "ring_subgroup"):
        for subgroup in sorted({getattr(profile, attribute) for profile in profiles}):
            subgroup_ids = tuple(
                profile.case_id
                for profile in profiles
                if getattr(profile, attribute) == subgroup
            )
            engine_values: dict[str, object] = {}
            for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES:
                selected = [row_map[(engine_id, case_id)] for case_id in subgroup_ids]
                engine_values[engine_id] = {
                    "failure_rate": sum(row.status == "failure" for row in selected)
                    / len(selected),
                    "top1_2a_recovery_rate": sum(
                        row.recovery(1, policy.rmsd_threshold_angstrom)
                        for row in selected
                    )
                    / len(selected),
                    "top5_2a_recovery_rate": sum(
                        row.recovery(5, policy.rmsd_threshold_angstrom)
                        for row in selected
                    )
                    / len(selected),
                    "top5_valid_pose_recovery_rate": sum(
                        row.valid_recovery(5, policy.rmsd_threshold_angstrom)
                        for row in selected
                    )
                    / len(selected),
                }
            results.append(
                {
                    "subgroup": subgroup,
                    "case_count": len(subgroup_ids),
                    "case_ids_sha256": canonical_sha256(list(subgroup_ids)),
                    "engines": engine_values,
                }
            )
    return results


def build_candidate_slot_ledger(
    *,
    case_ids: Sequence[str],
    engine_v2_rows: Sequence[Mapping[str, object]],
    engine_v2_execution_receipts: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Build exactly 64 typed slots per case, including preparation failures."""

    expected_case_ids = tuple(str(case_id) for case_id in case_ids)
    if len(expected_case_ids) != FRESH_CASE_COUNT or len(set(expected_case_ids)) != (
        FRESH_CASE_COUNT
    ):
        raise FreshRunVerificationError("Fresh-128 case identity is incomplete")
    row_by_case: dict[str, Mapping[str, object]] = {}
    for raw_row in engine_v2_rows:
        row = _mapping(raw_row, name="Engine V2 row")
        case_id = str(row.get("case_id", ""))
        if row.get("engine_id") != "engine_v2" or case_id in row_by_case:
            raise FreshRunVerificationError("Engine V2 row ledger is cross-wired")
        row_by_case[case_id] = row
    receipt_by_case: dict[str, Mapping[str, object]] = {}
    for raw_receipt in engine_v2_execution_receipts:
        receipt = _mapping(raw_receipt, name="Engine V2 execution receipt")
        result = _mapping(
            receipt.get("result"),
            name="Engine V2 execution receipt result",
        )
        case_id = str(result.get("case_id", ""))
        if (
            result.get("engine_id") != "engine_v2"
            or case_id in receipt_by_case
            or receipt.get("receipt_sha256") is None
            or not _is_sha256(receipt.get("receipt_sha256"))
        ):
            raise FreshRunVerificationError(
                "Engine V2 execution receipt ledger is cross-wired"
            )
        if result != row_by_case.get(case_id):
            raise FreshRunVerificationError(
                "Engine V2 execution receipt does not bind its result row"
            )
        receipt_by_case[case_id] = receipt
    if set(row_by_case) != set(expected_case_ids) or set(receipt_by_case) != set(
        expected_case_ids
    ):
        raise FreshRunVerificationError("Engine V2 Fresh-128 ledger is incomplete")

    slots: list[dict[str, object]] = []
    for case_id in expected_case_ids:
        row = row_by_case[case_id]
        diagnostics = _mapping(
            row.get("engine_v2_diagnostics"),
            name="Engine V2 diagnostics",
        )
        preparation_status = diagnostics.get("preparation_status")
        preparation_failure_code = str(
            diagnostics.get("preparation_failure_code", "") or ""
        )
        raw_candidates = _sequence(
            diagnostics.get("candidates"),
            name="Engine V2 candidates",
        )
        if preparation_status == "success":
            if preparation_failure_code or len(raw_candidates) != (
                PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
            ):
                raise FreshRunVerificationError(
                    "successful Engine V2 preparation has an incomplete slot denominator"
                )
            candidates: dict[int, Mapping[str, object]] = {}
            for raw_candidate in raw_candidates:
                candidate = _mapping(
                    raw_candidate,
                    name="Engine V2 candidate diagnostic",
                )
                proposal_index = candidate.get("proposal_index")
                if (
                    type(proposal_index) is not int
                    or not 0
                    <= proposal_index
                    < PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT
                    or proposal_index in candidates
                    or candidate.get("status") not in {"success", "failure"}
                ):
                    raise FreshRunVerificationError(
                        "Engine V2 candidate slot identity is invalid"
                    )
                candidates[proposal_index] = candidate
            if set(candidates) != set(
                range(PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT)
            ):
                raise FreshRunVerificationError(
                    "Engine V2 candidate proposal indices are incomplete"
                )
        elif preparation_status == "failure":
            if not preparation_failure_code or raw_candidates:
                raise FreshRunVerificationError(
                    "failed Engine V2 preparation evidence is inconsistent"
                )
            candidates = {}
        else:
            raise FreshRunVerificationError("Engine V2 preparation status is invalid")

        execution_receipt_sha256 = str(receipt_by_case[case_id]["receipt_sha256"])
        for proposal_index in range(PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT):
            candidate = candidates.get(proposal_index)
            if candidate is None:
                slot_status = "preparation_failure"
                diagnostic_sha256 = ""
            else:
                slot_status = f"candidate_{candidate['status']}"
                diagnostic_sha256 = canonical_sha256(candidate)
            slots.append(
                {
                    "schema_id": FRESH_CANDIDATE_SLOT_SCHEMA_ID,
                    "case_id": case_id,
                    "proposal_index": proposal_index,
                    "slot_status": slot_status,
                    "candidate_diagnostic_sha256": diagnostic_sha256,
                    "engine_execution_receipt_sha256": (execution_receipt_sha256),
                    "preparation_failure_code": (
                        preparation_failure_code if candidate is None else ""
                    ),
                }
            )
    verify_candidate_slot_ledger(
        slots,
        case_ids=expected_case_ids,
        engine_v2_rows=engine_v2_rows,
        engine_v2_execution_receipts=engine_v2_execution_receipts,
    )
    return slots


def verify_candidate_slot_ledger(
    slots: Sequence[Mapping[str, object]],
    *,
    case_ids: Sequence[str],
    engine_v2_rows: Sequence[Mapping[str, object]],
    engine_v2_execution_receipts: Sequence[Mapping[str, object]],
) -> None:
    """Recompute the canonical slot ledger and reject any count or binding drift."""

    observed = [dict(_mapping(slot, name="candidate slot")) for slot in slots]
    # Build the expected ledger without recursively invoking this verifier.
    expected_case_ids = tuple(str(case_id) for case_id in case_ids)
    if len(observed) != FRESH_ENGINE_V2_SLOT_COUNT:
        raise FreshRunVerificationError(
            "Fresh-128 candidate slot denominator must equal 8192"
        )
    expected_keys = [
        (case_id, proposal_index)
        for case_id in expected_case_ids
        for proposal_index in range(PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT)
    ]
    observed_keys = [
        (str(slot.get("case_id", "")), slot.get("proposal_index")) for slot in observed
    ]
    if observed_keys != expected_keys or len(set(observed_keys)) != len(observed_keys):
        raise FreshRunVerificationError(
            "Fresh-128 candidate slot identities are incomplete or reordered"
        )
    expected_fields = {
        "schema_id",
        "case_id",
        "proposal_index",
        "slot_status",
        "candidate_diagnostic_sha256",
        "engine_execution_receipt_sha256",
        "preparation_failure_code",
    }
    if any(
        set(slot) != expected_fields
        or slot.get("schema_id") != FRESH_CANDIDATE_SLOT_SCHEMA_ID
        for slot in observed
    ):
        raise FreshRunVerificationError("Fresh-128 candidate slot schema is invalid")

    row_by_case = {
        str(row.get("case_id", "")): row
        for row in (_mapping(value, name="Engine V2 row") for value in engine_v2_rows)
    }
    receipt_by_case: dict[str, Mapping[str, object]] = {}
    for raw_receipt in engine_v2_execution_receipts:
        receipt = _mapping(raw_receipt, name="Engine V2 execution receipt")
        result = _mapping(receipt.get("result"), name="execution result")
        receipt_by_case[str(result.get("case_id", ""))] = receipt
    if set(row_by_case) != set(expected_case_ids) or set(receipt_by_case) != set(
        expected_case_ids
    ):
        raise FreshRunVerificationError("Fresh-128 slot source ledgers are incomplete")
    for slot in observed:
        case_id = str(slot["case_id"])
        proposal_index = int(slot["proposal_index"])
        diagnostics = _mapping(
            row_by_case[case_id].get("engine_v2_diagnostics"),
            name="Engine V2 diagnostics",
        )
        candidates = _sequence(
            diagnostics.get("candidates"),
            name="Engine V2 candidates",
        )
        if slot.get("engine_execution_receipt_sha256") != receipt_by_case[case_id].get(
            "receipt_sha256"
        ):
            raise FreshRunVerificationError(
                "Fresh-128 candidate slot execution binding is invalid"
            )
        if diagnostics.get("preparation_status") == "failure":
            if (
                slot.get("slot_status") != "preparation_failure"
                or slot.get("candidate_diagnostic_sha256") != ""
                or slot.get("preparation_failure_code")
                != diagnostics.get("preparation_failure_code")
                or candidates
            ):
                raise FreshRunVerificationError(
                    "Fresh-128 preparation-failure slot is invalid"
                )
            continue
        if len(candidates) != PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT:
            raise FreshRunVerificationError(
                "Fresh-128 successful candidate diagnostics are incomplete"
            )
        candidate = _mapping(
            candidates[proposal_index],
            name="Engine V2 candidate diagnostic",
        )
        if (
            candidate.get("proposal_index") != proposal_index
            or slot.get("slot_status") != f"candidate_{candidate.get('status')}"
            or slot.get("candidate_diagnostic_sha256") != canonical_sha256(candidate)
            or slot.get("preparation_failure_code") != ""
        ):
            raise FreshRunVerificationError(
                "Fresh-128 candidate diagnostic slot binding is invalid"
            )


def verify_reservation_document(
    payload: Mapping[str, object],
) -> str:
    reservation = _mapping(payload, name="run-once reservation")
    required = {
        "schema_id",
        "runner_id",
        "status",
        "reservation_nonce",
        "reserved_at_unix_ns",
        "retention_root",
        "fresh_holdout_manifest_sha256",
        "case_ids_sha256",
        "stage0_policy_sha256",
        "source_freeze_sha256",
        "execution_profile_sha256",
        "external_run_once_authority_id",
        "external_run_once_reservation_sha256",
        "fresh_run_identity_sha256",
        "docking_pipeline_profile_id",
        "docking_pipeline_profile_sha256",
        "external_worm_reservation_bound",
        "expected_case_count",
        "expected_engine_case_row_count",
        "expected_engine_v2_candidate_slot_count",
        "single_execution_only",
        "resume_allowed",
        "rerun_allowed",
        "result_dependent_changes_allowed",
        "reservation_sha256",
    }
    if set(reservation) != required:
        raise FreshRunVerificationError("run-once reservation fields are incomplete")
    retention_root = str(reservation.get("retention_root", ""))
    retention_path = PurePosixPath(retention_root)
    retention_parts = retention_path.parts
    if (
        reservation.get("schema_id") != FRESH_RUN_ONCE_RESERVATION_SCHEMA_ID
        or reservation.get("runner_id") != FRESH_RUNNER_ID
        or reservation.get("status") != "reserved_before_holdout_open"
        or not isinstance(reservation.get("reservation_nonce"), str)
        or len(str(reservation.get("reservation_nonce"))) != 32
        or any(
            character not in _HEX
            for character in str(reservation.get("reservation_nonce"))
        )
        or type(reservation.get("reserved_at_unix_ns")) is not int
        or int(reservation["reserved_at_unix_ns"]) < 1
        or retention_root != STAGE0_CANONICAL_FRESH_RETENTION_ROOT
        or retention_path.is_absolute()
        or retention_parts != (".betelgeuze", "fresh-redocking-128")
        or any(part in {"", ".", ".."} for part in retention_parts)
        or retention_path.as_posix() != retention_root
        or "\\" in retention_root
        or reservation.get("fresh_holdout_manifest_sha256")
        != FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256
        or reservation.get("case_ids_sha256")
        != canonical_sha256(list(FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS))
        or reservation.get("expected_case_count") != FRESH_CASE_COUNT
        or reservation.get("expected_engine_case_row_count") != FRESH_ENGINE_ROW_COUNT
        or reservation.get("expected_engine_v2_candidate_slot_count")
        != FRESH_ENGINE_V2_SLOT_COUNT
        or reservation.get("single_execution_only") is not True
        or reservation.get("resume_allowed") is not False
        or reservation.get("rerun_allowed") is not False
        or reservation.get("result_dependent_changes_allowed") is not False
        or not str(reservation.get("external_run_once_authority_id", "")).strip()
        or not str(reservation.get("docking_pipeline_profile_id", "")).strip()
        or reservation.get("external_worm_reservation_bound") is not True
    ):
        raise FreshRunVerificationError("run-once reservation policy is invalid")
    for field in (
        "fresh_holdout_manifest_sha256",
        "case_ids_sha256",
        "stage0_policy_sha256",
        "source_freeze_sha256",
        "execution_profile_sha256",
        "external_run_once_reservation_sha256",
        "fresh_run_identity_sha256",
        "docking_pipeline_profile_sha256",
    ):
        if not _is_sha256(reservation.get(field)):
            raise FreshRunVerificationError(f"run-once reservation {field} is invalid")
    return _self_hash(
        reservation,
        field="reservation_sha256",
        name="run-once reservation",
    )


def verify_fresh_report_document(
    payload: Mapping[str, object],
    *,
    reservation_sha256: str,
    repo_root: Path | None = None,
    source_repo_root: Path | None = None,
    expected_output_root: Path | None = None,
) -> str:
    report = dict(_mapping(payload, name="Fresh-128 report"))
    expected_fields = {
        "schema_id",
        "runner_id",
        "analysis_scope",
        "case_count",
        "engine_case_row_count",
        "engine_v2_candidate_slot_count",
        "engine_v2_candidate_slots",
        "run_once_reservation_sha256",
        "fresh_holdout_manifest_sha256",
        "stage0_admission",
        "policy",
        "profiles",
        "materializations",
        "engine_identities",
        "metrics",
        "subgroup_results",
        "rows",
        "execution_receipts",
        "internal_provisional_only",
        "scientifically_validated",
        "public_claim_eligible",
        "product_promotion_eligible",
        "external_independent_review_required_before_public_claim",
        "claim_safe",
        "fingerprint_sha256",
    }
    if (
        set(report) != expected_fields
        or report.get("schema_id") != FRESH_INTERNAL_REPORT_SCHEMA_ID
        or report.get("runner_id") != FRESH_RUNNER_ID
        or report.get("analysis_scope") != "fresh_internal_blind_holdout"
        or report.get("case_count") != FRESH_CASE_COUNT
        or report.get("engine_case_row_count") != FRESH_ENGINE_ROW_COUNT
        or report.get("engine_v2_candidate_slot_count") != FRESH_ENGINE_V2_SLOT_COUNT
        or report.get("run_once_reservation_sha256") != reservation_sha256
        or report.get("internal_provisional_only") is not True
        or report.get("scientifically_validated") is not False
        or report.get("public_claim_eligible") is not False
        or report.get("product_promotion_eligible") is not False
        or report.get("external_independent_review_required_before_public_claim")
        is not True
        or report.get("claim_safe") is not False
    ):
        raise FreshRunVerificationError("Fresh-128 report authority is invalid")
    active_repo_root = Path(
        os.path.abspath(
            os.fspath(_DEFAULT_REPO_ROOT if repo_root is None else repo_root)
        )
    )
    active_source_repo_root = Path(
        os.path.abspath(
            os.fspath(
                active_repo_root if source_repo_root is None else source_repo_root
            )
        )
    )
    canonical_output_root: Path | None = None
    if expected_output_root is not None:
        output_root_text = os.fspath(expected_output_root)
        canonical_output_root = Path(output_root_text)
        if (
            not canonical_output_root.is_absolute()
            or os.path.normpath(output_root_text) != output_root_text
            or str(canonical_output_root) != output_root_text
        ):
            raise FreshRunVerificationError(
                "Fresh-128 expected output root is not canonical"
            )
    holdout = _trusted_holdout(active_repo_root)
    (
        expected_engine_v2_implementation_sha256,
        expected_pipeline_profile_id,
        expected_pipeline_profile_sha256,
    ) = _fresh_engine_v2_source_identity(active_source_repo_root)
    case_ids = holdout.case_ids
    if report.get("fresh_holdout_manifest_sha256") != (
        FRESH_REDOCKING_HOLDOUT_MANIFEST_SHA256
    ):
        raise FreshRunVerificationError("Fresh-128 manifest identity is invalid")
    admission = dict(
        _mapping(
            report.get("stage0_admission"),
            name="Stage 0 admission binding",
        )
    )
    if set(admission) != {
        "policy_sha256",
        "source_freeze_sha256",
        "execution_profile_sha256",
        "governance_mode",
        "independent_review_complete",
        "trusted_review_time_authority_id",
        "trusted_review_time_evidence_sha256",
        "external_run_once_authority_id",
        "external_run_once_reservation_sha256",
        "fresh_run_identity_sha256",
        "docking_pipeline_profile_id",
        "docking_pipeline_profile_sha256",
    }:
        raise FreshRunVerificationError("Fresh-128 Stage 0 binding schema is invalid")
    for field in (
        "policy_sha256",
        "source_freeze_sha256",
        "execution_profile_sha256",
        "trusted_review_time_evidence_sha256",
        "external_run_once_reservation_sha256",
        "fresh_run_identity_sha256",
        "docking_pipeline_profile_sha256",
    ):
        if not _is_sha256(admission.get(field)):
            raise FreshRunVerificationError(f"Fresh-128 Stage 0 {field} is invalid")
    governance_mode = str(admission.get("governance_mode", ""))
    independent_review_complete = admission.get("independent_review_complete")
    if (
        governance_mode != "independent_three_role"
        or independent_review_complete is not True
        or not str(admission.get("trusted_review_time_authority_id", "")).strip()
        or not str(admission.get("external_run_once_authority_id", "")).strip()
        or not str(admission.get("docking_pipeline_profile_id", "")).strip()
    ):
        raise FreshRunVerificationError(
            "Fresh-128 requires completed independent Stage 0 governance"
        )
    if (
        admission.get("docking_pipeline_profile_id") != expected_pipeline_profile_id
        or admission.get("docking_pipeline_profile_sha256")
        != expected_pipeline_profile_sha256
    ):
        raise FreshRunVerificationError(
            "Fresh-128 Stage 0 pipeline profile is not source authoritative"
        )
    policy = _typed_policy(report.get("policy"))
    raw_profiles = _sequence(report.get("profiles"), name="Fresh-128 profiles")
    if len(raw_profiles) != FRESH_CASE_COUNT:
        raise FreshRunVerificationError("Fresh-128 profile denominator is incomplete")
    profiles = tuple(
        _typed_profile(raw, frozen_case=frozen_case)
        for raw, frozen_case in zip(raw_profiles, holdout.cases, strict=True)
    )
    if tuple(profile.case_id for profile in profiles) != case_ids:
        raise FreshRunVerificationError("Fresh-128 profile order is invalid")

    raw_materializations = _sequence(
        report.get("materializations"), name="Fresh-128 materializations"
    )
    if len(raw_materializations) != FRESH_CASE_COUNT:
        raise FreshRunVerificationError(
            "Fresh-128 materialization denominator is incomplete"
        )
    materializations = tuple(
        _typed_materialization(raw, frozen_case=frozen_case)
        for raw, frozen_case in zip(raw_materializations, holdout.cases, strict=True)
    )

    raw_identities = _sequence(
        report.get("engine_identities"), name="Fresh-128 engine identities"
    )
    identities = tuple(_typed_identity(raw) for raw in raw_identities)
    if tuple(identity.engine_id for identity in identities) != (
        PUBLIC_REDOCKING_PRIMARY_ENGINES
    ):
        raise FreshRunVerificationError(
            "Fresh-128 engine identity ledger is incomplete"
        )
    if (
        len({identity.evaluation_pipeline_sha256 for identity in identities}) != 1
        or identities[1].implementation_sha256 != identities[2].implementation_sha256
    ):
        raise FreshRunVerificationError("Fresh-128 engine identities are cross-wired")
    if identities[0].implementation_sha256 != (
        expected_engine_v2_implementation_sha256
    ):
        raise FreshRunVerificationError(
            "Fresh-128 Engine V2 implementation does not match the source closure"
        )
    identity_by_engine = {identity.engine_id: identity for identity in identities}

    raw_rows = [
        dict(_mapping(row, name="Fresh-128 engine row"))
        for row in _sequence(report.get("rows"), name="Fresh-128 rows")
    ]
    expected_row_keys = [
        (engine_id, case_id)
        for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES
        for case_id in case_ids
    ]
    observed_row_keys = [
        (str(row.get("engine_id", "")), str(row.get("case_id", ""))) for row in raw_rows
    ]
    if (
        observed_row_keys != expected_row_keys
        or len(raw_rows) != FRESH_ENGINE_ROW_COUNT
    ):
        raise FreshRunVerificationError("Fresh-128 report engine rows are incomplete")
    rows = tuple(_typed_result(raw) for raw in raw_rows)
    materialization_by_case = {
        materialization.case_id: materialization for materialization in materializations
    }
    row_map = {(row.engine_id, row.case_id): row for row in rows}
    for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES:
        if (
            len({row.execution_policy for row in rows if row.engine_id == engine_id})
            != 1
        ):
            raise FreshRunVerificationError(
                "Fresh-128 row execution policy is not uniform by engine"
            )
    engine_v2_command_roots: set[Path] = set()
    for row in rows:
        frozen_case = materialization_by_case[row.case_id]
        if {
            "receptor": row.receptor_artifact_sha256,
            "reference": row.reference_artifact_sha256,
            "native": row.native_artifact_sha256,
            "seed": row.seed_artifact_sha256,
        } != dict(frozen_case.artifact_sha256s):
            raise FreshRunVerificationError(
                "Fresh-128 row input hashes do not match the frozen materialization"
            )
        _validate_row_policy(
            row,
            execution_profile_sha256=str(admission["execution_profile_sha256"]),
            policy=policy,
            engine_v2_pipeline_profile_id=expected_pipeline_profile_id,
            engine_v2_pipeline_profile_sha256=expected_pipeline_profile_sha256,
        )
        if row.engine_id == "engine_v2":
            engine_v2_command_roots.add(
                _validated_fresh_engine_v2_command_root(
                    row,
                    expected_output_root=canonical_output_root,
                )
            )
    if len(engine_v2_command_roots) != 1:
        raise FreshRunVerificationError(
            "Fresh-128 Engine V2 command roots are not uniform"
        )
    engine_v2_command_root = next(iter(engine_v2_command_roots))
    try:
        command_root_relative = engine_v2_command_root.relative_to(active_repo_root)
    except ValueError as exc:
        raise FreshRunVerificationError(
            "Fresh-128 Engine V2 command root escapes the repository"
        ) from exc
    if (
        len(command_root_relative.parts) < 2
        or command_root_relative.parts[0] != ".betelgeuze"
    ):
        raise FreshRunVerificationError(
            "Fresh-128 Engine V2 command root is outside retention"
        )
    engine_v2_policy = _execution_policy(rows[0])
    expected_engine_v2_identity_command = (
        PUBLIC_REDOCKING_RUNNER_ID,
        "engine_v2",
        "--candidate-count",
        str(PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT),
        "--cpu",
        "1",
        "--torch-version",
        str(engine_v2_policy["torch_version"]),
    )
    if identities[0].command != expected_engine_v2_identity_command:
        raise FreshRunVerificationError(
            "Fresh-128 Engine V2 identity command is not canonical"
        )

    receipts = [
        dict(_mapping(row, name="Fresh-128 execution receipt"))
        for row in _sequence(
            report.get("execution_receipts"),
            name="Fresh-128 execution receipts",
        )
    ]
    if len(receipts) != FRESH_ENGINE_ROW_COUNT:
        raise FreshRunVerificationError(
            "Fresh-128 execution receipt denominator is incomplete"
        )
    receipt_fields = {
        "schema_id",
        "runner_id",
        "archive_sha256",
        "source_ids_sha256",
        "command",
        "execution_policy",
        "input_sha256s",
        "materialization_receipt_sha256",
        "implementation_sha256",
        "evaluation_pipeline_sha256",
        "execution_environment_sha256",
        "cache_read_allowed",
        "fresh_execution",
        "result",
        "receipt_sha256",
    }
    receipt_sha256s: list[str] = []
    execution_environments: set[str] = set()
    for raw_row, row, receipt in zip(raw_rows, rows, receipts, strict=True):
        receipt_projection = dict(receipt)
        receipt_sha256 = receipt_projection.pop("receipt_sha256", None)
        input_sha256s = {
            "receptor": row.receptor_artifact_sha256,
            "reference": row.reference_artifact_sha256,
            "native": row.native_artifact_sha256,
            "seed": row.seed_artifact_sha256,
        }
        identity = identity_by_engine[row.engine_id]
        materialization = materialization_by_case[row.case_id]
        if (
            set(receipt) != receipt_fields
            or receipt.get("schema_id") != PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID
            or receipt.get("runner_id") != PUBLIC_REDOCKING_RUNNER_ID
            or receipt.get("archive_sha256") != PUBLIC_REDOCKING_ARCHIVE_SHA256
            or receipt.get("source_ids_sha256") != PUBLIC_REDOCKING_SOURCE_IDS_SHA256
            or receipt.get("command") != list(row.execution_command)
            or receipt.get("execution_policy") != _execution_policy(row)
            or receipt.get("input_sha256s") != input_sha256s
            or receipt.get("materialization_receipt_sha256")
            != materialization.receipt_sha256
            or receipt.get("implementation_sha256") != identity.implementation_sha256
            or receipt.get("evaluation_pipeline_sha256")
            != identity.evaluation_pipeline_sha256
            or not _is_sha256(receipt.get("execution_environment_sha256"))
            or receipt.get("cache_read_allowed") is not False
            or receipt.get("fresh_execution") is not True
            or _mapping(receipt.get("result"), name="execution receipt result")
            != raw_row
            or not _is_sha256(receipt_sha256)
            or receipt_sha256 != canonical_sha256(receipt_projection)
        ):
            raise FreshRunVerificationError(
                "Fresh-128 execution receipt is cross-wired"
            )
        receipt_sha256s.append(str(receipt_sha256))
        execution_environments.add(str(receipt["execution_environment_sha256"]))
    if (
        len(set(receipt_sha256s)) != FRESH_ENGINE_ROW_COUNT
        or len(execution_environments) != 1
    ):
        raise FreshRunVerificationError(
            "Fresh-128 execution receipt identities are not unique and uniform"
        )

    engine_v2_rows = raw_rows[:FRESH_CASE_COUNT]
    engine_v2_receipts = receipts[:FRESH_CASE_COUNT]
    slots = [
        _mapping(slot, name="Fresh-128 candidate slot")
        for slot in _sequence(
            report.get("engine_v2_candidate_slots"),
            name="Fresh-128 candidate slots",
        )
    ]
    verify_candidate_slot_ledger(
        slots,
        case_ids=case_ids,
        engine_v2_rows=engine_v2_rows,
        engine_v2_execution_receipts=engine_v2_receipts,
    )
    expected_metrics = [
        metric.to_dict()
        for metric in benchmark_contract._derive_scope_all_metrics(
            dict(row_map),
            policy=policy,
            analysis_scope="fresh_internal_blind_holdout",
            case_ids=case_ids,
        )
    ]
    if report.get("metrics") != expected_metrics:
        raise FreshRunVerificationError(
            "Fresh-128 metrics do not recompute from the typed row ledger"
        )
    expected_subgroups = derive_fresh_subgroup_results(
        profiles=profiles,
        row_map=row_map,
        policy=policy,
    )
    if report.get("subgroup_results") != expected_subgroups:
        raise FreshRunVerificationError(
            "Fresh-128 subgroup results do not recompute from the typed row ledger"
        )
    return _self_hash(
        report,
        field="fingerprint_sha256",
        name="Fresh-128 report",
    )


def verify_completion_document(
    payload: Mapping[str, object],
    *,
    reservation_sha256: str,
    report_fingerprint_sha256: str,
    report_file_sha256: str,
    artifact_manifest_sha256: str,
    artifact_manifest_file_sha256: str,
) -> str:
    completion = _mapping(payload, name="run-once completion")
    required = {
        "schema_id",
        "runner_id",
        "status",
        "completed_at_unix_ns",
        "reservation_sha256",
        "report_fingerprint_sha256",
        "report_file_sha256",
        "artifact_manifest_sha256",
        "artifact_manifest_file_sha256",
        "case_count",
        "engine_case_row_count",
        "engine_v2_candidate_slot_count",
        "thresholds_modified_after_results",
        "scorer_weights_modified_after_results",
        "proposal_allocation_modified_after_results",
        "failed_cases_rerun",
        "fresh_cases_moved_to_development",
        "completion_sha256",
    }
    if set(completion) != required:
        raise FreshRunVerificationError("run-once completion fields are incomplete")
    if (
        completion.get("schema_id") != FRESH_RUN_ONCE_COMPLETION_SCHEMA_ID
        or completion.get("runner_id") != FRESH_RUNNER_ID
        or completion.get("status") != "complete"
        or type(completion.get("completed_at_unix_ns")) is not int
        or int(completion["completed_at_unix_ns"]) < 1
        or completion.get("reservation_sha256") != reservation_sha256
        or completion.get("report_fingerprint_sha256") != report_fingerprint_sha256
        or completion.get("report_file_sha256") != report_file_sha256
        or completion.get("artifact_manifest_sha256") != artifact_manifest_sha256
        or completion.get("artifact_manifest_file_sha256")
        != artifact_manifest_file_sha256
        or completion.get("case_count") != FRESH_CASE_COUNT
        or completion.get("engine_case_row_count") != FRESH_ENGINE_ROW_COUNT
        or completion.get("engine_v2_candidate_slot_count")
        != FRESH_ENGINE_V2_SLOT_COUNT
        or completion.get("thresholds_modified_after_results") is not False
        or completion.get("scorer_weights_modified_after_results") is not False
        or completion.get("proposal_allocation_modified_after_results") is not False
        or completion.get("failed_cases_rerun") is not False
        or completion.get("fresh_cases_moved_to_development") is not False
    ):
        raise FreshRunVerificationError("run-once completion policy is invalid")
    return _self_hash(
        completion,
        field="completion_sha256",
        name="run-once completion",
    )


def verify_terminal_failure_document(
    payload: Mapping[str, object],
    *,
    reservation_sha256: str,
) -> str:
    failure = _mapping(payload, name="run-once terminal failure")
    required = {
        "schema_id",
        "runner_id",
        "status",
        "failed_at_unix_ns",
        "reservation_sha256",
        "exception_type",
        "private_error_sha256",
        "private_error_byte_length",
        "completion_published",
        "rerun_allowed",
        "result_replacement_allowed",
        "claim_safe",
        "failure_sha256",
    }
    exception_type = failure.get("exception_type")
    if (
        set(failure) != required
        or failure.get("schema_id") != FRESH_RUN_TERMINAL_FAILURE_SCHEMA_ID
        or failure.get("runner_id") != FRESH_RUNNER_ID
        or failure.get("status") != "failed_terminal"
        or type(failure.get("failed_at_unix_ns")) is not int
        or int(failure["failed_at_unix_ns"]) < 1
        or failure.get("reservation_sha256") != reservation_sha256
        or not isinstance(exception_type, str)
        or not 1 <= len(exception_type) <= 512
        or any(
            character
            not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_."
            for character in exception_type
        )
        or not _is_sha256(failure.get("private_error_sha256"))
        or type(failure.get("private_error_byte_length")) is not int
        or int(failure["private_error_byte_length"]) < 1
        or failure.get("completion_published") is not False
        or failure.get("rerun_allowed") is not False
        or failure.get("result_replacement_allowed") is not False
        or failure.get("claim_safe") is not False
    ):
        raise FreshRunVerificationError("run-once terminal failure is invalid")
    return _self_hash(
        failure,
        field="failure_sha256",
        name="run-once terminal failure",
    )


def _directory_descriptor(path: Path) -> int:
    if not path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise FreshRunVerificationError(
            "Fresh-128 directory must be an absolute canonical path"
        )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = -1
    try:
        descriptor = os.open("/", flags)
        for component in path.parts[1:]:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError as exc:
        if descriptor >= 0:
            os.close(descriptor)
        raise FreshRunVerificationError(
            "Fresh-128 directory contains a missing or symlink component"
        ) from exc


def _require_owned_directory(
    descriptor: int,
    *,
    name: str,
    exact_mode: int | None = None,
) -> os.stat_result:
    status = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(status.st_mode)
        or (hasattr(os, "geteuid") and status.st_uid != os.geteuid())
        or (exact_mode is not None and stat.S_IMODE(status.st_mode) != exact_mode)
    ):
        raise FreshRunVerificationError(
            f"{name} must be an owned directory with frozen permissions"
        )
    return status


def _require_path_identity(path: Path, status: os.stat_result) -> None:
    try:
        observed = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise FreshRunVerificationError(
            "Fresh-128 output root path became unavailable"
        ) from exc
    if not stat.S_ISDIR(observed.st_mode) or (
        observed.st_dev,
        observed.st_ino,
        observed.st_uid,
    ) != (status.st_dev, status.st_ino, status.st_uid):
        raise FreshRunVerificationError(
            "Fresh-128 output root identity changed during verification"
        )


def _read_owned_canonical_json_at(
    directory_descriptor: int,
    name: str,
    *,
    maximum: int,
) -> _OwnedCanonicalJson:
    if not name or "/" in name or name in {".", ".."}:
        raise FreshRunVerificationError("Fresh-128 artifact name is invalid")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = -1
    try:
        descriptor = os.open(name, flags, dir_fd=directory_descriptor)
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or (hasattr(os, "geteuid") and before.st_uid != os.geteuid())
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_size < 2
            or before.st_size > maximum
        ):
            raise FreshRunVerificationError(
                f"Fresh-128 artifact is not a bounded owned regular file: {name}"
            )
        raw = os.pread(descriptor, before.st_size + 1, 0)
        after = os.fstat(descriptor)

        if len(raw) != before.st_size or _stat_identity(before) != _stat_identity(
            after
        ):
            raise FreshRunVerificationError(
                f"Fresh-128 artifact changed while it was read: {name}"
            )
    except FreshRunVerificationError:
        raise
    except OSError as exc:
        raise FreshRunVerificationError(
            f"required Fresh-128 artifact is missing or unsafe: {name}"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    if not canonical or b"\r" in raw or raw.endswith(b"\n\n"):
        raise FreshRunVerificationError(
            f"Fresh-128 artifact line endings are invalid: {name}"
        )
    try:
        payload = json.loads(canonical.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FreshRunVerificationError(
            f"Fresh-128 artifact is invalid JSON: {name}"
        ) from exc
    if not isinstance(payload, dict) or canonical_bytes(payload) != canonical:
        raise FreshRunVerificationError(
            f"Fresh-128 artifact is not canonical JSON: {name}"
        )
    return _OwnedCanonicalJson(payload=payload, raw=raw)


def _verify_stage0_disk_receipt(
    payload: Mapping[str, object],
    *,
    admission: Mapping[str, object],
    reservation: Mapping[str, object],
    trusted: VerifiedStage0Admission | None,
) -> None:
    receipt = dict(payload)
    try:
        validate_stage0_admission_receipt_document(receipt)
    except (Stage0AdmissionError, TypeError, ValueError) as exc:
        raise FreshRunVerificationError(
            "on-disk Stage 0 admission receipt schema is invalid"
        ) from exc
    if (
        receipt.get("policy_sha256") != admission.get("policy_sha256")
        or receipt.get("execution_profile_sha256")
        != admission.get("execution_profile_sha256")
        or receipt.get("source_freeze_sha256") != admission.get("source_freeze_sha256")
        or receipt.get("governance_mode") != admission.get("governance_mode")
        or receipt.get("independent_review_complete")
        is not admission.get("independent_review_complete")
        or receipt.get("policy_sha256") != reservation.get("stage0_policy_sha256")
        or receipt.get("execution_profile_sha256")
        != reservation.get("execution_profile_sha256")
        or receipt.get("source_freeze_sha256")
        != reservation.get("source_freeze_sha256")
        or receipt.get("trusted_review_time_authority_id")
        != admission.get("trusted_review_time_authority_id")
        or receipt.get("trusted_review_time_evidence_sha256")
        != admission.get("trusted_review_time_evidence_sha256")
        or receipt.get("external_run_once_authority_id")
        != admission.get("external_run_once_authority_id")
        or receipt.get("external_run_once_reservation_sha256")
        != admission.get("external_run_once_reservation_sha256")
        or receipt.get("fresh_run_identity_sha256")
        != admission.get("fresh_run_identity_sha256")
        or receipt.get("docking_pipeline_profile_id")
        != admission.get("docking_pipeline_profile_id")
        or receipt.get("docking_pipeline_profile_sha256")
        != admission.get("docking_pipeline_profile_sha256")
        or receipt.get("external_run_once_authority_id")
        != reservation.get("external_run_once_authority_id")
        or receipt.get("external_run_once_reservation_sha256")
        != reservation.get("external_run_once_reservation_sha256")
        or receipt.get("fresh_run_identity_sha256")
        != reservation.get("fresh_run_identity_sha256")
        or receipt.get("docking_pipeline_profile_id")
        != reservation.get("docking_pipeline_profile_id")
        or receipt.get("docking_pipeline_profile_sha256")
        != reservation.get("docking_pipeline_profile_sha256")
    ):
        raise FreshRunVerificationError(
            "on-disk Stage 0 admission receipt is cross-wired"
        )
    if trusted is not None and receipt != trusted.to_dict():
        raise FreshRunVerificationError(
            "on-disk Stage 0 receipt does not match trusted admission"
        )


def _canonical_file_sha256(payload: object) -> str:
    return hashlib.sha256(canonical_bytes(payload) + b"\n").hexdigest()


def _manifest_entry_map(
    manifest: Mapping[str, object],
) -> dict[str, Mapping[str, object]]:
    entries = _sequence(manifest.get("entries"), name="Fresh artifact entries")
    mapped: dict[str, Mapping[str, object]] = {}
    for raw_entry in entries:
        entry = _mapping(raw_entry, name="Fresh artifact entry")
        relative_path = str(entry.get("relative_path", ""))
        if not relative_path or relative_path in mapped:
            raise FreshRunVerificationError(
                "Fresh artifact manifest paths are incomplete"
            )
        mapped[relative_path] = entry
    return mapped


def _read_manifest_artifact_at(
    root_descriptor: int,
    *,
    relative_path: str,
    entry: Mapping[str, object],
    maximum: int,
) -> bytes:
    path = PurePosixPath(relative_path)
    if (
        path.is_absolute()
        or path.as_posix() != relative_path
        or any(part in {"", ".", ".."} for part in path.parts)
        or not path.parts
    ):
        raise FreshRunVerificationError("Fresh artifact path is invalid")
    directory_descriptor = os.dup(root_descriptor)
    file_descriptor = -1
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    file_flags = (
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        for component in path.parts[:-1]:
            next_descriptor = os.open(
                component,
                directory_flags,
                dir_fd=directory_descriptor,
            )
            os.close(directory_descriptor)
            directory_descriptor = next_descriptor
            directory_status = os.fstat(directory_descriptor)
            if (
                not stat.S_ISDIR(directory_status.st_mode)
                or stat.S_IMODE(directory_status.st_mode) != 0o700
                or (hasattr(os, "geteuid") and directory_status.st_uid != os.geteuid())
            ):
                raise FreshRunVerificationError(
                    "Fresh artifact directory permissions changed"
                )
        file_descriptor = os.open(
            path.parts[-1],
            file_flags,
            dir_fd=directory_descriptor,
        )
        before = os.fstat(file_descriptor)
        expected_size = entry.get("size_bytes")
        expected_mode = int(str(entry.get("mode_octal", "0")), 8)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or (hasattr(os, "geteuid") and before.st_uid != os.geteuid())
            or stat.S_IMODE(before.st_mode) != expected_mode
            or type(expected_size) is not int
            or before.st_size != expected_size
            or not 1 <= before.st_size <= maximum
        ):
            raise FreshRunVerificationError("Fresh artifact identity or bounds changed")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(file_descriptor, min(1024 * 1024, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise FreshRunVerificationError("Fresh artifact exceeds its bound")
        raw = b"".join(chunks)
        after = os.fstat(file_descriptor)
        if (
            len(raw) != before.st_size
            or _stat_identity(before) != _stat_identity(after)
            or hashlib.sha256(raw).hexdigest() != entry.get("sha256")
        ):
            raise FreshRunVerificationError(
                "Fresh artifact changed while it was verified"
            )
        return raw
    except FreshRunVerificationError:
        raise
    except (OSError, ValueError) as exc:
        raise FreshRunVerificationError(
            "Fresh artifact could not be pinned from its manifest"
        ) from exc
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        os.close(directory_descriptor)


def _pose_record_sha256s(raw: bytes) -> tuple[str, ...]:
    if not raw or b"\r" in raw or not raw.endswith(b"$$$$\n"):
        raise FreshRunVerificationError("retained Fresh pose SDF is invalid")
    chunks = raw.split(b"$$$$\n")
    if chunks[-1] != b"" or any(not chunk for chunk in chunks[:-1]):
        raise FreshRunVerificationError("retained Fresh pose records are incomplete")
    return tuple(hashlib.sha256(chunk + b"$$$$\n").hexdigest() for chunk in chunks[:-1])


def _verify_process_log(
    value: object,
    *,
    engine_id: object,
    failure_code: object,
) -> None:
    process_log = _mapping(value, name="Fresh process log")
    if set(process_log) != {
        "capture_mode",
        "timeout_terminated",
        "log_limit_terminated",
        "stdout",
        "stderr",
    }:
        raise FreshRunVerificationError("Fresh process log fields are invalid")
    expected_mode = (
        "structured_in_process"
        if engine_id == "engine_v2"
        else "bounded_subprocess_pipe"
    )
    if (
        process_log.get("capture_mode") != expected_mode
        or type(process_log.get("timeout_terminated")) is not bool
        or type(process_log.get("log_limit_terminated")) is not bool
        or (process_log.get("timeout_terminated") is True)
        != (failure_code == "external_timeout")
        or (process_log.get("log_limit_terminated") is True)
        != (failure_code == "external_log_limit_exceeded")
    ):
        raise FreshRunVerificationError("Fresh process log disposition is invalid")
    for stream_name in ("stdout", "stderr"):
        stream = _mapping(
            process_log.get(stream_name),
            name=f"Fresh {stream_name} process log",
        )
        if set(stream) != {
            "payload_base64",
            "retained_byte_count",
            "observed_byte_count",
            "observed_sha256",
            "payload_complete",
        }:
            raise FreshRunVerificationError(
                "Fresh retained process stream fields are invalid"
            )
        encoded = stream.get("payload_base64")
        if not isinstance(encoded, str):
            raise FreshRunVerificationError(
                "Fresh retained process stream payload is invalid"
            )
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise FreshRunVerificationError(
                "Fresh retained process stream payload is invalid"
            ) from exc
        retained_count = stream.get("retained_byte_count")
        observed_count = stream.get("observed_byte_count")
        payload_complete = stream.get("payload_complete")
        if (
            type(retained_count) is not int
            or type(observed_count) is not int
            or not 0 <= retained_count <= 64 * 1024
            or observed_count < retained_count
            or retained_count != len(payload)
            or base64.b64encode(payload).decode("ascii") != encoded
            or not _is_sha256(stream.get("observed_sha256"))
            or type(payload_complete) is not bool
            or payload_complete != (observed_count == retained_count)
        ):
            raise FreshRunVerificationError(
                "Fresh retained process stream bounds are invalid"
            )
        if payload_complete and hashlib.sha256(payload).hexdigest() != stream.get(
            "observed_sha256"
        ):
            raise FreshRunVerificationError(
                "Fresh retained process stream digest is invalid"
            )
        if engine_id == "engine_v2" and (
            payload
            or observed_count != 0
            or payload_complete is not True
            or process_log.get("timeout_terminated") is not False
            or process_log.get("log_limit_terminated") is not False
        ):
            raise FreshRunVerificationError(
                "Fresh in-process engine log is inconsistent"
            )


def _runtime_dependency_authority_sha256(value: object) -> str:
    authority = _mapping(value, name="Stage 0 runtime dependency authority")
    expected_fields = {
        "schema_id",
        "distribution_versions",
        "installed_distribution_file_ledger_sha256s",
        "authority_sha256",
    }
    versions = _mapping(
        authority.get("distribution_versions"),
        name="Stage 0 runtime dependency versions",
    )
    ledgers = _mapping(
        authority.get("installed_distribution_file_ledger_sha256s"),
        name="Stage 0 runtime dependency file ledgers",
    )
    expected_distributions = set(STAGE0_EVALUATOR_DISTRIBUTION_VERSIONS) | set(
        STAGE0_CORE_RUNTIME_DISTRIBUTIONS
    )
    projection = dict(authority)
    observed_sha256 = projection.pop("authority_sha256", None)
    if (
        set(authority) != expected_fields
        or authority.get("schema_id") != STAGE0_RUNTIME_DEPENDENCY_AUTHORITY_SCHEMA_ID
        or set(versions) != expected_distributions
        or set(ledgers) != expected_distributions
        or any(
            not isinstance(version, str) or not version for version in versions.values()
        )
        or any(not _is_sha256(digest) for digest in ledgers.values())
        or not _is_sha256(observed_sha256)
        or observed_sha256 != canonical_sha256(projection)
    ):
        raise FreshRunVerificationError(
            "Stage 0 runtime dependency authority is invalid"
        )
    return str(observed_sha256)


def _verify_prebound_runtime_authority(
    *,
    stage0_policy: Mapping[str, object],
    environment_receipt: Mapping[str, object],
    report: Mapping[str, object],
) -> None:
    source_freeze = _mapping(
        stage0_policy.get("source_freeze"),
        name="Stage 0 source freeze",
    )
    execution_profile = _mapping(
        source_freeze.get("execution_profile"),
        name="Stage 0 execution profile",
    )
    environment_freeze = _mapping(
        stage0_policy.get("environment_freeze"),
        name="Stage 0 environment freeze",
    )
    profile_authority = execution_profile.get("runtime_dependency_authority")
    frozen_authority = environment_freeze.get("runtime_dependency_authority")
    profile_authority_sha256 = _runtime_dependency_authority_sha256(profile_authority)
    frozen_authority_sha256 = _runtime_dependency_authority_sha256(frozen_authority)
    profile_evaluation_sha256 = execution_profile.get("evaluation_pipeline_sha256")
    frozen_evaluation_sha256 = environment_freeze.get("evaluation_pipeline_sha256")
    if (
        profile_authority != frozen_authority
        or profile_authority_sha256 != frozen_authority_sha256
        or not _is_sha256(profile_evaluation_sha256)
        or profile_evaluation_sha256 != frozen_evaluation_sha256
    ):
        raise FreshRunVerificationError(
            "Stage 0 runtime dependency or evaluation authority is cross-wired"
        )
    runtime_environment = _mapping(
        environment_receipt.get("environment"),
        name="Fresh execution environment",
    )
    if (
        runtime_environment.get("runtime_dependency_authority") != frozen_authority
        or runtime_environment.get("evaluation_pipeline_sha256")
        != frozen_evaluation_sha256
    ):
        raise FreshRunVerificationError(
            "Fresh runtime environment differs from Stage 0 authority"
        )
    identities = [
        _mapping(identity, name="Fresh engine identity")
        for identity in _sequence(
            report.get("engine_identities"),
            name="Fresh engine identities",
        )
    ]
    if not identities or any(
        identity.get("evaluation_pipeline_sha256") != frozen_evaluation_sha256
        for identity in identities
    ):
        raise FreshRunVerificationError(
            "Fresh report evaluation pipeline differs from Stage 0 authority"
        )


def _verify_environment_and_log_receipts(
    *,
    environment_receipt: Mapping[str, object],
    execution_log: Mapping[str, object],
    report: Mapping[str, object],
) -> None:
    environment_fields = {
        "schema_id",
        "runner_id",
        "environment",
        "execution_environment_sha256",
        "boot_session_id_available",
        "cache_read_allowed",
        "timed_cache_reusable",
        "result_values_included",
        "claim_safe",
        "receipt_sha256",
    }
    environment = _mapping(
        environment_receipt.get("environment"),
        name="Fresh execution environment",
    )
    if (
        set(environment_receipt) != environment_fields
        or environment_receipt.get("schema_id")
        != "betelgeuze.engine_v2_fresh_execution_environment_receipt/1.0.0"
        or environment_receipt.get("runner_id") != FRESH_RUNNER_ID
        or canonical_sha256(environment)
        != environment_receipt.get("execution_environment_sha256")
        or type(environment_receipt.get("boot_session_id_available")) is not bool
        or environment_receipt.get("cache_read_allowed") is not False
        or environment_receipt.get("timed_cache_reusable") is not False
        or environment_receipt.get("result_values_included") is not False
        or environment_receipt.get("claim_safe") is not False
    ):
        raise FreshRunVerificationError(
            "Fresh execution environment receipt is invalid"
        )
    _self_hash(
        environment_receipt,
        field="receipt_sha256",
        name="Fresh execution environment receipt",
    )

    receipts = [
        _mapping(value, name="Fresh execution receipt")
        for value in _sequence(
            report.get("execution_receipts"),
            name="Fresh execution receipts",
        )
    ]
    expected_entries: list[dict[str, object]] = []
    environment_sha256 = str(environment_receipt["execution_environment_sha256"])
    for receipt in receipts:
        result = _mapping(receipt.get("result"), name="Fresh execution result")
        if receipt.get("execution_environment_sha256") != environment_sha256:
            raise FreshRunVerificationError(
                "Fresh execution receipt environment is cross-wired"
            )
        expected_entries.append(
            {
                "engine_id": result.get("engine_id"),
                "case_id": result.get("case_id"),
                "status": result.get("status"),
                "failure_code": result.get("failure_code", ""),
                "execution_receipt_sha256": receipt.get("receipt_sha256"),
                "execution_environment_sha256": receipt.get(
                    "execution_environment_sha256"
                ),
            }
        )
    log_fields = {
        "schema_id",
        "runner_id",
        "execution_environment_sha256",
        "engine_case_row_count",
        "entries",
        "entries_sha256",
        "stdout_stderr_payload_retained",
        "structured_execution_receipts_are_authoritative",
        "result_replacement_allowed",
        "claim_safe",
        "receipt_sha256",
    }
    observed_entries = [
        _mapping(value, name="Fresh execution log entry")
        for value in _sequence(
            execution_log.get("entries"),
            name="Fresh execution log entries",
        )
    ]
    if len(observed_entries) != len(expected_entries):
        raise FreshRunVerificationError("Fresh execution log denominator is invalid")
    for observed, expected in zip(observed_entries, expected_entries, strict=True):
        if set(observed) != set(expected) | {"process_log"} or any(
            observed.get(name) != expected_value
            for name, expected_value in expected.items()
        ):
            raise FreshRunVerificationError("Fresh execution log row is cross-wired")
        _verify_process_log(
            observed.get("process_log"),
            engine_id=expected["engine_id"],
            failure_code=expected["failure_code"],
        )
    if (
        set(execution_log) != log_fields
        or execution_log.get("schema_id")
        != "betelgeuze.engine_v2_fresh_execution_log_receipt/1.0.0"
        or execution_log.get("runner_id") != FRESH_RUNNER_ID
        or execution_log.get("execution_environment_sha256") != environment_sha256
        or execution_log.get("engine_case_row_count") != FRESH_ENGINE_ROW_COUNT
        or execution_log.get("entries_sha256") != canonical_sha256(observed_entries)
        or execution_log.get("stdout_stderr_payload_retained") is not True
        or execution_log.get("structured_execution_receipts_are_authoritative")
        is not True
        or execution_log.get("result_replacement_allowed") is not False
        or execution_log.get("claim_safe") is not False
    ):
        raise FreshRunVerificationError("Fresh execution log receipt is invalid")
    _self_hash(
        execution_log,
        field="receipt_sha256",
        name="Fresh execution log receipt",
    )


def _verify_manifest_report_artifacts(
    *,
    root_descriptor: int,
    manifest: Mapping[str, object],
    reservation_artifact: _OwnedCanonicalJson,
    stage0_artifact: _OwnedCanonicalJson,
    policy_artifact: _OwnedCanonicalJson,
    environment_artifact: _OwnedCanonicalJson,
    execution_log_artifact: _OwnedCanonicalJson,
    report_artifact: _OwnedCanonicalJson,
) -> None:
    report = report_artifact.payload
    entries = _manifest_entry_map(manifest)
    expected_hashes = {
        FRESH_RESERVATION_FILENAME: hashlib.sha256(
            reservation_artifact.raw
        ).hexdigest(),
        FRESH_STAGE0_ADMISSION_RECEIPT_FILENAME: hashlib.sha256(
            stage0_artifact.raw
        ).hexdigest(),
        FRESH_STAGE0_POLICY_SNAPSHOT_FILENAME: hashlib.sha256(
            policy_artifact.raw
        ).hexdigest(),
        FRESH_EXECUTION_ENVIRONMENT_FILENAME: hashlib.sha256(
            environment_artifact.raw
        ).hexdigest(),
        FRESH_EXECUTION_LOG_FILENAME: hashlib.sha256(
            execution_log_artifact.raw
        ).hexdigest(),
        FRESH_REPORT_FILENAME: hashlib.sha256(report_artifact.raw).hexdigest(),
    }
    materializations = _sequence(
        report.get("materializations"),
        name="Fresh materializations",
    )
    for materialization in materializations:
        payload = _mapping(materialization, name="Fresh materialization")
        case_id = str(payload.get("case_id", ""))
        expected_hashes[f"receipts/materializations/{case_id}.json"] = (
            _canonical_file_sha256(payload)
        )

    receipts = _sequence(
        report.get("execution_receipts"),
        name="Fresh execution receipts",
    )
    rows = _sequence(report.get("rows"), name="Fresh rows")
    expected_pose_paths: dict[str, Mapping[str, object]] = {}
    for raw_receipt in receipts:
        receipt = _mapping(raw_receipt, name="Fresh execution receipt")
        result = _mapping(receipt.get("result"), name="Fresh execution result")
        engine_id = str(result.get("engine_id", ""))
        case_id = str(result.get("case_id", ""))
        expected_hashes[f"receipts/{engine_id}/{case_id}.json"] = (
            _canonical_file_sha256(receipt)
        )
    for raw_row in rows:
        row = _mapping(raw_row, name="Fresh row")
        if row.get("status") == "success":
            pose_path = f"poses/{row.get('engine_id')}/{row.get('case_id')}.sdf"
            expected_pose_paths[pose_path] = row

    gnina_entries = [
        (path, entry)
        for path, entry in entries.items()
        if entry.get("artifact_role") == "gnina_binary"
    ]
    identities = {
        str(
            _mapping(value, name="Fresh engine identity").get("engine_id", "")
        ): _mapping(value, name="Fresh engine identity")
        for value in _sequence(
            report.get("engine_identities"),
            name="Fresh engine identities",
        )
    }
    if (
        len(gnina_entries) != 1
        or set(identities) != set(PUBLIC_REDOCKING_PRIMARY_ENGINES)
        or identities["vina"].get("implementation_sha256")
        != gnina_entries[0][1].get("sha256")
        or identities["gnina"].get("implementation_sha256")
        != gnina_entries[0][1].get("sha256")
        or PurePosixPath(gnina_entries[0][0]).name != gnina_entries[0][1].get("sha256")
    ):
        raise FreshRunVerificationError(
            "retained GNINA binary is not bound to engine identities"
        )
    expected_paths = (
        set(expected_hashes) | set(expected_pose_paths) | {gnina_entries[0][0]}
    )
    if set(entries) != expected_paths:
        raise FreshRunVerificationError(
            "Fresh artifact manifest does not contain the exact report artifact set"
        )
    for relative_path, expected_sha256 in expected_hashes.items():
        if entries[relative_path].get("sha256") != expected_sha256:
            raise FreshRunVerificationError(
                "Fresh JSON artifact differs from its report ledger"
            )
    for relative_path, row in expected_pose_paths.items():
        raw = _read_manifest_artifact_at(
            root_descriptor,
            relative_path=relative_path,
            entry=entries[relative_path],
            maximum=64 * 1024 * 1024,
        )
        if list(_pose_record_sha256s(raw)) != row.get("pose_artifact_sha256s"):
            raise FreshRunVerificationError(
                "retained Fresh pose records differ from the row ledger"
            )


def verify_fresh_run_root(
    output_root: Path,
    *,
    repo_root: Path | None = None,
    source_repo_root: Path | None = None,
    stage0_policy_path: Path | None = None,
    gnina_path: Path | None = None,
    verified_stage0_receipt: VerifiedStage0Admission | None = None,
    proposed_completion_document: Mapping[str, object] | None = None,
) -> VerifiedFreshRun:
    """Verify a local run root, optionally anchored by a trusted Stage 0 policy.

    The in-process runner remains compatible by using its owner-only on-disk
    Stage 0 receipt.  External verification should pass ``stage0_policy_path``
    and ``gnina_path``; tests or an already-admitted caller may instead pass the
    typed ``verified_stage0_receipt``.  The local marker is never represented as
    proof of global exactly-once execution; even a retained signed reservation
    is a historical binding rather than a live global-ledger query.
    """

    if stage0_policy_path is not None and verified_stage0_receipt is not None:
        raise FreshRunVerificationError(
            "provide either a Stage 0 policy or a verified Stage 0 receipt"
        )
    if stage0_policy_path is not None and gnina_path is None:
        raise FreshRunVerificationError(
            "Stage 0 policy verification requires the exact GNINA binary"
        )
    if verified_stage0_receipt is not None and type(verified_stage0_receipt) is not (
        VerifiedStage0Admission
    ):
        raise FreshRunVerificationError("verified Stage 0 receipt is not typed")

    active_repo_root = Path(
        os.path.abspath(
            os.fspath(_DEFAULT_REPO_ROOT if repo_root is None else repo_root)
        )
    )
    root = Path(os.path.abspath(os.fspath(output_root)))
    try:
        relative_root = root.relative_to(active_repo_root).as_posix()
    except ValueError as exc:
        raise FreshRunVerificationError(
            "Fresh-128 output root escapes the repository"
        ) from exc
    if relative_root != STAGE0_CANONICAL_FRESH_RETENTION_ROOT:
        raise FreshRunVerificationError(
            "Fresh-128 output root is not the canonical fixed retention root"
        )

    repo_descriptor = _directory_descriptor(active_repo_root)
    try:
        _require_owned_directory(repo_descriptor, name="repository root")
    finally:
        os.close(repo_descriptor)
    root_descriptor = _directory_descriptor(root)
    try:
        root_status = _require_owned_directory(
            root_descriptor,
            name="Fresh-128 output root",
            exact_mode=0o700,
        )
        _require_path_identity(root, root_status)
        reservation_artifact = _read_owned_canonical_json_at(
            root_descriptor,
            FRESH_RESERVATION_FILENAME,
            maximum=_MAX_RECEIPT_BYTES,
        )
        reservation = reservation_artifact.payload
        reservation_sha256 = verify_reservation_document(reservation)
        if reservation.get("retention_root") != relative_root:
            raise FreshRunVerificationError(
                "Fresh-128 reservation retention root is cross-wired"
            )

        stage0_artifact = _read_owned_canonical_json_at(
            root_descriptor,
            FRESH_STAGE0_ADMISSION_RECEIPT_FILENAME,
            maximum=_MAX_RECEIPT_BYTES,
        )
        policy_artifact = _read_owned_canonical_json_at(
            root_descriptor,
            FRESH_STAGE0_POLICY_SNAPSHOT_FILENAME,
            maximum=_MAX_RECEIPT_BYTES,
        )
        try:
            observed_policy_sha256 = compute_stage0_policy_sha256(
                policy_artifact.payload
            )
        except (TypeError, ValueError) as exc:
            raise FreshRunVerificationError(
                "retained Stage 0 policy snapshot is invalid"
            ) from exc
        if policy_artifact.payload.get(
            "policy_sha256"
        ) != observed_policy_sha256 or observed_policy_sha256 != reservation.get(
            "stage0_policy_sha256"
        ):
            raise FreshRunVerificationError(
                "retained Stage 0 policy snapshot is cross-wired"
            )
        environment_artifact = _read_owned_canonical_json_at(
            root_descriptor,
            FRESH_EXECUTION_ENVIRONMENT_FILENAME,
            maximum=_MAX_RECEIPT_BYTES,
        )
        execution_log_artifact = _read_owned_canonical_json_at(
            root_descriptor,
            FRESH_EXECUTION_LOG_FILENAME,
            maximum=_MAX_REPORT_BYTES,
        )
        report_artifact = _read_owned_canonical_json_at(
            root_descriptor,
            FRESH_REPORT_FILENAME,
            maximum=_MAX_REPORT_BYTES,
        )
        report = report_artifact.payload
        report_fingerprint = verify_fresh_report_document(
            report,
            reservation_sha256=reservation_sha256,
            repo_root=active_repo_root,
            source_repo_root=source_repo_root,
            expected_output_root=root,
        )
        admission = _mapping(
            report.get("stage0_admission"), name="Stage 0 admission binding"
        )
        if (
            reservation.get("fresh_holdout_manifest_sha256")
            != report.get("fresh_holdout_manifest_sha256")
            or reservation.get("stage0_policy_sha256") != admission.get("policy_sha256")
            or reservation.get("source_freeze_sha256")
            != admission.get("source_freeze_sha256")
            or reservation.get("execution_profile_sha256")
            != admission.get("execution_profile_sha256")
            or reservation.get("external_run_once_authority_id")
            != admission.get("external_run_once_authority_id")
            or reservation.get("external_run_once_reservation_sha256")
            != admission.get("external_run_once_reservation_sha256")
            or reservation.get("fresh_run_identity_sha256")
            != admission.get("fresh_run_identity_sha256")
            or reservation.get("docking_pipeline_profile_id")
            != admission.get("docking_pipeline_profile_id")
            or reservation.get("docking_pipeline_profile_sha256")
            != admission.get("docking_pipeline_profile_sha256")
        ):
            raise FreshRunVerificationError(
                "Fresh-128 reservation and report identities are cross-wired"
            )
        _verify_prebound_runtime_authority(
            stage0_policy=policy_artifact.payload,
            environment_receipt=environment_artifact.payload,
            report=report,
        )
        _verify_environment_and_log_receipts(
            environment_receipt=environment_artifact.payload,
            execution_log=execution_log_artifact.payload,
            report=report,
        )

        trusted_receipt = verified_stage0_receipt
        stage0_binding_authority = "on_disk_stage0_admission_receipt"
        stage0_policy_verified = False
        if stage0_policy_path is not None:
            try:
                trusted_receipt = verify_stage0_admission(
                    Path(stage0_policy_path),
                    repo_root=active_repo_root,
                    gnina_path=Path(gnina_path),
                    output_root=root,
                )
            except (OSError, TypeError, ValueError) as exc:
                raise FreshRunVerificationError(
                    "Stage 0 policy failed post-run verification"
                ) from exc
            stage0_binding_authority = "verified_stage0_policy"
            stage0_policy_verified = True
        elif trusted_receipt is not None:
            stage0_binding_authority = "verified_stage0_receipt"
            stage0_policy_verified = True
        _verify_stage0_disk_receipt(
            stage0_artifact.payload,
            admission=admission,
            reservation=reservation,
            trusted=trusted_receipt,
        )

        report_file_sha256 = hashlib.sha256(report_artifact.raw).hexdigest()
        manifest_artifact = _read_owned_canonical_json_at(
            root_descriptor,
            FRESH_ARTIFACT_MANIFEST_FILENAME,
            maximum=_MAX_REPORT_BYTES,
        )
        try:
            artifact_manifest_sha256 = verify_fresh_artifact_manifest_document(
                manifest_artifact.payload
            )
            verify_fresh_artifact_set(
                output_root=root,
                manifest=manifest_artifact.payload,
                completion_filename=FRESH_COMPLETION_FILENAME,
            )
        except FreshArtifactManifestError as exc:
            raise FreshRunVerificationError(
                "Fresh artifact manifest or retained set is invalid"
            ) from exc
        manifest = manifest_artifact.payload
        if (
            manifest.get("runner_id") != FRESH_RUNNER_ID
            or manifest.get("retention_root") != relative_root
            or manifest.get("reservation_sha256") != reservation_sha256
            or manifest.get("report_fingerprint_sha256") != report_fingerprint
            or manifest.get("report_file_sha256") != report_file_sha256
            or manifest.get("stage0_policy_sha256")
            != reservation.get("stage0_policy_sha256")
            or manifest.get("source_freeze_sha256")
            != reservation.get("source_freeze_sha256")
            or manifest.get("execution_profile_sha256")
            != reservation.get("execution_profile_sha256")
            or manifest.get("fresh_holdout_manifest_sha256")
            != reservation.get("fresh_holdout_manifest_sha256")
        ):
            raise FreshRunVerificationError(
                "Fresh artifact manifest bindings are cross-wired"
            )
        _verify_manifest_report_artifacts(
            root_descriptor=root_descriptor,
            manifest=manifest,
            reservation_artifact=reservation_artifact,
            stage0_artifact=stage0_artifact,
            policy_artifact=policy_artifact,
            environment_artifact=environment_artifact,
            execution_log_artifact=execution_log_artifact,
            report_artifact=report_artifact,
        )
        artifact_manifest_file_sha256 = hashlib.sha256(
            manifest_artifact.raw
        ).hexdigest()
        if proposed_completion_document is None:
            completion = _read_owned_canonical_json_at(
                root_descriptor,
                FRESH_COMPLETION_FILENAME,
                maximum=_MAX_RECEIPT_BYTES,
            ).payload
        else:
            try:
                os.stat(
                    FRESH_COMPLETION_FILENAME,
                    dir_fd=root_descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                pass
            else:
                raise FreshRunVerificationError(
                    "Fresh completion is already published before preverification"
                )
            completion = _mapping(
                proposed_completion_document,
                name="proposed Fresh completion",
            )
        completion_sha256 = verify_completion_document(
            completion,
            reservation_sha256=reservation_sha256,
            report_fingerprint_sha256=report_fingerprint,
            report_file_sha256=report_file_sha256,
            artifact_manifest_sha256=artifact_manifest_sha256,
            artifact_manifest_file_sha256=artifact_manifest_file_sha256,
        )
        if int(completion["completed_at_unix_ns"]) < int(
            reservation["reserved_at_unix_ns"]
        ):
            raise FreshRunVerificationError(
                "Fresh-128 completion predates its reservation"
            )
        _require_path_identity(root, root_status)
    finally:
        os.close(root_descriptor)
    return VerifiedFreshRun._from_verified_root(
        reservation_sha256=reservation_sha256,
        report_fingerprint_sha256=report_fingerprint,
        report_file_sha256=report_file_sha256,
        artifact_manifest_sha256=artifact_manifest_sha256,
        artifact_manifest_file_sha256=artifact_manifest_file_sha256,
        completion_sha256=completion_sha256,
        stage0_admission_receipt_sha256=str(
            stage0_artifact.payload.get("receipt_sha256", "")
        ),
        external_run_once_reservation_sha256=str(
            reservation.get("external_run_once_reservation_sha256", "")
        ),
        fresh_run_identity_sha256=str(reservation.get("fresh_run_identity_sha256", "")),
        docking_pipeline_profile_id=str(
            reservation.get("docking_pipeline_profile_id", "")
        ),
        docking_pipeline_profile_sha256=str(
            reservation.get("docking_pipeline_profile_sha256", "")
        ),
        stage0_binding_authority=stage0_binding_authority,
        stage0_policy_verified=stage0_policy_verified,
        external_worm_reservation_cryptographically_verified=(stage0_policy_verified),
        exactly_once_verified=False,
        verification_authority=_VERIFIED_FRESH_RUN_AUTHORITY,
    )


__all__ = [
    "FRESH_CANDIDATE_SLOT_SCHEMA_ID",
    "FRESH_CASE_COUNT",
    "FRESH_COMPLETION_FILENAME",
    "FRESH_FAILURE_FILENAME",
    "FRESH_ENGINE_ROW_COUNT",
    "FRESH_ENGINE_V2_SLOT_COUNT",
    "FRESH_INTERNAL_REPORT_SCHEMA_ID",
    "FRESH_REPORT_FILENAME",
    "FRESH_RESERVATION_FILENAME",
    "FRESH_RUNNER_ID",
    "FRESH_RUN_ONCE_COMPLETION_SCHEMA_ID",
    "FRESH_RUN_ONCE_RESERVATION_SCHEMA_ID",
    "FRESH_RUN_TERMINAL_FAILURE_SCHEMA_ID",
    "FRESH_STAGE0_ADMISSION_RECEIPT_FILENAME",
    "FRESH_VERIFIED_RUN_SCHEMA_ID",
    "FreshRedockingCaseProfile",
    "FreshRedockingCaseResult",
    "FreshRunVerificationError",
    "VerifiedFreshRun",
    "build_candidate_slot_ledger",
    "canonical_bytes",
    "canonical_sha256",
    "derive_fresh_subgroup_results",
    "fresh_engine_v2_execution_command",
    "require_fresh_run_product_shadow_activation",
    "verify_candidate_slot_ledger",
    "verify_completion_document",
    "verify_fresh_report_document",
    "verify_fresh_run_root",
    "verify_reservation_document",
    "verify_terminal_failure_document",
]
