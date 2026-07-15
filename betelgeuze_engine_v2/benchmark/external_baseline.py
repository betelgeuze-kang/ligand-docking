"""Offline Vina/GNINA/Smina work orders and operator result receipts.

This module never launches an external docking engine. It creates deterministic
work orders and validates operator-produced result rows and pose artifacts.
"""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from types import MappingProxyType
from typing import Any, Mapping, Sequence

SUPPORTED_EXTERNAL_ENGINES = frozenset({"vina", "gnina", "smina"})
EXTERNAL_BASELINE_WORK_ORDER_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_baseline_work_order/1.0.0"
)
EXTERNAL_BASELINE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_external_baseline_receipt/1.0.0"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RESULT_ROW_FIELDS = frozenset(
    {"case_id", "status", "score", "pose_path", "pose_sha256", "error_code"}
)
_CSV_RESULT_FIELDS = (
    "case_id",
    "status",
    "score",
    "pose_path",
    "pose_sha256",
    "error_code",
)
_SECURE_DIR_FD_OPEN_SUPPORTED = os.open in getattr(os, "supports_dir_fd", set())


class ExternalBaselineContractError(ValueError):
    """External baseline work-order or result provenance is invalid."""


def _sha256(value: str, *, name: str, allow_empty: bool = False) -> str:
    text = str(value or "").strip().lower()
    if allow_empty and not text:
        return ""
    if _SHA256_RE.fullmatch(text) is None:
        raise ExternalBaselineContractError(f"{name} must be a lowercase SHA-256")
    return text


