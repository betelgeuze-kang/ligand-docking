from __future__ import annotations

from typing import Any

DEFAULT_DENSE_DIAGNOSTIC_MAX_ATOMS = 512


def ensure_small_dense_diagnostic(
    coords: Any,
    *,
    max_atoms: int = DEFAULT_DENSE_DIAGNOSTIC_MAX_ATOMS,
    context: str,
) -> int:
    """Fail closed before diagnostic-only NxN distance allocations grow product-sized."""

    shape = getattr(coords, "shape", ())
    if len(shape) < 2:
        return 0
    atom_count = int(shape[-2])
    cap = int(max_atoms)
    if cap < 1:
        raise ValueError(f"{context} dense diagnostic atom cap must be >= 1")
    if atom_count > cap:
        raise ValueError(
            f"{context} dense NxN diagnostic is limited to <= {cap} atoms; "
            f"got {atom_count}. Use a cell-list/product neighbor provider path."
        )
    return atom_count
