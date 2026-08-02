"""Single source of truth for the four product status axes (P0-6).

Status was previously reported as one blended notion of "readiness", which let a
strong result on one axis imply strength on the others: a shipped distribution
version could read as scientific validation, and an evaluator-only benchmark
lane could read as a product guarantee.

These four axes must be reported separately and never collapsed:

- ``distribution_version``: what artifact version exists.
- ``scientific_maturity``: what the science actually supports.
- ``benchmark_maturity``: what the benchmark evidence actually covers.
- ``product_maturity``: what may be offered to whom.

Dependency-free so status reporting stays importable everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

MATURITY_STATUS_SCHEMA_VERSION = "product_maturity_status_v1"

STATUS_AXES = (
    "distribution_version",
    "scientific_maturity",
    "benchmark_maturity",
    "product_maturity",
)

#: Ordered weakest-to-strongest. Order matters: a caller may compare axes, but
#: only within the same axis.
SCIENTIFIC_MATURITY_LEVELS = (
    "not_assessed",
    "known_pocket_scaffold",
    "blind_pocket_capable",
    "prospectively_validated",
)

BENCHMARK_MATURITY_LEVELS = (
    "not_assessed",
    "evaluator_only",
    "internal_frozen_suite",
    "public_frozen_suite",
    "externally_reproduced",
)

PRODUCT_MATURITY_LEVELS = (
    "not_assessed",
    "restricted_internal",
    "developer_preview",
    "external_beta",
    "general_availability",
)

_LEVELS_BY_AXIS = {
    "scientific_maturity": SCIENTIFIC_MATURITY_LEVELS,
    "benchmark_maturity": BENCHMARK_MATURITY_LEVELS,
    "product_maturity": PRODUCT_MATURITY_LEVELS,
}


class MaturityStatusError(ValueError):
    """Raised when a status axis value is not a declared level."""


@dataclass(frozen=True)
class MaturityStatus:
    """The four axes, reported together but never merged into one score."""

    distribution_version: str
    scientific_maturity: str
    benchmark_maturity: str
    product_maturity: str

    def __post_init__(self) -> None:
        if not str(self.distribution_version).strip():
            raise MaturityStatusError("distribution_version_missing")
        for axis, levels in _LEVELS_BY_AXIS.items():
            value = str(getattr(self, axis) or "").strip()
            if value not in levels:
                raise MaturityStatusError(f"{axis}_invalid:{value or '<empty>'}")

    def as_dict(self) -> dict[str, str]:
        return {
            "distribution_version": str(self.distribution_version).strip(),
            "scientific_maturity": str(self.scientific_maturity).strip(),
            "benchmark_maturity": str(self.benchmark_maturity).strip(),
            "product_maturity": str(self.product_maturity).strip(),
        }

    def receipt(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "maturity_status_schema_version": MATURITY_STATUS_SCHEMA_VERSION,
        }
        payload.update(self.as_dict())
        return payload

    def as_markdown_lines(self) -> list[str]:
        return [f"- {axis}: `{value}`" for axis, value in self.as_dict().items()]


def parse_maturity_status(payload: Mapping[str, Any]) -> MaturityStatus:
    """Build a status from a mapping, failing closed on a missing axis."""

    if not isinstance(payload, Mapping):
        raise MaturityStatusError("maturity_status_payload_invalid")
    missing = [
        axis
        for axis in STATUS_AXES
        if not str(payload.get(axis) or "").strip()
    ]
    if missing:
        raise MaturityStatusError("maturity_status_axis_missing:" + ",".join(missing))
    return MaturityStatus(
        distribution_version=str(payload["distribution_version"]).strip(),
        scientific_maturity=str(payload["scientific_maturity"]).strip(),
        benchmark_maturity=str(payload["benchmark_maturity"]).strip(),
        product_maturity=str(payload["product_maturity"]).strip(),
    )


__all__ = [
    "BENCHMARK_MATURITY_LEVELS",
    "MATURITY_STATUS_SCHEMA_VERSION",
    "MaturityStatus",
    "MaturityStatusError",
    "PRODUCT_MATURITY_LEVELS",
    "SCIENTIFIC_MATURITY_LEVELS",
    "STATUS_AXES",
    "parse_maturity_status",
]
