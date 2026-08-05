"""Self-contained evidence for deterministic global-orientation generation."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Iterable, Sequence

from .global_orientation import (
    GLOBAL_ORIENTATION_GENERATOR_ID,
    GlobalOrientationBatch,
    GlobalOrientationConfig,
    GlobalOrientationError,
    generate_global_orientation_batch,
)


GLOBAL_ORIENTATION_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_evidence/1.0.0"
)

Vector3 = tuple[float, float, float]
Coordinates = tuple[Vector3, ...]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _vector(value: Sequence[float], *, name: str) -> Vector3:
    if len(value) != 3:
        raise GlobalOrientationError(f"{name} must contain exactly three values")
    observed = tuple(float(component) for component in value)
    if any(not math.isfinite(component) for component in observed):
        raise GlobalOrientationError(f"{name} must contain finite values")
    return observed  # type: ignore[return-value]


def _coordinates(
    value: Iterable[Sequence[float]],
    *,
    name: str,
) -> Coordinates:
    observed = tuple(
        _vector(point, name=f"{name}[{index}]")
        for index, point in enumerate(value)
    )
    if not observed:
        raise GlobalOrientationError(f"{name} must not be empty")
    return observed


def _coordinates_projection(value: Coordinates) -> list[list[str]]:
    return [[component.hex() for component in point] for point in value]


@dataclass(frozen=True, slots=True)
class GlobalOrientationEvidence:
    """Bind source geometry to a fully rederived proposal batch."""

    ligand_coordinates: Coordinates
    pocket_center: Vector3
    pocket_normal: Vector3
    receptor_surface_points: Coordinates
    config: GlobalOrientationConfig
    batch: GlobalOrientationBatch
    schema_id: str = GLOBAL_ORIENTATION_EVIDENCE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != GLOBAL_ORIENTATION_EVIDENCE_SCHEMA_ID:
            raise GlobalOrientationError("global-orientation evidence schema is invalid")
        ligand = _coordinates(self.ligand_coordinates, name="ligand_coordinates")
        center = _vector(self.pocket_center, name="pocket_center")
        normal = _vector(self.pocket_normal, name="pocket_normal")
        receptor = tuple(
            _vector(point, name=f"receptor_surface_points[{index}]")
            for index, point in enumerate(self.receptor_surface_points)
        )
        if type(self.config) is not GlobalOrientationConfig:
            raise TypeError("config must be the exact GlobalOrientationConfig type")
        if type(self.batch) is not GlobalOrientationBatch:
            raise TypeError("batch must be the exact GlobalOrientationBatch type")
        expected = generate_global_orientation_batch(
            ligand,
            pocket_center=center,
            pocket_normal=normal,
            receptor_surface_points=receptor,
            config=self.config,
        )
        if self.batch.to_dict() != expected.to_dict():
            raise GlobalOrientationError(
                "global-orientation batch does not equal source rederivation"
            )
        object.__setattr__(self, "ligand_coordinates", ligand)
        object.__setattr__(self, "pocket_center", center)
        object.__setattr__(self, "pocket_normal", normal)
        object.__setattr__(self, "receptor_surface_points", receptor)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "generator_id": GLOBAL_ORIENTATION_GENERATOR_ID,
            "ligand_coordinates_binary64_hex": _coordinates_projection(
                self.ligand_coordinates
            ),
            "pocket_center_binary64_hex": [
                component.hex() for component in self.pocket_center
            ],
            "pocket_normal_binary64_hex": [
                component.hex() for component in self.pocket_normal
            ],
            "receptor_surface_points_binary64_hex": _coordinates_projection(
                self.receptor_surface_points
            ),
            "config": self.config.to_dict(),
            "batch": self.batch.to_dict(),
            "source_rederivation_verified": True,
            "native_pose_input_consumed": False,
            "score_input_consumed": False,
            "fresh_holdout_input_consumed": False,
            "product_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationError("global-orientation evidence changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def build_global_orientation_evidence(
    ligand_coordinates: Iterable[Sequence[float]],
    *,
    pocket_center: Sequence[float],
    pocket_normal: Sequence[float],
    receptor_surface_points: Iterable[Sequence[float]] = (),
    config: GlobalOrientationConfig | None = None,
) -> GlobalOrientationEvidence:
    active_config = config or GlobalOrientationConfig()
    ligand = _coordinates(ligand_coordinates, name="ligand_coordinates")
    center = _vector(pocket_center, name="pocket_center")
    normal = _vector(pocket_normal, name="pocket_normal")
    receptor = tuple(
        _vector(point, name=f"receptor_surface_points[{index}]")
        for index, point in enumerate(receptor_surface_points)
    )
    batch = generate_global_orientation_batch(
        ligand,
        pocket_center=center,
        pocket_normal=normal,
        receptor_surface_points=receptor,
        config=active_config,
    )
    return GlobalOrientationEvidence(
        ligand_coordinates=ligand,
        pocket_center=center,
        pocket_normal=normal,
        receptor_surface_points=receptor,
        config=active_config,
        batch=batch,
    )


__all__ = [
    "GLOBAL_ORIENTATION_EVIDENCE_SCHEMA_ID",
    "GlobalOrientationEvidence",
    "build_global_orientation_evidence",
]