def _canonical_bytes(payload: object) -> bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            ensure_ascii=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ExternalBaselineContractError(
            "external baseline payload is not canonical JSON"
        ) from exc


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _normalize_metadata(
    value: Any,
    *,
    path: str = "metadata",
    active_containers: set[int] | None = None,
) -> Any:
    active = active_containers if active_containers is not None else set()
    if isinstance(value, MappingABC):
        identity = id(value)
        if identity in active:
            raise ExternalBaselineContractError(
                f"{path} must not contain cyclic containers"
            )
        active.add(identity)
        try:
            normalized: dict[str, Any] = {}
            for key, item in value.items():
                if type(key) is not str:
                    raise ExternalBaselineContractError(
                        f"{path} object keys must be strings"
                    )
                normalized[key] = _normalize_metadata(
                    item,
                    path=f"{path}.{key}",
                    active_containers=active,
                )
            return {key: normalized[key] for key in sorted(normalized)}
        finally:
            active.remove(identity)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active:
            raise ExternalBaselineContractError(
                f"{path} must not contain cyclic containers"
            )
        active.add(identity)
        try:
            return [
                _normalize_metadata(
                    item,
                    path=f"{path}[{index}]",
                    active_containers=active,
                )
                for index, item in enumerate(value)
            ]
        finally:
            active.remove(identity)
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ExternalBaselineContractError(
                f"{path} floating-point values must be finite"
            )
        return float(value)
    raise ExternalBaselineContractError(
        f"{path} must contain only canonical JSON values"
    )


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, MappingABC):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _canonical_metadata(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise ExternalBaselineContractError("metadata must be a mapping")
    normalized = _normalize_metadata(value)
    _canonical_sha256(normalized)
    return _freeze_json(normalized)


def _finite_score(value: Any, *, message: str) -> float:
    if isinstance(value, bool):
        raise ExternalBaselineContractError(message)
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ExternalBaselineContractError(message) from exc
    if not math.isfinite(score):
        raise ExternalBaselineContractError(message)
    return score


def _secure_open_flags(*, directory: bool) -> int:
    required = ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK")
    if os.name != "posix" or any(not hasattr(os, name) for name in required):
        raise ExternalBaselineContractError(
            "secure external baseline artifact validation is unavailable"
        )
    if not _SECURE_DIR_FD_OPEN_SUPPORTED:
        raise ExternalBaselineContractError(
            "secure external baseline artifact validation is unavailable"
        )
    flags = os.O_RDONLY | os.O_NOFOLLOW
    if directory:
        flags |= os.O_DIRECTORY
    else:
        flags |= getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    return flags


def _root_components(root: Path) -> tuple[str, ...]:
    if ".." in root.parts:
        raise ExternalBaselineContractError(
            "external baseline artifact_root may not contain '..' or traverse symlinks"
        )
    expanded = root.expanduser()
    if ".." in expanded.parts:
        raise ExternalBaselineContractError(
            "external baseline artifact_root may not contain '..' or traverse symlinks"
        )
    if expanded.is_absolute():
        if expanded.anchor != os.sep:
            raise ExternalBaselineContractError(
                "external baseline artifact_root has an unsupported filesystem anchor"
            )
        absolute = expanded
    else:
        absolute = Path.cwd().joinpath(expanded)
    if absolute.anchor != os.sep:
        raise ExternalBaselineContractError(
            "external baseline artifact_root has an unsupported filesystem anchor"
        )
    return tuple(part for part in absolute.parts[1:] if part not in {"", "."})


def _open_directory_at(parent_fd: int, component: str, *, scope: str) -> int:
    try:
        return os.open(
            component,
            _secure_open_flags(directory=True),
            dir_fd=parent_fd,
        )
    except (OSError, ValueError) as exc:
        raise ExternalBaselineContractError(
            f"external baseline {scope} component is missing, inaccessible, "
            "not a directory, or a symlink"
        ) from exc


def _open_regular_at(parent_fd: int, component: str) -> int:
    try:
        return os.open(
            component,
            _secure_open_flags(directory=False),
            dir_fd=parent_fd,
        )
    except (OSError, ValueError) as exc:
        raise ExternalBaselineContractError(
            "external baseline pose artifact is missing, inaccessible, or a symlink"
        ) from exc


def _open_directory_chain(components: Sequence[str]) -> int:
    directory_flags = _secure_open_flags(directory=True)
    try:
        current_fd = os.open(os.sep, directory_flags)
    except (OSError, ValueError) as exc:
        raise ExternalBaselineContractError(
            "external baseline filesystem root cannot be opened securely"
        ) from exc
    try:
        for component in components:
            previous_fd = current_fd
            current_fd = _open_directory_at(
                previous_fd,
                component,
                scope="artifact_root",
            )
            os.close(previous_fd)
        result_fd = current_fd
        current_fd = None
        return result_fd
    finally:
        if current_fd is not None:
            os.close(current_fd)


def _open_pose_directory(root_fd: int, components: Sequence[str]) -> int:
    current_fd = root_fd
    try:
        for component in components:
            previous_fd = current_fd
            current_fd = _open_directory_at(
                previous_fd,
                component,
                scope="pose path",
            )
            os.close(previous_fd)
        result_fd = current_fd
        current_fd = None
        return result_fd
    finally:
        if current_fd is not None:
            os.close(current_fd)


def _confined_file(
    root: Path,
    relative_path: str,
    expected_sha256: str,
) -> tuple[int, str]:
    relative = Path(str(relative_path or ""))
    if (
        not relative_path
        or relative.is_absolute()
        or ".." in relative.parts
        or not relative.parts
    ):
        raise ExternalBaselineContractError(
            "pose_path must be a relative path below artifact_root"
        )
    root_fd = _open_directory_chain(_root_components(root))
    directory_fd = _open_pose_directory(root_fd, relative.parts[:-1])
    file_fd: int | None = None
    try:
        file_fd = _open_regular_at(directory_fd, relative.parts[-1])
        try:
            before = os.fstat(file_fd)
        except OSError as exc:
            raise ExternalBaselineContractError(
                "external baseline pose artifact cannot be inspected"
            ) from exc
        if not stat.S_ISREG(before.st_mode):
            raise ExternalBaselineContractError(
                "external baseline pose is not a regular file"
            )
        digest = hashlib.sha256()
        size = 0
        try:
            while chunk := os.read(file_fd, 1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        except OSError as exc:
            raise ExternalBaselineContractError(
                "external baseline pose artifact cannot be read"
            ) from exc
        try:
            after = os.fstat(file_fd)
        except OSError as exc:
            raise ExternalBaselineContractError(
                "external baseline pose artifact cannot be inspected"
            ) from exc
        stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, name) != getattr(after, name) for name in stable_fields):
            raise ExternalBaselineContractError(
                "external baseline pose artifact changed during validation"
            )
        if size != after.st_size:
            raise ExternalBaselineContractError(
                "external baseline pose artifact size changed during validation"
            )
        actual = digest.hexdigest()
        if actual != expected_sha256:
            raise ExternalBaselineContractError("external baseline pose SHA-256 mismatch")
        return size, actual
    finally:
        try:
            if file_fd is not None:
                os.close(file_fd)
        finally:
            os.close(directory_fd)


