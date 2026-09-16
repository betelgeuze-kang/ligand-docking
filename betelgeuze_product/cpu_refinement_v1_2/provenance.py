"""Canonical, bounded data and installed-source identities for research 1.2."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import platform
from typing import Mapping

import torch


class ResearchError(ValueError):
    """An explicit research contract is invalid; no fallback is authorized."""


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("ascii")).hexdigest()


def require_digest(value: object) -> str:
    if (type(value) is not str or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)):
        raise ResearchError("canonical SHA-256 required")
    return value


def integer(value: object, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ResearchError(f"exact integer in [{low},{high}] required")
    return value


def finite(value: object, *, nonnegative: bool = False) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ResearchError("finite numeric value required")
    if nonnegative and value < 0:
        raise ResearchError("nonnegative value required")
    return float(value)


def exact_fields(value: object, names: set[str]) -> Mapping:
    if not isinstance(value, Mapping) or set(value) != names:
        raise ResearchError("document fields are not canonical")
    return value


def coordinates_hex(coordinates: torch.Tensor) -> list[list[str]]:
    return [[float(v).hex() for v in row]
            for row in coordinates.detach().reshape(-1, 3).tolist()]


def decode_coordinates(value: object, atom_count: int) -> torch.Tensor:
    integer(atom_count, 1, 256)
    if type(value) is not list or len(value) != atom_count:
        raise ResearchError("coordinate atom count mismatch")
    parsed = []
    for row in value:
        if type(row) is not list or len(row) != 3:
            raise ResearchError("coordinate row must have three components")
        values = []
        for item in row:
            if type(item) is not str or len(item) > 32:
                raise ResearchError("canonical binary64 hexadecimal coordinate required")
            try:
                number = float.fromhex(item)
            except ValueError as exc:
                raise ResearchError("invalid hexadecimal coordinate") from exc
            if not math.isfinite(number) or number.hex() != item:
                raise ResearchError("noncanonical or nonfinite coordinate")
            values.append(number)
        parsed.append(values)
    return torch.tensor([parsed], dtype=torch.float64)


def source_manifest() -> dict[str, str]:
    import betelgeuze_engine_v2
    engine = Path(betelgeuze_engine_v2.__file__).resolve().parent
    product = Path(__file__).resolve().parents[1]
    roots = (("betelgeuze_engine_v2", engine),
             ("betelgeuze_product/cpu_refinement", product / "cpu_refinement"),
             ("betelgeuze_product/cpu_refinement_v1_2", Path(__file__).resolve().parent))
    paths = {f"{prefix}/{p.relative_to(root).as_posix()}": p
             for prefix, root in roots for p in sorted(root.rglob("*.py"))}
    for name in ("__init__.py", "local_research_workflow.py",
                 "reference_minimization_workflow.py", "refinement_comparison_workflow.py"):
        paths[f"betelgeuze_product/{name}"] = product / name
    return {name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in sorted(paths.items())}


def environment() -> dict[str, object]:
    return {"python": platform.python_version(), "torch": str(torch.__version__),
            "platform": platform.platform(), "torch_threads": torch.get_num_threads(),
            "torch_interop_threads": torch.get_num_interop_threads(),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled()}
