"""Authenticated raw-input boundary for offline public redocking evaluation.

The lower-level evaluator accepts already prepared canonical systems and
validity inputs. This module is the public entrypoint: it accepts only byte
artifacts already named by a successful materialization receipt, recomputes all
artifact identities, parses the receptor/reference/seed/candidate locally, and
derives the pocket, topology exclusions, and chirality declarations from those
authenticated structures.

The derivation policy is intentionally bounded and deterministic. It is not a
scientific pocket-prediction method and grants no benchmark, product, customer,
or claim promotion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from types import MappingProxyType
from typing import Mapping, Sequence

import torch

from betelgeuze_engine_v2.io import parse_pdb, parse_sdf_v2000
from betelgeuze_engine_v2.molecular import AllAtomSystem, canonical_system_sha256

from .public_evaluator import (
    PublicBenchmarkEvaluationCaseInput,
    PublicBenchmarkEvaluationError,
    PublicBenchmarkEvaluationReport,
    run_offline_public_benchmark_evaluation as _run_prepared_evaluation,
)
from .public_materializer import (
    PUBLIC_BENCHMARK_MAX_SDF_BYTES,
    PublicBenchmarkCaseMaterialization,
    PublicBenchmarkMaterializationManifest,
    exact_graph_isomorphisms,
    split_sdf_v2000_records,
)


AUTHENTICATED_PUBLIC_BENCHMARK_CASE_INPUT_SCHEMA_ID = (
    "betelgeuze.engine_v2_authenticated_public_benchmark_case_input/1.0.0"
)
AUTHENTICATED_PUBLIC_BENCHMARK_DERIVATION_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_authenticated_public_benchmark_derivation_policy/1.0.0"
)
AUTHENTICATED_PUBLIC_BENCHMARK_POCKET_MARGIN_ANGSTROM = 6.0
AUTHENTICATED_PUBLIC_BENCHMARK_MINIMUM_POCKET_RADIUS_ANGSTROM = 4.0
AUTHENTICATED_PUBLIC_BENCHMARK_MAXIMUM_POCKET_RADIUS_ANGSTROM = 20.0
AUTHENTICATED_PUBLIC_BENCHMARK_MAX_RECEPTOR_BYTES = 16 * 1024 * 1024
AUTHENTICATED_PUBLIC_BENCHMARK_MAX_CANDIDATE_BYTES = 16 * 1024 * 1024


class AuthenticatedPublicBenchmarkInputError(PublicBenchmarkEvaluationError):
    """Raw evaluator inputs are missing, tampered, ambiguous, or unsupported."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise AuthenticatedPublicBenchmarkInputError(
            "authenticated evaluator input is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _bounded_bytes(value: object, *, name: str, maximum: int) -> bytes:
    if not isinstance(value, bytes) or not value or len(value) > maximum:
        raise AuthenticatedPublicBenchmarkInputError(
            f"{name} must be bounded non-empty bytes"
        )
    return value


def _require_digest(payload: bytes, expected: str, *, name: str) -> str:
    observed = hashlib.sha256(payload).hexdigest()
    if observed != expected:
        raise AuthenticatedPublicBenchmarkInputError(
            f"{name} SHA-256 does not match the materialization receipt"
        )
    return observed


def _single_sdf_system(payload: bytes, *, source_id: str) -> AllAtomSystem:
    records = split_sdf_v2000_records(payload)
    if len(records) != 1:
        raise AuthenticatedPublicBenchmarkInputError(
            "candidate and ligand-seed SDF inputs must contain exactly one record"
        )
    try:
        return parse_sdf_v2000(records[0].decode("ascii"), source_id=source_id)
    except (UnicodeDecodeError, ValueError) as exc:
        raise AuthenticatedPublicBenchmarkInputError(
            "SDF input is outside the strict supported subset"
        ) from exc