@dataclass(frozen=True)
class ExternalBaselineEngine:
    engine_id: str
    engine_version: str
    executable_sha256: str
    container_image_digest: str = ""

    def __post_init__(self) -> None:
        engine = str(self.engine_id or "").strip().lower()
        if engine not in SUPPORTED_EXTERNAL_ENGINES:
            raise ExternalBaselineContractError(
                f"unsupported external baseline engine: {self.engine_id!r}"
            )
        if not str(self.engine_version or "").strip():
            raise ExternalBaselineContractError("engine_version must be non-empty")
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "engine_version", str(self.engine_version).strip())
        object.__setattr__(
            self,
            "executable_sha256",
            _sha256(self.executable_sha256, name="executable_sha256"),
        )
        digest = str(self.container_image_digest or "").strip().lower()
        if digest and (
            not digest.startswith("sha256:")
            or _SHA256_RE.fullmatch(digest.removeprefix("sha256:")) is None
        ):
            raise ExternalBaselineContractError(
                "container_image_digest must be empty or sha256:<digest>"
            )
        object.__setattr__(self, "container_image_digest", digest)

    def to_dict(self) -> dict[str, str]:
        return {
            "engine_id": self.engine_id,
            "engine_version": self.engine_version,
            "executable_sha256": self.executable_sha256,
            "container_image_digest": self.container_image_digest,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class ExternalBaselineCase:
    case_id: str
    target_id: str
    ligand_id: str
    receptor_sha256: str
    ligand_sha256: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all(
            str(value or "").strip()
            for value in (self.case_id, self.target_id, self.ligand_id)
        ):
            raise ExternalBaselineContractError(
                "case_id, target_id, and ligand_id must be non-empty"
            )
        object.__setattr__(self, "case_id", str(self.case_id).strip())
        object.__setattr__(self, "target_id", str(self.target_id).strip())
        object.__setattr__(self, "ligand_id", str(self.ligand_id).strip())
        object.__setattr__(
            self,
            "receptor_sha256",
            _sha256(self.receptor_sha256, name="receptor_sha256"),
        )
        object.__setattr__(
            self,
            "ligand_sha256",
            _sha256(self.ligand_sha256, name="ligand_sha256"),
        )
        object.__setattr__(self, "metadata", _canonical_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "target_id": self.target_id,
            "ligand_id": self.ligand_id,
            "receptor_sha256": self.receptor_sha256,
            "ligand_sha256": self.ligand_sha256,
            "metadata": _thaw_json(self.metadata),
        }


@dataclass(frozen=True)
class ExternalBaselineWorkOrder:
    work_order_id: str
    engine: ExternalBaselineEngine
    cases: tuple[ExternalBaselineCase, ...]
    command_template: tuple[str, ...]
    score_direction: str = "minimize"
    score_unit: str = ""
    score_semantics: str = "external_engine_native_score"
    schema_id: str = EXTERNAL_BASELINE_WORK_ORDER_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != EXTERNAL_BASELINE_WORK_ORDER_SCHEMA_ID:
            raise ExternalBaselineContractError("unsupported work-order schema")
        if not str(self.work_order_id or "").strip():
            raise ExternalBaselineContractError("work_order_id must be non-empty")
        cases = tuple(self.cases)
        if not cases:
            raise ExternalBaselineContractError("work order requires at least one case")
        case_ids = [case.case_id for case in cases]
        if len(case_ids) != len(set(case_ids)):
            raise ExternalBaselineContractError("work-order case IDs must be unique")
        command = tuple(str(value) for value in self.command_template)
        if not command or any(not value for value in command):
            raise ExternalBaselineContractError("command_template must be a non-empty argv tuple")
        required_tokens = {"{receptor_path}", "{ligand_path}", "{output_path}"}
        if not required_tokens.issubset(set(command)):
            raise ExternalBaselineContractError(
                "command_template must contain receptor, ligand, and output placeholders"
            )
        if self.score_direction not in {"minimize", "maximize"}:
            raise ExternalBaselineContractError(
                "score_direction must be minimize or maximize"
            )
        if not str(self.score_unit or "").strip():
            raise ExternalBaselineContractError("score_unit must be non-empty")
        if not str(self.score_semantics or "").strip():
            raise ExternalBaselineContractError("score_semantics must be non-empty")
        object.__setattr__(self, "work_order_id", str(self.work_order_id).strip())
        object.__setattr__(self, "cases", cases)
        object.__setattr__(self, "command_template", command)
        object.__setattr__(self, "score_unit", str(self.score_unit).strip())
        object.__setattr__(self, "score_semantics", str(self.score_semantics).strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "work_order_id": self.work_order_id,
            "engine": self.engine.to_dict(),
            "cases": [case.to_dict() for case in self.cases],
            "command_template": list(self.command_template),
            "score_direction": self.score_direction,
            "score_unit": self.score_unit,
            "score_semantics": self.score_semantics,
            "execution_enabled": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "customer_execution_enabled": False,
            "docking_accuracy_claim_allowed": False,
            "claim_safe": False,
            "claim_boundary": (
                "Offline external-engine comparison work order only; it does not "
                "launch binaries or establish product/scientific parity."
            ),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    def write_json(self, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.tmp-{os.getpid()}")
        temporary.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, output)
        return output


@dataclass(frozen=True)
class ExternalBaselineResultRow:
    case_id: str
    status: str
    score: float | None = None
    pose_path: str = ""
    pose_sha256: str = ""
    error_code: str = ""
    pose_size_bytes: int = field(default=0, init=False)
    pose_verified: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        case_id = str(self.case_id or "").strip()
        status = str(self.status or "").strip().lower()
        pose_path = str(self.pose_path or "").strip()
        pose_sha256 = str(self.pose_sha256 or "").strip()
        error_code = str(self.error_code or "").strip()
        if not case_id:
            raise ExternalBaselineContractError("result case_id must be non-empty")
        if status not in {"success", "failure"}:
            raise ExternalBaselineContractError("result status must be success or failure")
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "pose_path", pose_path)
        object.__setattr__(self, "error_code", error_code)
        if status == "success":
            score = _finite_score(
                self.score,
                message="success result requires a finite non-boolean score",
            )
            if not pose_path:
                raise ExternalBaselineContractError("success result requires pose_path")
            object.__setattr__(self, "score", score)
            object.__setattr__(
                self,
                "pose_sha256",
                _sha256(pose_sha256, name="pose_sha256"),
            )
            if error_code:
                raise ExternalBaselineContractError("success result cannot contain error_code")
        else:
            if self.score is not None or pose_path or pose_sha256:
                raise ExternalBaselineContractError(
                    "failure result cannot contain score or pose provenance"
                )
            if not error_code:
                raise ExternalBaselineContractError("failure result requires error_code")
            object.__setattr__(self, "pose_sha256", "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "status": self.status,
            "score": self.score,
            "pose_path": self.pose_path,
            "pose_sha256": self.pose_sha256,
            "pose_size_bytes": int(self.pose_size_bytes),
            "pose_verified": bool(self.pose_verified),
            "error_code": self.error_code,
        }


@dataclass(frozen=True, init=False)
class ExternalBaselineReceipt:
    work_order: ExternalBaselineWorkOrder
    rows: tuple[ExternalBaselineResultRow, ...]
    schema_id: str = EXTERNAL_BASELINE_RECEIPT_SCHEMA_ID

    def __init__(
        self,
        work_order: ExternalBaselineWorkOrder,
        rows: Sequence[ExternalBaselineResultRow],
        schema_id: str = EXTERNAL_BASELINE_RECEIPT_SCHEMA_ID,
    ) -> None:
        _validate_receipt_content(work_order, tuple(rows), schema_id)
        raise ExternalBaselineContractError(
            "external baseline receipts may only be created by result validation"
        )

    @property
    def success_count(self) -> int:
        return sum(row.status == "success" for row in self.rows)

    @property
    def failure_count(self) -> int:
        return len(self.rows) - self.success_count

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_id": self.schema_id,
            "work_order": self.work_order.to_dict(),
            "work_order_fingerprint_sha256": self.work_order.fingerprint_sha256,
            "rows": [row.to_dict() for row in self.rows],
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "complete": len(self.rows) == len(self.work_order.cases),
            "scientifically_validated": False,
            "benchmark_validated": False,
            "customer_execution_enabled": False,
            "docking_accuracy_claim_allowed": False,
            "claim_safe": False,
            "blockers": [
                "external_baseline_results_not_product_runtime",
                "public_holdout_comparison_not_reviewed",
            ],
        }
        payload["receipt_fingerprint_sha256"] = _canonical_sha256(payload)
        return payload


