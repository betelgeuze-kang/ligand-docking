"""Contract-first AI-MD product boundary.

This package intentionally starts small: it freezes JSON-serializable contracts
and reference oracles that existing core/runtime code can adapt to before larger
engine refactors.
"""

from __future__ import annotations

__all__ = ["contracts", "coarse_md"]
