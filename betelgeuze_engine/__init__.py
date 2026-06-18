"""Product engine scaffold for AI-MD topology, physics, and evidence modules."""

from betelgeuze_engine.contracts.result import EnergyForces, TermResult
from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_engine.physics.forcefield import (
    ProductForceField,
    ForceTermRegistry,
    default_force_term_registry,
    guarded_force_term_registry,
)
from betelgeuze_engine.residual.guarded_force import (
    ForceResidualDecision,
    ForceResidualPolicy,
    ForceResidualReport,
)

__all__ = [
    "EnergyForces",
    "EngineState",
    "ForceResidualDecision",
    "ForceResidualPolicy",
    "ForceResidualReport",
    "ForceTermRegistry",
    "ProductForceField",
    "TermResult",
    "default_force_term_registry",
    "guarded_force_term_registry",
]