def _selected_reference_system(
    materialization: PublicBenchmarkCaseMaterialization,
    payload: bytes,
) -> AllAtomSystem:
    records = split_sdf_v2000_records(payload)
    index = materialization.selected_reference_record_index
    if index >= len(records):
        raise AuthenticatedPublicBenchmarkInputError(
            "selected reference record index is outside the authenticated SDF"
        )
    record = records[index]
    _require_digest(
        record,
        materialization.selected_reference_record_sha256,
        name="selected reference record",
    )
    try:
        return parse_sdf_v2000(
            record.decode("ascii"),
            source_id=f"{materialization.case_id}:reference:{index}",
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise AuthenticatedPublicBenchmarkInputError(
            "selected reference record is outside the strict supported subset"
        ) from exc


def _heavy_indices(system: AllAtomSystem) -> tuple[int, ...]:
    indices = tuple(
        index
        for index, atom in enumerate(system.atoms)
        if atom.element.upper() != "H"
    )
    if not indices:
        raise AuthenticatedPublicBenchmarkInputError(
            "reference ligand contains no heavy atoms"
        )
    return indices


def _derive_pocket(
    reference_system: AllAtomSystem,
) -> tuple[torch.Tensor, float]:
    coordinates = (
        reference_system.coordinates[0]
        .detach()
        .to(dtype=torch.float64, device="cpu")
    )
    heavy = coordinates[
        torch.tensor(_heavy_indices(reference_system), dtype=torch.long)
    ]
    center = heavy.mean(dim=0).contiguous().requires_grad_(False)
    maximum_distance = float(
        torch.linalg.vector_norm(heavy - center, dim=-1).max().item()
    )
    radius = max(
        AUTHENTICATED_PUBLIC_BENCHMARK_MINIMUM_POCKET_RADIUS_ANGSTROM,
        maximum_distance + AUTHENTICATED_PUBLIC_BENCHMARK_POCKET_MARGIN_ANGSTROM,
    )
    radius = min(
        radius, AUTHENTICATED_PUBLIC_BENCHMARK_MAXIMUM_POCKET_RADIUS_ANGSTROM
    )
    if not math.isfinite(radius) or radius <= 0.0:
        raise AuthenticatedPublicBenchmarkInputError(
            "derived pocket radius is invalid"
        )
    return center, radius


def _bond_pairs(system: AllAtomSystem) -> tuple[tuple[int, int], ...]:
    return tuple(
        sorted(
            {
                tuple(sorted((int(bond.atom_i), int(bond.atom_j))))
                for bond in system.bonds
            }
        )
    )


def _derive_nonbonded_exclusions(
    system: AllAtomSystem,
) -> tuple[tuple[int, int], ...]:
    adjacency: dict[int, set[int]] = {
        index: set() for index in range(system.atom_count)
    }
    for first, second in _bond_pairs(system):
        adjacency[first].add(second)
        adjacency[second].add(first)
    exclusions: set[tuple[int, int]] = set(_bond_pairs(system))
    for center, neighbors in adjacency.items():
        for first in neighbors:
            for second in adjacency[first]:
                if second != center:
                    exclusions.add(tuple(sorted((center, second))))
    return tuple(sorted(exclusions))


def _reference_coordinates_in_seed_order(
    reference_system: AllAtomSystem,
    seed_system: AllAtomSystem,
) -> torch.Tensor:
    mappings = exact_graph_isomorphisms(reference_system, seed_system)
    if not mappings:
        raise AuthenticatedPublicBenchmarkInputError(
            "reference and ligand seed are not exact labeled-graph isomorphs"
        )
    mapping = mappings[0]
    reference = (
        reference_system.coordinates[0]
        .detach()
        .to(dtype=torch.float64, device="cpu")
    )
    ordered = torch.empty(
        (seed_system.atom_count, 3), dtype=torch.float64, device="cpu"
    )
    if len(mapping) != reference_system.atom_count:
        raise AuthenticatedPublicBenchmarkInputError(
            "reference-to-seed graph mapping has an invalid atom count"
        )
    for reference_index, seed_index in enumerate(mapping):
        ordered[int(seed_index)] = reference[reference_index]
    return ordered.contiguous().requires_grad_(False)


def _signed_volume(
    coordinates: torch.Tensor,
    center: int,
    first: int,
    second: int,
    third: int,
) -> float:
    origin = coordinates[center]
    return float(
        torch.dot(
            torch.cross(
                coordinates[first] - origin,
                coordinates[second] - origin,
                dim=0,
            ),
            coordinates[third] - origin,
        ).item()
    )


def _derive_chirality_centers(
    system: AllAtomSystem,
    authenticated_reference_coordinates: torch.Tensor,
) -> tuple[tuple[int, int, int, int], ...]:
    if authenticated_reference_coordinates.shape != (system.atom_count, 3):
        raise AuthenticatedPublicBenchmarkInputError(
            "authenticated reference coordinates have an invalid shape"
        )
    adjacency: dict[int, list[int]] = {
        index: [] for index in range(system.atom_count)
    }
    for first, second in _bond_pairs(system):
        adjacency[first].append(second)
        adjacency[second].append(first)
    rows: list[tuple[int, int, int, int]] = []
    for center, neighbors in sorted(adjacency.items()):
        ordered = tuple(sorted(neighbors))
        if len(ordered) != 4:
            continue
        first, second, third = ordered[:3]
        if (
            abs(
                _signed_volume(
                    authenticated_reference_coordinates,
                    center,
                    first,
                    second,
                    third,
                )
            )
            <= 1.0e-8
        ):
            continue
        rows.append((center, first, second, third))
    return tuple(rows)


def authenticated_public_benchmark_derivation_policy_document() -> dict[str, object]:
    projection: dict[str, object] = {
        "schema_id": AUTHENTICATED_PUBLIC_BENCHMARK_DERIVATION_POLICY_SCHEMA_ID,
        "receptor_parser": "betelgeuze_engine_v2.strict_pdb/1.0.0",
        "ligand_parser": "betelgeuze_engine_v2.strict_sdf_v2000/1.0.0",
        "candidate_sha256_recomputed": True,
        "receptor_sha256_recomputed": True,
        "reference_sha256_recomputed": True,
        "ligand_seed_sha256_recomputed": True,
        "receptor_coordinates_derived_from_authenticated_bytes": True,
        "pocket_center": "authenticated_reference_heavy_atom_centroid",
        "pocket_margin_angstrom": (
            AUTHENTICATED_PUBLIC_BENCHMARK_POCKET_MARGIN_ANGSTROM
        ),
        "minimum_pocket_radius_angstrom": (
            AUTHENTICATED_PUBLIC_BENCHMARK_MINIMUM_POCKET_RADIUS_ANGSTROM
        ),
        "maximum_pocket_radius_angstrom": (
            AUTHENTICATED_PUBLIC_BENCHMARK_MAXIMUM_POCKET_RADIUS_ANGSTROM
        ),
        "nonbonded_exclusions": "ligand_graph_distance_at_most_two",
        "chirality_centers": (
            "degree_four_seed_graph_with_nondegenerate_authenticated_"
            "reference_signed_volume"
        ),
        "ligand_identity_seed_coordinates_used": False,
        "caller_supplied_receptor_coordinates_allowed": False,
        "caller_supplied_pocket_allowed": False,
        "caller_supplied_exclusions_allowed": False,
        "caller_supplied_chirality_allowed": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    projection["policy_sha256"] = _sha256(projection)
    return projection


@dataclass(frozen=True, slots=True)
class AuthenticatedPublicBenchmarkCaseInput:
    case_id: str
    materialization: PublicBenchmarkCaseMaterialization
    receptor_bytes: bytes
    reference_ligands_bytes: bytes
    ligand_identity_seed_bytes: bytes
    candidate_bytes: bytes
    _prepared: PublicBenchmarkEvaluationCaseInput = field(init=False, repr=False)
    _input_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.materialization, PublicBenchmarkCaseMaterialization
        ):
            raise TypeError(
                "materialization must be PublicBenchmarkCaseMaterialization"
            )
        if self.case_id != self.materialization.case_id:
            raise AuthenticatedPublicBenchmarkInputError(
                "raw evaluation case is cross-wired to another materialization"
            )
        receptor_raw = _bounded_bytes(
            self.receptor_bytes,
            name="receptor bytes",
            maximum=AUTHENTICATED_PUBLIC_BENCHMARK_MAX_RECEPTOR_BYTES,
        )
        reference_raw = _bounded_bytes(
            self.reference_ligands_bytes,
            name="reference ligand bytes",
            maximum=PUBLIC_BENCHMARK_MAX_SDF_BYTES,
        )
        seed_raw = _bounded_bytes(
            self.ligand_identity_seed_bytes,
            name="ligand seed bytes",
            maximum=PUBLIC_BENCHMARK_MAX_SDF_BYTES,
        )
        candidate_raw = _bounded_bytes(
            self.candidate_bytes,
            name="candidate bytes",
            maximum=AUTHENTICATED_PUBLIC_BENCHMARK_MAX_CANDIDATE_BYTES,
        )
        receptor_sha256 = _require_digest(
            receptor_raw,
            self.materialization.receptor_sha256,
            name="receptor artifact",
        )
        _require_digest(
            reference_raw,
            self.materialization.reference_ligands_sha256,
            name="reference artifact",
        )
        _require_digest(
            seed_raw,
            self.materialization.ligand_identity_seed_sha256,
            name="ligand seed artifact",
        )
        candidate_sha256 = hashlib.sha256(candidate_raw).hexdigest()
        try:
            receptor_system = parse_pdb(
                receptor_raw,
                source_id=f"{self.case_id}:receptor",
                dtype=torch.float64,
                device="cpu",
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise AuthenticatedPublicBenchmarkInputError(
                "receptor artifact is outside the strict supported PDB subset"
            ) from exc
        reference_system = _selected_reference_system(
            self.materialization,
            reference_raw,
        )
        seed_system = _single_sdf_system(
            seed_raw,
            source_id=f"{self.case_id}:ligand-identity-seed",
        )
        candidate_system = _single_sdf_system(
            candidate_raw,
            source_id=f"{self.case_id}:candidate",
        )
        reference_in_seed_order = _reference_coordinates_in_seed_order(
            reference_system,
            seed_system,
        )
        pocket_center, pocket_radius = _derive_pocket(reference_system)
        prepared = PublicBenchmarkEvaluationCaseInput(
            case_id=self.case_id,
            materialization=self.materialization,
            receptor_artifact_sha256=receptor_sha256,
            reference_artifact_sha256=(
                self.materialization.reference_ligands_sha256
            ),
            ligand_identity_seed_artifact_sha256=(
                self.materialization.ligand_identity_seed_sha256
            ),
            candidate_artifact_sha256=candidate_sha256,
            receptor_system_sha256=canonical_system_sha256(receptor_system),
            reference_system=reference_system,
            ligand_identity_seed_system=seed_system,
            candidate_system=candidate_system,
            receptor_coordinates=(
                receptor_system.coordinates[0]
                .detach()
                .to(dtype=torch.float64, device="cpu")
                .clone()
                .contiguous()
            ),
            pocket_center=pocket_center,
            pocket_radius_angstrom=pocket_radius,
            excluded_nonbonded_pairs=_derive_nonbonded_exclusions(seed_system),
            chirality_centers=_derive_chirality_centers(
                seed_system,
                reference_in_seed_order,
            ),
        )
        projection = {
            "schema_id": AUTHENTICATED_PUBLIC_BENCHMARK_CASE_INPUT_SCHEMA_ID,
            "case_id": self.case_id,
            "materialization_sha256": (
                self.materialization.materialization_sha256
            ),
            "receptor_sha256": receptor_sha256,
            "reference_ligands_sha256": hashlib.sha256(reference_raw).hexdigest(),
            "ligand_identity_seed_sha256": hashlib.sha256(seed_raw).hexdigest(),
            "candidate_sha256": candidate_sha256,
            "receptor_system_sha256": canonical_system_sha256(receptor_system),
            "candidate_system_sha256": canonical_system_sha256(candidate_system),
            "derivation_policy_sha256": (
                authenticated_public_benchmark_derivation_policy_document()[
                    "policy_sha256"
                ]
            ),
            "caller_controlled_validity_inputs": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }
        object.__setattr__(self, "receptor_bytes", receptor_raw)
        object.__setattr__(self, "reference_ligands_bytes", reference_raw)
        object.__setattr__(self, "ligand_identity_seed_bytes", seed_raw)
        object.__setattr__(self, "candidate_bytes", candidate_raw)
        object.__setattr__(self, "_prepared", prepared)
        object.__setattr__(self, "_input_sha256", _sha256(projection))

    @property
    def prepared_input(self) -> PublicBenchmarkEvaluationCaseInput:
        return self._prepared

    @property
    def input_sha256(self) -> str:
        return self._input_sha256

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": AUTHENTICATED_PUBLIC_BENCHMARK_CASE_INPUT_SCHEMA_ID,
            "case_id": self.case_id,
            "materialization_sha256": (
                self.materialization.materialization_sha256
            ),
            "receptor_sha256": hashlib.sha256(self.receptor_bytes).hexdigest(),
            "reference_ligands_sha256": hashlib.sha256(
                self.reference_ligands_bytes
            ).hexdigest(),
            "ligand_identity_seed_sha256": hashlib.sha256(
                self.ligand_identity_seed_bytes
            ).hexdigest(),
            "candidate_sha256": hashlib.sha256(self.candidate_bytes).hexdigest(),
            "derivation_policy_sha256": (
                authenticated_public_benchmark_derivation_policy_document()[
                    "policy_sha256"
                ]
            ),
            "input_sha256": self.input_sha256,
            "caller_controlled_validity_inputs": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }


def run_authenticated_offline_public_benchmark_evaluation(
    materialization_manifest: PublicBenchmarkMaterializationManifest,
    case_inputs: Mapping[str, AuthenticatedPublicBenchmarkCaseInput],
    *,
    engine_commit: str,
    environment_fingerprint_sha256: str,
    command: Sequence[str],
    seed: int,
) -> PublicBenchmarkEvaluationReport:
    if not isinstance(case_inputs, Mapping):
        raise TypeError("case_inputs must be a mapping")
    prepared: dict[str, PublicBenchmarkEvaluationCaseInput] = {}
    for case_id, row in case_inputs.items():
        if not isinstance(case_id, str) or not isinstance(
            row, AuthenticatedPublicBenchmarkCaseInput
        ):
            raise AuthenticatedPublicBenchmarkInputError(
                "authenticated evaluator inputs are invalid"
            )
        if case_id != row.case_id:
            raise AuthenticatedPublicBenchmarkInputError(
                "authenticated evaluator input key is cross-wired"
            )
        prepared[case_id] = row.prepared_input
    return _run_prepared_evaluation(
        materialization_manifest,
        MappingProxyType(prepared),
        engine_commit=engine_commit,
        environment_fingerprint_sha256=environment_fingerprint_sha256,
        command=command,
        seed=seed,
    )


__all__ = [
    "AUTHENTICATED_PUBLIC_BENCHMARK_CASE_INPUT_SCHEMA_ID",
    "AUTHENTICATED_PUBLIC_BENCHMARK_DERIVATION_POLICY_SCHEMA_ID",
    "AuthenticatedPublicBenchmarkCaseInput",
    "AuthenticatedPublicBenchmarkInputError",
    "authenticated_public_benchmark_derivation_policy_document",
    "run_authenticated_offline_public_benchmark_evaluation",
]
