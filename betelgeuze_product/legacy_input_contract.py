"""Fail-closed input contract for the legacy product intake path.

The legacy product path historically accepted malformed intake and silently
substituted a "safe" value:

- an unparseable ``ATOM``/``HETATM`` coordinate column was skipped, so a
  structure could be analyzed with a subset of its atoms;
- an invalid numeric field fell back to a hardcoded default;
- a missing required field fell back to a placeholder (``UNK``, ``_``, ``0``);
- a non-boolean value was coerced by truthiness.

Each of those turns a bad request into a plausible-looking result, which is the
opposite of what a product intake boundary should do. This module makes the
legacy path fail closed by default and keeps the old behaviour reachable only
through an explicit, recorded compatibility mode.

Dependency-free on purpose: the intake boundary must stay importable without
numpy/pandas/rdkit so it can be validated in lightweight contexts.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from betelgeuze_product.structured_reason import join_reason, split_reason

LEGACY_INPUT_CONTRACT_VERSION = "legacy_product_input_contract_v1"

#: Environment switch for the explicit compatibility mode. Unset/anything other
#: than the canonical true tokens means fail-closed.
LEGACY_INPUT_COMPATIBILITY_ENV = "BETELGEUZE_LEGACY_INPUT_COMPATIBILITY_MODE"

_TRUE_TOKENS = frozenset({"1", "true", "yes", "y", "on"})
_FALSE_TOKENS = frozenset({"0", "false", "no", "n", "off"})

REASON_INVALID_COORDINATE = "legacy_input_invalid_coordinate"
REASON_INVALID_NUMERIC = "legacy_input_invalid_numeric"
REASON_MISSING_REQUIRED_FIELD = "legacy_input_missing_required_field"
REASON_INVALID_BOOLEAN = "legacy_input_invalid_boolean"

LEGACY_INPUT_FAIL_CLOSED_REASON_CODES = (
    REASON_INVALID_COORDINATE,
    REASON_INVALID_NUMERIC,
    REASON_MISSING_REQUIRED_FIELD,
    REASON_INVALID_BOOLEAN,
)


class LegacyInputContractError(ValueError):
    """Raised when legacy product intake cannot be trusted.

    Carries a stable ``reason_code`` plus a diagnostic ``reason_detail`` so
    callers branch on the category instead of matching message text, matching
    the convention used by :mod:`betelgeuze_product.structured_reason`.
    """

    def __init__(self, reason_code: str, reason_detail: str = ""):
        if reason_detail == "" and ":" in str(reason_code):
            code, detail = split_reason(reason_code)
        else:
            code, detail = str(reason_code), str(reason_detail)
        self.reason_code = code
        self.reason_detail = detail
        super().__init__(join_reason(code, detail))

    @property
    def reason(self) -> str:
        return join_reason(self.reason_code, self.reason_detail)


@dataclass(frozen=True)
class LegacyInputPolicy:
    """Resolved intake policy for one legacy product request.

    ``compatibility_mode`` restores the pre-contract lenient behaviour. It is
    never the default and is always reported in the receipt so a lenient parse
    can never be mistaken for a strict one.
    """

    compatibility_mode: bool = False

    @property
    def fail_closed(self) -> bool:
        return not self.compatibility_mode

    def receipt(self) -> dict[str, Any]:
        return {
            "legacy_input_contract_version": LEGACY_INPUT_CONTRACT_VERSION,
            "fail_closed": bool(self.fail_closed),
            "compatibility_mode": bool(self.compatibility_mode),
        }


def resolve_legacy_input_policy(
    *,
    compatibility_mode: bool | None = None,
    env: Mapping[str, str] | None = None,
) -> LegacyInputPolicy:
    """Resolve the intake policy.

    An explicit ``compatibility_mode`` argument wins. Otherwise the environment
    switch is consulted, and anything that is not a canonical true token
    (including an unset variable and an unparseable value) resolves to
    fail-closed.
    """

    if compatibility_mode is not None:
        return LegacyInputPolicy(compatibility_mode=bool(compatibility_mode))
    source = os.environ if env is None else env
    raw = str(source.get(LEGACY_INPUT_COMPATIBILITY_ENV, "") or "").strip().lower()
    return LegacyInputPolicy(compatibility_mode=raw in _TRUE_TOKENS)


def _detail(field: str, value: Any) -> str:
    rendered = str(value)
    if len(rendered) > 64:
        rendered = rendered[:61] + "..."
    return f"field={field} value={rendered!r}"


def require_field(
    payload: Mapping[str, Any],
    field: str,
    *,
    policy: LegacyInputPolicy,
    default: Any = None,
    context: str = "",
) -> Any:
    """Return ``payload[field]``, failing closed when it is absent or blank.

    In compatibility mode the supplied ``default`` is returned instead, which is
    the historical placeholder behaviour.
    """

    value = payload.get(field) if isinstance(payload, Mapping) else None
    present = value is not None and str(value).strip() != ""
    if present:
        return value
    if policy.compatibility_mode:
        return default
    raise LegacyInputContractError(
        REASON_MISSING_REQUIRED_FIELD,
        f"field={field}" + (f" context={context}" if context else ""),
    )


def require_fields(
    payload: Mapping[str, Any],
    fields: Iterable[str],
    *,
    policy: LegacyInputPolicy,
    context: str = "",
) -> None:
    """Fail closed listing every missing required field at once."""

    missing = [
        field
        for field in fields
        if not (
            isinstance(payload, Mapping)
            and payload.get(field) is not None
            and str(payload.get(field)).strip() != ""
        )
    ]
    if not missing or policy.compatibility_mode:
        return
    detail = "fields=" + ",".join(missing)
    raise LegacyInputContractError(
        REASON_MISSING_REQUIRED_FIELD,
        detail + (f" context={context}" if context else ""),
    )


def strict_float(
    value: Any,
    *,
    field: str,
    policy: LegacyInputPolicy,
    default: float | None = None,
    allow_non_finite: bool = False,
) -> float | None:
    """Parse a numeric intake field without a silent default.

    Fails closed on ``None``, blank, unparseable, and (unless
    ``allow_non_finite``) NaN/inf. In compatibility mode the historical
    ``default`` is returned.
    """

    if value is None or (isinstance(value, str) and value.strip() == ""):
        if policy.compatibility_mode:
            return default
        raise LegacyInputContractError(REASON_INVALID_NUMERIC, _detail(field, value))
    if isinstance(value, bool):
        # A boolean silently scoring as 0.0/1.0 is exactly the coercion this
        # contract exists to reject.
        if policy.compatibility_mode:
            return float(value)
        raise LegacyInputContractError(REASON_INVALID_NUMERIC, _detail(field, value))
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        if policy.compatibility_mode:
            return default
        raise LegacyInputContractError(REASON_INVALID_NUMERIC, _detail(field, value)) from None
    if not allow_non_finite and not math.isfinite(parsed):
        if policy.compatibility_mode:
            return default
        raise LegacyInputContractError(REASON_INVALID_NUMERIC, _detail(field, value))
    return parsed


def strict_int(
    value: Any,
    *,
    field: str,
    policy: LegacyInputPolicy,
    default: int | None = None,
) -> int | None:
    """Parse an integer intake field, rejecting non-integral numerics."""

    if value is None or (isinstance(value, str) and value.strip() == ""):
        if policy.compatibility_mode:
            return default
        raise LegacyInputContractError(REASON_INVALID_NUMERIC, _detail(field, value))
    if isinstance(value, bool):
        if policy.compatibility_mode:
            return int(value)
        raise LegacyInputContractError(REASON_INVALID_NUMERIC, _detail(field, value))
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        if policy.compatibility_mode:
            return default
        raise LegacyInputContractError(REASON_INVALID_NUMERIC, _detail(field, value)) from None
    if not math.isfinite(parsed) or parsed != int(parsed):
        if policy.compatibility_mode:
            return default
        raise LegacyInputContractError(REASON_INVALID_NUMERIC, _detail(field, value))
    return int(parsed)


def strict_bool(
    value: Any,
    *,
    field: str,
    policy: LegacyInputPolicy,
    default: bool | None = None,
) -> bool | None:
    """Parse a boolean intake field without truthiness coercion.

    Accepts real booleans and the canonical string/int tokens. Everything else
    fails closed, so ``"maybe"`` or ``"0.5"`` can no longer become ``True``.
    """

    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, str) and value.strip() == ""):
        if policy.compatibility_mode:
            return default
        raise LegacyInputContractError(REASON_INVALID_BOOLEAN, _detail(field, value))
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    token = str(value).strip().lower()
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    if policy.compatibility_mode:
        return bool(value) if default is None else default
    raise LegacyInputContractError(REASON_INVALID_BOOLEAN, _detail(field, value))


def strict_coordinate(
    values: Sequence[Any],
    *,
    field: str,
    policy: LegacyInputPolicy,
    max_abs_coordinate_a: float = 1.0e6,
) -> tuple[float, float, float] | None:
    """Parse an ``(x, y, z)`` coordinate triple, failing closed on garbage.

    Rejects wrong arity, unparseable columns, NaN/inf, and physically absurd
    magnitudes. Returns ``None`` only in compatibility mode, matching the old
    "skip this atom" behaviour.
    """

    raw = list(values or [])
    if len(raw) != 3:
        if policy.compatibility_mode:
            return None
        raise LegacyInputContractError(
            REASON_INVALID_COORDINATE, f"field={field} expected=3 observed={len(raw)}"
        )
    parsed: list[float] = []
    for axis, item in zip(("x", "y", "z"), raw):
        if isinstance(item, bool):
            if policy.compatibility_mode:
                return None
            raise LegacyInputContractError(
                REASON_INVALID_COORDINATE, _detail(f"{field}.{axis}", item)
            )
        try:
            component = float(item)
        except (TypeError, ValueError):
            if policy.compatibility_mode:
                return None
            raise LegacyInputContractError(
                REASON_INVALID_COORDINATE, _detail(f"{field}.{axis}", item)
            ) from None
        if not math.isfinite(component) or abs(component) > float(max_abs_coordinate_a):
            if policy.compatibility_mode:
                return None
            raise LegacyInputContractError(
                REASON_INVALID_COORDINATE, _detail(f"{field}.{axis}", item)
            )
        parsed.append(component)
    return (parsed[0], parsed[1], parsed[2])


__all__ = [
    "LEGACY_INPUT_COMPATIBILITY_ENV",
    "LEGACY_INPUT_CONTRACT_VERSION",
    "LEGACY_INPUT_FAIL_CLOSED_REASON_CODES",
    "LegacyInputContractError",
    "LegacyInputPolicy",
    "REASON_INVALID_BOOLEAN",
    "REASON_INVALID_COORDINATE",
    "REASON_INVALID_NUMERIC",
    "REASON_MISSING_REQUIRED_FIELD",
    "require_field",
    "require_fields",
    "resolve_legacy_input_policy",
    "strict_bool",
    "strict_coordinate",
    "strict_float",
    "strict_int",
]