def _validate_receipt_content(
    work_order: ExternalBaselineWorkOrder,
    rows: tuple[ExternalBaselineResultRow, ...],
    schema_id: str,
) -> None:
    if schema_id != EXTERNAL_BASELINE_RECEIPT_SCHEMA_ID:
        raise ExternalBaselineContractError("unsupported baseline receipt schema")
    expected = [case.case_id for case in work_order.cases]
    observed = [row.case_id for row in rows]
    if observed != expected:
        raise ExternalBaselineContractError(
            "receipt must preserve exactly one ordered row per work-order case"
        )
    for row in rows:
        if row.status == "success" and not row.pose_verified:
            raise ExternalBaselineContractError(
                "receipt success rows require verified pose provenance"
            )
        if row.status == "failure" and (
            row.pose_verified or row.pose_size_bytes != 0
        ):
            raise ExternalBaselineContractError(
                "receipt failure rows cannot contain verified pose provenance"
            )


def read_external_baseline_csv(path: str | Path) -> tuple[dict[str, str], ...]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"external baseline CSV not found: {source}")
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ExternalBaselineContractError("external baseline CSV has no header")
        if tuple(reader.fieldnames) != _CSV_RESULT_FIELDS:
            raise ExternalBaselineContractError(
                "external baseline CSV header must match the result schema exactly"
            )
        parsed: list[dict[str, str]] = []
        for row in reader:
            if None in row:
                raise ExternalBaselineContractError(
                    "external baseline CSV rows must match the result schema exactly"
                )
            parsed.append({str(key): str(value or "") for key, value in row.items()})
        return tuple(parsed)


