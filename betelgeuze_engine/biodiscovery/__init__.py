"""Tier-beta structure-based ligand screening vertical slice.

Local-only, deterministic calculations. No external data, downloads,
public PDB lookup, or other-team models. Fail-closed on invalid input.
"""

from betelgeuze_engine.biodiscovery.contracts import (
    FailureCode,
    StageRecord,
    TierBetaScreeningInput,
    TierBetaScreeningOutput,
)
from betelgeuze_engine.biodiscovery import pose as _pose_module
from betelgeuze_engine.biodiscovery import screening as _screening_module
from betelgeuze_engine.biodiscovery.strict_pose_contracts import (
    install_strict_pose_contracts,
)

# Install the compatibility-preserving strict contract before exposing either the
# package class or the legacy submodule class. Python initializes this package
# before returning any ``biodiscovery.pose`` or ``biodiscovery.screening`` import,
# so all supported import paths observe the same reviewed semantics.
install_strict_pose_contracts(_pose_module, _screening_module)

TierBetaScreening = _screening_module.TierBetaScreening
TierBetaScreeningResult = _screening_module.TierBetaScreeningResult

__all__ = [
    "FailureCode",
    "StageRecord",
    "TierBetaScreening",
    "TierBetaScreeningInput",
    "TierBetaScreeningOutput",
    "TierBetaScreeningResult",
]
