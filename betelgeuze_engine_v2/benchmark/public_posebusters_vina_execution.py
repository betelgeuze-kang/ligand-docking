"""Failure-inclusive AutoDock Vina execution for strict PoseBusters inputs.

The runner consumes an exact, caller-pinned external-preparation receipt and its
private PDBQT tree.  It executes Vina only for prepared rows, while preserving
preparation failures and chemistry abstentions in the 308-case denominator.
Generated PDBQT poses and Vina energy components are retained, but pose validity,
symmetry-aware RMSD, ranking calibration, and benchmark claims remain separate
gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from typing import Any, Callable, Protocol, Sequence

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _positive_int,
    _source_file_sha256,
    _token,
)
from .public_posebusters_external_preparation import (
    POSEBUSTERS_EXTERNAL_PREPARATION_ARTIFACT_SCHEMA_ID,
    POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256,
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
    POSEBUSTERS_EXTERNAL_PREPARATION_MAX_RECEIPT_BYTES,
    POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID,
    PoseBustersExternalPreparationDependency,
    PoseBustersExternalPreparationError,
    PoseBustersExternalPreparationRuntime,
    _dependency_payload,
    _require_import_owned_by_distribution,
    _runtime_identity,
    _verify_artifact_tree,
    _write_artifact_tree,
)
from .public_posebusters_intake import _read_exact_regular_file


POSEBUSTERS_VINA_EXECUTION_ARTIFACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_vina_execution_artifact/1.0.0"
)
POSEBUSTERS_VINA_EXECUTION_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_vina_execution_case/1.0.0"
)
POSEBUSTERS_VINA_EXECUTION_ENGINE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_vina_execution_engine/1.0.0"
)
POSEBUSTERS_VINA_EXECUTION_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_vina_execution_metric/1.0.0"
)
POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_vina_execution/1.0.0"
)
POSEBUSTERS_VINA_EXECUTION_MAX_RECEIPT_BYTES = 8 * 1024 * 1024
POSEBUSTERS_VINA_EXECUTION_MAX_POSE_ARTIFACT_BYTES = 32 * 1024 * 1024
POSEBUSTERS_VINA_EXECUTION_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_VINA_EXECUTION_Z = 1.959963984540054
POSEBUSTERS_VINA_VERSION = "1.2.7"
POSEBUSTERS_VINA_EXECUTION_CONFIGURATION = {
    "box_size_angstrom": [22.5, 22.5, 22.5],
    "cpu_count": 1,
    "energy_range_kcal_per_mol": 20.0,
    "exhaustiveness": 32,
    "force_even_voxels": False,
    "max_evals": 0,
    "min_rmsd_angstrom": 1.0,
    "no_refine": False,
    "num_modes": 20,
    "scoring_function": "vina",
    "seed": 20260723,
    "spacing_angstrom": 0.375,
    "verbosity": 0,
}
POSEBUSTERS_VINA_EXECUTION_CONFIGURATION_SHA256 = (
    "bbe44bef15f8620ae33e6358a7206382505c9faa338f36c4b662708cd0abacfb"
)
POSEBUSTERS_VINA_EXECUTION_BLOCKERS = (
    "only_strictly_prepared_chemistry_subset_executed",
    "prepared_ad4_types_and_gasteiger_charges_not_independently_validated",
    "generated_pose_validity_not_evaluated",
    "symmetry_aware_rmsd_not_evaluated",
    "gnina_and_smina_same_input_results_missing",
    "target_family_and_leakage_receipts_missing",
    "independent_external_rerun_missing",
    "scientific_review_missing",
)

_CASE_STATUSES = {
    "success",
    "engine_failure",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "abstain_chemistry_scope",
}
_PREPARATION_STATUSES = {
    "prepared",
    "preparation_failure",
    "upstream_failure",
    "abstain_chemistry_scope",
}
_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_ENERGY_COMPONENTS = (
    "total",
    "inter",
    "intra",
    "torsions",
    "intra_best_pose",
)


class PoseBustersVinaExecutionError(ValueError):
    """Vina execution input, runtime, artifact, or receipt is invalid."""


class PoseBustersVinaCaseExecutionError(RuntimeError):
    """One attempted Vina case failed with a bounded disposition."""

    def __init__(
        self,
        *,
        stage: str,
        error_code: str,
        error_type: str,
        error_message_sha256: str,
        diagnostic_sha256: str,
        diagnostic_size_bytes: int,
    ) -> None:
        super().__init__(error_code)
        self.stage = _token(stage, name="Vina failure stage")
        self.error_code = _token(error_code, name="Vina error code")
        self.error_type = _identifier(error_type, name="Vina error type")
        self.error_message_sha256 = _digest(
            error_message_sha256,
            name="Vina error message",
        )
        self.diagnostic_sha256 = _digest(
            diagnostic_sha256,
            name="Vina diagnostic",
        )
        self.diagnostic_size_bytes = _positive_int(
            diagnostic_size_bytes,
            name="Vina diagnostic size",
            allow_zero=True,
        )


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise PoseBustersVinaExecutionError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _case_id(value: object) -> str:
    if not isinstance(value, str):
        raise PoseBustersVinaExecutionError("case ID must be text")
    result = value.strip()
    parts = result.split("_")
    if (
        len(parts) != 2
        or len(parts[0]) != 4
        or len(parts[1]) != 3
        or not all(
            part.isascii() and part.isalnum() and part.upper() == part
            for part in parts
        )
    ):
        raise PoseBustersVinaExecutionError(
            "case ID must use uppercase PDB4_CCD3 form"
        )
    return result


def _identifier(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PoseBustersVinaExecutionError(f"{name} must be non-empty text")
    if (
        not value.isascii()
        or not (value[0].isalpha() or value[0] == "_")
        or any(not (character.isalnum() or character == "_") for character in value)
    ):
        raise PoseBustersVinaExecutionError(f"{name} must be an identifier")
    return value


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _finite_hex(value: float, *, name: str) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise PoseBustersVinaExecutionError(f"{name} must be finite")
    return number.hex()


def _validate_hex(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PoseBustersVinaExecutionError(
            f"{name} must be hexadecimal binary64"
        )
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise PoseBustersVinaExecutionError(
            f"{name} must be hexadecimal binary64"
        ) from exc
    if not math.isfinite(number) or number.hex() != value:
        raise PoseBustersVinaExecutionError(
            f"{name} must be canonical finite binary64"
        )
    return value


def _relative_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PoseBustersVinaExecutionError(
            "Vina artifact path must be non-empty text"
        )
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise PoseBustersVinaExecutionError(
            "Vina artifact path must remain below artifact root"
        )
    return path.as_posix()


def _normalize_error(error: BaseException) -> bytes:
    return (
        str(error)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
        .encode("utf-8", errors="backslashreplace")
    )


class _DigestingTextSink:
    def __init__(self) -> None:
        self._digest = hashlib.sha256()
        self.size_bytes = 0

    def write(self, value: str) -> int:
        if not isinstance(value, str):
            raise TypeError("diagnostic sink accepts text")
        source = value.encode("utf-8", errors="backslashreplace")
        self._digest.update(source)
        self.size_bytes += len(source)
        return len(value)

    def flush(self) -> None:
        return None

    @property
    def sha256(self) -> str:
        return self._digest.hexdigest()


@dataclass(frozen=True, slots=True)
class _PreparedArtifactView:
    role: str
    relative_path: str
    sha256: str
    size_bytes: int
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _PreparedCaseView:
    case_id: str
    status: str
    disposition_code: str
    pocket_center_binary64_hex: tuple[str, ...]
    artifacts: tuple[_PreparedArtifactView, ...]
    error_code: str


@dataclass(frozen=True, slots=True)
class _PreparationReceiptView:
    receipt_sha256: str
    receipt_file_sha256: str
    artifact_set_sha256: str
    runtime_identity: dict[str, Any]
    runtime_identity_sha256: str
    case_rows: tuple[_PreparedCaseView, ...]


def _load_preparation_receipt(
    receipt_path: str | os.PathLike[str],
    artifact_root: str | os.PathLike[str],
    *,
    expected_receipt_sha256: str,
) -> tuple[_PreparationReceiptView, dict[str, bytes]]:
    expected_sha = _digest(
        expected_receipt_sha256,
        name="expected preparation receipt",
    )
    source = _read_exact_regular_file(
        receipt_path,
        maximum_bytes=POSEBUSTERS_EXTERNAL_PREPARATION_MAX_RECEIPT_BYTES,
    )
    try:
        metadata = Path(receipt_path).stat(follow_symlinks=False)
    except OSError as exc:
        raise PoseBustersVinaExecutionError(
            "preparation receipt metadata is unavailable"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersVinaExecutionError(
            "preparation receipt must remain mode 0600"
        )
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersVinaExecutionError(
            "preparation receipt is not canonical JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersVinaExecutionError(
            "preparation receipt bytes are not canonical"
        )
    receipt_sha = raw.get("receipt_sha256")
    if not isinstance(receipt_sha, str):
        raise PoseBustersVinaExecutionError(
            "preparation receipt fingerprint is missing"
        )
    payload = dict(raw)
    payload.pop("receipt_sha256", None)
    if (
        raw.get("schema_id") != POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID
        or _canonical_sha256(payload) != receipt_sha
        or receipt_sha != expected_sha
        or raw.get("configuration_sha256")
        != POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256
        or raw.get("strict_bad_residue_deletion_allowed") is not False
        or raw.get("native_reference_used_for_ligand_preparation") is not False
        or raw.get("external_engine_executed") is not False
        or raw.get("benchmark_executed") is not False
        or raw.get("claim_safe") is not False
    ):
        raise PoseBustersVinaExecutionError(
            "preparation receipt contract or fingerprint is invalid"
        )
    runtime_identity = raw.get("runtime_identity")
    runtime_sha = raw.get("runtime_identity_sha256")
    if (
        not isinstance(runtime_identity, dict)
        or not isinstance(runtime_sha, str)
        or _canonical_sha256(runtime_identity) != runtime_sha
    ):
        raise PoseBustersVinaExecutionError(
            "preparation runtime identity is invalid"
        )
    source_members = raw.get("implementation_source_members")
    source_sha = raw.get("implementation_source_sha256")
    current_preparation_source_sha = _source_file_sha256(
        Path(__file__).with_name("public_posebusters_external_preparation.py")
    )
    if (
        not isinstance(source_members, dict)
        or not isinstance(source_sha, str)
        or _canonical_sha256(source_members) != source_sha
        or source_members.get("external_preparation")
        != current_preparation_source_sha
    ):
        raise PoseBustersVinaExecutionError(
            "preparation implementation-source identity is invalid"
        )
    raw_rows = raw.get("case_rows")
    if (
        not isinstance(raw_rows, list)
        or raw.get("all_case_denominator") != len(raw_rows)
        or not raw_rows
    ):
        raise PoseBustersVinaExecutionError(
            "preparation receipt case denominator is invalid"
        )
    rows: list[_PreparedCaseView] = []
    artifact_projection: dict[str, dict[str, Any]] = {}
    payloads: dict[str, bytes] = {}
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            raise PoseBustersVinaExecutionError(
                "preparation case row must be an object"
            )
        case_id = _case_id(raw_row.get("case_id"))
        status = str(raw_row.get("status", ""))
        if status not in _PREPARATION_STATUSES:
            raise PoseBustersVinaExecutionError(
                "preparation case status is invalid"
            )
        disposition = _token(
            raw_row.get("disposition_code"),
            name="preparation disposition",
        )
        raw_center = raw_row.get("pocket_center_binary64_hex")
        if not isinstance(raw_center, list):
            raise PoseBustersVinaExecutionError(
                "preparation pocket center is invalid"
            )
        center = tuple(
            _validate_hex(value, name="preparation pocket center")
            for value in raw_center
        )
        raw_artifacts = raw_row.get("artifacts")
        if not isinstance(raw_artifacts, list):
            raise PoseBustersVinaExecutionError(
                "preparation artifact rows are invalid"
            )
        artifacts: list[_PreparedArtifactView] = []
        for raw_artifact in raw_artifacts:
            if (
                not isinstance(raw_artifact, dict)
                or raw_artifact.get("schema_id")
                != POSEBUSTERS_EXTERNAL_PREPARATION_ARTIFACT_SCHEMA_ID
            ):
                raise PoseBustersVinaExecutionError(
                    "preparation artifact schema is invalid"
                )
            role = str(raw_artifact.get("role", ""))
            if role not in {
                "prepared_ligand_pdbqt",
                "prepared_receptor_pdbqt",
            }:
                raise PoseBustersVinaExecutionError(
                    "preparation artifact role is invalid"
                )
            relative_path = _relative_path(raw_artifact.get("relative_path"))
            if PurePosixPath(relative_path).parts[0] != case_id:
                raise PoseBustersVinaExecutionError(
                    "preparation artifact path is cross-wired"
                )
            digest = _digest(
                raw_artifact.get("sha256"),
                name="prepared artifact",
            )
            size = _positive_int(
                raw_artifact.get("size_bytes"),
                name="prepared artifact size",
            )
            if size > POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES:
                raise PoseBustersVinaExecutionError(
                    "prepared artifact exceeds its size bound"
                )
            artifact = _PreparedArtifactView(
                role=role,
                relative_path=relative_path,
                sha256=digest,
                size_bytes=size,
                raw=dict(raw_artifact),
            )
            artifacts.append(artifact)
            key = f"{case_id}/{role}"
            if key in artifact_projection or relative_path in payloads:
                raise PoseBustersVinaExecutionError(
                    "prepared artifact identity is duplicated"
                )
            artifact_projection[key] = dict(raw_artifact)
            observed = _read_exact_regular_file(
                Path(artifact_root) / relative_path,
                maximum_bytes=POSEBUSTERS_EXTERNAL_PREPARATION_MAX_ARTIFACT_BYTES,
            )
            if len(observed) != size or _hash_bytes(observed) != digest:
                raise PoseBustersVinaExecutionError(
                    "prepared artifact does not match its receipt"
                )
            payloads[relative_path] = observed
        artifacts_tuple = tuple(sorted(artifacts, key=lambda row: row.role))
        if status == "prepared":
            if (
                len(center) != 3
                or tuple(row.role for row in artifacts_tuple)
                != ("prepared_ligand_pdbqt", "prepared_receptor_pdbqt")
            ):
                raise PoseBustersVinaExecutionError(
                    "prepared case does not contain an exact input pair"
                )
        elif status == "preparation_failure":
            if len(center) != 3 or artifacts_tuple:
                raise PoseBustersVinaExecutionError(
                    "preparation failure does not retain only its pocket center"
                )
        elif center or artifacts_tuple:
            raise PoseBustersVinaExecutionError(
                "non-attempted case contains executable inputs"
            )
        raw_error_code = raw_row.get("error_code")
        if not isinstance(raw_error_code, str):
            raise PoseBustersVinaExecutionError(
                "preparation error code must be text"
            )
        if status.endswith("failure"):
            error_code = _token(
                raw_error_code,
                name="preparation error code",
            )
        elif raw_error_code:
            raise PoseBustersVinaExecutionError(
                "successful or abstained preparation row contains an error"
            )
        else:
            error_code = ""
        rows.append(
            _PreparedCaseView(
                case_id=case_id,
                status=status,
                disposition_code=disposition,
                pocket_center_binary64_hex=center,
                artifacts=artifacts_tuple,
                error_code=error_code,
            )
        )
    rows_tuple = tuple(rows)
    if (
        tuple(row.case_id for row in rows_tuple)
        != tuple(sorted(row.case_id for row in rows_tuple))
        or len({row.case_id for row in rows_tuple}) != len(rows_tuple)
        or raw.get("attempted_case_count")
        != sum(
            row.status in {"prepared", "preparation_failure"}
            for row in rows_tuple
        )
        or raw.get("prepared_case_count")
        != sum(row.status == "prepared" for row in rows_tuple)
        or raw.get("failed_case_count")
        != sum(row.status.endswith("failure") for row in rows_tuple)
        or raw.get("abstained_case_count")
        != sum(row.status == "abstain_chemistry_scope" for row in rows_tuple)
        or _canonical_sha256(artifact_projection)
        != raw.get("artifact_set_sha256")
    ):
        raise PoseBustersVinaExecutionError(
            "preparation rows or artifact-set identity are inconsistent"
        )
    try:
        _verify_artifact_tree(Path(artifact_root), payloads)
    except PoseBustersExternalPreparationError as exc:
        raise PoseBustersVinaExecutionError(
            "prepared artifact tree failed exact verification"
        ) from exc
    return (
        _PreparationReceiptView(
            receipt_sha256=receipt_sha,
            receipt_file_sha256=_hash_bytes(source),
            artifact_set_sha256=_digest(
                raw.get("artifact_set_sha256"),
                name="preparation artifact set",
            ),
            runtime_identity=runtime_identity,
            runtime_identity_sha256=_digest(
                runtime_sha,
                name="preparation runtime identity",
            ),
            case_rows=rows_tuple,
        ),
        payloads,
    )


@dataclass(frozen=True, slots=True)
class PoseBustersVinaEngineIdentity:
    preparation_runtime: PoseBustersExternalPreparationRuntime
    vina_dependency: PoseBustersExternalPreparationDependency
    vina_api_source_sha256: str
    schema_id: str = POSEBUSTERS_VINA_EXECUTION_ENGINE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_VINA_EXECUTION_ENGINE_SCHEMA_ID:
            raise PoseBustersVinaExecutionError(
                "unsupported Vina engine identity schema"
            )
        if not isinstance(
            self.preparation_runtime,
            PoseBustersExternalPreparationRuntime,
        ):
            raise PoseBustersVinaExecutionError(
                "Vina engine identity requires the preparation runtime"
            )
        if (
            not isinstance(
                self.vina_dependency,
                PoseBustersExternalPreparationDependency,
            )
            or self.vina_dependency.distribution_name != "vina"
            or self.vina_dependency.version != POSEBUSTERS_VINA_VERSION
        ):
            raise PoseBustersVinaExecutionError(
                "Vina distribution identity is invalid"
            )
        object.__setattr__(
            self,
            "vina_api_source_sha256",
            _digest(self.vina_api_source_sha256, name="Vina Python API source"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "preparation_runtime": self.preparation_runtime.to_dict(),
            "preparation_runtime_identity_sha256": (
                self.preparation_runtime.fingerprint_sha256
            ),
            "vina_distribution": self.vina_dependency.to_dict(),
            "vina_api_source_sha256": self.vina_api_source_sha256,
            "engine_id": "vina",
            "engine_version": POSEBUSTERS_VINA_VERSION,
            "engine_payload_includes_native_wrapper_and_shared_libraries": True,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PoseBustersVinaExecutionBytes:
    poses_pdbqt: bytes
    energies_binary64_hex: tuple[tuple[str, ...], ...]
    diagnostic_sha256: str
    diagnostic_size_bytes: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.poses_pdbqt, bytes)
            or not self.poses_pdbqt
            or len(self.poses_pdbqt)
            > POSEBUSTERS_VINA_EXECUTION_MAX_POSE_ARTIFACT_BYTES
            or b"\x00" in self.poses_pdbqt
        ):
            raise PoseBustersVinaExecutionError(
                "Vina poses must be bounded non-empty PDBQT bytes"
            )
        energies = tuple(
            tuple(_validate_hex(value, name="Vina energy") for value in row)
            for row in self.energies_binary64_hex
        )
        if (
            not energies
            or len(energies) > POSEBUSTERS_VINA_EXECUTION_CONFIGURATION["num_modes"]
            or any(len(row) != len(_ENERGY_COMPONENTS) for row in energies)
            or any(
                float.fromhex(energies[index][0])
                > float.fromhex(energies[index + 1][0])
                for index in range(len(energies) - 1)
            )
        ):
            raise PoseBustersVinaExecutionError(
                "Vina energy table is invalid"
            )
        try:
            text = self.poses_pdbqt.decode("ascii")
        except UnicodeDecodeError as exc:
            raise PoseBustersVinaExecutionError(
                "Vina pose artifact must be ASCII PDBQT"
            ) from exc
        model_count = sum(line.startswith("MODEL") for line in text.splitlines())
        end_count = sum(line.startswith("ENDMDL") for line in text.splitlines())
        if model_count != len(energies) or end_count != model_count:
            raise PoseBustersVinaExecutionError(
                "Vina pose models and energy rows disagree"
            )
        object.__setattr__(self, "energies_binary64_hex", energies)
        object.__setattr__(
            self,
            "diagnostic_sha256",
            _digest(self.diagnostic_sha256, name="Vina diagnostic"),
        )
        object.__setattr__(
            self,
            "diagnostic_size_bytes",
            _positive_int(
                self.diagnostic_size_bytes,
                name="Vina diagnostic size",
                allow_zero=True,
            ),
        )


class _VinaRuntimeProtocol(Protocol):
    identity: PoseBustersVinaEngineIdentity

    def execute(
        self,
        receptor_pdbqt: bytes,
        ligand_pdbqt: bytes,
        pocket_center_binary64_hex: Sequence[str],
    ) -> PoseBustersVinaExecutionBytes: ...


def _private_scratch_root(path: Path) -> Path:
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        metadata = path.lstat()
    except OSError as exc:
        raise PoseBustersVinaExecutionError(
            "Vina scratch root is unavailable"
        ) from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise PoseBustersVinaExecutionError(
            "Vina scratch root must be a private real directory"
        )
    return path


class _VinaRuntime:
    def __init__(self, *, Vina: Any, identity: PoseBustersVinaEngineIdentity, scratch_root: Path) -> None:
        self._Vina = Vina
        self.identity = identity
        self._scratch_root = _private_scratch_root(scratch_root)

    def execute(
        self,
        receptor_pdbqt: bytes,
        ligand_pdbqt: bytes,
        pocket_center_binary64_hex: Sequence[str],
    ) -> PoseBustersVinaExecutionBytes:
        center = [
            float.fromhex(_validate_hex(value, name="Vina pocket center"))
            for value in pocket_center_binary64_hex
        ]
        if len(center) != 3:
            raise PoseBustersVinaExecutionError(
                "Vina pocket center must have three values"
            )
        sink = _DigestingTextSink()
        try:
            ligand_text = ligand_pdbqt.decode("ascii")
        except UnicodeDecodeError as exc:
            raise PoseBustersVinaCaseExecutionError(
                stage="ligand_decode",
                error_code="vina_ligand_ascii_decode_failed",
                error_type=type(exc).__name__,
                error_message_sha256=_hash_bytes(_normalize_error(exc)),
                diagnostic_sha256=sink.sha256,
                diagnostic_size_bytes=sink.size_bytes,
            ) from exc
        try:
            with tempfile.TemporaryDirectory(
                prefix="vina-case-",
                dir=self._scratch_root,
            ) as temporary:
                receptor_path = Path(temporary) / "receptor.pdbqt"
                descriptor = os.open(
                    receptor_path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                    0o600,
                )
                try:
                    observed = 0
                    while observed < len(receptor_pdbqt):
                        written = os.write(descriptor, receptor_pdbqt[observed:])
                        if written < 1:
                            raise RuntimeError("Vina receptor staging made no progress")
                        observed += written
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                    engine = self._Vina(
                        sf_name=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                            "scoring_function"
                        ],
                        cpu=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION["cpu_count"],
                        seed=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION["seed"],
                        no_refine=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                            "no_refine"
                        ],
                        verbosity=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                            "verbosity"
                        ],
                    )
                    engine.set_receptor(str(receptor_path))
                    engine.set_ligand_from_string(ligand_text)
                    engine.compute_vina_maps(
                        center=center,
                        box_size=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                            "box_size_angstrom"
                        ],
                        spacing=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                            "spacing_angstrom"
                        ],
                        force_even_voxels=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                            "force_even_voxels"
                        ],
                    )
                    engine.dock(
                        exhaustiveness=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                            "exhaustiveness"
                        ],
                        n_poses=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                            "num_modes"
                        ],
                        min_rmsd=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                            "min_rmsd_angstrom"
                        ],
                        max_evals=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                            "max_evals"
                        ],
                    )
                    poses = engine.poses(
                        n_poses=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                            "num_modes"
                        ],
                        energy_range=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                            "energy_range_kcal_per_mol"
                        ],
                        coordinates_only=False,
                    )
                    energies = engine.energies(
                        n_poses=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                            "num_modes"
                        ],
                        energy_range=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION[
                            "energy_range_kcal_per_mol"
                        ],
                    )
                if not isinstance(poses, str):
                    raise TypeError("Vina poses API did not return PDBQT text")
                rows = tuple(
                    tuple(_finite_hex(float(value), name="Vina energy") for value in row)
                    for row in energies.tolist()
                )
                return PoseBustersVinaExecutionBytes(
                    poses_pdbqt=poses.encode("ascii"),
                    energies_binary64_hex=rows,
                    diagnostic_sha256=sink.sha256,
                    diagnostic_size_bytes=sink.size_bytes,
                )
        except PoseBustersVinaCaseExecutionError:
            raise
        except Exception as exc:
            raise PoseBustersVinaCaseExecutionError(
                stage="vina_execution",
                error_code="vina_execution_failed",
                error_type=type(exc).__name__,
                error_message_sha256=_hash_bytes(_normalize_error(exc)),
                diagnostic_sha256=sink.sha256,
                diagnostic_size_bytes=sink.size_bytes,
            ) from exc


def _load_vina_runtime(scratch_root: Path) -> _VinaRuntimeProtocol:
    try:
        import torch
        import vina
        from vina import Vina
    except ImportError as exc:
        raise PoseBustersVinaExecutionError(
            "Vina execution requires the pinned optional Vina runtime"
        ) from exc
    _require_import_owned_by_distribution(vina, "vina")
    preparation_runtime = _runtime_identity(str(torch.__version__))
    dependency = _dependency_payload("vina", POSEBUSTERS_VINA_VERSION)
    source = Path(Vina.__init__.__code__.co_filename)
    identity = PoseBustersVinaEngineIdentity(
        preparation_runtime=preparation_runtime,
        vina_dependency=dependency,
        vina_api_source_sha256=_source_file_sha256(source),
    )
    return _VinaRuntime(
        Vina=Vina,
        identity=identity,
        scratch_root=scratch_root,
    )


@dataclass(frozen=True, slots=True)
class PoseBustersVinaPoseArtifact:
    relative_path: str
    sha256: str
    size_bytes: int
    prepared_receptor_sha256: str
    prepared_ligand_sha256: str
    schema_id: str = POSEBUSTERS_VINA_EXECUTION_ARTIFACT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_VINA_EXECUTION_ARTIFACT_SCHEMA_ID:
            raise PoseBustersVinaExecutionError(
                "unsupported Vina pose artifact schema"
            )
        object.__setattr__(self, "relative_path", _relative_path(self.relative_path))
        for name in (
            "sha256",
            "prepared_receptor_sha256",
            "prepared_ligand_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        size = _positive_int(self.size_bytes, name="Vina pose artifact size")
        if size > POSEBUSTERS_VINA_EXECUTION_MAX_POSE_ARTIFACT_BYTES:
            raise PoseBustersVinaExecutionError(
                "Vina pose artifact exceeds its size bound"
            )
        object.__setattr__(self, "size_bytes", size)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "role": "vina_generated_poses_pdbqt",
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": "chemical/x-pdbqt",
            "prepared_receptor_sha256": self.prepared_receptor_sha256,
            "prepared_ligand_sha256": self.prepared_ligand_sha256,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersVinaExecutionCase:
    case_id: str
    status: str
    disposition_code: str
    preparation_status: str
    preparation_disposition_code: str
    pocket_center_binary64_hex: tuple[str, ...] = ()
    engine_attempted: bool = False
    pose_count: int = 0
    energies_binary64_hex: tuple[tuple[str, ...], ...] = ()
    pose_artifact: PoseBustersVinaPoseArtifact | None = None
    error_stage: str = ""
    error_code: str = ""
    error_type: str = ""
    error_message_sha256: str = ""
    diagnostic_sha256: str = ""
    diagnostic_size_bytes: int = 0
    schema_id: str = POSEBUSTERS_VINA_EXECUTION_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_VINA_EXECUTION_CASE_SCHEMA_ID:
            raise PoseBustersVinaExecutionError(
                "unsupported Vina execution case schema"
            )
        case_id = _case_id(self.case_id)
        if self.status not in _CASE_STATUSES:
            raise PoseBustersVinaExecutionError(
                "Vina execution case status is invalid"
            )
        disposition = _token(self.disposition_code, name="Vina disposition")
        if self.preparation_status not in _PREPARATION_STATUSES:
            raise PoseBustersVinaExecutionError(
                "Vina row preparation status is invalid"
            )
        preparation_disposition = _token(
            self.preparation_disposition_code,
            name="preparation disposition",
        )
        center = tuple(
            _validate_hex(value, name="Vina pocket center")
            for value in self.pocket_center_binary64_hex
        )
        attempted = bool(self.engine_attempted)
        pose_count = _positive_int(
            self.pose_count,
            name="Vina pose count",
            allow_zero=True,
        )
        energies = tuple(
            tuple(_validate_hex(value, name="Vina energy") for value in row)
            for row in self.energies_binary64_hex
        )
        diagnostic_size = _positive_int(
            self.diagnostic_size_bytes,
            name="Vina diagnostic size",
            allow_zero=True,
        )
        if self.status == "success":
            valid = (
                self.preparation_status == "prepared"
                and attempted
                and len(center) == 3
                and pose_count == len(energies)
                and pose_count > 0
                and isinstance(self.pose_artifact, PoseBustersVinaPoseArtifact)
                and not any(
                    (
                        self.error_stage,
                        self.error_code,
                        self.error_type,
                        self.error_message_sha256,
                    )
                )
                and bool(self.diagnostic_sha256)
            )
        elif self.status == "engine_failure":
            valid = (
                self.preparation_status == "prepared"
                and attempted
                and len(center) == 3
                and pose_count == 0
                and not energies
                and self.pose_artifact is None
                and all(
                    (
                        self.error_stage,
                        self.error_code,
                        self.error_type,
                        self.error_message_sha256,
                    )
                )
                and bool(self.diagnostic_sha256)
            )
        else:
            expected_preparation = {
                "blocked_preparation_failure": "preparation_failure",
                "blocked_upstream_failure": "upstream_failure",
                "abstain_chemistry_scope": "abstain_chemistry_scope",
            }[self.status]
            valid = (
                self.preparation_status == expected_preparation
                and not attempted
                and not center
                and pose_count == 0
                and not energies
                and self.pose_artifact is None
                and not self.error_stage
                and not self.error_type
                and not self.error_message_sha256
                and not self.diagnostic_sha256
                and diagnostic_size == 0
            )
        if not valid:
            raise PoseBustersVinaExecutionError(
                "Vina execution case disposition is inconsistent"
            )
        if energies and (
            any(len(row) != len(_ENERGY_COMPONENTS) for row in energies)
            or any(
                float.fromhex(energies[index][0])
                > float.fromhex(energies[index + 1][0])
                for index in range(len(energies) - 1)
            )
        ):
            raise PoseBustersVinaExecutionError("Vina case energy table is invalid")
        error_stage = (
            _token(self.error_stage, name="Vina error stage")
            if self.error_stage
            else ""
        )
        error_code = (
            _token(self.error_code, name="Vina error code")
            if self.error_code
            else ""
        )
        error_type = (
            _identifier(self.error_type, name="Vina error type")
            if self.error_type
            else ""
        )
        error_sha = (
            _digest(self.error_message_sha256, name="Vina error message")
            if self.error_message_sha256
            else ""
        )
        diagnostic_sha = (
            _digest(self.diagnostic_sha256, name="Vina diagnostic")
            if self.diagnostic_sha256
            else ""
        )
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "disposition_code", disposition)
        object.__setattr__(
            self,
            "preparation_disposition_code",
            preparation_disposition,
        )
        object.__setattr__(self, "pocket_center_binary64_hex", center)
        object.__setattr__(self, "engine_attempted", attempted)
        object.__setattr__(self, "pose_count", pose_count)
        object.__setattr__(self, "energies_binary64_hex", energies)
        object.__setattr__(self, "error_stage", error_stage)
        object.__setattr__(self, "error_code", error_code)
        object.__setattr__(self, "error_type", error_type)
        object.__setattr__(self, "error_message_sha256", error_sha)
        object.__setattr__(self, "diagnostic_sha256", diagnostic_sha)
        object.__setattr__(self, "diagnostic_size_bytes", diagnostic_size)

    @property
    def generated_pose_present(self) -> bool:
        return self.status == "success"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "status": self.status,
            "disposition_code": self.disposition_code,
            "preparation_status": self.preparation_status,
            "preparation_disposition_code": self.preparation_disposition_code,
            "pocket_center_binary64_hex": list(
                self.pocket_center_binary64_hex
            ),
            "engine_attempted": self.engine_attempted,
            "pose_count": self.pose_count,
            "energy_component_order": list(_ENERGY_COMPONENTS),
            "energies_binary64_hex": [list(row) for row in self.energies_binary64_hex],
            "top_affinity_kcal_per_mol_binary64_hex": (
                self.energies_binary64_hex[0][0]
                if self.energies_binary64_hex
                else None
            ),
            "pose_artifact": (
                self.pose_artifact.to_dict()
                if self.pose_artifact is not None
                else None
            ),
            "generated_pose_present": self.generated_pose_present,
            "pose_validity_evaluated": False,
            "symmetry_aware_rmsd_evaluated": False,
            "error_stage": self.error_stage,
            "error_code": self.error_code,
            "error_type": self.error_type,
            "error_message_sha256": self.error_message_sha256,
            "diagnostic_sha256": self.diagnostic_sha256,
            "diagnostic_size_bytes": self.diagnostic_size_bytes,
        }


@dataclass(frozen=True, slots=True)
class PoseBustersVinaExecutionMetric:
    metric_id: str
    numerator: int
    denominator: int
    estimate: float
    confidence_interval_low: float
    confidence_interval_high: float
    schema_id: str = POSEBUSTERS_VINA_EXECUTION_METRIC_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_VINA_EXECUTION_METRIC_SCHEMA_ID:
            raise PoseBustersVinaExecutionError(
                "unsupported Vina execution metric schema"
            )
        metric_id = _token(self.metric_id, name="metric_id")
        numerator = _positive_int(self.numerator, name="numerator", allow_zero=True)
        denominator = _positive_int(self.denominator, name="denominator")
        values = tuple(
            float(value)
            for value in (
                self.estimate,
                self.confidence_interval_low,
                self.confidence_interval_high,
            )
        )
        if (
            numerator > denominator
            or any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in values)
            or not values[1] <= values[0] <= values[2]
            or not math.isclose(values[0], numerator / denominator, abs_tol=1.0e-15)
        ):
            raise PoseBustersVinaExecutionError(
                "Vina execution metric is inconsistent"
            )
        object.__setattr__(self, "metric_id", metric_id)
        object.__setattr__(self, "numerator", numerator)
        object.__setattr__(self, "denominator", denominator)
        object.__setattr__(self, "estimate", values[0])
        object.__setattr__(self, "confidence_interval_low", values[1])
        object.__setattr__(self, "confidence_interval_high", values[2])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "metric_id": self.metric_id,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "estimate": self.estimate,
            "confidence_level": POSEBUSTERS_VINA_EXECUTION_CONFIDENCE_LEVEL,
            "confidence_interval_method": "wilson_score_binomial",
            "confidence_interval_low": self.confidence_interval_low,
            "confidence_interval_high": self.confidence_interval_high,
        }


def _metric(
    metric_id: str,
    numerator: int,
    denominator: int,
) -> PoseBustersVinaExecutionMetric:
    proportion = numerator / denominator
    z2 = POSEBUSTERS_VINA_EXECUTION_Z**2
    scale = 1.0 + z2 / denominator
    center = (proportion + z2 / (2.0 * denominator)) / scale
    radius = (
        POSEBUSTERS_VINA_EXECUTION_Z
        * math.sqrt(
            proportion * (1.0 - proportion) / denominator
            + z2 / (4.0 * denominator**2)
        )
        / scale
    )
    return PoseBustersVinaExecutionMetric(
        metric_id=metric_id,
        numerator=numerator,
        denominator=denominator,
        estimate=proportion,
        confidence_interval_low=min(proportion, max(0.0, center - radius)),
        confidence_interval_high=max(proportion, min(1.0, center + radius)),
    )


def _summary_metrics(
    rows: Sequence[PoseBustersVinaExecutionCase],
) -> tuple[PoseBustersVinaExecutionMetric, ...]:
    predicates: tuple[
        tuple[str, Callable[[PoseBustersVinaExecutionCase], bool]], ...
    ] = (
        (
            "strict_prepared_input_pair_rate",
            lambda row: row.preparation_status == "prepared",
        ),
        ("vina_engine_attempt_rate", lambda row: row.engine_attempted),
        ("vina_engine_success_rate", lambda row: row.status == "success"),
        ("vina_engine_failure_rate", lambda row: row.status == "engine_failure"),
        (
            "generated_pose_artifact_rate",
            lambda row: row.generated_pose_present,
        ),
        (
            "preparation_failure_blocked_rate",
            lambda row: row.status == "blocked_preparation_failure",
        ),
        (
            "upstream_failure_blocked_rate",
            lambda row: row.status == "blocked_upstream_failure",
        ),
        (
            "chemistry_scope_abstention_rate",
            lambda row: row.status == "abstain_chemistry_scope",
        ),
        ("generated_pose_validity_evaluation_rate", lambda _row: False),
        ("symmetry_aware_rmsd_evaluation_rate", lambda _row: False),
    )
    denominator = len(rows)
    return tuple(
        _metric(metric_id, sum(bool(predicate(row)) for row in rows), denominator)
        for metric_id, predicate in predicates
    )


def _artifact_set_sha256(rows: Sequence[PoseBustersVinaExecutionCase]) -> str:
    payload = {
        row.case_id: row.pose_artifact.to_dict()
        for row in rows
        if row.pose_artifact is not None
    }
    return _canonical_sha256(payload)


@dataclass(frozen=True, slots=True)
class PoseBustersVinaExecutionReceipt:
    preparation_receipt_sha256: str
    preparation_receipt_file_sha256: str
    preparation_artifact_set_sha256: str
    implementation_source_sha256: str
    implementation_source_members: tuple[tuple[str, str], ...]
    engine_identity: PoseBustersVinaEngineIdentity
    configuration_sha256: str
    case_rows: tuple[PoseBustersVinaExecutionCase, ...]
    metrics: tuple[PoseBustersVinaExecutionMetric, ...]
    artifact_set_sha256: str
    schema_id: str = POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID:
            raise PoseBustersVinaExecutionError(
                "unsupported Vina execution receipt schema"
            )
        for name in (
            "preparation_receipt_sha256",
            "preparation_receipt_file_sha256",
            "preparation_artifact_set_sha256",
            "implementation_source_sha256",
            "configuration_sha256",
            "artifact_set_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if self.configuration_sha256 != (
            POSEBUSTERS_VINA_EXECUTION_CONFIGURATION_SHA256
        ):
            raise PoseBustersVinaExecutionError(
                "Vina execution configuration identity is invalid"
            )
        members = tuple(
            (
                _token(role, name="implementation source role"),
                _digest(digest, name=f"{role} implementation source"),
            )
            for role, digest in self.implementation_source_members
        )
        if (
            not members
            or tuple(sorted(members)) != members
            or len({role for role, _sha in members}) != len(members)
            or self.implementation_source_sha256 != _canonical_sha256(dict(members))
        ):
            raise PoseBustersVinaExecutionError(
                "Vina implementation-source identity is inconsistent"
            )
        if not isinstance(self.engine_identity, PoseBustersVinaEngineIdentity):
            raise PoseBustersVinaExecutionError(
                "Vina engine identity is missing"
            )
        rows = tuple(self.case_rows)
        if (
            not rows
            or tuple(row.case_id for row in rows)
            != tuple(sorted(row.case_id for row in rows))
            or len({row.case_id for row in rows}) != len(rows)
        ):
            raise PoseBustersVinaExecutionError(
                "Vina rows must be canonical unique cases"
            )
        metrics = _summary_metrics(rows)
        if tuple(row.to_dict() for row in self.metrics) != tuple(
            row.to_dict() for row in metrics
        ):
            raise PoseBustersVinaExecutionError(
                "Vina metrics do not match all-case rows"
            )
        if self.artifact_set_sha256 != _artifact_set_sha256(rows):
            raise PoseBustersVinaExecutionError(
                "Vina artifact-set identity is inconsistent"
            )
        object.__setattr__(self, "implementation_source_members", members)
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "metrics", metrics)

    @property
    def attempted_case_count(self) -> int:
        return sum(row.engine_attempted for row in self.case_rows)

    @property
    def success_case_count(self) -> int:
        return sum(row.status == "success" for row in self.case_rows)

    @property
    def engine_failure_case_count(self) -> int:
        return sum(row.status == "engine_failure" for row in self.case_rows)

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "preparation_receipt_sha256": self.preparation_receipt_sha256,
            "preparation_receipt_file_sha256": (
                self.preparation_receipt_file_sha256
            ),
            "preparation_artifact_set_sha256": (
                self.preparation_artifact_set_sha256
            ),
            "implementation_source_sha256": self.implementation_source_sha256,
            "implementation_source_members": dict(self.implementation_source_members),
            "engine_identity": self.engine_identity.to_dict(),
            "engine_identity_sha256": self.engine_identity.fingerprint_sha256,
            "configuration": POSEBUSTERS_VINA_EXECUTION_CONFIGURATION,
            "configuration_sha256": self.configuration_sha256,
            "all_case_denominator": len(self.case_rows),
            "attempted_case_count": self.attempted_case_count,
            "success_case_count": self.success_case_count,
            "engine_failure_case_count": self.engine_failure_case_count,
            "case_rows": [row.to_dict() for row in self.case_rows],
            "metrics": [row.to_dict() for row in self.metrics],
            "artifact_set_sha256": self.artifact_set_sha256,
            "external_engine_executed": self.attempted_case_count > 0,
            "vina_same_input_execution_performed": self.attempted_case_count > 0,
            "gnina_same_input_execution_performed": False,
            "smina_same_input_execution_performed": False,
            "generated_pose_validity_evaluated": False,
            "symmetry_aware_rmsd_evaluated": False,
            "target_family_metrics_present": False,
            "leakage_receipt_present": False,
            "benchmark_executed": False,
            "scientific_blockers": list(POSEBUSTERS_VINA_EXECUTION_BLOCKERS),
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
        payload = _canonical_bytes(self.to_dict()) + b"\n"
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
                raise PoseBustersVinaExecutionError(
                    "PoseBusters Vina execution output already exists"
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


def _implementation_source_members() -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            {
                "external_preparation_contract": _source_file_sha256(
                    Path(__file__).with_name(
                        "public_posebusters_external_preparation.py"
                    )
                ),
                "vina_execution": _source_file_sha256(__file__),
            }.items()
        )
    )


def _blocked_row(prepared: _PreparedCaseView) -> PoseBustersVinaExecutionCase:
    status = {
        "preparation_failure": "blocked_preparation_failure",
        "upstream_failure": "blocked_upstream_failure",
        "abstain_chemistry_scope": "abstain_chemistry_scope",
    }[prepared.status]
    disposition = {
        "preparation_failure": "blocked_by_strict_preparation_failure",
        "upstream_failure": "blocked_by_upstream_preparation_input_failure",
        "abstain_chemistry_scope": "chemistry_scope_abstention",
    }[prepared.status]
    return PoseBustersVinaExecutionCase(
        case_id=prepared.case_id,
        status=status,
        disposition_code=disposition,
        preparation_status=prepared.status,
        preparation_disposition_code=prepared.disposition_code,
        error_code=prepared.error_code,
    )


def _execute_case(
    prepared: _PreparedCaseView,
    prepared_payloads: dict[str, bytes],
    runtime: _VinaRuntimeProtocol,
) -> tuple[PoseBustersVinaExecutionCase, dict[str, bytes]]:
    if prepared.status != "prepared":
        return _blocked_row(prepared), {}
    artifacts = {row.role: row for row in prepared.artifacts}
    receptor = artifacts["prepared_receptor_pdbqt"]
    ligand = artifacts["prepared_ligand_pdbqt"]
    try:
        execution = runtime.execute(
            prepared_payloads[receptor.relative_path],
            prepared_payloads[ligand.relative_path],
            prepared.pocket_center_binary64_hex,
        )
    except PoseBustersVinaCaseExecutionError as exc:
        return PoseBustersVinaExecutionCase(
            case_id=prepared.case_id,
            status="engine_failure",
            disposition_code=exc.error_code,
            preparation_status=prepared.status,
            preparation_disposition_code=prepared.disposition_code,
            pocket_center_binary64_hex=prepared.pocket_center_binary64_hex,
            engine_attempted=True,
            error_stage=exc.stage,
            error_code=exc.error_code,
            error_type=exc.error_type,
            error_message_sha256=exc.error_message_sha256,
            diagnostic_sha256=exc.diagnostic_sha256,
            diagnostic_size_bytes=exc.diagnostic_size_bytes,
        ), {}
    except Exception as exc:
        empty_sha = _hash_bytes(b"")
        return PoseBustersVinaExecutionCase(
            case_id=prepared.case_id,
            status="engine_failure",
            disposition_code="unclassified_vina_runtime_failure",
            preparation_status=prepared.status,
            preparation_disposition_code=prepared.disposition_code,
            pocket_center_binary64_hex=prepared.pocket_center_binary64_hex,
            engine_attempted=True,
            error_stage="runtime",
            error_code="unclassified_vina_runtime_failure",
            error_type=type(exc).__name__,
            error_message_sha256=_hash_bytes(_normalize_error(exc)),
            diagnostic_sha256=empty_sha,
            diagnostic_size_bytes=0,
        ), {}
    relative_path = f"{prepared.case_id}/poses.pdbqt"
    artifact = PoseBustersVinaPoseArtifact(
        relative_path=relative_path,
        sha256=_hash_bytes(execution.poses_pdbqt),
        size_bytes=len(execution.poses_pdbqt),
        prepared_receptor_sha256=receptor.sha256,
        prepared_ligand_sha256=ligand.sha256,
    )
    return PoseBustersVinaExecutionCase(
        case_id=prepared.case_id,
        status="success",
        disposition_code="vina_generated_pose_artifact",
        preparation_status=prepared.status,
        preparation_disposition_code=prepared.disposition_code,
        pocket_center_binary64_hex=prepared.pocket_center_binary64_hex,
        engine_attempted=True,
        pose_count=len(execution.energies_binary64_hex),
        energies_binary64_hex=execution.energies_binary64_hex,
        pose_artifact=artifact,
        diagnostic_sha256=execution.diagnostic_sha256,
        diagnostic_size_bytes=execution.diagnostic_size_bytes,
    ), {relative_path: execution.poses_pdbqt}


def _build_execution(
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    output_artifact_root: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_preparation_receipt_sha256: str,
) -> tuple[PoseBustersVinaExecutionReceipt, dict[str, bytes]]:
    preparation_root = Path(preparation_artifact_root).resolve(strict=False)
    output_root = Path(output_artifact_root).resolve(strict=False)
    scratch = Path(scratch_root).resolve(strict=False)
    if any(
        first == second or first in second.parents or second in first.parents
        for first, second in (
            (preparation_root, output_root),
            (preparation_root, scratch),
            (output_root, scratch),
        )
    ):
        raise PoseBustersVinaExecutionError(
            "preparation, output, and scratch roots must be disjoint"
        )
    preparation, prepared_payloads = _load_preparation_receipt(
        preparation_receipt_path,
        preparation_artifact_root,
        expected_receipt_sha256=expected_preparation_receipt_sha256,
    )
    if (
        _canonical_sha256(POSEBUSTERS_VINA_EXECUTION_CONFIGURATION)
        != POSEBUSTERS_VINA_EXECUTION_CONFIGURATION_SHA256
    ):
        raise PoseBustersVinaExecutionError(
            "Vina execution frozen configuration was mutated"
        )
    runtime = _load_vina_runtime(Path(scratch_root))
    if (
        runtime.identity.preparation_runtime.to_dict()
        != preparation.runtime_identity
        or runtime.identity.preparation_runtime.fingerprint_sha256
        != preparation.runtime_identity_sha256
    ):
        raise PoseBustersVinaExecutionError(
            "Vina runtime does not match the exact preparation runtime"
        )
    rows: list[PoseBustersVinaExecutionCase] = []
    output_payloads: dict[str, bytes] = {}
    for prepared in preparation.case_rows:
        row, payloads = _execute_case(prepared, prepared_payloads, runtime)
        rows.append(row)
        if set(output_payloads).intersection(payloads):
            raise PoseBustersVinaExecutionError(
                "Vina output artifact path is duplicated"
            )
        output_payloads.update(payloads)
    rows_tuple = tuple(rows)
    source_members = _implementation_source_members()
    receipt = PoseBustersVinaExecutionReceipt(
        preparation_receipt_sha256=preparation.receipt_sha256,
        preparation_receipt_file_sha256=preparation.receipt_file_sha256,
        preparation_artifact_set_sha256=preparation.artifact_set_sha256,
        implementation_source_sha256=_canonical_sha256(dict(source_members)),
        implementation_source_members=source_members,
        engine_identity=runtime.identity,
        configuration_sha256=POSEBUSTERS_VINA_EXECUTION_CONFIGURATION_SHA256,
        case_rows=rows_tuple,
        metrics=_summary_metrics(rows_tuple),
        artifact_set_sha256=_artifact_set_sha256(rows_tuple),
    )
    expected_paths = {
        row.pose_artifact.relative_path
        for row in rows_tuple
        if row.pose_artifact is not None
    }
    if set(output_payloads) != expected_paths:
        raise PoseBustersVinaExecutionError(
            "Vina output artifact set is incomplete"
        )
    return receipt, output_payloads


def materialize_posebusters_vina_execution(
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    output_artifact_root: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_preparation_receipt_sha256: str,
) -> PoseBustersVinaExecutionReceipt:
    """Execute pinned Vina for prepared rows and retain all dispositions."""

    try:
        Path(output_artifact_root).lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise PoseBustersVinaExecutionError(
            "Vina output artifact root cannot be inspected"
        ) from exc
    else:
        raise PoseBustersVinaExecutionError(
            "Vina output artifact root already exists"
        )

    receipt, payloads = _build_execution(
        preparation_receipt_path,
        preparation_artifact_root,
        output_artifact_root,
        scratch_root,
        expected_preparation_receipt_sha256=expected_preparation_receipt_sha256,
    )
    try:
        _write_artifact_tree(Path(output_artifact_root), payloads)
    except PoseBustersExternalPreparationError as exc:
        raise PoseBustersVinaExecutionError(
            "Vina output artifact tree could not be materialized"
        ) from exc
    return receipt


def verify_posebusters_vina_execution_receipt(
    execution_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    preparation_artifact_root: str | os.PathLike[str],
    output_artifact_root: str | os.PathLike[str],
    scratch_root: str | os.PathLike[str],
    *,
    expected_preparation_receipt_sha256: str,
) -> PoseBustersVinaExecutionReceipt:
    """Require exact Vina reexecution, receipt bytes, and private pose artifacts."""

    source = _read_exact_regular_file(
        execution_receipt_path,
        maximum_bytes=POSEBUSTERS_VINA_EXECUTION_MAX_RECEIPT_BYTES,
    )
    expected, payloads = _build_execution(
        preparation_receipt_path,
        preparation_artifact_root,
        output_artifact_root,
        scratch_root,
        expected_preparation_receipt_sha256=expected_preparation_receipt_sha256,
    )
    try:
        _verify_artifact_tree(Path(output_artifact_root), payloads)
    except PoseBustersExternalPreparationError as exc:
        raise PoseBustersVinaExecutionError(
            "Vina output artifact tree failed exact verification"
        ) from exc
    if source != _canonical_bytes(expected.to_dict()) + b"\n":
        raise PoseBustersVinaExecutionError(
            "PoseBusters Vina receipt does not match exact reexecution"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-vina-execute",
        description=(
            "Execute pinned Vina on strict PoseBusters inputs with all-case rows."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--preparation-receipt", required=True)
    materialize.add_argument("--expected-preparation-receipt-sha256", required=True)
    materialize.add_argument("--preparation-artifact-root", required=True)
    materialize.add_argument("--output-artifact-root", required=True)
    materialize.add_argument("--scratch-root", required=True)
    materialize.add_argument("--output", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--preparation-receipt", required=True)
    verify.add_argument("--expected-preparation-receipt-sha256", required=True)
    verify.add_argument("--preparation-artifact-root", required=True)
    verify.add_argument("--output-artifact-root", required=True)
    verify.add_argument("--scratch-root", required=True)
    verify.add_argument("--execution-receipt", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {
        "preparation_receipt_path": args.preparation_receipt,
        "preparation_artifact_root": args.preparation_artifact_root,
        "output_artifact_root": args.output_artifact_root,
        "scratch_root": args.scratch_root,
        "expected_preparation_receipt_sha256": (
            args.expected_preparation_receipt_sha256
        ),
    }
    if args.command == "materialize":
        if Path(args.output).exists():
            raise PoseBustersVinaExecutionError(
                "PoseBusters Vina execution output already exists"
            )
        receipt = materialize_posebusters_vina_execution(**common)
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_vina_execution_receipt(
            execution_receipt_path=args.execution_receipt,
            **common,
        )
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": len(receipt.case_rows),
                "attempted_case_count": receipt.attempted_case_count,
                "success_case_count": receipt.success_case_count,
                "engine_failure_case_count": receipt.engine_failure_case_count,
                "external_engine_executed": receipt.attempted_case_count > 0,
                "benchmark_executed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_VINA_EXECUTION_ARTIFACT_SCHEMA_ID",
    "POSEBUSTERS_VINA_EXECUTION_BLOCKERS",
    "POSEBUSTERS_VINA_EXECUTION_CASE_SCHEMA_ID",
    "POSEBUSTERS_VINA_EXECUTION_CONFIDENCE_LEVEL",
    "POSEBUSTERS_VINA_EXECUTION_CONFIGURATION",
    "POSEBUSTERS_VINA_EXECUTION_CONFIGURATION_SHA256",
    "POSEBUSTERS_VINA_EXECUTION_ENGINE_SCHEMA_ID",
    "POSEBUSTERS_VINA_EXECUTION_MAX_POSE_ARTIFACT_BYTES",
    "POSEBUSTERS_VINA_EXECUTION_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_VINA_EXECUTION_METRIC_SCHEMA_ID",
    "POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID",
    "POSEBUSTERS_VINA_VERSION",
    "PoseBustersVinaCaseExecutionError",
    "PoseBustersVinaEngineIdentity",
    "PoseBustersVinaExecutionBytes",
    "PoseBustersVinaExecutionCase",
    "PoseBustersVinaExecutionError",
    "PoseBustersVinaExecutionMetric",
    "PoseBustersVinaExecutionReceipt",
    "PoseBustersVinaPoseArtifact",
    "main",
    "materialize_posebusters_vina_execution",
    "verify_posebusters_vina_execution_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
