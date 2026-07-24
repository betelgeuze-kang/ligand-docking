"""Bounded CPU runner for the frozen synthetic validation protocol.

The runner accepts only a freshly reverified execution-environment receipt,
atomically consumes a one-time runner-start marker, verifies the frozen source
binding, and evaluates exactly twenty-seven cases and fifty-nine variants.  It
returns an in-memory failure-inclusive observation.  The exact module entrypoint
can additionally orchestrate environment-receipt creation and result-receipt
finalization from one canonical standard-input request, but neither path
authorizes a production run, accepts parameter-fitting data, or promotes
scientific, benchmark, product, publication, or customer claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import stat
import sys
import threading
import time
from typing import Any, Mapping, Sequence

from .reference_validation_bootstrap import (
    REFERENCE_VALIDATION_APPLICATION_SEED_ENV,
    REFERENCE_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE,
    REFERENCE_VALIDATION_CONTROLLED_INNER_STAGE_ENV,
    REFERENCE_VALIDATION_CONTROLLED_INNER_STATE,
    REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV,
    REFERENCE_VALIDATION_TRUSTED_OUTER_LAUNCHER_ARGV,
    reference_validation_bootstrap_path,
    reference_validation_controlled_inner_environment,
    reference_validation_execution_source_sha256,
)
from .reference_validation_dependency_identity import (
    REFERENCE_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS,
    ReferenceValidationDependencyIdentityError,
    observed_reference_validation_dependency_artifact_sha256_rows,
)
from .reference_validation_nonce_reservation import (
    ReferenceValidationNonceReservationError,
    _open_secure_reservation_root,
    _validate_reservation_file_stat,
)
from .reference_validation_protocol import (
    FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
    CPUReferenceValidationCase,
    CPUReferenceValidationMetric,
    frozen_cpu_reference_validation_protocol,
)
from .reference_validation_receipts import (
    FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256,
)
from .reference_validation_run_start import (
    FROZEN_REFERENCE_VALIDATION_RUN_START_CONTRACT_SHA256,
    ReferenceValidationExecutionEnvironmentReceipt,
    ReferenceValidationRunStartError,
    _require_reference_validation_root_outside_checkout as _require_external_root,
    require_reference_validation_execution_environment_receipt_for_runner,
)
from .validation_source_identity import (
    ValidationSourceIdentityError,
    require_validation_source_manifest_document,
)
from .validation_native_runtime_identity import (
    WORKER_RUNTIME_LANE_ENERGY_FORCE,
    WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
    ValidationNativeRuntimeIdentityError,
    build_complete_worker_runtime_lifecycle_evidence,
    build_incomplete_worker_runtime_lifecycle_evidence,
    build_worker_runtime_pre_evidence,
    BoundedWorkerProcessCommunicationEvidence,
    communicate_bounded_worker_process_with_evidence,
    require_complete_worker_runtime_process_id,
    require_worker_runtime_lifecycle_evidence,
    require_worker_runtime_pre_evidence,
)


REFERENCE_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_runner_contract/7.0.0"
)
REFERENCE_VALIDATION_RUNNER_START_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_runner_start/7.0.0"
)
REFERENCE_VALIDATION_RUN_OBSERVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_run_observation/7.0.0"
)
_CASE_WORKER_INCOMPLETE_FAILURE_CODES = frozenset(
    {
        "case_worker_start_failed",
        "runner_time_budget_exhausted",
        "case_worker_nonzero_exit",
        "case_worker_protocol_invalid",
    }
)
REFERENCE_VALIDATION_RUNNER_CONTRACT_ID = (
    "cpu_reference_validation_bounded_runner/7.0.0"
)
REFERENCE_VALIDATION_RUNNER_CONTRACT_VERSION = "7.0.0"
REFERENCE_VALIDATION_RUNNER_CONTRACT_FROZEN_AT_UTC = "2026-07-24T18:40:00Z"
REFERENCE_VALIDATION_RUNNER_MAX_RECEIPT_AGE = timedelta(minutes=5)
REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS = 120.0
REFERENCE_VALIDATION_RUNNER_PREFLIGHT_MAX_WALL_SECONDS = 180.0
REFERENCE_VALIDATION_RUNNER_MAX_CASES = 27
REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS = 59
REFERENCE_VALIDATION_RUNNER_MAX_START_RECORD_BYTES = 65_536
REFERENCE_VALIDATION_RUNNER_MAX_REQUEST_BYTES = 1_048_576
REFERENCE_VALIDATION_CASE_WORKER_MAX_REQUEST_BYTES = 16_384
REFERENCE_VALIDATION_CASE_WORKER_MAX_OUTPUT_BYTES = 8 * 1_048_576
REFERENCE_VALIDATION_TRUST_STORE_MAX_BYTES = 65_536
REFERENCE_VALIDATION_CENTRAL_DIFFERENCE_STEP_ANGSTROM = 1.0e-5
REFERENCE_VALIDATION_RUNNER_REQUEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_runner_request/4.0.0"
)
REFERENCE_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_runner_response/4.0.0"
)
REFERENCE_VALIDATION_CASE_WORKER_REQUEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_case_worker_request/6.0.0"
)
REFERENCE_VALIDATION_WORKER_FRAME_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_worker_frame/1.0.0"
)
REFERENCE_VALIDATION_WORKER_EXECUTION_PROVENANCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_worker_execution_provenance/1.0.0"
)
REFERENCE_VALIDATION_TRUST_STORE_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_validation_trust_store/2.0.0"
)
REFERENCE_VALIDATION_TRUST_STORE_PATH = (
    "/etc/betelgeuze/engine-v2/reference-validation-trust-anchors.json"
)

FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256 = (
    "dda3ba6733c35c5609892e5666a79bf2e9a2d82f13e674af025470e56c0a5e18"
)
FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V6 = (
    "2322a391f8ce2457c830a834ebff642b2130355bd4fe85b324a01e0694583a93"
)
FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V5 = (
    "4c2cc8f162f2e71686c99245deca977df725306ab58afc1fa96d84019be00cdb"
)
FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V4 = (
    "baeb0ae59234cf69154b0ed34658d779fdc0cfec05c969856056a586be13bad8"
)
FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V3 = (
    "c450059857a38f7cf8aa44ba1efbb79ff3d6218ebc7deaf963078c2e3f44a1e9"
)
FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V2 = (
    "96b133144344183191db89c86838a6d712a26f0dbfc5eee4981d34e2fe074754"
)
FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V1 = (
    "c9c3ca36f9afcda451f41848605bcc141e99520e262894d24013a2fabda9ef33"
)

_ROTATION_MATRIX = (
    (0.0, -1.0, 0.0),
    (1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0),
)
_PERMUTATION_NEW_TO_OLD = (3, 1, 0, 2)
_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
_REFERENCE_VALIDATION_FIXED_WORKER_BOOTSTRAP = (
    "import sys;"
    "from betelgeuze_engine_v2.physics import reference_validation_runner as worker;"
    "raise SystemExit(worker._fixed_worker_main(sys.argv[1:]))"
)
_REFERENCE_VALIDATION_WORKER_ENVIRONMENT_NAMES = frozenset(
    {
        REFERENCE_VALIDATION_APPLICATION_SEED_ENV,
        "CUDA_VISIBLE_DEVICES",
        "HIP_VISIBLE_DEVICES",
        "HOME",
        "LANG",
        "LC_ALL",
        "MKL_NUM_THREADS",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "PATH",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONHASHSEED",
        "PYTHONNOUSERSITE",
        "PYTHONPATH",
        "PYTHONPYCACHEPREFIX",
        "ROCR_VISIBLE_DEVICES",
        "TZ",
    }
)
_POST_RUN_BLOCKERS = (
    "production_validation_result_not_collected",
    "result_receipt_not_written",
    "independent_result_review_missing",
    "external_worker_launch_identity_not_established",
    "parameter_fitting_not_authorized",
    "minimization_validation_results_not_collected",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)
_CURRENT_BLOCKERS = (
    "independent_scientific_review_missing",
    "signed_independent_scientific_review_attestation_missing",
    "trusted_independent_scientific_reviewer_key_not_provided",
    "signed_execution_authorization_receipt_missing",
    "trusted_authorization_operator_key_not_provided",
    "authorization_nonce_not_atomically_reserved",
    "production_environment_receipt_missing",
    "production_result_receipt_missing",
    "independent_result_review_missing",
    "validation_execution_not_authorized",
    "validation_results_not_collected",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceValidationRunnerError(RuntimeError):
    """The bounded runner preflight, execution, or observation failed."""


class ReferenceValidationRunnerAlreadyStartedError(ReferenceValidationRunnerError):
    """The one-time runner-start path for the authorization nonce exists."""


class _ReferenceValidationDeadlineExceeded(Exception):
    """Internal, sanitized control flow for the frozen wall-clock deadline."""


def _require_runner_root_outside_checkout(
    root: str | os.PathLike[str],
    *,
    name: str,
) -> None:
    try:
        _require_external_root(root, name=name)
    except ReferenceValidationRunStartError as exc:
        raise ReferenceValidationRunnerError(
            f"{name} must be outside the source checkout"
        ) from exc


def _require_source_only_python_runtime() -> None:
    """Reject startup modes that can execute ignored timestamp bytecode caches."""

    if (
        os.environ.get("PYTHONDONTWRITEBYTECODE") != "1"
        or os.environ.get("PYTHONPYCACHEPREFIX") != "/dev/null"
        or sys.flags.dont_write_bytecode != 1
        or sys.dont_write_bytecode is not True
        or sys.pycache_prefix != "/dev/null"
    ):
        raise ReferenceValidationRunnerError(
            "validation runner requires source-only Python imports"
        )
    try:
        null_stat = os.lstat("/dev/null")
    except OSError as exc:
        raise ReferenceValidationRunnerError(
            "source-only Python cache sink is unavailable"
        ) from exc
    if (
        not stat.S_ISCHR(null_stat.st_mode)
        or null_stat.st_uid != 0
        or os.major(null_stat.st_rdev) != 1
        or os.minor(null_stat.st_rdev) != 3
    ):
        raise ReferenceValidationRunnerError("source-only Python cache sink is invalid")


def _require_trusted_dependency_roots(
    raw_dependency_roots: object,
) -> tuple[Path, ...]:
    if not isinstance(raw_dependency_roots, tuple) or not raw_dependency_roots:
        raise ReferenceValidationRunnerError(
            "validation runner dependency roots are invalid"
        )
    dependency_roots: list[Path] = []
    for raw_root in raw_dependency_roots:
        if not isinstance(raw_root, str) or not raw_root or os.pathsep in raw_root:
            raise ReferenceValidationRunnerError(
                "validation runner dependency root is invalid"
            )
        candidate = Path(raw_root)
        try:
            file_stat = candidate.lstat()
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise ReferenceValidationRunnerError(
                "validation runner dependency root is unavailable"
            ) from exc
        if (
            not candidate.is_absolute()
            or candidate.is_symlink()
            or resolved != candidate
            or not stat.S_ISDIR(file_stat.st_mode)
            or file_stat.st_uid != 0
            or stat.S_IMODE(file_stat.st_mode) & 0o022
        ):
            raise ReferenceValidationRunnerError(
                "validation runner dependency root is not trusted"
            )
        dependency_roots.append(resolved)

    import numpy
    import torch

    for dependency, name in ((numpy, "NumPy"), (torch, "Torch")):
        try:
            module_path = Path(dependency.__file__).resolve(strict=True)
        except (OSError, TypeError) as exc:
            raise ReferenceValidationRunnerError(
                f"validation runner {name} source is unavailable"
            ) from exc
        if not any(module_path.is_relative_to(root) for root in dependency_roots):
            raise ReferenceValidationRunnerError(
                f"validation runner {name} was not imported from a trusted root"
            )
    return tuple(dependency_roots)


def _require_isolated_python_bootstrap_runtime(
    *,
    expected_code_commit_sha: str | None = None,
    expected_source_manifest_sha256: str | None = None,
) -> tuple[Path, ...]:
    """Require the stdlib-only bootstrap before trusting imported dependencies."""

    state = getattr(sys, REFERENCE_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE, None)
    expected_bootstrap = Path(reference_validation_bootstrap_path())
    expected_repository = Path(__file__).resolve(strict=True).parents[2]
    if (
        sys.flags.isolated != 0
        or sys.flags.ignore_environment != 0
        or sys.flags.no_site != 1
        or sys.flags.no_user_site != 1
        or sys.flags.dont_write_bytecode != 1
        or sys.dont_write_bytecode is not True
        or sys.pycache_prefix != "/dev/null"
        or not isinstance(state, tuple)
        or len(state) != 6
    ):
        raise ReferenceValidationRunnerError(
            "validation runner requires the seeded controlled dependency bootstrap"
        )
    (
        state_marker,
        bootstrap_path,
        repository_root,
        raw_dependency_roots,
        frozen_sys_path,
        source_manifest_bytes,
    ) = state
    try:
        source_manifest = json.loads(source_manifest_bytes.decode("ascii"))
        if (
            not isinstance(source_manifest, dict)
            or _canonical_bytes(source_manifest) != source_manifest_bytes
        ):
            raise ValidationSourceIdentityError(
                "bootstrap source manifest is not canonical"
            )
        source_manifest = require_validation_source_manifest_document(source_manifest)
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationRunnerError(
            "validation runner bootstrap source manifest is invalid"
        ) from exc
    except ValidationSourceIdentityError as exc:
        raise ReferenceValidationRunnerError(
            "validation runner bootstrap source manifest is invalid"
        ) from exc
    if expected_code_commit_sha is not None and source_manifest.get(
        "code_commit_sha"
    ) != _require_commit_sha(
        expected_code_commit_sha,
        name="expected bootstrap source commit",
    ):
        raise ReferenceValidationRunnerError(
            "validation runner bootstrap source commit is cross-wired"
        )
    if expected_source_manifest_sha256 is not None and source_manifest.get(
        "manifest_sha256"
    ) != _require_sha256(
        expected_source_manifest_sha256,
        name="expected bootstrap source manifest",
    ):
        raise ReferenceValidationRunnerError(
            "validation runner bootstrap source manifest is cross-wired"
        )
    expected_orig_argv = (
        os.path.realpath(sys.executable),
        *REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV[1:-1],
        os.fspath(expected_bootstrap),
    )
    try:
        expected_environment = reference_validation_controlled_inner_environment()
    except Exception as exc:
        raise ReferenceValidationRunnerError(
            "validation runner controlled environment is invalid"
        ) from exc
    if (
        state_marker != REFERENCE_VALIDATION_CONTROLLED_INNER_STATE
        or bootstrap_path != os.fspath(expected_bootstrap)
        or repository_root != os.fspath(expected_repository)
        or not isinstance(frozen_sys_path, tuple)
        or tuple(sys.path) != frozen_sys_path
        or not sys.path
        or sys.path[0] != os.fspath(expected_repository)
        or tuple(getattr(sys, "orig_argv", ())) != expected_orig_argv
        or sys.argv != [os.fspath(expected_bootstrap)]
        or os.getcwd() != "/"
        or dict(os.environ) != expected_environment
        or os.environ.get(REFERENCE_VALIDATION_CONTROLLED_INNER_STAGE_ENV)
        != REFERENCE_VALIDATION_CONTROLLED_INNER_STATE
    ):
        raise ReferenceValidationRunnerError(
            "validation runner bootstrap state is invalid"
        )
    return _require_trusted_dependency_roots(raw_dependency_roots)


def _observe_dependency_artifact_sha256_rows(
    dependency_roots: tuple[Path, ...],
    *,
    deadline: float | None = None,
) -> dict[str, str]:
    try:
        return observed_reference_validation_dependency_artifact_sha256_rows(
            dependency_roots,
            deadline=deadline,
        )
    except ReferenceValidationDependencyIdentityError as exc:
        raise ReferenceValidationRunnerError(
            "runner dependency bytes cannot be measured"
        ) from exc


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ReferenceValidationRunnerError(
            "runner observation is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceValidationRunnerError(f"{name} must be a lowercase SHA-256")
    return value


def _require_commit_sha(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceValidationRunnerError(
            f"{name} must be a lowercase forty-character commit SHA"
        )
    return value


def _format_utc(value: datetime, *, name: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReferenceValidationRunnerError(f"{name} must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    if normalized.microsecond:
        raise ReferenceValidationRunnerError(f"{name} must use second resolution")
    return normalized.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str):
        raise ReferenceValidationRunnerError(f"{name} must be UTC text")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ReferenceValidationRunnerError(
            f"{name} must use second-resolution UTC"
        ) from exc


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _normalize_dependency_rows(
    rows: Mapping[str, str] | tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    if isinstance(rows, Mapping):
        raw_rows: tuple[object, ...] = tuple(rows.items())
        canonicalize = True
    elif isinstance(rows, tuple):
        raw_rows = rows
        canonicalize = False
    else:
        raise ReferenceValidationRunnerError(
            "runner dependency rows must be a mapping or canonical tuple"
        )
    normalized_rows: list[tuple[str, str]] = []
    for row in raw_rows:
        if not isinstance(row, tuple) or len(row) != 2:
            raise ReferenceValidationRunnerError(
                "runner dependency rows must contain identity and digest pairs"
            )
        artifact_id, digest = row
        if not isinstance(artifact_id, str) or not isinstance(digest, str):
            raise ReferenceValidationRunnerError(
                "runner dependency rows must contain text identities and digests"
            )
        normalized_rows.append((artifact_id, digest))
    normalized = tuple(sorted(normalized_rows) if canonicalize else normalized_rows)
    if not normalized or (not canonicalize and tuple(sorted(normalized)) != normalized):
        raise ReferenceValidationRunnerError(
            "runner dependency rows must be non-empty and sorted"
        )
    if len({row[0] for row in normalized}) != len(normalized):
        raise ReferenceValidationRunnerError(
            "runner dependency artifact identities must be unique"
        )
    if tuple(row[0] for row in normalized) != (
        REFERENCE_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
    ):
        raise ReferenceValidationRunnerError(
            "runner dependency rows do not match the required byte identities"
        )
    for artifact_id, digest in normalized:
        if (
            not isinstance(artifact_id, str)
            or not artifact_id
            or len(artifact_id) > 200
            or not all(
                character.isascii() and (character.isalnum() or character in "._-")
                for character in artifact_id
            )
        ):
            raise ReferenceValidationRunnerError(
                "runner dependency artifact identity is invalid"
            )
        _require_sha256(digest, name=f"runner dependency {artifact_id}")
    return normalized


def reference_validation_runner_source_sha256() -> str:
    """Return the bootstrap, dependency-helper, and runner source identity."""

    try:
        return reference_validation_execution_source_sha256()
    except RuntimeError as exc:
        raise ReferenceValidationRunnerError(
            "runner execution sources are unavailable"
        ) from exc


def _read_small_regular_text(
    path: Path,
    *,
    name: str,
    maximum_bytes: int = 65_536,
    encoding: str = "ascii",
) -> str:
    try:
        file_stat = path.lstat()
        if (
            path.is_symlink()
            or not stat.S_ISREG(file_stat.st_mode)
            or not 0 < file_stat.st_size <= maximum_bytes
        ):
            raise ReferenceValidationRunnerError(f"{name} is not a small regular file")
        raw = path.read_bytes()
    except OSError as exc:
        raise ReferenceValidationRunnerError(f"{name} cannot be read") from exc
    if len(raw) != file_stat.st_size:
        raise ReferenceValidationRunnerError(f"{name} changed while it was read")
    try:
        return raw.decode(encoding).strip()
    except UnicodeDecodeError as exc:
        raise ReferenceValidationRunnerError(
            f"{name} contains invalid text encoding"
        ) from exc


def _require_safe_git_ref(value: str) -> str:
    if (
        not value.startswith("refs/")
        or value.startswith("refs/.")
        or value.endswith(("/", "."))
        or ".." in value
        or "//" in value
        or not all(
            character.isascii() and (character.isalnum() or character in "/._-")
            for character in value
        )
    ):
        raise ReferenceValidationRunnerError("checked-out Git ref is invalid")
    return value


def _packed_git_ref(common_git_dir: Path, ref_name: str) -> str:
    packed_refs = _read_small_regular_text(
        common_git_dir / "packed-refs",
        name="Git packed refs",
        maximum_bytes=8 * 1024 * 1024,
    )
    matches = []
    for line in packed_refs.splitlines():
        if not line or line.startswith(("#", "^")):
            continue
        try:
            commit_sha, candidate_ref = line.split(" ", 1)
        except ValueError as exc:
            raise ReferenceValidationRunnerError("Git packed refs are invalid") from exc
        if candidate_ref == ref_name:
            matches.append(commit_sha)
    if len(matches) != 1:
        raise ReferenceValidationRunnerError(
            "checked-out Git ref is absent or ambiguous"
        )
    return matches[0]


def _require_no_git_replacement_refs(git_dir: Path, common_git_dir: Path) -> None:
    """Reject loose or packed replacement refs before trusting checkout state."""

    for metadata_root in dict.fromkeys((git_dir, common_git_dir)):
        replacement_root = metadata_root / "refs" / "replace"
        if os.path.lexists(replacement_root):
            raise ReferenceValidationRunnerError(
                "Git replacement refs are not allowed for validation"
            )
    for metadata_root in dict.fromkeys((git_dir, common_git_dir)):
        packed_refs_path = metadata_root / "packed-refs"
        if not os.path.lexists(packed_refs_path):
            continue
        packed_refs = _read_small_regular_text(
            packed_refs_path,
            name="Git packed refs",
            maximum_bytes=8 * 1024 * 1024,
        )
        for line in packed_refs.splitlines():
            if not line or line.startswith(("#", "^")):
                continue
            try:
                _commit_sha, ref_name = line.split(" ", 1)
            except ValueError as exc:
                raise ReferenceValidationRunnerError(
                    "Git packed refs are invalid"
                ) from exc
            if ref_name.startswith("refs/replace/"):
                raise ReferenceValidationRunnerError(
                    "Git replacement refs are not allowed for validation"
                )


def reference_validation_checked_out_code_commit_sha() -> str:
    """Observe the Git HEAD containing the loaded runner without spawning Git."""

    source = Path(__file__).resolve(strict=True)
    repository_root = source.parents[2]
    dot_git = repository_root / ".git"
    if dot_git.is_symlink():
        raise ReferenceValidationRunnerError("Git metadata must not be a symlink")
    if dot_git.is_dir():
        git_dir = dot_git.resolve(strict=True)
    else:
        pointer = _read_small_regular_text(
            dot_git,
            name="Git worktree pointer",
            encoding="utf-8",
        )
        if not pointer.startswith("gitdir: "):
            raise ReferenceValidationRunnerError("Git worktree pointer is invalid")
        candidate = Path(pointer[8:])
        git_dir = (
            candidate if candidate.is_absolute() else repository_root / candidate
        ).resolve(strict=True)
    if not git_dir.is_dir() or git_dir.is_symlink():
        raise ReferenceValidationRunnerError("Git directory is invalid")
    common_git_dir = git_dir
    commondir_path = git_dir / "commondir"
    if commondir_path.exists():
        commondir = _read_small_regular_text(
            commondir_path,
            name="Git common-directory pointer",
            encoding="utf-8",
        )
        candidate = Path(commondir)
        common_git_dir = (
            candidate if candidate.is_absolute() else git_dir / candidate
        ).resolve(strict=True)
        if not common_git_dir.is_dir() or common_git_dir.is_symlink():
            raise ReferenceValidationRunnerError("Git common directory is invalid")

    _require_no_git_replacement_refs(git_dir, common_git_dir)

    head = _read_small_regular_text(git_dir / "HEAD", name="Git HEAD")
    for _ in range(5):
        if not head.startswith("ref: "):
            return _require_commit_sha(head, name="checked-out Git HEAD")
        ref_name = _require_safe_git_ref(head[5:])
        ref_paths = (git_dir / ref_name, common_git_dir / ref_name)
        existing = tuple(dict.fromkeys(path for path in ref_paths if path.exists()))
        if existing:
            if len(existing) != 1:
                raise ReferenceValidationRunnerError("checked-out Git ref is ambiguous")
            head = _read_small_regular_text(existing[0], name="checked-out Git ref")
        else:
            head = _packed_git_ref(common_git_dir, ref_name)
    raise ReferenceValidationRunnerError("checked-out Git ref chain is too deep")


def _require_clean_checked_out_code_commit(expected_commit_sha: str) -> None:
    """Use one constrained local Git status call to prove HEAD has no drift."""

    import subprocess

    expected = _require_commit_sha(
        expected_commit_sha,
        name="clean-checkout expected commit",
    )
    if reference_validation_checked_out_code_commit_sha() != expected:
        raise ReferenceValidationRunnerError(
            "checked-out code commit does not match the clean-checkout request"
        )
    git_executable = Path("/usr/bin/git")
    try:
        executable_stat = git_executable.lstat()
    except OSError as exc:
        raise ReferenceValidationRunnerError(
            "clean-checkout Git executable is unavailable"
        ) from exc
    if (
        git_executable.is_symlink()
        or not stat.S_ISREG(executable_stat.st_mode)
        or executable_stat.st_uid != 0
        or stat.S_IMODE(executable_stat.st_mode) & 0o022
    ):
        raise ReferenceValidationRunnerError(
            "clean-checkout Git executable does not satisfy the trust policy"
        )
    repository_root = Path(__file__).resolve(strict=True).parents[2]
    environment = {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
    }
    try:
        completed = subprocess.run(
            [
                os.fspath(git_executable),
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            cwd=repository_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReferenceValidationRunnerError(
            "clean-checkout Git preflight could not run"
        ) from exc
    if completed.returncode != 0 or completed.stdout:
        raise ReferenceValidationRunnerError(
            "validation checkout is not exactly clean at the authorized commit"
        )


def _force_array_sha256(values: tuple[tuple[float, float, float], ...]) -> str:
    return _sha256(
        {
            "shape": [len(values), 3],
            "dtype": "float64",
            "unit": "kcal/mol/angstrom",
            "values_hex": [[float(value).hex() for value in row] for row in values],
        }
    )


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReferenceValidationRunnerError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ReferenceValidationRunnerError(f"{name} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class ReferenceValidationMetricObservation:
    metric_id: str
    observed: bool
    value: float | bool | None
    unit: str
    threshold_operator: str
    threshold_value: float
    passed: bool

    def __post_init__(self) -> None:
        if type(self.observed) is not bool or type(self.passed) is not bool:
            raise ReferenceValidationRunnerError(
                "metric observation flags must be booleans"
            )
        if not self.metric_id or not self.unit:
            raise ReferenceValidationRunnerError(
                "metric observation identity and unit must be non-empty"
            )
        if type(self.threshold_value) is not float:
            raise ReferenceValidationRunnerError(
                "metric observation threshold must be binary64"
            )
        _finite(self.threshold_value, name="metric threshold")
        if self.threshold_operator not in {"less_than_or_equal", "equal"}:
            raise ReferenceValidationRunnerError(
                "metric observation threshold operator is invalid"
            )
        if self.observed:
            if self.threshold_operator == "equal":
                if type(self.value) is not bool:
                    raise ReferenceValidationRunnerError(
                        "equal metric observation must be boolean"
                    )
                expected_passed = self.value == bool(self.threshold_value)
            else:
                if type(self.value) is not float:
                    raise ReferenceValidationRunnerError(
                        "continuous metric observation must be binary64"
                    )
                numeric_value = _finite(
                    self.value,
                    name="metric observation value",
                )
                if numeric_value < 0.0:
                    raise ReferenceValidationRunnerError(
                        "continuous metric observation must be nonnegative"
                    )
                expected_passed = numeric_value <= self.threshold_value
            if self.passed != expected_passed:
                raise ReferenceValidationRunnerError(
                    "metric observation pass flag contradicts its value and threshold"
                )
        elif self.value is not None or self.passed:
            raise ReferenceValidationRunnerError(
                "missing metric observations cannot contain a value or pass"
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "metric_id": self.metric_id,
            "observed": self.observed,
            "unit": self.unit,
            "threshold_operator": self.threshold_operator,
            "threshold_value": self.threshold_value,
            "passed": self.passed,
        }
        if self.observed:
            payload["value"] = self.value
        else:
            payload["error_code"] = "metric_not_observed"
        return payload


@dataclass(frozen=True, slots=True)
class ReferenceValidationVariantObservation:
    ordinal: int
    variant_id: str
    runtime_input_sha256: str
    oracle_input_sha256: str | None
    observed_status: str
    observed_error_code: str | None
    component_energies_kcal_per_mol: tuple[tuple[str, float], ...] = ()
    total_energy_kcal_per_mol: float | None = None
    forces_kcal_per_mol_angstrom: tuple[tuple[float, float, float], ...] = ()
    force_array_sha256: str | None = None
    oracle_total_energy_kcal_per_mol: float | None = None
    oracle_forces_kcal_per_mol_angstrom: tuple[tuple[float, float, float], ...] = ()
    oracle_force_array_sha256: str | None = None

    def __post_init__(self) -> None:
        if type(self.ordinal) is not int or self.ordinal < 0 or not self.variant_id:
            raise ReferenceValidationRunnerError(
                "variant observation ordinal or identity is invalid"
            )
        _require_sha256(self.runtime_input_sha256, name="variant runtime input")
        if self.oracle_input_sha256 is not None:
            _require_sha256(self.oracle_input_sha256, name="variant oracle input")
        if self.observed_status == "success":
            if self.observed_error_code is not None:
                raise ReferenceValidationRunnerError(
                    "successful variant cannot contain an error code"
                )
            if (
                self.total_energy_kcal_per_mol is None
                or not self.component_energies_kcal_per_mol
                or not self.forces_kcal_per_mol_angstrom
                or self.force_array_sha256 is None
                or self.oracle_total_energy_kcal_per_mol is None
                or not self.oracle_forces_kcal_per_mol_angstrom
                or self.oracle_force_array_sha256 is None
            ):
                raise ReferenceValidationRunnerError(
                    "successful variant observation is incomplete"
                )
            _finite(self.total_energy_kcal_per_mol, name="variant total energy")
            _finite(
                self.oracle_total_energy_kcal_per_mol,
                name="variant oracle total energy",
            )
            for name, value in self.component_energies_kcal_per_mol:
                if not name:
                    raise ReferenceValidationRunnerError(
                        "variant component energy identity is empty"
                    )
                _finite(value, name="variant component energy")
            if tuple(sorted(self.component_energies_kcal_per_mol)) != (
                self.component_energies_kcal_per_mol
            ):
                raise ReferenceValidationRunnerError(
                    "variant component energies must be canonical"
                )
            for array_name, array in (
                ("reference", self.forces_kcal_per_mol_angstrom),
                ("oracle", self.oracle_forces_kcal_per_mol_angstrom),
            ):
                if not array or any(len(row) != 3 for row in array):
                    raise ReferenceValidationRunnerError(
                        f"{array_name} force array shape is invalid"
                    )
                for row in array:
                    for value in row:
                        _finite(value, name=f"{array_name} force component")
            if len(self.forces_kcal_per_mol_angstrom) != len(
                self.oracle_forces_kcal_per_mol_angstrom
            ):
                raise ReferenceValidationRunnerError(
                    "reference and oracle force shapes diverged"
                )
            if self.force_array_sha256 != _force_array_sha256(
                self.forces_kcal_per_mol_angstrom
            ) or self.oracle_force_array_sha256 != _force_array_sha256(
                self.oracle_forces_kcal_per_mol_angstrom
            ):
                raise ReferenceValidationRunnerError(
                    "variant force array identity is cross-wired"
                )
        elif self.observed_status in {
            "fail_closed",
            "unexpected_error",
            "unexpected_success",
            "time_budget_exhausted",
        }:
            if not self.observed_error_code:
                raise ReferenceValidationRunnerError(
                    "non-success variant requires an error code"
                )
            if any(
                (
                    self.component_energies_kcal_per_mol,
                    self.total_energy_kcal_per_mol is not None,
                    self.forces_kcal_per_mol_angstrom,
                    self.force_array_sha256 is not None,
                    self.oracle_total_energy_kcal_per_mol is not None,
                    self.oracle_forces_kcal_per_mol_angstrom,
                    self.oracle_force_array_sha256 is not None,
                )
            ):
                raise ReferenceValidationRunnerError(
                    "non-success variant cannot retain numeric results"
                )
        else:
            raise ReferenceValidationRunnerError(
                "variant observation status is invalid"
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ordinal": self.ordinal,
            "variant_id": self.variant_id,
            "runtime_input_sha256": self.runtime_input_sha256,
            "oracle_input_sha256": self.oracle_input_sha256,
            "observed_status": self.observed_status,
            "observed_error_code": self.observed_error_code,
        }
        if self.observed_status == "success":
            payload.update(
                {
                    "component_energy_values_and_units": [
                        {
                            "name": name,
                            "value": value,
                            "unit": "kcal/mol",
                        }
                        for name, value in self.component_energies_kcal_per_mol
                    ],
                    "total_energy_value": self.total_energy_kcal_per_mol,
                    "total_energy_unit": "kcal/mol",
                    "force_array_shape": [
                        len(self.forces_kcal_per_mol_angstrom),
                        3,
                    ],
                    "force_array_dtype": "float64",
                    "force_array_unit": "kcal/mol/angstrom",
                    "force_array_sha256": self.force_array_sha256,
                    "force_array_values": [
                        list(row) for row in self.forces_kcal_per_mol_angstrom
                    ],
                    "oracle_total_energy_value": (
                        self.oracle_total_energy_kcal_per_mol
                    ),
                    "oracle_total_energy_unit": "kcal/mol",
                    "oracle_force_array_sha256": self.oracle_force_array_sha256,
                    "oracle_force_array_values": [
                        list(row) for row in self.oracle_forces_kcal_per_mol_angstrom
                    ],
                }
            )
        return payload


@dataclass(frozen=True, slots=True)
class ReferenceValidationCaseObservation:
    ordinal: int
    case_id: str
    case_input_sha256: str
    materialization_sha256: str
    expected_outcome: str
    observation_origin: str
    observed_status: str
    expected_error_code: str | None
    observed_error_code: str | None
    variant_results: tuple[ReferenceValidationVariantObservation, ...]
    metric_values: tuple[ReferenceValidationMetricObservation, ...]
    case_passed: bool

    def __post_init__(self) -> None:
        if type(self.case_passed) is not bool:
            raise ReferenceValidationRunnerError("case pass flag must be boolean")
        if type(self.ordinal) is not int or self.ordinal < 0 or not self.case_id:
            raise ReferenceValidationRunnerError(
                "case observation ordinal or identity is invalid"
            )
        if self.observation_origin not in {"worker", "supervisor"}:
            raise ReferenceValidationRunnerError("case observation origin is invalid")
        _require_sha256(self.case_input_sha256, name="case input")
        _require_sha256(self.materialization_sha256, name="case materialization")
        if not self.variant_results:
            raise ReferenceValidationRunnerError(
                "case observation must retain every variant row"
            )
        if tuple(row.ordinal for row in self.variant_results) != tuple(
            range(len(self.variant_results))
        ):
            raise ReferenceValidationRunnerError(
                "case variant observation order is invalid"
            )
        if len({row.variant_id for row in self.variant_results}) != len(
            self.variant_results
        ):
            raise ReferenceValidationRunnerError(
                "case variant observation identities are not unique"
            )
        if len({row.metric_id for row in self.metric_values}) != len(
            self.metric_values
        ):
            raise ReferenceValidationRunnerError(
                "case metric observation identities are not unique"
            )
        if self.expected_outcome == "pass":
            if self.expected_error_code is not None or not self.metric_values:
                raise ReferenceValidationRunnerError(
                    "pass case expectation is incomplete"
                )
            if any(
                row.observed_status
                not in {"success", "unexpected_error", "time_budget_exhausted"}
                for row in self.variant_results
            ):
                raise ReferenceValidationRunnerError(
                    "pass case contains an impossible variant status"
                )
            if any(
                row.observed_status == "time_budget_exhausted"
                for row in self.variant_results
            ):
                derived_status = "time_budget_exhausted"
            elif any(row.observed_status != "success" for row in self.variant_results):
                derived_status = "unexpected_error"
            elif all(row.passed for row in self.metric_values):
                derived_status = "metrics_passed"
            else:
                derived_status = "metric_threshold_failed"
            derived_error = (
                None
                if derived_status in {"metrics_passed", "metric_threshold_failed"}
                else next(
                    (
                        row.observed_error_code
                        for row in self.variant_results
                        if row.observed_error_code is not None
                    ),
                    "metric_not_observed",
                )
            )
        elif self.expected_outcome == "fail_closed":
            if not self.expected_error_code or self.metric_values:
                raise ReferenceValidationRunnerError(
                    "fail-closed case expectation is incomplete"
                )
            if any(
                row.observed_status
                not in {
                    "fail_closed",
                    "unexpected_error",
                    "unexpected_success",
                    "time_budget_exhausted",
                }
                for row in self.variant_results
            ):
                raise ReferenceValidationRunnerError(
                    "fail-closed case contains an impossible variant status"
                )
            error_codes = {row.observed_error_code for row in self.variant_results}
            if all(
                row.observed_status == "fail_closed" for row in self.variant_results
            ) and error_codes == {self.expected_error_code}:
                derived_status = "fail_closed_as_expected"
                derived_error = self.expected_error_code
            elif any(
                row.observed_status == "time_budget_exhausted"
                for row in self.variant_results
            ):
                derived_status = "time_budget_exhausted"
                derived_error = "runner_time_budget_exhausted"
            elif any(
                row.observed_status == "unexpected_success"
                for row in self.variant_results
            ):
                derived_status = "unexpected_success"
                derived_error = "expected_fail_closed_variant_executed"
            else:
                derived_status = "unexpected_error"
                derived_error = (
                    next(iter(error_codes))
                    if len(error_codes) == 1
                    else "multiple_or_unexpected_error_codes"
                )
        else:
            raise ReferenceValidationRunnerError("case expected outcome is invalid")
        if self.observed_status not in {
            "metrics_passed",
            "metric_threshold_failed",
            "fail_closed_as_expected",
            "unexpected_success",
            "unexpected_error",
            "time_budget_exhausted",
        }:
            raise ReferenceValidationRunnerError("case observation status is invalid")
        if (
            self.observed_status != derived_status
            or self.observed_error_code != derived_error
        ):
            raise ReferenceValidationRunnerError(
                "case status or error contradicts its retained variant rows"
            )
        if self.case_passed != (
            derived_status in {"metrics_passed", "fail_closed_as_expected"}
        ):
            raise ReferenceValidationRunnerError(
                "case pass flag and observed status diverged"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "case_id": self.case_id,
            "case_input_sha256": self.case_input_sha256,
            "materialization_sha256": self.materialization_sha256,
            "expected_outcome": self.expected_outcome,
            "observation_origin": self.observation_origin,
            "observed_status": self.observed_status,
            "expected_error_code": self.expected_error_code,
            "observed_error_code": self.observed_error_code,
            "variant_results": [row.to_dict() for row in self.variant_results],
            "metric_values": [row.to_dict() for row in self.metric_values],
            "case_passed": self.case_passed,
        }


def _manifest_worker_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, Mapping):
        raise ReferenceValidationRunnerError(
            "manifest-worker lifecycle manifest is invalid"
        )
    return {
        "ordinal": 0,
        "case_id": "materialization_manifest",
        "materialization_manifest": dict(manifest),
    }


def _lifecycle_evidence_bytes(value: Mapping[str, Any], *, name: str) -> bytes:
    if not isinstance(value, Mapping):
        raise ReferenceValidationRunnerError(f"{name} must be a mapping")
    encoded = _canonical_bytes(dict(value))
    if not encoded:
        raise ReferenceValidationRunnerError(f"{name} is empty")
    return encoded


def _lifecycle_evidence_from_bytes(value: bytes, *, name: str) -> dict[str, Any]:
    if not isinstance(value, bytes) or not value:
        raise ReferenceValidationRunnerError(f"{name} canonical bytes are invalid")
    try:
        payload = json.loads(value.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationRunnerError(
            f"{name} canonical bytes are invalid"
        ) from exc
    if not isinstance(payload, dict) or _canonical_bytes(payload) != value:
        raise ReferenceValidationRunnerError(f"{name} canonical bytes are not exact")
    return payload


def _raw_sha256(value: bytes) -> str:
    if not isinstance(value, bytes):
        raise ReferenceValidationRunnerError("raw SHA-256 input must be bytes")
    return hashlib.sha256(value).hexdigest()


def _canonical_worker_frame_prefix(
    transcript: bytes,
) -> tuple[list[dict[str, Any]], int]:
    """Describe the exact contiguous canonical-frame prefix of one transcript."""

    if not isinstance(transcript, bytes):
        raise ReferenceValidationRunnerError(
            "validation-worker transcript must be bytes"
        )
    sequence: list[dict[str, Any]] = []
    prefix_byte_count = 0
    for index, raw_line in enumerate(transcript.splitlines(keepends=True)):
        try:
            frame = _decode_worker_frame(raw_line)
        except ReferenceValidationRunnerError:
            break
        sequence.append(
            {
                "frame_index": index,
                "frame_type": frame["frame_type"],
                "ordinal": frame.get("ordinal"),
                "worker_kind": frame["worker_kind"],
                "worker_request_sha256": frame["worker_request_sha256"],
                "frame_byte_count": len(raw_line),
                "frame_sha256": _raw_sha256(raw_line),
            }
        )
        prefix_byte_count += len(raw_line)
    return sequence, prefix_byte_count


def _build_worker_execution_provenance(
    *,
    worker_kind: str,
    request: Mapping[str, Any],
    supervisor_launched_child_process_id: int | None,
    transcript: bytes,
    lifecycle: Mapping[str, Any],
    accepted_payload_rows: Sequence[Mapping[str, Any]] | None,
    failure_stage: str | None,
    child_exit_code: int | None,
    timed_out: bool,
    output_overflow: bool,
    communication_failed: bool,
    request_fully_written: bool,
) -> dict[str, Any]:
    """Bind exact supervisor inputs/outputs to one lifecycle without dropping bytes."""

    if worker_kind not in {"manifest", "case"}:
        raise ReferenceValidationRunnerError(
            "validation-worker provenance kind is invalid"
        )
    request_bytes = _canonical_bytes(dict(request)) + b"\n"
    checked_request = _load_case_worker_request(request_bytes)
    if checked_request["worker_kind"] != worker_kind:
        raise ReferenceValidationRunnerError(
            "validation-worker provenance request kind is cross-wired"
        )
    if (
        not isinstance(transcript, bytes)
        or len(transcript) > REFERENCE_VALIDATION_CASE_WORKER_MAX_OUTPUT_BYTES
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker provenance transcript exceeds the fixed bound"
        )
    if supervisor_launched_child_process_id is not None and (
        type(supervisor_launched_child_process_id) is not int
        or supervisor_launched_child_process_id <= 0
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker provenance child process identity is invalid"
        )
    if not isinstance(lifecycle, Mapping):
        raise ReferenceValidationRunnerError(
            "validation-worker provenance lifecycle is invalid"
        )
    frame_sequence, canonical_prefix_byte_count = _canonical_worker_frame_prefix(
        transcript
    )
    completion_state = lifecycle.get("completion_state")
    if completion_state == "complete":
        if accepted_payload_rows is None:
            raise ReferenceValidationRunnerError(
                "complete validation-worker provenance requires retained payload rows"
            )
        request_sha256 = _worker_request_sha256(checked_request)
        reconstructed = b"".join(
            _canonical_bytes(frame) + b"\n"
            for frame in (
                _worker_frame(
                    frame_type="pre",
                    worker_kind=worker_kind,
                    worker_request_sha256=request_sha256,
                    payload=lifecycle["pre"],
                ),
                *(
                    _worker_frame(
                        frame_type="payload",
                        worker_kind=worker_kind,
                        worker_request_sha256=request_sha256,
                        payload=row,
                        ordinal=ordinal,
                    )
                    for ordinal, row in enumerate(accepted_payload_rows)
                ),
                _worker_frame(
                    frame_type="completion",
                    worker_kind=worker_kind,
                    worker_request_sha256=request_sha256,
                    payload=lifecycle,
                ),
            )
        )
        if transcript != reconstructed:
            raise ReferenceValidationRunnerError(
                "complete validation-worker raw transcript differs from reconstruction"
            )
    elif accepted_payload_rows is not None:
        raise ReferenceValidationRunnerError(
            "incomplete validation-worker provenance cannot accept payload rows"
        )
    if (
        (failure_stage is not None and not isinstance(failure_stage, str))
        or type(timed_out) is not bool
        or type(output_overflow) is not bool
        or type(communication_failed) is not bool
        or type(request_fully_written) is not bool
        or (child_exit_code is not None and type(child_exit_code) is not int)
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker termination provenance is invalid"
        )
    payload_prefix_count = sum(row["frame_type"] == "payload" for row in frame_sequence)
    trailing_fragment_byte_count = (
        len(transcript.rsplit(b"\n", 1)[-1]) if not transcript.endswith(b"\n") else 0
    )
    projection: dict[str, Any] = {
        "schema_id": REFERENCE_VALIDATION_WORKER_EXECUTION_PROVENANCE_SCHEMA_ID,
        "worker_kind": worker_kind,
        "worker_request_canonical_jsonl_hex": request_bytes.hex(),
        "worker_request_byte_count": len(request_bytes),
        "worker_request_sha256": _worker_request_sha256(checked_request),
        "worker_request_transport_sha256": _raw_sha256(request_bytes),
        "supervisor_launched_child_process_id": (supervisor_launched_child_process_id),
        "transcript_byte_count": len(transcript),
        "transcript_sha256": _raw_sha256(transcript),
        "canonical_frame_sequence": frame_sequence,
        "parsed_prefix_frame_count": len(frame_sequence),
        "canonical_prefix_byte_count": canonical_prefix_byte_count,
        "discarded_suffix_byte_count": len(transcript) - canonical_prefix_byte_count,
        "trailing_fragment_byte_count": trailing_fragment_byte_count,
        "discarded_payload_frame_count": (
            0 if completion_state == "complete" else payload_prefix_count
        ),
        "accepted_payload_frame_count": (
            payload_prefix_count if completion_state == "complete" else 0
        ),
        "lifecycle_evidence_sha256": _sha256(dict(lifecycle)),
        "completion_state": completion_state,
        "failure_code": lifecycle.get("failure_code"),
        "failure_stage": failure_stage,
        "child_exit_code": child_exit_code,
        "timed_out": timed_out,
        "output_overflow": output_overflow,
        "communication_failed": communication_failed,
        "request_fully_written": request_fully_written,
        "raw_partial_not_independently_replayable": completion_state == "incomplete",
        "partial_worker_payload_accepted": False,
    }
    projection["provenance_sha256"] = _sha256(projection)
    return projection


def _worker_execution_provenance_bytes(value: Mapping[str, Any], *, name: str) -> bytes:
    if not isinstance(value, Mapping):
        raise ReferenceValidationRunnerError(f"{name} must be a mapping")
    encoded = _canonical_bytes(dict(value))
    if not encoded:
        raise ReferenceValidationRunnerError(f"{name} is empty")
    return encoded


def _worker_execution_provenance_from_bytes(
    value: bytes, *, name: str
) -> dict[str, Any]:
    if not isinstance(value, bytes) or not value:
        raise ReferenceValidationRunnerError(f"{name} canonical bytes are invalid")
    try:
        payload = json.loads(value.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationRunnerError(
            f"{name} canonical bytes are invalid"
        ) from exc
    if not isinstance(payload, dict) or _canonical_bytes(payload) != value:
        raise ReferenceValidationRunnerError(f"{name} canonical bytes are not exact")
    return payload


def _decode_lower_hex_bytes(value: object, *, name: str, maximum: int) -> bytes:
    if (
        not isinstance(value, str)
        or len(value) % 2
        or len(value) > maximum * 2
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceValidationRunnerError(f"{name} is not bounded lowercase hex")
    return bytes.fromhex(value)


def require_reference_validation_worker_execution_provenance_document(
    payload: Mapping[str, Any],
    *,
    lifecycle: Mapping[str, Any],
    expected_worker_kind: str,
    expected_code_commit_sha: str,
    expected_runner_source_sha256: str,
    expected_source_manifest_sha256: str,
    expected_dependency_artifact_sha256_rows: Mapping[str, str]
    | Sequence[tuple[str, str]],
    expected_environment_receipt_sha256: str,
    expected_environment_fingerprint_sha256: str,
    expected_authorization_nonce_sha256: str,
    expected_runner_start_record_sha256: str | None,
    expected_application_seed: int,
    expected_materialization_manifest_sha256: str | None,
    expected_payload_rows: Sequence[Mapping[str, Any]] | None,
    expected_python_hash_seed: int | None = None,
    expected_worker_environment: Mapping[str, str] | None = None,
    expected_dependency_roots: Sequence[Path] | None = None,
    expected_python_hash_probe_sha256: str | None = None,
) -> dict[str, Any]:
    """Reparse exact request/transcript bytes and bind them to outer run identity."""

    if not isinstance(payload, Mapping) or not isinstance(lifecycle, Mapping):
        raise ReferenceValidationRunnerError(
            "validation-worker execution provenance must be mappings"
        )
    observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    expected_fields = {
        "schema_id",
        "worker_kind",
        "worker_request_canonical_jsonl_hex",
        "worker_request_byte_count",
        "worker_request_sha256",
        "worker_request_transport_sha256",
        "supervisor_launched_child_process_id",
        "transcript_byte_count",
        "transcript_sha256",
        "canonical_frame_sequence",
        "parsed_prefix_frame_count",
        "canonical_prefix_byte_count",
        "discarded_suffix_byte_count",
        "trailing_fragment_byte_count",
        "discarded_payload_frame_count",
        "accepted_payload_frame_count",
        "lifecycle_evidence_sha256",
        "completion_state",
        "failure_code",
        "failure_stage",
        "child_exit_code",
        "timed_out",
        "output_overflow",
        "communication_failed",
        "request_fully_written",
        "raw_partial_not_independently_replayable",
        "partial_worker_payload_accepted",
        "provenance_sha256",
    }
    if (
        set(observed) != expected_fields
        or observed.get("schema_id")
        != REFERENCE_VALIDATION_WORKER_EXECUTION_PROVENANCE_SCHEMA_ID
        or observed.get("worker_kind") != expected_worker_kind
        or observed.get("partial_worker_payload_accepted") is not False
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker execution provenance fields are invalid"
        )
    projection = dict(observed)
    provenance_sha256 = _require_sha256(
        projection.pop("provenance_sha256", None),
        name="validation-worker execution provenance",
    )
    if provenance_sha256 != _sha256(projection):
        raise ReferenceValidationRunnerError(
            "validation-worker execution provenance SHA-256 drifted"
        )

    request_bytes = _decode_lower_hex_bytes(
        observed["worker_request_canonical_jsonl_hex"],
        name="validation-worker canonical request",
        maximum=REFERENCE_VALIDATION_CASE_WORKER_MAX_REQUEST_BYTES,
    )
    if observed.get("worker_request_byte_count") != len(request_bytes) or observed.get(
        "worker_request_transport_sha256"
    ) != _raw_sha256(request_bytes):
        raise ReferenceValidationRunnerError(
            "validation-worker request transport identity drifted"
        )
    request = _load_case_worker_request(request_bytes)
    request_sha256 = _worker_request_sha256(request)
    normalized_dependencies = dict(
        _normalize_dependency_rows(expected_dependency_artifact_sha256_rows)
    )
    expected_materialization = (
        None
        if expected_worker_kind == "manifest"
        else _require_sha256(
            expected_materialization_manifest_sha256,
            name="validation-worker expected materialization",
        )
    )
    expected_runner_start = (
        None
        if expected_worker_kind == "manifest"
        else _require_sha256(
            expected_runner_start_record_sha256,
            name="validation-worker expected runner start",
        )
    )
    request_environment = request["expected_worker_environment"]
    request_dependency_roots = request["dependency_roots"]
    request_python_hash_seed = request["expected_python_hash_seed"]
    request_application_seed = _require_worker_seed(
        expected_application_seed,
        name="validation-worker outer application seed",
        maximum=2**63 - 1,
    )
    dependency_roots_are_canonical = len(set(request_dependency_roots)) == len(
        request_dependency_roots
    ) and all(
        Path(root).is_absolute()
        and os.path.normpath(root) == root
        and os.pathsep not in root
        for root in request_dependency_roots
    )
    if (
        not dependency_roots_are_canonical
        or request_environment.get("PYTHONPATH")
        != os.pathsep.join(request_dependency_roots)
        or request_environment.get("PYTHONHASHSEED") != str(request_python_hash_seed)
        or request_environment.get(REFERENCE_VALIDATION_APPLICATION_SEED_ENV)
        != str(request_application_seed)
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker request environment is internally cross-wired"
        )

    trusted_worker_environment: dict[str, str] | None = None
    trusted_dependency_roots: list[str] | None = None
    trusted_python_hash_seed: int | None = None
    trusted_python_hash_probe_sha256: str | None = None
    if expected_worker_environment is not None:
        trusted_worker_environment = dict(expected_worker_environment)
        if set(
            trusted_worker_environment
        ) != _REFERENCE_VALIDATION_WORKER_ENVIRONMENT_NAMES or any(
            not isinstance(name, str) or not isinstance(value, str)
            for name, value in trusted_worker_environment.items()
        ):
            raise ReferenceValidationRunnerError(
                "validation-worker trusted environment is invalid"
            )
    if expected_dependency_roots is not None:
        trusted_dependency_roots = [
            os.fspath(root) for root in expected_dependency_roots
        ]
        if (
            not trusted_dependency_roots
            or len(set(trusted_dependency_roots)) != len(trusted_dependency_roots)
            or any(
                not isinstance(root, str)
                or not Path(root).is_absolute()
                or os.path.normpath(root) != root
                or os.pathsep in root
                for root in trusted_dependency_roots
            )
        ):
            raise ReferenceValidationRunnerError(
                "validation-worker trusted dependency roots are invalid"
            )
    if expected_python_hash_seed is not None:
        trusted_python_hash_seed = _require_worker_seed(
            expected_python_hash_seed,
            name="validation-worker trusted Python hash seed",
            maximum=2**32 - 1,
        )
    if expected_python_hash_probe_sha256 is not None:
        trusted_python_hash_probe_sha256 = _require_sha256(
            expected_python_hash_probe_sha256,
            name="validation-worker trusted Python hash probe",
        )
    if (
        observed.get("worker_request_sha256") != request_sha256
        or request["worker_kind"] != expected_worker_kind
        or request["expected_code_commit_sha"]
        != _require_commit_sha(
            expected_code_commit_sha,
            name="validation-worker outer commit",
        )
        or request["expected_runner_source_sha256"]
        != _require_sha256(
            expected_runner_source_sha256,
            name="validation-worker outer source",
        )
        or request["expected_source_manifest_sha256"]
        != _require_sha256(
            expected_source_manifest_sha256,
            name="validation-worker outer source manifest",
        )
        or request["expected_dependency_artifact_sha256_rows"]
        != normalized_dependencies
        or request["expected_environment_receipt_sha256"]
        != _require_sha256(
            expected_environment_receipt_sha256,
            name="validation-worker outer environment receipt",
        )
        or request["expected_environment_fingerprint_sha256"]
        != _require_sha256(
            expected_environment_fingerprint_sha256,
            name="validation-worker outer environment fingerprint",
        )
        or request["expected_authorization_nonce_sha256"]
        != _require_sha256(
            expected_authorization_nonce_sha256,
            name="validation-worker outer authorization nonce",
        )
        or request["expected_runner_start_record_sha256"] != expected_runner_start
        or request["expected_application_seed"] != request_application_seed
        or request["expected_materialization_manifest_sha256"]
        != expected_materialization
        or request["expected_worker_environment_sha256"]
        != _sha256(request["expected_worker_environment"])
        or (
            trusted_python_hash_seed is not None
            and request_python_hash_seed != trusted_python_hash_seed
        )
        or (
            trusted_worker_environment is not None
            and request_environment != trusted_worker_environment
        )
        or (
            trusted_dependency_roots is not None
            and request_dependency_roots != trusted_dependency_roots
        )
        or (
            trusted_python_hash_probe_sha256 is not None
            and request["expected_python_hash_probe_sha256"]
            != trusted_python_hash_probe_sha256
        )
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker request is cross-wired to the run observation"
        )

    transcript_byte_count = observed.get("transcript_byte_count")
    _require_sha256(
        observed.get("transcript_sha256"),
        name="validation-worker transcript",
    )
    prefix_byte_count = observed.get("canonical_prefix_byte_count")
    frame_sequence = observed.get("canonical_frame_sequence")
    frame_sequence_valid = (
        isinstance(frame_sequence, list)
        and len(frame_sequence) <= REFERENCE_VALIDATION_RUNNER_MAX_CASES + 2
    )
    if frame_sequence_valid:
        for index, frame_row in enumerate(frame_sequence):
            if (
                not isinstance(frame_row, dict)
                or set(frame_row)
                != {
                    "frame_index",
                    "frame_type",
                    "ordinal",
                    "worker_kind",
                    "worker_request_sha256",
                    "frame_byte_count",
                    "frame_sha256",
                }
                or frame_row.get("frame_index") != index
                or frame_row.get("frame_type") not in {"pre", "payload", "completion"}
                or frame_row.get("worker_kind") != expected_worker_kind
                or frame_row.get("worker_request_sha256") != request_sha256
                or type(frame_row.get("frame_byte_count")) is not int
                or frame_row["frame_byte_count"] <= 0
            ):
                frame_sequence_valid = False
                break
            _require_sha256(
                frame_row.get("frame_sha256"),
                name="validation-worker frame",
            )
    if (
        type(transcript_byte_count) is not int
        or not 0
        <= transcript_byte_count
        <= REFERENCE_VALIDATION_CASE_WORKER_MAX_OUTPUT_BYTES
        or type(prefix_byte_count) is not int
        or not 0 <= prefix_byte_count <= transcript_byte_count
        or not frame_sequence_valid
        or observed.get("parsed_prefix_frame_count") != len(frame_sequence)
        or prefix_byte_count != sum(row["frame_byte_count"] for row in frame_sequence)
        or observed.get("discarded_suffix_byte_count")
        != transcript_byte_count - prefix_byte_count
        or type(observed.get("trailing_fragment_byte_count")) is not int
        or not 0
        <= observed["trailing_fragment_byte_count"]
        <= observed["discarded_suffix_byte_count"]
        or observed.get("lifecycle_evidence_sha256") != _sha256(dict(lifecycle))
        or observed.get("completion_state") != lifecycle.get("completion_state")
        or observed.get("failure_code") != lifecycle.get("failure_code")
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker transcript or lifecycle provenance drifted"
        )

    expected_lane = (
        WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST
        if expected_worker_kind == "manifest"
        else WORKER_RUNTIME_LANE_ENERGY_FORCE
    )
    completion_state = lifecycle.get("completion_state")
    try:
        checked_lifecycle = require_worker_runtime_lifecycle_evidence(
            lifecycle,
            expected_lane=expected_lane,
            expected_worker_request_sha256=request_sha256,
            expected_payload_rows=(
                expected_payload_rows if completion_state == "complete" else None
            ),
        )
    except ValidationNativeRuntimeIdentityError as exc:
        raise ReferenceValidationRunnerError(
            "validation-worker provenance lifecycle is invalid"
        ) from exc

    process_id = observed.get("supervisor_launched_child_process_id")
    if completion_state == "complete":
        request_sha256 = _worker_request_sha256(request)
        reconstructed = b"".join(
            _canonical_bytes(frame) + b"\n"
            for frame in (
                _worker_frame(
                    frame_type="pre",
                    worker_kind=expected_worker_kind,
                    worker_request_sha256=request_sha256,
                    payload=checked_lifecycle["pre"],
                ),
                *(
                    _worker_frame(
                        frame_type="payload",
                        worker_kind=expected_worker_kind,
                        worker_request_sha256=request_sha256,
                        payload=row,
                        ordinal=ordinal,
                    )
                    for ordinal, row in enumerate(expected_payload_rows or ())
                ),
                _worker_frame(
                    frame_type="completion",
                    worker_kind=expected_worker_kind,
                    worker_request_sha256=request_sha256,
                    payload=checked_lifecycle,
                ),
            )
        )
        reconstructed_sequence, reconstructed_prefix = _canonical_worker_frame_prefix(
            reconstructed
        )
        if (
            type(process_id) is not int
            or process_id <= 0
            or expected_payload_rows is None
            or prefix_byte_count != transcript_byte_count
            or transcript_byte_count != len(reconstructed)
            or observed.get("transcript_sha256") != _raw_sha256(reconstructed)
            or frame_sequence != reconstructed_sequence
            or reconstructed_prefix != len(reconstructed)
            or observed.get("discarded_suffix_byte_count") != 0
            or observed.get("trailing_fragment_byte_count") != 0
            or observed.get("discarded_payload_frame_count") != 0
            or observed.get("accepted_payload_frame_count")
            != len(expected_payload_rows)
            or observed.get("failure_stage") is not None
            or observed.get("child_exit_code") != 0
            or observed.get("timed_out") is not False
            or observed.get("output_overflow") is not False
            or observed.get("communication_failed") is not False
            or observed.get("request_fully_written") is not True
            or observed.get("raw_partial_not_independently_replayable") is not False
        ):
            raise ReferenceValidationRunnerError(
                "complete validation-worker provenance is incomplete"
            )
        try:
            require_complete_worker_runtime_process_id(
                checked_lifecycle,
                expected_process_id=process_id,
            )
        except ValidationNativeRuntimeIdentityError as exc:
            raise ReferenceValidationRunnerError(
                "validation-worker provenance process identity is invalid"
            ) from exc
        frames = reconstructed.splitlines(keepends=True)
        expected_frame_count = len(expected_payload_rows) + 2
        if len(frames) != expected_frame_count:
            raise ReferenceValidationRunnerError(
                "complete validation-worker transcript frame count drifted"
            )
        pre_evidence = _require_worker_pre_frame(
            _decode_worker_frame(frames[0]),
            worker_kind=expected_worker_kind,
            worker_request_sha256=request_sha256,
            lane=expected_lane,
        )
        if pre_evidence != checked_lifecycle["pre"]:
            raise ReferenceValidationRunnerError(
                "validation-worker transcript pre evidence is cross-wired"
            )
        for ordinal, (raw_line, expected_row) in enumerate(
            zip(frames[1:-1], expected_payload_rows, strict=True)
        ):
            frame = _require_worker_frame_binding(
                _decode_worker_frame(raw_line),
                frame_type="payload",
                worker_kind=expected_worker_kind,
                worker_request_sha256=request_sha256,
                ordinal=ordinal,
            )
            if frame["payload"] != dict(expected_row):
                raise ReferenceValidationRunnerError(
                    "validation-worker transcript payload is cross-wired"
                )
        completion = _require_worker_frame_binding(
            _decode_worker_frame(frames[-1]),
            frame_type="completion",
            worker_kind=expected_worker_kind,
            worker_request_sha256=request_sha256,
        )
        if completion["evidence"] != checked_lifecycle:
            raise ReferenceValidationRunnerError(
                "validation-worker transcript completion evidence is cross-wired"
            )
    elif completion_state == "incomplete":
        failure_code = checked_lifecycle["failure_code"]
        if expected_worker_kind != "case" or failure_code not in (
            _CASE_WORKER_INCOMPLETE_FAILURE_CODES
        ):
            raise ReferenceValidationRunnerError(
                "incomplete validation-worker provenance is unsupported"
            )
        if (
            observed.get("accepted_payload_frame_count") != 0
            or observed.get("discarded_payload_frame_count")
            != sum(row.get("frame_type") == "payload" for row in frame_sequence)
            or observed.get("raw_partial_not_independently_replayable") is not True
            or not isinstance(observed.get("failure_stage"), str)
            or type(observed.get("timed_out")) is not bool
            or type(observed.get("output_overflow")) is not bool
            or type(observed.get("communication_failed")) is not bool
            or type(observed.get("request_fully_written")) is not bool
            or (
                observed.get("child_exit_code") is not None
                and type(observed.get("child_exit_code")) is not int
            )
        ):
            raise ReferenceValidationRunnerError(
                "incomplete validation-worker discard provenance is invalid"
            )
        if failure_code == "case_worker_start_failed":
            if (
                process_id is not None
                or transcript_byte_count != 0
                or observed.get("transcript_sha256") != _raw_sha256(b"")
                or observed.get("failure_stage") != "worker_start"
                or observed.get("child_exit_code") is not None
                or observed.get("timed_out") is not False
                or observed.get("output_overflow") is not False
                or observed.get("communication_failed") is not False
                or observed.get("request_fully_written") is not False
            ):
                raise ReferenceValidationRunnerError(
                    "unstarted validation-worker retained process output"
                )
        elif type(process_id) is not int or process_id <= 0:
            raise ReferenceValidationRunnerError(
                "started validation-worker process identity is missing"
            )
        if (
            checked_lifecycle["pre"] is not None
            and checked_lifecycle["pre"]["snapshot"]["process_id"] != process_id
        ):
            raise ReferenceValidationRunnerError(
                "incomplete validation-worker process identity is cross-wired"
            )
    else:
        raise ReferenceValidationRunnerError(
            "validation-worker provenance completion state is invalid"
        )
    return observed


@dataclass(frozen=True, slots=True)
class ReferenceValidationRunObservation:
    runner_start_record_sha256: str
    execution_environment_receipt_sha256: str
    environment_fingerprint_sha256: str
    authorization_receipt_sha256: str
    authorization_nonce_sha256: str
    code_commit_sha: str
    runner_source_sha256: str
    source_manifest_sha256: str
    dependency_artifact_sha256_rows: tuple[tuple[str, str], ...]
    command_argv: tuple[str, ...]
    seed: int
    started_at_utc: str
    completed_at_utc: str
    case_results: tuple[ReferenceValidationCaseObservation, ...]
    manifest_worker_lifecycle_evidence_bytes: bytes
    case_worker_lifecycle_evidence_bytes: bytes
    manifest_worker_execution_provenance_bytes: bytes
    case_worker_execution_provenance_bytes: bytes
    retained_case_payload_aggregate_sha256: str
    blockers: tuple[str, ...] = _POST_RUN_BLOCKERS

    def __post_init__(self) -> None:
        for name, value in (
            ("runner start record", self.runner_start_record_sha256),
            ("environment receipt", self.execution_environment_receipt_sha256),
            ("environment fingerprint", self.environment_fingerprint_sha256),
            ("authorization receipt", self.authorization_receipt_sha256),
            ("authorization nonce", self.authorization_nonce_sha256),
            ("runner source", self.runner_source_sha256),
            ("source manifest", self.source_manifest_sha256),
        ):
            _require_sha256(value, name=name)
        _require_commit_sha(self.code_commit_sha, name="run observation code commit")
        if self.command_argv != REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV:
            raise ReferenceValidationRunnerError("run observation argv drifted")
        if type(self.seed) is not int or not 0 <= self.seed <= 2**63 - 1:
            raise ReferenceValidationRunnerError("run observation seed is invalid")
        if _normalize_dependency_rows(self.dependency_artifact_sha256_rows) != (
            self.dependency_artifact_sha256_rows
        ):
            raise ReferenceValidationRunnerError(
                "run observation dependency rows drifted"
            )
        started = _parse_utc(self.started_at_utc, name="run started_at")
        completed = _parse_utc(self.completed_at_utc, name="run completed_at")
        if completed < started:
            raise ReferenceValidationRunnerError("run completion precedes its start")
        if len(self.case_results) != REFERENCE_VALIDATION_RUNNER_MAX_CASES:
            raise ReferenceValidationRunnerError(
                "run observation must retain all twenty-seven cases"
            )
        if tuple(row.ordinal for row in self.case_results) != tuple(
            range(REFERENCE_VALIDATION_RUNNER_MAX_CASES)
        ):
            raise ReferenceValidationRunnerError("run observation case order drifted")
        protocol_cases = frozen_cpu_reference_validation_protocol().cases
        expected_case_rows = tuple(
            (
                row.case_id,
                row.input_sha256,
                row.expected_outcome,
                row.expected_error_code,
            )
            for row in protocol_cases
        )
        observed_case_rows = tuple(
            (
                row.case_id,
                row.case_input_sha256,
                row.expected_outcome,
                row.expected_error_code,
            )
            for row in self.case_results
        )
        if observed_case_rows != expected_case_rows:
            raise ReferenceValidationRunnerError(
                "run observation cases do not match the frozen protocol"
            )
        if sum(len(row.variant_results) for row in self.case_results) != (
            REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
        ):
            raise ReferenceValidationRunnerError(
                "run observation must retain all fifty-nine variants"
            )
        manifest_protocol, manifest = _load_frozen_case_manifest_document()
        manifest_cases = manifest["cases"]
        for ordinal, (row, case, manifest_case) in enumerate(
            zip(
                self.case_results,
                manifest_protocol.cases,
                manifest_cases,
                strict=True,
            )
        ):
            _require_case_matches_frozen_matrix(row, ordinal, case, manifest_case)
        retained_payload_rows = [row.to_dict() for row in self.case_results]
        if self.retained_case_payload_aggregate_sha256 != _sha256(
            retained_payload_rows
        ):
            raise ReferenceValidationRunnerError(
                "run observation retained case payload aggregate drifted"
            )
        manifest_lifecycle = _lifecycle_evidence_from_bytes(
            self.manifest_worker_lifecycle_evidence_bytes,
            name="manifest-worker lifecycle evidence",
        )
        case_lifecycle = _lifecycle_evidence_from_bytes(
            self.case_worker_lifecycle_evidence_bytes,
            name="case-worker lifecycle evidence",
        )
        manifest_provenance = _worker_execution_provenance_from_bytes(
            self.manifest_worker_execution_provenance_bytes,
            name="manifest-worker execution provenance",
        )
        case_provenance = _worker_execution_provenance_from_bytes(
            self.case_worker_execution_provenance_bytes,
            name="case-worker execution provenance",
        )
        try:
            require_reference_validation_worker_execution_provenance_document(
                manifest_provenance,
                lifecycle=manifest_lifecycle,
                expected_worker_kind="manifest",
                expected_code_commit_sha=self.code_commit_sha,
                expected_runner_source_sha256=self.runner_source_sha256,
                expected_source_manifest_sha256=self.source_manifest_sha256,
                expected_dependency_artifact_sha256_rows=(
                    self.dependency_artifact_sha256_rows
                ),
                expected_environment_receipt_sha256=(
                    self.execution_environment_receipt_sha256
                ),
                expected_environment_fingerprint_sha256=(
                    self.environment_fingerprint_sha256
                ),
                expected_authorization_nonce_sha256=self.authorization_nonce_sha256,
                expected_runner_start_record_sha256=None,
                expected_application_seed=self.seed,
                expected_materialization_manifest_sha256=None,
                expected_payload_rows=[_manifest_worker_payload(manifest)],
            )
            require_reference_validation_worker_execution_provenance_document(
                case_provenance,
                lifecycle=case_lifecycle,
                expected_worker_kind="case",
                expected_code_commit_sha=self.code_commit_sha,
                expected_runner_source_sha256=self.runner_source_sha256,
                expected_source_manifest_sha256=self.source_manifest_sha256,
                expected_dependency_artifact_sha256_rows=(
                    self.dependency_artifact_sha256_rows
                ),
                expected_environment_receipt_sha256=(
                    self.execution_environment_receipt_sha256
                ),
                expected_environment_fingerprint_sha256=(
                    self.environment_fingerprint_sha256
                ),
                expected_authorization_nonce_sha256=self.authorization_nonce_sha256,
                expected_runner_start_record_sha256=self.runner_start_record_sha256,
                expected_application_seed=self.seed,
                expected_materialization_manifest_sha256=manifest[
                    "materialization_manifest_sha256"
                ],
                expected_payload_rows=(
                    retained_payload_rows
                    if case_lifecycle.get("completion_state") == "complete"
                    else None
                ),
            )
        except (
            ReferenceValidationRunnerError,
            ValidationNativeRuntimeIdentityError,
        ) as exc:
            raise ReferenceValidationRunnerError(
                "run observation worker execution provenance is invalid"
            ) from exc
        if manifest_lifecycle["completion_state"] != "complete":
            raise ReferenceValidationRunnerError(
                "run observation manifest-worker lifecycle is incomplete"
            )
        if case_lifecycle["completion_state"] == "complete":
            if any(row.observation_origin != "worker" for row in self.case_results):
                raise ReferenceValidationRunnerError(
                    "complete case-worker lifecycle contains supervisor-generated rows"
                )
        else:
            failure_code = case_lifecycle["failure_code"]
            if failure_code not in _CASE_WORKER_INCOMPLETE_FAILURE_CODES:
                raise ReferenceValidationRunnerError(
                    "incomplete case-worker lifecycle failure code is unsupported"
                )
            expected_status = (
                "time_budget_exhausted"
                if failure_code == "runner_time_budget_exhausted"
                else "unexpected_error"
            )
            if any(
                row.observation_origin != "supervisor"
                or row.observed_status != expected_status
                or row.observed_error_code != failure_code
                or row.case_passed
                or any(
                    variant.observed_status != expected_status
                    or variant.observed_error_code != failure_code
                    for variant in row.variant_results
                )
                for row in self.case_results
            ):
                raise ReferenceValidationRunnerError(
                    "incomplete case-worker lifecycle did not produce one failure-complete supervisor matrix"
                )
        if self.blockers != _POST_RUN_BLOCKERS:
            raise ReferenceValidationRunnerError(
                "run observation downstream blockers drifted"
            )

    @property
    def observation_sha256(self) -> str:
        return _sha256(self.projection())

    def projection(self) -> dict[str, Any]:
        passed = sum(row.case_passed for row in self.case_results)
        return {
            "schema_id": REFERENCE_VALIDATION_RUN_OBSERVATION_SCHEMA_ID,
            "runner_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256
            ),
            "result_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
            ),
            "protocol_sha256": FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
            "run_start_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_RUN_START_CONTRACT_SHA256
            ),
            "runner_start_record_sha256": self.runner_start_record_sha256,
            "execution_environment_receipt_sha256": (
                self.execution_environment_receipt_sha256
            ),
            "environment_fingerprint_sha256": self.environment_fingerprint_sha256,
            "authorization_receipt_sha256": self.authorization_receipt_sha256,
            "authorization_nonce_sha256": self.authorization_nonce_sha256,
            "code_commit_sha": self.code_commit_sha,
            "runner_source_sha256": self.runner_source_sha256,
            "source_manifest_sha256": self.source_manifest_sha256,
            "dependency_artifact_sha256_rows": [
                {"artifact_id": artifact_id, "sha256": digest}
                for artifact_id, digest in self.dependency_artifact_sha256_rows
            ],
            "command_argv": list(self.command_argv),
            "seed": self.seed,
            "started_at_utc": self.started_at_utc,
            "completed_at_utc": self.completed_at_utc,
            "case_results": [row.to_dict() for row in self.case_results],
            "manifest_worker_lifecycle_evidence": _lifecycle_evidence_from_bytes(
                self.manifest_worker_lifecycle_evidence_bytes,
                name="manifest-worker lifecycle evidence",
            ),
            "case_worker_lifecycle_evidence": _lifecycle_evidence_from_bytes(
                self.case_worker_lifecycle_evidence_bytes,
                name="case-worker lifecycle evidence",
            ),
            "manifest_worker_execution_provenance": (
                _worker_execution_provenance_from_bytes(
                    self.manifest_worker_execution_provenance_bytes,
                    name="manifest-worker execution provenance",
                )
            ),
            "case_worker_execution_provenance": (
                _worker_execution_provenance_from_bytes(
                    self.case_worker_execution_provenance_bytes,
                    name="case-worker execution provenance",
                )
            ),
            "retained_case_payload_aggregate_sha256": self.retained_case_payload_aggregate_sha256,
            "coverage_summary": {
                "case_count": len(self.case_results),
                "variant_count": sum(
                    len(row.variant_results) for row in self.case_results
                ),
                "case_pass_count": passed,
                "case_failure_count": len(self.case_results) - passed,
                "all_cases_retained": True,
                "all_variants_retained": True,
                "skipped_cases": 0,
            },
            "in_memory_observation_created": True,
            "production_validation_results_collected": False,
            "result_receipt_written": False,
            "parameter_fitting_proposal_authorized": False,
            "parameter_fitting_authorized": False,
            "scientifically_validated": False,
            "claim_safe": False,
            "blockers": list(self.blockers),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.projection()
        payload["observation_sha256"] = self.observation_sha256
        return payload


def _closed_claim_policy() -> dict[str, bool]:
    return {
        "bounded_validation_runner_implemented": True,
        "production_validation_execution_authorized": False,
        "production_validation_results_collected": False,
        "result_receipt_writer_implemented": True,
        "force_or_energy_validated": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _contract_projection() -> dict[str, Any]:
    return {
        "schema_id": REFERENCE_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID,
        "contract_id": REFERENCE_VALIDATION_RUNNER_CONTRACT_ID,
        "contract_version": REFERENCE_VALIDATION_RUNNER_CONTRACT_VERSION,
        "frozen_at_utc": REFERENCE_VALIDATION_RUNNER_CONTRACT_FROZEN_AT_UTC,
        "superseded_contract_sha256": (
            FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V6
        ),
        "legacy_contract_chain_sha256s": [
            FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V5,
            FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V4,
            FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V3,
            FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V2,
            FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V1,
        ],
        "refreeze_reason": (
            "bind_energy_force_protocol_result_and_run_start_contracts_"
            "without_execution_bound_change"
        ),
        "purpose": {
            "lane": "synthetic_implementation_mathematics_only",
            "bounded_runner_primitive_only": True,
            "production_execution_performed": False,
            "production_results_collected": False,
            "result_receipt_written": False,
        },
        "dependencies": {
            "protocol_sha256": FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
            "result_receipt_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_RESULT_RECEIPT_CONTRACT_SHA256
            ),
            "run_start_contract_sha256": (
                FROZEN_REFERENCE_VALIDATION_RUN_START_CONTRACT_SHA256
            ),
        },
        "preflight": {
            "persisted_environment_receipt_reread_required": True,
            "live_environment_fingerprint_reverification_required": True,
            "maximum_environment_receipt_age_seconds": int(
                REFERENCE_VALIDATION_RUNNER_MAX_RECEIPT_AGE.total_seconds()
            ),
            "exact_code_runner_source_dependency_identity_required": True,
            "bootstrap_source_manifest_reverified_and_carried": True,
            "actual_checked_out_git_head_required": True,
            "frozen_reference_evaluator_source_required": True,
            "frozen_artifact_binding_reverification_required": True,
            "source_only_python_import_runtime_required": True,
            "ignored_timestamp_bytecode_cache_execution_allowed": False,
            "stdlib_only_bootstrap_before_dependency_imports_required": True,
            "dependency_payload_bytes_remeasured_before_package_import": True,
            "dependency_payload_bytes_remeasured_in_parent": True,
            "active_import_origin_bound_to_distribution_record": True,
            "trusted_isolated_outer_launcher_required": True,
            "seeded_controlled_inner_exec_required": True,
            "python_hash_seed_applied_at_interpreter_initialization": True,
            "pythonpath_user_site_and_pth_startup_allowed": False,
            "bootstrap_source_bound_to_runner_source_sha256": True,
            "signed_clean_checkout_verified_before_package_import": True,
            "git_replacement_refs_allowed": False,
            "one_time_runner_start_marker_required": True,
            "duplicate_runner_start_fails_closed": True,
            "release_or_delete_api_provided": False,
        },
        "bounds": {
            "device": "cpu",
            "coordinate_dtype": "float64",
            "case_count": REFERENCE_VALIDATION_RUNNER_MAX_CASES,
            "variant_count": REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS,
            "maximum_wall_seconds": REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS,
            "case_order_matches_protocol": True,
            "variant_order_matches_materialization_manifest": True,
            "all_failure_rows_retained": True,
            "skipped_cases_allowed": False,
            "network_access_allowed": False,
            "arbitrary_subprocess_execution_allowed": False,
            "root_owned_absolute_git_executable_required": True,
            "clean_checkout_preflight_required": True,
            "source_checkout_root_owned_read_only_required": True,
            "same_uid_source_checkout_replacement_resistance_established": False,
            "git_no_replace_objects_environment_required": True,
            "case_materialization_under_posix_deadline_required": True,
            "dedicated_manifest_preflight_worker_required": True,
            "runner_start_requires_remaining_wall_budget": True,
            "dedicated_case_worker_subprocess_required": True,
            "worker_automatic_site_initialization_allowed": False,
            "worker_dependency_paths_derived_from_verified_runtime": True,
            "worker_dependency_paths_derived_from_isolated_bootstrap": True,
            "case_worker_request_contains_trust_keys_or_receipts": False,
            "worker_environment_derived_from_verified_receipt": True,
            "retained_worker_environment_internal_coherence_reverified": True,
            "worker_python_hash_seed_uint32_bound_to_receipt": True,
            "worker_application_seed_bound_to_receipt": True,
            "parent_child_python_hash_probe_equality_required": True,
            "worker_exact_argv_cwd_and_environment_reverified": True,
            "worker_dependency_roots_and_bytes_reverified": True,
            "case_worker_hard_kill_at_wall_deadline_required": True,
            "worker_output_prefix_hard_bounded_before_buffer_growth": True,
            "worker_output_overflow_and_request_write_state_retained": True,
            "in_worker_posix_deadline_interrupt_required": True,
            "worker_canonical_jsonl_frame_protocol_required": True,
            "manifest_worker_frame_order": ["pre", "payload", "completion"],
            "case_worker_frame_order": ["pre", "payload_x27", "completion"],
            "worker_request_sha256_bound_to_every_frame": True,
            "exact_worker_request_transport_bytes_retained": True,
            "supervisor_launched_child_process_id_retained": True,
            "complete_raw_transcript_equals_canonical_reconstruction_required": True,
            "worker_transcript_digest_and_frame_sequence_retained": True,
            "worker_payload_aggregate_bound_to_completion": True,
            "worker_pre_and_post_native_snapshots_required": True,
            "native_runtime_allowlist_authorization_established": False,
            "production_native_lifetime_closure_claimed": False,
            "partial_worker_success_retained_after_lifecycle_failure": False,
            "supervisor_failure_complete_27_case_59_variant_matrix_required": True,
        },
        "entrypoint": {
            "logical_argv": list(REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV),
            "trusted_outer_launcher_argv": list(
                REFERENCE_VALIDATION_TRUSTED_OUTER_LAUNCHER_ARGV
            ),
            "direct_stdlib_only_bootstrap_required": True,
            "canonical_request_bounded_before_package_import": True,
            "operator_signature_verified_before_package_import": True,
            "expected_commit_and_source_verified_before_package_import": True,
            "trusted_outer_launcher_flags": [
                "-I",
                "-S",
                "-B",
                "-X",
                "pycache_prefix=/dev/null",
            ],
            "seeded_controlled_inner_flags": [
                "-S",
                "-B",
                "-X",
                "pycache_prefix=/dev/null",
                "-c",
            ],
            "environment_import_path_overrides_honored": False,
            "automatic_site_initialization_allowed": False,
            "clean_source_checkout_with_git_metadata_required": True,
            "reservation_and_artifact_roots_outside_checkout_required": True,
            "canonical_standard_input_request_schema_id": (
                REFERENCE_VALIDATION_RUNNER_REQUEST_SCHEMA_ID
            ),
            "maximum_request_bytes": REFERENCE_VALIDATION_RUNNER_MAX_REQUEST_BYTES,
            "secret_bearing_argv_allowed": False,
            "trust_keys_in_standard_input_allowed": False,
            "fixed_root_owned_mode_0600_trust_store_required": True,
            "trust_store_path": REFERENCE_VALIDATION_TRUST_STORE_PATH,
            "trust_store_schema_id": REFERENCE_VALIDATION_TRUST_STORE_SCHEMA_ID,
            "trust_store_contains_ed25519_public_keys_only": True,
            "private_or_symmetric_key_material_allowed": False,
            "repository_bundles_trust_store_or_keys": False,
            "trust_keys_retained_or_echoed": False,
            "environment_receipt_runner_and_result_writer_reachable": True,
            "result_receipt_finalized_in_same_verified_process": True,
            "response_contains_hashes_and_closed_claim_state_only": True,
        },
        "observation": {
            "in_memory_only": True,
            "success_variant_energy_force_and_oracle_values_retained": True,
            "failure_variant_numeric_values_retained": False,
            "all_predefined_metrics_evaluated_or_marked_missing": True,
            "failed_metrics_and_cases_retained": True,
            "canonical_observation_sha256_required": True,
            "result_receipt_writer_implemented": True,
            "dependency_bytes_remeasured_during_result_finalize": True,
            "manifest_and_case_worker_lifecycle_evidence_retained": True,
            "manifest_and_case_worker_execution_provenance_retained": True,
            "worker_request_reparsed_and_cross_checked_against_run_identity": True,
            "worker_pid_cross_checked_against_native_snapshots": True,
            "external_worker_launch_identity_established": False,
            "complete_worker_transcript_reconstructed_and_rehashed": True,
            "incomplete_worker_partial_transcript_digest_retained_bounded": True,
            "incomplete_raw_partial_independent_replay_available": False,
            "retained_case_payload_aggregate_sha256_required": True,
            "incomplete_worker_lifecycle_requires_supervisor_only_failure_rows": True,
        },
        "current_state": {
            "bounded_validation_runner_implemented": True,
            "production_environment_receipt_present": False,
            "production_validation_execution_authorized": False,
            "production_validation_results_collected": False,
            "production_result_receipt_present": False,
            "preconfigured_trust_store_present": False,
        },
        "claim_policy": _closed_claim_policy(),
        "blockers": list(_CURRENT_BLOCKERS),
    }


def reference_validation_runner_contract_document() -> dict[str, Any]:
    document = _contract_projection()
    document["contract_sha256"] = _sha256(document)
    if document["contract_sha256"] != (
        FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256
    ):
        raise ReferenceValidationRunnerError(
            "frozen validation runner contract SHA-256 drifted"
        )
    return document


def require_reference_validation_runner_contract_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReferenceValidationRunnerError(
            "validation runner contract document must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    expected = reference_validation_runner_contract_document()
    if observed != expected:
        raise ReferenceValidationRunnerError(
            "validation runner contract document does not match the frozen record"
        )
    return observed


def _runner_start_projection(
    receipt: ReferenceValidationExecutionEnvironmentReceipt,
    *,
    runner_source_sha256: str,
    started_at_utc: str,
) -> dict[str, Any]:
    return {
        "schema_id": REFERENCE_VALIDATION_RUNNER_START_SCHEMA_ID,
        "runner_contract_sha256": FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256,
        "environment_receipt_sha256": receipt.receipt_sha256,
        "environment_fingerprint_sha256": receipt.environment_fingerprint_sha256,
        "authorization_receipt_sha256": receipt.authorization_receipt_sha256,
        "authorization_nonce_sha256": receipt.authorization_nonce_sha256,
        "code_commit_sha": receipt.code_commit_sha,
        "runner_source_sha256": runner_source_sha256,
        "source_manifest_sha256": receipt.source_manifest_sha256,
        "dependency_artifact_sha256_rows": [
            {"artifact_id": artifact_id, "sha256": digest}
            for artifact_id, digest in receipt.dependency_artifact_sha256_rows
        ],
        "started_at_utc": started_at_utc,
        "one_time_runner_start_consumed": True,
        "result_values_present": False,
        "result_receipt_written": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def _persist_runner_start(
    artifact_output_root: str | os.PathLike[str],
    receipt: ReferenceValidationExecutionEnvironmentReceipt,
    *,
    runner_source_sha256: str,
    started_at_utc: str,
) -> str:
    projection = _runner_start_projection(
        receipt,
        runner_source_sha256=runner_source_sha256,
        started_at_utc=started_at_utc,
    )
    payload = dict(projection)
    payload["runner_start_record_sha256"] = _sha256(projection)
    encoded = _canonical_bytes(payload) + b"\n"
    if len(encoded) > REFERENCE_VALIDATION_RUNNER_MAX_START_RECORD_BYTES:
        raise ReferenceValidationRunnerError("runner-start record is too large")
    try:
        root_fd = _open_secure_reservation_root(artifact_output_root)
    except ReferenceValidationNonceReservationError as exc:
        raise ReferenceValidationRunnerError(
            "runner artifact root does not satisfy the private POSIX policy"
        ) from exc
    filename = f"{receipt.authorization_nonce_sha256}.runner-start.json"
    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(
                filename,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=root_fd,
            )
        except FileExistsError as exc:
            raise ReferenceValidationRunnerAlreadyStartedError(
                "bounded validation runner already started for this nonce"
            ) from exc
        except (OSError, ValueError) as exc:
            raise ReferenceValidationRunnerError(
                "runner-start record cannot be created securely"
            ) from exc
        try:
            _validate_reservation_file_stat(os.fstat(descriptor))
            remaining = memoryview(encoded)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("runner-start write made no progress")
                remaining = remaining[written:]
            os.fsync(descriptor)
        except Exception as exc:
            raise ReferenceValidationRunnerError(
                "runner-start persistence failed; the path remains consumed"
            ) from exc
        os.close(descriptor)
        descriptor = None
        try:
            os.fsync(root_fd)
        except OSError as exc:
            raise ReferenceValidationRunnerError(
                "runner-start durability failed; the path remains consumed"
            ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(root_fd)
    return payload["runner_start_record_sha256"]


def read_reference_validation_runner_start_record(
    artifact_output_root: str | os.PathLike[str],
    authorization_nonce_sha256: str,
    *,
    expected_record_sha256: str,
    expected_environment_receipt_sha256: str,
    expected_runner_source_sha256: str,
    expected_source_manifest_sha256: str,
) -> dict[str, Any]:
    """Read and verify the consumed runner-start marker without releasing it."""

    nonce = _require_sha256(
        authorization_nonce_sha256,
        name="runner-start authorization nonce",
    )
    expected_record = _require_sha256(
        expected_record_sha256,
        name="expected runner-start record",
    )
    expected_environment = _require_sha256(
        expected_environment_receipt_sha256,
        name="expected runner-start environment receipt",
    )
    expected_source = _require_sha256(
        expected_runner_source_sha256,
        name="expected runner-start source",
    )
    expected_source_manifest = _require_sha256(
        expected_source_manifest_sha256,
        name="expected runner-start source manifest",
    )
    try:
        root_fd = _open_secure_reservation_root(artifact_output_root)
    except ReferenceValidationNonceReservationError as exc:
        raise ReferenceValidationRunnerError(
            "runner-start artifact root does not satisfy the private POSIX policy"
        ) from exc
    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(
                f"{nonce}.runner-start.json",
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=root_fd,
            )
            _validate_reservation_file_stat(os.fstat(descriptor))
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, 8192)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > REFERENCE_VALIDATION_RUNNER_MAX_START_RECORD_BYTES:
                    raise ReferenceValidationRunnerError(
                        "runner-start record exceeds the size limit"
                    )
        except (OSError, ValueError, ReferenceValidationNonceReservationError) as exc:
            raise ReferenceValidationRunnerError(
                "runner-start record cannot be read securely"
            ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(root_fd)
    raw = b"".join(chunks)

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceValidationRunnerError(
                    "runner-start record contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        if not raw.endswith(b"\n"):
            raise ReferenceValidationRunnerError(
                "runner-start record is not canonical JSON"
            )
        payload = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationRunnerError(
            "runner-start record is not canonical JSON"
        ) from exc
    if not isinstance(payload, dict) or _canonical_bytes(payload) + b"\n" != raw:
        raise ReferenceValidationRunnerError(
            "runner-start record is not canonical JSON"
        )
    observed_record = payload.pop("runner_start_record_sha256", None)
    if observed_record != _sha256(payload) or observed_record != expected_record:
        raise ReferenceValidationRunnerError(
            "runner-start record identity is cross-wired"
        )
    expected_keys = {
        "schema_id",
        "runner_contract_sha256",
        "environment_receipt_sha256",
        "environment_fingerprint_sha256",
        "authorization_receipt_sha256",
        "authorization_nonce_sha256",
        "code_commit_sha",
        "runner_source_sha256",
        "source_manifest_sha256",
        "dependency_artifact_sha256_rows",
        "started_at_utc",
        "one_time_runner_start_consumed",
        "result_values_present",
        "result_receipt_written",
        "parameter_fitting_authorized",
        "scientifically_validated",
        "claim_safe",
    }
    if set(payload) != expected_keys:
        raise ReferenceValidationRunnerError("runner-start record fields are invalid")
    if (
        payload["schema_id"] != REFERENCE_VALIDATION_RUNNER_START_SCHEMA_ID
        or payload["runner_contract_sha256"]
        != FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256
        or payload["environment_receipt_sha256"] != expected_environment
        or payload["authorization_nonce_sha256"] != nonce
        or payload["runner_source_sha256"] != expected_source
        or payload["source_manifest_sha256"] != expected_source_manifest
        or payload["one_time_runner_start_consumed"] is not True
        or any(
            payload[name] is not False
            for name in (
                "result_values_present",
                "result_receipt_written",
                "parameter_fitting_authorized",
                "scientifically_validated",
                "claim_safe",
            )
        )
    ):
        raise ReferenceValidationRunnerError(
            "runner-start record does not match the bounded runner contract"
        )
    result = dict(payload)
    result["runner_start_record_sha256"] = observed_record
    return result


def _normalize_physics_error(error: Exception) -> str:
    message = str(error)
    prefix = "reference parameter applicability failed: "
    if message.startswith(prefix):
        first = message[len(prefix) :].split(", ", 1)[0]
        if first:
            return first
    exact = {
        "nonbonded pair is below minimum_pair_distance_angstrom": (
            "nonbonded_pair_below_minimum_pair_distance_angstrom"
        ),
        "angle contains a zero-length vector": "angle_zero_length_vector",
        "torsion is undefined for collinear atoms": (
            "torsion_undefined_for_collinear_atoms"
        ),
    }
    return exact.get(message, "unclassified_reference_physics_error")


def _failure_variant(
    ordinal: int,
    variant: Any,
    *,
    status: str,
    error_code: str,
) -> ReferenceValidationVariantObservation:
    return ReferenceValidationVariantObservation(
        ordinal=ordinal,
        variant_id=variant.variant_id,
        runtime_input_sha256=variant.runtime_input_sha256,
        oracle_input_sha256=(
            None if variant.oracle_input is None else variant.oracle_input.input_sha256
        ),
        observed_status=status,
        observed_error_code=error_code,
    )


def _failed_case_from_frozen_manifest(
    ordinal: int,
    case: CPUReferenceValidationCase,
    manifest_case: Mapping[str, Any],
    *,
    metric_map: Mapping[str, CPUReferenceValidationMetric],
    observed_status: str,
    observed_error_code: str,
    observation_origin: str = "supervisor",
) -> ReferenceValidationCaseObservation:
    """Retain exact frozen variant identities after a supervised worker failure."""

    if observed_status not in {"time_budget_exhausted", "unexpected_error"}:
        raise ReferenceValidationRunnerError(
            "supervised worker failure status is invalid"
        )
    if not observed_error_code:
        raise ReferenceValidationRunnerError(
            "supervised worker failure error is invalid"
        )

    if not isinstance(manifest_case, Mapping) or (
        manifest_case.get("case_id"),
        manifest_case.get("case_input_sha256"),
        manifest_case.get("expected_outcome"),
        manifest_case.get("expected_error_code"),
    ) != (
        case.case_id,
        case.input_sha256,
        case.expected_outcome,
        case.expected_error_code,
    ):
        raise ReferenceValidationRunnerError(
            "materialization manifest case is cross-wired"
        )
    variant_payloads = manifest_case.get("variants")
    if (
        not isinstance(variant_payloads, list)
        or not variant_payloads
        or manifest_case.get("variant_count") != len(variant_payloads)
    ):
        raise ReferenceValidationRunnerError(
            "materialization manifest variant coverage is invalid"
        )
    variants: list[ReferenceValidationVariantObservation] = []
    for variant_ordinal, payload in enumerate(variant_payloads):
        if not isinstance(payload, Mapping):
            raise ReferenceValidationRunnerError(
                "materialization manifest variant is invalid"
            )
        variant_id = payload.get("variant_id")
        if not isinstance(variant_id, str) or not variant_id:
            raise ReferenceValidationRunnerError(
                "materialization manifest variant identity is invalid"
            )
        oracle_input_sha256 = payload.get("oracle_input_sha256")
        if oracle_input_sha256 is not None:
            oracle_input_sha256 = _require_sha256(
                oracle_input_sha256,
                name="materialization manifest oracle input",
            )
        variants.append(
            ReferenceValidationVariantObservation(
                ordinal=variant_ordinal,
                variant_id=variant_id,
                runtime_input_sha256=_require_sha256(
                    payload.get("runtime_input_sha256"),
                    name="materialization manifest runtime input",
                ),
                oracle_input_sha256=oracle_input_sha256,
                observed_status=observed_status,
                observed_error_code=observed_error_code,
            )
        )
    variant_rows = tuple(variants)
    metrics = (
        ()
        if case.expected_outcome == "fail_closed"
        else _metric_observations(case, variant_rows, metric_map)
    )
    return ReferenceValidationCaseObservation(
        ordinal=ordinal,
        case_id=case.case_id,
        case_input_sha256=case.input_sha256,
        materialization_sha256=_require_sha256(
            manifest_case.get("materialization_sha256"),
            name="materialization manifest case",
        ),
        expected_outcome=case.expected_outcome,
        observation_origin=observation_origin,
        observed_status=observed_status,
        expected_error_code=case.expected_error_code,
        observed_error_code=observed_error_code,
        variant_results=variant_rows,
        metric_values=metrics,
        case_passed=False,
    )


def _time_budget_case_from_frozen_manifest(
    ordinal: int,
    case: CPUReferenceValidationCase,
    manifest_case: Mapping[str, Any],
    *,
    metric_map: Mapping[str, CPUReferenceValidationMetric],
) -> ReferenceValidationCaseObservation:
    return _failed_case_from_frozen_manifest(
        ordinal,
        case,
        manifest_case,
        metric_map=metric_map,
        observed_status="time_budget_exhausted",
        observed_error_code="runner_time_budget_exhausted",
        observation_origin="worker",
    )


def _success_variant(
    ordinal: int,
    variant: Any,
    evaluation: Any,
    oracle: Any,
) -> ReferenceValidationVariantObservation:
    forces = tuple(
        tuple(float(value) for value in row)
        for row in evaluation.term.forces[0].detach().cpu().tolist()
    )
    oracle_forces = tuple(
        tuple(float(value) for value in row)
        for row in oracle.forces_kcal_per_mol_angstrom
    )
    components = tuple(
        sorted(
            (
                name,
                float(value[0].detach().cpu().item()),
            )
            for name, value in evaluation.component_energies.items()
        )
    )
    return ReferenceValidationVariantObservation(
        ordinal=ordinal,
        variant_id=variant.variant_id,
        runtime_input_sha256=variant.runtime_input_sha256,
        oracle_input_sha256=variant.oracle_input.input_sha256,
        observed_status="success",
        observed_error_code=None,
        component_energies_kcal_per_mol=components,
        total_energy_kcal_per_mol=float(
            evaluation.term.energy[0].detach().cpu().item()
        ),
        forces_kcal_per_mol_angstrom=forces,
        force_array_sha256=_force_array_sha256(forces),
        oracle_total_energy_kcal_per_mol=float(oracle.total_energy_kcal_per_mol),
        oracle_forces_kcal_per_mol_angstrom=oracle_forces,
        oracle_force_array_sha256=_force_array_sha256(oracle_forces),
    )


def _max_abs(first: list[float], second: list[float]) -> float:
    if len(first) != len(second) or not first:
        raise ReferenceValidationRunnerError("metric arrays are empty or misaligned")
    return max(abs(a - b) for a, b in zip(first, second))


def _max_rel(
    observed: list[float],
    independent_reference: list[float],
) -> float:
    if len(observed) != len(independent_reference) or not observed:
        raise ReferenceValidationRunnerError("relative metric arrays are misaligned")
    return max(
        abs(value - reference) / max(abs(reference), 1.0e-12)
        for value, reference in zip(observed, independent_reference)
    )


def _flatten_force(
    values: tuple[tuple[float, float, float], ...],
) -> list[float]:
    return [value for row in values for value in row]


def _success_map(
    rows: tuple[ReferenceValidationVariantObservation, ...],
) -> dict[str, ReferenceValidationVariantObservation]:
    return {row.variant_id: row for row in rows if row.observed_status == "success"}


def _oracle_metric_values(
    rows: tuple[ReferenceValidationVariantObservation, ...],
) -> dict[str, float]:
    successes = tuple(row for row in rows if row.observed_status == "success")
    if not successes:
        return {}
    energies = [float(row.total_energy_kcal_per_mol) for row in successes]
    oracle_energies = [float(row.oracle_total_energy_kcal_per_mol) for row in successes]
    forces = [
        value
        for row in successes
        for value in _flatten_force(row.forces_kcal_per_mol_angstrom)
    ]
    oracle_forces = [
        value
        for row in successes
        for value in _flatten_force(row.oracle_forces_kcal_per_mol_angstrom)
    ]
    return {
        "energy_oracle_max_abs_error": _max_abs(energies, oracle_energies),
        "energy_oracle_max_rel_error": _max_rel(energies, oracle_energies),
        "force_oracle_max_component_abs_error": _max_abs(forces, oracle_forces),
        "force_oracle_max_component_rel_error": _max_rel(forces, oracle_forces),
    }


def _net_force_norm(row: ReferenceValidationVariantObservation) -> float:
    totals = [
        sum(atom[axis] for atom in row.forces_kcal_per_mol_angstrom)
        for axis in range(3)
    ]
    return math.sqrt(sum(value * value for value in totals))


def _case_metric_values(
    case: CPUReferenceValidationCase,
    rows: tuple[ReferenceValidationVariantObservation, ...],
) -> dict[str, float | bool]:
    values: dict[str, float | bool] = _oracle_metric_values(rows)
    by_id = _success_map(rows)
    if case.case_id == "quintic_switch_window_and_cutoff" and len(by_id) == 3:
        values["switch_cutoff_energy_abs"] = max(
            abs(float(row.total_energy_kcal_per_mol)) for row in by_id.values()
        )
        values["switch_cutoff_force_max_abs"] = max(
            abs(value)
            for row in by_id.values()
            for value in _flatten_force(row.forces_kcal_per_mol_angstrom)
        )
    elif case.case_id == "orthorhombic_minimum_image" and len(by_id) == 2:
        periodic = by_id["periodic-minimum-image"]
        direct = by_id["direct-equivalent"]
        values["minimum_image_energy_abs_error"] = abs(
            float(periodic.total_energy_kcal_per_mol)
            - float(direct.total_energy_kcal_per_mol)
        )
        values["minimum_image_force_max_abs_error"] = _max_abs(
            _flatten_force(periodic.forces_kcal_per_mol_angstrom),
            _flatten_force(direct.forces_kcal_per_mol_angstrom),
        )
    elif case.case_id == "full_five_term_composition" and by_id:
        values["net_force_norm"] = max(_net_force_norm(row) for row in by_id.values())
    elif case.case_id == "full_force_central_difference" and len(by_id) == 25:
        baseline = by_id["baseline"]
        numerical: list[float] = []
        reference: list[float] = []
        for atom_index, force_row in enumerate(baseline.forces_kcal_per_mol_angstrom):
            for axis_name, axis in _AXIS_INDEX.items():
                minus = by_id[f"atom-{atom_index}-{axis_name}-minus"]
                plus = by_id[f"atom-{atom_index}-{axis_name}-plus"]
                numerical_force = -(
                    float(plus.total_energy_kcal_per_mol)
                    - float(minus.total_energy_kcal_per_mol)
                ) / (2.0 * REFERENCE_VALIDATION_CENTRAL_DIFFERENCE_STEP_ANGSTROM)
                numerical.append(numerical_force)
                reference.append(force_row[axis])
        values["finite_difference_force_max_abs_error"] = _max_abs(
            reference,
            numerical,
        )
        values["finite_difference_force_max_rel_error"] = _max_rel(
            reference,
            numerical,
        )
    elif case.case_id == "rigid_translation_invariance" and len(by_id) == 2:
        baseline = by_id["baseline"]
        translated = by_id["translated"]
        values["translation_energy_abs_drift"] = abs(
            float(baseline.total_energy_kcal_per_mol)
            - float(translated.total_energy_kcal_per_mol)
        )
        values["translation_force_max_abs_drift"] = _max_abs(
            _flatten_force(baseline.forces_kcal_per_mol_angstrom),
            _flatten_force(translated.forces_kcal_per_mol_angstrom),
        )
        values["net_force_norm"] = max(
            _net_force_norm(baseline),
            _net_force_norm(translated),
        )
    elif case.case_id == "rigid_rotation_invariance" and len(by_id) == 2:
        baseline = by_id["baseline"]
        rotated = by_id["rotated"]
        covariant = [
            sum(_ROTATION_MATRIX[axis][column] * row[column] for column in range(3))
            for row in baseline.forces_kcal_per_mol_angstrom
            for axis in range(3)
        ]
        values["rotation_energy_abs_drift"] = abs(
            float(baseline.total_energy_kcal_per_mol)
            - float(rotated.total_energy_kcal_per_mol)
        )
        values["rotation_force_covariance_max_abs_error"] = _max_abs(
            _flatten_force(rotated.forces_kcal_per_mol_angstrom),
            covariant,
        )
    elif case.case_id == "atom_permutation_equivariance" and len(by_id) == 2:
        baseline = by_id["baseline"]
        permuted = by_id["permuted"]
        expected = [
            value
            for old_index in _PERMUTATION_NEW_TO_OLD
            for value in baseline.forces_kcal_per_mol_angstrom[old_index]
        ]
        values["permutation_energy_abs_drift"] = abs(
            float(baseline.total_energy_kcal_per_mol)
            - float(permuted.total_energy_kcal_per_mol)
        )
        values["permutation_force_equivariance_max_abs_error"] = _max_abs(
            _flatten_force(permuted.forces_kcal_per_mol_angstrom),
            expected,
        )
    elif case.case_id == "same_environment_repeat_determinism" and len(by_id) == 3:
        ordered = [by_id[f"repeat-{index}"] for index in (1, 2, 3)]
        values["repeat_energy_bitwise_equal"] = (
            len({float(row.total_energy_kcal_per_mol).hex() for row in ordered}) == 1
        )
        values["repeat_force_bitwise_equal"] = (
            len(
                {
                    tuple(
                        value.hex()
                        for value in _flatten_force(row.forces_kcal_per_mol_angstrom)
                    )
                    for row in ordered
                }
            )
            == 1
        )
    return values


def _metric_observations(
    case: CPUReferenceValidationCase,
    rows: tuple[ReferenceValidationVariantObservation, ...],
    metric_map: Mapping[str, CPUReferenceValidationMetric],
) -> tuple[ReferenceValidationMetricObservation, ...]:
    values = _case_metric_values(case, rows)
    observations: list[ReferenceValidationMetricObservation] = []
    for metric_id in case.required_metric_ids:
        metric = metric_map[metric_id]
        value = values.get(metric_id)
        if value is None:
            observations.append(
                ReferenceValidationMetricObservation(
                    metric_id=metric_id,
                    observed=False,
                    value=None,
                    unit=metric.unit,
                    threshold_operator=metric.threshold_operator,
                    threshold_value=metric.threshold_value,
                    passed=False,
                )
            )
            continue
        if metric.threshold_operator == "equal":
            passed = isinstance(value, bool) and value == bool(metric.threshold_value)
        else:
            passed = (
                not isinstance(value, bool) and float(value) <= metric.threshold_value
            )
        observations.append(
            ReferenceValidationMetricObservation(
                metric_id=metric_id,
                observed=True,
                value=value,
                unit=metric.unit,
                threshold_operator=metric.threshold_operator,
                threshold_value=metric.threshold_value,
                passed=passed,
            )
        )
    return tuple(observations)


def _require_deadline_timer_available() -> None:
    if (
        threading.current_thread() is not threading.main_thread()
        or not hasattr(signal, "SIGALRM")
        or not hasattr(signal, "ITIMER_REAL")
    ):
        raise ReferenceValidationRunnerError(
            "bounded validation must run on the POSIX main thread"
        )
    try:
        active_seconds, active_interval = signal.getitimer(signal.ITIMER_REAL)
    except (OSError, ValueError) as exc:
        raise ReferenceValidationRunnerError(
            "bounded validation deadline timer is unavailable"
        ) from exc
    if active_seconds > 0.0 or active_interval > 0.0:
        raise ReferenceValidationRunnerError(
            "bounded validation requires an unused process deadline timer"
        )


def _call_before_deadline(
    function: Any,
    *args: Any,
    deadline: float,
) -> Any:
    remaining = deadline - time.monotonic()
    if remaining <= 0.0:
        raise _ReferenceValidationDeadlineExceeded
    previous_handler = signal.getsignal(signal.SIGALRM)

    def deadline_handler(_signum: int, _frame: Any) -> None:
        raise _ReferenceValidationDeadlineExceeded

    try:
        signal.signal(signal.SIGALRM, deadline_handler)
        signal.setitimer(signal.ITIMER_REAL, remaining)
        result = function(*args)
        if time.monotonic() >= deadline:
            raise _ReferenceValidationDeadlineExceeded
        return result
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)


def _evaluate_case(
    ordinal: int,
    case: CPUReferenceValidationCase,
    materialized: Any,
    *,
    metric_map: Mapping[str, CPUReferenceValidationMetric],
    deadline: float,
    evaluate_reference_force_field: Any,
    reference_error_type: type[Exception],
    evaluate_independent_analytic_oracle: Any,
) -> ReferenceValidationCaseObservation:
    rows: list[ReferenceValidationVariantObservation] = []
    for variant_ordinal, variant in enumerate(materialized.variants):
        if time.monotonic() > deadline:
            rows.append(
                _failure_variant(
                    variant_ordinal,
                    variant,
                    status="time_budget_exhausted",
                    error_code="runner_time_budget_exhausted",
                )
            )
            continue
        try:
            evaluation = _call_before_deadline(
                evaluate_reference_force_field,
                variant.system,
                variant.neighbors,
                variant.parameters,
                deadline=deadline,
            )
        except _ReferenceValidationDeadlineExceeded:
            rows.append(
                _failure_variant(
                    variant_ordinal,
                    variant,
                    status="time_budget_exhausted",
                    error_code="runner_time_budget_exhausted",
                )
            )
            continue
        except reference_error_type as exc:
            status = (
                "fail_closed"
                if case.expected_outcome == "fail_closed"
                else "unexpected_error"
            )
            rows.append(
                _failure_variant(
                    variant_ordinal,
                    variant,
                    status=status,
                    error_code=_normalize_physics_error(exc),
                )
            )
            continue
        except Exception:
            rows.append(
                _failure_variant(
                    variant_ordinal,
                    variant,
                    status="unexpected_error",
                    error_code="unexpected_reference_evaluator_error",
                )
            )
            continue
        if case.expected_outcome == "fail_closed":
            rows.append(
                _failure_variant(
                    variant_ordinal,
                    variant,
                    status="unexpected_success",
                    error_code="expected_fail_closed_variant_executed",
                )
            )
            continue
        try:
            oracle = _call_before_deadline(
                evaluate_independent_analytic_oracle,
                variant.oracle_input,
                deadline=deadline,
            )
            rows.append(_success_variant(variant_ordinal, variant, evaluation, oracle))
        except _ReferenceValidationDeadlineExceeded:
            rows.append(
                _failure_variant(
                    variant_ordinal,
                    variant,
                    status="time_budget_exhausted",
                    error_code="runner_time_budget_exhausted",
                )
            )
        except Exception:
            rows.append(
                _failure_variant(
                    variant_ordinal,
                    variant,
                    status="unexpected_error",
                    error_code="unexpected_independent_oracle_error",
                )
            )
    variant_rows = tuple(rows)
    if case.expected_outcome == "fail_closed":
        error_codes = {row.observed_error_code for row in variant_rows}
        expected = all(
            row.observed_status == "fail_closed" for row in variant_rows
        ) and error_codes == {case.expected_error_code}
        if expected:
            status = "fail_closed_as_expected"
            observed_error = case.expected_error_code
        elif any(
            row.observed_status == "time_budget_exhausted" for row in variant_rows
        ):
            status = "time_budget_exhausted"
            observed_error = "runner_time_budget_exhausted"
        elif any(row.observed_status == "unexpected_success" for row in variant_rows):
            status = "unexpected_success"
            observed_error = "expected_fail_closed_variant_executed"
        else:
            status = "unexpected_error"
            observed_error = (
                next(iter(error_codes))
                if len(error_codes) == 1
                else ("multiple_or_unexpected_error_codes")
            )
        metrics: tuple[ReferenceValidationMetricObservation, ...] = ()
    else:
        metrics = _metric_observations(case, variant_rows, metric_map)
        if any(row.observed_status == "time_budget_exhausted" for row in variant_rows):
            status = "time_budget_exhausted"
        elif any(row.observed_status != "success" for row in variant_rows):
            status = "unexpected_error"
        elif all(row.passed for row in metrics):
            status = "metrics_passed"
        else:
            status = "metric_threshold_failed"
        observed_error = (
            None
            if status in {"metrics_passed", "metric_threshold_failed"}
            else next(
                (
                    row.observed_error_code
                    for row in variant_rows
                    if row.observed_error_code is not None
                ),
                "metric_not_observed",
            )
        )
    return ReferenceValidationCaseObservation(
        ordinal=ordinal,
        case_id=case.case_id,
        case_input_sha256=case.input_sha256,
        materialization_sha256=materialized.materialization_sha256,
        expected_outcome=case.expected_outcome,
        observation_origin="worker",
        observed_status=status,
        expected_error_code=case.expected_error_code,
        observed_error_code=observed_error,
        variant_results=variant_rows,
        metric_values=metrics,
        case_passed=status in {"metrics_passed", "fail_closed_as_expected"},
    )


def _load_frozen_case_manifest_document() -> tuple[Any, dict[str, Any]]:
    from .reference_validation_artifact_binding import (
        ReferenceValidationArtifactBindingError,
        frozen_reference_validation_artifact_binding,
    )
    from .reference_validation_materializer import (
        reference_validation_materialization_manifest_document,
    )

    try:
        frozen_reference_validation_artifact_binding()
    except ReferenceValidationArtifactBindingError as exc:
        raise ReferenceValidationRunnerError(
            "runner reference evaluator or validation artifact source drifted"
        ) from exc
    manifest = reference_validation_materialization_manifest_document()
    if manifest["coverage"] != {
        "fixture_count": 7,
        "mutation_count": 20,
        "case_count": REFERENCE_VALIDATION_RUNNER_MAX_CASES,
        "variant_count": REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS,
        "expected_pass_case_count": 15,
        "expected_fail_closed_case_count": 12,
    }:
        raise ReferenceValidationRunnerError("runner materialization coverage drifted")
    manifest_cases = manifest.get("cases")
    if not isinstance(manifest_cases, list) or len(manifest_cases) != (
        REFERENCE_VALIDATION_RUNNER_MAX_CASES
    ):
        raise ReferenceValidationRunnerError(
            "runner materialization manifest cases drifted"
        )
    protocol = frozen_cpu_reference_validation_protocol()
    if len(protocol.cases) != REFERENCE_VALIDATION_RUNNER_MAX_CASES:
        raise ReferenceValidationRunnerError("runner protocol case bound drifted")
    return protocol, manifest


def _load_frozen_case_matrix() -> tuple[Any, list[Mapping[str, Any]]]:
    protocol, manifest = _load_frozen_case_manifest_document()
    return protocol, manifest["cases"]


def _iter_case_matrix_in_process(
    protocol: Any,
    manifest_cases: list[Mapping[str, Any]],
    *,
    deadline: float,
) -> Any:
    """Yield frozen case rows inside the dedicated, killable worker only."""

    from .reference_validation_materializer import (
        materialize_frozen_reference_validation_case,
    )
    from .reference_validation_oracle import evaluate_independent_analytic_oracle
    from .reference_forcefield import (
        ReferencePhysicsApplicabilityError,
        evaluate_reference_force_field,
    )

    metric_map = {row.metric_id: row for row in protocol.metrics}
    for ordinal, (case, manifest_case) in enumerate(
        zip(protocol.cases, manifest_cases, strict=True)
    ):
        try:
            materialized = _call_before_deadline(
                materialize_frozen_reference_validation_case,
                case.case_id,
                protocol,
                deadline=deadline,
            )
        except _ReferenceValidationDeadlineExceeded:
            yield _time_budget_case_from_frozen_manifest(
                ordinal,
                case,
                manifest_case,
                metric_map=metric_map,
            )
        else:
            yield _evaluate_case(
                ordinal,
                case,
                materialized,
                metric_map=metric_map,
                deadline=deadline,
                evaluate_reference_force_field=evaluate_reference_force_field,
                reference_error_type=ReferencePhysicsApplicabilityError,
                evaluate_independent_analytic_oracle=(
                    evaluate_independent_analytic_oracle
                ),
            )


def _run_case_matrix_in_process(
    protocol: Any,
    manifest_cases: list[Mapping[str, Any]],
    *,
    deadline: float,
) -> tuple[ReferenceValidationCaseObservation, ...]:
    return tuple(
        _iter_case_matrix_in_process(
            protocol,
            manifest_cases,
            deadline=deadline,
        )
    )


def _python_hash_probe_sha256() -> str:
    return _sha256(
        {
            "bytes": hash(b"betelgeuze-engine-v2-worker-seed-probe"),
            "string": hash("betelgeuze-engine-v2-worker-seed-probe"),
            "tuple": hash(("betelgeuze-engine-v2-worker-seed-probe", 17)),
        }
    )


def _require_worker_seed(value: object, *, name: str, maximum: int) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ReferenceValidationRunnerError(f"{name} is outside the frozen range")
    return value


def _configure_deterministic_torch_runtime(application_seed: int | None = None) -> None:
    import torch

    try:
        if application_seed is not None:
            torch.manual_seed(
                _require_worker_seed(
                    application_seed,
                    name="worker application seed",
                    maximum=2**63 - 1,
                )
            )
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
    except RuntimeError as exc:
        raise ReferenceValidationRunnerError(
            "runner deterministic single-thread runtime cannot be configured"
        ) from exc


def _load_case_worker_request(raw: bytes) -> dict[str, Any]:
    if (
        not raw
        or len(raw) > REFERENCE_VALIDATION_CASE_WORKER_MAX_REQUEST_BYTES
        or not raw.endswith(b"\n")
    ):
        raise ReferenceValidationRunnerError(
            "case-worker request size or framing is invalid"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceValidationRunnerError(
                    "case-worker request contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        request = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationRunnerError(
            "case-worker request must be canonical ASCII JSON"
        ) from exc
    if (
        not isinstance(request, dict)
        or set(request)
        != {
            "schema_id",
            "worker_kind",
            "expected_protocol_sha256",
            "expected_materialization_manifest_sha256",
            "expected_case_count",
            "expected_variant_count",
            "expected_code_commit_sha",
            "expected_runner_source_sha256",
            "expected_source_manifest_sha256",
            "expected_dependency_artifact_sha256_rows",
            "dependency_roots",
            "expected_environment_receipt_sha256",
            "expected_environment_fingerprint_sha256",
            "expected_authorization_nonce_sha256",
            "expected_runner_start_record_sha256",
            "expected_python_hash_seed",
            "expected_application_seed",
            "expected_worker_environment",
            "expected_worker_environment_sha256",
            "expected_python_hash_probe_sha256",
        }
        or request.get("schema_id")
        != REFERENCE_VALIDATION_CASE_WORKER_REQUEST_SCHEMA_ID
        or _canonical_bytes(request) + b"\n" != raw
    ):
        raise ReferenceValidationRunnerError(
            "case-worker request is not the exact canonical schema"
        )
    worker_kind = request["worker_kind"]
    worker_environment = request["expected_worker_environment"]
    raw_dependency_rows = request["expected_dependency_artifact_sha256_rows"]
    raw_dependency_roots = request["dependency_roots"]
    if (
        worker_kind not in {"manifest", "case"}
        or not isinstance(worker_environment, dict)
        or set(worker_environment) != _REFERENCE_VALIDATION_WORKER_ENVIRONMENT_NAMES
        or any(
            not isinstance(name, str) or not isinstance(value, str)
            for name, value in worker_environment.items()
        )
        or not isinstance(raw_dependency_rows, dict)
        or tuple(sorted(raw_dependency_rows))
        != REFERENCE_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
        or not isinstance(raw_dependency_roots, list)
        or not raw_dependency_roots
        or any(not isinstance(root, str) or not root for root in raw_dependency_roots)
        or request["expected_protocol_sha256"]
        != FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256
        or request["expected_case_count"] != REFERENCE_VALIDATION_RUNNER_MAX_CASES
        or type(request["expected_case_count"]) is not int
        or request["expected_variant_count"] != REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS
        or type(request["expected_variant_count"]) is not int
        or (
            worker_kind == "manifest"
            and request["expected_materialization_manifest_sha256"] is not None
        )
        or (
            worker_kind == "manifest"
            and request["expected_runner_start_record_sha256"] is not None
        )
        or (
            worker_kind == "case"
            and (
                not isinstance(request["expected_materialization_manifest_sha256"], str)
                or _require_sha256(
                    request["expected_materialization_manifest_sha256"],
                    name="case-worker materialization manifest",
                )
                != request["expected_materialization_manifest_sha256"]
            )
        )
        or (
            worker_kind == "case"
            and not isinstance(request["expected_runner_start_record_sha256"], str)
        )
    ):
        raise ReferenceValidationRunnerError("case-worker runtime binding is invalid")
    return {
        "schema_id": request["schema_id"],
        "worker_kind": worker_kind,
        "expected_protocol_sha256": request["expected_protocol_sha256"],
        "expected_materialization_manifest_sha256": request[
            "expected_materialization_manifest_sha256"
        ],
        "expected_case_count": request["expected_case_count"],
        "expected_variant_count": request["expected_variant_count"],
        "expected_code_commit_sha": _require_commit_sha(
            request["expected_code_commit_sha"],
            name="case-worker expected commit",
        ),
        "expected_runner_source_sha256": _require_sha256(
            request["expected_runner_source_sha256"],
            name="case-worker expected source",
        ),
        "expected_source_manifest_sha256": _require_sha256(
            request["expected_source_manifest_sha256"],
            name="case-worker expected source manifest",
        ),
        "expected_dependency_artifact_sha256_rows": {
            artifact_id: _require_sha256(
                raw_dependency_rows[artifact_id],
                name=f"case-worker dependency {artifact_id}",
            )
            for artifact_id in REFERENCE_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
        },
        "dependency_roots": list(raw_dependency_roots),
        "expected_environment_receipt_sha256": _require_sha256(
            request["expected_environment_receipt_sha256"],
            name="case-worker environment receipt",
        ),
        "expected_environment_fingerprint_sha256": _require_sha256(
            request["expected_environment_fingerprint_sha256"],
            name="case-worker environment fingerprint",
        ),
        "expected_authorization_nonce_sha256": _require_sha256(
            request["expected_authorization_nonce_sha256"],
            name="case-worker authorization nonce",
        ),
        "expected_runner_start_record_sha256": (
            None
            if request["expected_runner_start_record_sha256"] is None
            else _require_sha256(
                request["expected_runner_start_record_sha256"],
                name="case-worker runner-start record",
            )
        ),
        "expected_python_hash_seed": _require_worker_seed(
            request["expected_python_hash_seed"],
            name="case-worker Python hash seed",
            maximum=2**32 - 1,
        ),
        "expected_application_seed": _require_worker_seed(
            request["expected_application_seed"],
            name="case-worker application seed",
            maximum=2**63 - 1,
        ),
        "expected_worker_environment": dict(worker_environment),
        "expected_worker_environment_sha256": _require_sha256(
            request["expected_worker_environment_sha256"],
            name="case-worker environment identity",
        ),
        "expected_python_hash_probe_sha256": _require_sha256(
            request["expected_python_hash_probe_sha256"],
            name="case-worker hash probe",
        ),
    }


def _read_worker_process_argv() -> tuple[str, ...]:
    try:
        raw = Path("/proc/self/cmdline").read_bytes()
        decoded = tuple(
            token.decode("utf-8") for token in raw.rstrip(b"\0").split(b"\0")
        )
    except (OSError, UnicodeDecodeError) as exc:
        raise ReferenceValidationRunnerError(
            "validation worker process argv is unavailable"
        ) from exc
    if not raw.endswith(b"\0") or not decoded or any(not token for token in decoded):
        raise ReferenceValidationRunnerError(
            "validation worker process argv is invalid"
        )
    return decoded


def _require_fixed_worker_preflight(request: Mapping[str, Any]) -> None:
    _require_source_only_python_runtime()
    worker_kind = request["worker_kind"]
    worker_flag = f"--{worker_kind}-worker"
    executable = os.path.realpath(sys.executable)
    expected_argv = (
        executable,
        "-S",
        "-B",
        "-X",
        "pycache_prefix=/dev/null",
        "-c",
        _REFERENCE_VALIDATION_FIXED_WORKER_BOOTSTRAP,
        worker_flag,
    )
    expected_environment = request["expected_worker_environment"]
    python_hash_seed = request["expected_python_hash_seed"]
    application_seed = request["expected_application_seed"]
    repository_root = Path(__file__).resolve(strict=True).parents[2]
    try:
        executable_stat = os.lstat(executable)
        running_stat = os.stat("/proc/self/exe")
    except OSError as exc:
        raise ReferenceValidationRunnerError(
            "validation worker Python executable is unavailable"
        ) from exc
    if (
        not stat.S_ISREG(executable_stat.st_mode)
        or executable_stat.st_uid != 0
        or stat.S_IMODE(executable_stat.st_mode) & 0o022
        or (executable_stat.st_dev, executable_stat.st_ino)
        != (running_stat.st_dev, running_stat.st_ino)
        or sys.flags.isolated != 0
        or sys.flags.ignore_environment != 0
        or sys.flags.no_site != 1
        or sys.flags.no_user_site != 1
        or sys.flags.dont_write_bytecode != 1
        or sys.flags.hash_randomization != (0 if python_hash_seed == 0 else 1)
        or tuple(getattr(sys, "orig_argv", ())) != expected_argv
        or _read_worker_process_argv() != expected_argv
        or sys.argv != ["-c", worker_flag]
        or Path.cwd().resolve(strict=True) != repository_root
        or dict(os.environ) != expected_environment
        or _sha256(expected_environment)
        != request["expected_worker_environment_sha256"]
        or expected_environment.get("PYTHONHASHSEED") != str(python_hash_seed)
        or expected_environment.get(REFERENCE_VALIDATION_APPLICATION_SEED_ENV)
        != str(application_seed)
        or _python_hash_probe_sha256() != request["expected_python_hash_probe_sha256"]
    ):
        raise ReferenceValidationRunnerError(
            "validation worker fixed runtime is invalid"
        )
    dependency_roots = _require_trusted_dependency_roots(
        tuple(request["dependency_roots"])
    )
    if (
        expected_environment.get("PYTHONPATH")
        != os.pathsep.join(os.fspath(root) for root in dependency_roots)
        or _observe_dependency_artifact_sha256_rows(dependency_roots)
        != request["expected_dependency_artifact_sha256_rows"]
    ):
        raise ReferenceValidationRunnerError(
            "validation worker dependency bytes do not match the supervisor"
        )
    expected_commit = request["expected_code_commit_sha"]
    if reference_validation_checked_out_code_commit_sha() != expected_commit:
        raise ReferenceValidationRunnerError(
            "validation worker commit does not match the checkout"
        )
    _require_clean_checked_out_code_commit(expected_commit)
    if (
        reference_validation_runner_source_sha256()
        != request["expected_runner_source_sha256"]
    ):
        raise ReferenceValidationRunnerError(
            "validation worker source does not match the supervisor"
        )
    _require_deadline_timer_available()
    _configure_deterministic_torch_runtime(application_seed)


def _case_worker_main_from_standard_streams() -> int:
    input_stream = getattr(sys.stdin, "buffer", sys.stdin)
    output_stream = getattr(sys.stdout, "buffer", sys.stdout)
    try:
        raw = input_stream.read(REFERENCE_VALIDATION_CASE_WORKER_MAX_REQUEST_BYTES + 1)
        if not isinstance(raw, bytes):
            return 2
        request = _load_case_worker_request(raw)
        worker_request_sha256 = _worker_request_sha256(request)
        deadline = time.monotonic() + REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS
        _require_fixed_worker_preflight(request)
        pre_evidence = build_worker_runtime_pre_evidence(
            lane=WORKER_RUNTIME_LANE_ENERGY_FORCE,
            worker_request_sha256=worker_request_sha256,
            deadline=deadline,
        )
        _write_worker_frame(
            output_stream,
            _worker_frame(
                frame_type="pre",
                worker_kind="case",
                worker_request_sha256=worker_request_sha256,
                payload=pre_evidence,
            ),
        )
        protocol, manifest = _load_frozen_case_manifest_document()
        if (
            manifest["materialization_manifest_sha256"]
            != request["expected_materialization_manifest_sha256"]
        ):
            raise ReferenceValidationRunnerError(
                "case-worker materialization manifest is cross-wired"
            )
        manifest_cases = manifest["cases"]
        payload_rows: list[dict[str, Any]] = []
        for row in _iter_case_matrix_in_process(
            protocol,
            manifest_cases,
            deadline=deadline,
        ):
            payload = row.to_dict()
            payload_rows.append(payload)
            _write_worker_frame(
                output_stream,
                _worker_frame(
                    frame_type="payload",
                    worker_kind="case",
                    worker_request_sha256=worker_request_sha256,
                    payload=payload,
                    ordinal=row.ordinal,
                ),
            )
        lifecycle = build_complete_worker_runtime_lifecycle_evidence(
            lane=WORKER_RUNTIME_LANE_ENERGY_FORCE,
            worker_request_sha256=worker_request_sha256,
            pre_evidence=pre_evidence,
            payload_rows=payload_rows,
            deadline=deadline,
        )
        _write_worker_frame(
            output_stream,
            _worker_frame(
                frame_type="completion",
                worker_kind="case",
                worker_request_sha256=worker_request_sha256,
                payload=lifecycle,
            ),
        )
    except Exception:
        return 2
    return 0


def _manifest_worker_main_from_standard_streams() -> int:
    input_stream = getattr(sys.stdin, "buffer", sys.stdin)
    output_stream = getattr(sys.stdout, "buffer", sys.stdout)
    try:
        raw = input_stream.read(REFERENCE_VALIDATION_CASE_WORKER_MAX_REQUEST_BYTES + 1)
        if not isinstance(raw, bytes):
            return 2
        request = _load_case_worker_request(raw)
        worker_request_sha256 = _worker_request_sha256(request)
        deadline = time.monotonic() + REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS
        _require_fixed_worker_preflight(request)
        pre_evidence = build_worker_runtime_pre_evidence(
            lane=WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
            worker_request_sha256=worker_request_sha256,
            deadline=deadline,
        )
        _write_worker_frame(
            output_stream,
            _worker_frame(
                frame_type="pre",
                worker_kind="manifest",
                worker_request_sha256=worker_request_sha256,
                payload=pre_evidence,
            ),
        )
        _protocol, manifest = _load_frozen_case_manifest_document()
        manifest_payload = _manifest_worker_payload(manifest)
        _write_worker_frame(
            output_stream,
            _worker_frame(
                frame_type="payload",
                worker_kind="manifest",
                worker_request_sha256=worker_request_sha256,
                payload=manifest_payload,
                ordinal=0,
            ),
        )
        lifecycle = build_complete_worker_runtime_lifecycle_evidence(
            lane=WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
            worker_request_sha256=worker_request_sha256,
            pre_evidence=pre_evidence,
            payload_rows=[manifest_payload],
            deadline=deadline,
        )
        _write_worker_frame(
            output_stream,
            _worker_frame(
                frame_type="completion",
                worker_kind="manifest",
                worker_request_sha256=worker_request_sha256,
                payload=lifecycle,
            ),
        )
    except Exception:
        return 2
    return 0


def _fixed_worker_main(arguments: list[str]) -> int:
    if arguments == ["--manifest-worker"]:
        return _manifest_worker_main_from_standard_streams()
    if arguments == ["--case-worker"]:
        return _case_worker_main_from_standard_streams()
    return 2


def _case_worker_environment(
    environment_variable_rows: Sequence[tuple[str, str]],
    *,
    dependency_python_path: str,
) -> dict[str, str]:
    environment = dict(environment_variable_rows)
    expected_receipt_names = _REFERENCE_VALIDATION_WORKER_ENVIRONMENT_NAMES - {
        "HOME",
        "PATH",
        "PYTHONNOUSERSITE",
        "PYTHONPATH",
    }
    if (
        set(environment) != expected_receipt_names
        or len(environment) != len(environment_variable_rows)
        or not dependency_python_path
    ):
        raise ReferenceValidationRunnerError(
            "case-worker receipt environment is incomplete"
        )
    environment.update(
        {
            "HOME": "/nonexistent",
            "PATH": "/usr/bin:/bin",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": dependency_python_path,
        }
    )
    return environment


def _fixed_worker_dependency_python_path() -> str:
    """Return only dependency roots established by the isolated bootstrap."""

    import numpy
    import torch

    roots = list(_require_isolated_python_bootstrap_runtime())
    for module, name in ((torch, "Torch"), (numpy, "NumPy")):
        module_path = Path(module.__file__).resolve(strict=True)
        if not any(module_path.is_relative_to(root) for root in roots):
            raise ReferenceValidationRunnerError(
                f"validation-worker {name} path is outside the fixed dependency roots"
            )
    return os.pathsep.join(os.fspath(root) for root in roots)


def _worker_request_sha256(request: Mapping[str, Any]) -> str:
    return _sha256(dict(request))


def _worker_frame(
    *,
    frame_type: str,
    worker_kind: str,
    worker_request_sha256: str,
    payload: Mapping[str, Any],
    ordinal: int | None = None,
) -> dict[str, Any]:
    if frame_type not in {"pre", "payload", "completion"} or worker_kind not in {
        "manifest",
        "case",
    }:
        raise ReferenceValidationRunnerError(
            "validation-worker frame identity is invalid"
        )
    request_sha256 = _require_sha256(
        worker_request_sha256,
        name="validation-worker frame request",
    )
    if not isinstance(payload, Mapping):
        raise ReferenceValidationRunnerError(
            "validation-worker frame payload is invalid"
        )
    frame: dict[str, Any] = {
        "schema_id": REFERENCE_VALIDATION_WORKER_FRAME_SCHEMA_ID,
        "frame_type": frame_type,
        "worker_kind": worker_kind,
        "worker_request_sha256": request_sha256,
    }
    if frame_type == "payload":
        if type(ordinal) is not int or ordinal < 0:
            raise ReferenceValidationRunnerError(
                "validation-worker payload frame ordinal is invalid"
            )
        frame["ordinal"] = ordinal
        frame["payload"] = dict(payload)
    else:
        if ordinal is not None:
            raise ReferenceValidationRunnerError(
                "validation-worker lifecycle frame cannot have an ordinal"
            )
        frame["evidence"] = dict(payload)
    return frame


def _decode_worker_frame(raw: bytes) -> dict[str, Any]:
    if not raw.endswith(b"\n"):
        raise ReferenceValidationRunnerError(
            "validation-worker output frame is not newline terminated"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceValidationRunnerError(
                    "validation-worker output frame has a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        frame = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationRunnerError(
            "validation-worker output frame is not canonical ASCII JSON"
        ) from exc
    if not isinstance(frame, dict) or _canonical_bytes(frame) + b"\n" != raw:
        raise ReferenceValidationRunnerError(
            "validation-worker output frame is not canonical ASCII JSON"
        )
    frame_type = frame.get("frame_type")
    expected_fields = {
        "schema_id",
        "frame_type",
        "worker_kind",
        "worker_request_sha256",
    }
    expected_fields.update(
        {"ordinal", "payload"} if frame_type == "payload" else {"evidence"}
    )
    if (
        set(frame) != expected_fields
        or frame.get("schema_id") != REFERENCE_VALIDATION_WORKER_FRAME_SCHEMA_ID
        or frame_type not in {"pre", "payload", "completion"}
        or frame.get("worker_kind") not in {"manifest", "case"}
        or not isinstance(
            frame.get("payload" if frame_type == "payload" else "evidence"), dict
        )
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker output frame schema is invalid"
        )
    _require_sha256(
        frame["worker_request_sha256"], name="validation-worker output request"
    )
    if frame_type == "payload" and (
        type(frame["ordinal"]) is not int or frame["ordinal"] < 0
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker output frame ordinal is invalid"
        )
    return frame


def _write_worker_frame(output_stream: Any, frame: Mapping[str, Any]) -> None:
    output_stream.write(_canonical_bytes(dict(frame)) + b"\n")
    output_stream.flush()


def _require_worker_frame_binding(
    frame: Mapping[str, Any],
    *,
    frame_type: str,
    worker_kind: str,
    worker_request_sha256: str,
    ordinal: int | None = None,
) -> dict[str, Any]:
    if (
        frame.get("frame_type") != frame_type
        or frame.get("worker_kind") != worker_kind
        or frame.get("worker_request_sha256") != worker_request_sha256
        or (frame_type == "payload" and frame.get("ordinal") != ordinal)
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker output frame order or request binding is invalid"
        )
    return dict(frame)


def _require_worker_pre_frame(
    frame: Mapping[str, Any],
    *,
    worker_kind: str,
    worker_request_sha256: str,
    lane: str,
) -> dict[str, Any]:
    bound = _require_worker_frame_binding(
        frame,
        frame_type="pre",
        worker_kind=worker_kind,
        worker_request_sha256=worker_request_sha256,
    )
    try:
        return require_worker_runtime_pre_evidence(
            bound["evidence"],
            expected_lane=lane,
            expected_worker_request_sha256=worker_request_sha256,
        )
    except ValidationNativeRuntimeIdentityError as exc:
        raise ReferenceValidationRunnerError(
            "validation-worker pre evidence is invalid"
        ) from exc


def _decode_case_worker_line(raw: bytes) -> ReferenceValidationCaseObservation:
    if not raw.endswith(b"\n"):
        raise ReferenceValidationRunnerError("case-worker output line is not framed")

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceValidationRunnerError(
                    "case-worker output contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        payload = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationRunnerError(
            "case-worker output is not canonical ASCII JSON"
        ) from exc
    if not isinstance(payload, dict) or _canonical_bytes(payload) + b"\n" != raw:
        raise ReferenceValidationRunnerError(
            "case-worker output is not canonical ASCII JSON"
        )
    return _case_observation_from_payload(payload)


def _require_case_matches_frozen_matrix(
    row: ReferenceValidationCaseObservation,
    ordinal: int,
    case: CPUReferenceValidationCase,
    manifest_case: Mapping[str, Any],
) -> None:
    expected_identity = (
        ordinal,
        case.case_id,
        case.input_sha256,
        manifest_case.get("materialization_sha256"),
        case.expected_outcome,
        case.expected_error_code,
    )
    observed_identity = (
        row.ordinal,
        row.case_id,
        row.case_input_sha256,
        row.materialization_sha256,
        row.expected_outcome,
        row.expected_error_code,
    )
    variants = manifest_case.get("variants")
    if not isinstance(variants, list):
        raise ReferenceValidationRunnerError(
            "frozen worker manifest variants are invalid"
        )
    expected_variants = tuple(
        (
            variant_ordinal,
            payload.get("variant_id"),
            payload.get("runtime_input_sha256"),
            payload.get("oracle_input_sha256"),
        )
        for variant_ordinal, payload in enumerate(variants)
    )
    observed_variants = tuple(
        (
            variant.ordinal,
            variant.variant_id,
            variant.runtime_input_sha256,
            variant.oracle_input_sha256,
        )
        for variant in row.variant_results
    )
    metric_map = {
        metric.metric_id: metric
        for metric in frozen_cpu_reference_validation_protocol().metrics
    }
    expected_metrics = tuple(
        (
            metric_id,
            metric_map[metric_id].unit,
            metric_map[metric_id].threshold_operator,
            metric_map[metric_id].threshold_value,
        )
        for metric_id in case.required_metric_ids
    )
    observed_metrics = tuple(
        (
            metric.metric_id,
            metric.unit,
            metric.threshold_operator,
            metric.threshold_value,
        )
        for metric in row.metric_values
    )
    recomputed_metrics = _metric_observations(
        case,
        row.variant_results,
        metric_map,
    )
    if (
        observed_identity != expected_identity
        or observed_variants != expected_variants
        or observed_metrics != expected_metrics
        or _canonical_bytes([metric.to_dict() for metric in row.metric_values])
        != _canonical_bytes([metric.to_dict() for metric in recomputed_metrics])
    ):
        raise ReferenceValidationRunnerError(
            "case-worker output is cross-wired to the frozen matrix"
        )


def _fixed_worker_request(
    *,
    worker_kind: str,
    expected_materialization_manifest_sha256: str | None,
    expected_code_commit_sha: str,
    expected_runner_source_sha256: str,
    expected_source_manifest_sha256: str,
    expected_authorization_nonce_sha256: str,
    expected_runner_start_record_sha256: str | None,
    expected_dependency_artifact_sha256_rows: Mapping[str, str],
    dependency_roots: Sequence[Path],
    environment_receipt: ReferenceValidationExecutionEnvironmentReceipt,
    worker_environment: Mapping[str, str],
) -> dict[str, Any]:
    if worker_kind not in {"manifest", "case"}:
        raise ReferenceValidationRunnerError("validation-worker kind is invalid")
    if worker_kind == "manifest":
        if (
            expected_materialization_manifest_sha256 is not None
            or expected_runner_start_record_sha256 is not None
        ):
            raise ReferenceValidationRunnerError(
                "manifest-worker cannot receive post-materialization identities"
            )
        materialization_manifest_sha256 = None
        runner_start_record_sha256 = None
    else:
        materialization_manifest_sha256 = _require_sha256(
            expected_materialization_manifest_sha256,
            name="case-worker materialization manifest",
        )
        runner_start_record_sha256 = _require_sha256(
            expected_runner_start_record_sha256,
            name="case-worker runner-start record",
        )
    if set(worker_environment) != _REFERENCE_VALIDATION_WORKER_ENVIRONMENT_NAMES:
        raise ReferenceValidationRunnerError("validation-worker environment is invalid")
    normalized_dependency_rows = dict(
        _normalize_dependency_rows(expected_dependency_artifact_sha256_rows)
    )
    if tuple(normalized_dependency_rows) != (
        REFERENCE_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker dependency artifact schema is invalid"
        )
    normalized_dependency_roots = [os.fspath(root) for root in dependency_roots]
    if (
        not normalized_dependency_roots
        or len(set(normalized_dependency_roots)) != len(normalized_dependency_roots)
        or os.pathsep.join(normalized_dependency_roots)
        != worker_environment.get("PYTHONPATH")
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker dependency roots are invalid"
        )
    request: dict[str, Any] = {
        "schema_id": REFERENCE_VALIDATION_CASE_WORKER_REQUEST_SCHEMA_ID,
        "worker_kind": worker_kind,
        "expected_protocol_sha256": FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256,
        "expected_materialization_manifest_sha256": materialization_manifest_sha256,
        "expected_case_count": REFERENCE_VALIDATION_RUNNER_MAX_CASES,
        "expected_variant_count": REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS,
        "expected_code_commit_sha": _require_commit_sha(
            expected_code_commit_sha,
            name="validation-worker supervisor commit",
        ),
        "expected_runner_source_sha256": _require_sha256(
            expected_runner_source_sha256,
            name="validation-worker supervisor source",
        ),
        "expected_source_manifest_sha256": _require_sha256(
            expected_source_manifest_sha256,
            name="validation-worker supervisor source manifest",
        ),
        "expected_dependency_artifact_sha256_rows": normalized_dependency_rows,
        "dependency_roots": normalized_dependency_roots,
        "expected_environment_receipt_sha256": _require_sha256(
            environment_receipt.receipt_sha256,
            name="validation-worker environment receipt",
        ),
        "expected_environment_fingerprint_sha256": _require_sha256(
            environment_receipt.environment_fingerprint_sha256,
            name="validation-worker environment fingerprint",
        ),
        "expected_authorization_nonce_sha256": _require_sha256(
            expected_authorization_nonce_sha256,
            name="validation-worker authorization nonce",
        ),
        "expected_runner_start_record_sha256": runner_start_record_sha256,
        "expected_python_hash_seed": _require_worker_seed(
            environment_receipt.python_hash_seed,
            name="validation-worker Python hash seed",
            maximum=2**32 - 1,
        ),
        "expected_application_seed": _require_worker_seed(
            environment_receipt.application_seed,
            name="validation-worker application seed",
            maximum=2**63 - 1,
        ),
        "expected_worker_environment": dict(worker_environment),
        "expected_worker_environment_sha256": _sha256(dict(worker_environment)),
        "expected_python_hash_probe_sha256": _python_hash_probe_sha256(),
    }
    if (
        len(_canonical_bytes(request)) + 1
        > REFERENCE_VALIDATION_CASE_WORKER_MAX_REQUEST_BYTES
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker runtime binding exceeds the request limit"
        )
    return request


def _start_fixed_validation_worker(
    worker_flag: str,
    request: Mapping[str, Any],
) -> Any:
    import subprocess

    if worker_flag not in {"--manifest-worker", "--case-worker"}:
        raise ReferenceValidationRunnerError("validation-worker operation is invalid")
    expected_kind = worker_flag.removeprefix("--").removesuffix("-worker")
    raw_environment = request.get("expected_worker_environment")
    if (
        request.get("worker_kind") != expected_kind
        or not isinstance(raw_environment, Mapping)
        or set(raw_environment) != _REFERENCE_VALIDATION_WORKER_ENVIRONMENT_NAMES
        or any(not isinstance(value, str) for value in raw_environment.values())
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker launch binding is invalid"
        )
    executable = Path(os.path.realpath(sys.executable))
    try:
        executable_stat = executable.stat()
        running_stat = os.stat("/proc/self/exe")
    except OSError as exc:
        raise ReferenceValidationRunnerError(
            "validation-worker Python executable is unavailable"
        ) from exc
    if (
        not executable.is_absolute()
        or not stat.S_ISREG(executable_stat.st_mode)
        or executable_stat.st_uid != 0
        or stat.S_IMODE(executable_stat.st_mode) & 0o022
        or (executable_stat.st_dev, executable_stat.st_ino)
        != (running_stat.st_dev, running_stat.st_ino)
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker Python executable does not match the running interpreter"
        )
    repository_root = Path(__file__).resolve(strict=True).parents[2]
    try:
        return subprocess.Popen(
            [
                os.fspath(executable),
                "-S",
                "-B",
                "-X",
                "pycache_prefix=/dev/null",
                "-c",
                _REFERENCE_VALIDATION_FIXED_WORKER_BOOTSTRAP,
                worker_flag,
            ],
            cwd=repository_root,
            env=dict(raw_environment),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except (OSError, ValueError) as exc:
        raise ReferenceValidationRunnerError(
            "validation-worker process could not be started"
        ) from exc


def _communicate_fixed_validation_worker(
    process: Any,
    request: Mapping[str, Any],
    *,
    deadline: float,
) -> BoundedWorkerProcessCommunicationEvidence:
    try:
        return communicate_bounded_worker_process_with_evidence(
            process,
            _canonical_bytes(dict(request)) + b"\n",
            deadline=deadline,
            max_output_bytes=REFERENCE_VALIDATION_CASE_WORKER_MAX_OUTPUT_BYTES,
        )
    except ValidationNativeRuntimeIdentityError as exc:
        raise ReferenceValidationRunnerError(
            "validation-worker bounded communication failed"
        ) from exc


def _worker_communication_result(
    value: object,
) -> tuple[bytes, bool, bool, bool, bool, bool, int | None]:
    """Validate the private communication result; accept legacy triples in tests."""

    if isinstance(value, BoundedWorkerProcessCommunicationEvidence):
        return (
            value.raw_output_prefix,
            value.timed_out,
            value.succeeded,
            value.output_exceeded,
            value.communication_failed,
            value.request_fully_written,
            value.final_returncode,
        )
    if not isinstance(value, tuple) or len(value) not in {3, 4}:
        raise ReferenceValidationRunnerError(
            "validation-worker communication result is invalid"
        )
    output, timed_out, succeeded = value[:3]
    output_overflow = value[3] if len(value) == 4 else False
    if (
        not isinstance(output, bytes)
        or type(timed_out) is not bool
        or type(succeeded) is not bool
        or type(output_overflow) is not bool
    ):
        raise ReferenceValidationRunnerError(
            "validation-worker communication result is invalid"
        )
    return (
        output,
        timed_out,
        succeeded,
        output_overflow,
        False,
        True,
        0 if succeeded else None,
    )


def _manifest_cases_from_worker_output(
    raw: bytes,
    protocol: Any,
) -> list[Mapping[str, Any]]:
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise ReferenceValidationRunnerError(
            "manifest-worker output framing is invalid"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceValidationRunnerError(
                    "manifest-worker output contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        manifest = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationRunnerError(
            "manifest-worker output is not canonical ASCII JSON"
        ) from exc
    expected_fields = {
        "schema_id",
        "materializer_id",
        "materializer_version",
        "materializer_source_sha256",
        "protocol_sha256",
        "fixture_manifest_sha256",
        "materialization_policy",
        "coverage",
        "cases",
        "result_collection_performed",
        "energy_or_force_values_present",
        "metric_values_present",
        "validation_execution_authorized",
        "scientifically_validated",
        "claim_safe",
        "materialization_manifest_sha256",
    }
    if (
        not isinstance(manifest, dict)
        or set(manifest) != expected_fields
        or _canonical_bytes(manifest) + b"\n" != raw
    ):
        raise ReferenceValidationRunnerError(
            "manifest-worker output is not the exact canonical schema"
        )
    manifest_projection = dict(manifest)
    manifest_sha256 = manifest_projection.pop("materialization_manifest_sha256")
    if manifest_sha256 != _sha256(manifest_projection):
        raise ReferenceValidationRunnerError(
            "manifest-worker output identity is invalid"
        )
    _require_sha256(
        manifest.get("materializer_source_sha256"),
        name="manifest-worker materializer source",
    )
    if (
        manifest.get("schema_id")
        != "betelgeuze.engine_v2_reference_validation_materializer/1.0.0"
        or manifest.get("materializer_id")
        != "cpu_reference_validation_exact_fixture_materializer/1.0.0"
        or manifest.get("materializer_version") != "1.0.0"
        or manifest.get("protocol_sha256")
        != FROZEN_CPU_REFERENCE_VALIDATION_PROTOCOL_SHA256
        or manifest.get("fixture_manifest_sha256") != protocol.fixture_manifest_sha256
        or manifest.get("materialization_policy")
        != {
            "device": "cpu",
            "coordinate_dtype": "float64",
            "coordinate_unit": "angstrom",
            "max_neighbors": 16,
            "max_atoms_per_cell": 16,
            "applicability_domain": {
                "max_atoms": 16,
                "max_bonds": 32,
                "max_angles": 64,
                "max_torsions": 128,
                "max_nonbonded_pairs": 120,
                "periodic_orthorhombic_supported": True,
                "minimum_pair_distance_angstrom": 1.0e-6,
            },
            "case_order_matches_protocol": True,
            "all_failure_rows_retained": True,
            "skipped_cases_allowed": False,
        }
        or manifest.get("coverage")
        != {
            "fixture_count": 7,
            "mutation_count": 20,
            "case_count": REFERENCE_VALIDATION_RUNNER_MAX_CASES,
            "variant_count": REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS,
            "expected_pass_case_count": 15,
            "expected_fail_closed_case_count": 12,
        }
        or any(
            manifest.get(name) is not False
            for name in (
                "result_collection_performed",
                "energy_or_force_values_present",
                "metric_values_present",
                "validation_execution_authorized",
                "scientifically_validated",
                "claim_safe",
            )
        )
    ):
        raise ReferenceValidationRunnerError(
            "manifest-worker output contradicts the frozen validation policy"
        )
    manifest_cases = manifest.get("cases")
    if not isinstance(manifest_cases, list) or len(manifest_cases) != (
        REFERENCE_VALIDATION_RUNNER_MAX_CASES
    ):
        raise ReferenceValidationRunnerError("manifest-worker case coverage is invalid")
    metric_map = {row.metric_id: row for row in protocol.metrics}
    for ordinal, (case, manifest_case) in enumerate(
        zip(protocol.cases, manifest_cases, strict=True)
    ):
        retained = _failed_case_from_frozen_manifest(
            ordinal,
            case,
            manifest_case,
            metric_map=metric_map,
            observed_status="unexpected_error",
            observed_error_code="manifest_preflight_validation",
        )
        _require_case_matches_frozen_matrix(
            retained,
            ordinal,
            case,
            manifest_case,
        )
    return manifest_cases


def _manifest_worker_result_from_output(
    raw: bytes,
    *,
    request: Mapping[str, Any],
    protocol: Any,
) -> tuple[list[Mapping[str, Any]], str, dict[str, Any]]:
    frames = raw.splitlines(keepends=True)
    if len(frames) != 3:
        raise ReferenceValidationRunnerError(
            "manifest-worker output frame count is invalid"
        )
    request_sha256 = _worker_request_sha256(request)
    pre_frame = _decode_worker_frame(frames[0])
    pre_evidence = _require_worker_pre_frame(
        pre_frame,
        worker_kind="manifest",
        worker_request_sha256=request_sha256,
        lane=WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
    )
    payload_frame = _require_worker_frame_binding(
        _decode_worker_frame(frames[1]),
        frame_type="payload",
        worker_kind="manifest",
        worker_request_sha256=request_sha256,
        ordinal=0,
    )
    manifest_payload = payload_frame["payload"]
    if set(manifest_payload) != {"ordinal", "case_id", "materialization_manifest"} or (
        manifest_payload.get("ordinal"),
        manifest_payload.get("case_id"),
    ) != (0, "materialization_manifest"):
        raise ReferenceValidationRunnerError(
            "manifest-worker payload wrapper is invalid"
        )
    manifest = manifest_payload["materialization_manifest"]
    if not isinstance(manifest, dict):
        raise ReferenceValidationRunnerError(
            "manifest-worker payload document is invalid"
        )
    manifest_cases = _manifest_cases_from_worker_output(
        _canonical_bytes(manifest) + b"\n",
        protocol,
    )
    completion_frame = _require_worker_frame_binding(
        _decode_worker_frame(frames[2]),
        frame_type="completion",
        worker_kind="manifest",
        worker_request_sha256=request_sha256,
    )
    try:
        lifecycle = require_worker_runtime_lifecycle_evidence(
            completion_frame["evidence"],
            expected_lane=WORKER_RUNTIME_LANE_ENERGY_FORCE_MANIFEST,
            expected_worker_request_sha256=request_sha256,
            expected_payload_rows=[manifest_payload],
        )
    except ValidationNativeRuntimeIdentityError as exc:
        raise ReferenceValidationRunnerError(
            "manifest-worker lifecycle evidence is invalid"
        ) from exc
    if lifecycle["completion_state"] != "complete" or lifecycle["pre"] != pre_evidence:
        raise ReferenceValidationRunnerError(
            "manifest-worker lifecycle is incomplete or cross-wired"
        )
    return (
        manifest_cases,
        _require_sha256(
            manifest.get("materialization_manifest_sha256"),
            name="manifest-worker materialization manifest",
        ),
        lifecycle,
    )


def _run_supervised_frozen_case_matrix(
    *,
    expected_code_commit_sha: str,
    expected_runner_source_sha256: str,
    expected_dependency_artifact_sha256_rows: Mapping[str, str],
    dependency_roots: Sequence[Path],
    environment_receipt: ReferenceValidationExecutionEnvironmentReceipt,
    worker_environment: Mapping[str, str],
    deadline: float,
) -> tuple[Any, list[Mapping[str, Any]], str, dict[str, Any], dict[str, Any]]:
    """Materialize frozen identities in a child before consuming the start marker."""

    protocol = frozen_cpu_reference_validation_protocol()
    request = _fixed_worker_request(
        worker_kind="manifest",
        expected_materialization_manifest_sha256=None,
        expected_code_commit_sha=expected_code_commit_sha,
        expected_runner_source_sha256=expected_runner_source_sha256,
        expected_source_manifest_sha256=environment_receipt.source_manifest_sha256,
        expected_authorization_nonce_sha256=(
            environment_receipt.authorization_nonce_sha256
        ),
        expected_runner_start_record_sha256=None,
        expected_dependency_artifact_sha256_rows=(
            expected_dependency_artifact_sha256_rows
        ),
        dependency_roots=dependency_roots,
        environment_receipt=environment_receipt,
        worker_environment=worker_environment,
    )
    process = _start_fixed_validation_worker("--manifest-worker", request)
    try:
        (
            output,
            timed_out,
            succeeded,
            output_overflow,
            communication_failed,
            request_fully_written,
            final_returncode,
        ) = _worker_communication_result(
            _communicate_fixed_validation_worker(process, request, deadline=deadline)
        )
    except ReferenceValidationRunnerError as exc:
        raise ReferenceValidationRunnerError(
            "supervised materialization preflight did not complete"
        ) from exc
    if timed_out or output_overflow or not succeeded:
        raise ReferenceValidationRunnerError(
            "supervised materialization preflight did not complete"
        )
    manifest_cases, manifest_sha256, lifecycle = _manifest_worker_result_from_output(
        output,
        request=request,
        protocol=protocol,
    )
    try:
        require_complete_worker_runtime_process_id(
            lifecycle,
            expected_process_id=process.pid,
        )
    except (AttributeError, ValidationNativeRuntimeIdentityError) as exc:
        raise ReferenceValidationRunnerError(
            "manifest-worker lifecycle process identity is invalid"
        ) from exc
    provenance = _build_worker_execution_provenance(
        worker_kind="manifest",
        request=request,
        supervisor_launched_child_process_id=process.pid,
        transcript=output,
        lifecycle=lifecycle,
        accepted_payload_rows=[
            _manifest_worker_payload(_load_frozen_case_manifest_document()[1])
        ],
        failure_stage=None,
        child_exit_code=final_returncode,
        timed_out=False,
        output_overflow=False,
        communication_failed=communication_failed,
        request_fully_written=request_fully_written,
    )
    return protocol, manifest_cases, manifest_sha256, lifecycle, provenance


def _supervisor_failure_complete_case_matrix(
    protocol: Any,
    manifest_cases: list[Mapping[str, Any]],
    *,
    observed_status: str,
    observed_error_code: str,
) -> tuple[ReferenceValidationCaseObservation, ...]:
    metric_map = {row.metric_id: row for row in protocol.metrics}
    return tuple(
        _failed_case_from_frozen_manifest(
            ordinal,
            protocol.cases[ordinal],
            manifest_cases[ordinal],
            metric_map=metric_map,
            observed_status=observed_status,
            observed_error_code=observed_error_code,
            observation_origin="supervisor",
        )
        for ordinal in range(REFERENCE_VALIDATION_RUNNER_MAX_CASES)
    )


def _case_worker_pre_evidence_from_output(
    output: bytes,
    *,
    worker_request_sha256: str,
) -> dict[str, Any] | None:
    first_line = output.splitlines(keepends=True)[:1]
    if not first_line:
        return None
    try:
        return _require_worker_pre_frame(
            _decode_worker_frame(first_line[0]),
            worker_kind="case",
            worker_request_sha256=worker_request_sha256,
            lane=WORKER_RUNTIME_LANE_ENERGY_FORCE,
        )
    except ReferenceValidationRunnerError:
        return None


def _incomplete_case_worker_result(
    protocol: Any,
    manifest_cases: list[Mapping[str, Any]],
    *,
    request: Mapping[str, Any],
    failure_code: str,
    observed_status: str,
    pre_evidence: Mapping[str, Any] | None,
    supervisor_launched_child_process_id: int | None,
    transcript: bytes,
    failure_stage: str,
    child_exit_code: int | None,
    timed_out: bool,
    output_overflow: bool,
    communication_failed: bool,
    request_fully_written: bool,
) -> tuple[
    tuple[ReferenceValidationCaseObservation, ...],
    dict[str, Any],
    dict[str, Any],
]:
    worker_request_sha256 = _worker_request_sha256(request)
    try:
        lifecycle = build_incomplete_worker_runtime_lifecycle_evidence(
            lane=WORKER_RUNTIME_LANE_ENERGY_FORCE,
            worker_request_sha256=worker_request_sha256,
            failure_code=failure_code,
            pre_evidence=pre_evidence,
        )
    except (
        ValidationNativeRuntimeIdentityError
    ) as exc:  # pragma: no cover - pre evidence already checked
        raise ReferenceValidationRunnerError(
            "case-worker incomplete lifecycle could not be built"
        ) from exc
    rows = _supervisor_failure_complete_case_matrix(
        protocol,
        manifest_cases,
        observed_status=observed_status,
        observed_error_code=failure_code,
    )
    provenance = _build_worker_execution_provenance(
        worker_kind="case",
        request=request,
        supervisor_launched_child_process_id=(supervisor_launched_child_process_id),
        transcript=transcript,
        lifecycle=lifecycle,
        accepted_payload_rows=None,
        failure_stage=failure_stage,
        child_exit_code=child_exit_code,
        timed_out=timed_out,
        output_overflow=output_overflow,
        communication_failed=communication_failed,
        request_fully_written=request_fully_written,
    )
    return rows, lifecycle, provenance


def _run_supervised_case_matrix(
    protocol: Any,
    manifest_cases: list[Mapping[str, Any]],
    *,
    materialization_manifest_sha256: str,
    expected_code_commit_sha: str,
    expected_runner_source_sha256: str,
    expected_runner_start_record_sha256: str,
    expected_dependency_artifact_sha256_rows: Mapping[str, str],
    dependency_roots: Sequence[Path],
    environment_receipt: ReferenceValidationExecutionEnvironmentReceipt,
    worker_environment: Mapping[str, str],
    deadline: float,
) -> tuple[
    tuple[ReferenceValidationCaseObservation, ...],
    dict[str, Any],
    dict[str, Any],
]:
    """Run the matrix in one fixed child and hard-kill native stalls at deadline."""

    request = _fixed_worker_request(
        worker_kind="case",
        expected_materialization_manifest_sha256=materialization_manifest_sha256,
        expected_code_commit_sha=expected_code_commit_sha,
        expected_runner_source_sha256=expected_runner_source_sha256,
        expected_source_manifest_sha256=environment_receipt.source_manifest_sha256,
        expected_authorization_nonce_sha256=(
            environment_receipt.authorization_nonce_sha256
        ),
        expected_runner_start_record_sha256=expected_runner_start_record_sha256,
        expected_dependency_artifact_sha256_rows=(
            expected_dependency_artifact_sha256_rows
        ),
        dependency_roots=dependency_roots,
        environment_receipt=environment_receipt,
        worker_environment=worker_environment,
    )
    worker_request_sha256 = _worker_request_sha256(request)
    try:
        process = _start_fixed_validation_worker("--case-worker", request)
    except ReferenceValidationRunnerError:
        return _incomplete_case_worker_result(
            protocol,
            manifest_cases,
            request=request,
            failure_code="case_worker_start_failed",
            observed_status="unexpected_error",
            pre_evidence=None,
            supervisor_launched_child_process_id=None,
            transcript=b"",
            failure_stage="worker_start",
            child_exit_code=None,
            timed_out=False,
            output_overflow=False,
            communication_failed=False,
            request_fully_written=False,
        )
    try:
        (
            output,
            timed_out,
            succeeded,
            output_overflow,
            communication_failed,
            request_fully_written,
            final_returncode,
        ) = _worker_communication_result(
            _communicate_fixed_validation_worker(process, request, deadline=deadline)
        )
    except ReferenceValidationRunnerError:
        return _incomplete_case_worker_result(
            protocol,
            manifest_cases,
            request=request,
            failure_code="case_worker_protocol_invalid",
            observed_status="unexpected_error",
            pre_evidence=None,
            supervisor_launched_child_process_id=process.pid,
            transcript=b"",
            failure_stage="worker_communication",
            child_exit_code=getattr(process, "returncode", None),
            timed_out=False,
            output_overflow=False,
            communication_failed=True,
            request_fully_written=False,
        )
    pre_evidence = _case_worker_pre_evidence_from_output(
        output,
        worker_request_sha256=worker_request_sha256,
    )
    if communication_failed or not request_fully_written:
        return _incomplete_case_worker_result(
            protocol,
            manifest_cases,
            request=request,
            failure_code="case_worker_protocol_invalid",
            observed_status="unexpected_error",
            pre_evidence=pre_evidence,
            supervisor_launched_child_process_id=process.pid,
            transcript=output,
            failure_stage="worker_communication",
            child_exit_code=final_returncode,
            timed_out=timed_out,
            output_overflow=output_overflow,
            communication_failed=communication_failed,
            request_fully_written=request_fully_written,
        )
    if output_overflow:
        return _incomplete_case_worker_result(
            protocol,
            manifest_cases,
            request=request,
            failure_code="case_worker_protocol_invalid",
            observed_status="unexpected_error",
            pre_evidence=pre_evidence,
            supervisor_launched_child_process_id=process.pid,
            transcript=output,
            failure_stage="worker_output_overflow",
            child_exit_code=final_returncode,
            timed_out=False,
            output_overflow=True,
            communication_failed=communication_failed,
            request_fully_written=request_fully_written,
        )
    if timed_out:
        return _incomplete_case_worker_result(
            protocol,
            manifest_cases,
            request=request,
            failure_code="runner_time_budget_exhausted",
            observed_status="time_budget_exhausted",
            pre_evidence=pre_evidence,
            supervisor_launched_child_process_id=process.pid,
            transcript=output,
            failure_stage="worker_timeout",
            child_exit_code=final_returncode,
            timed_out=True,
            output_overflow=False,
            communication_failed=communication_failed,
            request_fully_written=request_fully_written,
        )
    if not succeeded:
        return _incomplete_case_worker_result(
            protocol,
            manifest_cases,
            request=request,
            failure_code="case_worker_nonzero_exit",
            observed_status="unexpected_error",
            pre_evidence=pre_evidence,
            supervisor_launched_child_process_id=process.pid,
            transcript=output,
            failure_stage="worker_exit",
            child_exit_code=final_returncode,
            timed_out=False,
            output_overflow=False,
            communication_failed=communication_failed,
            request_fully_written=request_fully_written,
        )

    frames = output.splitlines(keepends=True)
    accepted: list[ReferenceValidationCaseObservation] = []
    try:
        if len(frames) != REFERENCE_VALIDATION_RUNNER_MAX_CASES + 2:
            raise ReferenceValidationRunnerError(
                "case-worker output frame count is invalid"
            )
        exact_pre_evidence = _require_worker_pre_frame(
            _decode_worker_frame(frames[0]),
            worker_kind="case",
            worker_request_sha256=worker_request_sha256,
            lane=WORKER_RUNTIME_LANE_ENERGY_FORCE,
        )
        for ordinal, raw_line in enumerate(frames[1:-1]):
            payload_frame = _require_worker_frame_binding(
                _decode_worker_frame(raw_line),
                frame_type="payload",
                worker_kind="case",
                worker_request_sha256=worker_request_sha256,
                ordinal=ordinal,
            )
            row = _case_observation_from_payload(payload_frame["payload"])
            if row.observation_origin != "worker":
                raise ReferenceValidationRunnerError(
                    "case-worker supplied a supervisor-origin row"
                )
            _require_case_matches_frozen_matrix(
                row,
                ordinal,
                protocol.cases[ordinal],
                manifest_cases[ordinal],
            )
            accepted.append(row)
        completion_frame = _require_worker_frame_binding(
            _decode_worker_frame(frames[-1]),
            frame_type="completion",
            worker_kind="case",
            worker_request_sha256=worker_request_sha256,
        )
        payload_rows = [row.to_dict() for row in accepted]
        lifecycle = require_worker_runtime_lifecycle_evidence(
            completion_frame["evidence"],
            expected_lane=WORKER_RUNTIME_LANE_ENERGY_FORCE,
            expected_worker_request_sha256=worker_request_sha256,
            expected_payload_rows=payload_rows,
        )
        if (
            lifecycle["completion_state"] != "complete"
            or lifecycle["pre"] != exact_pre_evidence
        ):
            raise ReferenceValidationRunnerError(
                "case-worker lifecycle is incomplete or cross-wired"
            )
        require_complete_worker_runtime_process_id(
            lifecycle,
            expected_process_id=process.pid,
        )
    except (ReferenceValidationRunnerError, ValidationNativeRuntimeIdentityError):
        return _incomplete_case_worker_result(
            protocol,
            manifest_cases,
            request=request,
            failure_code="case_worker_protocol_invalid",
            observed_status="unexpected_error",
            pre_evidence=pre_evidence,
            supervisor_launched_child_process_id=process.pid,
            transcript=output,
            failure_stage="worker_protocol",
            child_exit_code=final_returncode,
            timed_out=False,
            output_overflow=False,
            communication_failed=communication_failed,
            request_fully_written=request_fully_written,
        )
    if len(accepted) != REFERENCE_VALIDATION_RUNNER_MAX_CASES:
        raise ReferenceValidationRunnerError(
            "case-worker accepted coverage is internally inconsistent"
        )
    provenance = _build_worker_execution_provenance(
        worker_kind="case",
        request=request,
        supervisor_launched_child_process_id=process.pid,
        transcript=output,
        lifecycle=lifecycle,
        accepted_payload_rows=[row.to_dict() for row in accepted],
        failure_stage=None,
        child_exit_code=final_returncode,
        timed_out=False,
        output_overflow=False,
        communication_failed=communication_failed,
        request_fully_written=request_fully_written,
    )
    return tuple(accepted), lifecycle, provenance


def run_bounded_cpu_reference_validation(
    artifact_output_root: str | os.PathLike[str],
    authorization_nonce_sha256: str,
    *,
    expected_environment_receipt_sha256: str,
    expected_code_commit_sha: str,
    expected_dependency_artifact_sha256_rows: Mapping[str, str],
) -> ReferenceValidationRunObservation:
    """Consume one runner start and evaluate the exact frozen synthetic matrix."""

    preflight_deadline = (
        time.monotonic() + REFERENCE_VALIDATION_RUNNER_PREFLIGHT_MAX_WALL_SECONDS
    )
    _require_runner_root_outside_checkout(
        artifact_output_root,
        name="artifact output root",
    )
    started = _utc_now()
    try:
        receipt = require_reference_validation_execution_environment_receipt_for_runner(
            artifact_output_root,
            authorization_nonce_sha256,
            expected_receipt_sha256=expected_environment_receipt_sha256,
            deadline=preflight_deadline,
        )
    except ReferenceValidationRunStartError as exc:
        raise ReferenceValidationRunnerError(
            "runner execution-environment re-verification failed"
        ) from exc
    receipt_started = _parse_utc(
        receipt.started_at_utc,
        name="environment receipt started_at",
    )
    if (
        not receipt_started
        <= started
        <= (receipt_started + REFERENCE_VALIDATION_RUNNER_MAX_RECEIPT_AGE)
    ):
        raise ReferenceValidationRunnerError(
            "execution environment receipt is not fresh enough for the runner"
        )
    _require_commit_sha(expected_code_commit_sha, name="expected runner code commit")
    if receipt.code_commit_sha != expected_code_commit_sha:
        raise ReferenceValidationRunnerError("runner code commit is cross-wired")
    dependencies = _normalize_dependency_rows(expected_dependency_artifact_sha256_rows)
    if receipt.dependency_artifact_sha256_rows != dependencies:
        raise ReferenceValidationRunnerError(
            "runner dependency artifact rows are cross-wired"
        )
    dependency_roots = _require_isolated_python_bootstrap_runtime(
        expected_code_commit_sha=receipt.code_commit_sha,
        expected_source_manifest_sha256=receipt.source_manifest_sha256,
    )
    _require_source_only_python_runtime()
    live_dependency_rows = _observe_dependency_artifact_sha256_rows(
        dependency_roots,
        deadline=preflight_deadline,
    )
    if tuple(sorted(live_dependency_rows.items())) != dependencies:
        raise ReferenceValidationRunnerError(
            "live runner dependency bytes do not match the signed receipt"
        )
    runner_source = reference_validation_runner_source_sha256()
    if receipt.runner_source_sha256 != runner_source:
        raise ReferenceValidationRunnerError(
            "runner source does not match the signed authorization chain"
        )
    checked_out_commit = reference_validation_checked_out_code_commit_sha()
    if checked_out_commit != expected_code_commit_sha:
        raise ReferenceValidationRunnerError(
            "checked-out code commit does not match the signed authorization chain"
        )
    _require_clean_checked_out_code_commit(expected_code_commit_sha)
    if time.monotonic() >= preflight_deadline:
        raise ReferenceValidationRunnerError(
            "validation preflight time budget expired before worker launch"
        )
    _require_deadline_timer_available()
    worker_environment = _case_worker_environment(
        receipt.environment_variable_rows,
        dependency_python_path=os.pathsep.join(
            os.fspath(root) for root in dependency_roots
        ),
    )
    deadline = time.monotonic() + REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS
    (
        protocol,
        manifest_cases,
        materialization_manifest_sha256,
        manifest_lifecycle,
        manifest_provenance,
    ) = _run_supervised_frozen_case_matrix(
        expected_code_commit_sha=expected_code_commit_sha,
        expected_runner_source_sha256=runner_source,
        expected_dependency_artifact_sha256_rows=live_dependency_rows,
        dependency_roots=dependency_roots,
        environment_receipt=receipt,
        worker_environment=worker_environment,
        deadline=deadline,
    )
    if time.monotonic() >= deadline:
        raise ReferenceValidationRunnerError(
            "validation time budget expired before runner start"
        )

    started_at_utc = _format_utc(_utc_now(), name="runner started_at")
    start_record_sha256 = _persist_runner_start(
        artifact_output_root,
        receipt,
        runner_source_sha256=runner_source,
        started_at_utc=started_at_utc,
    )

    case_results, case_lifecycle, case_provenance = _run_supervised_case_matrix(
        protocol,
        manifest_cases,
        materialization_manifest_sha256=materialization_manifest_sha256,
        expected_code_commit_sha=expected_code_commit_sha,
        expected_runner_source_sha256=runner_source,
        expected_runner_start_record_sha256=start_record_sha256,
        expected_dependency_artifact_sha256_rows=live_dependency_rows,
        dependency_roots=dependency_roots,
        environment_receipt=receipt,
        worker_environment=worker_environment,
        deadline=deadline,
    )
    completed_at_utc = _format_utc(_utc_now(), name="runner completed_at")
    return ReferenceValidationRunObservation(
        runner_start_record_sha256=start_record_sha256,
        execution_environment_receipt_sha256=receipt.receipt_sha256,
        environment_fingerprint_sha256=receipt.environment_fingerprint_sha256,
        authorization_receipt_sha256=receipt.authorization_receipt_sha256,
        authorization_nonce_sha256=receipt.authorization_nonce_sha256,
        code_commit_sha=receipt.code_commit_sha,
        runner_source_sha256=runner_source,
        source_manifest_sha256=receipt.source_manifest_sha256,
        dependency_artifact_sha256_rows=receipt.dependency_artifact_sha256_rows,
        command_argv=receipt.command_argv,
        seed=receipt.application_seed,
        started_at_utc=started_at_utc,
        completed_at_utc=completed_at_utc,
        case_results=case_results,
        manifest_worker_lifecycle_evidence_bytes=_lifecycle_evidence_bytes(
            manifest_lifecycle,
            name="manifest-worker lifecycle evidence",
        ),
        case_worker_lifecycle_evidence_bytes=_lifecycle_evidence_bytes(
            case_lifecycle,
            name="case-worker lifecycle evidence",
        ),
        manifest_worker_execution_provenance_bytes=(
            _worker_execution_provenance_bytes(
                manifest_provenance,
                name="manifest-worker execution provenance",
            )
        ),
        case_worker_execution_provenance_bytes=(
            _worker_execution_provenance_bytes(
                case_provenance,
                name="case-worker execution provenance",
            )
        ),
        retained_case_payload_aggregate_sha256=_sha256(
            [row.to_dict() for row in case_results]
        ),
    )


def reference_validation_runner_contract_decision() -> dict[str, Any]:
    contract = reference_validation_runner_contract_document()
    return {
        "contract_sha256": contract["contract_sha256"],
        "bounded_validation_runner_implemented": True,
        "production_environment_receipt_present": False,
        "production_runner_start_consumed": False,
        "production_validation_execution_authorized": False,
        "production_validation_results_collected": False,
        "result_receipt_writer_implemented": True,
        "parameter_fitting_authorized": False,
        "blockers": list(_CURRENT_BLOCKERS),
    }


def _case_observation_from_payload(
    case_payload: Mapping[str, Any],
) -> ReferenceValidationCaseObservation:
    """Reconstruct one exact canonical case row for the worker protocol."""

    if not isinstance(case_payload, Mapping):
        raise ReferenceValidationRunnerError(
            "validation case observation must be a mapping"
        )
    try:
        metrics: list[ReferenceValidationMetricObservation] = []
        for metric_payload in case_payload["metric_values"]:
            if metric_payload["observed"]:
                metric_value = metric_payload["value"]
            else:
                if metric_payload.get("error_code") != "metric_not_observed":
                    raise ReferenceValidationRunnerError(
                        "missing metric observation error is invalid"
                    )
                metric_value = None
            metrics.append(
                ReferenceValidationMetricObservation(
                    metric_id=metric_payload["metric_id"],
                    observed=metric_payload["observed"],
                    value=metric_value,
                    unit=metric_payload["unit"],
                    threshold_operator=metric_payload["threshold_operator"],
                    threshold_value=metric_payload["threshold_value"],
                    passed=metric_payload["passed"],
                )
            )
        variants: list[ReferenceValidationVariantObservation] = []
        for variant_payload in case_payload["variant_results"]:
            success = variant_payload["observed_status"] == "success"
            components = (
                tuple(
                    (row["name"], row["value"])
                    for row in variant_payload["component_energy_values_and_units"]
                )
                if success
                else ()
            )
            forces = (
                tuple(tuple(row) for row in variant_payload["force_array_values"])
                if success
                else ()
            )
            oracle_forces = (
                tuple(
                    tuple(row) for row in variant_payload["oracle_force_array_values"]
                )
                if success
                else ()
            )
            variants.append(
                ReferenceValidationVariantObservation(
                    ordinal=variant_payload["ordinal"],
                    variant_id=variant_payload["variant_id"],
                    runtime_input_sha256=variant_payload["runtime_input_sha256"],
                    oracle_input_sha256=variant_payload["oracle_input_sha256"],
                    observed_status=variant_payload["observed_status"],
                    observed_error_code=variant_payload["observed_error_code"],
                    component_energies_kcal_per_mol=components,
                    total_energy_kcal_per_mol=(
                        variant_payload["total_energy_value"] if success else None
                    ),
                    forces_kcal_per_mol_angstrom=forces,
                    force_array_sha256=(
                        variant_payload["force_array_sha256"] if success else None
                    ),
                    oracle_total_energy_kcal_per_mol=(
                        variant_payload["oracle_total_energy_value"]
                        if success
                        else None
                    ),
                    oracle_forces_kcal_per_mol_angstrom=oracle_forces,
                    oracle_force_array_sha256=(
                        variant_payload["oracle_force_array_sha256"]
                        if success
                        else None
                    ),
                )
            )
        result = ReferenceValidationCaseObservation(
            ordinal=case_payload["ordinal"],
            case_id=case_payload["case_id"],
            case_input_sha256=case_payload["case_input_sha256"],
            materialization_sha256=case_payload["materialization_sha256"],
            expected_outcome=case_payload["expected_outcome"],
            observation_origin=case_payload["observation_origin"],
            observed_status=case_payload["observed_status"],
            expected_error_code=case_payload["expected_error_code"],
            observed_error_code=case_payload["observed_error_code"],
            variant_results=tuple(variants),
            metric_values=tuple(metrics),
            case_passed=case_payload["case_passed"],
        )
    except ReferenceValidationRunnerError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ReferenceValidationRunnerError(
            "validation case observation is invalid"
        ) from exc
    if result.to_dict() != dict(case_payload):
        raise ReferenceValidationRunnerError(
            "validation case observation is not canonical or exact"
        )
    return result


def require_reference_validation_run_observation_document(
    payload: Mapping[str, Any],
) -> ReferenceValidationRunObservation:
    """Reconstruct and verify an exact canonical bounded-run observation."""

    if not isinstance(payload, Mapping):
        raise ReferenceValidationRunnerError(
            "validation run observation document must be a mapping"
        )
    try:
        observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
        cases: list[ReferenceValidationCaseObservation] = []
        for case_payload in observed["case_results"]:
            metrics: list[ReferenceValidationMetricObservation] = []
            for metric_payload in case_payload["metric_values"]:
                if metric_payload["observed"]:
                    metric_value = metric_payload["value"]
                else:
                    if metric_payload.get("error_code") != "metric_not_observed":
                        raise ReferenceValidationRunnerError(
                            "missing metric observation error is invalid"
                        )
                    metric_value = None
                metrics.append(
                    ReferenceValidationMetricObservation(
                        metric_id=metric_payload["metric_id"],
                        observed=metric_payload["observed"],
                        value=metric_value,
                        unit=metric_payload["unit"],
                        threshold_operator=metric_payload["threshold_operator"],
                        threshold_value=metric_payload["threshold_value"],
                        passed=metric_payload["passed"],
                    )
                )
            variants: list[ReferenceValidationVariantObservation] = []
            for variant_payload in case_payload["variant_results"]:
                success = variant_payload["observed_status"] == "success"
                components = (
                    tuple(
                        (row["name"], row["value"])
                        for row in variant_payload["component_energy_values_and_units"]
                    )
                    if success
                    else ()
                )
                forces = (
                    tuple(tuple(row) for row in variant_payload["force_array_values"])
                    if success
                    else ()
                )
                oracle_forces = (
                    tuple(
                        tuple(row)
                        for row in variant_payload["oracle_force_array_values"]
                    )
                    if success
                    else ()
                )
                variants.append(
                    ReferenceValidationVariantObservation(
                        ordinal=variant_payload["ordinal"],
                        variant_id=variant_payload["variant_id"],
                        runtime_input_sha256=variant_payload["runtime_input_sha256"],
                        oracle_input_sha256=variant_payload["oracle_input_sha256"],
                        observed_status=variant_payload["observed_status"],
                        observed_error_code=variant_payload["observed_error_code"],
                        component_energies_kcal_per_mol=components,
                        total_energy_kcal_per_mol=(
                            variant_payload["total_energy_value"] if success else None
                        ),
                        forces_kcal_per_mol_angstrom=forces,
                        force_array_sha256=(
                            variant_payload["force_array_sha256"] if success else None
                        ),
                        oracle_total_energy_kcal_per_mol=(
                            variant_payload["oracle_total_energy_value"]
                            if success
                            else None
                        ),
                        oracle_forces_kcal_per_mol_angstrom=oracle_forces,
                        oracle_force_array_sha256=(
                            variant_payload["oracle_force_array_sha256"]
                            if success
                            else None
                        ),
                    )
                )
            cases.append(
                ReferenceValidationCaseObservation(
                    ordinal=case_payload["ordinal"],
                    case_id=case_payload["case_id"],
                    case_input_sha256=case_payload["case_input_sha256"],
                    materialization_sha256=case_payload["materialization_sha256"],
                    expected_outcome=case_payload["expected_outcome"],
                    observation_origin=case_payload["observation_origin"],
                    observed_status=case_payload["observed_status"],
                    expected_error_code=case_payload["expected_error_code"],
                    observed_error_code=case_payload["observed_error_code"],
                    variant_results=tuple(variants),
                    metric_values=tuple(metrics),
                    case_passed=case_payload["case_passed"],
                )
            )
        dependencies = tuple(
            (row["artifact_id"], row["sha256"])
            for row in observed["dependency_artifact_sha256_rows"]
        )
        result = ReferenceValidationRunObservation(
            runner_start_record_sha256=observed["runner_start_record_sha256"],
            execution_environment_receipt_sha256=observed[
                "execution_environment_receipt_sha256"
            ],
            environment_fingerprint_sha256=observed["environment_fingerprint_sha256"],
            authorization_receipt_sha256=observed["authorization_receipt_sha256"],
            authorization_nonce_sha256=observed["authorization_nonce_sha256"],
            code_commit_sha=observed["code_commit_sha"],
            runner_source_sha256=observed["runner_source_sha256"],
            source_manifest_sha256=observed["source_manifest_sha256"],
            dependency_artifact_sha256_rows=dependencies,
            command_argv=tuple(observed["command_argv"]),
            seed=observed["seed"],
            started_at_utc=observed["started_at_utc"],
            completed_at_utc=observed["completed_at_utc"],
            case_results=tuple(cases),
            manifest_worker_lifecycle_evidence_bytes=_lifecycle_evidence_bytes(
                observed["manifest_worker_lifecycle_evidence"],
                name="manifest-worker lifecycle evidence",
            ),
            case_worker_lifecycle_evidence_bytes=_lifecycle_evidence_bytes(
                observed["case_worker_lifecycle_evidence"],
                name="case-worker lifecycle evidence",
            ),
            manifest_worker_execution_provenance_bytes=(
                _worker_execution_provenance_bytes(
                    observed["manifest_worker_execution_provenance"],
                    name="manifest-worker execution provenance",
                )
            ),
            case_worker_execution_provenance_bytes=(
                _worker_execution_provenance_bytes(
                    observed["case_worker_execution_provenance"],
                    name="case-worker execution provenance",
                )
            ),
            retained_case_payload_aggregate_sha256=observed[
                "retained_case_payload_aggregate_sha256"
            ],
            blockers=tuple(observed["blockers"]),
        )
    except ReferenceValidationRunnerError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ReferenceValidationRunnerError(
            "validation run observation document is invalid"
        ) from exc
    if result.to_dict() != observed:
        raise ReferenceValidationRunnerError(
            "validation run observation document is not canonical or exact"
        )
    return result


def _require_string_sequence(value: object, *, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(row, str) for row in value):
        raise ReferenceValidationRunnerError(f"{name} must be a JSON string array")
    return tuple(value)


def _verification_key_from_hex(value: object, *, name: str) -> bytes:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReferenceValidationRunnerError(
            f"{name} must be an exact lowercase Ed25519 public key"
        )
    return bytes.fromhex(value)


def _trust_store_key_id(value: object, *, name: str) -> str:
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 128
        or any(character not in allowed for character in value)
    ):
        raise ReferenceValidationRunnerError(
            f"{name} must contain 1 to 128 safe ASCII characters"
        )
    return value


def _trusted_reviewer_keys_from_store(value: object) -> dict[str, Any]:
    from .reference_validation_review import ScientificReviewerTrustAnchor

    if not isinstance(value, list) or not value:
        raise ReferenceValidationRunnerError(
            "preconfigured trust store reviewer keys must be a non-empty array"
        )
    result: dict[str, ScientificReviewerTrustAnchor] = {}
    for row in value:
        if not isinstance(row, dict) or set(row) != {
            "key_id",
            "reviewer_identity_sha256",
            "verification_key_hex",
        }:
            raise ReferenceValidationRunnerError(
                "preconfigured trust store reviewer key fields are invalid"
            )
        key_id = _trust_store_key_id(
            row["key_id"],
            name="preconfigured reviewer key id",
        )
        if key_id in result:
            raise ReferenceValidationRunnerError(
                "preconfigured trust store reviewer key ids are not unique"
            )
        result[key_id] = ScientificReviewerTrustAnchor(
            row["reviewer_identity_sha256"],
            _verification_key_from_hex(
                row["verification_key_hex"],
                name="trusted reviewer verification key",
            ),
        )
    return result


def _trusted_operator_keys_from_store(value: object) -> dict[str, Any]:
    from .reference_validation_authorization import AuthorizationOperatorTrustAnchor

    if not isinstance(value, list) or not value:
        raise ReferenceValidationRunnerError(
            "preconfigured trust store operator keys must be a non-empty array"
        )
    result: dict[str, AuthorizationOperatorTrustAnchor] = {}
    for row in value:
        if not isinstance(row, dict) or set(row) != {
            "key_id",
            "operator_identity_sha256",
            "verification_key_hex",
        }:
            raise ReferenceValidationRunnerError(
                "preconfigured trust store operator key fields are invalid"
            )
        key_id = _trust_store_key_id(
            row["key_id"],
            name="preconfigured operator key id",
        )
        if key_id in result:
            raise ReferenceValidationRunnerError(
                "preconfigured trust store operator key ids are not unique"
            )
        result[key_id] = AuthorizationOperatorTrustAnchor(
            row["operator_identity_sha256"],
            _verification_key_from_hex(
                row["verification_key_hex"],
                name="trusted operator verification key",
            ),
        )
    return result


def _validate_preconfigured_trust_directory(file_stat: os.stat_result) -> None:
    if (
        not stat.S_ISDIR(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) & 0o022
    ):
        raise ReferenceValidationRunnerError(
            "preconfigured trust-store directory policy failed"
        )


def _validate_preconfigured_trust_file(file_stat: os.stat_result) -> None:
    if (
        not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_uid != 0
        or stat.S_IMODE(file_stat.st_mode) != 0o600
        or file_stat.st_nlink != 1
        or not 0 < file_stat.st_size <= REFERENCE_VALIDATION_TRUST_STORE_MAX_BYTES
    ):
        raise ReferenceValidationRunnerError(
            "preconfigured trust-store file policy failed"
        )


def _open_preconfigured_trust_store() -> int:
    required_flags = ("O_NOFOLLOW", "O_CLOEXEC", "O_DIRECTORY", "O_NONBLOCK")
    if (
        os.name != "posix"
        or any(not hasattr(os, name) for name in required_flags)
        or os.open not in os.supports_dir_fd
    ):
        raise ReferenceValidationRunnerError(
            "secure preconfigured trust-store access is unavailable"
        )
    path = Path(REFERENCE_VALIDATION_TRUST_STORE_PATH)
    if not path.is_absolute() or ".." in path.parts or path.anchor != os.sep:
        raise ReferenceValidationRunnerError(
            "preconfigured trust-store path is invalid"
        )
    components = tuple(part for part in path.parts[1:] if part not in {"", "."})
    if len(components) < 2:
        raise ReferenceValidationRunnerError(
            "preconfigured trust-store path is invalid"
        )
    directory_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_DIRECTORY
    current_fd = -1
    file_fd = -1
    try:
        current_fd = os.open(os.sep, directory_flags)
        for component in components[:-1]:
            _validate_preconfigured_trust_directory(os.fstat(current_fd))
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        _validate_preconfigured_trust_directory(os.fstat(current_fd))
        file_fd = os.open(
            components[-1],
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=current_fd,
        )
        file_stat = os.fstat(file_fd)
        _validate_preconfigured_trust_file(file_stat)
        result_fd = file_fd
        file_fd = -1
        return result_fd
    except ReferenceValidationRunnerError:
        raise
    except (OSError, ValueError) as exc:
        raise ReferenceValidationRunnerError(
            "preconfigured trust store cannot be opened securely"
        ) from exc
    finally:
        if file_fd >= 0:
            os.close(file_fd)
        if current_fd >= 0:
            os.close(current_fd)


def _load_preconfigured_trust_anchors() -> tuple[dict[str, Any], dict[str, Any]]:
    descriptor = _open_preconfigured_trust_store()
    try:
        initial_stat = os.fstat(descriptor)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, 8192)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > REFERENCE_VALIDATION_TRUST_STORE_MAX_BYTES:
                raise ReferenceValidationRunnerError(
                    "preconfigured trust store exceeds the size limit"
                )
        final_stat = os.fstat(descriptor)
        _validate_preconfigured_trust_file(final_stat)
    except ReferenceValidationRunnerError:
        raise
    except OSError as exc:
        raise ReferenceValidationRunnerError(
            "preconfigured trust store cannot be read securely"
        ) from exc
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if (
        initial_stat.st_dev != final_stat.st_dev
        or initial_stat.st_ino != final_stat.st_ino
        or initial_stat.st_size != final_stat.st_size
        or len(raw) != initial_stat.st_size
        or not raw.endswith(b"\n")
    ):
        raise ReferenceValidationRunnerError(
            "preconfigured trust store changed or is not framed canonically"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceValidationRunnerError(
                    "preconfigured trust store contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        payload = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationRunnerError(
            "preconfigured trust store must be canonical ASCII JSON"
        ) from exc
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_id", "reviewer_keys", "operator_keys"}
        or payload.get("schema_id") != REFERENCE_VALIDATION_TRUST_STORE_SCHEMA_ID
        or _canonical_bytes(payload) + b"\n" != raw
    ):
        raise ReferenceValidationRunnerError(
            "preconfigured trust store is not the exact canonical schema"
        )
    return (
        _trusted_reviewer_keys_from_store(payload["reviewer_keys"]),
        _trusted_operator_keys_from_store(payload["operator_keys"]),
    )


def _load_runner_request(raw: bytes) -> dict[str, Any]:
    if (
        not raw
        or len(raw) > REFERENCE_VALIDATION_RUNNER_MAX_REQUEST_BYTES
        or not raw.endswith(b"\n")
    ):
        raise ReferenceValidationRunnerError(
            "runner request size or framing is invalid"
        )

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceValidationRunnerError(
                    "runner request contains a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        request = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceValidationRunnerError(
            "runner request must be canonical ASCII JSON"
        ) from exc
    if not isinstance(request, dict) or _canonical_bytes(request) + b"\n" != raw:
        raise ReferenceValidationRunnerError(
            "runner request must be exact canonical JSON"
        )
    expected_fields = {
        "schema_id",
        "reservation_root",
        "artifact_output_root",
        "authorization_nonce_sha256",
        "authorization_receipt",
        "review_attestation",
        "expected_implementation_author_identity_sha256",
        "network_isolation_attestation",
        "expected_code_commit_sha",
        "expected_runner_source_sha256",
        "expected_dependency_artifact_sha256_rows",
        "revoked_authorization_receipt_sha256s",
        "revoked_review_attestation_sha256s",
        "externally_conflicting_nonce_sha256s",
        "revoked_network_attestation_sha256s",
    }
    if set(request) != expected_fields or request.get("schema_id") != (
        REFERENCE_VALIDATION_RUNNER_REQUEST_SCHEMA_ID
    ):
        raise ReferenceValidationRunnerError("runner request fields are invalid")
    for name in ("reservation_root", "artifact_output_root"):
        if not isinstance(request[name], str) or not request[name]:
            raise ReferenceValidationRunnerError(
                f"runner request {name} must be non-empty text"
            )
    if (
        not isinstance(request["authorization_receipt"], dict)
        or not isinstance(request["review_attestation"], dict)
        or not isinstance(request["network_isolation_attestation"], dict)
    ):
        raise ReferenceValidationRunnerError(
            "runner request signed artifacts must be JSON objects"
        )
    raw_dependency_rows = request["expected_dependency_artifact_sha256_rows"]
    if (
        not isinstance(raw_dependency_rows, dict)
        or tuple(sorted(raw_dependency_rows))
        != REFERENCE_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS
        or any(
            _require_sha256(value, name=f"runner request dependency {artifact_id}")
            != value
            for artifact_id, value in raw_dependency_rows.items()
        )
    ):
        raise ReferenceValidationRunnerError(
            "runner request dependency rows are invalid"
        )
    return request


def _execute_runner_request(request: Mapping[str, Any]) -> dict[str, Any]:
    from .reference_validation_run_start import (
        create_reference_validation_execution_environment_receipt,
    )
    from .reference_validation_result_writer import (
        write_reference_validation_result_receipt,
    )

    _require_runner_root_outside_checkout(
        request["reservation_root"],
        name="reservation root",
    )
    _require_runner_root_outside_checkout(
        request["artifact_output_root"],
        name="artifact output root",
    )
    revoked_authorizations = _require_string_sequence(
        request["revoked_authorization_receipt_sha256s"],
        name="revoked authorization receipts",
    )
    revoked_reviews = _require_string_sequence(
        request["revoked_review_attestation_sha256s"],
        name="revoked review attestations",
    )
    conflicting_nonces = _require_string_sequence(
        request["externally_conflicting_nonce_sha256s"],
        name="externally conflicting nonces",
    )
    revoked_network = _require_string_sequence(
        request["revoked_network_attestation_sha256s"],
        name="revoked network attestations",
    )
    expected_commit = _require_commit_sha(
        request["expected_code_commit_sha"],
        name="runner request code commit",
    )
    expected_source = _require_sha256(
        request["expected_runner_source_sha256"],
        name="runner request source",
    )
    if reference_validation_checked_out_code_commit_sha() != expected_commit:
        raise ReferenceValidationRunnerError(
            "runner request code commit does not match the checkout"
        )
    dependency_roots = _require_isolated_python_bootstrap_runtime(
        expected_code_commit_sha=expected_commit,
    )
    _require_source_only_python_runtime()
    _require_clean_checked_out_code_commit(expected_commit)
    if reference_validation_runner_source_sha256() != expected_source:
        raise ReferenceValidationRunnerError(
            "runner request source does not match the loaded runner"
        )
    expected_dependency_rows = request["expected_dependency_artifact_sha256_rows"]
    if (
        _observe_dependency_artifact_sha256_rows(dependency_roots)
        != expected_dependency_rows
    ):
        raise ReferenceValidationRunnerError(
            "runner request dependency bytes do not match the loaded runtime"
        )
    reviewer_keys, operator_keys = _load_preconfigured_trust_anchors()

    _configure_deterministic_torch_runtime()

    environment = create_reference_validation_execution_environment_receipt(
        request["reservation_root"],
        request["artifact_output_root"],
        authorization_nonce_sha256=request["authorization_nonce_sha256"],
        authorization_receipt=request["authorization_receipt"],
        review_attestation=request["review_attestation"],
        trusted_reviewer_keys=reviewer_keys,
        expected_implementation_author_identity_sha256=(
            request["expected_implementation_author_identity_sha256"]
        ),
        trusted_operator_keys=operator_keys,
        network_isolation_attestation=request["network_isolation_attestation"],
        expected_code_commit_sha=expected_commit,
        expected_runner_source_sha256=expected_source,
        expected_dependency_artifact_sha256_rows=(
            request["expected_dependency_artifact_sha256_rows"]
        ),
        revoked_receipt_sha256s=revoked_authorizations,
        revoked_review_attestation_sha256s=revoked_reviews,
        externally_conflicting_nonce_sha256s=conflicting_nonces,
        revoked_network_attestation_sha256s=revoked_network,
    )
    observation = run_bounded_cpu_reference_validation(
        request["artifact_output_root"],
        request["authorization_nonce_sha256"],
        expected_environment_receipt_sha256=environment.receipt_sha256,
        expected_code_commit_sha=expected_commit,
        expected_dependency_artifact_sha256_rows=(
            request["expected_dependency_artifact_sha256_rows"]
        ),
    )
    receipt = write_reference_validation_result_receipt(
        request["artifact_output_root"],
        request["authorization_nonce_sha256"],
        observation,
        review_attestation=request["review_attestation"],
        authorization_receipt=request["authorization_receipt"],
        trusted_reviewer_keys=reviewer_keys,
        expected_implementation_author_identity_sha256=(
            request["expected_implementation_author_identity_sha256"]
        ),
        trusted_operator_keys=operator_keys,
        revoked_authorization_receipt_sha256s=revoked_authorizations,
        revoked_review_attestation_sha256s=revoked_reviews,
        externally_conflicting_nonce_sha256s=conflicting_nonces,
    )
    return {
        "schema_id": REFERENCE_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID,
        "environment_receipt_sha256": environment.receipt_sha256,
        "observation_sha256": observation.observation_sha256,
        "result_receipt_sha256": receipt.receipt_sha256,
        "production_validation_results_collected": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def _main_from_canonical_request(raw: bytes) -> int:
    """Execute one request already bounded and verified by the bootstrap."""

    output_stream = getattr(sys.stdout, "buffer", sys.stdout)
    try:
        response = _execute_runner_request(_load_runner_request(raw))
        encoded = _canonical_bytes(response) + b"\n"
        output_stream.write(encoded)
        output_stream.flush()
    except Exception:
        return 2
    return 0


def _main_from_standard_streams() -> int:
    input_stream = getattr(sys.stdin, "buffer", sys.stdin)
    try:
        raw = input_stream.read(REFERENCE_VALIDATION_RUNNER_MAX_REQUEST_BYTES + 1)
    except (AttributeError, OSError):
        return 2
    if not isinstance(raw, bytes):
        return 2
    return _main_from_canonical_request(raw)


def main() -> int:
    """Run the exact stdin-delivered, fail-closed validation chain."""

    canonical_name = "betelgeuze_engine_v2.physics.reference_validation_runner"
    canonical_module = sys.modules.get(canonical_name)
    delegate = (
        __name__ == "__main__"
        and canonical_module is not None
        and canonical_module is not sys.modules.get(__name__)
    )
    implementation = canonical_module if delegate else sys.modules[__name__]
    return implementation._main_from_standard_streams()


__all__ = [
    "FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V1",
    "FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V2",
    "FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V3",
    "FROZEN_LEGACY_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256_V4",
    "FROZEN_REFERENCE_VALIDATION_RUNNER_CONTRACT_SHA256",
    "REFERENCE_VALIDATION_CENTRAL_DIFFERENCE_STEP_ANGSTROM",
    "REFERENCE_VALIDATION_CASE_WORKER_MAX_OUTPUT_BYTES",
    "REFERENCE_VALIDATION_CASE_WORKER_MAX_REQUEST_BYTES",
    "REFERENCE_VALIDATION_CASE_WORKER_REQUEST_SCHEMA_ID",
    "REFERENCE_VALIDATION_RUNNER_CONTRACT_ID",
    "REFERENCE_VALIDATION_RUNNER_CONTRACT_SCHEMA_ID",
    "REFERENCE_VALIDATION_RUNNER_CONTRACT_VERSION",
    "REFERENCE_VALIDATION_RUNNER_MAX_CASES",
    "REFERENCE_VALIDATION_RUNNER_MAX_RECEIPT_AGE",
    "REFERENCE_VALIDATION_RUNNER_MAX_REQUEST_BYTES",
    "REFERENCE_VALIDATION_RUNNER_MAX_START_RECORD_BYTES",
    "REFERENCE_VALIDATION_RUNNER_MAX_VARIANTS",
    "REFERENCE_VALIDATION_RUNNER_MAX_WALL_SECONDS",
    "REFERENCE_VALIDATION_RUNNER_START_SCHEMA_ID",
    "REFERENCE_VALIDATION_RUNNER_REQUEST_SCHEMA_ID",
    "REFERENCE_VALIDATION_RUNNER_RESPONSE_SCHEMA_ID",
    "REFERENCE_VALIDATION_RUN_OBSERVATION_SCHEMA_ID",
    "REFERENCE_VALIDATION_TRUST_STORE_MAX_BYTES",
    "REFERENCE_VALIDATION_TRUST_STORE_PATH",
    "REFERENCE_VALIDATION_TRUST_STORE_SCHEMA_ID",
    "REFERENCE_VALIDATION_WORKER_FRAME_SCHEMA_ID",
    "REFERENCE_VALIDATION_WORKER_EXECUTION_PROVENANCE_SCHEMA_ID",
    "ReferenceValidationCaseObservation",
    "ReferenceValidationMetricObservation",
    "ReferenceValidationRunObservation",
    "ReferenceValidationRunnerAlreadyStartedError",
    "ReferenceValidationRunnerError",
    "ReferenceValidationVariantObservation",
    "reference_validation_runner_contract_decision",
    "reference_validation_runner_contract_document",
    "reference_validation_runner_source_sha256",
    "reference_validation_checked_out_code_commit_sha",
    "read_reference_validation_runner_start_record",
    "require_reference_validation_run_observation_document",
    "require_reference_validation_worker_execution_provenance_document",
    "require_reference_validation_runner_contract_document",
    "run_bounded_cpu_reference_validation",
]


if __name__ == "__main__":
    raise SystemExit(main())
