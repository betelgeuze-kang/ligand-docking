"""Reuse canonical validation within one request, with full mutation checks.

Only a successful report for the exact same live object can be reused. Every
reuse calls the unchanged AllAtomSystem integrity owner, including its complete
tensor and nested-metadata digest. Numerical, parameter, source-file and geometry
checks are not cached. No frozen V2 implementation or registry is modified.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from threading import get_ident

from betelgeuze_engine_v2.molecular import AllAtomSystem
from betelgeuze_engine_v2.molecular.validation import require_valid_all_atom_system

_REQUEST_VALIDATION = ContextVar("prepared_request_validation", default=None)
_MAX_ENTRIES = 64


@contextmanager
def prepared_validation_scope():
    """Create a bounded, nonpersistent cache; nested requests are independent."""
    token = _REQUEST_VALIDATION.set((get_ident(), {}))
    try:
        yield
    finally:
        _REQUEST_VALIDATION.reset(token)


def require_valid_prepared_system(system, *, warnings_as_errors=False):
    """Return the owner's report without repeating unchanged canonical encoding."""
    scope = _REQUEST_VALIDATION.get()
    if type(system) is not AllAtomSystem or scope is None or scope[0] != get_ident():
        return require_valid_all_atom_system(system, warnings_as_errors=warnings_as_errors)
    cache = scope[1]
    entry = cache.get(id(system))
    if entry is not None and entry[0] is system:
        # Tensor version counters are insufficient: NumPy aliases and .data can
        # change bytes without incrementing them. Always use the full owner.
        AllAtomSystem.assert_integrity(system)
        report = entry[1]
        report.raise_for_errors(warnings_as_errors=warnings_as_errors)
        return report
    report = require_valid_all_atom_system(system, warnings_as_errors=warnings_as_errors)
    AllAtomSystem.assert_integrity(system)
    if len(cache) >= _MAX_ENTRIES:
        # Strong references prevent object-id reuse. Bound their request lifetime
        # and count; eviction merely causes a fresh canonical validation.
        cache.pop(next(iter(cache)))
    cache[id(system)] = (system, report)
    return report
