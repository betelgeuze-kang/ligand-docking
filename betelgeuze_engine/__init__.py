"""Product engine scaffold for AI-MD topology, physics, and evidence modules."""

from importlib import import_module as _import_module

# Keep package-level compatibility without loading molecular physics for adapters
# that only need metadata. Each value remains the original defining module object.
_EXPORT_MODULES = {
    "EnergyForces": "contracts.result",
    "TermResult": "contracts.result",
    "EngineState": "contracts.state",
    "ProductForceField": "physics.forcefield",
    "ForceTermRegistry": "physics.forcefield",
    "default_force_term_registry": "physics.forcefield",
    "guarded_force_term_registry": "physics.forcefield",
    "ForceResidualDecision": "residual.guarded_force",
    "ForceResidualPolicy": "residual.guarded_force",
    "ForceResidualReport": "residual.guarded_force",
}

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


def __getattr__(name):
    module_name = _EXPORT_MODULES.get(name)
    if module_name == "contracts.result":
        module = _import_module("betelgeuze_engine.contracts.result")
    elif module_name == "contracts.state":
        module = _import_module("betelgeuze_engine.contracts.state")
    elif module_name == "physics.forcefield":
        module = _import_module("betelgeuze_engine.physics.forcefield")
    elif module_name == "residual.guarded_force":
        module = _import_module("betelgeuze_engine.residual.guarded_force")
    else:
        module = None
    if module is not None:
        value = getattr(module, name)
        globals()[name] = value
        return value
    if name == "contracts":
        return _import_module("betelgeuze_engine.contracts")
    if name == "physics":
        return _import_module("betelgeuze_engine.physics")
    if name == "residual":
        return _import_module("betelgeuze_engine.residual")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__) | {"contracts", "physics", "residual"})