def _row_value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def validate_external_baseline_results(
    work_order: ExternalBaselineWorkOrder,
    rows: Sequence[Mapping[str, Any]],
    *,
    artifact_root: str | Path,
) -> ExternalBaselineReceipt:
    by_case: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        unknown_fields = set(row).difference(_RESULT_ROW_FIELDS)
        if unknown_fields:
            raise ExternalBaselineContractError(
                "external baseline result contains unsupported fields: "
                + ", ".join(sorted(str(value) for value in unknown_fields))
            )
        case_id = str(row.get("case_id", "") or "").strip()
        if not case_id or case_id in by_case:
            raise ExternalBaselineContractError(
                "external baseline result case IDs must be non-empty and unique"
            )
        by_case[case_id] = row
    expected = {case.case_id for case in work_order.cases}
    if set(by_case) != expected:
        raise ExternalBaselineContractError(
            "external baseline results must cover exactly the work-order cases"
        )
    root = Path(artifact_root)
    validated: list[ExternalBaselineResultRow] = []
    for case in work_order.cases:
        row = by_case[case.case_id]
        status = str(row.get("status", "") or "").strip().lower()
        if status == "failure":
            contradictory = any(
                _row_value_present(row.get(field))
                for field in ("score", "pose_path", "pose_sha256")
            )
            if contradictory:
                raise ExternalBaselineContractError(
                    f"case {case.case_id} failure result cannot contain "
                    "score or pose provenance"
                )
            validated.append(
                ExternalBaselineResultRow(
                    case_id=case.case_id,
                    status="failure",
                    error_code=str(row.get("error_code", "") or "").strip(),
                )
            )
            continue
        if status != "success":
            raise ExternalBaselineContractError(
                f"case {case.case_id} has unsupported result status {status!r}"
            )
        if _row_value_present(row.get("error_code")):
            raise ExternalBaselineContractError(
                f"case {case.case_id} success result cannot contain error_code"
            )
        score = _finite_score(
            row.get("score", ""),
            message=f"case {case.case_id} score is not finite numeric data",
        )
        pose_sha = _sha256(
            str(row.get("pose_sha256", "")),
            name="pose_sha256",
        )
        pose_path = str(row.get("pose_path", "") or "").strip()
        size, actual_pose_sha = _confined_file(root, pose_path, pose_sha)
        validated_row = ExternalBaselineResultRow(
            case_id=case.case_id,
            status="success",
            score=score,
            pose_path=pose_path,
            pose_sha256=actual_pose_sha,
        )
        object.__setattr__(validated_row, "pose_size_bytes", size)
        object.__setattr__(validated_row, "pose_verified", True)
        validated.append(validated_row)

    validator_token = object()
    validated_rows = tuple(validated)

    def issue_receipt(authorization: object) -> ExternalBaselineReceipt:
        if authorization is not validator_token:
            raise ExternalBaselineContractError(
                "external baseline receipt authorization is invalid"
            )
        _validate_receipt_content(
            work_order,
            validated_rows,
            EXTERNAL_BASELINE_RECEIPT_SCHEMA_ID,
        )
        receipt = object.__new__(ExternalBaselineReceipt)
        object.__setattr__(receipt, "work_order", work_order)
        object.__setattr__(receipt, "rows", validated_rows)
        object.__setattr__(
            receipt,
            "schema_id",
            EXTERNAL_BASELINE_RECEIPT_SCHEMA_ID,
        )
        return receipt

    return issue_receipt(validator_token)


__all__ = [
    "EXTERNAL_BASELINE_RECEIPT_SCHEMA_ID",
    "EXTERNAL_BASELINE_WORK_ORDER_SCHEMA_ID",
    "SUPPORTED_EXTERNAL_ENGINES",
    "ExternalBaselineCase",
    "ExternalBaselineContractError",
    "ExternalBaselineEngine",
    "ExternalBaselineReceipt",
    "ExternalBaselineResultRow",
    "ExternalBaselineWorkOrder",
    "read_external_baseline_csv",
    "validate_external_baseline_results",
]
