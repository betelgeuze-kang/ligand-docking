"""Leakage-controlled reference-pose materialization for public redocking.

The materializer consumes caller-supplied bytes that are already bound by a
``PublicBenchmarkCaseDefinition``.  It never fetches data.  Ligand identity is
decided from labeled V2000 molecular graphs only; coordinates from the ligand
identity seed are never read by the matching or symmetry algorithms.  Every
reference record is retained as a selected, graph-mismatch, or failure row.

Matched reference coordinates remain in the receptor frame.  The companion
RMSD helper therefore performs no ligand-only alignment and takes the minimum
over every graph-matched reference record and every stereo-preserving graph
automorphism admitted by the bounded search.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Integral
from typing import Mapping

import torch

from betelgeuze_engine_v2.io.sdf import (
    SDFParseError,
    SDFParserLimits,
    parse_sdf_v2000,
)
from betelgeuze_engine_v2.molecular import AllAtomSystem

from .public_protocol import (
    PublicBenchmarkCaseDefinition,
    PublicBenchmarkProtocolError,
    frozen_public_benchmark_protocol,
)


PUBLIC_REFERENCE_MATERIALIZATION_ALGORITHM_ID = (
    "verified_v2000_labeled_graph_all_reference_match_stereo_automorphism/1.0.0"
)
PUBLIC_REFERENCE_MATERIALIZATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_reference_materialization/1.0.0"
)
PUBLIC_REFERENCE_RECORD_ROW_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_reference_record_row/1.0.0"
)
PUBLIC_REFERENCE_POSE_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_reference_pose/1.0.0"
)
PUBLIC_REFERENCE_RMSD_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_reference_rmsd_result/1.0.0"
)

MAX_PUBLIC_REFERENCE_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_PUBLIC_REFERENCE_RECORD_BYTES = 4 * 1024 * 1024
MAX_PUBLIC_REFERENCE_RECORDS = 64
MAX_PUBLIC_REFERENCE_ATOMS = 256
MAX_PUBLIC_REFERENCE_BONDS = 1_024
MAX_PUBLIC_REFERENCE_SYMMETRY_PERMUTATIONS = 1_024
MAX_PUBLIC_REFERENCE_GRAPH_SEARCH_STATES = 2_000_000
MAX_PUBLIC_REFERENCE_RECEIPT_BYTES = 16 * 1024 * 1024

PUBLIC_REFERENCE_MATERIALIZATION_SCIENTIFIC_BLOCKERS = (
    "four_case_contract_cohort_not_statistically_representative",
    "posebusters_benchmark_equivalence_not_established",
    "v2000_labeled_graph_identity_not_independent_chemical_standardization",
    "atom_stereo_parity_beyond_directional_v2000_bonds_not_interpreted",
    "public_benchmark_not_executed",
    "public_holdout_results_missing",
    "independent_attestation_missing",
    "legal_compliance_determination_not_made",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)

_RECORD_STATUSES = frozenset(
    {
        "selected_graph_match",
        "rejected_graph_mismatch",
        "failure_parse",
        "failure_graph_search",
    }
)
_FAILURE_STATUSES = frozenset({"failure_parse", "failure_graph_search"})
_STEREO_CODE_BY_NAME = {"none": 0, "up": 1, "either": 4, "down": 6}


class PublicReferenceMaterializationError(ValueError):
    """Public reference materialization failed its bounded input contract."""


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise PublicReferenceMaterializationError(f"{name} must be an integer")
    result = int(value)
    if result < minimum or (maximum is not None and result > maximum):
        upper = "" if maximum is None else f" and at most {maximum}"
        raise PublicReferenceMaterializationError(
            f"{name} must be at least {minimum}{upper}"
        )
    return result


def _digest(value: object, *, name: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise PublicReferenceMaterializationError(f"{name} must be a SHA-256")
    result = value.strip().lower()
    if allow_empty and not result:
        return ""
    if len(result) != 64 or any(character not in "0123456789abcdef" for character in result):
        raise PublicReferenceMaterializationError(
            f"{name} must be a lowercase SHA-256"
        )
    return result


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise PublicReferenceMaterializationError(
            "public reference payload is not canonical JSON"
        ) from exc


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _tensor_hex_rows(value: torch.Tensor) -> list[list[str]]:
    return [
        [float(component).hex() for component in row]
        for row in value.detach().cpu().tolist()
    ]


def _tensor_from_hex_rows(value: object, *, name: str) -> torch.Tensor:
    if not isinstance(value, list) or not value:
        raise PublicReferenceMaterializationError(
            f"{name} must be a non-empty coordinate list"
        )
    rows: list[list[float]] = []
    for row_index, row in enumerate(value):
        if not isinstance(row, list) or len(row) != 3:
            raise PublicReferenceMaterializationError(
                f"{name}[{row_index}] must contain three hexadecimal floats"
            )
        parsed: list[float] = []
        for column_index, component in enumerate(row):
            if not isinstance(component, str):
                raise PublicReferenceMaterializationError(
                    f"{name}[{row_index}][{column_index}] must be hexadecimal"
                )
            try:
                number = float.fromhex(component)
            except ValueError as exc:
                raise PublicReferenceMaterializationError(
                    f"{name}[{row_index}][{column_index}] is invalid"
                ) from exc
            if not math.isfinite(number) or number.hex() != component:
                raise PublicReferenceMaterializationError(
                    f"{name}[{row_index}][{column_index}] is not canonical binary64"
                )
            parsed.append(number)
        rows.append(parsed)
    return torch.tensor(rows, dtype=torch.float64, device="cpu")


@dataclass(frozen=True, slots=True)
class PublicReferenceMaterializationLimits:
    max_artifact_bytes: int = MAX_PUBLIC_REFERENCE_ARTIFACT_BYTES
    max_record_bytes: int = MAX_PUBLIC_REFERENCE_RECORD_BYTES
    max_records: int = MAX_PUBLIC_REFERENCE_RECORDS
    max_atoms: int = MAX_PUBLIC_REFERENCE_ATOMS
    max_bonds: int = MAX_PUBLIC_REFERENCE_BONDS
    max_symmetry_permutations: int = MAX_PUBLIC_REFERENCE_SYMMETRY_PERMUTATIONS
    max_graph_search_states: int = MAX_PUBLIC_REFERENCE_GRAPH_SEARCH_STATES

    def __post_init__(self) -> None:
        for name, hard_maximum in (
            ("max_artifact_bytes", MAX_PUBLIC_REFERENCE_ARTIFACT_BYTES),
            ("max_record_bytes", MAX_PUBLIC_REFERENCE_RECORD_BYTES),
            ("max_records", MAX_PUBLIC_REFERENCE_RECORDS),
            ("max_atoms", MAX_PUBLIC_REFERENCE_ATOMS),
            ("max_bonds", MAX_PUBLIC_REFERENCE_BONDS),
            (
                "max_symmetry_permutations",
                MAX_PUBLIC_REFERENCE_SYMMETRY_PERMUTATIONS,
            ),
            ("max_graph_search_states", MAX_PUBLIC_REFERENCE_GRAPH_SEARCH_STATES),
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(
                    getattr(self, name),
                    name=name,
                    minimum=1,
                    maximum=hard_maximum,
                ),
            )
        if self.max_record_bytes > self.max_artifact_bytes:
            raise PublicReferenceMaterializationError(
                "max_record_bytes cannot exceed max_artifact_bytes"
            )

    def to_dict(self) -> dict[str, int]:
        return {
            "max_artifact_bytes": self.max_artifact_bytes,
            "max_record_bytes": self.max_record_bytes,
            "max_records": self.max_records,
            "max_atoms": self.max_atoms,
            "max_bonds": self.max_bonds,
            "max_symmetry_permutations": self.max_symmetry_permutations,
            "max_graph_search_states": self.max_graph_search_states,
        }

    @classmethod
    def from_dict(cls, value: object) -> "PublicReferenceMaterializationLimits":
        expected = {
            "max_artifact_bytes",
            "max_record_bytes",
            "max_records",
            "max_atoms",
            "max_bonds",
            "max_symmetry_permutations",
            "max_graph_search_states",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise PublicReferenceMaterializationError(
                "public reference limits payload is invalid"
            )
        result = cls(**{name: value[name] for name in expected})
        if result.to_dict() != dict(value):
            raise PublicReferenceMaterializationError(
                "public reference limits payload is not canonical"
            )
        return result

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class _SDFRecord:
    index: int
    raw_bytes: bytes
    molblock_bytes: bytes
    source_title: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.raw_bytes).hexdigest()


def _sdf_record(
    index: int,
    raw: bytes,
    *,
    limits: PublicReferenceMaterializationLimits,
) -> _SDFRecord:
    if len(raw) < 1 or len(raw) > limits.max_record_bytes:
        raise PublicReferenceMaterializationError(
            "SDF record byte length is outside the configured bound"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PublicReferenceMaterializationError(
            "public reference SDF must be UTF-8"
        ) from exc
    lines = text.splitlines(keepends=True)
    end_rows = [
        row_index
        for row_index, line in enumerate(lines)
        if line.strip() == "M  END"
    ]
    if len(end_rows) == 1:
        molblock = "".join(lines[: end_rows[0] + 1])
        if not molblock.endswith(("\n", "\r")):
            molblock += "\n"
    else:
        # Keep the record addressable so the strict parser can emit a retained
        # failure row for missing or duplicate terminators.
        molblock = text
    title = lines[0].rstrip("\r\n") if lines else ""
    return _SDFRecord(
        index=index,
        raw_bytes=raw,
        molblock_bytes=molblock.encode("utf-8"),
        source_title=title,
    )


def _split_sdf_records(
    source: bytes,
    *,
    limits: PublicReferenceMaterializationLimits,
) -> tuple[_SDFRecord, ...]:
    if not isinstance(source, bytes):
        raise TypeError("public reference SDF source must be bytes")
    if len(source) < 1 or len(source) > limits.max_artifact_bytes:
        raise PublicReferenceMaterializationError(
            "public reference SDF artifact size is outside the configured bound"
        )
    records: list[_SDFRecord] = []
    current: list[bytes] = []
    for line in source.splitlines(keepends=True):
        if line.strip() == b"$$$$":
            raw = b"".join(current)
            if not raw.strip():
                raise PublicReferenceMaterializationError(
                    "public reference SDF contains an empty record"
                )
            records.append(_sdf_record(len(records), raw, limits=limits))
            current = []
            if len(records) > limits.max_records:
                raise PublicReferenceMaterializationError(
                    "public reference SDF record count exceeds the configured bound"
                )
        else:
            current.append(line)
    trailing = b"".join(current)
    if trailing.strip():
        records.append(_sdf_record(len(records), trailing, limits=limits))
    if not records or len(records) > limits.max_records:
        raise PublicReferenceMaterializationError(
            "public reference SDF record count is outside the configured bound"
        )
    return tuple(records)


def _parse_record(
    record: _SDFRecord,
    *,
    source_id: str,
    limits: PublicReferenceMaterializationLimits,
) -> AllAtomSystem:
    parser_limits = SDFParserLimits(
        max_bytes=limits.max_record_bytes,
        max_lines=100_000,
        max_atoms=limits.max_atoms,
        max_bonds=limits.max_bonds,
    )
    return parse_sdf_v2000(
        record.molblock_bytes,
        source_id=source_id,
        limits=parser_limits,
        dtype=torch.float64,
        device="cpu",
    )


AtomLabel = tuple[int, int, int, bool]
DirectedEdgeLabel = tuple[str, bool, int, int]


@dataclass(frozen=True, slots=True)
class _LabeledGraph:
    atom_labels: tuple[AtomLabel, ...]
    adjacency: tuple[Mapping[int, DirectedEdgeLabel], ...]
    edge_count: int
    ordered_sha256: str

    @property
    def atom_count(self) -> int:
        return len(self.atom_labels)


def _bond_directional_label(bond: object, source: int) -> DirectedEdgeLabel:
    order = float(getattr(bond, "order"))
    aromatic = bool(getattr(bond, "aromatic"))
    stereo_name = str(getattr(bond, "stereo", "none")).strip().lower()
    metadata = dict(getattr(bond, "metadata", {}))
    raw_code = metadata.get("v2000_stereo_code", _STEREO_CODE_BY_NAME.get(stereo_name))
    if isinstance(raw_code, bool) or not isinstance(raw_code, Integral):
        raise PublicReferenceMaterializationError(
            "V2000 stereo code is unavailable for graph materialization"
        )
    stereo_code = int(raw_code)
    if stereo_code not in {0, 1, 4, 6}:
        raise PublicReferenceMaterializationError(
            "unsupported V2000 stereo code in graph materialization"
        )
    direction = 0
    if stereo_code != 0:
        raw_first = metadata.get("v2000_source_atom_i")
        raw_second = metadata.get("v2000_source_atom_j")
        if isinstance(raw_first, bool) or isinstance(raw_second, bool) or not isinstance(
            raw_first, Integral
        ) or not isinstance(raw_second, Integral):
            raise PublicReferenceMaterializationError(
                "directional V2000 stereo metadata is missing"
            )
        if source == int(raw_first):
            direction = 1
        elif source == int(raw_second):
            direction = -1
        else:
            raise PublicReferenceMaterializationError(
                "directional V2000 stereo metadata is inconsistent"
            )
    return order.hex(), aromatic, stereo_code, direction


def _labeled_graph(system: AllAtomSystem) -> _LabeledGraph:
    labels: tuple[AtomLabel, ...] = tuple(
        (
            int(atom.atomic_number),
            int(atom.formal_charge),
            0 if atom.isotope_mass_number is None else int(atom.isotope_mass_number),
            bool(atom.aromatic),
        )
        for atom in system.atoms
    )
    adjacency: list[dict[int, DirectedEdgeLabel]] = [
        {} for _ in range(system.atom_count)
    ]
    ordered_bonds: list[dict[str, object]] = []
    for bond in system.bonds:
        first = int(bond.atom_i)
        second = int(bond.atom_j)
        forward = _bond_directional_label(bond, first)
        reverse = _bond_directional_label(bond, second)
        adjacency[first][second] = forward
        adjacency[second][first] = reverse
        ordered_bonds.append(
            {
                "atom_i": first,
                "atom_j": second,
                "forward_label": list(forward),
                "reverse_label": list(reverse),
            }
        )
    payload = {
        "atom_labels": [list(label) for label in labels],
        "bonds": ordered_bonds,
        "identity_policy": (
            "atomic_number_formal_charge_isotope_aromatic_and_directional_"
            "v2000_bond_order_aromatic_stereo"
        ),
    }
    return _LabeledGraph(
        atom_labels=labels,
        adjacency=tuple(adjacency),
        edge_count=len(system.bonds),
        ordered_sha256=_canonical_sha256(payload),
    )


def _refined_colors(graph: _LabeledGraph) -> tuple[str, ...]:
    colors = tuple(
        _canonical_sha256({"atom_label": list(label)})
        for label in graph.atom_labels
    )
    for _ in range(max(1, graph.atom_count)):
        next_colors = tuple(
            _canonical_sha256(
                {
                    "self": colors[index],
                    "neighbors": sorted(
                        [*edge_label, colors[neighbor]]
                        for neighbor, edge_label in graph.adjacency[index].items()
                    ),
                }
            )
            for index in range(graph.atom_count)
        )
        colors = next_colors
    return colors


def _graph_isomorphisms(
    source: _LabeledGraph,
    target: _LabeledGraph,
    *,
    max_mappings: int,
    max_search_states: int,
) -> tuple[tuple[int, ...], ...]:
    if source.atom_count != target.atom_count or source.edge_count != target.edge_count:
        return ()
    if Counter(source.atom_labels) != Counter(target.atom_labels):
        return ()
    source_colors = _refined_colors(source)
    target_colors = _refined_colors(target)
    if Counter(source_colors) != Counter(target_colors):
        return ()
    candidates = tuple(
        tuple(
            target_index
            for target_index, target_color in enumerate(target_colors)
            if target_color == source_colors[source_index]
        )
        for source_index in range(source.atom_count)
    )
    if any(not row for row in candidates):
        return ()
    source_order = tuple(
        sorted(
            range(source.atom_count),
            key=lambda index: (
                len(candidates[index]),
                -len(source.adjacency[index]),
                index,
            ),
        )
    )
    mapping = [-1] * source.atom_count
    used = [False] * target.atom_count
    results: list[tuple[int, ...]] = []
    state_count = 0

    def compatible(source_index: int, target_index: int) -> bool:
        if len(source.adjacency[source_index]) != len(target.adjacency[target_index]):
            return False
        for mapped_source, mapped_target in enumerate(mapping):
            if mapped_target < 0:
                continue
            source_edge = source.adjacency[source_index].get(mapped_source)
            target_edge = target.adjacency[target_index].get(mapped_target)
            if source_edge != target_edge:
                return False
        return True

    def visit(depth: int) -> None:
        nonlocal state_count
        state_count += 1
        if state_count > max_search_states:
            raise PublicReferenceMaterializationError(
                "labeled graph search state capacity exceeded"
            )
        if depth == source.atom_count:
            results.append(tuple(mapping))
            if len(results) > max_mappings:
                raise PublicReferenceMaterializationError(
                    "labeled graph mapping capacity exceeded"
                )
            return
        source_index = source_order[depth]
        for target_index in candidates[source_index]:
            if used[target_index] or not compatible(source_index, target_index):
                continue
            mapping[source_index] = target_index
            used[target_index] = True
            visit(depth + 1)
            used[target_index] = False
            mapping[source_index] = -1

    visit(0)
    return tuple(sorted(results))


@dataclass(frozen=True, slots=True)
class PublicReferenceRecordRow:
    record_index: int
    record_sha256: str
    source_title: str
    status: str
    atom_count: int
    bond_count: int
    ordered_graph_sha256: str
    isomorphism_count: int
    error_code: str = ""
    schema_id: str = PUBLIC_REFERENCE_RECORD_ROW_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_REFERENCE_RECORD_ROW_SCHEMA_ID:
            raise PublicReferenceMaterializationError(
                "unsupported public reference record-row schema"
            )
        object.__setattr__(
            self,
            "record_index",
            _exact_int(self.record_index, name="record_index"),
        )
        object.__setattr__(
            self,
            "record_sha256",
            _digest(self.record_sha256, name="record_sha256"),
        )
        if self.status not in _RECORD_STATUSES:
            raise PublicReferenceMaterializationError(
                "unsupported public reference record disposition"
            )
        for name in ("atom_count", "bond_count", "isomorphism_count"):
            object.__setattr__(
                self,
                name,
                _exact_int(getattr(self, name), name=name),
            )
        object.__setattr__(
            self,
            "ordered_graph_sha256",
            _digest(
                self.ordered_graph_sha256,
                name="ordered_graph_sha256",
                allow_empty=True,
            ),
        )
        object.__setattr__(self, "source_title", str(self.source_title))
        object.__setattr__(self, "error_code", str(self.error_code))
        if self.status == "selected_graph_match" and (
            self.isomorphism_count < 1 or not self.ordered_graph_sha256
        ):
            raise PublicReferenceMaterializationError(
                "selected reference rows require graph mappings"
            )
        if self.status == "rejected_graph_mismatch" and (
            self.isomorphism_count != 0 or not self.ordered_graph_sha256
        ):
            raise PublicReferenceMaterializationError(
                "graph-mismatch rows have inconsistent graph evidence"
            )
        if (self.status in _FAILURE_STATUSES) != bool(self.error_code):
            raise PublicReferenceMaterializationError(
                "record failure disposition and error_code disagree"
            )

    @property
    def failed(self) -> bool:
        return self.status in _FAILURE_STATUSES

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "record_index": self.record_index,
            "record_sha256": self.record_sha256,
            "source_title": self.source_title,
            "status": self.status,
            "atom_count": self.atom_count,
            "bond_count": self.bond_count,
            "ordered_graph_sha256": self.ordered_graph_sha256,
            "isomorphism_count": self.isomorphism_count,
            "error_code": self.error_code,
        }

    @classmethod
    def from_dict(cls, value: object) -> "PublicReferenceRecordRow":
        expected = {
            "schema_id",
            "record_index",
            "record_sha256",
            "source_title",
            "status",
            "atom_count",
            "bond_count",
            "ordered_graph_sha256",
            "isomorphism_count",
            "error_code",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise PublicReferenceMaterializationError(
                "public reference record-row payload is invalid"
            )
        result = cls(**{name: value[name] for name in expected})
        if result.to_dict() != dict(value):
            raise PublicReferenceMaterializationError(
                "public reference record-row payload is not canonical"
            )
        return result


@dataclass(frozen=True, slots=True)
class PublicReferencePose:
    record_index: int
    record_sha256: str
    source_title: str
    atom_count: int
    seed_to_reference_atom_mapping: tuple[int, ...]
    isomorphism_count: int
    reference_coordinates_seed_heavy_order: torch.Tensor
    ordered_graph_sha256: str
    schema_id: str = PUBLIC_REFERENCE_POSE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_REFERENCE_POSE_SCHEMA_ID:
            raise PublicReferenceMaterializationError(
                "unsupported public reference-pose schema"
            )
        atom_count = _exact_int(self.atom_count, name="atom_count", minimum=1)
        mapping = tuple(
            _exact_int(value, name="seed_to_reference_atom_mapping")
            for value in self.seed_to_reference_atom_mapping
        )
        if len(mapping) != atom_count or sorted(mapping) != list(range(atom_count)):
            raise PublicReferenceMaterializationError(
                "seed_to_reference_atom_mapping must be a full atom bijection"
            )
        coordinates = self.reference_coordinates_seed_heavy_order
        if (
            not isinstance(coordinates, torch.Tensor)
            or coordinates.ndim != 2
            or coordinates.shape[-1] != 3
            or coordinates.shape[0] < 1
            or coordinates.shape[0] > atom_count
            or coordinates.dtype != torch.float64
            or coordinates.device.type != "cpu"
            or not bool(torch.isfinite(coordinates).all().item())
        ):
            raise PublicReferenceMaterializationError(
                "reference pose coordinates must be finite CPU float64 [H,3]"
            )
        object.__setattr__(self, "atom_count", atom_count)
        object.__setattr__(self, "seed_to_reference_atom_mapping", mapping)
        object.__setattr__(
            self,
            "record_index",
            _exact_int(self.record_index, name="record_index"),
        )
        object.__setattr__(
            self,
            "record_sha256",
            _digest(self.record_sha256, name="record_sha256"),
        )
        object.__setattr__(
            self,
            "ordered_graph_sha256",
            _digest(self.ordered_graph_sha256, name="ordered_graph_sha256"),
        )
        object.__setattr__(
            self,
            "isomorphism_count",
            _exact_int(self.isomorphism_count, name="isomorphism_count", minimum=1),
        )
        object.__setattr__(self, "source_title", str(self.source_title))
        object.__setattr__(self, "reference_coordinates_seed_heavy_order", coordinates.detach().clone())

    @property
    def heavy_atom_count(self) -> int:
        return int(self.reference_coordinates_seed_heavy_order.shape[0])

    @property
    def coordinate_sha256(self) -> str:
        return _canonical_sha256(
            _tensor_hex_rows(self.reference_coordinates_seed_heavy_order)
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "record_index": self.record_index,
            "record_sha256": self.record_sha256,
            "source_title": self.source_title,
            "atom_count": self.atom_count,
            "heavy_atom_count": self.heavy_atom_count,
            "seed_to_reference_atom_mapping": list(
                self.seed_to_reference_atom_mapping
            ),
            "isomorphism_count": self.isomorphism_count,
            "ordered_graph_sha256": self.ordered_graph_sha256,
            "reference_coordinates_seed_heavy_order_hex": _tensor_hex_rows(
                self.reference_coordinates_seed_heavy_order
            ),
            "coordinate_sha256": self.coordinate_sha256,
        }

    @classmethod
    def from_dict(cls, value: object) -> "PublicReferencePose":
        expected = {
            "schema_id",
            "record_index",
            "record_sha256",
            "source_title",
            "atom_count",
            "heavy_atom_count",
            "seed_to_reference_atom_mapping",
            "isomorphism_count",
            "ordered_graph_sha256",
            "reference_coordinates_seed_heavy_order_hex",
            "coordinate_sha256",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise PublicReferenceMaterializationError(
                "public reference-pose payload is invalid"
            )
        raw_mapping = value["seed_to_reference_atom_mapping"]
        if not isinstance(raw_mapping, list):
            raise PublicReferenceMaterializationError(
                "reference-pose mapping payload must be a list"
            )
        result = cls(
            record_index=value["record_index"],
            record_sha256=value["record_sha256"],
            source_title=value["source_title"],
            atom_count=value["atom_count"],
            seed_to_reference_atom_mapping=tuple(raw_mapping),
            isomorphism_count=value["isomorphism_count"],
            ordered_graph_sha256=value["ordered_graph_sha256"],
            reference_coordinates_seed_heavy_order=_tensor_from_hex_rows(
                value["reference_coordinates_seed_heavy_order_hex"],
                name="reference_coordinates_seed_heavy_order_hex",
            ),
            schema_id=value["schema_id"],
        )
        if value["heavy_atom_count"] != result.heavy_atom_count:
            raise PublicReferenceMaterializationError(
                "reference-pose heavy atom count is inconsistent"
            )
        if value["coordinate_sha256"] != result.coordinate_sha256:
            raise PublicReferenceMaterializationError(
                "reference-pose coordinate SHA-256 is inconsistent"
            )
        if result.to_dict() != dict(value):
            raise PublicReferenceMaterializationError(
                "public reference-pose payload is not canonical"
            )
        return result


@dataclass(frozen=True, slots=True)
class PublicBenchmarkCaseMaterialization:
    protocol_sha256: str
    case_id: str
    case_input_sha256: str
    ligand_identity_seed_sha256: str
    reference_ligands_sha256: str
    limits: PublicReferenceMaterializationLimits
    seed_atom_count: int
    seed_heavy_atom_indices: tuple[int, ...]
    seed_ordered_graph_sha256: str
    symmetry_permutations_seed_heavy_order: tuple[tuple[int, ...], ...]
    record_rows: tuple[PublicReferenceRecordRow, ...]
    reference_poses: tuple[PublicReferencePose, ...]
    scientific_blockers: tuple[str, ...] = (
        PUBLIC_REFERENCE_MATERIALIZATION_SCIENTIFIC_BLOCKERS
    )
    schema_id: str = PUBLIC_REFERENCE_MATERIALIZATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_REFERENCE_MATERIALIZATION_SCHEMA_ID:
            raise PublicReferenceMaterializationError(
                "unsupported public reference materialization schema"
            )
        for name in (
            "protocol_sha256",
            "case_input_sha256",
            "ligand_identity_seed_sha256",
            "reference_ligands_sha256",
            "seed_ordered_graph_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if not isinstance(self.case_id, str) or not self.case_id.strip():
            raise PublicReferenceMaterializationError("case_id must be non-empty")
        object.__setattr__(self, "case_id", self.case_id.strip())
        if not isinstance(self.limits, PublicReferenceMaterializationLimits):
            raise PublicReferenceMaterializationError(
                "limits must be PublicReferenceMaterializationLimits"
            )
        atom_count = _exact_int(
            self.seed_atom_count,
            name="seed_atom_count",
            minimum=1,
            maximum=self.limits.max_atoms,
        )
        heavy = tuple(
            _exact_int(value, name="seed_heavy_atom_indices")
            for value in self.seed_heavy_atom_indices
        )
        if not heavy or tuple(sorted(set(heavy))) != heavy or heavy[-1] >= atom_count:
            raise PublicReferenceMaterializationError(
                "seed_heavy_atom_indices must be a sorted non-empty atom subset"
            )
        permutations = tuple(
            tuple(
                _exact_int(value, name="symmetry permutation")
                for value in permutation
            )
            for permutation in self.symmetry_permutations_seed_heavy_order
        )
        identity = tuple(range(len(heavy)))
        if (
            not permutations
            or len(permutations) > self.limits.max_symmetry_permutations
            or tuple(sorted(set(permutations))) != permutations
            or permutations[0] != identity
            or any(sorted(permutation) != list(identity) for permutation in permutations)
        ):
            raise PublicReferenceMaterializationError(
                "symmetry permutations must be sorted unique heavy-atom bijections"
            )
        rows = tuple(self.record_rows)
        poses = tuple(self.reference_poses)
        if not rows or any(
            row.record_index != index for index, row in enumerate(rows)
        ):
            raise PublicReferenceMaterializationError(
                "public reference record rows must be contiguous and ordered"
            )
        selected_indices = {
            row.record_index
            for row in rows
            if row.status == "selected_graph_match"
        }
        pose_indices = {pose.record_index for pose in poses}
        if selected_indices != pose_indices or len(poses) != len(pose_indices):
            raise PublicReferenceMaterializationError(
                "selected record rows and reference poses disagree"
            )
        if tuple(pose.record_index for pose in poses) != tuple(
            sorted(selected_indices)
        ):
            raise PublicReferenceMaterializationError(
                "public reference poses must follow selected record order"
            )
        rows_by_index = {row.record_index: row for row in rows}
        for pose in poses:
            row = rows_by_index[pose.record_index]
            if (
                pose.record_sha256 != row.record_sha256
                or pose.source_title != row.source_title
                or pose.atom_count != row.atom_count
                or pose.ordered_graph_sha256 != row.ordered_graph_sha256
                or pose.isomorphism_count != row.isomorphism_count
            ):
                raise PublicReferenceMaterializationError(
                    "public reference pose is cross-wired from its record row"
                )
        if any(
            pose.atom_count != atom_count or pose.heavy_atom_count != len(heavy)
            for pose in poses
        ):
            raise PublicReferenceMaterializationError(
                "reference-pose atom dimensions disagree with the seed"
            )
        if tuple(self.scientific_blockers) != (
            PUBLIC_REFERENCE_MATERIALIZATION_SCIENTIFIC_BLOCKERS
        ):
            raise PublicReferenceMaterializationError(
                "public reference scientific blockers cannot be promoted"
            )
        object.__setattr__(self, "seed_atom_count", atom_count)
        object.__setattr__(self, "seed_heavy_atom_indices", heavy)
        object.__setattr__(
            self,
            "symmetry_permutations_seed_heavy_order",
            permutations,
        )
        object.__setattr__(self, "record_rows", rows)
        object.__setattr__(self, "reference_poses", poses)

    @property
    def failed_record_indices(self) -> tuple[int, ...]:
        return tuple(row.record_index for row in self.record_rows if row.failed)

    @property
    def ready_for_rmsd(self) -> bool:
        return bool(self.reference_poses and not self.failed_record_indices)

    @property
    def claim_safe(self) -> bool:
        return False

    def _payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": PUBLIC_REFERENCE_MATERIALIZATION_ALGORITHM_ID,
            "protocol_sha256": self.protocol_sha256,
            "case_id": self.case_id,
            "case_input_sha256": self.case_input_sha256,
            "ligand_identity_seed_sha256": self.ligand_identity_seed_sha256,
            "reference_ligands_sha256": self.reference_ligands_sha256,
            "limits": self.limits.to_dict(),
            "limits_fingerprint_sha256": self.limits.fingerprint_sha256,
            "seed_atom_count": self.seed_atom_count,
            "seed_heavy_atom_indices": list(self.seed_heavy_atom_indices),
            "seed_ordered_graph_sha256": self.seed_ordered_graph_sha256,
            "ligand_identity_seed_coordinates_used": False,
            "graph_identity_policy": (
                "atomic_number_formal_charge_isotope_aromatic_and_directional_"
                "v2000_bond_order_aromatic_stereo"
            ),
            "symmetry_permutations_seed_heavy_order": [
                list(permutation)
                for permutation in self.symmetry_permutations_seed_heavy_order
            ],
            "reference_selection_policy": (
                "all_reference_records_matching_seed_labeled_graph_identity"
            ),
            "rmsd_alignment_policy": "direct_receptor_frame_no_ligand_alignment",
            "reference_pose_aggregation": (
                "minimum_across_all_matched_records_and_symmetry_permutations"
            ),
            "record_rows": [row.to_dict() for row in self.record_rows],
            "reference_poses": [pose.to_dict() for pose in self.reference_poses],
            "failed_record_indices": list(self.failed_record_indices),
            "ready_for_rmsd": self.ready_for_rmsd,
            "scientific_blockers": list(self.scientific_blockers),
            "scientifically_validated": False,
            "benchmark_validated": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self._payload())

    def to_dict(self) -> dict[str, object]:
        return {
            **self._payload(),
            "materialization_sha256": self.fingerprint_sha256,
        }

    def to_json_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict()) + b"\n"

    @classmethod
    def from_json_bytes(cls, source: bytes) -> "PublicBenchmarkCaseMaterialization":
        if not isinstance(source, bytes):
            raise TypeError("public reference receipt source must be bytes")
        if len(source) < 1 or len(source) > MAX_PUBLIC_REFERENCE_RECEIPT_BYTES:
            raise PublicReferenceMaterializationError(
                "public reference receipt size is outside the configured bound"
            )
        try:
            value = json.loads(source.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PublicReferenceMaterializationError(
                "public reference receipt is not canonical JSON"
            ) from exc
        expected = {
            "schema_id",
            "algorithm_id",
            "protocol_sha256",
            "case_id",
            "case_input_sha256",
            "ligand_identity_seed_sha256",
            "reference_ligands_sha256",
            "limits",
            "limits_fingerprint_sha256",
            "seed_atom_count",
            "seed_heavy_atom_indices",
            "seed_ordered_graph_sha256",
            "ligand_identity_seed_coordinates_used",
            "graph_identity_policy",
            "symmetry_permutations_seed_heavy_order",
            "reference_selection_policy",
            "rmsd_alignment_policy",
            "reference_pose_aggregation",
            "record_rows",
            "reference_poses",
            "failed_record_indices",
            "ready_for_rmsd",
            "scientific_blockers",
            "scientifically_validated",
            "benchmark_validated",
            "customer_execution_enabled",
            "claim_safe",
            "materialization_sha256",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise PublicReferenceMaterializationError(
                "public reference receipt payload is invalid"
            )
        if value["algorithm_id"] != PUBLIC_REFERENCE_MATERIALIZATION_ALGORITHM_ID:
            raise PublicReferenceMaterializationError(
                "unsupported public reference materialization algorithm"
            )
        raw_heavy = value["seed_heavy_atom_indices"]
        raw_permutations = value["symmetry_permutations_seed_heavy_order"]
        raw_rows = value["record_rows"]
        raw_poses = value["reference_poses"]
        if not all(
            isinstance(item, list)
            for item in (raw_heavy, raw_permutations, raw_rows, raw_poses)
        ):
            raise PublicReferenceMaterializationError(
                "public reference receipt collection payload is invalid"
            )
        result = cls(
            protocol_sha256=value["protocol_sha256"],
            case_id=value["case_id"],
            case_input_sha256=value["case_input_sha256"],
            ligand_identity_seed_sha256=value["ligand_identity_seed_sha256"],
            reference_ligands_sha256=value["reference_ligands_sha256"],
            limits=PublicReferenceMaterializationLimits.from_dict(value["limits"]),
            seed_atom_count=value["seed_atom_count"],
            seed_heavy_atom_indices=tuple(raw_heavy),
            seed_ordered_graph_sha256=value["seed_ordered_graph_sha256"],
            symmetry_permutations_seed_heavy_order=tuple(
                tuple(permutation) for permutation in raw_permutations
            ),
            record_rows=tuple(
                PublicReferenceRecordRow.from_dict(row) for row in raw_rows
            ),
            reference_poses=tuple(
                PublicReferencePose.from_dict(pose) for pose in raw_poses
            ),
            scientific_blockers=tuple(value["scientific_blockers"]),
            schema_id=value["schema_id"],
        )
        canonical = result.to_dict()
        if canonical != dict(value) or result.to_json_bytes() != source:
            raise PublicReferenceMaterializationError(
                "public reference receipt is not canonical or is inconsistent"
            )
        return result


def materialize_public_benchmark_case(
    case: PublicBenchmarkCaseDefinition,
    ligand_identity_seed_bytes: bytes,
    reference_ligands_bytes: bytes,
    *,
    protocol_sha256: str,
    limits: PublicReferenceMaterializationLimits | None = None,
) -> PublicBenchmarkCaseMaterialization:
    """Materialize all graph-matched public reference poses for one case."""

    if not isinstance(case, PublicBenchmarkCaseDefinition):
        raise PublicReferenceMaterializationError(
            "case must be PublicBenchmarkCaseDefinition"
        )
    active = PublicReferenceMaterializationLimits() if limits is None else limits
    if not isinstance(active, PublicReferenceMaterializationLimits):
        raise PublicReferenceMaterializationError(
            "limits must be PublicReferenceMaterializationLimits"
        )
    protocol_digest = _digest(protocol_sha256, name="protocol_sha256")
    try:
        case.ligand_identity_seed.verify_bytes(ligand_identity_seed_bytes)
        case.reference_ligands.verify_bytes(reference_ligands_bytes)
    except PublicBenchmarkProtocolError as exc:
        raise PublicReferenceMaterializationError(
            "public reference artifact identity verification failed"
        ) from exc
    seed_records = _split_sdf_records(
        ligand_identity_seed_bytes,
        limits=active,
    )
    if len(seed_records) != 1:
        raise PublicReferenceMaterializationError(
            "ligand identity seed must contain exactly one SDF record"
        )
    try:
        seed_system = _parse_record(
            seed_records[0],
            source_id=f"{case.case_id}:identity-seed",
            limits=active,
        )
    except SDFParseError as exc:
        raise PublicReferenceMaterializationError(
            "ligand identity seed is outside the bounded V2000 parser"
        ) from exc
    seed_graph = _labeled_graph(seed_system)
    automorphisms = _graph_isomorphisms(
        seed_graph,
        seed_graph,
        max_mappings=active.max_symmetry_permutations,
        max_search_states=active.max_graph_search_states,
    )
    if not automorphisms:
        raise PublicReferenceMaterializationError(
            "ligand identity seed did not reproduce its own labeled graph"
        )
    heavy_indices = tuple(
        atom.index for atom in seed_system.atoms if atom.atomic_number != 1
    )
    if not heavy_indices:
        raise PublicReferenceMaterializationError(
            "ligand identity seed contains no heavy atoms"
        )
    heavy_position = {
        atom_index: position for position, atom_index in enumerate(heavy_indices)
    }
    heavy_permutations = tuple(
        sorted(
            {
                tuple(heavy_position[mapping[index]] for index in heavy_indices)
                for mapping in automorphisms
            }
        )
    )
    reference_records = _split_sdf_records(
        reference_ligands_bytes,
        limits=active,
    )
    rows: list[PublicReferenceRecordRow] = []
    poses: list[PublicReferencePose] = []
    for record in reference_records:
        try:
            system = _parse_record(
                record,
                source_id=f"{case.case_id}:reference:{record.index}",
                limits=active,
            )
        except SDFParseError:
            rows.append(
                PublicReferenceRecordRow(
                    record_index=record.index,
                    record_sha256=record.sha256,
                    source_title=record.source_title,
                    status="failure_parse",
                    atom_count=0,
                    bond_count=0,
                    ordered_graph_sha256="",
                    isomorphism_count=0,
                    error_code="SDFParseError",
                )
            )
            continue
        graph = _labeled_graph(system)
        try:
            mappings = _graph_isomorphisms(
                seed_graph,
                graph,
                max_mappings=active.max_symmetry_permutations,
                max_search_states=active.max_graph_search_states,
            )
        except PublicReferenceMaterializationError:
            rows.append(
                PublicReferenceRecordRow(
                    record_index=record.index,
                    record_sha256=record.sha256,
                    source_title=record.source_title,
                    status="failure_graph_search",
                    atom_count=system.atom_count,
                    bond_count=len(system.bonds),
                    ordered_graph_sha256=graph.ordered_sha256,
                    isomorphism_count=0,
                    error_code="GraphSearchCapacityError",
                )
            )
            continue
        if not mappings:
            rows.append(
                PublicReferenceRecordRow(
                    record_index=record.index,
                    record_sha256=record.sha256,
                    source_title=record.source_title,
                    status="rejected_graph_mismatch",
                    atom_count=system.atom_count,
                    bond_count=len(system.bonds),
                    ordered_graph_sha256=graph.ordered_sha256,
                    isomorphism_count=0,
                )
            )
            continue
        canonical_mapping = min(mappings)
        coordinate_indices = torch.tensor(
            [canonical_mapping[index] for index in heavy_indices],
            dtype=torch.long,
            device="cpu",
        )
        reference_coordinates = system.coordinates[0].index_select(
            0,
            coordinate_indices,
        )
        rows.append(
            PublicReferenceRecordRow(
                record_index=record.index,
                record_sha256=record.sha256,
                source_title=record.source_title,
                status="selected_graph_match",
                atom_count=system.atom_count,
                bond_count=len(system.bonds),
                ordered_graph_sha256=graph.ordered_sha256,
                isomorphism_count=len(mappings),
            )
        )
        poses.append(
            PublicReferencePose(
                record_index=record.index,
                record_sha256=record.sha256,
                source_title=record.source_title,
                atom_count=system.atom_count,
                seed_to_reference_atom_mapping=canonical_mapping,
                isomorphism_count=len(mappings),
                reference_coordinates_seed_heavy_order=reference_coordinates,
                ordered_graph_sha256=graph.ordered_sha256,
            )
        )
    return PublicBenchmarkCaseMaterialization(
        protocol_sha256=protocol_digest,
        case_id=case.case_id,
        case_input_sha256=case.input_sha256,
        ligand_identity_seed_sha256=case.ligand_identity_seed.sha256,
        reference_ligands_sha256=case.reference_ligands.sha256,
        limits=active,
        seed_atom_count=seed_system.atom_count,
        seed_heavy_atom_indices=heavy_indices,
        seed_ordered_graph_sha256=seed_graph.ordered_sha256,
        symmetry_permutations_seed_heavy_order=heavy_permutations,
        record_rows=tuple(rows),
        reference_poses=tuple(poses),
    )


def materialize_frozen_public_benchmark_case(
    case_id: str,
    ligand_identity_seed_bytes: bytes,
    reference_ligands_bytes: bytes,
    *,
    limits: PublicReferenceMaterializationLimits | None = None,
) -> PublicBenchmarkCaseMaterialization:
    """Materialize one case from the exact frozen public protocol."""

    protocol = frozen_public_benchmark_protocol()
    matches = [case for case in protocol.cases if case.case_id == case_id]
    if len(matches) != 1:
        raise PublicReferenceMaterializationError(
            "case_id is not present exactly once in the frozen public protocol"
        )
    return materialize_public_benchmark_case(
        matches[0],
        ligand_identity_seed_bytes,
        reference_ligands_bytes,
        protocol_sha256=protocol.protocol_sha256,
        limits=limits,
    )


@dataclass(frozen=True, slots=True)
class PublicReferenceRMSDResult:
    rmsd_angstrom: float
    reference_record_index: int
    symmetry_permutation_index: int
    evaluated_reference_pose_count: int
    evaluated_symmetry_permutation_count: int
    materialization_sha256: str
    candidate_coordinates_seed_order_sha256: str
    schema_id: str = PUBLIC_REFERENCE_RMSD_RESULT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_REFERENCE_RMSD_RESULT_SCHEMA_ID:
            raise PublicReferenceMaterializationError(
                "unsupported public reference RMSD-result schema"
            )
        value = float(self.rmsd_angstrom)
        if not math.isfinite(value) or value < 0.0:
            raise PublicReferenceMaterializationError(
                "public reference RMSD must be finite and non-negative"
            )
        object.__setattr__(self, "rmsd_angstrom", value)
        for name, minimum in (
            ("reference_record_index", 0),
            ("symmetry_permutation_index", 0),
            ("evaluated_reference_pose_count", 1),
            ("evaluated_symmetry_permutation_count", 1),
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(getattr(self, name), name=name, minimum=minimum),
            )
        object.__setattr__(
            self,
            "materialization_sha256",
            _digest(self.materialization_sha256, name="materialization_sha256"),
        )
        object.__setattr__(
            self,
            "candidate_coordinates_seed_order_sha256",
            _digest(
                self.candidate_coordinates_seed_order_sha256,
                name="candidate_coordinates_seed_order_sha256",
            ),
        )

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "rmsd_angstrom": self.rmsd_angstrom,
            "reference_record_index": self.reference_record_index,
            "symmetry_permutation_index": self.symmetry_permutation_index,
            "evaluated_reference_pose_count": self.evaluated_reference_pose_count,
            "evaluated_symmetry_permutation_count": (
                self.evaluated_symmetry_permutation_count
            ),
            "materialization_sha256": self.materialization_sha256,
            "candidate_coordinates_seed_order_sha256": (
                self.candidate_coordinates_seed_order_sha256
            ),
            "alignment_policy": "direct_receptor_frame_no_ligand_alignment",
            "claim_safe": False,
        }


def minimum_public_reference_rmsd(
    materialization: PublicBenchmarkCaseMaterialization,
    candidate_coordinates_seed_order: torch.Tensor,
) -> PublicReferenceRMSDResult:
    """Return minimum direct receptor-frame RMSD over all admitted references."""

    if not isinstance(materialization, PublicBenchmarkCaseMaterialization):
        raise PublicReferenceMaterializationError(
            "materialization type is invalid"
        )
    if not materialization.ready_for_rmsd:
        raise PublicReferenceMaterializationError(
            "materialization is not ready for RMSD evaluation"
        )
    candidate = candidate_coordinates_seed_order
    if (
        not isinstance(candidate, torch.Tensor)
        or candidate.shape != (materialization.seed_atom_count, 3)
        or not candidate.is_floating_point()
        or not bool(torch.isfinite(candidate).all().item())
    ):
        raise PublicReferenceMaterializationError(
            "candidate coordinates must be finite [seed_atom_count,3]"
        )
    candidate = candidate.detach().to(dtype=torch.float64, device="cpu")
    heavy_index = torch.tensor(
        materialization.seed_heavy_atom_indices,
        dtype=torch.long,
        device="cpu",
    )
    candidate_heavy = candidate.index_select(0, heavy_index)
    permutations = materialization.symmetry_permutations_seed_heavy_order
    best: tuple[float, int, int] | None = None
    for pose in materialization.reference_poses:
        reference = pose.reference_coordinates_seed_heavy_order
        for permutation_index, permutation in enumerate(permutations):
            mapping = torch.tensor(permutation, dtype=torch.long, device="cpu")
            permuted = candidate_heavy.index_select(0, mapping)
            value = float(
                torch.sqrt(
                    (reference - permuted).square().sum(dim=-1).mean()
                ).item()
            )
            row = (value, pose.record_index, permutation_index)
            if best is None or row < best:
                best = row
    if best is None:
        raise PublicReferenceMaterializationError(
            "materialization contained no evaluable reference pose"
        )
    return PublicReferenceRMSDResult(
        rmsd_angstrom=best[0],
        reference_record_index=best[1],
        symmetry_permutation_index=best[2],
        evaluated_reference_pose_count=len(materialization.reference_poses),
        evaluated_symmetry_permutation_count=len(permutations),
        materialization_sha256=materialization.fingerprint_sha256,
        candidate_coordinates_seed_order_sha256=_canonical_sha256(
            _tensor_hex_rows(candidate)
        ),
    )


__all__ = [
    "MAX_PUBLIC_REFERENCE_ARTIFACT_BYTES",
    "MAX_PUBLIC_REFERENCE_ATOMS",
    "MAX_PUBLIC_REFERENCE_BONDS",
    "MAX_PUBLIC_REFERENCE_GRAPH_SEARCH_STATES",
    "MAX_PUBLIC_REFERENCE_RECEIPT_BYTES",
    "MAX_PUBLIC_REFERENCE_RECORD_BYTES",
    "MAX_PUBLIC_REFERENCE_RECORDS",
    "MAX_PUBLIC_REFERENCE_SYMMETRY_PERMUTATIONS",
    "PUBLIC_REFERENCE_MATERIALIZATION_ALGORITHM_ID",
    "PUBLIC_REFERENCE_MATERIALIZATION_SCHEMA_ID",
    "PUBLIC_REFERENCE_MATERIALIZATION_SCIENTIFIC_BLOCKERS",
    "PUBLIC_REFERENCE_POSE_SCHEMA_ID",
    "PUBLIC_REFERENCE_RECORD_ROW_SCHEMA_ID",
    "PUBLIC_REFERENCE_RMSD_RESULT_SCHEMA_ID",
    "PublicBenchmarkCaseMaterialization",
    "PublicReferenceMaterializationError",
    "PublicReferenceMaterializationLimits",
    "PublicReferencePose",
    "PublicReferenceRMSDResult",
    "PublicReferenceRecordRow",
    "materialize_frozen_public_benchmark_case",
    "materialize_public_benchmark_case",
    "minimum_public_reference_rmsd",
]
