"""Active proxy-energy field names for the refine-tier benchmark surface (P0-5).

``deltaG_*_kcal_mol`` is retired from the active schema. Those names read like
calibrated binding free energies in kcal/mol, but the values they carried were
uncalibrated internal proxy scores, so any downstream reader (operator sheet,
benchmark work order, evidence bundle) could mistake a proxy for a measurement.

The active names below state what the value actually is. The retired names stay
listed so historical artifacts can still be read, and so a contract test can
assert the active surface never emits them again.

Dependency-free on purpose: benchmark tooling imports this without pulling in
numpy/pandas.
"""

from __future__ import annotations

from typing import Any, Mapping

PROXY_ENERGY_SCHEMA_VERSION = "proxy_energy_field_names_v1"

#: Internal GB/SA refine-tier proxy score (unitless, uncalibrated).
INTERNAL_REFINE_PROXY_SCORE_FIELD = "internal_refine_proxy_score"

#: Candidate-side proxy score in a paired benchmark row.
CANDIDATE_REFINE_PROXY_SCORE_FIELD = "candidate_refine_proxy_score"

#: Generic proxy-score column used by recovery/audit queues.
REFINE_PROXY_SCORE_FIELD = "refine_proxy_score"

#: Retired names, newest-first per field. Read-only compatibility.
RETIRED_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    INTERNAL_REFINE_PROXY_SCORE_FIELD: ("deltaG_mm_gbsa_kcal_mol",),
    CANDIDATE_REFINE_PROXY_SCORE_FIELD: ("deltaG_candidate_kcal_mol",),
    REFINE_PROXY_SCORE_FIELD: ("deltaG_proxy_kcal_mol",),
}

#: Every retired proxy-energy field name. An experimental measurement column
#: (``deltaG_experimental_kcal_mol``) is intentionally NOT here: it really is a
#: measured free energy in kcal/mol, so its name is accurate.
RETIRED_PROXY_ENERGY_FIELDS = tuple(
    alias for aliases in RETIRED_FIELD_ALIASES.values() for alias in aliases
)


def field_with_aliases(field: str) -> tuple[str, ...]:
    """Return ``field`` followed by its retired aliases, in read priority order."""

    name = str(field)
    return (name, *RETIRED_FIELD_ALIASES.get(name, ()))


def read_proxy_energy(row: Mapping[str, Any], field: str, default: Any = None) -> Any:
    """Read a proxy-energy value, tolerating retired field names on input.

    Writers must use the active name; only readers accept the retired aliases.
    """

    if not isinstance(row, Mapping):
        return default
    for candidate in field_with_aliases(field):
        if candidate in row:
            value = row[candidate]
            if value not in {None, ""}:
                return value
    return default


def rename_retired_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    """Upgrade a row read from a pre-rename artifact to the active field names."""

    if not isinstance(row, Mapping):
        return {}
    alias_to_active = {
        alias: active
        for active, aliases in RETIRED_FIELD_ALIASES.items()
        for alias in aliases
    }
    out: dict[str, Any] = {}
    for key, value in row.items():
        out[alias_to_active.get(str(key), str(key))] = value
    return out


__all__ = [
    "CANDIDATE_REFINE_PROXY_SCORE_FIELD",
    "INTERNAL_REFINE_PROXY_SCORE_FIELD",
    "PROXY_ENERGY_SCHEMA_VERSION",
    "REFINE_PROXY_SCORE_FIELD",
    "RETIRED_FIELD_ALIASES",
    "RETIRED_PROXY_ENERGY_FIELDS",
    "field_with_aliases",
    "read_proxy_energy",
    "rename_retired_fields",
]
