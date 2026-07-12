"""Version contracts shared by the independent engine v2 packages.

The molecular schema is intentionally independent from package releases. A
consumer can therefore reject a topology it cannot interpret before any
scientific calculation is attempted.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


ENGINE_API_VERSION = "2.0.0"
ALL_ATOM_SCHEMA_NAME = "betelgeuze.all_atom_system"
ALL_ATOM_SCHEMA_VERSION = "2.0.0"
ALL_ATOM_SCHEMA_ID = f"{ALL_ATOM_SCHEMA_NAME}/{ALL_ATOM_SCHEMA_VERSION}"

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)\.(?P<minor>0|[1-9][0-9]*)\.(?P<patch>0|[1-9][0-9]*)$"
)


class ContractVersionError(ValueError):
    """Raised when a versioned payload is not compatible with engine v2."""


@dataclass(frozen=True, order=True)
class SemanticVersion:
    """Small, dependency-free semantic-version value used by data contracts."""

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
                f"engine v2 supports major {supported.major}"
            )
        if received > supported:
            raise ContractVersionError(
                f"schema {self.schema_id} is newer than supported {ALL_ATOM_SCHEMA_ID}"
            )


def parse_schema_id(schema_id: str) -> SchemaIdentity:
    """Parse ``name/x.y.z`` without accepting ambiguous partial versions."""

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
