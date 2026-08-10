"""Canonical, engine-neutral contracts for external benchmark oracles."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, Mapping

from .errors import OracleContractError


REQUEST_SCHEMA_ID = "betelgeuze.external_oracle_request/1.0.0"
RESULT_SCHEMA_ID = "betelgeuze.external_oracle_result/1.0.0"
CANONICAL_UNITS = MappingProxyType(
    {
        "length": "angstrom",
        "energy": "kcal/mol",
        "force": "kcal/(mol*angstrom)",
        "charge": "elementary_charge",
        "mass": "dalton",
        "angle": "radian",
        "time": "femtosecond",
        "temperature": "kelvin",
    }
)
SUPPORTED_ENGINES = frozenset({"openmm", "gromacs", "vina", "gnina"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_INPUT_ROLE = re.compile(r"^[a-z][a-z0-9_]*$")


def _canonical_value(value: Any, *, path: str = "payload") -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise OracleContractError(f"{path} contains a non-finite number")
        return float(value)
    if isinstance(value, (list, tuple)):
        return [
            _canonical_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise OracleContractError(f"{path} object keys must be strings")
            normalized[key] = _canonical_value(item, path=f"{path}.{key}")
        return {key: normalized[key] for key in sorted(normalized)}
    raise OracleContractError(f"{path} is not canonical JSON")


def _freeze_value(value: Any) -> Any:
    """Recursively freeze an already-normalized canonical JSON value."""

    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze_value(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    return value


def _plain_value(value: Any) -> Any:
    """Return a detached mutable JSON tree for serialization and callers."""

    if isinstance(value, Mapping):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain_value(item) for item in value]
    return value


def canonical_json_bytes(payload: Any) -> bytes:
    """Return the one permitted UTF-8 representation for a contract value."""

    try:
        return (
            json.dumps(
                _canonical_value(payload),
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise OracleContractError("payload is not canonical JSON") from exc


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def require_sha256(value: str, *, field: str) -> str:
    if not isinstance(value, str):
        raise OracleContractError(f"{field} must be a lowercase SHA-256")
    normalized = value.strip().lower()
    if _SHA256.fullmatch(normalized) is None:
        raise OracleContractError(f"{field} must be a lowercase SHA-256")
    return normalized


@dataclass(frozen=True)
class OracleRequest:
    """A prepared, hashed benchmark case; adapters may not prepare inputs."""

    engine_id: str
    case_id: str
    task: str
    input_sha256: Mapping[str, str]
    parameters: Mapping[str, Any]
    seed: int = 0
    thread_count: int = 1

    def __post_init__(self) -> None:
        engine = str(self.engine_id or "").strip().lower()
        case_id = str(self.case_id or "").strip()
        task = str(self.task or "").strip()
        if engine not in SUPPORTED_ENGINES:
            raise OracleContractError("unsupported external oracle engine")
        if not case_id or not task:
            raise OracleContractError("case_id and task must be non-empty")
        if (
            isinstance(self.seed, bool)
            or not isinstance(self.seed, int)
            or not 0 <= self.seed <= (1 << 64) - 1
        ):
            raise OracleContractError("seed must fit uint64")
        if (
            isinstance(self.thread_count, bool)
            or not isinstance(self.thread_count, int)
            or self.thread_count <= 0
        ):
            raise OracleContractError("thread_count must be positive")
        if not isinstance(self.input_sha256, Mapping):
            raise OracleContractError("input_sha256 must be an object")
        if not isinstance(self.parameters, Mapping):
            raise OracleContractError("parameters must be an object")
        if any(
            type(role) is not str or _INPUT_ROLE.fullmatch(role) is None
            for role in self.input_sha256
        ):
            raise OracleContractError(
                "input digest roles must be canonical identifiers"
            )
        hashes = {
            role: require_sha256(digest, field=f"input_sha256.{role}")
            for role, digest in self.input_sha256.items()
        }
        if not hashes or any(not role for role in hashes):
            raise OracleContractError("at least one named input digest is required")
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "task", task)
        object.__setattr__(
            self, "input_sha256", MappingProxyType(dict(sorted(hashes.items())))
        )
        object.__setattr__(
            self,
            "parameters",
            _freeze_value(_canonical_value(self.parameters, path="parameters")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": REQUEST_SCHEMA_ID,
            "engine_id": self.engine_id,
            "case_id": self.case_id,
            "task": self.task,
            "canonical_units": dict(CANONICAL_UNITS),
            "input_sha256": dict(self.input_sha256),
            "parameters": _plain_value(self.parameters),
            "seed": self.seed,
            "thread_count": self.thread_count,
            "prepared_inputs_only": True,
            "customer_execution_enabled": False,
            "claim_safe": False,
        }

    @property
    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class OracleResult:
    """Normalized external output with immutable identity and no product claim."""

    request_sha256: str
    engine_id: str
    engine_version: str
    executable_sha256: str
    status: str
    values: Mapping[str, Any]
    raw_output_sha256: Mapping[str, str]
    error_code: str = ""

    def __post_init__(self) -> None:
        request_hash = require_sha256(self.request_sha256, field="request_sha256")
        executable_hash = require_sha256(
            self.executable_sha256, field="executable_sha256"
        )
        engine = str(self.engine_id or "").strip().lower()
        version = " ".join(str(self.engine_version or "").split())
        status = str(self.status or "").strip().lower()
        error = str(self.error_code or "").strip().lower()
        if engine not in SUPPORTED_ENGINES or not version:
            raise OracleContractError("result engine identity is incomplete")
        if status not in {"success", "failure"}:
            raise OracleContractError("result status must be success or failure")
        if status == "success" and error:
            raise OracleContractError("successful result cannot contain error_code")
        if status == "failure" and not error:
            raise OracleContractError("failed result requires error_code")
        if not isinstance(self.values, Mapping):
            raise OracleContractError("values must be an object")
        if not isinstance(self.raw_output_sha256, Mapping):
            raise OracleContractError("raw_output_sha256 must be an object")
        if any(
            type(role) is not str or _INPUT_ROLE.fullmatch(role) is None
            for role in self.raw_output_sha256
        ):
            raise OracleContractError("raw output roles must be canonical identifiers")
        output_hashes = {
            role: require_sha256(digest, field=f"raw_output_sha256.{role}")
            for role, digest in self.raw_output_sha256.items()
        }
        if status == "success" and not output_hashes:
            raise OracleContractError("successful result requires raw output digests")
        object.__setattr__(self, "request_sha256", request_hash)
        object.__setattr__(self, "executable_sha256", executable_hash)
        object.__setattr__(self, "engine_id", engine)
        object.__setattr__(self, "engine_version", version)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "error_code", error)
        object.__setattr__(
            self,
            "values",
            _freeze_value(_canonical_value(self.values, path="values")),
        )
        object.__setattr__(
            self,
            "raw_output_sha256",
            MappingProxyType(dict(sorted(output_hashes.items()))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": RESULT_SCHEMA_ID,
            "request_sha256": self.request_sha256,
            "engine": {
                "engine_id": self.engine_id,
                "engine_version": self.engine_version,
                "executable_sha256": self.executable_sha256,
            },
            "status": self.status,
            "values": _plain_value(self.values),
            "raw_output_sha256": dict(self.raw_output_sha256),
            "error_code": self.error_code,
            "benchmark_oracle_only": True,
            "customer_execution_enabled": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())
