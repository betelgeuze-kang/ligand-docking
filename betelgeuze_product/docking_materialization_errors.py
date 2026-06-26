"""Structured docking materialization error.

``DockingMaterializationError`` previously encoded everything in a single
string (sometimes ``"code:detail"``). This module gives it a stable
``reason_code`` plus a separate ``reason_detail`` while keeping ``str(error)``
backward compatible, so callers/tests can branch on the category instead of
matching exact strings.

Defined here (dependency-free) and re-exported by the materializer so the heavy
(pandas/rdkit) import surface is not required to construct or inspect the error.
"""

from __future__ import annotations

from betelgeuze_product.structured_reason import join_reason, split_reason


class DockingMaterializationError(ValueError):
    """Raised when the runner cannot prove which ligand source it will materialize.

    Construct with either a combined ``"code:detail"`` string (back-compat) or an
    explicit ``(reason_code, reason_detail)`` pair. ``str(error)`` always renders
    as ``code`` or ``code:detail`` so existing message-based matching keeps
    working; ``.reason_code`` / ``.reason_detail`` expose the structured form.
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


__all__ = ["DockingMaterializationError"]
