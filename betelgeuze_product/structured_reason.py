"""Structured reason helpers.

Several fail-closed paths report a ``reason`` string that follows a
``"code"`` or ``"code:detail"`` convention (e.g. dispatch eligibility,
materialization errors). Historically callers/tests matched on the exact
string, which is brittle: appending a detail (like a profile id) to a code
broke equality assertions.

These helpers split a reason into a stable ``reason_code`` (the category) and a
separate ``reason_detail`` so consumers can branch on the category and keep the
detail for diagnostics. Dependency-free so it is trivially testable.
"""

from __future__ import annotations

from typing import Any


def split_reason(reason: Any) -> tuple[str, str]:
    """Split ``"code:detail"`` into ``(code, detail)``.

    The split is on the FIRST colon only, so a detail that itself contains
    colons (e.g. ``"expected=2:observed=1"``) is preserved intact. A reason with
    no colon yields ``(reason, "")``.
    """

    text = str(reason or "")
    code, sep, detail = text.partition(":")
    return code, (detail if sep else "")


def reason_fields(reason: Any) -> dict[str, str]:
    """Return ``{"reason", "reason_code", "reason_detail"}`` for a reason.

    Keeps the original ``reason`` string for backward compatibility while adding
    the structured fields.
    """

    code, detail = split_reason(reason)
    return {"reason": str(reason or ""), "reason_code": code, "reason_detail": detail}


def join_reason(reason_code: str, reason_detail: str = "") -> str:
    """Inverse of :func:`split_reason`."""

    code = str(reason_code or "")
    detail = str(reason_detail or "")
    return f"{code}:{detail}" if detail else code


__all__ = ["split_reason", "reason_fields", "join_reason"]
