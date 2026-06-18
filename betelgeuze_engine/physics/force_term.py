from __future__ import annotations

from typing import Protocol

from betelgeuze_engine.contracts.result import TermResult
from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_engine.physics.neighbor import NeighborPairs


class ForceTerm(Protocol):
    name: str

    def energy_forces(self, state: EngineState, pairs: NeighborPairs | None = None) -> TermResult:
        ...
