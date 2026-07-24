"""Version taxonomy shared by independent Engine v2 contracts.

Distribution, API, molecular-state, runtime-input, checkpoint, and result
versions are intentionally distinct. Consumers must validate the contract they
actually consume instead of treating one package version as universal.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

DISTRIBUTION_NAME = "betelgeuze-engine-v2"
DISTRIBUTION_VERSION = "0.3.0a1"
ENGINE_API_VERSION = "2.0.0"
ENGINE_RESULT_SCHEMA_VERSION = "2.0.0"
CHECKPOINT_SCHEMA_VERSION = "2.0.0"
RUNTIME_INPUT_SCHEMA_VERSION = "2.1.0"
ALL_ATOM_SCHEMA_NAME = "betelgeuze.all_atom_system"
ALL_ATOM_SCHEMA_VERSION = "2.0.0"
ALL_ATOM_SCHEMA_ID = f"{ALL_ATOM_SCHEMA_NAME}/{ALL_ATOM_SCHEMA_VERSION}"

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)$"
)
_DISTRIBUTION_VERSION_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:(a|b|rc)(0|[1-9][0-9]*))?$"
)


class ContractVersionError(ValueError):
    """Raised when a versioned payload is not compatible with Engine v2."""


@dataclass(frozen=True, order=True)
class SemanticVersion:
    """Small dependency-free semantic version used by serialized contracts."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "SemanticVersion":
        match = _SEMVER_RE.fullmatch(str(value or ""))
        if match is None:
            raise ContractVersionError(f"invalid semantic version: {value!r}")
        return cls(*(int(match.group(name)) for name in ("major", "minor", "patch")))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def require_distribution_version(value: str) -> str:
    text = str(value or "")
    if _DISTRIBUTION_VERSION_RE.fullmatch(text) is None:
        raise ContractVersionError(f"invalid distribution version: {value!r}")
    return text


@dataclass(frozen=True)
class VersionTaxonomy:
    """Machine-readable inventory of independently evolving version surfaces."""

    distribution_name: str = DISTRIBUTION_NAME
    distribution_version: str = DISTRIBUTION_VERSION
    engine_api_version: str = ENGINE_API_VERSION
    molecular_schema_version: str = ALL_ATOM_SCHEMA_VERSION
    result_schema_version: str = ENGINE_RESULT_SCHEMA_VERSION
    checkpoint_schema_version: str = CHECKPOINT_SCHEMA_VERSION
    runtime_input_schema_version: str = RUNTIME_INPUT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not str(self.distribution_name).strip():
            raise ContractVersionError("distribution_name must be non-empty")
        require_distribution_version(self.distribution_version)
        for value in (
            self.engine_api_version,
            self.molecular_schema_version,
            self.result_schema_version,
            self.checkpoint_schema_version,
            self.runtime_input_schema_version,
        ):
            SemanticVersion.parse(str(value))

    def to_dict(self) -> dict[str, str]:
        return {
            "distribution_name": self.distribution_name,
            "distribution_version": self.distribution_version,
            "engine_api_version": self.engine_api_version,
            "molecular_schema_version": self.molecular_schema_version,
            "result_schema_version": self.result_schema_version,
            "checkpoint_schema_version": self.checkpoint_schema_version,
            "runtime_input_schema_version": self.runtime_input_schema_version,
        }


VERSION_TAXONOMY = VersionTaxonomy()


@dataclass(frozen=True)
class SchemaIdentity:
    """Stable identity carried by every canonical all-atom system."""

    name: str = ALL_ATOM_SCHEMA_NAME
    version: str = ALL_ATOM_SCHEMA_VERSION

    @property
    def schema_id(self) -> str:
        return f"{self.name}/{self.version}"

    def require_compatible(self) -> None:
        if self.name != ALL_ATOM_SCHEMA_NAME:
            raise ContractVersionError(
                f"unsupported schema name {self.name!r}; expected {ALL_ATOM_SCHEMA_NAME!r}"
            )
        received = SemanticVersion.parse(self.version)
        supported = SemanticVersion.parse(ALL_ATOM_SCHEMA_VERSION)
        if received.major != supported.major:
            raise ContractVersionError(
                f"unsupported {self.name} major version {received.major}; "
                f"Engine v2 supports major {supported.major}"
            )
        if received > supported:
            raise ContractVersionError(
                f"schema {self.schema_id} is newer than supported {ALL_ATOM_SCHEMA_ID}"
            )


def parse_schema_id(schema_id: str) -> SchemaIdentity:
    text = str(schema_id or "")
    if "/" not in text:
        raise ContractVersionError(f"invalid schema id: {schema_id!r}")
    name, version = text.rsplit("/", 1)
    identity = SchemaIdentity(name=name, version=version)
    SemanticVersion.parse(identity.version)
    return identity


def require_compatible_schema(schema_id: str) -> SchemaIdentity:
    identity = parse_schema_id(schema_id)
    identity.require_compatible()
    return identity


__all__ = [
    "ALL_ATOM_SCHEMA_ID",
    "ALL_ATOM_SCHEMA_NAME",
    "ALL_ATOM_SCHEMA_VERSION",
    "CHECKPOINT_SCHEMA_VERSION",
    "DISTRIBUTION_NAME",
    "DISTRIBUTION_VERSION",
    "ENGINE_API_VERSION",
    "ENGINE_RESULT_SCHEMA_VERSION",
    "RUNTIME_INPUT_SCHEMA_VERSION",
    "VERSION_TAXONOMY",
    "ContractVersionError",
    "SchemaIdentity",
    "SemanticVersion",
    "VersionTaxonomy",
    "parse_schema_id",
    "require_compatible_schema",
    "require_distribution_version",
]
